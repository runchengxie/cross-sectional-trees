#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from csml.repo_paths import find_repo_root

REPO_ROOT = find_repo_root(__file__)
PACKAGE_MODULE = "cstree.release_tools.package_runs"
DATETIME_PARSE_FORMATS = (
    "%Y%m%d_%H%M%S",
    "%Y%m%d",
    "%Y-%m-%d",
    "%Y%m%d%H%M%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
)


def _resolve_path(path_text: str | Path) -> Path:
    path = Path(path_text).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (Path.cwd() / path).resolve()


def _run(cmd: list[str], *, dry_run: bool, capture: bool = False) -> subprocess.CompletedProcess:
    print("+", " ".join(shlex.quote(part) for part in cmd))
    if dry_run:
        return subprocess.CompletedProcess(cmd, 0, "", "")
    return subprocess.run(cmd, check=False, capture_output=capture, text=True)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", text.strip())
    return slug.strip("-") or "runs"


def _parse_staged_root(output: str) -> Path | None:
    for line in output.splitlines():
        if line.startswith("Staged run parts at:"):
            path_text = line.split(":", 1)[1].strip()
            if path_text:
                return Path(path_text).expanduser().resolve()
    return None


def _load_manifest(staged_root: Path) -> dict[str, Any]:
    manifest_path = staged_root / "manifest.yml"
    if not manifest_path.exists():
        raise SystemExit(f"Manifest not found: {manifest_path}")
    return yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}


def _manifest_distribution(manifest: dict[str, Any]) -> dict[str, Any]:
    node = manifest.get("distribution")
    return node if isinstance(node, dict) else {}


