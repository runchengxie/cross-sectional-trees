import pandas as pd
import pytest

from cstree.backtest import backtest_topk
from cstree.execution import build_execution_model
from cstree.execution_calendar import (
    is_execution_open,
    resolve_execution_date,
    resolve_execution_open_dates,
)
from cstree.liveops.alloc_hk import _enforce_stock_connect_execution_gate
from cstree.liveops.alloc_hk_types import HkAllocSettings
from cstree.portfolio import build_positions_by_rebalance


class FakeConnectCalendarRQ:
    def get_trading_dates(self, start_date, end_date, market="hk"):
        dates = pd.date_range(start_date, end_date, freq="D")
        if market == "hk":
            allowed = {"20260504", "20260505", "20260506"}
        elif market == "cn":
            allowed = {"20260506"}
        else:
            raise ValueError(f"unsupported market={market}")
        return [date for date in dates if date.strftime("%Y%m%d") in allowed]


def test_hk_connect_calendar_uses_hk_and_mainland_intersection():
    rq = FakeConnectCalendarRQ()

    open_dates = resolve_execution_open_dates(
        pd.Timestamp("2026-05-04"),
        pd.Timestamp("2026-05-06"),
        calendar="hk_connect",
        rqdatac_module=rq,
    )

    assert open_dates == [pd.Timestamp("2026-05-06")]
    assert not is_execution_open("2026-05-04", calendar="hk_connect", rqdatac_module=rq)
    assert is_execution_open("2026-05-06", calendar="hk_connect", rqdatac_module=rq)


def test_hk_connect_entry_date_can_resolve_future_open_day():
    rq = FakeConnectCalendarRQ()

    entry_date = resolve_execution_date(
        "2026-05-05",
        1,
        [pd.Timestamp("2026-05-04"), pd.Timestamp("2026-05-05")],
        calendar="hk_connect",
        rqdatac_module=rq,
        allow_future=True,
    )

    assert entry_date == pd.Timestamp("2026-05-06")


def test_live_position_builder_allows_explicit_future_entry_date():
    data = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2026-05-05", "2026-05-05"]),
            "symbol": ["00005.HK", "00700.HK"],
            "pred": [2.0, 1.0],
            "close": [50.0, 300.0],
        }
    )

    positions = build_positions_by_rebalance(
        data,
        pred_col="pred",
        price_col="close",
        rebalance_dates=[pd.Timestamp("2026-05-05")],
        top_k=1,
        shift_days=1,
        entry_dates_by_rebalance={
            pd.Timestamp("2026-05-05"): pd.Timestamp("2026-05-06")
        },
    )

    assert positions["rebalance_date"].tolist() == ["20260505"]
    assert positions["entry_date"].tolist() == ["20260506"]
    assert positions["symbol"].tolist() == ["00005.HK"]


def test_backtest_hk_connect_shift_uses_execution_calendar_closed_dates():
    dates = pd.to_datetime(
        ["2026-04-30", "2026-05-04", "2026-05-05", "2026-05-06", "2026-05-29", "2026-06-01"]
    )
    data = pd.DataFrame(
        {
            "trade_date": dates.repeat(2),
            "symbol": ["A", "B"] * len(dates),
            "pred": [2.0, 1.0] * len(dates),
            "close": [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 110.0, 90.0, 120.0, 80.0, 130.0, 70.0],
        }
    )
    execution = build_execution_model(
        {"calendar": "hk_connect", "closed_dates": ["20260504", "20260505"]},
        default_cost_bps=0,
        default_exit_price_policy="strict",
        default_exit_fallback_policy="ffill",
        default_price_col="close",
    )

    _, _, _, _, period_info = backtest_topk(
        data,
        pred_col="pred",
        price_col="close",
        rebalance_dates=[pd.Timestamp("2026-04-30"), pd.Timestamp("2026-05-29")],
        top_k=1,
        shift_days=1,
        cost_bps=0,
        trading_days_per_year=252,
        execution=execution,
    )

    assert period_info[0]["entry_date"] == pd.Timestamp("2026-05-06")


def test_alloc_hk_blocks_closed_stock_connect_execution_day():
    rq = FakeConnectCalendarRQ()
    settings = HkAllocSettings(require_stock_connect=True, execution_calendar="hk_connect")

    with pytest.raises(SystemExit, match="Stock Connect southbound execution calendar is closed"):
        _enforce_stock_connect_execution_gate(
            settings=settings,
            as_of=pd.Timestamp("2026-05-04"),
            entry_date=pd.Timestamp("2026-05-04"),
            rqdatac_module=rq,
            market="hk",
        )


def test_alloc_hk_allows_closed_day_when_explicitly_overridden():
    rq = FakeConnectCalendarRQ()
    settings = HkAllocSettings(
        require_stock_connect=True,
        execution_calendar="hk_connect",
        allow_connect_closed=True,
    )

    check_date, is_open = _enforce_stock_connect_execution_gate(
        settings=settings,
        as_of=pd.Timestamp("2026-05-04"),
        entry_date=pd.Timestamp("2026-05-04"),
        rqdatac_module=rq,
        market="hk",
    )

    assert check_date == pd.Timestamp("2026-05-04")
    assert is_open is False
