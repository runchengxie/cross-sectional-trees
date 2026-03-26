from __future__ import annotations

from collections.abc import Mapping, Sequence

import pandas as pd

from csml.data_tools import rqdata_assets as _base


def mirror_hk_southbound(args, rqdatac) -> int:
    symbols, symbol_metadata = _base._resolve_symbols(args)
    start_date = _base._normalize_absolute_date(args.start_date, label="--start-date")
    end_date = _base._normalize_absolute_date(args.end_date, label="--end-date")
    if start_date > end_date:
        raise SystemExit("--start-date must be <= --end-date.")

    trading_types = _base._resolve_hk_southbound_trading_types(args)
    snapshot_dates, snapshot_metadata = _base._resolve_hk_trading_snapshot_dates(
        rqdatac,
        args,
        start_date=start_date,
        end_date=end_date,
    )
    resume = bool(getattr(args, "resume", False))
    skip_existing = bool(getattr(args, "skip_existing", False) or resume)
    max_attempts = max(1, int(getattr(args, "max_attempts", _base.DEFAULT_MIRROR_MAX_ATTEMPTS) or 1))
    backoff_seconds = float(getattr(args, "backoff_seconds", _base.DEFAULT_MIRROR_BACKOFF_SECONDS))
    max_backoff_seconds = float(
        getattr(args, "max_backoff_seconds", _base.DEFAULT_MIRROR_MAX_BACKOFF_SECONDS)
    )
    output_dir = _base._prepare_daily_output_dir(
        out_root=getattr(args, "out_root", _base.DEFAULT_OUT_ROOT),
        dataset_name="southbound",
        start_date=start_date,
        end_date=end_date,
        name=getattr(args, "name", None),
        resume=resume,
    )
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    audit_path = output_dir / "audit.csv"

    fields = ["trading_type", "eligible"]
    field_metadata = {
        "count": len(fields),
        "fields_file": [],
        "source": "southbound_membership",
        "base_fields": list(fields),
    }
    entries_by_symbol: dict[str, _base.DatedMirrorEntry] = {}
    audit_by_symbol: dict[str, _base.DatedMirrorAuditRecord] = {}
    frames_by_symbol: dict[str, list[pd.DataFrame]] = {}
    batches: list[dict[str, object]] = []
    columns: list[str] = []
    field_coverage = _base._field_coverage_template(fields)
    started_at = _base._timestamp_now()
    status = "completed"
    error: str | None = None
    result_code = 0
    quota_blocked = False
    order_book_id_by_symbol = {symbol: _base._to_rqdata_symbol("hk", symbol) for symbol in symbols}
    symbol_map = {order_book_id: symbol for symbol, order_book_id in order_book_id_by_symbol.items()}

    def _record_entry(
        *,
        symbol: str,
        entry: _base.DatedMirrorEntry,
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
        audit_by_symbol[symbol] = _base._dated_audit_record(
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
        record_status: str,
        attempts: int,
        started_at_value: str | None,
        finished_at_value: str | None,
        error_text: str | None = None,
    ) -> None:
        audit_by_symbol[symbol] = _base._dated_audit_record(
            ts_code=symbol,
            order_book_id=order_book_id_by_symbol[symbol],
            status=record_status,
            attempts=attempts,
            started_at=started_at_value,
            finished_at=finished_at_value,
            file_mtime=None,
            error=error_text,
            entry=None,
        )

    try:
        if resume:
            _base._validate_dated_resume_inputs(
                output_dir=output_dir,
                dataset_name="southbound",
                fields=fields,
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
            )
            manifest = _base._load_manifest(output_dir / "manifest.yml") or {}
            query = manifest.get("query") if isinstance(manifest.get("query"), Mapping) else {}
            if isinstance(query, Mapping):
                if query.get("rebalance_frequency") not in {
                    None,
                    snapshot_metadata.get("rebalance_frequency"),
                }:
                    raise SystemExit("Resume target query mismatch for rebalance_frequency.")
                existing_types = query.get("trading_types")
                if existing_types is not None:
                    normalized_existing_types = (
                        _base._dedupe_preserve_order(existing_types)
                        if isinstance(existing_types, Sequence) and not isinstance(existing_types, str)
                        else _base._dedupe_preserve_order([existing_types])
                    )
                    if normalized_existing_types != list(trading_types):
                        raise SystemExit("Resume target query mismatch for trading_types.")
            existing_dates = _base._load_existing_text_list(output_dir / "dates.txt", strip=False)
            if existing_dates and list(existing_dates) != list(snapshot_dates):
                raise SystemExit("Resume target dates.txt does not match the requested date list.")
            existing_trading_types = _base._load_existing_text_list(
                output_dir / "trading_types.txt",
                strip=False,
            )
            if existing_trading_types and list(existing_trading_types) != list(trading_types):
                raise SystemExit(
                    "Resume target trading_types.txt does not match the requested trading type list."
                )

        _base._write_text_list(output_dir / "fields.txt", fields)
        _base._write_text_list(output_dir / "symbols.txt", symbols)
        _base._write_text_list(output_dir / "dates.txt", snapshot_dates)
        _base._write_text_list(output_dir / "trading_types.txt", trading_types)

        pending_symbols: list[str] = []
        for symbol in symbols:
            out_path = data_dir / f"{symbol}.parquet"
            if skip_existing and out_path.exists():
                try:
                    entry, symbol_frame = _base._load_existing_dated_entry(
                        out_path,
                        date_column="date",
                        fields=fields,
                    )
                except Exception:
                    pending_symbols.append(symbol)
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
            pending_symbols.append(symbol)

        pending_symbol_set = set(pending_symbols)
        for query_date in snapshot_dates:
            if quota_blocked or not pending_symbol_set:
                break
            for trading_type in trading_types:
                if quota_blocked or not pending_symbol_set:
                    break
                batch_started_at = _base._timestamp_now()
                try:
                    payload, attempts = _base._retry_fetch(
                        f"southbound fetch failed for {trading_type} @ {query_date}",
                        lambda: rqdatac.hk.get_southbound_eligible_secs(
                            trading_type=trading_type,
                            date=query_date,
                        ),
                        max_attempts=max_attempts,
                        backoff_seconds=backoff_seconds,
                        max_backoff_seconds=max_backoff_seconds,
                    )
                except _base.MirrorQuotaError as exc:
                    quota_blocked = True
                    status = "stopped_quota"
                    error = str(exc)
                    result_code = max(result_code, 2)
                    batches.append(
                        {
                            "date": query_date,
                            "trading_type": trading_type,
                            "rows": 0,
                            "symbols": 0,
                            "status": "quota_blocked",
                            "attempts": exc.attempts,
                            "error": str(exc),
                        }
                    )
                    break
                except _base.MirrorFetchError as exc:
                    batches.append(
                        {
                            "date": query_date,
                            "trading_type": trading_type,
                            "rows": 0,
                            "symbols": 0,
                            "status": "failed",
                            "attempts": exc.attempts,
                            "error": str(exc),
                        }
                    )
                    if status == "completed":
                        status = "completed_with_failures"
                    result_code = max(result_code, 1)
                    continue

                rows = []
                for order_book_id in list(payload or []):
                    ts_code = _base._normalize_hk_symbol(order_book_id)
                    if not ts_code or ts_code not in pending_symbol_set:
                        continue
                    rows.append(
                        {
                            "date": query_date,
                            "ts_code": ts_code,
                            "order_book_id": order_book_id_by_symbol[ts_code],
                            "trading_type": trading_type,
                            "eligible": 1,
                        }
                    )
                prepared = _base._prepare_dated_asset_frame(
                    pd.DataFrame(
                        rows,
                        columns=["date", "ts_code", "order_book_id", "trading_type", "eligible"],
                    ),
                    symbol_map=symbol_map,
                    date_column="date",
                    sort_columns=("trading_type",),
                )
                prepared = _base._ensure_requested_fields(prepared, fields)
                batches.append(
                    {
                        "date": query_date,
                        "trading_type": trading_type,
                        "rows": int(len(prepared)),
                        "symbols": int(prepared["ts_code"].nunique()) if not prepared.empty else 0,
                        "status": "completed",
                        "attempts": attempts,
                        "started_at": batch_started_at,
                        "finished_at": _base._timestamp_now(),
                    }
                )
                if prepared.empty:
                    continue
                for symbol in prepared["ts_code"].drop_duplicates().tolist():
                    symbol_frame = prepared[prepared["ts_code"] == symbol].reset_index(drop=True)
                    if symbol_frame.empty:
                        continue
                    frames_by_symbol.setdefault(symbol, []).append(symbol_frame)

        if result_code == 1 and status == "completed":
            status = "completed_with_failures"
    except Exception as exc:
        status = "failed"
        error = str(exc)
        result_code = max(result_code, 1)
        raise
    finally:
        finished_at = _base._timestamp_now()
        for symbol in symbols:
            if symbol in audit_by_symbol:
                continue
            frames = frames_by_symbol.get(symbol) or []
            if frames:
                combined = pd.concat(frames, ignore_index=True)
                combined = combined.drop_duplicates(subset=["date", "trading_type"], keep="last")
                combined = combined.sort_values(["date", "trading_type"]).reset_index(drop=True)
                entry = _base._write_dated_symbol_frame(data_dir, combined, date_column="date")
                _record_entry(
                    symbol=symbol,
                    entry=entry,
                    symbol_frame=combined,
                    record_status="written",
                    attempts=0,
                    started_at_value=started_at,
                    finished_at_value=finished_at,
                    error_text=error if quota_blocked else None,
                )
                continue
            _record_non_entry(
                symbol=symbol,
                record_status="quota_blocked" if quota_blocked else "missing_remote",
                attempts=0,
                started_at_value=None,
                finished_at_value=finished_at,
                error_text=error if quota_blocked else None,
            )

        audit_records = [audit_by_symbol[symbol] for symbol in symbols]
        _base._write_dated_audit_csv(audit_path, audit_records)
        manifest = _base._build_dated_manifest(
            dataset_name="southbound",
            api_name="rqdatac.hk.get_southbound_eligible_secs",
            output_dir=output_dir,
            fields=fields,
            field_metadata=field_metadata,
            symbol_metadata=symbol_metadata,
            symbols_requested=symbols,
            entries=[entries_by_symbol[symbol] for symbol in symbols if symbol in entries_by_symbol],
            missing_symbols=[item.ts_code for item in audit_records if item.status == "missing_remote"],
            start_date=start_date,
            end_date=end_date,
            date_column="date",
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
        manifest_query = manifest.get("query", {})
        if isinstance(manifest_query, dict):
            manifest_query["rebalance_frequency"] = snapshot_metadata.get("rebalance_frequency")
            manifest_query["dates_count"] = len(snapshot_dates)
            manifest_query["dates_file"] = str(output_dir / "dates.txt")
            manifest_query["trading_types"] = list(trading_types)
            manifest_query["trading_types_file"] = str(output_dir / "trading_types.txt")
        manifest["date_source"] = snapshot_metadata
        _base._write_manifest(output_dir / "manifest.yml", manifest)

    totals = {
        "files": len(entries_by_symbol),
        "symbols": len(entries_by_symbol),
        "rows": sum(item.rows for item in entries_by_symbol.values()),
        "bytes": sum(item.total_bytes for item in entries_by_symbol.values()),
    }
    print(
        f"Wrote southbound mirror to {output_dir} "
        f"({totals['symbols']} symbols, {totals['files']} files, {totals['rows']} rows, {totals['bytes']} bytes, status={status})"
    )
    return result_code


def mirror_hk_instrument_industry(args, rqdatac) -> int:
    source = _base._resolve_hk_industry_source(args)
    level, fields = _base._resolve_hk_instrument_industry_level(args)
    symbols, symbol_metadata = _base._resolve_symbols(args)
    start_date = _base._normalize_absolute_date(args.start_date, label="--start-date")
    end_date = _base._normalize_absolute_date(args.end_date, label="--end-date")
    if start_date > end_date:
        raise SystemExit("--start-date must be <= --end-date.")

    snapshot_dates, snapshot_metadata = _base._resolve_hk_snapshot_dates(
        args,
        start_date=start_date,
        end_date=end_date,
    )
    resume = bool(getattr(args, "resume", False))
    skip_existing = bool(getattr(args, "skip_existing", False) or resume)
    max_attempts = max(1, int(getattr(args, "max_attempts", _base.DEFAULT_MIRROR_MAX_ATTEMPTS) or 1))
    backoff_seconds = float(getattr(args, "backoff_seconds", _base.DEFAULT_MIRROR_BACKOFF_SECONDS))
    max_backoff_seconds = float(
        getattr(args, "max_backoff_seconds", _base.DEFAULT_MIRROR_MAX_BACKOFF_SECONDS)
    )
    output_dir = _base._prepare_daily_output_dir(
        out_root=getattr(args, "out_root", _base.DEFAULT_OUT_ROOT),
        dataset_name="instrument_industry",
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
    entries_by_symbol: dict[str, _base.DatedMirrorEntry] = {}
    audit_by_symbol: dict[str, _base.DatedMirrorAuditRecord] = {}
    frames_by_symbol: dict[str, list[pd.DataFrame]] = {}
    batches: list[dict[str, object]] = []
    columns: list[str] = []
    field_metadata = {
        "count": len(fields),
        "fields_file": [],
        "source": f"rqdatac_level_{level}",
        "base_fields": list(fields),
    }
    field_coverage = _base._field_coverage_template(fields)
    started_at = _base._timestamp_now()
    status = "completed"
    error: str | None = None
    result_code = 0
    quota_blocked = False

    def _record_entry(
        *,
        symbol: str,
        entry: _base.DatedMirrorEntry,
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
        audit_by_symbol[symbol] = _base._dated_audit_record(
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
        audit_by_symbol[symbol] = _base._dated_audit_record(
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

    def _process_batch(batch_order_book_ids: list[str], query_date: str) -> None:
        nonlocal status, error, result_code, quota_blocked
        if not batch_order_book_ids or quota_blocked:
            return
        batch_started_at = _base._timestamp_now()
        try:
            payload, attempts = _base._retry_fetch(
                f"instrument industry fetch failed for {query_date}: {', '.join(batch_order_book_ids)}",
                lambda: rqdatac.get_instrument_industry(
                    batch_order_book_ids,
                    source=source,
                    level=level,
                    date=query_date,
                    market="hk",
                ),
                max_attempts=max_attempts,
                backoff_seconds=backoff_seconds,
                max_backoff_seconds=max_backoff_seconds,
            )
        except _base.MirrorQuotaError as exc:
            quota_blocked = True
            status = "stopped_quota"
            error = str(exc)
            result_code = max(result_code, 2)
            batches.append(
                {
                    "date": query_date,
                    "order_book_ids": len(batch_order_book_ids),
                    "rows": 0,
                    "status": "quota_blocked",
                    "attempts": exc.attempts,
                    "error": str(exc),
                }
            )
            return
        except _base.MirrorFetchError as exc:
            if len(batch_order_book_ids) > 1:
                batches.append(
                    {
                        "date": query_date,
                        "order_book_ids": len(batch_order_book_ids),
                        "rows": 0,
                        "status": "split_after_error",
                        "attempts": exc.attempts,
                        "error": str(exc),
                    }
                )
                for order_book_id in batch_order_book_ids:
                    _process_batch([order_book_id], query_date)
                    if quota_blocked:
                        break
                return
            batches.append(
                {
                    "date": query_date,
                    "order_book_ids": 1,
                    "rows": 0,
                    "status": "failed",
                    "attempts": exc.attempts,
                    "error": str(exc),
                }
            )
            if status == "completed":
                status = "completed_with_failures"
            result_code = max(result_code, 1)
            return

        prepared = _base._prepare_hk_instrument_industry_frame(
            payload,
            symbol_map={order_book_id: symbol_map[order_book_id] for order_book_id in batch_order_book_ids},
            query_date=query_date,
        )
        prepared = _base._ensure_requested_fields(prepared, fields)
        batches.append(
            {
                "date": query_date,
                "order_book_ids": len(batch_order_book_ids),
                "rows": int(len(prepared)),
                "status": "completed",
                "attempts": attempts,
            }
        )
        if prepared.empty:
            return

        for order_book_id in batch_order_book_ids:
            symbol = symbol_map[order_book_id]
            symbol_frame = prepared[prepared["ts_code"] == symbol].reset_index(drop=True)
            if symbol_frame.empty:
                continue
            frames_by_symbol.setdefault(symbol, []).append(symbol_frame)

    try:
        if resume:
            _base._validate_dated_resume_inputs(
                output_dir=output_dir,
                dataset_name="instrument_industry",
                fields=fields,
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
            )
            manifest = _base._load_manifest(output_dir / "manifest.yml") or {}
            query = manifest.get("query") if isinstance(manifest.get("query"), Mapping) else {}
            if isinstance(query, Mapping):
                if query.get("source") not in {None, source}:
                    raise SystemExit(
                        f"Resume target query mismatch for source: expected {source!r}, got {query.get('source')!r}."
                    )
                if query.get("level") not in {None, level}:
                    raise SystemExit(
                        f"Resume target query mismatch for level: expected {level!r}, got {query.get('level')!r}."
                    )
                if query.get("rebalance_frequency") not in {None, snapshot_metadata.get("rebalance_frequency")}:
                    raise SystemExit("Resume target query mismatch for rebalance_frequency.")
            existing_dates = _base._load_existing_text_list(output_dir / "dates.txt", strip=False)
            if existing_dates and list(existing_dates) != list(snapshot_dates):
                raise SystemExit("Resume target dates.txt does not match the requested date list.")

        _base._write_text_list(output_dir / "fields.txt", fields)
        _base._write_text_list(output_dir / "symbols.txt", symbols)
        _base._write_text_list(output_dir / "dates.txt", snapshot_dates)

        pending_order_book_ids: list[str] = []
        for order_book_id in order_book_ids:
            symbol = symbol_map[order_book_id]
            out_path = data_dir / f"{symbol}.parquet"
            if skip_existing and out_path.exists():
                try:
                    entry, symbol_frame = _base._load_existing_dated_entry(
                        out_path,
                        date_column="date",
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

        for query_date in snapshot_dates:
            for batch_order_book_ids in _base._chunked(
                pending_order_book_ids,
                getattr(args, "batch_size", _base.DEFAULT_BATCH_SIZE),
            ):
                _process_batch(batch_order_book_ids, query_date)
                if quota_blocked:
                    break
            if quota_blocked:
                break
            if result_code == 1 and status == "completed":
                status = "completed_with_failures"
    except Exception as exc:
        status = "failed"
        error = str(exc)
        result_code = max(result_code, 1)
        raise
    finally:
        finished_at = _base._timestamp_now()
        for order_book_id in pending_order_book_ids if "pending_order_book_ids" in locals() else order_book_ids:
            symbol = symbol_map[order_book_id]
            if symbol in audit_by_symbol:
                continue
            frames = frames_by_symbol.get(symbol) or []
            if frames:
                combined = pd.concat(frames, ignore_index=True)
                combined = combined.drop_duplicates(subset=["date"], keep="last")
                combined = combined.sort_values(["date"]).reset_index(drop=True)
                entry = _base._write_dated_symbol_frame(data_dir, combined, date_column="date")
                _record_entry(
                    symbol=symbol,
                    entry=entry,
                    symbol_frame=combined,
                    record_status="written",
                    attempts=0,
                    started_at_value=started_at,
                    finished_at_value=finished_at,
                    error_text=error if quota_blocked else None,
                )
                continue
            _record_non_entry(
                symbol=symbol,
                order_book_id=order_book_id,
                record_status="quota_blocked" if quota_blocked else "missing_remote",
                attempts=0,
                started_at_value=None,
                finished_at_value=finished_at,
                error_text=error if quota_blocked else None,
            )

        audit_records = [audit_by_symbol[symbol] for symbol in symbols]
        _base._write_dated_audit_csv(audit_path, audit_records)
        manifest = _base._build_dated_manifest(
            dataset_name="instrument_industry",
            api_name="rqdatac.get_instrument_industry",
            output_dir=output_dir,
            fields=fields,
            field_metadata=field_metadata,
            symbol_metadata=symbol_metadata,
            symbols_requested=symbols,
            entries=[entries_by_symbol[symbol] for symbol in symbols if symbol in entries_by_symbol],
            missing_symbols=[item.ts_code for item in audit_records if item.status == "missing_remote"],
            start_date=start_date,
            end_date=end_date,
            date_column="date",
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
        manifest_query = manifest.get("query", {})
        if isinstance(manifest_query, dict):
            manifest_query["source"] = source
            manifest_query["level"] = level
            manifest_query["rebalance_frequency"] = snapshot_metadata.get("rebalance_frequency")
            manifest_query["dates_count"] = len(snapshot_dates)
            manifest_query["dates_file"] = str(output_dir / "dates.txt")
        manifest["date_source"] = snapshot_metadata
        _base._write_manifest(output_dir / "manifest.yml", manifest)

    totals = {
        "files": len(entries_by_symbol),
        "symbols": len(entries_by_symbol),
        "rows": sum(item.rows for item in entries_by_symbol.values()),
        "bytes": sum(item.total_bytes for item in entries_by_symbol.values()),
    }
    print(
        f"Wrote instrument_industry mirror to {output_dir} "
        f"({totals['symbols']} symbols, {totals['files']} files, {totals['rows']} rows, {totals['bytes']} bytes, status={status})"
    )
    return result_code


def mirror_hk_industry_changes(args, rqdatac) -> int:
    source = _base._resolve_hk_industry_source(args)
    level = _base._resolve_hk_industry_change_level(args)
    symbols, symbol_metadata = _base._resolve_symbols(args)
    start_date = _base._normalize_absolute_date(args.start_date, label="--start-date")
    end_date = _base._normalize_absolute_date(args.end_date, label="--end-date")
    if start_date > end_date:
        raise SystemExit("--start-date must be <= --end-date.")

    mapping_date = getattr(args, "mapping_date", None)
    mapping_date = _base._normalize_absolute_date(mapping_date, label="--mapping-date") if mapping_date else end_date
    catalog = _base._build_hk_industry_catalog(
        rqdatac,
        source=source,
        level=level,
        mapping_date=mapping_date,
    )
    industries = catalog["industry_code"].astype(str).tolist()
    resume = bool(getattr(args, "resume", False))
    skip_existing = bool(getattr(args, "skip_existing", False) or resume)
    max_attempts = max(1, int(getattr(args, "max_attempts", _base.DEFAULT_MIRROR_MAX_ATTEMPTS) or 1))
    backoff_seconds = float(getattr(args, "backoff_seconds", _base.DEFAULT_MIRROR_BACKOFF_SECONDS))
    max_backoff_seconds = float(
        getattr(args, "max_backoff_seconds", _base.DEFAULT_MIRROR_MAX_BACKOFF_SECONDS)
    )
    output_dir = _base._prepare_daily_output_dir(
        out_root=getattr(args, "out_root", _base.DEFAULT_OUT_ROOT),
        dataset_name="industry_changes",
        start_date=start_date,
        end_date=end_date,
        name=getattr(args, "name", None),
        resume=resume,
    )
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    audit_path = output_dir / "audit.csv"
    catalog_path = output_dir / "industry_catalog.parquet"

    symbol_map = {_base._to_rqdata_symbol("hk", symbol): symbol for symbol in symbols}
    order_book_ids = list(symbol_map.keys())
    fields = [
        "cancel_date",
        "industry_code",
        "industry_name",
        "industry_level",
        "industry_source",
        *_base.HK_INDUSTRY_HIERARCHY_COLUMNS,
    ]
    field_metadata = {
        "count": len(fields),
        "fields_file": [],
        "source": f"industry_mapping_level_{level}",
        "base_fields": list(fields),
    }
    entries_by_symbol: dict[str, _base.DatedMirrorEntry] = {}
    audit_by_symbol: dict[str, _base.DatedMirrorAuditRecord] = {}
    frames_by_symbol: dict[str, list[pd.DataFrame]] = {}
    batches: list[dict[str, object]] = []
    columns: list[str] = []
    field_coverage = _base._field_coverage_template(fields)
    started_at = _base._timestamp_now()
    status = "completed"
    error: str | None = None
    result_code = 0
    quota_blocked = False

    def _record_entry(
        *,
        symbol: str,
        entry: _base.DatedMirrorEntry,
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
        audit_by_symbol[symbol] = _base._dated_audit_record(
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
        audit_by_symbol[symbol] = _base._dated_audit_record(
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

    try:
        if resume:
            _base._validate_dated_resume_inputs(
                output_dir=output_dir,
                dataset_name="industry_changes",
                fields=fields,
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
            )
            manifest = _base._load_manifest(output_dir / "manifest.yml") or {}
            query = manifest.get("query") if isinstance(manifest.get("query"), Mapping) else {}
            if isinstance(query, Mapping):
                if query.get("source") not in {None, source}:
                    raise SystemExit(
                        f"Resume target query mismatch for source: expected {source!r}, got {query.get('source')!r}."
                    )
                if query.get("level") not in {None, level}:
                    raise SystemExit(
                        f"Resume target query mismatch for level: expected {level!r}, got {query.get('level')!r}."
                    )
                if query.get("mapping_date") not in {None, mapping_date}:
                    raise SystemExit(
                        f"Resume target query mismatch for mapping_date: expected {mapping_date!r}, got {query.get('mapping_date')!r}."
                    )
            existing_industries = _base._load_existing_text_list(output_dir / "industries.txt", strip=False)
            if existing_industries and list(existing_industries) != list(industries):
                raise SystemExit("Resume target industries.txt does not match the requested industry list.")

        _base._write_text_list(output_dir / "fields.txt", fields)
        _base._write_text_list(output_dir / "symbols.txt", symbols)
        _base._write_text_list(output_dir / "industries.txt", industries)
        catalog.to_parquet(catalog_path, index=False)

        pending_order_book_ids: list[str] = []
        for order_book_id in order_book_ids:
            symbol = symbol_map[order_book_id]
            out_path = data_dir / f"{symbol}.parquet"
            if skip_existing and out_path.exists():
                try:
                    entry, symbol_frame = _base._load_existing_dated_entry(
                        out_path,
                        date_column="start_date",
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

        pending_symbol_set = {symbol_map[order_book_id] for order_book_id in pending_order_book_ids}
        for industry_row in catalog.itertuples(index=False):
            if quota_blocked or not pending_symbol_set:
                break
            industry_code = str(getattr(industry_row, "industry_code"))
            industry_name = str(getattr(industry_row, "industry_name"))
            batch_started_at = _base._timestamp_now()
            try:
                payload, attempts = _base._retry_fetch(
                    f"industry change fetch failed for {industry_code}",
                    lambda: rqdatac.get_industry_change(
                        industry=industry_code,
                        source=source,
                        level=level,
                        market="hk",
                    ),
                    max_attempts=max_attempts,
                    backoff_seconds=backoff_seconds,
                    max_backoff_seconds=max_backoff_seconds,
                )
            except _base.MirrorQuotaError as exc:
                quota_blocked = True
                status = "stopped_quota"
                error = str(exc)
                result_code = max(result_code, 2)
                batches.append(
                    {
                        "industry_code": industry_code,
                        "industry_name": industry_name,
                        "rows": 0,
                        "status": "quota_blocked",
                        "attempts": exc.attempts,
                        "error": str(exc),
                    }
                )
                break
            except _base.MirrorFetchError as exc:
                batches.append(
                    {
                        "industry_code": industry_code,
                        "industry_name": industry_name,
                        "rows": 0,
                        "status": "failed",
                        "attempts": exc.attempts,
                        "error": str(exc),
                    }
                )
                if status == "completed":
                    status = "completed_with_failures"
                result_code = max(result_code, 1)
                continue

            prepared = _base._prepare_hk_industry_change_frame(
                payload,
                catalog_row=industry_row._asdict(),
                symbol_filter=pending_symbol_set,
                start_date=start_date,
                end_date=end_date,
            )
            prepared = _base._ensure_requested_fields(prepared, fields)
            batches.append(
                {
                    "industry_code": industry_code,
                    "industry_name": industry_name,
                    "rows": int(len(prepared)),
                    "status": "completed",
                    "attempts": attempts,
                    "started_at": batch_started_at,
                    "finished_at": _base._timestamp_now(),
                }
            )
            if prepared.empty:
                continue
            for symbol in prepared["ts_code"].drop_duplicates().tolist():
                symbol_frame = prepared[prepared["ts_code"] == symbol].reset_index(drop=True)
                if symbol_frame.empty:
                    continue
                frames_by_symbol.setdefault(symbol, []).append(symbol_frame)

        if result_code == 1 and status == "completed":
            status = "completed_with_failures"
    except Exception as exc:
        status = "failed"
        error = str(exc)
        result_code = max(result_code, 1)
        raise
    finally:
        finished_at = _base._timestamp_now()
        for order_book_id in pending_order_book_ids if "pending_order_book_ids" in locals() else order_book_ids:
            symbol = symbol_map[order_book_id]
            if symbol in audit_by_symbol:
                continue
            frames = frames_by_symbol.get(symbol) or []
            if frames:
                combined = pd.concat(frames, ignore_index=True)
                combined = combined.drop_duplicates(
                    subset=["start_date", "industry_code"],
                    keep="last",
                )
                combined = combined.sort_values(
                    [column for column in ("start_date", "cancel_date", "industry_code") if column in combined.columns]
                ).reset_index(drop=True)
                entry = _base._write_dated_symbol_frame(data_dir, combined, date_column="start_date")
                _record_entry(
                    symbol=symbol,
                    entry=entry,
                    symbol_frame=combined,
                    record_status="written",
                    attempts=0,
                    started_at_value=started_at,
                    finished_at_value=finished_at,
                    error_text=error if quota_blocked else None,
                )
                continue
            _record_non_entry(
                symbol=symbol,
                order_book_id=order_book_id,
                record_status="quota_blocked" if quota_blocked else "missing_remote",
                attempts=0,
                started_at_value=None,
                finished_at_value=finished_at,
                error_text=error if quota_blocked else None,
            )

        audit_records = [audit_by_symbol[symbol] for symbol in symbols]
        _base._write_dated_audit_csv(audit_path, audit_records)
        manifest = _base._build_dated_manifest(
            dataset_name="industry_changes",
            api_name="rqdatac.get_industry_change",
            output_dir=output_dir,
            fields=fields,
            field_metadata=field_metadata,
            symbol_metadata=symbol_metadata,
            symbols_requested=symbols,
            entries=[entries_by_symbol[symbol] for symbol in symbols if symbol in entries_by_symbol],
            missing_symbols=[item.ts_code for item in audit_records if item.status == "missing_remote"],
            start_date=start_date,
            end_date=end_date,
            date_column="start_date",
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
        manifest_query = manifest.get("query", {})
        if isinstance(manifest_query, dict):
            manifest_query["source"] = source
            manifest_query["level"] = level
            manifest_query["mapping_date"] = mapping_date
            manifest_query["industries_count"] = len(industries)
            manifest_query["industries_file"] = str(output_dir / "industries.txt")
        manifest["industry_catalog_file"] = str(catalog_path)
        _base._write_manifest(output_dir / "manifest.yml", manifest)

    totals = {
        "files": len(entries_by_symbol),
        "symbols": len(entries_by_symbol),
        "rows": sum(item.rows for item in entries_by_symbol.values()),
        "bytes": sum(item.total_bytes for item in entries_by_symbol.values()),
    }
    print(
        f"Wrote industry_changes mirror to {output_dir} "
        f"({totals['symbols']} symbols, {totals['files']} files, {totals['rows']} rows, {totals['bytes']} bytes, status={status})"
    )
    return result_code
