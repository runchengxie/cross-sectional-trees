from __future__ import annotations

import logging
import math
import re
from datetime import date, datetime
from typing import Any, Sequence
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from . import alloc as base_alloc
from .alloc_hk_common import (
    coerce_scalar,
    get_attr_or_key,
    is_missing_value,
    pick_last_non_missing,
    pick_round_lot,
    safe_float,
    to_date,
    to_timestamp,
)
from .alloc_hk_types import MarketDataBundle, SelectedTicker

LOGGER = logging.getLogger(__name__)

STOCK_CONNECT_TRUE_VALUES: set[str] = {
    "1",
    "true",
    "yes",
    "y",
    "是",
    "沪港通",
    "深港通",
    "southbound",
    "eligible",
    "sh",
    "sz",
    "沪",
    "深",
}

STOCK_CONNECT_FALSE_VALUES: set[str] = {
    "",
    "0",
    "false",
    "no",
    "n",
    "none",
    "nan",
    "null",
    "否",
    "不是",
    "不可",
    "不支持",
    "not eligible",
}


def build_order_book_mapping(
    tickers: Sequence[SelectedTicker],
) -> tuple[list[str], list[str], dict[str, str]]:
    symbols = [item.symbol for item in tickers]
    order_book_ids = [base_alloc._to_rq_order_book_id(symbol, "hk") for symbol in symbols]
    symbol_to_oid = dict(zip(symbols, order_book_ids))
    return symbols, order_book_ids, symbol_to_oid


def normalize_close_output(px: pd.DataFrame | None, order_book_ids: Sequence[str]) -> pd.DataFrame:
    if px is None:
        return pd.DataFrame(columns=list(order_book_ids))

    if isinstance(px.index, pd.MultiIndex):
        close = px["close"].unstack(0)
    elif isinstance(px.columns, pd.MultiIndex):
        close = (
            px["close"]
            if "close" in px.columns.get_level_values(0)
            else px.xs("close", axis=1, level=1)
        )
    else:
        if list(px.columns) == ["close"]:
            close = px.rename(columns={"close": order_book_ids[0]})
        else:
            close = px.copy()

    if isinstance(close, pd.Series):
        close = close.to_frame(name=order_book_ids[0])

    close.index = pd.to_datetime(close.index)
    close = close.sort_index()

    for oid in order_book_ids:
        if oid not in close.columns:
            close[oid] = np.nan

    return close[list(order_book_ids)]


def fetch_instruments(rqdatac_module: Any, order_book_ids: Sequence[str], market: str) -> pd.DataFrame:
    instruments = rqdatac_module.instruments(list(order_book_ids), market=market)
    if not isinstance(instruments, list):
        instruments = [instruments]

    rows: list[dict[str, Any]] = []
    for ins in instruments:
        if ins is None:
            continue
        rows.append(
            {
                "order_book_id": ins.order_book_id,
                "symbol": getattr(ins, "symbol", None),
                "round_lot": safe_float(getattr(ins, "round_lot", np.nan)),
                "stock_connect": getattr(ins, "stock_connect", None),
            }
        )

    if not rows:
        return pd.DataFrame(columns=["symbol", "round_lot", "stock_connect"])

    raw = pd.DataFrame(rows)
    grouped = (
        raw.groupby("order_book_id", sort=False, as_index=True)
        .agg(
            symbol=("symbol", lambda s: pick_last_non_missing(s.tolist())),
            round_lot=("round_lot", lambda s: pick_round_lot(s.tolist(), logger=LOGGER)),
            stock_connect=("stock_connect", lambda s: pick_last_non_missing(s.tolist())),
        )
    )
    return grouped


def fetch_close_prices(
    rqdatac_module: Any,
    order_book_ids: Sequence[str],
    start_date: date,
    end_date: date,
    market: str,
    adjust_type: str,
) -> pd.DataFrame:
    px = rqdatac_module.get_price(
        list(order_book_ids),
        start_date=start_date,
        end_date=end_date,
        frequency="1d",
        fields=["close"],
        adjust_type=adjust_type,
        market=market,
        expect_df=True,
    )
    return normalize_close_output(px, order_book_ids)


def empty_live_price_frame(order_book_ids: Sequence[str]) -> pd.DataFrame:
    return pd.DataFrame(
        index=list(order_book_ids),
        data={"price": np.nan, "pricing_ts": pd.NaT},
    )


