from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
import time

import numpy as np
import pandas as pd

from . import args as _args
from .shared import (
    DATE_TEXT_OUTPUT_COLUMNS,
    DEFAULT_HK_DAILY_FIELDS,
    DEFAULT_HK_EXCHANGE_RATE_FIELDS,
    DEFAULT_HK_INDUSTRY_CHANGE_LEVEL,
    DEFAULT_HK_INDUSTRY_LABELS_FILENAME_PREFIX,
    DEFAULT_HK_INDUSTRY_SOURCE,
    DEFAULT_HK_INSTRUMENT_INDUSTRY_LEVEL,
    DEFAULT_HK_SHARES_FIELDS,
    DEFAULT_HK_VALUATION_FIELDS,
    DEFAULT_PIPELINE_FUNDAMENTALS_NAME,
    DERIVED_PIT_FEATURES,
    HK_INDUSTRY_HIERARCHY_COLUMNS,
    HK_INSTRUMENT_INDUSTRY_FIELDS,
    PIT_METADATA_COLUMNS,
    STARTER_HK_FINANCIAL_FIELDS,
    _coerce_bool,
    _dedupe_preserve_order,
    _drop_conflicting_index_levels,
    _git_metadata,
    _load_hk_financial_fields,
    _load_manifest,
    _load_symbols_from_by_date,
    _load_text_list,
    _normalize_absolute_date,
    _normalize_field_list,
    _normalize_frame_columns,
    _normalize_hk_symbol,
    _path_mtime_iso,
    _prepare_daily_output_dir,
    _prepare_output_dir,
    _resolve_daily_fields,
    _resolve_default_plus_explicit_fields,
    _resolve_optional_explicit_fields,
    _resolve_path,
    _resolve_fields_with_overrides,
    _resolve_universe_by_date_columns,
    _split_daily_range_by_year,
    _timestamp_now,
    _load_existing_text_list,
    _write_text_list,
    _write_manifest,
)
from ...artifacts import (
    RQDATA_ASSETS_DIR as DEFAULT_RQDATA_ASSETS_DIR,
)
from ...config_utils import resolve_pipeline_config
from ...data_providers import (
    _fetch_daily_rqdata,
    _to_rqdata_symbol,
)
from ...rebalance import get_rebalance_dates

DEFAULT_OUT_ROOT = DEFAULT_RQDATA_ASSETS_DIR.as_posix()
DEFAULT_BATCH_SIZE = 20
DEFAULT_HK_INSTRUMENTS_FILENAME_PREFIX = "hk_instruments"
DEFAULT_HK_INSTRUMENTS_DIR = DEFAULT_RQDATA_ASSETS_DIR / "hk" / "instruments"
DEFAULT_MIRROR_MAX_ATTEMPTS = 3
DEFAULT_MIRROR_BACKOFF_SECONDS = 1.0
DEFAULT_MIRROR_MAX_BACKOFF_SECONDS = 30.0
DEFAULT_HK_SOUTHBOUND_TRADING_TYPES = ("sh", "sz")


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


@dataclass(frozen=True)
class DailyMirrorEntry:
    ts_code: str
    order_book_id: str
    path: Path
    rows: int
    total_bytes: int
    min_trade_date: str | None
    max_trade_date: str | None


@dataclass(frozen=True)
class DailyMirrorAuditRecord:
    ts_code: str
    order_book_id: str
    status: str
    attempts: int
    rows: int
    total_bytes: int
    min_trade_date: str | None
    max_trade_date: str | None
    started_at: str | None
    finished_at: str | None
    file_mtime: str | None
    error: str | None


@dataclass(frozen=True)
class DatedMirrorEntry:
    ts_code: str
    order_book_id: str
    path: Path
    rows: int
    total_bytes: int
    min_date: str | None
    max_date: str | None


@dataclass(frozen=True)
class DatedMirrorAuditRecord:
    ts_code: str
    order_book_id: str
    status: str
    attempts: int
    rows: int
    total_bytes: int
    min_date: str | None
    max_date: str | None
    started_at: str | None
    finished_at: str | None
    file_mtime: str | None
    dropped_fields: str | None
    error: str | None


@dataclass(frozen=True)
class DatedRequestGroup:
    ts_code: str
    request_ids: tuple[str, ...]
    order_book_ids: tuple[str, ...]


class MirrorFetchError(RuntimeError):
    def __init__(self, message: str, *, attempts: int):
        super().__init__(message)
        self.attempts = attempts


class MirrorQuotaError(MirrorFetchError):
    pass


_HK_INSTRUMENTS_FRAME_CACHE: dict[Path, pd.DataFrame] = {}


def _resolve_fields(args) -> tuple[list[str], dict]:
    return _resolve_fields_with_overrides(
        args,
        load_hk_financial_fields_override=_load_hk_financial_fields,
    )


def _resolve_hk_industry_source(args) -> str:
    source = str(getattr(args, "source", DEFAULT_HK_INDUSTRY_SOURCE) or DEFAULT_HK_INDUSTRY_SOURCE).strip()
    if not source:
        raise SystemExit("--source must not be empty.")
    return source


def _resolve_hk_instrument_industry_level(args) -> tuple[int, list[str]]:
    raw_level = str(
        getattr(args, "level", DEFAULT_HK_INSTRUMENT_INDUSTRY_LEVEL)
        if getattr(args, "level", None) is not None
        else DEFAULT_HK_INSTRUMENT_INDUSTRY_LEVEL
    ).strip()
    try:
        level = int(raw_level)
    except ValueError as exc:
        raise SystemExit("--level for mirror-hk-instrument-industry must be one of 0/1/2/3.") from exc
    if level not in HK_INSTRUMENT_INDUSTRY_FIELDS:
        raise SystemExit("--level for mirror-hk-instrument-industry must be one of 0/1/2/3.")
    return level, list(HK_INSTRUMENT_INDUSTRY_FIELDS[level])


def _resolve_hk_industry_change_level(args) -> int:
    raw_level = str(
        getattr(args, "level", DEFAULT_HK_INDUSTRY_CHANGE_LEVEL)
        if getattr(args, "level", None) is not None
        else DEFAULT_HK_INDUSTRY_CHANGE_LEVEL
    ).strip()
    try:
        level = int(raw_level)
    except ValueError as exc:
        raise SystemExit("--level for mirror-hk-industry-changes must be one of 1/2/3.") from exc
    if level not in {1, 2, 3}:
        raise SystemExit("--level for mirror-hk-industry-changes must be one of 1/2/3.")
    return level


def _resolve_hk_rebalance_frequency(args, *, default: str = "M") -> str:
    freq = str(getattr(args, "rebalance_frequency", default) or default).strip().upper()
    if not freq:
        raise SystemExit("--rebalance-frequency must not be empty.")
    return freq


