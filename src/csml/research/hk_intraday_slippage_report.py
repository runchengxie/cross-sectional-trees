#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from csml.repo_paths import find_repo_root, resolve_repo_path as resolve_repo_relative_path


REPO_ROOT = find_repo_root(__file__)
DEFAULT_REPORT_DIR = REPO_ROOT / "artifacts" / "reports"


def resolve_repo_path(path_text: str | Path) -> Path:
    return resolve_repo_relative_path(path_text, repo_root=REPO_ROOT)


def _bps(move: pd.Series) -> pd.Series:
    return move.astype(float) * 10_000.0


def compute_daily_slippage_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"trade_datetime", "open", "close", "volume", "amount"}
    missing = required.difference(frame.columns)
    if missing:
        raise SystemExit(f"Intraday frame is missing required columns: {sorted(missing)}")

    work = frame.copy()
    symbol_col = "ts_code" if "ts_code" in work.columns else "rq_order_book_id"
    if symbol_col not in work.columns:
        raise SystemExit("Intraday frame must contain ts_code or rq_order_book_id.")
    work["symbol"] = work[symbol_col].astype(str).str.upper()
    work["trade_datetime"] = pd.to_datetime(work["trade_datetime"], errors="coerce")
    work = work.dropna(subset=["trade_datetime", "symbol"]).copy()
    work["trade_date"] = work["trade_datetime"].dt.normalize()
    work = work.sort_values(["symbol", "trade_datetime"]).reset_index(drop=True)

    grouped = work.groupby(["symbol", "trade_date"], sort=True)
    summary = grouped.agg(
        open_price=("open", "first"),
        close_price=("close", "last"),
        session_volume=("volume", "sum"),
        session_amount=("amount", "sum"),
        first_bar_at=("trade_datetime", "first"),
        last_bar_at=("trade_datetime", "last"),
        bar_count=("trade_datetime", "size"),
    ).reset_index()
    summary["session_vwap"] = np.where(
        summary["session_volume"].astype(float) > 0,
        summary["session_amount"].astype(float) / summary["session_volume"].astype(float),
        np.nan,
    )
    summary["buy_open_to_vwap_bps"] = _bps(summary["session_vwap"] / summary["open_price"] - 1.0)
    summary["buy_open_to_close_bps"] = _bps(summary["close_price"] / summary["open_price"] - 1.0)
    summary["abs_open_to_vwap_bps"] = summary["buy_open_to_vwap_bps"].abs()
    summary["abs_open_to_close_bps"] = summary["buy_open_to_close_bps"].abs()
    return summary


def _metric_snapshot(series: pd.Series) -> dict[str, float | int | None]:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "std": None,
            "p10": None,
            "p25": None,
            "p75": None,
            "p90": None,
        }
    return {
        "count": int(clean.shape[0]),
        "mean": float(clean.mean()),
        "median": float(clean.median()),
        "std": float(clean.std(ddof=0)),
        "p10": float(clean.quantile(0.10)),
        "p25": float(clean.quantile(0.25)),
        "p75": float(clean.quantile(0.75)),
        "p90": float(clean.quantile(0.90)),
    }


def build_liquidity_bucket_summary(
    daily_metrics: pd.DataFrame,
    *,
    n_buckets: int = 5,
) -> pd.DataFrame:
    work = daily_metrics.copy()
    clean_amount = pd.to_numeric(work["session_amount"], errors="coerce")
    work = work[clean_amount.notna()].copy()
    if work.empty:
        return pd.DataFrame()

    rank = clean_amount.rank(method="first")
    work["liquidity_bucket"] = pd.qcut(rank, q=min(n_buckets, len(work)), labels=False) + 1
    rows: list[dict[str, float | int]] = []
    for bucket, bucket_df in work.groupby("liquidity_bucket", sort=True):
        rows.append(
            {
                "liquidity_bucket": int(bucket),
                "count": int(len(bucket_df)),
                "amount_min": float(bucket_df["session_amount"].min()),
                "amount_median": float(bucket_df["session_amount"].median()),
                "amount_max": float(bucket_df["session_amount"].max()),
                "buy_open_to_vwap_bps_median": float(bucket_df["buy_open_to_vwap_bps"].median()),
                "buy_open_to_vwap_bps_p75": float(bucket_df["buy_open_to_vwap_bps"].quantile(0.75)),
                "buy_open_to_vwap_bps_p90": float(bucket_df["buy_open_to_vwap_bps"].quantile(0.90)),
                "abs_open_to_vwap_bps_median": float(bucket_df["abs_open_to_vwap_bps"].median()),
                "buy_open_to_close_bps_median": float(bucket_df["buy_open_to_close_bps"].median()),
                "abs_open_to_close_bps_median": float(bucket_df["abs_open_to_close_bps"].median()),
            }
        )
    return pd.DataFrame(rows)


def summarize_slippage_metrics(daily_metrics: pd.DataFrame) -> dict[str, object]:
    return {
        "rows": int(len(daily_metrics)),
        "symbols": int(daily_metrics["symbol"].nunique()) if not daily_metrics.empty else 0,
        "trade_dates": int(daily_metrics["trade_date"].nunique()) if not daily_metrics.empty else 0,
        "bar_count": _metric_snapshot(daily_metrics["bar_count"]),
        "session_amount": _metric_snapshot(daily_metrics["session_amount"]),
        "buy_open_to_vwap_bps": _metric_snapshot(daily_metrics["buy_open_to_vwap_bps"]),
        "abs_open_to_vwap_bps": _metric_snapshot(daily_metrics["abs_open_to_vwap_bps"]),
        "buy_open_to_close_bps": _metric_snapshot(daily_metrics["buy_open_to_close_bps"]),
        "abs_open_to_close_bps": _metric_snapshot(daily_metrics["abs_open_to_close_bps"]),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a daily slippage calibration report from HK intraday parquet data."
    )
    parser.add_argument("--input", required=True, help="Input intraday parquet path.")
    parser.add_argument(
        "--output-prefix",
        required=True,
        help="Output prefix for *_daily.parquet, *_summary.json, *_liquidity.csv.",
    )
    parser.add_argument("--liquidity-buckets", type=int, default=5, help="Number of liquidity buckets.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    input_path = resolve_repo_path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input intraday file not found: {input_path}")

    frame = pd.read_parquet(input_path)
    daily_metrics = compute_daily_slippage_metrics(frame)
    summary = summarize_slippage_metrics(daily_metrics)
    liquidity = build_liquidity_bucket_summary(
        daily_metrics,
        n_buckets=max(1, int(args.liquidity_buckets)),
    )

    prefix = resolve_repo_path(args.output_prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    daily_path = prefix.with_name(prefix.name + "_daily.parquet")
    summary_path = prefix.with_name(prefix.name + "_summary.json")
    liquidity_path = prefix.with_name(prefix.name + "_liquidity.csv")

    daily_metrics.to_parquet(daily_path, index=False)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    liquidity.to_csv(liquidity_path, index=False)

    print(f"saved daily metrics: {daily_path}")
    print(f"saved summary: {summary_path}")
    print(f"saved liquidity buckets: {liquidity_path}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
