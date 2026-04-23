from pathlib import Path

import pytest
import yaml

import cstree.config_utils as config_utils
from cstree.config_utils import (
    get_research_universe_config,
    resolve_pipeline_config,
    resolve_pipeline_filename,
)
from cstree.data_tools import build_hk_connect_universe, build_hk_daily_asset_universe


def test_resolve_pipeline_config_supports_repo_relative_extends_outside_repo_root(
    tmp_path,
    monkeypatch,
):
    config_path = tmp_path / "external.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "extends": "configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml",
                "eval": {"run_name": "external_demo"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    resolved = resolve_pipeline_config(str(config_path)).data

    assert resolved["market"] == "hk"
    assert resolved["model"]["type"] == "xgb_regressor"
    assert resolved["eval"]["run_name"] == "external_demo"


def test_resolve_pipeline_config_allows_shared_base_dag(tmp_path):
    base = tmp_path / "base.yml"
    left = tmp_path / "left.yml"
    right = tmp_path / "right.yml"
    top = tmp_path / "top.yml"

    base.write_text(yaml.safe_dump({"base": 1}, sort_keys=False), encoding="utf-8")
    left.write_text(yaml.safe_dump({"extends": "base.yml", "left": 1}, sort_keys=False), encoding="utf-8")
    right.write_text(
        yaml.safe_dump({"extends": "base.yml", "right": 1}, sort_keys=False),
        encoding="utf-8",
    )
    top.write_text(
        yaml.safe_dump({"extends": ["left.yml", "right.yml"], "top": 1}, sort_keys=False),
        encoding="utf-8",
    )

    resolved = resolve_pipeline_config(str(top)).data

    assert resolved == {"base": 1, "left": 1, "right": 1, "top": 1}


def test_universe_config_defaults_resolve_outside_repo_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    hk_connect = build_hk_connect_universe.load_yaml_config(None)
    hk_all_assets = build_hk_daily_asset_universe.load_yaml_config(None)

    assert hk_connect["hk_connect_universe"]["rebalance_frequency"] == "M"
    assert hk_all_assets["hk_daily_asset_universe"]["rebalance_frequency"] == "M"


def test_linear_provider_overlay_validate_variants_do_not_inherit_xgb_params():
    ridge_cfg = resolve_pipeline_config(
        "configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_ridge_validate.yml"
    ).data
    elasticnet_cfg = resolve_pipeline_config(
        "configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_elasticnet_validate.yml"
    ).data

    ridge_params = ridge_cfg["model"]["params"]
    elasticnet_params = elasticnet_cfg["model"]["params"]

    assert ridge_cfg["model"]["type"] == "ridge"
    assert elasticnet_cfg["model"]["type"] == "elasticnet"
    assert "n_estimators" not in ridge_params
    assert "learning_rate" not in ridge_params
    assert "n_estimators" not in elasticnet_params
    assert "learning_rate" not in elasticnet_params


def test_provider_dense_quarterly_variant_replaces_sparse_pit_block():
    cfg = resolve_pipeline_config(
        "configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_dense.yml"
    ).data

    feature_list = cfg["features"]["list"]
    missing_features = cfg["features"]["missing"]["features"]
    fundamentals_features = cfg["fundamentals"]["features"]

    assert cfg["eval"]["run_name"] == "hk_sel_q_variant_pit_core_hybrid_provider_dense_xgb_reg"
    assert feature_list == [
        "ret_60",
        "ret_120",
        "ret_240",
        "rv_60",
        "rv_120",
        "volume_sma20_ratio",
        "volume_sma60_ratio",
        "log_vol",
        "vol",
        "total_assets",
        "total_liabilities",
        "leverage",
        "days_since_report",
    ]
    assert missing_features == [
        "total_assets",
        "total_liabilities",
        "leverage",
        "days_since_report",
    ]
    assert fundamentals_features == ["total_assets", "total_liabilities"]
    assert "sales" not in feature_list
    assert "growth_sales" not in feature_list
    assert "net_profit" not in feature_list
    assert "cash_flow_from_operating_activities" not in feature_list


def test_resolve_pipeline_config_normalizes_legacy_universe_to_research_universe(tmp_path):
    config_path = tmp_path / "legacy_universe.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "market": "hk",
                "universe": {
                    "mode": "pit",
                    "by_date_file": "artifacts/assets/universe/demo_by_date.csv",
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    resolved = resolve_pipeline_config(str(config_path)).data

    assert "universe" not in resolved
    assert resolved["research_universe"]["mode"] == "pit"
    assert (
        resolved["research_universe"]["by_date_file"]
        == "artifacts/assets/universe/demo_by_date.csv"
    )


def test_get_research_universe_config_prefers_canonical_key():
    cfg = {"research_universe": {"mode": "pit"}, "model": {"type": "ridge"}}

    assert get_research_universe_config(cfg) == {"mode": "pit"}


def test_get_research_universe_config_accepts_legacy_key():
    cfg = {"universe": {"mode": "static", "symbols": ["00005.HK"]}}

    assert get_research_universe_config(cfg) == {
        "mode": "static",
        "symbols": ["00005.HK"],
    }


def test_get_research_universe_config_rejects_conflicting_keys():
    cfg = {"research_universe": {"mode": "pit"}, "universe": {"mode": "static"}}

    with pytest.raises(SystemExit, match="both research_universe and legacy universe"):
        get_research_universe_config(cfg)


def test_resolve_pipeline_config_allows_research_universe_to_override_legacy_base(tmp_path):
    base = tmp_path / "base.yml"
    child = tmp_path / "child.yml"

    base.write_text(
        yaml.safe_dump(
            {
                "market": "hk",
                "universe": {
                    "mode": "pit",
                    "by_date_file": "artifacts/assets/universe/base_by_date.csv",
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    child.write_text(
        yaml.safe_dump(
            {
                "extends": "base.yml",
                "research_universe": {
                    "mode": "pit",
                    "by_date_file": "artifacts/assets/universe/child_by_date.csv",
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    resolved = resolve_pipeline_config(str(child)).data

    assert "universe" not in resolved
    assert (
        resolved["research_universe"]["by_date_file"]
        == "artifacts/assets/universe/child_by_date.csv"
    )


def test_resolve_pipeline_config_rejects_conflicting_research_universe_keys(tmp_path):
    config_path = tmp_path / "conflict.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "market": "hk",
                "universe": {"mode": "pit"},
                "research_universe": {"mode": "static"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="both research_universe and legacy universe"):
        resolve_pipeline_config(str(config_path))


def test_pipeline_aliases_fail_fast_when_repo_configs_are_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(config_utils, "_iter_repo_root_candidates", lambda: [tmp_path])

    with pytest.raises(SystemExit, match="Repository configs/ directory not found"):
        resolve_pipeline_config("default")

    with pytest.raises(SystemExit, match="Repository configs/ directory not found"):
        resolve_pipeline_filename("hk")
