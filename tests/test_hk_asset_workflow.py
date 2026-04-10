import importlib
import json
import subprocess
from pathlib import Path

import yaml


def _load_module(module_name: str):
    return importlib.reload(importlib.import_module(module_name))


def _configure_repo_roots(module, repo_root: Path) -> None:
    module.REPO_ROOT = repo_root
    module.ASSETS_ROOT = repo_root / "artifacts" / "assets"
    module.REPORTS_ROOT = repo_root / "artifacts" / "reports"
    module.RELEASES_ROOT = repo_root / "artifacts" / "releases"


def test_hk_asset_workflow_dry_run_builds_refresh_package_and_release_commands(tmp_path, monkeypatch):
    workflow = _load_module("csml.release_tools.hk_asset_workflow")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _configure_repo_roots(workflow, repo_root)

    calls: list[list[str]] = []

    def _fake_run(cmd: list[str], *, dry_run: bool):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(workflow, "_run", _fake_run)

    exit_code = workflow.main(
        [
            "--phase",
            "refresh",
            "--phase",
            "inspect",
            "--phase",
            "package",
            "--phase",
            "release",
            "--target-date",
            "20260402",
            "--dry-run",
            "--part",
            "daily",
            "--part",
            "valuation",
        ]
    )

    assert exit_code == 0
    assert any("mirror-hk-daily" in cmd for cmd in calls)
    assert any("build-hk-daily-clean-layer" in cmd for cmd in calls)
    assert any("mirror-hk-valuation" in cmd for cmd in calls)

    package_cmd = next(cmd for cmd in calls if cmd[1:3] == ["-m", "csml.release_tools.package_assets"])
    assert "--valuation-snapshot" in package_cmd
    assert package_cmd[package_cmd.index("--valuation-snapshot") + 1].endswith(
        "artifacts/assets/rqdata/hk/valuation/hk_all_2000_20260402_valuation_full_market_refetched_latest"
    )
    assert package_cmd[package_cmd.index("--part") + 1] == "daily"
    assert package_cmd[package_cmd.index("--part", package_cmd.index("--part") + 1) + 1] == "valuation"

    release_cmd = next(cmd for cmd in calls if cmd[1:3] == ["-m", "csml.release_tools.release_assets"])
    assert "--staged-root" in release_cmd
    assert "--tar-dir" in release_cmd


def test_hk_asset_workflow_refresh_repoints_latest_aliases(tmp_path, monkeypatch):
    workflow = _load_module("csml.release_tools.hk_asset_workflow")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _configure_repo_roots(workflow, repo_root)

    def _fake_run(cmd: list[str], *, dry_run: bool):
        if "export-hk-instruments" in cmd:
            out_path = repo_root / cmd[cmd.index("--out") + 1]
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text("instruments", encoding="utf-8")
        if "mirror-hk-valuation" in cmd:
            name = cmd[cmd.index("--name") + 1]
            out_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "valuation" / name
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "data").mkdir(exist_ok=True)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(workflow, "_run", _fake_run)

    exit_code = workflow.main(
        [
            "--phase",
            "refresh",
            "--refresh-asset",
            "instruments",
            "--refresh-asset",
            "valuation",
            "--target-date",
            "20260402",
        ]
    )

    assert exit_code == 0

    instruments_alias = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "instruments" / "hk_all_instruments_latest.parquet"
    valuation_alias = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "valuation" / "hk_all_valuation_latest"
    current_contract_path = repo_root / "artifacts" / "metadata" / "current_assets" / "hk_current.json"

    assert instruments_alias.is_symlink()
    assert valuation_alias.is_symlink()
    assert instruments_alias.resolve() == repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "instruments" / "hk_all_instruments_20260402.parquet"
    assert valuation_alias.resolve() == repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "valuation" / "hk_all_2000_20260402_valuation_full_market_refetched_latest"
    assert current_contract_path.exists()

    current_contract = json.loads(current_contract_path.read_text(encoding="utf-8"))
    assert current_contract["contract"]["name"] == "hk_current"
    assert current_contract["contract"]["target_date"] == "20260402"
    assert current_contract["assets"]["valuation"]["alias_path"] == str(valuation_alias.absolute())
    assert current_contract["assets"]["valuation"]["resolved_path"] == str(valuation_alias.resolve())
    assert current_contract["assets"]["valuation"]["exists"] is True
    assert current_contract["assets"]["instruments"]["alias_path"] == str(instruments_alias.absolute())
    assert current_contract["assets"]["instruments"]["resolved_path"] == str(instruments_alias.resolve())
    assert current_contract["assets"]["instruments"]["exists"] is True


