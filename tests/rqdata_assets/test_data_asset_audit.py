from __future__ import annotations

import json
from types import SimpleNamespace

import pandas as pd
import yaml

from csml.current_assets import (
    build_hk_current_contract,
    default_hk_current_contract_path,
    hk_current_candidate_paths,
    write_current_contract,
)
from csml.data_tools.rqdata_assets.audit_assets import build_hk_data_asset_audit_report


def _symlink(target, link) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(target.name)


def _write_manifest(asset_dir, *, dataset: str, start_date: str = "20000101", end_date: str = "20260410") -> None:
    (asset_dir / "data").mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset": dataset,
        "status": "completed",
        "output_dir": str(asset_dir),
        "query": {"start_date": start_date, "end_date": end_date},
    }
    (asset_dir / "manifest.yml").write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _args(**overrides):
    payload = {
        "artifacts_root": "artifacts",
        "current_contract": None,
        "reports_dir": None,
        "target_date": "20260410",
        "asset": ["daily", "etf_daily", "intraday"],
        "scan_family": ["daily", "intraday"],
        "metadata_only_etf_daily": False,
        "intraday_mode": "metadata",
        "health_report": [],
        "run_refresh": False,
        "refresh_mode": "patch",
        "refresh_asset": [],
        "refresh_dry_run": False,
        "config": None,
        "execute_repair": False,
        "approved_repair_action": [],
        "delete_prune_candidates": False,
        "approved_prune_path": [],
        "sample_limit": 3,
        "format": "json",
        "out": None,
        "fail_on_severity": "none",
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_hk_data_asset_audit_reports_inventory_freshness_and_prune_plan(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    artifacts_root = repo_root / "artifacts"
    candidate_paths = hk_current_candidate_paths(artifacts_root)
    monkeypatch.chdir(repo_root)

    daily_snapshot = artifacts_root / "assets" / "rqdata" / "hk" / "daily" / "hk_all_2000_20260410_daily_latest"
    _write_manifest(daily_snapshot, dataset="daily")
    _symlink(daily_snapshot, candidate_paths["daily"])

    etf_snapshot = artifacts_root / "assets" / "rqdata" / "hk" / "daily" / "hk_etf_2000_20260410_daily_latest"
    _write_manifest(etf_snapshot, dataset="daily")
    (etf_snapshot / "symbols.txt").write_text("02800.HK\n03033.HK\n", encoding="utf-8")
    for symbol in ("02800.HK", "03033.HK"):
        pd.DataFrame(
            {
                "trade_date": ["20000103", "20260410"],
                "open": [1.0, 2.0],
                "high": [1.0, 2.0],
                "low": [1.0, 2.0],
                "close": [1.0, 2.0],
                "volume": [100.0, 200.0],
                "total_turnover": [100.0, 400.0],
            }
        ).to_parquet(etf_snapshot / "data" / f"{symbol}.parquet", index=False)
    _symlink(etf_snapshot, candidate_paths["etf_daily"])

    intraday_snapshot = artifacts_root / "assets" / "rqdata" / "hk" / "intraday" / "intraday_20240501_20260410"
    _write_manifest(intraday_snapshot, dataset="intraday", start_date="20240501", end_date="20260410")
    _symlink(intraday_snapshot, candidate_paths["intraday"])

    patch_snapshot = artifacts_root / "assets" / "rqdata" / "hk" / "daily" / "hk_etf_20260410_daily_patch"
    _write_manifest(patch_snapshot, dataset="daily", start_date="20260401", end_date="20260410")
    reports_dir = artifacts_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "hk_data_asset_audit_current.json").write_text(
        json.dumps({"path": str(patch_snapshot)}),
        encoding="utf-8",
    )

    contract = build_hk_current_contract(artifacts_root, generated_by="test", target_date="20260410")
    write_current_contract(default_hk_current_contract_path(artifacts_root), contract)

    report = build_hk_data_asset_audit_report(_args())

    assert report["target_date"] == "20260410"
    assert report["inventory"]["summary"]["current"] >= 3
    assert report["freshness"]["etf_daily"]["status"] == "pass"
    assert report["freshness"]["etf_daily"]["effective_end_date"] == "2026-04-10"
    assert report["freshness"]["intraday"]["status"] == "pass"
    assert report["freshness"]["intraday"]["latest_observed_trade_date"] == "2026-04-10"
    assert any(item["path"].endswith("hk_etf_20260410_daily_patch") for item in report["prune"]["candidates"])
    assert all(item["status"] == "dry-run" for item in report["prune"]["delete_result"]["results"])


def test_hk_data_asset_audit_classifies_stale_etf_daily_repair_candidate(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    artifacts_root = repo_root / "artifacts"
    candidate_paths = hk_current_candidate_paths(artifacts_root)
    monkeypatch.chdir(repo_root)

    etf_snapshot = artifacts_root / "assets" / "rqdata" / "hk" / "daily" / "hk_etf_2000_20260409_daily_latest"
    _write_manifest(etf_snapshot, dataset="daily", end_date="20260409")
    (etf_snapshot / "symbols.txt").write_text("02800.HK\n", encoding="utf-8")
    pd.DataFrame(
        {
            "trade_date": ["20000103", "20260409"],
            "close": [1.0, 2.0],
        }
    ).to_parquet(etf_snapshot / "data" / "02800.HK.parquet", index=False)
    _symlink(etf_snapshot, candidate_paths["etf_daily"])

    contract = build_hk_current_contract(artifacts_root, generated_by="test", target_date="20260410")
    write_current_contract(default_hk_current_contract_path(artifacts_root), contract)

    report = build_hk_data_asset_audit_report(
        _args(asset=["etf_daily"], scan_family=["daily"], metadata_only_etf_daily=False)
    )

    assert report["freshness"]["etf_daily"]["status"] == "fail"
    assert any(item["code"] == "asset_stale_before_target" for item in report["freshness"]["etf_daily"]["issues"])
    assert any(
        item["asset_key"] == "etf_daily" and item["action"] == "patch-refresh"
        for item in report["repair"]["candidates"]
    )


def test_hk_data_asset_audit_classifies_current_manifest_mismatch_as_repoint(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    artifacts_root = repo_root / "artifacts"
    candidate_paths = hk_current_candidate_paths(artifacts_root)
    monkeypatch.chdir(repo_root)

    daily_snapshot = artifacts_root / "assets" / "rqdata" / "hk" / "daily" / "hk_all_2000_20260410_daily_latest"
    _write_manifest(daily_snapshot, dataset="daily")
    manifest_path = daily_snapshot / "manifest.yml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["output_dir"] = str(daily_snapshot.parent / "stale_alias_target")
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    _symlink(daily_snapshot, candidate_paths["daily"])

    contract = build_hk_current_contract(artifacts_root, generated_by="test", target_date="20260410")
    write_current_contract(default_hk_current_contract_path(artifacts_root), contract)

    report = build_hk_data_asset_audit_report(_args(asset=["daily"], scan_family=["daily"]))

    assert any(
        item["asset_key"] == "daily" and item["action"] == "repoint"
        for item in report["repair"]["candidates"]
    )


def test_hk_data_asset_audit_writes_json_output(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    artifacts_root = repo_root / "artifacts"
    candidate_paths = hk_current_candidate_paths(artifacts_root)
    monkeypatch.chdir(repo_root)

    etf_snapshot = artifacts_root / "assets" / "rqdata" / "hk" / "daily" / "hk_etf_2000_20260410_daily_latest"
    _write_manifest(etf_snapshot, dataset="daily")
    (etf_snapshot / "symbols.txt").write_text("", encoding="utf-8")
    _symlink(etf_snapshot, candidate_paths["etf_daily"])
    contract = build_hk_current_contract(artifacts_root, generated_by="test", target_date="20260410")
    write_current_contract(default_hk_current_contract_path(artifacts_root), contract)

    out_path = repo_root / "audit.json"
    from csml.data_tools.rqdata_assets.audit_assets import inspect_hk_data_assets

    assert inspect_hk_data_assets(_args(asset=["etf_daily"], scan_family=["daily"], out=str(out_path))) == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["generated_by"] == "inspect-hk-data-assets"
