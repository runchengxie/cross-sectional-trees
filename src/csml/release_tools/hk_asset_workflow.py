#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

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
            )
        )

    if "daily" in selected:
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
    args.package_dest = args.package_dest or _default_package_dest(args.target_date)
    args.tar_dir = args.tar_dir or _default_tar_dir(args.target_date)
    args.reports_dir = args.reports_dir.resolve() if args.reports_dir.is_absolute() else REPO_ROOT / args.reports_dir
    args.package_dest = (
        args.package_dest.resolve() if args.package_dest.is_absolute() else REPO_ROOT / args.package_dest
    )
    args.tar_dir = args.tar_dir.resolve() if args.tar_dir.is_absolute() else REPO_ROOT / args.tar_dir

    phases = _phase_selection(args)
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

    print(
        "Workflow complete:",
        f"phases={','.join(phases)}",
        f"target_date={args.target_date}",
        f"package_dest={_repo_relative(args.package_dest)}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
