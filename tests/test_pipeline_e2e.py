import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from csml import pipeline
from csml.data_interface import DataInterface


def _build_daily_frames(symbols: list[str], dates: pd.DatetimeIndex) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    steps = np.arange(len(dates))
    for idx, symbol in enumerate(symbols):
        base = 100.0 + idx * 10.0
        slope = 0.1 * (idx + 1)
        close = base + slope * steps
        vol = np.full(len(dates), 1000 + idx, dtype=float)
        amount = vol * close
        frames[symbol] = pd.DataFrame(
            {
                "trade_date": [d.strftime("%Y%m%d") for d in dates],
                "symbol": symbol,
                "close": close,
                "vol": vol,
                "amount": amount,
            }
        )
    return frames


@pytest.mark.integration
def test_pipeline_run_offline(tmp_path, monkeypatch):
    dates = pd.date_range("2020-01-01", periods=60, freq="B")
    symbols = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    frames = _build_daily_frames(symbols, dates)

    def fake_init_client(self):
        self.client = None

    def fake_fetch_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        return frames[symbol].copy()

    def fake_load_basic(self, symbols=None) -> pd.DataFrame:
        return pd.DataFrame()

    monkeypatch.setattr(DataInterface, "_init_client", fake_init_client)
    monkeypatch.setattr(DataInterface, "fetch_daily", fake_fetch_daily)
    monkeypatch.setattr(DataInterface, "load_basic", fake_load_basic)

    output_dir = tmp_path / "runs"
    config = {
        "market": "hk",
        "data": {
            "provider": "rqdata",
            "start_date": "20200101",
            "end_date": "20200331",
            "cache_dir": str(tmp_path / "cache"),
            "price_col": "close",
        },
        "universe": {
            "mode": "static",
            "require_by_date": False,
            "symbols": symbols,
            "min_symbols_per_date": 3,
            "drop_suspended": True,
            "suspended_policy": "mark",
        },
        "fundamentals": {"enabled": False},
        "label": {
            "horizon_mode": "next_rebalance",
            "rebalance_frequency": "W",
            "horizon_days": 5,
            "shift_days": 1,
            "target_col": "future_return",
        },
        "features": {
            "list": ["sma_5"],
            "params": {"sma_windows": [5]},
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
            "n_quantiles": 3,
            "rebalance_frequency": "W",
            "top_k": 2,
            "signal_direction_mode": "fixed",
            "signal_direction": 1,
            "transaction_cost_bps": 0,
            "sample_on_rebalance_dates": False,
            "report_train_ic": False,
            "save_artifacts": True,
            "save_dataset": True,
            "output_dir": str(output_dir),
            "run_name": "e2e",
            "walk_forward": {"enabled": False},
        },
        "backtest": {
            "enabled": True,
            "top_k": 2,
            "rebalance_frequency": "W",
            "transaction_cost_bps": 0,
            "long_only": True,
            "exit_mode": "rebalance",
            "exit_price_policy": "delay",
        },
    }

    config_path = tmp_path / "config.yml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    pipeline.run(str(config_path))

    run_dirs = list(Path(output_dir).glob("e2e_*"))
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    summary_path = run_dir / "summary.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["run"]["name"] == "e2e"
    assert summary["run"]["log_file"] == str(run_dir / "run.log")
    assert summary["dataset"]["file"]
    assert summary["data"]["price_col"] == "close"
    assert summary["backtest"]["execution_source"] == "default_flat_cost"
    assert set(summary.keys()) == {
        "run",
        "data",
        "dataset",
        "universe",
        "label",
        "split",
        "eval",
        "backtest",
        "final_oos",
        "positions",
        "live",
        "quality",
        "fundamentals",
        "industry",
        "walk_forward",
    }
    assert set(summary["positions"]["window_fields"].keys()) == {
        "signal_asof",
        "entry_date",
        "next_entry_date",
        "holding_window",
    }

    assert (run_dir / "dataset.parquet").exists()
    assert (run_dir / "ic_test.csv").exists()
    assert (run_dir / "quantile_returns.csv").exists()
    assert (run_dir / "backtest_net.csv").exists()
    assert (run_dir / "positions_by_rebalance.csv").exists()
    assert (run_dir / "positions_current.csv").exists()
    assert (run_dir / "run.log").exists()
    assert not (run_dir / "eval_scored.parquet").exists()
    assert summary["eval"]["save_scored_artifact"] is False
    assert summary["eval"]["scored_file"] is None
    assert "Artifacts will be saved to" in (run_dir / "run.log").read_text(encoding="utf-8")

    required_position_columns = {
        "signal_asof",
        "entry_date",
        "next_entry_date",
        "holding_window",
        "symbol",
        "weight",
        "signal",
        "rank",
        "side",
    }
    positions_full = pd.read_csv(run_dir / "positions_by_rebalance.csv")
    positions_current = pd.read_csv(run_dir / "positions_current.csv")
    assert required_position_columns.issubset(positions_full.columns)
    assert required_position_columns.issubset(positions_current.columns)


