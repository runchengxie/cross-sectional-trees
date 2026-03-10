from __future__ import annotations

import argparse
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

from ..config_utils import resolve_pipeline_config
from ..data_providers import _to_rqdata_symbol
from .backup_data import _git_metadata

DEFAULT_OUT_ROOT = "data_assets/rqdata"
DEFAULT_BATCH_SIZE = 20
DEFAULT_PIPELINE_FUNDAMENTALS_NAME = "pipeline_fundamentals.parquet"
PIT_METADATA_COLUMNS = (
    "quarter",
    "info_date",
    "fiscal_year",
    "standard",
    "if_adjusted",
    "rice_create_tm",
    "order_book_id",
)


@dataclass(frozen=True)
class MirrorEntry:
    ts_code: str
    order_book_id: str
    path: Path
    rows: int
    total_bytes: int
    min_quarter: str | None
    max_quarter: str | None
    min_info_date: str | None
    max_info_date: str | None


def _resolve_path(path_text: str | Path) -> Path:
    path = Path(path_text).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (Path.cwd() / path).resolve()


def _normalize_hk_symbol(symbol: object) -> str:
    text = str(symbol or "").strip().upper()
    if not text:
        return ""
    if text.endswith(".XHKG"):
        text = text[:-5]
    if text.endswith(".HK"):
        text = text[:-3]
    if text.isdigit():
        text = text.zfill(5)
    return f"{text}.HK"


def _coerce_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "t"}
    return False


def _load_text_list(path_text: str | Path, *, label: str) -> list[str]:
    path = _resolve_path(path_text)
    if not path.exists():
        raise SystemExit(f"{label} not found: {path}")
    values: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            values.append(text)
    return values


def _load_symbols_from_by_date(path_text: str | Path) -> list[str]:
    path = _resolve_path(path_text)
    if not path.exists():
        raise SystemExit(f"Universe-by-date file not found: {path}")
    df = pd.read_csv(path)
    if df.empty:
        raise SystemExit(f"Universe-by-date file is empty: {path}")

    columns = {col.lower(): col for col in df.columns}
    date_col = columns.get("trade_date") or columns.get("date") or columns.get("rebalance_date")
    symbol_col = (
        columns.get("ts_code")
        or columns.get("stock_ticker")
        or columns.get("symbol")
        or columns.get("order_book_id")
    )
    if not date_col or not symbol_col:
        raise SystemExit("Universe-by-date file must include date + symbol columns.")

    selected_col = (
        columns.get("selected")
        or columns.get("selected_bool")
        or columns.get("selected_flag")
        or columns.get("is_selected")
    )
    if selected_col and selected_col in df.columns:
        df = df[df[selected_col].map(_coerce_bool)].copy()

    df = df.rename(columns={date_col: "trade_date", symbol_col: "ts_code"})
    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
    df = df[df["trade_date"].notna()].copy()
    df["ts_code"] = df["ts_code"].astype(str).str.strip()
    df["ts_code"] = df["ts_code"].map(_normalize_hk_symbol)
    df = df[df["ts_code"] != ""].copy()
    return df["ts_code"].drop_duplicates().tolist()


def _dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        deduped.append(text)
        seen.add(text)
    return deduped


def _resolve_fields(args) -> tuple[list[str], dict]:
    fields: list[str] = []
    if getattr(args, "field", None):
        fields.extend(str(item) for item in args.field)
    for path_text in getattr(args, "fields_file", None) or []:
        fields.extend(_load_text_list(path_text, label="Fields file"))
    fields = _dedupe_preserve_order(fields)
    if not fields:
        raise SystemExit("Provide at least one --field or --fields-file.")
    metadata = {
        "count": len(fields),
        "fields_file": [str(_resolve_path(path_text)) for path_text in (args.fields_file or [])],
    }
    return fields, metadata