def test_hk_asset_workflow_inspect_gate_blocks_alias_repoint_and_package(tmp_path, monkeypatch):
    workflow = _load_module("csml.release_tools.hk_asset_workflow")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _configure_repo_roots(workflow, repo_root)

    calls: list[list[str]] = []

    def _fake_run(cmd: list[str], *, dry_run: bool):
        calls.append(cmd)
        if "mirror-hk-daily" in cmd:
            out_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / cmd[cmd.index("--name") + 1]
            (out_dir / "data").mkdir(parents=True, exist_ok=True)
            (out_dir / "manifest.yml").write_text(
                yaml.safe_dump({"query": {"start_date": "20000101", "end_date": "20260402"}}, sort_keys=False),
                encoding="utf-8",
            )
        elif "inspect-hk-asset-health" in cmd:
            out_path = repo_root / cmd[cmd.index("--out") + 1]
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                json.dumps(
                    {
                        "summary": {"history_issue_count": 1},
                        "quality_checks": [
                            {"severity": "warning", "check": "demo_warning"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(workflow, "_run", _fake_run)

    exit_code = workflow.main(
        [
            "--phase",
            "refresh",
            "--phase",
            "inspect",
            "--phase",
            "package",
            "--refresh-asset",
            "daily",
            "--inspect-asset",
            "daily",
            "--target-date",
            "20260402",
        ]
    )

    assert exit_code == 2
    assert any("mirror-hk-daily" in cmd for cmd in calls)
    assert not any(cmd[1:3] == ["-m", "csml.release_tools.package_assets"] for cmd in calls)

    daily_alias = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "hk_all_daily_latest"
    assert not daily_alias.exists()

    report = json.loads(
        (repo_root / "artifacts" / "reports" / "hk_asset_refresh_20260402.json").read_text(encoding="utf-8")
    )
    assert report["gate"]["enabled"] is True
    assert report["gate"]["triggered"] is True
    assert report["gate"]["triggered_assets"] == [
        {
            "asset_name": "daily",
            "overall_severity": "warning",
            "severity_counts": {"error": 0, "warning": 1, "info": 0},
            "report_path": str(repo_root / "artifacts" / "reports" / "hk_daily_health_20260402_full_history.json"),
        }
    ]
    assert report["gate"]["blocked_alias_updates"] == [
        {
            "phase": "refresh",
            "asset_name": "daily",
            "alias_path": str(daily_alias),
            "target_path": str(
                repo_root
                / "artifacts"
                / "assets"
                / "rqdata"
                / "hk"
                / "daily"
                / "hk_all_2000_20260402_daily_final_refetched_latest"
            ),
            "reason": "inspect gate triggered at severity >= warning",
        }
    ]
    assert report["gate"]["skipped_steps"] == [
        {
            "phase": "package",
            "label": "Stage HK asset release parts",
            "asset_name": None,
            "reason": "inspect gate triggered at severity >= warning",
        }
    ]


def test_hk_asset_workflow_inspect_gate_allows_repoint_and_package_when_clean(tmp_path, monkeypatch):
    workflow = _load_module("csml.release_tools.hk_asset_workflow")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _configure_repo_roots(workflow, repo_root)

    calls: list[list[str]] = []

    def _fake_run(cmd: list[str], *, dry_run: bool):
        calls.append(cmd)
        if "mirror-hk-daily" in cmd:
            out_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / cmd[cmd.index("--name") + 1]
            (out_dir / "data").mkdir(parents=True, exist_ok=True)
            (out_dir / "manifest.yml").write_text(
                yaml.safe_dump({"query": {"start_date": "20000101", "end_date": "20260402"}}, sort_keys=False),
                encoding="utf-8",
            )
        elif "inspect-hk-asset-health" in cmd:
            out_path = repo_root / cmd[cmd.index("--out") + 1]
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                json.dumps(
                    {
                        "summary": {"history_issue_count": 0},
                        "quality_checks": [
                            {"severity": "info", "check": "demo_info"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(workflow, "_run", _fake_run)

    exit_code = workflow.main(
        [
            "--phase",
            "refresh",
            "--phase",
            "inspect",
            "--phase",
            "package",
            "--refresh-asset",
            "daily",
            "--inspect-asset",
            "daily",
            "--part",
            "daily",
            "--target-date",
            "20260402",
        ]
    )

    assert exit_code == 0
    assert any("mirror-hk-daily" in cmd for cmd in calls)
    assert any(cmd[1:3] == ["-m", "csml.release_tools.package_assets"] for cmd in calls)

    daily_alias = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "hk_all_daily_latest"
    assert daily_alias.is_symlink()
    assert daily_alias.resolve() == (
        repo_root
        / "artifacts"
        / "assets"
        / "rqdata"
        / "hk"
        / "daily"
        / "hk_all_2000_20260402_daily_final_refetched_latest"
    )

    report = json.loads(
        (repo_root / "artifacts" / "reports" / "hk_asset_refresh_20260402.json").read_text(encoding="utf-8")
    )
    assert report["gate"]["enabled"] is True
    assert report["gate"]["triggered"] is False
    assert report["gate"]["blocked_alias_updates"] == []
    assert report["gate"]["skipped_steps"] == []


def test_hk_asset_workflow_gate_ignores_raw_daily_price_bounds_when_daily_clean_passes(
    tmp_path, monkeypatch
):
    workflow = _load_module("csml.release_tools.hk_asset_workflow")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _configure_repo_roots(workflow, repo_root)

    calls: list[list[str]] = []

    def _fake_run(cmd: list[str], *, dry_run: bool):
        calls.append(cmd)
        if "mirror-hk-daily" in cmd:
            out_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / cmd[cmd.index("--name") + 1]
            (out_dir / "data").mkdir(parents=True, exist_ok=True)
            (out_dir / "manifest.yml").write_text(
                yaml.safe_dump({"query": {"start_date": "20000101", "end_date": "20260402"}}, sort_keys=False),
                encoding="utf-8",
            )
        elif "build-hk-daily-clean-layer" in cmd:
            out_dir = repo_root / cmd[cmd.index("--out-dir") + 1]
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "data").mkdir(exist_ok=True)
            (out_dir / "manifest.yml").write_text(
                yaml.safe_dump({"query": {"start_date": "20000101", "end_date": "20260402"}}, sort_keys=False),
                encoding="utf-8",
            )
        elif "inspect-hk-asset-health" in cmd:
            out_path = repo_root / cmd[cmd.index("--out") + 1]
            out_path.parent.mkdir(parents=True, exist_ok=True)
            if "daily_clean" in out_path.name:
                payload = {
                    "summary": {"history_issue_count": 0},
                    "quality_checks": [],
                }
            else:
                payload = {
                    "summary": {"history_issue_count": 0},
                    "quality_checks": [
                        {
                            "severity": "error",
                            "check": "daily_price_bounds_violation",
                            "sample_symbols": ["00005.HK"],
                        }
                    ],
                }
            out_path.write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(workflow, "_run", _fake_run)

    exit_code = workflow.main(
        [
            "--phase",
            "refresh",
            "--phase",
            "inspect",
            "--phase",
            "package",
            "--refresh-asset",
            "daily",
            "--refresh-asset",
            "daily_clean",
            "--inspect-asset",
            "daily",
            "--inspect-asset",
            "daily_clean",
            "--part",
            "daily",
            "--target-date",
            "20260402",
        ]
    )

    assert exit_code == 0
    assert any(cmd[1:3] == ["-m", "csml.release_tools.package_assets"] for cmd in calls)

    report = json.loads(
        (repo_root / "artifacts" / "reports" / "hk_asset_refresh_20260402.json").read_text(encoding="utf-8")
    )
    assert report["gate"]["enabled"] is True
    assert report["gate"]["triggered"] is False
    assert report["gate"]["blocked_alias_updates"] == []
    assert report["gate"]["skipped_steps"] == []
    assert report["gate"]["suppressed_triggered_assets"] == [
        {
            "asset_name": "daily",
            "overall_severity": "error",
            "severity_counts": {"error": 1, "warning": 0, "info": 0},
            "report_path": str(repo_root / "artifacts" / "reports" / "hk_daily_health_20260402_full_history.json"),
            "reason": "raw daily price-bounds-only issues are tolerated when daily_clean passes the gate",
        }
    ]


def test_hk_asset_workflow_prints_health_summary_from_json_reports(tmp_path, monkeypatch, capsys):
    workflow = _load_module("csml.release_tools.hk_asset_workflow")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _configure_repo_roots(workflow, repo_root)

    def _fake_run(cmd: list[str], *, dry_run: bool):
        out_path = repo_root / cmd[cmd.index("--out") + 1]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(
                {
                    "summary": {"history_issue_count": 2},
                    "quality_checks": [
                        {"severity": "warning", "check": "demo_warning"},
                        {"severity": "info", "check": "demo_info"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(workflow, "_run", _fake_run)

    exit_code = workflow.main(
        [
            "--phase",
            "inspect",
            "--inspect-asset",
            "dividends",
            "--target-date",
            "20260402",
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr().out
    assert "warnings=1" in captured
    assert "info=1" in captured
    assert "history_issues=2" in captured


def test_hk_asset_workflow_patch_mode_builds_patch_and_merge_commands(tmp_path, monkeypatch):
    workflow = _load_module("csml.release_tools.hk_asset_workflow")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _configure_repo_roots(workflow, repo_root)

    daily_current = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "hk_all_daily_latest"
    daily_current.mkdir(parents=True, exist_ok=True)
    (daily_current / "manifest.yml").write_text(
        yaml.safe_dump({"query": {"end_date": "20260401"}}, sort_keys=False),
        encoding="utf-8",
    )

    valuation_current = (
        repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "valuation" / "hk_all_valuation_latest"
    )
    valuation_current.mkdir(parents=True, exist_ok=True)
    (valuation_current / "manifest.yml").write_text(
        yaml.safe_dump({"query": {"end_date": "20260401"}}, sort_keys=False),
        encoding="utf-8",
    )

    calls: list[list[str]] = []

    def _fake_run(cmd: list[str], *, dry_run: bool):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(workflow, "_run", _fake_run)

    exit_code = workflow.main(
        [
            "--phase",
            "refresh",
            "--refresh-asset",
            "daily",
            "--refresh-asset",
            "valuation",
            "--target-date",
            "20260402",
            "--refresh-mode",
            "patch",
            "--dry-run",
        ]
    )

    assert exit_code == 0

    daily_patch_cmd = next(cmd for cmd in calls if "mirror-hk-daily" in cmd)
    assert daily_patch_cmd[daily_patch_cmd.index("--start-date") + 1] == "20260313"
    assert daily_patch_cmd[daily_patch_cmd.index("--name") + 1].endswith(
        "hk_all_2000_20260402_daily_final_refetched_latest__patch"
    )

    valuation_patch_cmd = next(cmd for cmd in calls if "mirror-hk-valuation" in cmd)
    assert valuation_patch_cmd[valuation_patch_cmd.index("--start-date") + 1] == "20260221"
    assert valuation_patch_cmd[valuation_patch_cmd.index("--name") + 1].endswith(
        "hk_all_2000_20260402_valuation_full_market_refetched_latest__patch"
    )

    merge_cmds = [
        cmd for cmd in calls if len(cmd) >= 3 and cmd[1:3] == ["-m", "csml.research.hk_asset_patch_merge"]
    ]
    assert len(merge_cmds) == 2

    daily_merge_cmd = next(cmd for cmd in merge_cmds if "daily_final_refetched_latest" in cmd[cmd.index("--out-dir") + 1])
    assert daily_merge_cmd[daily_merge_cmd.index("--base-dir") + 1].endswith(
        "artifacts/assets/rqdata/hk/daily/hk_all_daily_latest"
    )
    assert daily_merge_cmd[daily_merge_cmd.index("--patch-dir") + 1].endswith(
        "artifacts/assets/rqdata/hk/daily/hk_all_2000_20260402_daily_final_refetched_latest__patch"
    )


def test_hk_asset_workflow_writes_structured_refresh_report(tmp_path, monkeypatch):
    workflow = _load_module("csml.release_tools.hk_asset_workflow")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _configure_repo_roots(workflow, repo_root)

    daily_base = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "hk_all_2000_20260401_daily_clean"
    (daily_base / "data").mkdir(parents=True, exist_ok=True)
    (daily_base / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "daily",
                "status": "completed",
                "output_dir": str(daily_base),
                "query": {"start_date": "20000101", "end_date": "20260401"},
                "totals": {"rows": 10, "files": 1, "symbols_written": 1},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    daily_current = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "hk_all_daily_latest"
    daily_current.parent.mkdir(parents=True, exist_ok=True)
    daily_current.symlink_to(daily_base.name, target_is_directory=True)

    def _fake_run(cmd: list[str], *, dry_run: bool):
        if "mirror-hk-daily" in cmd:
            patch_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / cmd[cmd.index("--name") + 1]
            (patch_dir / "data").mkdir(parents=True, exist_ok=True)
            (patch_dir / "manifest.yml").write_text(
                yaml.safe_dump(
                    {
                        "dataset": "daily",
                        "status": "completed",
                        "output_dir": str(patch_dir),
                        "query": {
                            "start_date": cmd[cmd.index("--start-date") + 1],
                            "end_date": cmd[cmd.index("--end-date") + 1],
                        },
                        "totals": {"rows": 3, "files": 1, "symbols_written": 1},
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
        elif len(cmd) >= 3 and cmd[1:3] == ["-m", "csml.research.hk_asset_patch_merge"]:
            out_dir = repo_root / cmd[cmd.index("--out-dir") + 1]
            (out_dir / "data").mkdir(parents=True, exist_ok=True)
            (out_dir / "manifest.yml").write_text(
                yaml.safe_dump(
                    {
                        "dataset": "daily",
                        "status": "completed",
                        "output_dir": str(out_dir),
                        "query": {"start_date": "20000101", "end_date": "20260402"},
                        "totals": {"rows": 12, "files": 1, "symbols_written": 1},
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
        elif "inspect-hk-asset-health" in cmd:
            out_path = repo_root / cmd[cmd.index("--out") + 1]
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                json.dumps(
                    {
                        "summary": {
                            "target_date": "2026-04-02",
                            "history_issue_count": 2,
                        },
                        "quality_checks": [
                            {
                                "severity": "warning",
                                "check": "field_ffill_age_gt_1d",
                                "field": "close",
                                "sample_symbols": ["00005.HK"],
                            },
                            {"severity": "info", "check": "stale_tail"},
                        ],
                        "sample_stale_symbols": [
                            {
                                "symbol": "00011.HK",
                                "latest_date": "2026-03-31",
                                "status": "linked_base",
                            }
                        ],
                        "field_coverage": [
                            {
                                "field": "close",
                                "sample_oldest_ffill_symbols": [
                                    {
                                        "symbol": "00005.HK",
                                        "last_nonnull_date": "2026-03-28",
                                        "age_days": 5,
                                    }
                                ],
                            }
                        ],
                        "history": {
                            "issues": [
                                {
                                    "check": "daily_negative_volume_any_date",
                                    "severity": "error",
                                    "field": None,
                                    "sample_rows": [
                                        {
                                            "symbol": "00007.HK",
                                            "trade_date": "2026-04-01",
                                            "volume": -50,
                                        }
                                    ],
                                }
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(workflow, "_run", _fake_run)

    exit_code = workflow.main(
        [
            "--phase",
            "refresh",
            "--phase",
            "inspect",
            "--refresh-asset",
            "daily",
            "--inspect-asset",
            "daily",
            "--target-date",
            "20260402",
            "--refresh-mode",
            "patch",
            "--gate-on-severity",
            "none",
        ]
    )

    assert exit_code == 0

    report_path = repo_root / "artifacts" / "reports" / "hk_asset_refresh_20260402.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["workflow"]["target_date"] == "20260402"
    assert report["workflow"]["refresh_mode"] == "patch"
    assert report["workflow"]["gate_on_severity"] == "none"
    assert report["gate"]["enabled"] is False
    assert report["gate"]["triggered"] is False
    assert report["refresh"]["assets"]["daily"]["mode"] == "patch"
    assert report["refresh"]["assets"]["daily"]["patch_window"] == {
        "start_date": "20260313",
        "end_date": "20260402",
        "lookback_days": 20,
    }
    assert report["refresh"]["assets"]["daily"]["base"]["manifest"]["query"]["end_date"] == "20260401"
    assert report["refresh"]["assets"]["daily"]["patch"]["manifest"]["query"]["end_date"] == "20260402"
    assert report["refresh"]["assets"]["daily"]["refreshed"]["manifest"]["totals"]["rows"] == 12
    assert report["inspect"]["assets"]["daily"]["quality"] == {
        "report_path": str(
            repo_root / "artifacts" / "reports" / "hk_daily_health_20260402_full_history.json"
        ),
        "issue_count": 2,
        "severity_counts": {"error": 0, "warning": 1, "info": 1},
        "overall_severity": "warning",
        "history_issue_count": 2,
    }
    assert report["inspect"]["assets"]["daily"]["repair_candidate_count"] == 3
    assert report["inspect"]["assets"]["daily"]["repair_candidates"] == [
        {
            "symbol": "00007.HK",
            "trade_date": "2026-04-01",
            "start_date": None,
            "end_date": None,
            "checks": ["daily_negative_volume_any_date"],
            "fields": [],
            "sources": ["history_issues"],
            "reference_contexts": [],
            "errors": [],
            "max_severity": "error",
            "asset_name": "daily",
        },
        {
            "symbol": "00005.HK",
            "trade_date": None,
            "start_date": "2026-03-28",
            "end_date": "2026-04-02",
            "checks": ["field_ffill_age_gt_1d"],
            "fields": ["close"],
            "sources": ["quality_checks"],
            "reference_contexts": [],
            "errors": [],
            "max_severity": "warning",
            "asset_name": "daily",
        },
        {
            "symbol": "00011.HK",
            "trade_date": None,
            "start_date": "2026-03-31",
            "end_date": "2026-04-02",
            "checks": ["stale_symbol_missing_target_date_row"],
            "fields": [],
            "sources": ["sample_stale_symbols"],
            "reference_contexts": [],
            "errors": ["linked_base"],
            "max_severity": "warning",
            "asset_name": "daily",
        },
    ]
    assert len(report["steps"]) == 3


def test_hk_asset_workflow_repair_phase_uses_report_candidates_to_build_subset_patch(tmp_path, monkeypatch):
    workflow = _load_module("csml.release_tools.hk_asset_workflow")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _configure_repo_roots(workflow, repo_root)

    daily_base = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "hk_all_2000_20260402_daily_clean"
    (daily_base / "data").mkdir(parents=True, exist_ok=True)
    (daily_base / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "daily",
                "status": "completed",
                "output_dir": str(daily_base),
                "query": {"start_date": "20000101", "end_date": "20260402"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    daily_current = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "hk_all_daily_latest"
    daily_current.parent.mkdir(parents=True, exist_ok=True)
    daily_current.symlink_to(daily_base.name, target_is_directory=True)

    source_report = repo_root / "artifacts" / "reports" / "hk_asset_refresh_20260402.json"
    source_report.parent.mkdir(parents=True, exist_ok=True)
    source_report.write_text(
        json.dumps(
            {
                "inspect": {
                    "assets": {
                        "daily": {
                            "repair_candidates": [
                                {
                                    "symbol": "00005.HK",
                                    "trade_date": None,
                                    "start_date": "2026-03-28",
                                    "end_date": "2026-04-02",
                                    "max_severity": "warning",
                                },
                                {
                                    "symbol": "00011.HK",
                                    "trade_date": "2026-04-01",
                                    "start_date": None,
                                    "end_date": None,
                                    "max_severity": "error",
                                },
                                {
                                    "symbol": "00700.HK",
                                    "trade_date": "2026-04-02",
                                    "start_date": None,
                                    "end_date": None,
                                    "max_severity": "info",
                                },
                            ]
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    calls: list[list[str]] = []

    def _fake_run(cmd: list[str], *, dry_run: bool):
        calls.append(cmd)
        if "mirror-hk-daily" in cmd:
            patch_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / cmd[cmd.index("--name") + 1]
            (patch_dir / "data").mkdir(parents=True, exist_ok=True)
            (patch_dir / "manifest.yml").write_text(
                yaml.safe_dump(
                    {
                        "dataset": "daily",
                        "status": "completed",
                        "output_dir": str(patch_dir),
                        "query": {
                            "start_date": cmd[cmd.index("--start-date") + 1],
                            "end_date": cmd[cmd.index("--end-date") + 1],
                        },
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
        elif len(cmd) >= 3 and cmd[1:3] == ["-m", "csml.research.hk_asset_patch_merge"]:
            out_dir = repo_root / cmd[cmd.index("--out-dir") + 1]
            (out_dir / "data").mkdir(parents=True, exist_ok=True)
            (out_dir / "manifest.yml").write_text(
                yaml.safe_dump(
                    {
                        "dataset": "daily",
                        "status": "completed",
                        "output_dir": str(out_dir),
                        "query": {"start_date": "20000101", "end_date": "20260402"},
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
        elif "inspect-hk-asset-health" in cmd:
            out_path = repo_root / cmd[cmd.index("--out") + 1]
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                json.dumps(
                    {
                        "summary": {"target_date": "2026-04-02", "history_issue_count": 0},
                        "quality_checks": [{"severity": "info", "check": "demo_info"}],
                    }
                ),
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(workflow, "_run", _fake_run)

    exit_code = workflow.main(
        [
            "--phase",
            "repair",
            "--repair-asset",
            "daily",
            "--target-date",
            "20260402",
            "--repair-source-report",
            str(source_report),
        ]
    )

    assert exit_code == 0

    symbols_file = repo_root / "artifacts" / "reports" / "repair_inputs" / "daily_20260402_repair_symbols.txt"
    assert symbols_file.read_text(encoding="utf-8") == "00005.HK\n00011.HK\n"

    daily_patch_cmd = next(cmd for cmd in calls if "mirror-hk-daily" in cmd)
    assert daily_patch_cmd[daily_patch_cmd.index("--symbols-file") + 1].endswith(
        "artifacts/reports/repair_inputs/daily_20260402_repair_symbols.txt"
    )
    assert daily_patch_cmd[daily_patch_cmd.index("--start-date") + 1] == "20260328"
    assert daily_patch_cmd[daily_patch_cmd.index("--end-date") + 1] == "20260402"
    assert daily_patch_cmd[daily_patch_cmd.index("--name") + 1].endswith(
        "hk_all_2000_20260402_daily_final_refetched_latest__repair"
    )
    repair_inspect_cmd = next(cmd for cmd in calls if "inspect-hk-asset-health" in cmd)
    assert repair_inspect_cmd[repair_inspect_cmd.index("--out") + 1].endswith(
        "artifacts/reports/hk_daily_health_20260402_full_history_post_repair.json"
    )

    assert daily_current.is_symlink()
    assert daily_current.resolve() == (
        repo_root
        / "artifacts"
        / "assets"
        / "rqdata"
        / "hk"
        / "daily"
        / "hk_all_2000_20260402_daily_final_refetched_latest"
    )

    report = json.loads(source_report.read_text(encoding="utf-8"))
    assert report["repair"]["assets"]["daily"]["candidate_count"] == 2
    assert report["repair"]["assets"]["daily"]["symbols"] == ["00005.HK", "00011.HK"]
    assert report["repair"]["assets"]["daily"]["patch_window"] == {
        "start_date": "20260328",
        "end_date": "20260402",
        "lookback_days": None,
    }
    assert report["gate"]["stage"] == "post_repair"
    assert report["gate"]["triggered"] is False
    assert report["inspect"]["assets"]["daily"]["latest_stage"] == "post_repair"
    assert report["inspect"]["assets"]["daily"]["post_repair_quality"] == {
        "report_path": str(
            repo_root / "artifacts" / "reports" / "hk_daily_health_20260402_full_history_post_repair.json"
        ),
        "issue_count": 1,
        "severity_counts": {"error": 0, "warning": 0, "info": 1},
        "overall_severity": "info",
        "history_issue_count": 0,
    }

    repair_queue = json.loads(
        (repo_root / "artifacts" / "reports" / "hk_asset_repair_queue_20260402.json").read_text(encoding="utf-8")
    )
    assert repair_queue["candidate_count"] == 2
    assert repair_queue["assets"]["daily"]["symbols"] == ["00005.HK", "00011.HK"]

    remaining_queue = json.loads(
        (
            repo_root / "artifacts" / "reports" / "hk_asset_remaining_repair_candidates_20260402.json"
        ).read_text(encoding="utf-8")
    )
    assert remaining_queue["candidate_count"] == 0
    assert remaining_queue["assets"]["daily"]["repair_candidates"] == []
    assert report["repair"]["queue"]["report_path"] == str(
        repo_root / "artifacts" / "reports" / "hk_asset_repair_queue_20260402.json"
    )
    assert report["repair"]["remaining_candidates"]["report_path"] == str(
        repo_root / "artifacts" / "reports" / "hk_asset_remaining_repair_candidates_20260402.json"
    )


def test_hk_asset_workflow_repair_only_unresolved_uses_remaining_candidates(tmp_path, monkeypatch):
    workflow = _load_module("csml.release_tools.hk_asset_workflow")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _configure_repo_roots(workflow, repo_root)

    daily_base = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "hk_all_2000_20260402_daily_clean"
    (daily_base / "data").mkdir(parents=True, exist_ok=True)
    (daily_base / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "daily",
                "status": "completed",
                "output_dir": str(daily_base),
                "query": {"start_date": "20000101", "end_date": "20260402"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    daily_current = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "hk_all_daily_latest"
    daily_current.parent.mkdir(parents=True, exist_ok=True)
    daily_current.symlink_to(daily_base.name, target_is_directory=True)

    source_report = repo_root / "artifacts" / "reports" / "hk_asset_refresh_20260402.json"
    source_report.parent.mkdir(parents=True, exist_ok=True)
    source_report.write_text(
        json.dumps(
            {
                "inspect": {
                    "assets": {
                        "daily": {
                            "repair_candidates": [
                                {
                                    "symbol": "00005.HK",
                                    "trade_date": "2026-04-01",
                                    "start_date": None,
                                    "end_date": None,
                                    "max_severity": "error",
                                },
                                {
                                    "symbol": "00011.HK",
                                    "trade_date": "2026-04-02",
                                    "start_date": None,
                                    "end_date": None,
                                    "max_severity": "warning",
                                },
                            ],
                            "post_repair_repair_candidates": [
                                {
                                    "symbol": "00011.HK",
                                    "trade_date": "2026-04-02",
                                    "start_date": None,
                                    "end_date": None,
                                    "max_severity": "warning",
                                }
                            ],
                        }
                    }
                },
                "repair": {
                    "remaining_candidates": {
                        "assets": {
                            "daily": {
                                "repair_candidates": [
                                    {
                                        "symbol": "00011.HK",
                                        "trade_date": "2026-04-02",
                                        "start_date": None,
                                        "end_date": None,
                                        "max_severity": "warning",
                                    }
                                ]
                            }
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    calls: list[list[str]] = []

    def _fake_run(cmd: list[str], *, dry_run: bool):
        calls.append(cmd)
        if "mirror-hk-daily" in cmd:
            patch_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / cmd[cmd.index("--name") + 1]
            (patch_dir / "data").mkdir(parents=True, exist_ok=True)
            (patch_dir / "manifest.yml").write_text(
                yaml.safe_dump(
                    {
                        "dataset": "daily",
                        "status": "completed",
                        "output_dir": str(patch_dir),
                        "query": {
                            "start_date": cmd[cmd.index("--start-date") + 1],
                            "end_date": cmd[cmd.index("--end-date") + 1],
                        },
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
        elif len(cmd) >= 3 and cmd[1:3] == ["-m", "csml.research.hk_asset_patch_merge"]:
            out_dir = repo_root / cmd[cmd.index("--out-dir") + 1]
            (out_dir / "data").mkdir(parents=True, exist_ok=True)
            (out_dir / "manifest.yml").write_text(
                yaml.safe_dump(
                    {
                        "dataset": "daily",
                        "status": "completed",
                        "output_dir": str(out_dir),
                        "query": {"start_date": "20000101", "end_date": "20260402"},
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(workflow, "_run", _fake_run)

    exit_code = workflow.main(
        [
            "--phase",
            "repair",
            "--repair-asset",
            "daily",
            "--target-date",
            "20260402",
            "--repair-source-report",
            str(source_report),
            "--repair-only-unresolved",
            "--no-repair-rerun-inspect",
        ]
    )

    assert exit_code == 0
    symbols_file = repo_root / "artifacts" / "reports" / "repair_inputs" / "daily_20260402_repair_symbols.txt"
    assert symbols_file.read_text(encoding="utf-8") == "00011.HK\n"

    daily_patch_cmd = next(cmd for cmd in calls if "mirror-hk-daily" in cmd)
    assert daily_patch_cmd[daily_patch_cmd.index("--start-date") + 1] == "20260402"
    assert daily_patch_cmd[daily_patch_cmd.index("--end-date") + 1] == "20260402"

    report = json.loads(source_report.read_text(encoding="utf-8"))
    assert report["workflow"]["repair_only_unresolved"] is True
    assert report["repair"]["queue"]["source_kind"] == "remaining_repair_candidates"
    assert report["repair"]["queue"]["candidate_count"] == 1
    assert report["repair"]["queue"]["assets"]["daily"]["symbols"] == ["00011.HK"]
    assert report["repair"]["remaining_candidates"] is None