@pytest.mark.integration
def test_pipeline_run_offline_uses_external_artifacts_root_and_writes_inputs_lock(tmp_path, monkeypatch):
    dates = pd.date_range("2020-01-01", periods=60, freq="B")
    symbols = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    frames = _build_daily_frames(symbols, dates)

    def fake_init_client(self):
        self.client = None

    def fake_fetch_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        return frames[symbol].copy()

    def fake_load_basic(self, symbols=None) -> pd.DataFrame:
        return pd.DataFrame()

    monkeypatch.setattr(DataInterface, "_init_client", fake_init_client)
    monkeypatch.setattr(DataInterface, "fetch_daily", fake_fetch_daily)
    monkeypatch.setattr(DataInterface, "load_basic", fake_load_basic)

    artifacts_root = tmp_path / "external-artifacts"
    config = {
        "market": "hk",
        "data": {
            "provider": "rqdata",
            "start_date": "20200101",
            "end_date": "20200331",
            "cache_dir": str(tmp_path / "cache"),
            "price_col": "close",
        },
        "universe": {
            "mode": "static",
            "require_by_date": False,
            "symbols": symbols,
            "min_symbols_per_date": 3,
            "drop_suspended": True,
            "suspended_policy": "mark",
        },
        "fundamentals": {"enabled": False},
        "label": {
            "horizon_mode": "next_rebalance",
            "rebalance_frequency": "W",
            "horizon_days": 5,
            "shift_days": 1,
            "target_col": "future_return",
        },
        "features": {
            "list": ["sma_5"],
            "params": {"sma_windows": [5]},
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
            "n_quantiles": 3,
            "rebalance_frequency": "W",
            "top_k": 2,
            "signal_direction_mode": "fixed",
            "signal_direction": 1,
            "transaction_cost_bps": 0,
            "sample_on_rebalance_dates": False,
            "report_train_ic": False,
            "save_artifacts": True,
            "save_dataset": True,
            "run_name": "e2e_external_artifacts",
            "walk_forward": {"enabled": False},
        },
        "backtest": {
            "enabled": True,
            "top_k": 2,
            "rebalance_frequency": "W",
            "transaction_cost_bps": 0,
            "long_only": True,
            "exit_mode": "rebalance",
            "exit_price_policy": "delay",
        },
    }

    config_path = tmp_path / "config.yml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    pipeline.run(str(config_path), artifacts_root=str(artifacts_root))

    run_dirs = list((artifacts_root / "runs").glob("e2e_external_artifacts_*"))
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    inputs_lock = json.loads((run_dir / "inputs.lock.json").read_text(encoding="utf-8"))
    assert inputs_lock["artifacts_root"] == str(artifacts_root.resolve())
    assert inputs_lock["run_dir"] == str(run_dir)
    assert inputs_lock["resolved_dates"]["start_date"] == "20200101"
    assert inputs_lock["resolved_dates"]["end_date"] == "20200331"
    assert inputs_lock["inputs"]["cache_dir"] == str((tmp_path / "cache").resolve())
    assert inputs_lock["mutable_inputs"]["used_relative_start_date"] is False
    assert inputs_lock["mutable_inputs"]["used_relative_end_date"] is False
    assert inputs_lock["mutable_inputs"]["used_latest_pointer"] is False


@pytest.mark.integration
def test_pipeline_run_offline_with_train_target_transform(tmp_path, monkeypatch):
    dates = pd.date_range("2020-01-01", periods=60, freq="B")
    symbols = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    frames = _build_daily_frames(symbols, dates)

    def fake_init_client(self):
        self.client = None

    def fake_fetch_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        return frames[symbol].copy()

    def fake_load_basic(self, symbols=None) -> pd.DataFrame:
        return pd.DataFrame()

    monkeypatch.setattr(DataInterface, "_init_client", fake_init_client)
    monkeypatch.setattr(DataInterface, "fetch_daily", fake_fetch_daily)
    monkeypatch.setattr(DataInterface, "load_basic", fake_load_basic)

    output_dir = tmp_path / "runs"
    config = {
        "market": "hk",
        "data": {
            "provider": "rqdata",
            "start_date": "20200101",
            "end_date": "20200331",
            "cache_dir": str(tmp_path / "cache"),
            "price_col": "close",
        },
        "universe": {
            "mode": "static",
            "require_by_date": False,
            "symbols": symbols,
            "min_symbols_per_date": 3,
            "drop_suspended": True,
            "suspended_policy": "mark",
        },
        "fundamentals": {"enabled": False},
        "label": {
            "horizon_mode": "next_rebalance",
            "rebalance_frequency": "W",
            "horizon_days": 5,
            "shift_days": 1,
            "target_col": "future_return",
            "train_target_transform": "rank",
        },
        "features": {
            "list": ["sma_5"],
            "params": {"sma_windows": [5]},
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
            "n_quantiles": 3,
            "rebalance_frequency": "W",
            "top_k": 2,
            "signal_direction_mode": "fixed",
            "signal_direction": 1,
            "transaction_cost_bps": 0,
            "sample_on_rebalance_dates": False,
            "report_train_ic": False,
            "save_artifacts": True,
            "save_dataset": True,
            "output_dir": str(output_dir),
            "run_name": "e2e_train_target_transform",
            "walk_forward": {"enabled": False},
        },
        "backtest": {
            "enabled": True,
            "top_k": 2,
            "rebalance_frequency": "W",
            "transaction_cost_bps": 0,
            "long_only": True,
            "exit_mode": "rebalance",
            "exit_price_policy": "delay",
        },
    }

    config_path = tmp_path / "config.yml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    pipeline.run(str(config_path))

    run_dirs = list(Path(output_dir).glob("e2e_train_target_transform_*"))
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["label"]["train_target_transform"] == "rank"

    dataset = pd.read_parquet(run_dir / "dataset.parquet").reset_index()
    assert "future_return__train_target" in dataset.columns
    labeled = dataset.dropna(subset=["future_return", "future_return__train_target"])
    assert not labeled.empty
    assert not np.allclose(
        labeled["future_return"].to_numpy(),
        labeled["future_return__train_target"].to_numpy(),
    )


