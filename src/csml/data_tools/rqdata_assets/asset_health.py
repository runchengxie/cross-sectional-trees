from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

import pandas as pd

from .shared import (
    DEFAULT_HK_DAILY_FIELDS,
    DEFAULT_HK_VALUATION_FIELDS,
    _load_manifest,
    _normalize_absolute_date,
    _normalize_frame_columns,
    _normalize_hk_symbol,
    _resolve_path,
)

DATE_COLUMN_CANDIDATES = ("trade_date", "date", "info_date")
AUDIT_LATEST_DATE_COLUMNS = ("max_trade_date", "max_date", "max_info_date")
AUDIT_SYMBOL_COLUMNS = ("symbol", "ts_code", "order_book_id")
KEY_COLUMNS = {
    "symbol",
    "ts_code",
    "stock_ticker",
    "order_book_id",
    "trade_date",
    "date",
    "info_date",
    "quarter",
    "fiscal_year",
    "rice_create_tm",
    "standard",
    "if_adjusted",
    "index",
}


def _parse_compact_date(value: object, *, label: str) -> pd.Timestamp:
    normalized = _normalize_absolute_date(value, label=label)
    return pd.to_datetime(normalized, format="%Y%m%d").normalize()


def _format_date(value: object) -> str | None:
    text = str(value or "").strip()
    if not text or text.lower() == "nan":
        return None
    timestamp = pd.to_datetime(text, errors="coerce")
    if pd.isna(timestamp):
        return None
    return timestamp.normalize().strftime("%Y-%m-%d")


def _resolve_manifest_query_date(manifest: Mapping[str, object] | None) -> str | None:
    if not isinstance(manifest, Mapping):
        return None
    query = manifest.get("query")
    if not isinstance(query, Mapping):
        return None
    for key in ("end_date", "date", "mapping_date", "as_of_date"):
        value = query.get(key)
        if value is None:
            continue
        try:
            return _format_date(_parse_compact_date(value, label=f"manifest.query.{key}"))
        except SystemExit:
            continue
    return None


def _infer_date_column(columns: Sequence[str], explicit: str | None) -> str:
    if explicit:
        if explicit not in columns:
            raise SystemExit(f"Date column not found in asset schema: {explicit}")
        return explicit
    for candidate in DATE_COLUMN_CANDIDATES:
        if candidate in columns:
            return candidate
    raise SystemExit(
        "Could not infer a date column. Pass --date-column explicitly. "
        f"Available columns: {', '.join(columns)}"
    )


def _resolve_default_fields(
    *,
    dataset: str | None,
    manifest: Mapping[str, object] | None,
    columns: Sequence[str],
) -> tuple[list[str], str]:
    if dataset == "daily":
        fields = [field for field in DEFAULT_HK_DAILY_FIELDS if field in columns]
        if fields:
            return fields, "default_daily_fields"
    if dataset == "valuation":
        fields = [field for field in DEFAULT_HK_VALUATION_FIELDS if field in columns]
        if fields:
            return fields, "default_valuation_fields"

    if isinstance(manifest, Mapping):
        query = manifest.get("query")
        if isinstance(query, Mapping):
            manifest_fields = query.get("fields")
            if isinstance(manifest_fields, Sequence) and not isinstance(manifest_fields, (str, bytes)):
                fields = [str(field).strip() for field in manifest_fields if str(field).strip() in columns]
                if fields:
                    return fields, "manifest_query_fields"

    inferred = [column for column in columns if column not in KEY_COLUMNS]
    if inferred:
        return inferred, "inferred_non_key_columns"
    raise SystemExit("No value fields resolved for asset health inspection.")


