from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import numpy as np
import pandas as pd

from .data_tools.symbols import canonicalize_symbol_columns
from .execution import (
    BpsCostModel,
    CostModel,
    EntryPolicy,
    ExecutionModel,
    ExitPolicy,
    NoSlippageModel,
    ParticipationSlippageModel,
    SelectionConstraints,
    SlippageModel,
)
from .execution_calendar import resolve_execution_date
from .portfolio import (
    build_position_weights,
    normalize_position_weights,
    normalize_weighting_mode,
    select_holdings,
)


def _drawdown_timing(nav: pd.Series) -> dict[str, float]:
    if nav is None:
        return {
            "drawdown_duration": np.nan,
            "recovery_time": np.nan,
            "drawdown_duration_days": np.nan,
            "recovery_time_days": np.nan,
        }
    nav = nav.dropna()
    if nav.empty:
        return {
            "drawdown_duration": np.nan,
            "recovery_time": np.nan,
            "drawdown_duration_days": np.nan,
            "recovery_time_days": np.nan,
        }

    running_max = nav.cummax()
    drawdown = nav / running_max - 1.0
    trough_date = drawdown.idxmin()
    try:
        trough_pos = nav.index.get_loc(trough_date)
    except KeyError:
        trough_pos = int(drawdown.values.argmin())
        trough_date = nav.index[trough_pos]

    peak_value = float(running_max.loc[trough_date])
    pre_peak = nav.loc[:trough_date]
    peak_candidates = pre_peak[pre_peak == peak_value]
    if peak_candidates.empty:
        peak_date = nav.index[0]
        peak_pos = 0
    else:
        peak_date = peak_candidates.index[-1]
        peak_pos = nav.index.get_loc(peak_date)

    drawdown_duration = float(trough_pos - peak_pos)

    post_nav = nav.loc[trough_date:]
    recovery_candidates = post_nav[post_nav >= peak_value]
    if recovery_candidates.empty:
        recovery_time = np.nan
        recovery_days = np.nan
    else:
        recovery_date = recovery_candidates.index[0]
        recovery_pos = nav.index.get_loc(recovery_date)
        recovery_time = float(recovery_pos - trough_pos)
        if isinstance(nav.index, pd.DatetimeIndex):
            recovery_days = float((recovery_date - trough_date).days)
        else:
            recovery_days = np.nan

    if isinstance(nav.index, pd.DatetimeIndex):
        drawdown_days = float((trough_date - peak_date).days)
    else:
        drawdown_days = np.nan

    return {
        "drawdown_duration": drawdown_duration,
        "recovery_time": recovery_time,
        "drawdown_duration_days": drawdown_days,
        "recovery_time_days": recovery_days,
    }

