from __future__ import annotations

import logging
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Optional

import numpy as np

if not hasattr(np, "NaN"):
    np.NaN = np.nan

import pandas as pd
import pandas_ta as ta

from ..artifacts import CACHE_DIR as DEFAULT_CACHE_DIR, resolve_repo_path
from ..data_interface import DataInterface
from ..data_providers import normalize_market
from ..data_tools.symbols import ensure_symbol_columns
from ..dataset import DatasetSchema, build_dataset
from .dates import _build_trade_date_slices, _slice_trade_dates
from .support import (
    _ensure_symbol_alias,
    _parse_window_config,
    _prepare_panel_join_frame,
    _select_panel_join_columns,
    apply_universe_by_date,
    parse_feature_windows,
)
from ..rebalance import estimate_rebalance_gap, get_rebalance_dates
from ..transform import apply_cross_sectional_series_transform, apply_cross_sectional_transform

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
    if df.empty:
        return df
    if "amount" not in df.columns:
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
    df = ensure_symbol_columns(df, context="Daily panel")
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
                basic_df = ensure_symbol_columns(basic_df, context="Basic data")
        except Exception as exc:
            logger.warning("Basic data load failed (%s); skipping ST/listed filters.", exc)
            basic_df = None

    if drop_st and basic_df is not None and "name" in basic_df.columns:
        st_codes = basic_df[
            basic_df["name"].str.contains("ST", case=False, na=False)
        ]["symbol"]
        df = df[~df["symbol"].isin(st_codes)].copy()

    if min_listed_days > 0 and basic_df is not None and "list_date" in basic_df.columns:
        list_dates = basic_df.copy()
        list_dates["list_date"] = pd.to_datetime(
            list_dates["list_date"], format="%Y%m%d", errors="coerce"
        )
        list_date_map = list_dates.set_index("symbol")["list_date"].to_dict()
        df["list_date"] = df["symbol"].map(list_date_map)
        df = df[df["list_date"].notna()].copy()
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
            logger.warning("Fundamentals enabled but no data was loaded.")

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
                logger.warning("Provider overlay enabled but no overlay data was loaded.")

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
            )
            industry_df = _select_panel_join_columns(
                industry_df,
                keep_columns=industry_keep_columns,
                item_label="Industry",
            )
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
        "fund_cache_dir": fund_cache_dir,
        "provider_overlay_cache_dir": provider_overlay_cache_dir,
        "features": features,
        "label_horizon_mode": label_horizon_mode_effective,
        "label_next_rebalance_map": label_next_rebalance_map,
        "label_horizon_gap": label_horizon_gap,
        "price_col_diagnostics": price_col_diagnostics,
    }