def _resolve_symbols_from_config(config_ref: str) -> tuple[list[str], dict]:
    resolved = resolve_pipeline_config(config_ref)
    cfg = resolved.data
    universe_cfg = cfg.get("universe") if isinstance(cfg, Mapping) else None
    if not isinstance(universe_cfg, Mapping):
        raise SystemExit("Config is missing universe settings.")

    symbols: list[str] = []
    raw_symbols = universe_cfg.get("symbols")
    if isinstance(raw_symbols, str):
        symbols.append(raw_symbols)
    elif isinstance(raw_symbols, Sequence):
        symbols.extend(str(item) for item in raw_symbols)

    symbols_file = universe_cfg.get("symbols_file")
    if symbols_file:
        symbols.extend(_load_text_list(symbols_file, label="Symbols file"))

    by_date_file = universe_cfg.get("by_date_file")
    if by_date_file:
        symbols.extend(_load_symbols_from_by_date(by_date_file))

    metadata = {
        "mode": "config_universe",
        "config_ref": str(config_ref),
        "config_source": resolved.source,
        "symbols_file": str(_resolve_path(symbols_file)) if symbols_file else None,
        "by_date_file": str(_resolve_path(by_date_file)) if by_date_file else None,
    }
    return symbols, metadata


def _resolve_symbols(args) -> tuple[list[str], dict]:
    explicit_values = list(getattr(args, "symbol", None) or [])
    symbols_file = getattr(args, "symbols_file", None)
    by_date_file = getattr(args, "by_date_file", None)
    if explicit_values or symbols_file or by_date_file:
        symbols = list(explicit_values)
        if symbols_file:
            symbols.extend(_load_text_list(symbols_file, label="Symbols file"))
        if by_date_file:
            symbols.extend(_load_symbols_from_by_date(by_date_file))
        metadata = {
            "mode": "explicit",
            "symbols_file": str(_resolve_path(symbols_file)) if symbols_file else None,
            "by_date_file": str(_resolve_path(by_date_file)) if by_date_file else None,
        }
    elif getattr(args, "config", None):
        symbols, metadata = _resolve_symbols_from_config(args.config)
    else:
        raise SystemExit(
            "Provide --symbol/--symbols-file/--by-date-file, or pass --config with universe settings."
        )

    normalized = _dedupe_preserve_order(_normalize_hk_symbol(symbol) for symbol in symbols)
    limit = getattr(args, "limit", None)
    if limit is not None:
        if limit <= 0:
            raise SystemExit("--limit must be > 0.")
        normalized = normalized[:limit]
    if not normalized:
        raise SystemExit("No HK symbols resolved for mirroring.")
    metadata["count"] = len(normalized)
    metadata["limit"] = limit
    return normalized, metadata


def _default_snapshot_name(dataset_name: str, start_quarter: str, end_quarter: str, statements: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{dataset_name}_{start_quarter}_{end_quarter}_{statements}_{timestamp}"


def _prepare_output_dir(
    *,
    out_root: str,
    dataset_name: str,
    start_quarter: str,
    end_quarter: str,
    statements: str,
    name: str | None,
) -> Path:
    root = _resolve_path(out_root)
    snapshot_name = name or _default_snapshot_name(dataset_name, start_quarter, end_quarter, statements)
    output_dir = root / "hk" / dataset_name / snapshot_name
    if output_dir.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=False)
    return output_dir


def _chunked(values: Sequence[str], size: int) -> Iterable[list[str]]:
    if size <= 0:
        raise SystemExit("--batch-size must be > 0.")
    for idx in range(0, len(values), size):
        yield list(values[idx : idx + size])


