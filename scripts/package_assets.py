#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ASSETS_ROOT = REPO_ROOT / "artifacts" / "assets"

PRESETS = {
    "hk_full": {
        "daily_snapshot": "hk_all_2000_20260312_daily_final_latest",
        "instruments_file": "hk_all_instruments_20260312.parquet",
        "pit_snapshot": "hk_all_2000_2025_full_market_latest",
        "universe_by_date": "hk_all_full_by_date.csv",
        "universe_symbols": "hk_all_full_symbols.txt",
        "universe_meta": "hk_all_full_by_date.meta.yml",
    },
    "hk_connect": {
        "daily_snapshot": "hk_connect_full_2000_20260311_daily_latest",
        "instruments_file": "hk_connect_full_20260312.parquet",
        "pit_snapshot": "hk_connect_full_2000_2025_full_latest",
        "universe_by_date": "hk_connect_full_by_date.csv",
        "universe_symbols": "hk_connect_full_symbols.txt",
        "universe_meta": "hk_connect_full_by_date.meta.yml",
    },
}


def resolve_repo_path(path_text: str | Path) -> Path:
    path = Path(path_text).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (REPO_ROOT / path).resolve()


def looks_like_path(value: str) -> bool:
    return "/" in value or "\\" in value or value.startswith(".") or value.startswith("~")


def resolve_snapshot_path(base: Path, value: str) -> Path:
    if looks_like_path(value):
        return resolve_repo_path(value)
    return base / value


def detect_as_of(text: str) -> str:
    match = re.search(r"(\\d{8})", text)
    if match:
        return match.group(1)
    return datetime.now().strftime("%Y%m%d")


def ensure_dest_root(dest: Path, overwrite: bool) -> None:
    if dest.exists():
        if not overwrite and any(dest.iterdir()):
            raise SystemExit(f"Destination exists and is not empty: {dest}")
        if overwrite:
            shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)


def ensure_exists(path: Path, kind: str) -> None:
    if not path.exists():
        raise SystemExit(f"{kind} not found: {path}")


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


def yaml_quote(value: str | None) -> str:
    if value is None:
        return "null"
    return f"\"{value.replace('\"', '\\\\\"')}\""


