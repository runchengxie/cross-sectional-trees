from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from ..date_utils import is_relative_date_token
from ..repo_paths import resolve_repo_path as resolve_repo_relative_path
from .support import save_json


def _configured_input_path(value: object | None) -> Path | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    path = Path(text).expanduser()
    if path.is_absolute():
        return path.absolute()
    return (Path.cwd() / path).absolute()


def _resolve_input_path(value: object | None) -> Path | None:
    configured = _configured_input_path(value)
    if configured is None:
        return None
    return resolve_repo_relative_path(configured)


def _infer_manifest_path(value: object | None) -> Path | None:
    path = _configured_input_path(value)
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
            return candidate.resolve()
    return None


def _looks_like_latest(value: object | None) -> bool:
    if value is None:
        return False
    text = str(value).strip().lower()
    if not text:
        return False
    return "latest" in text


def _path_kind(path: Path | None) -> str | None:
    if path is None:
        return None
    if not path.exists():
        return "missing"
    if path.is_dir():
        return "directory"
    if path.is_file():
        return "file"
    return "other"


def _load_manifest_summary(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        return None
    query = payload.get("query") if isinstance(payload.get("query"), Mapping) else {}
    output_dir = str(payload.get("output_dir") or "").strip()
    snapshot_name = Path(output_dir).name if output_dir else None
    query_end_date = None
    for key in ("end_date", "date", "mapping_date", "as_of_date"):
        value = query.get(key)
        if value is None:
            continue
        query_end_date = str(value).strip() or None
        if query_end_date:
            break
    return {
        "dataset": str(payload.get("dataset") or "").strip() or None,
        "status": str(payload.get("status") or "").strip() or None,
        "output_dir": output_dir or None,
        "snapshot_name": snapshot_name,
        "query_end_date": query_end_date,
    }


def _build_input_resolution_entry(value: object | None) -> dict[str, Any] | None:
    configured_path = _configured_input_path(value)
    resolved_path = _resolve_input_path(value)
    if configured_path is None and resolved_path is None:
        return None
    manifest_path = _infer_manifest_path(value)
    manifest_summary = _load_manifest_summary(manifest_path)
    return {
        "raw": None if value is None else str(value),
        "configured_path": str(configured_path) if configured_path is not None else None,
        "resolved_path": str(resolved_path) if resolved_path is not None else None,
        "path_kind": _path_kind(configured_path),
        "exists": bool(configured_path.exists()) if configured_path is not None else False,
        "is_symlink": bool(configured_path.is_symlink()) if configured_path is not None else False,
        "points_to_latest_name": _looks_like_latest(value),
        "manifest_path": str(manifest_path) if manifest_path is not None else None,
        "manifest": manifest_summary,
    }


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
    benchmark_compare_symbols = [
        str(item.get("symbol")).strip()
        for item in benchmark_compare_cfg
        if isinstance(item, Mapping) and item.get("symbol")
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
    input_resolution = {
        key: entry
        for key, entry in (
            (key, _build_input_resolution_entry(value))
            for key, value in raw_inputs.items()
        )
        if entry is not None
    }
    resolved_inputs = {
        key: str(entry["resolved_path"])
        for key, entry in input_resolution.items()
        if entry.get("resolved_path")
    }
    source_manifests = {
        f"{key}_manifest": str(entry["manifest_path"])
        for key, entry in input_resolution.items()
        if key not in {"cache_dir", "eval_output_dir"} and entry.get("manifest_path")
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
    if benchmark_compare_symbols:
        resolved_inputs["benchmark_compare_symbols"] = benchmark_compare_symbols
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
        "input_resolution": input_resolution,
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