def _prepare_asset_frame(frame: pd.DataFrame | pd.Series | None, *, symbol_map: Mapping[str, str]) -> pd.DataFrame:
    if frame is None:
        return pd.DataFrame()
    if isinstance(frame, pd.Series):
        frame = frame.to_frame(name=str(frame.name or "value"))
    if frame.empty:
        return frame.copy()

    normalized = frame.reset_index()
    if "order_book_id" not in normalized.columns:
        if len(symbol_map) == 1:
            normalized["order_book_id"] = next(iter(symbol_map.keys()))
        else:
            raise ValueError("RQData payload is missing order_book_id.")
    normalized["order_book_id"] = normalized["order_book_id"].astype(str).str.strip()
    normalized["ts_code"] = normalized["order_book_id"].map(symbol_map)
    missing_mask = normalized["ts_code"].isna()
    if missing_mask.any():
        normalized.loc[missing_mask, "ts_code"] = normalized.loc[missing_mask, "order_book_id"].map(
            _normalize_hk_symbol
        )
    if "quarter" in normalized.columns:
        normalized["quarter"] = normalized["quarter"].astype(str)

    sort_cols = [
        col
        for col in ["ts_code", "quarter", "info_date", "rice_create_tm", "field", "subject"]
        if col in normalized.columns
    ]
    if sort_cols:
        normalized = normalized.sort_values(sort_cols).reset_index(drop=True)
    return normalized


def _series_bounds_as_date(frame: pd.DataFrame, column: str) -> tuple[str | None, str | None]:
    if column not in frame.columns:
        return None, None
    values = pd.to_datetime(frame[column], errors="coerce").dropna()
    if values.empty:
        return None, None
    return values.min().strftime("%Y-%m-%d"), values.max().strftime("%Y-%m-%d")


def _series_bounds_as_text(frame: pd.DataFrame, column: str) -> tuple[str | None, str | None]:
    if column not in frame.columns:
        return None, None
    values = frame[column].dropna().astype(str)
    if values.empty:
        return None, None
    return values.min(), values.max()


def _write_symbol_frame(data_dir: Path, symbol_frame: pd.DataFrame) -> MirrorEntry:
    ts_code = str(symbol_frame["ts_code"].iloc[0])
    order_book_id = str(symbol_frame["order_book_id"].iloc[0])
    out_path = data_dir / f"{ts_code}.parquet"
    symbol_frame.to_parquet(out_path, index=False)
    min_quarter, max_quarter = _series_bounds_as_text(symbol_frame, "quarter")
    min_info_date, max_info_date = _series_bounds_as_date(symbol_frame, "info_date")
    return MirrorEntry(
        ts_code=ts_code,
        order_book_id=order_book_id,
        path=out_path,
        rows=int(len(symbol_frame)),
        total_bytes=int(out_path.stat().st_size),
        min_quarter=min_quarter,
        max_quarter=max_quarter,
        min_info_date=min_info_date,
        max_info_date=max_info_date,
    )


def _write_text_list(path: Path, values: Sequence[str]) -> None:
    text = "\n".join(values)
    if text:
        text += "\n"
    path.write_text(text, encoding="utf-8")


def _write_manifest(path: Path, payload: dict) -> None:
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _load_manifest(path: Path) -> dict | None:
    if not path.exists():
        return None
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    return None


