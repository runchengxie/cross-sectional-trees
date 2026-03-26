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
import yaml

from . import rqdata_assets_args as _args
from ..artifacts import (
    RQDATA_ASSETS_DIR as DEFAULT_RQDATA_ASSETS_DIR,
)
from ..config_utils import resolve_pipeline_config
from ..data_providers import (
    DEFAULT_RQDATA_HK_FUNDAMENTAL_FIELDS,
    _fetch_daily_rqdata,
    _to_rqdata_symbol,
)
from ..rebalance import get_rebalance_dates
from .backup_data import _git_metadata

DEFAULT_OUT_ROOT = DEFAULT_RQDATA_ASSETS_DIR.as_posix()
DEFAULT_BATCH_SIZE = 20
DEFAULT_PIPELINE_FUNDAMENTALS_NAME = "pipeline_fundamentals.parquet"
DEFAULT_HK_INDUSTRY_LABELS_FILENAME_PREFIX = "industry_labels"
DEFAULT_HK_INSTRUMENTS_FILENAME_PREFIX = "hk_instruments"
DEFAULT_HK_INSTRUMENTS_DIR = DEFAULT_RQDATA_ASSETS_DIR / "hk" / "instruments"
DEFAULT_MIRROR_MAX_ATTEMPTS = 3
DEFAULT_MIRROR_BACKOFF_SECONDS = 1.0
DEFAULT_MIRROR_MAX_BACKOFF_SECONDS = 30.0
DEFAULT_HK_DAILY_FIELDS = (
    "open",
    "high",
    "low",
    "close",
    "volume",
    "total_turnover",
)
DEFAULT_HK_VALUATION_FIELDS = tuple(DEFAULT_RQDATA_HK_FUNDAMENTAL_FIELDS.values())
DEFAULT_HK_SHARES_FIELDS = (
    "total",
    "circulation_a",
    "management_circulation",
    "non_circulation_a",
    "total_a",
    "total_hk",
    "total_hk1",
)
DEFAULT_HK_EXCHANGE_RATE_FIELDS = (
    "currency_pair",
    "middle_referrence_rate",
)
DEFAULT_HK_SOUTHBOUND_TRADING_TYPES = ("sh", "sz")
DEFAULT_HK_INDUSTRY_SOURCE = "citics_2019"
DEFAULT_HK_INSTRUMENT_INDUSTRY_LEVEL = 0
DEFAULT_HK_INDUSTRY_CHANGE_LEVEL = 1
HK_INSTRUMENT_INDUSTRY_FIELDS = {
    0: (
        "first_industry_code",
        "first_industry_name",
        "second_industry_code",
        "second_industry_name",
        "third_industry_code",
        "third_industry_name",
    ),
    1: ("first_industry_code", "first_industry_name"),
    2: (
        "first_industry_code",
        "first_industry_name",
        "second_industry_code",
        "second_industry_name",
    ),
    3: (
        "first_industry_code",
        "first_industry_name",
        "second_industry_code",
        "second_industry_name",
        "third_industry_code",
        "third_industry_name",
    ),
}
HK_INDUSTRY_HIERARCHY_COLUMNS = (
    "first_industry_code",
    "first_industry_name",
    "second_industry_code",
    "second_industry_name",
    "third_industry_code",
    "third_industry_name",
)
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
DERIVED_PIT_FEATURES = {
    "sales",
    "debt",
    "profit_margin",
    "operating_margin",
    "cfo_margin",
    "cfo_to_profit",
    "asset_turnover",
    "roa",
    "leverage",
    "cfo_to_assets",
    "debt_to_assets",
    "debt_to_equity",
    "cash_to_assets",
    "goodwill_to_assets",
    "accrual_ratio",
    "receivables_to_revenue",
    "inventory_to_revenue",
    "working_capital_to_assets",
    "net_debt_to_assets",
    "days_since_report",
}


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


