from __future__ import annotations

import logging
import sys
from typing import Optional

import pandas as pd

logger = logging.getLogger("csml")

RELATIVE_DATE_TOKENS = {
    "today",
    "t-1",
    "last_trading_day",
    "last_completed_trading_day",
}


def normalize_date_token(value: object | None, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    lowered = text.lower()
    if lowered in {"today", "t", "now"}:
        return "today"
    if lowered in {"t-1", "yesterday"}:
        return "t-1"
    if lowered in {"last_trading_day", "last_completed_trading_day"}:
        return lowered
    return text


def is_relative_date_token(value: object | None, default: str = "today") -> bool:
    token = normalize_date_token(value, default=default)
    return token in RELATIVE_DATE_TOKENS


def _resolve_last_trading_date(
    as_of: pd.Timestamp,
    market: str,
    *,
    include_today: bool,
) -> Optional[pd.Timestamp]:
    try:
        import rqdatac
    except ImportError:
        return None

    as_of = pd.to_datetime(as_of).normalize()
    lookbacks = [366, 365 * 5]
    for days in lookbacks:
        start = (as_of - pd.Timedelta(days=days)).strftime("%Y%m%d")
        end = as_of.strftime("%Y%m%d")
        try:
            dates = rqdatac.get_trading_dates(start, end, market=market)
        except Exception:
            continue
        if not dates:
            continue
        candidates = [d.normalize() for d in pd.to_datetime(dates)]
        if include_today:
            candidates = [d for d in candidates if d <= as_of]
        else:
            candidates = [d for d in candidates if d < as_of]
        if candidates:
            return max(candidates)
    return None


def resolve_date_token(
    value: object | None,
    default: str = "today",
    *,
    market: str | None = None,
    provider: str | None = None,
    warn_to_stderr: bool = False,
    warn_label: str | None = None,
) -> pd.Timestamp:
    token = normalize_date_token(value, default=default)
    today = pd.Timestamp.now().normalize()
    if token == "today":
        return today
    if token in {"last_trading_day", "last_completed_trading_day"}:
        include_today = token == "last_trading_day"
        if provider == "rqdata" and market:
            resolved = _resolve_last_trading_date(today, market, include_today=include_today)
            if resolved is not None:
                return resolved
        if warn_to_stderr:
            if warn_label:
                print(
                    f"Warning: {warn_label}={token} uses calendar day fallback (no trading calendar).",
                    file=sys.stderr,
                )
            else:
                print(
                    f"Warning: {token} uses calendar day fallback (no trading calendar).",
                    file=sys.stderr,
                )
        logger.warning(
            "Token '%s' requested but trading calendar unavailable; falling back to calendar day.",
            token,
        )
        return today if include_today else today - pd.Timedelta(days=1)
    if token == "t-1":
        return today - pd.Timedelta(days=1)
    text = str(token).strip()
    compact = text.replace("-", "")
    if compact.isdigit() and len(compact) == 8:
        parsed = pd.to_datetime(compact, format="%Y%m%d", errors="coerce")
    else:
        parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        raise SystemExit(f"Invalid date token: {value}")
    return pd.Timestamp(parsed).normalize()