def _build_manifest(
    *,
    dataset_name: str,
    api_name: str,
    output_dir: Path,
    fields: Sequence[str],
    field_metadata: Mapping[str, object],
    symbol_metadata: Mapping[str, object],
    symbols_requested: Sequence[str],
    entries: Sequence[MirrorEntry],
    missing_symbols: Sequence[str],
    query_date: str | None,
    start_quarter: str,
    end_quarter: str,
    statements: str,
    batches: Sequence[Mapping[str, object]],
    columns: Sequence[str],
    status: str,
    error: str | None,
    config_ref: str | None,
) -> dict:
    return {
        "name": output_dir.name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "error": error,
        "dataset": dataset_name,
        "api": api_name,
        "market": "hk",
        "config_ref": config_ref,
        "repo_root": str(Path.cwd().resolve()),
        "output_dir": str(output_dir),
        "query": {
            "start_quarter": start_quarter,
            "end_quarter": end_quarter,
            "date": query_date,
            "statements": statements,
            "fields_count": len(fields),
            "fields": list(fields),
            "fields_file": list(field_metadata.get("fields_file") or []),
        },
        "symbol_source": dict(symbol_metadata),
        "columns": list(columns),
        "batches": list(batches),
        "entries": [
            {
                "ts_code": item.ts_code,
                "order_book_id": item.order_book_id,
                "path": str(item.path),
                "rows": item.rows,
                "total_bytes": item.total_bytes,
                "min_quarter": item.min_quarter,
                "max_quarter": item.max_quarter,
                "min_info_date": item.min_info_date,
                "max_info_date": item.max_info_date,
            }
            for item in entries
        ],
        "missing_symbols": list(missing_symbols),
        "totals": {
            "symbols_requested": len(symbols_requested),
            "symbols_written": len(entries),
            "symbols_missing": len(missing_symbols),
            "files": len(entries),
            "rows": sum(item.rows for item in entries),
            "bytes": sum(item.total_bytes for item in entries),
        },
        "git": _git_metadata(Path.cwd().resolve()),
    }


def _load_hk_financial_fields() -> list[str]:
    try:
        from rqdatac.services.financial import HK_FIELDS_LIST_EX
    except ImportError as exc:
        raise SystemExit(
            "rqdatac with HK financial field metadata is not installed. Install with: pip install '.[rqdata]'"
        ) from exc
    return list(HK_FIELDS_LIST_EX)


def _ensure_rqdatac_hk_plugin() -> None:
    try:
        import rqdatac_hk  # noqa: F401
    except ImportError as exc:
        raise SystemExit("rqdatac-hk is not installed. Install with: pip install '.[rqdata]'") from exc


def list_hk_financial_fields(args) -> int:
    fields = _load_hk_financial_fields()
    contains = [str(item).strip().lower() for item in (getattr(args, "contains", None) or []) if str(item).strip()]
    if contains:
        fields = [field for field in fields if all(token in field.lower() for token in contains)]
    limit = getattr(args, "limit", None)
    if limit is not None:
        if limit <= 0:
            raise SystemExit("--limit must be > 0.")
        fields = fields[:limit]

    output = "\n".join(fields)
    if output:
        output += "\n"
    out = getattr(args, "out", None)
    if out:
        out_path = _resolve_path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(f"Wrote {len(fields)} HK financial fields to {out_path}")
    else:
        print(output, end="")
    return 0


