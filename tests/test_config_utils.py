from pathlib import Path

import yaml

from csml.config_utils import resolve_pipeline_config
from csml.data_tools import build_hk_connect_universe, build_hk_daily_asset_universe


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
