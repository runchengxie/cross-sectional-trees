#!/usr/bin/env python3
"""Collect lightweight maintainability metrics for the repository."""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
import tomllib
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOTS = ("src", "scripts", "tests")
DEFAULT_LIMIT = 10
PUBLIC_API_PATH = Path("src/cstree/data_tools/rqdata_assets/public_api.py")
PYPROJECT_PATH = Path("pyproject.toml")


@dataclass(frozen=True)
class FileMetric:
    path: str
    lines: int
    long_lines_over_100: int


@dataclass(frozen=True)
class FunctionMetric:
    path: str
    name: str
    start_line: int
    end_line: int
    lines: int


@dataclass(frozen=True)
class Metrics:
    roots: list[str]
    python_files: int
    python_lines: int
    long_lines_over_100: int
    functions_over_100: int
    functions_over_250: int
    functions_over_500: int
    c901_file_ignores: int
    rqdata_public_api_all: int | None
    largest_files: list[FileMetric]
    largest_functions: list[FunctionMetric]

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["thresholds"] = {
            "long_line_columns": 100,
            "large_function_lines": 100,
            "very_large_function_lines": 250,
            "huge_function_lines": 500,
        }
        return payload


def _run_git_ls_files(repo_root: Path) -> set[str] | None:
    if not (repo_root / ".git").exists():
        return None
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
        ],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return {
        path
        for path in result.stdout.decode("utf-8").split("\0")
        if path
    }


def _is_included_python_path(path: Path, roots: Sequence[str]) -> bool:
    return (
        path.suffix == ".py"
        and "__pycache__" not in path.parts
        and bool(path.parts)
        and path.parts[0] in roots
    )


def discover_python_files(
    repo_root: Path = REPO_ROOT,
    roots: Sequence[str] = DEFAULT_ROOTS,
) -> list[Path]:
    tracked_paths = _run_git_ls_files(repo_root)
    if tracked_paths is not None:
        return sorted(
            repo_root / path
            for path in tracked_paths
            if _is_included_python_path(Path(path), roots)
        )

    files: list[Path] = []
    for root_name in roots:
        root = repo_root / root_name
        if root.exists():
            files.extend(
                path
                for path in root.rglob("*.py")
                if "__pycache__" not in path.parts
            )
    return sorted(files)