def _mirror_dataset(
    *,
    args,
    rqdatac,
    dataset_name: str,
    api_name: str,
    fetch_batch,
) -> int:
    fields, field_metadata = _resolve_fields(args)
    symbols, symbol_metadata = _resolve_symbols(args)
    output_dir = _prepare_output_dir(
        out_root=getattr(args, "out_root", DEFAULT_OUT_ROOT),
        dataset_name=dataset_name,
        start_quarter=args.start_quarter,
        end_quarter=args.end_quarter,
        statements=args.statements,
        name=getattr(args, "name", None),
    )
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    symbol_map = {_to_rqdata_symbol("hk", symbol): symbol for symbol in symbols}
    order_book_ids = list(symbol_map.keys())
    entries: list[MirrorEntry] = []
    written_symbols: set[str] = set()
    batches: list[dict[str, object]] = []
    columns: list[str] = []
    status = "completed"
    error: str | None = None

    try:
        _write_text_list(output_dir / "fields.txt", fields)
        _write_text_list(output_dir / "symbols.txt", symbols)
        for batch_order_book_ids in _chunked(order_book_ids, getattr(args, "batch_size", DEFAULT_BATCH_SIZE)):
            payload = fetch_batch(
                batch_order_book_ids,
                fields,
                args.start_quarter,
                args.end_quarter,
                date=getattr(args, "date", None),
                statements=args.statements,
            )
            prepared = _prepare_asset_frame(payload, symbol_map=symbol_map)
            if prepared.empty:
                batches.append({"order_book_ids": len(batch_order_book_ids), "rows": 0})
                continue
            if not columns:
                columns = prepared.columns.tolist()
            batch_rows = int(len(prepared))
            batch_symbols = 0
            for _, symbol_frame in prepared.groupby("ts_code", sort=False):
                entry = _write_symbol_frame(data_dir, symbol_frame.reset_index(drop=True))
                entries.append(entry)
                written_symbols.add(entry.ts_code)
                batch_symbols += 1
            batches.append(
                {
                    "order_book_ids": len(batch_order_book_ids),
                    "rows": batch_rows,
                    "symbols_written": batch_symbols,
                }
            )
    except Exception as exc:
        status = "failed"
        error = str(exc)
        raise
    finally:
        missing_symbols = [symbol for symbol in symbols if symbol not in written_symbols]
        manifest = _build_manifest(
            dataset_name=dataset_name,
            api_name=api_name,
            output_dir=output_dir,
            fields=fields,
            field_metadata=field_metadata,
            symbol_metadata=symbol_metadata,
            symbols_requested=symbols,
            entries=entries,
            missing_symbols=missing_symbols,
            query_date=getattr(args, "date", None),
            start_quarter=args.start_quarter,
            end_quarter=args.end_quarter,
            statements=args.statements,
            batches=batches,
            columns=columns,
            status=status,
            error=error,
            config_ref=getattr(args, "config", None),
        )
        _write_manifest(output_dir / "manifest.yml", manifest)

    totals = {
        "files": len(entries),
        "symbols": len(entries),
        "rows": sum(item.rows for item in entries),
        "bytes": sum(item.total_bytes for item in entries),
    }
    print(
        f"Wrote {dataset_name} mirror to {output_dir} "
        f"({totals['symbols']} symbols, {totals['files']} files, {totals['rows']} rows, {totals['bytes']} bytes)"
    )
    return 0


def mirror_hk_pit_financials(args, rqdatac) -> int:
    return _mirror_dataset(
        args=args,
        rqdatac=rqdatac,
        dataset_name="pit_financials",
        api_name="rqdatac.get_pit_financials_ex",
        fetch_batch=lambda order_book_ids, fields, start_quarter, end_quarter, **kwargs: rqdatac.get_pit_financials_ex(
            order_book_ids=order_book_ids,
            fields=list(fields),
            start_quarter=start_quarter,
            end_quarter=end_quarter,
            market="hk",
            **kwargs,
        ),
    )


def mirror_hk_financial_details(args, rqdatac) -> int:
    _ensure_rqdatac_hk_plugin()
    hk_api = getattr(rqdatac, "hk", None)
    if hk_api is None or not hasattr(hk_api, "get_detailed_financial_items"):
        raise SystemExit("rqdatac.hk.get_detailed_financial_items is unavailable. Check rqdatac-hk installation.")
    return _mirror_dataset(
        args=args,
        rqdatac=rqdatac,
        dataset_name="financial_details",
        api_name="rqdatac.hk.get_detailed_financial_items",
        fetch_batch=lambda order_book_ids, fields, start_quarter, end_quarter, **kwargs: hk_api.get_detailed_financial_items(
            order_book_ids=order_book_ids,
            fields=list(fields),
            start_quarter=start_quarter,
            end_quarter=end_quarter,
            market="hk",
            **kwargs,
        ),
    )


def _resolve_pit_asset_dir(path_text: str | Path) -> tuple[Path, dict | None]:
    asset_dir = _resolve_path(path_text)
    if not asset_dir.exists():
        raise SystemExit(f"PIT asset directory not found: {asset_dir}")
    data_dir = asset_dir / "data"
    if not data_dir.is_dir():
        raise SystemExit(f"PIT asset directory is missing data/: {asset_dir}")
    manifest = _load_manifest(asset_dir / "manifest.yml")
    if manifest and manifest.get("dataset") not in {None, "pit_financials"}:
        raise SystemExit(
            f"Expected a pit_financials asset directory, got dataset={manifest.get('dataset')!r}: {asset_dir}"
        )
    return asset_dir, manifest