def _resolve_fields(
    *,
    requested_fields: Sequence[str],
    dataset: str | None,
    manifest: Mapping[str, object] | None,
    columns: Sequence[str],
) -> tuple[list[str], str]:
    explicit = [str(field).strip() for field in requested_fields if str(field).strip()]
    if explicit:
        missing = [field for field in explicit if field not in columns]
        if missing:
            raise SystemExit(
                "Requested field(s) not found in asset schema: "
                + ", ".join(missing)
                + ". Available columns: "
                + ", ".join(columns)
            )
        return explicit, "explicit"
    return _resolve_default_fields(dataset=dataset, manifest=manifest, columns=columns)


def _load_audit_frame(asset_dir: Path) -> tuple[pd.DataFrame | None, str | None]:
    audit_path = asset_dir / "audit.csv"
    if not audit_path.exists():
        return None, None
    audit = pd.read_csv(audit_path)
    audit = _normalize_frame_columns(audit)
    if audit.empty:
        return audit, None
    latest_col = next((column for column in AUDIT_LATEST_DATE_COLUMNS if column in audit.columns), None)
    if latest_col is None:
        return audit, None
    symbol_col = next((column for column in AUDIT_SYMBOL_COLUMNS if column in audit.columns), None)
    if symbol_col is None:
        return audit, latest_col

    audit = audit.copy()
    audit["symbol"] = audit[symbol_col].map(_normalize_hk_symbol)
    latest_text = audit[latest_col].astype(str).str.strip()
    latest_text = latest_text.str.replace(r"\.0+$", "", regex=True)
    audit["latest_date"] = pd.to_datetime(latest_text, errors="coerce").dt.normalize()
    if "status" in audit.columns:
        audit["status"] = audit["status"].fillna("").astype(str).str.strip()
    else:
        audit["status"] = ""
    audit = audit.dropna(subset=["symbol"])
    return audit, latest_col


def _resolve_target_date(
    *,
    explicit_value: object,
    audit: pd.DataFrame | None,
    manifest: Mapping[str, object] | None,
    data_files: Sequence[Path],
    date_column: str,
) -> tuple[pd.Timestamp, str]:
    if explicit_value:
        return _parse_compact_date(explicit_value, label="--target-date"), "explicit"

    if audit is not None and "latest_date" in audit.columns and audit["latest_date"].notna().any():
        return pd.Timestamp(audit["latest_date"].dropna().max()).normalize(), "audit_latest_date"

    manifest_query_date = _resolve_manifest_query_date(manifest)
    if manifest_query_date:
        return pd.to_datetime(manifest_query_date).normalize(), "manifest_query_date"

    latest_dates: list[pd.Timestamp] = []
    for path in data_files:
        frame = pd.read_parquet(path, columns=[date_column])
        frame = _normalize_frame_columns(frame)
        if date_column not in frame.columns:
            continue
        parsed = pd.to_datetime(frame[date_column], errors="coerce").dropna()
        if not parsed.empty:
            latest_dates.append(parsed.max().normalize())
    if not latest_dates:
        raise SystemExit("Could not resolve a target date from audit, manifest, or parquet files.")
    return max(latest_dates), "file_scan_latest_date"


def _build_latest_date_counts(audit: pd.DataFrame | None, data_files: Sequence[Path]) -> tuple[Counter, Counter]:
    latest_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    if audit is None or audit.empty:
        return latest_counts, status_counts

    file_symbols = {_normalize_hk_symbol(path.stem) for path in data_files}
    for _, row in audit.iterrows():
        symbol = str(row.get("symbol") or "").strip()
        if not symbol or symbol not in file_symbols:
            continue
        latest_date = _format_date(row.get("latest_date"))
        if latest_date:
            latest_counts[latest_date] += 1
        status = str(row.get("status") or "").strip()
        if status:
            status_counts[status] += 1
    return latest_counts, status_counts


def _append_sample(values: list[str], item: str, *, limit: int) -> None:
    if item not in values and len(values) < limit:
        values.append(item)


def _round_pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(float(numerator) / float(denominator) * 100.0, 2)


