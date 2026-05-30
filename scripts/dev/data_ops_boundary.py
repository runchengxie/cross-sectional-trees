#!/usr/bin/env python3
"""Validate that shared market-data operations stay in market-data-platform."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_DOC = Path("docs/internal/data-ops-boundary-inventory.md")


@dataclass(frozen=True)
class BoundaryEntry:
    path: str
    classification: str
    owner: str
    replacement: str
    reason: str
    required_tokens: tuple[str, ...] = ()


BOUNDARY_ENTRIES: tuple[BoundaryEntry, ...] = (
    BoundaryEntry(
        "src/cstree/artifacts.py",
        "compat-wrapper",
        "market-data-platform",
        "market_data_platform.artifacts",
        "Shared artifact path constants are platform-owned.",
        ("load_market_data_platform_module", "artifacts"),
    ),
    BoundaryEntry(
        "src/cstree/current_assets.py",
        "compat-wrapper",
        "market-data-platform",
        "market_data_platform.current_assets",
        "Current contract helpers are platform-owned.",
        ("load_market_data_platform_module", "current_assets"),
    ),
    BoundaryEntry(
        "src/cstree/data_provider_contracts.py",
        "compat-wrapper",
        "market-data-platform",
        "market_data_platform.data_provider_contracts",
        "Provider contract definitions are shared platform APIs.",
        ("load_market_data_platform_module", "data_provider_contracts"),
    ),
    BoundaryEntry(
        "src/cstree/data_providers.py",
        "compat-wrapper",
        "market-data-platform",
        "market_data_platform.data_providers",
        "Provider adapters and local asset readers are shared platform APIs.",
        ("load_market_data_platform_module", "data_providers"),
    ),
    BoundaryEntry(
        "src/cstree/data_tools/backup_data.py",
        "compat-wrapper",
        "market-data-platform",
        "marketdata backup-data",
        "Data snapshot implementation is platform-owned.",
        ("load_market_data_platform_module", "backup_data"),
    ),
    BoundaryEntry(
        "src/cstree/data_tools/build_hk_connect_universe.py",
        "compat-wrapper",
        "market-data-platform",
        "market_data_platform.hk_assets.build_hk_connect_universe",
        "HK universe asset builders are platform-owned.",
        ("load_market_data_platform_module", "hk_assets.build_hk_connect_universe"),
    ),
    BoundaryEntry(
        "src/cstree/data_tools/build_hk_daily_asset_universe.py",
        "compat-wrapper",
        "market-data-platform",
        "market_data_platform.hk_assets.build_hk_daily_asset_universe",
        "HK universe asset builders are platform-owned.",
        ("load_market_data_platform_module", "hk_assets.build_hk_daily_asset_universe"),
    ),
    BoundaryEntry(
        "src/cstree/data_tools/data_warehouse.py",
        "compat-wrapper",
        "market-data-platform",
        "marketdata data ...",
        "Catalog, standardized materialization, and query helpers are platform-owned.",
        ("load_market_data_platform_module", "data_warehouse"),
    ),
    BoundaryEntry(
        "src/cstree/data_tools/symbols.py",
        "compat-wrapper",
        "market-data-platform",
        "market_data_platform.symbols",
        "Symbol normalization is shared platform API.",
        ("load_market_data_platform_module", "symbols"),
    ),
    BoundaryEntry(
        "src/cstree/intraday_paths.py",
        "compat-wrapper",
        "market-data-platform",
        "market_data_platform.intraday_paths",
        "Intraday asset path helpers are shared platform API.",
        ("load_market_data_platform_module", "intraday_paths"),
    ),
    BoundaryEntry(
        "src/cstree/pit_feature_stats.py",
        "compat-wrapper",
        "market-data-platform",
        "market_data_platform.pit_feature_stats",
        "PIT feature coverage utilities are shared platform API.",
        ("load_market_data_platform_module", "pit_feature_stats"),
    ),
    BoundaryEntry(
        "src/cstree/repo_paths.py",
        "compat-wrapper",
        "market-data-platform",
        "market_data_platform.repo_paths",
        "Repository path helpers are shared platform API.",
        ("load_market_data_platform_module", "repo_paths"),
    ),
    BoundaryEntry(
        "src/cstree/rqdata_runtime.py",
        "compat-wrapper",
        "market-data-platform",
        "market_data_platform.rqdata_runtime",
        "RQData runtime initialization is shared platform API.",
        ("load_market_data_platform_module", "rqdata_runtime"),
    ),
    BoundaryEntry(
        "src/cstree/cli/data.py",
        "compat-wrapper",
        "market-data-platform",
        "marketdata data ...",
        "CLI is retained as a compatibility alias for platform data helpers.",
        ("data_warehouse", "refresh_catalog", "materialize_standardized", "query_standardized"),
    ),
    BoundaryEntry(
        "src/cstree/cli/universe.py",
        "compat-wrapper",
        "market-data-platform",
        "market_data_platform.hk_assets universe builders",
        "CLI is retained as a compatibility alias for HK universe asset builders.",
        ("_run_market_data_platform_universe_builder", "compatibility wrapper"),
    ),
    BoundaryEntry(
        "src/cstree/cli/research.py",
        "compat-wrapper",
        "market-data-platform",
        "marketdata backup-data",
        "Only the backup-data subcommand delegates to platform snapshot implementation.",
        ("backup_data.main", "backup_data_tool.add_backup_data_args"),
    ),
    BoundaryEntry(
        "src/cstree/research/hk_intraday_download.py",
        "compat-wrapper",
        "market-data-platform",
        "marketdata rqdata refresh-hk-intraday",
        "Legacy module path delegates to platform intraday download implementation.",
        ("load_market_data_platform_module", "hk_assets.intraday_download"),
    ),
    BoundaryEntry(
        "src/cstree/data_interface.py",
        "research-consumer",
        "cross-sectional-trees",
        "N/A",
        "Research runtime reads platform assets or explicit provider-online inputs.",
    ),
    BoundaryEntry(
        "src/cstree/dataset.py",
        "research-consumer",
        "cross-sectional-trees",
        "N/A",
        "Research dataset construction consumes configured inputs.",
    ),
    BoundaryEntry(
        "src/cstree/pipeline/data.py",
        "research-consumer",
        "cross-sectional-trees",
        "N/A",
        "Pipeline data loading consumes configured provider or local inputs.",
    ),
    BoundaryEntry(
        "src/cstree/pipeline/dataset_sampling.py",
        "research-consumer",
        "cross-sectional-trees",
        "N/A",
        "Sampling logic operates on in-memory research datasets.",
    ),
    BoundaryEntry(
        "src/cstree/pipeline/feature_dataset.py",
        "research-consumer",
        "cross-sectional-trees",
        "N/A",
        "Feature dataset assembly consumes platform-prepared assets.",
    ),
    BoundaryEntry(
        "src/cstree/pipeline/industry_enrichment.py",
        "research-consumer",
        "cross-sectional-trees",
        "N/A",
        "Industry labels are read as research inputs.",
    ),
    BoundaryEntry(
        "src/cstree/pipeline/output_summary_metadata.py",
        "research-consumer",
        "cross-sectional-trees",
        "N/A",
        "Run provenance records consumed current contracts without refreshing them.",
    ),
    BoundaryEntry(
        "src/cstree/pipeline/output_artifacts.py",
        "research-output",
        "cross-sectional-trees",
        "N/A",
        "Writes research run artifacts such as positions, summaries, and scored outputs.",
    ),
    BoundaryEntry(
        "src/cstree/liveops/alloc_market_data.py",
        "research-consumer",
        "cross-sectional-trees",
        "N/A",
        "Live allocation reads latest market prices and lot sizes for target export.",
    ),
    BoundaryEntry(
        "src/cstree/liveops/alloc_hk_market_data.py",
        "research-consumer",
        "cross-sectional-trees",
        "N/A",
        "HK live allocation reads provider data for execution preparation.",
    ),
    BoundaryEntry(
        "src/cstree/release_tools/package_runs.py",
        "research-output",
        "cross-sectional-trees",
        "N/A",
        "Packages research runs, not reusable market data assets.",
    ),
    BoundaryEntry(
        "src/cstree/release_tools/__init__.py",
        "research-output",
        "cross-sectional-trees",
        "N/A",
        "Namespace package for research run packaging helpers.",
    ),
    BoundaryEntry(
        "src/cstree/release_tools/release_runs.py",
        "research-output",
        "cross-sectional-trees",
        "N/A",
        "Uploads research run packages, not data asset releases.",
    ),
    BoundaryEntry(
        "src/cstree/research/hk_connect_cap_weight_benchmark.py",
        "research-consumer",
        "cross-sectional-trees",
        "N/A",
        "Builds benchmark evidence from prepared daily, valuation, and universe inputs.",
    ),
    BoundaryEntry(
        "src/cstree/research/hk_financial_details.py",
        "research-consumer",
        "cross-sectional-trees",
        "N/A",
        "Analyzes prepared financial-details probes and mapping rules.",
    ),
    BoundaryEntry(
        "src/cstree/research/hk_industry_filtered_universe.py",
        "research-consumer",
        "cross-sectional-trees",
        "N/A",
        "Builds research-specific filtered universe files from prepared inputs.",
    ),
    BoundaryEntry(
        "src/cstree/research/hk_intraday_slippage_report.py",
        "research-consumer",
        "cross-sectional-trees",
        "N/A",
        "Consumes prepared intraday assets to calibrate research slippage assumptions.",
    ),
    BoundaryEntry(
        "src/cstree/research/hk_selected_provider_valuation_audit.py",
        "research-consumer",
        "cross-sectional-trees",
        "N/A",
        "Audits provider-overlay research runs and cached valuation inputs.",
    ),
    BoundaryEntry(
        "src/cstree/research/hk_selected_provider_valuation_merge.py",
        "research-consumer",
        "cross-sectional-trees",
        "N/A",
        "Research experiment helper for provider valuation overlays; does not publish assets.",
    ),
    BoundaryEntry(
        "scripts/internal/package_repo.sh",
        "repo-maintenance",
        "cross-sectional-trees",
        "N/A",
        "Packages repository source, not market data.",
    ),
    BoundaryEntry(
        "scripts/dev/data_ops_boundary.py",
        "repo-maintenance",
        "cross-sectional-trees",
        "N/A",
        "Governance check for this inventory.",
    ),
)

BOUNDARY_BY_PATH = {entry.path: entry for entry in BOUNDARY_ENTRIES}
SOURCE_ROOTS = ("src/cstree", "scripts")
PATH_KEYWORDS = (
    "rqdata",
    "data",
    "asset",
    "health",
    "download",
    "mirror",
    "current",
    "registry",
    "catalog",
    "universe",
    "backup",
    "package",
    "release",
    "provider",
    "intraday",
    "pit",
    "valuation",
    "financial",
    "industry",
    "warehouse",
    "symbols",
    "artifacts",
    "repo_paths",
)
PLATFORM_IMPL_IMPORT_RE = re.compile(
    r"(?:from|import)\s+market_data_platform\."
    r"(hk_assets|hk_depth|release_tools|registry|contract)\b"
)
DOC_TARGETS = (
    "README.md",
    "AGENTS.md",
    "scripts/README.md",
    "docs/*.md",
    "docs/concepts/*.md",
    "docs/playbooks/*.md",
    "docs/rqdata/*.md",
    "docs/internal/*.md",
)
STALE_DOC_PHRASES = (
    "HK 资产健康检查脚本",
    "HK 资产维护 Driver",
    "本仓库提供 HK 数据资产维护",
)


def _run_git_ls_files(repo_root: Path) -> set[str] | None:
    if not repo_root.joinpath(".git").exists():
        return None
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z"],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return {path for path in result.stdout.decode("utf-8").split("\0") if path}


def tracked_paths(repo_root: Path = REPO_ROOT) -> set[str]:
    git_paths = _run_git_ls_files(repo_root)
    if git_paths is not None:
        return git_paths
    return {
        path.relative_to(repo_root).as_posix()
        for path in repo_root.rglob("*")
        if path.is_file()
        and ".git" not in path.parts
        and "__pycache__" not in path.parts
        and "artifacts" not in path.parts
    }


def _is_source_path(path: str) -> bool:
    return any(path == root or path.startswith(f"{root}/") for root in SOURCE_ROOTS)


def _is_boundary_candidate(path: str) -> bool:
    if not _is_source_path(path):
        return False
    name = Path(path).as_posix().lower()
    return any(keyword in name for keyword in PATH_KEYWORDS)


def _read_text(repo_root: Path, relative_path: str) -> str:
    return repo_root.joinpath(relative_path).read_text(encoding="utf-8", errors="ignore")


def source_boundary_issues(repo_root: Path = REPO_ROOT) -> list[str]:
    paths = tracked_paths(repo_root)
    issues: list[str] = []
    missing_inventory = sorted(
        path for path in paths if _is_boundary_candidate(path) and path not in BOUNDARY_BY_PATH
    )
    for path in missing_inventory:
        issues.append(f"{path}: data-ops-sensitive source path is missing boundary inventory")

    for entry in BOUNDARY_ENTRIES:
        if entry.path not in paths:
            issues.append(f"{entry.path}: boundary inventory path is not tracked")
            continue
        text = _read_text(repo_root, entry.path)
        for token in entry.required_tokens:
            if token not in text:
                issues.append(f"{entry.path}: missing wrapper evidence token {token!r}")
        if entry.classification != "compat-wrapper" and PLATFORM_IMPL_IMPORT_RE.search(text):
            issues.append(
                f"{entry.path}: non-wrapper source must not import platform implementation modules"
            )
    return issues


def _doc_paths(repo_root: Path) -> list[str]:
    paths: set[str] = set()
    for pattern in DOC_TARGETS:
        paths.update(path.relative_to(repo_root).as_posix() for path in repo_root.glob(pattern))
    return sorted(path for path in paths if repo_root.joinpath(path).is_file())


def documentation_issues(repo_root: Path = REPO_ROOT) -> list[str]:
    issues: list[str] = []
    for path in _doc_paths(repo_root):
        text = _read_text(repo_root, path)
        for phrase in STALE_DOC_PHRASES:
            if phrase in text:
                issues.append(f"{path}: stale research-owned data operations phrase: {phrase}")
        if "cstree rqdata" in text and "market-data-platform" not in text:
            issues.append(f"{path}: cstree rqdata references must point to market-data-platform")
    return issues


def inventory_doc_issues(repo_root: Path = REPO_ROOT) -> list[str]:
    path = repo_root / INVENTORY_DOC
    if not path.exists():
        return [f"{INVENTORY_DOC.as_posix()}: missing boundary inventory document"]
    text = path.read_text(encoding="utf-8")
    issues = []
    for entry in BOUNDARY_ENTRIES:
        if f"`{entry.path}`" not in text:
            issues.append(f"{INVENTORY_DOC.as_posix()}: missing entry for {entry.path}")
    return issues


def build_report(repo_root: Path = REPO_ROOT) -> dict[str, object]:
    entries = [asdict(entry) for entry in BOUNDARY_ENTRIES]
    issues = [
        *source_boundary_issues(repo_root),
        *documentation_issues(repo_root),
        *inventory_doc_issues(repo_root),
    ]
    return {
        "inventory_doc": INVENTORY_DOC.as_posix(),
        "entries": entries,
        "issues": issues,
    }


def format_text(report: dict[str, object]) -> str:
    lines = [f"Data operations boundary inventory: {report['inventory_doc']}"]
    issues = report["issues"]
    if isinstance(issues, Sequence) and issues:
        lines.append("Issues:")
        lines.extend(f"- {issue}" for issue in issues)
    else:
        lines.append("Boundary issues: 0")
    lines.extend(["", "Classified surfaces:"])
    for entry in report["entries"]:
        if not isinstance(entry, dict):
            continue
        lines.append("- {path}: {classification} ({owner}) -> {replacement}".format(**entry))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate cross-sectional-trees market-data operations ownership.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--check", action="store_true", help="Fail if boundary issues exist.")
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root. Defaults to this checkout.",
    )
    args = parser.parse_args(argv)

    report = build_report(args.root.resolve())
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(format_text(report))
    return 1 if args.check and report["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
