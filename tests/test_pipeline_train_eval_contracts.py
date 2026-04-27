import numpy as np
import pandas as pd
import pytest

from cstree.pipeline import train_eval_stage
from cstree.pipeline.contracts import (
    TrainEvalBacktestSettings,
    TrainEvalData,
    TrainEvalFeatureTarget,
    TrainEvalLiveSettings,
    TrainEvalModelSettings,
    TrainEvalPeriodSettings,
    TrainEvalRequest,
    TrainEvalServices,
    TrainEvalSignalSettings,
    TrainEvalWalkForwardSettings,
)


def _request() -> TrainEvalRequest:
    dates = pd.to_datetime(["2020-01-01", "2020-01-02"])
    frame = pd.DataFrame(
        {
            "trade_date": dates,
            "symbol": ["A", "B"],
            "f1": [0.0, 1.0],
            "target": [0.0, 1.0],
        }
    )
    return TrainEvalRequest(
        data=TrainEvalData(
            train_df=frame,
            test_df=frame,
            test_dates=dates.to_numpy(),
            df_features=frame,
            df_full=frame,
            df_model_sorted=frame,
            all_dates=dates.to_numpy(),
            all_date_start_rows=np.array([0, 1]),
            all_date_end_rows=np.array([1, 2]),
            all_date_to_pos={pd.Timestamp("2020-01-01"): 0},
            valid_dates_set={pd.Timestamp("2020-01-01")},
            backtest_pricing_df=frame,
            benchmark_df=None,
            benchmark_return_series=pd.Series(dtype=float),
            industry_source_df=pd.DataFrame(),
            passthrough_cols=[],
            industry_keep_columns=[],
            price_passthrough_cols=[],
            bucket_cols=[],
        ),
        feature_target=TrainEvalFeatureTarget(
            features=["f1"],
            target="target",
            train_target="target",
            price_col="close",
            fundamentals_mcap_col="market_cap",
        ),
        model=TrainEvalModelSettings(
            model_type="ridge",
            model_params={"alpha": 1.0},
            model_cfg={"type": "ridge", "params": {"alpha": 1.0}},
            sample_weight_mode="none",
            sample_weight_params={},
            n_splits=2,
            embargo_steps=0,
            purge_steps=0,
            train_window_mode="full",
            train_window_size=None,
            train_window_unit="dates",
        ),
        signal=TrainEvalSignalSettings(
            signal_direction_mode="fixed",
            signal_direction=1.0,
            min_abs_ic_to_flip=0.0,
            score_postprocess_method="none",
            score_postprocess_columns=[],
            score_postprocess_strength=1.0,
            score_postprocess_min_obs=5,
            report_train_ic=True,
        ),
        live=TrainEvalLiveSettings(
            live_enabled=False,
            live_as_of=None,
            market="hk",
            provider="rqdata",
            live_train_mode="full",
            min_symbols_per_date=1,
        ),
        backtest=TrainEvalBacktestSettings(
            backtest_top_k=1,
            label_shift_days=1,
            backtest_weighting="equal",
            backtest_buffer_exit=0,
            backtest_buffer_entry=0,
            backtest_long_only=True,
            backtest_short_k=None,
            backtest_tradable_col=None,
            backtest_group_col=None,
            backtest_max_names_per_group=None,
            execution_model={},
            execution_sim_config={},
            backtest_rebalance_frequency="D",
            backtest_enabled=False,
            backtest_signal_direction_raw=None,
            backtest_cost_bps_effective=0.0,
            backtest_trading_days_per_year=252,
            backtest_exit_mode="rebalance",
            backtest_exit_horizon_days=1,
            backtest_exit_price_policy="strict",
            backtest_exit_fallback_policy="none",
        ),
        period=TrainEvalPeriodSettings(
            rebalance_frequency="D",
            sample_on_rebalance_dates=False,
            perm_test_runs=1,
            perm_test_seed=None,
            label_horizon_mode="fixed",
            label_horizon_effective=1,
            n_quantiles=2,
            top_k=1,
            eval_buffer_exit=0,
            eval_buffer_entry=0,
            transaction_cost_bps=0.0,
            bucket_ic_enabled=False,
            bucket_ic_schemes=[],
            bucket_ic_method="spearman",
            bucket_ic_min_count=0,
            rolling_windows_months=[],
        ),
        walk_forward=TrainEvalWalkForwardSettings(
            wf_enabled=False,
            wf_n_windows=0,
            wf_test_size=None,
            wf_step_size=None,
            effective_gap_steps=0,
            wf_anchor_end=True,
            wf_feature_top_k=1,
            wf_backtest_enabled=False,
            wf_perm_test_enabled=False,
            wf_perm_test_runs=1,
            wf_perm_test_seed=None,
        ),
        services=TrainEvalServices(
            backtest_topk_fn=lambda *args, **kwargs: None,
            bucket_ic_summary_fn=lambda *args, **kwargs: None,
        ),
    )


def test_train_eval_request_flattens_to_legacy_kwargs():
    kwargs = _request().to_kwargs()

    assert kwargs["features"] == ["f1"]
    assert kwargs["model_type"] == "ridge"
    assert kwargs["backtest_enabled"] is False
    assert kwargs["wf_enabled"] is False
    assert kwargs["valid_dates_set"] == {pd.Timestamp("2020-01-01")}


def test_run_train_eval_stage_accepts_contract_request(monkeypatch):
    captured = {}

    def _fake_impl(request):
        captured.update(request.to_kwargs())
        return {"ok": True}

    monkeypatch.setattr(train_eval_stage, "_run_train_eval_stage_impl", _fake_impl)

    assert train_eval_stage.run_train_eval_stage(request=_request()) == {"ok": True}
    assert captured["features"] == ["f1"]
    assert captured["model_type"] == "ridge"


def test_run_train_eval_stage_accepts_legacy_kwargs(monkeypatch):
    captured = {}

    def _fake_impl(request):
        captured.update(request.to_kwargs())
        return {"ok": True}

    monkeypatch.setattr(train_eval_stage, "_run_train_eval_stage_impl", _fake_impl)

    assert train_eval_stage.run_train_eval_stage(**_request().to_kwargs()) == {"ok": True}
    assert captured["features"] == ["f1"]
    assert captured["model_type"] == "ridge"


def test_run_train_eval_stage_rejects_mixed_request_and_kwargs():
    with pytest.raises(TypeError, match="either request or keyword"):
        train_eval_stage.run_train_eval_stage(request=_request(), train_df=pd.DataFrame())
