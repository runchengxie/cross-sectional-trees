from __future__ import annotations

import logging
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Optional

import numpy as np

from ..artifacts import CACHE_DIR as DEFAULT_CACHE_DIR, resolve_repo_path
from ..compat import ensure_numpy_nan_alias
from ..data_interface import DataInterface
from ..data_providers import normalize_market
from ..data_tools.symbols import (
    DEFAULT_SYMBOL_PRIORITY,
    PROVIDER_SYMBOL_PRIORITY,
    canonicalize_symbol_columns,
)
from ..rebalance import estimate_rebalance_gap, get_rebalance_dates
from .support import (
    _prepare_panel_join_frame,
    _select_panel_join_columns,
)

ensure_numpy_nan_alias()
import pandas as pd

logger = logging.getLogger("csml")
_EXECUTION_LIQUIDITY_PROXY_PATTERN = re.compile(r"^(?P<kind>adv|medadv)(?P<window>\d+)_amount$")


def _parse_execution_liquidity_proxy_column(column: str) -> tuple[str, int] | None:
    match = _EXECUTION_LIQUIDITY_PROXY_PATTERN.fullmatch(str(column).strip())
    if match is None:
        return None
    window = int(match.group("window"))
    if window <= 0:
        return None
    return match.group("kind"), window


def _derive_execution_liquidity_proxy_columns(
    df: pd.DataFrame,
    required_columns: set[str],
) -> pd.DataFrame:
    if df.empty or "amount" not in df.columns:
        return df

    out = df
    derived_columns: list[str] = []
    amount = pd.to_numeric(out["amount"], errors="coerce")
    grouped_amount = amount.groupby(out["symbol"])

    for column in sorted(required_columns):
        if column in out.columns:
            continue
        parsed = _parse_execution_liquidity_proxy_column(column)
        if parsed is None:
            continue

        kind, window = parsed
        lagged = grouped_amount.shift(1)
        if kind == "adv":
            proxy = lagged.groupby(out["symbol"]).transform(
                lambda series: series.rolling(window=window, min_periods=1).mean()
            )
        else:
            proxy = lagged.groupby(out["symbol"]).transform(
                lambda series: series.rolling(window=window, min_periods=1).median()
            )

        if out is df:
            out = df.copy()
        out[column] = pd.to_numeric(proxy, errors="coerce")
        derived_columns.append(column)

    if derived_columns:
        logger.info(
            "Derived execution liquidity proxy columns from lagged amount: %s",
            derived_columns,
        )
    return out


def _default_tr_close_meta_for_frame(
    symbol: str,
    frame: pd.DataFrame,
) -> dict[str, Any]:
    source = "input_frame" if "tr_close" in frame.columns else "unavailable"
    return {
        "symbol": symbol,
        "source": source,
        "configured_local_ex_factors": False,
        "local_ex_factors_available": None,
        "adjust_type": None,
    }


def _sample_symbols(symbols: list[str], *, limit: int = 10) -> list[str]:
    return sorted(symbols)[:limit]


def _build_price_col_diagnostics(
    *,
    price_col: str,
    symbol_metas: list[dict[str, Any]],
) -> dict[str, Any]:
    source_counts: dict[str, int] = {}
    unavailable_symbols: list[str] = []
    ex_factor_gap_symbols: list[str] = []
    close_fallback_symbols: list[str] = []

    for meta in symbol_metas:
        source = str(meta.get("source") or "unavailable")
        symbol = str(meta.get("symbol") or "").strip()
        source_counts[source] = source_counts.get(source, 0) + 1
        if not symbol:
            continue
        if source == "unavailable":
            unavailable_symbols.append(symbol)
        if source in {
            "input_frame_missing_ex_factors",
            "close_fallback_missing_ex_factors",
        }:
            ex_factor_gap_symbols.append(symbol)
        if source == "close_fallback_missing_ex_factors":
            close_fallback_symbols.append(symbol)

    return {
        "price_col": price_col,
        "tr_close_source_counts": source_counts,
        "tr_close_symbol_count": int(sum(source_counts.values())),
        "tr_close_missing_symbol_count": len(unavailable_symbols),
        "tr_close_missing_symbols_sample": _sample_symbols(unavailable_symbols),
        "tr_close_ex_factor_gap_symbol_count": len(ex_factor_gap_symbols),
        "tr_close_ex_factor_gap_symbols_sample": _sample_symbols(ex_factor_gap_symbols),
        "tr_close_close_fallback_symbol_count": len(close_fallback_symbols),
        "tr_close_close_fallback_symbols_sample": _sample_symbols(close_fallback_symbols),
    }