def _render_asset_health_text(payload: Mapping[str, object]) -> str:
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    field_rows = (
        payload.get("field_coverage")
        if isinstance(payload.get("field_coverage"), list)
        else []
    )
    latest_rows = (
        payload.get("latest_date_distribution")
        if isinstance(payload.get("latest_date_distribution"), list)
        else []
    )
    stale_rows = (
        payload.get("sample_stale_symbols")
        if isinstance(payload.get("sample_stale_symbols"), list)
        else []
    )

    lines = ["HK Asset Health"]
    for key in (
        "asset_dir",
        "dataset",
        "target_date",
        "target_date_source",
        "date_column",
        "selection_source",
    ):
        value = summary.get(key)
        if value:
            lines.append(f"{key}: {value}")
    selected_fields = summary.get("selected_fields")
    if isinstance(selected_fields, list) and selected_fields:
        lines.append(f"selected_fields: {', '.join(str(item) for item in selected_fields)}")
    manifest_query_date = summary.get("manifest_query_date")
    if manifest_query_date:
        lines.append(f"manifest_query_date: {manifest_query_date}")

    lines.append("")
    lines.append("Summary")
    for key in (
        "symbols_scanned",
        "symbols_with_target_date_row",
        "symbols_without_target_date_row",
        "target_date_coverage_pct",
        "latest_date_min",
        "latest_date_max",
    ):
        lines.append(f"{key}: {summary.get(key)}")

    status_counts = summary.get("audit_status_counts")
    if isinstance(status_counts, Mapping) and status_counts:
        lines.append("")
        lines.append("Audit Status")
        for status, count in sorted(status_counts.items()):
            lines.append(f"{status}: {count}")

    if latest_rows:
        lines.append("")
        lines.append(f"Latest Dates (top {len(latest_rows)})")
        latest_df = pd.DataFrame(latest_rows)
        lines.append(latest_df.to_string(index=False))

    if stale_rows:
        lines.append("")
        lines.append("Sample Stale Symbols")
        for row in stale_rows:
            if not isinstance(row, Mapping):
                continue
            symbol = row.get("symbol")
            latest_date = row.get("latest_date")
            status = row.get("status")
            if status:
                lines.append(f"{symbol} @ {latest_date} ({status})")
            else:
                lines.append(f"{symbol} @ {latest_date}")

    if field_rows:
        lines.append("")
        lines.append("Field Coverage")
        field_df = pd.DataFrame(field_rows)
        field_df = field_df[
            [
                "field",
                "nonnull_on_target_date",
                "missing_on_target_date",
                "missing_but_prior_nonnull",
                "missing_and_never_nonnull",
                "nonnull_pct_on_target_date",
            ]
        ]
        lines.append(field_df.to_string(index=False))

    return "\n".join(lines).strip() + "\n"


