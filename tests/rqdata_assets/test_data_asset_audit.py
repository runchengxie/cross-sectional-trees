from __future__ import annotations

import json
from types import SimpleNamespace

import pandas as pd
import yaml

from cstree.current_assets import (
    build_hk_current_contract,
    default_hk_current_contract_path,
    hk_current_candidate_paths,
    write_current_contract,
)
from cstree.data_tools.rqdata_assets.audit_assets import (
    aggregate_health_reports,
    build_hk_data_asset_audit_report,
    build_repair_candidates,
)


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


def test_hk_data_asset_audit_treats_report_and_release_references_as_soft_prune_evidence(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    artifacts_root = repo_root / "artifacts"
    candidate_paths = hk_current_candidate_paths(artifacts_root)
    monkeypatch.chdir(repo_root)

    current_daily = artifacts_root / "assets" / "rqdata" / "hk" / "daily" / "hk_all_2000_20260410_daily_latest"
    _write_manifest(current_daily, dataset="daily")
    _symlink(current_daily, candidate_paths["daily"])

    stale_patch = artifacts_root / "assets" / "rqdata" / "hk" / "daily" / "hk_all_2000_20260409_daily_latest__patch"
    _write_manifest(stale_patch, dataset="daily", end_date="20260409")
    reports_dir = artifacts_root / "reports"
    releases_dir = artifacts_root / "releases" / "hk_rqdata_assets_20260409"
    reports_dir.mkdir(parents=True, exist_ok=True)
    releases_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "hk_current_health_20260410_soft_reference.json").write_text(
        json.dumps({"checked_path": str(stale_patch)}),
        encoding="utf-8",
    )
    (releases_dir / "manifest.yml").write_text(
        yaml.safe_dump({"source_path": str(stale_patch)}, sort_keys=False),
        encoding="utf-8",
    )

    contract = build_hk_current_contract(artifacts_root, generated_by="test", target_date="20260410")
    write_current_contract(default_hk_current_contract_path(artifacts_root), contract)

    report = build_hk_data_asset_audit_report(_args(asset=["daily"], scan_family=["daily"]))

    stale_record = next(
        item
        for item in report["inventory"]["records"]
        if str(item["path"]).endswith("hk_all_2000_20260409_daily_latest__patch")
    )
    assert stale_record["classification"] == "unreferenced"
    assert {item["type"] for item in stale_record["references"]} == {"report", "release"}
    candidate = next(
        item
        for item in report["prune"]["candidates"]
        if str(item["path"]).endswith("hk_all_2000_20260409_daily_latest__patch")
    )
    assert candidate["references"] == {"release": 1, "report": 1}
    assert candidate["references_checked"] == ["current"]
    assert candidate["soft_references_ignored_for_prune"] == ["release", "report"]


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
    candidate = next(
        item
        for item in report["repair"]["candidates"]
        if item["asset_key"] == "etf_daily" and item["action"] == "patch-refresh"
    )
    assert candidate["command"][-4:] == [
        "--refresh-asset",
        "etf_daily",
        "--refresh-asset",
        "etf_daily_clean",
    ]