@pytest.mark.integration
def test_pipeline_run_uses_explicit_log_file(tmp_path, monkeypatch):
    dates = pd.date_range("2020-01-01", periods=60, freq="B")
    symbols = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    frames = _build_daily_frames(symbols, dates)

    def fake_init_client(self):
        self.client = None

    def fake_fetch_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        return frames[symbol].copy()

    def fake_load_basic(self, symbols=None) -> pd.DataFrame:
        return pd.DataFrame()

    monkeypatch.setattr(DataInterface, "_init_client", fake_init_client)
    monkeypatch.setattr(DataInterface, "fetch_daily", fake_fetch_daily)
    monkeypatch.setattr(DataInterface, "load_basic", fake_load_basic)

    output_dir = tmp_path / "runs"
    explicit_log_path = tmp_path / "custom.log"
    config = {
        "market": "hk",
        "data": {
            "provider": "rqdata",
            "start_date": "20200101",
            "end_date": "20200331",
            "cache_dir": str(tmp_path / "cache"),
            "price_col": "close",
        },
        "universe": {
            "mode": "static",
            "require_by_date": False,
            "symbols": symbols,
            "min_symbols_per_date": 3,
            "drop_suspended": True,
            "suspended_policy": "mark",
        },
        "fundamentals": {"enabled": False},
        "label": {
            "horizon_mode": "next_rebalance",
            "rebalance_frequency": "W",
            "horizon_days": 5,
            "shift_days": 1,
            "target_col": "future_return",
        },
        "features": {
            "list": ["sma_5"],
            "params": {"sma_windows": [5]},
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
        "logging": {
            "level": "INFO",
            "file": str(explicit_log_path),
        },
        "eval": {
            "test_size": 0.2,
            "n_splits": 2,
            "n_quantiles": 3,
            "rebalance_frequency": "W",
            "top_k": 2,
            "signal_direction_mode": "fixed",
            "signal_direction": 1,
            "transaction_cost_bps": 0,
            "sample_on_rebalance_dates": False,
            "report_train_ic": False,
            "save_artifacts": True,
            "save_dataset": True,
            "output_dir": str(output_dir),
            "run_name": "e2e_explicit_log",
            "walk_forward": {"enabled": False},
        },
        "backtest": {
            "enabled": True,
            "top_k": 2,
            "rebalance_frequency": "W",
            "transaction_cost_bps": 0,
            "long_only": True,
            "exit_mode": "rebalance",
            "exit_price_policy": "delay",
        },
    }

    config_path = tmp_path / "config.yml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    pipeline.run(str(config_path))

    run_dirs = list(Path(output_dir).glob("e2e_explicit_log_*"))
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))

    assert summary["run"]["log_file"] == str(explicit_log_path)
    assert explicit_log_path.exists()
    assert not (run_dir / "run.log").exists()
    assert "Artifacts will be saved to" in explicit_log_path.read_text(encoding="utf-8")