def _resolve_hk_snapshot_dates(
    args,
    *,
    start_date: str,
    end_date: str,
) -> tuple[list[str], dict]:
    start_ts = pd.to_datetime(start_date, format="%Y%m%d", errors="coerce")
    end_ts = pd.to_datetime(end_date, format="%Y%m%d", errors="coerce")
    if pd.isna(start_ts) or pd.isna(end_ts):
        raise SystemExit("Unable to resolve snapshot dates from the requested date range.")

    frequency = _resolve_hk_rebalance_frequency(args)
    by_date_file = getattr(args, "by_date_file", None)
    if by_date_file:
        universe = _load_universe_by_date_frame(by_date_file)
        candidates = universe[
            (universe["trade_date"] >= start_ts.normalize())
            & (universe["trade_date"] <= end_ts.normalize())
        ]["trade_date"].drop_duplicates().tolist()
        source_meta = {
            "mode": "by_date_file",
            "by_date_file": str(_resolve_path(by_date_file)),
        }
    else:
        candidates = pd.date_range(start_ts.normalize(), end_ts.normalize(), freq="D").tolist()
        source_meta = {"mode": "calendar_range"}

    if not candidates:
        raise SystemExit("No snapshot dates resolved for industry mirroring.")

    if frequency != "D":
        dates = list(pd.to_datetime(get_rebalance_dates(sorted(candidates), frequency)))
    else:
        dates = list(pd.to_datetime(sorted(candidates)))
    normalized = [pd.Timestamp(item).normalize().strftime("%Y%m%d") for item in dates]
    normalized = _dedupe_preserve_order(normalized)
    if not normalized:
        raise SystemExit("No rebalance dates resolved for industry mirroring.")
    source_meta["rebalance_frequency"] = frequency
    source_meta["count"] = len(normalized)
    return normalized, source_meta


def _resolve_hk_trading_snapshot_dates(
    rqdatac,
    args,
    *,
    start_date: str,
    end_date: str,
) -> tuple[list[str], dict]:
    start_ts = pd.to_datetime(start_date, format="%Y%m%d", errors="coerce")
    end_ts = pd.to_datetime(end_date, format="%Y%m%d", errors="coerce")
    if pd.isna(start_ts) or pd.isna(end_ts):
        raise SystemExit("Unable to resolve trading dates from the requested date range.")

    frequency = _resolve_hk_rebalance_frequency(args, default="D")
    by_date_file = getattr(args, "by_date_file", None)
    if by_date_file:
        universe = _load_universe_by_date_frame(by_date_file)
        candidates = universe[
            (universe["trade_date"] >= start_ts.normalize())
            & (universe["trade_date"] <= end_ts.normalize())
        ]["trade_date"].drop_duplicates().tolist()
        source_meta = {
            "mode": "by_date_file",
            "by_date_file": str(_resolve_path(by_date_file)),
        }
    else:
        candidates = list(pd.to_datetime(rqdatac.get_trading_dates(start_date, end_date, market="hk")))
        source_meta = {"mode": "trading_calendar", "market": "hk"}

    if not candidates:
        raise SystemExit("No trading dates resolved for southbound mirroring.")

    if frequency != "D":
        dates = list(pd.to_datetime(get_rebalance_dates(sorted(candidates), frequency)))
    else:
        dates = list(pd.to_datetime(sorted(candidates)))
    normalized = [pd.Timestamp(item).normalize().strftime("%Y%m%d") for item in dates]
    normalized = _dedupe_preserve_order(normalized)
    if not normalized:
        raise SystemExit("No rebalance dates resolved for southbound mirroring.")
    source_meta["rebalance_frequency"] = frequency
    source_meta["count"] = len(normalized)
    return normalized, source_meta


def _resolve_hk_southbound_trading_types(args) -> list[str]:
    raw_values = list(getattr(args, "trading_type", None) or ["both"])
    resolved: list[str] = []
    for raw in raw_values:
        text = str(raw or "").strip().lower()
        if not text:
            continue
        if text == "both":
            resolved.extend(DEFAULT_HK_SOUTHBOUND_TRADING_TYPES)
            continue
        if text not in DEFAULT_HK_SOUTHBOUND_TRADING_TYPES:
            raise SystemExit("--trading-type must be one of: sh, sz, both.")
        resolved.append(text)
    normalized = _dedupe_preserve_order(resolved)
    if not normalized:
        raise SystemExit("No southbound trading types resolved.")
    return normalized


def _reset_frame_index(frame: pd.DataFrame | pd.Series | None) -> pd.DataFrame:
    if frame is None:
        return pd.DataFrame()
    if isinstance(frame, pd.Series):
        frame = frame.to_frame(name=str(frame.name or "value"))
    if frame.empty and len(frame.columns) == 0:
        return frame.copy()
    normalized = _normalize_frame_columns(frame)
    normalized = _drop_conflicting_index_levels(normalized)
    if isinstance(normalized.index, pd.MultiIndex):
        has_named_levels = any(name is not None for name in normalized.index.names)
    else:
        has_named_levels = normalized.index.name is not None
    if "order_book_id" in normalized.columns and not has_named_levels:
        return normalized
    if not has_named_levels:
        return normalized
    reset = _normalize_frame_columns(normalized.reset_index())
    if "order_book_id" not in reset.columns and "index" in reset.columns:
        reset = reset.rename(columns={"index": "order_book_id"})
    return reset


def _prepare_hk_instrument_industry_frame(
    frame: pd.DataFrame | pd.Series | None,
    *,
    symbol_map: Mapping[str, str],
    query_date: str,
) -> pd.DataFrame:
    normalized = _reset_frame_index(frame)
    if normalized.empty:
        return normalized
    if "order_book_id" not in normalized.columns:
        raise ValueError("RQData payload is missing order_book_id.")
    normalized["order_book_id"] = normalized["order_book_id"].astype(str).str.strip()
    normalized["ts_code"] = normalized["order_book_id"].map(
        lambda value: symbol_map.get(value) or _normalize_hk_symbol(value)
    )
    normalized = normalized[normalized["ts_code"] != ""].copy()
    normalized["date"] = pd.to_datetime(query_date, format="%Y%m%d", errors="coerce")
    preferred = [column for column in ("ts_code", "order_book_id", "date") if column in normalized.columns]
    remaining = [column for column in normalized.columns if column not in preferred]
    work = normalized.loc[:, preferred + remaining].copy()
    return work.sort_values(["ts_code", "date"]).reset_index(drop=True)


def _build_hk_industry_catalog(
    rqdatac,
    *,
    source: str,
    level: int,
    mapping_date: str | None,
) -> pd.DataFrame:
    catalog = rqdatac.get_industry_mapping(source=source, date=mapping_date, market="hk")
    if catalog is None or (isinstance(catalog, pd.DataFrame) and catalog.empty):
        raise SystemExit("rqdatac.get_industry_mapping returned no HK industry mapping rows.")
    normalized = _reset_frame_index(catalog)
    code_column = {1: "first_industry_code", 2: "second_industry_code", 3: "third_industry_code"}[level]
    name_column = {1: "first_industry_name", 2: "second_industry_name", 3: "third_industry_name"}[level]
    required_columns = [code_column, name_column, *HK_INDUSTRY_HIERARCHY_COLUMNS]
    missing = [column for column in required_columns if column not in normalized.columns]
    if missing:
        raise SystemExit(
            "Industry mapping payload is missing required columns: " + ", ".join(missing)
        )

    normalized = normalized.loc[:, _dedupe_preserve_order(required_columns)].copy()
    normalized[code_column] = normalized[code_column].astype(str).str.strip()
    normalized[name_column] = normalized[name_column].astype(str).str.strip()
    normalized = normalized[
        (normalized[code_column] != "")
        & (normalized[name_column] != "")
    ].copy()
    normalized = normalized.drop_duplicates(subset=[code_column, name_column]).sort_values(
        [code_column, name_column],
        kind="mergesort",
    )
    normalized["industry_code"] = normalized[code_column]
    normalized["industry_name"] = normalized[name_column]
    normalized["industry_level"] = level
    normalized["industry_source"] = source
    normalized.reset_index(drop=True, inplace=True)
    return normalized


