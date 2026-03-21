#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = REPO_ROOT / "artifacts" / "runs"
ASSETS_ROOT = REPO_ROOT / "artifacts" / "assets"
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from csml.research_tools import summarize_runs


RUN_DIR_PATTERN = re.compile(
    r"^(?P<run_name>.+)_(?P<timestamp>\d{8}_\d{6})_(?P<config_hash>[0-9a-fA-F]{8})$"
)
DATETIME_PARSE_FORMATS = (
    "%Y%m%d_%H%M%S",
    "%Y%m%d",
    "%Y-%m-%d",
    "%Y%m%d%H%M%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
)
DEFAULT_INCLUDE_GLOBS = (
    "summary.json",
    "config.used.yml",
    "dropped_dates.csv",
    "positions*.csv",
    "rebalance_diff*.csv",
    "backtest_*.csv",
    "ic_*.csv",
    "quantile_returns*.csv",
    "bucket_ic*.csv",
    "feature_importance.csv",
    "walk_forward_*.csv",
    "permutation_test.csv",
)
PROFILE_CHOICES = ("light", "milestone", "full")
PATH_SUFFIXES = (".parquet", ".csv", ".yml", ".yaml", ".json", ".txt")
PROFILE_DEFAULTS = {
    "light": {
        "include_scored": False,
        "include_dataset": False,
        "include_full_run_dir": False,
    },
    "milestone": {
        "include_scored": True,
        "include_dataset": True,
        "include_full_run_dir": False,
    },
    "full": {
        "include_scored": True,
        "include_dataset": True,
        "include_full_run_dir": True,
    },
}


def resolve_repo_path(path_text: str | Path) -> Path:
    path = Path(path_text).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (REPO_ROOT / path).resolve()


def ensure_dest_root(dest: Path, overwrite: bool, *, dry_run: bool) -> None:
    if dest.exists():
        if not overwrite and any(dest.iterdir()):
            raise SystemExit(f"Destination exists and is not empty: {dest}")
        if overwrite and not dry_run:
            shutil.rmtree(dest)
    if not dry_run:
        dest.mkdir(parents=True, exist_ok=True)


def create_relative_symlink(target: Path, link: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists() or link.is_symlink():
        link.unlink()
    rel_target = os.path.relpath(target, start=link.parent)
    os.symlink(rel_target, link, target_is_directory=target.is_dir())


def copy_dir(src: Path, dest: Path, mode: str, dry_run: bool) -> None:
    if dry_run:
        return
    if mode == "symlink":
        create_relative_symlink(src, dest)
    else:
        shutil.copytree(src, dest, dirs_exist_ok=True)


def copy_file(src: Path, dest: Path, mode: str, dry_run: bool) -> None:
    if dry_run:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    if mode == "symlink":
        create_relative_symlink(src, dest)
    else:
        shutil.copy2(src, dest)


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise SystemExit(f"YAML top-level payload must be an object: {path}")
    return payload


def _load_summary(summary_path: Path) -> dict[str, Any]:
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"summary.json top-level payload must be an object: {summary_path}")
    return payload