@pytest.mark.integration
def test_pipeline_ic_uses_rebalance_dates(tmp_path, monkeypatch):
    dates = pd.date_range("2020-01-01", periods=70, freq="B")
    symbols = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    frames = _build_daily_frames(symbols, dates)

    def fake_init_client(self):
        self.client = None

    def fake_fetch_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        return frames[symbol].copy()

    def fake_load_basic(self, symbols=None) -> pd.DataFrame:
        return pd.DataFrame()

    monkeypatch.setattr(DataInterface, "_init_client", fake_init_client)
    monkeypatch.setattr(DataInterface, "fetch_daily", fake_fetch_daily)
    monkeypatch.setattr(DataInterface, "load_basic", fake_load_basic)

    output_dir = tmp_path / "runs"
    config = {
        "market": "hk",
        "data": {
            "provider": "rqdata",
            "start_date": "20200101",
            "end_date": "20200430",
            "cache_dir": str(tmp_path / "cache"),
            "price_col": "close",
        },
        "universe": {
            "mode": "static",
            "symbols": symbols,
            "min_symbols_per_date": 3,
            "drop_suspended": True,
            "suspended_policy": "mark",
        },
        "fundamentals": {"enabled": False},
        "label": {
            "horizon_mode": "next_rebalance",
            "rebalance_frequency": "W",
            "horizon_days": 5,
            "shift_days": 1,
            "target_col": "future_return",
        },
        "features": {
            "list": ["sma_5"],
            "params": {"sma_windows": [5]},
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
            "test_size": 0.25,
            "n_splits": 2,
            "n_quantiles": 3,
            "rebalance_frequency": "W",
            "top_k": 2,
            "signal_direction_mode": "fixed",
            "signal_direction": 1,
            "transaction_cost_bps": 0,
            "sample_on_rebalance_dates": False,
            "report_train_ic": False,
            "save_artifacts": True,
            "save_dataset": False,
            "output_dir": str(output_dir),
            "run_name": "e2e_rebalance_eval",
            "walk_forward": {"enabled": False},
        },
        "backtest": {
            "enabled": False,
            "top_k": 2,
            "rebalance_frequency": "W",
            "transaction_cost_bps": 0,
            "long_only": True,
            "exit_mode": "rebalance",
        },
    }

    config_path = tmp_path / "config.yml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    pipeline.run(str(config_path))

    run_dirs = list(Path(output_dir).glob("e2e_rebalance_eval_*"))
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    rebalance_dates = summary["eval"]["rebalance_dates"]
    assert rebalance_dates

    ic_test = pd.read_csv(run_dir / "ic_test.csv")
    ic_dates = pd.to_datetime(ic_test["trade_date"], errors="coerce").dt.strftime("%Y%m%d").dropna().tolist()
    assert ic_dates == rebalance_dates


@pytest.mark.integration
def test_pipeline_run_offline_with_ridge(tmp_path, monkeypatch):
    dates = pd.date_range("2020-01-01", periods=60, freq="B")
    symbols = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    frames = _build_daily_frames(symbols, dates)

    def fake_init_client(self):
        self.client = None

    def fake_fetch_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        return frames[symbol].copy()

    def fake_load_basic(self, symbols=None) -> pd.DataFrame:
        return pd.DataFrame()

    monkeypatch.setattr(DataInterface, "_init_client", fake_init_client)
    monkeypatch.setattr(DataInterface, "fetch_daily", fake_fetch_daily)
    monkeypatch.setattr(DataInterface, "load_basic", fake_load_basic)

    output_dir = tmp_path / "runs"
    config = {
        "market": "hk",
        "data": {
            "provider": "rqdata",
            "start_date": "20200101",
            "end_date": "20200331",
            "cache_dir": str(tmp_path / "cache"),
            "price_col": "close",
        },
        "universe": {
            "mode": "static",
            "require_by_date": False,
            "symbols": symbols,
            "min_symbols_per_date": 3,
            "drop_suspended": True,
            "suspended_policy": "mark",
        },
        "fundamentals": {"enabled": False},
        "label": {
            "horizon_mode": "next_rebalance",
            "rebalance_frequency": "W",
            "horizon_days": 5,
            "shift_days": 1,
            "target_col": "future_return",
        },
        "features": {
            "list": ["sma_5"],
            "params": {"sma_windows": [5]},
            "cross_sectional": {"method": "none"},
        },
        "model": {
            "type": "ridge",
            "params": {"alpha": 1.0, "fit_intercept": True},
            "sample_weight_mode": "none",
        },
        "eval": {
            "test_size": 0.2,
            "n_splits": 2,
            "n_quantiles": 3,
            "rebalance_frequency": "W",
            "top_k": 2,
            "signal_direction_mode": "fixed",
            "signal_direction": 1,
            "transaction_cost_bps": 0,
            "sample_on_rebalance_dates": False,
            "report_train_ic": False,
            "save_artifacts": True,
            "save_dataset": False,
            "output_dir": str(output_dir),
            "run_name": "e2e_ridge",
            "walk_forward": {"enabled": False},
        },
        "backtest": {
            "enabled": False,
        },
    }

    config_path = tmp_path / "config.yml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    pipeline.run(str(config_path))

    run_dirs = list(Path(output_dir).glob("e2e_ridge_*"))
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    assert (run_dir / "summary.json").exists()
    assert (run_dir / "feature_importance.csv").exists()
    assert (run_dir / "ic_test.csv").exists()