def _prepare_hk_industry_change_frame(
    frame: pd.DataFrame | pd.Series | None,
    *,
    catalog_row: Mapping[str, object],
    symbol_filter: set[str],
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    normalized = _reset_frame_index(frame)
    if normalized.empty:
        return normalized
    if "order_book_id" not in normalized.columns:
        raise ValueError("RQData payload is missing order_book_id.")
    if "start_date" not in normalized.columns or "cancel_date" not in normalized.columns:
        raise ValueError("RQData payload is missing start_date/cancel_date.")

    normalized["order_book_id"] = normalized["order_book_id"].astype(str).str.strip()
    normalized["ts_code"] = normalized["order_book_id"].map(_normalize_hk_symbol)
    normalized = normalized[normalized["ts_code"].isin(symbol_filter)].copy()
    if normalized.empty:
        return normalized

    overlap_start = pd.to_datetime(start_date, format="%Y%m%d", errors="coerce")
    overlap_end = pd.to_datetime(end_date, format="%Y%m%d", errors="coerce")
    normalized["start_date"] = pd.to_datetime(normalized["start_date"], errors="coerce")
    normalized["cancel_date"] = pd.to_datetime(normalized["cancel_date"], errors="coerce")
    overlap_mask = normalized["start_date"].notna() & (
        (normalized["start_date"] <= overlap_end) &
        (normalized["cancel_date"].isna() | (normalized["cancel_date"] >= overlap_start))
    )
    normalized = normalized[overlap_mask].copy()
    if normalized.empty:
        return normalized

    for column in ("industry_code", "industry_name", "industry_level", "industry_source", *HK_INDUSTRY_HIERARCHY_COLUMNS):
        if column in catalog_row:
            normalized[column] = catalog_row[column]

    preferred = [column for column in ("ts_code", "order_book_id", "start_date") if column in normalized.columns]
    remaining = [column for column in normalized.columns if column not in preferred]
    work = normalized.loc[:, preferred + remaining].copy()
    sort_columns = [column for column in ("ts_code", "start_date", "cancel_date", "industry_code") if column in work.columns]
    return work.sort_values(sort_columns).reset_index(drop=True)


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


def _resolve_instrument_symbol_filter(args) -> tuple[list[str] | None, dict]:
    explicit_values = list(getattr(args, "symbol", None) or [])
    symbols_file = getattr(args, "symbols_file", None)
    by_date_file = getattr(args, "by_date_file", None)
    use_config_universe = bool(getattr(args, "use_config_universe", False))
    limit = getattr(args, "limit", None)
    if limit is not None and limit <= 0:
        raise SystemExit("--limit must be > 0.")

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
    elif use_config_universe:
        config_ref = getattr(args, "config", None)
        if not config_ref:
            raise SystemExit("--use-config-universe requires --config.")
        symbols, metadata = _resolve_symbols_from_config(config_ref)
    else:
        return None, {
            "mode": "all_instruments",
            "config_ref": str(getattr(args, "config", None) or "") or None,
            "limit": limit,
        }

    normalized = _dedupe_preserve_order(_normalize_hk_symbol(symbol) for symbol in symbols)
    if limit is not None:
        normalized = normalized[:limit]
    if not normalized:
        raise SystemExit("No HK symbols resolved for instrument export.")
    metadata["count"] = len(normalized)
    metadata["limit"] = limit
    return normalized, metadata


def _default_hk_instruments_out_path() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return (
        _resolve_path(DEFAULT_OUT_ROOT)
        / "hk"
        / "instruments"
        / f"{DEFAULT_HK_INSTRUMENTS_FILENAME_PREFIX}_{timestamp}.parquet"
    )


def _candidate_hk_instruments_snapshot_paths(out_root: str | Path) -> list[Path]:
    instruments_dir = _resolve_path(out_root) / "hk" / "instruments"
    if not instruments_dir.exists():
        return []
    paths = [path for path in instruments_dir.glob("*.parquet") if path.is_file()]
    return sorted(
        paths,
        key=lambda path: (
            0 if "all_instruments" in path.name.lower() else 1,
            -path.stat().st_mtime,
            path.name,
        ),
    )


def _load_cached_hk_instruments_frame(path: Path) -> pd.DataFrame:
    cached = _HK_INSTRUMENTS_FRAME_CACHE.get(path)
    if cached is not None:
        return cached.copy()

    frame = pd.read_parquet(path)
    instruments = _normalize_frame_columns(frame.copy())
    if "ts_code" not in instruments.columns or "order_book_id" not in instruments.columns:
        raise ValueError(f"HK instruments snapshot is missing ts_code/order_book_id: {path}")

    instruments["ts_code"] = instruments["ts_code"].map(_normalize_hk_symbol)
    instruments["order_book_id"] = instruments["order_book_id"].astype(str).str.strip()
    if "unique_id" in instruments.columns:
        instruments["unique_id"] = instruments["unique_id"].astype(str).str.strip()
        instruments.loc[instruments["unique_id"] == "", "unique_id"] = pd.NA
    else:
        instruments["unique_id"] = pd.NA
    _HK_INSTRUMENTS_FRAME_CACHE[path] = instruments.copy()
    return instruments


def _build_default_dated_request_groups(
    symbols: Sequence[str],
) -> tuple[list[DatedRequestGroup], dict[str, dict[str, str | None]], dict[str, object]]:
    groups: list[DatedRequestGroup] = []
    metadata: dict[str, dict[str, str | None]] = {}
    for symbol in symbols:
        order_book_id = _to_rqdata_symbol("hk", symbol)
        groups.append(
            DatedRequestGroup(
                ts_code=symbol,
                request_ids=(order_book_id,),
                order_book_ids=(order_book_id,),
            )
        )
        metadata[order_book_id] = {
            "ts_code": symbol,
            "order_book_id": order_book_id,
            "unique_id": None,
        }
    return groups, metadata, {"mode": "default_order_book_id", "file": None}


def _resolve_hk_dated_request_groups(
    symbols: Sequence[str],
    *,
    start_date: str,
    end_date: str,
    out_root: str,
) -> tuple[list[DatedRequestGroup], dict[str, dict[str, str | None]], dict[str, object]]:
    default_groups, default_metadata, default_info = _build_default_dated_request_groups(symbols)
    snapshot_paths = _candidate_hk_instruments_snapshot_paths(out_root)
    if not snapshot_paths:
        return default_groups, default_metadata, default_info

    start_ts = pd.to_datetime(start_date, errors="coerce")
    end_ts = pd.to_datetime(end_date, errors="coerce")
    if pd.isna(start_ts) or pd.isna(end_ts):
        return default_groups, default_metadata, default_info

    for path in snapshot_paths:
        try:
            instruments = _load_cached_hk_instruments_frame(path)
        except Exception:
            continue

        subset = instruments[instruments["ts_code"].isin(symbols)].copy()
        if subset.empty:
            continue

        if "listed_date" in subset.columns:
            subset["listed_date_parsed"] = pd.to_datetime(subset["listed_date"], errors="coerce")
        else:
            subset["listed_date_parsed"] = pd.NaT
        if "de_listed_date" in subset.columns:
            delisted_text = subset["de_listed_date"].astype(str).str.strip()
            delisted_text = delisted_text.mask(delisted_text == "0000-00-00")
            subset["de_listed_date_parsed"] = pd.to_datetime(delisted_text, errors="coerce")
        else:
            subset["de_listed_date_parsed"] = pd.NaT

        overlap_mask = (
            subset["listed_date_parsed"].isna() | (subset["listed_date_parsed"] <= end_ts)
        ) & (
            subset["de_listed_date_parsed"].isna() | (subset["de_listed_date_parsed"] >= start_ts)
        )
        overlapping = subset[overlap_mask].copy()
        effective = overlapping if not overlapping.empty else subset

        groups: list[DatedRequestGroup] = []
        metadata: dict[str, dict[str, str | None]] = {}
        for symbol in symbols:
            symbol_rows = effective[effective["ts_code"] == symbol].copy()
            if symbol_rows.empty:
                fallback_order_book_id = _to_rqdata_symbol("hk", symbol)
                groups.append(
                    DatedRequestGroup(
                        ts_code=symbol,
                        request_ids=(fallback_order_book_id,),
                        order_book_ids=(fallback_order_book_id,),
                    )
                )
                metadata[fallback_order_book_id] = {
                    "ts_code": symbol,
                    "order_book_id": fallback_order_book_id,
                    "unique_id": None,
                }
                continue

            symbol_rows = symbol_rows.sort_values(
                ["listed_date_parsed", "order_book_id", "unique_id"],
                kind="mergesort",
            )
            request_ids: list[str] = []
            order_book_ids: list[str] = []
            for row in symbol_rows.itertuples(index=False):
                order_book_id = str(getattr(row, "order_book_id") or "").strip()
                unique_id = str(getattr(row, "unique_id") or "").strip() or None
                request_id = unique_id or order_book_id
                if not request_id:
                    continue
                request_ids.append(request_id)
                order_book_ids.append(order_book_id or request_id)
                metadata[request_id] = {
                    "ts_code": symbol,
                    "order_book_id": order_book_id or request_id,
                    "unique_id": unique_id,
                }
                metadata[order_book_id or request_id] = {
                    "ts_code": symbol,
                    "order_book_id": order_book_id or request_id,
                    "unique_id": unique_id,
                }

            request_ids = _dedupe_preserve_order(request_ids)
            order_book_ids = _dedupe_preserve_order(order_book_ids)
            if not request_ids:
                fallback_order_book_id = _to_rqdata_symbol("hk", symbol)
                request_ids = [fallback_order_book_id]
                order_book_ids = [fallback_order_book_id]
                metadata[fallback_order_book_id] = {
                    "ts_code": symbol,
                    "order_book_id": fallback_order_book_id,
                    "unique_id": None,
                }

            groups.append(
                DatedRequestGroup(
                    ts_code=symbol,
                    request_ids=tuple(request_ids),
                    order_book_ids=tuple(order_book_ids),
                )
            )

        return (
            groups,
            metadata,
            {
                "mode": "local_hk_instruments_snapshot",
                "file": str(path),
                "symbols_resolved": len(groups),
            },
        )

    return default_groups, default_metadata, default_info


def _uses_hk_unique_ids(request_ids: Sequence[str]) -> bool:
    for request_id in request_ids:
        prefix = str(request_id or "").strip().split(".", 1)[0]
        if "_" in prefix:
            return True
    return False


def _normalize_hk_dated_payload(
    payload,
    *,
    request_id_metadata: Mapping[str, Mapping[str, str | None]],
) -> pd.DataFrame | pd.Series | None:
    if payload is None:
        return None
    if isinstance(payload, (pd.DataFrame, pd.Series)):
        frame = payload.copy()
    else:
        frame = pd.DataFrame(payload)
    if isinstance(frame, pd.Series):
        return frame
    if frame.empty and len(frame.columns) == 0:
        return frame

    normalized = _normalize_frame_columns(frame)
    if "order_book_id" not in normalized.columns:
        return normalized

    raw_request_ids = normalized["order_book_id"].astype(str).str.strip()
    canonical_order_book_ids = raw_request_ids.map(
        lambda value: (request_id_metadata.get(value) or {}).get("order_book_id")
    )
    unique_ids = raw_request_ids.map(
        lambda value: (request_id_metadata.get(value) or {}).get("unique_id")
    )

    if "unique_id" not in normalized.columns:
        unique_series = unique_ids.where(unique_ids.notna(), raw_request_ids.where(raw_request_ids.str.contains("_")))
        if unique_series.notna().any():
            normalized["unique_id"] = unique_series
    else:
        existing_unique_ids = normalized["unique_id"].astype(str).str.strip()
        existing_unique_ids = existing_unique_ids.mask(existing_unique_ids == "")
        normalized["unique_id"] = existing_unique_ids.where(existing_unique_ids.notna(), unique_ids)

    normalized["order_book_id"] = canonical_order_book_ids.where(
        canonical_order_book_ids.notna(),
        raw_request_ids,
    )
    return normalized


def _normalize_hk_valuation_payload(
    payload,
    *,
    request_id_metadata: Mapping[str, Mapping[str, str | None]],
) -> pd.DataFrame | pd.Series | None:
    if payload is None:
        return None
    if isinstance(payload, pd.Series):
        frame = payload.to_frame(name=str(payload.name or "value"))
    elif isinstance(payload, pd.DataFrame):
        frame = payload.copy()
    else:
        frame = pd.DataFrame(payload)
    if frame.empty and len(frame.columns) == 0:
        return frame

    if isinstance(frame.index, pd.MultiIndex):
        raw_request_ids = frame.index.get_level_values(0).map(lambda value: str(value or "").strip())
        order_book_ids = raw_request_ids.map(
            lambda value: (request_id_metadata.get(value) or {}).get("order_book_id") or value
        )
        trade_dates = pd.to_datetime(frame.index.get_level_values(-1), errors="coerce")
        valid_trade_date = pd.Series(trade_dates.notna(), index=frame.index)
        normalized = frame.loc[valid_trade_date.values].copy()
        normalized.index = pd.MultiIndex.from_arrays(
            [
                order_book_ids[valid_trade_date.values].tolist(),
                trade_dates[valid_trade_date.values].strftime("%Y%m%d").tolist(),
            ],
            names=["order_book_id", "trade_date"],
        )
        return normalized

    trade_dates = pd.to_datetime(frame.index, errors="coerce")
    valid_trade_date = pd.Series(trade_dates.notna(), index=frame.index)
    normalized = frame.loc[valid_trade_date.values].copy()
    normalized.index = pd.Index(
        trade_dates[valid_trade_date.values].strftime("%Y%m%d").tolist(),
        name="trade_date",
    )
    return normalized


def _fetch_hk_ex_factors_direct(request_ids: Sequence[str], *, start_date: str, end_date: str) -> pd.DataFrame:
    from rqdatac.client import get_client

    payload = get_client().execute(
        "get_ex_factor",
        list(request_ids),
        int(start_date),
        int(end_date),
        market="hk",
    )
    return pd.DataFrame(payload or [])


def _fetch_hk_dividends_direct(request_ids: Sequence[str], *, start_date: str, end_date: str) -> pd.DataFrame:
    from rqdatac.client import get_client

    payload = get_client().execute(
        "get_dividend",
        list(request_ids),
        int(start_date),
        int(end_date),
        market="hk",
    )
    return pd.DataFrame(payload or [])


def _fetch_hk_shares_direct(
    request_ids: Sequence[str],
    *,
    fields: Sequence[str],
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    from rqdatac.client import get_client

    payload = get_client().execute(
        "get_shares_v2",
        list(request_ids),
        list(fields),
        start_date=int(start_date),
        end_date=int(end_date),
        market="hk",
    )
    return pd.DataFrame(payload or [])


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


def _validate_global_daily_resume_inputs(
    *,
    output_dir: Path,
    dataset_name: str,
    fields: Sequence[str],
    start_date: str,
    end_date: str,
) -> None:
    manifest = _load_manifest(output_dir / "manifest.yml")
    if manifest and manifest.get("dataset") not in {None, dataset_name}:
        raise SystemExit(
            f"Resume target dataset mismatch: expected {dataset_name!r}, got {manifest.get('dataset')!r}."
        )
    if manifest:
        query = manifest.get("query") if isinstance(manifest.get("query"), Mapping) else {}
        checks = [
            ("start_date", start_date),
            ("end_date", end_date),
        ]
        for key, expected in checks:
            actual = query.get(key) if isinstance(query, Mapping) else None
            if actual not in {None, expected}:
                raise SystemExit(
                    f"Resume target query mismatch for {key}: expected {expected!r}, got {actual!r}."
                )

    existing_fields = _load_existing_text_list(output_dir / "fields.txt", strip=False)
    if existing_fields and list(existing_fields) != list(fields):
        raise SystemExit("Resume target fields.txt does not match the requested field list.")


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

    normalized = _reset_frame_index(frame)
    if normalized.empty and "order_book_id" not in normalized.columns:
        return normalized
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
        if field not in coverage:
            continue
        if field in frame.columns:
            nonnull_rows = int(frame[field].notna().sum())
            if nonnull_rows == 0 and {"field", "amount"}.issubset(frame.columns):
                mask = frame["field"].astype(str) == str(field)
                mask = mask & frame["amount"].notna()
                nonnull_rows = int(mask.sum())
        elif {"field", "amount"}.issubset(frame.columns):
            mask = frame["field"].astype(str) == str(field)
            mask = mask & frame["amount"].notna()
            nonnull_rows = int(mask.sum())
        else:
            continue
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


def _prepare_daily_asset_frame(
    frame: pd.DataFrame | pd.Series | None,
    *,
    symbol: str,
    order_book_id: str,
) -> pd.DataFrame:
    if frame is None:
        return pd.DataFrame()
    if isinstance(frame, pd.Series):
        frame = frame.to_frame(name=str(frame.name or "value"))
    if frame.empty and len(frame.columns) == 0:
        return frame.copy()

    normalized = _normalize_frame_columns(frame)
    if "trade_date" not in normalized.columns and "date" in normalized.columns:
        normalized = normalized.rename(columns={"date": "trade_date"})
    if "trade_date" not in normalized.columns:
        reset = _normalize_frame_columns(frame.reset_index())
        if "trade_date" not in reset.columns and "date" in reset.columns:
            reset = reset.rename(columns={"date": "trade_date"})
        elif "trade_date" not in reset.columns and "index" in reset.columns:
            reset = reset.rename(columns={"index": "trade_date"})
        normalized = reset
    if "trade_date" not in normalized.columns:
        raise ValueError("RQData daily payload is missing trade_date.")

    trade_dates = pd.to_datetime(normalized["trade_date"], errors="coerce")
    valid_trade_date = trade_dates.notna()
    work = normalized.loc[valid_trade_date].copy()
    if work.empty:
        return work
    work["trade_date"] = trade_dates.loc[valid_trade_date].dt.strftime("%Y%m%d")
    work["ts_code"] = symbol
    work["order_book_id"] = order_book_id
    preferred = ["trade_date", "ts_code", "order_book_id"]
    remaining = [column for column in work.columns if column not in preferred]
    work = work.loc[:, preferred + remaining].copy()
    work = work.drop_duplicates(subset=["trade_date"], keep="last")
    work = work.sort_values(["trade_date"]).reset_index(drop=True)
    return work


def _daily_entry_from_symbol_frame(out_path: Path, symbol_frame: pd.DataFrame) -> DailyMirrorEntry:
    ts_code = str(symbol_frame["ts_code"].iloc[0])
    order_book_id = str(symbol_frame["order_book_id"].iloc[0])
    min_trade_date, max_trade_date = _series_bounds_as_text(symbol_frame, "trade_date")
    return DailyMirrorEntry(
        ts_code=ts_code,
        order_book_id=order_book_id,
        path=out_path,
        rows=int(len(symbol_frame)),
        total_bytes=int(out_path.stat().st_size),
        min_trade_date=min_trade_date,
        max_trade_date=max_trade_date,
    )


def _write_daily_symbol_frame(data_dir: Path, symbol_frame: pd.DataFrame) -> DailyMirrorEntry:
    ts_code = str(symbol_frame["ts_code"].iloc[0])
    out_path = data_dir / f"{ts_code}.parquet"
    symbol_frame.to_parquet(out_path, index=False)
    return _daily_entry_from_symbol_frame(out_path, symbol_frame)


def _load_daily_symbol_frame(path: Path, *, fields: Sequence[str]) -> pd.DataFrame:
    columns = ["trade_date", "ts_code", "order_book_id", *_field_columns_for_audit(fields)]
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


def _load_existing_daily_entry(path: Path, *, fields: Sequence[str]) -> tuple[DailyMirrorEntry, pd.DataFrame]:
    frame = _ensure_requested_fields(_load_daily_symbol_frame(path, fields=fields), fields)
    if frame.empty:
        ts_code = path.stem
        order_book_id = _to_rqdata_symbol("hk", ts_code)
        entry = DailyMirrorEntry(
            ts_code=ts_code,
            order_book_id=order_book_id,
            path=path,
            rows=0,
            total_bytes=int(path.stat().st_size),
            min_trade_date=None,
            max_trade_date=None,
        )
        return entry, frame
    return _daily_entry_from_symbol_frame(path, frame), frame


def _daily_audit_record(
    *,
    ts_code: str,
    order_book_id: str,
    status: str,
    attempts: int,
    started_at: str | None,
    finished_at: str | None,
    file_mtime: str | None,
    error: str | None,
    entry: DailyMirrorEntry | None = None,
) -> DailyMirrorAuditRecord:
    return DailyMirrorAuditRecord(
        ts_code=ts_code,
        order_book_id=order_book_id,
        status=status,
        attempts=attempts,
        rows=entry.rows if entry else 0,
        total_bytes=entry.total_bytes if entry else 0,
        min_trade_date=entry.min_trade_date if entry else None,
        max_trade_date=entry.max_trade_date if entry else None,
        started_at=started_at,
        finished_at=finished_at,
        file_mtime=file_mtime,
        error=error,
    )


def _write_daily_audit_csv(path: Path, records: Sequence[DailyMirrorAuditRecord]) -> None:
    rows = [
        {
            "ts_code": item.ts_code,
            "order_book_id": item.order_book_id,
            "status": item.status,
            "attempts": item.attempts,
            "rows": item.rows,
            "total_bytes": item.total_bytes,
            "min_trade_date": item.min_trade_date,
            "max_trade_date": item.max_trade_date,
            "started_at": item.started_at,
            "finished_at": item.finished_at,
            "file_mtime": item.file_mtime,
            "error": item.error,
        }
        for item in records
    ]
    pd.DataFrame(rows).to_csv(path, index=False)


def _prepare_dated_asset_frame(
    frame: pd.DataFrame | pd.Series | None,
    *,
    symbol_map: Mapping[str, str],
    date_column: str,
    sort_columns: Sequence[str] = (),
) -> pd.DataFrame:
    normalized = _prepare_asset_frame(frame, symbol_map=symbol_map)
    if normalized.empty:
        return normalized
    if date_column not in normalized.columns:
        raise ValueError(f"RQData payload is missing {date_column}.")
    parsed_dates = pd.to_datetime(normalized[date_column], errors="coerce")
    valid_dates = parsed_dates.notna()
    work = normalized.loc[valid_dates].copy()
    if work.empty:
        return work
    if date_column in DATE_TEXT_OUTPUT_COLUMNS:
        work[date_column] = parsed_dates.loc[valid_dates].dt.strftime("%Y%m%d")
    else:
        work[date_column] = parsed_dates.loc[valid_dates]

    preferred = [column for column in ["ts_code", "order_book_id", date_column] if column in work.columns]
    remaining = [column for column in work.columns if column not in preferred]
    work = work.loc[:, preferred + remaining].copy()
    ordered_sort_cols = [
        column for column in ["ts_code", date_column, *sort_columns] if column in work.columns
    ]
    if ordered_sort_cols:
        work = work.sort_values(ordered_sort_cols).reset_index(drop=True)
    return work


def _dated_entry_from_symbol_frame(
    out_path: Path,
    symbol_frame: pd.DataFrame,
    *,
    date_column: str,
) -> DatedMirrorEntry:
    ts_code = str(symbol_frame["ts_code"].iloc[0])
    order_book_id = (
        str(symbol_frame["order_book_id"].iloc[0])
        if "order_book_id" in symbol_frame.columns
        else _to_rqdata_symbol("hk", ts_code)
    )
    min_date, max_date = _series_bounds_as_date(symbol_frame, date_column)
    return DatedMirrorEntry(
        ts_code=ts_code,
        order_book_id=order_book_id,
        path=out_path,
        rows=int(len(symbol_frame)),
        total_bytes=int(out_path.stat().st_size),
        min_date=min_date,
        max_date=max_date,
    )


def _write_dated_symbol_frame(
    data_dir: Path,
    symbol_frame: pd.DataFrame,
    *,
    date_column: str,
) -> DatedMirrorEntry:
    ts_code = str(symbol_frame["ts_code"].iloc[0])
    out_path = data_dir / f"{ts_code}.parquet"
    symbol_frame.to_parquet(out_path, index=False)
    return _dated_entry_from_symbol_frame(out_path, symbol_frame, date_column=date_column)


def _load_dated_symbol_frame(path: Path, *, date_column: str, fields: Sequence[str]) -> pd.DataFrame:
    columns = ["ts_code", "order_book_id", date_column, *_field_columns_for_audit(fields)]
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


def _load_existing_dated_entry(
    path: Path,
    *,
    date_column: str,
    fields: Sequence[str],
) -> tuple[DatedMirrorEntry, pd.DataFrame]:
    frame = _ensure_requested_fields(_load_dated_symbol_frame(path, date_column=date_column, fields=fields), fields)
    if frame.empty:
        ts_code = path.stem
        order_book_id = _to_rqdata_symbol("hk", ts_code)
        entry = DatedMirrorEntry(
            ts_code=ts_code,
            order_book_id=order_book_id,
            path=path,
            rows=0,
            total_bytes=int(path.stat().st_size),
            min_date=None,
            max_date=None,
        )
        return entry, frame
    return _dated_entry_from_symbol_frame(path, frame, date_column=date_column), frame


def _dated_audit_record(
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
    entry: DatedMirrorEntry | None = None,
) -> DatedMirrorAuditRecord:
    return DatedMirrorAuditRecord(
        ts_code=ts_code,
        order_book_id=order_book_id,
        status=status,
        attempts=attempts,
        rows=entry.rows if entry else 0,
        total_bytes=entry.total_bytes if entry else 0,
        min_date=entry.min_date if entry else None,
        max_date=entry.max_date if entry else None,
        started_at=started_at,
        finished_at=finished_at,
        file_mtime=file_mtime,
        dropped_fields=",".join(str(item) for item in (dropped_fields or []) if str(item).strip()) or None,
        error=error,
    )


def _write_dated_audit_csv(path: Path, records: Sequence[DatedMirrorAuditRecord]) -> None:
    rows = [
        {
            "ts_code": item.ts_code,
            "order_book_id": item.order_book_id,
            "status": item.status,
            "attempts": item.attempts,
            "rows": item.rows,
            "total_bytes": item.total_bytes,
            "min_date": item.min_date,
            "max_date": item.max_date,
            "started_at": item.started_at,
            "finished_at": item.finished_at,
            "file_mtime": item.file_mtime,
            "dropped_fields": item.dropped_fields,
            "error": item.error,
        }
        for item in records
    ]
    pd.DataFrame(rows).to_csv(path, index=False)


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

    existing_fields = _load_existing_text_list(output_dir / "fields.txt", strip=False)
    if existing_fields and list(existing_fields) != list(fields):
        raise SystemExit("Resume target fields.txt does not match the requested field list.")
    existing_symbols = _load_existing_text_list(output_dir / "symbols.txt")
    if existing_symbols and list(existing_symbols) != list(symbols):
        raise SystemExit("Resume target symbols.txt does not match the requested symbol list.")


def _validate_daily_resume_inputs(
    *,
    output_dir: Path,
    dataset_name: str,
    fields: Sequence[str],
    symbols: Sequence[str],
    start_date: str,
    end_date: str,
    frequency: str,
    adjust_type: str | None,
    skip_suspended: bool,
) -> None:
    manifest = _load_manifest(output_dir / "manifest.yml")
    if manifest and manifest.get("dataset") not in {None, dataset_name}:
        raise SystemExit(
            f"Resume target dataset mismatch: expected {dataset_name!r}, got {manifest.get('dataset')!r}."
        )
    if manifest:
        query = manifest.get("query") if isinstance(manifest.get("query"), Mapping) else {}
        checks = [
            ("start_date", start_date),
            ("end_date", end_date),
            ("frequency", frequency),
            ("adjust_type", adjust_type),
            ("skip_suspended", skip_suspended),
        ]
        for key, expected in checks:
            actual = query.get(key) if isinstance(query, Mapping) else None
            if actual not in {None, expected}:
                raise SystemExit(
                    f"Resume target query mismatch for {key}: expected {expected!r}, got {actual!r}."
                )

    existing_fields = _load_existing_text_list(output_dir / "fields.txt", strip=False)
    if existing_fields and list(existing_fields) != list(fields):
        raise SystemExit("Resume target fields.txt does not match the requested field list.")
    existing_symbols = _load_existing_text_list(output_dir / "symbols.txt")
    if existing_symbols and list(existing_symbols) != list(symbols):
        raise SystemExit("Resume target symbols.txt does not match the requested symbol list.")


def _validate_dated_resume_inputs(
    *,
    output_dir: Path,
    dataset_name: str,
    fields: Sequence[str],
    symbols: Sequence[str],
    start_date: str,
    end_date: str,
) -> None:
    manifest = _load_manifest(output_dir / "manifest.yml")
    if manifest and manifest.get("dataset") not in {None, dataset_name}:
        raise SystemExit(
            f"Resume target dataset mismatch: expected {dataset_name!r}, got {manifest.get('dataset')!r}."
        )
    if manifest:
        query = manifest.get("query") if isinstance(manifest.get("query"), Mapping) else {}
        checks = [
            ("start_date", start_date),
            ("end_date", end_date),
        ]
        for key, expected in checks:
            actual = query.get(key) if isinstance(query, Mapping) else None
            if actual not in {None, expected}:
                raise SystemExit(
                    f"Resume target query mismatch for {key}: expected {expected!r}, got {actual!r}."
                )

    existing_fields = _load_existing_text_list(output_dir / "fields.txt", strip=False)
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


def _build_daily_manifest(
    *,
    dataset_name: str,
    api_name: str,
    output_dir: Path,
    fields: Sequence[str],
    field_metadata: Mapping[str, object],
    symbol_metadata: Mapping[str, object],
    symbols_requested: Sequence[str],
    entries: Sequence[DailyMirrorEntry],
    missing_symbols: Sequence[str],
    start_date: str,
    end_date: str,
    frequency: str,
    adjust_type: str | None,
    skip_suspended: bool,
    batches: Sequence[Mapping[str, object]],
    columns: Sequence[str],
    audit_file: Path,
    audit_records: Sequence[DailyMirrorAuditRecord],
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
            "start_date": start_date,
            "end_date": end_date,
            "frequency": frequency,
            "adjust_type": adjust_type,
            "skip_suspended": skip_suspended,
            "fields_count": len(fields),
            "fields": list(fields),
            "fields_file": list(field_metadata.get("fields_file") or []),
            "field_source": field_metadata.get("source"),
            "base_fields": list(field_metadata.get("base_fields") or []),
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
                "min_trade_date": item.min_trade_date,
                "max_trade_date": item.max_trade_date,
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


def _build_dated_manifest(
    *,
    dataset_name: str,
    api_name: str,
    output_dir: Path,
    fields: Sequence[str],
    field_metadata: Mapping[str, object],
    symbol_metadata: Mapping[str, object],
    symbols_requested: Sequence[str],
    entries: Sequence[DatedMirrorEntry],
    missing_symbols: Sequence[str],
    start_date: str,
    end_date: str,
    date_column: str,
    batches: Sequence[Mapping[str, object]],
    columns: Sequence[str],
    audit_file: Path,
    audit_records: Sequence[DatedMirrorAuditRecord],
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
            "start_date": start_date,
            "end_date": end_date,
            "date_column": date_column,
            "fields_count": len(fields),
            "fields": list(fields),
            "fields_file": list(field_metadata.get("fields_file") or []),
            "field_source": field_metadata.get("source"),
            "base_fields": list(field_metadata.get("base_fields") or []),
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
                "min_date": item.min_date,
                "max_date": item.max_date,
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

def _ensure_rqdatac_hk_plugin() -> None:
    try:
        import rqdatac_hk  # noqa: F401
    except ImportError as exc:
        raise SystemExit("rqdatac-hk is not installed. Install with: pip install '.[rqdata]'") from exc


from .mirror_daily import mirror_hk_daily
from .mirror_dated import (
    mirror_hk_announcement,
    mirror_hk_dividends,
    mirror_hk_ex_factors,
    mirror_hk_exchange_rate,
    mirror_hk_shares,
    mirror_hk_valuation,
)
from .mirror_financial import (
    export_hk_instruments,
    list_hk_financial_fields,
    mirror_hk_financial_details,
    mirror_hk_pit_financials,
)


from .mirror_workflow import (
    _collect_pending_mirror_items,
    _mirror_dated_dataset,
    _mirror_dataset,
    _run_partitioned_mirror_batches,
)
from .mirror_industry import (
    mirror_hk_industry_changes,
    mirror_hk_instrument_industry,
    mirror_hk_southbound,
)
from .build import (
    _build_filtered_universe_by_date,
    _default_hk_industry_labels_path,
    _default_pipeline_fundamentals_path,
    _derive_hk_industry_labels,
    _industry_labels_manifest_path,
    _load_industry_changes_frame,
    _load_trade_date_grid_from_daily_asset_dir,
    _load_universe_by_date_frame,
    _pipeline_fundamentals_manifest_path,
    _resolve_build_fields,
    _resolve_hk_industry_label_grid,
    _resolve_hk_industry_labels_out_path,
    _resolve_hk_label_frequency,
    _resolve_industry_changes_asset_dir,
    _resolve_optional_absolute_date,
    _resolve_pipeline_fundamentals_out_path,
    _resolve_pit_asset_dir,
    _sample_trade_date_grid,
    _write_symbol_list,
    build_hk_industry_labels_file,
    build_hk_pit_fundamentals_file,
)
from .coverage import (
    _assess_trainable_fill_dependence,
    _build_trainable_period_grid,
    _compute_pit_coverage_series,
    _estimate_trainable_pit_coverage,
    _is_supported_pit_coverage_feature,
    _render_hk_pit_coverage_text,
    _resolve_pit_coverage_features,
    _resolve_trainable_pit_features,
    _resolve_trainable_pit_settings,
    inspect_hk_pit_coverage,
)


def add_list_hk_financial_fields_args(parser: argparse.ArgumentParser) -> None:
    _args.add_list_hk_financial_fields_args(parser)


def add_hk_instruments_export_args(parser: argparse.ArgumentParser) -> None:
    _args.add_hk_instruments_export_args(
        parser,
        default_out_root=DEFAULT_OUT_ROOT,
        default_instruments_filename_prefix=DEFAULT_HK_INSTRUMENTS_FILENAME_PREFIX,
    )


def add_hk_daily_mirror_args(parser: argparse.ArgumentParser) -> None:
    _args.add_hk_daily_mirror_args(
        parser,
        default_out_root=DEFAULT_OUT_ROOT,
        max_attempts_default=DEFAULT_MIRROR_MAX_ATTEMPTS,
        backoff_seconds_default=DEFAULT_MIRROR_BACKOFF_SECONDS,
        max_backoff_seconds_default=DEFAULT_MIRROR_MAX_BACKOFF_SECONDS,
    )


def add_hk_valuation_mirror_args(parser: argparse.ArgumentParser) -> None:
    _args.add_hk_valuation_mirror_args(
        parser,
        default_batch_size=DEFAULT_BATCH_SIZE,
        default_out_root=DEFAULT_OUT_ROOT,
        max_attempts_default=DEFAULT_MIRROR_MAX_ATTEMPTS,
        backoff_seconds_default=DEFAULT_MIRROR_BACKOFF_SECONDS,
        max_backoff_seconds_default=DEFAULT_MIRROR_MAX_BACKOFF_SECONDS,
    )


def add_hk_dated_mirror_args(
    parser: argparse.ArgumentParser,
    *,
    supports_fields: bool = False,
    field_help: str | None = None,
    fields_file_help: str | None = None,
) -> None:
    _args.add_hk_dated_mirror_args(
        parser,
        default_batch_size=DEFAULT_BATCH_SIZE,
        default_out_root=DEFAULT_OUT_ROOT,
        max_attempts_default=DEFAULT_MIRROR_MAX_ATTEMPTS,
        backoff_seconds_default=DEFAULT_MIRROR_BACKOFF_SECONDS,
        max_backoff_seconds_default=DEFAULT_MIRROR_MAX_BACKOFF_SECONDS,
        supports_fields=supports_fields,
        field_help=field_help,
        fields_file_help=fields_file_help,
    )


def add_hk_ex_factors_mirror_args(parser: argparse.ArgumentParser) -> None:
    _args.add_hk_ex_factors_mirror_args(
        parser,
        default_batch_size=DEFAULT_BATCH_SIZE,
        default_out_root=DEFAULT_OUT_ROOT,
        max_attempts_default=DEFAULT_MIRROR_MAX_ATTEMPTS,
        backoff_seconds_default=DEFAULT_MIRROR_BACKOFF_SECONDS,
        max_backoff_seconds_default=DEFAULT_MIRROR_MAX_BACKOFF_SECONDS,
    )


def add_hk_dividends_mirror_args(parser: argparse.ArgumentParser) -> None:
    _args.add_hk_dividends_mirror_args(
        parser,
        default_batch_size=DEFAULT_BATCH_SIZE,
        default_out_root=DEFAULT_OUT_ROOT,
        max_attempts_default=DEFAULT_MIRROR_MAX_ATTEMPTS,
        backoff_seconds_default=DEFAULT_MIRROR_BACKOFF_SECONDS,
        max_backoff_seconds_default=DEFAULT_MIRROR_MAX_BACKOFF_SECONDS,
    )


def add_hk_shares_mirror_args(parser: argparse.ArgumentParser) -> None:
    _args.add_hk_shares_mirror_args(
        parser,
        default_batch_size=DEFAULT_BATCH_SIZE,
        default_out_root=DEFAULT_OUT_ROOT,
        max_attempts_default=DEFAULT_MIRROR_MAX_ATTEMPTS,
        backoff_seconds_default=DEFAULT_MIRROR_BACKOFF_SECONDS,
        max_backoff_seconds_default=DEFAULT_MIRROR_MAX_BACKOFF_SECONDS,
    )


def add_hk_exchange_rate_mirror_args(parser: argparse.ArgumentParser) -> None:
    _args.add_hk_exchange_rate_mirror_args(
        parser,
        default_out_root=DEFAULT_OUT_ROOT,
        max_attempts_default=DEFAULT_MIRROR_MAX_ATTEMPTS,
        backoff_seconds_default=DEFAULT_MIRROR_BACKOFF_SECONDS,
        max_backoff_seconds_default=DEFAULT_MIRROR_MAX_BACKOFF_SECONDS,
    )


def add_hk_announcement_mirror_args(parser: argparse.ArgumentParser) -> None:
    _args.add_hk_announcement_mirror_args(
        parser,
        default_batch_size=DEFAULT_BATCH_SIZE,
        default_out_root=DEFAULT_OUT_ROOT,
        max_attempts_default=DEFAULT_MIRROR_MAX_ATTEMPTS,
        backoff_seconds_default=DEFAULT_MIRROR_BACKOFF_SECONDS,
        max_backoff_seconds_default=DEFAULT_MIRROR_MAX_BACKOFF_SECONDS,
    )


def add_hk_southbound_mirror_args(parser: argparse.ArgumentParser) -> None:
    _args.add_hk_southbound_mirror_args(
        parser,
        default_out_root=DEFAULT_OUT_ROOT,
        max_attempts_default=DEFAULT_MIRROR_MAX_ATTEMPTS,
        backoff_seconds_default=DEFAULT_MIRROR_BACKOFF_SECONDS,
        max_backoff_seconds_default=DEFAULT_MIRROR_MAX_BACKOFF_SECONDS,
    )


def add_hk_instrument_industry_mirror_args(parser: argparse.ArgumentParser) -> None:
    _args.add_hk_instrument_industry_mirror_args(
        parser,
        default_batch_size=DEFAULT_BATCH_SIZE,
        default_out_root=DEFAULT_OUT_ROOT,
        max_attempts_default=DEFAULT_MIRROR_MAX_ATTEMPTS,
        backoff_seconds_default=DEFAULT_MIRROR_BACKOFF_SECONDS,
        max_backoff_seconds_default=DEFAULT_MIRROR_MAX_BACKOFF_SECONDS,
        default_industry_source=DEFAULT_HK_INDUSTRY_SOURCE,
        default_industry_level=DEFAULT_HK_INSTRUMENT_INDUSTRY_LEVEL,
    )


def add_hk_industry_changes_mirror_args(parser: argparse.ArgumentParser) -> None:
    _args.add_hk_industry_changes_mirror_args(
        parser,
        default_batch_size=DEFAULT_BATCH_SIZE,
        default_out_root=DEFAULT_OUT_ROOT,
        max_attempts_default=DEFAULT_MIRROR_MAX_ATTEMPTS,
        backoff_seconds_default=DEFAULT_MIRROR_BACKOFF_SECONDS,
        max_backoff_seconds_default=DEFAULT_MIRROR_MAX_BACKOFF_SECONDS,
        default_industry_source=DEFAULT_HK_INDUSTRY_SOURCE,
        default_change_level=DEFAULT_HK_INDUSTRY_CHANGE_LEVEL,
    )


def add_hk_financial_mirror_args(parser: argparse.ArgumentParser) -> None:
    _args.add_hk_financial_mirror_args(
        parser,
        default_batch_size=DEFAULT_BATCH_SIZE,
        default_out_root=DEFAULT_OUT_ROOT,
        max_attempts_default=DEFAULT_MIRROR_MAX_ATTEMPTS,
        backoff_seconds_default=DEFAULT_MIRROR_BACKOFF_SECONDS,
        max_backoff_seconds_default=DEFAULT_MIRROR_MAX_BACKOFF_SECONDS,
    )


def add_hk_pit_fundamentals_build_args(parser: argparse.ArgumentParser) -> None:
    _args.add_hk_pit_fundamentals_build_args(
        parser,
        default_pipeline_fundamentals_name=DEFAULT_PIPELINE_FUNDAMENTALS_NAME,
    )


def add_hk_industry_labels_build_args(parser: argparse.ArgumentParser) -> None:
    _args.add_hk_industry_labels_build_args(
        parser,
        default_industry_labels_filename_prefix=DEFAULT_HK_INDUSTRY_LABELS_FILENAME_PREFIX,
    )


def add_hk_pit_coverage_args(parser: argparse.ArgumentParser) -> None:
    _args.add_hk_pit_coverage_args(parser)
