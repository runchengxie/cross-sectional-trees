from __future__ import annotations

import json
import logging
import tempfile
from argparse import Namespace
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..artifacts import resolve_repo_path
from ..config_utils import get_research_universe_config, resolve_pipeline_config
from ..data_tools import rqdata_assets
from ..data_tools.rqdata_assets.quality_gate import (
    normalize_fail_on_severity,
    rethreshold_quality_verdict,
)

LOGGER = logging.getLogger("csml")


def _mapping(value: object | None) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _normalize_list(values: object | None) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        text = values.strip()
        return [text] if text else []
    if isinstance(values, Sequence):
        items: list[str] = []
        for value in values:
            text = str(value or "").strip()
            if text:
                items.append(text)
        return items
    text = str(values).strip()
    return [text] if text else []


def resolve_quality_fail_on_severity(
    config: Mapping[str, Any] | None,
    *,
    override: object | None = None,
) -> str:
    quality_cfg = _mapping(_mapping(config).get("quality"))
    if override is not None:
        return normalize_fail_on_severity(override)
    return normalize_fail_on_severity(quality_cfg.get("fail_on_severity", "none"))


def _build_hk_pit_preflight_args(
    *,
    config: Mapping[str, Any],
    fail_on_severity: str,
    out_path: Path,
) -> Namespace | None:
    data_cfg = _mapping(config.get("data"))
    market = str(config.get("market") or data_cfg.get("market") or "").strip().lower()
    provider = str(data_cfg.get("provider") or "").strip().lower()
    if market != "hk" or provider not in {"rqdata", "rqdatac"}:
        return None

    fundamentals_cfg = _mapping(config.get("fundamentals"))
    if not bool(fundamentals_cfg.get("enabled", False)):
        return None
    if str(fundamentals_cfg.get("source", "provider") or "provider").strip().lower() != "file":
        return None

    fundamentals_file = fundamentals_cfg.get("file")
    if not fundamentals_file:
        return None

    universe_cfg = _mapping(get_research_universe_config(config))
    quality_cfg = _mapping(config.get("quality"))
    by_date_file = universe_cfg.get("by_date_file")
    min_symbols = universe_cfg.get("min_symbols_per_date")

    target_date = quality_cfg.get("target_date")
    target_date_text = None if target_date is None else str(target_date).strip() or None
    mode = str(quality_cfg.get("pit_coverage_mode", "strict") or "strict").strip().lower()

    min_symbols_value = None
    if min_symbols is not None:
        min_symbols_value = int(min_symbols)

    return Namespace(
        config=None,
        asset_dir=None,
        fundamentals_file=str(resolve_repo_path(str(fundamentals_file))),
        field_profile=[],
        field=_normalize_list(fundamentals_cfg.get("features")),
        fields_file=[],
        mode=mode,
        include_health=True,
        target_date=target_date_text,
        symbols_file=None,
        by_date_file=str(resolve_repo_path(str(by_date_file))) if by_date_file else None,
        health_sample_limit=int(quality_cfg.get("health_sample_limit", 5) or 5),
        min_symbols=min_symbols_value,
        top=10,
        quarter_limit=12,
        format="json",
        out=str(out_path),
        fail_on_severity=fail_on_severity,
    )


def _build_disabled_preflight(
    *,
    fail_on_severity: str,
    message: str,
) -> dict[str, Any]:
    return {
        "enabled": False,
        "fail_on_severity": fail_on_severity,
        "checks": [],
        "overall_verdict": None,
        "gate_triggered": False,
        "message": message,
    }


def run_quality_preflight(
    *,
    config: Mapping[str, Any],
    run_dir: Path | None,
    save_artifacts: bool,
    fail_on_quality: object | None = None,
    logger: logging.Logger | None = None,
) -> dict[str, Any]:
    logger = logger or LOGGER
    fail_on_severity = resolve_quality_fail_on_severity(config, override=fail_on_quality)
    quality_cfg = _mapping(config.get("quality"))
    save_report = bool(quality_cfg.get("save_report", False)) or fail_on_severity != "none"
    if fail_on_severity == "none" and not save_report:
        return _build_disabled_preflight(
            fail_on_severity=fail_on_severity,
            message="Quality preflight disabled.",
        )

    cleanup_path: Path | None = None
    if save_artifacts and run_dir is not None:
        report_dir = run_dir / "quality"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "hk_pit_coverage_preflight.json"
    else:
        handle = tempfile.NamedTemporaryFile(
            prefix="csml_quality_preflight_",
            suffix=".json",
            delete=False,
        )
        handle.close()
        report_path = Path(handle.name)
        cleanup_path = report_path

    try:
        args = _build_hk_pit_preflight_args(
            config=config,
            fail_on_severity=fail_on_severity,
            out_path=report_path,
        )
        if args is None:
            return _build_disabled_preflight(
                fail_on_severity=fail_on_severity,
                message="No supported quality preflight checks matched the current config.",
            )

        result_code = rqdata_assets.inspect_hk_pit_coverage(args)
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        raw_verdict = payload.get("quality_verdict")
        quality_verdict = (
            rethreshold_quality_verdict(raw_verdict, fail_on_severity=fail_on_severity)
            if isinstance(raw_verdict, Mapping)
            else None
        )
        health = payload.get("health") if isinstance(payload.get("health"), Mapping) else None
        selection = payload.get("selection") if isinstance(payload.get("selection"), Mapping) else None
        check_result = {
            "name": "hk_pit_coverage_health",
            "kind": "hk_pit_coverage",
            "status": "fail" if bool(quality_verdict and quality_verdict.get("gate_triggered")) else "pass",
            "result_code": int(result_code or 0),
            "report_file": str(report_path) if save_artifacts and run_dir is not None else None,
            "quality_verdict": quality_verdict,
            "summary": {
                "target_date": health.get("target_date") if isinstance(health, Mapping) else None,
                "selected_feature_count": int(selection.get("count", 0) or 0)
                if isinstance(selection, Mapping)
                else 0,
                "min_symbols_threshold": selection.get("min_symbols_threshold")
                if isinstance(selection, Mapping)
                else None,
                "fundamentals_file": _mapping(payload.get("source")).get("fundamentals_file"),
            },
        }
        overall_verdict = quality_verdict
        return {
            "enabled": True,
            "fail_on_severity": fail_on_severity,
            "checks": [check_result],
            "overall_verdict": overall_verdict,
            "gate_triggered": bool(overall_verdict and overall_verdict.get("gate_triggered")),
            "message": (
                str(overall_verdict.get("message"))
                if isinstance(overall_verdict, Mapping) and overall_verdict.get("message")
                else "Quality preflight completed."
            ),
        }
    finally:
        if cleanup_path is not None:
            cleanup_path.unlink(missing_ok=True)


