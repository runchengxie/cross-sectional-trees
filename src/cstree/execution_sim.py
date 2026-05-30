"""Order-level capacity execution simulation for rebalance targets."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np
import pandas as pd

SELL_UNTIL_NEXT_REBALANCE = "until_next_rebalance"


@dataclass(frozen=True)
class ExecutionSimConfig:
    enabled: bool = False
    portfolio_value: float = 1_000_000.0
    participation_rate: float = 0.05
    liquidity_cols: tuple[str, ...] = ("medadv20_amount", "amount")
    buy_max_days: int = 5
    sell_max_days: int | str = 10
    zero_fill_abort_days_buy: int | None = 5
    unfilled_buy_action: str = "keep_cash"
    unfilled_sell_action: str = "keep_position"


@dataclass(frozen=True)
class ExecutionSimResult:
    summary: dict[str, Any]
    orders: pd.DataFrame
    fills: pd.DataFrame


@dataclass(frozen=True)
class _ExecutionTables:
    trade_dates: list[pd.Timestamp]
    date_to_idx: dict[pd.Timestamp, int]
    price_table: pd.DataFrame
    tradable_table: pd.DataFrame | None
    liquidity_tables: dict[str, pd.DataFrame]


@dataclass(frozen=True)
class _OrderSink:
    order_rows: list[dict[str, Any]]
    fill_rows: list[dict[str, Any]]


def build_execution_sim_config(
    sim_cfg: object,
    *,
    default_portfolio_value: float = 1_000_000.0,
    default_liquidity_col: str = "medadv20_amount",
) -> ExecutionSimConfig:
    if sim_cfg is None:
        return ExecutionSimConfig(enabled=False)
    if isinstance(sim_cfg, bool):
        if not sim_cfg:
            return ExecutionSimConfig(enabled=False)
        sim_cfg = {"enabled": True}
    if not isinstance(sim_cfg, Mapping):
        raise ValueError("backtest.execution_sim must be a mapping or boolean.")

    enabled = bool(sim_cfg.get("enabled", False))
    if not enabled:
        return ExecutionSimConfig(enabled=False)

    portfolio_value = _coerce_positive_float(
        sim_cfg.get("portfolio_value", default_portfolio_value),
        label="execution_sim.portfolio_value",
    )
    participation_rate = _coerce_positive_float(
        sim_cfg.get("participation_rate", sim_cfg.get("participation", 0.05)),
        label="execution_sim.participation_rate",
    )
    liquidity_cols = _resolve_liquidity_cols(
        sim_cfg,
        default_liquidity_col=default_liquidity_col,
    )
    buy_max_days = _coerce_positive_int(
        sim_cfg.get("buy_max_days", 5),
        label="execution_sim.buy_max_days",
    )
    sell_max_days = _resolve_sell_max_days(sim_cfg.get("sell_max_days", 10))
    zero_fill_abort_days_buy_raw = sim_cfg.get("zero_fill_abort_days_buy", 5)
    if zero_fill_abort_days_buy_raw is None:
        zero_fill_abort_days_buy = None
    else:
        zero_fill_abort_days_buy = _coerce_positive_int(
            zero_fill_abort_days_buy_raw,
            label="execution_sim.zero_fill_abort_days_buy",
        )

    unfilled_buy_action = str(sim_cfg.get("unfilled_buy_action", "keep_cash")).strip().lower()
    if unfilled_buy_action != "keep_cash":
        raise ValueError("execution_sim.unfilled_buy_action must be 'keep_cash'.")
    unfilled_sell_action = str(
        sim_cfg.get("unfilled_sell_action", "keep_position")
    ).strip().lower()
    if unfilled_sell_action != "keep_position":
        raise ValueError("execution_sim.unfilled_sell_action must be 'keep_position'.")

    return ExecutionSimConfig(
        enabled=True,
        portfolio_value=portfolio_value,
        participation_rate=participation_rate,
        liquidity_cols=liquidity_cols,
        buy_max_days=buy_max_days,
        sell_max_days=sell_max_days,
        zero_fill_abort_days_buy=zero_fill_abort_days_buy,
        unfilled_buy_action=unfilled_buy_action,
        unfilled_sell_action=unfilled_sell_action,
    )


def required_execution_sim_columns(
    config: ExecutionSimConfig,
    *,
    price_col: str,
    tradable_col: str | None,
) -> set[str]:
    if not config.enabled:
        return set()
    columns = {str(price_col), *config.liquidity_cols}
    return {col for col in columns if col}


def describe_execution_sim_config(config: ExecutionSimConfig) -> dict[str, Any]:
    return {
        "enabled": bool(config.enabled),
        "portfolio_value": float(config.portfolio_value),
        "participation_rate": float(config.participation_rate),
        "liquidity_cols": list(config.liquidity_cols),
        "buy_max_days": int(config.buy_max_days),
        "sell_max_days": config.sell_max_days,
        "zero_fill_abort_days_buy": config.zero_fill_abort_days_buy,
        "unfilled_buy_action": config.unfilled_buy_action,
        "unfilled_sell_action": config.unfilled_sell_action,
    }


def simulate_capacity_execution(
    positions: pd.DataFrame | None,
    pricing_data: pd.DataFrame | None,
    config: ExecutionSimConfig,
    *,
    price_col: str,
    tradable_col: str | None = None,
) -> ExecutionSimResult:
    if not config.enabled:
        return _empty_result(config, status="disabled")
    if positions is None or positions.empty:
        return _empty_result(config, status="no_positions")
    if pricing_data is None or pricing_data.empty:
        return _empty_result(config, status="no_pricing_data")

    work_positions = positions.copy()
    if "side" in work_positions.columns:
        unsupported_side = work_positions["side"].astype(str).str.lower().eq("short").any()
        if unsupported_side:
            return _empty_result(config, status="skipped_long_short_not_supported")
    work_positions["weight"] = pd.to_numeric(work_positions["weight"], errors="coerce")
    if (work_positions["weight"] < 0).any():
        return _empty_result(config, status="skipped_negative_weights_not_supported")
    work_positions["rebalance_date"] = pd.to_datetime(
        work_positions["rebalance_date"], errors="coerce"
    )
    work_positions["entry_date"] = pd.to_datetime(work_positions["entry_date"], errors="coerce")
    work_positions = work_positions.dropna(subset=["rebalance_date", "entry_date", "symbol"])
    work_positions = work_positions[work_positions["weight"].notna()].copy()
    if work_positions.empty:
        return _empty_result(config, status="no_usable_positions")

    pricing = pricing_data.drop_duplicates(subset=["trade_date", "symbol"]).copy()
    pricing["trade_date"] = pd.to_datetime(pricing["trade_date"], errors="coerce")
    pricing = pricing.dropna(subset=["trade_date", "symbol"])
    required_cols = required_execution_sim_columns(
        config,
        price_col=price_col,
        tradable_col=tradable_col if tradable_col in pricing.columns else None,
    )
    missing_cols = sorted(col for col in required_cols if col not in pricing.columns)
    if missing_cols:
        return _empty_result(
            config,
            status="missing_pricing_columns",
            extra={"missing_pricing_columns": missing_cols},
        )

    execution_tables = _build_execution_tables(
        pricing,
        config,
        price_col=price_col,
        tradable_col=tradable_col,
    )
    if not execution_tables.trade_dates:
        return _empty_result(config, status="no_trade_dates")

    targets_by_rebalance = _build_targets_by_rebalance(work_positions)
    current_weights: dict[str, float] = {}
    cash_weight = 1.0
    order_rows: list[dict[str, Any]] = []
    fill_rows: list[dict[str, Any]] = []
    order_sink = _OrderSink(order_rows=order_rows, fill_rows=fill_rows)

    for idx, (rebalance_date, target_info) in enumerate(targets_by_rebalance):
        entry_date = target_info["entry_date"]
        if entry_date not in execution_tables.date_to_idx:
            continue
        next_entry_date = (
            targets_by_rebalance[idx + 1][1]["entry_date"]
            if idx + 1 < len(targets_by_rebalance)
            else None
        )
        target_weights = target_info["weights"]
        symbols = sorted(set(current_weights) | set(target_weights))
        deltas = {
            symbol: float(target_weights.get(symbol, 0.0) - current_weights.get(symbol, 0.0))
            for symbol in symbols
        }
        sell_requests = {symbol: -delta for symbol, delta in deltas.items() if delta < -1e-12}
        if sell_requests:
            cash_weight = _execute_sell_orders(
                rebalance_date=rebalance_date,
                entry_date=entry_date,
                next_entry_date=next_entry_date,
                requests=sell_requests,
                current_weights=current_weights,
                cash_weight=cash_weight,
                config=config,
                tables=execution_tables,
                sink=order_sink,
            )

        buy_requests = {
            symbol: max(
                float(target_weights.get(symbol, 0.0) - current_weights.get(symbol, 0.0)),
                0.0,
            )
            for symbol in target_weights
        }
        buy_requests = {symbol: amount for symbol, amount in buy_requests.items() if amount > 1e-12}
        if buy_requests:
            cash_weight = _execute_buy_orders(
                rebalance_date=rebalance_date,
                entry_date=entry_date,
                requests=buy_requests,
                current_weights=current_weights,
                cash_weight=cash_weight,
                config=config,
                tables=execution_tables,
                sink=order_sink,
            )

    orders = pd.DataFrame(order_rows, columns=_order_columns())
    fills = pd.DataFrame(fill_rows, columns=_fill_columns())
    summary = _summarize_orders(
        config,
        orders,
        rebalances=len(targets_by_rebalance),
        final_cash_weight=cash_weight,
        final_invested_weight=sum(current_weights.values()),
        status="ok",
    )
    return ExecutionSimResult(summary=summary, orders=orders, fills=fills)


def _build_execution_tables(
    pricing: pd.DataFrame,
    config: ExecutionSimConfig,
    *,
    price_col: str,
    tradable_col: str | None,
) -> _ExecutionTables:
    trade_dates = sorted(pd.to_datetime(pricing["trade_date"].unique()))
    date_to_idx = {date: idx for idx, date in enumerate(trade_dates)}
    price_table = pricing.pivot(index="trade_date", columns="symbol", values=price_col)
    tradable_table = _build_tradable_table(pricing, tradable_col)
    liquidity_tables = {
        col: pricing.pivot(index="trade_date", columns="symbol", values=col)
        for col in config.liquidity_cols
    }
    return _ExecutionTables(
        trade_dates=trade_dates,
        date_to_idx=date_to_idx,
        price_table=price_table,
        tradable_table=tradable_table,
        liquidity_tables=liquidity_tables,
    )


def _build_tradable_table(
    pricing: pd.DataFrame,
    tradable_col: str | None,
) -> pd.DataFrame | None:
    if not tradable_col or tradable_col not in pricing.columns:
        return None
    return (
        pricing.pivot(index="trade_date", columns="symbol", values=tradable_col)
        .fillna(False)
        .astype(bool)
    )


def _execute_sell_orders(
    *,
    rebalance_date: pd.Timestamp,
    entry_date: pd.Timestamp,
    next_entry_date: pd.Timestamp | None,
    requests: dict[str, float],
    current_weights: dict[str, float],
    cash_weight: float,
    config: ExecutionSimConfig,
    tables: _ExecutionTables,
    sink: _OrderSink,
) -> float:
    remaining = dict(requests)
    states = _build_order_states(requests)
    window_dates = _execution_window_dates(
        entry_date,
        max_days=config.sell_max_days,
        next_entry_date=next_entry_date,
        trade_dates=tables.trade_dates,
        date_to_idx=tables.date_to_idx,
    )
    for day_number, trade_date in enumerate(window_dates, start=1):
        for symbol in sorted(list(remaining)):
            before = remaining[symbol]
            capacity = _capacity_weight(
                symbol,
                trade_date,
                config=config,
                price_table=tables.price_table,
                tradable_table=tables.tradable_table,
                liquidity_tables=tables.liquidity_tables,
            )
            fill = min(before, capacity)
            if fill > 1e-12:
                remaining[symbol] = max(before - fill, 0.0)
                current_weights[symbol] = max(current_weights.get(symbol, 0.0) - fill, 0.0)
                if current_weights[symbol] <= 1e-12:
                    current_weights.pop(symbol, None)
                cash_weight += fill
                _record_fill(
                    sink.fill_rows,
                    rebalance_date=rebalance_date,
                    entry_date=entry_date,
                    trade_date=trade_date,
                    day_number=day_number,
                    side="sell",
                    symbol=symbol,
                    remaining_before=before,
                    capacity=capacity,
                    fill=fill,
                    config=config,
                )
                _update_state(states[symbol], trade_date, fill)
            if remaining.get(symbol, 0.0) <= 1e-12:
                remaining.pop(symbol, None)
        if not remaining:
            break
    _append_order_rows(
        sink.order_rows,
        rebalance_date=rebalance_date,
        entry_date=entry_date,
        side="sell",
        requests=requests,
        remaining=remaining,
        states=states,
        max_days=len(window_dates),
        config=config,
        unfilled_status="delayed_sell",
    )
    return cash_weight


def _execute_buy_orders(
    *,
    rebalance_date: pd.Timestamp,
    entry_date: pd.Timestamp,
    requests: dict[str, float],
    current_weights: dict[str, float],
    cash_weight: float,
    config: ExecutionSimConfig,
    tables: _ExecutionTables,
    sink: _OrderSink,
) -> float:
    remaining = dict(requests)
    states = _build_order_states(requests)
    abandoned: set[str] = set()
    window_dates = _execution_window_dates(
        entry_date,
        max_days=config.buy_max_days,
        next_entry_date=None,
        trade_dates=tables.trade_dates,
        date_to_idx=tables.date_to_idx,
    )
    for day_number, trade_date in enumerate(window_dates, start=1):
        daily_fills: dict[str, tuple[float, float]] = {}
        for symbol in sorted(list(remaining)):
            if symbol in abandoned:
                continue
            before = remaining[symbol]
            capacity = _capacity_weight(
                symbol,
                trade_date,
                config=config,
                price_table=tables.price_table,
                tradable_table=tables.tradable_table,
                liquidity_tables=tables.liquidity_tables,
            )
            fill = min(before, capacity)
            daily_fills[symbol] = (capacity, fill)

        total_requested_fill = sum(fill for _, fill in daily_fills.values())
        scale = 1.0
        if total_requested_fill > max(cash_weight, 0.0) and total_requested_fill > 0:
            scale = max(cash_weight, 0.0) / total_requested_fill

        for symbol in sorted(list(remaining)):
            if symbol in abandoned:
                continue
            before = remaining[symbol]
            capacity, raw_fill = daily_fills.get(symbol, (0.0, 0.0))
            fill = min(before, raw_fill * scale)
            if fill > 1e-12:
                remaining[symbol] = max(before - fill, 0.0)
                current_weights[symbol] = current_weights.get(symbol, 0.0) + fill
                cash_weight = max(cash_weight - fill, 0.0)
                _record_fill(
                    sink.fill_rows,
                    rebalance_date=rebalance_date,
                    entry_date=entry_date,
                    trade_date=trade_date,
                    day_number=day_number,
                    side="buy",
                    symbol=symbol,
                    remaining_before=before,
                    capacity=capacity,
                    fill=fill,
                    config=config,
                )
                _update_state(states[symbol], trade_date, fill)
                states[symbol]["zero_fill_days"] = 0
            else:
                if capacity <= 1e-12:
                    states[symbol]["zero_fill_days"] += 1
                    if (
                        config.zero_fill_abort_days_buy is not None
                        and states[symbol]["zero_fill_days"] >= config.zero_fill_abort_days_buy
                    ):
                        abandoned.add(symbol)
            if remaining.get(symbol, 0.0) <= 1e-12:
                remaining.pop(symbol, None)
        if not remaining:
            break
        if set(remaining).issubset(abandoned):
            break

    _append_order_rows(
        sink.order_rows,
        rebalance_date=rebalance_date,
        entry_date=entry_date,
        side="buy",
        requests=requests,
        remaining=remaining,
        states=states,
        max_days=len(window_dates),
        config=config,
        unfilled_status="cancelled_buy_deadline",
        abandoned=abandoned,
    )
    return cash_weight


def _execution_window_dates(
    entry_date: pd.Timestamp,
    *,
    max_days: int | str,
    next_entry_date: pd.Timestamp | None,
    trade_dates: list[pd.Timestamp],
    date_to_idx: dict[pd.Timestamp, int],
) -> list[pd.Timestamp]:
    if entry_date not in date_to_idx:
        return []
    start_idx = date_to_idx[entry_date]
    if max_days == SELL_UNTIL_NEXT_REBALANCE:
        if next_entry_date is not None and next_entry_date in date_to_idx:
            end_idx = max(start_idx + 1, date_to_idx[next_entry_date])
        else:
            end_idx = len(trade_dates)
        return trade_dates[start_idx:min(end_idx, len(trade_dates))]

    end_idx = min(start_idx + int(max_days), len(trade_dates))
    return trade_dates[start_idx:end_idx]


def _capacity_weight(
    symbol: str,
    trade_date: pd.Timestamp,
    *,
    config: ExecutionSimConfig,
    price_table: pd.DataFrame,
    tradable_table: pd.DataFrame | None,
    liquidity_tables: dict[str, pd.DataFrame],
) -> float:
    if trade_date not in price_table.index:
        return 0.0
    price = pd.to_numeric(pd.Series([price_table.loc[trade_date].get(symbol, np.nan)]), errors="coerce").iloc[0]
    if not np.isfinite(price) or price <= 0:
        return 0.0
    if tradable_table is not None:
        if trade_date not in tradable_table.index:
            return 0.0
        if not bool(tradable_table.loc[trade_date].get(symbol, False)):
            return 0.0

    liquidity_values: list[float] = []
    for column in config.liquidity_cols:
        table = liquidity_tables.get(column)
        if table is None or trade_date not in table.index:
            return 0.0
        value = pd.to_numeric(pd.Series([table.loc[trade_date].get(symbol, np.nan)]), errors="coerce").iloc[0]
        if not np.isfinite(value) or value <= 0:
            return 0.0
        liquidity_values.append(float(value))
    if not liquidity_values:
        return 0.0
    liquidity = min(liquidity_values)
    notional = float(config.participation_rate) * liquidity
    return max(notional / float(config.portfolio_value), 0.0)


def _build_targets_by_rebalance(
    positions: pd.DataFrame,
) -> list[tuple[pd.Timestamp, dict[str, Any]]]:
    grouped = []
    for rebalance_date, group in positions.groupby("rebalance_date", sort=True):
        entry_date = pd.to_datetime(group["entry_date"].iloc[0])
        weights = (
            group.groupby("symbol")["weight"]
            .sum()
            .astype(float)
            .loc[lambda series: series > 0]
            .to_dict()
        )
        grouped.append((pd.to_datetime(rebalance_date), {"entry_date": entry_date, "weights": weights}))
    return grouped


def _build_order_states(requests: dict[str, float]) -> dict[str, dict[str, Any]]:
    return {
        symbol: {
            "requested": float(amount),
            "filled": 0.0,
            "first_fill_date": None,
            "last_fill_date": None,
            "fill_days": 0,
            "zero_fill_days": 0,
        }
        for symbol, amount in requests.items()
    }


def _update_state(state: dict[str, Any], trade_date: pd.Timestamp, fill: float) -> None:
    state["filled"] += float(fill)
    if state["first_fill_date"] is None:
        state["first_fill_date"] = trade_date
    state["last_fill_date"] = trade_date
    state["fill_days"] += 1


def _append_order_rows(
    order_rows: list[dict[str, Any]],
    *,
    rebalance_date: pd.Timestamp,
    entry_date: pd.Timestamp,
    side: str,
    requests: dict[str, float],
    remaining: dict[str, float],
    states: dict[str, dict[str, Any]],
    max_days: int,
    config: ExecutionSimConfig,
    unfilled_status: str,
    abandoned: set[str] | None = None,
) -> None:
    abandoned = abandoned or set()
    for symbol in sorted(requests):
        state = states[symbol]
        requested = float(requests[symbol])
        filled = min(float(state["filled"]), requested)
        unfilled = max(float(remaining.get(symbol, 0.0)), 0.0)
        if unfilled <= 1e-12:
            status = "filled"
        elif symbol in abandoned:
            status = "abandoned_zero_fill"
        else:
            status = unfilled_status
        order_rows.append(
            {
                "rebalance_date": _format_date(rebalance_date),
                "entry_date": _format_date(entry_date),
                "side": side,
                "symbol": symbol,
                "requested_weight": requested,
                "filled_weight": filled,
                "unfilled_weight": unfilled,
                "requested_notional": requested * config.portfolio_value,
                "filled_notional": filled * config.portfolio_value,
                "unfilled_notional": unfilled * config.portfolio_value,
                "fill_ratio": filled / requested if requested > 0 else np.nan,
                "status": status,
                "first_fill_date": _format_date(state["first_fill_date"]),
                "last_fill_date": _format_date(state["last_fill_date"]),
                "fill_days": int(state["fill_days"]),
                "max_days": int(max_days),
                "zero_fill_days": int(state["zero_fill_days"]),
                "participation_rate": float(config.participation_rate),
            }
        )


def _record_fill(
    fill_rows: list[dict[str, Any]],
    *,
    rebalance_date: pd.Timestamp,
    entry_date: pd.Timestamp,
    trade_date: pd.Timestamp,
    day_number: int,
    side: str,
    symbol: str,
    remaining_before: float,
    capacity: float,
    fill: float,
    config: ExecutionSimConfig,
) -> None:
    fill_rows.append(
        {
            "rebalance_date": _format_date(rebalance_date),
            "entry_date": _format_date(entry_date),
            "trade_date": _format_date(trade_date),
            "day_number": int(day_number),
            "side": side,
            "symbol": symbol,
            "remaining_before_weight": float(remaining_before),
            "capacity_weight": float(capacity),
            "filled_weight": float(fill),
            "capacity_notional": float(capacity) * config.portfolio_value,
            "filled_notional": float(fill) * config.portfolio_value,
        }
    )


def _summarize_orders(
    config: ExecutionSimConfig,
    orders: pd.DataFrame,
    *,
    rebalances: int,
    final_cash_weight: float,
    final_invested_weight: float,
    status: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "enabled": bool(config.enabled),
        "status": status,
        "config": describe_execution_sim_config(config),
        "rebalances": int(rebalances),
        "orders": int(orders.shape[0]),
        "final_cash_weight": float(final_cash_weight),
        "final_invested_weight": float(final_invested_weight),
    }
    if orders.empty:
        summary.update(
            {
                "requested_notional": 0.0,
                "filled_notional": 0.0,
                "unfilled_notional": 0.0,
                "fill_ratio": np.nan,
                "buy_fill_ratio": np.nan,
                "sell_fill_ratio": np.nan,
                "unfilled_buy_notional": 0.0,
                "unfilled_sell_notional": 0.0,
                "abandoned_buy_orders": 0,
                "delayed_sell_orders": 0,
            }
        )
    else:
        requested = float(orders["requested_notional"].sum())
        filled = float(orders["filled_notional"].sum())
        unfilled = float(orders["unfilled_notional"].sum())
        buy_orders = orders[orders["side"] == "buy"]
        sell_orders = orders[orders["side"] == "sell"]
        summary.update(
            {
                "requested_notional": requested,
                "filled_notional": filled,
                "unfilled_notional": unfilled,
                "fill_ratio": filled / requested if requested > 0 else np.nan,
                "buy_fill_ratio": _side_fill_ratio(buy_orders),
                "sell_fill_ratio": _side_fill_ratio(sell_orders),
                "unfilled_buy_notional": float(buy_orders["unfilled_notional"].sum())
                if not buy_orders.empty
                else 0.0,
                "unfilled_sell_notional": float(sell_orders["unfilled_notional"].sum())
                if not sell_orders.empty
                else 0.0,
                "abandoned_buy_orders": int(
                    (buy_orders["status"] == "abandoned_zero_fill").sum()
                )
                if not buy_orders.empty
                else 0,
                "delayed_sell_orders": int((sell_orders["status"] == "delayed_sell").sum())
                if not sell_orders.empty
                else 0,
            }
        )
    if extra:
        summary.update(extra)
    return summary


def _empty_result(
    config: ExecutionSimConfig,
    *,
    status: str,
    extra: dict[str, Any] | None = None,
) -> ExecutionSimResult:
    orders = pd.DataFrame(columns=_order_columns())
    fills = pd.DataFrame(columns=_fill_columns())
    summary = _summarize_orders(
        config,
        orders,
        rebalances=0,
        final_cash_weight=1.0,
        final_invested_weight=0.0,
        status=status,
        extra=extra,
    )
    return ExecutionSimResult(summary=summary, orders=orders, fills=fills)


def _side_fill_ratio(frame: pd.DataFrame) -> float:
    if frame.empty:
        return np.nan
    requested = float(frame["requested_notional"].sum())
    if requested <= 0:
        return np.nan
    return float(frame["filled_notional"].sum()) / requested


def _resolve_liquidity_cols(
    cfg: Mapping[str, Any],
    *,
    default_liquidity_col: str,
) -> tuple[str, ...]:
    raw_cols = cfg.get("liquidity_cols")
    if raw_cols is None:
        raw_cols = [cfg.get("liquidity_col", default_liquidity_col)]
    elif isinstance(raw_cols, str):
        raw_cols = [raw_cols]
    else:
        raw_cols = list(raw_cols)

    if bool(cfg.get("cap_daily_amount", True)):
        daily_col = str(cfg.get("daily_amount_col", "amount")).strip()
        if daily_col:
            raw_cols.append(daily_col)

    cols = [str(col).strip() for col in raw_cols if str(col).strip()]
    cols = list(dict.fromkeys(cols))
    if not cols:
        raise ValueError("execution_sim.liquidity_cols must not be empty.")
    return tuple(cols)


def _resolve_sell_max_days(value: object) -> int | str:
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {SELL_UNTIL_NEXT_REBALANCE, "until_next", "next_rebalance"}:
            return SELL_UNTIL_NEXT_REBALANCE
    return _coerce_positive_int(value, label="execution_sim.sell_max_days")


def _coerce_positive_float(value: object, *, label: str) -> float:
    number = float(value)
    if not np.isfinite(number) or number <= 0:
        raise ValueError(f"{label} must be > 0.")
    return number


def _coerce_positive_int(value: object, *, label: str) -> int:
    number = int(value)
    if number <= 0:
        raise ValueError(f"{label} must be a positive integer.")
    return number


def _format_date(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.to_datetime(value).strftime("%Y%m%d")


def _order_columns() -> list[str]:
    return [
        "rebalance_date",
        "entry_date",
        "side",
        "symbol",
        "requested_weight",
        "filled_weight",
        "unfilled_weight",
        "requested_notional",
        "filled_notional",
        "unfilled_notional",
        "fill_ratio",
        "status",
        "first_fill_date",
        "last_fill_date",
        "fill_days",
        "max_days",
        "zero_fill_days",
        "participation_rate",
    ]


def _fill_columns() -> list[str]:
    return [
        "rebalance_date",
        "entry_date",
        "trade_date",
        "day_number",
        "side",
        "symbol",
        "remaining_before_weight",
        "capacity_weight",
        "filled_weight",
        "capacity_notional",
        "filled_notional",
    ]
