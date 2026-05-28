from __future__ import annotations

from typing import Literal, Optional

import numpy as np
import pandas as pd

from ..execution import CostModel, ExecutionModel, SelectionConstraints, SlippageModel
from ..portfolio import (
    build_position_weights,
    normalize_position_weights,
    normalize_weighting_mode,
    select_holdings,
)
from .metrics import summarize_period_returns
from .periods import resolve_backtest_period_plan
from .pricing import (
    normalize_backtest_frame,
    prepare_backtest_pricing_context,
    resolve_backtest_execution_context,
    slippage_pricing_row,
)
from .types import BacktestLegResult, BacktestPositionState


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
    previous: BacktestPositionState,
    buffer_exit: int,
    buffer_entry: int,
    group_col: str | None,
    max_names_per_group: int | None,
    cost_model: CostModel,
    slippage_model: SlippageModel,
    resolve_exit_prices,
) -> BacktestLegResult | None:
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
        pricing_row=slippage_pricing_row(
            slippage_model=slippage_model,
            amount_tables=amount_tables,
            entry_date=entry_date,
        ),
        is_initial=previous.weights is None,
        side=side,
    )
    return BacktestLegResult(
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
    data = normalize_backtest_frame(data, context="Backtest data")
    pricing_data = normalize_backtest_frame(pricing_data, context="Backtest pricing data")
    execution_context = resolve_backtest_execution_context(
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
    pricing_context = prepare_backtest_pricing_context(
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
    long_state = BacktestPositionState()
    short_state = BacktestPositionState()
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
        period_plan = resolve_backtest_period_plan(
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
            long_state = BacktestPositionState(
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

            long_state = BacktestPositionState(
                holdings=set(long_leg.holdings),
                weights=long_leg.weights,
                entry_date=entry_date,
                entry_prices=long_leg.entry_prices,
            )
            short_state = BacktestPositionState(
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
