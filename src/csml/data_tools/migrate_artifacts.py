from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from pathlib import Path

from ..artifacts import LEGACY_ARTIFACT_PATHS


@dataclass(frozen=True)
class MigrationEntry:
    source: Path
    target: Path
    kind: str
    file_count: int
    total_bytes: int


def _describe_path(path: Path) -> tuple[str, int, int]:
    if path.is_file():
        return "file", 1, int(path.stat().st_size)
    if path.is_dir():
        files = [child for child in path.rglob("*") if child.is_file()]
        return "directory", len(files), sum(int(child.stat().st_size) for child in files)
    raise SystemExit(f"Unsupported path type: {path}")


def _transfer_file(source: Path, target: Path, *, move: bool, force: bool) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.is_dir():
            raise SystemExit(f"Target exists as a directory: {target}")
        if not force:
            raise SystemExit(f"Refusing to overwrite existing file: {target}")
        target.unlink()
    if move:
        shutil.move(str(source), str(target))
    else:
        shutil.copy2(source, target)


def _find_conflicts(source: Path, target: Path) -> list[Path]:
    if source.is_file():
        return [target] if target.exists() else []
    if not source.is_dir():
        raise SystemExit(f"Unsupported path type: {source}")
    if not target.exists():
        return []
    if not target.is_dir():
        return [target]
    conflicts: list[Path] = []
    for child in source.rglob("*"):
        if not child.is_file():
            continue
        destination = target / child.relative_to(source)
        if destination.exists():
            conflicts.append(destination)
    return conflicts


def _cleanup_moved_tree(source: Path) -> None:
    directories = sorted(
        [child for child in source.rglob("*") if child.is_dir()],
        key=lambda item: len(item.parts),
        reverse=True,
    )
    for directory in directories:
        try:
            directory.rmdir()
        except OSError:
            continue
    try:
        source.rmdir()
    except OSError:
        pass


def _prune_empty_legacy_parents(path: Path, *, stop: Path) -> None:
    current = path
    while current != stop and current.exists():
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def _transfer_path(source: Path, target: Path, *, move: bool, force: bool) -> None:
    if source.is_file():
        _transfer_file(source, target, move=move, force=force)
        return
    if not source.is_dir():
        raise SystemExit(f"Unsupported path type: {source}")
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        if move:
            shutil.move(str(source), str(target))
        else:
            shutil.copytree(source, target)
        return
    if not target.is_dir():
        raise SystemExit(f"Target exists as a file: {target}")
    for child in sorted([item for item in source.rglob("*") if item.is_file()]):
        relative = child.relative_to(source)
        _transfer_file(child, target / relative, move=move, force=force)
    if move:
        _cleanup_moved_tree(source)


def add_migrate_artifacts_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Copy legacy paths into artifacts/ instead of moving them.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite conflicting files under artifacts/.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without changing files.",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="csml migrate-artifacts",
        description="One-time migration for old cache/out/data_mirror paths into the artifacts/ layout.",
    )
    add_migrate_artifacts_args(parser)
    args = parser.parse_args(argv)

    repo_root = Path.cwd().resolve()
    entries: list[MigrationEntry] = []

    for legacy_relative, artifact_relative in LEGACY_ARTIFACT_PATHS:
        source = repo_root / legacy_relative
        if not source.exists():
            continue
        target = repo_root / artifact_relative
        kind, file_count, total_bytes = _describe_path(source)
        entries.append(
            MigrationEntry(
                source=source,
                target=target,
                kind=kind,
                file_count=file_count,
                total_bytes=total_bytes,
            )
        )

    if not entries:
        print("No legacy artifact paths found.")
        return 0

    if not args.dry_run and not args.force:
        conflicts: list[Path] = []
        for entry in entries:
            conflicts.extend(_find_conflicts(entry.source, entry.target))
        if conflicts:
            unique_conflicts = sorted({path for path in conflicts})
            rendered = "\n".join(
                f"- {path.relative_to(repo_root)}" for path in unique_conflicts[:20]
            )
            suffix = ""
            if len(unique_conflicts) > 20:
                suffix = f"\n... and {len(unique_conflicts) - 20} more"
            raise SystemExit(
                "Refusing to overwrite existing artifact targets:\n"
                f"{rendered}{suffix}\nUse --force to overwrite."
            )

    action = "COPY" if args.copy else "MOVE"
    for entry in entries:
        print(
            f"{action} {entry.source.relative_to(repo_root)} -> "
            f"{entry.target.relative_to(repo_root)} "
            f"({entry.file_count} files, {entry.total_bytes} bytes)"
        )
        if args.dry_run:
            continue
        _transfer_path(
            entry.source,
            entry.target,
            move=not args.copy,
            force=bool(args.force),
        )
        if not args.copy:
            _prune_empty_legacy_parents(entry.source.parent, stop=repo_root)

    migrated_bytes = sum(entry.total_bytes for entry in entries)
    migrated_files = sum(entry.file_count for entry in entries)
    verb = "copied" if args.copy else "moved"
    print(
        f"{verb.capitalize()} {len(entries)} paths "
        f"({migrated_files} files, {migrated_bytes} bytes)."
    )
    return 0
