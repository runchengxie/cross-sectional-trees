#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from csml.repo_paths import find_repo_root

from .package_assets import AVAILABLE_PART_CHOICES, create_relative_symlink

REPO_ROOT = find_repo_root(__file__)
ASSETS_ROOT = REPO_ROOT / "artifacts" / "assets"
REPORTS_ROOT = REPO_ROOT / "artifacts" / "reports"
RELEASES_ROOT = REPO_ROOT / "artifacts" / "releases"

REFRESH_ASSETS = (
    "instruments",
    "daily",
    "daily_clean",
    "valuation",
    "ex_factors",
    "dividends",
    "shares",
    "industry_changes",
    "southbound",
)
INSPECT_ASSETS = (
    "daily",
    "daily_clean",
    "valuation",
    "ex_factors",
    "dividends",
    "shares",
    "industry_changes",
    "southbound",
)
DEFAULT_PHASES = ("refresh", "inspect", "package")
DEFAULT_PACKAGE_PARTS = tuple(part for part in AVAILABLE_PART_CHOICES if part != "announcement")
PATCH_MERGE_SUPPORTED_ASSETS = frozenset({"daily", "valuation", "ex_factors", "dividends", "shares"})
DEFAULT_DAILY_PATCH_LOOKBACK_DAYS = 20
DEFAULT_DATED_PATCH_LOOKBACK_DAYS = 40
REPAIR_SEVERITY_RANK = {"error": 2, "warning": 1, "info": 0}


@dataclass
class SnapshotBundle:
    instruments_file: Path
    daily_dir: Path
    daily_clean_dir: Path
    valuation_dir: Path
    ex_factors_dir: Path
    dividends_dir: Path
    shares_dir: Path
    industry_changes_dir: Path
    southbound_dir: Path
    pit_dir: Path | None
    exchange_rate_dir: Path | None
    financial_details_dir: Path | None
    universe_by_date: Path
    universe_symbols: Path
    universe_meta: Path | None


@dataclass
class Step:
    phase: str
    label: str
    command: list[str]
    summary_path: Path | None = None
    alias_target: Path | None = None
    alias_link: Path | None = None
    asset_name: str | None = None
    report_metadata: dict[str, Any] | None = None


def _normalize_target_date(value: str) -> str:
    token = value.replace("-", "").strip()
    if len(token) != 8 or not token.isdigit():
        raise SystemExit(f"--target-date must be YYYYMMDD or YYYY-MM-DD. Got: {value!r}")
    return token