def summarize_period_returns(
    returns: pd.Series,
    period_info: list[dict],
    trading_days_per_year: int,
) -> dict:
    if returns is None or returns.empty:
        return {
            "periods": 0,
            "total_return": np.nan,
            "ann_return": np.nan,
            "ann_vol": np.nan,
            "sharpe": np.nan,
            "max_drawdown": np.nan,
            "avg_holding": np.nan,
            "periods_per_year": np.nan,
            "sortino": np.nan,
            "calmar": np.nan,
            "drawdown_duration": np.nan,
            "recovery_time": np.nan,
            "drawdown_duration_days": np.nan,
            "recovery_time_days": np.nan,
            "skew": np.nan,
            "kurtosis": np.nan,
            "var_95": np.nan,
            "cvar_95": np.nan,
            "avg_exit_lag_days": np.nan,
            "max_exit_lag_days": np.nan,
            "periods_with_delayed_exit": 0,
            "delayed_exit_ratio": np.nan,
        }

    nav = (1 + returns).cumprod()
    total_return = nav.iloc[-1] - 1.0
    max_drawdown = (nav / nav.cummax() - 1.0).min()

    total_days = np.nan
    if period_info:
        entry_first = period_info[0]["entry_idx"]
        exit_last = period_info[-1]["exit_idx"]
        total_days = exit_last - entry_first
    if np.isfinite(total_days) and total_days > 0:
        ann_return = (1 + total_return) ** (trading_days_per_year / total_days) - 1.0
    else:
        ann_return = np.nan

    holding_lengths = [info["exit_idx"] - info["entry_idx"] for info in period_info]
    avg_holding = np.mean(holding_lengths) if holding_lengths else np.nan
    periods_per_year = (
        trading_days_per_year / avg_holding
        if np.isfinite(avg_holding) and avg_holding > 0
        else np.nan
    )
    period_vol = returns.std(ddof=1)
    if np.isfinite(period_vol) and period_vol > 0 and np.isfinite(periods_per_year):
        ann_vol = period_vol * np.sqrt(periods_per_year)
        sharpe = returns.mean() / period_vol * np.sqrt(periods_per_year)
    else:
        ann_vol = np.nan
        sharpe = np.nan

    downside = np.minimum(returns.to_numpy(), 0.0)
    downside_std = float(np.sqrt(np.mean(downside**2))) if len(downside) > 0 else np.nan
    if np.isfinite(downside_std) and downside_std > 0 and np.isfinite(periods_per_year):
        sortino = float(returns.mean() / downside_std * np.sqrt(periods_per_year))
    else:
        sortino = np.nan

    if np.isfinite(max_drawdown) and max_drawdown < 0 and np.isfinite(ann_return):
        calmar = float(ann_return / abs(max_drawdown))
    else:
        calmar = np.nan

    timing = _drawdown_timing(nav)

    exit_lags: list[float] = []
    for info in period_info:
        lag_raw = info.get("exit_delay_steps")
        if lag_raw is None:
            planned_idx = info.get("planned_exit_idx")
            exit_idx = info.get("exit_idx")
            if planned_idx is not None and exit_idx is not None:
                lag_raw = int(exit_idx) - int(planned_idx)
        if lag_raw is None:
            continue
        try:
            lag = float(lag_raw)
        except (TypeError, ValueError):
            continue
        if np.isfinite(lag):
            exit_lags.append(max(0.0, lag))

    if exit_lags:
        avg_exit_lag = float(np.mean(exit_lags))
        max_exit_lag = float(np.max(exit_lags))
        delayed_periods = int(sum(lag > 0 for lag in exit_lags))
        delayed_ratio = delayed_periods / float(len(exit_lags))
    else:
        avg_exit_lag = np.nan
        max_exit_lag = np.nan
        delayed_periods = 0
        delayed_ratio = np.nan

    skew = float(returns.skew()) if returns.shape[0] > 2 else np.nan
    kurtosis = float(returns.kurtosis()) if returns.shape[0] > 3 else np.nan
    if returns.shape[0] > 0:
        var_95 = float(np.nanpercentile(returns, 5))
        tail = returns[returns <= var_95]
        cvar_95 = float(tail.mean()) if not tail.empty else np.nan
    else:
        var_95 = np.nan
        cvar_95 = np.nan

    return {
        "periods": len(returns),
        "total_return": total_return,
        "ann_return": ann_return,
        "ann_vol": ann_vol,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "avg_holding": avg_holding,
        "periods_per_year": periods_per_year,
        "sortino": sortino,
        "calmar": calmar,
        "drawdown_duration": timing["drawdown_duration"],
        "recovery_time": timing["recovery_time"],
        "drawdown_duration_days": timing["drawdown_duration_days"],
        "recovery_time_days": timing["recovery_time_days"],
        "skew": skew,
        "kurtosis": kurtosis,
        "var_95": var_95,
        "cvar_95": cvar_95,
        "avg_exit_lag_days": avg_exit_lag,
        "max_exit_lag_days": max_exit_lag,
        "periods_with_delayed_exit": delayed_periods,
        "delayed_exit_ratio": delayed_ratio,
    }


