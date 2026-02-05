"""Data interface to decouple provider wiring from research logic."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, Optional
import logging
import os
import time

import numpy as np
import pandas as pd

from .data_providers import (
    fetch_daily,
    fetch_fundamentals,
    load_basic,
    normalize_market,
    resolve_provider,
)


def _patch_rqdatac_adjust_price_readonly(logger: logging.Logger) -> None:
    """Ensure rqdatac's in-place adjust doesn't choke on read-only arrays."""
    try:
        import rqdatac.services.detail.adjust_price as adjust_price
    except Exception as exc:  # pragma: no cover - defensive import
        logger.debug("rqdatac adjust_price import failed: %s", exc)
        return
    if getattr(adjust_price, "_csxgb_readonly_patch", False):
        return

    original = adjust_price.adjust_price_multi_df

    def wrapped(df, order_book_ids, how, obid_slice_map, market):
        r_map_fields = {
            f: i
            for i, f in enumerate(df.columns)
            if f in adjust_price.FIELDS_NEED_TO_ADJUST
        }
        if not r_map_fields:
            return
        pre = how in ("pre", "pre_volume")
        volume_adjust_by_ex_factor = how in ("pre_volume", "post_volume")
        ex_factors = adjust_price.get_ex_factor_for(order_book_ids, market)
        volume_adjust_factors = {}
        if "volume" in r_map_fields:
            if not volume_adjust_by_ex_factor:
                volume_adjust_factors = adjust_price.get_split_factor_for(order_book_ids, market)
            else:
                volume_adjust_factors = ex_factors

        data = df.to_numpy(copy=True)
        try:
            data.setflags(write=True)
        except Exception:
            pass
        timestamps_level = df.index.get_level_values(1)
        for order_book_id, slice_ in obid_slice_map.items():
            if order_book_id not in order_book_ids:
                continue
            timestamps = timestamps_level[slice_]

            def calculate_factor(factors_map, order_book_id):
                factors = factors_map.get(order_book_id, None)
                if factors is not None:
                    factor = np.take(
                        factors.values,
                        factors.index.searchsorted(timestamps, side="right") - 1,
                    )
                    if pre:
                        factor /= factors.iloc[-1]
                    return factor

            factor = calculate_factor(ex_factors, order_book_id)
            if factor is None:
                continue

            if not volume_adjust_by_ex_factor:
                factor_volume = calculate_factor(volume_adjust_factors, order_book_id)
            else:
                factor_volume = factor

            for f, j in r_map_fields.items():
                if f in adjust_price.PRICE_FIELDS:
                    data[slice_, j] *= factor
                elif factor_volume is not None:
                    data[slice_, j] *= 1 / factor_volume

        df.iloc[:, :] = data

    wrapped.__name__ = original.__name__
    wrapped.__doc__ = original.__doc__
    adjust_price._csxgb_original_adjust_price_multi_df = original
    adjust_price.adjust_price_multi_df = wrapped
    adjust_price._csxgb_readonly_patch = True
    logger.warning(
        "Applied rqdatac read-only adjust_price patch (DataFrame copy on demand)."
    )


@dataclass
class DataInterface:
    market: str
    data_cfg: Mapping
    cache_dir: Path
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("csxgb"))
    provider: str = field(init=False)
    client: object = field(init=False, default=None)
    tushare_tokens: list[str] = field(default_factory=list)
    tushare_token_idx: int = 0
    max_attempts: int = field(init=False)
    backoff_seconds: float = field(init=False)
    max_backoff_seconds: float = field(init=False)
    rotate_tokens: bool = field(init=False)

    def __post_init__(self) -> None:
        self.market = normalize_market(self.market)
        self.data_cfg = self.data_cfg if isinstance(self.data_cfg, Mapping) else {}
        self.provider = resolve_provider(self.data_cfg)
        self.cache_dir.mkdir(exist_ok=True)

        retry_cfg = self.data_cfg.get("retry") if isinstance(self.data_cfg, Mapping) else None
        retry_cfg = retry_cfg if isinstance(retry_cfg, Mapping) else {}
        self.max_attempts = max(1, int(retry_cfg.get("max_attempts", 1)))
        self.backoff_seconds = float(retry_cfg.get("backoff_seconds", 0.5))
        self.max_backoff_seconds = float(retry_cfg.get("max_backoff_seconds", 5.0))
        self.rotate_tokens = bool(retry_cfg.get("rotate_tokens", True))

        self._init_client()

    def _load_tushare_tokens(self) -> list[str]:
        raw_tokens = [
            os.getenv("TUSHARE_TOKEN"),
            os.getenv("TUSHARE_TOKEN_2"),
            os.getenv("TUSHARE_API_KEY"),  # legacy alias
        ]
        tokens: list[str] = []
        for token in raw_tokens:
            if token and token not in tokens:
                tokens.append(token)
        return tokens

    def _make_tushare_client(self, token: str):
        import tushare as ts

        try:
            return ts.pro_api(token)
        except TypeError:
            ts.set_token(token)
            return ts.pro_api()

    def _init_client(self) -> None:
        if self.provider == "tushare":
            self.tushare_tokens = self._load_tushare_tokens()
            if not self.tushare_tokens:
                raise SystemExit(
                    "Please set TUSHARE_TOKEN (or TUSHARE_TOKEN_2 / legacy TUSHARE_API_KEY) first."
                )
            self.tushare_token_idx = 0
            self.client = self._make_tushare_client(self.tushare_tokens[self.tushare_token_idx])
            return

        if self.provider == "rqdata":
            try:
                import rqdatac
            except ImportError as exc:
                raise SystemExit(f"rqdatac is required for provider='rqdata' ({exc}).") from exc
            rq_cfg = self.data_cfg.get("rqdata") or {}
            init_kwargs = {}
            if isinstance(rq_cfg, dict) and isinstance(rq_cfg.get("init"), dict):
                init_kwargs.update(rq_cfg.get("init"))
            env_username = os.getenv("RQDATA_USERNAME") or os.getenv("RQDATA_USER")
            env_password = os.getenv("RQDATA_PASSWORD")
            if env_username and "username" not in init_kwargs:
                init_kwargs["username"] = env_username
            if env_password and "password" not in init_kwargs:
                init_kwargs["password"] = env_password
            try:
                rqdatac.init(**init_kwargs)
            except Exception as exc:
                raise SystemExit(f"rqdatac.init failed: {exc}") from exc
            _patch_rqdatac_adjust_price_readonly(self.logger)
            self.client = rqdatac
            return

        if self.provider == "eodhd":
            eod_cfg = self.data_cfg.get("eodhd") or {}
            api_token = (
                (eod_cfg.get("api_token") if isinstance(eod_cfg, Mapping) else None)
                or os.getenv("EODHD_API_TOKEN")
                or os.getenv("EODHD_API_KEY")
            )
            if not api_token:
                raise SystemExit("Please set EODHD_API_TOKEN (or data.eodhd.api_token) first.")
            client = {"api_token": api_token}
            if isinstance(eod_cfg, Mapping):
                if eod_cfg.get("base_url"):
                    client["base_url"] = eod_cfg.get("base_url")
                if eod_cfg.get("exchange"):
                    client["exchange"] = eod_cfg.get("exchange")
                if eod_cfg.get("timeout"):
                    client["timeout"] = eod_cfg.get("timeout")
            self.client = client
            return

        raise SystemExit(f"Unsupported data.provider '{self.provider}'.")

    def _rotate_tushare_token(self) -> None:
        if self.provider != "tushare":
            return
        if not self.rotate_tokens or len(self.tushare_tokens) <= 1:
            return
        self.tushare_token_idx = (self.tushare_token_idx + 1) % len(self.tushare_tokens)
        self.client = self._make_tushare_client(self.tushare_tokens[self.tushare_token_idx])
        self.logger.info("Switched Tushare token to index %s.", self.tushare_token_idx)

    def _with_retry(
        self,
        label: str,
        action: Callable[[], pd.DataFrame],
    ) -> pd.DataFrame:
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return action()
            except Exception as exc:
                last_exc = exc
                self.logger.warning(
                    "%s (attempt %s/%s): %s",
                    label,
                    attempt,
                    self.max_attempts,
                    exc,
                    exc_info=True,
                )
                self._rotate_tushare_token()
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

        return self._with_retry(label, _load)