def format_manifest(
    *,
    name: str,
    as_of: str,
    mode: str,
    generated_at: str,
    source_repo: Path,
    daily_snapshot: str,
    instruments_file: str,
    pit_snapshot: str | None,
    universe_by_date: str,
    universe_symbols: str,
    universe_meta: str | None,
) -> str:
    lines = [
        "bundle:",
        f"  name: {yaml_quote(name)}",
        f"  as_of: {yaml_quote(as_of)}",
        f"  generated_at: {yaml_quote(generated_at)}",
        f"  source_repo: {yaml_quote(source_repo.as_posix())}",
        f"  mode: {yaml_quote(mode)}",
        "assets:",
        "  daily:",
        f"    snapshot: {yaml_quote(daily_snapshot)}",
        f"    path: {yaml_quote(f'rqdata/hk/daily/{daily_snapshot}')}",
        "  instruments:",
        f"    file: {yaml_quote(instruments_file)}",
        f"    path: {yaml_quote(f'rqdata/hk/instruments/{instruments_file}')}",
    ]
    if pit_snapshot:
        lines.extend(
            [
                "  pit_financials:",
                f"    snapshot: {yaml_quote(pit_snapshot)}",
                f"    path: {yaml_quote(f'rqdata/hk/pit_financials/{pit_snapshot}')}",
            ]
        )
    lines.extend(
        [
            "  universe:",
            f"    by_date: {yaml_quote(universe_by_date)}",
            f"    symbols: {yaml_quote(universe_symbols)}",
        ]
    )
    if universe_meta:
        lines.append(f"    meta: {yaml_quote(universe_meta)}")
    lines.append(f"    path: {yaml_quote('universe/')}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Package assets into a portable bundle for sharing.",
    )
    parser.add_argument("--preset", choices=sorted(PRESETS.keys()), default="hk_full")
    parser.add_argument("--name", default=None, help="Bundle name for manifest.")
    parser.add_argument("--dest", default=None, help="Destination directory.")
    parser.add_argument("--mode", choices=["copy", "symlink"], default="copy")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite destination.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-pit", action="store_true", help="Skip PIT assets.")
    parser.add_argument("--as-of", dest="as_of", default=None)
    parser.add_argument("--daily-snapshot", default=None)
    parser.add_argument("--instruments-file", default=None)
    parser.add_argument("--pit-snapshot", default=None)
    parser.add_argument("--universe-by-date", default=None)
    parser.add_argument("--universe-symbols", default=None)
    parser.add_argument("--universe-meta", default=None)
    args = parser.parse_args()

    preset = PRESETS[args.preset]
    daily_snapshot = args.daily_snapshot or preset["daily_snapshot"]
    instruments_file = args.instruments_file or preset["instruments_file"]
    pit_snapshot = None if args.no_pit else (args.pit_snapshot or preset["pit_snapshot"])
    universe_by_date = args.universe_by_date or preset["universe_by_date"]
    universe_symbols = args.universe_symbols or preset["universe_symbols"]
    universe_meta = args.universe_meta if args.universe_meta is not None else preset["universe_meta"]

    as_of = args.as_of or detect_as_of(daily_snapshot)
    bundle_name = args.name or args.preset

    dest = resolve_repo_path(
        args.dest
        or (REPO_ROOT.parent / "csml_assets" / f"{bundle_name}_{as_of}")
    )

    daily_dir = resolve_snapshot_path(
        ASSETS_ROOT / "rqdata" / "hk" / "daily",
        daily_snapshot,
    )
    instruments_path = resolve_snapshot_path(
        ASSETS_ROOT / "rqdata" / "hk" / "instruments",
        instruments_file,
    )
    pit_dir = None
    if pit_snapshot:
        pit_dir = resolve_snapshot_path(
            ASSETS_ROOT / "rqdata" / "hk" / "pit_financials",
            pit_snapshot,
        )
    universe_root = ASSETS_ROOT / "universe"
    universe_by_date_path = resolve_snapshot_path(universe_root, universe_by_date)
    universe_symbols_path = resolve_snapshot_path(universe_root, universe_symbols)
    universe_meta_path = None
    if universe_meta:
        universe_meta_path = resolve_snapshot_path(universe_root, universe_meta)

    ensure_exists(daily_dir, "Daily snapshot directory")
    ensure_exists(instruments_path, "Instruments file")
    if pit_dir:
        ensure_exists(pit_dir, "PIT snapshot directory")
    ensure_exists(universe_by_date_path, "Universe by-date file")
    ensure_exists(universe_symbols_path, "Universe symbols file")
    if universe_meta_path and not universe_meta_path.exists():
        universe_meta_path = None

    ensure_dest_root(dest, args.overwrite)

    actions = [
        ("daily", daily_dir, dest / "rqdata" / "hk" / "daily" / daily_dir.name),
        (
            "instruments",
            instruments_path,
            dest / "rqdata" / "hk" / "instruments" / instruments_path.name,
        ),
        (
            "universe_by_date",
            universe_by_date_path,
            dest / "universe" / universe_by_date_path.name,
        ),
        (
            "universe_symbols",
            universe_symbols_path,
            dest / "universe" / universe_symbols_path.name,
        ),
    ]
    if pit_dir:
        actions.append(
            ("pit_financials", pit_dir, dest / "rqdata" / "hk" / "pit_financials" / pit_dir.name)
        )
    if universe_meta_path:
        actions.append(
            ("universe_meta", universe_meta_path, dest / "universe" / universe_meta_path.name)
        )

    for label, src, out in actions:
        if src.is_dir():
            copy_dir(src, out, args.mode, args.dry_run)
        else:
            copy_file(src, out, args.mode, args.dry_run)

    if not args.dry_run:
        try:
            create_relative_symlink(
                dest / "rqdata" / "hk" / "daily" / daily_dir.name,
                dest / "rqdata" / "hk" / "daily" / "latest",
            )
            create_relative_symlink(
                dest / "rqdata" / "hk" / "instruments" / instruments_path.name,
                dest / "rqdata" / "hk" / "instruments" / "latest.parquet",
            )
            create_relative_symlink(
                dest / "universe" / universe_by_date_path.name,
                dest / "universe" / "latest_by_date.csv",
            )
            create_relative_symlink(
                dest / "universe" / universe_symbols_path.name,
                dest / "universe" / "latest_symbols.txt",
            )
            if universe_meta_path:
                create_relative_symlink(
                    dest / "universe" / universe_meta_path.name,
                    dest / "universe" / "latest_meta.yml",
                )
            if pit_dir:
                create_relative_symlink(
                    dest / "rqdata" / "hk" / "pit_financials" / pit_dir.name,
                    dest / "rqdata" / "hk" / "pit_financials" / "latest",
                )
        except OSError as exc:
            print(f"Warning: could not create latest symlinks ({exc})", file=sys.stderr)

    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    manifest_text = format_manifest(
        name=bundle_name,
        as_of=as_of,
        mode=args.mode,
        generated_at=generated_at,
        source_repo=REPO_ROOT,
        daily_snapshot=daily_dir.name,
        instruments_file=instruments_path.name,
        pit_snapshot=pit_dir.name if pit_dir else None,
        universe_by_date=universe_by_date_path.name,
        universe_symbols=universe_symbols_path.name,
        universe_meta=universe_meta_path.name if universe_meta_path else None,
    )
    if not args.dry_run:
        (dest / "manifest.yml").write_text(manifest_text, encoding="utf-8")

    print(f"Bundle created at: {dest}")
    print(f"Manifest: {dest / 'manifest.yml'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
