from __future__ import annotations

import pandas as pd

from ...data_providers import _to_rqdata_symbol
from .asset_io import (
    _chunked,
    _daily_audit_record,
    _ensure_requested_fields,
    _field_coverage_template,
    _load_existing_daily_entry,
    _prepare_daily_batch_asset_frame,
    _update_field_coverage,
    _write_daily_audit_csv,
    _write_daily_symbol_frame,
)
from .manifest_ops import _build_daily_manifest, _validate_daily_resume_inputs
from .fetch_runtime import _retry_fetch
from .models import DailyMirrorAuditRecord, DailyMirrorEntry, MirrorFetchError, MirrorQuotaError
from .package_api import _package_attr
from .request_groups import _resolve_symbols
from .shared import (
    _normalize_absolute_date,
    _path_mtime_iso,
    _prepare_daily_output_dir,
    _resolve_daily_fields,
    _timestamp_now,
    _write_text_list,
    _write_manifest,
)


DEFAULT_MIRROR_MAX_ATTEMPTS = _package_attr("DEFAULT_MIRROR_MAX_ATTEMPTS")
DEFAULT_MIRROR_BACKOFF_SECONDS = _package_attr("DEFAULT_MIRROR_BACKOFF_SECONDS")
DEFAULT_MIRROR_MAX_BACKOFF_SECONDS = _package_attr("DEFAULT_MIRROR_MAX_BACKOFF_SECONDS")
DEFAULT_BATCH_SIZE = _package_attr("DEFAULT_BATCH_SIZE")
DEFAULT_OUT_ROOT = _package_attr("DEFAULT_OUT_ROOT")


