from __future__ import annotations

import argparse
import copy
import csv
import json
import logging
import tempfile
from pathlib import Path

import yaml

from ..config_utils import resolve_pipeline_config


def _resolve_output_path(path_text: str) -> Path:
    candidate = Path(path_text).expanduser()
    if candidate.is_absolute():
        return candidate
    return (Path.cwd() / candidate).resolve()


def _parse_int_list(values: list[str]) -> list[int]:
    items: list[int] = []
    for entry in values:
        for part in entry.split(","):
            text = part.strip()
            if not text:
                continue
            items.append(int(text))
    return items


def _parse_float_list(values: list[str]) -> list[float]:
    items: list[float] = []
    for entry in values:
        for part in entry.split(","):
            text = part.strip()
            if not text:
                continue
            items.append(float(text))
    return items


def _safe_run_name(base: str, top_k: int, cost_bps: float) -> str:
    cost_text = ("%g" % cost_bps).replace(".", "p")
    return f"{base}_k{top_k}_bps{cost_text}"


def _find_latest_summary(output_dir: Path, run_name: str) -> Path | None:
    pattern = f"{run_name}_*/summary.json"
    candidates = list(output_dir.glob(pattern))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _get_nested(payload: dict, *keys):
    current = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _extract_row(summary: dict | None, top_k: int, cost_bps: float, run_name: str, summary_path: Path | None):
    row = {
        "run_name": run_name,
        "top_k": top_k,
        "cost_bps": cost_bps,
        "summary_path": str(summary_path) if summary_path else None,
        "output_dir": None,
        "label_horizon_days": None,
        "eval_ic_mean": None,
        "eval_ic_ir": None,
        "eval_long_short": None,
        "eval_turnover_mean": None,
        "backtest_periods": None,
        "backtest_total_return": None,
        "backtest_ann_return": None,
        "backtest_ann_vol": None,
        "backtest_sharpe": None,
        "backtest_max_drawdown": None,
        "backtest_avg_turnover": None,
        "backtest_avg_cost_drag": None,
        "status": "ok",
        "error": None,
    }
    if summary is None:
        row["status"] = "missing_summary"
        return row

    row["output_dir"] = _get_nested(summary, "run", "output_dir")
    row["label_horizon_days"] = _get_nested(summary, "label", "horizon_days")
    row["eval_ic_mean"] = _get_nested(summary, "eval", "ic", "mean")
    row["eval_ic_ir"] = _get_nested(summary, "eval", "ic", "ir")
    row["eval_long_short"] = _get_nested(summary, "eval", "long_short")
    row["eval_turnover_mean"] = _get_nested(summary, "eval", "turnover_mean")

    bt_stats = _get_nested(summary, "backtest", "stats") or {}
    if isinstance(bt_stats, dict) and bt_stats:
        row["backtest_periods"] = bt_stats.get("periods")
        row["backtest_total_return"] = bt_stats.get("total_return")
        row["backtest_ann_return"] = bt_stats.get("ann_return")
        row["backtest_ann_vol"] = bt_stats.get("ann_vol")
        row["backtest_sharpe"] = bt_stats.get("sharpe")
        row["backtest_max_drawdown"] = bt_stats.get("max_drawdown")
        row["backtest_avg_turnover"] = bt_stats.get("avg_turnover")
        row["backtest_avg_cost_drag"] = bt_stats.get("avg_cost_drag")
    else:
        row["status"] = "no_backtest"
    return row


def add_grid_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument(
        "--config",
        default="config/hk.yml",
        help="Base config path or built-in name (default: config/hk.yml)",
    )
    parser.add_argument(
        "--top-k",
        action="append",
        default=["5,10,20"],
        help="Comma-separated top_k values (default: 5,10,20)",
    )
    parser.add_argument(
        "--cost-bps",
        action="append",
        default=["15,25,40"],
        help="Comma-separated cost bps per side (default: 15,25,40)",
    )
    parser.add_argument(
        "--output",
        default="out/runs/grid_summary.csv",
        help="Output CSV path (default: out/runs/grid_summary.csv)",
    )
    parser.add_argument(
        "--run-name-prefix",
        default=None,
        help="Optional prefix for run_name (default: base config stem)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Logging level",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run a grid of Top-K and cost bps settings")
    add_grid_args(parser)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(levelname)s: %(message)s",
    )

    resolved = resolve_pipeline_config(args.config)
    base_cfg = resolved.data
    base_label = args.run_name_prefix or resolved.label

    from .. import pipeline

    top_k_values = _parse_int_list(args.top_k)
    cost_values = _parse_float_list(args.cost_bps)
    combos = [(top_k, cost) for top_k in top_k_values for cost in cost_values]

    output_path = _resolve_output_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logging.info("Running %s combinations ...", len(combos))
    rows = []

    with tempfile.TemporaryDirectory(prefix="csxgb_grid_") as tmp_dir:
        tmp_dir_path = Path(tmp_dir)

        for top_k, cost_bps in combos:
            cfg = copy.deepcopy(base_cfg)
            cfg.setdefault("eval", {})
            cfg.setdefault("backtest", {})

            run_name = _safe_run_name(base_label, top_k, cost_bps)
            cfg["eval"]["run_name"] = run_name
            cfg["eval"]["top_k"] = top_k
            cfg["backtest"]["top_k"] = top_k
            cfg["eval"]["transaction_cost_bps"] = cost_bps
            cfg["backtest"]["transaction_cost_bps"] = cost_bps

            cfg_path = tmp_dir_path / f"{run_name}.yml"
            with cfg_path.open("w", encoding="utf-8") as handle:
                yaml.safe_dump(cfg, handle, sort_keys=False)

            logging.info("Running: top_k=%s cost_bps=%s", top_k, cost_bps)
            summary = None
            summary_path = None
            try:
                pipeline.run(str(cfg_path))
                output_dir = Path(cfg.get("eval", {}).get("output_dir", "out/runs"))
                output_dir = _resolve_output_path(str(output_dir))
                summary_path = _find_latest_summary(output_dir, run_name)
                if summary_path and summary_path.exists():
                    with summary_path.open("r", encoding="utf-8") as handle:
                        summary = json.load(handle)
            except SystemExit as exc:
                logging.error("Run failed for top_k=%s cost_bps=%s: %s", top_k, cost_bps, exc)
                row = _extract_row(None, top_k, cost_bps, run_name, summary_path)
                row["status"] = "failed"
                row["error"] = str(exc)
                rows.append(row)
                continue

            row = _extract_row(summary, top_k, cost_bps, run_name, summary_path)
            rows.append(row)

    fieldnames = [
        "run_name",
        "top_k",
        "cost_bps",
        "summary_path",
        "output_dir",
        "label_horizon_days",
        "eval_ic_mean",
        "eval_ic_ir",
        "eval_long_short",
        "eval_turnover_mean",
        "backtest_periods",
        "backtest_total_return",
        "backtest_ann_return",
        "backtest_ann_vol",
        "backtest_sharpe",
        "backtest_max_drawdown",
        "backtest_avg_turnover",
        "backtest_avg_cost_drag",
        "status",
        "error",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    logging.info("Summary written to %s", output_path)


if __name__ == "__main__":
    main()
