from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd

from .alloc_hk_common import coerce_scalar as _coerce_scalar
from .alloc_hk_common import safe_float
from .alloc_hk_common import to_date as _to_date
from .alloc_hk_market_data import build_order_book_mapping as _build_order_book_mapping
from .alloc_hk_market_data import classify_valuation, compute_valuation_metrics
from .alloc_hk_market_data import subset_market_data as _subset_market_data
from .alloc_hk_types import HkAllocSettings, MarketDataBundle, SelectedTicker


def build_sell_signals(
    *,
    settings: HkAllocSettings,
    tickers: Sequence[SelectedTicker],
    market_data: MarketDataBundle,
) -> pd.DataFrame:
    _, order_book_ids, symbol_to_oid = _build_order_book_mapping(tickers)
    instruments_df, _, _, close_pre = _subset_market_data(market_data, order_book_ids)
    if close_pre.empty:
        raise SystemExit("No historical HK price data returned; cannot build sell signals.")

    percentile, zscore, q_high, q_extreme = compute_valuation_metrics(
        close_pre,
        window=settings.roll_window,
        sell_quantile=settings.sell_quantile,
        extreme_quantile=settings.extreme_quantile,
    )

    sell_trigger = q_high.shift(1)
    extreme_trigger = q_extreme.shift(1)
    signal = (close_pre >= sell_trigger) & (close_pre.shift(1) < sell_trigger)
    latest_row = close_pre.index.max()

    rows: list[dict[str, Any]] = []
    for item in tickers:
        symbol = item.symbol
        oid = symbol_to_oid[symbol]
        instrument_symbol = None
        if oid in instruments_df.index and "symbol" in instruments_df.columns:
            instrument_symbol = _coerce_scalar(instruments_df.loc[oid, "symbol"])

        col_signal = signal[oid].fillna(False)
        signal_dates = col_signal.index[col_signal]
        last_signal_date = signal_dates.max() if len(signal_dates) > 0 else pd.NaT

        current_price = safe_float(close_pre.loc[latest_row, oid]) if oid in close_pre.columns else np.nan
        pct = safe_float(percentile.loc[latest_row, oid]) if oid in percentile.columns else np.nan
        z_1y = safe_float(zscore.loc[latest_row, oid]) if oid in zscore.columns else np.nan
        high_line = safe_float(sell_trigger.loc[latest_row, oid]) if oid in sell_trigger.columns else np.nan
        extreme_line = safe_float(extreme_trigger.loc[latest_row, oid]) if oid in extreme_trigger.columns else np.nan

        rows.append(
            {
                "symbol": symbol,
                "name": item.name or (str(instrument_symbol).strip() if instrument_symbol else None),
                "side": item.side,
                "rank": item.rank,
                "signal": item.signal,
                "weight": item.weight,
                "order_book_id": oid,
                "as_of": _to_date(latest_row),
                "close_pre": current_price,
                "pct_1y": pct,
                "z_1y": z_1y,
                "sell_trigger": high_line,
                "extreme_trigger": extreme_line,
                "last_sell_signal_date": _to_date(last_signal_date) if pd.notna(last_signal_date) else None,
                "valuation": classify_valuation(
                    pct,
                    z_1y,
                    sell_quantile=settings.sell_quantile,
                    extreme_quantile=settings.extreme_quantile,
                ),
            }
        )

    return pd.DataFrame(rows)
