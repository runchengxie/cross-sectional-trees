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
)
from ..pit_feature_stats import (
    compute_calendar_cagr,
    compute_trailing_calendar_window_stat,
)
from .panel_join_support import load_panel_join_frames, merge_panel_frame
from .support import _prepare_panel_join_frame

logger = logging.getLogger("csml")


def _derive_requested_fundamental_fields(
    fund_df: pd.DataFrame,
    requested_feature_names: set[str],
) -> pd.DataFrame:
    fund_df = fund_df.copy()

    def _numeric(name: str) -> pd.Series:
        if name not in fund_df.columns:
            return pd.Series(np.nan, index=fund_df.index, dtype=float)
        return pd.to_numeric(fund_df[name], errors="coerce")

    def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
        valid_denominator = denominator.where(denominator.notna() & (denominator != 0))
        return (numerator / valid_denominator).replace([np.inf, -np.inf], np.nan)

    def _need_any(*feature_names: str) -> bool:
        return any(name in requested_feature_names for name in feature_names)

    if (
        _need_any(
            "sales",
            "delta_sales",
            "growth_sales",
            "profit_margin",
            "operating_margin",
            "cfo_margin",
            "sales_cagr_3y",
        )
    ):
        revenue = _numeric("revenue")
        operating_revenue = _numeric("operating_revenue")
        fund_df["sales"] = revenue.combine_first(operating_revenue)
    if (
        _need_any(
            "debt",
            "delta_debt",
            "growth_debt",
            "debt_to_assets",
            "debt_to_equity",
            "net_debt_to_assets",
        )
    ):
        short_term_debt = _numeric("short_term_debt")
        long_term_loans = _numeric("long_term_loans")
        debt = short_term_debt.fillna(0.0) + long_term_loans.fillna(0.0)
        fund_df["debt"] = debt.where(~(short_term_debt.isna() & long_term_loans.isna()))
    if _need_any("profit_margin", "profit_margin_std_3y"):
        fund_df["profit_margin"] = _safe_ratio(_numeric("net_profit"), _numeric("sales"))
    if _need_any("operating_margin"):
        fund_df["operating_margin"] = _safe_ratio(_numeric("operating_profit"), _numeric("sales"))
    if _need_any("cfo_margin", "cfo_margin_avg_3y"):
        fund_df["cfo_margin"] = _safe_ratio(
            _numeric("cash_flow_from_operating_activities"),
            _numeric("sales"),
        )
    if _need_any("cfo_to_profit", "cfo_to_profit_median_3y"):
        fund_df["cfo_to_profit"] = _safe_ratio(
            _numeric("cash_flow_from_operating_activities"),
            _numeric("net_profit"),
        )
    if "days_since_report" in requested_feature_names:
        fund_df["report_trade_date"] = fund_df["trade_date"]
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
    if "sales_cagr_3y" in requested_feature_names:
        fund_df["sales_cagr_3y"] = compute_calendar_cagr(fund_df, fund_df["sales"], years=3)
    if "eps_cagr_3y" in requested_feature_names:
        fund_df["eps_cagr_3y"] = compute_calendar_cagr(
            fund_df,
            _numeric("basic_earnings_per_share"),
            years=3,
        )
    if "cfo_margin_avg_3y" in requested_feature_names:
        fund_df["cfo_margin_avg_3y"] = compute_trailing_calendar_window_stat(
            fund_df,
            fund_df["cfo_margin"],
            years=3,
            stat="mean",
            min_periods=3,
        )
    if "profit_margin_std_3y" in requested_feature_names:
        fund_df["profit_margin_std_3y"] = compute_trailing_calendar_window_stat(
            fund_df,
            fund_df["profit_margin"],
            years=3,
            stat="std",
            min_periods=3,
        )
    if "cfo_to_profit_median_3y" in requested_feature_names:
        fund_df["cfo_to_profit_median_3y"] = compute_trailing_calendar_window_stat(
            fund_df,
            fund_df["cfo_to_profit"],
            years=3,
            stat="median",
            min_periods=3,
        )
    if "positive_cfo_ratio_3y" in requested_feature_names:
        fund_df["positive_cfo_ratio_3y"] = compute_trailing_calendar_window_stat(
            fund_df,
            _numeric("cash_flow_from_operating_activities"),
            years=3,
            stat="positive_ratio",
            min_periods=3,
        )
    if "positive_cfo_ratio_2y" in requested_feature_names:
        fund_df["positive_cfo_ratio_2y"] = compute_trailing_calendar_window_stat(
            fund_df,
            _numeric("cash_flow_from_operating_activities"),
            years=2,
            stat="positive_ratio",
            min_periods=2,
        )
    if "positive_cfo_ratio_3y_min2" in requested_feature_names:
        fund_df["positive_cfo_ratio_3y_min2"] = compute_trailing_calendar_window_stat(
            fund_df,
            _numeric("cash_flow_from_operating_activities"),
            years=3,
            stat="positive_ratio",
            min_periods=2,
        )
    return fund_df


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
        df, fundamentals_cols = merge_panel_frame(
            df,
            fund_df,
            ffill=fundamentals_ffill,
            ffill_limit=fundamentals_ffill_limit,
            merge_label="Fundamentals",
        )
        logger.info(
            "Merged fundamentals: %s rows, %s columns.",
            len(fund_df),
            len(fundamentals_cols),
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
