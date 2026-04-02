from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

_SEVERITY_RANK = {
    "info": 0,
    "warning": 1,
    "error": 2,
}
_FAIL_ON_SEVERITIES = ("none", "info", "warning", "error")


def _normalize_quality_severity(value: object) -> str | None:
    text = str(value or "").strip().lower()
    if text in _SEVERITY_RANK:
        return text
    return None


def normalize_fail_on_severity(value: object) -> str:
    text = str(value or "none").strip().lower()
    if not text:
        return "none"
    if text not in _FAIL_ON_SEVERITIES:
        raise SystemExit("fail_on_severity must be one of: none, info, warning, error.")
    return text


def format_quality_check_label(row: Mapping[str, object]) -> str:
    check = str(row.get("check") or "").strip() or "unknown_check"
    field = str(row.get("field") or "").strip()
    if field:
        return f"{check} [{field}]"
    return check


def summarize_quality_checks(
    quality_checks: Sequence[Mapping[str, object]] | None,
    *,
    fail_on_severity: object = "none",
) -> dict[str, object]:
    threshold = normalize_fail_on_severity(fail_on_severity)
    threshold_rank = _SEVERITY_RANK.get(threshold, 99)

    severity_counts: Counter[str] = Counter()
    failing_labels: list[str] = []
    max_rank = -1
    max_severity = "none"

    for row in quality_checks or []:
        if not isinstance(row, Mapping):
            continue
        severity = _normalize_quality_severity(row.get("severity")) or "info"
        severity_counts[severity] += 1
        severity_rank = _SEVERITY_RANK[severity]
        if severity_rank > max_rank:
            max_rank = severity_rank
            max_severity = severity
        if threshold != "none" and severity_rank >= threshold_rank:
            label = format_quality_check_label(row)
            if label not in failing_labels and len(failing_labels) < 5:
                failing_labels.append(label)

    issue_count = int(sum(severity_counts.values()))
    failing_issue_count = 0
    if threshold != "none":
        failing_issue_count = int(
            sum(
                count
                for severity, count in severity_counts.items()
                if _SEVERITY_RANK[severity] >= threshold_rank
            )
        )
    gate_triggered = bool(failing_issue_count > 0)

    if issue_count <= 0:
        color = "green"
        message = "No quality issues detected."
    elif max_severity == "error":
        color = "red"
        message = f"{issue_count} quality issue(s) detected, including at least one error."
    else:
        color = "yellow"
        message = f"{issue_count} quality issue(s) detected; max_severity={max_severity}."

    if threshold != "none":
        if gate_triggered:
            message = (
                f"{failing_issue_count} quality issue(s) met fail_on_severity={threshold}; "
                "the inspection gate was triggered."
            )
        else:
            message = (
                f"{issue_count} quality issue(s) detected; none met fail_on_severity={threshold}."
            )

    return {
        "color": color,
        "overall_severity": max_severity if issue_count > 0 else "none",
        "issue_count": issue_count,
        "severity_counts": {
            "error": int(severity_counts.get("error", 0)),
            "warning": int(severity_counts.get("warning", 0)),
            "info": int(severity_counts.get("info", 0)),
        },
        "fail_on_severity": threshold,
        "gate_triggered": gate_triggered,
        "gate_status": "fail" if gate_triggered else "pass",
        "failing_issue_count": failing_issue_count,
        "sample_failing_checks": failing_labels,
        "message": message,
    }


def quality_gate_exit_code(quality_verdict: Mapping[str, object] | None) -> int:
    if isinstance(quality_verdict, Mapping) and bool(quality_verdict.get("gate_triggered")):
        return 2
    return 0


def append_quality_verdict_lines(
    lines: list[str],
    quality_verdict: Mapping[str, object] | None,
    *,
    heading: str = "Quality Verdict",
) -> None:
    if not isinstance(quality_verdict, Mapping):
        return
    lines.append("")
    lines.append(heading)
    for key in ("color", "overall_severity", "issue_count", "gate_status", "fail_on_severity"):
        lines.append(f"{key}: {quality_verdict.get(key)}")
    severity_counts = quality_verdict.get("severity_counts")
    if isinstance(severity_counts, Mapping):
        lines.append(
            "severity_counts: "
            f"error={int(severity_counts.get('error', 0))}, "
            f"warning={int(severity_counts.get('warning', 0))}, "
            f"info={int(severity_counts.get('info', 0))}"
        )
    lines.append(f"gate_triggered: {bool(quality_verdict.get('gate_triggered'))}")
    message = quality_verdict.get("message")
    if message:
        lines.append(f"message: {message}")
    sample_failing_checks = quality_verdict.get("sample_failing_checks")
    if isinstance(sample_failing_checks, list) and sample_failing_checks:
        lines.append("sample_failing_checks: " + ", ".join(str(item) for item in sample_failing_checks))
