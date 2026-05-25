from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import yaml

from cstree.current_assets import (
    build_hk_current_contract,
    build_dataset_registry_rows,
    default_hk_current_contract_path,
    hk_current_candidate_paths,
    write_current_contract,
)
from cstree.data_tools.rqdata_assets.current_health import inspect_hk_current_health


def _symlink(target: Path, link: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(target.name)


def _write_manifest(asset_dir: Path, *, dataset: str, end_date: str, status: str = "completed") -> None:
    (asset_dir / "data").mkdir(parents=True, exist_ok=True)
    manifest = {
        "dataset": dataset,
        "status": status,
        "output_dir": str(asset_dir),
        "query": {"end_date": end_date},
    }
    (asset_dir / "manifest.yml").write_text(
        yaml.safe_dump(manifest, sort_keys=False),
        encoding="utf-8",
    )


def test_inspect_hk_current_health_flags_stale_universe(tmp_path):
    artifacts_root = tmp_path / "artifacts"
    candidate_paths = hk_current_candidate_paths(artifacts_root)

    daily_clean_snapshot = (
        artifacts_root
        / "assets"
        / "rqdata"
        / "hk"
        / "daily"
        / "hk_all_2000_20260409_daily_clean_refetched_latest"
    )
    _write_manifest(daily_clean_snapshot, dataset="daily", end_date="20260409")
    (daily_clean_snapshot / "data" / "00005.HK.parquet").write_text("daily-clean", encoding="utf-8")
    _symlink(daily_clean_snapshot, candidate_paths["daily_clean"])

    instruments_snapshot = (
        artifacts_root
        / "assets"
        / "rqdata"
        / "hk"
        / "instruments"
        / "hk_all_instruments_20260409.parquet"
    )
    instruments_snapshot.parent.mkdir(parents=True, exist_ok=True)
    instruments_snapshot.write_text("instruments", encoding="utf-8")
    _symlink(instruments_snapshot, candidate_paths["instruments"])

    candidate_paths["universe_by_date"].parent.mkdir(parents=True, exist_ok=True)
    candidate_paths["universe_by_date"].write_text(
        "trade_date,symbol\n20260326,00005.HK\n",
        encoding="utf-8",
    )
    candidate_paths["universe_symbols"].write_text("00005.HK\n", encoding="utf-8")
    candidate_paths["universe_meta"].write_text(
        yaml.safe_dump(
            {
                "settings": {
                    "daily_asset_dir": str(
                        artifacts_root
                        / "assets"
                        / "rqdata"
                        / "hk"
                        / "daily"
                        / "hk_all_2000_20260326_daily_final_latest"
                    ),
                    "end_date": "20260326",
                },
                "build": {
                    "last_trade_date": "20260326",
                    "last_rebalance_date": "20260326",
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    contract = build_hk_current_contract(
        artifacts_root,
        generated_by="test_current_health",
        target_date="20260409",
    )
    write_current_contract(default_hk_current_contract_path(artifacts_root), contract)

    out_path = tmp_path / "hk_current_health.json"
    args = SimpleNamespace(
        artifacts_root=str(artifacts_root),
        current_contract=None,
        asset=[
            "daily_clean",
            "instruments",
            "universe_by_date",
            "universe_symbols",
            "universe_meta",
        ],
        target_date="20260409",
        format="json",
        out=str(out_path),
        fail_on_severity="warning",
    )

    exit_code = inspect_hk_current_health(args)

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert payload["summary"]["contract_exists"] is True
    assert payload["summary"]["target_date"] == "20260409"
    assert payload["quality_verdict"]["overall_severity"] == "error"
    lagging_assets = {
        item["asset_key"]
        for item in payload["quality_checks"]
        if item["check"] == "asset_as_of_lagging_target_date"
    }
    assert lagging_assets == {"universe_by_date", "universe_symbols", "universe_meta"}
    assert any(
        item["check"] == "universe_source_daily_asset_lagging_target_date"
        and item["asset_key"] == "universe_meta"
        for item in payload["quality_checks"]
    )
    assert payload["assets"]["daily_clean"]["effective_as_of"] == "20260409"
    assert payload["assets"]["universe_meta"]["effective_as_of"] == "20260326"


def test_inspect_hk_current_health_falls_back_when_contract_is_missing(tmp_path):
    artifacts_root = tmp_path / "artifacts"
    candidate_paths = hk_current_candidate_paths(artifacts_root)

    daily_clean_snapshot = (
        artifacts_root
        / "assets"
        / "rqdata"
        / "hk"
        / "daily"
        / "hk_all_2000_20260409_daily_clean_refetched_latest"
    )
    _write_manifest(daily_clean_snapshot, dataset="daily", end_date="20260409")
    (daily_clean_snapshot / "data" / "00005.HK.parquet").write_text("daily-clean", encoding="utf-8")
    _symlink(daily_clean_snapshot, candidate_paths["daily_clean"])

    out_path = tmp_path / "hk_current_health_missing_contract.json"
    args = SimpleNamespace(
        artifacts_root=str(artifacts_root),
        current_contract=None,
        asset=["daily_clean"],
        target_date="20260409",
        format="json",
        out=str(out_path),
        fail_on_severity="error",
    )

    exit_code = inspect_hk_current_health(args)

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert payload["summary"]["contract_exists"] is False
    assert payload["quality_verdict"]["gate_triggered"] is True
    assert any(
        item["check"] == "current_contract_missing"
        for item in payload["quality_checks"]
    )
    assert payload["assets"]["daily_clean"]["effective_as_of"] == "20260409"


def test_inspect_hk_current_health_accepts_etf_daily_clean_current_key(tmp_path):
    artifacts_root = tmp_path / "artifacts"
    candidate_paths = hk_current_candidate_paths(artifacts_root)

    etf_clean_snapshot = (
        artifacts_root
        / "assets"
        / "rqdata"
        / "hk"
        / "daily"
        / "hk_etf_2000_20260409_daily_clean_latest"
    )
    _write_manifest(etf_clean_snapshot, dataset="daily", end_date="20260409")
    (etf_clean_snapshot / "data" / "02800.HK.parquet").write_text("etf-clean", encoding="utf-8")
    _symlink(etf_clean_snapshot, candidate_paths["etf_daily_clean"])

    contract = build_hk_current_contract(
        artifacts_root,
        generated_by="test_current_health",
        target_date="20260409",
    )
    write_current_contract(default_hk_current_contract_path(artifacts_root), contract)

    out_path = tmp_path / "hk_current_health_etf_clean.json"
    args = SimpleNamespace(
        artifacts_root=str(artifacts_root),
        current_contract=None,
        asset=["etf_daily_clean"],
        target_date="20260409",
        format="json",
        out=str(out_path),
        fail_on_severity="warning",
    )

    exit_code = inspect_hk_current_health(args)

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["assets"]["etf_daily_clean"]["effective_as_of"] == "20260409"
    assert payload["quality_checks"] == []


def test_inspect_hk_current_health_accepts_tick_depth_daily_contract_key(tmp_path):
    artifacts_root = tmp_path / "artifacts"
    candidate_paths = hk_current_candidate_paths(artifacts_root)

    tick_daily_snapshot = (
        artifacts_root
        / "assets"
        / "rqdata"
        / "hk"
        / "tick_depth_daily"
        / "hk_tick_depth_daily_core_20250401_20260409"
    )
    (tick_daily_snapshot / "data").mkdir(parents=True, exist_ok=True)
    (tick_daily_snapshot / "data" / "data.parquet").write_text("tick-depth-daily", encoding="utf-8")
    (tick_daily_snapshot / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "tick_depth_daily.v1",
                "provider": "rqdata",
                "market": "hk",
                "frequency": "daily",
                "row_count": 123,
                "symbol_count": 2,
                "date_range": {"start": "20250401", "end": "20260409"},
                "files": ["data/data.parquet"],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    _symlink(tick_daily_snapshot, candidate_paths["tick_depth_daily"])

    contract = build_hk_current_contract(
        artifacts_root,
        generated_by="test_current_health",
        target_date="20260409",
    )
    write_current_contract(default_hk_current_contract_path(artifacts_root), contract)

    out_path = tmp_path / "hk_current_health_tick_depth_daily.json"
    args = SimpleNamespace(
        artifacts_root=str(artifacts_root),
        current_contract=None,
        asset=["tick_depth_daily"],
        target_date="20260409",
        format="json",
        out=str(out_path),
        fail_on_severity="warning",
    )

    exit_code = inspect_hk_current_health(args)

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    registry_rows = build_dataset_registry_rows(contract)
    tick_row = next(row for row in registry_rows if row["dataset_name"] == "hk_tick_depth_daily")
    assert exit_code == 0
    assert payload["assets"]["tick_depth_daily"]["effective_as_of"] == "20260409"
    assert payload["assets"]["tick_depth_daily"]["manifest"]["dataset"] == "tick_depth_daily"
    assert payload["quality_checks"] == []
    assert tick_row["source"] == "derived"
    assert tick_row["records"] == "123"
    assert tick_row["symbols"] == "2"


def test_inspect_hk_current_health_uses_asset_freshness_tolerance(tmp_path):
    artifacts_root = tmp_path / "artifacts"
    candidate_paths = hk_current_candidate_paths(artifacts_root)

    pit_snapshot = (
        artifacts_root
        / "assets"
        / "rqdata"
        / "hk"
        / "pit_financials"
        / "hk_all_2000_2025_full_market_asof_20260430"
    )
    _write_manifest(pit_snapshot, dataset="pit_financials", end_date="20260430")
    (pit_snapshot / "data" / "00005.HK.parquet").write_text("pit", encoding="utf-8")
    _symlink(pit_snapshot, candidate_paths["pit"])

    contract = build_hk_current_contract(
        artifacts_root,
        generated_by="test_current_health",
        target_date="20260508",
    )
    write_current_contract(default_hk_current_contract_path(artifacts_root), contract)

    out_path = tmp_path / "hk_current_health_pit_tolerance.json"
    args = SimpleNamespace(
        artifacts_root=str(artifacts_root),
        current_contract=None,
        asset=["pit"],
        target_date="20260508",
        format="json",
        out=str(out_path),
        fail_on_severity="warning",
    )

    exit_code = inspect_hk_current_health(args)

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["summary"]["stale_assets"] == 0
    assert payload["quality_checks"] == []
    assert payload["assets"]["pit"]["freshness_policy"] == {
        "cadence": "filing_asof",
        "allowed_lag_days": 45,
    }