def fetch_snapshot_prices(
    rqdatac_module: Any,
    order_book_ids: Sequence[str],
    market: str,
) -> pd.DataFrame:
    empty = empty_live_price_frame(order_book_ids)

    try:
        snapshots = rqdatac_module.current_snapshot(list(order_book_ids), market=market)
    except Exception:
        return empty

    if snapshots is None:
        return empty
    if not isinstance(snapshots, list):
        snapshots = [snapshots]

    rows: list[dict[str, Any]] = []
    for snap in snapshots:
        if snap is None:
            continue

        oid = get_attr_or_key(snap, "order_book_id")
        if is_missing_value(oid):
            continue

        last = safe_float(get_attr_or_key(snap, "last"))
        close = safe_float(get_attr_or_key(snap, "close"))
        price = last if last > 0 else close if close > 0 else np.nan
        pricing_ts = to_timestamp(get_attr_or_key(snap, "datetime"))
        rows.append(
            {
                "order_book_id": str(oid),
                "price": price,
                "pricing_ts": pricing_ts,
            }
        )

    if not rows:
        return empty

    snap_df = pd.DataFrame(rows).drop_duplicates(subset=["order_book_id"], keep="last")
    snap_df = snap_df.set_index("order_book_id")[["price", "pricing_ts"]]
    empty.update(snap_df)
    return empty


def fetch_current_minute_prices(
    rqdatac_module: Any,
    order_book_ids: Sequence[str],
    market: str,
) -> pd.DataFrame:
    empty = empty_live_price_frame(order_book_ids)

    minute_df: pd.DataFrame | None
    try:
        minute_df = rqdatac_module.current_minute(list(order_book_ids), fields=["close"], market=market)
    except TypeError:
        try:
            minute_df = rqdatac_module.current_minute(list(order_book_ids), market=market)
        except Exception:
            return empty
    except Exception:
        return empty

    if minute_df is None or minute_df.empty:
        return empty

    frame = minute_df.reset_index()
    if "order_book_id" not in frame.columns:
        return empty

    price_field = "close" if "close" in frame.columns else "last" if "last" in frame.columns else None
    if price_field is None:
        return empty
    if "datetime" not in frame.columns:
        frame["datetime"] = pd.NaT

    frame["price"] = pd.to_numeric(frame[price_field], errors="coerce")
    frame["pricing_ts"] = pd.to_datetime(frame["datetime"], errors="coerce")
    frame = frame.sort_values(["order_book_id", "pricing_ts"], na_position="last")
    frame = frame.groupby("order_book_id", as_index=False).tail(1)

    latest = frame.set_index("order_book_id")[["price", "pricing_ts"]]
    empty.update(latest)
    return empty


def should_try_live_prices(as_of: date, market: str) -> bool:
    market_key = str(market).strip().lower()
    if market_key == "hk":
        today = datetime.now(ZoneInfo("Asia/Hong_Kong")).date()
        return as_of == today
    return as_of == datetime.now().date()


def get_previous_trading_date(
    rqdatac_module: Any,
    ref_date: date,
    n: int,
    market: str,
) -> date:
    try:
        result = rqdatac_module.get_previous_trading_date(ref_date, n=n, market=market)
    except TypeError:
        result = rqdatac_module.get_previous_trading_date(ref_date, n, market=market)
    return to_date(result)


def build_latest_price_frame(
    rqdatac_module: Any,
    order_book_ids: Sequence[str],
    as_of: date,
    market: str,
) -> pd.DataFrame:
    price_start = get_previous_trading_date(rqdatac_module, as_of, n=10, market=market)
    close_today = fetch_close_prices(
        rqdatac_module,
        order_book_ids,
        start_date=price_start,
        end_date=as_of,
        market=market,
        adjust_type="none",
    )
    if close_today.empty:
        raise SystemExit("No recent HK close price returned for allocation.")

    close_today_clean = close_today.dropna(how="all")
    if close_today_clean.empty:
        raise SystemExit("Recent HK close prices are all missing for the selected tickers.")

    latest_close_ts = pd.Timestamp(close_today_clean.index[-1])
    latest_close_row = close_today_clean.iloc[-1].reindex(list(order_book_ids))

    price_frame = pd.DataFrame(
        index=list(order_book_ids),
        data={
            "price": pd.to_numeric(latest_close_row, errors="coerce"),
            "price_source": "1d_close",
            "pricing_ts": latest_close_ts,
        },
    )

    if should_try_live_prices(as_of=as_of, market=market):
        snapshot_frame = fetch_snapshot_prices(rqdatac_module, order_book_ids, market=market)
        minute_frame = fetch_current_minute_prices(rqdatac_module, order_book_ids, market=market)

        for oid in order_book_ids:
            snapshot_price = safe_float(snapshot_frame.at[oid, "price"])
            if snapshot_price > 0:
                price_frame.at[oid, "price"] = snapshot_price
                price_frame.at[oid, "price_source"] = "snapshot"
                snapshot_ts = to_timestamp(snapshot_frame.at[oid, "pricing_ts"])
                if pd.notna(snapshot_ts):
                    price_frame.at[oid, "pricing_ts"] = snapshot_ts
                continue

            minute_price = safe_float(minute_frame.at[oid, "price"])
            if minute_price > 0:
                price_frame.at[oid, "price"] = minute_price
                price_frame.at[oid, "price_source"] = "1m_close"
                minute_ts = to_timestamp(minute_frame.at[oid, "pricing_ts"])
                if pd.notna(minute_ts):
                    price_frame.at[oid, "pricing_ts"] = minute_ts

    price_frame["pricing_date"] = pd.to_datetime(price_frame["pricing_ts"], errors="coerce").dt.date
    fallback_date = to_date(latest_close_ts)
    price_frame["pricing_date"] = price_frame["pricing_date"].fillna(fallback_date)
    return price_frame


