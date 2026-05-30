"""Data interface to decouple provider wiring from research logic."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, Optional

import pandas as pd
from market_data_platform.data_provider_contracts import require_supported_market
from market_data_platform.data_providers import (
    fetch_daily,
    fetch_fundamentals,
    has_local_rqdata_assets,
    load_basic,
    normalize_market,
    resolve_provider,
)
from market_data_platform.rqdata_runtime import (
    init_rqdatac as _init_rqdatac_runtime,
    patch_rqdatac_adjust_price_readonly as _patch_rqdatac_adjust_price_readonly,
)

PLATFORM_ASSET_SOURCE_MODE = "platform_assets"
PROVIDER_ONLINE_SOURCE_MODE = "provider_online_legacy"
AUTO_SOURCE_MODE = "auto"
SUPPORTED_SOURCE_MODES = {
    AUTO_SOURCE_MODE,
    PLATFORM_ASSET_SOURCE_MODE,
    PROVIDER_ONLINE_SOURCE_MODE,
}


def _resolve_source_mode(data_cfg: Mapping) -> str:
    value = str(data_cfg.get("source_mode") or AUTO_SOURCE_MODE).strip().lower()
    if value in {"provider_online", "online_provider", "provider"}:
        return PROVIDER_ONLINE_SOURCE_MODE
    if value not in SUPPORTED_SOURCE_MODES:
        supported = ", ".join(sorted(SUPPORTED_SOURCE_MODES))
        raise SystemExit(f"data.source_mode must be one of: {supported}.")
    return value


@dataclass
class DataInterface:
    market: str
    data_cfg: Mapping
    cache_dir: Path
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("cstree"))
    provider: str = field(init=False)
    client: object = field(init=False, default=None)
    max_attempts: int = field(init=False)
    backoff_seconds: float = field(init=False)
    max_backoff_seconds: float = field(init=False)

    def __post_init__(self) -> None:
        try:
            self.market = require_supported_market(normalize_market(self.market))
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        self.data_cfg = self.data_cfg if isinstance(self.data_cfg, Mapping) else {}
        self.provider = resolve_provider(self.data_cfg)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        if self.provider != "rqdata":
            raise SystemExit(
                f"Unsupported data.provider '{self.provider}'. This project currently supports only provider='rqdata'."
            )

        retry_cfg = self.data_cfg.get("retry") if isinstance(self.data_cfg, Mapping) else None
        retry_cfg = retry_cfg if isinstance(retry_cfg, Mapping) else {}
        self.max_attempts = max(1, int(retry_cfg.get("max_attempts", 1)))
        self.backoff_seconds = float(retry_cfg.get("backoff_seconds", 0.5))
        self.max_backoff_seconds = float(retry_cfg.get("max_backoff_seconds", 5.0))

        self._init_client()

    def _init_client(self) -> None:
        source_mode = _resolve_source_mode(self.data_cfg)
        try:
            has_local_assets = has_local_rqdata_assets(self.data_cfg)
        except SystemExit as exc:
            if source_mode == PLATFORM_ASSET_SOURCE_MODE:
                raise SystemExit(
                    "data.source_mode=platform_assets requires local RQData daily and instruments "
                    "assets. Set DATA_PLATFORM_ROOT/HK_DATA_PLATFORM_ROOT to the market-data-platform "
                    "artifacts root, configure data.rqdata.daily_asset_dir and instruments_file, "
                    f"or explicitly opt into online provider reads with data.source_mode={PROVIDER_ONLINE_SOURCE_MODE}."
                ) from exc
            raise

        if has_local_assets:
            self.logger.info("Using local RQData daily/instruments assets; skipping rqdatac.init.")
            self.client = None
            return

        if source_mode == PLATFORM_ASSET_SOURCE_MODE:
            raise SystemExit(
                "data.source_mode=platform_assets requires local RQData daily and instruments "
                "assets. Set DATA_PLATFORM_ROOT/HK_DATA_PLATFORM_ROOT to the market-data-platform "
                "artifacts root, configure data.rqdata.daily_asset_dir and instruments_file, "
                f"or explicitly opt into online provider reads with data.source_mode={PROVIDER_ONLINE_SOURCE_MODE}."
            )

        self.client = _init_rqdatac_runtime(
            data_cfg=self.data_cfg,
            logger=self.logger,
            error_cls=SystemExit,
            import_error_message="rqdatac is required for provider='rqdata'.",
            patch_fn=_patch_rqdatac_adjust_price_readonly,
        )

    def _with_retry(
        self,
        label: str,
        action: Callable[[], pd.DataFrame],
        *,
        log_failures: bool = True,
        log_traceback: bool = True,
    ) -> pd.DataFrame:
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return action()
            except Exception as exc:
                last_exc = exc
                if log_failures:
                    self.logger.warning(
                        "%s (attempt %s/%s): %s",
                        label,
                        attempt,
                        self.max_attempts,
                        exc,
                        exc_info=log_traceback,
                    )
                if attempt < self.max_attempts:
                    sleep_for = min(
                        self.backoff_seconds * (2 ** (attempt - 1)),
                        self.max_backoff_seconds,
                    )
                    time.sleep(sleep_for)
        if last_exc is not None:
            raise last_exc
        return pd.DataFrame()

    def fetch_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        label = f"Daily data load failed for {symbol}"

        def _load() -> pd.DataFrame:
            return fetch_daily(
                self.market,
                symbol,
                start_date,
                end_date,
                self.cache_dir,
                self.client,
                self.data_cfg,
            )

        return self._with_retry(label, _load)

    def load_basic(self, symbols: Optional[list[str]] = None) -> pd.DataFrame:
        return load_basic(
            self.market,
            self.cache_dir,
            self.client,
            self.data_cfg,
            symbols=symbols,
        )

    def fetch_fundamentals(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        fundamentals_cfg: Mapping,
        *,
        cache_dir: Optional[Path] = None,
        log_retry_failures: bool = True,
        log_retry_traceback: bool = True,
    ) -> pd.DataFrame:
        label = f"Fundamentals load failed for {symbol}"
        fund_cache_dir = cache_dir or self.cache_dir

        def _load() -> pd.DataFrame:
            return fetch_fundamentals(
                self.market,
                symbol,
                start_date,
                end_date,
                fund_cache_dir,
                self.client,
                self.data_cfg,
                fundamentals_cfg,
            )

        return self._with_retry(
            label,
            _load,
            log_failures=log_retry_failures,
            log_traceback=log_retry_traceback,
        )
