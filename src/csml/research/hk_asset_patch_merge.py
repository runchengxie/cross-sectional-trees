#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path

import pandas as pd

from csml.data_providers import _to_rqdata_symbol
from csml.data_tools import rqdata_assets as _base


DATASET_CONFIG: dict[str, dict[str, object]] = {
    "daily": {
        "kind": "daily",
        "date_column": "trade_date",
        "sort_columns": (),
        "dedupe_keys": ("trade_date",),
    },
    "valuation": {
        "kind": "dated",
        "date_column": "trade_date",
        "sort_columns": (),
        "dedupe_keys": ("trade_date",),
    },
    "ex_factors": {
        "kind": "dated",
        "date_column": "ex_date",
        "sort_columns": ("index",),
        "dedupe_keys": ("unique_id", "ex_date", "index"),
    },
    "dividends": {
        "kind": "dated",
        "date_column": "declaration_announcement_date",
        "sort_columns": ("index", "ex_dividend_date", "payable_date"),
        "dedupe_keys": ("unique_id", "declaration_announcement_date", "index"),
    },
    "shares": {
        "kind": "dated",
        "date_column": "date",
        "sort_columns": ("index",),
        "dedupe_keys": ("unique_id", "date", "index"),
    },
}


def _resolve_path(path_text: str | Path) -> Path:
    path = Path(path_text).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (Path.cwd() / path).resolve()


def _resolve_link_path(path_text: str | Path) -> Path:
    path = Path(path_text).expanduser()
    if path.is_absolute():
        return path
    return (Path.cwd() / path).absolute()


