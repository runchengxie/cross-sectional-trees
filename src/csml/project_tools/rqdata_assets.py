from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
import time

import pandas as pd
import yaml

from ..artifacts import (
    RQDATA_ASSETS_DIR as DEFAULT_RQDATA_ASSETS_DIR,
)
from ..config_utils import resolve_pipeline_config
from ..data_providers import _to_rqdata_symbol
from .backup_data import _git_metadata

DEFAULT_OUT_ROOT = DEFAULT_RQDATA_ASSETS_DIR.as_posix()
DEFAULT_BATCH_SIZE = 20
DEFAULT_PIPELINE_FUNDAMENTALS_NAME = "pipeline_fundamentals.parquet"
DEFAULT_MIRROR_MAX_ATTEMPTS = 3
DEFAULT_MIRROR_BACKOFF_SECONDS = 1.0
DEFAULT_MIRROR_MAX_BACKOFF_SECONDS = 30.0
PIT_METADATA_COLUMNS = (
    "quarter",
    "info_date",
    "fiscal_year",
    "standard",
    "if_adjusted",
    "rice_create_tm",
    "order_book_id",
)
STARTER_HK_FINANCIAL_FIELDS = (
    "revenue",
    "operating_revenue",
    "operating_profit",
    "net_profit",
    "basic_earnings_per_share",
    "dividend_per_share",
    "total_assets",
    "total_liabilities",
    "total_equity",
    "cash_and_equivalents",
    "cash_flow_from_operating_activities",
    "inventory",
    "accounts_receivable",
    "accounts_payable",
    "short_term_debt",
    "long_term_loans",
    "goodwill",
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


@dataclass(frozen=True)
class MirrorAuditRecord:
    ts_code: str
    order_book_id: str
    status: str
    attempts: int
    rows: int
    total_bytes: int
    min_quarter: str | None
    max_quarter: str | None
    min_info_date: str | None
    max_info_date: str | None
    started_at: str | None
    finished_at: str | None
    file_mtime: str | None
    dropped_fields: str | None
    error: str | None


class MirrorFetchError(RuntimeError):
    def __init__(self, message: str, *, attempts: int):
        super().__init__(message)
        self.attempts = attempts


class MirrorQuotaError(MirrorFetchError):
    pass


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


def _normalize_field_name(value: object) -> str:
    return str(value or "").strip()


def _normalize_field_list(values: Iterable[object]) -> list[str]:
    return _dedupe_preserve_order(_normalize_field_name(value) for value in values)


def _normalize_frame_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty and len(frame.columns) == 0:
        return frame.copy()
    normalized_names = [_normalize_field_name(column) or str(column) for column in frame.columns]
    if normalized_names == [str(column) for column in frame.columns] and len(set(normalized_names)) == len(
        normalized_names
    ):
        return frame.copy()
    if len(set(normalized_names)) == len(normalized_names):
        normalized = frame.copy()
        normalized.columns = normalized_names
        return normalized

    groups: dict[str, list[pd.Series]] = {}
    order: list[str] = []
    for idx, column_name in enumerate(normalized_names):
        series = frame.iloc[:, idx].copy()
        series.name = column_name
        if column_name not in groups:
            groups[column_name] = [series]
            order.append(column_name)
        else:
            groups[column_name].append(series)

    merged: list[pd.Series] = []
    for column_name in order:
        combined = groups[column_name][0]
        for series in groups[column_name][1:]:
            combined = combined.combine_first(series)
        combined.name = column_name
        merged.append(combined)
    return pd.concat(merged, axis=1) if merged else pd.DataFrame(index=frame.index)


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

    columns = {str(col).lower(): str(col) for col in df.columns}
    date_col, symbol_col = _resolve_universe_by_date_columns(df)

    selected_col = (
        columns.get("selected")
        or columns.get("selected_bool")
        or columns.get("selected_flag")
        or columns.get("is_selected")
    )
    if selected_col and selected_col in df.columns:
        df = df[df[selected_col].map(_coerce_bool)].copy()

    df = df.rename(columns={date_col: "trade_date", symbol_col: "ts_code"})
    trade_date_text = (
        df["trade_date"].astype(str).str.strip().str.replace(r"\.0+$", "", regex=True)
    )
    digits_mask = trade_date_text.str.fullmatch(r"\d{8}")
    parsed = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    if digits_mask.any():
        parsed.loc[digits_mask] = pd.to_datetime(
            trade_date_text.loc[digits_mask],
            format="%Y%m%d",
            errors="coerce",
        )
    if (~digits_mask).any():
        parsed.loc[~digits_mask] = pd.to_datetime(
            trade_date_text.loc[~digits_mask],
            errors="coerce",
        )
    df["trade_date"] = parsed
    df = df[df["trade_date"].notna()].copy()
    df["ts_code"] = df["ts_code"].astype(str).str.strip()
    df["ts_code"] = df["ts_code"].map(_normalize_hk_symbol)
    df = df[df["ts_code"] != ""].copy()
    return df["ts_code"].drop_duplicates().tolist()


def _resolve_universe_by_date_columns(df: pd.DataFrame) -> tuple[str, str]:
    columns = {str(col).lower(): str(col) for col in df.columns}
    date_col = columns.get("trade_date") or columns.get("date") or columns.get("rebalance_date")
    symbol_col = (
        columns.get("ts_code")
        or columns.get("stock_ticker")
        or columns.get("symbol")
        or columns.get("order_book_id")
    )
    if not date_col or not symbol_col:
        raise SystemExit("Universe-by-date file must include date + symbol columns.")
    return date_col, symbol_col


def _dedupe_preserve_order(values: Iterable[str], *, strip: bool = True) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "")
        normalized = text.strip() if strip else text
        if not normalized or normalized in seen:
            continue
        deduped.append(normalized if strip else text)
        seen.add(normalized)
    return deduped


