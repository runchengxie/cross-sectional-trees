"""Provider and market boundary helpers for the supported HK/RQData workflow."""

from __future__ import annotations

from typing import Mapping, Optional

SUPPORTED_MARKETS = {"hk"}


def normalize_market(market: Optional[str], *, default: Optional[str] = "hk") -> Optional[str]:
    fallback = None if default is None else str(default).strip().lower() or None
    value = str(market).strip().lower() if market is not None else None
    return value or fallback


def resolve_provider(
    data_cfg: Optional[Mapping], *, default: Optional[str] = "rqdata"
) -> Optional[str]:
    if not isinstance(data_cfg, Mapping):
        return default
    raw = data_cfg.get("provider", default)
    if raw is None:
        return None
    value = str(raw).strip().lower()
    if value in {"rqdatac", "rqdata"}:
        return "rqdata"
    return value or default


def fundamentals_provider_supported(provider: str, market: str) -> bool:
    provider = resolve_provider({"provider": provider}, default="rqdata")
    market = normalize_market(market)
    return provider == "rqdata" and market == "hk"


def require_supported_market(market: str) -> str:
    market = normalize_market(market)
    if market not in SUPPORTED_MARKETS:
        raise ValueError(
            f"Unsupported market '{market}'. This project currently supports only market='hk'."
        )
    return market


def hk_to_rqdata_symbol(symbol: str) -> str:
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


def to_rqdata_symbol(market: str, symbol: str) -> str:
    require_supported_market(market)
    return hk_to_rqdata_symbol(symbol)
