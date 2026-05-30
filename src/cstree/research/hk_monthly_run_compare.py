#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from cstree.metrics import summarize_active_returns, summarize_ic
from market_data_platform.repo_paths import find_repo_root, resolve_repo_path as resolve_repo_relative_path

REPO_ROOT = find_repo_root(__file__)
DEFAULT_REPORT_DIR = REPO_ROOT / "artifacts" / "reports"
DEFAULT_WINDOWS = ("6m", "12m", "24m", "full")
STYLE_ACTIVE_SUFFIX = "_active_net_vs_equal"
_LABEL_PATTERN = re.compile(r"[^a-z0-9]+")


def resolve_repo_path(path_text: str | Path) -> Path:
    return resolve_repo_relative_path(path_text, repo_root=REPO_ROOT)


def _slugify(text: str) -> str:
    slug = _LABEL_PATTERN.sub("_", str(text).strip().lower()).strip("_")
    return slug or "run"


def _get_nested(payload: Mapping[str, Any] | None, *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise SystemExit(f"Expected JSON object in {path}")
    return payload


def _normalize_date_series(series: pd.Series) -> pd.Series:
    if series.empty:
        return pd.to_datetime(series, errors="coerce")
    raw = series.copy()
    if pd.api.types.is_numeric_dtype(raw):
        numeric = pd.to_numeric(raw, errors="coerce")
        if numeric.notna().any():
            as_int = numeric.dropna().astype(np.int64).astype(str)
            if as_int.str.fullmatch(r"\d{8}").all():
                return pd.to_datetime(numeric.astype("Int64").astype(str), format="%Y%m%d", errors="coerce")
    text = raw.astype(str).str.strip()
    if text.replace({"": pd.NA}).dropna().str.fullmatch(r"\d{8}").all():
        return pd.to_datetime(text, format="%Y%m%d", errors="coerce")
    return pd.to_datetime(raw, errors="coerce")


def _require_file(path: Path, *, label: str) -> Path:
    if not path.exists():
        raise SystemExit(f"Missing {label}: {path}")
    return path


def _resolve_run_arg(text: str) -> tuple[str, Path]:
    label, sep, raw_path = str(text).partition("=")
    if not sep:
        raise SystemExit("Each --run must use the form <label>=<run_dir>.")
    clean_label = label.strip()
    if not clean_label:
        raise SystemExit("Run label cannot be empty.")
    run_dir = resolve_repo_path(raw_path.strip())
    if not run_dir.exists():
        raise SystemExit(f"Run directory not found: {run_dir}")
    return clean_label, run_dir


def _parse_windows(values: Sequence[str] | None) -> list[str]:
    tokens: list[str] = []
    for value in values or DEFAULT_WINDOWS:
        for part in str(value).split(","):
            text = part.strip().lower()
            if text:
                tokens.append(text)
    ordered: list[str] = []
    for token in tokens:
        if token == "full":
            normalized = "full"
        else:
            match = re.fullmatch(r"(\d+)m", token)
            if not match:
                raise SystemExit("Windows must be 'full' or '<months>m', for example: 6m,12m,24m.")
            normalized = f"{int(match.group(1))}m"
        if normalized not in ordered:
            ordered.append(normalized)
    return ordered


def _load_series(path: Path, *, value_col: str) -> pd.Series:
    frame = pd.read_csv(path)
    date_col = "trade_date" if "trade_date" in frame.columns else None
    if date_col is None:
        fallback_cols = [column for column in frame.columns if column != value_col]
        if fallback_cols:
            date_col = fallback_cols[0]
    if date_col is None or value_col not in frame.columns:
        raise SystemExit(f"{path} is missing required date/value columns for {value_col}")
    work = frame.loc[:, [date_col, value_col]].copy()
    work[date_col] = _normalize_date_series(work[date_col])
    work[value_col] = pd.to_numeric(work[value_col], errors="coerce")
    work = work.dropna(subset=[date_col, value_col]).sort_values(date_col)
    series = work.set_index(date_col)[value_col].astype(float)
    series.index = pd.DatetimeIndex(series.index).normalize()
    series = series[~series.index.duplicated(keep="last")]
    series.name = value_col
    return series


def _load_frame(path: Path, *, date_col: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if date_col not in frame.columns:
        raise SystemExit(f"{path} is missing required column {date_col}")
    work = frame.copy()
    work[date_col] = _normalize_date_series(work[date_col])
    work = work[work[date_col].notna()].sort_values(date_col).reset_index(drop=True)
    return work


def _window_target_periods(window_label: str) -> int | None:
    if window_label == "full":
        return None
    return int(window_label[:-1])


def _slice_series_window(series: pd.Series, *, window_label: str) -> pd.Series:
    if series.empty:
        return series
    target_periods = _window_target_periods(window_label)
    if target_periods is None:
        return series.copy()
    return series.tail(target_periods).copy()


def _series_sharpe(returns: pd.Series, *, periods_per_year: float) -> float:
    if returns is None or returns.empty:
        return np.nan
    std = float(returns.std(ddof=1)) if returns.shape[0] > 1 else np.nan
    if not np.isfinite(std) or std <= 0 or not np.isfinite(periods_per_year) or periods_per_year <= 0:
        return np.nan
    return float(returns.mean() / std * np.sqrt(periods_per_year))


def _artifact_path(run_dir: Path, summary: dict[str, Any], *summary_keys: str, default_name: str) -> Path:
    path_value = _get_nested(summary, *summary_keys)
    if path_value:
        return resolve_repo_path(str(path_value))
    return run_dir / default_name


def _mean_or_nan(series: pd.Series) -> float:
    if series is None or series.empty:
        return np.nan
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return np.nan
    return float(numeric.mean())


def _mode_text(series: pd.Series) -> tuple[str | None, float]:
    values = [str(value).strip() for value in series.dropna() if str(value).strip()]
    if not values:
        return None, np.nan
    counts = Counter(values)
    name, count = counts.most_common(1)[0]
    return name, float(count / len(values))


def _overlap_ratio_by_date(positions: pd.DataFrame) -> float:
    if positions.empty or "entry_date" not in positions.columns or "symbol" not in positions.columns:
        return np.nan
    grouped = {
        pd.Timestamp(entry_date): set(group["symbol"].astype(str))
        for entry_date, group in positions.groupby("entry_date", sort=True)
    }
    prev: set[str] | None = None
    ratios: list[float] = []
    for _, symbols in sorted(grouped.items(), key=lambda item: item[0]):
        if prev is not None and symbols:
            ratios.append(len(prev & symbols) / float(len(symbols)))
        prev = symbols
    if not ratios:
        return np.nan
    return float(np.mean(ratios))


def _select_window_frame(frame: pd.DataFrame, *, date_col: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    return frame[(frame[date_col] >= start) & (frame[date_col] <= end)].copy()


def _build_window_metrics_row(
    *,
    label: str,
    run_name: str,
    run_dir: Path,
    periods_per_year: float,
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    turnover: pd.Series,
    ic_series: pd.Series,
    window_label: str,
) -> dict[str, Any]:
    strategy_window = _slice_series_window(strategy_returns, window_label=window_label)
    if strategy_window.empty:
        raise SystemExit(f"Run {label} has no OOS strategy returns for window={window_label}.")
    start = pd.Timestamp(strategy_window.index.min()).normalize()
    end = pd.Timestamp(strategy_window.index.max()).normalize()
    benchmark_window = benchmark_returns[(benchmark_returns.index >= start) & (benchmark_returns.index <= end)]
    turnover_window = turnover[(turnover.index >= start) & (turnover.index <= end)]
    ic_window = ic_series[(ic_series.index >= start) & (ic_series.index <= end)]
    active_stats, _ = summarize_active_returns(strategy_window, benchmark_window, periods_per_year)
    ic_stats = summarize_ic(ic_window)
    return {
        "label": label,
        "run_name": run_name,
        "run_dir": str(run_dir),
        "window": window_label,
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": end.strftime("%Y-%m-%d"),
        "requested_periods": _window_target_periods(window_label) or int(strategy_window.shape[0]),
        "actual_periods": int(strategy_window.shape[0]),
        "sharpe": _series_sharpe(strategy_window, periods_per_year=periods_per_year),
        "active_ir": active_stats.get("information_ratio"),
        "active_total_return": active_stats.get("active_total_return"),
        "avg_turnover": _mean_or_nan(turnover_window),
        "ic_mean": ic_stats.get("mean"),
        "ic_ir": ic_stats.get("ir"),
        "ic_obs": ic_stats.get("n"),
    }


def _build_attribution_row(
    *,
    label: str,
    run_name: str,
    run_dir: Path,
    exposures: pd.DataFrame,
    positions: pd.DataFrame,
    window_label: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    exposure_window = _select_window_frame(exposures, date_col="entry_date", start=start, end=end)
    positions_window = _select_window_frame(positions, date_col="entry_date", start=start, end=end)
    row: dict[str, Any] = {
        "label": label,
        "run_name": run_name,
        "run_dir": str(run_dir),
        "window": window_label,
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": end.strftime("%Y-%m-%d"),
        "exposure_periods": int(exposure_window["entry_date"].nunique()) if not exposure_window.empty else 0,
        "avg_names_per_rebalance": np.nan,
        "median_names_per_rebalance": np.nan,
        "avg_holdover_ratio": np.nan,
        "industry_top1_name_mode": None,
        "industry_top1_name_mode_share": np.nan,
        "industry_top1_abs_active_mean": np.nan,
        "industry_top1_portfolio_net_weight_mean": np.nan,
    }
    if not positions_window.empty:
        counts = positions_window.groupby("entry_date", sort=True)["symbol"].nunique()
        row["avg_names_per_rebalance"] = float(counts.mean()) if not counts.empty else np.nan
        row["median_names_per_rebalance"] = float(counts.median()) if not counts.empty else np.nan
        row["avg_holdover_ratio"] = _overlap_ratio_by_date(positions_window)
    if not exposure_window.empty:
        if "industry_top_1_name" in exposure_window.columns:
            mode_name, mode_share = _mode_text(exposure_window["industry_top_1_name"])
            row["industry_top1_name_mode"] = mode_name
            row["industry_top1_name_mode_share"] = mode_share
        if "industry_top_1_active" in exposure_window.columns:
            row["industry_top1_abs_active_mean"] = _mean_or_nan(
                pd.to_numeric(exposure_window["industry_top_1_active"], errors="coerce").abs()
            )
        if "industry_top_1_portfolio_net_weight" in exposure_window.columns:
            row["industry_top1_portfolio_net_weight_mean"] = _mean_or_nan(
                pd.to_numeric(exposure_window["industry_top_1_portfolio_net_weight"], errors="coerce")
            )
        for column in exposure_window.columns:
            if not column.endswith(STYLE_ACTIVE_SUFFIX):
                continue
            style_name = column[: -len(STYLE_ACTIVE_SUFFIX)]
            values = pd.to_numeric(exposure_window[column], errors="coerce")
            if values.notna().sum() == 0:
                continue
            row[f"{style_name}_active_mean"] = float(values.mean())
            row[f"{style_name}_active_abs_mean"] = float(values.abs().mean())
    return row


def _build_summary_payload(
    *,
    run_specs: Sequence[tuple[str, Path]],
    windows: Sequence[str],
    window_metrics: pd.DataFrame,
    attribution_summary: pd.DataFrame,
    out_dir: Path,
) -> dict[str, Any]:
    winners: dict[str, dict[str, str | None]] = {}
    for window in windows:
        subset = window_metrics[window_metrics["window"] == window].copy()
        if subset.empty:
            continue
        winners[window] = {}
        for metric in ("sharpe", "active_ir", "active_total_return", "ic_mean"):
            work = subset.dropna(subset=[metric]).sort_values(metric, ascending=False)
            winners[window][metric] = str(work.iloc[0]["label"]) if not work.empty else None
    return {
        "runs": [{"label": label, "run_dir": str(run_dir)} for label, run_dir in run_specs],
        "windows": list(windows),
        "window_metrics_file": str(out_dir / "window_metrics.csv"),
        "attribution_summary_file": str(out_dir / "attribution_summary.csv"),
        "winners": winners,
        "window_metrics_rows": int(window_metrics.shape[0]),
        "attribution_rows": int(attribution_summary.shape[0]),
    }


def compare_runs(
    *,
    run_specs: Sequence[tuple[str, Path]],
    windows: Sequence[str],
    out_dir: Path,
) -> dict[str, Any]:
    window_rows: list[dict[str, Any]] = []
    attribution_rows: list[dict[str, Any]] = []

    for label, run_dir in run_specs:
        summary = _load_json(_require_file(run_dir / "summary.json", label="summary.json"))
        if not _get_nested(summary, "final_oos", "enabled"):
            raise SystemExit(f"Run {label} does not have final_oos.enabled=true: {run_dir}")
        run_name = str(_get_nested(summary, "run", "name") or run_dir.name)
        periods_per_year = float(
            _get_nested(summary, "final_oos", "backtest", "stats", "periods_per_year")
            or _get_nested(summary, "backtest", "stats", "periods_per_year")
            or np.nan
        )
        strategy_returns = _load_series(
            _require_file(run_dir / "backtest_net_oos.csv", label="backtest_net_oos.csv"),
            value_col="net_return",
        )
        benchmark_returns = _load_series(
            _require_file(run_dir / "backtest_benchmark_oos.csv", label="backtest_benchmark_oos.csv"),
            value_col="benchmark_return",
        )
        turnover = _load_series(
            _require_file(run_dir / "backtest_turnover_oos.csv", label="backtest_turnover_oos.csv"),
            value_col="turnover",
        )
        ic_series = _load_series(
            _require_file(run_dir / "ic_oos.csv", label="ic_oos.csv"),
            value_col="ic",
        )
        exposure_path = _artifact_path(
            run_dir,
            summary,
            "final_oos",
            "backtest",
            "exposure",
            "active_summary_file",
            default_name="backtest_active_exposure_summary_oos.csv",
        )
        positions_path = _artifact_path(
            run_dir,
            summary,
            "final_oos",
            "positions",
            "by_rebalance_file",
            default_name="positions_by_rebalance_oos.csv",
        )
        exposures = _load_frame(_require_file(exposure_path, label="backtest active exposure summary"), date_col="entry_date")
        positions = _load_frame(_require_file(positions_path, label="positions_by_rebalance_oos"), date_col="entry_date")

        for window_label in windows:
            window_row = _build_window_metrics_row(
                label=label,
                run_name=run_name,
                run_dir=run_dir,
                periods_per_year=periods_per_year,
                strategy_returns=strategy_returns,
                benchmark_returns=benchmark_returns,
                turnover=turnover,
                ic_series=ic_series,
                window_label=window_label,
            )
            window_rows.append(window_row)
            attribution_rows.append(
                _build_attribution_row(
                    label=label,
                    run_name=run_name,
                    run_dir=run_dir,
                    exposures=exposures,
                    positions=positions,
                    window_label=window_label,
                    start=pd.Timestamp(window_row["start_date"]),
                    end=pd.Timestamp(window_row["end_date"]),
                )
            )

    window_metrics = pd.DataFrame(window_rows)
    attribution_summary = pd.DataFrame(attribution_rows)
    out_dir.mkdir(parents=True, exist_ok=True)
    window_metrics.to_csv(out_dir / "window_metrics.csv", index=False)
    attribution_summary.to_csv(out_dir / "attribution_summary.csv", index=False)
    payload = _build_summary_payload(
        run_specs=run_specs,
        windows=windows,
        window_metrics=window_metrics,
        attribution_summary=attribution_summary,
        out_dir=out_dir,
    )
    (out_dir / "summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare HK monthly run outputs across fixed trailing windows using final OOS "
            "backtest / IC / exposure artifacts."
        )
    )
    parser.add_argument(
        "--run",
        action="append",
        required=True,
        help="Run spec in the form <label>=<run_dir>. Provide at least two.",
    )
    parser.add_argument(
        "--windows",
        action="append",
        help="Comma-separated trailing windows. Default: 6m,12m,24m,full",
    )
    parser.add_argument(
        "--out-dir",
        help="Optional output directory. Default: artifacts/reports/hk_monthly_run_compare_<labels>/",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    run_specs = [_resolve_run_arg(item) for item in args.run or []]
    if len(run_specs) < 2:
        raise SystemExit("Provide at least two --run entries.")
    windows = _parse_windows(args.windows)
    if args.out_dir:
        out_dir = resolve_repo_path(args.out_dir)
    else:
        label_slug = "__vs__".join(_slugify(label) for label, _ in run_specs)
        out_dir = DEFAULT_REPORT_DIR / f"hk_monthly_run_compare_{label_slug}"
    payload = compare_runs(run_specs=run_specs, windows=windows, out_dir=out_dir)
    print(f"Wrote comparison reports to {out_dir}")
    print(json.dumps(payload["winners"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
