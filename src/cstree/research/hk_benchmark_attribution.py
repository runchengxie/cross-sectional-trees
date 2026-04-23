#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from cstree.research.hk_connect_cap_weight_benchmark import (
    DEFAULT_DAILY_ASSET_DIR,
    DEFAULT_ENTRY_PRICE_COL,
    DEFAULT_EXIT_PRICE_COL,
    DEFAULT_VALUATION_ASSET_DIR,
    DEFAULT_WEIGHT_COL,
    DEFAULT_WEIGHTING,
    _lookup_asof_value,
    _lookup_exact_value,
    _normalize_dates,
    _normalize_symbols,
    load_periods,
    load_symbol_daily_frame,
    load_symbol_valuation_frame,
    load_universe_by_date,
    resolve_repo_path,
)


DEFAULT_INDUSTRY_FILE = (
    "artifacts/assets/rqdata/hk/industry_changes/hk_all_industry_changes_latest/industry_labels_m.parquet"
)
DEFAULT_INDUSTRY_COLUMN = "first_industry_name"
UNKNOWN_INDUSTRY = "Unknown"


def load_industry_frame(path: Path, *, industry_col: str) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"Industry labels file not found: {path}")
    frame = pd.read_parquet(path)
    required = {"trade_date", "symbol", industry_col}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise SystemExit(f"Industry labels file is missing required columns {missing}: {path}")
    work = frame.loc[:, ["trade_date", "symbol", industry_col]].copy()
    work["trade_date"] = _normalize_dates(work["trade_date"])
    work["symbol"] = _normalize_symbols(work["symbol"])
    work[industry_col] = work[industry_col].astype("string")
    work = work.dropna(subset=["trade_date", "symbol"]).drop_duplicates(
        subset=["trade_date", "symbol"], keep="last"
    )
    return work.sort_values(["symbol", "trade_date"]).reset_index(drop=True)