def _resolve_fundamentals_cache_dir(
    data_cfg: Mapping[str, Any],
    fundamentals_cfg: Mapping[str, Any],
    market: str,
) -> Path:
    configured = fundamentals_cfg.get("cache_dir")
    if configured:
        return resolve_repo_path(configured)
    base_dir = resolve_repo_path(
        data_cfg.get("cache_dir", DEFAULT_CACHE_DIR.as_posix())
    )
    return base_dir / "fundamentals" / normalize_market(market)


def _load_fundamentals_frames(
    *,
    source: str,
    file_path: Optional[Path],
    data_interface: DataInterface,
    symbols: list[str],
    start_date: str,
    end_date: str,
    data_cfg: Mapping[str, Any],
    fundamentals_cfg: Mapping[str, Any],
    market: str,
    item_label: str,
    log_retry_failures: bool = True,
    log_retry_traceback: bool = True,
) -> tuple[list[pd.DataFrame], Optional[Path]]:
    frames: list[pd.DataFrame] = []
    cache_dir: Optional[Path] = None
    if source == "file":
        if file_path is None:
            return frames, cache_dir
        if file_path.suffix.lower() in {".parquet", ".pq"}:
            frames.append(pd.read_parquet(file_path))
        else:
            frames.append(pd.read_csv(file_path))
        return frames, cache_dir

    cache_dir = _resolve_fundamentals_cache_dir(data_cfg, fundamentals_cfg, market)
    cache_dir.mkdir(parents=True, exist_ok=True)

    for symbol in symbols:
        logger.info("Fetching %s for %s (%s) ...", item_label, symbol, market)
        try:
            frame = data_interface.fetch_fundamentals(
                symbol,
                start_date,
                end_date,
                fundamentals_cfg,
                cache_dir=cache_dir,
                log_retry_failures=log_retry_failures,
                log_retry_traceback=log_retry_traceback,
            )
        except Exception as exc:
            logger.warning("Skipping %s for %s after retries (%s).", item_label, symbol, exc)
            frame = pd.DataFrame()
        if frame is not None and not frame.empty:
            frames.append(frame)
    return frames, cache_dir


def _derive_requested_fundamental_fields(
    fund_df: pd.DataFrame,
    requested_feature_names: set[str],
) -> pd.DataFrame:
    fund_df = fund_df.copy()
    if (
        "sales" in requested_feature_names
        or "delta_sales" in requested_feature_names
        or "growth_sales" in requested_feature_names
        or "profit_margin" in requested_feature_names
        or "operating_margin" in requested_feature_names
        or "cfo_margin" in requested_feature_names
    ):
        revenue = (
            pd.to_numeric(fund_df["revenue"], errors="coerce")
            if "revenue" in fund_df.columns
            else pd.Series(np.nan, index=fund_df.index, dtype=float)
        )
        operating_revenue = (
            pd.to_numeric(fund_df["operating_revenue"], errors="coerce")
            if "operating_revenue" in fund_df.columns
            else pd.Series(np.nan, index=fund_df.index, dtype=float)
        )
        fund_df["sales"] = revenue.combine_first(operating_revenue)
    if (
        "debt" in requested_feature_names
        or "delta_debt" in requested_feature_names
        or "growth_debt" in requested_feature_names
        or "debt_to_assets" in requested_feature_names
        or "debt_to_equity" in requested_feature_names
        or "net_debt_to_assets" in requested_feature_names
    ):
        short_term_debt = (
            pd.to_numeric(fund_df["short_term_debt"], errors="coerce")
            if "short_term_debt" in fund_df.columns
            else pd.Series(np.nan, index=fund_df.index, dtype=float)
        )
        long_term_loans = (
            pd.to_numeric(fund_df["long_term_loans"], errors="coerce")
            if "long_term_loans" in fund_df.columns
            else pd.Series(np.nan, index=fund_df.index, dtype=float)
        )
        debt = short_term_debt.fillna(0.0) + long_term_loans.fillna(0.0)
        fund_df["debt"] = debt.where(~(short_term_debt.isna() & long_term_loans.isna()))
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
    return fund_df


