import copy
from pathlib import Path

import pytest
import yaml

from csml import pipeline
from csml.config_utils import resolve_pipeline_config
from csml.data_interface import DataInterface


def _base_config(tmp_path):
    return {
        "market": "us",
        "data": {
            "provider": "tushare",
            "start_date": "20200101",
            "end_date": "20200110",
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
            "run_name": "validation",
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


@pytest.fixture
def no_client(monkeypatch):
    monkeypatch.setattr(DataInterface, "_init_client", lambda self: None)


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        (("backtest", "exit_mode"), "oops", "backtest.exit_mode must be one of: rebalance, label_horizon."),
        (
            ("backtest", "exit_price_policy"),
            "oops",
            "backtest.exit_price_policy must be one of: strict, ffill, delay.",
        ),
        (
            ("backtest", "exit_fallback_policy"),
            "oops",
            "backtest.exit_fallback_policy must be one of: ffill, none.",
        ),
    ],
)
def test_pipeline_backtest_validation(tmp_path, no_client, key, value, message):
    config = copy.deepcopy(_base_config(tmp_path))
    cfg = config
    for part in key[:-1]:
        cfg = cfg[part]
    cfg[key[-1]] = value
    config_path = _write_config(tmp_path, config)
    with pytest.raises(SystemExit, match=message):
        pipeline.run(str(config_path))


def test_pipeline_live_train_mode_validation(tmp_path, no_client):
    config = copy.deepcopy(_base_config(tmp_path))
    config["live"] = {"enabled": False, "train_mode": "bad"}
    config_path = _write_config(tmp_path, config)
    with pytest.raises(SystemExit, match="live.train_mode must be one of: full, train."):
        pipeline.run(str(config_path))


def test_pipeline_live_requires_artifacts(tmp_path, no_client):
    config = copy.deepcopy(_base_config(tmp_path))
    config["eval"]["save_artifacts"] = False
    config["live"] = {"enabled": True, "train_mode": "full"}
    config_path = _write_config(tmp_path, config)
    with pytest.raises(
        SystemExit,
        match="live.enabled=true requires eval.save_artifacts=true to persist holdings.",
    ):
        pipeline.run(str(config_path))


def test_pipeline_model_type_validation(tmp_path, no_client):
    config = copy.deepcopy(_base_config(tmp_path))
    config["model"]["type"] = "random_forest"
    config_path = _write_config(tmp_path, config)
    with pytest.raises(SystemExit, match="Unsupported model.type: random_forest"):
        pipeline.run(str(config_path))


def test_pipeline_model_params_validation(tmp_path, no_client):
    config = copy.deepcopy(_base_config(tmp_path))
    config["model"]["params"] = "oops"
    config_path = _write_config(tmp_path, config)
    with pytest.raises(SystemExit, match="model.params must be a mapping."):
        pipeline.run(str(config_path))


def test_hk_benchmark_protocol_configs_align_research_unit():
    repo_root = Path(__file__).resolve().parents[1]
    config_paths = [
        repo_root / "configs" / "experiments" / "baseline" / "hk_selected__quarterly_price_only.yml",
        repo_root / "configs" / "experiments" / "baseline" / "hk_selected__quarterly_pit_core.yml",
        repo_root / "configs" / "experiments" / "baseline" / "hk_selected__quarterly_pit_core_hybrid.yml",
        repo_root / "configs" / "experiments" / "variants" / "hk_selected__quarterly_pit_core_hybrid_ridge.yml",
        repo_root / "configs" / "experiments" / "variants" / "hk_selected__quarterly_pit_core_hybrid_xgb_ranker.yml",
        repo_root / "configs" / "experiments" / "variants" / "hk_selected__quarterly_pit_core_hybrid_elasticnet.yml",
    ]

    payloads = [
        resolve_pipeline_config(str(path)).data
        for path in config_paths
    ]

    for payload in payloads:
        assert payload["market"] == "hk"
        assert payload["label"]["rebalance_frequency"] == "Q"
        assert payload["eval"]["rebalance_frequency"] == "Q"
        assert payload["backtest"]["rebalance_frequency"] == "Q"
        assert payload["backtest"]["benchmark_symbol"] == "02800.HK"
        assert payload["eval"]["sample_on_rebalance_dates"] is True
        assert payload["features"]["cross_sectional"]["method"] == "rank"

    price_cfg, pit_cfg, hybrid_cfg, ridge_cfg, ranker_cfg, elasticnet_cfg = payloads

    assert price_cfg["fundamentals"]["enabled"] is False
    assert "ret_240" in price_cfg["features"]["list"]
    assert "sales" not in price_cfg["features"]["list"]
    assert price_cfg["features"]["missing"] is None

    assert pit_cfg["fundamentals"]["enabled"] is True
    assert pit_cfg["fundamentals"]["source"] == "file"
    assert "sales" in pit_cfg["features"]["list"]
    assert "ret_240" not in pit_cfg["features"]["list"]
    assert pit_cfg["features"]["missing"]["add_indicators"] is False

    assert hybrid_cfg["fundamentals"]["source"] == "file"
    assert hybrid_cfg["model"]["type"] == "xgb_regressor"
    assert "ret_240" in hybrid_cfg["features"]["list"]
    assert "sales" in hybrid_cfg["features"]["list"]
    assert hybrid_cfg["features"]["missing"]["add_indicators"] is False

    for variant_cfg in (ridge_cfg, ranker_cfg, elasticnet_cfg):
        assert variant_cfg["fundamentals"] == hybrid_cfg["fundamentals"]
        assert variant_cfg["features"] == hybrid_cfg["features"]
        assert variant_cfg["universe"] == hybrid_cfg["universe"]
        assert variant_cfg["backtest"] == hybrid_cfg["backtest"]

    assert ridge_cfg["model"]["type"] == "ridge"
    assert ranker_cfg["model"]["type"] == "xgb_ranker"
    assert ranker_cfg["model"]["params"]["objective"] == "rank:pairwise"
    assert elasticnet_cfg["model"]["type"] == "elasticnet"