def test_hk_data_asset_audit_downgrades_stale_etf_daily_when_provider_permission_blocked(
    tmp_path, monkeypatch
):
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

    blocked_patch = artifacts_root / "assets" / "rqdata" / "hk" / "daily" / "hk_etf_2000_20260410_daily_latest__patch"
    (blocked_patch / "data").mkdir(parents=True, exist_ok=True)
    (blocked_patch / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "daily",
                "status": "blocked_provider_permission",
                "error": "no permission to access day bar for instruments with type ETF, please contact RiceQuant",
                "output_dir": str(blocked_patch),
                "query": {"start_date": "20260401", "end_date": "20260410"},
                "status_counts": {"provider_permission_blocked": 1},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    contract = build_hk_current_contract(artifacts_root, generated_by="test", target_date="20260410")
    write_current_contract(default_hk_current_contract_path(artifacts_root), contract)

    report = build_hk_data_asset_audit_report(
        _args(asset=["etf_daily"], scan_family=["daily"], metadata_only_etf_daily=False)
    )

    assert report["freshness"]["etf_daily"]["status"] == "pass"
    stale_issue = next(
        item
        for item in report["freshness"]["etf_daily"]["issues"]
        if item["code"] == "asset_stale_before_target"
    )
    assert stale_issue["severity"] == "warning"
    assert stale_issue["classification"] == "provider-permission-gap"
    assert stale_issue["provider_permission_blocker"]["path"] == str(blocked_patch.resolve())
    assert all(
        item["action"] == "provider-boundary"
        for item in report["repair"]["candidates"]
        if item["asset_key"] == "etf_daily"
    )
    assert not any(
        item["path"] == str(blocked_patch.resolve())
        for item in report["prune"]["candidates"]
    )
    assert any(
        item["path"] == str(blocked_patch.resolve())
        and item["reason"] == "provider_permission_boundary_evidence"
        for item in report["prune"]["protected"]
    )


def test_hk_data_asset_audit_classifies_etf_provider_permission_gap(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    artifacts_root = repo_root / "artifacts"
    candidate_paths = hk_current_candidate_paths(artifacts_root)
    monkeypatch.chdir(repo_root)

    etf_snapshot = artifacts_root / "assets" / "rqdata" / "hk" / "daily" / "hk_etf_2000_20260410_daily_latest"
    _write_manifest(etf_snapshot, dataset="daily")
    (etf_snapshot / "symbols.txt").write_text("02800.HK\n02802_01.HK\n", encoding="utf-8")
    pd.DataFrame(
        {
            "trade_date": ["20000103", "20260410"],
            "close": [1.0, 2.0],
        }
    ).to_parquet(etf_snapshot / "data" / "02800.HK.parquet", index=False)
    pd.DataFrame(
        [
            {"symbol": "02800.HK", "status": "written", "error": ""},
            {
                "symbol": "02802_01.HK",
                "status": "missing_remote",
                "error": "daily fetch failed: no permission to access day bar for instruments with type ETF, please contact RiceQuant",
            },
        ]
    ).to_csv(etf_snapshot / "audit.csv", index=False)
    _symlink(etf_snapshot, candidate_paths["etf_daily"])

    contract = build_hk_current_contract(artifacts_root, generated_by="test", target_date="20260410")
    write_current_contract(default_hk_current_contract_path(artifacts_root), contract)

    report = build_hk_data_asset_audit_report(
        _args(asset=["etf_daily"], scan_family=["daily"], metadata_only_etf_daily=False)
    )

    assert report["freshness"]["etf_daily"]["status"] == "pass"
    assert report["freshness"]["etf_daily"]["classification"] == "provider-boundary"
    assert any(
        item["code"] == "provider_permission_symbol_files"
        and item["classification"] == "provider-permission-gap"
        for item in report["freshness"]["etf_daily"]["issues"]
    )
    provider_candidates = [
        item for item in report["repair"]["candidates"] if item["asset_key"] == "etf_daily"
    ]
    assert provider_candidates
    assert all(item["action"] == "provider-boundary" for item in provider_candidates)
    assert all(item["command"] is None for item in provider_candidates)


def test_aggregate_health_reports_classifies_explicit_pit_report_as_pit_coverage(tmp_path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    pit_report = reports_dir / "hk_pit_health_20260430_codex_current_live.json"
    pit_report.write_text(
        json.dumps(
            {
                "quality_verdict": {"overall_severity": "warning", "issue_count": 1},
                "quality_checks": [{"check": "pit_fill_dependence_high", "severity": "warning"}],
            }
        ),
        encoding="utf-8",
    )

    health = aggregate_health_reports(
        reports_dir=reports_dir,
        target_date="20260508",
        extra_reports=[pit_report],
        expected_report_kinds=("pit_coverage",),
    )

    assert not any(
        item["source"] == "pit_coverage" and item["check"] == "expected_report_missing"
        for item in health["merged_issues"]
    )
    assert any(
        item["source"] == "pit_coverage" and item["check"] == "pit_fill_dependence_high"
        for item in health["merged_issues"]
    )


def test_aggregate_health_reports_deduplicates_explicit_default_report(tmp_path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    intraday_report = reports_dir / "hk_intraday_health_20260508_codex.json"
    intraday_report.write_text(
        json.dumps(
            {
                "quality_verdict": {"overall_severity": "warning", "issue_count": 1},
                "quality_checks": [{"check": "daily_active_but_intraday_missing", "severity": "warning"}],
            }
        ),
        encoding="utf-8",
    )

    health = aggregate_health_reports(
        reports_dir=reports_dir,
        target_date="20260508",
        extra_reports=[intraday_report],
        expected_report_kinds=("intraday_health",),
    )

    assert [
        item["check"]
        for item in health["merged_issues"]
        if item.get("check") == "daily_active_but_intraday_missing"
    ] == ["daily_active_but_intraday_missing"]


def test_repair_candidates_map_legacy_intraday_reconcile_checks_to_assets():
    candidates = build_repair_candidates(
        freshness={},
        inventory={"records": []},
        health={
            "merged_issues": [
                {
                    "source": "intraday_health",
                    "check": "intraday_after_daily_end_with_trading",
                    "severity": "warning",
                },
                {
                    "source": "intraday_health",
                    "check": "daily_active_but_intraday_missing",
                    "severity": "warning",
                },
            ]
        },
        target_date="20260508",
    )

    assert [
        (item["asset_key"], item["action"])
        for item in candidates
    ] == [
        ("daily_clean", "patch-refresh"),
        ("intraday", "targeted-rebuild"),
    ]


def test_hk_data_asset_audit_intraday_repair_command_uses_stale_range(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    artifacts_root = repo_root / "artifacts"
    candidate_paths = hk_current_candidate_paths(artifacts_root)
    monkeypatch.chdir(repo_root)

    intraday_snapshot = artifacts_root / "assets" / "rqdata" / "hk" / "intraday" / "intraday_20240501_20260424"
    _write_manifest(intraday_snapshot, dataset="intraday", start_date="20240501", end_date="20260424")
    _symlink(intraday_snapshot, candidate_paths["intraday"])

    contract = build_hk_current_contract(artifacts_root, generated_by="test", target_date="20260430")
    write_current_contract(default_hk_current_contract_path(artifacts_root), contract)

    report = build_hk_data_asset_audit_report(
        _args(
            asset=["intraday"],
            scan_family=["intraday"],
            intraday_mode="metadata",
            target_date="20260430",
        )
    )

    intraday_candidates = [
        item for item in report["repair"]["candidates"] if item["asset_key"] == "intraday"
    ]
    assert intraday_candidates
    command = intraday_candidates[0]["command"]
    assert command[command.index("--start-date") + 1] == "20260427"
    assert command[command.index("--end-date") + 1] == "20260430"


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
    from cstree.data_tools.rqdata_assets.audit_assets import inspect_hk_data_assets

    assert inspect_hk_data_assets(_args(asset=["etf_daily"], scan_family=["daily"], out=str(out_path))) == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["generated_by"] == "inspect-hk-data-assets"
