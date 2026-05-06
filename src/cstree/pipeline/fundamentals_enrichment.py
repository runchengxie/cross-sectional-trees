from __future__ import annotations

import logging
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..data_interface import DataInterface
from ..data_tools.symbols import (
    DEFAULT_SYMBOL_PRIORITY,
    PROVIDER_SYMBOL_PRIORITY,
    normalize_symbol_standard_name,
)
from ..pit_feature_stats import (
    compute_calendar_cagr,
    compute_trailing_calendar_window_stat,
)
from .panel_join_support import frame_memory_mb, load_panel_join_frames, merge_panel_frame
from .support import _prepare_panel_join_frame

logger = logging.getLogger("cstree")


_SYMBOL_COLUMN_CANDIDATES = ("symbol", "ts_code", "stock_ticker", "order_book_id")


def _numeric_fundamental_series(fund_df: pd.DataFrame, name: str) -> pd.Series:
    if name not in fund_df.columns:
        return pd.Series(np.nan, index=fund_df.index, dtype=float)
    return pd.to_numeric(fund_df[name], errors="coerce")


def _safe_fundamental_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    valid_denominator = denominator.where(denominator.notna() & (denominator != 0))
    return (numerator / valid_denominator).replace([np.inf, -np.inf], np.nan)


def _needs_fundamental_feature(
    requested_feature_names: set[str],
    *feature_names: str,
) -> bool:
    return any(name in requested_feature_names for name in feature_names)


def _add_sales_field(fund_df: pd.DataFrame, requested_feature_names: set[str]) -> None:
    if not _needs_fundamental_feature(
        requested_feature_names,
        "sales",
        "delta_sales",
        "growth_sales",
        "profit_margin",
        "operating_margin",
        "cfo_margin",
        "sales_cagr_3y",
    ):
        return
    revenue = _numeric_fundamental_series(fund_df, "revenue")
    operating_revenue = _numeric_fundamental_series(fund_df, "operating_revenue")
    fund_df["sales"] = revenue.combine_first(operating_revenue)


def _add_debt_field(fund_df: pd.DataFrame, requested_feature_names: set[str]) -> None:
    if not _needs_fundamental_feature(
        requested_feature_names,
        "debt",
        "delta_debt",
        "growth_debt",
        "debt_to_assets",
        "debt_to_equity",
        "net_debt_to_assets",
    ):
        return
    short_term_debt = _numeric_fundamental_series(fund_df, "short_term_debt")
    long_term_loans = _numeric_fundamental_series(fund_df, "long_term_loans")
    debt = short_term_debt.fillna(0.0) + long_term_loans.fillna(0.0)
    fund_df["debt"] = debt.where(~(short_term_debt.isna() & long_term_loans.isna()))


def _add_margin_fields(fund_df: pd.DataFrame, requested_feature_names: set[str]) -> None:
    if _needs_fundamental_feature(requested_feature_names, "profit_margin", "profit_margin_std_3y"):
        fund_df["profit_margin"] = _safe_fundamental_ratio(
            _numeric_fundamental_series(fund_df, "net_profit"),
            _numeric_fundamental_series(fund_df, "sales"),
        )
    if "operating_margin" in requested_feature_names:
        fund_df["operating_margin"] = _safe_fundamental_ratio(
            _numeric_fundamental_series(fund_df, "operating_profit"),
            _numeric_fundamental_series(fund_df, "sales"),
        )
    if _needs_fundamental_feature(requested_feature_names, "cfo_margin", "cfo_margin_avg_3y"):
        fund_df["cfo_margin"] = _safe_fundamental_ratio(
            _numeric_fundamental_series(fund_df, "cash_flow_from_operating_activities"),
            _numeric_fundamental_series(fund_df, "sales"),
        )
    if _needs_fundamental_feature(
        requested_feature_names,
        "cfo_to_profit",
        "cfo_to_profit_median_3y",
    ):
        fund_df["cfo_to_profit"] = _safe_fundamental_ratio(
            _numeric_fundamental_series(fund_df, "cash_flow_from_operating_activities"),
            _numeric_fundamental_series(fund_df, "net_profit"),
        )