def last_value_percentile(values: np.ndarray) -> float:
    if values.size == 0 or np.isnan(values[-1]):
        return np.nan
    valid = values[~np.isnan(values)]
    if valid.size == 0:
        return np.nan
    return float(np.mean(valid <= values[-1]))


def compute_valuation_metrics(
    close_pre: pd.DataFrame,
    window: int,
    sell_quantile: float,
    extreme_quantile: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    q_high = close_pre.rolling(window=window, min_periods=window).quantile(sell_quantile)
    q_extreme = close_pre.rolling(window=window, min_periods=window).quantile(extreme_quantile)
    percentile = close_pre.rolling(window=window, min_periods=window).apply(last_value_percentile, raw=True)

    log_price = np.log(close_pre.where(close_pre > 0))
    mean = log_price.rolling(window=window, min_periods=window).mean()
    std = log_price.rolling(window=window, min_periods=window).std()
    zscore = (log_price - mean) / std

    return percentile, zscore, q_high, q_extreme


def classify_valuation(
    percentile: float,
    zscore: float,
    sell_quantile: float,
    extreme_quantile: float,
) -> str:
    if math.isnan(percentile) and math.isnan(zscore):
        return "NA"
    if (
        not math.isnan(percentile)
        and percentile >= extreme_quantile
    ) or (
        not math.isnan(zscore)
        and zscore >= 2.5
    ):
        return "EXTREME"
    if (
        not math.isnan(percentile)
        and percentile >= sell_quantile
    ) or (
        not math.isnan(zscore)
        and zscore >= 2.0
    ):
        return "HIGH"
    if (
        not math.isnan(percentile)
        and percentile <= (1 - sell_quantile)
    ) or (
        not math.isnan(zscore)
        and zscore <= -2.0
    ):
        return "LOW"
    return "NEUTRAL"


def is_stock_connect_tradable(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if is_missing_value(value):
        return False
    if isinstance(value, (list, tuple, set)):
        return any(is_stock_connect_tradable(item) for item in value)

    text = re.sub(r"\s+", " ", str(value).strip().lower())
    if text in STOCK_CONNECT_TRUE_VALUES:
        return True
    if text in STOCK_CONNECT_FALSE_VALUES:
        return False

    tokens = [token for token in re.split(r"[,\s/|]+", text) if token]
    if tokens:
        if any(token in STOCK_CONNECT_TRUE_VALUES for token in tokens):
            return True
        if all(token in STOCK_CONNECT_FALSE_VALUES for token in tokens):
            return False
    return False


def prefetch_market_data(
    rqdatac_module: Any,
    tickers: Sequence[SelectedTicker],
    as_of: date,
    *,
    history_years: int,
    roll_window: int,
) -> MarketDataBundle:
    symbols, order_book_ids, symbol_to_oid = build_order_book_mapping(tickers)
    if not order_book_ids:
        raise SystemExit("No holdings selected for market data prefetch.")

    instruments_df = fetch_instruments(rqdatac_module, order_book_ids, market="hk")
    latest_prices = build_latest_price_frame(
        rqdatac_module,
        order_book_ids=order_book_ids,
        as_of=as_of,
        market="hk",
    )

    hist_days = max(history_years * 252, roll_window + 5)
    hist_start = get_previous_trading_date(rqdatac_module, as_of, n=hist_days, market="hk")

    close_none = fetch_close_prices(
        rqdatac_module,
        order_book_ids,
        start_date=hist_start,
        end_date=as_of,
        market="hk",
        adjust_type="none",
    )
    close_pre = fetch_close_prices(
        rqdatac_module,
        order_book_ids,
        start_date=hist_start,
        end_date=as_of,
        market="hk",
        adjust_type="pre",
    )

    return MarketDataBundle(
        symbols=tuple(symbols),
        order_book_ids=tuple(order_book_ids),
        symbol_to_oid=symbol_to_oid,
        instruments_df=instruments_df,
        latest_prices=latest_prices,
        close_none=close_none,
        close_pre=close_pre,
    )


def subset_market_data(
    bundle: MarketDataBundle,
    order_book_ids: Sequence[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    missing = [oid for oid in order_book_ids if oid not in bundle.order_book_ids]
    if missing:
        raise SystemExit(f"Market data bundle missing order_book_ids: {', '.join(missing)}")

    instruments = bundle.instruments_df.reindex(list(order_book_ids))
    latest_prices = bundle.latest_prices.reindex(list(order_book_ids))
    close_none = bundle.close_none.reindex(columns=list(order_book_ids))
    close_pre = bundle.close_pre.reindex(columns=list(order_book_ids))
    return instruments, latest_prices, close_none, close_pre
