from __future__ import annotations

from typing import Any

import pandas as pd

from market_data_platform.data_provider_contracts import to_rqdata_symbol


def to_rq_order_book_id(symbol: str, market: str | None) -> str:
    text = str(symbol or "").strip().upper()
    if not text:
        return text
    market_text = str(market or "").strip().lower()
    if text.endswith((".XHKG", ".XSHG", ".XSHE")):
        return text

    if text.endswith(".HK") or market_text == "hk":
        if text.endswith(".HK"):
            text = text[:-3]
        if text.endswith(".XHKG"):
            text = text[:-5]
        if text.isdigit():
            text = text.zfill(5)
        return f"{text}.XHKG"

    if text.endswith((".SH", ".SZ")) or market_text == "a_share":
        return to_rqdata_symbol("a_share", text)

    raise SystemExit(f"Unsupported symbol '{symbol}'. Supported markets: hk, a_share.")


def resolve_price_date(rqdatac: Any, as_of: pd.Timestamp, market: str | None) -> pd.Timestamp:
    get_trading_dates = getattr(rqdatac, "get_trading_dates", None)
    if get_trading_dates is None:
        return as_of
    start = (as_of - pd.Timedelta(days=366)).strftime("%Y%m%d")
    end = as_of.strftime("%Y%m%d")
    kwargs = {"market": market} if market else {}
    try:
        trading_dates = get_trading_dates(start, end, **kwargs)
    except TypeError:
        trading_dates = get_trading_dates(start, end)
    except Exception:
        return as_of
    if not trading_dates:
        return as_of
    parsed = pd.to_datetime(list(trading_dates), errors="coerce")
    parsed = [pd.Timestamp(ts).normalize() for ts in parsed if pd.notna(ts)]
    parsed = [ts for ts in parsed if ts <= as_of]
    if not parsed:
        return as_of
    return max(parsed)


def extract_price_wide_frame(
    payload: Any,
    field: str,
    order_book_ids: list[str],
) -> pd.DataFrame:
    if payload is None:
        return pd.DataFrame()

    if isinstance(payload, pd.Series):
        if isinstance(payload.index, pd.MultiIndex):
            if "order_book_id" in payload.index.names:
                wide = payload.unstack("order_book_id")
            else:
                wide = payload.unstack(level=0)
        else:
            wide = payload.to_frame(name=order_book_ids[0] if order_book_ids else "value")
    elif isinstance(payload, pd.DataFrame):
        if payload.empty:
            return payload
        if isinstance(payload.index, pd.MultiIndex):
            if field in payload.columns:
                values = payload[field]
            elif payload.shape[1] == 1:
                values = payload.iloc[:, 0]
            else:
                raise SystemExit(f"get_price result is missing '{field}' column.")
            if "order_book_id" in payload.index.names:
                wide = values.unstack("order_book_id")
            else:
                wide = values.unstack(level=0)
        else:
            if set(order_book_ids).issubset(payload.columns):
                wide = payload[order_book_ids].copy()
            elif field in payload.columns and len(order_book_ids) == 1:
                wide = payload[[field]].rename(columns={field: order_book_ids[0]})
            elif {"order_book_id", field}.issubset(payload.columns):
                date_col = None
                for candidate in ("date", "trade_date", "datetime", "time"):
                    if candidate in payload.columns:
                        date_col = candidate
                        break
                if not date_col:
                    raise SystemExit(
                        "Unable to parse get_price output: missing date column for long-form frame."
                    )
                wide = payload.pivot(index=date_col, columns="order_book_id", values=field)
            elif len(order_book_ids) == 1 and payload.shape[1] == 1:
                wide = payload.copy()
                wide.columns = [order_book_ids[0]]
            else:
                raise SystemExit("Unexpected get_price output format.")
    else:
        raise SystemExit("Unexpected get_price output type.")

    wide = wide.copy()
    wide.index = pd.to_datetime(wide.index, errors="coerce")
    wide = wide[wide.index.notna()]
    return wide.sort_index()


def fetch_latest_price_map(
    rqdatac: Any,
    order_book_ids: list[str],
    *,
    field: str,
    start_date: str,
    end_date: str,
    market: str | None,
) -> dict[str, float]:
    kwargs = {
        "frequency": "1d",
        "fields": [field],
        "expect_df": True,
    }
    if market:
        kwargs["market"] = market
    try:
        payload = rqdatac.get_price(order_book_ids, start_date, end_date, **kwargs)
    except TypeError:
        kwargs.pop("expect_df", None)
        payload = rqdatac.get_price(order_book_ids, start_date, end_date, **kwargs)
    if payload is None:
        raise SystemExit("rqdatac.get_price returned no data.")

    wide = extract_price_wide_frame(payload, field, order_book_ids)
    if wide.empty:
        raise SystemExit("rqdatac.get_price returned an empty frame.")

    price_map: dict[str, float] = {}
    missing: list[str] = []
    for order_book_id in order_book_ids:
        if order_book_id not in wide.columns:
            missing.append(order_book_id)
            continue
        values = pd.to_numeric(wide[order_book_id], errors="coerce").dropna()
        if values.empty:
            missing.append(order_book_id)
            continue
        price_map[order_book_id] = float(values.iloc[-1])
    if missing:
        joined = ", ".join(missing)
        raise SystemExit(
            f"Missing '{field}' price for {len(missing)} symbol(s): {joined}."
        )
    return price_map


def fetch_round_lot_map(
    rqdatac: Any,
    order_book_ids: list[str],
    market: str | None,
) -> dict[str, int]:
    kwargs = {"market": market} if market else {}
    try:
        instruments = rqdatac.instruments(order_book_ids, **kwargs)
    except TypeError:
        instruments = rqdatac.instruments(order_book_ids)

    if not isinstance(instruments, list):
        instruments = [instruments]
    lot_map: dict[str, int] = {}
    for ins in instruments:
        if ins is None:
            continue
        order_book_id = getattr(ins, "order_book_id", None)
        if order_book_id is None:
            continue
        round_lot = getattr(ins, "round_lot", None)
        try:
            lot_map[str(order_book_id)] = max(1, int(round_lot))
        except (TypeError, ValueError):
            continue
    for order_book_id in order_book_ids:
        lot_map.setdefault(order_book_id, 1)
    return lot_map
