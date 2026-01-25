# -*- coding: utf-8 -*-
"""Build a PIT HK Connect universe with liquidity filtering."""
from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv


def validate_yyyymmdd(value: str, label: str) -> str:
    if not value or len(value) != 8 or not value.isdigit():
        raise SystemExit(f"{label} must be in YYYYMMDD format.")
    return value


def parse_date(value: str) -> pd.Timestamp:
    value = validate_yyyymmdd(value, "date")
    return pd.to_datetime(value, format="%Y%m%d")


def normalize_hk_symbol(order_book_id: str) -> str:
    text = str(order_book_id or "").strip().upper()
    if not text:
        return text
    if text.endswith(".XHKG"):
        text = text[:-5]
    if text.endswith(".HK"):
        text = text[:-3]
    if text.isdigit():
        text = text.zfill(5)
    return f"{text}.HK"


def get_rebalance_dates(dates: list[pd.Timestamp], freq: str) -> list[pd.Timestamp]:
    if not freq or freq.upper() == "D":
        return list(dates)
    date_df = pd.DataFrame({"date": pd.to_datetime(dates)})
    date_df["period"] = date_df["date"].dt.to_period(freq)
    return date_df.groupby("period")["date"].max().sort_values().tolist()


def coerce_trading_dates(dates) -> list[pd.Timestamp]:
    return sorted(pd.to_datetime(list(dates)))


def require_rqdata(username: str | None, password: str | None):
    try:
        import rqdatac
    except ImportError as exc:
        raise SystemExit(f"rqdatac is required ({exc}).")
    try:
        import rqdatac_hk  # noqa: F401
    except ImportError as exc:
        raise SystemExit(f"rqdatac_hk is required ({exc}).")

    init_kwargs = {}
    if username:
        init_kwargs["username"] = username
    if password:
        init_kwargs["password"] = password
    try:
        rqdatac.init(**init_kwargs)
    except Exception as exc:
        raise SystemExit(f"rqdatac.init failed: {exc}")
    return rqdatac


def fetch_southbound_membership(rqdatac, dates: list[pd.Timestamp]) -> dict[pd.Timestamp, set[str]]:
    membership = {}
    for date in dates:
        date_str = date.strftime("%Y%m%d")
        sh_list = rqdatac.hk.get_southbound_eligible_secs(trading_type="sh", date=date_str)
        sz_list = rqdatac.hk.get_southbound_eligible_secs(trading_type="sz", date=date_str)
        combined = set(sh_list or []) | set(sz_list or [])
        membership[date.normalize()] = combined
    return membership