def _resolve_build_fields(
    *,
    args,
    manifest: Mapping[str, object] | None,
    available_columns: Sequence[str],
) -> tuple[list[str], dict]:
    if getattr(args, "field", None) or getattr(args, "fields_file", None):
        fields, metadata = _resolve_fields(args)
        metadata["source"] = "explicit"
    else:
        manifest_fields: list[str] = []
        if manifest:
            query = manifest.get("query")
            if isinstance(query, Mapping):
                raw_fields = query.get("fields")
                if isinstance(raw_fields, Sequence) and not isinstance(raw_fields, str):
                    manifest_fields = [str(item) for item in raw_fields]
        fields = _dedupe_preserve_order(manifest_fields)
        source = "asset_manifest"
        if not fields:
            excluded = {"ts_code", "order_book_id", *PIT_METADATA_COLUMNS}
            fields = [str(col) for col in available_columns if str(col) not in excluded]
            source = "inferred"
        metadata = {"count": len(fields), "fields_file": [], "source": source}
    if not fields:
        raise SystemExit("No PIT value fields resolved for building fundamentals.")
    available = {str(col) for col in available_columns}
    missing = [field for field in fields if field not in available]
    if missing:
        raise SystemExit(
            "Requested PIT fields are not available in the asset: " + ", ".join(missing)
        )
    return fields, metadata


def _default_pipeline_fundamentals_path(asset_dir: Path) -> Path:
    return asset_dir / DEFAULT_PIPELINE_FUNDAMENTALS_NAME


def _resolve_pipeline_fundamentals_out_path(args, asset_dir: Path) -> Path:
    out = getattr(args, "out", None)
    if out:
        return _resolve_path(out)
    return _default_pipeline_fundamentals_path(asset_dir)


def _pipeline_fundamentals_manifest_path(out_path: Path) -> Path:
    return out_path.with_name(f"{out_path.stem}.manifest.yml")