def build_industry_lookup(
    industry_frame: pd.DataFrame,
    *,
    industry_col: str,
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    if industry_frame.empty:
        return {}

    lookup: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for symbol, group in industry_frame.groupby("symbol", sort=False):
        dates = group["trade_date"].to_numpy(dtype="datetime64[ns]")
        values = group[industry_col].fillna(pd.NA).to_numpy(dtype=object)
        lookup[str(symbol)] = (dates, values)
    return lookup


def _lookup_industry_asof(
    industry_lookup: dict[str, tuple[np.ndarray, np.ndarray]],
    date: pd.Timestamp,
    symbol: str,
) -> str | None:
    series = industry_lookup.get(symbol)
    if series is None:
        return None
    dates, values = series
    if dates.size == 0:
        return None
    idx = np.searchsorted(dates, np.datetime64(date), side="right") - 1
    if idx < 0:
        return None
    value = values[idx]
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def build_benchmark_attribution(
    *,
    periods: pd.DataFrame,
    universe_by_date: pd.DataFrame,
    daily_asset_dir: Path,
    valuation_asset_dir: Path,
    weight_col: str,
    entry_price_col: str,
    exit_price_col: str,
    weighting: str = DEFAULT_WEIGHTING,
    industry_frame: pd.DataFrame | None = None,
    industry_col: str = DEFAULT_INDUSTRY_COLUMN,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    weighting_mode = str(weighting).strip().lower()
    if weighting_mode not in {"cap", "equal"}:
        raise SystemExit(f"Unsupported --weighting={weighting!r}; expected 'cap' or 'equal'.")

    universe_map = {
        trade_date: sorted(group["symbol"].tolist())
        for trade_date, group in universe_by_date.groupby("trade_date", sort=True)
    }
    symbols = sorted(universe_by_date["symbol"].unique().tolist())
    daily_cache = {
        symbol: load_symbol_daily_frame(
            symbol=symbol,
            asset_dir=daily_asset_dir,
            entry_price_col=entry_price_col,
            exit_price_col=exit_price_col,
        )
        for symbol in symbols
    }
    valuation_cache = {
        symbol: load_symbol_valuation_frame(
            symbol=symbol,
            asset_dir=valuation_asset_dir,
            weight_col=weight_col,
        )
        for symbol in symbols
    }
    industry_lookup = build_industry_lookup(
        industry_frame if industry_frame is not None else pd.DataFrame(),
        industry_col=industry_col,
    )

    contribution_rows: list[dict[str, object]] = []
    period_rows: list[dict[str, object]] = []

    for period in periods.itertuples(index=False):
        members = universe_map.get(period.rebalance_date, [])
        component_rows: list[dict[str, object]] = []

        for symbol in members:
            daily_frame = daily_cache[symbol]
            entry_price = _lookup_exact_value(daily_frame, period.entry_date, entry_price_col)
            exit_price = _lookup_exact_value(daily_frame, period.exit_date, exit_price_col)
            if not (
                np.isfinite(entry_price)
                and entry_price > 0
                and np.isfinite(exit_price)
                and exit_price > 0
            ):
                continue

            weight_raw = _lookup_asof_value(valuation_cache[symbol], period.rebalance_date, weight_col)
            if weighting_mode == "cap":
                if not (np.isfinite(weight_raw) and weight_raw > 0):
                    continue
                base_weight = float(weight_raw)
            else:
                base_weight = 1.0

            component_rows.append(
                {
                    "rebalance_date": period.rebalance_date,
                    "entry_date": period.entry_date,
                    "exit_date": period.exit_date,
                    "symbol": symbol,
                    "industry": _lookup_industry_asof(industry_lookup, period.rebalance_date, symbol)
                    or UNKNOWN_INDUSTRY,
                    "weight_raw": base_weight,
                    "entry_price": float(entry_price),
                    "exit_price": float(exit_price),
                    "period_return": float(exit_price / entry_price - 1.0),
                }
            )

        if not component_rows:
            period_rows.append(
                {
                    "rebalance_date": period.rebalance_date.strftime("%Y%m%d"),
                    "entry_date": period.entry_date.strftime("%Y%m%d"),
                    "exit_date": period.exit_date.strftime("%Y%m%d"),
                    "n_universe": int(len(members)),
                    "n_used": 0,
                    "benchmark_return": np.nan,
                    "top1_weight": np.nan,
                    "top5_weight": np.nan,
                    "effective_n": np.nan,
                    "hhi": np.nan,
                }
            )
            continue

        raw_weights = np.array([row["weight_raw"] for row in component_rows], dtype=float)
        norm_weights = raw_weights / raw_weights.sum()
        period_returns = np.array([row["period_return"] for row in component_rows], dtype=float)
        benchmark_return = float(np.dot(norm_weights, period_returns))
        sorted_weights = np.sort(norm_weights)[::-1]
        hhi = float(np.square(norm_weights).sum())
        effective_n = float(1.0 / hhi) if hhi > 0 else np.nan

        period_rows.append(
            {
                "rebalance_date": period.rebalance_date.strftime("%Y%m%d"),
                "entry_date": period.entry_date.strftime("%Y%m%d"),
                "exit_date": period.exit_date.strftime("%Y%m%d"),
                "n_universe": int(len(members)),
                "n_used": int(len(component_rows)),
                "benchmark_return": benchmark_return,
                "top1_weight": float(sorted_weights[:1].sum()),
                "top5_weight": float(sorted_weights[:5].sum()),
                "effective_n": effective_n,
                "hhi": hhi,
            }
        )

        for row, weight in zip(component_rows, norm_weights, strict=False):
            contribution_rows.append(
                {
                    "rebalance_date": period.rebalance_date.strftime("%Y%m%d"),
                    "entry_date": period.entry_date.strftime("%Y%m%d"),
                    "exit_date": period.exit_date.strftime("%Y%m%d"),
                    "symbol": row["symbol"],
                    "industry": row["industry"],
                    "weight": float(weight),
                    "period_return": row["period_return"],
                    "contribution": float(weight * row["period_return"]),
                    "entry_price": row["entry_price"],
                    "exit_price": row["exit_price"],
                }
            )

    return pd.DataFrame(contribution_rows), pd.DataFrame(period_rows)


def summarize_contributions(
    contributions: pd.DataFrame,
    *,
    group_col: str,
    label: str,
) -> pd.DataFrame:
    if contributions.empty:
        return pd.DataFrame(
            columns=[
                group_col,
                "periods_present",
                "avg_weight",
                "median_weight",
                "avg_period_return",
                "total_contribution",
                "contribution_share",
                "positive_contribution_periods",
                "negative_contribution_periods",
            ]
        )

    grouped = contributions.groupby(group_col, dropna=False)
    summary = grouped.agg(
        periods_present=("rebalance_date", "nunique"),
        avg_weight=("weight", "mean"),
        median_weight=("weight", "median"),
        avg_period_return=("period_return", "mean"),
        total_contribution=("contribution", "sum"),
        positive_contribution_periods=("contribution", lambda s: int((s > 0).sum())),
        negative_contribution_periods=("contribution", lambda s: int((s < 0).sum())),
    ).reset_index()
    total_contribution = float(summary["total_contribution"].sum())
    if np.isfinite(total_contribution) and total_contribution != 0:
        summary["contribution_share"] = summary["total_contribution"] / total_contribution
    else:
        summary["contribution_share"] = np.nan
    summary = summary.sort_values("total_contribution", ascending=False).reset_index(drop=True)
    summary.attrs["label"] = label
    return summary


def build_summary_payload(
    *,
    benchmark_name: str,
    weighting: str,
    period_summary: pd.DataFrame,
    symbol_summary: pd.DataFrame,
    industry_summary: pd.DataFrame,
) -> dict[str, object]:
    valid = period_summary["benchmark_return"].dropna()
    top_symbol_share = (
        float(symbol_summary["contribution_share"].iloc[0])
        if not symbol_summary.empty and pd.notna(symbol_summary["contribution_share"].iloc[0])
        else np.nan
    )
    top5_symbol_share = (
        float(symbol_summary["contribution_share"].head(5).sum())
        if not symbol_summary.empty and symbol_summary["contribution_share"].notna().any()
        else np.nan
    )
    top_industry_share = (
        float(industry_summary["contribution_share"].iloc[0])
        if not industry_summary.empty and pd.notna(industry_summary["contribution_share"].iloc[0])
        else np.nan
    )
    top3_industry_share = (
        float(industry_summary["contribution_share"].head(3).sum())
        if not industry_summary.empty and industry_summary["contribution_share"].notna().any()
        else np.nan
    )
    return {
        "benchmark_name": benchmark_name,
        "weighting": weighting,
        "periods": int(len(period_summary)),
        "valid_periods": int(valid.shape[0]),
        "benchmark_total_return": float((1.0 + valid).prod() - 1.0) if not valid.empty else np.nan,
        "avg_benchmark_return": float(valid.mean()) if not valid.empty else np.nan,
        "avg_top1_weight": float(period_summary["top1_weight"].dropna().mean())
        if period_summary["top1_weight"].notna().any()
        else np.nan,
        "avg_top5_weight": float(period_summary["top5_weight"].dropna().mean())
        if period_summary["top5_weight"].notna().any()
        else np.nan,
        "avg_effective_n": float(period_summary["effective_n"].dropna().mean())
        if period_summary["effective_n"].notna().any()
        else np.nan,
        "top_symbol_share": top_symbol_share,
        "top5_symbol_share": top5_symbol_share,
        "top_industry_share": top_industry_share,
        "top3_industry_share": top3_industry_share,
        "top_symbol": None if symbol_summary.empty else symbol_summary.iloc[0][symbol_summary.columns[0]],
        "top_industry": None if industry_summary.empty else industry_summary.iloc[0][industry_summary.columns[0]],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build constituent and industry attribution reports for an HK benchmark "
            "defined by by-date universe, periods, daily prices, and optional weights."
        )
    )
    parser.add_argument("--benchmark-name", required=True, help="Benchmark label written into summary.json.")
    parser.add_argument(
        "--periods-file",
        action="append",
        required=True,
        help="CSV file containing rebalance_date, entry_date, exit_date. Repeatable.",
    )
    parser.add_argument("--by-date-file", required=True, help="Universe by-date CSV.")
    parser.add_argument("--daily-asset-dir", default=DEFAULT_DAILY_ASSET_DIR)
    parser.add_argument("--valuation-asset-dir", default=DEFAULT_VALUATION_ASSET_DIR)
    parser.add_argument("--weight-col", default=DEFAULT_WEIGHT_COL)
    parser.add_argument("--weighting", default=DEFAULT_WEIGHTING, choices=["cap", "equal"])
    parser.add_argument("--entry-price-col", default=DEFAULT_ENTRY_PRICE_COL)
    parser.add_argument("--exit-price-col", default=DEFAULT_EXIT_PRICE_COL)
    parser.add_argument("--industry-file", default=DEFAULT_INDUSTRY_FILE)
    parser.add_argument("--industry-column", default=DEFAULT_INDUSTRY_COLUMN)
    parser.add_argument("--out-dir", required=True, help="Directory to write attribution artifacts.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    periods_paths = [resolve_repo_path(path_text) for path_text in args.periods_file]
    periods = load_periods(periods_paths)
    rebalance_dates = set(periods["rebalance_date"].tolist())
    universe_by_date = load_universe_by_date(
        resolve_repo_path(args.by_date_file),
        allowed_dates=rebalance_dates,
    )
    industry_frame = load_industry_frame(
        resolve_repo_path(args.industry_file),
        industry_col=str(args.industry_column).strip(),
    )

    contributions, period_summary = build_benchmark_attribution(
        periods=periods,
        universe_by_date=universe_by_date,
        daily_asset_dir=resolve_repo_path(args.daily_asset_dir),
        valuation_asset_dir=resolve_repo_path(args.valuation_asset_dir),
        weight_col=str(args.weight_col).strip(),
        entry_price_col=str(args.entry_price_col).strip(),
        exit_price_col=str(args.exit_price_col).strip(),
        weighting=str(args.weighting).strip(),
        industry_frame=industry_frame,
        industry_col=str(args.industry_column).strip(),
    )

    symbol_summary = summarize_contributions(contributions, group_col="symbol", label="symbol")
    industry_summary = summarize_contributions(contributions, group_col="industry", label="industry")
    payload = build_summary_payload(
        benchmark_name=str(args.benchmark_name).strip(),
        weighting=str(args.weighting).strip(),
        period_summary=period_summary,
        symbol_summary=symbol_summary,
        industry_summary=industry_summary,
    )

    out_dir = resolve_repo_path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    contributions.to_csv(out_dir / "component_contributions.csv", index=False)
    period_summary.to_csv(out_dir / "period_summary.csv", index=False)
    symbol_summary.to_csv(out_dir / "symbol_summary.csv", index=False)
    industry_summary.to_csv(out_dir / "industry_summary.csv", index=False)
    (out_dir / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote attribution reports to {out_dir}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
