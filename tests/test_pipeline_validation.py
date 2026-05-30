import copy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from cstree import pipeline
from cstree.config_utils import resolve_pipeline_config
from cstree.data_interface import DataInterface
from cstree.pipeline import runner as pipeline_runner
from cstree.pipeline.config import normalize_eval_settings
from cstree.pipeline.runner import _load_benchmark_return_series
from cstree.pipeline.stats import _ensure_execution_daily_fields


def _base_config(tmp_path):
    return {
        "market": "hk",
        "data": {
            "provider": "rqdata",
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
            "save_scored_artifact": False,
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


def test_pipeline_backtest_rejects_multiple_benchmark_sources(tmp_path, no_client):
    config = copy.deepcopy(_base_config(tmp_path))
    benchmark_file = tmp_path / "benchmark.csv"
    benchmark_file.write_text("trade_date,benchmark_return\n20200103,0.01\n", encoding="utf-8")
    config["backtest"]["benchmark_symbol"] = "02800.HK"
    config["backtest"]["benchmark_returns_file"] = str(benchmark_file)
    config_path = _write_config(tmp_path, config)
    with pytest.raises(
        SystemExit,
        match="backtest.benchmark_symbol and backtest.benchmark_returns_file are mutually exclusive.",
    ):
        pipeline.run(str(config_path))


@pytest.mark.parametrize(
    "benchmark_compare",
    [
        [{"name": "bad"}],
        [{"name": "bad", "symbol": "3432.HK", "returns_file": "foo.csv"}],
    ],
)
def test_pipeline_backtest_rejects_invalid_compare_benchmark_specs(
    tmp_path,
    no_client,
    benchmark_compare,
):
    config = copy.deepcopy(_base_config(tmp_path))
    config["backtest"]["benchmark_compare"] = benchmark_compare
    config_path = _write_config(tmp_path, config)
    with pytest.raises(
        SystemExit,
        match="backtest.benchmark_compare\\[0\\] must provide exactly one of returns_file or symbol.",
    ):
        pipeline.run(str(config_path))


def test_pipeline_backtest_rejects_invalid_tearsheet_config(tmp_path, no_client):
    config = copy.deepcopy(_base_config(tmp_path))
    config["backtest"]["tearsheet"] = "yes"
    config_path = _write_config(tmp_path, config)

    with pytest.raises(
        SystemExit,
        match="backtest.tearsheet must be a boolean or a mapping with enabled.",
    ):
        pipeline.run(str(config_path))


def test_load_benchmark_return_series_accepts_yyyymmdd_csv(tmp_path):
    benchmark_file = tmp_path / "benchmark.csv"
    benchmark_file.write_text(
        "trade_date,benchmark_return\n20200103,0.01\n20200106,-0.02\n",
        encoding="utf-8",
    )

    series = _load_benchmark_return_series(benchmark_file)

    assert series.index.tolist() == [
        pd.Timestamp("2020-01-03"),
        pd.Timestamp("2020-01-06"),
    ]
    assert series.tolist() == pytest.approx([0.01, -0.02])


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


def test_pipeline_quality_gate_blocks_before_panel_load(tmp_path, no_client, monkeypatch):
    config = copy.deepcopy(_base_config(tmp_path))
    config["quality"] = {"fail_on_severity": "warning"}
    config["fundamentals"] = {
        "enabled": True,
        "source": "file",
        "file": str(tmp_path / "pit.parquet"),
        "features": ["revenue"],
    }
    config_path = _write_config(tmp_path, config)

    monkeypatch.setattr(
        pipeline_runner,
        "run_quality_preflight",
        lambda **_kwargs: {
            "enabled": True,
            "fail_on_severity": "warning",
            "checks": [
                {
                    "name": "hk_pit_coverage_health",
                    "report_file": str(tmp_path / "runs" / "validation_quality" / "quality" / "hk_pit_coverage_preflight.json"),
                }
            ],
            "overall_verdict": {
                "color": "red",
                "overall_severity": "error",
                "issue_count": 2,
                "severity_counts": {"error": 1, "warning": 1, "info": 0},
                "fail_on_severity": "warning",
                "gate_triggered": True,
                "gate_status": "fail",
                "failing_issue_count": 2,
                "sample_failing_checks": ["hk_pit_coverage_health"],
                "message": "2 quality issue(s) met fail_on_severity=warning; the inspection gate was triggered.",
            },
            "gate_triggered": True,
            "message": "2 quality issue(s) met fail_on_severity=warning; the inspection gate was triggered.",
        },
    )
    monkeypatch.setattr(
        pipeline_runner,
        "_load_research_panel",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("_load_research_panel should not run")),
    )

    with pytest.raises(SystemExit, match="Pipeline quality gate failed: 2 quality issue\\(s\\) met fail_on_severity=warning"):
        pipeline.run(str(config_path))


def test_execution_daily_fields_expands_rqdata_list_fields():
    data_cfg = {
        "rqdata": {
            "fields": ["close", "volume", "total_turnover"],
        }
    }

    _ensure_execution_daily_fields(
        data_cfg=data_cfg,
        provider="rqdata",
        required_columns={"open", "close", "amount"},
    )

    assert data_cfg["rqdata"]["fields"] == [
        "close",
        "volume",
        "total_turnover",
        "open",
    ]


def test_pipeline_scored_artifact_requires_artifacts(tmp_path, no_client):
    config = copy.deepcopy(_base_config(tmp_path))
    config["eval"]["save_artifacts"] = False
    config["eval"]["save_scored_artifact"] = True
    config_path = _write_config(tmp_path, config)
    with pytest.raises(
        SystemExit,
        match="eval.save_scored_artifact=true requires eval.save_artifacts=true.",
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


def test_pipeline_train_target_transform_validation(tmp_path, no_client):
    config = copy.deepcopy(_base_config(tmp_path))
    config["label"]["train_target_transform"] = "oops"
    config_path = _write_config(tmp_path, config)
    with pytest.raises(SystemExit, match="label.train_target_transform must be one of: none, zscore, rank."):
        pipeline.run(str(config_path))


def test_pipeline_exp_decay_requires_weight_params(tmp_path, no_client):
    config = copy.deepcopy(_base_config(tmp_path))
    config["model"]["sample_weight_mode"] = "exp_decay"
    config_path = _write_config(tmp_path, config)
    with pytest.raises(
        SystemExit,
        match="model.sample_weight_mode=exp_decay requires model.sample_weight_params.halflife or decay_rate.",
    ):
        pipeline.run(str(config_path))


@pytest.mark.parametrize(
    ("train_window", "message"),
    [
        ({"mode": "oops", "size": 4, "unit": "dates"}, "model.train_window.mode must be one of: full, rolling."),
        ({"mode": "rolling", "unit": "dates"}, "model.train_window.size is required when model.train_window.mode=rolling."),
        ({"mode": "rolling", "size": 0, "unit": "dates"}, "model.train_window.size must be a positive integer."),
        ({"mode": "rolling", "size": 4, "unit": "months"}, "model.train_window.unit must be one of: dates, years."),
    ],
)
def test_pipeline_train_window_validation(tmp_path, no_client, train_window, message):
    config = copy.deepcopy(_base_config(tmp_path))
    config["model"]["train_window"] = train_window
    config_path = _write_config(tmp_path, config)
    with pytest.raises(SystemExit, match=message):
        pipeline.run(str(config_path))


def test_pipeline_low_coverage_split_error_is_informative(tmp_path, no_client, monkeypatch):
    dates = pd.date_range("2020-01-01", periods=10, freq="B")
    frames = {}
    for idx, symbol in enumerate(["AAA", "BBB", "CCC"]):
        close = 100.0 + np.arange(len(dates), dtype=float) + idx
        vol = np.full(len(dates), 1000.0 + idx, dtype=float)
        frames[symbol] = pd.DataFrame(
            {
                "trade_date": [date.strftime("%Y%m%d") for date in dates],
                "symbol": symbol,
                "close": close,
                "vol": vol,
                "amount": close * vol,
            }
        )

    monkeypatch.setattr(
        DataInterface,
        "fetch_daily",
        lambda self, symbol, start_date, end_date: frames[symbol].copy(),
    )
    monkeypatch.setattr(DataInterface, "load_basic", lambda self, symbols=None: pd.DataFrame())

    config = copy.deepcopy(_base_config(tmp_path))
    config["data"]["end_date"] = "20200114"
    config["features"]["list"] = ["sma_20"]
    config["features"]["params"] = {"sma_windows": [20]}
    config_path = _write_config(tmp_path, config)

    with pytest.raises(
        SystemExit,
        match="selected feature set left too few complete dates",
    ):
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
        assert variant_cfg["research_universe"] == hybrid_cfg["research_universe"]
        assert variant_cfg["backtest"] == hybrid_cfg["backtest"]

    assert ridge_cfg["model"]["type"] == "ridge"
    assert ranker_cfg["model"]["type"] == "xgb_ranker"
    assert ranker_cfg["model"]["params"]["objective"] == "rank:pairwise"
    assert elasticnet_cfg["model"]["type"] == "elasticnet"


def test_normalize_eval_settings_accepts_score_postprocess_mapping():
    settings = normalize_eval_settings(
        {
            "score_postprocess": {
                "method": "neutralize",
                "columns": ["log_mcap"],
                "strength": 0.5,
                "min_obs": 7,
            }
        }
    )

    assert settings["SCORE_POSTPROCESS_ENABLED"] is True
    assert settings["SCORE_POSTPROCESS_METHOD"] == "neutralize"
    assert settings["SCORE_POSTPROCESS_COLUMNS"] == ["log_mcap"]
    assert settings["SCORE_POSTPROCESS_STRENGTH"] == pytest.approx(0.5)
    assert settings["SCORE_POSTPROCESS_MIN_OBS"] == 7


def test_normalize_eval_settings_rejects_invalid_score_postprocess_strength():
    with pytest.raises(
        SystemExit,
        match="eval.score_postprocess.strength must be between 0 and 1.",
    ):
        normalize_eval_settings(
            {
                "score_postprocess": {
                    "method": "neutralize",
                    "columns": ["log_mcap"],
                    "strength": 1.5,
                }
            }
        )