def _load_run_quality_preflight(run_dir: Path) -> dict[str, Any] | None:
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        return None
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    quality = payload.get("quality")
    if not isinstance(quality, Mapping):
        return None
    preflight = quality.get("preflight")
    return dict(preflight) if isinstance(preflight, Mapping) else None


def _resolve_summary_threshold(preflight: Mapping[str, Any] | None) -> str:
    if not isinstance(preflight, Mapping):
        return "none"
    return normalize_fail_on_severity(preflight.get("fail_on_severity", "none"))


def _rethreshold_preflight(
    preflight: Mapping[str, Any],
    *,
    fail_on_severity: str,
) -> dict[str, Any]:
    checks_out: list[dict[str, Any]] = []
    for item in preflight.get("checks") if isinstance(preflight.get("checks"), list) else []:
        if not isinstance(item, Mapping):
            continue
        updated = dict(item)
        if isinstance(item.get("quality_verdict"), Mapping):
            updated["quality_verdict"] = rethreshold_quality_verdict(
                item.get("quality_verdict"),
                fail_on_severity=fail_on_severity,
            )
        checks_out.append(updated)

    overall_verdict = (
        rethreshold_quality_verdict(
            preflight.get("overall_verdict"),
            fail_on_severity=fail_on_severity,
        )
        if isinstance(preflight.get("overall_verdict"), Mapping)
        else None
    )
    return {
        **dict(preflight),
        "fail_on_severity": fail_on_severity,
        "checks": checks_out,
        "overall_verdict": overall_verdict,
        "gate_triggered": bool(overall_verdict and overall_verdict.get("gate_triggered")),
        "message": (
            str(overall_verdict.get("message"))
            if isinstance(overall_verdict, Mapping) and overall_verdict.get("message")
            else str(preflight.get("message") or "")
        ),
    }


def enforce_liveops_quality_gate(
    *,
    command_name: str,
    run_dir: Path | None,
    config_ref: str | Path | None,
    fail_on_quality: object | None = None,
) -> dict[str, Any] | None:
    saved_preflight = _load_run_quality_preflight(run_dir) if run_dir is not None else None
    if fail_on_quality is not None:
        fail_on_severity = normalize_fail_on_severity(fail_on_quality)
    elif config_ref is not None:
        resolved = resolve_pipeline_config(config_ref)
        fail_on_severity = resolve_quality_fail_on_severity(resolved.data)
    else:
        fail_on_severity = _resolve_summary_threshold(saved_preflight)

    if fail_on_severity == "none":
        return (
            _rethreshold_preflight(saved_preflight, fail_on_severity=fail_on_severity)
            if isinstance(saved_preflight, Mapping)
            else None
        )

    if isinstance(saved_preflight, Mapping):
        evaluated = _rethreshold_preflight(saved_preflight, fail_on_severity=fail_on_severity)
    elif config_ref is not None:
        resolved = resolve_pipeline_config(config_ref)
        evaluated = run_quality_preflight(
            config=resolved.data if isinstance(resolved.data, Mapping) else {},
            run_dir=None,
            save_artifacts=False,
            fail_on_quality=fail_on_severity,
            logger=LOGGER,
        )
    else:
        raise SystemExit(
            f"{command_name} quality gate requires --config or a run_dir whose summary.json includes quality.preflight."
        )

    overall_verdict = evaluated.get("overall_verdict") if isinstance(evaluated, Mapping) else None
    if isinstance(overall_verdict, Mapping) and bool(overall_verdict.get("gate_triggered")):
        report_file = None
        checks = evaluated.get("checks") if isinstance(evaluated.get("checks"), list) else []
        for item in checks:
            if isinstance(item, Mapping) and item.get("report_file"):
                report_file = str(item.get("report_file"))
                break
        suffix = f" Report: {report_file}" if report_file else ""
        raise SystemExit(
            f"{command_name} blocked by quality gate: {overall_verdict.get('message')}{suffix}"
        )
    return evaluated
