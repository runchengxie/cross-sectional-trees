from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..config_utils import resolve_pipeline_config

LOGGER = logging.getLogger("cstree")
_SEVERITY_RANK = {"info": 0, "warning": 1, "error": 2}
_FAIL_ON_SEVERITIES = ("none", "info", "warning", "error")


def _mapping(value: object | None) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def normalize_fail_on_severity(value: object) -> str:
    text = str(value or "none").strip().lower()
    if not text:
        return "none"
    if text not in _FAIL_ON_SEVERITIES:
        raise SystemExit("fail_on_severity must be one of: none, info, warning, error.")
    return text


def _coerce_int(value: object, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _normalize_quality_severity(value: object) -> str | None:
    text = str(value or "").strip().lower()
    return text if text in _SEVERITY_RANK else None


def _summarize_quality_state(
    *,
    issue_count: int,
    overall_severity: str,
    fail_on_severity: str,
    severity_counts: Mapping[str, object] | None,
) -> tuple[str, int, bool, str]:
    threshold_rank = _SEVERITY_RANK.get(fail_on_severity, 99)
    counts = severity_counts if isinstance(severity_counts, Mapping) else {}
    failing_issue_count = 0
    if fail_on_severity != "none":
        failing_issue_count = int(
            sum(
                _coerce_int(counts.get(severity, 0))
                for severity, rank in _SEVERITY_RANK.items()
                if rank >= threshold_rank
            )
        )
    gate_triggered = failing_issue_count > 0
    if issue_count <= 0:
        color = "green"
        message = "No quality issues detected."
    elif overall_severity == "error":
        color = "red"
        message = f"{issue_count} quality issue(s) detected, including at least one error."
    else:
        color = "yellow"
        message = f"{issue_count} quality issue(s) detected; max_severity={overall_severity}."
    if fail_on_severity != "none":
        if gate_triggered:
            message = (
                f"{failing_issue_count} quality issue(s) met fail_on_severity={fail_on_severity}; "
                "the inspection gate was triggered."
            )
        else:
            message = (
                f"{issue_count} quality issue(s) detected; none met fail_on_severity={fail_on_severity}."
            )
    return color, failing_issue_count, gate_triggered, message


def rethreshold_quality_verdict(
    quality_verdict: Mapping[str, object] | None,
    *,
    fail_on_severity: object | None = None,
) -> dict[str, object] | None:
    if not isinstance(quality_verdict, Mapping):
        return None
    threshold = normalize_fail_on_severity(
        fail_on_severity
        if fail_on_severity is not None
        else quality_verdict.get("fail_on_severity", "none")
    )
    counts_raw = quality_verdict.get("severity_counts")
    counts = {
        "error": _coerce_int(counts_raw.get("error") if isinstance(counts_raw, Mapping) else 0),
        "warning": _coerce_int(
            counts_raw.get("warning") if isinstance(counts_raw, Mapping) else 0
        ),
        "info": _coerce_int(counts_raw.get("info") if isinstance(counts_raw, Mapping) else 0),
    }
    issue_count = _coerce_int(quality_verdict.get("issue_count"), default=sum(counts.values()))
    overall_severity = _normalize_quality_severity(quality_verdict.get("overall_severity"))
    if overall_severity is None:
        if counts["error"] > 0:
            overall_severity = "error"
        elif counts["warning"] > 0:
            overall_severity = "warning"
        elif counts["info"] > 0:
            overall_severity = "info"
        else:
            overall_severity = "none"
    color, failing_issue_count, gate_triggered, message = _summarize_quality_state(
        issue_count=issue_count,
        overall_severity=overall_severity if issue_count > 0 else "none",
        fail_on_severity=threshold,
        severity_counts=counts,
    )
    updated = dict(quality_verdict)
    updated.update(
        {
            "color": color,
            "overall_severity": overall_severity if issue_count > 0 else "none",
            "issue_count": issue_count,
            "severity_counts": counts,
            "fail_on_severity": threshold,
            "gate_triggered": gate_triggered,
            "gate_status": "fail" if gate_triggered else "pass",
            "failing_issue_count": failing_issue_count,
            "message": message,
        }
    )
    return updated


def resolve_quality_fail_on_severity(
    config: Mapping[str, Any] | None,
    *,
    override: object | None = None,
) -> str:
    quality_cfg = _mapping(_mapping(config).get("quality"))
    if override is not None:
        return normalize_fail_on_severity(override)
    return normalize_fail_on_severity(quality_cfg.get("fail_on_severity", "none"))


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

    logger.info(
        "HK PIT quality preflight is no longer executed by cstree; use "
        "marketdata rqdata hk-assets -- inspect-hk-pit-coverage."
    )
    return _build_disabled_preflight(
        fail_on_severity=fail_on_severity,
        message=(
            "HK PIT quality preflight moved to market-data-platform. Run "
            "`marketdata rqdata hk-assets -- inspect-hk-pit-coverage ...` before research "
            "runs when this gate is required."
        ),
    )


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