def _get_nested(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _read_git_value(repo_root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    text = result.stdout.strip()
    return text or None


def _git_metadata(repo_root: Path) -> dict[str, Any] | None:
    commit = _read_git_value(repo_root, "rev-parse", "HEAD")
    if not commit:
        return None
    short_commit = _read_git_value(repo_root, "rev-parse", "--short", "HEAD")
    branch = _read_git_value(repo_root, "rev-parse", "--abbrev-ref", "HEAD")
    status = _read_git_value(repo_root, "status", "--short")
    return {
        "commit": commit,
        "short_commit": short_commit,
        "branch": branch,
        "is_dirty": bool(status),
    }


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in DATETIME_PARSE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _run_identity(run_dir: Path, summary: dict[str, Any]) -> tuple[str, str | None, str | None]:
    run_name = str(_get_nested(summary, "run", "name") or "").strip() or None
    run_timestamp = str(_get_nested(summary, "run", "timestamp") or "").strip() or None
    config_hash = str(_get_nested(summary, "run", "config_hash") or "").strip() or None

    match = RUN_DIR_PATTERN.match(run_dir.name)
    if match:
        run_name = run_name or match.group("run_name")
        run_timestamp = run_timestamp or match.group("timestamp")
        config_hash = config_hash or match.group("config_hash")

    return run_name or run_dir.name, run_timestamp, config_hash


def _coerce_path_value(run_dir: Path, value: Any) -> Path | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    raw = Path(text).expanduser()
    candidates: list[Path] = []
    if raw.is_absolute():
        candidates.append(raw.resolve())
    else:
        candidates.append((run_dir / raw).resolve())
        candidates.append((REPO_ROOT / raw).resolve())
        candidates.append((Path.cwd() / raw).resolve())
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists():
            return candidate
    return None


def _summary_artifact_paths(run_dir: Path, summary: dict[str, Any]) -> set[Path]:
    collected: set[Path] = set()

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key.endswith("_file"):
                    path = _coerce_path_value(run_dir, value)
                    if path is not None:
                        collected.add(path)
                    continue
                if key == "series_files" and isinstance(value, dict):
                    for item in value.values():
                        path = _coerce_path_value(run_dir, item)
                        if path is not None:
                            collected.add(path)
                    continue
                visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(summary)
    return collected


def _looks_like_path_text(text: str) -> bool:
    return (
        "/" in text
        or "\\" in text
        or text.startswith(".")
        or text.startswith("~")
        or text.startswith("artifacts/")
        or text.endswith(PATH_SUFFIXES)
    )


def _iter_local_paths(run_dir: Path, node: Any) -> set[Path]:
    collected: set[Path] = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, str):
            if not _looks_like_path_text(value):
                return
            path = _coerce_path_value(run_dir, value)
            if path is not None:
                collected.add(path)

    visit(node)
    return collected


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _infer_asset_manifest(path: Path) -> Path | None:
    if not path.exists():
        return None
    if path.name == "manifest.yml" or path.name.endswith(".manifest.yml"):
        return path
    if path.is_dir():
        candidate = path / "manifest.yml"
        if candidate.exists():
            return candidate
    else:
        candidate = path.with_name(f"{path.stem}.manifest.yml")
        if candidate.exists():
            return candidate

    current = path if path.is_dir() else path.parent
    assets_root = ASSETS_ROOT.resolve()
    while True:
        candidate = current / "manifest.yml"
        if candidate.exists():
            return candidate
        if current == assets_root or current.parent == current:
            break
        current = current.parent
    return None


def _manifest_release_tag(payload: dict[str, Any]) -> str | None:
    for keys in (
        ("release_tag",),
        ("tag",),
        ("release", "tag"),
        ("github", "release_tag"),
        ("distribution", "tag"),
        ("distribution", "release_tag"),
    ):
        value = _get_nested(payload, *keys)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _build_asset_reference(
    *,
    kind: str,
    path: Path,
    referenced_paths: set[Path],
) -> dict[str, Any]:
    reference = {
        "kind": kind,
        "path": str(path),
        "sha256": _sha256_file(path),
        "referenced_paths": [str(item) for item in sorted(referenced_paths)],
    }
    if kind == "manifest":
        payload = _load_yaml_mapping(path)
        release_tag = _manifest_release_tag(payload)
        if payload.get("dataset") is not None:
            reference["dataset"] = payload.get("dataset")
        if payload.get("source_asset_dir") is not None:
            reference["source_asset_dir"] = str(payload.get("source_asset_dir"))
        if payload.get("source_manifest") is not None:
            reference["source_manifest"] = str(payload.get("source_manifest"))
        if release_tag is not None:
            reference["release_tag"] = release_tag
    return reference


def _merge_asset_references(groups: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for references in groups:
        for reference in references:
            key = (str(reference["kind"]), str(reference["path"]))
            existing = merged.get(key)
            if existing is None:
                merged[key] = {
                    **reference,
                    "referenced_paths": list(reference.get("referenced_paths") or []),
                }
                continue
            existing_paths = set(existing.get("referenced_paths") or [])
            existing_paths.update(reference.get("referenced_paths") or [])
            existing["referenced_paths"] = sorted(existing_paths)
    return [merged[key] for key in sorted(merged)]


def _collect_asset_references(run_dir: Path, summary: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    assets_root = ASSETS_ROOT.resolve()
    candidates = _iter_local_paths(run_dir, summary)
    candidates.update(_iter_local_paths(run_dir, config))

    grouped: dict[tuple[str, Path], set[Path]] = {}
    for candidate in sorted(candidates):
        if not _is_relative_to(candidate, assets_root):
            continue
        manifest_path = _infer_asset_manifest(candidate)
        if manifest_path is not None:
            key = ("manifest", manifest_path.resolve())
        else:
            if not candidate.is_file():
                continue
            key = ("file", candidate.resolve())
        grouped.setdefault(key, set()).add(candidate.resolve())

    references = [
        _build_asset_reference(kind=kind, path=path, referenced_paths=referenced_paths)
        for (kind, path), referenced_paths in sorted(grouped.items(), key=lambda item: (item[0][0], str(item[0][1])))
    ]
    return references


def _iter_candidate_runs(runs_roots: list[Path]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for root in runs_roots:
        if not root.exists():
            continue
        if not root.is_dir():
            continue
        for summary_path in sorted(root.rglob("summary.json")):
            run_dir = summary_path.parent.resolve()
            if run_dir in seen:
                continue
            seen.add(run_dir)
            summary = _load_summary(summary_path)
            config = _load_yaml_mapping(run_dir / "config.used.yml")
            run_name, run_timestamp, config_hash = _run_identity(run_dir, summary)
            run_dt = _parse_datetime(run_timestamp)
            if run_dt is None:
                run_dt = datetime.fromtimestamp(summary_path.stat().st_mtime)
            items.append(
                {
                    "run_dir": run_dir,
                    "summary_path": summary_path.resolve(),
                    "summary": summary,
                    "config": config,
                    "run_name": run_name,
                    "run_timestamp": run_timestamp,
                    "config_hash": config_hash,
                    "sort_dt": run_dt,
                }
            )
    items.sort(key=lambda item: item["sort_dt"], reverse=True)
    return items


def _apply_run_filters(candidates: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    selected = list(candidates)

    if args.run:
        indexed: dict[str, list[dict[str, Any]]] = {}
        by_path: dict[Path, dict[str, Any]] = {}
        for item in selected:
            indexed.setdefault(item["run_dir"].name, []).append(item)
            by_path[item["run_dir"]] = item

        explicit: list[dict[str, Any]] = []
        seen: set[Path] = set()
        for raw in args.run:
            candidate_path = Path(raw).expanduser()
            if not candidate_path.is_absolute():
                candidate_path = (Path.cwd() / candidate_path).resolve()
            else:
                candidate_path = candidate_path.resolve()
            if candidate_path in by_path:
                if candidate_path not in seen:
                    explicit.append(by_path[candidate_path])
                    seen.add(candidate_path)
                continue

            matches = indexed.get(Path(raw).name, [])
            if not matches:
                raise SystemExit(f"Run not found under current selection roots: {raw}")
            if len(matches) > 1:
                raise SystemExit(f"Run name is ambiguous across runs roots: {raw}")
            item = matches[0]
            if item["run_dir"] not in seen:
                explicit.append(item)
                seen.add(item["run_dir"])
        selected = explicit

    prefixes = list(dict.fromkeys(args.run_name_prefix or []))
    if prefixes:
        selected = [
            item for item in selected if any(str(item["run_name"]).startswith(prefix) for prefix in prefixes)
        ]

    since_dt = _parse_datetime(args.since) if args.since else None
    if since_dt is not None:
        selected = [item for item in selected if item["sort_dt"] >= since_dt]

    if args.latest_n is not None:
        if int(args.latest_n) <= 0:
            raise SystemExit("--latest-n must be a positive integer.")
        selected = selected[: int(args.latest_n)]

    if not selected:
        raise SystemExit("No runs matched current packaging filters.")
    return selected


def _gather_relative_files(
    run_dir: Path,
    summary: dict[str, Any],
    *,
    include_scored: bool,
    include_dataset: bool,
    include_full_run_dir: bool,
    extra_globs: list[str],
) -> list[Path]:
    if include_full_run_dir:
        return sorted(path.relative_to(run_dir) for path in run_dir.rglob("*") if path.is_file())

    collected: set[Path] = set()
    for pattern in [*DEFAULT_INCLUDE_GLOBS, *extra_globs]:
        for path in run_dir.glob(pattern):
            if path.is_file():
                collected.add(path.resolve())

    for path in _summary_artifact_paths(run_dir, summary):
        try:
            path.relative_to(run_dir)
        except ValueError:
            continue
        if path.name == "eval_scored.parquet" and not include_scored:
            continue
        if path.name == "dataset.parquet" and not include_dataset:
            continue
        if path.is_file():
            collected.add(path.resolve())

    if include_scored:
        scored_path = _coerce_path_value(run_dir, _get_nested(summary, "eval", "scored_file"))
        if scored_path is None:
            scored_path = (run_dir / "eval_scored.parquet").resolve()
        if scored_path.exists() and scored_path.is_file():
            collected.add(scored_path)

    if include_dataset:
        dataset_path = _coerce_path_value(run_dir, _get_nested(summary, "dataset", "file"))
        if dataset_path is None:
            dataset_path = (run_dir / "dataset.parquet").resolve()
        if dataset_path.exists() and dataset_path.is_file():
            collected.add(dataset_path)

    rel_paths = sorted(path.relative_to(run_dir) for path in collected)
    if not rel_paths:
        raise SystemExit(f"No files selected for run: {run_dir}")
    return rel_paths


def _copy_selected_files(
    run_dir: Path,
    rel_paths: list[Path],
    part_dir: Path,
    *,
    mode: str,
    dry_run: bool,
) -> None:
    for rel_path in rel_paths:
        src = run_dir / rel_path
        dest = part_dir / rel_path
        if src.is_dir():
            copy_dir(src, dest, mode, dry_run)
        else:
            copy_file(src, dest, mode, dry_run)


def _describe_selected_files(run_dir: Path, rel_paths: list[Path]) -> tuple[int, int]:
    file_count = 0
    total_bytes = 0
    for rel_path in rel_paths:
        path = run_dir / rel_path
        if not path.is_file():
            continue
        file_count += 1
        total_bytes += int(path.stat().st_size)
    return file_count, total_bytes


def _resolve_profile_options(args: argparse.Namespace) -> dict[str, Any]:
    defaults = PROFILE_DEFAULTS[args.profile]
    include_full_run_dir = bool(defaults["include_full_run_dir"] or args.include_full_run_dir)
    include_scored = bool(include_full_run_dir or defaults["include_scored"] or args.include_scored)
    include_dataset = bool(include_full_run_dir or defaults["include_dataset"] or args.include_dataset)
    return {
        "profile": args.profile,
        "include_scored": include_scored,
        "include_dataset": include_dataset,
        "include_full_run_dir": include_full_run_dir,
    }


def _run_snapshot(summary: dict[str, Any]) -> dict[str, Any]:
    backtest_enabled = bool(_get_nested(summary, "backtest", "enabled"))
    backtest_stats = _get_nested(summary, "backtest", "stats")
    return {
        "market": _get_nested(summary, "data", "market"),
        "data_provider": _get_nested(summary, "data", "provider"),
        "eval_ic_mean": _get_nested(summary, "eval", "ic", "mean"),
        "eval_long_short": _get_nested(summary, "eval", "long_short"),
        "backtest_sharpe": _get_nested(summary, "backtest", "stats", "sharpe"),
        "backtest_total_return": _get_nested(summary, "backtest", "stats", "total_return"),
        "status": "ok" if backtest_enabled and isinstance(backtest_stats, dict) else "no_backtest",
    }


def _build_root_manifest(
    *,
    name: str,
    created_at: str,
    mode: str,
    profile_options: dict[str, Any],
    git: dict[str, Any] | None,
    asset_references: list[dict[str, Any]],
    runs_roots: list[Path],
    args: argparse.Namespace,
    selected_runs: list[dict[str, Any]],
    run_payloads: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    manifest = {
        "distribution": {
            "name": name,
            "created_at": created_at,
            "source_repo": str(REPO_ROOT),
            "mode": mode,
            "profile": profile_options["profile"],
            "include_scored": profile_options["include_scored"],
            "include_dataset": profile_options["include_dataset"],
            "include_full_run_dir": profile_options["include_full_run_dir"],
        },
        "selection": {
            "runs_roots": [str(path) for path in runs_roots],
            "run": list(args.run or []),
            "run_name_prefix": list(args.run_name_prefix or []),
            "since": args.since,
            "latest_n": args.latest_n,
            "profile": args.profile,
            "profile_overrides": {
                "include_scored": bool(args.include_scored),
                "include_dataset": bool(args.include_dataset),
                "include_full_run_dir": bool(args.include_full_run_dir),
            },
            "include_glob": list(args.include_glob or []),
        },
        "reproducibility": {
            "asset_references": asset_references,
        },
        "runs": run_payloads,
        "totals": {
            "runs": len(selected_runs),
            "files": sum(int(item["totals"]["files"]) for item in run_payloads.values()),
            "bytes": sum(int(item["totals"]["bytes"]) for item in run_payloads.values()),
        },
    }
    if git:
        manifest["git"] = git
    return manifest


def _build_run_manifest(
    *,
    name: str,
    created_at: str,
    mode: str,
    profile_options: dict[str, Any],
    git: dict[str, Any] | None,
    asset_references: list[dict[str, Any]],
    item: dict[str, Any],
    rel_paths: list[Path],
    file_count: int,
    total_bytes: int,
) -> dict[str, Any]:
    manifest = {
        "distribution": {
            "name": name,
            "created_at": created_at,
            "source_repo": str(REPO_ROOT),
            "mode": mode,
            "profile": profile_options["profile"],
        },
        "reproducibility": {
            "asset_references": asset_references,
        },
        "run": {
            "run_dir_name": item["run_dir"].name,
            "run_name": item["run_name"],
            "run_timestamp": item["run_timestamp"],
            "config_hash": item["config_hash"],
            "source_dir": str(item["run_dir"]),
            "files": [path.as_posix() for path in rel_paths],
            "totals": {
                "files": file_count,
                "bytes": total_bytes,
            },
            "summary": _run_snapshot(item["summary"]),
        },
    }
    if git:
        manifest["git"] = git
    return manifest


def _write_runs_summary(staged_root: Path, *, dry_run: bool) -> None:
    if dry_run:
        return
    summarize_runs.main(
        [
            "--runs-dir",
            str(staged_root),
            "--output",
            str(staged_root / "runs_summary.csv"),
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage historical run artifacts into per-run release parts.",
    )
    parser.add_argument(
        "--runs-dir",
        action="append",
        default=[],
        help="Runs root to scan. Repeatable. Default: artifacts/runs",
    )
    parser.add_argument(
        "--run",
        action="append",
        default=[],
        help="Specific run directory path or basename to include. Repeatable.",
    )
    parser.add_argument(
        "--run-name-prefix",
        action="append",
        default=[],
        help="Only include runs whose run_name starts with this prefix. Repeatable.",
    )
    parser.add_argument("--since", default=None, help="Only include runs on/after this timestamp/date.")
    parser.add_argument("--latest-n", type=int, default=None, help="Keep only the latest N runs after filtering.")
    parser.add_argument("--name", default="runs_history", help="Distribution name used in manifests and tarballs.")
    parser.add_argument("--dest", default=None, help="Destination staging root.")
    parser.add_argument("--mode", choices=["copy", "symlink"], default="copy")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite destination.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--profile",
        choices=PROFILE_CHOICES,
        default="light",
        help="Packaging profile: light (default curated files), milestone (curated files + scored/dataset), full (full run dir).",
    )
    parser.add_argument(
        "--include-scored",
        action="store_true",
        help="Add eval_scored.parquet on top of the selected profile when available.",
    )
    parser.add_argument(
        "--include-dataset",
        action="store_true",
        help="Add dataset.parquet on top of the selected profile when available.",
    )
    parser.add_argument(
        "--include-full-run-dir",
        action="store_true",
        help="Add the full run directory on top of the selected profile.",
    )
    parser.add_argument(
        "--include-glob",
        action="append",
        default=[],
        help="Extra file glob relative to each run dir. Repeatable.",
    )
    args = parser.parse_args(argv)

    created_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    created_label = datetime.now().strftime("%Y%m%d_%H%M%S")
    runs_roots = [resolve_repo_path(path) for path in (args.runs_dir or [RUNS_ROOT])]
    candidates = _iter_candidate_runs(runs_roots)
    if not candidates:
        targets = ", ".join(str(path) for path in runs_roots)
        raise SystemExit(f"No summary.json files found under: {targets}")
    selected_runs = _apply_run_filters(candidates, args)
    profile_options = _resolve_profile_options(args)
    git = _git_metadata(REPO_ROOT)

    dest = resolve_repo_path(
        args.dest or (REPO_ROOT.parent / "csml_run_parts" / f"{args.name}_{created_label}")
    )
    ensure_dest_root(dest, args.overwrite, dry_run=args.dry_run)

    run_payloads: dict[str, dict[str, Any]] = {}
    run_asset_references: list[list[dict[str, Any]]] = []
    for item in selected_runs:
        run_dir = item["run_dir"]
        asset_references = _collect_asset_references(run_dir, item["summary"], item["config"])
        rel_paths = _gather_relative_files(
            run_dir,
            item["summary"],
            include_scored=profile_options["include_scored"],
            include_dataset=profile_options["include_dataset"],
            include_full_run_dir=profile_options["include_full_run_dir"],
            extra_globs=list(args.include_glob or []),
        )
        file_count, total_bytes = _describe_selected_files(run_dir, rel_paths)
        part_dir = dest / run_dir.name
        if not args.dry_run:
            part_dir.mkdir(parents=True, exist_ok=True)
        _copy_selected_files(run_dir, rel_paths, part_dir, mode=args.mode, dry_run=args.dry_run)
        if not args.dry_run:
            _write_yaml(
                part_dir / "manifest.yml",
                _build_run_manifest(
                    name=args.name,
                    created_at=created_at,
                    mode=args.mode,
                    profile_options=profile_options,
                    git=git,
                    asset_references=asset_references,
                    item=item,
                    rel_paths=rel_paths,
                    file_count=file_count,
                    total_bytes=total_bytes,
                ),
            )
        run_payloads[run_dir.name] = {
            "path": run_dir.name,
            "run_name": item["run_name"],
            "run_timestamp": item["run_timestamp"],
            "config_hash": item["config_hash"],
            "source_dir": str(run_dir),
            "files": [path.as_posix() for path in rel_paths],
            "totals": {"files": file_count, "bytes": total_bytes},
            "summary": _run_snapshot(item["summary"]),
            "reproducibility": {
                "asset_references": asset_references,
            },
        }
        run_asset_references.append(asset_references)

    if not args.dry_run:
        _write_yaml(
            dest / "manifest.yml",
            _build_root_manifest(
                name=args.name,
                created_at=created_at,
                mode=args.mode,
                profile_options=profile_options,
                git=git,
                asset_references=_merge_asset_references(run_asset_references),
                runs_roots=runs_roots,
                args=args,
                selected_runs=selected_runs,
                run_payloads=run_payloads,
            ),
        )
        _write_runs_summary(dest, dry_run=args.dry_run)

    print(f"Staged run parts at: {dest}")
    for item in selected_runs:
        print(f"Run {item['run_dir'].name}: {dest / item['run_dir'].name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
