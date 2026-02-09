import numpy as np
import pandas as pd

from csml.rebalance import estimate_rebalance_gap, get_rebalance_dates


def test_get_rebalance_dates_month_end():
    dates = pd.to_datetime(
        ["2020-01-02", "2020-01-15", "2020-01-31", "2020-02-03", "2020-02-28"]
    )
    rebal = get_rebalance_dates(dates, "M")
    assert rebal == [pd.Timestamp("2020-01-31"), pd.Timestamp("2020-02-28")]


def test_estimate_rebalance_gap_median():
    trade_dates = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-06"])
    rebalance_dates = pd.to_datetime(["2020-01-01", "2020-01-03", "2020-01-06"])
    gap = estimate_rebalance_gap(trade_dates, rebalance_dates)
    assert np.isclose(gap, 2.0)
