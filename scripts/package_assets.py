#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
ASSETS_ROOT = REPO_ROOT / "artifacts" / "assets"
PART_CHOICES = ("daily", "instruments", "pit", "reference", "industry", "universe")

PRESETS = {
    "hk_full": {
        "daily_snapshot": "hk_all_2000_20260312_daily_final_latest",
        "instruments_file": "hk_all_instruments_20260318.parquet",
        "pit_snapshot": "hk_all_2000_2025_full_market_latest",
        "ex_factors_snapshot": "hk_all_2000_20260318_ex_factors_full_market_latest",
        "dividends_snapshot": "hk_all_2000_20260318_dividends_full_market_latest",
        "shares_snapshot": "hk_all_2000_20260318_shares_full_market_latest",
        "industry_changes_snapshot": "hk_all_2000_20260318_industry_changes_full_market_latest",
        "universe_by_date": "hk_all_full_by_date.csv",
        "universe_symbols": "hk_all_full_symbols.txt",
        "universe_meta": "hk_all_full_by_date.meta.yml",
    },
    "hk_connect": {
        "daily_snapshot": "hk_all_2000_20260312_daily_final_latest",
        "instruments_file": "hk_connect_full_20260318.parquet",
        "pit_snapshot": "hk_connect_full_2000_2025_full_latest",
        "ex_factors_snapshot": None,
        "dividends_snapshot": None,
        "shares_snapshot": None,
        "industry_changes_snapshot": None,
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
    match = re.search(r"(\d{8})", text)
    if match:
        return match.group(1)
    return datetime.now().strftime("%Y%m%d")


def ensure_dest_root(dest: Path, overwrite: bool, *, dry_run: bool) -> None:
    if dest.exists():
        if not overwrite and any(dest.iterdir()):
            raise SystemExit(f"Destination exists and is not empty: {dest}")
        if overwrite and not dry_run:
            shutil.rmtree(dest)
    if not dry_run:
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


def _entry_kind(path: Path) -> str:
    return "directory" if path.is_dir() else "file"


def _part_entry(label: str, source: Path, target: str) -> dict:
    return {
        "label": label,
        "source": str(source),
        "target": target,
        "kind": _entry_kind(source),
    }


def _latest_link(link: str, target: str) -> dict:
    return {"link": link, "target": target}


def _resolve_assets(args: argparse.Namespace) -> dict[str, object]:
    preset = PRESETS[args.preset]
    daily_snapshot = args.daily_snapshot or preset["daily_snapshot"]
    instruments_file = args.instruments_file or preset["instruments_file"]
    pit_snapshot = None if args.no_pit else (args.pit_snapshot or preset["pit_snapshot"])
    if args.no_reference:
        ex_factors_snapshot = None
        dividends_snapshot = None
        shares_snapshot = None
    else:
        ex_factors_snapshot = args.ex_factors_snapshot or preset.get("ex_factors_snapshot")
        dividends_snapshot = args.dividends_snapshot or preset.get("dividends_snapshot")
        shares_snapshot = args.shares_snapshot or preset.get("shares_snapshot")
    industry_changes_snapshot = (
        None
        if args.no_industry
        else (args.industry_changes_snapshot or preset.get("industry_changes_snapshot"))
    )
    universe_by_date = args.universe_by_date or preset["universe_by_date"]
    universe_symbols = args.universe_symbols or preset["universe_symbols"]
    universe_meta = args.universe_meta if args.universe_meta is not None else preset["universe_meta"]

    daily_dir = resolve_snapshot_path(ASSETS_ROOT / "rqdata" / "hk" / "daily", daily_snapshot)
    instruments_path = resolve_snapshot_path(
        ASSETS_ROOT / "rqdata" / "hk" / "instruments",
        instruments_file,
    )
    pit_dir = (
        resolve_snapshot_path(ASSETS_ROOT / "rqdata" / "hk" / "pit_financials", pit_snapshot)
        if pit_snapshot
        else None
    )
    ex_factors_dir = (
        resolve_snapshot_path(ASSETS_ROOT / "rqdata" / "hk" / "ex_factors", ex_factors_snapshot)
        if ex_factors_snapshot
        else None
    )
    dividends_dir = (
        resolve_snapshot_path(ASSETS_ROOT / "rqdata" / "hk" / "dividends", dividends_snapshot)
        if dividends_snapshot
        else None
    )
    shares_dir = (
        resolve_snapshot_path(ASSETS_ROOT / "rqdata" / "hk" / "shares", shares_snapshot)
        if shares_snapshot
        else None
    )
    industry_changes_dir = (
        resolve_snapshot_path(
            ASSETS_ROOT / "rqdata" / "hk" / "industry_changes",
            industry_changes_snapshot,
        )
        if industry_changes_snapshot
        else None
    )
    universe_root = ASSETS_ROOT / "universe"
    universe_by_date_path = resolve_snapshot_path(universe_root, universe_by_date)
    universe_symbols_path = resolve_snapshot_path(universe_root, universe_symbols)
    universe_meta_path = resolve_snapshot_path(universe_root, universe_meta) if universe_meta else None

    ensure_exists(daily_dir, "Daily snapshot directory")
    ensure_exists(instruments_path, "Instruments file")
    if pit_dir:
        ensure_exists(pit_dir, "PIT snapshot directory")
    if ex_factors_dir:
        ensure_exists(ex_factors_dir, "Ex-factors snapshot directory")
    if dividends_dir:
        ensure_exists(dividends_dir, "Dividends snapshot directory")
    if shares_dir:
        ensure_exists(shares_dir, "Shares snapshot directory")
    if industry_changes_dir:
        ensure_exists(industry_changes_dir, "Industry changes snapshot directory")
    ensure_exists(universe_by_date_path, "Universe by-date file")
    ensure_exists(universe_symbols_path, "Universe symbols file")
    if universe_meta_path and not universe_meta_path.exists():
        universe_meta_path = None

    return {
        "daily_dir": daily_dir,
        "instruments_path": instruments_path,
        "pit_dir": pit_dir,
        "ex_factors_dir": ex_factors_dir,
        "dividends_dir": dividends_dir,
        "shares_dir": shares_dir,
        "industry_changes_dir": industry_changes_dir,
        "universe_by_date_path": universe_by_date_path,
        "universe_symbols_path": universe_symbols_path,
        "universe_meta_path": universe_meta_path,
    }


def _build_part_specs(resolved: dict[str, object]) -> dict[str, dict]:
    daily_dir = resolved["daily_dir"]
    instruments_path = resolved["instruments_path"]
    pit_dir = resolved["pit_dir"]
    ex_factors_dir = resolved["ex_factors_dir"]
    dividends_dir = resolved["dividends_dir"]
    shares_dir = resolved["shares_dir"]
    industry_changes_dir = resolved["industry_changes_dir"]
    universe_by_date_path = resolved["universe_by_date_path"]
    universe_symbols_path = resolved["universe_symbols_path"]
    universe_meta_path = resolved["universe_meta_path"]

    parts = {
        "daily": {
            "description": "HK daily snapshot directory.",
            "entries": [
                _part_entry(
                    "daily",
                    daily_dir,
                    f"rqdata/hk/daily/{daily_dir.name}",
                )
            ],
            "latest_links": [
                _latest_link(
                    "rqdata/hk/daily/latest",
                    f"rqdata/hk/daily/{daily_dir.name}",
                )
            ],
            "summary": {"snapshot": daily_dir.name},
        },
        "instruments": {
            "description": "HK instruments parquet.",
            "entries": [
                _part_entry(
                    "instruments",
                    instruments_path,
                    f"rqdata/hk/instruments/{instruments_path.name}",
                )
            ],
            "latest_links": [
                _latest_link(
                    "rqdata/hk/instruments/latest.parquet",
                    f"rqdata/hk/instruments/{instruments_path.name}",
                )
            ],
            "summary": {"file": instruments_path.name},
        },
        "universe": {
            "description": "Universe membership and symbol files.",
            "entries": [
                _part_entry(
                    "by_date",
                    universe_by_date_path,
                    f"universe/{universe_by_date_path.name}",
                ),
                _part_entry(
                    "symbols",
                    universe_symbols_path,
                    f"universe/{universe_symbols_path.name}",
                ),
            ],
            "latest_links": [
                _latest_link(
                    "universe/latest_by_date.csv",
                    f"universe/{universe_by_date_path.name}",
                ),
                _latest_link(
                    "universe/latest_symbols.txt",
                    f"universe/{universe_symbols_path.name}",
                ),
            ],
            "summary": {
                "by_date": universe_by_date_path.name,
                "symbols": universe_symbols_path.name,
            },
        },
    }
    if universe_meta_path:
        parts["universe"]["entries"].append(
            _part_entry(
                "meta",
                universe_meta_path,
                f"universe/{universe_meta_path.name}",
            )
        )
        parts["universe"]["latest_links"].append(
            _latest_link(
                "universe/latest_meta.yml",
                f"universe/{universe_meta_path.name}",
            )
        )
        parts["universe"]["summary"]["meta"] = universe_meta_path.name

    if pit_dir:
        parts["pit"] = {
            "description": "PIT fundamentals snapshot directory.",
            "entries": [
                _part_entry(
                    "pit_financials",
                    pit_dir,
                    f"rqdata/hk/pit_financials/{pit_dir.name}",
                )
            ],
            "latest_links": [
                _latest_link(
                    "rqdata/hk/pit_financials/latest",
                    f"rqdata/hk/pit_financials/{pit_dir.name}",
                )
            ],
            "summary": {"snapshot": pit_dir.name},
        }

    reference_entries: list[dict] = []
    reference_links: list[dict] = []
    reference_summary: dict[str, str] = {}
    if ex_factors_dir:
        reference_entries.append(
            _part_entry(
                "ex_factors",
                ex_factors_dir,
                f"rqdata/hk/ex_factors/{ex_factors_dir.name}",
            )
        )
        reference_links.append(
            _latest_link(
                "rqdata/hk/ex_factors/latest",
                f"rqdata/hk/ex_factors/{ex_factors_dir.name}",
            )
        )
        reference_summary["ex_factors_snapshot"] = ex_factors_dir.name
    if dividends_dir:
        reference_entries.append(
            _part_entry(
                "dividends",
                dividends_dir,
                f"rqdata/hk/dividends/{dividends_dir.name}",
            )
        )
        reference_links.append(
            _latest_link(
                "rqdata/hk/dividends/latest",
                f"rqdata/hk/dividends/{dividends_dir.name}",
            )
        )
        reference_summary["dividends_snapshot"] = dividends_dir.name
    if shares_dir:
        reference_entries.append(
            _part_entry(
                "shares",
                shares_dir,
                f"rqdata/hk/shares/{shares_dir.name}",
            )
        )
        reference_links.append(
            _latest_link(
                "rqdata/hk/shares/latest",
                f"rqdata/hk/shares/{shares_dir.name}",
            )
        )
        reference_summary["shares_snapshot"] = shares_dir.name
    if reference_entries:
        parts["reference"] = {
            "description": "Reference snapshots: ex-factors, dividends, shares.",
            "entries": reference_entries,
            "latest_links": reference_links,
            "summary": reference_summary,
        }

    if industry_changes_dir:
        parts["industry"] = {
            "description": "Industry changes snapshot directory.",
            "entries": [
                _part_entry(
                    "industry_changes",
                    industry_changes_dir,
                    f"rqdata/hk/industry_changes/{industry_changes_dir.name}",
                )
            ],
            "latest_links": [
                _latest_link(
                    "rqdata/hk/industry_changes/latest",
                    f"rqdata/hk/industry_changes/{industry_changes_dir.name}",
                )
            ],
            "summary": {"snapshot": industry_changes_dir.name},
        }

    return parts


def _selected_parts(requested_parts: list[str], available_parts: dict[str, dict]) -> list[str]:
    selected = list(dict.fromkeys(requested_parts or PART_CHOICES))
    missing = [part for part in selected if part not in available_parts]
    if missing:
        raise SystemExit(f"Requested parts are not available under the current preset/settings: {missing}")
    return selected


def _write_yaml(path: Path, payload: dict) -> None:
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _copy_entry_to_part(entry: dict, part_dir: Path, mode: str, dry_run: bool) -> None:
    src = Path(entry["source"])
    out = part_dir / str(entry["target"])
    if src.is_dir():
        copy_dir(src, out, mode, dry_run)
    else:
        copy_file(src, out, mode, dry_run)


def _build_root_manifest(
    *,
    name: str,
    as_of: str,
    mode: str,
    preset: str,
    generated_at: str,
    selected_parts: list[str],
    part_specs: dict[str, dict],
) -> dict:
    payload = {
        "distribution": {
            "name": name,
            "as_of": as_of,
            "generated_at": generated_at,
            "source_repo": str(REPO_ROOT),
            "mode": mode,
            "preset": preset,
        },
        "parts": {},
    }
    for part_name in selected_parts:
        spec = part_specs[part_name]
        payload["parts"][part_name] = {
            "path": part_name,
            "description": spec["description"],
            "entries": spec["entries"],
            "latest_links": spec["latest_links"],
            "summary": spec["summary"],
        }
    return payload


def _build_part_manifest(
    *,
    name: str,
    as_of: str,
    mode: str,
    preset: str,
    generated_at: str,
    part_name: str,
    spec: dict,
) -> dict:
    return {
        "distribution": {
            "name": name,
            "as_of": as_of,
            "generated_at": generated_at,
            "source_repo": str(REPO_ROOT),
            "mode": mode,
            "preset": preset,
        },
        "part": {
            "name": part_name,
            "description": spec["description"],
            "entries": spec["entries"],
            "latest_links": spec["latest_links"],
            "summary": spec["summary"],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage HK assets into multiple release parts.",
    )
    parser.add_argument("--preset", choices=sorted(PRESETS.keys()), default="hk_full")
    parser.add_argument("--name", default=None, help="Distribution name used in manifests and tarballs.")
    parser.add_argument("--dest", default=None, help="Destination staging root.")
    parser.add_argument("--mode", choices=["copy", "symlink"], default="copy")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite destination.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--part", action="append", choices=PART_CHOICES, default=[], help="Only stage selected part(s). Repeatable.")
    parser.add_argument("--no-pit", action="store_true", help="Skip PIT assets.")
    parser.add_argument("--no-reference", action="store_true", help="Skip reference assets (ex_factors/dividends/shares).")
    parser.add_argument("--as-of", dest="as_of", default=None)
    parser.add_argument("--daily-snapshot", default=None)
    parser.add_argument("--instruments-file", default=None)
    parser.add_argument("--pit-snapshot", default=None)
    parser.add_argument("--ex-factors-snapshot", default=None)
    parser.add_argument("--dividends-snapshot", default=None)
    parser.add_argument("--shares-snapshot", default=None)
    parser.add_argument("--industry-changes-snapshot", default=None)
    parser.add_argument("--universe-by-date", default=None)
    parser.add_argument("--universe-symbols", default=None)
    parser.add_argument("--universe-meta", default=None)
    parser.add_argument("--no-industry", action="store_true", help="Skip industry_changes assets.")
    args = parser.parse_args(argv)

    resolved = _resolve_assets(args)
    daily_dir = resolved["daily_dir"]
    as_of = args.as_of or detect_as_of(daily_dir.name)
    distribution_name = args.name or args.preset
    dest = resolve_repo_path(
        args.dest or (REPO_ROOT.parent / "csml_asset_parts" / f"{distribution_name}_{as_of}")
    )
    ensure_dest_root(dest, args.overwrite, dry_run=args.dry_run)

    part_specs = _build_part_specs(resolved)
    selected_parts = _selected_parts(args.part, part_specs)
    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    for part_name in selected_parts:
        spec = part_specs[part_name]
        part_dir = dest / part_name
        if not args.dry_run:
            part_dir.mkdir(parents=True, exist_ok=True)
        for entry in spec["entries"]:
            _copy_entry_to_part(entry, part_dir, args.mode, args.dry_run)
        if not args.dry_run:
            for link_spec in spec["latest_links"]:
                create_relative_symlink(
                    part_dir / str(link_spec["target"]),
                    part_dir / str(link_spec["link"]),
                )
            _write_yaml(
                part_dir / "manifest.yml",
                _build_part_manifest(
                    name=distribution_name,
                    as_of=as_of,
                    mode=args.mode,
                    preset=args.preset,
                    generated_at=generated_at,
                    part_name=part_name,
                    spec=spec,
                ),
            )

    if not args.dry_run:
        _write_yaml(
            dest / "manifest.yml",
            _build_root_manifest(
                name=distribution_name,
                as_of=as_of,
                mode=args.mode,
                preset=args.preset,
                generated_at=generated_at,
                selected_parts=selected_parts,
                part_specs=part_specs,
            ),
        )

    print(f"Staged asset parts at: {dest}")
    for part_name in selected_parts:
        print(f"Part {part_name}: {dest / part_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