@pytest.mark.integration
def test_pipeline_run_offline_with_xgb_ranker(tmp_path, monkeypatch):
    dates = pd.date_range("2020-01-01", periods=60, freq="B")
    symbols = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    frames = _build_daily_frames(symbols, dates)

    def fake_init_client(self):
        self.client = None

    def fake_fetch_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        return frames[symbol].copy()

    def fake_load_basic(self, symbols=None) -> pd.DataFrame:
        return pd.DataFrame()

    monkeypatch.setattr(DataInterface, "_init_client", fake_init_client)
    monkeypatch.setattr(DataInterface, "fetch_daily", fake_fetch_daily)
    monkeypatch.setattr(DataInterface, "load_basic", fake_load_basic)

    output_dir = tmp_path / "runs"
    config = {
        "market": "hk",
        "data": {
            "provider": "rqdata",
            "start_date": "20200101",
            "end_date": "20200331",
            "cache_dir": str(tmp_path / "cache"),
            "price_col": "close",
        },
        "universe": {
            "mode": "static",
            "require_by_date": False,
            "symbols": symbols,
            "min_symbols_per_date": 3,
            "drop_suspended": True,
            "suspended_policy": "mark",
        },
        "fundamentals": {"enabled": False},
        "label": {
            "horizon_mode": "next_rebalance",
            "rebalance_frequency": "W",
            "horizon_days": 5,
            "shift_days": 1,
            "target_col": "future_return",
        },
        "features": {
            "list": ["sma_5"],
            "params": {"sma_windows": [5]},
            "cross_sectional": {"method": "none"},
        },
        "model": {
            "type": "xgb_ranker",
            "params": {
                "n_estimators": 5,
                "learning_rate": 0.1,
                "max_depth": 2,
                "subsample": 1.0,
                "colsample_bytree": 1.0,
                "objective": "rank:pairwise",
                "random_state": 7,
            },
            "sample_weight_mode": "date_equal",
        },
        "eval": {
            "test_size": 0.2,
            "n_splits": 2,
            "n_quantiles": 3,
            "rebalance_frequency": "W",
            "top_k": 2,
            "signal_direction_mode": "fixed",
            "signal_direction": 1,
            "transaction_cost_bps": 0,
            "sample_on_rebalance_dates": False,
            "report_train_ic": False,
            "save_artifacts": True,
            "save_dataset": False,
            "output_dir": str(output_dir),
            "run_name": "e2e_ranker",
            "walk_forward": {"enabled": False},
        },
        "backtest": {
            "enabled": False,
        },
    }

    config_path = tmp_path / "config.yml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    pipeline.run(str(config_path))

    run_dirs = list(Path(output_dir).glob("e2e_ranker_*"))
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    assert (run_dir / "summary.json").exists()
    assert (run_dir / "feature_importance.csv").exists()
    assert (run_dir / "ic_test.csv").exists()


@pytest.mark.integration
def test_pipeline_walk_forward_feature_stability_outputs(tmp_path, monkeypatch):
    dates = pd.date_range("2020-01-01", periods=90, freq="B")
    symbols = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    frames = _build_daily_frames(symbols, dates)

    def fake_init_client(self):
        self.client = None

    def fake_fetch_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        return frames[symbol].copy()

    def fake_load_basic(self, symbols=None) -> pd.DataFrame:
        return pd.DataFrame()

    monkeypatch.setattr(DataInterface, "_init_client", fake_init_client)
    monkeypatch.setattr(DataInterface, "fetch_daily", fake_fetch_daily)
    monkeypatch.setattr(DataInterface, "load_basic", fake_load_basic)

    output_dir = tmp_path / "runs"
    config = {
        "market": "hk",
        "data": {
            "provider": "rqdata",
            "start_date": "20200101",
            "end_date": "20200530",
            "cache_dir": str(tmp_path / "cache"),
            "price_col": "close",
        },
        "universe": {
            "mode": "static",
            "require_by_date": False,
            "symbols": symbols,
            "min_symbols_per_date": 3,
            "drop_suspended": True,
            "suspended_policy": "mark",
        },
        "fundamentals": {"enabled": False},
        "label": {
            "horizon_mode": "next_rebalance",
            "rebalance_frequency": "W",
            "horizon_days": 5,
            "shift_days": 1,
            "target_col": "future_return",
        },
        "features": {
            "list": ["sma_5", "ret_5"],
            "params": {"sma_windows": [5], "ret_windows": [5]},
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
            "n_quantiles": 3,
            "rebalance_frequency": "W",
            "top_k": 2,
            "signal_direction_mode": "fixed",
            "signal_direction": 1,
            "transaction_cost_bps": 0,
            "sample_on_rebalance_dates": False,
            "report_train_ic": False,
            "save_artifacts": True,
            "save_dataset": False,
            "output_dir": str(output_dir),
            "run_name": "e2e_wf_stability",
            "walk_forward": {
                "enabled": True,
                "n_windows": 2,
                "test_size": 0.2,
                "step_size": 0.2,
                "backtest_enabled": False,
                "feature_top_k": 1,
            },
        },
        "backtest": {
            "enabled": False,
        },
    }

    config_path = tmp_path / "config.yml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    pipeline.run(str(config_path))

    run_dirs = list(Path(output_dir).glob("e2e_wf_stability_*"))
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    wf_importance_path = run_dir / "walk_forward_feature_importance.csv"
    wf_stability_path = run_dir / "walk_forward_feature_stability.csv"
    assert wf_importance_path.exists()
    assert wf_stability_path.exists()

    wf_importance = pd.read_csv(wf_importance_path)
    assert {"window", "feature", "importance", "importance_source"}.issubset(wf_importance.columns)
    assert wf_importance["window"].nunique() >= 1

    wf_stability = pd.read_csv(wf_stability_path)
    assert {"feature", "importance_mean", "top_k_hit_rate", "nonzero_hit_rate"}.issubset(
        wf_stability.columns
    )

    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    walk_forward = summary["walk_forward"]
    assert walk_forward["feature_top_k"] == 1
    assert walk_forward["actual_windows"] == len(walk_forward["results"])
    assert walk_forward["feature_importance_windows"] >= 1
    assert walk_forward["feature_importance_file"]
    assert walk_forward["feature_stability_file"]