def mirror_hk_daily(args, rqdatac) -> int:
    fields, field_metadata = _resolve_daily_fields(args)
    symbols, symbol_metadata = _resolve_symbols(args)
    start_date = _normalize_absolute_date(args.start_date, label="--start-date")
    end_date = _normalize_absolute_date(args.end_date, label="--end-date")
    if start_date > end_date:
        raise SystemExit("--start-date must be <= --end-date.")

    frequency = "1d"
    adjust_type = getattr(args, "adjust_type", None)
    if adjust_type is not None:
        adjust_type = str(adjust_type).strip() or None
    skip_suspended_raw = getattr(args, "skip_suspended", None)
    skip_suspended = True if skip_suspended_raw is None else bool(skip_suspended_raw)

    resume = bool(getattr(args, "resume", False))
    skip_existing = bool(getattr(args, "skip_existing", False) or resume)
    batch_size = int(getattr(args, "batch_size", DEFAULT_BATCH_SIZE) or DEFAULT_BATCH_SIZE)
    max_attempts = max(
        1,
        int(getattr(args, "max_attempts", DEFAULT_MIRROR_MAX_ATTEMPTS) or 1),
    )
    backoff_seconds = float(
        getattr(args, "backoff_seconds", DEFAULT_MIRROR_BACKOFF_SECONDS)
    )
    max_backoff_seconds = float(
        getattr(args, "max_backoff_seconds", DEFAULT_MIRROR_MAX_BACKOFF_SECONDS)
    )
    output_dir = _prepare_daily_output_dir(
        out_root=getattr(args, "out_root", DEFAULT_OUT_ROOT),
        dataset_name="daily",
        start_date=start_date,
        end_date=end_date,
        name=getattr(args, "name", None),
        resume=resume,
    )
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    audit_path = output_dir / "audit.csv"

    symbol_map = {_to_rqdata_symbol("hk", symbol): symbol for symbol in symbols}
    order_book_ids = list(symbol_map.keys())
    entries_by_symbol: dict[str, DailyMirrorEntry] = {}
    audit_by_symbol: dict[str, DailyMirrorAuditRecord] = {}
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
        entry: DailyMirrorEntry,
        symbol_frame: pd.DataFrame,
        record_status: str,
        attempts: int,
        started_at_value: str | None,
        finished_at_value: str | None,
        error_text: str | None = None,
    ) -> None:
        nonlocal columns
        entries_by_symbol[symbol] = entry
        if not columns and not symbol_frame.empty:
            columns = symbol_frame.columns.tolist()
        _update_field_coverage(field_coverage, symbol_frame, fields=fields)
        audit_by_symbol[symbol] = _daily_audit_record(
            symbol=symbol,
            order_book_id=entry.order_book_id,
            status=record_status,
            attempts=attempts,
            started_at=started_at_value,
            finished_at=finished_at_value,
            file_mtime=_path_mtime_iso(entry.path),
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
        error_text: str | None = None,
    ) -> None:
        audit_by_symbol[symbol] = _daily_audit_record(
            symbol=symbol,
            order_book_id=order_book_id,
            status=record_status,
            attempts=attempts,
            started_at=started_at_value,
            finished_at=finished_at_value,
            file_mtime=None,
            error=error_text,
            entry=None,
        )

    def _fetch_batch_payload(batch_order_book_ids: list[str]):
        request_target: str | list[str]
        if len(batch_order_book_ids) == 1:
            request_target = batch_order_book_ids[0]
        else:
            request_target = list(batch_order_book_ids)
        kwargs = {
            "fields": list(fields),
            "skip_suspended": skip_suspended,
            "market": "hk",
        }
        if adjust_type:
            kwargs["adjust_type"] = adjust_type
        return rqdatac.get_price(
            request_target,
            start_date,
            end_date,
            frequency,
            **kwargs,
        )

    def _process_batch(batch_order_book_ids: list[str]) -> None:
        nonlocal status, error, result_code, quota_blocked, columns
        if not batch_order_book_ids or quota_blocked:
            return

        batch_started_at = _timestamp_now()
        try:
            payload, attempts = _retry_fetch(
                f"daily fetch failed for {', '.join(batch_order_book_ids)}",
                lambda: _fetch_batch_payload(batch_order_book_ids),
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
                _record_non_entry(
                    symbol=symbol,
                    order_book_id=order_book_id,
                    record_status="quota_blocked",
                    attempts=exc.attempts,
                    started_at_value=batch_started_at,
                    finished_at_value=batch_finished_at,
                    error_text=str(exc),
                )
            batches.append(
                {
                    "order_book_ids": len(batch_order_book_ids),
                    "rows": 0,
                    "symbols_written": 0,
                    "symbols_missing_remote": len(batch_order_book_ids),
                    "status": "quota_blocked",
                    "attempts": exc.attempts,
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
                    "error": str(exc),
                }
            )
            if status == "completed":
                status = "completed_with_failures"
            result_code = max(result_code, 1)
            return

        batch_finished_at = _timestamp_now()
        prepared = _prepare_daily_batch_asset_frame(
            payload,
            symbol_map={order_book_id: symbol_map[order_book_id] for order_book_id in batch_order_book_ids},
        )
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
                )
            batches.append(
                {
                    "order_book_ids": len(batch_order_book_ids),
                    "rows": 0,
                    "symbols_written": 0,
                    "symbols_missing_remote": len(batch_order_book_ids),
                    "status": "empty",
                    "attempts": attempts,
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
            symbol_frame = prepared[prepared["symbol"] == symbol].reset_index(drop=True)
            if symbol_frame.empty:
                batch_symbols_missing += 1
                _record_non_entry(
                    symbol=symbol,
                    order_book_id=order_book_id,
                    record_status="missing_remote",
                    attempts=attempts,
                    started_at_value=batch_started_at,
                    finished_at_value=batch_finished_at,
                )
                continue
            entry = _write_daily_symbol_frame(data_dir, symbol_frame)
            _record_entry(
                symbol=symbol,
                entry=entry,
                symbol_frame=symbol_frame,
                record_status="written",
                attempts=attempts,
                started_at_value=batch_started_at,
                finished_at_value=batch_finished_at,
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
            }
        )

    try:
        if resume:
            _validate_daily_resume_inputs(
                output_dir=output_dir,
                dataset_name="daily",
                fields=fields,
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                frequency=frequency,
                adjust_type=adjust_type,
                skip_suspended=skip_suspended,
            )

        _write_text_list(output_dir / "fields.txt", fields)
        _write_text_list(output_dir / "symbols.txt", symbols)

        pending_order_book_ids: list[str] = []
        for order_book_id in order_book_ids:
            symbol = symbol_map[order_book_id]
            out_path = data_dir / f"{symbol}.parquet"
            if skip_existing and out_path.exists():
                try:
                    entry, symbol_frame = _load_existing_daily_entry(
                        out_path,
                        fields=fields,
                    )
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

        for batch_order_book_ids in _chunked(pending_order_book_ids, batch_size):
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
        _write_daily_audit_csv(audit_path, audit_records)
        manifest = _build_daily_manifest(
            dataset_name="daily",
            api_name="rqdatac.get_price",
            output_dir=output_dir,
            fields=fields,
            field_metadata=field_metadata,
            symbol_metadata=symbol_metadata,
            symbols_requested=symbols,
            entries=[
                entries_by_symbol[symbol]
                for symbol in symbols
                if symbol in entries_by_symbol
            ],
            missing_symbols=[
                item.symbol for item in audit_records if item.status == "missing_remote"
            ],
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
            adjust_type=adjust_type,
            skip_suspended=skip_suspended,
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
        f"Wrote daily mirror to {output_dir} "
        f"({totals['symbols']} symbols, {totals['files']} files, {totals['rows']} rows, {totals['bytes']} bytes, status={status})"
    )
    return result_code
