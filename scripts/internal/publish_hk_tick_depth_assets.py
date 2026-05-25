#!/usr/bin/env python
"""Publish local HK tick-depth assets into an HK data platform root.

The raw snapshot cache is intentionally linked, not copied, by default. The
source cache is tens of GiB and still owned by rqdata-hk-depth-snapshots during
the stage-1 platform migration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from cstree.current_assets import (
    build_hk_current_contract,
    default_dataset_registry_path,
    default_hk_current_contract_path,
    write_current_contract,
    write_dataset_registry,
)


DEFAULT_START_DATE = "20250401"
DEFAULT_AS_OF = "20260522"

RAW_HEALTH_ROWS = 445_397_450
RAW_SYMBOL_COUNT = 2_810
RAW_EXPECTED_UNITS = 753_751


@dataclass(frozen=True)
class PublishPaths:
    hk_root: Path
    depth_repo: Path
    raw_source: Path
    daily_source: Path
    raw_asset: Path
    raw_alias: Path
    daily_asset: Path
    daily_alias: Path
    cost_asset: Path
    cost_alias: Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_depth_repo() -> Path:
    return _repo_root().parent / "rqdata-hk-depth-snapshots"


def _generated_at() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def _reset_dir(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _symlink_force(target: Path, link: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink() or link.is_file():
        link.unlink()
    elif link.exists():
        shutil.rmtree(link)
    link.symlink_to(target, target_is_directory=True)


def _sha256_lines(values: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(value.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _parquet_inventory(root: Path) -> tuple[int, int]:
    count = 0
    size = 0
    for path in root.rglob("*.parquet"):
        count += 1
        size += path.stat().st_size
    return count, size


def _bool_series(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series.fillna(False)
    if series.dtype == object:
        normalized = series.fillna(False)
        if normalized.map(lambda value: isinstance(value, str)).any():
            return normalized.astype(str).str.lower().isin({"1", "true", "yes", "y"})
    return series.fillna(False).astype(bool)


def _asset_paths(hk_root: Path, depth_repo: Path, start_date: str, as_of: str) -> PublishPaths:
    raw_name = f"hk_tick_depth_{start_date}_{as_of}_current"
    daily_name = f"hk_tick_depth_daily_{start_date}_{as_of}_current"
    cost_name = f"hk_execution_cost_model_{start_date}_{as_of}_baseline_v1"
    return PublishPaths(
        hk_root=hk_root,
        depth_repo=depth_repo,
        raw_source=depth_repo / "artifacts/cache/rqdata/hk_tick_depth",
        daily_source=depth_repo / "artifacts/cache/rqdata/hk_tick_depth_daily",
        raw_asset=hk_root / f"assets/rqdata/hk/tick_depth/{raw_name}",
        raw_alias=hk_root / "assets/rqdata/hk/tick_depth/hk_tick_depth_latest",
        daily_asset=hk_root / f"assets/rqdata/hk/tick_depth_daily/{daily_name}",
        daily_alias=hk_root / "assets/rqdata/hk/tick_depth_daily/hk_tick_depth_daily_latest",
        cost_asset=hk_root / f"assets/rqdata/hk/execution_cost/{cost_name}",
        cost_alias=hk_root / "assets/rqdata/hk/execution_cost/hk_execution_cost_model_latest",
    )


def _generator(depth_repo: Path) -> dict[str, str]:
    return {
        "package": "cross-sectional-trees",
        "script": "scripts/internal/publish_hk_tick_depth_assets.py",
        "source_project": str(depth_repo),
    }


def publish_raw_asset(paths: PublishPaths, *, start_date: str, as_of: str) -> dict[str, Any]:
    if not paths.raw_source.exists():
        raise FileNotFoundError(f"Raw tick-depth source not found: {paths.raw_source}")

    _reset_dir(paths.raw_asset)
    _symlink_force(paths.raw_source, paths.raw_asset / "data")
    source_dirs = sorted(path.name for path in paths.raw_source.iterdir() if path.is_dir())
    parquet_files, parquet_bytes = _parquet_inventory(paths.raw_source)
    generated_at = _generated_at()
    manifest: dict[str, Any] = {
        "dataset": "tick_depth_raw",
        "schema_version": "tick_depth_raw.v1",
        "status": "completed",
        "provider": "rqdata",
        "market": "hk",
        "frequency": "tick",
        "output_dir": str(paths.raw_asset),
        "snapshot_name": paths.raw_asset.name,
        "generated_at": generated_at,
        "generator": _generator(paths.depth_repo),
        "query": {"start_date": start_date, "end_date": as_of},
        "date_range": {"start": start_date, "end": as_of},
        "source_path": str(paths.raw_source),
        "files": ["data"],
        "storage": {
            "link_mode": "external_symlink",
            "layout": "source_batch_collection",
            "raw_layout": "symbol-date",
            "source_batch_dirs": len(source_dirs),
            "source_parquet_files": parquet_files,
            "source_bytes": parquet_bytes,
            "source_dirs_sha256": _sha256_lines(source_dirs),
        },
        "coverage": {
            "latest_confirmed_trade_date": as_of,
            "scope": (
                "HK CS symbols available to the current RQData account; "
                "ETFs excluded by provider permission."
            ),
            "symbol_count": RAW_SYMBOL_COUNT,
            "expected_symbol_date_units": RAW_EXPECTED_UNITS,
            "missing_units": 0,
            "health_rows": RAW_HEALTH_ROWS,
            "health_failures": 0,
        },
        "totals": {
            "rows": RAW_HEALTH_ROWS,
            "symbols": RAW_SYMBOL_COUNT,
            "files": parquet_files,
            "bytes": parquet_bytes,
            "source_batch_dirs": len(source_dirs),
        },
        "lineage": {
            "source_project": str(paths.depth_repo),
            "coverage_record": str(
                paths.depth_repo / "docs/records/2026-05-25-hk-depth-current-coverage.md"
            ),
        },
    }
    _write_yaml(paths.raw_asset / "manifest.yml", manifest)
    _write_json(paths.raw_asset / "meta.json", manifest)
    (paths.raw_asset / "source_dirs.txt").write_text(
        "\n".join(source_dirs) + "\n",
        encoding="utf-8",
    )
    (paths.raw_asset / "README.md").write_text(
        "# HK Tick Depth Raw Asset\n\n"
        "This platform asset exposes the current RQData HK ten-level depth snapshot cache.\n"
        "The `data` entry is an external symlink to the active "
        "`rqdata-hk-depth-snapshots` cache, avoiding a duplicate 43G raw copy during "
        "the stage-1 platform migration.\n",
        encoding="utf-8",
    )
    _symlink_force(paths.raw_asset, paths.raw_alias)
    return manifest


def _load_daily_sources(source_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    daily_files = sorted(source_root.glob("*/data.parquet"))
    if not daily_files:
        raise FileNotFoundError(f"No tick-depth daily parquet files found: {source_root}")

    frames: list[pd.DataFrame] = []
    source_rows: list[dict[str, Any]] = []
    source_names: list[str] = []
    for path in daily_files:
        frame = pd.read_parquet(path)
        source_name = path.parent.name
        source_names.append(f"{source_name}\t{path.stat().st_size}")
        source_rows.append(
            {
                "source_name": source_name,
                "path": str(path),
                "rows": int(len(frame)),
                "bytes": int(path.stat().st_size),
            }
        )
        frames.append(frame)

    return (
        pd.concat(frames, ignore_index=True),
        pd.DataFrame(source_rows).sort_values("source_name"),
        _sha256_lines(source_names),
    )


def _assert_identical_duplicate_daily_keys(frame: pd.DataFrame, key_cols: list[str]) -> int:
    duplicate_mask = frame.duplicated(key_cols, keep=False)
    if not bool(duplicate_mask.any()):
        return 0

    duplicate_frame = frame.loc[duplicate_mask].copy()
    value_cols = [column for column in frame.columns if column not in key_cols]
    row_hashes = pd.util.hash_pandas_object(duplicate_frame[value_cols], index=False)
    check_frame = duplicate_frame.loc[:, key_cols].copy()
    check_frame["_row_hash"] = row_hashes.to_numpy()
    conflicts = int(check_frame.groupby(key_cols)["_row_hash"].nunique().gt(1).sum())
    if conflicts:
        raise ValueError(f"Conflicting duplicate tick-depth daily keys: {conflicts}")
    return int(check_frame.drop_duplicates(key_cols).shape[0])


def publish_daily_asset(paths: PublishPaths) -> tuple[dict[str, Any], pd.DataFrame]:
    _reset_dir(paths.daily_asset)
    (paths.daily_asset / "data").mkdir(parents=True, exist_ok=True)
    all_daily, source_summary, source_sha256 = _load_daily_sources(paths.daily_source)

    key_cols = ["order_book_id", "trading_date"]
    duplicate_rows = int(all_daily.duplicated(key_cols, keep=False).sum())
    duplicate_keys = _assert_identical_duplicate_daily_keys(all_daily, key_cols)
    combined = (
        all_daily.drop_duplicates(key_cols, keep="first")
        .sort_values(key_cols)
        .reset_index(drop=True)
    )

    output_path = paths.daily_asset / "data/data.parquet"
    combined.to_parquet(output_path, index=False, compression="zstd")
    source_summary.to_csv(paths.daily_asset / "source_files.csv", index=False)

    fields = [str(column) for column in combined.columns]
    symbols = sorted(str(value) for value in combined["order_book_id"].dropna().astype(str).unique())
    dates = combined["trading_date"].dropna().astype(str)
    start_date = str(dates.min())
    as_of = str(dates.max())
    cost_usable = int(_bool_series(combined["is_usable_for_cost_model"]).sum())
    research_usable = int(_bool_series(combined["is_usable_for_research"]).sum())
    manifest: dict[str, Any] = {
        "dataset": "tick_depth_daily",
        "schema_version": "tick_depth_daily.v1",
        "status": "completed",
        "provider": "rqdata",
        "market": "hk",
        "frequency": "daily",
        "output_dir": str(paths.daily_asset),
        "snapshot_name": paths.daily_asset.name,
        "generated_at": _generated_at(),
        "generator": _generator(paths.depth_repo),
        "query": {"start_date": start_date, "end_date": as_of},
        "date_range": {"start": start_date, "end": as_of},
        "source_path": str(paths.daily_source),
        "files": ["data/data.parquet", "source_files.csv"],
        "fields": fields,
        "row_count": int(len(combined)),
        "symbol_count": len(symbols),
        "totals": {
            "rows": int(len(combined)),
            "symbols": len(symbols),
            "input_rows": int(len(all_daily)),
            "duplicate_rows": duplicate_rows,
            "duplicate_keys": duplicate_keys,
            "source_files": int(len(source_summary)),
            "bytes": int(output_path.stat().st_size),
        },
        "quality": {
            "dedupe_key": key_cols,
            "dedupe_note": "Duplicate source rows for the same key were value-identical.",
            "is_usable_for_research_rows": research_usable,
            "is_usable_for_cost_model_rows": cost_usable,
        },
        "lineage": {
            "raw_asset": str(paths.raw_asset),
            "source_project": str(paths.depth_repo),
            "source_files_sha256": source_sha256,
        },
    }
    _write_yaml(paths.daily_asset / "manifest.yml", manifest)
    _write_json(paths.daily_asset / "meta.json", manifest)
    (paths.daily_asset / "symbols.txt").write_text("\n".join(symbols) + "\n", encoding="utf-8")
    (paths.daily_asset / "fields.txt").write_text("\n".join(fields) + "\n", encoding="utf-8")
    _symlink_force(paths.daily_asset, paths.daily_alias)
    return manifest, combined


def publish_execution_cost_model(
    paths: PublishPaths,
    daily_manifest: dict[str, Any],
    daily_frame: pd.DataFrame,
) -> dict[str, Any]:
    _reset_dir(paths.cost_asset)
    (paths.cost_asset / "data").mkdir(parents=True, exist_ok=True)

    model_input = daily_frame[_bool_series(daily_frame["is_usable_for_cost_model"])].copy()
    if model_input.empty:
        model_input = daily_frame.copy()

    aggregate = model_input.groupby("order_book_id", dropna=True).agg(
        {
            "trading_date": ["min", "max", "count"],
            "quote_coverage_ratio": "median",
            "bad_quote_ratio": "median",
            "spread_bps_p50": "median",
            "spread_bps_p90": "median",
            "depth1_notional_p50": "median",
            "depth5_notional_p50": "median",
            "depth10_notional_p50": "median",
            "imbalance1_p50": "median",
            "imbalance5_p50": "median",
        }
    )
    aggregate.columns = [
        "sample_start_date",
        "sample_end_date",
        "usable_days",
        "quote_coverage_ratio_median",
        "bad_quote_ratio_median",
        "spread_bps_p50_median",
        "spread_bps_p90_median",
        "depth1_notional_p50_median",
        "depth5_notional_p50_median",
        "depth10_notional_p50_median",
        "imbalance1_p50_median",
        "imbalance5_p50_median",
    ]
    model = aggregate.reset_index()
    model["half_spread_bps"] = (model["spread_bps_p50_median"] / 2.0).clip(lower=0)
    model["impact_sqrt_coef_bps"] = (
        model["spread_bps_p90_median"] - model["spread_bps_p50_median"]
    ).clip(lower=0)
    model["depth5_notional_reference"] = model["depth5_notional_p50_median"].clip(lower=1.0)
    model["model_formula"] = (
        "half_spread_bps + impact_sqrt_coef_bps * "
        "sqrt(order_notional / max(depth5_notional_reference, 1.0))"
    )
    model["model_version"] = "execution_cost_model.baseline.v1"
    start_date = str(daily_manifest["date_range"]["start"])
    as_of = str(daily_manifest["date_range"]["end"])
    model["calibration_start_date"] = start_date
    model["calibration_end_date"] = as_of
    model["model_quality_flag"] = "ok"
    model.loc[model["usable_days"] < 20, "model_quality_flag"] = "low_sample_lt20"
    model = model.sort_values("order_book_id").reset_index(drop=True)

    output_path = paths.cost_asset / "data/execution_cost_model.parquet"
    model.to_parquet(output_path, index=False, compression="zstd")
    summary = {
        "symbols": int(len(model)),
        "calibration_rows": int(len(model_input)),
        "calibration_start_date": start_date,
        "calibration_end_date": as_of,
        "median_half_spread_bps": float(model["half_spread_bps"].median()),
        "median_impact_sqrt_coef_bps": float(model["impact_sqrt_coef_bps"].median()),
        "median_depth5_notional_reference": float(model["depth5_notional_reference"].median()),
        "low_sample_symbols": int((model["model_quality_flag"] != "ok").sum()),
    }
    _write_json(paths.cost_asset / "model_summary.json", summary)

    fields = [str(column) for column in model.columns]
    manifest: dict[str, Any] = {
        "dataset": "execution_cost_model",
        "schema_version": "execution_cost_model.baseline.v1",
        "status": "completed",
        "provider": "derived",
        "market": "hk",
        "frequency": "calibration_window",
        "output_dir": str(paths.cost_asset),
        "snapshot_name": paths.cost_asset.name,
        "generated_at": _generated_at(),
        "generator": _generator(paths.depth_repo),
        "query": {"start_date": start_date, "end_date": as_of},
        "date_range": {"start": start_date, "end": as_of},
        "source_path": str(paths.daily_asset),
        "files": ["data/execution_cost_model.parquet", "model_summary.json"],
        "fields": fields,
        "row_count": int(len(model)),
        "symbol_count": int(len(model)),
        "totals": {
            "rows": int(len(model)),
            "symbols": int(len(model)),
            "calibration_rows": int(len(model_input)),
            "bytes": int(output_path.stat().st_size),
        },
        "method": {
            "name": "spread_depth_baseline",
            "formula": (
                "cost_bps = half_spread_bps + impact_sqrt_coef_bps * "
                "sqrt(order_notional / max(depth5_notional_reference, 1.0))"
            ),
            "calibration_inputs": [
                "spread_bps_p50",
                "spread_bps_p90",
                "depth5_notional_p50",
                "is_usable_for_cost_model",
            ],
            "intended_use": "Research backtest cost proxy; not a live execution simulator.",
        },
        "lineage": {
            "tick_depth_daily_asset": str(paths.daily_asset),
            "raw_asset": str(paths.raw_asset),
            "source_project": str(paths.depth_repo),
        },
    }
    _write_yaml(paths.cost_asset / "manifest.yml", manifest)
    _write_json(paths.cost_asset / "meta.json", manifest)
    (paths.cost_asset / "fields.txt").write_text("\n".join(fields) + "\n", encoding="utf-8")
    _symlink_force(paths.cost_asset, paths.cost_alias)
    return manifest


def rebuild_contract(paths: PublishPaths, *, as_of: str, generated_by: str) -> Path:
    contract_path = default_hk_current_contract_path(paths.hk_root)
    contract = build_hk_current_contract(
        paths.hk_root,
        generated_by=generated_by,
        target_date=as_of,
    )
    write_current_contract(contract_path, contract)
    write_dataset_registry(default_dataset_registry_path(paths.hk_root), contract)
    return contract_path


def publish_assets(args: argparse.Namespace) -> dict[str, Any]:
    hk_root = Path(args.hk_root).expanduser().resolve()
    depth_repo = Path(args.depth_repo).expanduser().resolve()
    paths = _asset_paths(hk_root, depth_repo, args.start_date, args.as_of)

    raw_manifest = publish_raw_asset(paths, start_date=args.start_date, as_of=args.as_of)
    daily_manifest, daily_frame = publish_daily_asset(paths)
    cost_manifest = publish_execution_cost_model(paths, daily_manifest, daily_frame)
    contract_path = rebuild_contract(
        paths,
        as_of=args.as_of,
        generated_by="publish_hk_tick_depth_assets.py",
    )

    if args.sync_cross_registry:
        cross_registry = Path(args.sync_cross_registry).expanduser().resolve()
        shutil.copy2(default_dataset_registry_path(paths.hk_root), cross_registry)
    else:
        cross_registry = None

    return {
        "hk_root": str(paths.hk_root),
        "raw_asset": str(paths.raw_asset),
        "raw_alias": str(paths.raw_alias),
        "raw_source_link_mode": raw_manifest["storage"]["link_mode"],
        "daily_asset": str(paths.daily_asset),
        "daily_rows": daily_manifest["totals"]["rows"],
        "daily_symbols": daily_manifest["totals"]["symbols"],
        "daily_duplicate_keys_dropped": daily_manifest["totals"]["duplicate_keys"],
        "execution_cost_model": str(paths.cost_asset),
        "execution_cost_symbols": cost_manifest["totals"]["symbols"],
        "contract_path": str(contract_path),
        "dataset_registry_path": str(default_dataset_registry_path(paths.hk_root)),
        "synced_cross_registry": str(cross_registry) if cross_registry is not None else None,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hk-root", required=True, help="HK data platform artifacts root.")
    parser.add_argument("--depth-repo", default=str(_default_depth_repo()))
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--as-of", default=DEFAULT_AS_OF)
    parser.add_argument(
        "--sync-cross-registry",
        default="",
        help=(
            "Optional cross-sectional-trees dataset_registry.csv mirror to update after "
            "publishing the platform registry."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    summary = publish_assets(args)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