def _compute_trade_summary(
    prev_weights: Optional[pd.Series],
    prev_prices: Optional[pd.Series],
    prev_date: Optional[pd.Timestamp],
    target_weights: pd.Series,
    entry_date: pd.Timestamp,
    *,
    price_table: pd.DataFrame,
) -> tuple[float, float, float, pd.Series]:
    if target_weights is None or target_weights.empty:
        return 0.0, 0.0, 0.0, pd.Series(dtype=float)

    target_clean = normalize_position_weights(target_weights)
    if target_clean.empty:
        return 0.0, 0.0, 0.0, pd.Series(dtype=float)

    if prev_weights is None or prev_weights.empty:
        trade_weights = target_clean.copy()
        traded = float(trade_weights.abs().sum())
        return traded, traded, 0.0, trade_weights

    prev_clean = normalize_position_weights(prev_weights)
    drift_weights = prev_clean
    if prev_prices is not None and prev_date is not None:
        prev_prices = prev_prices.reindex(prev_clean.index)
        prev_prices = prev_prices[prev_prices.notna()]
        if not prev_prices.empty and entry_date in price_table.index:
            prev_clean = prev_clean.reindex(prev_prices.index).dropna()
            current_prices = price_table.loc[entry_date, prev_prices.index]
            valid_prev = current_prices.notna()
            prev_prices = prev_prices[valid_prev]
            current_prices = current_prices[valid_prev]
            prev_clean = prev_clean.reindex(prev_prices.index).dropna()
            if not prev_prices.empty and not prev_clean.empty:
                drift = prev_clean * (current_prices / prev_prices)
                drift_sum = float(drift.sum())
                if drift_sum > 0:
                    drift_weights = normalize_position_weights(drift)

    all_ids = drift_weights.index.union(target_clean.index)
    drift_aligned = drift_weights.reindex(all_ids).fillna(0.0)
    target_aligned = target_clean.reindex(all_ids).fillna(0.0)
    trade_weights = target_aligned - drift_aligned
    entry_turnover = float(trade_weights.clip(lower=0.0).sum())
    exit_turnover = float((-trade_weights.clip(upper=0.0)).sum())
    turnover = 0.5 * float(np.abs(trade_weights).sum())
    return turnover, entry_turnover, exit_turnover, trade_weights


@dataclass(frozen=True)
class _BacktestExecutionContext:
    exit_policy: ExitPolicy
    cost_model: CostModel
    slippage_model: SlippageModel
    entry_policy: EntryPolicy
    selection_constraints: SelectionConstraints
    calendar: str
    open_dates: tuple
    closed_dates: tuple


@dataclass(frozen=True)
class _BacktestPricingContext:
    trade_dates: list[pd.Timestamp]
    date_to_idx: dict[pd.Timestamp, int]
    entry_price_table: pd.DataFrame
    exit_price_table: pd.DataFrame
    day_groups: dict[pd.Timestamp, pd.DataFrame]
    tradable_table: pd.DataFrame | None
    amount_tables: dict[str, pd.DataFrame]


@dataclass(frozen=True)
class _BacktestPositionState:
    holdings: set[str] | None = None
    weights: pd.Series | None = None
    entry_date: pd.Timestamp | None = None
    entry_prices: pd.Series | None = None


@dataclass(frozen=True)
class _BacktestLegResult:
    holdings: list[str]
    weights: pd.Series
    entry_prices: pd.Series
    exit_idx: int
    exit_date: pd.Timestamp
    gross: float
    turnover: float
    fee_cost: float
    slippage_cost: float


@dataclass(frozen=True)
class _BacktestPeriodPlan:
    entry_idx: int
    planned_exit_idx: int
    entry_date: pd.Timestamp
    planned_exit_date: pd.Timestamp


def _normalize_backtest_frame(
    frame: pd.DataFrame | None,
    *,
    context: str,
) -> pd.DataFrame | None:
    if frame is None or frame.empty:
        return frame
    normalized = canonicalize_symbol_columns(frame, context=context)
    normalized = normalized.copy()
    normalized["trade_date"] = pd.to_datetime(normalized["trade_date"]).dt.normalize()
    return normalized


