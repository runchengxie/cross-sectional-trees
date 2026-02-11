import copy

import pandas as pd
import pytest
import yaml

from csml import pipeline
from csml.data_interface import DataInterface


def _base_config(tmp_path):
    return {
        "market": "us",
        "data": {
            "provider": "tushare",
            "start_date": "20200101",
            "end_date": "today",
            "cache_dir": str(tmp_path / "cache"),
            "price_col": "close",
        },
        "universe": {
            "mode": "static",
            "symbols": ["AAA", "BBB", "CCC"],
            "min_symbols_per_date": 1,
            "drop_suspended": False,
            "suspended_policy": "mark",
        },
        "fundamentals": {"enabled": False},
        "label": {
            "horizon_mode": "fixed",
            "horizon_days": 1,
            "shift_days": 0,
            "target_col": "future_return",
        },
        "features": {
            "list": ["sma_3"],
            "params": {"sma_windows": [3]},
            "cross_sectional": {"method": "none"},
        },
        "model": {
            "type": "xgb_regressor",
            "params": {
                "n_estimators": 1,
                "learning_rate": 0.1,
                "max_depth": 2,
                "objective": "reg:squarederror",
            },
            "sample_weight_mode": "none",
        },
        "eval": {
            "test_size": 0.2,
            "n_splits": 1,
            "n_quantiles": 2,
            "rebalance_frequency": "W",
            "top_k": 1,
            "signal_direction_mode": "fixed",
            "signal_direction": 1,
            "transaction_cost_bps": 0,
            "sample_on_rebalance_dates": False,
            "report_train_ic": False,
            "save_artifacts": True,
            "save_dataset": False,
            "output_dir": str(tmp_path / "runs"),
            "run_name": "warning",
            "walk_forward": {"enabled": False},
        },
        "backtest": {
            "enabled": True,
            "top_k": 1,
            "rebalance_frequency": "W",
            "transaction_cost_bps": 0,
            "long_only": True,
            "exit_mode": "rebalance",
            "exit_price_policy": "strict",
            "exit_fallback_policy": "ffill",
        },
        "live": {"enabled": False},
    }


def _write_config(tmp_path, config):
    path = tmp_path / "config.yml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return path


def _patch_empty_data(monkeypatch):
    monkeypatch.setattr(DataInterface, "_init_client", lambda self: None)
    monkeypatch.setattr(
        DataInterface,
        "fetch_daily",
        lambda self, symbol, start_date, end_date: pd.DataFrame(),
    )
    monkeypatch.setattr(DataInterface, "load_basic", lambda self, symbols=None: pd.DataFrame())


def test_pipeline_warns_relative_end_date_when_live_disabled(tmp_path, monkeypatch, caplog):
    _patch_empty_data(monkeypatch)
    config = _base_config(tmp_path)
    config_path = _write_config(tmp_path, config)

    caplog.set_level("WARNING", logger="csml")
    with pytest.raises(SystemExit):
        pipeline.run(str(config_path))

    assert any(
        "data.end_date=today is a relative token" in record.getMessage()
        for record in caplog.records
    )


def test_pipeline_relative_end_date_warning_suppressed_when_live_enabled(tmp_path, monkeypatch, caplog):
    _patch_empty_data(monkeypatch)
    config = copy.deepcopy(_base_config(tmp_path))
    config["live"] = {"enabled": True, "train_mode": "full"}
    config_path = _write_config(tmp_path, config)

    caplog.set_level("WARNING", logger="csml")
    with pytest.raises(SystemExit):
        pipeline.run(str(config_path))

    assert not any(
        "data.end_date=today is a relative token" in record.getMessage()
        for record in caplog.records
    )