def _repo_relative(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def _csml_executable() -> list[str]:
    local = Path(sys.executable).with_name("csml")
    if local.exists():
        return [str(local)]
    resolved = shutil.which("csml")
    if resolved:
        return [resolved]
    return [
        sys.executable,
        "-c",
        "from csml.cli import main; import sys; raise SystemExit(main(sys.argv[1:]))",
    ]


def _run(cmd: list[str], *, dry_run: bool) -> subprocess.CompletedProcess:
    printable = " ".join(shlex.quote(part) for part in cmd)
    print("+", printable)
    if dry_run:
        return subprocess.CompletedProcess(cmd, 0, "", "")
    return subprocess.run(
        cmd,
        check=False,
        capture_output=False,
        text=True,
        cwd=REPO_ROOT,
    )


def _current_snapshot_bundle() -> SnapshotBundle:
    universe_root = ASSETS_ROOT / "universe"
    return SnapshotBundle(
        instruments_file=ASSETS_ROOT / "rqdata" / "hk" / "instruments" / "hk_all_instruments_latest.parquet",
        daily_dir=ASSETS_ROOT / "rqdata" / "hk" / "daily" / "hk_all_daily_latest",
        daily_clean_dir=ASSETS_ROOT / "rqdata" / "hk" / "daily" / "hk_all_daily_clean_latest",
        valuation_dir=ASSETS_ROOT / "rqdata" / "hk" / "valuation" / "hk_all_valuation_latest",
        ex_factors_dir=ASSETS_ROOT / "rqdata" / "hk" / "ex_factors" / "hk_all_ex_factors_latest",
        dividends_dir=ASSETS_ROOT / "rqdata" / "hk" / "dividends" / "hk_all_dividends_latest",
        shares_dir=ASSETS_ROOT / "rqdata" / "hk" / "shares" / "hk_all_shares_latest",
        industry_changes_dir=ASSETS_ROOT / "rqdata" / "hk" / "industry_changes" / "hk_all_industry_changes_latest",
        southbound_dir=ASSETS_ROOT / "rqdata" / "hk" / "southbound" / "hk_connect_southbound_latest",
        pit_dir=ASSETS_ROOT / "rqdata" / "hk" / "pit_financials" / "hk_all_2000_2025_full_market_latest",
        exchange_rate_dir=ASSETS_ROOT / "rqdata" / "hk" / "exchange_rate" / "hk_all_2000_20260319_exchange_rate_latest",
        financial_details_dir=None,
        universe_by_date=universe_root / "hk_all_full_by_date.csv",
        universe_symbols=universe_root / "hk_all_full_symbols.txt",
        universe_meta=universe_root / "hk_all_full_by_date.meta.yml",
    )


def _refreshed_snapshot_bundle(target_date: str) -> SnapshotBundle:
    universe_root = ASSETS_ROOT / "universe"
    return SnapshotBundle(
        instruments_file=ASSETS_ROOT / "rqdata" / "hk" / "instruments" / f"hk_all_instruments_{target_date}.parquet",
        daily_dir=ASSETS_ROOT
        / "rqdata"
        / "hk"
        / "daily"
        / f"hk_all_2000_{target_date}_daily_final_refetched_latest",
        daily_clean_dir=ASSETS_ROOT
        / "rqdata"
        / "hk"
        / "daily"
        / f"hk_all_2000_{target_date}_daily_clean_refetched_latest",
        valuation_dir=ASSETS_ROOT
        / "rqdata"
        / "hk"
        / "valuation"
        / f"hk_all_2000_{target_date}_valuation_full_market_refetched_latest",
        ex_factors_dir=ASSETS_ROOT
        / "rqdata"
        / "hk"
        / "ex_factors"
        / f"hk_all_2000_{target_date}_ex_factors_full_market_latest",
        dividends_dir=ASSETS_ROOT
        / "rqdata"
        / "hk"
        / "dividends"
        / f"hk_all_2000_{target_date}_dividends_full_market_latest",
        shares_dir=ASSETS_ROOT
        / "rqdata"
        / "hk"
        / "shares"
        / f"hk_all_2000_{target_date}_shares_full_market_latest",
        industry_changes_dir=ASSETS_ROOT
        / "rqdata"
        / "hk"
        / "industry_changes"
        / f"hk_all_2000_{target_date}_industry_changes_full_market_latest",
        southbound_dir=ASSETS_ROOT / "rqdata" / "hk" / "southbound" / f"hk_connect_southbound_{target_date}",
        pit_dir=ASSETS_ROOT / "rqdata" / "hk" / "pit_financials" / "hk_all_2000_2025_full_market_latest",
        exchange_rate_dir=ASSETS_ROOT / "rqdata" / "hk" / "exchange_rate" / "hk_all_2000_20260319_exchange_rate_latest",
        financial_details_dir=None,
        universe_by_date=universe_root / "hk_all_full_by_date.csv",
        universe_symbols=universe_root / "hk_all_full_symbols.txt",
        universe_meta=universe_root / "hk_all_full_by_date.meta.yml",
    )


def _phase_selection(args: argparse.Namespace) -> tuple[str, ...]:
    return tuple(dict.fromkeys(args.phase or DEFAULT_PHASES))


def _selected_refresh_assets(args: argparse.Namespace) -> tuple[str, ...]:
    return tuple(dict.fromkeys(args.refresh_asset or REFRESH_ASSETS))


def _selected_inspect_assets(args: argparse.Namespace) -> tuple[str, ...]:
    return tuple(dict.fromkeys(args.inspect_asset or INSPECT_ASSETS))


def _selected_parts(args: argparse.Namespace) -> tuple[str, ...]:
    return tuple(dict.fromkeys(args.part or DEFAULT_PACKAGE_PARTS))


def _default_workflow_report_path(target_date: str) -> Path:
    return REPORTS_ROOT / f"hk_asset_refresh_{target_date}.json"


def _load_asset_manifest(asset_dir: Path, *, asset_name: str) -> dict[str, object]:
    manifest_path = asset_dir / "manifest.yml"
    if not manifest_path.exists():
        raise SystemExit(
            f"Patch refresh requires an existing {asset_name} manifest: {manifest_path}"
        )
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Invalid manifest payload for {asset_name}: {manifest_path}")
    return payload


def _resolve_asset_end_date(asset_dir: Path, *, asset_name: str) -> str:
    manifest = _load_asset_manifest(asset_dir, asset_name=asset_name)
    query = manifest.get("query")
    if not isinstance(query, dict):
        raise SystemExit(
            f"Patch refresh requires manifest.query with an end date for {asset_name}: {asset_dir / 'manifest.yml'}"
        )
    for key in ("end_date", "date", "mapping_date", "as_of_date"):
        value = query.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return _normalize_target_date(text)
    raise SystemExit(
        f"Could not resolve current end date for patch refresh: {asset_dir / 'manifest.yml'}"
    )


def _subtract_calendar_days(date_text: str, days: int) -> str:
    parsed = datetime.strptime(date_text, "%Y%m%d")
    return (parsed - timedelta(days=days)).strftime("%Y%m%d")


def _patch_lookback_days(args: argparse.Namespace, *, asset_name: str) -> int:
    if asset_name == "daily":
        return int(args.daily_patch_lookback_days)
    return int(args.dated_patch_lookback_days)


def _resolve_patch_start_date(
    args: argparse.Namespace,
    *,
    asset_name: str,
    current_path: Path,
    floor_start_date: str,
) -> str:
    current_end_date = _resolve_asset_end_date(current_path, asset_name=asset_name)
    if args.target_date < current_end_date:
        raise SystemExit(
            f"Patch refresh requires --target-date >= current {asset_name} end date "
            f"({current_end_date}), got {args.target_date}."
        )
    lookback_days = _patch_lookback_days(args, asset_name=asset_name)
    window_start = _subtract_calendar_days(current_end_date, lookback_days - 1)
    return max(window_start, floor_start_date)


def _patch_snapshot_path(refreshed_path: Path) -> Path:
    return refreshed_path.parent / f"{refreshed_path.name}__patch"


def _normalize_report_path(path: Path | None, *, base_root: Path) -> Path | None:
    if path is None:
        return None
    return path.resolve() if path.is_absolute() else (base_root / path).resolve()


def _infer_manifest_path(path: Path) -> Path | None:
    if path.is_dir():
        candidate = path / "manifest.yml"
        if candidate.exists():
            return candidate.resolve()
        return None
    candidates = (
        path.with_name(f"{path.stem}.manifest.yml"),
        path.parent / "manifest.yml",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def _load_manifest_summary(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    query = payload.get("query") if isinstance(payload.get("query"), dict) else {}
    totals = payload.get("totals") if isinstance(payload.get("totals"), dict) else {}
    output_dir = str(payload.get("output_dir") or "").strip() or None
    return {
        "path": str(path),
        "dataset": str(payload.get("dataset") or "").strip() or None,
        "status": str(payload.get("status") or "").strip() or None,
        "output_dir": output_dir,
        "snapshot_name": Path(output_dir).name if output_dir else None,
        "query": {
            key: str(query.get(key)).strip()
            for key in ("start_date", "end_date", "date", "mapping_date", "as_of_date")
            if query.get(key) is not None and str(query.get(key)).strip()
        },
        "totals": {
            key: int(totals.get(key) or 0)
            for key in ("rows", "files", "symbols_written", "symbols_missing_remote")
            if key in totals
        },
    }


def _describe_path(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    manifest_path = _infer_manifest_path(path)
    exists = path.exists()
    return {
        "path": str(path),
        "resolved_path": str(path.resolve()) if exists or path.is_symlink() else str(path),
        "exists": exists,
        "is_symlink": path.is_symlink(),
        "kind": "directory" if path.is_dir() else "file" if path.is_file() else "missing",
        "manifest": _load_manifest_summary(manifest_path),
    }


def _load_health_report_summary(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    quality_checks = payload.get("quality_checks") if isinstance(payload.get("quality_checks"), list) else []
    severity_counts = {"error": 0, "warning": 0, "info": 0}
    for item in quality_checks:
        if not isinstance(item, dict):
            continue
        severity = str(item.get("severity") or "").strip().lower()
        if severity in severity_counts:
            severity_counts[severity] += 1
    issue_count = int(sum(severity_counts.values()))
    overall_severity = "none"
    if severity_counts["error"] > 0:
        overall_severity = "error"
    elif severity_counts["warning"] > 0:
        overall_severity = "warning"
    elif severity_counts["info"] > 0:
        overall_severity = "info"
    return {
        "report_path": str(path),
        "issue_count": issue_count,
        "severity_counts": severity_counts,
        "overall_severity": overall_severity,
        "history_issue_count": int(summary.get("history_issue_count") or 0),
    }


def _append_repair_candidate(
    candidates: dict[tuple[str, str | None, str | None, str | None], dict[str, Any]],
    *,
    symbol: str | None,
    trade_date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    check: str,
    severity: str | None,
    field: str | None = None,
    source: str,
    asset_name: str | None = None,
    reference_context: str | None = None,
    error: str | None = None,
) -> None:
    symbol_text = str(symbol or "").strip()
    if not symbol_text:
        return
    key = (
        symbol_text,
        str(trade_date).strip() or None if trade_date is not None else None,
        str(start_date).strip() or None if start_date is not None else None,
        str(end_date).strip() or None if end_date is not None else None,
    )
    entry = candidates.setdefault(
        key,
        {
            "symbol": symbol_text,
            "trade_date": key[1],
            "start_date": key[2],
            "end_date": key[3],
            "checks": [],
            "fields": [],
            "sources": [],
            "reference_contexts": [],
            "errors": [],
            "max_severity": "info",
            "asset_name": asset_name,
        },
    )
    if check and check not in entry["checks"]:
        entry["checks"].append(check)
    if field and field not in entry["fields"]:
        entry["fields"].append(field)
    if source and source not in entry["sources"]:
        entry["sources"].append(source)
    if reference_context and reference_context not in entry["reference_contexts"]:
        entry["reference_contexts"].append(reference_context)
    if error and error not in entry["errors"]:
        entry["errors"].append(error)
    severity_text = str(severity or "info").strip().lower() or "info"
    if REPAIR_SEVERITY_RANK.get(severity_text, -1) > REPAIR_SEVERITY_RANK.get(entry["max_severity"], -1):
        entry["max_severity"] = severity_text


def _extract_health_repair_candidates(
    *,
    payload: Mapping[str, Any],
    asset_name: str | None,
) -> list[dict[str, Any]]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    target_date = str(summary.get("target_date") or "").strip() or None
    field_rows = payload.get("field_coverage") if isinstance(payload.get("field_coverage"), list) else []
    field_map = {
        str(row.get("field")): row
        for row in field_rows
        if isinstance(row, Mapping) and str(row.get("field") or "").strip()
    }
    candidates: dict[tuple[str, str | None, str | None, str | None], dict[str, Any]] = {}

    for row in payload.get("sample_missing_asset_file_details") or []:
        if not isinstance(row, Mapping):
            continue
        _append_repair_candidate(
            candidates,
            symbol=str(row.get("symbol") or "").strip() or None,
            trade_date=target_date,
            check="missing_asset_file",
            severity="error",
            source="missing_asset_file",
            asset_name=asset_name,
            error=str(row.get("error") or "").strip() or None,
        )

    for row in payload.get("sample_stale_symbols") or []:
        if not isinstance(row, Mapping):
            continue
        _append_repair_candidate(
            candidates,
            symbol=str(row.get("symbol") or "").strip() or None,
            start_date=str(row.get("latest_date") or "").strip() or None,
            end_date=target_date,
            check="stale_symbol_missing_target_date_row",
            severity="warning",
            source="sample_stale_symbols",
            asset_name=asset_name,
            error=str(row.get("status") or "").strip() or None,
        )

    for issue in payload.get("quality_checks") or []:
        if not isinstance(issue, Mapping):
            continue
        check = str(issue.get("check") or "").strip()
        severity = str(issue.get("severity") or "").strip().lower() or "info"
        field = str(issue.get("field") or "").strip() or None
        sample_symbols = [
            str(item).strip()
            for item in (issue.get("sample_symbols") or [])
            if str(item).strip()
        ]
        if not sample_symbols:
            continue
        field_row = field_map.get(field or "")
        detail_key = None
        if "provider_like_ffill" in check or check == "field_all_clean_missing_on_target_date_provider_like":
            detail_key = "sample_provider_like_ffill_symbols"
        elif "ffill_age_gt_" in check:
            detail_key = "sample_oldest_ffill_symbols"
        elif "fresh_target_gap" in check:
            detail_key = "sample_fresh_target_gap_symbols"
        detail_map = {}
        if detail_key and isinstance(field_row, Mapping):
            detail_map = {
                str(item.get("symbol") or "").strip(): item
                for item in (field_row.get(detail_key) or [])
                if isinstance(item, Mapping) and str(item.get("symbol") or "").strip()
            }
        for symbol in sample_symbols:
            detail = detail_map.get(symbol, {})
            if isinstance(detail, Mapping) and (
                detail.get("start_date") is not None or detail.get("end_date") is not None
            ):
                _append_repair_candidate(
                    candidates,
                    symbol=symbol,
                    start_date=str(detail.get("start_date") or "").strip() or None,
                    end_date=str(detail.get("end_date") or "").strip() or None,
                    check=check,
                    severity=severity,
                    field=field,
                    source="quality_checks",
                    asset_name=asset_name,
                    reference_context=str(detail.get("reference_context") or "").strip() or None,
                )
                continue
            if isinstance(detail, Mapping) and detail.get("last_nonnull_date") is not None:
                _append_repair_candidate(
                    candidates,
                    symbol=symbol,
                    start_date=str(detail.get("last_nonnull_date") or "").strip() or None,
                    end_date=target_date,
                    check=check,
                    severity=severity,
                    field=field,
                    source="quality_checks",
                    asset_name=asset_name,
                    reference_context=str(detail.get("reference_context") or "").strip() or None,
                )
                continue
            _append_repair_candidate(
                candidates,
                symbol=symbol,
                trade_date=target_date,
                check=check,
                severity=severity,
                field=field,
                source="quality_checks",
                asset_name=asset_name,
            )

    history = payload.get("history") if isinstance(payload.get("history"), Mapping) else {}
    for issue in history.get("issues") or []:
        if not isinstance(issue, Mapping):
            continue
        check = str(issue.get("check") or "").strip()
        severity = str(issue.get("severity") or "").strip().lower() or "info"
        field = str(issue.get("field") or "").strip() or None
        for row in issue.get("sample_rows") or []:
            if not isinstance(row, Mapping):
                continue
            _append_repair_candidate(
                candidates,
                symbol=str(row.get("symbol") or "").strip() or None,
                trade_date=str(row.get("trade_date") or "").strip() or None,
                start_date=str(row.get("start_date") or "").strip() or None,
                end_date=str(row.get("end_date") or "").strip() or None,
                check=check,
                severity=severity,
                field=field,
                source="history_issues",
                asset_name=asset_name,
                reference_context=str(row.get("reference_context") or "").strip() or None,
            )

    return sorted(
        candidates.values(),
        key=lambda item: (
            -REPAIR_SEVERITY_RANK.get(str(item.get("max_severity") or "info"), -1),
            str(item.get("symbol") or ""),
            str(item.get("trade_date") or item.get("end_date") or item.get("start_date") or ""),
        ),
    )


def _load_health_report_analysis(path: Path, *, asset_name: str | None) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "quality": _load_health_report_summary(path),
        "repair_candidates": _extract_health_repair_candidates(payload=payload, asset_name=asset_name),
    }


def _init_workflow_report(
    *,
    args: argparse.Namespace,
    phases: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "workflow": {
            "target_date": args.target_date,
            "refresh_mode": args.refresh_mode,
            "phases": list(phases),
            "selected_refresh_assets": list(_selected_refresh_assets(args)),
            "selected_inspect_assets": list(_selected_inspect_assets(args)),
            "selected_parts": list(_selected_parts(args)),
            "inspect_fail_on_severity": args.inspect_fail_on_severity,
            "started_at": datetime.now().isoformat(timespec="seconds"),
        },
        "refresh": {
            "assets": {},
        },
        "inspect": {
            "assets": {},
        },
        "steps": [],
    }


def _record_refresh_report(
    report: dict[str, Any],
    *,
    step: Step,
) -> None:
    if not step.asset_name:
        return
    assets = report.setdefault("refresh", {}).setdefault("assets", {})
    entry = assets.setdefault(step.asset_name, {"asset_name": step.asset_name})
    metadata = dict(step.report_metadata or {})
    action = str(metadata.get("action") or "").strip()
    mode = str(metadata.get("mode") or "").strip() or None
    if mode:
        entry["mode"] = mode
    if action == "patch_fetch":
        base_path = metadata.get("base_path")
        patch_path = metadata.get("patch_path")
        refreshed_path = metadata.get("refreshed_path")
        entry["base"] = _describe_path(base_path) if isinstance(base_path, Path) else None
        entry["patch_window"] = {
            "start_date": metadata.get("start_date"),
            "end_date": metadata.get("end_date"),
            "lookback_days": metadata.get("lookback_days"),
        }
        entry["patch"] = _describe_path(patch_path) if isinstance(patch_path, Path) else None
        if isinstance(refreshed_path, Path):
            entry["planned_refreshed"] = str(refreshed_path)
        return
    if action in {"patch_merge", "full_refresh", "export"}:
        refreshed_path = metadata.get("refreshed_path")
        alias_path = metadata.get("alias_path")
        entry["refreshed"] = _describe_path(refreshed_path) if isinstance(refreshed_path, Path) else None
        entry["latest_alias"] = _describe_path(alias_path) if isinstance(alias_path, Path) else None


def _record_inspect_report(
    report: dict[str, Any],
    *,
    step: Step,
) -> None:
    if not step.asset_name or step.summary_path is None or not step.summary_path.exists():
        return
    assets = report.setdefault("inspect", {}).setdefault("assets", {})
    metadata = dict(step.report_metadata or {})
    analysis = _load_health_report_analysis(step.summary_path, asset_name=step.asset_name)
    assets[step.asset_name] = {
        "asset_name": step.asset_name,
        "asset_dir": metadata.get("asset_dir"),
        "target_date": metadata.get("target_date"),
        "quality": analysis["quality"],
        "repair_candidate_count": len(analysis["repair_candidates"]),
        "repair_candidates": analysis["repair_candidates"],
    }


def _record_step_report(
    report: dict[str, Any],
    *,
    step: Step,
    result: subprocess.CompletedProcess,
) -> None:
    report.setdefault("steps", []).append(
        {
            "phase": step.phase,
            "label": step.label,
            "asset_name": step.asset_name,
            "returncode": int(result.returncode),
            "command": step.command,
        }
    )
    if step.phase == "refresh":
        _record_refresh_report(report, step=step)
    elif step.phase == "inspect":
        _record_inspect_report(report, step=step)


def _write_workflow_report(
    path: Path,
    *,
    report: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    report.setdefault("workflow", {})["finished_at"] = datetime.now().isoformat(timespec="seconds")
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_patch_refresh_steps(
    args: argparse.Namespace,
    *,
    asset_name: str,
    command_name: str,
    current_path: Path,
    refreshed_path: Path,
    by_date_file: Path,
    floor_start_date: str,
) -> list[Step]:
    patch_start_date = _resolve_patch_start_date(
        args,
        asset_name=asset_name,
        current_path=current_path,
        floor_start_date=floor_start_date,
    )
    patch_dir = _patch_snapshot_path(refreshed_path)
    mirror_command = _rqdata_command(
        args,
        command_name,
        "--by-date-file",
        _repo_relative(by_date_file),
        "--start-date",
        patch_start_date,
        "--end-date",
        args.target_date,
        "--name",
        patch_dir.name,
    )
    if args.resume:
        mirror_command.append("--resume")
    merge_command = [
        sys.executable,
        "-m",
        "csml.research.hk_asset_patch_merge",
        "--base-dir",
        _repo_relative(current_path),
        "--patch-dir",
        _repo_relative(patch_dir),
        "--out-dir",
        _repo_relative(refreshed_path),
        "--overwrite",
    ]
    display_name = asset_name.replace("_", " ")
    return [
        Step(
            phase="refresh",
            label=f"Mirror HK {display_name} patch window",
            command=mirror_command,
            asset_name=asset_name,
            report_metadata={
                "action": "patch_fetch",
                "mode": "patch",
                "base_path": current_path,
                "patch_path": patch_dir,
                "refreshed_path": refreshed_path,
                "start_date": patch_start_date,
                "end_date": args.target_date,
                "lookback_days": _patch_lookback_days(args, asset_name=asset_name),
            },
        ),
        Step(
            phase="refresh",
            label=f"Merge HK {display_name} patch into refreshed snapshot",
            command=merge_command,
            alias_target=refreshed_path,
            alias_link=current_path,
            asset_name=asset_name,
            report_metadata={
                "action": "patch_merge",
                "mode": "patch",
                "refreshed_path": refreshed_path,
                "alias_path": current_path,
            },
        ),
    ]


def _planned_bundle(
    current: SnapshotBundle,
    refreshed: SnapshotBundle,
    *,
    selected_refresh_assets: tuple[str, ...],
) -> SnapshotBundle:
    payload = current.__dict__.copy()
    mapping = {
        "instruments": "instruments_file",
        "daily": "daily_dir",
        "daily_clean": "daily_clean_dir",
        "valuation": "valuation_dir",
        "ex_factors": "ex_factors_dir",
        "dividends": "dividends_dir",
        "shares": "shares_dir",
        "industry_changes": "industry_changes_dir",
        "southbound": "southbound_dir",
    }
    for asset_name in selected_refresh_assets:
        field_name = mapping.get(asset_name)
        if field_name is not None:
            payload[field_name] = getattr(refreshed, field_name)
    return SnapshotBundle(**payload)


def _forward_rqdata_credentials(args: argparse.Namespace) -> list[str]:
    forwarded: list[str] = []
    if args.config:
        forwarded.extend(["--config", args.config])
    if args.username:
        forwarded.extend(["--username", args.username])
    if args.password:
        forwarded.extend(["--password", args.password])
    return forwarded


def _rqdata_command(args: argparse.Namespace, *rest: str) -> list[str]:
    return [*_csml_executable(), "rqdata", *rest, *_forward_rqdata_credentials(args)]


def _build_refresh_steps(
    args: argparse.Namespace,
    *,
    current: SnapshotBundle,
    refreshed: SnapshotBundle,
) -> list[Step]:
    selected = _selected_refresh_assets(args)
    steps: list[Step] = []
    patch_mode = args.refresh_mode == "patch"

    if "instruments" in selected:
        steps.append(
            Step(
                phase="refresh",
                label="Export HK instruments",
                command=_rqdata_command(
                    args,
                    "export-hk-instruments",
                    "--by-date-file",
                    _repo_relative(args.universe_by_date),
                    "--out",
                    _repo_relative(refreshed.instruments_file),
                    "--force",
                ),
                alias_target=refreshed.instruments_file,
                alias_link=current.instruments_file,
                asset_name="instruments",
                report_metadata={
                    "action": "export",
                    "mode": "full",
                    "refreshed_path": refreshed.instruments_file,
                    "alias_path": current.instruments_file,
                },
            )
        )

    if "daily" in selected:
        if patch_mode:
            steps.extend(
                _build_patch_refresh_steps(
                    args,
                    asset_name="daily",
                    command_name="mirror-hk-daily",
                    current_path=current.daily_dir,
                    refreshed_path=refreshed.daily_dir,
                    by_date_file=args.universe_by_date,
                    floor_start_date=args.start_date,
                )
            )
        else:
            command = _rqdata_command(
                args,
                "mirror-hk-daily",
                "--by-date-file",
                _repo_relative(args.universe_by_date),
                "--start-date",
                args.start_date,
                "--end-date",
                args.target_date,
                "--name",
                refreshed.daily_dir.name,
            )
            if args.resume:
                command.append("--resume")
            steps.append(
                Step(
                    phase="refresh",
                    label="Mirror HK daily",
                    command=command,
                    alias_target=refreshed.daily_dir,
                    alias_link=current.daily_dir,
                    asset_name="daily",
                    report_metadata={
                        "action": "full_refresh",
                        "mode": "full",
                        "refreshed_path": refreshed.daily_dir,
                        "alias_path": current.daily_dir,
                        "start_date": args.start_date,
                        "end_date": args.target_date,
                    },
                )
            )

    if "daily_clean" in selected:
        steps.append(
            Step(
                phase="refresh",
                label="Build HK daily clean layer",
                command=[
                    *_csml_executable(),
                    "rqdata",
                    "build-hk-daily-clean-layer",
                    "--asset-dir",
                    _repo_relative(refreshed.daily_dir if "daily" in selected else current.daily_dir),
                    "--out-dir",
                    _repo_relative(refreshed.daily_clean_dir),
                    "--overwrite",
                ],
                alias_target=refreshed.daily_clean_dir,
                alias_link=current.daily_clean_dir,
            )
        )

    dated_assets = (
        ("valuation", "mirror-hk-valuation", refreshed.valuation_dir, current.valuation_dir),
        ("ex_factors", "mirror-hk-ex-factors", refreshed.ex_factors_dir, current.ex_factors_dir),
        ("dividends", "mirror-hk-dividends", refreshed.dividends_dir, current.dividends_dir),
        ("shares", "mirror-hk-shares", refreshed.shares_dir, current.shares_dir),
        (
            "industry_changes",
            "mirror-hk-industry-changes",
            refreshed.industry_changes_dir,
            current.industry_changes_dir,
        ),
    )
    for asset_name, command_name, refreshed_path, alias_link in dated_assets:
        if asset_name not in selected:
            continue
        if patch_mode and asset_name in PATCH_MERGE_SUPPORTED_ASSETS:
            steps.extend(
                _build_patch_refresh_steps(
                    args,
                    asset_name=asset_name,
                    command_name=command_name,
                    current_path=alias_link,
                    refreshed_path=refreshed_path,
                    by_date_file=args.universe_by_date,
                    floor_start_date=args.start_date,
                )
            )
            continue
        command = _rqdata_command(
            args,
            command_name,
            "--by-date-file",
            _repo_relative(args.universe_by_date),
            "--start-date",
            args.start_date,
            "--end-date",
            args.target_date,
            "--name",
            refreshed_path.name,
        )
        if args.resume:
            command.append("--resume")
        steps.append(
            Step(
                phase="refresh",
                label=f"Mirror HK {asset_name}",
                command=command,
                alias_target=refreshed_path,
                alias_link=alias_link,
                asset_name=asset_name,
                report_metadata={
                    "action": "full_refresh",
                    "mode": "full",
                    "refreshed_path": refreshed_path,
                    "alias_path": alias_link,
                    "start_date": args.start_date,
                    "end_date": args.target_date,
                },
            )
        )

    if "southbound" in selected:
        command = _rqdata_command(
            args,
            "mirror-hk-southbound",
            "--by-date-file",
            _repo_relative(args.southbound_by_date),
            "--start-date",
            args.southbound_start_date,
            "--end-date",
            args.target_date,
            "--trading-type",
            "both",
            "--name",
            refreshed.southbound_dir.name,
        )
        if args.resume:
            command.append("--resume")
        steps.append(
            Step(
                phase="refresh",
                label="Mirror HK southbound",
                command=command,
                alias_target=refreshed.southbound_dir,
                alias_link=current.southbound_dir,
                asset_name="southbound",
                report_metadata={
                    "action": "full_refresh",
                    "mode": "full",
                    "refreshed_path": refreshed.southbound_dir,
                    "alias_path": current.southbound_dir,
                    "start_date": args.southbound_start_date,
                    "end_date": args.target_date,
                },
            )
        )

    return steps


def _inspect_report_name(asset_name: str, target_date: str) -> str:
    if asset_name == "valuation":
        return f"hk_valuation_health_{target_date}_with_daily_ref.json"
    return f"hk_{asset_name}_health_{target_date}_full_history.json"


def _build_inspect_steps(
    args: argparse.Namespace,
    *,
    bundle: SnapshotBundle,
) -> list[Step]:
    selected = _selected_inspect_assets(args)
    steps: list[Step] = []
    mapping = {
        "daily": bundle.daily_dir,
        "daily_clean": bundle.daily_clean_dir,
        "valuation": bundle.valuation_dir,
        "ex_factors": bundle.ex_factors_dir,
        "dividends": bundle.dividends_dir,
        "shares": bundle.shares_dir,
        "industry_changes": bundle.industry_changes_dir,
        "southbound": bundle.southbound_dir,
    }
    for asset_name in selected:
        report_path = args.reports_dir / _inspect_report_name(asset_name, args.target_date)
        command = [
            *_csml_executable(),
            "rqdata",
            "inspect-hk-asset-health",
            "--asset-dir",
            _repo_relative(mapping[asset_name]),
            "--target-date",
            args.target_date,
            "--format",
            "json",
            "--out",
            _repo_relative(report_path),
            "--fail-on-severity",
            args.inspect_fail_on_severity,
        ]
        if not args.skip_history:
            command.append("--include-history")
        if asset_name == "valuation":
            command.extend(["--daily-asset-dir", _repo_relative(bundle.daily_clean_dir)])
        steps.append(
            Step(
                phase="inspect",
                label=f"Inspect HK {asset_name} asset health",
                command=command,
                summary_path=report_path,
                asset_name=asset_name,
                report_metadata={
                    "asset_dir": str(mapping[asset_name]),
                    "target_date": args.target_date,
                },
            )
        )
    return steps


def _build_package_step(
    args: argparse.Namespace,
    *,
    bundle: SnapshotBundle,
) -> Step:
    command = [
        sys.executable,
        "-m",
        "csml.release_tools.package_assets",
        "--preset",
        args.preset,
        "--dest",
        _repo_relative(args.package_dest),
        "--name",
        args.distribution_name,
        "--as-of",
        args.target_date,
        "--overwrite",
        "--daily-snapshot",
        _repo_relative(bundle.daily_dir),
        "--valuation-snapshot",
        _repo_relative(bundle.valuation_dir),
        "--instruments-file",
        _repo_relative(bundle.instruments_file),
        "--ex-factors-snapshot",
        _repo_relative(bundle.ex_factors_dir),
        "--dividends-snapshot",
        _repo_relative(bundle.dividends_dir),
        "--shares-snapshot",
        _repo_relative(bundle.shares_dir),
        "--southbound-snapshot",
        _repo_relative(bundle.southbound_dir),
        "--industry-changes-snapshot",
        _repo_relative(bundle.industry_changes_dir),
        "--universe-by-date",
        _repo_relative(bundle.universe_by_date),
        "--universe-symbols",
        _repo_relative(bundle.universe_symbols),
    ]
    if bundle.universe_meta is not None:
        command.extend(["--universe-meta", _repo_relative(bundle.universe_meta)])
    if bundle.pit_dir is not None:
        command.extend(["--pit-snapshot", _repo_relative(bundle.pit_dir)])
    if bundle.exchange_rate_dir is not None:
        command.extend(["--exchange-rate-snapshot", _repo_relative(bundle.exchange_rate_dir)])
    if bundle.financial_details_dir is not None:
        command.extend(["--financial-details-snapshot", _repo_relative(bundle.financial_details_dir)])
    for part_name in _selected_parts(args):
        command.extend(["--part", part_name])
    return Step(phase="package", label="Stage HK asset release parts", command=command)


def _build_release_step(args: argparse.Namespace) -> Step:
    command = [
        sys.executable,
        "-m",
        "csml.release_tools.release_assets",
        "--staged-root",
        _repo_relative(args.package_dest),
        "--tar-dir",
        _repo_relative(args.tar_dir),
    ]
    for part_name in _selected_parts(args):
        command.extend(["--part", part_name])
    if args.repo:
        command.extend(["--repo", args.repo])
    if args.tag:
        command.extend(["--tag", args.tag])
    if args.title:
        command.extend(["--title", args.title])
    if args.prerelease:
        command.append("--prerelease")
    if args.draft:
        command.append("--draft")
    if args.latest:
        command.append("--latest")
    if args.clobber:
        command.append("--clobber")
    return Step(phase="release", label="Create or update GitHub Release", command=command)


def _summarize_report(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    checks = payload.get("quality_checks") or []
    severity_counts = {"error": 0, "warning": 0, "info": 0}
    for item in checks:
        severity = str(item.get("severity") or "").lower()
        if severity in severity_counts:
            severity_counts[severity] += 1
    summary = payload.get("summary") or {}
    return (
        f"errors={severity_counts['error']} "
        f"warnings={severity_counts['warning']} "
        f"info={severity_counts['info']} "
        f"history_issues={summary.get('history_issue_count', 0)} "
        f"report={_repo_relative(path)}"
    )


def _maybe_repoint_alias(step: Step, *, dry_run: bool, repoint_latest: bool) -> None:
    if dry_run or not repoint_latest:
        return
    if step.alias_target is None or step.alias_link is None:
        return
    if not step.alias_target.exists():
        raise SystemExit(f"Expected refreshed output not found: {step.alias_target}")
    create_relative_symlink(step.alias_target, step.alias_link)
    print(f"  repointed latest alias: {_repo_relative(step.alias_link)} -> {step.alias_target.name}")


def _update_active_bundle(
    bundle: SnapshotBundle,
    step: Step,
) -> SnapshotBundle:
    if step.alias_target is None:
        return bundle
    replacements = {
        bundle.instruments_file: ("instruments_file", step.alias_target),
        bundle.daily_dir: ("daily_dir", step.alias_target),
        bundle.daily_clean_dir: ("daily_clean_dir", step.alias_target),
        bundle.valuation_dir: ("valuation_dir", step.alias_target),
        bundle.ex_factors_dir: ("ex_factors_dir", step.alias_target),
        bundle.dividends_dir: ("dividends_dir", step.alias_target),
        bundle.shares_dir: ("shares_dir", step.alias_target),
        bundle.industry_changes_dir: ("industry_changes_dir", step.alias_target),
        bundle.southbound_dir: ("southbound_dir", step.alias_target),
    }
    if step.alias_link not in replacements:
        return bundle
    field_name, value = replacements[step.alias_link]
    payload = bundle.__dict__.copy()
    payload[field_name] = value
    return SnapshotBundle(**payload)


def _default_package_dest(target_date: str) -> Path:
    return RELEASES_ROOT / f"hk_rqdata_assets_{target_date}" / "staged"


def _default_tar_dir(target_date: str) -> Path:
    return RELEASES_ROOT / f"hk_rqdata_assets_{target_date}" / "tarballs"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Thin maintainer workflow for HK RQData refresh, inspect, package, and release.",
    )
    parser.add_argument(
        "--phase",
        action="append",
        choices=["refresh", "inspect", "package", "release"],
        default=[],
        help="Workflow phase to run. Repeatable. Default: refresh, inspect, package.",
    )
    parser.add_argument("--target-date", required=True, help="Target date in YYYYMMDD or YYYY-MM-DD.")
    parser.add_argument("--config", help="Optional config path or alias forwarded to RQData commands.")
    parser.add_argument("--username", help="Optional RQData username override.")
    parser.add_argument("--password", help="Optional RQData password override.")
    parser.add_argument("--resume", action="store_true", help="Pass --resume to mirror commands.")
    parser.add_argument(
        "--refresh-mode",
        choices=["full", "patch"],
        default="full",
        help=(
            "Refresh strategy for supported assets. "
            "'full' re-mirrors the whole date range; "
            "'patch' only re-fetches a tail window then merges it into a refreshed snapshot. "
            "Default: full."
        ),
    )
    parser.add_argument(
        "--daily-patch-lookback-days",
        type=int,
        default=DEFAULT_DAILY_PATCH_LOOKBACK_DAYS,
        help=(
            "Calendar-day overlap to re-fetch before the current daily asset end date when "
            "--refresh-mode=patch. Default: 20."
        ),
    )
    parser.add_argument(
        "--dated-patch-lookback-days",
        type=int,
        default=DEFAULT_DATED_PATCH_LOOKBACK_DAYS,
        help=(
            "Calendar-day overlap to re-fetch before the current dated-asset end date when "
            "--refresh-mode=patch. Applies to valuation/ex_factors/dividends/shares. Default: 40."
        ),
    )
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing them.")
    parser.add_argument(
        "--refresh-asset",
        action="append",
        choices=REFRESH_ASSETS,
        default=[],
        help="Only refresh selected asset(s). Repeatable.",
    )
    parser.add_argument(
        "--inspect-asset",
        action="append",
        choices=INSPECT_ASSETS,
        default=[],
        help="Only inspect selected asset(s). Repeatable.",
    )
    parser.add_argument(
        "--part",
        action="append",
        choices=AVAILABLE_PART_CHOICES,
        default=[],
        help="Only stage or upload selected release part(s). Repeatable.",
    )
    parser.add_argument("--start-date", default="20000101", help="Start date for dated HK mirrors.")
    parser.add_argument(
        "--southbound-start-date",
        default="20141117",
        help="Start date for southbound mirrors.",
    )
    parser.add_argument(
        "--universe-by-date",
        type=Path,
        default=ASSETS_ROOT / "universe" / "hk_all_full_by_date.csv",
        help="Universe-by-date CSV used for full-market mirrors.",
    )
    parser.add_argument(
        "--southbound-by-date",
        type=Path,
        default=ASSETS_ROOT / "universe" / "hk_connect_full_by_date.csv",
        help="Universe-by-date CSV used for southbound mirrors.",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=REPORTS_ROOT,
        help="Directory used for health report outputs.",
    )
    parser.add_argument(
        "--workflow-report",
        type=Path,
        help=(
            "Optional JSON report path for this workflow run. "
            "Default: artifacts/reports/hk_asset_refresh_<target_date>.json"
        ),
    )
    parser.add_argument(
        "--inspect-fail-on-severity",
        default="none",
        choices=["none", "info", "warning", "error"],
        help="Fail threshold forwarded to inspect-hk-asset-health. Default: none.",
    )
    parser.add_argument(
        "--skip-history",
        action="store_true",
        help="Do not add --include-history to inspect-hk-asset-health.",
    )
    parser.add_argument(
        "--no-repoint-latest",
        action="store_true",
        help="Leave generic latest symlinks untouched after refresh.",
    )
    parser.add_argument("--preset", default="hk_full", help="Preset forwarded to package_assets.")
    parser.add_argument(
        "--distribution-name",
        default="hk-full-rqdata",
        help="Distribution name used for package/release manifests.",
    )
    parser.add_argument("--package-dest", type=Path, help="Override staged package root.")
    parser.add_argument("--tar-dir", type=Path, help="Override tarball output directory.")
    parser.add_argument("--repo", help="GitHub repo in owner/name format for release upload.")
    parser.add_argument("--tag", help="Optional GitHub release tag override.")
    parser.add_argument("--title", help="Optional GitHub release title override.")
    parser.add_argument("--prerelease", action="store_true", help="Mark release as prerelease.")
    parser.add_argument("--draft", action="store_true", help="Create the GitHub release as draft.")
    parser.add_argument("--latest", action="store_true", help="Mark the GitHub release as latest.")
    parser.add_argument("--clobber", action="store_true", help="Overwrite existing release assets if needed.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.target_date = _normalize_target_date(args.target_date)
    args.start_date = _normalize_target_date(args.start_date)
    args.southbound_start_date = _normalize_target_date(args.southbound_start_date)
    if args.daily_patch_lookback_days <= 0:
        raise SystemExit("--daily-patch-lookback-days must be > 0.")
    if args.dated_patch_lookback_days <= 0:
        raise SystemExit("--dated-patch-lookback-days must be > 0.")
    args.package_dest = args.package_dest or _default_package_dest(args.target_date)
    args.tar_dir = args.tar_dir or _default_tar_dir(args.target_date)
    args.reports_dir = args.reports_dir.resolve() if args.reports_dir.is_absolute() else REPO_ROOT / args.reports_dir
    args.workflow_report = _normalize_report_path(
        args.workflow_report or _default_workflow_report_path(args.target_date),
        base_root=REPO_ROOT,
    )
    args.package_dest = (
        args.package_dest.resolve() if args.package_dest.is_absolute() else REPO_ROOT / args.package_dest
    )
    args.tar_dir = args.tar_dir.resolve() if args.tar_dir.is_absolute() else REPO_ROOT / args.tar_dir

    phases = _phase_selection(args)
    workflow_report = _init_workflow_report(args=args, phases=phases)
    current = _current_snapshot_bundle()
    refreshed = _refreshed_snapshot_bundle(args.target_date)
    selected_refresh_assets = _selected_refresh_assets(args)
    planned_bundle = _planned_bundle(
        current,
        refreshed,
        selected_refresh_assets=selected_refresh_assets,
    )
    active_bundle = current

    steps: list[Step] = []
    if "refresh" in phases:
        steps.extend(_build_refresh_steps(args, current=current, refreshed=refreshed))
    if "inspect" in phases:
        inspect_bundle = active_bundle if "refresh" not in phases else planned_bundle
        steps.extend(_build_inspect_steps(args, bundle=inspect_bundle))
    if "package" in phases:
        package_bundle = active_bundle if "refresh" not in phases else planned_bundle
        steps.append(_build_package_step(args, bundle=package_bundle))
    if "release" in phases:
        steps.append(_build_release_step(args))

    if not steps:
        print("No steps selected.")
        return 0

    if not args.dry_run:
        args.reports_dir.mkdir(parents=True, exist_ok=True)
        args.package_dest.parent.mkdir(parents=True, exist_ok=True)
        args.tar_dir.parent.mkdir(parents=True, exist_ok=True)
        if args.workflow_report is not None:
            args.workflow_report.parent.mkdir(parents=True, exist_ok=True)

    for index, step in enumerate(steps, start=1):
        print(f"==> [{index}/{len(steps)}] {step.phase}: {step.label}")
        result = _run(step.command, dry_run=args.dry_run)
        if result.returncode != 0:
            raise SystemExit(result.returncode)
        _maybe_repoint_alias(step, dry_run=args.dry_run, repoint_latest=not args.no_repoint_latest)
        active_bundle = _update_active_bundle(active_bundle, step)
        if step.summary_path is not None and not args.dry_run:
            if not step.summary_path.exists():
                raise SystemExit(f"Expected health report not found: {step.summary_path}")
            print("  " + _summarize_report(step.summary_path))
        if not args.dry_run:
            _record_step_report(workflow_report, step=step, result=result)

    if not args.dry_run and args.workflow_report is not None:
        _write_workflow_report(args.workflow_report, report=workflow_report)
        print(f"Workflow report: {_repo_relative(args.workflow_report)}")

    print(
        "Workflow complete:",
        f"phases={','.join(phases)}",
        f"target_date={args.target_date}",
        f"package_dest={_repo_relative(args.package_dest)}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