@pytest.mark.integration
def test_pipeline_walk_forward_backtest_benchmark_summary(tmp_path, monkeypatch):
    dates = pd.date_range("2020-01-01", periods=90, freq="B")
    symbols = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    benchmark_symbol = "02800.HK"
    frames = _build_daily_frames(symbols + [benchmark_symbol], dates)

    def fake_init_client(self):
        self.client = None

    def fake_fetch_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        return frames[symbol].copy()

    def fake_load_basic(self, symbols=None) -> pd.DataFrame:
        return pd.DataFrame()

    monkeypatch.setattr(DataInterface, "_init_client", fake_init_client)
    monkeypatch.setattr(DataInterface, "fetch_daily", fake_fetch_daily)
    monkeypatch.setattr(DataInterface, "load_basic", fake_load_basic)

    output_dir = tmp_path / "runs"
    config = {
        "market": "hk",
        "data": {
            "provider": "rqdata",
            "start_date": "20200101",
            "end_date": "20200530",
            "cache_dir": str(tmp_path / "cache"),
            "price_col": "close",
        },
        "universe": {
            "mode": "static",
            "require_by_date": False,
            "symbols": symbols,
            "min_symbols_per_date": 3,
            "drop_suspended": True,
            "suspended_policy": "mark",
        },
        "fundamentals": {"enabled": False},
        "label": {
            "horizon_mode": "next_rebalance",
            "rebalance_frequency": "W",
            "horizon_days": 5,
            "shift_days": 1,
            "target_col": "future_return",
        },
        "features": {
            "list": ["sma_5", "ret_5"],
            "params": {"sma_windows": [5], "ret_windows": [5]},
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
            "n_quantiles": 3,
            "rebalance_frequency": "W",
            "top_k": 2,
            "signal_direction_mode": "fixed",
            "signal_direction": 1,
            "transaction_cost_bps": 0,
            "sample_on_rebalance_dates": False,
            "report_train_ic": False,
            "save_artifacts": True,
            "save_dataset": False,
            "output_dir": str(output_dir),
            "run_name": "e2e_wf_benchmark",
            "walk_forward": {
                "enabled": True,
                "n_windows": 2,
                "test_size": 0.2,
                "step_size": 0.2,
                "backtest_enabled": True,
                "feature_top_k": 1,
            },
        },
        "backtest": {
            "enabled": True,
            "top_k": 2,
            "rebalance_frequency": "W",
            "transaction_cost_bps": 0,
            "long_only": True,
            "exit_mode": "rebalance",
            "benchmark_symbol": benchmark_symbol,
        },
    }

    config_path = tmp_path / "config.yml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    pipeline.run(str(config_path))

    run_dirs = list(Path(output_dir).glob("e2e_wf_benchmark_*"))
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["walk_forward"]["actual_windows"] == len(summary["walk_forward"]["results"])
    walk_forward_results = summary["walk_forward"]["results"]
    assert walk_forward_results
    assert any(result.get("backtest") for result in walk_forward_results)
    assert any(
        result.get("backtest") and result["backtest"].get("benchmark") is not None
        for result in walk_forward_results
    )