def _normalize_absolute_date(value: object, *, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise SystemExit(f"{label} is required.")
    normalized = text.replace("/", "-").replace(".", "-")
    parsed = pd.to_datetime(normalized, errors="coerce")
    if pd.isna(parsed):
        raise SystemExit(f"{label} must be a valid absolute date such as 20260310 or 2026-03-10.")
    return parsed.strftime("%Y%m%d")


def _resolve_daily_fields(args) -> tuple[list[str], dict]:
    explicit_fields: list[str] = []
    if getattr(args, "field", None):
        explicit_fields.extend(str(item).strip() for item in args.field if str(item).strip())
    for path_text in getattr(args, "fields_file", None) or []:
        explicit_fields.extend(_load_text_list(path_text, label="Fields file"))
    fields = _dedupe_preserve_order([*DEFAULT_HK_DAILY_FIELDS, *explicit_fields], strip=False)
    metadata = {
        "count": len(fields),
        "base_fields": list(DEFAULT_HK_DAILY_FIELDS),
        "fields_file": [str(_resolve_path(path_text)) for path_text in (args.fields_file or [])],
        "source": "default_plus_explicit" if explicit_fields else "default",
    }
    return fields, metadata


def _resolve_default_plus_explicit_fields(
    args,
    *,
    default_fields: Sequence[str],
    source_label: str,
) -> tuple[list[str], dict]:
    explicit_fields: list[str] = []
    if getattr(args, "field", None):
        explicit_fields.extend(str(item).strip() for item in args.field if str(item).strip())
    for path_text in getattr(args, "fields_file", None) or []:
        explicit_fields.extend(_load_text_list(path_text, label="Fields file"))
    fields = _dedupe_preserve_order([*default_fields, *explicit_fields], strip=False)
    metadata = {
        "count": len(fields),
        "base_fields": list(default_fields),
        "fields_file": [str(_resolve_path(path_text)) for path_text in (args.fields_file or [])],
        "source": source_label if explicit_fields else "default",
    }
    return fields, metadata


def _resolve_optional_explicit_fields(
    args,
    *,
    empty_source_label: str = "api_default",
    explicit_source_label: str = "explicit",
) -> tuple[list[str], dict]:
    fields: list[str] = []
    if getattr(args, "field", None):
        fields.extend(str(item).strip() for item in args.field if str(item).strip())
    for path_text in getattr(args, "fields_file", None) or []:
        fields.extend(_load_text_list(path_text, label="Fields file"))
    fields = _dedupe_preserve_order(fields, strip=False)
    metadata = {
        "count": len(fields),
        "base_fields": [],
        "fields_file": [str(_resolve_path(path_text)) for path_text in (args.fields_file or [])],
        "source": explicit_source_label if fields else empty_source_label,
    }
    return fields, metadata


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
    if "order_book_id" in normalized.columns:
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


def _default_snapshot_name(dataset_name: str, start_quarter: str, end_quarter: str, statements: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{dataset_name}_{start_quarter}_{end_quarter}_{statements}_{timestamp}"


def _default_daily_snapshot_name(dataset_name: str, start_date: str, end_date: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{dataset_name}_{start_date}_{end_date}_{timestamp}"


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


def _prepare_daily_output_dir(
    *,
    out_root: str,
    dataset_name: str,
    start_date: str,
    end_date: str,
    name: str | None,
    resume: bool,
) -> Path:
    root = _resolve_path(out_root)
    snapshot_name = name or _default_daily_snapshot_name(dataset_name, start_date, end_date)
    output_dir = root / "hk" / dataset_name / snapshot_name
    if output_dir.exists():
        if not resume:
            raise SystemExit(f"Refusing to overwrite existing output: {output_dir}")
        if not output_dir.is_dir():
            raise SystemExit(f"Resume target is not a directory: {output_dir}")
    else:
        output_dir.mkdir(parents=True, exist_ok=False)
    return output_dir


def _split_daily_range_by_year(start_date: str, end_date: str) -> list[tuple[str, str]]:
    start_ts = pd.to_datetime(start_date, format="%Y%m%d", errors="raise")
    end_ts = pd.to_datetime(end_date, format="%Y%m%d", errors="raise")
    chunks: list[tuple[str, str]] = []
    current = start_ts
    while current <= end_ts:
        year_end = pd.Timestamp(year=current.year, month=12, day=31)
        chunk_end = min(year_end, end_ts)
        chunks.append((current.strftime("%Y%m%d"), chunk_end.strftime("%Y%m%d")))
        current = chunk_end + pd.Timedelta(days=1)
    return chunks


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

    normalized = _normalize_frame_columns(frame.reset_index())
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


def _load_existing_text_list(path: Path, *, strip: bool = True) -> list[str]:
    if not path.exists():
        return []
    values: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip() if strip else line.rstrip("\r\n")
            if text:
                values.append(text)
    return values


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

    preferred = [column for column in ["ts_code", "order_book_id", date_column] if column in normalized.columns]
    remaining = [column for column in normalized.columns if column not in preferred]
    work = normalized.loc[:, preferred + remaining].copy()
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


def export_hk_instruments(args, rqdatac) -> int:
    _ensure_rqdatac_hk_plugin()
    symbol_filter, symbol_metadata = _resolve_instrument_symbol_filter(args)
    try:
        frame = rqdatac.all_instruments("CS", market="hk")
    except TypeError:
        frame = rqdatac.all_instruments("CS")
    if frame is None or frame.empty:
        raise SystemExit("rqdatac.all_instruments returned no HK instruments.")

    instruments = _normalize_frame_columns(frame.copy())
    if "order_book_id" not in instruments.columns:
        raise SystemExit("HK instruments payload is missing order_book_id.")
    instruments["order_book_id"] = instruments["order_book_id"].astype(str).str.strip()
    instruments["ts_code"] = instruments["order_book_id"].map(_normalize_hk_symbol)
    instruments = instruments[instruments["ts_code"] != ""].copy()

    if symbol_filter is not None:
        instruments = instruments[instruments["ts_code"].isin(symbol_filter)].copy()
    elif getattr(args, "limit", None) is not None:
        instruments = instruments.sort_values(["ts_code", "order_book_id"], kind="mergesort").head(args.limit).copy()

    if instruments.empty:
        raise SystemExit("No HK instruments matched the requested filter.")

    preferred_columns = [
        column
        for column in (
            "ts_code",
            "order_book_id",
            "symbol",
            "name",
            "listed_date",
            "de_listed_date",
            "round_lot",
            "board_type",
            "status",
        )
        if column in instruments.columns
    ]
    remaining_columns = [column for column in instruments.columns if column not in preferred_columns]
    instruments = instruments[preferred_columns + remaining_columns].copy()
    instruments.sort_values(["ts_code", "order_book_id"], kind="mergesort", inplace=True)
    instruments.reset_index(drop=True, inplace=True)

    out_arg = getattr(args, "out", None)
    out_path = _resolve_path(out_arg) if out_arg else _default_hk_instruments_out_path()
    if not out_path.suffix:
        out_path = out_path.with_suffix(".parquet")
    if out_path.exists() and not getattr(args, "force", False):
        raise SystemExit(f"Refusing to overwrite existing output: {out_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.suffix.lower() == ".csv":
        instruments.to_csv(out_path, index=False)
    else:
        instruments.to_parquet(out_path, index=False)

    manifest_path = Path(f"{out_path}.manifest.yml")
    symbol_metadata = dict(symbol_metadata)
    symbol_metadata["count"] = int(instruments["ts_code"].nunique())
    manifest = {
        "name": out_path.stem,
        "created_at": _timestamp_now(),
        "dataset": "hk_instruments",
        "api": "rqdatac.all_instruments",
        "market": "hk",
        "config_ref": getattr(args, "config", None),
        "output_file": str(out_path),
        "format": out_path.suffix.lstrip(".").lower(),
        "symbol_source": symbol_metadata,
        "columns": instruments.columns.tolist(),
        "totals": {
            "rows": int(len(instruments)),
            "symbols": int(instruments["ts_code"].nunique()),
            "round_lot_nonnull": int(instruments["round_lot"].notna().sum())
            if "round_lot" in instruments.columns
            else 0,
        },
        "git": _git_metadata(Path.cwd().resolve()),
    }
    _write_manifest(manifest_path, manifest)
    print(
        f"Wrote {len(instruments)} HK instruments to {out_path} "
        f"(manifest: {manifest_path})"
    )
    return 0


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
    max_attempts = max(1, int(getattr(args, "max_attempts", DEFAULT_MIRROR_MAX_ATTEMPTS) or 1))
    backoff_seconds = float(getattr(args, "backoff_seconds", DEFAULT_MIRROR_BACKOFF_SECONDS))
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
            ts_code=symbol,
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
        started = _timestamp_now()
        try:
            payload, attempts = _retry_fetch(
                f"daily fetch failed for {order_book_id}",
                lambda: _fetch_daily_rqdata(
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
        except MirrorQuotaError as exc:
            finished = _timestamp_now()
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
        except MirrorFetchError as exc:
            finished = _timestamp_now()
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

        finished = _timestamp_now()
        prepared = _prepare_daily_asset_frame(payload, symbol=symbol, order_book_id=order_book_id)
        prepared = _ensure_requested_fields(prepared, fields)
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
        entry = _write_daily_symbol_frame(data_dir, prepared)
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
                    entry, symbol_frame = _load_existing_daily_entry(out_path, fields=fields)
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

        for order_book_id in pending_order_book_ids:
            _process_symbol(order_book_id)
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
            entries=[entries_by_symbol[symbol] for symbol in symbols if symbol in entries_by_symbol],
            missing_symbols=[item.ts_code for item in audit_records if item.status == "missing_remote"],
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


def mirror_hk_valuation(args, rqdatac) -> int:
    fields, field_metadata = _resolve_default_plus_explicit_fields(
        args,
        default_fields=DEFAULT_HK_VALUATION_FIELDS,
        source_label="default_plus_explicit",
    )
    return _mirror_dated_dataset(
        args=args,
        rqdatac=rqdatac,
        dataset_name="valuation",
        api_name="rqdatac.get_factor",
        date_column="trade_date",
        fields=fields,
        field_metadata=field_metadata,
        resolve_request_groups=lambda symbols, start_date, end_date, args: _resolve_hk_dated_request_groups(
            symbols,
            start_date=start_date,
            end_date=end_date,
            out_root=getattr(args, "out_root", DEFAULT_OUT_ROOT),
        ),
        normalize_payload=_normalize_hk_valuation_payload,
        fetch_batch=lambda order_book_ids, selected_fields, start_date, end_date: rqdatac.get_factor(
            list(order_book_ids),
            list(selected_fields),
            start_date,
            end_date,
            market="hk",
        ),
    )


def _collect_pending_mirror_items(
    *,
    items: Sequence[str],
    data_dir: Path,
    skip_existing: bool,
    item_to_symbol: Callable[[str], str],
    load_existing: Callable[[Path], tuple[object, pd.DataFrame]],
    record_entry: Callable[..., None],
) -> list[str]:
    pending_items: list[str] = []
    for item in items:
        symbol = item_to_symbol(item)
        out_path = data_dir / f"{symbol}.parquet"
        if skip_existing and out_path.exists():
            try:
                entry, symbol_frame = load_existing(out_path)
            except Exception:
                pending_items.append(item)
                continue
            record_entry(
                symbol=symbol,
                entry=entry,
                symbol_frame=symbol_frame,
                record_status="skipped_existing",
                attempts=0,
                started_at_value=None,
                finished_at_value=_path_mtime_iso(out_path),
            )
            continue
        pending_items.append(item)
    return pending_items


def _run_partitioned_mirror_batches(
    *,
    pending_items: Sequence[str],
    batch_size: int,
    process_batch: Callable[[list[str]], None],
    quota_blocked: Callable[[], bool],
    on_quota_blocked: Callable[[], None],
    on_completed_without_quota: Callable[[], None],
    on_exception: Callable[[Exception], None],
    on_finalize: Callable[[], None],
) -> None:
    try:
        for batch_items in _chunked(pending_items, batch_size):
            process_batch(list(batch_items))
            if quota_blocked():
                break
        if quota_blocked():
            on_quota_blocked()
        else:
            on_completed_without_quota()
    except Exception as exc:
        on_exception(exc)
        raise
    finally:
        on_finalize()


def _mirror_dated_dataset(
    *,
    args,
    rqdatac,
    dataset_name: str,
    api_name: str,
    date_column: str,
    fields: Sequence[str],
    field_metadata: Mapping[str, object],
    fetch_batch,
    sort_columns: Sequence[str] = (),
    resolve_request_groups=None,
    normalize_payload=None,
) -> int:
    symbols, symbol_metadata = _resolve_symbols(args)
    start_date = _normalize_absolute_date(args.start_date, label="--start-date")
    end_date = _normalize_absolute_date(args.end_date, label="--end-date")
    if start_date > end_date:
        raise SystemExit("--start-date must be <= --end-date.")

    resume = bool(getattr(args, "resume", False))
    skip_existing = bool(getattr(args, "skip_existing", False) or resume)
    max_attempts = max(1, int(getattr(args, "max_attempts", DEFAULT_MIRROR_MAX_ATTEMPTS) or 1))
    backoff_seconds = float(getattr(args, "backoff_seconds", DEFAULT_MIRROR_BACKOFF_SECONDS))
    max_backoff_seconds = float(
        getattr(args, "max_backoff_seconds", DEFAULT_MIRROR_MAX_BACKOFF_SECONDS)
    )
    output_dir = _prepare_daily_output_dir(
        out_root=getattr(args, "out_root", DEFAULT_OUT_ROOT),
        dataset_name=dataset_name,
        start_date=start_date,
        end_date=end_date,
        name=getattr(args, "name", None),
        resume=resume,
    )
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    audit_path = output_dir / "audit.csv"

    if resolve_request_groups is not None:
        request_groups, request_id_metadata, request_group_metadata = resolve_request_groups(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            args=args,
        )
    else:
        request_groups, request_id_metadata, request_group_metadata = _build_default_dated_request_groups(symbols)
    if request_group_metadata:
        symbol_metadata = dict(symbol_metadata)
        symbol_metadata["request_groups"] = dict(request_group_metadata)

    request_ids_by_symbol = {group.ts_code: list(group.request_ids) for group in request_groups}
    primary_order_book_id_by_symbol = {
        group.ts_code: (
            next((item for item in group.order_book_ids if str(item).strip()), None)
            or next((item for item in group.request_ids if str(item).strip()), None)
            or _to_rqdata_symbol("hk", group.ts_code)
        )
        for group in request_groups
    }
    symbol_map: dict[str, str] = {}
    for group in request_groups:
        for request_id in (*group.request_ids, *group.order_book_ids):
            text = str(request_id or "").strip()
            if text:
                symbol_map[text] = group.ts_code

    entries_by_symbol: dict[str, DatedMirrorEntry] = {}
    audit_by_symbol: dict[str, DatedMirrorAuditRecord] = {}
    batches: list[dict[str, object]] = []
    columns: list[str] = []
    field_coverage = _field_coverage_template(fields)
    started_at = _timestamp_now()
    status = "completed"
    error: str | None = None
    result_code = 0
    quota_blocked = False

    def _payload_to_frame(payload):
        if normalize_payload is None:
            return payload
        return normalize_payload(payload, request_id_metadata=request_id_metadata)

    def _record_entry(
        *,
        symbol: str,
        entry: DatedMirrorEntry,
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
        audit_by_symbol[symbol] = _dated_audit_record(
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
        audit_by_symbol[symbol] = _dated_audit_record(
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
        request_ids: Sequence[str],
    ) -> tuple[pd.DataFrame, int, list[str]]:
        active_fields = list(fields)
        dropped_fields: list[str] = []
        total_attempts = 0
        request_ids = [str(item).strip() for item in request_ids if str(item).strip()]
        while True:
            label = f"{dataset_name} fetch failed for {', '.join(request_ids)}"
            try:
                payload, attempts = _retry_fetch(
                    label,
                    lambda: fetch_batch(request_ids, active_fields, start_date, end_date),
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
            prepared = _prepare_dated_asset_frame(
                _payload_to_frame(payload),
                symbol_map=symbol_map,
                date_column=date_column,
                sort_columns=sort_columns,
            )
            prepared = _ensure_requested_fields(prepared, fields)
            return prepared, total_attempts, dropped_fields

    def _process_batch(batch_symbols: list[str]) -> None:
        nonlocal status, error, result_code, quota_blocked, columns
        if not batch_symbols or quota_blocked:
            return
        batch_request_ids = [
            request_id
            for symbol in batch_symbols
            for request_id in request_ids_by_symbol.get(symbol, ())
            if str(request_id).strip()
        ]
        if not batch_request_ids:
            return
        batch_started_at = _timestamp_now()
        dropped_fields: list[str] = []
        try:
            if len(batch_symbols) == 1:
                payload, attempts, dropped_fields = _fetch_single_symbol_with_field_fallback(
                    batch_request_ids
                )
            else:
                label = f"{dataset_name} fetch failed for {', '.join(batch_symbols)}"
                payload, attempts = _retry_fetch(
                    label,
                    lambda: fetch_batch(batch_request_ids, fields, start_date, end_date),
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
            for symbol in batch_symbols:
                if symbol in audit_by_symbol:
                    continue
                _record_non_entry(
                    symbol=symbol,
                    order_book_id=primary_order_book_id_by_symbol[symbol],
                    record_status="quota_blocked",
                    attempts=exc.attempts,
                    started_at_value=batch_started_at,
                    finished_at_value=batch_finished_at,
                    dropped_fields=dropped_fields,
                    error_text=str(exc),
                )
            batches.append(
                {
                    "order_book_ids": len(batch_request_ids),
                    "rows": 0,
                    "symbols_written": 0,
                    "symbols_missing_remote": len(batch_symbols),
                    "status": "quota_blocked",
                    "attempts": exc.attempts,
                    "dropped_fields": list(dropped_fields),
                    "error": str(exc),
                }
            )
            return
        except MirrorFetchError as exc:
            batch_finished_at = _timestamp_now()
            if len(batch_symbols) > 1:
                batches.append(
                    {
                        "order_book_ids": len(batch_request_ids),
                        "rows": 0,
                        "symbols_written": 0,
                        "symbols_missing_remote": 0,
                        "status": "split_after_error",
                        "attempts": exc.attempts,
                        "error": str(exc),
                    }
                )
                for symbol in batch_symbols:
                    _process_batch([symbol])
                    if quota_blocked:
                        break
                return

            symbol = batch_symbols[0]
            _record_non_entry(
                symbol=symbol,
                order_book_id=primary_order_book_id_by_symbol[symbol],
                record_status="failed",
                attempts=exc.attempts,
                started_at_value=batch_started_at,
                finished_at_value=batch_finished_at,
                dropped_fields=dropped_fields,
                error_text=str(exc),
            )
            batches.append(
                {
                    "order_book_ids": len(batch_request_ids),
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
        prepared = _prepare_dated_asset_frame(
            _payload_to_frame(payload),
            symbol_map=symbol_map,
            date_column=date_column,
            sort_columns=sort_columns,
        )
        prepared = _ensure_requested_fields(prepared, fields)
        if prepared.empty:
            for symbol in batch_symbols:
                _record_non_entry(
                    symbol=symbol,
                    order_book_id=primary_order_book_id_by_symbol[symbol],
                    record_status="missing_remote",
                    attempts=attempts,
                    started_at_value=batch_started_at,
                    finished_at_value=batch_finished_at,
                    dropped_fields=dropped_fields,
                )
            batches.append(
                {
                    "order_book_ids": len(batch_request_ids),
                    "rows": 0,
                    "symbols_written": 0,
                    "symbols_missing_remote": len(batch_symbols),
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
        for symbol in batch_symbols:
            symbol_frame = prepared[prepared["ts_code"] == symbol].reset_index(drop=True)
            if symbol_frame.empty:
                batch_symbols_missing += 1
                _record_non_entry(
                    symbol=symbol,
                    order_book_id=primary_order_book_id_by_symbol[symbol],
                    record_status="missing_remote",
                    attempts=attempts,
                    started_at_value=batch_started_at,
                    finished_at_value=batch_finished_at,
                    dropped_fields=dropped_fields,
                )
                continue
            entry = _write_dated_symbol_frame(data_dir, symbol_frame, date_column=date_column)
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
                "order_book_ids": len(batch_request_ids),
                "rows": batch_rows,
                "symbols_written": batch_symbols_written,
                "symbols_missing_remote": batch_symbols_missing,
                "status": "completed",
                "attempts": attempts,
                "dropped_fields": list(dropped_fields),
            }
        )

    if resume:
        _validate_dated_resume_inputs(
            output_dir=output_dir,
            dataset_name=dataset_name,
            fields=fields,
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
        )

    _write_text_list(output_dir / "fields.txt", list(fields))
    _write_text_list(output_dir / "symbols.txt", symbols)

    pending_symbols = _collect_pending_mirror_items(
        items=symbols,
        data_dir=data_dir,
        skip_existing=skip_existing,
        item_to_symbol=lambda symbol: symbol,
        load_existing=lambda path: _load_existing_dated_entry(
            path,
            date_column=date_column,
            fields=fields,
        ),
        record_entry=_record_entry,
    )

    def _quota_blocked() -> bool:
        return quota_blocked

    def _on_quota_blocked() -> None:
        quota_finished_at = _timestamp_now()
        for symbol in pending_symbols:
            if symbol in audit_by_symbol:
                continue
            _record_non_entry(
                symbol=symbol,
                order_book_id=primary_order_book_id_by_symbol[symbol],
                record_status="quota_blocked",
                attempts=0,
                started_at_value=None,
                finished_at_value=quota_finished_at,
                error_text=error,
            )

    def _on_completed_without_quota() -> None:
        nonlocal status
        if result_code == 1 and status == "completed":
            status = "completed_with_failures"

    def _on_exception(exc: Exception) -> None:
        nonlocal status, error, result_code
        status = "failed"
        error = str(exc)
        result_code = max(result_code, 1)

    def _on_finalize() -> None:
        finished_at = _timestamp_now()
        for symbol in symbols:
            if symbol in audit_by_symbol:
                continue
            _record_non_entry(
                symbol=symbol,
                order_book_id=primary_order_book_id_by_symbol[symbol],
                record_status="failed",
                attempts=0,
                started_at_value=None,
                finished_at_value=finished_at,
                error_text=error or "missing audit status",
            )
        audit_records = [audit_by_symbol[symbol] for symbol in symbols]
        _write_dated_audit_csv(audit_path, audit_records)
        manifest = _build_dated_manifest(
            dataset_name=dataset_name,
            api_name=api_name,
            output_dir=output_dir,
            fields=fields,
            field_metadata=field_metadata,
            symbol_metadata=symbol_metadata,
            symbols_requested=symbols,
            entries=[entries_by_symbol[symbol] for symbol in symbols if symbol in entries_by_symbol],
            missing_symbols=[item.ts_code for item in audit_records if item.status == "missing_remote"],
            start_date=start_date,
            end_date=end_date,
            date_column=date_column,
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

    _run_partitioned_mirror_batches(
        pending_items=pending_symbols,
        batch_size=getattr(args, "batch_size", DEFAULT_BATCH_SIZE),
        process_batch=_process_batch,
        quota_blocked=_quota_blocked,
        on_quota_blocked=_on_quota_blocked,
        on_completed_without_quota=_on_completed_without_quota,
        on_exception=_on_exception,
        on_finalize=_on_finalize,
    )

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

    pending_order_book_ids = _collect_pending_mirror_items(
        items=order_book_ids,
        data_dir=data_dir,
        skip_existing=skip_existing,
        item_to_symbol=lambda order_book_id: symbol_map[order_book_id],
        load_existing=lambda path: _load_existing_entry(path, fields=fields),
        record_entry=_record_entry,
    )

    def _quota_blocked() -> bool:
        return quota_blocked

    def _on_quota_blocked() -> None:
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

    def _on_completed_without_quota() -> None:
        nonlocal status
        if result_code == 1 and status == "completed":
            status = "completed_with_failures"

    def _on_exception(exc: Exception) -> None:
        nonlocal status, error, result_code
        status = "failed"
        error = str(exc)
        result_code = max(result_code, 1)

    def _on_finalize() -> None:
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

    _run_partitioned_mirror_batches(
        pending_items=pending_order_book_ids,
        batch_size=getattr(args, "batch_size", DEFAULT_BATCH_SIZE),
        process_batch=_process_batch,
        quota_blocked=_quota_blocked,
        on_quota_blocked=_on_quota_blocked,
        on_completed_without_quota=_on_completed_without_quota,
        on_exception=_on_exception,
        on_finalize=_on_finalize,
    )

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


def mirror_hk_ex_factors(args, rqdatac) -> int:
    return _mirror_dated_dataset(
        args=args,
        rqdatac=rqdatac,
        dataset_name="ex_factors",
        api_name="rqdatac.get_ex_factor",
        date_column="ex_date",
        fields=[],
        field_metadata={"count": 0, "fields_file": [], "source": "api_payload", "base_fields": []},
        sort_columns=("announcement_date", "ex_end_date"),
        resolve_request_groups=lambda symbols, start_date, end_date, args: _resolve_hk_dated_request_groups(
            symbols,
            start_date=start_date,
            end_date=end_date,
            out_root=getattr(args, "out_root", DEFAULT_OUT_ROOT),
        ),
        normalize_payload=_normalize_hk_dated_payload,
        fetch_batch=lambda order_book_ids, fields, start_date, end_date: (
            _fetch_hk_ex_factors_direct(order_book_ids, start_date=start_date, end_date=end_date)
            if _uses_hk_unique_ids(order_book_ids)
            else rqdatac.get_ex_factor(
                order_book_ids,
                start_date=start_date,
                end_date=end_date,
                market="hk",
            )
        ),
    )


def mirror_hk_dividends(args, rqdatac) -> int:
    return _mirror_dated_dataset(
        args=args,
        rqdatac=rqdatac,
        dataset_name="dividends",
        api_name="rqdatac.get_dividend",
        date_column="declaration_announcement_date",
        fields=[],
        field_metadata={"count": 0, "fields_file": [], "source": "api_payload", "base_fields": []},
        sort_columns=("ex_dividend_date", "payable_date"),
        resolve_request_groups=lambda symbols, start_date, end_date, args: _resolve_hk_dated_request_groups(
            symbols,
            start_date=start_date,
            end_date=end_date,
            out_root=getattr(args, "out_root", DEFAULT_OUT_ROOT),
        ),
        normalize_payload=_normalize_hk_dated_payload,
        fetch_batch=lambda order_book_ids, fields, start_date, end_date: (
            _fetch_hk_dividends_direct(order_book_ids, start_date=start_date, end_date=end_date)
            if _uses_hk_unique_ids(order_book_ids)
            else rqdatac.get_dividend(
                order_book_ids,
                start_date=start_date,
                end_date=end_date,
                market="hk",
            )
        ),
    )


def mirror_hk_shares(args, rqdatac) -> int:
    fields, field_metadata = _resolve_default_plus_explicit_fields(
        args,
        default_fields=DEFAULT_HK_SHARES_FIELDS,
        source_label="default_plus_explicit",
    )
    return _mirror_dated_dataset(
        args=args,
        rqdatac=rqdatac,
        dataset_name="shares",
        api_name="rqdatac.get_shares",
        date_column="date",
        fields=fields,
        field_metadata=field_metadata,
        resolve_request_groups=lambda symbols, start_date, end_date, args: _resolve_hk_dated_request_groups(
            symbols,
            start_date=start_date,
            end_date=end_date,
            out_root=getattr(args, "out_root", DEFAULT_OUT_ROOT),
        ),
        normalize_payload=_normalize_hk_dated_payload,
        fetch_batch=lambda order_book_ids, selected_fields, start_date, end_date: (
            _fetch_hk_shares_direct(
                order_book_ids,
                fields=list(selected_fields),
                start_date=start_date,
                end_date=end_date,
            )
            if _uses_hk_unique_ids(order_book_ids)
            else rqdatac.get_shares(
                order_book_ids,
                start_date=start_date,
                end_date=end_date,
                fields=list(selected_fields),
                market="hk",
            )
        ),
    )


def mirror_hk_exchange_rate(args, rqdatac) -> int:
    start_date = _normalize_absolute_date(args.start_date, label="--start-date")
    end_date = _normalize_absolute_date(args.end_date, label="--end-date")
    if start_date > end_date:
        raise SystemExit("--start-date must be <= --end-date.")

    fields, field_metadata = _resolve_default_plus_explicit_fields(
        args,
        default_fields=DEFAULT_HK_EXCHANGE_RATE_FIELDS,
        source_label="default_plus_explicit",
    )
    resume = bool(getattr(args, "resume", False))
    max_attempts = max(1, int(getattr(args, "max_attempts", DEFAULT_MIRROR_MAX_ATTEMPTS) or 1))
    backoff_seconds = float(getattr(args, "backoff_seconds", DEFAULT_MIRROR_BACKOFF_SECONDS))
    max_backoff_seconds = float(
        getattr(args, "max_backoff_seconds", DEFAULT_MIRROR_MAX_BACKOFF_SECONDS)
    )
    output_dir = _prepare_daily_output_dir(
        out_root=getattr(args, "out_root", DEFAULT_OUT_ROOT),
        dataset_name="exchange_rate",
        start_date=start_date,
        end_date=end_date,
        name=getattr(args, "name", None),
        resume=resume,
    )
    if resume:
        _validate_global_daily_resume_inputs(
            output_dir=output_dir,
            dataset_name="exchange_rate",
            fields=fields,
            start_date=start_date,
            end_date=end_date,
        )

    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    fields_path = output_dir / "fields.txt"
    data_path = data_dir / "exchange_rate.parquet"
    currency_pairs_path = output_dir / "currency_pairs.txt"
    dates_path = output_dir / "dates.txt"

    started_at = _timestamp_now()
    finished_at: str | None = None
    status = "completed"
    error: str | None = None
    result_code = 0
    total_attempts = 0
    fetch_chunks = _split_daily_range_by_year(start_date, end_date)
    frame = pd.DataFrame()

    try:
        chunk_frames: list[pd.DataFrame] = []
        for chunk_index, (chunk_start, chunk_end) in enumerate(fetch_chunks, start=1):
            print(
                f"Fetching exchange_rate chunk {chunk_index}/{len(fetch_chunks)}: "
                f"{chunk_start} -> {chunk_end}"
            )
            payload, attempts = _retry_fetch(
                f"exchange_rate fetch failed for {chunk_start}->{chunk_end}",
                lambda chunk_start=chunk_start, chunk_end=chunk_end: rqdatac.get_exchange_rate(
                    start_date=chunk_start,
                    end_date=chunk_end,
                    fields=list(fields),
                ),
                max_attempts=max_attempts,
                backoff_seconds=backoff_seconds,
                max_backoff_seconds=max_backoff_seconds,
            )
            total_attempts += attempts
            if isinstance(payload, pd.Series):
                chunk_frame = payload.to_frame().reset_index()
            elif isinstance(payload, pd.DataFrame):
                chunk_frame = payload.reset_index()
            else:
                chunk_frame = pd.DataFrame(payload)
            chunk_frames.append(_normalize_frame_columns(chunk_frame))

        if chunk_frames:
            frame = pd.concat(chunk_frames, ignore_index=True)
        else:
            frame = pd.DataFrame()
        if "date" not in frame.columns and "index" in frame.columns:
            frame = frame.rename(columns={"index": "date"})
        if "date" not in frame.columns:
            raise SystemExit("exchange_rate payload is missing date.")
        if "currency_pair" not in frame.columns:
            raise SystemExit("exchange_rate payload is missing currency_pair.")

        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y%m%d")
        frame = frame[frame["date"].notna()].copy()
        frame["currency_pair"] = frame["currency_pair"].astype(str).str.strip()
        frame = frame[frame["currency_pair"] != ""].copy()
        frame.sort_values(["date", "currency_pair"], kind="mergesort", inplace=True)
        frame.reset_index(drop=True, inplace=True)

        _write_text_list(fields_path, fields)
        _write_text_list(currency_pairs_path, frame["currency_pair"].drop_duplicates().tolist())
        _write_text_list(dates_path, frame["date"].drop_duplicates().tolist())
        frame.to_parquet(data_path, index=False)
    except MirrorQuotaError as exc:
        status = "quota_exhausted"
        error = str(exc)
        result_code = 2
        finished_at = _timestamp_now()
    except Exception as exc:
        status = "failed"
        error = str(exc)
        result_code = 1
        finished_at = _timestamp_now()
    else:
        finished_at = _timestamp_now()
    finally:
        totals = {
            "rows": int(len(frame)),
            "dates": int(frame["date"].nunique()) if "date" in frame.columns else 0,
            "currency_pairs": int(frame["currency_pair"].nunique()) if "currency_pair" in frame.columns else 0,
            "bytes": int(data_path.stat().st_size) if data_path.exists() else 0,
        }
        manifest = {
            "name": output_dir.name,
            "created_at": started_at,
            "dataset": "exchange_rate",
            "api": "rqdatac.get_exchange_rate",
            "market": "hk",
            "config_ref": getattr(args, "config", None),
            "output_dir": str(output_dir),
            "data_file": str(data_path),
            "fields_file": str(fields_path),
            "currency_pairs_file": str(currency_pairs_path),
            "dates_file": str(dates_path),
            "query": {
                "start_date": start_date,
                "end_date": end_date,
                "fields": list(fields),
            },
            "field_metadata": field_metadata,
            "columns": frame.columns.tolist(),
            "totals": totals,
            "currency_pairs": frame["currency_pair"].drop_duplicates().tolist()
            if "currency_pair" in frame.columns
            else [],
            "status": status,
            "error": error,
            "started_at": started_at,
            "finished_at": finished_at,
            "attempts": total_attempts,
            "fetch_chunks": len(fetch_chunks),
            "git": _git_metadata(Path.cwd().resolve()),
        }
        _write_manifest(output_dir / "manifest.yml", manifest)

    print(
        f"Wrote exchange_rate mirror to {output_dir} "
        f"({len(frame)} rows, {int(frame['date'].nunique()) if 'date' in frame.columns else 0} dates, "
        f"{int(frame['currency_pair'].nunique()) if 'currency_pair' in frame.columns else 0} currency pairs, "
        f"status={status})"
    )
    return result_code


def mirror_hk_announcement(args, rqdatac) -> int:
    _ensure_rqdatac_hk_plugin()
    hk_api = getattr(rqdatac, "hk", None)
    if hk_api is None or not hasattr(hk_api, "get_announcement"):
        raise SystemExit("rqdatac.hk.get_announcement is unavailable. Check rqdatac-hk installation.")

    fields, field_metadata = _resolve_optional_explicit_fields(args)
    return _mirror_dated_dataset(
        args=args,
        rqdatac=rqdatac,
        dataset_name="announcement",
        api_name="rqdatac.hk.get_announcement",
        date_column="info_date",
        fields=fields,
        field_metadata=field_metadata,
        sort_columns=("rice_create_tm", "first_category", "second_category", "third_category", "title"),
        resolve_request_groups=lambda symbols, start_date, end_date, args: _resolve_hk_dated_request_groups(
            symbols,
            start_date=start_date,
            end_date=end_date,
            out_root=getattr(args, "out_root", DEFAULT_OUT_ROOT),
        ),
        normalize_payload=_normalize_hk_dated_payload,
        fetch_batch=lambda order_book_ids, selected_fields, start_date, end_date: hk_api.get_announcement(
            order_book_ids=list(order_book_ids),
            start_date=start_date,
            end_date=end_date,
            fields=list(selected_fields) if selected_fields else None,
            market="hk",
        ),
    )


def mirror_hk_southbound(args, rqdatac) -> int:
    symbols, symbol_metadata = _resolve_symbols(args)
    start_date = _normalize_absolute_date(args.start_date, label="--start-date")
    end_date = _normalize_absolute_date(args.end_date, label="--end-date")
    if start_date > end_date:
        raise SystemExit("--start-date must be <= --end-date.")

    trading_types = _resolve_hk_southbound_trading_types(args)
    snapshot_dates, snapshot_metadata = _resolve_hk_trading_snapshot_dates(
        rqdatac,
        args,
        start_date=start_date,
        end_date=end_date,
    )
    resume = bool(getattr(args, "resume", False))
    skip_existing = bool(getattr(args, "skip_existing", False) or resume)
    max_attempts = max(1, int(getattr(args, "max_attempts", DEFAULT_MIRROR_MAX_ATTEMPTS) or 1))
    backoff_seconds = float(getattr(args, "backoff_seconds", DEFAULT_MIRROR_BACKOFF_SECONDS))
    max_backoff_seconds = float(
        getattr(args, "max_backoff_seconds", DEFAULT_MIRROR_MAX_BACKOFF_SECONDS)
    )
    output_dir = _prepare_daily_output_dir(
        out_root=getattr(args, "out_root", DEFAULT_OUT_ROOT),
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
    entries_by_symbol: dict[str, DatedMirrorEntry] = {}
    audit_by_symbol: dict[str, DatedMirrorAuditRecord] = {}
    frames_by_symbol: dict[str, list[pd.DataFrame]] = {}
    batches: list[dict[str, object]] = []
    columns: list[str] = []
    field_coverage = _field_coverage_template(fields)
    started_at = _timestamp_now()
    status = "completed"
    error: str | None = None
    result_code = 0
    quota_blocked = False
    order_book_id_by_symbol = {symbol: _to_rqdata_symbol("hk", symbol) for symbol in symbols}
    symbol_map = {order_book_id: symbol for symbol, order_book_id in order_book_id_by_symbol.items()}

    def _record_entry(
        *,
        symbol: str,
        entry: DatedMirrorEntry,
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
        audit_by_symbol[symbol] = _dated_audit_record(
            ts_code=symbol,
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
        record_status: str,
        attempts: int,
        started_at_value: str | None,
        finished_at_value: str | None,
        error_text: str | None = None,
    ) -> None:
        audit_by_symbol[symbol] = _dated_audit_record(
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
            _validate_dated_resume_inputs(
                output_dir=output_dir,
                dataset_name="southbound",
                fields=fields,
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
            )
            manifest = _load_manifest(output_dir / "manifest.yml") or {}
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
                        _dedupe_preserve_order(existing_types)
                        if isinstance(existing_types, Sequence) and not isinstance(existing_types, str)
                        else _dedupe_preserve_order([existing_types])
                    )
                    if normalized_existing_types != list(trading_types):
                        raise SystemExit("Resume target query mismatch for trading_types.")
            existing_dates = _load_existing_text_list(output_dir / "dates.txt", strip=False)
            if existing_dates and list(existing_dates) != list(snapshot_dates):
                raise SystemExit("Resume target dates.txt does not match the requested date list.")
            existing_trading_types = _load_existing_text_list(output_dir / "trading_types.txt", strip=False)
            if existing_trading_types and list(existing_trading_types) != list(trading_types):
                raise SystemExit(
                    "Resume target trading_types.txt does not match the requested trading type list."
                )

        _write_text_list(output_dir / "fields.txt", fields)
        _write_text_list(output_dir / "symbols.txt", symbols)
        _write_text_list(output_dir / "dates.txt", snapshot_dates)
        _write_text_list(output_dir / "trading_types.txt", trading_types)

        pending_symbols: list[str] = []
        for symbol in symbols:
            out_path = data_dir / f"{symbol}.parquet"
            if skip_existing and out_path.exists():
                try:
                    entry, symbol_frame = _load_existing_dated_entry(
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
                    finished_at_value=_path_mtime_iso(out_path),
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
                batch_started_at = _timestamp_now()
                try:
                    payload, attempts = _retry_fetch(
                        f"southbound fetch failed for {trading_type} @ {query_date}",
                        lambda: rqdatac.hk.get_southbound_eligible_secs(
                            trading_type=trading_type,
                            date=query_date,
                        ),
                        max_attempts=max_attempts,
                        backoff_seconds=backoff_seconds,
                        max_backoff_seconds=max_backoff_seconds,
                    )
                except MirrorQuotaError as exc:
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
                except MirrorFetchError as exc:
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
                    ts_code = _normalize_hk_symbol(order_book_id)
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
                prepared = _prepare_dated_asset_frame(
                    pd.DataFrame(
                        rows,
                        columns=["date", "ts_code", "order_book_id", "trading_type", "eligible"],
                    ),
                    symbol_map=symbol_map,
                    date_column="date",
                    sort_columns=("trading_type",),
                )
                prepared = _ensure_requested_fields(prepared, fields)
                batches.append(
                    {
                        "date": query_date,
                        "trading_type": trading_type,
                        "rows": int(len(prepared)),
                        "symbols": int(prepared["ts_code"].nunique()) if not prepared.empty else 0,
                        "status": "completed",
                        "attempts": attempts,
                        "started_at": batch_started_at,
                        "finished_at": _timestamp_now(),
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
        finished_at = _timestamp_now()
        for symbol in symbols:
            if symbol in audit_by_symbol:
                continue
            frames = frames_by_symbol.get(symbol) or []
            if frames:
                combined = pd.concat(frames, ignore_index=True)
                combined = combined.drop_duplicates(subset=["date", "trading_type"], keep="last")
                combined = combined.sort_values(["date", "trading_type"]).reset_index(drop=True)
                entry = _write_dated_symbol_frame(data_dir, combined, date_column="date")
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
        _write_dated_audit_csv(audit_path, audit_records)
        manifest = _build_dated_manifest(
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
        _write_manifest(output_dir / "manifest.yml", manifest)

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
    source = _resolve_hk_industry_source(args)
    level, fields = _resolve_hk_instrument_industry_level(args)
    symbols, symbol_metadata = _resolve_symbols(args)
    start_date = _normalize_absolute_date(args.start_date, label="--start-date")
    end_date = _normalize_absolute_date(args.end_date, label="--end-date")
    if start_date > end_date:
        raise SystemExit("--start-date must be <= --end-date.")

    snapshot_dates, snapshot_metadata = _resolve_hk_snapshot_dates(
        args,
        start_date=start_date,
        end_date=end_date,
    )
    resume = bool(getattr(args, "resume", False))
    skip_existing = bool(getattr(args, "skip_existing", False) or resume)
    max_attempts = max(1, int(getattr(args, "max_attempts", DEFAULT_MIRROR_MAX_ATTEMPTS) or 1))
    backoff_seconds = float(getattr(args, "backoff_seconds", DEFAULT_MIRROR_BACKOFF_SECONDS))
    max_backoff_seconds = float(
        getattr(args, "max_backoff_seconds", DEFAULT_MIRROR_MAX_BACKOFF_SECONDS)
    )
    output_dir = _prepare_daily_output_dir(
        out_root=getattr(args, "out_root", DEFAULT_OUT_ROOT),
        dataset_name="instrument_industry",
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
    entries_by_symbol: dict[str, DatedMirrorEntry] = {}
    audit_by_symbol: dict[str, DatedMirrorAuditRecord] = {}
    frames_by_symbol: dict[str, list[pd.DataFrame]] = {}
    batches: list[dict[str, object]] = []
    columns: list[str] = []
    field_metadata = {
        "count": len(fields),
        "fields_file": [],
        "source": f"rqdatac_level_{level}",
        "base_fields": list(fields),
    }
    field_coverage = _field_coverage_template(fields)
    started_at = _timestamp_now()
    status = "completed"
    error: str | None = None
    result_code = 0
    quota_blocked = False

    def _record_entry(
        *,
        symbol: str,
        entry: DatedMirrorEntry,
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
        audit_by_symbol[symbol] = _dated_audit_record(
            ts_code=symbol,
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
        audit_by_symbol[symbol] = _dated_audit_record(
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
        batch_started_at = _timestamp_now()
        try:
            payload, attempts = _retry_fetch(
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
        except MirrorQuotaError as exc:
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
        except MirrorFetchError as exc:
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

        prepared = _prepare_hk_instrument_industry_frame(
            payload,
            symbol_map={order_book_id: symbol_map[order_book_id] for order_book_id in batch_order_book_ids},
            query_date=query_date,
        )
        prepared = _ensure_requested_fields(prepared, fields)
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
            _validate_dated_resume_inputs(
                output_dir=output_dir,
                dataset_name="instrument_industry",
                fields=fields,
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
            )
            manifest = _load_manifest(output_dir / "manifest.yml") or {}
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
                if query.get("rebalance_frequency") not in {None, snapshot_metadata.get('rebalance_frequency')}:
                    raise SystemExit(
                        "Resume target query mismatch for rebalance_frequency."
                    )
            existing_dates = _load_existing_text_list(output_dir / "dates.txt", strip=False)
            if existing_dates and list(existing_dates) != list(snapshot_dates):
                raise SystemExit("Resume target dates.txt does not match the requested date list.")

        _write_text_list(output_dir / "fields.txt", fields)
        _write_text_list(output_dir / "symbols.txt", symbols)
        _write_text_list(output_dir / "dates.txt", snapshot_dates)

        pending_order_book_ids: list[str] = []
        for order_book_id in order_book_ids:
            symbol = symbol_map[order_book_id]
            out_path = data_dir / f"{symbol}.parquet"
            if skip_existing and out_path.exists():
                try:
                    entry, symbol_frame = _load_existing_dated_entry(
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
                    finished_at_value=_path_mtime_iso(out_path),
                )
                continue
            pending_order_book_ids.append(order_book_id)

        for query_date in snapshot_dates:
            for batch_order_book_ids in _chunked(
                pending_order_book_ids,
                getattr(args, "batch_size", DEFAULT_BATCH_SIZE),
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
        finished_at = _timestamp_now()
        for order_book_id in pending_order_book_ids if "pending_order_book_ids" in locals() else order_book_ids:
            symbol = symbol_map[order_book_id]
            if symbol in audit_by_symbol:
                continue
            frames = frames_by_symbol.get(symbol) or []
            if frames:
                combined = pd.concat(frames, ignore_index=True)
                combined = combined.drop_duplicates(subset=["date"], keep="last")
                combined = combined.sort_values(["date"]).reset_index(drop=True)
                entry = _write_dated_symbol_frame(data_dir, combined, date_column="date")
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
        _write_dated_audit_csv(audit_path, audit_records)
        manifest = _build_dated_manifest(
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
        _write_manifest(output_dir / "manifest.yml", manifest)

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
    source = _resolve_hk_industry_source(args)
    level = _resolve_hk_industry_change_level(args)
    symbols, symbol_metadata = _resolve_symbols(args)
    start_date = _normalize_absolute_date(args.start_date, label="--start-date")
    end_date = _normalize_absolute_date(args.end_date, label="--end-date")
    if start_date > end_date:
        raise SystemExit("--start-date must be <= --end-date.")

    mapping_date = getattr(args, "mapping_date", None)
    mapping_date = _normalize_absolute_date(mapping_date, label="--mapping-date") if mapping_date else end_date
    catalog = _build_hk_industry_catalog(
        rqdatac,
        source=source,
        level=level,
        mapping_date=mapping_date,
    )
    industries = catalog["industry_code"].astype(str).tolist()
    resume = bool(getattr(args, "resume", False))
    skip_existing = bool(getattr(args, "skip_existing", False) or resume)
    max_attempts = max(1, int(getattr(args, "max_attempts", DEFAULT_MIRROR_MAX_ATTEMPTS) or 1))
    backoff_seconds = float(getattr(args, "backoff_seconds", DEFAULT_MIRROR_BACKOFF_SECONDS))
    max_backoff_seconds = float(
        getattr(args, "max_backoff_seconds", DEFAULT_MIRROR_MAX_BACKOFF_SECONDS)
    )
    output_dir = _prepare_daily_output_dir(
        out_root=getattr(args, "out_root", DEFAULT_OUT_ROOT),
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

    symbol_set = set(symbols)
    symbol_map = {_to_rqdata_symbol("hk", symbol): symbol for symbol in symbols}
    order_book_ids = list(symbol_map.keys())
    fields = [
        "cancel_date",
        "industry_code",
        "industry_name",
        "industry_level",
        "industry_source",
        *HK_INDUSTRY_HIERARCHY_COLUMNS,
    ]
    field_metadata = {
        "count": len(fields),
        "fields_file": [],
        "source": f"industry_mapping_level_{level}",
        "base_fields": list(fields),
    }
    entries_by_symbol: dict[str, DatedMirrorEntry] = {}
    audit_by_symbol: dict[str, DatedMirrorAuditRecord] = {}
    frames_by_symbol: dict[str, list[pd.DataFrame]] = {}
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
        entry: DatedMirrorEntry,
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
        audit_by_symbol[symbol] = _dated_audit_record(
            ts_code=symbol,
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
        audit_by_symbol[symbol] = _dated_audit_record(
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
            _validate_dated_resume_inputs(
                output_dir=output_dir,
                dataset_name="industry_changes",
                fields=fields,
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
            )
            manifest = _load_manifest(output_dir / "manifest.yml") or {}
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
            existing_industries = _load_existing_text_list(output_dir / "industries.txt", strip=False)
            if existing_industries and list(existing_industries) != list(industries):
                raise SystemExit("Resume target industries.txt does not match the requested industry list.")

        _write_text_list(output_dir / "fields.txt", fields)
        _write_text_list(output_dir / "symbols.txt", symbols)
        _write_text_list(output_dir / "industries.txt", industries)
        catalog.to_parquet(catalog_path, index=False)

        pending_order_book_ids: list[str] = []
        for order_book_id in order_book_ids:
            symbol = symbol_map[order_book_id]
            out_path = data_dir / f"{symbol}.parquet"
            if skip_existing and out_path.exists():
                try:
                    entry, symbol_frame = _load_existing_dated_entry(
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
                    finished_at_value=_path_mtime_iso(out_path),
                )
                continue
            pending_order_book_ids.append(order_book_id)

        pending_symbol_set = {symbol_map[order_book_id] for order_book_id in pending_order_book_ids}
        for industry_row in catalog.itertuples(index=False):
            if quota_blocked or not pending_symbol_set:
                break
            industry_code = str(getattr(industry_row, "industry_code"))
            industry_name = str(getattr(industry_row, "industry_name"))
            batch_started_at = _timestamp_now()
            try:
                payload, attempts = _retry_fetch(
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
            except MirrorQuotaError as exc:
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
            except MirrorFetchError as exc:
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

            prepared = _prepare_hk_industry_change_frame(
                payload,
                catalog_row=industry_row._asdict(),
                symbol_filter=pending_symbol_set,
                start_date=start_date,
                end_date=end_date,
            )
            prepared = _ensure_requested_fields(prepared, fields)
            batches.append(
                {
                    "industry_code": industry_code,
                    "industry_name": industry_name,
                    "rows": int(len(prepared)),
                    "status": "completed",
                    "attempts": attempts,
                    "started_at": batch_started_at,
                    "finished_at": _timestamp_now(),
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
        finished_at = _timestamp_now()
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
                entry = _write_dated_symbol_frame(data_dir, combined, date_column="start_date")
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
        _write_dated_audit_csv(audit_path, audit_records)
        manifest = _build_dated_manifest(
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
        _write_manifest(output_dir / "manifest.yml", manifest)

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


def _rqdata_assets_build_module():
    from . import rqdata_assets_build as _build

    return _build


def _resolve_pit_asset_dir(path_text: str | Path) -> tuple[Path, dict | None]:
    return _rqdata_assets_build_module()._resolve_pit_asset_dir(path_text)


def _resolve_industry_changes_asset_dir(path_text: str | Path) -> tuple[Path, dict | None]:
    return _rqdata_assets_build_module()._resolve_industry_changes_asset_dir(path_text)


def _default_hk_industry_labels_path(asset_dir: Path, frequency: str) -> Path:
    return _rqdata_assets_build_module()._default_hk_industry_labels_path(asset_dir, frequency)


def _resolve_hk_industry_labels_out_path(args, asset_dir: Path) -> Path:
    return _rqdata_assets_build_module()._resolve_hk_industry_labels_out_path(args, asset_dir)


def _industry_labels_manifest_path(out_path: Path) -> Path:
    return _rqdata_assets_build_module()._industry_labels_manifest_path(out_path)


def _resolve_hk_label_frequency(args) -> str:
    return _rqdata_assets_build_module()._resolve_hk_label_frequency(args)


def _resolve_optional_absolute_date(value: object, *, label: str) -> str | None:
    return _rqdata_assets_build_module()._resolve_optional_absolute_date(value, label=label)


def _load_trade_date_grid_from_daily_asset_dir(
    daily_asset_dir: Path,
    *,
    start_date: str | None,
    end_date: str | None,
) -> pd.DataFrame:
    return _rqdata_assets_build_module()._load_trade_date_grid_from_daily_asset_dir(
        daily_asset_dir,
        start_date=start_date,
        end_date=end_date,
    )


def _sample_trade_date_grid(grid: pd.DataFrame, *, frequency: str) -> tuple[pd.DataFrame, dict[str, object]]:
    return _rqdata_assets_build_module()._sample_trade_date_grid(grid, frequency=frequency)


def _resolve_hk_industry_label_grid(args) -> tuple[pd.DataFrame, dict[str, object]]:
    return _rqdata_assets_build_module()._resolve_hk_industry_label_grid(args)


def _load_industry_changes_frame(data_files: Sequence[Path]) -> tuple[pd.DataFrame, int]:
    return _rqdata_assets_build_module()._load_industry_changes_frame(data_files)


def _derive_hk_industry_labels(
    *,
    grid: pd.DataFrame,
    intervals: pd.DataFrame,
) -> tuple[pd.DataFrame, int]:
    return _rqdata_assets_build_module()._derive_hk_industry_labels(
        grid=grid,
        intervals=intervals,
    )


def _resolve_build_fields(
    *,
    args,
    manifest: Mapping[str, object] | None,
    available_columns: Sequence[str],
) -> tuple[list[str], dict]:
    return _rqdata_assets_build_module()._resolve_build_fields(
        args=args,
        manifest=manifest,
        available_columns=available_columns,
    )


def _default_pipeline_fundamentals_path(asset_dir: Path) -> Path:
    return _rqdata_assets_build_module()._default_pipeline_fundamentals_path(asset_dir)


def _resolve_pipeline_fundamentals_out_path(args, asset_dir: Path) -> Path:
    return _rqdata_assets_build_module()._resolve_pipeline_fundamentals_out_path(args, asset_dir)


def _load_universe_by_date_frame(path_text: str | Path) -> pd.DataFrame:
    return _rqdata_assets_build_module()._load_universe_by_date_frame(path_text)


def _rqdata_assets_coverage_module():
    from . import rqdata_assets_coverage as _coverage

    return _coverage


def _is_supported_pit_coverage_feature(feature: str, available_columns: set[str]) -> bool:
    return _rqdata_assets_coverage_module()._is_supported_pit_coverage_feature(
        feature, available_columns
    )


def _compute_pit_coverage_series(
    frame: pd.DataFrame,
    feature: str,
    *,
    cache: dict[str, pd.Series],
) -> pd.Series:
    return _rqdata_assets_coverage_module()._compute_pit_coverage_series(
        frame,
        feature,
        cache=cache,
    )


def _resolve_pit_coverage_features(
    *,
    args,
    config_data: Mapping[str, object] | None,
    manifest: Mapping[str, object] | None,
    available_columns: Sequence[str],
) -> tuple[list[str], dict[str, object]]:
    return _rqdata_assets_coverage_module()._resolve_pit_coverage_features(
        args=args,
        config_data=config_data,
        manifest=manifest,
        available_columns=available_columns,
    )


def _resolve_trainable_pit_features(
    *,
    args,
    config_data: Mapping[str, object] | None,
    available_columns: Sequence[str],
    fallback_features: Sequence[str],
    fallback_metadata: Mapping[str, object],
) -> tuple[list[str], dict[str, object]]:
    return _rqdata_assets_coverage_module()._resolve_trainable_pit_features(
        args=args,
        config_data=config_data,
        available_columns=available_columns,
        fallback_features=fallback_features,
        fallback_metadata=fallback_metadata,
    )


def _resolve_trainable_pit_settings(
    config_data: Mapping[str, object] | None,
    *,
    selected_features: Sequence[str],
) -> dict[str, object]:
    return _rqdata_assets_coverage_module()._resolve_trainable_pit_settings(
        config_data,
        selected_features=selected_features,
    )


def _build_trainable_period_grid(
    *,
    frame: pd.DataFrame,
    rebalance_frequency: str,
    sample_on_rebalance_dates: bool,
    universe_by_date: pd.DataFrame | None,
) -> tuple[pd.DataFrame, str]:
    return _rqdata_assets_coverage_module()._build_trainable_period_grid(
        frame=frame,
        rebalance_frequency=rebalance_frequency,
        sample_on_rebalance_dates=sample_on_rebalance_dates,
        universe_by_date=universe_by_date,
    )


def _estimate_trainable_pit_coverage(
    *,
    frame: pd.DataFrame,
    feature_frame: pd.DataFrame,
    selected_features: Sequence[str],
    config_data: Mapping[str, object] | None,
    min_symbols: int,
    feature_source: str,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    return _rqdata_assets_coverage_module()._estimate_trainable_pit_coverage(
        frame=frame,
        feature_frame=feature_frame,
        selected_features=selected_features,
        config_data=config_data,
        min_symbols=min_symbols,
        feature_source=feature_source,
    )


def _assess_trainable_fill_dependence(
    *,
    trainable_estimate: Mapping[str, object],
    non_pit_features_ignored: Sequence[str],
) -> dict[str, object]:
    return _rqdata_assets_coverage_module()._assess_trainable_fill_dependence(
        trainable_estimate=trainable_estimate,
        non_pit_features_ignored=non_pit_features_ignored,
    )


def _render_hk_pit_coverage_text(
    payload: Mapping[str, object],
    *,
    top: int,
    quarter_limit: int,
) -> str:
    return _rqdata_assets_coverage_module()._render_hk_pit_coverage_text(
        payload,
        top=top,
        quarter_limit=quarter_limit,
    )


def inspect_hk_pit_coverage(args) -> int:
    return _rqdata_assets_coverage_module().inspect_hk_pit_coverage(args)


def _pipeline_fundamentals_manifest_path(out_path: Path) -> Path:
    return _rqdata_assets_build_module()._pipeline_fundamentals_manifest_path(out_path)


def _write_symbol_list(path: Path, symbols: Sequence[str]) -> None:
    return _rqdata_assets_build_module()._write_symbol_list(path, symbols)


def _build_filtered_universe_by_date(
    *,
    source_path: Path,
    out_path: Path,
    symbols: Sequence[str],
) -> dict[str, object]:
    return _rqdata_assets_build_module()._build_filtered_universe_by_date(
        source_path=source_path,
        out_path=out_path,
        symbols=symbols,
    )


def build_hk_pit_fundamentals_file(args) -> int:
    return _rqdata_assets_build_module().build_hk_pit_fundamentals_file(args)


def build_hk_industry_labels_file(args) -> int:
    return _rqdata_assets_build_module().build_hk_industry_labels_file(args)


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