def _relative_path(repo_root: Path, path: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _function_metrics_for_file(repo_root: Path, path: Path, text: str) -> list[FunctionMetric]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    metrics: list[FunctionMetric] = []
    relative = _relative_path(repo_root, path)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        end_line = getattr(node, "end_lineno", None)
        if end_line is None:
            continue
        metrics.append(
            FunctionMetric(
                path=relative,
                name=node.name,
                start_line=node.lineno,
                end_line=end_line,
                lines=end_line - node.lineno + 1,
            )
        )
    return metrics


def _c901_file_ignore_count(repo_root: Path) -> int:
    pyproject_path = repo_root / PYPROJECT_PATH
    if not pyproject_path.exists():
        return 0
    config = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    per_file = config.get("tool", {}).get("ruff", {}).get("lint", {}).get("per-file-ignores", {})
    return sum(1 for values in per_file.values() if "C901" in values)


def _literal_all_count(repo_root: Path, path: Path) -> int | None:
    full_path = repo_root / path
    if not full_path.exists():
        return None
    tree = ast.parse(full_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        is_all_assignment = any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in node.targets
        )
        if not is_all_assignment:
            continue
        value = ast.literal_eval(node.value)
        if isinstance(value, (list, tuple)):
            return len(value)
    return None


def collect_metrics(
    repo_root: Path = REPO_ROOT,
    roots: Sequence[str] = DEFAULT_ROOTS,
    limit: int = DEFAULT_LIMIT,
) -> Metrics:
    files = discover_python_files(repo_root, roots)
    file_metrics: list[FileMetric] = []
    function_metrics: list[FunctionMetric] = []
    total_lines = 0
    total_long_lines = 0

    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        long_lines = sum(1 for line in lines if len(line) > 100)
        total_lines += len(lines)
        total_long_lines += long_lines
        file_metrics.append(
            FileMetric(
                path=_relative_path(repo_root, path),
                lines=len(lines),
                long_lines_over_100=long_lines,
            )
        )
        function_metrics.extend(_function_metrics_for_file(repo_root, path, text))

    largest_files = sorted(file_metrics, key=lambda item: item.lines, reverse=True)[:limit]
    largest_functions = sorted(function_metrics, key=lambda item: item.lines, reverse=True)[:limit]

    return Metrics(
        roots=list(roots),
        python_files=len(files),
        python_lines=total_lines,
        long_lines_over_100=total_long_lines,
        functions_over_100=sum(1 for item in function_metrics if item.lines > 100),
        functions_over_250=sum(1 for item in function_metrics if item.lines > 250),
        functions_over_500=sum(1 for item in function_metrics if item.lines > 500),
        c901_file_ignores=_c901_file_ignore_count(repo_root),
        rqdata_public_api_all=_literal_all_count(repo_root, PUBLIC_API_PATH),
        largest_files=largest_files,
        largest_functions=largest_functions,
    )


def format_markdown(metrics: Metrics) -> str:
    lines = [
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Python files | {metrics.python_files} |",
        f"| Python lines | {metrics.python_lines} |",
        f"| Lines over 100 chars | {metrics.long_lines_over_100} |",
        f"| Functions over 100 lines | {metrics.functions_over_100} |",
        f"| Functions over 250 lines | {metrics.functions_over_250} |",
        f"| Functions over 500 lines | {metrics.functions_over_500} |",
        f"| C901 file ignores | {metrics.c901_file_ignores} |",
    ]
    if metrics.rqdata_public_api_all is not None:
        lines.append(f"| rqdata public_api __all__ | {metrics.rqdata_public_api_all} |")

    lines.extend(["", "Largest functions:", ""])
    lines.extend([
        "| Lines | Function | Path |",
        "| ---: | --- | --- |",
    ])
    for item in metrics.largest_functions:
        lines.append(f"| {item.lines} | `{item.name}` | `{item.path}:{item.start_line}` |")
    return "\n".join(lines)


def format_text(metrics: Metrics) -> str:
    rows = [
        ("python_files", metrics.python_files),
        ("python_lines", metrics.python_lines),
        ("long_lines_over_100", metrics.long_lines_over_100),
        ("functions_over_100", metrics.functions_over_100),
        ("functions_over_250", metrics.functions_over_250),
        ("functions_over_500", metrics.functions_over_500),
        ("c901_file_ignores", metrics.c901_file_ignores),
    ]
    if metrics.rqdata_public_api_all is not None:
        rows.append(("rqdata_public_api_all", metrics.rqdata_public_api_all))

    lines = ["Maintainability metrics:"]
    lines.extend(f"- {name}: {value}" for name, value in rows)
    lines.extend(["", "Largest functions:"])
    lines.extend(
        f"- {item.lines} lines {item.path}:{item.start_line} {item.name}"
        for item in metrics.largest_functions
    )
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect static maintainability metrics for src, scripts, and tests.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON.",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Print a markdown table suitable for maintenance docs.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Number of largest files/functions to include. Default: {DEFAULT_LIMIT}.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root. Defaults to the current checkout.",
    )
    parser.add_argument(
        "--scope",
        action="append",
        choices=DEFAULT_ROOTS,
        help="Root to include. May be repeated. Defaults to src, scripts, tests.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    roots = tuple(args.scope or DEFAULT_ROOTS)
    metrics = collect_metrics(args.root.resolve(), roots, max(args.limit, 0))
    if args.json:
        json.dump(metrics.to_payload(), sys.stdout, indent=2, ensure_ascii=False)
        print()
    elif args.markdown:
        print(format_markdown(metrics))
    else:
        print(format_text(metrics))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
