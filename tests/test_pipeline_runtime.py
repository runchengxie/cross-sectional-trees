import numpy as np
import pandas as pd

import cstree.pipeline as pipeline_pkg
from cstree.pipeline import runner as pipeline_runner
from cstree.pipeline.dates import _build_trade_date_slices
from cstree.pipeline.runtime import _prepare_split_context


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


def test_resolve_train_eval_service_hooks_prefers_package_monkeypatch(monkeypatch):
    def fake_backtest_topk(*args, **kwargs):
        return None

    def fake_bucket_ic_summary(*args, **kwargs):
        return None

    monkeypatch.setattr(pipeline_pkg, "backtest_topk", fake_backtest_topk)
    monkeypatch.setattr(pipeline_pkg, "bucket_ic_summary", fake_bucket_ic_summary)

    backtest_topk_fn, bucket_ic_summary_fn = pipeline_runner._resolve_train_eval_service_hooks()

    assert backtest_topk_fn is fake_backtest_topk
    assert bucket_ic_summary_fn is fake_bucket_ic_summary


def test_attach_benchmark_compare_frames_adds_symbol_frames_without_mutating_specs():
    specs = [
        {"source_type": "symbol", "symbol": "02800.HK"},
        {"source_type": "file", "name": "local"},
    ]
    benchmark_frame = pd.DataFrame({"trade_date": ["2024-01-31"], "benchmark_return": [0.01]})

    resolved = pipeline_runner._attach_benchmark_compare_frames(
        specs,
        {"02800.HK": benchmark_frame},
    )

    assert resolved[0]["benchmark_df"].equals(benchmark_frame)
    assert resolved[0]["series"].empty
    assert resolved[1] == specs[1]
    assert "benchmark_df" not in specs[0]
