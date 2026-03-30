import numpy as np
import pandas as pd

from csml.pipeline.dates import _build_trade_date_slices
from csml.pipeline.runtime import _prepare_split_context


def test_prepare_split_context_uses_reference_trade_calendar_for_rebalance_gap():
    reference_trade_dates = pd.date_range("2024-01-01", "2025-03-31", freq="B").to_numpy()
    model_dates = pd.date_range("2024-01-31", periods=14, freq="BME")
    frame = pd.DataFrame(
        {
            "trade_date": np.repeat(model_dates, 2),
            "symbol": ["AAA", "BBB"] * len(model_dates),
            "feature": 1.0,
            "target": 0.0,
        }
    )
    (
        df_model_all_sorted,
        all_dates_model_full,
        model_date_start_rows,
        model_date_end_rows,
        model_date_to_pos,
    ) = _build_trade_date_slices(frame)

    split_state = _prepare_split_context(
        df_model_all_sorted=df_model_all_sorted,
        all_dates_model_full=all_dates_model_full,
        model_date_start_rows=model_date_start_rows,
        model_date_end_rows=model_date_end_rows,
        model_date_to_pos=model_date_to_pos,
        reference_trade_dates=reference_trade_dates,
        sample_on_rebalance_dates=True,
        df_model_all=df_model_all_sorted,
        all_dates_full=all_dates_model_full,
        label_horizon_days=42,
        label_horizon_mode="fixed",
        label_horizon_gap=None,
        label_shift_days=0,
        purge_days_cfg=None,
        embargo_days_cfg=21,
        test_size=0.5,
        final_oos_enabled=False,
        final_oos_size_raw=None,
        train_window_mode="expanding",
        train_window_size=None,
        train_window_unit="dates",
    )

    assert split_state["rebalance_gap_days"] >= 20
    assert split_state["purge_steps"] == 2
    assert split_state["embargo_steps"] == 1
    assert len(split_state["train_dates_full"]) == 5
    assert len(split_state["test_dates"]) == 7