def _manifest_runs(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    node = manifest.get("runs")
    if not isinstance(node, dict):
        return {}
    return {str(key): value for key, value in node.items() if isinstance(value, dict)}


def _parse_datetime(value: Any):
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


def _selected_runs(manifest: dict[str, Any], args: argparse.Namespace) -> list[str]:
    available = _manifest_runs(manifest)
    if not available:
        raise SystemExit("No runs found in staged manifest.")

    items = []
    for key, value in available.items():
        run_name = str(value.get("run_name") or key)
        run_timestamp = value.get("run_timestamp")
        run_dt = _parse_datetime(run_timestamp)
        items.append((key, value, run_name, run_dt))
    items.sort(key=lambda item: item[3] or datetime.min, reverse=True)

    selected_keys = [key for key, _, _, _ in items]

    if args.run:
        requested = [Path(value).name for value in args.run]
        missing = [value for value in requested if value not in available]
        if missing:
            raise SystemExit(f"Requested runs are not available in staged manifest: {missing}")
        selected_keys = list(dict.fromkeys(requested))

    prefixes = list(dict.fromkeys(args.run_name_prefix or []))
    if prefixes:
        selected_keys = [
            key
            for key in selected_keys
            if any(str(available[key].get("run_name") or key).startswith(prefix) for prefix in prefixes)
        ]

    since_dt = _parse_datetime(args.since) if args.since else None
    if since_dt is not None:
        selected_keys = [
            key
            for key in selected_keys
            if (dt := _parse_datetime(available[key].get("run_timestamp"))) is not None and dt >= since_dt
        ]

    if args.latest_n is not None:
        if int(args.latest_n) <= 0:
            raise SystemExit("--latest-n must be a positive integer.")
        selected_keys = selected_keys[: int(args.latest_n)]

    if not selected_keys:
        raise SystemExit("No staged runs matched current release filters.")
    return selected_keys


def _format_readme(manifest: dict[str, Any], selected_runs: list[str]) -> str:
    distribution = _manifest_distribution(manifest)
    runs = _manifest_runs(manifest)
    name = distribution.get("name") or "runs_history"
    created_at = distribution.get("created_at") or "unknown"
    mode = distribution.get("mode") or "copy"
    profile = distribution.get("profile") or "light"
    git = manifest.get("git") if isinstance(manifest.get("git"), dict) else {}

    lines = [
        "# CSTree Run History Release Parts",
        "",
        "This release uploads historical run results as independent per-run tarballs.",
        "",
        f"Distribution: {name}",
        f"Created at: {created_at}",
        f"Mode: {mode}",
        f"Profile: {profile}",
    ]
    short_commit = git.get("short_commit") or git.get("commit")
    if short_commit:
        lines.append(f"Git: {short_commit}{' dirty' if git.get('is_dirty') else ''}")
    lines.extend(["", "Included runs:"])
    for run_dir_name in selected_runs:
        run = runs[run_dir_name]
        summary = run.get("summary")
        lines.append(
            f"- {run_dir_name}: status={summary.get('status') if isinstance(summary, dict) else 'unknown'}"
        )
        if isinstance(summary, dict):
            for key in ("market", "data_provider", "eval_ic_mean", "backtest_sharpe"):
                value = summary.get(key)
                if value is not None:
                    lines.append(f"  - {key}: {value}")
    lines.extend(
        [
            "",
            "Each uploaded tarball contains one run directory plus its manifest.yml.",
            "The staged root also includes runs_summary.csv for quick inspection.",
            "",
        ]
    )
    return "\n".join(lines)


def _format_release_notes(manifest: dict[str, Any], selected_runs: list[str], tar_paths: list[Path]) -> str:
    distribution = _manifest_distribution(manifest)
    runs = _manifest_runs(manifest)
    name = distribution.get("name") or "runs_history"
    created_at = distribution.get("created_at") or "unknown"
    profile = distribution.get("profile") or "light"
    git = manifest.get("git") if isinstance(manifest.get("git"), dict) else {}

    lines = [
        f"Distribution: {name}",
        f"Created at: {created_at}",
        f"Profile: {profile}",
    ]
    short_commit = git.get("short_commit") or git.get("commit")
    if short_commit:
        lines.append(f"Git: {short_commit}{' dirty' if git.get('is_dirty') else ''}")
    lines.extend(["", "Uploaded runs:"])
    for run_dir_name, tar_path in zip(selected_runs, tar_paths, strict=True):
        run = runs[run_dir_name]
        run_name = run.get("run_name") or run_dir_name
        run_timestamp = run.get("run_timestamp") or "unknown"
        summary = run.get("summary")
        lines.append(f"- {run_dir_name}: {tar_path.name}")
        lines.append(f"  - run_name: {run_name}")
        lines.append(f"  - run_timestamp: {run_timestamp}")
        if isinstance(summary, dict):
            for key in ("status", "market", "data_provider", "eval_ic_mean", "backtest_sharpe"):
                value = summary.get(key)
                if value is not None:
                    lines.append(f"  - {key}: {value}")
    return "\n".join(lines) + "\n"


def _ensure_gh() -> None:
    if shutil.which("gh") is None:
        raise SystemExit("GitHub CLI (gh) not found in PATH.")


def _default_tag(manifest: dict[str, Any]) -> str:
    distribution = _manifest_distribution(manifest)
    name = _slugify(str(distribution.get("name") or "runs_history"))
    created_at = str(distribution.get("created_at") or "")
    date_text = created_at[:10].replace("-", "") if len(created_at) >= 10 else "unknown"
    return f"runs-{name}-{date_text}"


def _default_title(manifest: dict[str, Any]) -> str:
    distribution = _manifest_distribution(manifest)
    name = distribution.get("name") or "runs_history"
    created_at = str(distribution.get("created_at") or "")
    date_text = created_at[:10] if len(created_at) >= 10 else "unknown"
    return f"Runs {name} {date_text}"


def _run_tar_name(manifest: dict[str, Any], run_dir_name: str) -> str:
    distribution = _manifest_distribution(manifest)
    name = _slugify(str(distribution.get("name") or "runs_history"))
    return f"runs-{name}-{run_dir_name}.tar.gz"


def _build_tar(part_dir: Path, tar_path: Path, *, dry_run: bool) -> None:
    if dry_run:
        return
    if tar_path.exists():
        tar_path.unlink()
    tar_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(part_dir, arcname=part_dir.name, recursive=True)


def _build_tars(
    *,
    staged_root: Path,
    manifest: dict[str, Any],
    selected_runs: list[str],
    tar_dir: Path,
    dry_run: bool,
) -> list[Path]:
    tar_paths: list[Path] = []
    for run_dir_name in selected_runs:
        part_dir = staged_root / run_dir_name
        if not part_dir.exists():
            raise SystemExit(f"Staged run part not found: {part_dir}")
        tar_path = tar_dir / _run_tar_name(manifest, run_dir_name)
        _build_tar(part_dir, tar_path, dry_run=dry_run)
        tar_paths.append(tar_path)
    return tar_paths


def _package_cmd_from_args(args: argparse.Namespace) -> list[str]:
    cmd = [sys.executable, "-m", PACKAGE_MODULE]
    for runs_dir in args.runs_dir or []:
        cmd.extend(["--runs-dir", runs_dir])
    for run in args.run or []:
        cmd.extend(["--run", run])
    for prefix in args.run_name_prefix or []:
        cmd.extend(["--run-name-prefix", prefix])
    if args.since:
        cmd.extend(["--since", args.since])
    if args.latest_n is not None:
        cmd.extend(["--latest-n", str(args.latest_n)])
    if args.name:
        cmd.extend(["--name", args.name])
    if args.dest:
        cmd.extend(["--dest", args.dest])
    if args.mode:
        cmd.extend(["--mode", args.mode])
    if args.overwrite:
        cmd.append("--overwrite")
    if args.profile:
        cmd.extend(["--profile", args.profile])
    if args.include_scored:
        cmd.append("--include-scored")
    if args.include_dataset:
        cmd.append("--include-dataset")
    if args.include_full_run_dir:
        cmd.append("--include-full-run-dir")
    for pattern in args.include_glob or []:
        cmd.extend(["--include-glob", pattern])
    if args.dry_run:
        cmd.append("--dry-run")
    return cmd


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage historical runs and upload multiple tarballs into one GitHub Release.",
    )
    parser.add_argument("--staged-root", help="Existing staged run-parts root to upload.")
    parser.add_argument("--tar-dir", help="Output directory for per-run tarballs.")
    parser.add_argument("--tag", help="Release tag (default derived from manifest).")
    parser.add_argument("--title", help="Release title (default derived from manifest).")
    parser.add_argument("--notes-file", help="Release notes file.")
    parser.add_argument("--draft", action="store_true", help="Create as draft.")
    parser.add_argument("--prerelease", action="store_true", help="Mark as prerelease.")
    parser.add_argument("--latest", action="store_true", help="Mark as latest.")
    parser.add_argument("--clobber", action="store_true", help="Overwrite assets if they exist.")
    parser.add_argument("--repo", help="Target repo in owner/name format.")
    parser.add_argument("--skip-package", action="store_true", help="Skip staging step.")
    parser.add_argument("--skip-upload", action="store_true", help="Skip release upload step.")
    parser.add_argument("--no-readme", action="store_true", help="Do not write release README.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--runs-dir", action="append", default=[], help="Runs root to scan when staging. Repeatable.")
    parser.add_argument("--run", action="append", default=[], help="Specific run directory path or basename. Repeatable.")
    parser.add_argument(
        "--run-name-prefix",
        action="append",
        default=[],
        help="Only include runs whose run_name starts with this prefix. Repeatable.",
    )
    parser.add_argument("--since", default=None, help="Only include runs on/after this timestamp/date.")
    parser.add_argument("--latest-n", type=int, default=None, help="Keep only the latest N runs after filtering.")
    parser.add_argument("--name", default="runs_history", help="Distribution name for the staging step.")
    parser.add_argument("--dest", default=None, help="Destination staging root for the packaging step.")
    parser.add_argument("--mode", choices=["copy", "symlink"], default="copy")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite staging destination.")
    parser.add_argument(
        "--profile",
        choices=["light", "milestone", "full"],
        default="light",
        help="Packaging profile forwarded to cstree.release_tools.package_runs.",
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

    staged_root: Path
    if args.staged_root:
        staged_root = _resolve_path(args.staged_root)
        if not staged_root.exists():
            raise SystemExit(f"Staged root not found: {staged_root}")
    else:
        if args.skip_package:
            raise SystemExit("No staged root provided and --skip-package was set.")
        package_cmd = _package_cmd_from_args(args)
        result = _run(package_cmd, dry_run=False, capture=True)
        if result.returncode != 0:
            sys.stderr.write(result.stderr or "")
            raise SystemExit(result.returncode)
        sys.stdout.write(result.stdout or "")
        if args.dry_run:
            print("Dry run complete.")
            return 0
        staged_root = _parse_staged_root(result.stdout or "")
        if staged_root is None:
            raise SystemExit("Could not detect staged root from package_runs output.")

    manifest = _load_manifest(staged_root)
    selected_runs = _selected_runs(manifest, args)

    if not args.no_readme and not args.dry_run:
        readme_path = staged_root / "README.md"
        readme_path.write_text(_format_readme(manifest, selected_runs), encoding="utf-8")

    tar_dir = (
        _resolve_path(args.tar_dir)
        if args.tar_dir
        else staged_root.parent / f"{staged_root.name}_tarballs"
    )
    if not args.dry_run:
        tar_dir.mkdir(parents=True, exist_ok=True)
    tar_paths = _build_tars(
        staged_root=staged_root,
        manifest=manifest,
        selected_runs=selected_runs,
        tar_dir=tar_dir,
        dry_run=args.dry_run,
    )

    if args.skip_upload:
        print(f"Staged root: {staged_root}")
        for tar_path in tar_paths:
            print(f"Tarball: {tar_path}")
        return 0

    _ensure_gh()
    tag = args.tag or _default_tag(manifest)
    title = args.title or _default_title(manifest)
    notes_file = args.notes_file
    if not notes_file:
        notes_path = tar_dir / f"{tag}.release_notes.txt"
        if not args.dry_run:
            notes_path.write_text(
                _format_release_notes(manifest, selected_runs, tar_paths),
                encoding="utf-8",
            )
        notes_file = str(notes_path)

    repo_args: list[str] = ["--repo", args.repo] if args.repo else []

    view_cmd = ["gh", "release", "view", tag, *repo_args]
    view_result = _run(view_cmd, dry_run=args.dry_run, capture=True)
    tar_args = [str(path) for path in tar_paths]
    if view_result.returncode == 0:
        upload_cmd = ["gh", "release", "upload", tag, *tar_args, *repo_args]
        if args.clobber:
            upload_cmd.append("--clobber")
        _run(upload_cmd, dry_run=args.dry_run)
        return 0

    create_cmd = [
        "gh",
        "release",
        "create",
        tag,
        *tar_args,
        "--title",
        title,
        "--notes-file",
        notes_file,
        *repo_args,
    ]
    if args.draft:
        create_cmd.append("--draft")
    if args.prerelease:
        create_cmd.append("--prerelease")
    if args.latest:
        create_cmd.append("--latest")
    _run(create_cmd, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
