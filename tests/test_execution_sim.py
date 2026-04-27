import numpy as np
import pandas as pd
import pytest

from cstree.execution_sim import (
    ExecutionSimConfig,
    build_execution_sim_config,
    required_execution_sim_columns,
    simulate_capacity_execution,
)


def _pricing_frame(dates, symbols, *, amount_map=None, tradable_map=None):
    rows = []
    amount_map = amount_map or {}
    tradable_map = tradable_map or {}
    for date in pd.to_datetime(dates):
        for symbol in symbols:
            amount = float(amount_map.get((symbol, date.strftime("%Y%m%d")), 500_000.0))
            rows.append(
                {
                    "trade_date": date,
                    "symbol": symbol,
                    "open": 10.0,
                    "amount": amount,
                    "medadv20_amount": amount,
                    "is_tradable": bool(tradable_map.get((symbol, date.strftime("%Y%m%d")), amount > 0)),
                }
            )
    return pd.DataFrame(rows)


def test_capacity_execution_partially_fills_buy_deadline():
    dates = pd.date_range("2020-01-01", periods=7, freq="B")
    positions = pd.DataFrame(
        {
            "rebalance_date": ["20200101", "20200101"],
            "entry_date": ["20200102", "20200102"],
            "symbol": ["AAA", "BBB"],
            "weight": [0.10, 0.10],
            "side": ["long", "long"],
        }
    )
    amount_map = {}
    for date in dates:
        amount_map[("AAA", date.strftime("%Y%m%d"))] = 500_000.0
        amount_map[("BBB", date.strftime("%Y%m%d"))] = 100_000.0
    pricing = _pricing_frame(dates, ["AAA", "BBB"], amount_map=amount_map)
    config = ExecutionSimConfig(
        enabled=True,
        portfolio_value=1_000_000.0,
        participation_rate=0.05,
        liquidity_cols=("medadv20_amount", "amount"),
        buy_max_days=5,
    )

    result = simulate_capacity_execution(
        positions,
        pricing,
        config,
        price_col="open",
        tradable_col="is_tradable",
    )

    orders = result.orders.set_index("symbol")
    assert orders.loc["AAA", "status"] == "filled"
    assert orders.loc["AAA", "filled_weight"] == pytest.approx(0.10)
    assert orders.loc["BBB", "status"] == "cancelled_buy_deadline"
    assert orders.loc["BBB", "filled_weight"] == pytest.approx(0.025)
    assert result.summary["unfilled_buy_notional"] == pytest.approx(75_000.0)


def test_capacity_execution_abandons_zero_fill_buy_after_threshold():
    dates = pd.date_range("2020-01-01", periods=7, freq="B")
    positions = pd.DataFrame(
        {
            "rebalance_date": ["20200101"],
            "entry_date": ["20200102"],
            "symbol": ["AAA"],
            "weight": [0.10],
            "side": ["long"],
        }
    )
    amount_map = {("AAA", date.strftime("%Y%m%d")): 0.0 for date in dates}
    pricing = _pricing_frame(dates, ["AAA"], amount_map=amount_map)
    config = ExecutionSimConfig(
        enabled=True,
        portfolio_value=1_000_000.0,
        participation_rate=0.05,
        liquidity_cols=("medadv20_amount", "amount"),
        buy_max_days=5,
        zero_fill_abort_days_buy=3,
    )

    result = simulate_capacity_execution(
        positions,
        pricing,
        config,
        price_col="open",
        tradable_col="is_tradable",
    )

    assert result.orders.loc[0, "status"] == "abandoned_zero_fill"
    assert result.orders.loc[0, "zero_fill_days"] == 3
    assert result.orders.loc[0, "filled_weight"] == 0.0
    assert result.summary["abandoned_buy_orders"] == 1
    assert result.fills.empty


def test_capacity_execution_keeps_unfilled_sell_as_delayed_exit():
    dates = pd.date_range("2020-01-01", periods=9, freq="B")
    positions = pd.DataFrame(
        {
            "rebalance_date": ["20200101", "20200106"],
            "entry_date": ["20200102", "20200107"],
            "symbol": ["AAA", "BBB"],
            "weight": [0.20, 0.20],
            "side": ["long", "long"],
        }
    )
    amount_map = {}
    for date in dates:
        amount_map[("AAA", date.strftime("%Y%m%d"))] = 2_000_000.0
        amount_map[("BBB", date.strftime("%Y%m%d"))] = 2_000_000.0
    for date in dates[4:]:
        amount_map[("AAA", date.strftime("%Y%m%d"))] = 0.0
    pricing = _pricing_frame(dates, ["AAA", "BBB"], amount_map=amount_map)
    config = ExecutionSimConfig(
        enabled=True,
        portfolio_value=1_000_000.0,
        participation_rate=0.10,
        liquidity_cols=("medadv20_amount", "amount"),
        buy_max_days=2,
        sell_max_days=2,
    )

    result = simulate_capacity_execution(
        positions,
        pricing,
        config,
        price_col="open",
        tradable_col="is_tradable",
    )

    sell_orders = result.orders[result.orders["side"] == "sell"]
    assert sell_orders.shape[0] == 1
    assert sell_orders.iloc[0]["symbol"] == "AAA"
    assert sell_orders.iloc[0]["status"] == "delayed_sell"
    assert sell_orders.iloc[0]["unfilled_weight"] == pytest.approx(0.20)
    assert result.summary["delayed_sell_orders"] == 1


def test_build_execution_sim_config_defaults_to_daily_amount_cap():
    config = build_execution_sim_config(
        {"enabled": True, "liquidity_col": "medadv60_amount"},
        default_portfolio_value=2_000_000.0,
        default_liquidity_col="adv20_amount",
    )

    assert config.portfolio_value == pytest.approx(2_000_000.0)
    assert config.liquidity_cols == ("medadv60_amount", "amount")
    assert required_execution_sim_columns(
        config,
        price_col="open",
        tradable_col="is_tradable",
    ) == {"open", "medadv60_amount", "amount"}


def test_capacity_execution_skips_long_short_targets():
    positions = pd.DataFrame(
        {
            "rebalance_date": ["20200101"],
            "entry_date": ["20200102"],
            "symbol": ["AAA"],
            "weight": [-0.10],
            "side": ["short"],
        }
    )
    pricing = _pricing_frame(pd.date_range("2020-01-01", periods=3, freq="B"), ["AAA"])

    result = simulate_capacity_execution(
        positions,
        pricing,
        ExecutionSimConfig(enabled=True),
        price_col="open",
    )

    assert result.summary["status"] == "skipped_long_short_not_supported"
    assert np.isnan(result.summary["fill_ratio"])
