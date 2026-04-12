import csv
import re
import subprocess
from pathlib import Path

CONFIG_REF_PATTERN = re.compile(r"configs/[A-Za-z0-9_./-]+\.yml")
LOCAL_CONFIG_REF_PATTERN = re.compile(r"configs/local/[A-Za-z0-9_./-]+\.yml")


def _tracked_config_paths(repo_root: Path) -> set[str]:
    working_tree_configs = {
        path.relative_to(repo_root).as_posix() for path in (repo_root / "configs").rglob("*.yml")
    }
    if not (repo_root / ".git").exists():
        return working_tree_configs

    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z", "--", "configs"],
        check=True,
        capture_output=True,
    )
    return {path for path in result.stdout.decode("utf-8").split("\0") if path.endswith(".yml")}


def test_catalog_entries_point_to_existing_configs():
    repo_root = Path(__file__).resolve().parents[1]
    catalog_path = repo_root / "configs" / "catalog.csv"
    tracked_configs = _tracked_config_paths(repo_root)
    missing: list[str] = []

    with catalog_path.open("r", encoding="utf-8", newline="") as handle:
        rows = csv.DictReader(line for line in handle if not line.startswith("#"))
        for row in rows:
            config_name = str(row.get("config_name") or "").strip()
            if not config_name:
                continue
            if f"configs/{config_name}" not in tracked_configs:
                missing.append(config_name)

    assert missing == []


def test_docs_do_not_reference_specific_local_configs():
    repo_root = Path(__file__).resolve().parents[1]
    targets = [repo_root / "README.md", *sorted((repo_root / "docs").rglob("*.md"))]
    bad_refs: dict[str, list[str]] = {}

    for path in targets:
        refs = sorted(set(LOCAL_CONFIG_REF_PATTERN.findall(path.read_text(encoding="utf-8"))))
        if refs:
            bad_refs[path.relative_to(repo_root).as_posix()] = refs

    assert bad_refs == {}


def test_tracked_configs_do_not_live_under_configs_local():
    repo_root = Path(__file__).resolve().parents[1]
    local_configs = sorted(
        path for path in _tracked_config_paths(repo_root) if path.startswith("configs/local/")
    )

    assert local_configs == []


def test_tracked_configs_do_not_extend_local_configs():
    repo_root = Path(__file__).resolve().parents[1]
    tracked_configs = _tracked_config_paths(repo_root)
    bad_refs: dict[str, list[str]] = {}

    for config_path in tracked_configs:
        path = repo_root / config_path
        refs = sorted(set(LOCAL_CONFIG_REF_PATTERN.findall(path.read_text(encoding="utf-8"))))
        if refs:
            bad_refs[config_path] = refs

    assert bad_refs == {}


def test_docs_config_references_point_to_tracked_configs():
    repo_root = Path(__file__).resolve().parents[1]
    targets = [repo_root / "README.md", *sorted((repo_root / "docs").rglob("*.md"))]
    tracked_configs = _tracked_config_paths(repo_root)
    missing: dict[str, list[str]] = {}

    for path in targets:
        refs = sorted(set(CONFIG_REF_PATTERN.findall(path.read_text(encoding="utf-8"))))
        bad = [ref for ref in refs if ref not in tracked_configs]
        if bad:
            missing[path.relative_to(repo_root).as_posix()] = bad

    assert missing == {}
