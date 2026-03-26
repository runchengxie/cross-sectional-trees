from __future__ import annotations

import pandas as pd

from csml.data_tools import rqdata_assets as _base


def mirror_hk_daily(args, rqdatac) -> int:
    fields, field_metadata = _base._resolve_daily_fields(args)
    symbols, symbol_metadata = _base._resolve_symbols(args)
    start_date = _base._normalize_absolute_date(args.start_date, label="--start-date")
    end_date = _base._normalize_absolute_date(args.end_date, label="--end-date")
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
    max_attempts = max(
        1,
        int(getattr(args, "max_attempts", _base.DEFAULT_MIRROR_MAX_ATTEMPTS) or 1),
    )
    backoff_seconds = float(
        getattr(args, "backoff_seconds", _base.DEFAULT_MIRROR_BACKOFF_SECONDS)
    )
    max_backoff_seconds = float(
        getattr(args, "max_backoff_seconds", _base.DEFAULT_MIRROR_MAX_BACKOFF_SECONDS)
    )
    output_dir = _base._prepare_daily_output_dir(
        out_root=getattr(args, "out_root", _base.DEFAULT_OUT_ROOT),
        dataset_name="daily",
        start_date=start_date,
        end_date=end_date,
        name=getattr(args, "name", None),
        resume=resume,
    )
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    audit_path = output_dir / "audit.csv"

    symbol_map = {_base._to_rqdata_symbol("hk", symbol): symbol for symbol in symbols}
    order_book_ids = list(symbol_map.keys())
    entries_by_symbol: dict[str, _base.DailyMirrorEntry] = {}
    audit_by_symbol: dict[str, _base.DailyMirrorAuditRecord] = {}
    batches: list[dict[str, object]] = []
    columns: list[str] = []
    field_coverage = _base._field_coverage_template(fields)
    started_at = _base._timestamp_now()
    status = "completed"
    error: str | None = None
    result_code = 0
    quota_blocked = False

    data_cfg = {
        "provider": "rqdata",
        "rqdata": {
            "market": "hk",
            "frequency": frequency,
            "fields": list(fields),
            "skip_suspended": skip_suspended,
        },
    }
    if adjust_type:
        data_cfg["rqdata"]["adjust_type"] = adjust_type

    def _record_entry(
        *,
        symbol: str,
        entry: _base.DailyMirrorEntry,
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
        _base._update_field_coverage(field_coverage, symbol_frame, fields=fields)
        audit_by_symbol[symbol] = _base._daily_audit_record(
            ts_code=symbol,
            order_book_id=entry.order_book_id,
            status=record_status,
            attempts=attempts,
            started_at=started_at_value,
            finished_at=finished_at_value,
            file_mtime=_base._path_mtime_iso(entry.path),
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
        audit_by_symbol[symbol] = _base._daily_audit_record(
            ts_code=symbol,
            order_book_id=order_book_id,
            status=record_status,
            attempts=attempts,
            started_at=started_at_value,
            finished_at=finished_at_value,
            file_mtime=None,
            error=error_text,
            entry=None,
        )

    def _process_symbol(order_book_id: str) -> None:
        nonlocal status, error, result_code, quota_blocked, columns
        if quota_blocked:
            return

        symbol = symbol_map[order_book_id]
        started = _base._timestamp_now()
        try:
            payload, attempts = _base._retry_fetch(
                f"daily fetch failed for {order_book_id}",
                lambda: _base._fetch_daily_rqdata(
                    "hk",
                    symbol,
                    start_date,
                    end_date,
                    rqdatac,
                    data_cfg,
                ),
                max_attempts=max_attempts,
                backoff_seconds=backoff_seconds,
                max_backoff_seconds=max_backoff_seconds,
            )
        except _base.MirrorQuotaError as exc:
            finished = _base._timestamp_now()
            quota_blocked = True
            status = "stopped_quota"
            error = str(exc)
            result_code = max(result_code, 2)
            _record_non_entry(
                symbol=symbol,
                order_book_id=order_book_id,
                record_status="quota_blocked",
                attempts=exc.attempts,
                started_at_value=started,
                finished_at_value=finished,
                error_text=str(exc),
            )
            batches.append(
                {
                    "order_book_ids": 1,
                    "rows": 0,
                    "symbols_written": 0,
                    "symbols_missing_remote": 0,
                    "status": "quota_blocked",
                    "attempts": exc.attempts,
                    "error": str(exc),
                }
            )
            return
        except _base.MirrorFetchError as exc:
            finished = _base._timestamp_now()
            _record_non_entry(
                symbol=symbol,
                order_book_id=order_book_id,
                record_status="failed",
                attempts=exc.attempts,
                started_at_value=started,
                finished_at_value=finished,
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

        finished = _base._timestamp_now()
        prepared = _base._prepare_daily_asset_frame(
            payload,
            symbol=symbol,
            order_book_id=order_book_id,
        )
        prepared = _base._ensure_requested_fields(prepared, fields)
        if prepared.empty:
            _record_non_entry(
                symbol=symbol,
                order_book_id=order_book_id,
                record_status="missing_remote",
                attempts=attempts,
                started_at_value=started,
                finished_at_value=finished,
            )
            batches.append(
                {
                    "order_book_ids": 1,
                    "rows": 0,
                    "symbols_written": 0,
                    "symbols_missing_remote": 1,
                    "status": "empty",
                    "attempts": attempts,
                }
            )
            return

        if not columns:
            columns = prepared.columns.tolist()
        entry = _base._write_daily_symbol_frame(data_dir, prepared)
        _record_entry(
            symbol=symbol,
            entry=entry,
            symbol_frame=prepared,
            record_status="written",
            attempts=attempts,
            started_at_value=started,
            finished_at_value=finished,
        )
        batches.append(
            {
                "order_book_ids": 1,
                "rows": int(len(prepared)),
                "symbols_written": 1,
                "symbols_missing_remote": 0,
                "status": "completed",
                "attempts": attempts,
            }
        )

    try:
        if resume:
            _base._validate_daily_resume_inputs(
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

        _base._write_text_list(output_dir / "fields.txt", fields)
        _base._write_text_list(output_dir / "symbols.txt", symbols)

        pending_order_book_ids: list[str] = []
        for order_book_id in order_book_ids:
            symbol = symbol_map[order_book_id]
            out_path = data_dir / f"{symbol}.parquet"
            if skip_existing and out_path.exists():
                try:
                    entry, symbol_frame = _base._load_existing_daily_entry(
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
                    finished_at_value=_base._path_mtime_iso(out_path),
                )
                continue
            pending_order_book_ids.append(order_book_id)

        for order_book_id in pending_order_book_ids:
            _process_symbol(order_book_id)
            if quota_blocked:
                break

        if quota_blocked:
            quota_finished_at = _base._timestamp_now()
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
        finished_at = _base._timestamp_now()
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
        _base._write_daily_audit_csv(audit_path, audit_records)
        manifest = _base._build_daily_manifest(
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
                item.ts_code for item in audit_records if item.status == "missing_remote"
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
        _base._write_manifest(output_dir / "manifest.yml", manifest)

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