def _resolve_backtest_execution_context(
    *,
    execution: ExecutionModel | None,
    exit_price_policy: Literal["strict", "ffill", "delay"],
    exit_fallback_policy: Literal["ffill", "none"],
    price_col: str,
    cost_bps: float,
) -> _BacktestExecutionContext:
    if execution is not None:
        return _BacktestExecutionContext(
            exit_policy=execution.exit_policy,
            cost_model=execution.cost_model,
            slippage_model=execution.slippage_model,
            entry_policy=execution.entry_policy,
            selection_constraints=execution.selection_constraints,
            calendar=execution.calendar,
            open_dates=execution.calendar_open_dates,
            closed_dates=execution.calendar_closed_dates,
        )

    if exit_price_policy not in {"strict", "ffill", "delay"}:
        raise ValueError("exit_price_policy must be one of: strict, ffill, delay.")
    if exit_fallback_policy not in {"ffill", "none"}:
        raise ValueError("exit_fallback_policy must be one of: ffill, none.")
    return _BacktestExecutionContext(
        exit_policy=ExitPolicy(exit_price_policy, exit_fallback_policy, price_col),
        cost_model=BpsCostModel(cost_bps),
        slippage_model=NoSlippageModel(),
        entry_policy=EntryPolicy(price_col),
        selection_constraints=SelectionConstraints(),
        calendar="market",
        open_dates=(),
        closed_dates=(),
    )


def _prepare_backtest_pricing_context(
    *,
    data: pd.DataFrame | None,
    pricing_data: pd.DataFrame | None,
    entry_policy: EntryPolicy,
    exit_policy: ExitPolicy,
    selection_constraints: SelectionConstraints,
    slippage_model: SlippageModel,
    tradable_col: str | None,
) -> _BacktestPricingContext | None:
    pricing_source = pricing_data if pricing_data is not None else data
    if pricing_source is None or pricing_source.empty:
        return None

    entry_price_col = entry_policy.price_col
    exit_price_col = exit_policy.price_col
    required_pricing_cols = {entry_price_col, exit_price_col}
    if selection_constraints.min_amount is not None:
        required_pricing_cols.add(selection_constraints.amount_col)
    if isinstance(slippage_model, ParticipationSlippageModel):
        required_pricing_cols.add(slippage_model.amount_col)
    missing_pricing_cols = [
        col for col in sorted(required_pricing_cols) if col not in pricing_source.columns
    ]
    if missing_pricing_cols:
        raise ValueError(
            "Backtest pricing data is missing required columns: "
            + ", ".join(missing_pricing_cols)
        )

    pricing_source = pricing_source.drop_duplicates(subset=["trade_date", "symbol"]).copy()
    trade_dates = [
        pd.Timestamp(date).normalize()
        for date in sorted(pricing_source["trade_date"].unique())
    ]
    if len(trade_dates) < 2:
        return None
    date_to_idx = {date: idx for idx, date in enumerate(trade_dates)}
    entry_price_table = pricing_source.pivot(
        index="trade_date", columns="symbol", values=entry_price_col
    )
    exit_price_table = pricing_source.pivot(
        index="trade_date", columns="symbol", values=exit_price_col
    )
    day_groups = (
        {date: group for date, group in data.groupby("trade_date", sort=False)}
        if data is not None
        else {}
    )
    tradable_table = None
    if tradable_col and tradable_col in pricing_source.columns:
        tradable_table = pricing_source.pivot(
            index="trade_date", columns="symbol", values=tradable_col
        )
        tradable_table = tradable_table.fillna(False).astype(bool)
    amount_tables: dict[str, pd.DataFrame] = {}
    for amount_col in sorted(required_pricing_cols):
        if amount_col in {entry_price_col, exit_price_col}:
            continue
        if amount_col in pricing_source.columns:
            amount_tables[amount_col] = pricing_source.pivot(
                index="trade_date", columns="symbol", values=amount_col
            )

    return _BacktestPricingContext(
        trade_dates=trade_dates,
        date_to_idx=date_to_idx,
        entry_price_table=entry_price_table,
        exit_price_table=exit_price_table,
        day_groups=day_groups,
        tradable_table=tradable_table,
        amount_tables=amount_tables,
    )


def _slippage_pricing_row(
    *,
    slippage_model: SlippageModel,
    amount_tables: dict[str, pd.DataFrame],
    entry_date: pd.Timestamp,
) -> pd.Series | None:
    if not isinstance(slippage_model, ParticipationSlippageModel):
        return None
    return amount_tables[slippage_model.amount_col].loc[entry_date]


