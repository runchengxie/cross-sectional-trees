#!/usr/bin/env python3
"""Validate that market-data platform wrappers are absent from this repo."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections.abc import Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_DOC = Path("docs/internal/data-ops-boundary-inventory.md")

REMOVED_WRAPPER_PATHS: tuple[str, ...] = (
    "src/cstree/_mdp_compat.py",
    "src/cstree/artifacts.py",
    "src/cstree/current_assets.py",
    "src/cstree/data_provider_contracts.py",
    "src/cstree/data_providers.py",
    "src/cstree/data_tools/backup_data.py",
    "src/cstree/data_tools/build_hk_connect_universe.py",
    "src/cstree/data_tools/build_hk_daily_asset_universe.py",
    "src/cstree/data_tools/data_warehouse.py",
    "src/cstree/data_tools/symbols.py",
    "src/cstree/intraday_paths.py",
    "src/cstree/pit_feature_stats.py",
    "src/cstree/repo_paths.py",
    "src/cstree/rqdata_runtime.py",
    "src/cstree/cli/data.py",
    "src/cstree/cli/universe.py",
    "src/cstree/research/hk_intraday_download.py",
)

REMOVED_PLATFORM_ASSET_PATHS: tuple[str, ...] = (
    "artifacts/metadata/dataset_registry.csv",
    "configs/presets/universe/hk_all_assets.yml",
    "configs/presets/universe/hk_connect.yml",
)

RESEARCH_OWNED_PATHS: tuple[str, ...] = (
    "src/cstree/data_interface.py",
    "src/cstree/dataset.py",
    "src/cstree/pipeline/data.py",
    "src/cstree/pipeline/dataset_sampling.py",
    "src/cstree/pipeline/feature_dataset.py",
    "src/cstree/pipeline/industry_enrichment.py",
    "src/cstree/pipeline/output_summary_metadata.py",
    "src/cstree/pipeline/output_artifacts.py",
    "src/cstree/liveops/alloc_market_data.py",
    "src/cstree/liveops/alloc_hk_market_data.py",
    "src/cstree/release_tools/__init__.py",
    "src/cstree/release_tools/package_runs.py",
    "src/cstree/release_tools/release_runs.py",
    "src/cstree/research/hk_connect_cap_weight_benchmark.py",
    "src/cstree/research/hk_financial_details.py",
    "src/cstree/research/hk_industry_filtered_universe.py",
    "src/cstree/research/hk_intraday_slippage_report.py",
    "src/cstree/research/hk_selected_provider_valuation_audit.py",
    "src/cstree/research/hk_selected_provider_valuation_merge.py",
    "scripts/dev/data_ops_boundary.py",
    "scripts/internal/package_repo.sh",
)

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
FORBIDDEN_SOURCE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile("load_" + r"market_data_platform_module"),
    re.compile(r"(?:from|import)\s+cstree\."
               r"(artifacts|current_assets|data_provider_contracts|data_providers|data_tools|intraday_paths|pit_feature_stats|repo_paths|rqdata_runtime)\b"),
    re.compile(r"from\s+\.\.?\s*"
               r"(artifacts|current_assets|data_provider_contracts|data_providers|data_tools|intraday_paths|pit_feature_stats|repo_paths|rqdata_runtime)\b"),
)
DOC_TARGETS = (
    "README.md",
    "AGENTS.md",
    "scripts/README.md",
    "docs/*.md",
    "docs/concepts/*.md",
    "docs/playbooks/*.md",
    "docs/rqdata/*.md",
)
STALE_DOC_PHRASES = (
    "HK 资产健康检查脚本",
    "HK 资产维护 Driver",
    "本仓库提供 HK 数据资产维护",
    "兼容 wrapper",
    "compat wrapper",
    "cstree data",
    "cstree universe",
    "cstree backup-data",
    "python -m cstree.research.hk_intraday_download",
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
        deleted = subprocess.run(
            ["git", "-C", str(repo_root), "diff", "--name-only", "--diff-filter=D", "-z"],
            check=False,
            capture_output=True,
        )
        deleted_paths = (
            {path for path in deleted.stdout.decode("utf-8").split("\0") if path}
            if deleted.returncode == 0
            else set()
        )
        untracked = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "--others", "--exclude-standard", "-z"],
            check=False,
            capture_output=True,
        )
        untracked_paths = (
            {path for path in untracked.stdout.decode("utf-8").split("\0") if path}
            if untracked.returncode == 0
            else set()
        )
        return (git_paths - deleted_paths) | untracked_paths
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
    for path in (*REMOVED_WRAPPER_PATHS, *REMOVED_PLATFORM_ASSET_PATHS):
        if path in paths or repo_root.joinpath(path).exists():
            issues.append(f"{path}: platform wrapper or asset tail must not exist in cross-sectional-trees")

    allowed = set(RESEARCH_OWNED_PATHS) | {"scripts/README.md"}
    missing_inventory = sorted(
        path
        for path in paths
        if _is_boundary_candidate(path)
        and path not in allowed
        and path not in REMOVED_WRAPPER_PATHS
        and path not in REMOVED_PLATFORM_ASSET_PATHS
    )
    for path in missing_inventory:
        issues.append(f"{path}: data-ops-sensitive source path is missing boundary inventory")

    for path in sorted(p for p in paths if _is_source_path(p) and p.endswith(".py")):
        text = _read_text(repo_root, path)
        for pattern in FORBIDDEN_SOURCE_PATTERNS:
            if pattern.search(text):
                issues.append(f"{path}: forbidden legacy cstree data-platform wrapper reference")
                break
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
                issues.append(f"{path}: stale cross-owned data platform phrase: {phrase}")
        if "cstree rqdata" in text and "market-data-platform" not in text:
            issues.append(f"{path}: cstree rqdata references must point to market-data-platform")
    return issues


def inventory_doc_issues(repo_root: Path = REPO_ROOT) -> list[str]:
    path = repo_root / INVENTORY_DOC
    if not path.exists():
        return [f"{INVENTORY_DOC.as_posix()}: missing boundary inventory document"]
    text = path.read_text(encoding="utf-8")
    issues = []
    for removed in REMOVED_WRAPPER_PATHS:
        if f"`{removed}`" not in text or "must not exist" not in text:
            issues.append(f"{INVENTORY_DOC.as_posix()}: missing hard-cut entry for {removed}")
    for owned in RESEARCH_OWNED_PATHS:
        if f"`{owned}`" not in text:
            issues.append(f"{INVENTORY_DOC.as_posix()}: missing research-owned entry for {owned}")
    return issues


def build_report(repo_root: Path = REPO_ROOT) -> dict[str, object]:
    issues = [
        *source_boundary_issues(repo_root),
        *documentation_issues(repo_root),
        *inventory_doc_issues(repo_root),
    ]
    return {
        "inventory_doc": INVENTORY_DOC.as_posix(),
        "removed_wrappers": list(REMOVED_WRAPPER_PATHS),
        "removed_platform_asset_paths": list(REMOVED_PLATFORM_ASSET_PATHS),
        "research_owned_paths": list(RESEARCH_OWNED_PATHS),
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
    lines.extend(["", "Removed wrapper paths:"])
    removed_wrappers = report.get("removed_wrappers", ())
    if isinstance(removed_wrappers, Sequence):
        lines.extend(f"- {path}" for path in removed_wrappers)
    lines.extend(["", "Research-owned paths:"])
    research_owned_paths = report.get("research_owned_paths", ())
    if isinstance(research_owned_paths, Sequence):
        lines.extend(f"- {path}" for path in research_owned_paths)
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
