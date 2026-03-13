from __future__ import annotations

import pandas as pd


def _clean_symbol_series(values: pd.Series) -> pd.Series:
    text = values.where(values.notna(), "").astype(str).str.strip()
    return text


def ensure_symbol_columns(df: pd.DataFrame, *, context: str) -> pd.DataFrame:
    symbol_columns = ["symbol", "stock_ticker", "ts_code", "order_book_id"]
    present_columns = [column for column in symbol_columns if column in df.columns]
    if not present_columns:
        raise SystemExit(f"{context} is missing symbol/stock_ticker/ts_code/order_book_id.")

    normalized = df.copy()
    merged = pd.Series([""] * len(normalized), index=normalized.index, dtype="object")
    for column in present_columns[::-1]:
        series = _clean_symbol_series(normalized[column])
        merged = series.where(series != "", merged)

    normalized["ts_code"] = merged
    normalized["stock_ticker"] = merged
    normalized["symbol"] = merged
    return normalized