def _evaluate_backtest_leg(
    *,
    day: pd.DataFrame,
    entry_date: pd.Timestamp,
    entry_idx: int,
    planned_exit_idx: int,
    trade_dates: list[pd.Timestamp],
    pred_col: str,
    side: Literal["long", "short"],
    count: int,
    ascending: bool,
    weighting_mode: str,
    entry_price_table: pd.DataFrame,
    tradable_table: pd.DataFrame | None,
    amount_tables: dict[str, pd.DataFrame],
    selection_constraints: SelectionConstraints,
    previous: _BacktestPositionState,
    buffer_exit: int,
    buffer_entry: int,
    group_col: str | None,
    max_names_per_group: int | None,
    cost_model: CostModel,
    slippage_model: SlippageModel,
    resolve_exit_prices,
) -> _BacktestLegResult | None:
    if count <= 0:
        return None

    holdings, entry_prices = select_holdings(
        day,
        entry_date,
        count,
        pred_col,
        ascending=ascending,
        price_table=entry_price_table,
        tradable_table=tradable_table,
        amount_table=amount_tables.get(selection_constraints.amount_col),
        constraints=selection_constraints,
        prev_holdings=previous.holdings,
        buffer_exit=buffer_exit,
        buffer_entry=buffer_entry,
        group_col=group_col,
        max_names_per_group=max_names_per_group,
    )
    if not holdings:
        return None

    weights = build_position_weights(
        day,
        holdings,
        pred_col,
        side=side,
        weighting=weighting_mode,
    )
    exit_prices, period_exit_idx = resolve_exit_prices(holdings, planned_exit_idx)
    if exit_prices.empty:
        return None

    entry_prices = entry_prices.reindex(exit_prices.index)
    weights = normalize_position_weights(weights.reindex(exit_prices.index))
    holdings = list(weights.index)
    if not holdings:
        return None

    entry_prices = entry_prices.reindex(holdings)
    exit_prices = exit_prices.reindex(holdings)
    period_returns = (exit_prices / entry_prices) - 1.0
    gross = float((period_returns * weights.reindex(period_returns.index)).sum())
    if side == "short":
        gross = -gross

    turnover, entry_turnover, exit_turnover, trade_weights = _compute_trade_summary(
        previous.weights,
        previous.entry_prices,
        previous.entry_date,
        weights,
        entry_date,
        price_table=entry_price_table,
    )
    fee_cost = cost_model.cost(
        turnover,
        is_initial=previous.weights is None,
        side=side,
        entry_turnover=entry_turnover,
        exit_turnover=exit_turnover,
        holding_days=int(period_exit_idx - entry_idx),
        gross_exposure=float(weights.abs().sum()),
    )
    slippage_cost = slippage_model.cost(
        trade_weights,
        pricing_row=_slippage_pricing_row(
            slippage_model=slippage_model,
            amount_tables=amount_tables,
            entry_date=entry_date,
        ),
        is_initial=previous.weights is None,
        side=side,
    )
    return _BacktestLegResult(
        holdings=holdings,
        weights=weights,
        entry_prices=entry_prices,
        exit_idx=period_exit_idx,
        exit_date=trade_dates[period_exit_idx],
        gross=gross,
        turnover=turnover,
        fee_cost=fee_cost,
        slippage_cost=slippage_cost,
    )