def prepare_turnover_table(
    rqdatac,
    order_book_ids: list[str],
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    df = rqdatac.get_price(
        order_book_ids,
        start_date,
        end_date,
        frequency="1d",
        fields=["total_turnover"],
        market="hk",
        expect_df=True,
    )
    if df is None or df.empty:
        raise SystemExit("get_price returned no turnover data.")

    if isinstance(df.index, pd.MultiIndex):
        if "order_book_id" in df.index.names:
            turnover = df["total_turnover"].unstack("order_book_id")
        else:
            turnover = df["total_turnover"].unstack(level=0)
    else:
        turnover = df[["total_turnover"]].rename(columns={"total_turnover": order_book_ids[0]})

    turnover.index = pd.to_datetime(turnover.index)
    return turnover.sort_index()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build HK Connect universe (PIT + liquidity).")
    parser.add_argument("--start-date", help="Start date in YYYYMMDD")
    parser.add_argument("--end-date", help="End date in YYYYMMDD")
    parser.add_argument("--as-of", help="Single as-of date in YYYYMMDD (live mode)")
    parser.add_argument("--rebalance-frequency", default="M", help="Rebalance frequency (default: M)")
    parser.add_argument("--lookback-days", type=int, default=60, help="Lookback trading days (default: 60)")
    parser.add_argument("--min-window-days", type=int, default=30, help="Minimum valid days in window (default: 30)")
    parser.add_argument("--top-quantile", type=float, default=0.8, help="Liquidity quantile threshold (default: 0.8)")
    parser.add_argument("--out", default="universe_by_date.csv", help="Output CSV path")
    parser.add_argument("--latest-out", help="Optional symbols_file output for latest rebalance date")
    parser.add_argument("--rqdata-user", help="RQData username (optional)")
    parser.add_argument("--rqdata-pass", help="RQData password (optional)")
    args = parser.parse_args()

    load_dotenv()
    rq_user = args.rqdata_user or os.getenv("RQDATA_USERNAME") or os.getenv("RQDATA_USER")
    rq_pass = args.rqdata_pass or os.getenv("RQDATA_PASSWORD")

    if args.as_of:
        start_date = parse_date(args.as_of)
        end_date = start_date
    else:
        if not (args.start_date and args.end_date):
            raise SystemExit("Provide --start-date and --end-date, or use --as-of.")
        start_date = parse_date(args.start_date)
        end_date = parse_date(args.end_date)

    if not 0 < args.top_quantile < 1:
        raise SystemExit("top-quantile must be between 0 and 1.")

    rqdatac = require_rqdata(rq_user, rq_pass)

    buffer_days = max(args.lookback_days * 3, 90)
    extended_start = (start_date - pd.Timedelta(days=buffer_days)).strftime("%Y%m%d")
    trade_dates = coerce_trading_dates(
        rqdatac.get_trading_dates(extended_start, end_date.strftime("%Y%m%d"), market="hk")
    )
    if not trade_dates:
        raise SystemExit("No trading dates returned for the requested range.")

    trade_dates_in_range = [d for d in trade_dates if start_date <= d <= end_date]
    if not trade_dates_in_range:
        raise SystemExit("No trading dates in the requested range.")

    if args.as_of:
        rebalance_dates = [trade_dates_in_range[-1]]
    else:
        rebalance_dates = get_rebalance_dates(trade_dates_in_range, args.rebalance_frequency)
    if not rebalance_dates:
        raise SystemExit("No rebalance dates computed for the requested range.")

    membership = fetch_southbound_membership(rqdatac, rebalance_dates)
    all_symbols = sorted({sym for symbols in membership.values() for sym in symbols})
    if not all_symbols:
        raise SystemExit("No eligible HK Connect symbols returned.")

    turnover = prepare_turnover_table(
        rqdatac,
        all_symbols,
        trade_dates[0].strftime("%Y%m%d"),
        end_date.strftime("%Y%m%d"),
    )

    trade_index = {date.normalize(): idx for idx, date in enumerate(trade_dates)}
    results = []
    for reb_date in rebalance_dates:
        reb_date = reb_date.normalize()
        idx = trade_index.get(reb_date)
        if idx is None or idx == 0:
            continue
        window_end = idx - 1
        window_start = max(0, window_end - args.lookback_days + 1)
        window_dates = trade_dates[window_start : window_end + 1]
        window_data = turnover.reindex(window_dates)
        liq = window_data.median(axis=0, skipna=True)
        valid_counts = window_data.notna().sum(axis=0)
        liq = liq[valid_counts >= min(args.min_window_days, args.lookback_days)]

        eligible = membership.get(reb_date, set())
        if eligible:
            liq = liq[liq.index.isin(eligible)]
        if liq.empty:
            continue

        threshold = liq.quantile(args.top_quantile)
        selected = liq[liq >= threshold].sort_values(ascending=False)
        for order_book_id, metric in selected.items():
            results.append(
                {
                    "trade_date": reb_date.strftime("%Y%m%d"),
                    "ts_code": normalize_hk_symbol(order_book_id),
                    "liq_metric": float(metric),
                    "selected": 1,
                }
            )

    if not results:
        raise SystemExit("No symbols selected; check date range or parameters.")

    out_path = Path(args.out)
    pd.DataFrame(results).to_csv(out_path, index=False)
    print(f"Wrote universe rows: {len(results)} -> {out_path}")

    if args.latest_out:
        latest_date = max(row["trade_date"] for row in results)
        latest_symbols = sorted({row["ts_code"] for row in results if row["trade_date"] == latest_date})
        Path(args.latest_out).write_text("\n".join(latest_symbols), encoding="utf-8")
        print(f"Wrote latest symbols ({latest_date}) -> {args.latest_out}")


if __name__ == "__main__":
    main()
