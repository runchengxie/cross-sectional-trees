import csv
import re
from pathlib import Path


CONFIG_REF_PATTERN = re.compile(r"configs/[A-Za-z0-9_./-]+\.yml")


def test_catalog_entries_point_to_existing_configs():
    repo_root = Path(__file__).resolve().parents[1]
    catalog_path = repo_root / "configs" / "catalog.csv"
    missing: list[str] = []

    with catalog_path.open("r", encoding="utf-8", newline="") as handle:
        rows = csv.DictReader(line for line in handle if not line.startswith("#"))
        for row in rows:
            config_name = str(row.get("config_name") or "").strip()
            if not config_name:
                continue
            if not (repo_root / "configs" / config_name).exists():
                missing.append(config_name)

    assert missing == []


def test_docs_config_references_exist():
    repo_root = Path(__file__).resolve().parents[1]
    targets = [repo_root / "README.md", *sorted((repo_root / "docs").rglob("*.md"))]
    missing: dict[str, list[str]] = {}

    for path in targets:
        refs = sorted(set(CONFIG_REF_PATTERN.findall(path.read_text(encoding="utf-8"))))
        bad = [ref for ref in refs if not (repo_root / ref).exists()]
        if bad:
            missing[path.relative_to(repo_root).as_posix()] = bad

    assert missing == {}
