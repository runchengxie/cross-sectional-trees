from __future__ import annotations

import argparse
import csv
import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from ..metrics import summarize_active_returns

FIELDNAMES = [
    "benchmark_name",
    "role",
    "source_type",
    "strategy_returns_file",
    "benchmark_returns_file",
    "attribution_file",
    "attribution_available",
    "aligned_periods",
    "strategy_total_return",
    "benchmark_total_return",
    "active_total_return",
    "active_mean",
    "tracking_error",
    "information_ratio",
    "beta",
    "alpha",
    "corr",
    "status",
    "error",
]


def _resolve_path(path_text: str | Path | None, *, base_dir: Path | None = None) -> Path | None:
    if path_text is None:
        return None
    candidate = Path(path_text).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    if base_dir is not None:
        return (base_dir / candidate).resolve()
    return (Path.cwd() / candidate).resolve()


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Benchmark ladder config not found: {path}")
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Failed to parse benchmark ladder config: {path} ({exc})") from exc
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise SystemExit(f"Benchmark ladder config must be a mapping: {path}")
    return payload


def _section(config: dict[str, Any]) -> dict[str, Any]:
    raw = config.get("benchmark_ladder", config)
    if not isinstance(raw, dict):
        raise SystemExit("benchmark_ladder must be a mapping.")
    return raw


def _return_column(frame: pd.DataFrame, preferred: str | None = None) -> str:
    candidates = [
        preferred,
        "strategy_return",
        "benchmark_return",
        "net_return",
        "return",
        "active_return",
    ]
    for candidate in candidates:
        if candidate and candidate in frame.columns:
            return candidate
    raise ValueError(
        "Returns file must include one return column: strategy_return, "
        "benchmark_return, net_return, return, or active_return."
    )


def _date_column(frame: pd.DataFrame) -> str:
    for candidate in ("trade_date", "date", "period_end"):
        if candidate in frame.columns:
            return candidate
    raise ValueError("Returns file must include a trade_date, date, or period_end column.")


def _read_returns(path: Path, *, preferred_return_col: str | None = None) -> pd.Series:
    if not path.exists():
        raise FileNotFoundError(f"Returns file not found: {path}")
    frame = pd.read_csv(path)
    date_col = _date_column(frame)
    return_col = _return_column(frame, preferred_return_col)
    series = pd.Series(
        pd.to_numeric(frame[return_col], errors="coerce").to_numpy(dtype=float),
        index=pd.to_datetime(frame[date_col]),
        name=return_col,
    ).dropna()
    if series.empty:
        raise ValueError(f"Returns file has no usable returns: {path}")
    return series.sort_index()


def _total_return(series: pd.Series) -> float:
    if series.empty:
        return np.nan
    return float((1.0 + series).prod() - 1.0)