def _load_field_profile(profile_name: str) -> list[str]:
    profile = str(profile_name or "").strip().lower()
    if profile == "starter":
        return list(STARTER_HK_FINANCIAL_FIELDS)
    if profile == "full":
        return _load_hk_financial_fields()
    raise SystemExit(f"Unsupported --field-profile: {profile_name}")


def _resolve_fields(args) -> tuple[list[str], dict]:
    fields: list[str] = []
    field_profiles = [
        str(item).strip().lower()
        for item in (getattr(args, "field_profile", None) or [])
        if str(item).strip()
    ]
    for profile_name in field_profiles:
        fields.extend(_load_field_profile(profile_name))
    if getattr(args, "field", None):
        fields.extend(str(item).strip() for item in args.field if str(item).strip())
    for path_text in getattr(args, "fields_file", None) or []:
        fields.extend(_load_text_list(path_text, label="Fields file"))
    fields = _dedupe_preserve_order(fields, strip=False)
    if not fields:
        raise SystemExit("Provide at least one --field or --fields-file.")
    metadata = {
        "count": len(fields),
        "field_profile": field_profiles,
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


def _timestamp_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _path_mtime_iso(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
    except OSError:
        return None


def _looks_like_quota_error(exc: Exception) -> bool:
    text = str(exc).strip().lower()
    if not text:
        return False
    quota_terms = (
        "quota",
        "bytes_limit",
        "bytes_used",
        "traffic",
        "流量",
        "配额",
        "限额",
    )
    exhaustion_terms = (
        "exceed",
        "exceeded",
        "used up",
        "用完",
        "超出",
        "达到",
        "不足",
        "limit",
    )
    return any(term in text for term in quota_terms) and any(term in text for term in exhaustion_terms)


def _extract_invalid_field_name(error_text: str) -> str | None:
    if not error_text:
        return None
    match = re.search(r"got invalided value ([^,\s]+)", str(error_text), flags=re.IGNORECASE)
    if not match:
        return None
    field = str(match.group(1)).strip()
    return field or None


def _retry_fetch(
    label: str,
    action,
    *,
    max_attempts: int,
    backoff_seconds: float,
    max_backoff_seconds: float,
):
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return action(), attempt
        except Exception as exc:
            last_exc = exc
            if _looks_like_quota_error(exc):
                raise MirrorQuotaError(str(exc), attempts=attempt) from exc
            if attempt < max_attempts:
                sleep_for = min(backoff_seconds * (2 ** (attempt - 1)), max_backoff_seconds)
                if sleep_for > 0:
                    time.sleep(sleep_for)
    if last_exc is not None:
        raise MirrorFetchError(f"{label}: {last_exc}", attempts=max_attempts) from last_exc
    raise MirrorFetchError(f"{label}: unknown error", attempts=max_attempts)


def _prepare_output_dir(
    *,
    out_root: str,
    dataset_name: str,
    start_quarter: str,
    end_quarter: str,
    statements: str,
    name: str | None,
    resume: bool,
) -> Path:
    root = _resolve_path(out_root)
    snapshot_name = name or _default_snapshot_name(dataset_name, start_quarter, end_quarter, statements)
    output_dir = root / "hk" / dataset_name / snapshot_name
    if output_dir.exists():
        if not resume:
            raise SystemExit(f"Refusing to overwrite existing output: {output_dir}")
        if not output_dir.is_dir():
            raise SystemExit(f"Resume target is not a directory: {output_dir}")
    else:
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
    if frame.empty and len(frame.columns) == 0:
        return frame.copy()

    normalized = _normalize_frame_columns(frame.reset_index())
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


def _ensure_requested_fields(frame: pd.DataFrame, fields: Sequence[str]) -> pd.DataFrame:
    requested_fields = _field_columns_for_audit(fields)
    missing_fields = [field for field in requested_fields if field not in frame.columns]
    if not missing_fields:
        return frame.copy()
    extras = pd.DataFrame({field: pd.Series(pd.NA, index=frame.index) for field in missing_fields})
    return pd.concat([frame.copy(), extras], axis=1)


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


def _field_columns_for_audit(fields: Sequence[str]) -> list[str]:
    return [str(field) for field in fields if str(field).strip()]


def _entry_from_symbol_frame(out_path: Path, symbol_frame: pd.DataFrame) -> MirrorEntry:
    ts_code = str(symbol_frame["ts_code"].iloc[0])
    order_book_id = str(symbol_frame["order_book_id"].iloc[0]) if "order_book_id" in symbol_frame.columns else _to_rqdata_symbol("hk", ts_code)
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


def _write_symbol_frame(data_dir: Path, symbol_frame: pd.DataFrame) -> MirrorEntry:
    ts_code = str(symbol_frame["ts_code"].iloc[0])
    out_path = data_dir / f"{ts_code}.parquet"
    symbol_frame.to_parquet(out_path, index=False)
    return _entry_from_symbol_frame(out_path, symbol_frame)


def _load_symbol_frame(path: Path, *, fields: Sequence[str]) -> pd.DataFrame:
    columns = ["ts_code", "order_book_id", "quarter", "info_date", *_field_columns_for_audit(fields)]
    requested = []
    seen: set[str] = set()
    for column in columns:
        if column and column not in seen:
            requested.append(column)
            seen.add(column)
    try:
        frame = pd.read_parquet(path, columns=requested)
    except Exception:
        frame = pd.read_parquet(path)
    return _normalize_frame_columns(frame)


def _load_existing_entry(path: Path, *, fields: Sequence[str]) -> tuple[MirrorEntry, pd.DataFrame]:
    frame = _ensure_requested_fields(_load_symbol_frame(path, fields=fields), fields)
    if frame.empty:
        ts_code = path.stem
        order_book_id = _to_rqdata_symbol("hk", ts_code)
        entry = MirrorEntry(
            ts_code=ts_code,
            order_book_id=order_book_id,
            path=path,
            rows=0,
            total_bytes=int(path.stat().st_size),
            min_quarter=None,
            max_quarter=None,
            min_info_date=None,
            max_info_date=None,
        )
        return entry, frame
    return _entry_from_symbol_frame(path, frame), frame


def _field_coverage_template(fields: Sequence[str]) -> dict[str, dict[str, int | str]]:
    return {
        field: {"field": field, "nonnull_rows": 0, "symbols_with_values": 0}
        for field in _field_columns_for_audit(fields)
    }


def _update_field_coverage(
    coverage: dict[str, dict[str, int | str]],
    frame: pd.DataFrame,
    *,
    fields: Sequence[str],
) -> None:
    for field in _field_columns_for_audit(fields):
        if field not in coverage or field not in frame.columns:
            continue
        nonnull_rows = int(frame[field].notna().sum())
        coverage[field]["nonnull_rows"] = int(coverage[field]["nonnull_rows"]) + nonnull_rows
        if nonnull_rows > 0:
            coverage[field]["symbols_with_values"] = int(coverage[field]["symbols_with_values"]) + 1


def _audit_record(
    *,
    ts_code: str,
    order_book_id: str,
    status: str,
    attempts: int,
    started_at: str | None,
    finished_at: str | None,
    file_mtime: str | None,
    dropped_fields: Sequence[str] | None = None,
    error: str | None,
    entry: MirrorEntry | None = None,
) -> MirrorAuditRecord:
    return MirrorAuditRecord(
        ts_code=ts_code,
        order_book_id=order_book_id,
        status=status,
        attempts=attempts,
        rows=entry.rows if entry else 0,
        total_bytes=entry.total_bytes if entry else 0,
        min_quarter=entry.min_quarter if entry else None,
        max_quarter=entry.max_quarter if entry else None,
        min_info_date=entry.min_info_date if entry else None,
        max_info_date=entry.max_info_date if entry else None,
        started_at=started_at,
        finished_at=finished_at,
        file_mtime=file_mtime,
        dropped_fields=",".join(str(item) for item in (dropped_fields or []) if str(item).strip()) or None,
        error=error,
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


def _write_audit_csv(path: Path, records: Sequence[MirrorAuditRecord]) -> None:
    rows = [
        {
            "ts_code": item.ts_code,
            "order_book_id": item.order_book_id,
            "status": item.status,
            "attempts": item.attempts,
            "rows": item.rows,
            "total_bytes": item.total_bytes,
            "min_quarter": item.min_quarter,
            "max_quarter": item.max_quarter,
            "min_info_date": item.min_info_date,
            "max_info_date": item.max_info_date,
            "started_at": item.started_at,
            "finished_at": item.finished_at,
            "file_mtime": item.file_mtime,
            "dropped_fields": item.dropped_fields,
            "error": item.error,
        }
        for item in records
    ]
    pd.DataFrame(rows).to_csv(path, index=False)


def _load_existing_text_list(path: Path) -> list[str]:
    if not path.exists():
        return []
    values: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                values.append(text)
    return values


def _validate_resume_inputs(
    *,
    output_dir: Path,
    dataset_name: str,
    fields: Sequence[str],
    symbols: Sequence[str],
    start_quarter: str,
    end_quarter: str,
    statements: str,
    query_date: str | None,
) -> None:
    manifest = _load_manifest(output_dir / "manifest.yml")
    if manifest and manifest.get("dataset") not in {None, dataset_name}:
        raise SystemExit(
            f"Resume target dataset mismatch: expected {dataset_name!r}, got {manifest.get('dataset')!r}."
        )
    if manifest:
        query = manifest.get("query") if isinstance(manifest.get("query"), Mapping) else {}
        checks = [
            ("start_quarter", start_quarter),
            ("end_quarter", end_quarter),
            ("statements", statements),
            ("date", query_date),
        ]
        for key, expected in checks:
            actual = query.get(key) if isinstance(query, Mapping) else None
            if actual not in {None, expected}:
                raise SystemExit(
                    f"Resume target query mismatch for {key}: expected {expected!r}, got {actual!r}."
                )

    existing_fields = _load_existing_text_list(output_dir / "fields.txt")
    if existing_fields and list(existing_fields) != list(fields):
        raise SystemExit("Resume target fields.txt does not match the requested field list.")
    existing_symbols = _load_existing_text_list(output_dir / "symbols.txt")
    if existing_symbols and list(existing_symbols) != list(symbols):
        raise SystemExit("Resume target symbols.txt does not match the requested symbol list.")


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
    audit_file: Path,
    audit_records: Sequence[MirrorAuditRecord],
    field_coverage: Sequence[Mapping[str, object]],
    started_at: str,
    finished_at: str,
    status: str,
    error: str | None,
    config_ref: str | None,
) -> dict:
    status_counts = Counter(item.status for item in audit_records)
    return {
        "name": output_dir.name,
        "created_at": finished_at,
        "started_at": started_at,
        "finished_at": finished_at,
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
            "field_profile": list(field_metadata.get("field_profile") or []),
            "fields_file": list(field_metadata.get("fields_file") or []),
        },
        "symbol_source": dict(symbol_metadata),
        "columns": list(columns),
        "audit_file": str(audit_file),
        "status_counts": dict(status_counts),
        "field_coverage": list(field_coverage),
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
        "failed_symbols": [item.ts_code for item in audit_records if item.status == "failed"],
        "quota_blocked_symbols": [
            item.ts_code for item in audit_records if item.status == "quota_blocked"
        ],
        "totals": {
            "symbols_requested": len(symbols_requested),
            "symbols_written": len(entries),
            "symbols_newly_written": int(status_counts.get("written", 0)),
            "symbols_skipped_existing": int(status_counts.get("skipped_existing", 0)),
            "symbols_missing_remote": int(status_counts.get("missing_remote", 0)),
            "symbols_failed": int(status_counts.get("failed", 0)),
            "symbols_quota_blocked": int(status_counts.get("quota_blocked", 0)),
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
    resume = bool(getattr(args, "resume", False))
    skip_existing = bool(getattr(args, "skip_existing", False) or resume)
    max_attempts = max(1, int(getattr(args, "max_attempts", DEFAULT_MIRROR_MAX_ATTEMPTS) or 1))
    backoff_seconds = float(getattr(args, "backoff_seconds", DEFAULT_MIRROR_BACKOFF_SECONDS))
    max_backoff_seconds = float(
        getattr(args, "max_backoff_seconds", DEFAULT_MIRROR_MAX_BACKOFF_SECONDS)
    )
    output_dir = _prepare_output_dir(
        out_root=getattr(args, "out_root", DEFAULT_OUT_ROOT),
        dataset_name=dataset_name,
        start_quarter=args.start_quarter,
        end_quarter=args.end_quarter,
        statements=args.statements,
        name=getattr(args, "name", None),
        resume=resume,
    )
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    audit_path = output_dir / "audit.csv"

    symbol_map = {_to_rqdata_symbol("hk", symbol): symbol for symbol in symbols}
    order_book_ids = list(symbol_map.keys())
    entries_by_symbol: dict[str, MirrorEntry] = {}
    audit_by_symbol: dict[str, MirrorAuditRecord] = {}
    batches: list[dict[str, object]] = []
    columns: list[str] = []
    field_coverage = _field_coverage_template(fields)
    started_at = _timestamp_now()
    status = "completed"
    error: str | None = None
    result_code = 0
    quota_blocked = False

    def _record_entry(
        *,
        symbol: str,
        entry: MirrorEntry,
        symbol_frame: pd.DataFrame,
        record_status: str,
        attempts: int,
        started_at_value: str | None,
        finished_at_value: str | None,
        dropped_fields: Sequence[str] | None = None,
        error_text: str | None = None,
    ) -> None:
        nonlocal columns
        entries_by_symbol[symbol] = entry
        if not columns and not symbol_frame.empty:
            columns = symbol_frame.columns.tolist()
        _update_field_coverage(field_coverage, symbol_frame, fields=fields)
        audit_by_symbol[symbol] = _audit_record(
            ts_code=symbol,
            order_book_id=entry.order_book_id,
            status=record_status,
            attempts=attempts,
            started_at=started_at_value,
            finished_at=finished_at_value,
            file_mtime=_path_mtime_iso(entry.path),
            dropped_fields=dropped_fields,
            error=error_text,
            entry=entry,
        )

    def _record_non_entry(
        *,
        symbol: str,
        order_book_id: str,
        record_status: str,
        attempts: int,
        started_at_value: str | None,
        finished_at_value: str | None,
        dropped_fields: Sequence[str] | None = None,
        error_text: str | None = None,
    ) -> None:
        audit_by_symbol[symbol] = _audit_record(
            ts_code=symbol,
            order_book_id=order_book_id,
            status=record_status,
            attempts=attempts,
            started_at=started_at_value,
            finished_at=finished_at_value,
            file_mtime=None,
            dropped_fields=dropped_fields,
            error=error_text,
            entry=None,
        )

    def _fetch_single_symbol_with_field_fallback(
        order_book_id: str,
    ) -> tuple[pd.DataFrame, int, list[str]]:
        active_fields = list(fields)
        dropped_fields: list[str] = []
        total_attempts = 0
        while True:
            label = f"{dataset_name} fetch failed for {order_book_id}"
            try:
                payload, attempts = _retry_fetch(
                    label,
                    lambda: fetch_batch(
                        [order_book_id],
                        active_fields,
                        args.start_quarter,
                        args.end_quarter,
                        date=getattr(args, "date", None),
                        statements=args.statements,
                    ),
                    max_attempts=max_attempts,
                    backoff_seconds=backoff_seconds,
                    max_backoff_seconds=max_backoff_seconds,
                )
            except MirrorQuotaError as exc:
                raise MirrorQuotaError(str(exc), attempts=total_attempts + exc.attempts) from exc
            except MirrorFetchError as exc:
                invalid_field = _extract_invalid_field_name(str(exc))
                total_attempts += exc.attempts
                if invalid_field and invalid_field in active_fields and len(active_fields) > 1:
                    active_fields = [field for field in active_fields if field != invalid_field]
                    dropped_fields.append(invalid_field)
                    continue
                raise MirrorFetchError(str(exc), attempts=total_attempts) from exc
            total_attempts += attempts
            prepared = _prepare_asset_frame(payload, symbol_map=symbol_map)
            prepared = _ensure_requested_fields(prepared, fields)
            return prepared, total_attempts, dropped_fields

    def _process_batch(batch_order_book_ids: list[str]) -> None:
        nonlocal status, error, result_code, quota_blocked, columns
        if not batch_order_book_ids or quota_blocked:
            return
        batch_started_at = _timestamp_now()
        dropped_fields: list[str] = []
        try:
            if len(batch_order_book_ids) == 1:
                payload, attempts, dropped_fields = _fetch_single_symbol_with_field_fallback(
                    batch_order_book_ids[0]
                )
            else:
                label = f"{dataset_name} fetch failed for {', '.join(batch_order_book_ids)}"
                payload, attempts = _retry_fetch(
                    label,
                    lambda: fetch_batch(
                        batch_order_book_ids,
                        fields,
                        args.start_quarter,
                        args.end_quarter,
                        date=getattr(args, "date", None),
                        statements=args.statements,
                    ),
                    max_attempts=max_attempts,
                    backoff_seconds=backoff_seconds,
                    max_backoff_seconds=max_backoff_seconds,
                )
        except MirrorQuotaError as exc:
            batch_finished_at = _timestamp_now()
            quota_blocked = True
            status = "stopped_quota"
            error = str(exc)
            result_code = max(result_code, 2)
            for order_book_id in batch_order_book_ids:
                symbol = symbol_map[order_book_id]
                if symbol in audit_by_symbol:
                    continue
                _record_non_entry(
                    symbol=symbol,
                    order_book_id=order_book_id,
                    record_status="quota_blocked",
                    attempts=exc.attempts,
                    started_at_value=batch_started_at,
                    finished_at_value=batch_finished_at,
                    dropped_fields=dropped_fields,
                    error_text=str(exc),
                )
            batches.append(
                {
                    "order_book_ids": len(batch_order_book_ids),
                    "rows": 0,
                    "symbols_written": 0,
                    "symbols_missing_remote": 0,
                    "status": "quota_blocked",
                    "attempts": exc.attempts,
                    "dropped_fields": list(dropped_fields),
                    "error": str(exc),
                }
            )
            return
        except MirrorFetchError as exc:
            batch_finished_at = _timestamp_now()
            if len(batch_order_book_ids) > 1:
                batches.append(
                    {
                        "order_book_ids": len(batch_order_book_ids),
                        "rows": 0,
                        "symbols_written": 0,
                        "symbols_missing_remote": 0,
                        "status": "split_after_error",
                        "attempts": exc.attempts,
                        "error": str(exc),
                    }
                )
                for order_book_id in batch_order_book_ids:
                    _process_batch([order_book_id])
                    if quota_blocked:
                        break
                return

            order_book_id = batch_order_book_ids[0]
            symbol = symbol_map[order_book_id]
            _record_non_entry(
                symbol=symbol,
                order_book_id=order_book_id,
                record_status="failed",
                attempts=exc.attempts,
                started_at_value=batch_started_at,
                finished_at_value=batch_finished_at,
                dropped_fields=dropped_fields,
                error_text=str(exc),
            )
            batches.append(
                {
                    "order_book_ids": 1,
                    "rows": 0,
                    "symbols_written": 0,
                    "symbols_missing_remote": 0,
                    "status": "failed",
                    "attempts": exc.attempts,
                    "dropped_fields": list(dropped_fields),
                    "error": str(exc),
                }
            )
            if status == "completed":
                status = "completed_with_failures"
            result_code = max(result_code, 1)
            return

        batch_finished_at = _timestamp_now()
        prepared = _prepare_asset_frame(payload, symbol_map=symbol_map)
        prepared = _ensure_requested_fields(prepared, fields)
        if prepared.empty:
            for order_book_id in batch_order_book_ids:
                symbol = symbol_map[order_book_id]
                _record_non_entry(
                    symbol=symbol,
                    order_book_id=order_book_id,
                    record_status="missing_remote",
                    attempts=attempts,
                    started_at_value=batch_started_at,
                    finished_at_value=batch_finished_at,
                    dropped_fields=dropped_fields,
                )
            batches.append(
                {
                    "order_book_ids": len(batch_order_book_ids),
                    "rows": 0,
                    "symbols_written": 0,
                    "symbols_missing_remote": len(batch_order_book_ids),
                    "status": "empty",
                    "attempts": attempts,
                    "dropped_fields": list(dropped_fields),
                }
            )
            return

        if not columns:
            columns = prepared.columns.tolist()

        batch_rows = int(len(prepared))
        batch_symbols_written = 0
        batch_symbols_missing = 0
        for order_book_id in batch_order_book_ids:
            symbol = symbol_map[order_book_id]
            symbol_frame = prepared[prepared["ts_code"] == symbol].reset_index(drop=True)
            if symbol_frame.empty:
                batch_symbols_missing += 1
                _record_non_entry(
                    symbol=symbol,
                    order_book_id=order_book_id,
                    record_status="missing_remote",
                    attempts=attempts,
                    started_at_value=batch_started_at,
                    finished_at_value=batch_finished_at,
                    dropped_fields=dropped_fields,
                )
                continue
            entry = _write_symbol_frame(data_dir, symbol_frame)
            _record_entry(
                symbol=symbol,
                entry=entry,
                symbol_frame=symbol_frame,
                record_status="written",
                attempts=attempts,
                started_at_value=batch_started_at,
                finished_at_value=batch_finished_at,
                dropped_fields=dropped_fields,
            )
            batch_symbols_written += 1

        batches.append(
            {
                "order_book_ids": len(batch_order_book_ids),
                "rows": batch_rows,
                "symbols_written": batch_symbols_written,
                "symbols_missing_remote": batch_symbols_missing,
                "status": "completed",
                "attempts": attempts,
                "dropped_fields": list(dropped_fields),
            }
        )

    try:
        if resume:
            _validate_resume_inputs(
                output_dir=output_dir,
                dataset_name=dataset_name,
                fields=fields,
                symbols=symbols,
                start_quarter=args.start_quarter,
                end_quarter=args.end_quarter,
                statements=args.statements,
                query_date=getattr(args, "date", None),
            )

        _write_text_list(output_dir / "fields.txt", fields)
        _write_text_list(output_dir / "symbols.txt", symbols)

        pending_order_book_ids: list[str] = []
        for order_book_id in order_book_ids:
            symbol = symbol_map[order_book_id]
            out_path = data_dir / f"{symbol}.parquet"
            if skip_existing and out_path.exists():
                try:
                    entry, symbol_frame = _load_existing_entry(out_path, fields=fields)
                except Exception:
                    pending_order_book_ids.append(order_book_id)
                    continue
                _record_entry(
                    symbol=symbol,
                    entry=entry,
                    symbol_frame=symbol_frame,
                    record_status="skipped_existing",
                    attempts=0,
                    started_at_value=None,
                    finished_at_value=_path_mtime_iso(out_path),
                )
                continue
            pending_order_book_ids.append(order_book_id)

        for batch_order_book_ids in _chunked(
            pending_order_book_ids,
            getattr(args, "batch_size", DEFAULT_BATCH_SIZE),
        ):
            _process_batch(batch_order_book_ids)
            if quota_blocked:
                break

        if quota_blocked:
            quota_finished_at = _timestamp_now()
            for order_book_id in pending_order_book_ids:
                symbol = symbol_map[order_book_id]
                if symbol in audit_by_symbol:
                    continue
                _record_non_entry(
                    symbol=symbol,
                    order_book_id=order_book_id,
                    record_status="quota_blocked",
                    attempts=0,
                    started_at_value=None,
                    finished_at_value=quota_finished_at,
                    error_text=error,
                )
        elif result_code == 1 and status == "completed":
            status = "completed_with_failures"
    except Exception as exc:
        status = "failed"
        error = str(exc)
        result_code = max(result_code, 1)
        raise
    finally:
        finished_at = _timestamp_now()
        for order_book_id in order_book_ids:
            symbol = symbol_map[order_book_id]
            if symbol in audit_by_symbol:
                continue
            _record_non_entry(
                symbol=symbol,
                order_book_id=order_book_id,
                record_status="failed",
                attempts=0,
                started_at_value=None,
                finished_at_value=finished_at,
                error_text=error or "missing audit status",
            )
        audit_records = [audit_by_symbol[symbol] for symbol in symbols]
        _write_audit_csv(audit_path, audit_records)
        manifest = _build_manifest(
            dataset_name=dataset_name,
            api_name=api_name,
            output_dir=output_dir,
            fields=fields,
            field_metadata=field_metadata,
            symbol_metadata=symbol_metadata,
            symbols_requested=symbols,
            entries=[entries_by_symbol[symbol] for symbol in symbols if symbol in entries_by_symbol],
            missing_symbols=[item.ts_code for item in audit_records if item.status == "missing_remote"],
            query_date=getattr(args, "date", None),
            start_quarter=args.start_quarter,
            end_quarter=args.end_quarter,
            statements=args.statements,
            batches=batches,
            columns=columns,
            audit_file=audit_path,
            audit_records=audit_records,
            field_coverage=list(field_coverage.values()),
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            error=error,
            config_ref=getattr(args, "config", None),
        )
        _write_manifest(output_dir / "manifest.yml", manifest)

    totals = {
        "files": len(entries_by_symbol),
        "symbols": len(entries_by_symbol),
        "rows": sum(item.rows for item in entries_by_symbol.values()),
        "bytes": sum(item.total_bytes for item in entries_by_symbol.values()),
    }
    print(
        f"Wrote {dataset_name} mirror to {output_dir} "
        f"({totals['symbols']} symbols, {totals['files']} files, {totals['rows']} rows, {totals['bytes']} bytes, status={status})"
    )
    return result_code


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
        fields = _normalize_field_list(fields)
        metadata["source"] = "explicit"
    else:
        manifest_fields: list[str] = []
        if manifest:
            query = manifest.get("query")
            if isinstance(query, Mapping):
                raw_fields = query.get("fields")
                if isinstance(raw_fields, Sequence) and not isinstance(raw_fields, str):
                    manifest_fields = [str(item) for item in raw_fields]
        fields = _normalize_field_list(manifest_fields)
        source = "asset_manifest"
        if not fields:
            excluded = {"ts_code", "order_book_id", *PIT_METADATA_COLUMNS}
            fields = [
                field
                for field in _normalize_field_list(available_columns)
                if field not in excluded
            ]
            source = "inferred"
        metadata = {"count": len(fields), "fields_file": [], "source": source}
    if not fields:
        raise SystemExit("No PIT value fields resolved for building fundamentals.")
    available = set(_normalize_field_list(available_columns))
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


def _write_symbol_list(path: Path, symbols: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(str(symbol).strip() for symbol in symbols if str(symbol).strip())
    if content:
        content += "\n"
    path.write_text(content, encoding="utf-8")


def _build_filtered_universe_by_date(
    *,
    source_path: Path,
    out_path: Path,
    symbols: Sequence[str],
) -> dict[str, object]:
    universe = pd.read_csv(source_path)
    date_col, symbol_col = _resolve_universe_by_date_columns(universe)
    normalized_symbols = universe[symbol_col].astype(str).map(_normalize_hk_symbol)
    selected_symbols = set(symbols)
    filtered = universe.loc[normalized_symbols.isin(selected_symbols)].copy()
    filtered["ts_code"] = normalized_symbols.loc[filtered.index]
    if "stock_ticker" in filtered.columns:
        filtered["stock_ticker"] = filtered["ts_code"]

    preferred = []
    seen: set[str] = set()
    for column in [date_col, "ts_code", *filtered.columns]:
        if column in filtered.columns and column not in seen:
            preferred.append(column)
            seen.add(column)
    filtered = filtered.loc[:, preferred]
    filtered = filtered.drop_duplicates().reset_index(drop=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    filtered.to_csv(out_path, index=False)
    return {
        "source_path": str(source_path),
        "output_path": str(out_path),
        "rows": int(len(filtered)),
        "symbols": int(filtered["ts_code"].nunique()) if not filtered.empty else 0,
        "date_column": date_col,
        "symbol_column": symbol_col,
    }


def build_hk_pit_fundamentals_file(args) -> int:
    asset_dir, source_manifest = _resolve_pit_asset_dir(args.asset_dir)
    data_dir = asset_dir / "data"
    data_files = sorted(data_dir.glob("*.parquet"))
    if not data_files:
        raise SystemExit(f"No parquet files found under {data_dir}")

    first_frame = _normalize_frame_columns(pd.read_parquet(data_files[0]))
    available_columns = list(source_manifest.get("columns") or []) if source_manifest else []
    if not available_columns:
        available_columns = first_frame.columns.tolist()
    fields, field_metadata = _resolve_build_fields(
        args=args,
        manifest=source_manifest,
        available_columns=available_columns,
    )

    out_path = _resolve_pipeline_fundamentals_out_path(args, asset_dir)
    force = bool(getattr(args, "force", False))
    if out_path.exists() and not force:
        raise SystemExit(f"Refusing to overwrite existing output: {out_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    symbols_out_path = _resolve_path(args.symbols_out) if getattr(args, "symbols_out", None) else None
    if symbols_out_path and symbols_out_path.exists() and not force:
        raise SystemExit(f"Refusing to overwrite existing output: {symbols_out_path}")
    source_universe_path = (
        _resolve_path(args.source_universe_by_date)
        if getattr(args, "source_universe_by_date", None)
        else None
    )
    universe_out_path = (
        _resolve_path(args.universe_by_date_out)
        if getattr(args, "universe_by_date_out", None)
        else None
    )
    if universe_out_path and source_universe_path is None:
        raise SystemExit("--source-universe-by-date is required when --universe-by-date-out is set.")
    if source_universe_path and not source_universe_path.exists():
        raise SystemExit(f"Universe-by-date file not found: {source_universe_path}")
    if universe_out_path and universe_out_path.exists() and not force:
        raise SystemExit(f"Refusing to overwrite existing output: {universe_out_path}")

    combined_frames: list[pd.DataFrame] = []
    input_rows = 0
    dropped_missing_info_date = 0
    dropped_all_missing_fields = 0
    cached_frames: dict[Path, pd.DataFrame] = {data_files[0]: first_frame}
    keep_meta = bool(getattr(args, "keep_meta", False))

    for data_file in data_files:
        frame = cached_frames.get(data_file)
        if frame is None:
            frame = _normalize_frame_columns(pd.read_parquet(data_file))
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
    research_symbols = sorted(output_df["ts_code"].astype(str).str.strip().unique().tolist()) if not output_df.empty else []

    if out_path.suffix.lower() == ".csv":
        output_df.to_csv(out_path, index=False)
        output_format = "csv"
    else:
        output_df.to_parquet(out_path, index=False)
        output_format = "parquet"

    outputs = {"pipeline_fundamentals": str(out_path)}
    if symbols_out_path:
        _write_symbol_list(symbols_out_path, research_symbols)
        outputs["symbols_file"] = str(symbols_out_path)
    filtered_universe = None
    if source_universe_path and universe_out_path:
        filtered_universe = _build_filtered_universe_by_date(
            source_path=source_universe_path,
            out_path=universe_out_path,
            symbols=research_symbols,
        )
        outputs["universe_by_date_file"] = str(universe_out_path)

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
            "field_profile": list(field_metadata.get("field_profile") or []),
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
        "outputs": outputs,
        "filtered_universe": filtered_universe,
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
        "--field-profile",
        action="append",
        choices=["starter", "full"],
        default=[],
        help="Bundled HK financial field set. starter=repo baseline, full=all fields exposed by local rqdatac metadata.",
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
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume into an existing snapshot directory. Requires matching fields, symbols, and query settings.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip symbols whose parquet files already exist under data/. Implied by --resume.",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=DEFAULT_MIRROR_MAX_ATTEMPTS,
        help=f"Retry attempts per request batch. Default: {DEFAULT_MIRROR_MAX_ATTEMPTS}.",
    )
    parser.add_argument(
        "--backoff-seconds",
        type=float,
        default=DEFAULT_MIRROR_BACKOFF_SECONDS,
        help=f"Initial retry backoff in seconds. Default: {DEFAULT_MIRROR_BACKOFF_SECONDS}.",
    )
    parser.add_argument(
        "--max-backoff-seconds",
        type=float,
        default=DEFAULT_MIRROR_MAX_BACKOFF_SECONDS,
        help=f"Maximum retry backoff in seconds. Default: {DEFAULT_MIRROR_MAX_BACKOFF_SECONDS}.",
    )


def add_hk_pit_fundamentals_build_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--asset-dir",
        required=True,
        help="Path to a mirror-hk-pit-financials output directory.",
    )
    parser.add_argument(
        "--field-profile",
        action="append",
        choices=["starter", "full"],
        default=[],
        help="Bundled HK financial field set. starter=repo baseline, full=all fields exposed by local rqdatac metadata.",
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
        "--source-universe-by-date",
        help="Optional source universe-by-date CSV. Use with --universe-by-date-out to derive a research-ready PIT universe.",
    )
    parser.add_argument(
        "--universe-by-date-out",
        help="Optional filtered universe-by-date CSV output. Requires --source-universe-by-date.",
    )
    parser.add_argument(
        "--symbols-out",
        help="Optional text file output with one ts_code per line for symbols present in the derived fundamentals file.",
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
