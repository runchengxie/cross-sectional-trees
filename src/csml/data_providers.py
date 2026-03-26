"""Market-aware data providers for daily OHLCV data and basic metadata."""
from __future__ import annotations

import hashlib
import io
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable, Mapping, Optional

import numpy as np
import pandas as pd

from .data_tools.symbols import (
    PROVIDER_SYMBOL_PRIORITY,
    ensure_symbol_columns,
    normalize_symbol_standard_name,
)


DEFAULT_DAILY_ENDPOINTS = {
    "cn": "daily",
    "hk": "hk_daily",
    "us": "us_daily",
}

DEFAULT_BASIC_ENDPOINTS = {
    "cn": "stock_basic",
    "hk": "hk_basic",
    "us": "us_basic",
}

DEFAULT_BASIC_FIELDS = {
    "cn": "ts_code,name,list_date",
    "hk": "ts_code,name,list_date",
    "us": "ts_code,name,list_date",
}

DEFAULT_BASIC_PARAMS = {
    "cn": {"list_status": "L"},
    "hk": {},
    "us": {},
}

FUNDAMENTAL_COLUMN_CANDIDATES = {
    "trade_date": ["trade_date", "date", "trade_dt", "trade_day"],
    "symbol": ["symbol", "ts_code", "ticker", "code", "sec_code", "tscode", "order_book_id"],
}

FUNDAMENTAL_REQUIRED_COLUMNS = ("trade_date", "symbol")

DEFAULT_RQDATA_HK_FUNDAMENTAL_FIELDS = {
    "market_cap": "hk_total_market_val",
    "pe_ttm": "pe_ratio_ttm",
    "pb": "pb_ratio_ttm",
}

DEFAULT_COLUMN_MAPS = {
    "cn": {
        "trade_date": "trade_date",
        "symbol": "ts_code",
        "close": "close",
        "vol": "vol",
        "amount": "amount",
    },
    "hk": {
        "trade_date": "trade_date",
        "symbol": "ts_code",
        "close": "close",
        "vol": "vol",
        "amount": "amount",
    },
    "us": {
        "trade_date": "trade_date",
        "symbol": "ts_code",
        "close": "close",
        "vol": "vol",
        "amount": "amount",
    },
}

COLUMN_CANDIDATES = {
    "trade_date": ["trade_date", "date", "trade_dt", "trade_day"],
    "symbol": ["symbol", "ts_code", "ticker", "code", "sec_code", "tscode"],
    "close": ["close", "close_price", "adj_close", "close_adj", "cls"],
    "vol": ["vol", "volume", "trade_vol", "volume_traded"],
    "amount": ["amount", "turnover", "total_turnover", "trade_value", "value"],
}

REQUIRED_DAILY_COLUMNS = ("trade_date", "symbol", "close", "vol")
_RQDATA_LISTED_DATE_CACHE: dict[tuple[str, str], pd.Timestamp | None] = {}


def normalize_market(market: Optional[str]) -> str:
    value = str(market or "cn").strip().lower()
    return value if value else "cn"


def resolve_provider(data_cfg: Optional[Mapping]) -> str:
    if not isinstance(data_cfg, Mapping):
        return "tushare"
    value = str(data_cfg.get("provider", "tushare")).strip().lower()
    if value in {"rqdatac", "rqdata"}:
        return "rqdata"
    if value in {"tushare", "ts"}:
        return "tushare"
    if value in {"eodhd", "eod"}:
        return "eodhd"
    return value or "tushare"


def fundamentals_provider_supported(provider: str, market: str) -> bool:
    provider = resolve_provider({"provider": provider})
    market = normalize_market(market)
    return provider == "tushare" or (provider == "rqdata" and market == "hk")


def _hk_to_rqdata_symbol(symbol: str) -> str:
    text = str(symbol or "").strip().upper()
    if not text:
        return text
    if text.endswith(".XHKG"):
        return text
    if text.endswith(".HK"):
        text = text[:-3]
    if text.isdigit():
        text = text.zfill(5)
    return f"{text}.XHKG"


def _to_rqdata_symbol(market: str, symbol: str) -> str:
    market = normalize_market(market)
    if market == "hk":
        return _hk_to_rqdata_symbol(symbol)
    return str(symbol or "").strip()


def _hk_to_eodhd_symbol(symbol: str, eod_cfg: Optional[Mapping]) -> str:
    text = str(symbol or "").strip().upper()
    if not text:
        return text
    if text.endswith(".XHKG"):
        text = text[:-5]
    if text.endswith(".HK"):
        text = text[:-3]
    if text.isdigit():
        mode = None
        if isinstance(eod_cfg, Mapping):
            mode = str(eod_cfg.get("hk_symbol_mode") or "").strip().lower() or None
        if mode == "strip_one":
            if len(text) == 5 and text.startswith("0"):
                text = text[1:]
        elif mode == "strip_all":
            text = text.lstrip("0") or "0"
        elif mode == "pad4":
            text = text.zfill(4)
        elif mode == "pad5":
            text = text.zfill(5)
    return f"{text}.HK"


def _to_eodhd_symbol(market: str, symbol: str, eod_cfg: Optional[Mapping]) -> str:
    market = normalize_market(market)
    text = str(symbol or "").strip().upper()
    if not text:
        return text
    if market == "hk":
        return _hk_to_eodhd_symbol(text, eod_cfg)
    if "." in text:
        return text
    exchange = None
    if isinstance(eod_cfg, Mapping):
        exchange = str(eod_cfg.get("exchange") or "").strip().upper() or None
    if exchange:
        return f"{text}.{exchange}"
    return text