def _resolve_backtest_period_plan(
    *,
    rebalance_dates: list[pd.Timestamp],
    rebalance_index: int,
    rebalance_date: pd.Timestamp,
    exit_mode: Literal["rebalance", "label_horizon"],
    exit_horizon_days: int | None,
    shift_days: int,
    prev_exit_idx: int | None,
    trade_dates: list[pd.Timestamp],
    date_to_idx: dict[pd.Timestamp, int],
    execution_calendar: str,
    execution_open_dates: tuple,
    execution_closed_dates: tuple,
) -> _BacktestPeriodPlan | None:
    if rebalance_date not in date_to_idx:
        return None

    entry_date = resolve_execution_date(
        rebalance_date,
        shift_days,
        trade_dates,
        calendar=execution_calendar,
        open_dates=execution_open_dates,
        closed_dates=execution_closed_dates,
    )
    if entry_date is None:
        return None
    entry_idx = date_to_idx.get(entry_date)
    if entry_idx is None:
        return None

    if exit_mode == "rebalance":
        if rebalance_index >= len(rebalance_dates) - 1:
            return None
        next_rebalance = pd.Timestamp(rebalance_dates[rebalance_index + 1]).normalize()
        if next_rebalance not in date_to_idx:
            return None
        planned_exit_date = resolve_execution_date(
            next_rebalance,
            shift_days,
            trade_dates,
            calendar=execution_calendar,
            open_dates=execution_open_dates,
            closed_dates=execution_closed_dates,
        )
        if planned_exit_date is None:
            return None
        planned_exit_idx = date_to_idx.get(planned_exit_date)
        if planned_exit_idx is None:
            return None
    else:
        if exit_horizon_days is None:
            raise ValueError("exit_horizon_days is required for exit_mode='label_horizon'.")
        planned_exit_idx = entry_idx + exit_horizon_days
        planned_exit_date = (
            trade_dates[planned_exit_idx]
            if 0 <= planned_exit_idx < len(trade_dates)
            else pd.NaT
        )
        if prev_exit_idx is not None and entry_idx < prev_exit_idx:
            raise ValueError(
                "exit_mode='label_horizon' overlaps with rebalance_dates. "
                "Increase rebalance_frequency or use exit_mode='rebalance'."
            )

    if prev_exit_idx is not None and entry_idx < prev_exit_idx:
        return None
    if (
        entry_idx >= len(trade_dates)
        or planned_exit_idx >= len(trade_dates)
        or entry_idx >= planned_exit_idx
    ):
        return None

    return _BacktestPeriodPlan(
        entry_idx=entry_idx,
        planned_exit_idx=planned_exit_idx,
        entry_date=trade_dates[entry_idx],
        planned_exit_date=trade_dates[planned_exit_idx],
    )