def _benchmark_entries(cfg: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    entries: list[tuple[str, dict[str, Any]]] = []
    primary = cfg.get("primary_benchmark") or cfg.get("primary")
    if isinstance(primary, dict):
        entries.append(("primary", primary))
    comparisons = cfg.get("comparisons") or cfg.get("benchmarks") or []
    if not isinstance(comparisons, list):
        raise SystemExit("benchmark_ladder.comparisons must be a list.")
    for item in comparisons:
        if not isinstance(item, dict):
            raise SystemExit("benchmark_ladder.comparisons items must be mappings.")
        entries.append(("comparison", item))
    if not entries:
        raise SystemExit("Benchmark ladder requires primary_benchmark or comparisons.")
    return entries


def _empty_row(
    *,
    role: str,
    entry: dict[str, Any],
    strategy_path: Path,
    benchmark_path: Path | None,
    status: str,
    error: str,
) -> dict[str, Any]:
    attribution_path = _resolve_path(entry.get("attribution_file"), base_dir=benchmark_path.parent if benchmark_path else None)
    return {
        "benchmark_name": str(entry.get("name") or entry.get("benchmark_name") or ""),
        "role": role,
        "source_type": str(entry.get("source_type") or entry.get("type") or "returns_file"),
        "strategy_returns_file": str(strategy_path),
        "benchmark_returns_file": str(benchmark_path) if benchmark_path else None,
        "attribution_file": str(attribution_path) if attribution_path else None,
        "attribution_available": bool(attribution_path and attribution_path.exists()),
        "status": status,
        "error": error,
    }


def build_benchmark_ladder(config: dict[str, Any], *, config_dir: Path) -> list[dict[str, Any]]:
    cfg = _section(config)
    strategy_path = _resolve_path(cfg.get("strategy_returns_file"), base_dir=config_dir)
    if strategy_path is None:
        raise SystemExit("benchmark_ladder.strategy_returns_file is required.")
    periods_per_year = float(cfg.get("periods_per_year") or 12.0)
    strategy_return_col = cfg.get("strategy_return_col")
    strategy = _read_returns(strategy_path, preferred_return_col=strategy_return_col)

    rows: list[dict[str, Any]] = []
    for role, entry in _benchmark_entries(cfg):
        benchmark_path = _resolve_path(entry.get("returns_file") or entry.get("benchmark_returns_file"), base_dir=config_dir)
        if benchmark_path is None:
            rows.append(
                _empty_row(
                    role=role,
                    entry=entry,
                    strategy_path=strategy_path,
                    benchmark_path=None,
                    status="unavailable",
                    error="missing benchmark returns_file",
                )
            )
            continue
        try:
            benchmark = _read_returns(
                benchmark_path,
                preferred_return_col=entry.get("return_col") or entry.get("benchmark_return_col"),
            )
            active_stats, active = summarize_active_returns(strategy, benchmark, periods_per_year)
            if active.empty:
                row = _empty_row(
                    role=role,
                    entry=entry,
                    strategy_path=strategy_path,
                    benchmark_path=benchmark_path,
                    status="incompatible",
                    error="no overlapping return dates",
                )
                rows.append(row)
                continue
            aligned = pd.concat(
                [strategy.rename("strategy"), benchmark.rename("benchmark")],
                axis=1,
            ).dropna()
            attribution_path = _resolve_path(entry.get("attribution_file"), base_dir=config_dir)
            rows.append(
                {
                    **_empty_row(
                        role=role,
                        entry=entry,
                        strategy_path=strategy_path,
                        benchmark_path=benchmark_path,
                        status="ok",
                        error="",
                    ),
                    "attribution_file": str(attribution_path) if attribution_path else None,
                    "attribution_available": bool(attribution_path and attribution_path.exists()),
                    "aligned_periods": int(active_stats.get("n") or 0),
                    "strategy_total_return": _total_return(aligned["strategy"]),
                    "benchmark_total_return": _total_return(aligned["benchmark"]),
                    "active_total_return": active_stats.get("active_total_return"),
                    "active_mean": active_stats.get("mean"),
                    "tracking_error": active_stats.get("tracking_error"),
                    "information_ratio": active_stats.get("information_ratio"),
                    "beta": active_stats.get("beta"),
                    "alpha": active_stats.get("alpha"),
                    "corr": active_stats.get("corr"),
                }
            )
        except Exception as exc:
            rows.append(
                _empty_row(
                    role=role,
                    entry=entry,
                    strategy_path=strategy_path,
                    benchmark_path=benchmark_path,
                    status="unavailable",
                    error=str(exc),
                )
            )
    return rows


def write_reports(
    rows: list[dict[str, Any]],
    *,
    output_csv: Path | None,
    output_json: Path | None,
) -> None:
    if output_csv:
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        with output_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)
    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(rows, ensure_ascii=True, indent=2, default=str), encoding="utf-8")


def add_benchmark_ladder_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--config", required=True, help="Benchmark ladder YAML config.")
    parser.add_argument("--output", default=None, help="Output CSV path.")
    parser.add_argument("--output-json", default=None, help="Output JSON path.")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Logging level",
    )
    return parser


def run(args: argparse.Namespace) -> list[dict[str, Any]]:
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(levelname)s: %(message)s",
    )
    config_path = _resolve_path(args.config)
    assert config_path is not None
    config = _load_yaml(config_path)
    cfg = _section(config)
    rows = build_benchmark_ladder(config, config_dir=config_path.parent)
    output_csv = _resolve_path(args.output or cfg.get("output_csv") or cfg.get("output"), base_dir=config_path.parent)
    output_json = _resolve_path(args.output_json or cfg.get("output_json"), base_dir=config_path.parent)
    if output_csv is None and output_json is None:
        print(json.dumps(rows, ensure_ascii=True, indent=2, default=str))
    else:
        write_reports(rows, output_csv=output_csv, output_json=output_json)
        if output_csv:
            logging.info("Benchmark ladder CSV written to %s", output_csv)
        if output_json:
            logging.info("Benchmark ladder JSON written to %s", output_json)
    return rows

