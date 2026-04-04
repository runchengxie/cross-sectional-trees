from __future__ import annotations

import numpy as np
import pandas as pd
import pandas_ta as ta

from .support import _parse_window_config, parse_feature_windows


def engineer_symbol_features(
    group: pd.DataFrame,
    *,
    features: list[str],
    feature_params: dict,
    price_col: str,
    target: str,
    label_shift_days: int,
    label_horizon_days: int,
    label_horizon_mode: str,
    label_next_rebalance_map: dict[pd.Timestamp, pd.Timestamp] | None,
) -> pd.DataFrame:
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