def build_hk_pit_fundamentals_file(args) -> int:
    asset_dir, source_manifest = _resolve_pit_asset_dir(args.asset_dir)
    data_dir = asset_dir / "data"
    data_files = sorted(data_dir.glob("*.parquet"))
    if not data_files:
        raise SystemExit(f"No parquet files found under {data_dir}")

    first_frame = pd.read_parquet(data_files[0])
    available_columns = list(source_manifest.get("columns") or []) if source_manifest else []
    if not available_columns:
        available_columns = first_frame.columns.tolist()
    fields, field_metadata = _resolve_build_fields(
        args=args,
        manifest=source_manifest,
        available_columns=available_columns,
    )

    out_path = _resolve_pipeline_fundamentals_out_path(args, asset_dir)
    if out_path.exists() and not getattr(args, "force", False):
        raise SystemExit(f"Refusing to overwrite existing output: {out_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    combined_frames: list[pd.DataFrame] = []
    input_rows = 0
    dropped_missing_info_date = 0
    dropped_all_missing_fields = 0
    cached_frames: dict[Path, pd.DataFrame] = {data_files[0]: first_frame}
    keep_meta = bool(getattr(args, "keep_meta", False))

    for data_file in data_files:
        frame = cached_frames.get(data_file)
        if frame is None:
            frame = pd.read_parquet(data_file)
        input_rows += int(len(frame))
        if frame.empty:
            continue
        if "ts_code" not in frame.columns or "info_date" not in frame.columns:
            raise SystemExit(
                f"PIT asset file must include ts_code and info_date columns: {data_file}"
            )
        missing_fields = [field for field in fields if field not in frame.columns]
        if missing_fields:
            raise SystemExit(
                f"PIT asset file is missing requested fields {missing_fields}: {data_file}"
            )

        work = frame.copy()
        work["ts_code"] = work["ts_code"].astype(str).str.strip()
        info_dates = pd.to_datetime(work["info_date"], errors="coerce")
        valid_info_date = info_dates.notna()
        dropped_missing_info_date += int((~valid_info_date).sum())
        work = work.loc[valid_info_date].copy()
        if work.empty:
            continue
        work["info_date"] = info_dates.loc[valid_info_date].dt.normalize()
        work["trade_date"] = work["info_date"].dt.strftime("%Y%m%d")
        empty_value_rows = work[fields].isna().all(axis=1)
        dropped_all_missing_fields += int(empty_value_rows.sum())
        work = work.loc[~empty_value_rows].copy()
        if work.empty:
            continue
        combined_frames.append(work)

    meta_columns = [col for col in PIT_METADATA_COLUMNS if keep_meta and col in available_columns]
    output_columns = ["trade_date", "ts_code", *fields, *meta_columns]
    duplicate_rows_seen = 0
    duplicate_rows_dropped = 0
    if combined_frames:
        combined = pd.concat(combined_frames, ignore_index=True)
        sort_columns = [
            col
            for col in [
                "ts_code",
                "trade_date",
                "quarter",
                "fiscal_year",
                "info_date",
                "rice_create_tm",
                "if_adjusted",
                "standard",
            ]
            if col in combined.columns
        ]
        if sort_columns:
            combined = combined.sort_values(sort_columns).reset_index(drop=True)
        duplicate_rows_seen = int(
            combined.duplicated(subset=["trade_date", "ts_code"], keep=False).sum()
        )
        if duplicate_rows_seen and getattr(args, "duplicate_policy", "keep-last") == "error":
            raise SystemExit(
                "Duplicate trade_date + ts_code rows found in PIT asset. "
                "Retry with --duplicate-policy keep-last if you want automatic deduplication."
            )
        deduped = combined.drop_duplicates(subset=["trade_date", "ts_code"], keep="last")
        duplicate_rows_dropped = int(len(combined) - len(deduped))
        output_df = deduped.loc[:, [col for col in output_columns if col in deduped.columns]].copy()
        output_df = output_df.sort_values(["ts_code", "trade_date"]).reset_index(drop=True)
    else:
        output_df = pd.DataFrame(columns=output_columns)

    if out_path.suffix.lower() == ".csv":
        output_df.to_csv(out_path, index=False)
        output_format = "csv"
    else:
        output_df.to_parquet(out_path, index=False)
        output_format = "parquet"

    output_manifest = {
        "name": out_path.name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "status": "completed",
        "dataset": "pit_fundamentals_file",
        "market": "hk",
        "source_asset_dir": str(asset_dir),
        "source_manifest": str(asset_dir / "manifest.yml") if (asset_dir / "manifest.yml").exists() else None,
        "source_query": source_manifest.get("query") if isinstance(source_manifest, Mapping) else None,
        "symbol_source": source_manifest.get("symbol_source") if isinstance(source_manifest, Mapping) else None,
        "output_file": str(out_path),
        "output_format": output_format,
        "query": {
            "fields_count": len(fields),
            "fields": list(fields),
            "fields_file": list(field_metadata.get("fields_file") or []),
            "field_source": field_metadata.get("source"),
            "keep_meta": keep_meta,
            "duplicate_policy": getattr(args, "duplicate_policy", "keep-last"),
        },
        "columns": output_df.columns.tolist(),
        "totals": {
            "input_files": len(data_files),
            "input_rows": input_rows,
            "output_rows": int(len(output_df)),
            "symbols": int(output_df["ts_code"].nunique()) if not output_df.empty else 0,
            "dropped_missing_info_date": dropped_missing_info_date,
            "dropped_all_missing_fields": dropped_all_missing_fields,
            "duplicate_rows_seen": duplicate_rows_seen,
            "duplicate_rows_dropped": duplicate_rows_dropped,
        },
        "git": _git_metadata(Path.cwd().resolve()),
    }
    _write_manifest(_pipeline_fundamentals_manifest_path(out_path), output_manifest)

    print(
        f"Wrote HK PIT fundamentals file to {out_path} "
        f"({len(output_df)} rows, {len(fields)} value columns, {output_format})"
    )
    return 0


def add_list_hk_financial_fields_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--contains",
        action="append",
        default=[],
        help="Keep only field names containing this token. Repeatable.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional cap on the number of printed field names.",
    )
    parser.add_argument(
        "--out",
        help="Optional output path. Default: print to stdout.",
    )