def _add_delta_fields(fund_df: pd.DataFrame, requested_feature_names: set[str]) -> None:
    delta_base_features = sorted(
        {
            feat.removeprefix("delta_")
            for feat in requested_feature_names
            if feat.startswith("delta_")
        }
    )
    for base_feature in delta_base_features:
        if base_feature not in fund_df.columns:
            continue
        base_series = pd.to_numeric(fund_df[base_feature], errors="coerce")
        fund_df[f"delta_{base_feature}"] = base_series.groupby(fund_df["symbol"]).diff()


def _add_growth_fields(fund_df: pd.DataFrame, requested_feature_names: set[str]) -> None:
    growth_base_features = sorted(
        {
            feat.removeprefix("growth_")
            for feat in requested_feature_names
            if feat.startswith("growth_")
        }
    )
    for base_feature in growth_base_features:
        if base_feature not in fund_df.columns:
            continue
        current = pd.to_numeric(fund_df[base_feature], errors="coerce")
        previous = current.groupby(fund_df["symbol"]).shift()
        scale = ((current.abs() + previous.abs()) / 2.0).where(
            lambda values: values.notna() & (values != 0)
        )
        growth = (current - previous) / scale
        fund_df[f"growth_{base_feature}"] = growth.replace([np.inf, -np.inf], np.nan)


def _add_calendar_cagr_fields(fund_df: pd.DataFrame, requested_feature_names: set[str]) -> None:
    if "sales_cagr_3y" in requested_feature_names:
        fund_df["sales_cagr_3y"] = compute_calendar_cagr(fund_df, fund_df["sales"], years=3)
    if "eps_cagr_3y" in requested_feature_names:
        fund_df["eps_cagr_3y"] = compute_calendar_cagr(
            fund_df,
            _numeric_fundamental_series(fund_df, "basic_earnings_per_share"),
            years=3,
        )


def _add_trailing_window_fields(fund_df: pd.DataFrame, requested_feature_names: set[str]) -> None:
    specs = (
        ("cfo_margin_avg_3y", "cfo_margin", 3, "mean", 3),
        ("profit_margin_std_3y", "profit_margin", 3, "std", 3),
        ("cfo_to_profit_median_3y", "cfo_to_profit", 3, "median", 3),
        ("positive_cfo_ratio_3y", "cash_flow_from_operating_activities", 3, "positive_ratio", 3),
        ("positive_cfo_ratio_2y", "cash_flow_from_operating_activities", 2, "positive_ratio", 2),
        (
            "positive_cfo_ratio_3y_min2",
            "cash_flow_from_operating_activities",
            3,
            "positive_ratio",
            2,
        ),
    )
    for feature_name, source_name, years, stat, min_periods in specs:
        if feature_name not in requested_feature_names:
            continue
        source = (
            fund_df[source_name]
            if source_name in fund_df.columns
            else _numeric_fundamental_series(fund_df, source_name)
        )
        fund_df[feature_name] = compute_trailing_calendar_window_stat(
            fund_df,
            source,
            years=years,
            stat=stat,
            min_periods=min_periods,
        )


def _derive_requested_fundamental_fields(
    fund_df: pd.DataFrame,
    requested_feature_names: set[str],
) -> pd.DataFrame:
    fund_df = fund_df.copy()
    _add_sales_field(fund_df, requested_feature_names)
    _add_debt_field(fund_df, requested_feature_names)
    _add_margin_fields(fund_df, requested_feature_names)
    if "days_since_report" in requested_feature_names:
        fund_df["report_trade_date"] = fund_df["trade_date"]
    _add_delta_fields(fund_df, requested_feature_names)
    _add_growth_fields(fund_df, requested_feature_names)
    _add_calendar_cagr_fields(fund_df, requested_feature_names)
    _add_trailing_window_fields(fund_df, requested_feature_names)
    return fund_df


