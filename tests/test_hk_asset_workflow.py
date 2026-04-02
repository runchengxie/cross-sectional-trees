import importlib
import json
import subprocess
from pathlib import Path


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

    assert instruments_alias.is_symlink()
    assert valuation_alias.is_symlink()
    assert instruments_alias.resolve() == repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "instruments" / "hk_all_instruments_20260402.parquet"
    assert valuation_alias.resolve() == repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "valuation" / "hk_all_2000_20260402_valuation_full_market_refetched_latest"


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
