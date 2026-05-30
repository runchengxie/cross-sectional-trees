#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from cstree.data_tools.symbols import ensure_symbol_columns
from cstree.repo_paths import find_repo_root, resolve_repo_path as resolve_repo_relative_path

REPO_ROOT = find_repo_root(__file__)
DEFAULT_DAILY_ASSET_DIR = "artifacts/assets/rqdata/hk/daily/hk_all_daily_clean_latest"
DEFAULT_VALUATION_ASSET_DIR = "artifacts/assets/rqdata/hk/valuation/hk_all_valuation_latest"
DEFAULT_WEIGHT_COL = "hk_total_market_val"
DEFAULT_ENTRY_PRICE_COL = "open"
DEFAULT_EXIT_PRICE_COL = "close"
DEFAULT_WEIGHTING = "cap"


def resolve_repo_path(path_text: str | Path) -> Path:
    return resolve_repo_relative_path(path_text, repo_root=REPO_ROOT)


def _normalize_dates(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.strip()
    parsed = pd.to_datetime(text, format="%Y%m%d", errors="coerce")
    fallback_mask = parsed.isna()
    if fallback_mask.any():
        parsed.loc[fallback_mask] = pd.to_datetime(
            text.loc[fallback_mask],
            errors="coerce",
        )
    return parsed.dt.normalize()


def _normalize_symbols(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.upper()


def load_periods(paths: list[Path]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in paths:
        if not path.exists():
            raise SystemExit(f"Periods file not found: {path}")
        frame = pd.read_csv(path)
        required = {"rebalance_date", "entry_date", "exit_date"}
        missing = sorted(required - set(frame.columns))
        if missing:
            raise SystemExit(
                f"Periods file is missing required columns {missing}: {path}"
            )
        work = frame.loc[:, ["rebalance_date", "entry_date", "exit_date"]].copy()
        for col in ("rebalance_date", "entry_date", "exit_date"):
            work[col] = _normalize_dates(work[col])
        work = work.dropna(subset=["rebalance_date", "entry_date", "exit_date"])
        if work.empty:
            continue
        work["source_file"] = str(path)
        frames.append(work)
    if not frames:
        raise SystemExit("No valid periods resolved from --periods-file.")
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(
        subset=["rebalance_date", "entry_date", "exit_date"], keep="last"
    )
    combined = combined.sort_values(["rebalance_date", "entry_date", "exit_date"]).reset_index(
        drop=True
    )
    return combined


def load_universe_by_date(path: Path, *, allowed_dates: set[pd.Timestamp]) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"Universe by-date file not found: {path}")
    frame = pd.read_csv(path)
    if "trade_date" not in frame.columns:
        raise SystemExit(f"Universe by-date file is missing trade_date: {path}")
    frame = ensure_symbol_columns(frame, context=f"Universe by-date file {path.name}").copy()
    frame["trade_date"] = _normalize_dates(frame["trade_date"])
    frame["symbol"] = _normalize_symbols(frame["symbol"])
    frame = frame.dropna(subset=["trade_date", "symbol"])
    if "selected" in frame.columns:
        frame = frame[frame["selected"].fillna(0).astype(int) > 0].copy()
    frame = frame[frame["trade_date"].isin(allowed_dates)].copy()
    if frame.empty:
        raise SystemExit(
            "Universe by-date file has no rows matching the benchmark rebalance dates."
        )
    frame = frame.drop_duplicates(subset=["trade_date", "symbol"]).reset_index(drop=True)
    return frame.loc[:, ["trade_date", "symbol"]]


def _read_parquet_columns(path: Path, columns: list[str]) -> pd.DataFrame:
    try:
        return pd.read_parquet(path, columns=columns)
    except Exception:
        return pd.read_parquet(path)


def load_symbol_daily_frame(
    *,
    symbol: str,
    asset_dir: Path,
    entry_price_col: str,
    exit_price_col: str,
) -> pd.DataFrame:
    path = asset_dir / "data" / f"{symbol}.parquet"
    if not path.exists():
        return pd.DataFrame(columns=["trade_date", entry_price_col, exit_price_col])
    needed = ["trade_date"]
    for col in (entry_price_col, exit_price_col):
        if col not in needed:
            needed.append(col)
    frame = _read_parquet_columns(path, needed)
    if frame.empty or "trade_date" not in frame.columns:
        return pd.DataFrame(columns=["trade_date", entry_price_col, exit_price_col])
    work = frame.copy()
    work["trade_date"] = _normalize_dates(work["trade_date"])
    for col in (entry_price_col, exit_price_col):
        if col not in work.columns:
            work[col] = np.nan
        work[col] = pd.to_numeric(work[col], errors="coerce")
    work = work.dropna(subset=["trade_date"]).drop_duplicates(subset=["trade_date"], keep="last")
    return work.loc[:, ["trade_date", entry_price_col, exit_price_col]].sort_values("trade_date")


def load_symbol_valuation_frame(
    *,
    symbol: str,
    asset_dir: Path,
    weight_col: str,
) -> pd.DataFrame:
    path = asset_dir / "data" / f"{symbol}.parquet"
    if not path.exists():
        return pd.DataFrame(columns=["trade_date", weight_col])
    frame = _read_parquet_columns(path, ["trade_date", weight_col])
    if frame.empty or "trade_date" not in frame.columns:
        return pd.DataFrame(columns=["trade_date", weight_col])
    work = frame.copy()
    work["trade_date"] = _normalize_dates(work["trade_date"])
    if weight_col not in work.columns:
        work[weight_col] = np.nan
    work[weight_col] = pd.to_numeric(work[weight_col], errors="coerce")
    work = work.dropna(subset=["trade_date"]).drop_duplicates(subset=["trade_date"], keep="last")
    return work.loc[:, ["trade_date", weight_col]].sort_values("trade_date")


def _lookup_exact_value(frame: pd.DataFrame, date: pd.Timestamp, column: str) -> float:
    if frame.empty:
        return np.nan
    row = frame.loc[frame["trade_date"] == date, column]
    if row.empty:
        return np.nan
    try:
        value = float(row.iloc[-1])
    except (TypeError, ValueError):
        return np.nan
    return value if np.isfinite(value) else np.nan


def _lookup_asof_value(frame: pd.DataFrame, date: pd.Timestamp, column: str) -> float:
    if frame.empty:
        return np.nan
    row = frame.loc[frame["trade_date"] <= date, column].dropna()
    if row.empty:
        return np.nan
    try:
        value = float(row.iloc[-1])
    except (TypeError, ValueError):
        return np.nan
    return value if np.isfinite(value) else np.nan


def build_cap_weight_benchmark(
    *,
    periods: pd.DataFrame,
    universe_by_date: pd.DataFrame,
    daily_asset_dir: Path,
    valuation_asset_dir: Path,
    weight_col: str,
    entry_price_col: str,
    exit_price_col: str,
    weighting: str = DEFAULT_WEIGHTING,
) -> pd.DataFrame:
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

    rows: list[dict[str, object]] = []
    for period in periods.itertuples(index=False):
        members = universe_map.get(period.rebalance_date, [])
        n_universe = len(members)
        usable_rows: list[tuple[float, float]] = []
        n_with_weight = 0
        n_with_price = 0

        for symbol in members:
            weight = _lookup_asof_value(
                valuation_cache[symbol],
                period.rebalance_date,
                weight_col,
            )
            if np.isfinite(weight) and weight > 0:
                n_with_weight += 1

            daily_frame = daily_cache[symbol]
            entry_price = _lookup_exact_value(daily_frame, period.entry_date, entry_price_col)
            exit_price = _lookup_exact_value(daily_frame, period.exit_date, exit_price_col)
            if np.isfinite(entry_price) and entry_price > 0 and np.isfinite(exit_price) and exit_price > 0:
                n_with_price += 1

            if weighting_mode == "cap" and not (np.isfinite(weight) and weight > 0):
                continue
            if not (np.isfinite(entry_price) and entry_price > 0 and np.isfinite(exit_price) and exit_price > 0):
                continue
            effective_weight = weight if weighting_mode == "cap" else 1.0
            usable_rows.append((effective_weight, exit_price / entry_price - 1.0))

        if usable_rows:
            weights = np.array([item[0] for item in usable_rows], dtype=float)
            returns = np.array([item[1] for item in usable_rows], dtype=float)
            normalized_weights = weights / weights.sum()
            benchmark_return = float(np.dot(normalized_weights, returns))
            weight_sum = float(weights.sum())
        else:
            benchmark_return = np.nan
            weight_sum = np.nan

        used_count = len(usable_rows)
        coverage_pct = float(used_count / n_universe * 100.0) if n_universe > 0 else np.nan
        weight_coverage_pct = (
            float(n_with_weight / n_universe * 100.0) if n_universe > 0 else np.nan
        )
        price_coverage_pct = (
            float(n_with_price / n_universe * 100.0) if n_universe > 0 else np.nan
        )
        rows.append(
            {
                "trade_date": period.exit_date.strftime("%Y%m%d"),
                "rebalance_date": period.rebalance_date.strftime("%Y%m%d"),
                "entry_date": period.entry_date.strftime("%Y%m%d"),
                "exit_date": period.exit_date.strftime("%Y%m%d"),
                "benchmark_return": benchmark_return,
                "n_universe": int(n_universe),
                "n_with_weight": int(n_with_weight),
                "n_with_price": int(n_with_price),
                "n_used": int(used_count),
                "coverage_pct": coverage_pct,
                "weight_coverage_pct": weight_coverage_pct,
                "price_coverage_pct": price_coverage_pct,
                "raw_weight_sum": weight_sum,
            }
        )
    return pd.DataFrame(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build an HK connect-style cap-weight benchmark return series from "
            "local by-date universe, daily asset, valuation asset, and backtest periods."
        )
    )
    parser.add_argument(
        "--periods-file",
        action="append",
        required=True,
        help="CSV file containing rebalance_date, entry_date, exit_date. Repeatable.",
    )
    parser.add_argument(
        "--by-date-file",
        required=True,
        help="Universe by-date CSV used to define benchmark constituents on each rebalance date.",
    )
    parser.add_argument(
        "--daily-asset-dir",
        default=DEFAULT_DAILY_ASSET_DIR,
        help=f"Local HK daily asset directory. Default: {DEFAULT_DAILY_ASSET_DIR}",
    )
    parser.add_argument(
        "--valuation-asset-dir",
        default=DEFAULT_VALUATION_ASSET_DIR,
        help=f"Local HK valuation asset directory. Default: {DEFAULT_VALUATION_ASSET_DIR}",
    )
    parser.add_argument(
        "--weight-col",
        default=DEFAULT_WEIGHT_COL,
        help=f"Valuation column used as benchmark weight. Default: {DEFAULT_WEIGHT_COL}",
    )
    parser.add_argument(
        "--weighting",
        default=DEFAULT_WEIGHTING,
        choices=["cap", "equal"],
        help="Benchmark weighting mode. 'cap' uses --weight-col; 'equal' gives each usable member the same weight.",
    )
    parser.add_argument(
        "--entry-price-col",
        default=DEFAULT_ENTRY_PRICE_COL,
        help=f"Entry price column from daily assets. Default: {DEFAULT_ENTRY_PRICE_COL}",
    )
    parser.add_argument(
        "--exit-price-col",
        default=DEFAULT_EXIT_PRICE_COL,
        help=f"Exit price column from daily assets. Default: {DEFAULT_EXIT_PRICE_COL}",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output CSV path for the benchmark return series.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    periods_paths = [resolve_repo_path(path_text) for path_text in args.periods_file]
    by_date_path = resolve_repo_path(args.by_date_file)
    daily_asset_dir = resolve_repo_path(args.daily_asset_dir)
    valuation_asset_dir = resolve_repo_path(args.valuation_asset_dir)
    out_path = resolve_repo_path(args.out)

    periods = load_periods(periods_paths)
    rebalance_dates = set(periods["rebalance_date"].tolist())
    universe_by_date = load_universe_by_date(by_date_path, allowed_dates=rebalance_dates)
    benchmark = build_cap_weight_benchmark(
        periods=periods,
        universe_by_date=universe_by_date,
        daily_asset_dir=daily_asset_dir,
        valuation_asset_dir=valuation_asset_dir,
        weight_col=str(args.weight_col).strip(),
        entry_price_col=str(args.entry_price_col).strip(),
        exit_price_col=str(args.exit_price_col).strip(),
        weighting=str(args.weighting).strip(),
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    benchmark.to_csv(out_path, index=False)

    valid = benchmark["benchmark_return"].notna()
    min_coverage = float(benchmark["coverage_pct"].min()) if not benchmark.empty else np.nan
    avg_coverage = float(benchmark["coverage_pct"].mean()) if not benchmark.empty else np.nan
    print(f"Wrote {len(benchmark)} periods to {out_path}")
    print(f"Valid benchmark periods: {int(valid.sum())}/{len(benchmark)}")
    print(
        "Coverage pct (used/universe): "
        f"min={min_coverage:.2f}, avg={avg_coverage:.2f}"
        if np.isfinite(min_coverage) and np.isfinite(avg_coverage)
        else "Coverage pct (used/universe): n/a"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