def backtest_topk(
    data: pd.DataFrame,
    pred_col: str,
    price_col: str,
    rebalance_dates: list[pd.Timestamp],
    top_k: int,
    shift_days: int,
    cost_bps: float,
    trading_days_per_year: int,
    exit_mode: Literal["rebalance", "label_horizon"] = "rebalance",
    exit_horizon_days: Optional[int] = None,
    long_only: bool = True,
    short_k: Optional[int] = None,
    weighting: Literal["equal", "signal"] = "equal",
    buffer_exit: int = 0,
    buffer_entry: int = 0,
    tradable_col: Optional[str] = None,
    group_col: Optional[str] = None,
    max_names_per_group: Optional[int] = None,
    exit_price_policy: Literal["strict", "ffill", "delay"] = "strict",
    exit_fallback_policy: Literal["ffill", "none"] = "ffill",
    execution: Optional[ExecutionModel] = None,
    pricing_data: Optional[pd.DataFrame] = None,
):
    data = _normalize_backtest_frame(data, context="Backtest data")
    pricing_data = _normalize_backtest_frame(pricing_data, context="Backtest pricing data")
    execution_context = _resolve_backtest_execution_context(
        execution=execution,
        exit_price_policy=exit_price_policy,
        exit_fallback_policy=exit_fallback_policy,
        price_col=price_col,
        cost_bps=cost_bps,
    )
    exit_policy = execution_context.exit_policy
    cost_model = execution_context.cost_model
    slippage_model = execution_context.slippage_model
    entry_policy = execution_context.entry_policy
    selection_constraints = execution_context.selection_constraints
    execution_calendar = execution_context.calendar
    execution_open_dates = execution_context.open_dates
    execution_closed_dates = execution_context.closed_dates
    weighting_mode = normalize_weighting_mode(weighting)
    pricing_context = _prepare_backtest_pricing_context(
        data=data,
        pricing_data=pricing_data,
        entry_policy=entry_policy,
        exit_policy=exit_policy,
        selection_constraints=selection_constraints,
        slippage_model=slippage_model,
        tradable_col=tradable_col,
    )
    if pricing_context is None:
        return None
    trade_dates = pricing_context.trade_dates
    date_to_idx = pricing_context.date_to_idx
    entry_price_table = pricing_context.entry_price_table
    exit_price_table = pricing_context.exit_price_table
    day_groups = pricing_context.day_groups
    tradable_table = pricing_context.tradable_table
    amount_tables = pricing_context.amount_tables

    net_returns = []
    gross_returns = []
    turnovers = []
    costs = []
    fee_costs = []
    slippage_costs = []
    period_info = []
    long_state = _BacktestPositionState()
    short_state = _BacktestPositionState()
    prev_exit_idx = None

    def _resolve_exit_prices(
        holdings: list[str],
        planned_exit_idx: int,
    ) -> tuple[pd.Series, int]:
        return exit_policy.resolve_exit_prices(
            holdings,
            planned_exit_idx,
            price_table=exit_price_table,
            tradable_table=tradable_table,
            trade_dates=trade_dates,
            date_to_idx=date_to_idx,
        )

    for i, reb_date in enumerate(rebalance_dates):
        reb_date = pd.Timestamp(reb_date).normalize()
        period_plan = _resolve_backtest_period_plan(
            rebalance_dates=rebalance_dates,
            rebalance_index=i,
            rebalance_date=reb_date,
            exit_mode=exit_mode,
            exit_horizon_days=exit_horizon_days,
            shift_days=shift_days,
            prev_exit_idx=prev_exit_idx,
            trade_dates=trade_dates,
            date_to_idx=date_to_idx,
            execution_calendar=execution_calendar,
            execution_open_dates=execution_open_dates,
            execution_closed_dates=execution_closed_dates,
        )
        if period_plan is None:
            continue

        entry_idx = period_plan.entry_idx
        planned_exit_idx = period_plan.planned_exit_idx
        exit_idx = planned_exit_idx
        entry_date = period_plan.entry_date
        planned_exit_date = period_plan.planned_exit_date
        day = day_groups.get(reb_date)
        if day is None or day.empty:
            continue

        k = min(top_k, len(day))
        if k <= 0:
            continue

        if long_only:
            long_leg = _evaluate_backtest_leg(
                day=day,
                entry_date=entry_date,
                entry_idx=entry_idx,
                planned_exit_idx=planned_exit_idx,
                trade_dates=trade_dates,
                pred_col=pred_col,
                side="long",
                count=k,
                ascending=False,
                weighting_mode=weighting_mode,
                entry_price_table=entry_price_table,
                tradable_table=tradable_table,
                amount_tables=amount_tables,
                selection_constraints=selection_constraints,
                previous=long_state,
                buffer_exit=buffer_exit,
                buffer_entry=buffer_entry,
                group_col=group_col,
                max_names_per_group=max_names_per_group,
                cost_model=cost_model,
                slippage_model=slippage_model,
                resolve_exit_prices=_resolve_exit_prices,
            )
            if long_leg is None:
                continue

            gross = long_leg.gross
            turnover = long_leg.turnover
            fee_cost = long_leg.fee_cost
            slippage_cost = long_leg.slippage_cost
            total_cost = fee_cost + slippage_cost
            net = gross - total_cost
            exit_idx = long_leg.exit_idx
            exit_date = long_leg.exit_date
            long_state = _BacktestPositionState(
                holdings=set(long_leg.holdings),
                weights=long_leg.weights,
                entry_date=entry_date,
                entry_prices=long_leg.entry_prices,
            )
        else:
            short_k_final = short_k if short_k is not None else k
            short_k_final = min(int(short_k_final), len(day) - k)
            if short_k_final <= 0:
                continue

            long_leg = _evaluate_backtest_leg(
                day=day,
                entry_date=entry_date,
                entry_idx=entry_idx,
                planned_exit_idx=planned_exit_idx,
                trade_dates=trade_dates,
                pred_col=pred_col,
                side="long",
                count=k,
                ascending=False,
                weighting_mode=weighting_mode,
                entry_price_table=entry_price_table,
                tradable_table=tradable_table,
                amount_tables=amount_tables,
                selection_constraints=selection_constraints,
                previous=long_state,
                buffer_exit=buffer_exit,
                buffer_entry=buffer_entry,
                group_col=group_col,
                max_names_per_group=max_names_per_group,
                cost_model=cost_model,
                slippage_model=slippage_model,
                resolve_exit_prices=_resolve_exit_prices,
            )
            short_leg = _evaluate_backtest_leg(
                day=day,
                entry_date=entry_date,
                entry_idx=entry_idx,
                planned_exit_idx=planned_exit_idx,
                trade_dates=trade_dates,
                pred_col=pred_col,
                side="short",
                count=short_k_final,
                ascending=True,
                weighting_mode=weighting_mode,
                entry_price_table=entry_price_table,
                tradable_table=tradable_table,
                amount_tables=amount_tables,
                selection_constraints=selection_constraints,
                previous=short_state,
                buffer_exit=buffer_exit,
                buffer_entry=buffer_entry,
                group_col=group_col,
                max_names_per_group=max_names_per_group,
                cost_model=cost_model,
                slippage_model=slippage_model,
                resolve_exit_prices=_resolve_exit_prices,
            )
            if long_leg is None or short_leg is None:
                continue

            exit_idx = max(exit_idx, long_leg.exit_idx, short_leg.exit_idx)
            exit_date = trade_dates[exit_idx]
            gross = long_leg.gross + short_leg.gross
            fee_cost = long_leg.fee_cost + short_leg.fee_cost
            slippage_cost = long_leg.slippage_cost + short_leg.slippage_cost
            total_cost = fee_cost + slippage_cost
            net = gross - total_cost
            turnover = long_leg.turnover + short_leg.turnover

            long_state = _BacktestPositionState(
                holdings=set(long_leg.holdings),
                weights=long_leg.weights,
                entry_date=entry_date,
                entry_prices=long_leg.entry_prices,
            )
            short_state = _BacktestPositionState(
                holdings=set(short_leg.holdings),
                weights=short_leg.weights,
                entry_date=entry_date,
                entry_prices=short_leg.entry_prices,
            )

        gross_returns.append(gross)
        net_returns.append(net)
        turnovers.append(turnover)
        costs.append(total_cost)
        fee_costs.append(fee_cost)
        slippage_costs.append(slippage_cost)
        period_info.append(
            {
                "rebalance_date": reb_date,
                "entry_idx": entry_idx,
                "planned_exit_idx": planned_exit_idx,
                "exit_idx": exit_idx,
                "entry_date": entry_date,
                "planned_exit_date": planned_exit_date,
                "exit_date": exit_date,
                "exit_delay_steps": int(exit_idx - planned_exit_idx),
            }
        )
        prev_exit_idx = exit_idx

    if not net_returns:
        return None

    index = [info["exit_date"] for info in period_info]
    net_series = pd.Series(net_returns, index=index, name="net_return")
    gross_series = pd.Series(gross_returns, index=index, name="gross_return")
    turnover_series = pd.Series(turnovers, index=index, name="turnover")

    stats = summarize_period_returns(net_series, period_info, trading_days_per_year)
    avg_turnover = turnover_series.dropna().mean() if turnover_series.notna().any() else np.nan
    avg_cost = float(np.mean(costs)) if costs else np.nan
    avg_fee_cost = float(np.mean(fee_costs)) if fee_costs else np.nan
    avg_slippage_cost = float(np.mean(slippage_costs)) if slippage_costs else np.nan
    stats.update(
        {
            "avg_turnover": avg_turnover,
            "avg_cost_drag": avg_cost,
            "avg_fee_drag": avg_fee_cost,
            "avg_slippage_drag": avg_slippage_cost,
            "mode": "long_only" if long_only else "long_short",
            "weighting": weighting_mode,
            "long_k": int(top_k),
            "short_k": int(short_k) if (not long_only and short_k is not None) else None,
        }
    )
    return stats, net_series, gross_series, turnover_series, period_info