def _merge_fundamentals_panel(
    panel_df: pd.DataFrame,
    fund_df: pd.DataFrame,
    *,
    ffill: bool,
    ffill_limit: Optional[int],
    merge_label: str,
) -> tuple[pd.DataFrame, list[str]]:
    fundamentals_cols = [
        col for col in fund_df.columns if col not in {"trade_date", "symbol", "ts_code", "stock_ticker"}
    ]
    overlap_cols = sorted(set(fundamentals_cols).intersection(panel_df.columns))
    if overlap_cols:
        sys.exit(
            f"{merge_label} columns already exist in panel and would be overwritten: {overlap_cols}"
        )
    merged = panel_df.merge(fund_df, on=["trade_date", "symbol"], how="left")
    if ffill and fundamentals_cols:
        merged.sort_values(["symbol", "trade_date"], inplace=True)
        merged[fundamentals_cols] = merged.groupby("symbol")[fundamentals_cols].ffill(
            limit=ffill_limit
        )
    return merged, fundamentals_cols


def _load_research_panel(
    *,
    data_interface: DataInterface,
    symbols: list[str],
    market: str,
    start_date: str,
    end_date: str,
    execution_pricing_cols: set[str],
    price_col: str,
    benchmark_symbol: str | None,
    drop_st: bool,
    min_listed_days: int,
    drop_suspended: bool,
    suspended_policy: str,
    min_turnover: float,
    fundamentals_enabled: bool,
    fundamentals_source: str,
    fundamentals_file_path: Optional[Path],
    data_cfg: Mapping[str, Any],
    fundamentals_cfg: Mapping[str, Any],
    requested_features: list[str],
    fundamentals_ffill: bool,
    fundamentals_ffill_limit: Optional[int],
    fundamentals_log_mcap: bool,
    fundamentals_mcap_col: str,
    fundamentals_log_mcap_col: str,
    fundamentals_auto_add: bool,
    provider_overlay_enabled: bool,
    provider_overlay_cfg: Mapping[str, Any],
    provider_overlay_auto_add: bool,
    provider_overlay_features: list[str],
    industry_enabled: bool,
    industry_file_path: Optional[Path],
    industry_cfg: Mapping[str, Any],
    industry_keep_columns: list[str],
    industry_ffill: bool,
    industry_ffill_limit: Optional[int],
    label_horizon_mode: str,
    label_rebalance_frequency: str,
) -> dict[str, Any]:
    fundamentals_required = bool(fundamentals_cfg.get("required", False))
    provider_overlay_required = bool(provider_overlay_cfg.get("required", False))
    benchmark_symbol = str(benchmark_symbol).strip() if benchmark_symbol else None
    symbols_for_data = symbols[:]
    if benchmark_symbol and benchmark_symbol not in symbols_for_data:
        symbols_for_data.append(benchmark_symbol)

    frames = []
    tr_close_symbol_metas: list[dict[str, Any]] = []
    for symbol in symbols_for_data:
        logger.info("Fetching daily data for %s (%s) ...", symbol, market)
        try:
            data = data_interface.fetch_daily(symbol, start_date, end_date)
        except Exception as exc:
            logger.warning("Skipping %s after retries (%s).", symbol, exc)
            data = pd.DataFrame()
        if not data.empty:
            meta = data.attrs.get("tr_close_meta")
            if isinstance(meta, Mapping):
                tr_close_symbol_metas.append(dict(meta))
            else:
                tr_close_symbol_metas.append(
                    _default_tr_close_meta_for_frame(symbol, data)
                )
            frames.append(data)

    if not frames:
        sys.exit("No data returned - check symbols and date range.")

    df = pd.concat(frames, ignore_index=True)
    df = canonicalize_symbol_columns(df, context="Daily panel")
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    df.sort_values(["symbol", "trade_date"], inplace=True)
    df = _derive_execution_liquidity_proxy_columns(df, execution_pricing_cols)
    missing_execution_cols = [
        col for col in sorted(execution_pricing_cols) if col not in df.columns
    ]
    if missing_execution_cols:
        sys.exit(
            "Daily data is missing execution pricing columns required by backtest.execution: "
            + ", ".join(missing_execution_cols)
        )

    benchmark_df = None
    if benchmark_symbol:
        if benchmark_symbol in symbols:
            logger.info("Benchmark symbol %s removed from modeling universe.", benchmark_symbol)
        benchmark_df = df[df["symbol"] == benchmark_symbol].copy()
        df = df[df["symbol"] != benchmark_symbol].copy()
        if benchmark_df.empty:
            logger.warning(
                "Benchmark symbol %s returned no daily data; benchmark and active-return outputs will be skipped.",
                benchmark_symbol,
            )
    symbols_for_non_price = [
        symbol for symbol in symbols_for_data if not benchmark_symbol or symbol != benchmark_symbol
    ]
    modeling_symbol_set = set(symbols_for_non_price)
    price_col_diagnostics = _build_price_col_diagnostics(
        price_col=price_col,
        symbol_metas=[
            meta
            for meta in tr_close_symbol_metas
            if str(meta.get("symbol") or "").strip() in modeling_symbol_set
        ],
    )
    tr_close_source_counts = price_col_diagnostics["tr_close_source_counts"]
    if tr_close_source_counts and (
        price_col == "tr_close" or any(source != "unavailable" for source in tr_close_source_counts)
    ):
        logger.info(
            "Price column diagnostics for %s: tr_close sources=%s",
            price_col,
            tr_close_source_counts,
        )
    if price_col == "tr_close":
        ex_factor_gap_symbols = price_col_diagnostics["tr_close_ex_factor_gap_symbols_sample"]
        ex_factor_gap_count = int(price_col_diagnostics["tr_close_ex_factor_gap_symbol_count"])
        if ex_factor_gap_count > 0:
            logger.warning(
                "price_col=tr_close could not use local ex_factors for %s symbols; "
                "sample=%s. summary.json -> data -> price_col_diagnostics records the source mix.",
                ex_factor_gap_count,
                ex_factor_gap_symbols,
            )
        missing_symbol_count = int(price_col_diagnostics["tr_close_missing_symbol_count"])
        if missing_symbol_count > 0:
            logger.warning(
                "price_col=tr_close but tr_close was unavailable for %s symbols; sample=%s.",
                missing_symbol_count,
                price_col_diagnostics["tr_close_missing_symbols_sample"],
            )

    basic_df = None
    if drop_st or min_listed_days > 0:
        try:
            if market != "cn" and drop_st:
                logger.info(
                    "drop_st uses a legacy ST-name heuristic; attempting basic data for market '%s'.",
                    market,
                )
            basic_df = data_interface.load_basic(symbols_for_non_price)
            if basic_df is not None and not basic_df.empty:
                basic_df = canonicalize_symbol_columns(basic_df, context="Basic data")
        except Exception as exc:
            logger.warning("Basic data load failed (%s); skipping ST/listed filters.", exc)
            basic_df = None

    if drop_st and basic_df is not None and "name" in basic_df.columns:
        st_codes = basic_df[
            basic_df["name"].str.contains("ST", case=False, na=False)
        ]["symbol"]
        df = df[~df["symbol"].isin(st_codes)].copy()

    if min_listed_days > 0 and basic_df is not None and not basic_df.empty and "list_date" in basic_df.columns:
        list_dates = basic_df.copy()
        list_dates["list_date"] = pd.to_datetime(
            list_dates["list_date"], format="%Y%m%d", errors="coerce"
        )
        list_date_map = list_dates.set_index("symbol")["list_date"].to_dict()
        df["list_date"] = pd.to_datetime(df["symbol"].map(list_date_map), errors="coerce")
        valid_list_date_mask = df["list_date"].notna()
        if not valid_list_date_mask.any():
            logger.warning(
                "Basic data returned no usable list_date values; skipping min_listed_days=%s filter.",
                min_listed_days,
            )
        else:
            df = df[valid_list_date_mask].copy()
            df = df[
                df["trade_date"] >= df["list_date"] + pd.Timedelta(days=min_listed_days)
            ].copy()

    df["is_tradable"] = True
    if drop_suspended:
        if "amount" in df.columns:
            tradable_mask = (df["vol"] > 0) & (df["amount"] > 0)
        else:
            tradable_mask = df["vol"] > 0
        tradable_mask = tradable_mask.fillna(False)
        df["is_tradable"] = tradable_mask
        if suspended_policy == "filter":
            df = df[df["is_tradable"]].copy()

    if min_turnover > 0 and "amount" in df.columns:
        df = df[df["amount"] >= min_turnover].copy()

    features = list(requested_features)
    fundamentals_cols: list[str] = []
    industry_cols: list[str] = []
    industry_source_df = pd.DataFrame()
    fund_cache_dir: Optional[Path] = None
    provider_overlay_cache_dir: Optional[Path] = None

    if fundamentals_enabled:
        requested_feature_names = set(features)
        fundamentals_frames, fund_cache_dir = _load_fundamentals_frames(
            source=fundamentals_source,
            file_path=fundamentals_file_path,
            data_interface=data_interface,
            symbols=symbols_for_non_price,
            start_date=start_date,
            end_date=end_date,
            data_cfg=data_cfg,
            fundamentals_cfg=fundamentals_cfg,
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
            df, fundamentals_cols = _merge_fundamentals_panel(
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
            overlay_frames, provider_overlay_cache_dir = _load_fundamentals_frames(
                source="provider",
                file_path=None,
                data_interface=data_interface,
                symbols=symbols_for_non_price,
                start_date=start_date,
                end_date=end_date,
                data_cfg=data_cfg,
                fundamentals_cfg=provider_overlay_cfg,
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
                df, overlay_cols = _merge_fundamentals_panel(
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

    if industry_enabled:
        industry_frames, _ = _load_fundamentals_frames(
            source="file",
            file_path=industry_file_path,
            data_interface=data_interface,
            symbols=symbols_for_non_price,
            start_date=start_date,
            end_date=end_date,
            data_cfg=data_cfg,
            fundamentals_cfg=industry_cfg,
            market=market,
            item_label="industry labels",
        )
        if industry_frames:
            industry_df = pd.concat(industry_frames, ignore_index=True)
            industry_df = _prepare_panel_join_frame(
                industry_df,
                industry_cfg.get("column_map"),
                item_label="Industry",
                symbol_priority=DEFAULT_SYMBOL_PRIORITY,
            )
            industry_df = _select_panel_join_columns(
                industry_df,
                keep_columns=industry_keep_columns,
                item_label="Industry",
            )
            industry_source_df = industry_df.copy()
            df, industry_cols = _merge_fundamentals_panel(
                df,
                industry_df,
                ffill=industry_ffill,
                ffill_limit=industry_ffill_limit,
                merge_label="Industry",
            )
            logger.info(
                "Merged industry labels: %s rows, %s columns.",
                len(industry_df),
                len(industry_cols),
            )
        else:
            logger.warning("Industry join enabled but no industry data was loaded.")

    label_next_rebalance_map = None
    label_horizon_gap = None
    label_horizon_mode_effective = label_horizon_mode
    if label_horizon_mode == "next_rebalance":
        label_trade_dates = sorted(df["trade_date"].unique())
        label_rebalance_dates = get_rebalance_dates(
            label_trade_dates, label_rebalance_frequency
        )
        if len(label_rebalance_dates) < 2:
            logger.warning(
                "label.horizon_mode=next_rebalance but insufficient rebalance dates; "
                "falling back to fixed horizon_days."
            )
            label_horizon_mode_effective = "fixed"
        else:
            rebalance_array = np.array(label_rebalance_dates)
            trade_array = np.array(label_trade_dates)
            idx = np.searchsorted(rebalance_array, trade_array, side="right")
            next_dates = [
                rebalance_array[i] if i < len(rebalance_array) else pd.NaT
                for i in idx
            ]
            label_next_rebalance_map = dict(zip(label_trade_dates, next_dates))
            label_horizon_gap = estimate_rebalance_gap(
                label_trade_dates, label_rebalance_dates
            )
            if np.isfinite(label_horizon_gap):
                logger.info(
                    "Label horizon set to next rebalance date (median gap %.1f days).",
                    label_horizon_gap,
                )

    return {
        "df": df,
        "benchmark_df": benchmark_df,
        "symbols_for_non_price": symbols_for_non_price,
        "fundamentals_cols": fundamentals_cols,
        "industry_cols": industry_cols,
        "industry_source_df": industry_source_df,
        "fund_cache_dir": fund_cache_dir,
        "provider_overlay_cache_dir": provider_overlay_cache_dir,
        "features": features,
        "label_horizon_mode": label_horizon_mode_effective,
        "label_next_rebalance_map": label_next_rebalance_map,
        "label_horizon_gap": label_horizon_gap,
        "price_col_diagnostics": price_col_diagnostics,
    }
