import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from csml import pipeline
from csml.data_interface import DataInterface
from csml.data_tools import rqdata_assets
from tests._pipeline_test_utils import _build_frames, _run_pipeline


@pytest.mark.slow
def test_pipeline_filters_and_fallbacks(tmp_path, monkeypatch):
    dates = pd.date_range("2020-01-01", periods=12, freq="B")
    symbols = ["AAA", "BBB", "CCC"]
    vol_map = {
        "AAA": np.full(len(dates), 100.0),
        "BBB": np.full(len(dates), 120.0),
        "CCC": np.array([50.0, 0.0] + [60.0] * (len(dates) - 2)),
    }
    frames = _build_frames(symbols, dates, vol_map=vol_map, include_amount=False)
    basic_df = pd.DataFrame(
        {"symbol": symbols, "name": ["Alpha", "ST Beta", "Gamma"]}
    )

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
            "min_symbols_per_date": 1,
            "drop_suspended": True,
            "suspended_policy": "mark",
            "drop_st": True,
        },
        "fundamentals": {
            "enabled": False,
            "source": "provider",
            "required": False,
        },
        "label": {
            "horizon_mode": "fixed",
            "horizon_days": 1,
            "shift_days": 0,
            "target_col": "future_return",
        },
        "features": {
            "list": ["vol"],
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
            "run_name": "filters",
            "walk_forward": {"enabled": False},
        },
        "backtest": {"enabled": False},
    }

    run_dir = _run_pipeline(tmp_path, monkeypatch, config, frames, basic_df=basic_df)
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["data"]["price_col"] == "close"
    assert summary["data"]["min_symbols_per_date"] == 2
    assert summary["fundamentals"]["enabled"] is False

    dataset = pd.read_parquet(run_dir / "dataset.parquet").reset_index()
    assert "BBB" not in dataset["symbol"].unique()
    ccc_rows = dataset[dataset["symbol"] == "CCC"]
    assert not ccc_rows.empty
    zero_vol_rows = ccc_rows[ccc_rows["vol"] == 0.0]
    assert not zero_vol_rows.empty
    assert zero_vol_rows["is_tradable"].eq(False).all()

@pytest.mark.slow
def test_pipeline_min_listed_days_skips_empty_basic_df(tmp_path, monkeypatch):
    dates = pd.date_range("2020-01-01", periods=12, freq="B")
    symbols = ["AAA.HK", "BBB.HK"]
    frames = _build_frames(symbols, dates)

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
            "min_symbols_per_date": 1,
            "min_listed_days": 60,
            "drop_suspended": False,
        },
        "fundamentals": {
            "enabled": False,
            "source": "provider",
            "required": False,
        },
        "label": {
            "horizon_mode": "fixed",
            "horizon_days": 1,
            "shift_days": 0,
            "target_col": "future_return",
        },
        "features": {
            "list": ["vol"],
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
            "run_name": "min_listed_days_empty_basic",
            "walk_forward": {"enabled": False},
        },
        "backtest": {"enabled": False},
    }

    run_dir = _run_pipeline(tmp_path, monkeypatch, config, frames, basic_df=pd.DataFrame())
    dataset = pd.read_parquet(run_dir / "dataset.parquet").reset_index()

    assert sorted(dataset["symbol"].unique().tolist()) == symbols
    assert not dataset.empty