def add_hk_financial_mirror_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", help="Optional config path or alias for rqdata.init and default universe.")
    parser.add_argument("--username", help="Override RQData username")
    parser.add_argument("--password", help="Override RQData password")
    parser.add_argument("--start-quarter", required=True, help="Quarter range start, for example 2011q1.")
    parser.add_argument("--end-quarter", required=True, help="Quarter range end, for example 2025q4.")
    parser.add_argument(
        "--date",
        help="Optional PIT as-of date. Use an absolute date such as 20260310 for reproducible mirrors.",
    )
    parser.add_argument(
        "--statements",
        default="latest",
        choices=["latest", "all"],
        help="Return latest or all statements for each quarter. Default: latest.",
    )
    parser.add_argument(
        "--field",
        action="append",
        default=[],
        help="Financial field name. Repeatable.",
    )
    parser.add_argument(
        "--fields-file",
        action="append",
        default=[],
        help="Text file with one financial field per line. Repeatable.",
    )
    parser.add_argument(
        "--symbol",
        action="append",
        default=[],
        help="HK symbol to mirror, for example 00005.HK. Repeatable.",
    )
    parser.add_argument(
        "--symbols-file",
        help="Text file with one HK symbol per line. If provided, this takes precedence over config universe symbols.",
    )
    parser.add_argument(
        "--by-date-file",
        help="Universe-by-date CSV. If provided, this takes precedence over config universe symbols.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional cap on the resolved symbol count after dedupe.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Number of order_book_ids per RQData request. Default: {DEFAULT_BATCH_SIZE}.",
    )
    parser.add_argument(
        "--out-root",
        default=DEFAULT_OUT_ROOT,
        help=f"Mirror root directory. Default: {DEFAULT_OUT_ROOT}",
    )
    parser.add_argument(
        "--name",
        help="Optional snapshot folder name. Default: auto-generated from range + timestamp.",
    )


def add_hk_pit_fundamentals_build_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--asset-dir",
        required=True,
        help="Path to a mirror-hk-pit-financials output directory.",
    )
    parser.add_argument(
        "--field",
        action="append",
        default=[],
        help="Value field to keep in the output fundamentals file. Repeatable. Default: use asset manifest fields.",
    )
    parser.add_argument(
        "--fields-file",
        action="append",
        default=[],
        help="Text file with one financial field per line. Repeatable.",
    )
    parser.add_argument(
        "--out",
        help=(
            "Output file path. Default: <asset-dir>/"
            + DEFAULT_PIPELINE_FUNDAMENTALS_NAME
            + ". Use .csv to write CSV, otherwise Parquet."
        ),
    )
    parser.add_argument(
        "--keep-meta",
        action="store_true",
        help="Keep PIT metadata columns such as quarter, info_date, fiscal_year and rice_create_tm.",
    )
    parser.add_argument(
        "--duplicate-policy",
        choices=["keep-last", "error"],
        default="keep-last",
        help="How to handle duplicate trade_date + ts_code rows after mapping trade_date=info_date.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )
