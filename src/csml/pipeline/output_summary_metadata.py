from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from ..date_utils import is_relative_date_token
from ..repo_paths import resolve_repo_path as resolve_repo_relative_path
from .support import save_json


def _resolve_input_path(value: object | None) -> Path | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return resolve_repo_relative_path(text)


def _infer_manifest_path(value: object | None) -> Path | None:
    path = _resolve_input_path(value)
    if path is None:
        return None
    candidates: list[Path] = []
    if path.is_dir():
        candidates.append(path / "manifest.yml")
    else:
        candidates.append(path.with_name(f"{path.stem}.manifest.yml"))
        candidates.append(path.parent / "manifest.yml")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _looks_like_latest(value: object | None) -> bool:
    if value is None:
        return False
    text = str(value).strip().lower()
    if not text:
        return False
    return "latest" in text


def build_inputs_lock(context: Mapping[str, Any]) -> dict[str, Any]:
    ctx = context
    data_cfg = ctx.get("data_cfg") if isinstance(ctx.get("data_cfg"), Mapping) else {}
    eval_cfg = ctx.get("eval_cfg") if isinstance(ctx.get("eval_cfg"), Mapping) else {}
    live_cfg = ctx.get("live_cfg") if isinstance(ctx.get("live_cfg"), Mapping) else {}
    rq_cfg = data_cfg.get("rqdata") if isinstance(data_cfg.get("rqdata"), Mapping) else {}
    benchmark_compare_cfg = (
        ctx.get("BACKTEST_BENCHMARK_COMPARE")
        if isinstance(ctx.get("BACKTEST_BENCHMARK_COMPARE"), list)
        else []
    )
    benchmark_compare_files = [
        item.get("returns_file")
        for item in benchmark_compare_cfg
        if isinstance(item, Mapping) and item.get("returns_file")
    ]

    raw_inputs = {
        "cache_dir": ctx.get("CACHE_DIR"),
        "daily_asset_dir": rq_cfg.get("daily_asset_dir"),
        "instruments_file": rq_cfg.get("instruments_file"),
        "ex_factors_dir": rq_cfg.get("ex_factors_dir"),
        "universe_by_date_file": ctx.get("by_date_file"),
        "fundamentals_file": ctx.get("FUNDAMENTALS_FILE"),
        "industry_file": ctx.get("INDUSTRY_FILE"),
        "benchmark_returns_file": ctx.get("BACKTEST_BENCHMARK_RETURNS_FILE"),
        "eval_output_dir": eval_cfg.get("output_dir"),
    }
    resolved_inputs = {
        key: str(path)
        for key, path in (
            (key, _resolve_input_path(value))
            for key, value in raw_inputs.items()
        )
        if path is not None
    }
    source_manifests = {
        key: str(path)
        for key, path in (
            (f"{key}_manifest", _infer_manifest_path(value))
            for key, value in raw_inputs.items()
            if key not in {"cache_dir", "eval_output_dir"}
        )
        if path is not None
    }
    if benchmark_compare_files:
        resolved_compare_files = [
            str(path)
            for path in (
                _resolve_input_path(value) for value in benchmark_compare_files
            )
            if path is not None
        ]
        if resolved_compare_files:
            resolved_inputs["benchmark_compare_returns_files"] = resolved_compare_files
    return {
        "artifacts_root": str(ctx.get("ARTIFACTS_ROOT")) if ctx.get("ARTIFACTS_ROOT") else None,
        "run_dir": str(ctx["run_dir"]),
        "config_path": str(ctx["config_path"]) if ctx.get("config_path") else None,
        "config_source": ctx.get("config_source"),
        "resolved_dates": {
            "start_date": ctx.get("START_DATE"),
            "end_date": ctx.get("END_DATE"),
            "live_as_of": ctx.get("LIVE_AS_OF"),
        },
        "inputs": resolved_inputs,
        "source_manifests": source_manifests,
        "mutable_inputs": {
            "used_relative_start_date": is_relative_date_token(data_cfg.get("start_date")),
            "used_relative_end_date": is_relative_date_token(data_cfg.get("end_date")),
            "used_relative_live_as_of": is_relative_date_token(live_cfg.get("as_of")),
            "used_latest_pointer": any(_looks_like_latest(value) for value in raw_inputs.values()),
        },
    }


def write_run_metadata(
    *,
    context: Mapping[str, Any],
    summary: Mapping[str, Any],
) -> None:
    ctx = context
    run_dir = ctx["run_dir"]

    save_json(summary, run_dir / "summary.json")
    save_json(build_inputs_lock(ctx), run_dir / "inputs.lock.json")
    with (run_dir / "config.used.yml").open("w", encoding="utf-8") as handle:
        yaml.safe_dump(ctx["config"], handle, sort_keys=False)

    if ctx["LIVE_ENABLED"]:
        latest_payload = {
            "pointer_type": "mutable_latest",
            "run_dir": str(run_dir),
            "run_name": ctx["run_name"],
            "timestamp": ctx["run_stamp"],
            "config_hash": ctx["run_hash"],
            "summary_file": str(run_dir / "summary.json"),
            "as_of": summary.get("live", {}).get("as_of"),
            "positions_file": summary.get("live", {}).get("positions_file"),
            "current_file": summary.get("live", {}).get("current_file"),
            "diff_file": summary.get("live", {}).get("diff_file"),
        }
        save_json(latest_payload, run_dir.parent / "latest.json")
