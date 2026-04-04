from __future__ import annotations

import logging
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

from ..compat import ensure_numpy_nan_alias
from ..data_interface import DataInterface
from ..data_tools.symbols import canonicalize_symbol_columns
from ..rebalance import estimate_rebalance_gap, get_rebalance_dates
from .panel_enrichment import apply_fundamentals_enrichment, apply_industry_enrichment

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
    benchmark_compare_symbols: list[str] | None,
    drop_st: bool,
    min_listed_days: int,
    drop_suspended: bool,
    suspended_policy: str,
    min_turnover: float,
    fundamentals_enabled: bool,
    fundamentals_source: str,
    fundamentals_file_path: Path | None,
    data_cfg: Mapping[str, Any],
    fundamentals_cfg: Mapping[str, Any],
    requested_features: list[str],
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
    industry_enabled: bool,
    industry_file_path: Path | None,
    industry_cfg: Mapping[str, Any],
    industry_keep_columns: list[str],
    industry_ffill: bool,
    industry_ffill_limit: int | None,
    label_horizon_mode: str,
    label_rebalance_frequency: str,
) -> dict[str, Any]:
    benchmark_symbol = str(benchmark_symbol).strip() if benchmark_symbol else None
    compare_symbols = [
        str(symbol).strip()
        for symbol in (benchmark_compare_symbols or [])
        if str(symbol).strip()
    ]
    symbols_for_data = symbols[:]
    if benchmark_symbol and benchmark_symbol not in symbols_for_data:
        symbols_for_data.append(benchmark_symbol)
    for symbol in compare_symbols:
        if symbol not in symbols_for_data:
            symbols_for_data.append(symbol)

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
    benchmark_compare_dfs: dict[str, pd.DataFrame] = {}
    for symbol in compare_symbols:
        if benchmark_symbol and symbol == benchmark_symbol:
            compare_df = benchmark_df.copy() if benchmark_df is not None else pd.DataFrame()
        else:
            compare_df = df[df["symbol"] == symbol].copy()
            if symbol in symbols:
                logger.info(
                    "Compare benchmark symbol %s removed from modeling universe.",
                    symbol,
                )
            if not compare_df.empty:
                df = df[df["symbol"] != symbol].copy()
        if compare_df.empty:
            logger.warning(
                "Compare benchmark symbol %s returned no daily data; compare report for this symbol will be skipped.",
                symbol,
            )
        benchmark_compare_dfs[symbol] = compare_df
    symbols_for_non_price = [
        symbol
        for symbol in symbols_for_data
        if (not benchmark_symbol or symbol != benchmark_symbol) and symbol not in compare_symbols
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
    fund_cache_dir: Path | None = None
    provider_overlay_cache_dir: Path | None = None

    fundamentals_state = apply_fundamentals_enrichment(
        panel_df=df,
        data_interface=data_interface,
        symbols=symbols_for_non_price,
        start_date=start_date,
        end_date=end_date,
        market=market,
        data_cfg=data_cfg,
        fundamentals_cfg=fundamentals_cfg,
        requested_features=features,
        fundamentals_enabled=fundamentals_enabled,
        fundamentals_source=fundamentals_source,
        fundamentals_file_path=fundamentals_file_path,
        fundamentals_ffill=fundamentals_ffill,
        fundamentals_ffill_limit=fundamentals_ffill_limit,
        fundamentals_log_mcap=fundamentals_log_mcap,
        fundamentals_mcap_col=fundamentals_mcap_col,
        fundamentals_log_mcap_col=fundamentals_log_mcap_col,
        fundamentals_auto_add=fundamentals_auto_add,
        provider_overlay_enabled=provider_overlay_enabled,
        provider_overlay_cfg=provider_overlay_cfg,
        provider_overlay_auto_add=provider_overlay_auto_add,
        provider_overlay_features=provider_overlay_features,
    )
    df = fundamentals_state["df"]
    features = fundamentals_state["features"]
    fundamentals_cols = fundamentals_state["fundamentals_cols"]
    fund_cache_dir = fundamentals_state["fund_cache_dir"]
    provider_overlay_cache_dir = fundamentals_state["provider_overlay_cache_dir"]

    industry_state = apply_industry_enrichment(
        panel_df=df,
        data_interface=data_interface,
        symbols=symbols_for_non_price,
        start_date=start_date,
        end_date=end_date,
        market=market,
        data_cfg=data_cfg,
        industry_cfg=industry_cfg,
        industry_enabled=industry_enabled,
        industry_file_path=industry_file_path,
        industry_keep_columns=industry_keep_columns,
        industry_ffill=industry_ffill,
        industry_ffill_limit=industry_ffill_limit,
    )
    df = industry_state["df"]
    industry_cols = industry_state["industry_cols"]
    industry_source_df = industry_state["industry_source_df"]

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
        "benchmark_compare_dfs": benchmark_compare_dfs,
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
