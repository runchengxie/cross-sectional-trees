from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class HkAllocSettings:
    cash: float = 1_000_000.0
    method: str = "equal"
    require_stock_connect: bool = True
    execution_calendar: str = "hk_connect"
    allow_connect_closed: bool = False
    history_years: int = 3
    roll_window: int = 252
    sell_quantile: float = 0.95
    extreme_quantile: float = 0.99
    secondary_fill_enabled: bool = True
    secondary_fill_avoid_high_valuation: bool = True
    secondary_fill_avoid_high_valuation_strict: bool = False
    secondary_fill_max_steps: int = 5000
    secondary_fill_allow_over_alloc: bool = False
    secondary_fill_max_over_alloc_ratio: float = 0.0
    secondary_fill_max_over_alloc_amount: float = 0.0
    secondary_fill_max_over_alloc_lots_per_ticker: int = 1
    secondary_fill_cash_buffer_ratio: float = 0.0
    secondary_fill_cash_buffer_amount: float = 0.0
    secondary_fill_estimated_fee_per_order: float = 0.0


@dataclass(frozen=True)
class SelectedTicker:
    symbol: str
    name: str | None = None
    weight: float | None = None
    rank: int | None = None
    signal: float | None = None
    side: str = "long"


@dataclass(frozen=True)
class ScenarioReport:
    scenario_id: str
    allocation_df: pd.DataFrame
    summary_df: pd.DataFrame
    sell_signals_df: pd.DataFrame


@dataclass(frozen=True)
class MarketDataBundle:
    symbols: tuple[str, ...]
    order_book_ids: tuple[str, ...]
    symbol_to_oid: dict[str, str]
    instruments_df: pd.DataFrame
    latest_prices: pd.DataFrame
    close_none: pd.DataFrame
    close_pre: pd.DataFrame
