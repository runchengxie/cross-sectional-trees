"""Execution assumptions (cost + exit policy) as pluggable modules."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Optional, Protocol

import numpy as np
import pandas as pd

ExitPricePolicy = Literal["strict", "ffill", "delay"]
ExitFallbackPolicy = Literal["ffill", "none"]


class CostModel(Protocol):
    def cost(self, turnover: float, *, is_initial: bool, side: str) -> float:
        ...


@dataclass(frozen=True)
class BpsCostModel:
    bps: float
    round_trip: bool = True

    def cost(self, turnover: float, *, is_initial: bool, side: str) -> float:
        if not np.isfinite(self.bps) or self.bps <= 0:
            return 0.0
        per_side = self.bps / 10000.0
        if is_initial:
            return per_side
        factor = 2.0 if self.round_trip else 1.0
        return float(factor * per_side * turnover)


@dataclass(frozen=True)
class NoCostModel:
    def cost(self, turnover: float, *, is_initial: bool, side: str) -> float:
        return 0.0


@dataclass(frozen=True)
class ExitPolicy:
    price_policy: ExitPricePolicy
    fallback_policy: ExitFallbackPolicy

    def resolve_exit_prices(
        self,
        holdings: list[str],
        planned_exit_idx: int,
        *,
        price_table: pd.DataFrame,
        tradable_table: Optional[pd.DataFrame],
        trade_dates: list[pd.Timestamp],
        date_to_idx: dict[pd.Timestamp, int],
    ) -> tuple[pd.Series, int]:
        if not holdings:
            return pd.Series(dtype=float), planned_exit_idx

        exit_idx_map: dict[str, int] = {}
        exit_price_map: dict[str, float] = {}
        for symbol in holdings:
            series = price_table[symbol]
            tradable_series = tradable_table[symbol] if tradable_table is not None else None
            exit_idx = self._resolve_exit_idx(
                series,
                planned_exit_idx,
                trade_dates=trade_dates,
                date_to_idx=date_to_idx,
                tradable_series=tradable_series,
            )
            if exit_idx is None:
                continue
            exit_price = price_table.iloc[exit_idx][symbol]
            if not np.isfinite(exit_price):
                continue
            exit_idx_map[symbol] = int(exit_idx)
            exit_price_map[symbol] = float(exit_price)

        if not exit_price_map:
            return pd.Series(dtype=float), planned_exit_idx

        exit_prices = pd.Series(exit_price_map)
        if self.price_policy == "delay":
            max_exit_idx = max(exit_idx_map.values())
            period_exit_idx = max(planned_exit_idx, max_exit_idx)
        else:
            period_exit_idx = planned_exit_idx
        return exit_prices, period_exit_idx

    def _resolve_exit_idx(
        self,
        series: pd.Series,
        planned_exit_idx: int,
        *,
        trade_dates: list[pd.Timestamp],
        date_to_idx: dict[pd.Timestamp, int],
        tradable_series: Optional[pd.Series],
    ) -> Optional[int]:
        if planned_exit_idx >= len(trade_dates):
            return None
        if self.price_policy == "strict":
            if not np.isfinite(series.iloc[planned_exit_idx]):
                return None
            if tradable_series is not None and not bool(tradable_series.iloc[planned_exit_idx]):
                return None
            return planned_exit_idx

        if self.price_policy == "ffill":
            window = series.iloc[: planned_exit_idx + 1]
            if tradable_series is not None:
                window = window[tradable_series.iloc[: planned_exit_idx + 1]]
            exit_date = window.last_valid_index()
            return date_to_idx.get(exit_date) if exit_date is not None else None

        window = series.iloc[planned_exit_idx:]
        if tradable_series is not None:
            window = window[tradable_series.iloc[planned_exit_idx:]]
        exit_date = window.first_valid_index()
        if exit_date is None and self.fallback_policy == "ffill":
            window = series.iloc[: planned_exit_idx + 1]
            if tradable_series is not None:
                window = window[tradable_series.iloc[: planned_exit_idx + 1]]
            exit_date = window.last_valid_index()
        return date_to_idx.get(exit_date) if exit_date is not None else None


@dataclass(frozen=True)
class ExecutionModel:
    cost_model: CostModel
    exit_policy: ExitPolicy


def build_cost_model(cost_cfg: Optional[Mapping], default_bps: float) -> CostModel:
    if cost_cfg is None:
        return BpsCostModel(float(default_bps))
    if not isinstance(cost_cfg, Mapping):
        name = str(cost_cfg).strip().lower()
        if name in {"none", "zero", "off"}:
            return NoCostModel()
        return BpsCostModel(float(default_bps))

    name = str(cost_cfg.get("name", "bps")).strip().lower()
    if name in {"none", "zero", "off"}:
        return NoCostModel()
    if name in {"bps", "bp", "basis"}:
        bps = cost_cfg.get("bps", default_bps)
        round_trip = bool(cost_cfg.get("round_trip", True))
        return BpsCostModel(float(bps), round_trip=round_trip)
    raise ValueError(f"Unsupported cost model: {name}")


def build_exit_policy(
    exit_cfg: Optional[Mapping],
    default_price: ExitPricePolicy,
    default_fallback: ExitFallbackPolicy,
) -> ExitPolicy:
    if exit_cfg is None:
        return ExitPolicy(default_price, default_fallback)
    if not isinstance(exit_cfg, Mapping):
        return ExitPolicy(default_price, default_fallback)

    price = exit_cfg.get("price") or exit_cfg.get("price_policy") or default_price
    fallback = exit_cfg.get("fallback") or exit_cfg.get("fallback_policy") or default_fallback
    price = str(price).strip().lower()
    fallback = str(fallback).strip().lower()
    if price not in {"strict", "ffill", "delay"}:
        raise ValueError("exit_policy.price must be one of: strict, ffill, delay.")
    if fallback not in {"ffill", "none"}:
        raise ValueError("exit_policy.fallback must be one of: ffill, none.")
    return ExitPolicy(price, fallback)


def build_execution_model(
    execution_cfg: Optional[Mapping],
    *,
    default_cost_bps: float,
    default_exit_price_policy: ExitPricePolicy,
    default_exit_fallback_policy: ExitFallbackPolicy,
) -> ExecutionModel:
    cost_cfg = None
    exit_cfg = None
    if isinstance(execution_cfg, Mapping):
        cost_cfg = execution_cfg.get("cost_model") or execution_cfg.get("cost")
        exit_cfg = execution_cfg.get("exit_policy") or execution_cfg.get("exit")
    cost_model = build_cost_model(cost_cfg, default_cost_bps)
    exit_policy = build_exit_policy(
        exit_cfg,
        default_price=default_exit_price_policy,
        default_fallback=default_exit_fallback_policy,
    )
    return ExecutionModel(cost_model=cost_model, exit_policy=exit_policy)


def describe_cost_model(cost_model: CostModel) -> dict:
    if isinstance(cost_model, BpsCostModel):
        return {
            "name": "bps",
            "bps": float(cost_model.bps),
            "round_trip": bool(cost_model.round_trip),
        }
    if isinstance(cost_model, NoCostModel):
        return {"name": "none"}
    return {"name": cost_model.__class__.__name__}


def describe_execution_model(model: ExecutionModel) -> dict:
    return {
        "cost_model": describe_cost_model(model.cost_model),
        "exit_policy": {
            "price_policy": model.exit_policy.price_policy,
            "fallback_policy": model.exit_policy.fallback_policy,
        },
    }