def inspect_hk_asset_health(args) -> int:
    asset_dir = _resolve_path(args.asset_dir)
    data_dir = asset_dir / "data"
    if not data_dir.exists():
        raise SystemExit(f"Asset directory is missing data/: {asset_dir}")

    data_files = sorted(data_dir.glob("*.parquet"))
    if not data_files:
        raise SystemExit(f"No parquet files found under {data_dir}")

    manifest_path = asset_dir / "manifest.yml"
    manifest = _load_manifest(manifest_path) if manifest_path.exists() else None
    dataset = str(manifest.get("dataset") or "").strip() if isinstance(manifest, Mapping) else ""
    dataset = dataset or None

    sample_frame = _normalize_frame_columns(pd.read_parquet(data_files[0]))
    sample_columns = sample_frame.columns.tolist()
    date_column = _infer_date_column(sample_columns, getattr(args, "date_column", None))
    selected_fields, selection_source = _resolve_fields(
        requested_fields=getattr(args, "field", []) or [],
        dataset=dataset,
        manifest=manifest,
        columns=sample_columns,
    )

    audit, _ = _load_audit_frame(asset_dir)
    target_date, target_date_source = _resolve_target_date(
        explicit_value=getattr(args, "target_date", None),
        audit=audit,
        manifest=manifest,
        data_files=data_files,
        date_column=date_column,
    )

    latest_counts, status_counts = _build_latest_date_counts(audit, data_files)
    sample_limit = max(1, int(getattr(args, "sample_limit", 5) or 5))

    field_stats: dict[str, dict[str, object]] = {
        field: {
            "field": field,
            "symbols_with_target_date_row": 0,
            "nonnull_on_target_date": 0,
            "missing_on_target_date": 0,
            "missing_but_prior_nonnull": 0,
            "missing_and_never_nonnull": 0,
            "sample_missing_symbols": [],
            "sample_prior_nonnull_symbols": [],
        }
        for field in selected_fields
    }

    stale_rows: list[dict[str, str]] = []
    symbols_with_target_date_row = 0
    latest_min: pd.Timestamp | None = None
    latest_max: pd.Timestamp | None = None

    audit_by_symbol: dict[str, dict[str, object]] = {}
    if audit is not None and not audit.empty:
        audit_by_symbol = audit.set_index("symbol", drop=False).to_dict(orient="index")

    for path in data_files:
        symbol = _normalize_hk_symbol(path.stem)
        audit_entry = audit_by_symbol.get(symbol)
        latest_date = None
        status = ""
        if audit_entry:
            latest_date = audit_entry.get("latest_date")
            if pd.isna(latest_date):
                latest_date = None
            status = str(audit_entry.get("status") or "").strip()

        if latest_date is not None:
            latest_ts = pd.to_datetime(latest_date).normalize()
            latest_min = latest_ts if latest_min is None or latest_ts < latest_min else latest_min
            latest_max = latest_ts if latest_max is None or latest_ts > latest_max else latest_max
            if latest_ts != target_date:
                if len(stale_rows) < sample_limit:
                    stale_rows.append(
                        {
                            "symbol": symbol,
                            "latest_date": _format_date(latest_ts) or "",
                            "status": status,
                        }
                    )
                continue

        read_columns = [date_column, *selected_fields]
        try:
            frame = pd.read_parquet(path, columns=read_columns)
        except Exception:
            frame = pd.read_parquet(path)
        frame = _normalize_frame_columns(frame)
        if date_column not in frame.columns:
            raise SystemExit(f"Date column {date_column} not found in {path}")

        work = frame.copy()
        parsed_dates = pd.to_datetime(work[date_column], errors="coerce").dt.normalize()
        valid = parsed_dates.notna()
        work = work.loc[valid].copy()
        work[date_column] = parsed_dates.loc[valid]
        if work.empty:
            if len(stale_rows) < sample_limit:
                stale_rows.append(
                    {
                        "symbol": symbol,
                        "latest_date": None,
                        "status": status,
                    }
                )
            continue

        latest_ts = work[date_column].max()
        latest_min = latest_ts if latest_min is None or latest_ts < latest_min else latest_min
        latest_max = latest_ts if latest_max is None or latest_ts > latest_max else latest_max
        if not latest_counts:
            latest_counts[_format_date(latest_ts) or ""] += 1

        target_mask = work[date_column] == target_date
        if not bool(target_mask.any()):
            if len(stale_rows) < sample_limit:
                stale_rows.append(
                    {
                        "symbol": symbol,
                        "latest_date": _format_date(latest_ts) or "",
                        "status": status,
                    }
                )
            continue

        symbols_with_target_date_row += 1
        target_frame = work.loc[target_mask]
        prior_frame = work.loc[work[date_column] < target_date]
        for field in selected_fields:
            stats = field_stats[field]
            stats["symbols_with_target_date_row"] = int(stats["symbols_with_target_date_row"]) + 1
            if field not in work.columns:
                stats["missing_on_target_date"] = int(stats["missing_on_target_date"]) + 1
                stats["missing_and_never_nonnull"] = int(stats["missing_and_never_nonnull"]) + 1
                _append_sample(stats["sample_missing_symbols"], symbol, limit=sample_limit)
                continue

            target_series = target_frame[field]
            if target_series.notna().any():
                stats["nonnull_on_target_date"] = int(stats["nonnull_on_target_date"]) + 1
                continue

            stats["missing_on_target_date"] = int(stats["missing_on_target_date"]) + 1
            _append_sample(stats["sample_missing_symbols"], symbol, limit=sample_limit)
            prior_series = prior_frame[field]
            if prior_series.notna().any():
                stats["missing_but_prior_nonnull"] = int(stats["missing_but_prior_nonnull"]) + 1
                _append_sample(stats["sample_prior_nonnull_symbols"], symbol, limit=sample_limit)
            else:
                stats["missing_and_never_nonnull"] = int(stats["missing_and_never_nonnull"]) + 1

    symbols_scanned = len(data_files)
    latest_rows = [
        {"latest_date": date_text, "symbols": int(count)}
        for date_text, count in sorted(
            latest_counts.items(),
            key=lambda item: (-int(item[1]), str(item[0])),
        )[: max(1, int(getattr(args, "top_latest_dates", 5) or 5))]
        if date_text
    ]

    field_rows: list[dict[str, object]] = []
    for field in selected_fields:
        stats = field_stats[field]
        denominator = int(stats["symbols_with_target_date_row"])
        missing = int(stats["missing_on_target_date"])
        missing_but_prior = int(stats["missing_but_prior_nonnull"])
        field_rows.append(
            {
                "field": field,
                "symbols_with_target_date_row": denominator,
                "nonnull_on_target_date": int(stats["nonnull_on_target_date"]),
                "nonnull_pct_on_target_date": _round_pct(int(stats["nonnull_on_target_date"]), denominator),
                "missing_on_target_date": missing,
                "missing_pct_on_target_date": _round_pct(missing, denominator),
                "missing_but_prior_nonnull": missing_but_prior,
                "missing_but_prior_nonnull_pct_of_missing": _round_pct(missing_but_prior, missing),
                "missing_and_never_nonnull": int(stats["missing_and_never_nonnull"]),
                "sample_missing_symbols": list(stats["sample_missing_symbols"]),
                "sample_prior_nonnull_symbols": list(stats["sample_prior_nonnull_symbols"]),
            }
        )

    summary = {
        "asset_dir": str(asset_dir),
        "dataset": dataset,
        "target_date": _format_date(target_date),
        "target_date_source": target_date_source,
        "date_column": date_column,
        "selection_source": selection_source,
        "selected_fields": list(selected_fields),
        "manifest_query_date": _resolve_manifest_query_date(manifest),
        "symbols_scanned": symbols_scanned,
        "symbols_with_target_date_row": symbols_with_target_date_row,
        "symbols_without_target_date_row": int(symbols_scanned - symbols_with_target_date_row),
        "target_date_coverage_pct": _round_pct(symbols_with_target_date_row, symbols_scanned),
        "latest_date_min": _format_date(latest_min),
        "latest_date_max": _format_date(latest_max),
        "audit_status_counts": dict(sorted(status_counts.items())),
        "audit_file": str(asset_dir / "audit.csv") if (asset_dir / "audit.csv").exists() else None,
        "manifest_file": str(manifest_path) if manifest_path.exists() else None,
    }
    payload = {
        "summary": summary,
        "latest_date_distribution": latest_rows,
        "sample_stale_symbols": stale_rows,
        "field_coverage": field_rows,
    }

    output_format = str(getattr(args, "format", "text") or "text").strip().lower()
    if output_format == "json":
        rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    else:
        rendered = _render_asset_health_text(payload)

    out_path = _resolve_path(args.out) if getattr(args, "out", None) else None
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0