def _prepare_rqdata_daily_frame(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    df = df.copy()
    if isinstance(df.index, pd.MultiIndex):
        date_index = df.index.get_level_values(-1)
    else:
        date_index = df.index
    df = df.reset_index(drop=True)
    df["trade_date"] = pd.to_datetime(date_index).strftime("%Y%m%d")
    df["symbol"] = symbol
    return ensure_symbol_columns(df, context="RQData daily frame", priority=PROVIDER_SYMBOL_PRIORITY)


def _prepare_rqdata_fundamentals_frame(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if isinstance(df, pd.Series):
        df = df.to_frame(name=str(df.name or "value"))
    df = df.copy()
    if isinstance(df.index, pd.MultiIndex):
        date_index = pd.to_datetime(df.index.get_level_values(-1), errors="coerce")
    else:
        date_index = pd.to_datetime(df.index, errors="coerce")
    df = df.reset_index(drop=True)
    df["trade_date"] = date_index.strftime("%Y%m%d")
    df["symbol"] = symbol
    df = df[df["trade_date"].notna()].copy()
    return ensure_symbol_columns(
        df,
        context="RQData fundamentals frame",
        priority=PROVIDER_SYMBOL_PRIORITY,
    )


def _rqdata_default_fields(rq_cfg: Optional[Mapping]) -> Optional[list[str]]:
    if isinstance(rq_cfg, Mapping) and "fields" in rq_cfg:
        fields = rq_cfg.get("fields")
        if fields is None or fields == "all" or fields == "*":
            return None
        return list(fields) if isinstance(fields, (list, tuple)) else [str(fields)]
    return ["close", "volume", "total_turnover"]


def _rqdata_skip_suspended(market: str, rq_cfg: Optional[Mapping]) -> Optional[bool]:
    if isinstance(rq_cfg, Mapping) and "skip_suspended" in rq_cfg:
        return bool(rq_cfg.get("skip_suspended"))
    return True if normalize_market(market) == "hk" else None


def _rqdata_listed_date(client, market: str, rq_symbol: str) -> pd.Timestamp | None:
    key = (normalize_market(market), str(rq_symbol))
    if key in _RQDATA_LISTED_DATE_CACHE:
        return _RQDATA_LISTED_DATE_CACHE[key]

    instrument = None
    try:
        instrument = client.instruments(rq_symbol, market=market)
    except TypeError:
        instrument = client.instruments(rq_symbol)
    except Exception:
        instrument = None
    if isinstance(instrument, list):
        instrument = instrument[0] if instrument else None

    listed_date = getattr(instrument, "listed_date", None) or getattr(instrument, "listed_at", None)
    parsed = pd.to_datetime(listed_date, errors="coerce")
    normalized = None if pd.isna(parsed) else parsed.normalize()
    _RQDATA_LISTED_DATE_CACHE[key] = normalized
    return normalized


def _rqdata_fundamental_fields(fundamentals_cfg: Mapping) -> list[str]:
    explicit_fields = fundamentals_cfg.get("fields")
    if explicit_fields is not None:
        if isinstance(explicit_fields, str):
            text = explicit_fields.strip()
            if text and text not in {"all", "*"}:
                return [text]
        else:
            normalized = [str(field).strip() for field in explicit_fields if str(field).strip()]
            if normalized:
                return normalized

    column_map = fundamentals_cfg.get("column_map")
    if isinstance(column_map, Mapping):
        inferred_fields: list[str] = []
        for standard in DEFAULT_RQDATA_HK_FUNDAMENTAL_FIELDS:
            source = column_map.get(standard)
            if source:
                inferred_fields.append(str(source))
        if inferred_fields:
            return inferred_fields

    return list(DEFAULT_RQDATA_HK_FUNDAMENTAL_FIELDS.values())


def _fundamentals_cache_file(
    cache_dir: Path,
    market: str,
    provider: str,
    symbol: str,
    start_date: str,
    end_date: str,
    tag: Optional[str],
    fundamentals_cfg: Mapping,
) -> Path:
    prefix = f"{market}_{provider}"
    if tag:
        prefix = f"{prefix}_{tag}"
    cache_payload = {
        "endpoint": fundamentals_cfg.get("endpoint"),
        "fields": fundamentals_cfg.get("fields"),
        "params": fundamentals_cfg.get("params") or {},
        "column_map": fundamentals_cfg.get("column_map") or {},
    }
    cache_digest = hashlib.md5(
        json.dumps(cache_payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:12]
    return (
        cache_dir
        / f"{prefix}_fundamentals_{symbol}_{start_date}_{end_date}_{cache_digest}.parquet"
    )


def _fetch_daily_rqdata(
    market: str,
    symbol: str,
    start_date: str,
    end_date: str,
    client,
    data_cfg: Mapping,
) -> pd.DataFrame:
    if client is None:
        import rqdatac as client
    rq_cfg = data_cfg.get("rqdata") if isinstance(data_cfg, Mapping) else None
    if isinstance(rq_cfg, Mapping) and rq_cfg.get("market"):
        rq_market = normalize_market(rq_cfg.get("market"))
    else:
        rq_market = normalize_market(market)
    frequency = "1d"
    if isinstance(rq_cfg, Mapping) and rq_cfg.get("frequency"):
        frequency = str(rq_cfg.get("frequency"))
    fields = _rqdata_default_fields(rq_cfg)
    skip_suspended = _rqdata_skip_suspended(rq_market, rq_cfg)

    kwargs = {}
    if fields is not None:
        kwargs["fields"] = fields
    if isinstance(rq_cfg, Mapping) and "adjust_type" in rq_cfg:
        kwargs["adjust_type"] = rq_cfg.get("adjust_type")
    if skip_suspended is not None:
        kwargs["skip_suspended"] = skip_suspended
    kwargs["market"] = rq_market

    rq_symbol = _to_rqdata_symbol(rq_market, symbol)
    effective_start = str(start_date).strip()
    effective_end = str(end_date).strip()
    if skip_suspended:
        listed_date = _rqdata_listed_date(client, rq_market, rq_symbol)
        start_ts = pd.to_datetime(effective_start, errors="coerce")
        end_ts = pd.to_datetime(effective_end, errors="coerce")
        if listed_date is not None and not pd.isna(start_ts) and not pd.isna(end_ts):
            if listed_date > end_ts.normalize():
                return pd.DataFrame()
            if listed_date > start_ts.normalize():
                effective_start = listed_date.strftime("%Y%m%d")

    df = client.get_price(rq_symbol, effective_start, effective_end, frequency, **kwargs)
    if df is None or df.empty:
        return df
    return _prepare_rqdata_daily_frame(df, symbol)


def _basic_cache_file(
    cache_dir: Path,
    market: str,
    provider: str,
    symbols: Optional[Iterable[str]],
    tag: Optional[str] = None,
) -> Path:
    prefix = f"{market}_{provider}"
    if tag:
        prefix = f"{prefix}_{tag}"
    if symbols:
        normalized = "|".join(sorted(str(sym) for sym in symbols))
        digest = hashlib.md5(normalized.encode("utf-8")).hexdigest()[:12]
        return cache_dir / f"{prefix}_basic_{digest}.parquet"
    return cache_dir / f"{prefix}_basic.parquet"


def _sanitize_cache_tag(tag: Optional[str]) -> Optional[str]:
    if not tag:
        return None
    text = str(tag).strip()
    if not text:
        return None
    cleaned = "".join(ch for ch in text if ch.isalnum() or ch in {"-", "_"})
    return cleaned or None


def _cache_tag(data_cfg: Optional[Mapping]) -> Optional[str]:
    if not isinstance(data_cfg, Mapping):
        return None
    tag = data_cfg.get("cache_tag") or data_cfg.get("cache_version")
    return _sanitize_cache_tag(tag)


def _normalize_trade_date_series(series: pd.Series) -> pd.Series:
    if series.empty:
        return series.astype(str)
    if pd.api.types.is_datetime64_any_dtype(series):
        return series.dt.strftime("%Y%m%d")
    parsed = pd.to_datetime(series.astype(str), errors="coerce")
    return parsed.dt.strftime("%Y%m%d")


def _ensure_trade_date_str(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or "trade_date" not in df.columns:
        return df
    df = df.copy()
    df["trade_date"] = _normalize_trade_date_series(df["trade_date"])
    df = df[df["trade_date"].notna()].copy()
    return df


def _is_small_leading_calendar_gap(
    start_date: str,
    cached_min: str,
    *,
    max_gap_days: int = 7,
) -> bool:
    """Treat tiny left-edge gaps as likely non-trading days."""
    try:
        start_ts = pd.to_datetime(str(start_date), format="%Y%m%d", errors="raise")
        cached_min_ts = pd.to_datetime(str(cached_min), format="%Y%m%d", errors="raise")
    except Exception:
        return False
    gap_days = int((cached_min_ts.normalize() - start_ts.normalize()).days)
    return 0 < gap_days <= int(max_gap_days)


def _resolve_eodhd_config(data_cfg: Mapping, client) -> dict:
    eod_cfg = data_cfg.get("eodhd") if isinstance(data_cfg, Mapping) else None
    resolved = dict(eod_cfg) if isinstance(eod_cfg, Mapping) else {}
    if isinstance(client, Mapping):
        for key in ("api_token", "base_url", "timeout", "exchange"):
            if key in client and client[key] is not None and key not in resolved:
                resolved[key] = client[key]
    if "api_token" not in resolved or not resolved.get("api_token"):
        resolved["api_token"] = os.getenv("EODHD_API_TOKEN") or os.getenv("EODHD_API_KEY")
    resolved.setdefault("base_url", "https://eodhd.com/api")
    resolved.setdefault("timeout", 30)
    return resolved


def _eodhd_request_text(url: str, timeout: float) -> str:
    req = urllib.request.Request(
        url, headers={"User-Agent": "cross-sectional-machine-learning/0.1"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read().decode("utf-8")
    except Exception as exc:
        raise ValueError(f"EODHD request failed: {exc}") from exc
    return payload


def _eodhd_build_url(base_url: str, path: str, params: Mapping[str, object]) -> str:
    clean_params = {k: v for k, v in params.items() if v is not None and v != ""}
    query = urllib.parse.urlencode(clean_params)
    base = base_url.rstrip("/")
    endpoint = path.lstrip("/")
    return f"{base}/{endpoint}?{query}"


def _eodhd_format_date(value: str) -> str:
    dt = pd.to_datetime(str(value), errors="coerce")
    if pd.isna(dt):
        return ""
    return dt.strftime("%Y-%m-%d")


def _eodhd_payload_to_frame(payload: object) -> pd.DataFrame:
    if payload is None:
        return pd.DataFrame()
    if isinstance(payload, dict):
        error = payload.get("message") or payload.get("error")
        if error:
            raise ValueError(f"EODHD error: {error}")
        if isinstance(payload.get("data"), list):
            payload = payload["data"]
    if isinstance(payload, list):
        return pd.DataFrame(payload)
    return pd.DataFrame()


def _fetch_daily_eodhd(
    market: str,
    symbol: str,
    start_date: str,
    end_date: str,
    client,
    data_cfg: Mapping,
) -> pd.DataFrame:
    eod_cfg = _resolve_eodhd_config(data_cfg, client)
    api_token = eod_cfg.get("api_token")
    if not api_token:
        raise ValueError("EODHD api_token is required (set data.eodhd.api_token or EODHD_API_TOKEN).")
    eod_symbol = _to_eodhd_symbol(market, symbol, eod_cfg)
    fmt = str(eod_cfg.get("fmt", "json")).strip().lower()
    params = {
        "api_token": api_token,
        "fmt": fmt,
        "period": eod_cfg.get("period", "d"),
        "order": eod_cfg.get("order", "a"),
        "from": _eodhd_format_date(start_date) if start_date else None,
        "to": _eodhd_format_date(end_date) if end_date else None,
    }
    url = _eodhd_build_url(eod_cfg["base_url"], f"eod/{eod_symbol}", params)
    payload_text = _eodhd_request_text(url, float(eod_cfg.get("timeout", 30)))
    if fmt == "json":
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"EODHD response is not valid JSON: {exc}") from exc
        df = _eodhd_payload_to_frame(payload)
    else:
        df = pd.read_csv(io.StringIO(payload_text))
    if df.empty:
        return df
    date_col = None
    if "date" in df.columns:
        date_col = "date"
    else:
        columns = {col.lower(): col for col in df.columns}
        date_col = columns.get("date")
    if date_col:
        df = df.copy()
        df["trade_date"] = pd.to_datetime(df[date_col], errors="coerce").dt.strftime("%Y%m%d")
        df = df[df["trade_date"].notna()].copy()
    return df


def _eodhd_code_to_internal_symbol(market: str, code: str) -> str:
    text = str(code or "").strip().upper()
    if not text:
        return text
    if normalize_market(market) == "hk":
        if text.endswith(".HK"):
            text = text[:-3]
        if text.isdigit():
            text = text.zfill(5)
        return f"{text}.HK"
    return text


def _ensure_basic_symbol_aliases(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or "symbol" not in df.columns:
        return df
    out = df.copy()
    if "ts_code" not in out.columns:
        out["ts_code"] = out["symbol"]
    if "stock_ticker" not in out.columns:
        out["stock_ticker"] = out["symbol"]
    return out


def _load_basic_eodhd(
    market: str,
    symbols: Optional[Iterable[str]],
    client,
    data_cfg: Mapping,
) -> pd.DataFrame:
    eod_cfg = _resolve_eodhd_config(data_cfg, client)
    api_token = eod_cfg.get("api_token")
    if not api_token:
        raise ValueError("EODHD api_token is required (set data.eodhd.api_token or EODHD_API_TOKEN).")
    exchange = eod_cfg.get("exchange") or ("HK" if normalize_market(market) == "hk" else None)
    if not exchange:
        raise ValueError("EODHD exchange code is required for basic data.")
    fmt = str(eod_cfg.get("fmt", "json")).strip().lower()
    params = {
        "api_token": api_token,
        "fmt": fmt,
    }
    url = _eodhd_build_url(eod_cfg["base_url"], f"exchange-symbol-list/{exchange}", params)
    payload_text = _eodhd_request_text(url, float(eod_cfg.get("timeout", 30)))
    if fmt == "json":
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"EODHD response is not valid JSON: {exc}") from exc
        df = _eodhd_payload_to_frame(payload)
    else:
        df = pd.read_csv(io.StringIO(payload_text))
    if df.empty:
        return df
    columns = {col.lower(): col for col in df.columns}
    code_col = columns.get("code")
    name_col = columns.get("name")
    if not code_col:
        return pd.DataFrame()
    df_basic = pd.DataFrame()
    df_basic["symbol"] = df[code_col].map(lambda c: _eodhd_code_to_internal_symbol(market, c))
    if name_col:
        df_basic["name"] = df[name_col]
    if symbols:
        df_basic = df_basic[df_basic["symbol"].isin(list(symbols))].copy()
    return _ensure_basic_symbol_aliases(
        ensure_symbol_columns(
            df_basic,
            context="EODHD basic data",
            priority=PROVIDER_SYMBOL_PRIORITY,
        )
    )


def _load_basic_rqdata(
    market: str,
    symbols: Optional[Iterable[str]],
    client,
    data_cfg: Mapping,
) -> pd.DataFrame:
    local_basic = _load_basic_from_local_asset(symbols, data_cfg)
    if local_basic is not None:
        return local_basic
    if client is None:
        import rqdatac as client
    rq_cfg = data_cfg.get("rqdata") if isinstance(data_cfg, Mapping) else None
    if isinstance(rq_cfg, Mapping) and rq_cfg.get("market"):
        rq_market = normalize_market(rq_cfg.get("market"))
    else:
        rq_market = normalize_market(market)

    symbol_map = {}
    order_book_ids = None
    if symbols:
        order_book_ids = []
        for sym in symbols:
            rq_sym = _to_rqdata_symbol(rq_market, sym)
            order_book_ids.append(rq_sym)
            symbol_map[rq_sym] = sym

    if order_book_ids:
        instruments = client.instruments(order_book_ids, market=rq_market)
        if not isinstance(instruments, list):
            instruments = [instruments]
        rows = []
        for ins in instruments:
            if ins is None:
                continue
            order_book_id = getattr(ins, "order_book_id", None)
            rows.append(
                {
                    "symbol": symbol_map.get(order_book_id, order_book_id),
                    "name": getattr(ins, "symbol", None),
                    "list_date": getattr(ins, "listed_date", None),
                }
            )
        df_basic = pd.DataFrame(rows)
        if "list_date" in df_basic.columns:
            df_basic["list_date"] = pd.to_datetime(df_basic["list_date"], errors="coerce").dt.strftime("%Y%m%d")
        return _ensure_basic_symbol_aliases(
            ensure_symbol_columns(
                df_basic,
                context="RQData basic data",
                priority=PROVIDER_SYMBOL_PRIORITY,
            )
        )

    df_basic = client.all_instruments("CS", market=rq_market)
    if df_basic is None or df_basic.empty:
        return df_basic
    df_basic = df_basic.copy()
    if "order_book_id" in df_basic.columns:
        df_basic["symbol"] = df_basic["order_book_id"]
    if "listed_date" in df_basic.columns:
        df_basic["list_date"] = df_basic["listed_date"]
    if "symbol" in df_basic.columns and "name" not in df_basic.columns:
        df_basic["name"] = df_basic["symbol"]
    df_basic = ensure_symbol_columns(
        df_basic,
        context="RQData all instruments",
        priority=PROVIDER_SYMBOL_PRIORITY,
    )
    df_basic = _ensure_basic_symbol_aliases(df_basic)
    df_basic = df_basic[["symbol", "name", "list_date", "ts_code", "stock_ticker"]].copy()
    if "list_date" in df_basic.columns:
        df_basic["list_date"] = pd.to_datetime(df_basic["list_date"], errors="coerce").dt.strftime("%Y%m%d")
    return df_basic


def _merge_column_map(market: str, data_cfg: Mapping) -> dict[str, str]:
    merged = dict(DEFAULT_COLUMN_MAPS.get(market, {}))
    cfg_map = data_cfg.get("column_map") if isinstance(data_cfg, Mapping) else None
    if isinstance(cfg_map, Mapping):
        for key, value in cfg_map.items():
            if value:
                merged[normalize_symbol_standard_name(key)] = str(value)
    return merged


def _apply_column_map(df: pd.DataFrame, column_map: Mapping[str, str]) -> pd.DataFrame:
    rename_map = {}
    for standard, source in column_map.items():
        normalized_standard = normalize_symbol_standard_name(standard)
        if (
            source in df.columns
            and normalized_standard != source
            and normalized_standard not in df.columns
        ):
            rename_map[source] = normalized_standard
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def _infer_missing_columns(df: pd.DataFrame) -> pd.DataFrame:
    for standard, candidates in COLUMN_CANDIDATES.items():
        if standard in df.columns:
            continue
        for candidate in candidates:
            if candidate in df.columns:
                df = df.rename(columns={candidate: standard})
                break
    return df


def _infer_fundamental_columns(df: pd.DataFrame) -> pd.DataFrame:
    for standard, candidates in FUNDAMENTAL_COLUMN_CANDIDATES.items():
        if standard in df.columns:
            continue
        for candidate in candidates:
            if candidate in df.columns:
                df = df.rename(columns={candidate: standard})
                break
    return df


def _standardize_fundamentals_frame(
    df: pd.DataFrame,
    column_map: Mapping[str, str],
    symbol: str,
) -> pd.DataFrame:
    df = _apply_column_map(df, column_map)
    df = _infer_fundamental_columns(df)
    if "symbol" not in df.columns:
        df = df.copy()
        df["symbol"] = symbol
    df = ensure_symbol_columns(
        df,
        context="Fundamentals data",
        priority=PROVIDER_SYMBOL_PRIORITY,
    )
    if "ts_code" not in df.columns:
        df = df.copy()
        df["ts_code"] = df["symbol"]
    missing = [col for col in FUNDAMENTAL_REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Fundamentals data missing required columns: {missing}")
    return df


def _standardize_daily_frame(
    df: pd.DataFrame,
    market: str,
    data_cfg: Mapping,
    symbol: str,
) -> pd.DataFrame:
    df = _apply_column_map(df, _merge_column_map(market, data_cfg))
    df = _infer_missing_columns(df)
    if "ts_code" not in df.columns and "symbol" in df.columns and "order_book_id" in df.columns:
        df = df.copy()
        df["ts_code"] = df["symbol"]
    if "symbol" not in df.columns:
        df = df.copy()
        df["symbol"] = symbol
    df = ensure_symbol_columns(
        df,
        context="Daily data",
        priority=PROVIDER_SYMBOL_PRIORITY,
    )
    missing = [col for col in REQUIRED_DAILY_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Daily data missing required columns: {missing}")
    return df


def _resolve_local_path(path_text: object, *, label: str) -> Path | None:
    if path_text in {None, ""}:
        return None
    path = Path(str(path_text)).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    else:
        path = path.resolve()
    if not path.exists():
        raise SystemExit(f"{label} not found: {path}")
    return path


def _resolve_local_daily_asset_dir(data_cfg: Mapping | None) -> Path | None:
    if not isinstance(data_cfg, Mapping):
        return None
    rq_cfg = data_cfg.get("rqdata")
    candidates = []
    if isinstance(rq_cfg, Mapping):
        candidates.extend([rq_cfg.get("daily_asset_dir"), rq_cfg.get("asset_dir")])
    candidates.extend([data_cfg.get("daily_asset_dir"), data_cfg.get("asset_dir")])
    for candidate in candidates:
        root = _resolve_local_path(candidate, label="Local RQData daily asset path") if candidate else None
        if root is None:
            continue
        if (root / "data").exists():
            return root
        if root.name == "data" and root.is_dir():
            return root.parent
        raise SystemExit(f"Local RQData daily asset directory is missing data/: {root}")
    return None


def _resolve_local_instruments_file(data_cfg: Mapping | None) -> Path | None:
    if not isinstance(data_cfg, Mapping):
        return None
    rq_cfg = data_cfg.get("rqdata")
    candidates = []
    if isinstance(rq_cfg, Mapping):
        candidates.extend([rq_cfg.get("instruments_file"), rq_cfg.get("basic_file")])
    candidates.extend([data_cfg.get("instruments_file"), data_cfg.get("basic_file")])
    for candidate in candidates:
        resolved = _resolve_local_path(candidate, label="Local RQData instruments file") if candidate else None
        if resolved is not None:
            return resolved
    return None


def _resolve_local_reference_asset_dir(
    data_cfg: Mapping | None,
    dataset_name: str,
) -> Path | None:
    if not isinstance(data_cfg, Mapping):
        return None
    rq_cfg = data_cfg.get("rqdata")
    key = f"{str(dataset_name).strip()}_dir"
    candidates = []
    if isinstance(rq_cfg, Mapping):
        candidates.append(rq_cfg.get(key))
    candidates.append(data_cfg.get(key))
    for candidate in candidates:
        root = (
            _resolve_local_path(
                candidate,
                label=f"Local RQData {dataset_name} asset path",
            )
            if candidate
            else None
        )
        if root is None:
            continue
        if (root / "data").exists():
            return root
        if root.name == "data" and root.is_dir():
            return root.parent
        raise SystemExit(f"Local RQData {dataset_name} asset directory is missing data/: {root}")
    return None


def has_local_rqdata_assets(data_cfg: Mapping | None) -> bool:
    return (
        _resolve_local_daily_asset_dir(data_cfg) is not None
        and _resolve_local_instruments_file(data_cfg) is not None
    )


def _read_local_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    raise SystemExit(f"Unsupported local asset file type: {path}")


def _normalize_reference_date_frame(
    frame: pd.DataFrame,
    *,
    date_col: str,
) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=[date_col])
    work = frame.copy()
    if date_col not in work.columns:
        if isinstance(work.index, pd.MultiIndex) and date_col in work.index.names:
            work = work.reset_index()
        elif work.index.name == date_col:
            work = work.reset_index()
    if date_col not in work.columns:
        return pd.DataFrame(columns=[date_col])
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
    work = work[work[date_col].notna()].copy()
    return work


def _load_local_ex_factors_frame(symbol: str, data_cfg: Mapping | None) -> pd.DataFrame | None:
    asset_dir = _resolve_local_reference_asset_dir(data_cfg, "ex_factors")
    if asset_dir is None:
        return None
    asset_path = asset_dir / "data" / f"{symbol}.parquet"
    if not asset_path.exists():
        return pd.DataFrame(columns=["ex_date", "ex_cum_factor"])
    frame = _normalize_reference_date_frame(pd.read_parquet(asset_path), date_col="ex_date")
    if frame.empty:
        return pd.DataFrame(columns=["ex_date", "ex_cum_factor"])
    if "ex_cum_factor" not in frame.columns:
        if "ex_factor" not in frame.columns:
            return pd.DataFrame(columns=["ex_date", "ex_cum_factor"])
        frame["ex_cum_factor"] = pd.to_numeric(frame["ex_factor"], errors="coerce").cumprod()
    frame["ex_cum_factor"] = pd.to_numeric(frame["ex_cum_factor"], errors="coerce")
    frame = frame[
        frame["ex_cum_factor"].notna() & np.isfinite(frame["ex_cum_factor"]) & (frame["ex_cum_factor"] > 0)
    ][["ex_date", "ex_cum_factor"]].copy()
    if frame.empty:
        return pd.DataFrame(columns=["ex_date", "ex_cum_factor"])
    frame = frame.sort_values("ex_date").drop_duplicates(subset=["ex_date"], keep="last")
    return frame.reset_index(drop=True)


def _rqdata_adjust_type(data_cfg: Mapping | None) -> str | None:
    if not isinstance(data_cfg, Mapping):
        return None
    rq_cfg = data_cfg.get("rqdata")
    if not isinstance(rq_cfg, Mapping) or "adjust_type" not in rq_cfg:
        return None
    value = str(rq_cfg.get("adjust_type") or "").strip().lower()
    return value or None


def _build_tr_close_series(
    frame: pd.DataFrame,
    *,
    symbol: str,
    data_cfg: Mapping | None,
) -> pd.Series | None:
    if frame is None or frame.empty or "close" not in frame.columns or "trade_date" not in frame.columns:
        return None
    close = pd.to_numeric(frame["close"], errors="coerce")
    trade_dates = pd.to_datetime(frame["trade_date"], errors="coerce")

    ex_factors = _load_local_ex_factors_frame(symbol, data_cfg)
    if ex_factors is not None:
        if ex_factors.empty:
            return close.rename("tr_close")
        ex_dates = ex_factors["ex_date"].to_numpy(dtype="datetime64[ns]")
        trade_values = trade_dates.to_numpy(dtype="datetime64[ns]")
        ex_cum_values = ex_factors["ex_cum_factor"].to_numpy(dtype=float)
        idx = np.searchsorted(ex_dates, trade_values, side="right") - 1
        period_cum = np.ones(len(frame), dtype=float)
        valid_idx = idx >= 0
        period_cum[valid_idx] = ex_cum_values[idx[valid_idx]]
        tr_close = close * pd.Series(period_cum, index=frame.index, dtype=float)
        tr_close = tr_close.where(trade_dates.notna())
        tr_close.name = "tr_close"
        return tr_close

    adjust_type = _rqdata_adjust_type(data_cfg)
    if adjust_type in {"pre", "post", "pre_volume", "post_volume"}:
        return close.rename("tr_close")
    return None


def _augment_daily_frame(
    df: pd.DataFrame,
    *,
    market: str,
    symbol: str,
    data_cfg: Mapping | None,
) -> tuple[pd.DataFrame, bool]:
    if df is None or df.empty:
        return df, False
    out = df.copy()
    changed = False

    tr_close = _build_tr_close_series(out, symbol=symbol, data_cfg=data_cfg)
    if tr_close is not None:
        existing = out["tr_close"].copy() if "tr_close" in out.columns else None
        if existing is None or not existing.equals(tr_close):
            out["tr_close"] = tr_close
            changed = True

    return out, changed


def _load_daily_from_local_asset(
    market: str,
    symbol: str,
    start_date: str,
    end_date: str,
    data_cfg: Mapping,
) -> pd.DataFrame | None:
    asset_dir = _resolve_local_daily_asset_dir(data_cfg)
    if asset_dir is None:
        return None
    asset_path = asset_dir / "data" / f"{symbol}.parquet"
    if not asset_path.exists():
        return pd.DataFrame()
    frame = pd.read_parquet(asset_path)
    if frame is None or frame.empty:
        return pd.DataFrame()
    frame = _standardize_daily_frame(frame, market, data_cfg, symbol)
    frame = _ensure_trade_date_str(frame)
    if frame is None or frame.empty:
        return pd.DataFrame()
    mask = (frame["trade_date"] >= str(start_date)) & (frame["trade_date"] <= str(end_date))
    return frame.loc[mask].copy()


def _load_basic_from_local_asset(
    symbols: Optional[Iterable[str]],
    data_cfg: Mapping,
) -> pd.DataFrame | None:
    instruments_file = _resolve_local_instruments_file(data_cfg)
    if instruments_file is None:
        return None
    work = _read_local_table(instruments_file)
    if work is None or work.empty:
        return pd.DataFrame()
    work = work.copy()
    if "name" not in work.columns:
        for candidate in ("symbol", "eng_symbol", "abbrev_symbol", "order_book_id", "ts_code"):
            if candidate in work.columns:
                work["name"] = work[candidate]
                break
    if "order_book_id" in work.columns and "symbol" not in work.columns and "ts_code" not in work.columns:
        work["symbol"] = work["order_book_id"]
    if "listed_date" in work.columns and "list_date" not in work.columns:
        work["list_date"] = work["listed_date"]
    work = ensure_symbol_columns(
        work,
        context="Local RQData instruments file",
        priority=PROVIDER_SYMBOL_PRIORITY,
    )
    work = _ensure_basic_symbol_aliases(work)
    required = ["symbol", "name", "list_date"]
    missing = [column for column in required if column not in work.columns]
    if missing:
        raise SystemExit(
            f"Local RQData instruments file is missing required columns {missing}: {instruments_file}"
        )
    work = work[["symbol", "name", "list_date", "ts_code", "stock_ticker"]].copy()
    work["symbol"] = work["symbol"].astype(str).str.strip()
    work["list_date"] = pd.to_datetime(work["list_date"], errors="coerce").dt.strftime("%Y%m%d")
    if symbols:
        work = work[work["symbol"].isin(list(symbols))].copy()
    return work.reset_index(drop=True)


def _resolve_endpoint_name(
    market: str,
    data_cfg: Mapping,
    key: str,
    defaults: Mapping[str, str],
) -> Optional[str]:
    if isinstance(data_cfg, Mapping) and data_cfg.get(key):
        return str(data_cfg.get(key)).strip()
    return defaults.get(market)


def _resolve_endpoint_params(
    data_cfg: Mapping,
    params_key: str,
    default_params: Optional[Mapping[str, object]] = None,
) -> dict:
    params = dict(default_params or {})
    cfg_params = data_cfg.get(params_key) if isinstance(data_cfg, Mapping) else None
    if isinstance(cfg_params, Mapping):
        params.update(cfg_params)
    return params


def _fetch_daily_from_provider(
    provider: str,
    market: str,
    symbol: str,
    start_date: str,
    end_date: str,
    client,
    data_cfg: Mapping,
) -> pd.DataFrame:
    local_frame = _load_daily_from_local_asset(market, symbol, start_date, end_date, data_cfg)
    if local_frame is not None:
        return local_frame
    if provider == "rqdata":
        df = _fetch_daily_rqdata(market, symbol, start_date, end_date, client, data_cfg)
    elif provider == "tushare":
        endpoint_name = _resolve_endpoint_name(market, data_cfg, "daily_endpoint", DEFAULT_DAILY_ENDPOINTS)
        if not endpoint_name:
            raise ValueError(f"No daily endpoint configured for market '{market}'.")
        if client is None:
            raise ValueError("Tushare client is required for provider='tushare'.")
        endpoint = getattr(client, endpoint_name, None)
        if endpoint is None:
            raise ValueError(f"Tushare endpoint '{endpoint_name}' not found for market '{market}'.")

        params = {}
        symbol_param = data_cfg.get("daily_symbol_param", "ts_code")
        start_param = data_cfg.get("daily_start_param", "start_date")
        end_param = data_cfg.get("daily_end_param", "end_date")
        if symbol_param:
            params[str(symbol_param)] = symbol
        if start_param:
            params[str(start_param)] = start_date
        if end_param:
            params[str(end_param)] = end_date

        params.update(_resolve_endpoint_params(data_cfg, "daily_params"))

        fields = data_cfg.get("daily_fields") if isinstance(data_cfg, Mapping) else None
        if fields:
            params["fields"] = fields

        df = endpoint(**params)
    elif provider == "eodhd":
        df = _fetch_daily_eodhd(market, symbol, start_date, end_date, client, data_cfg)
    else:
        raise ValueError(f"Unsupported data provider '{provider}'.")
    if df is None or df.empty:
        return df
    return _standardize_daily_frame(df, market, data_cfg, symbol)


def fetch_daily(
    market: str,
    symbol: str,
    start_date: str,
    end_date: str,
    cache_dir: Path,
    client,
    data_cfg: Optional[Mapping] = None,
) -> pd.DataFrame:
    market = normalize_market(market)
    data_cfg = data_cfg or {}
    provider = resolve_provider(data_cfg)
    start_date = str(start_date).strip()
    end_date = str(end_date).strip()
    tag = _cache_tag(data_cfg)
    prefix = f"{market}_{provider}"
    if tag:
        prefix = f"{prefix}_{tag}"
    cache_mode = str(
        data_cfg.get("daily_cache_mode", data_cfg.get("cache_mode", "symbol"))
    ).strip().lower()
    if cache_mode in {"range", "window"}:
        cache_file = cache_dir / f"{prefix}_daily_{symbol}_{start_date}_{end_date}.parquet"
        if cache_file.exists():
            cached = pd.read_parquet(cache_file)
            if cached is None or cached.empty:
                return cached
            cached = ensure_symbol_columns(
                cached,
                context="Cached daily data",
                priority=PROVIDER_SYMBOL_PRIORITY,
            )
            cached, cache_changed = _augment_daily_frame(
                cached,
                market=market,
                symbol=symbol,
                data_cfg=data_cfg,
            )
            if cache_changed:
                cached = cached.copy(deep=True)
                cached.to_parquet(cache_file)
            return cached
        df = _fetch_daily_from_provider(provider, market, symbol, start_date, end_date, client, data_cfg)
        if df is None or df.empty:
            return df
        df, _ = _augment_daily_frame(
            df,
            market=market,
            symbol=symbol,
            data_cfg=data_cfg,
        )
        # Ensure buffers are writable before parquet serialization.
        df = df.copy(deep=True)
        df.to_parquet(cache_file)
        return df

    cache_file = cache_dir / f"{prefix}_daily_{symbol}.parquet"
    cached = None
    trade_dates = []
    if cache_file.exists():
        cached = pd.read_parquet(cache_file)
        cached = _ensure_trade_date_str(cached)
        if cached is not None and not cached.empty:
            cached = ensure_symbol_columns(
                cached,
                context="Cached daily data",
                priority=PROVIDER_SYMBOL_PRIORITY,
            )
        if cached is not None and not cached.empty and "trade_date" in cached.columns:
            trade_dates = sorted(cached["trade_date"].unique().tolist())
            if not trade_dates:
                cached = None

    refresh_days = int(data_cfg.get("cache_refresh_days", 0) or 0)
    refresh_days = max(0, refresh_days)
    refresh_on_hit = bool(data_cfg.get("cache_refresh_on_hit", False))

    fetch_ranges: list[tuple[str, str]] = []
    if cached is None or cached.empty or not trade_dates:
        fetch_ranges.append((start_date, end_date))
    else:
        cached_min, cached_max = trade_dates[0], trade_dates[-1]
        if start_date < cached_min and not _is_small_leading_calendar_gap(start_date, cached_min):
            left_end = min(end_date, cached_min)
            if start_date <= left_end:
                fetch_ranges.append((start_date, left_end))
        if end_date > cached_max:
            refresh_start = cached_max
            if refresh_days > 0:
                idx = max(0, len(trade_dates) - refresh_days)
                refresh_start = trade_dates[idx]
            if refresh_start < start_date:
                refresh_start = start_date
            fetch_ranges.append((refresh_start, end_date))
        elif refresh_on_hit and refresh_days > 0 and end_date >= cached_min:
            idx = max(0, len(trade_dates) - refresh_days)
            refresh_start = trade_dates[idx]
            if refresh_start < start_date:
                refresh_start = start_date
            if refresh_start <= end_date:
                fetch_ranges.append((refresh_start, end_date))

    new_frames: list[pd.DataFrame] = []
    for fetch_start, fetch_end in fetch_ranges:
        if fetch_start > fetch_end:
            continue
        df_new = _fetch_daily_from_provider(
            provider, market, symbol, fetch_start, fetch_end, client, data_cfg
        )
        if df_new is None or df_new.empty:
            continue
        df_new = _ensure_trade_date_str(df_new)
        if df_new is not None and not df_new.empty:
            new_frames.append(df_new)

    if cached is None or cached.empty:
        if not new_frames:
            return pd.DataFrame()
        merged = pd.concat(new_frames, ignore_index=True) if len(new_frames) > 1 else new_frames[0]
        updated = True
    else:
        if new_frames:
            merged = pd.concat([cached] + new_frames, ignore_index=True)
            updated = True
        else:
            merged = cached
            updated = False

    merged = _ensure_trade_date_str(merged)
    if merged is None or merged.empty:
        return pd.DataFrame()
    merged = ensure_symbol_columns(
        merged,
        context="Daily data",
        priority=PROVIDER_SYMBOL_PRIORITY,
    )
    merged, augment_changed = _augment_daily_frame(
        merged,
        market=market,
        symbol=symbol,
        data_cfg=data_cfg,
    )

    if updated or augment_changed:
        merged = merged.drop_duplicates(subset=["symbol", "trade_date"], keep="last")
        merged.sort_values(["symbol", "trade_date"], inplace=True)
        # Ensure buffers are writable before parquet serialization.
        merged = merged.copy(deep=True)
        merged.to_parquet(cache_file)

    mask = (merged["trade_date"] >= start_date) & (merged["trade_date"] <= end_date)
    return merged.loc[mask].copy()


def load_basic(
    market: str,
    cache_dir: Path,
    client,
    data_cfg: Optional[Mapping] = None,
    symbols: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    market = normalize_market(market)
    data_cfg = data_cfg or {}
    provider = resolve_provider(data_cfg)
    tag = _cache_tag(data_cfg)
    cache_file = _basic_cache_file(cache_dir, market, provider, symbols, tag=tag)
    if cache_file.exists():
        cached = pd.read_parquet(cache_file)
        if cached is None or cached.empty:
            return cached
        return ensure_symbol_columns(
            cached,
            context="Cached basic data",
            priority=PROVIDER_SYMBOL_PRIORITY,
        )

    if provider == "rqdata":
        df_basic = _load_basic_rqdata(market, symbols, client, data_cfg)
    elif provider == "tushare":
        endpoint_name = _resolve_endpoint_name(market, data_cfg, "basic_endpoint", DEFAULT_BASIC_ENDPOINTS)
        if not endpoint_name:
            raise ValueError(f"No basic endpoint configured for market '{market}'.")
        if client is None:
            raise ValueError("Tushare client is required for provider='tushare'.")
        endpoint = getattr(client, endpoint_name, None)
        if endpoint is None:
            raise ValueError(f"Tushare endpoint '{endpoint_name}' not found for market '{market}'.")

        params = _resolve_endpoint_params(data_cfg, "basic_params", DEFAULT_BASIC_PARAMS.get(market))
        fields = data_cfg.get("basic_fields") or DEFAULT_BASIC_FIELDS.get(market)
        if fields:
            params["fields"] = fields

        df_basic = endpoint(**params)
    elif provider == "eodhd":
        df_basic = _load_basic_eodhd(market, symbols, client, data_cfg)
    else:
        raise ValueError(f"Unsupported data provider '{provider}'.")

    if df_basic is None or df_basic.empty:
        return df_basic
    df_basic = ensure_symbol_columns(
        df_basic,
        context="Basic data",
        priority=PROVIDER_SYMBOL_PRIORITY,
    )

    if symbols:
        if "symbol" in df_basic.columns:
            df_basic = df_basic[df_basic["symbol"].isin(list(symbols))].copy()

    # Ensure buffers are writable before parquet serialization.
    df_basic = df_basic.copy(deep=True)
    df_basic.to_parquet(cache_file)
    return df_basic


def fetch_fundamentals(
    market: str,
    symbol: str,
    start_date: str,
    end_date: str,
    cache_dir: Path,
    client,
    data_cfg: Optional[Mapping] = None,
    fundamentals_cfg: Optional[Mapping] = None,
) -> pd.DataFrame:
    market = normalize_market(market)
    data_cfg = data_cfg or {}
    fundamentals_cfg = fundamentals_cfg or {}
    provider = resolve_provider({"provider": fundamentals_cfg.get("provider")}) if fundamentals_cfg.get("provider") else resolve_provider(data_cfg)
    tag = _sanitize_cache_tag(
        fundamentals_cfg.get("cache_tag")
        or fundamentals_cfg.get("cache_version")
        or _cache_tag(data_cfg)
    )
    cache_file = _fundamentals_cache_file(
        cache_dir,
        market,
        provider,
        symbol,
        start_date,
        end_date,
        tag,
        fundamentals_cfg,
    )
    if cache_file.exists():
        cached = pd.read_parquet(cache_file)
        if cached is None or cached.empty:
            return cached
        cached = ensure_symbol_columns(
            cached,
            context="Cached fundamentals data",
            priority=PROVIDER_SYMBOL_PRIORITY,
        )
        if "ts_code" not in cached.columns:
            cached = cached.copy()
            cached["ts_code"] = cached["symbol"]
        return cached

    if provider == "rqdata":
        if market != "hk":
            raise ValueError(
                "RQData fundamentals provider currently supports only market='hk'."
            )
        if client is None:
            import rqdatac as client

        endpoint_name = str(fundamentals_cfg.get("endpoint") or "get_factor").strip()
        if endpoint_name != "get_factor":
            raise ValueError(
                "RQData fundamentals provider currently supports only endpoint='get_factor'."
            )
        rq_cfg = data_cfg.get("rqdata") if isinstance(data_cfg, Mapping) else None
        rq_market = (
            normalize_market(rq_cfg.get("market"))
            if isinstance(rq_cfg, Mapping) and rq_cfg.get("market")
            else market
        )
        factor_fields = _rqdata_fundamental_fields(fundamentals_cfg)
        params = dict(fundamentals_cfg.get("params") or {})
        params["market"] = rq_market
        rq_symbol = _to_rqdata_symbol(rq_market, symbol)
        df = client.get_factor(rq_symbol, factor_fields, start_date, end_date, **params)
        if df is None or df.empty:
            return df
        column_map = fundamentals_cfg.get("column_map") or {}
        df = _prepare_rqdata_fundamentals_frame(df, symbol)
        df = _standardize_fundamentals_frame(df, column_map, symbol)
        df = df.copy(deep=True)
        df.to_parquet(cache_file)
        return df

    if provider != "tushare":
        raise ValueError(
            "Fundamentals provider not supported (use fundamentals.source=file, provider=tushare, or provider=rqdata with market=hk)."
        )
    endpoint_name = fundamentals_cfg.get("endpoint") or data_cfg.get("fundamentals_endpoint")
    if not endpoint_name:
        raise ValueError("Fundamentals endpoint is required (fundamentals.endpoint).")
    if client is None:
        raise ValueError("Tushare client is required for fundamentals.")
    endpoint = getattr(client, endpoint_name, None)
    if endpoint is None:
        raise ValueError(f"Tushare endpoint '{endpoint_name}' not found.")

    params = {}
    symbol_param = fundamentals_cfg.get("symbol_param", "ts_code")
    start_param = fundamentals_cfg.get("start_param", "start_date")
    end_param = fundamentals_cfg.get("end_param", "end_date")
    if symbol_param:
        params[str(symbol_param)] = symbol
    if start_param:
        params[str(start_param)] = start_date
    if end_param:
        params[str(end_param)] = end_date

    params.update(fundamentals_cfg.get("params") or {})

    fields = fundamentals_cfg.get("fields")
    if fields:
        params["fields"] = fields

    df = endpoint(**params)
    if df is None or df.empty:
        return df

    column_map = fundamentals_cfg.get("column_map") or {}
    df = _standardize_fundamentals_frame(df, column_map, symbol)
    df = ensure_symbol_columns(
        df,
        context="Fundamentals data",
        priority=PROVIDER_SYMBOL_PRIORITY,
    )
    df = df.copy(deep=True)
    df.to_parquet(cache_file)
    return df