def _fundamental_source_fields(requested_feature_names: set[str]) -> set[str]:
    fields = set(requested_feature_names)
    for feature in list(requested_feature_names):
        if feature.startswith("delta_"):
            fields.add(feature.removeprefix("delta_"))
        if feature.startswith("growth_"):
            fields.add(feature.removeprefix("growth_"))

    if _needs_fundamental_feature(
        fields,
        "sales",
        "delta_sales",
        "growth_sales",
        "profit_margin",
        "operating_margin",
        "cfo_margin",
        "sales_cagr_3y",
        "profit_margin_std_3y",
        "cfo_margin_avg_3y",
    ):
        fields.update({"revenue", "operating_revenue"})
    if _needs_fundamental_feature(
        fields,
        "debt",
        "delta_debt",
        "growth_debt",
        "debt_to_assets",
        "debt_to_equity",
        "net_debt_to_assets",
    ):
        fields.update({"short_term_debt", "long_term_loans"})
    if _needs_fundamental_feature(fields, "profit_margin", "profit_margin_std_3y"):
        fields.add("net_profit")
    if "operating_margin" in fields:
        fields.add("operating_profit")
    if _needs_fundamental_feature(
        fields,
        "cfo_margin",
        "cfo_to_profit",
        "cfo_margin_avg_3y",
        "cfo_to_profit_median_3y",
        "positive_cfo_ratio_3y",
        "positive_cfo_ratio_2y",
        "positive_cfo_ratio_3y_min2",
    ):
        fields.add("cash_flow_from_operating_activities")
    if _needs_fundamental_feature(fields, "cfo_to_profit", "cfo_to_profit_median_3y"):
        fields.add("net_profit")
    if "eps_cagr_3y" in fields:
        fields.add("basic_earnings_per_share")
    return fields


def _source_column_candidates(
    canonical_columns: set[str],
    column_map: Mapping[str, Any] | None,
) -> list[str]:
    normalized_source_map: dict[str, list[str]] = {}
    column_map = column_map if isinstance(column_map, Mapping) else {}
    for standard, source in column_map.items():
        canonical = normalize_symbol_standard_name(str(standard))
        if not source:
            continue
        normalized_source_map.setdefault(canonical, []).append(str(source))

    candidates: list[str] = ["trade_date", "date", *_SYMBOL_COLUMN_CANDIDATES]
    for column in sorted(canonical_columns):
        if not column:
            continue
        candidates.append(column)
        candidates.extend(normalized_source_map.get(column, []))
    return list(dict.fromkeys(candidates))


def _string_set(value: object) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        text = value.strip()
        return {text} if text else set()
    try:
        values = list(value)  # type: ignore[arg-type]
    except TypeError:
        text = str(value).strip()
        return {text} if text else set()
    return {str(item).strip() for item in values if str(item).strip()}


def _post_map_columns(columns: set[str], column_map: Mapping[str, Any] | None) -> set[str]:
    out = set(columns)
    column_map = column_map if isinstance(column_map, Mapping) else {}
    for standard, source in column_map.items():
        if source and str(source) in columns:
            out.add(normalize_symbol_standard_name(str(standard)))
    return out


def _fundamentals_file_columns(
    *,
    fundamentals_cfg: Mapping[str, Any],
    requested_feature_names: set[str],
    fundamentals_mcap_col: str,
    fundamentals_log_mcap: bool,
) -> list[str]:
    configured_features = _string_set(fundamentals_cfg.get("features"))
    configured_fields = _string_set(fundamentals_cfg.get("fields"))
    source_fields = _fundamental_source_fields(
        set(requested_feature_names) | configured_features | configured_fields
    )
    if fundamentals_log_mcap and fundamentals_mcap_col:
        source_fields.add(fundamentals_mcap_col)
    return _source_column_candidates(source_fields, fundamentals_cfg.get("column_map"))