def test_pipeline_backtest_accepts_external_benchmark_returns_file(tmp_path, monkeypatch):
    dates = pd.date_range("2020-01-01", periods=90, freq="B")
    symbols = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    frames = _build_daily_frames(symbols, dates)

    def fake_init_client(self):
        self.client = None

    def fake_fetch_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        return frames[symbol].copy()

    def fake_load_basic(self, symbols=None) -> pd.DataFrame:
        return pd.DataFrame()

    monkeypatch.setattr(DataInterface, "_init_client", fake_init_client)
    monkeypatch.setattr(DataInterface, "fetch_daily", fake_fetch_daily)
    monkeypatch.setattr(DataInterface, "load_basic", fake_load_basic)

    output_dir = tmp_path / "runs"
    benchmark_file = tmp_path / "benchmark_returns.csv"
    pd.DataFrame(
        {
            "trade_date": dates.strftime("%Y-%m-%d"),
            "benchmark_return": np.linspace(-0.01, 0.02, len(dates)),
        }
    ).to_csv(benchmark_file, index=False)

    config = {
        "market": "hk",
        "data": {
            "provider": "rqdata",
            "start_date": "20200101",
            "end_date": "20200530",
            "cache_dir": str(tmp_path / "cache"),
            "price_col": "close",
        },
        "universe": {
            "mode": "static",
            "require_by_date": False,
            "symbols": symbols,
            "min_symbols_per_date": 3,
            "drop_suspended": True,
            "suspended_policy": "mark",
        },
        "fundamentals": {"enabled": False},
        "label": {
            "horizon_mode": "next_rebalance",
            "rebalance_frequency": "W",
            "horizon_days": 5,
            "shift_days": 1,
            "target_col": "future_return",
        },
        "features": {
            "list": ["sma_5", "ret_5"],
            "params": {"sma_windows": [5], "ret_windows": [5]},
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
            "n_quantiles": 3,
            "rebalance_frequency": "W",
            "top_k": 2,
            "signal_direction_mode": "fixed",
            "signal_direction": 1,
            "transaction_cost_bps": 0,
            "sample_on_rebalance_dates": False,
            "report_train_ic": False,
            "save_artifacts": True,
            "save_dataset": False,
            "output_dir": str(output_dir),
            "run_name": "e2e_external_benchmark",
            "walk_forward": {
                "enabled": False,
            },
        },
        "backtest": {
            "enabled": True,
            "top_k": 2,
            "rebalance_frequency": "W",
            "transaction_cost_bps": 0,
            "long_only": True,
            "exit_mode": "rebalance",
            "benchmark_returns_file": str(benchmark_file),
        },
    }

    config_path = tmp_path / "config.yml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    pipeline.run(str(config_path))

    run_dirs = list(Path(output_dir).glob("e2e_external_benchmark_*"))
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["backtest"]["benchmark_symbol"] is None
    assert summary["backtest"]["benchmark_returns_file"] == str(benchmark_file.resolve())
    assert summary["backtest"]["benchmark"] is not None
    assert summary["backtest"]["active"] is not None
    assert summary["backtest"]["report_file"] == str((run_dir / "backtest_report.csv").resolve())
    assert (run_dir / "backtest_benchmark.csv").exists()
    assert (run_dir / "backtest_active.csv").exists()
    assert (run_dir / "backtest_report.csv").exists()


def test_pipeline_backtest_writes_compare_benchmark_reports(tmp_path, monkeypatch):
    dates = pd.date_range("2020-01-01", periods=320, freq="B")
    symbols = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    frames = _build_daily_frames(symbols, dates)

    def fake_init_client(self):
        self.client = None

    def fake_fetch_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        return frames[symbol].copy()

    def fake_load_basic(self, symbols=None) -> pd.DataFrame:
        return pd.DataFrame()

    monkeypatch.setattr(DataInterface, "_init_client", fake_init_client)
    monkeypatch.setattr(DataInterface, "fetch_daily", fake_fetch_daily)
    monkeypatch.setattr(DataInterface, "load_basic", fake_load_basic)

    output_dir = tmp_path / "runs"
    benchmark_primary_file = tmp_path / "benchmark_primary.csv"
    benchmark_alt_file = tmp_path / "benchmark_alt.csv"
    pd.DataFrame(
        {
            "trade_date": dates.strftime("%Y-%m-%d"),
            "benchmark_return": np.linspace(-0.01, 0.02, len(dates)),
        }
    ).to_csv(benchmark_primary_file, index=False)
    pd.DataFrame(
        {
            "trade_date": dates.strftime("%Y-%m-%d"),
            "benchmark_return": np.linspace(-0.015, 0.015, len(dates)),
        }
    ).to_csv(benchmark_alt_file, index=False)

    config = {
        "market": "hk",
        "data": {
            "provider": "rqdata",
            "start_date": "20200101",
            "end_date": "20210331",
            "cache_dir": str(tmp_path / "cache"),
            "price_col": "close",
        },
        "universe": {
            "mode": "static",
            "require_by_date": False,
            "symbols": symbols,
            "min_symbols_per_date": 3,
            "drop_suspended": True,
            "suspended_policy": "mark",
        },
        "fundamentals": {"enabled": False},
        "label": {
            "horizon_mode": "next_rebalance",
            "rebalance_frequency": "W",
            "horizon_days": 5,
            "shift_days": 1,
            "target_col": "future_return",
        },
        "features": {
            "list": ["sma_5", "ret_5"],
            "params": {"sma_windows": [5], "ret_windows": [5]},
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
            "n_quantiles": 3,
            "rebalance_frequency": "W",
            "top_k": 2,
            "signal_direction_mode": "fixed",
            "signal_direction": 1,
            "transaction_cost_bps": 0,
            "sample_on_rebalance_dates": False,
            "report_train_ic": False,
            "save_artifacts": True,
            "save_dataset": False,
            "output_dir": str(output_dir),
            "run_name": "e2e_benchmark_compare",
            "walk_forward": {
                "enabled": False,
            },
        },
        "backtest": {
            "enabled": True,
            "top_k": 2,
            "rebalance_frequency": "W",
            "transaction_cost_bps": 0,
            "long_only": True,
            "exit_mode": "rebalance",
            "benchmark_returns_file": str(benchmark_primary_file),
            "benchmark_compare": [
                {
                    "name": "primary_capw",
                    "returns_file": str(benchmark_primary_file),
                },
                {
                    "name": "alt_capw",
                    "returns_file": str(benchmark_alt_file),
                },
            ],
        },
    }

    config_path = tmp_path / "config.yml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    pipeline.run(str(config_path))

    run_dirs = list(Path(output_dir).glob("e2e_benchmark_compare_*"))
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    benchmark_compare = summary["backtest"]["benchmark_compare"]
    assert benchmark_compare["summary_file"] == str(
        (run_dir / "backtest_benchmark_compare_summary.csv").resolve()
    )
    assert len(benchmark_compare["benchmarks"]) == 2
    assert any(entry["is_primary"] for entry in benchmark_compare["benchmarks"])
    assert all(Path(entry["report_file"]).exists() for entry in benchmark_compare["benchmarks"])

    compare_report = pd.read_csv(run_dir / "backtest_benchmark_compare_primary_capw.csv")
    assert {
        "trade_date",
        "strategy_return",
        "strategy_nav",
        "benchmark_return",
        "benchmark_nav",
        "active_return",
        "relative_nav",
        "strategy_rolling_cagr_1y",
        "strategy_rolling_cagr_3y",
        "strategy_rolling_cagr_5y",
        "strategy_rolling_max_drawdown_1y",
        "strategy_rolling_max_drawdown_3y",
        "strategy_rolling_max_drawdown_5y",
    }.issubset(compare_report.columns)
    compare_summary = pd.read_csv(run_dir / "backtest_benchmark_compare_summary.csv")
    assert {"name", "benchmark_ann_return", "active_information_ratio", "report_file"}.issubset(
        compare_summary.columns
    )