def _prepare_feature_dataset(
    *,
    df: pd.DataFrame,
    features: list[str],
    feature_params: Mapping[str, Any],
    price_col: str,
    target: str,
    label_shift_days: int,
    label_horizon_days: int,
    label_horizon_mode: str,
    label_next_rebalance_map: Optional[dict[pd.Timestamp, pd.Timestamp]],
    fundamentals_allow_missing: bool,
    bucket_ic_enabled: bool,
    bucket_ic_schemes: list[dict[str, Any]],
    feature_missing_features: list[str],
    feature_missing_method: str,
    feature_missing_add_indicators: bool,
    feature_missing_suffix: str,
    industry_cols: list[str],
    execution_pricing_cols: set[str],
    backtest_tradable_col: str | None,
    universe_by_date: Optional[pd.DataFrame],
    winsorize_pct: float | None,
    cs_method: str,
    cs_winsorize_pct: float | None,
    train_target: str,
    train_target_transform: str,
    sample_on_rebalance_dates: bool,
    rebalance_frequency: str,
    min_symbols_per_date: int,
) -> dict[str, Any]:
    logger.info("Engineering features ...")
    if price_col not in df.columns:
        if price_col == "tr_close":
            sys.exit(
                "Price column 'tr_close' not found in data. "
                "Configure data.rqdata.ex_factors_dir for local RQData assets, "
                "or provide tr_close directly in the source daily data."
            )
        sys.exit(f"Price column '{price_col}' not found in data.")
    if not features:
        sys.exit("Feature list is empty.")

    features = list(features)

    def add_features(group: pd.DataFrame) -> pd.DataFrame:
        group = group.sort_values("trade_date").copy()
        needed = set(features)
        price_series = pd.to_numeric(group[price_col], errors="coerce")

        def _safe_ratio(
            numerator_col: str,
            denominator_col: str,
            out_col: str,
        ) -> None:
            if out_col not in needed:
                return
            if numerator_col not in group.columns or denominator_col not in group.columns:
                return
            numerator = pd.to_numeric(group[numerator_col], errors="coerce")
            denominator = pd.to_numeric(group[denominator_col], errors="coerce")
            valid_denominator = denominator.where(denominator.notna() & (denominator != 0))
            ratio = numerator / valid_denominator
            group[out_col] = ratio.replace([np.inf, -np.inf], np.nan)

        sma_windows = set(parse_feature_windows(features, "sma_"))
        sma_windows.update(parse_feature_windows(features, "sma_", "_diff"))
        if not sma_windows:
            sma_windows = _parse_window_config(feature_params.get("sma_windows"))
        for win in sorted(sma_windows):
            group[f"sma_{win}"] = ta.sma(price_series, length=win)
            if f"sma_{win}_diff" in needed:
                group[f"sma_{win}_diff"] = group[f"sma_{win}"].pct_change()

        rsi_lengths = set(parse_feature_windows(features, "rsi_"))
        if not rsi_lengths:
            rsi_lengths = _parse_window_config(feature_params.get("rsi"))
        for length in sorted(rsi_lengths):
            group[f"rsi_{length}"] = ta.rsi(price_series, length=length)

        if "macd_hist" in needed:
            macd_cfg = feature_params.get("macd", [12, 26, 9])
            macd_fast, macd_slow, macd_signal = macd_cfg
            macd = ta.macd(price_series, fast=macd_fast, slow=macd_slow, signal=macd_signal)
            col_name = f"MACDh_{macd_fast}_{macd_slow}_{macd_signal}"
            if macd is not None and col_name in macd.columns:
                group["macd_hist"] = macd[col_name]
            else:
                group["macd_hist"] = np.nan

        volume_windows = set(parse_feature_windows(features, "volume_sma", "_ratio"))
        if not volume_windows:
            volume_windows = _parse_window_config(feature_params.get("volume_sma_windows"))
        for win in sorted(volume_windows):
            volume_sma = ta.sma(group["vol"], length=win)
            if volume_sma is None:
                volume_sma = group["vol"].rolling(window=win).mean()
            group[f"volume_sma{win}"] = volume_sma
            if f"volume_sma{win}_ratio" in needed:
                group[f"volume_sma{win}_ratio"] = group["vol"] / group[f"volume_sma{win}"]

        ret_windows = set(parse_feature_windows(features, "ret_"))
        if not ret_windows:
            ret_windows = _parse_window_config(feature_params.get("ret_windows"))
        for win in sorted(ret_windows):
            group[f"ret_{win}"] = price_series.pct_change(win)

        rv_windows = set(parse_feature_windows(features, "rv_"))
        if not rv_windows:
            rv_windows = _parse_window_config(feature_params.get("rv_windows"))
        if rv_windows:
            daily_return = price_series.pct_change()
            daily_return = daily_return.replace([np.inf, -np.inf], np.nan)
            for win in sorted(rv_windows):
                group[f"rv_{win}"] = daily_return.rolling(window=win).std(ddof=0)

        if "log_vol" in needed:
            group["log_vol"] = np.log1p(group["vol"].clip(lower=0))

        if (
            "sales" in needed
            or "profit_margin" in needed
            or "operating_margin" in needed
            or "cfo_margin" in needed
        ):
            revenue = (
                pd.to_numeric(group["revenue"], errors="coerce")
                if "revenue" in group.columns
                else pd.Series(np.nan, index=group.index, dtype=float)
            )
            operating_revenue = (
                pd.to_numeric(group["operating_revenue"], errors="coerce")
                if "operating_revenue" in group.columns
                else pd.Series(np.nan, index=group.index, dtype=float)
            )
            group["sales"] = revenue.combine_first(operating_revenue)
        if (
            "debt" in needed
            or "debt_to_assets" in needed
            or "debt_to_equity" in needed
            or "net_debt_to_assets" in needed
        ):
            short_term_debt = (
                pd.to_numeric(group["short_term_debt"], errors="coerce")
                if "short_term_debt" in group.columns
                else pd.Series(np.nan, index=group.index, dtype=float)
            )
            long_term_loans = (
                pd.to_numeric(group["long_term_loans"], errors="coerce")
                if "long_term_loans" in group.columns
                else pd.Series(np.nan, index=group.index, dtype=float)
            )
            debt = short_term_debt.fillna(0.0) + long_term_loans.fillna(0.0)
            group["debt"] = debt.where(~(short_term_debt.isna() & long_term_loans.isna()))

        _safe_ratio("net_profit", "sales", "profit_margin")
        _safe_ratio("operating_profit", "sales", "operating_margin")
        _safe_ratio(
            "cash_flow_from_operating_activities",
            "sales",
            "cfo_margin",
        )
        _safe_ratio(
            "cash_flow_from_operating_activities",
            "net_profit",
            "cfo_to_profit",
        )
        _safe_ratio("revenue", "total_assets", "asset_turnover")
        _safe_ratio("net_profit", "total_assets", "roa")
        _safe_ratio("total_liabilities", "total_assets", "leverage")
        _safe_ratio(
            "cash_flow_from_operating_activities",
            "total_assets",
            "cfo_to_assets",
        )
        _safe_ratio("debt", "total_assets", "debt_to_assets")
        _safe_ratio("debt", "total_equity", "debt_to_equity")
        _safe_ratio("cash_and_equivalents", "total_assets", "cash_to_assets")
        _safe_ratio("goodwill", "total_assets", "goodwill_to_assets")
        if "accrual_ratio" in needed:
            if (
                "net_profit" in group.columns
                and "cash_flow_from_operating_activities" in group.columns
                and "total_assets" in group.columns
            ):
                net_profit = pd.to_numeric(group["net_profit"], errors="coerce")
                cfo = pd.to_numeric(group["cash_flow_from_operating_activities"], errors="coerce")
                total_assets = pd.to_numeric(group["total_assets"], errors="coerce")
                valid_assets = total_assets.where(total_assets.notna() & (total_assets != 0))
                accrual = (net_profit - cfo) / valid_assets
                group["accrual_ratio"] = accrual.replace([np.inf, -np.inf], np.nan)
        _safe_ratio("accounts_receivable", "revenue", "receivables_to_revenue")
        _safe_ratio("inventory", "revenue", "inventory_to_revenue")
        if "working_capital_to_assets" in needed:
            if (
                "accounts_receivable" in group.columns
                and "inventory" in group.columns
                and "accounts_payable" in group.columns
                and "total_assets" in group.columns
            ):
                receivables = pd.to_numeric(group["accounts_receivable"], errors="coerce")
                inventory = pd.to_numeric(group["inventory"], errors="coerce")
                payables = pd.to_numeric(group["accounts_payable"], errors="coerce")
                total_assets = pd.to_numeric(group["total_assets"], errors="coerce")
                valid_assets = total_assets.where(total_assets.notna() & (total_assets != 0))
                working_capital = receivables + inventory - payables
                ratio = working_capital / valid_assets
                group["working_capital_to_assets"] = ratio.replace([np.inf, -np.inf], np.nan)
        if "net_debt_to_assets" in needed:
            if (
                "debt" in group.columns
                and "cash_and_equivalents" in group.columns
                and "total_assets" in group.columns
            ):
                debt = pd.to_numeric(group["debt"], errors="coerce")
                cash_and_equivalents = pd.to_numeric(group["cash_and_equivalents"], errors="coerce")
                total_assets = pd.to_numeric(group["total_assets"], errors="coerce")
                valid_assets = total_assets.where(total_assets.notna() & (total_assets != 0))
                net_debt = debt - cash_and_equivalents
                ratio = net_debt / valid_assets
                group["net_debt_to_assets"] = ratio.replace([np.inf, -np.inf], np.nan)

        if label_shift_days > 0:
            shifted_price = group[price_col].shift(-label_shift_days)
        else:
            shifted_price = group[price_col]
        entry_price = shifted_price
        if label_horizon_mode == "next_rebalance" and label_next_rebalance_map is not None:
            exit_base = group["trade_date"].map(label_next_rebalance_map)
            shifted_by_date = pd.Series(shifted_price.values, index=group["trade_date"])
            exit_price = exit_base.map(shifted_by_date)
        else:
            exit_price = shifted_price.shift(-label_horizon_days)
        group[target] = exit_price / entry_price - 1.0

        return group

    df = df.groupby("symbol", group_keys=False).apply(add_features)

    missing_features = [feat for feat in features if feat not in df.columns]
    if missing_features:
        if fundamentals_allow_missing:
            logger.warning("Dropping missing features: %s", missing_features)
            features = [feat for feat in features if feat in df.columns]
        else:
            sys.exit(f"Missing features after engineering: {missing_features}")

    meta_cols = ["is_tradable"] if "is_tradable" in df.columns else []
    eval_extra_df = None
    bucket_cols = []
    if bucket_ic_enabled and bucket_ic_schemes:
        bucket_cols = list(dict.fromkeys([scheme["column"] for scheme in bucket_ic_schemes]))
        missing_bucket_cols = [col for col in bucket_cols if col not in df.columns]
        if missing_bucket_cols:
            logger.warning("Bucket IC columns missing in data: %s", missing_bucket_cols)
        bucket_cols = [col for col in bucket_cols if col in df.columns]
        if bucket_cols:
            eval_extra_df = df[["trade_date", "symbol"] + bucket_cols].copy()

    missing_fill_features = feature_missing_features or features
    missing_fill_features = [
        feature for feature in missing_fill_features if feature in features and feature in df.columns
    ]
    if feature_missing_add_indicators and missing_fill_features:
        indicator_features = []
        for feature in missing_fill_features:
            indicator_name = f"{feature}{feature_missing_suffix}"
            if indicator_name in df.columns and indicator_name not in features:
                sys.exit(
                    "features.missing.indicator_suffix collides with an existing column: "
                    f"{indicator_name}"
                )
            if indicator_name not in df.columns:
                df[indicator_name] = df[feature].isna().astype(np.int8)
            indicator_features.append(indicator_name)
        features = list(dict.fromkeys(features + indicator_features))

    df = _ensure_symbol_alias(df)
    execution_passthrough_cols = [
        col for col in execution_pricing_cols if col in df.columns and col != price_col
    ]
    price_passthrough_cols = list(
        dict.fromkeys(
            execution_passthrough_cols
            + [col for col in ("close", "tr_close") if col in df.columns and col != price_col]
        )
    )

    backtest_pricing_cols = [
        "trade_date",
        "symbol",
        price_col,
        *execution_passthrough_cols,
    ]
    if backtest_tradable_col and backtest_tradable_col in df.columns:
        backtest_pricing_cols.append(backtest_tradable_col)
    backtest_pricing_cols = list(dict.fromkeys(backtest_pricing_cols))
    backtest_pricing_df = (
        df[backtest_pricing_cols]
        .drop_duplicates(subset=["trade_date", "symbol"])
        .copy()
    )

    passthrough_cols = list(dict.fromkeys(industry_cols))
    cols = (
        ["trade_date", "symbol", price_col]
        + features
        + price_passthrough_cols
        + passthrough_cols
        + meta_cols
        + [target]
    )
    cols = list(dict.fromkeys(cols))
    df = df[cols].copy()

    if universe_by_date is not None:
        before_rows = len(df)
        df = apply_universe_by_date(df, universe_by_date)
        after_rows = len(df)
        logger.info("Applied universe-by-date filter: %s -> %s rows", before_rows, after_rows)
        if df.empty:
            sys.exit("Universe-by-date filter removed all rows.")

    if feature_missing_method != "none" and missing_fill_features:
        for feature in missing_fill_features:
            df[feature] = pd.to_numeric(df[feature], errors="coerce")
        if feature_missing_method == "zero":
            df[missing_fill_features] = df[missing_fill_features].fillna(0.0)
        elif feature_missing_method == "cross_sectional_median":
            by_date_median = df.groupby("trade_date")[missing_fill_features].transform("median")
            df[missing_fill_features] = df[missing_fill_features].fillna(by_date_median)
        remaining_missing = int(df[missing_fill_features].isna().sum().sum())
        logger.info(
            "Applied feature missing fill: method=%s, features=%s, add_indicators=%s, remaining_nans=%s.",
            feature_missing_method,
            len(missing_fill_features),
            feature_missing_add_indicators,
            remaining_missing,
        )

    required_cols = [price_col] + features
    df_features = df.dropna(subset=required_cols).reset_index(drop=True)

    if winsorize_pct:

        def _winsorize(group: pd.DataFrame) -> pd.DataFrame:
            lower = group[target].quantile(winsorize_pct)
            upper = group[target].quantile(1 - winsorize_pct)
            group[target] = group[target].clip(lower, upper)
            return group

        df_features = df_features.groupby("trade_date", group_keys=False).apply(_winsorize)

    if cs_method != "none":
        df_features = apply_cross_sectional_transform(
            df_features, features, cs_method, cs_winsorize_pct
        )

    if train_target != target:
        df_features[train_target] = apply_cross_sectional_series_transform(
            df_features,
            target,
            train_target_transform,
        )
        logger.info(
            "Applied training target transform: base=%s, method=%s, train_target=%s",
            target,
            train_target_transform,
            train_target,
        )

    dataset_schema = DatasetSchema(
        date_col="trade_date",
        instrument_col="symbol",
        price_col=price_col,
        label_col=target,
        tradable_col="is_tradable" if "is_tradable" in df_features.columns else None,
        feature_cols=features,
        extra_cols=[
            *price_passthrough_cols,
            *passthrough_cols,
            *([train_target] if train_target != target else []),
        ],
    )
    dataset = build_dataset(df_features, dataset_schema)
    df_features = dataset.frame
    df_full = df_features.dropna().reset_index(drop=True)
    if eval_extra_df is not None and not eval_extra_df.empty:
        eval_extra_df = eval_extra_df.drop_duplicates(subset=["trade_date", "symbol"])
        extra_eval_cols = [
            col
            for col in eval_extra_df.columns
            if col not in {"trade_date", "symbol"} and col not in df_full.columns
        ]
        if extra_eval_cols:
            df_full = df_full.merge(
                eval_extra_df[["trade_date", "symbol"] + extra_eval_cols],
                on=["trade_date", "symbol"],
                how="left",
            )

    (
        df_full_sorted,
        all_dates_full,
        full_date_start_rows,
        full_date_end_rows,
        full_date_to_pos,
    ) = _build_trade_date_slices(df_full)
    if sample_on_rebalance_dates:
        rebalance_dates_all = get_rebalance_dates(all_dates_full, rebalance_frequency)
        df_model_all = _slice_trade_dates(
            df_full_sorted,
            full_date_start_rows,
            full_date_end_rows,
            full_date_to_pos,
            rebalance_dates_all,
        )
    else:
        df_model_all = df_full_sorted

    date_counts = df_model_all.groupby("trade_date")["symbol"].nunique()
    valid_dates = date_counts[date_counts >= min_symbols_per_date].index
    dropped_date_counts = date_counts[date_counts < min_symbols_per_date].sort_index()
    (
        df_model_all_sorted,
        all_dates_model_full,
        model_date_start_rows,
        model_date_end_rows,
        model_date_to_pos,
    ) = _build_trade_date_slices(df_model_all)
    if len(valid_dates) != len(date_counts):
        df_model_all = _slice_trade_dates(
            df_model_all_sorted,
            model_date_start_rows,
            model_date_end_rows,
            model_date_to_pos,
            valid_dates.to_numpy(),
        )
        (
            df_model_all_sorted,
            all_dates_model_full,
            model_date_start_rows,
            model_date_end_rows,
            model_date_to_pos,
        ) = _build_trade_date_slices(df_model_all)
    else:
        df_model_all = df_model_all_sorted
    if not dropped_date_counts.empty:
        logger.info(
            "Dropped %s dates with < %s symbols (min=%s, max=%s).",
            len(dropped_date_counts),
            min_symbols_per_date,
            int(dropped_date_counts.min()),
            int(dropped_date_counts.max()),
        )

    return {
        "features": features,
        "dataset": dataset,
        "df_features": df_features,
        "df_full": df_full,
        "df_full_sorted": df_full_sorted,
        "all_dates_full": all_dates_full,
        "full_date_start_rows": full_date_start_rows,
        "full_date_end_rows": full_date_end_rows,
        "full_date_to_pos": full_date_to_pos,
        "df_model_all": df_model_all,
        "df_model_all_sorted": df_model_all_sorted,
        "all_dates_model_full": all_dates_model_full,
        "model_date_start_rows": model_date_start_rows,
        "model_date_end_rows": model_date_end_rows,
        "model_date_to_pos": model_date_to_pos,
        "valid_dates": valid_dates,
        "valid_dates_set": set(pd.to_datetime(valid_dates)),
        "dropped_date_counts": dropped_date_counts,
        "backtest_pricing_df": backtest_pricing_df,
        "bucket_cols": bucket_cols,
        "passthrough_cols": passthrough_cols,
        "price_passthrough_cols": price_passthrough_cols,
    }
