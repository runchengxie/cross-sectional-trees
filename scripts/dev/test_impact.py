#!/usr/bin/env python3
"""Recommend focused verification commands for changed repository paths."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Iterable

FAST_COMMAND = "scripts/dev/run_tests.sh fast"
LINT_COMMAND = "scripts/dev/run_tests.sh lint"

DOCS_COMMAND = (
    "uv run python -m pytest tests/test_docs_contracts.py tests/test_repo_path_references.py "
    "tests/test_run_tests_script.py -q"
)


@dataclass(frozen=True)
class ImpactRule:
    name: str
    prefixes: tuple[str, ...]
    commands: tuple[str, ...]

    def matches(self, path: str) -> bool:
        normalized = normalize_path(path)
        return any(
            normalized == prefix.rstrip("/") or normalized.startswith(prefix)
            for prefix in self.prefixes
        )


RULES: tuple[ImpactRule, ...] = (
    ImpactRule(
        name="pipeline-train-eval",
        prefixes=("src/cstree/pipeline/train_eval_stage.py",),
        commands=(
            "uv run python -m pytest tests/test_pipeline_train_eval_contracts.py "
            "tests/test_modeling.py tests/test_split.py -q",
        ),
    ),
    ImpactRule(
        name="pipeline-runner",
        prefixes=("src/cstree/pipeline/runner.py",),
        commands=(
            "uv run python -m pytest tests/test_pipeline_runtime.py "
            "tests/test_pipeline_filters_core.py -q",
        ),
    ),
    ImpactRule(
        name="pipeline-config",
        prefixes=(
            "src/cstree/pipeline/config.py",
            "src/cstree/pipeline/config_eval.py",
        ),
        commands=(
            "uv run python -m pytest tests/test_config_utils.py tests/test_pipeline_validation.py -q",
        ),
    ),
    ImpactRule(
        name="pipeline-general",
        prefixes=("src/cstree/pipeline/",),
        commands=(
            "uv run python -m pytest tests/test_pipeline_runtime.py "
            "tests/test_pipeline_filters_core.py -q",
        ),
    ),
    ImpactRule(
        name="backtest",
        prefixes=("src/cstree/backtest.py", "src/cstree/portfolio.py"),
        commands=(
            "uv run python -m pytest tests/test_metrics.py tests/test_backtest.py "
            "tests/test_backtest_reporting.py tests/test_pipeline_e2e.py -q",
        ),
    ),
    ImpactRule(
        name="liveops",
        prefixes=("src/cstree/liveops/",),
        commands=(
            "uv run python -m pytest tests/test_cli_liveops.py tests/test_alloc.py "
            "tests/test_alloc_hk.py tests/test_export_targets.py -q",
        ),
    ),
    ImpactRule(
        name="release-tools",
        prefixes=("src/cstree/release_tools/", "scripts/internal/"),
        commands=(
            "uv run python -m pytest tests/test_run_release_scripts.py -q",
        ),
    ),
    ImpactRule(
        name="docs-and-dev-scripts",
        prefixes=(
            "README.md",
            "AGENTS.md",
            "docs/",
            "scripts/README.md",
            "scripts/dev/",
            ".github/workflows/",
        ),
        commands=(DOCS_COMMAND,),
    ),
)


def normalize_path(path: str) -> str:
    value = path.strip().replace("\\", "/")
    if value.startswith("./"):
        value = value[2:]
    return PurePosixPath(value).as_posix()


def recommended_commands(paths: Iterable[str]) -> list[str]:
    commands: list[str] = []
    seen: set[str] = set()
    normalized_paths = [normalize_path(path) for path in paths if path.strip()]

    for path in normalized_paths:
        for rule in RULES:
            if rule.matches(path):
                for command in rule.commands:
                    if command not in seen:
                        seen.add(command)
                        commands.append(command)

    if not commands:
        commands.extend([FAST_COMMAND, LINT_COMMAND])
    elif LINT_COMMAND not in seen:
        commands.append(LINT_COMMAND)

    return commands


def build_payload(paths: Iterable[str]) -> dict[str, object]:
    normalized_paths = [normalize_path(path) for path in paths if path.strip()]
    return {
        "paths": normalized_paths,
        "commands": recommended_commands(normalized_paths),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recommend focused verification commands for changed paths.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Repository paths that changed.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args.paths)
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print("Recommended verification commands:")
    for command in payload["commands"]:
        print(f"- {command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