@pytest.mark.integration
def test_pipeline_records_exp_decay_and_train_window_summary(tmp_path, monkeypatch):
    dates = pd.date_range("2020-01-01", periods=80, freq="B")
    symbols = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    frames = _build_daily_frames(symbols, dates)

    def fake_init_client(self):
        self.client = None

    def fake_fetch_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        return frames[symbol].copy()

    def fake_load_basic(self, symbols=None) -> pd.DataFrame:
        return pd.DataFrame()

    monkeypatch.setattr(DataInterface, "_init_client", fake_init_client)
    monkeypatch.setattr(DataInterface, "fetch_daily", fake_fetch_daily)
    monkeypatch.setattr(DataInterface, "load_basic", fake_load_basic)

    output_dir = tmp_path / "runs"
    config = {
        "market": "hk",
        "data": {
            "provider": "rqdata",
            "start_date": "20200101",
            "end_date": "20200430",
            "cache_dir": str(tmp_path / "cache"),
            "price_col": "close",
        },
        "universe": {
            "mode": "static",
            "require_by_date": False,
            "symbols": symbols,
            "min_symbols_per_date": 3,
            "drop_suspended": True,
            "suspended_policy": "mark",
        },
        "fundamentals": {"enabled": False},
        "label": {
            "horizon_mode": "fixed",
            "horizon_days": 5,
            "shift_days": 1,
            "target_col": "future_return",
        },
        "features": {
            "list": ["sma_5", "ret_5"],
            "params": {"sma_windows": [5], "ret_windows": [5]},
            "cross_sectional": {"method": "none"},
        },
        "model": {
            "type": "ridge",
            "params": {"alpha": 1.0},
            "sample_weight_mode": "exp_decay",
            "sample_weight_params": {"halflife": 10},
            "train_window": {"mode": "rolling", "size": 15, "unit": "dates"},
        },
        "eval": {
            "test_size": 0.25,
            "n_splits": 2,
            "n_quantiles": 3,
            "rebalance_frequency": "W",
            "top_k": 2,
            "signal_direction_mode": "fixed",
            "signal_direction": 1,
            "transaction_cost_bps": 0,
            "sample_on_rebalance_dates": False,
            "report_train_ic": False,
            "save_artifacts": True,
            "save_dataset": False,
            "output_dir": str(output_dir),
            "run_name": "e2e_train_window",
            "walk_forward": {"enabled": False},
        },
        "backtest": {"enabled": False},
    }

    config_path = tmp_path / "config.yml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    pipeline.run(str(config_path))

    run_dirs = list(Path(output_dir).glob("e2e_train_window_*"))
    assert len(run_dirs) == 1
    summary = json.loads((run_dirs[0] / "summary.json").read_text(encoding="utf-8"))
    assert summary["run"]["sample_weight_mode"] == "exp_decay"
    assert summary["run"]["sample_weight_params"]["halflife"] == 10
    assert summary["run"]["train_window"] == {"mode": "rolling", "size": 15, "unit": "dates"}
    assert summary["split"]["train_dates_raw"] > summary["split"]["train_dates"]
    assert summary["split"]["train_dates"] == 15