def _select_fundamentals_merge_columns(
    fund_df: pd.DataFrame,
    *,
    fundamentals_cfg: Mapping[str, Any],
    requested_feature_names: set[str],
    fundamentals_mcap_col: str,
    fundamentals_log_mcap: bool,
) -> pd.DataFrame:
    configured_features = _string_set(fundamentals_cfg.get("features"))
    configured_fields = _post_map_columns(
        _string_set(fundamentals_cfg.get("fields")),
        fundamentals_cfg.get("column_map"),
    )
    keep = set(requested_feature_names) | configured_features | configured_fields
    if "days_since_report" in requested_feature_names:
        keep.add("report_trade_date")
    if fundamentals_log_mcap and fundamentals_mcap_col:
        keep.add(fundamentals_mcap_col)
    keep_columns = ["trade_date", "symbol"] + sorted(column for column in keep if column in fund_df.columns)
    return fund_df.loc[:, list(dict.fromkeys(keep_columns))].copy()


def apply_fundamentals_enrichment(
    *,
    panel_df: pd.DataFrame,
    data_interface: DataInterface,
    symbols: list[str],
    start_date: str,
    end_date: str,
    market: str,
    data_cfg: Mapping[str, Any],
    fundamentals_cfg: Mapping[str, Any],
    requested_features: list[str],
    fundamentals_enabled: bool,
    fundamentals_source: str,
    fundamentals_file_path: Path | None,
    fundamentals_ffill: bool,
    fundamentals_ffill_limit: int | None,
    fundamentals_log_mcap: bool,
    fundamentals_mcap_col: str,
    fundamentals_log_mcap_col: str,
    fundamentals_auto_add: bool,
    provider_overlay_enabled: bool,
    provider_overlay_cfg: Mapping[str, Any],
    provider_overlay_auto_add: bool,
    provider_overlay_features: list[str],
) -> dict[str, Any]:
    df = panel_df
    features = list(requested_features)
    fundamentals_cols: list[str] = []
    fund_cache_dir: Path | None = None
    provider_overlay_cache_dir: Path | None = None
    fundamentals_required = bool(fundamentals_cfg.get("required", False))
    provider_overlay_required = bool(provider_overlay_cfg.get("required", False))

    if not fundamentals_enabled:
        return {
            "df": df,
            "features": features,
            "fundamentals_cols": fundamentals_cols,
            "fund_cache_dir": fund_cache_dir,
            "provider_overlay_cache_dir": provider_overlay_cache_dir,
        }

    requested_feature_names = set(features)
    fundamentals_file_columns = (
        _fundamentals_file_columns(
            fundamentals_cfg=fundamentals_cfg,
            requested_feature_names=requested_feature_names,
            fundamentals_mcap_col=fundamentals_mcap_col,
            fundamentals_log_mcap=fundamentals_log_mcap,
        )
        if fundamentals_source == "file"
        else None
    )
    fundamentals_frames, fund_cache_dir = load_panel_join_frames(
        source=fundamentals_source,
        file_path=fundamentals_file_path,
        data_interface=data_interface,
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        data_cfg=data_cfg,
        join_cfg=fundamentals_cfg,
        market=market,
        item_label="fundamentals",
        file_columns=fundamentals_file_columns,
    )

    if fundamentals_frames:
        fund_df = pd.concat(fundamentals_frames, ignore_index=True)
        fund_df = _prepare_panel_join_frame(
            fund_df,
            fundamentals_cfg.get("column_map"),
            item_label="Fundamentals",
            symbol_priority=(
                DEFAULT_SYMBOL_PRIORITY
                if fundamentals_source == "file"
                else PROVIDER_SYMBOL_PRIORITY
            ),
        )
        fund_df = _derive_requested_fundamental_fields(
            fund_df, requested_feature_names
        )
        fund_df = _select_fundamentals_merge_columns(
            fund_df,
            fundamentals_cfg=fundamentals_cfg,
            requested_feature_names=requested_feature_names,
            fundamentals_mcap_col=fundamentals_mcap_col,
            fundamentals_log_mcap=fundamentals_log_mcap,
        )
        df, fundamentals_cols = merge_panel_frame(
            df,
            fund_df,
            ffill=fundamentals_ffill,
            ffill_limit=fundamentals_ffill_limit,
            merge_label="Fundamentals",
        )
        logger.info(
            "Merged fundamentals: %s rows, %s columns, join_frame_memory=%.2f MiB, panel_memory=%.2f MiB.",
            len(fund_df),
            len(fundamentals_cols),
            frame_memory_mb(fund_df),
            frame_memory_mb(df),
        )
    else:
        message = "Fundamentals enabled but no data was loaded."
        if fundamentals_required:
            sys.exit(message)
        logger.warning(message)

    if provider_overlay_enabled:
        overlay_frames, provider_overlay_cache_dir = load_panel_join_frames(
            source="provider",
            file_path=None,
            data_interface=data_interface,
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            data_cfg=data_cfg,
            join_cfg=provider_overlay_cfg,
            market=market,
            item_label="provider valuation overlay",
            log_retry_failures=False,
            log_retry_traceback=False,
        )
        if overlay_frames:
            overlay_df = pd.concat(overlay_frames, ignore_index=True)
            overlay_df = _prepare_panel_join_frame(
                overlay_df,
                provider_overlay_cfg.get("column_map"),
                item_label="Provider overlay",
                symbol_priority=(
                    DEFAULT_SYMBOL_PRIORITY
                    if str(provider_overlay_cfg.get("source") or "").strip().lower() == "file"
                    else PROVIDER_SYMBOL_PRIORITY
                ),
            )
            overlay_value_cols = [
                col
                for col in overlay_df.columns
                if col in {"market_cap", "pe_ttm", "pb", fundamentals_mcap_col}
            ]
            if overlay_value_cols and "valuation_trade_date" not in overlay_df.columns:
                overlay_df["valuation_trade_date"] = overlay_df["trade_date"]
            df, overlay_cols = merge_panel_frame(
                df,
                overlay_df,
                ffill=False,
                ffill_limit=None,
                merge_label="Provider overlay",
            )
            logger.info(
                "Merged provider overlay: %s rows, %s columns.",
                len(overlay_df),
                len(overlay_cols),
            )
        else:
            message = "Provider overlay enabled but no overlay data was loaded."
            if provider_overlay_required:
                sys.exit(message)
            logger.warning(message)

    if "days_since_report" in features and "report_trade_date" in df.columns:
        report_trade_date = pd.to_datetime(df["report_trade_date"], errors="coerce")
        df["days_since_report"] = (df["trade_date"] - report_trade_date).dt.days
    if "valuation_age_days" in features and "valuation_trade_date" in df.columns:
        valuation_trade_date = pd.to_datetime(df["valuation_trade_date"], errors="coerce")
        df["valuation_age_days"] = (df["trade_date"] - valuation_trade_date).dt.days
    if fundamentals_log_mcap and fundamentals_mcap_col in df.columns:
        df[fundamentals_log_mcap_col] = np.where(
            df[fundamentals_mcap_col] > 0,
            np.log(df[fundamentals_mcap_col]),
            np.nan,
        )
        if (
            (fundamentals_auto_add or provider_overlay_auto_add)
            and fundamentals_log_mcap_col not in features
        ):
            features = list(dict.fromkeys(features + [fundamentals_log_mcap_col]))

    return {
        "df": df,
        "features": features,
        "fundamentals_cols": fundamentals_cols,
        "fund_cache_dir": fund_cache_dir,
        "provider_overlay_cache_dir": provider_overlay_cache_dir,
    }
