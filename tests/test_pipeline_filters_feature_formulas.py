import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from cstree import pipeline
from cstree.data_interface import DataInterface
from cstree.data_tools import rqdata_assets
from tests._pipeline_test_utils import _build_frames, _run_pipeline


@pytest.mark.slow
def test_pipeline_feature_formulas(tmp_path, monkeypatch):
    dates = pd.date_range("2020-01-01", periods=20, freq="B")
    symbols = ["AAA", "BBB"]
    close_map = {
        "AAA": np.arange(1, len(dates) + 1, dtype=float),
        "BBB": np.full(len(dates), 2.0),
    }
    vol_map = {
        "AAA": np.arange(1, len(dates) + 1, dtype=float) * 10.0,
        "BBB": np.full(len(dates), 5.0),
    }
    frames = _build_frames(symbols, dates, close_map=close_map, vol_map=vol_map, include_amount=True)

    output_dir = tmp_path / "runs"
    config = {
        "market": "hk",
        "data": {
            "provider": "rqdata",
            "start_date": "20200101",
            "end_date": "20200131",
            "cache_dir": str(tmp_path / "cache"),
            "price_col": "close",
        },
        "universe": {
            "mode": "static",
            "symbols": symbols,
            "min_symbols_per_date": 2,
            "drop_suspended": False,
        },
        "fundamentals": {"enabled": False},
        "label": {
            "horizon_mode": "fixed",
            "horizon_days": 1,
            "shift_days": 0,
            "target_col": "future_return",
        },
        "features": {
            "list": [
                "sma_3",
                "sma_3_diff",
                "volume_sma3_ratio",
                "ret_3",
                "rv_3",
                "log_vol",
                "vol",
            ],
            "params": {
                "sma_windows": [3],
                "volume_sma_windows": [3],
                "ret_windows": [3],
                "rv_windows": [3],
            },
            "cross_sectional": {"method": "none"},
        },
        "model": {
            "type": "xgb_regressor",
            "params": {
                "n_estimators": 5,
                "learning_rate": 0.1,
                "max_depth": 2,
                "subsample": 1.0,
                "colsample_bytree": 1.0,
                "random_state": 7,
                "objective": "reg:squarederror",
            },
            "sample_weight_mode": "none",
        },
        "eval": {
            "test_size": 0.2,
            "n_splits": 2,
            "n_quantiles": 2,
            "rebalance_frequency": "W",
            "top_k": 1,
            "signal_direction_mode": "fixed",
            "signal_direction": 1,
            "transaction_cost_bps": 0,
            "sample_on_rebalance_dates": False,
            "report_train_ic": False,
            "save_artifacts": True,
            "save_dataset": True,
            "output_dir": str(output_dir),
            "run_name": "features",
            "walk_forward": {"enabled": False},
        },
        "backtest": {"enabled": False},
    }

    run_dir = _run_pipeline(tmp_path, monkeypatch, config, frames)
    dataset = pd.read_parquet(run_dir / "dataset.parquet").reset_index()
    aaa = dataset[dataset["symbol"] == "AAA"].sort_values("trade_date").reset_index(drop=True)

    close = pd.Series(close_map["AAA"], index=dates)
    vol = pd.Series(vol_map["AAA"], index=dates)
    sma3 = close.rolling(3).mean()
    sma3_diff = sma3.pct_change()
    vol_ratio = vol / vol.rolling(3).mean()
    ret3 = close.pct_change(3)
    rv3 = close.pct_change().rolling(3).std(ddof=0)
    log_vol = np.log1p(vol)
    expected = pd.DataFrame(
        {
            "trade_date": dates,
            "sma_3": sma3,
            "sma_3_diff": sma3_diff,
            "volume_sma3_ratio": vol_ratio,
            "ret_3": ret3,
            "rv_3": rv3,
            "log_vol": log_vol,
        }
    ).dropna(subset=["sma_3", "sma_3_diff", "volume_sma3_ratio", "ret_3", "rv_3", "log_vol"])
    expected = expected[expected["trade_date"].isin(aaa["trade_date"])].reset_index(drop=True)

    np.testing.assert_allclose(aaa["sma_3"].to_numpy(), expected["sma_3"].to_numpy(), rtol=1e-6, atol=1e-6)
    np.testing.assert_allclose(
        aaa["sma_3_diff"].to_numpy(), expected["sma_3_diff"].to_numpy(), rtol=1e-6, atol=1e-6
    )
    np.testing.assert_allclose(
        aaa["volume_sma3_ratio"].to_numpy(),
        expected["volume_sma3_ratio"].to_numpy(),
        rtol=1e-6,
        atol=1e-6,
    )
    np.testing.assert_allclose(aaa["ret_3"].to_numpy(), expected["ret_3"].to_numpy(), rtol=1e-6, atol=1e-6)
    np.testing.assert_allclose(aaa["rv_3"].to_numpy(), expected["rv_3"].to_numpy(), rtol=1e-6, atol=1e-6)
    np.testing.assert_allclose(aaa["log_vol"].to_numpy(), expected["log_vol"].to_numpy(), rtol=1e-6, atol=1e-6)
