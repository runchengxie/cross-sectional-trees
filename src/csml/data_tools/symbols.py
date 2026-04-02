from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

SYMBOL_COL = "symbol"
LEGACY_SYMBOL_COLUMNS = ("ts_code", "stock_ticker")
SYMBOL_INPUT_COLUMNS = ("symbol", "ts_code", "stock_ticker", "order_book_id")
DEFAULT_SYMBOL_PRIORITY = ("symbol", "ts_code", "stock_ticker", "order_book_id")
PROVIDER_SYMBOL_PRIORITY = ("ts_code", "stock_ticker", "order_book_id", "symbol")


def normalize_symbol_for_market(value: object, *, market: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if str(market or "").strip().lower() != "hk":
        return text

    upper = text.upper()
    if upper.endswith(".XHKG"):
        upper = upper[:-5]
    if upper.endswith(".HK"):
        upper = upper[:-3]
    if upper.isdigit():
        upper = upper.zfill(5)
    return f"{upper}.HK"


def _clean_symbol_series(values: pd.Series) -> pd.Series:
    text = values.where(values.notna(), "").astype(str).str.strip()
    return text


def normalize_symbol_standard_name(name: object) -> str:
    text = str(name or "").strip()
    if text in {SYMBOL_COL, *LEGACY_SYMBOL_COLUMNS, "order_book_id"}:
        return SYMBOL_COL
    return text


def resolve_symbol_series(
    df: pd.DataFrame,
    *,
    context: str,
    priority: Sequence[str] = DEFAULT_SYMBOL_PRIORITY,
) -> pd.Series:
    present_columns = [column for column in priority if column in df.columns]
    if not present_columns:
        raise SystemExit(f"{context} is missing symbol/stock_ticker/ts_code/order_book_id.")

    merged = _clean_symbol_series(df[present_columns[0]])
    for column in present_columns[1:]:
        series = _clean_symbol_series(df[column])
        merged = merged.where(merged != "", series)
    return merged


def ensure_symbol_columns(
    df: pd.DataFrame,
    *,
    context: str,
    priority: Sequence[str] = DEFAULT_SYMBOL_PRIORITY,
) -> pd.DataFrame:
    normalized = df.copy()
    merged = resolve_symbol_series(normalized, context=context, priority=priority)

    normalized[SYMBOL_COL] = merged
    return normalized


def drop_legacy_symbol_columns(
    df: pd.DataFrame,
    *,
    drop_order_book_id: bool = False,
) -> pd.DataFrame:
    drop_columns = [*LEGACY_SYMBOL_COLUMNS]
    if drop_order_book_id:
        drop_columns.append("order_book_id")
    out = df.drop(columns=drop_columns, errors="ignore")
    out.attrs = dict(getattr(df, "attrs", {}))
    return out


def canonicalize_symbol_columns(
    df: pd.DataFrame,
    *,
    context: str,
    priority: Sequence[str] = DEFAULT_SYMBOL_PRIORITY,
    drop_order_book_id: bool = False,
) -> pd.DataFrame:
    normalized = ensure_symbol_columns(df, context=context, priority=priority)
    return drop_legacy_symbol_columns(
        normalized,
        drop_order_book_id=drop_order_book_id,
    )