def _load_text_list(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _dedupe_preserve_order(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _merge_columns(base_manifest: Mapping | None, patch_manifest: Mapping | None) -> list[str]:
    base_columns = list(base_manifest.get("columns") or []) if isinstance(base_manifest, Mapping) else []
    patch_columns = list(patch_manifest.get("columns") or []) if isinstance(patch_manifest, Mapping) else []
    if base_columns:
        return _dedupe_preserve_order(base_columns)
    return _dedupe_preserve_order(patch_columns)


def _merge_fields(base_manifest: Mapping | None, patch_manifest: Mapping | None) -> tuple[list[str], dict[str, object]]:
    def _query(manifest: Mapping | None) -> Mapping:
        if not isinstance(manifest, Mapping):
            return {}
        value = manifest.get("query")
        return value if isinstance(value, Mapping) else {}

    base_query = _query(base_manifest)
    patch_query = _query(patch_manifest)
    fields = _dedupe_preserve_order(list(base_query.get("fields") or []) + list(patch_query.get("fields") or []))
    field_metadata = {
        "fields_file": _dedupe_preserve_order(
            list(base_query.get("fields_file") or []) + list(patch_query.get("fields_file") or [])
        ),
        "source": base_query.get("field_source") or patch_query.get("field_source"),
        "base_fields": _dedupe_preserve_order(
            list(base_query.get("base_fields") or []) + list(patch_query.get("base_fields") or [])
        ),
        "field_profile": _dedupe_preserve_order(
            list(base_query.get("field_profile") or []) + list(patch_query.get("field_profile") or [])
        ),
    }
    return fields, field_metadata


def _merge_symbol_metadata(
    *,
    base_manifest: Mapping | None,
    patch_manifest: Mapping | None,
    symbols_requested: Sequence[str],
) -> dict[str, object]:
    base_source = (
        dict(base_manifest.get("symbol_source") or {}) if isinstance(base_manifest, Mapping) else {}
    )
    patch_source = (
        dict(patch_manifest.get("symbol_source") or {}) if isinstance(patch_manifest, Mapping) else {}
    )
    merged = patch_source.copy()
    merged.update(base_source)
    merged["count"] = len(symbols_requested)
    return merged


def _create_relative_symlink(target: Path, link: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists() or link.is_symlink():
        link.unlink()
    rel_target = os.path.relpath(target, start=link.parent)
    os.symlink(rel_target, link, target_is_directory=target.is_dir())


def _ensure_clean_dir(path: Path, *, overwrite: bool) -> None:
    if path.exists() or path.is_symlink():
        if not overwrite:
            raise SystemExit(f"Output path already exists: {path}")
        if path.is_symlink() or path.is_file():
            path.unlink()
        else:
            shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _dedupe_dated_frame(
    frame: pd.DataFrame,
    *,
    dataset_name: str,
    date_column: str,
    sort_columns: Sequence[str],
) -> pd.DataFrame:
    config = DATASET_CONFIG[dataset_name]
    dedupe_keys = [column for column in config.get("dedupe_keys", ()) if column in frame.columns]
    if "unique_id" in dedupe_keys:
        unique_mask = frame["unique_id"].notna()
        if not unique_mask.any():
            dedupe_keys = [column for column in dedupe_keys if column != "unique_id"]
    if dedupe_keys:
        frame = frame.drop_duplicates(subset=dedupe_keys, keep="last")
    ordered_sort_cols = [column for column in ["symbol", date_column, *sort_columns] if column in frame.columns]
    if ordered_sort_cols:
        frame = frame.sort_values(ordered_sort_cols).reset_index(drop=True)
    return frame


def _merge_symbol_frames(
    *,
    dataset_name: str,
    schema_columns: Sequence[str],
    symbol: str,
    base_frame: pd.DataFrame | None,
    patch_frame: pd.DataFrame | None,
) -> pd.DataFrame:
    frames = [frame.copy() for frame in (base_frame, patch_frame) if frame is not None and not frame.empty]
    if not frames:
        return pd.DataFrame(columns=list(schema_columns))

    config = DATASET_CONFIG[dataset_name]
    kind = str(config["kind"])
    date_column = str(config["date_column"])
    sort_columns = tuple(str(column) for column in config.get("sort_columns", ()))
    merged = pd.concat(frames, ignore_index=True, sort=False)

    order_book_candidates = [
        str(value).strip()
        for value in merged.get("order_book_id", pd.Series(dtype=object)).dropna().astype(str).tolist()
        if str(value).strip()
    ]
    order_book_id = order_book_candidates[0] if order_book_candidates else _to_rqdata_symbol("hk", symbol)

    if kind == "daily":
        prepared = _base._prepare_daily_asset_frame(
            merged,
            symbol=symbol,
            order_book_id=order_book_id,
        )
    else:
        symbol_map = {
            candidate: symbol
            for candidate in _dedupe_preserve_order(order_book_candidates + [order_book_id])
        }
        prepared = _base._prepare_dated_asset_frame(
            merged,
            symbol_map=symbol_map,
            date_column=date_column,
            sort_columns=sort_columns,
        )
        prepared = _dedupe_dated_frame(
            prepared,
            dataset_name=dataset_name,
            date_column=date_column,
            sort_columns=sort_columns,
        )

    if schema_columns:
        keep_columns = [column for column in schema_columns if column in prepared.columns]
        if keep_columns:
            prepared = prepared.loc[:, keep_columns].copy()
    return prepared.reset_index(drop=True)


def _link_or_copy_base_file(source: Path, dest: Path) -> None:
    if dest.exists() or dest.is_symlink():
        dest.unlink()
    _create_relative_symlink(source, dest)


def _build_manifest_and_audit(
    *,
    dataset_name: str,
    base_manifest: Mapping,
    patch_manifest: Mapping,
    out_dir: Path,
    symbols_requested: Sequence[str],
    fields: Sequence[str],
    field_metadata: Mapping[str, object],
    symbol_metadata: Mapping[str, object],
    schema_columns: Sequence[str],
    entries_by_symbol: dict[str, object],
    audit_by_symbol: dict[str, object],
    field_coverage: Mapping[str, Mapping[str, object]],
    source_rows: Mapping[str, int],
    started_at: str,
    finished_at: str,
) -> dict:
    kind = str(DATASET_CONFIG[dataset_name]["kind"])
    audit_path = out_dir / "audit.csv"
    ordered_audit = [audit_by_symbol[symbol] for symbol in symbols_requested]
    missing_symbols = [symbol for symbol in symbols_requested if symbol not in entries_by_symbol]
    api_name = f"local_merge({base_manifest.get('api') or patch_manifest.get('api') or 'unknown'})"
    batches = [
        {
            "source_snapshot": Path(str(base_manifest.get("output_dir") or "")).name or Path(str(base_manifest.get("name") or "")).name,
            "rows": int(source_rows.get("base", 0)),
            "symbols_written": int(len(list((Path(str(base_manifest.get('output_dir'))) / 'data').glob('*.parquet'))))
            if base_manifest.get("output_dir")
            else 0,
            "status": "merged_source",
        },
        {
            "source_snapshot": Path(str(patch_manifest.get("output_dir") or "")).name or Path(str(patch_manifest.get("name") or "")).name,
            "rows": int(source_rows.get("patch", 0)),
            "symbols_written": int(len(list((Path(str(patch_manifest.get('output_dir'))) / 'data').glob('*.parquet'))))
            if patch_manifest.get("output_dir")
            else 0,
            "status": "merged_source",
        },
    ]

    if kind == "daily":
        _base._write_daily_audit_csv(audit_path, ordered_audit)
        query = dict(base_manifest.get("query") or {})
        manifest = _base._build_daily_manifest(
            dataset_name=dataset_name,
            api_name=api_name,
            output_dir=out_dir,
            fields=fields,
            field_metadata=field_metadata,
            symbol_metadata=symbol_metadata,
            symbols_requested=symbols_requested,
            entries=[entries_by_symbol[symbol] for symbol in symbols_requested if symbol in entries_by_symbol],
            missing_symbols=missing_symbols,
            start_date=str(query.get("start_date") or ""),
            end_date=str((patch_manifest.get("query") or {}).get("end_date") or query.get("end_date") or ""),
            frequency=str(query.get("frequency") or "1d"),
            adjust_type=query.get("adjust_type"),
            skip_suspended=bool(query.get("skip_suspended", True)),
            batches=batches,
            columns=schema_columns,
            audit_file=audit_path,
            audit_records=ordered_audit,
            field_coverage=list(field_coverage.values()),
            started_at=started_at,
            finished_at=finished_at,
            status="completed",
            error=None,
            config_ref=None,
        )
    else:
        _base._write_dated_audit_csv(audit_path, ordered_audit)
        query = dict(base_manifest.get("query") or {})
        patch_query = dict(patch_manifest.get("query") or {})
        manifest = _base._build_dated_manifest(
            dataset_name=dataset_name,
            api_name=api_name,
            output_dir=out_dir,
            fields=fields,
            field_metadata=field_metadata,
            symbol_metadata=symbol_metadata,
            symbols_requested=symbols_requested,
            entries=[entries_by_symbol[symbol] for symbol in symbols_requested if symbol in entries_by_symbol],
            missing_symbols=missing_symbols,
            start_date=str(query.get("start_date") or ""),
            end_date=str(patch_query.get("end_date") or query.get("end_date") or ""),
            date_column=str(query.get("date_column") or patch_query.get("date_column") or DATASET_CONFIG[dataset_name]["date_column"]),
            batches=batches,
            columns=schema_columns,
            audit_file=audit_path,
            audit_records=ordered_audit,
            field_coverage=list(field_coverage.values()),
            started_at=started_at,
            finished_at=finished_at,
            status="completed",
            error=None,
            config_ref=None,
        )
    return manifest


def merge_asset_patch(
    *,
    base_dir: Path,
    patch_dir: Path,
    out_dir: Path,
    alias_path: Path | None,
    overwrite: bool,
) -> dict[str, object]:
    base_manifest = _base._load_manifest(base_dir / "manifest.yml") or {}
    patch_manifest = _base._load_manifest(patch_dir / "manifest.yml") or {}
    dataset_name = str(base_manifest.get("dataset") or patch_manifest.get("dataset") or "").strip()
    if dataset_name not in DATASET_CONFIG:
        raise SystemExit(f"Unsupported dataset for local merge: {dataset_name!r}")
    if str(patch_manifest.get("dataset") or dataset_name).strip() != dataset_name:
        raise SystemExit(
            f"Dataset mismatch between base={base_manifest.get('dataset')!r} and patch={patch_manifest.get('dataset')!r}."
        )

    _ensure_clean_dir(out_dir, overwrite=overwrite)
    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    base_data_dir = base_dir / "data"
    patch_data_dir = patch_dir / "data"
    base_files = {path.stem: path for path in sorted(base_data_dir.glob("*.parquet"))}
    patch_files = {path.stem: path for path in sorted(patch_data_dir.glob("*.parquet"))}

    base_symbols_requested = _load_text_list(base_dir / "symbols.txt")
    patch_symbols_requested = _load_text_list(patch_dir / "symbols.txt")
    symbols_requested = _dedupe_preserve_order(
        base_symbols_requested + patch_symbols_requested + list(base_files) + list(patch_files)
    )

    fields, field_metadata = _merge_fields(base_manifest, patch_manifest)
    schema_columns = _merge_columns(base_manifest, patch_manifest)
    symbol_metadata = _merge_symbol_metadata(
        base_manifest=base_manifest,
        patch_manifest=patch_manifest,
        symbols_requested=symbols_requested,
    )
    field_coverage = _base._field_coverage_template(fields)
    entries_by_symbol: dict[str, object] = {}
    audit_by_symbol: dict[str, object] = {}
    started_at = _base._timestamp_now()
    source_rows = {
        "base": int(((base_manifest.get("totals") or {}).get("rows")) or 0),
        "patch": int(((patch_manifest.get("totals") or {}).get("rows")) or 0),
    }
    kind = str(DATASET_CONFIG[dataset_name]["kind"])
    date_column = str(DATASET_CONFIG[dataset_name]["date_column"])

    def _record_written(symbol: str, path: Path, status: str) -> None:
        if kind == "daily":
            entry, symbol_frame = _base._load_existing_daily_entry(path, fields=fields)
            entries_by_symbol[symbol] = entry
            _base._update_field_coverage(field_coverage, symbol_frame, fields=fields)
            audit_by_symbol[symbol] = _base._daily_audit_record(
                symbol=symbol,
                order_book_id=entry.order_book_id,
                status=status,
                attempts=0,
                started_at=None,
                finished_at=_base._path_mtime_iso(path),
                file_mtime=_base._path_mtime_iso(path),
                error=None,
                entry=entry,
            )
        else:
            entry, symbol_frame = _base._load_existing_dated_entry(path, date_column=date_column, fields=fields)
            entries_by_symbol[symbol] = entry
            _base._update_field_coverage(field_coverage, symbol_frame, fields=fields)
            audit_by_symbol[symbol] = _base._dated_audit_record(
                symbol=symbol,
                order_book_id=entry.order_book_id,
                status=status,
                attempts=0,
                started_at=None,
                finished_at=_base._path_mtime_iso(path),
                file_mtime=_base._path_mtime_iso(path),
                error=None,
                entry=entry,
            )

    for symbol in symbols_requested:
        base_path = base_files.get(symbol)
        patch_path = patch_files.get(symbol)
        out_path = data_dir / f"{symbol}.parquet"

        if patch_path is not None:
            base_frame = pd.read_parquet(base_path) if base_path and base_path.exists() else None
            patch_frame = pd.read_parquet(patch_path)
            merged = _merge_symbol_frames(
                dataset_name=dataset_name,
                schema_columns=schema_columns,
                symbol=symbol,
                base_frame=base_frame,
                patch_frame=patch_frame,
            )
            if merged.empty:
                continue
            if kind == "daily":
                _base._write_daily_symbol_frame(data_dir, merged)
            else:
                _base._write_dated_symbol_frame(data_dir, merged, date_column=date_column)
            _record_written(symbol, out_path, status="merged_patch" if base_path else "patch_only")
            continue

        if base_path is not None:
            _link_or_copy_base_file(base_path, out_path)
            _record_written(symbol, out_path, status="linked_base")
            continue

        order_book_id = _to_rqdata_symbol("hk", symbol)
        finished_at = _base._timestamp_now()
        if kind == "daily":
            audit_by_symbol[symbol] = _base._daily_audit_record(
                symbol=symbol,
                order_book_id=order_book_id,
                status="missing_remote",
                attempts=0,
                started_at=None,
                finished_at=finished_at,
                file_mtime=None,
                error=None,
                entry=None,
            )
        else:
            audit_by_symbol[symbol] = _base._dated_audit_record(
                symbol=symbol,
                order_book_id=order_book_id,
                status="missing_remote",
                attempts=0,
                started_at=None,
                finished_at=finished_at,
                file_mtime=None,
                error=None,
                entry=None,
            )

    _base._write_text_list(out_dir / "fields.txt", fields)
    _base._write_text_list(out_dir / "symbols.txt", symbols_requested)
    finished_at = _base._timestamp_now()
    manifest = _build_manifest_and_audit(
        dataset_name=dataset_name,
        base_manifest=base_manifest,
        patch_manifest=patch_manifest,
        out_dir=out_dir,
        symbols_requested=symbols_requested,
        fields=fields,
        field_metadata=field_metadata,
        symbol_metadata=symbol_metadata,
        schema_columns=schema_columns,
        entries_by_symbol=entries_by_symbol,
        audit_by_symbol=audit_by_symbol,
        field_coverage=field_coverage,
        source_rows=source_rows,
        started_at=started_at,
        finished_at=finished_at,
    )
    _base._write_manifest(out_dir / "manifest.yml", manifest)

    if alias_path is not None:
        _create_relative_symlink(out_dir, alias_path)

    totals = manifest.get("totals") if isinstance(manifest.get("totals"), Mapping) else {}
    return {
        "dataset": dataset_name,
        "output_dir": str(out_dir),
        "alias_path": str(alias_path) if alias_path is not None else None,
        "files": int(totals.get("files") or 0),
        "rows": int(totals.get("rows") or 0),
        "symbols_written": int(totals.get("symbols_written") or 0),
        "symbols_missing_remote": int(totals.get("symbols_missing_remote") or 0),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Merge a local HK base snapshot and a later patch snapshot into a new canonical asset directory."
    )
    parser.add_argument("--base-dir", required=True, help="Base asset directory with data/ + manifest.yml")
    parser.add_argument("--patch-dir", required=True, help="Patch asset directory with data/ + manifest.yml")
    parser.add_argument("--out-dir", required=True, help="Destination canonical asset directory")
    parser.add_argument("--alias", help="Optional alias/symlink path to repoint after the merge succeeds")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the destination directory if it already exists.",
    )
    args = parser.parse_args(argv)

    result = merge_asset_patch(
        base_dir=_resolve_path(args.base_dir),
        patch_dir=_resolve_path(args.patch_dir),
        out_dir=_resolve_path(args.out_dir),
        alias_path=_resolve_link_path(args.alias) if args.alias else None,
        overwrite=bool(args.overwrite),
    )
    print(
        "Merged {dataset} patch -> {output_dir} "
        "(symbols={symbols_written}, rows={rows}, missing_remote={symbols_missing_remote})".format(
            **result
        )
    )
    if result.get("alias_path"):
        print(f"Updated alias -> {result['alias_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
