#!/usr/bin/env python3
"""Validate that Ruff C901 file ignores are documented in the debt inventory."""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
INVENTORY_PATH = REPO_ROOT / "docs" / "internal" / "maintenance-debt-inventory.md"
REGISTRY_HEADER = (
    "| File / module | Owner area | Reason | Validation command | Exit condition |"
)
REGISTRY_ROW_PATTERN = re.compile(r"^\| `([^`]+)` \|")


def load_c901_ignore_paths(pyproject_path: Path = PYPROJECT_PATH) -> set[str]:
    config = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    per_file = config["tool"]["ruff"]["lint"].get("per-file-ignores", {})
    return {
        path
        for path, values in per_file.items()
        if "C901" in values
    }


def load_registry_paths(inventory_path: Path = INVENTORY_PATH) -> set[str]:
    registry_paths: set[str] = set()
    for line in inventory_path.read_text(encoding="utf-8").splitlines():
        match = REGISTRY_ROW_PATTERN.match(line)
        if match:
            registry_paths.add(match.group(1))
    return registry_paths


def missing_registry_entries(
    c901_paths: set[str],
    registry_paths: set[str],
) -> list[str]:
    return sorted(c901_paths - registry_paths)


def validate_registry(
    pyproject_path: Path = PYPROJECT_PATH,
    inventory_path: Path = INVENTORY_PATH,
) -> list[str]:
    inventory_text = inventory_path.read_text(encoding="utf-8")
    errors: list[str] = []
    if REGISTRY_HEADER not in inventory_text:
        errors.append(f"Missing C901 registry header in {inventory_path}")

    c901_paths = load_c901_ignore_paths(pyproject_path)
    registry_paths = load_registry_paths(inventory_path)
    missing = missing_registry_entries(c901_paths, registry_paths)
    if missing:
        errors.append(
            "C901 ignores missing from maintenance debt inventory: "
            + ", ".join(missing)
        )
    return errors


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate documented C901 debt inventory coverage.",
    )
    parser.add_argument("--quiet", action="store_true", help="Only print failures.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    errors = validate_registry()
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    if not args.quiet:
        count = len(load_c901_ignore_paths())
        print(f"C901 debt registry covers {count} file-level ignores.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
