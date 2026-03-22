import importlib
import json
import subprocess
from pathlib import Path

import yaml

def _load_module(module_name: str):
    return importlib.reload(importlib.import_module(module_name))


def _prepare_demo_assets(repo_root: Path) -> dict[str, Path]:
    daily_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "daily_demo"
    (daily_dir / "data").mkdir(parents=True, exist_ok=True)
    (daily_dir / "data" / "00005.HK.parquet").write_text("daily", encoding="utf-8")
    (daily_dir / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "daily",
                "release_tag": "assets-demo-20260318",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    pit_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "pit_financials" / "pit_demo"
    (pit_dir / "data").mkdir(parents=True, exist_ok=True)
    (pit_dir / "data" / "00005.HK.parquet").write_text("pit", encoding="utf-8")
    (pit_dir / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "pit_financials",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    pipeline_file = pit_dir / "pipeline_fundamentals.parquet"
    pipeline_file.write_text("pipeline", encoding="utf-8")
    (pit_dir / "pipeline_fundamentals.manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "pit_fundamentals_file",
                "source_asset_dir": str(pit_dir),
                "source_manifest": str(pit_dir / "manifest.yml"),
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    industry_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "industry_changes" / "industry_demo"
    (industry_dir / "data").mkdir(parents=True, exist_ok=True)
    (industry_dir / "data" / "00005.HK.parquet").write_text("industry", encoding="utf-8")
    (industry_dir / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "industry_changes",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    industry_file = industry_dir / "industry_labels_m.parquet"
    industry_file.write_text("industry-labels", encoding="utf-8")
    (industry_dir / "industry_labels_m.manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "industry_labels_file",
                "source_asset_dir": str(industry_dir),
                "source_manifest": str(industry_dir / "manifest.yml"),
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    universe_dir = repo_root / "artifacts" / "assets" / "universe"
    universe_dir.mkdir(parents=True, exist_ok=True)
    universe_file = universe_dir / "by_date_demo.csv"
    universe_file.write_text("trade_date,ts_code\n20260131,00005.HK\n", encoding="utf-8")

    return {
        "daily_dir": daily_dir,
        "pipeline_file": pipeline_file,
        "industry_file": industry_file,
        "universe_file": universe_file,
    }


def _write_demo_run(
    runs_root: Path,
    *,
    run_dir_name: str,
    run_name: str,
    timestamp: str,
    config_hash: str,
    asset_paths: dict[str, Path],
) -> Path:
    run_dir = runs_root / run_dir_name
    run_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "run": {
            "name": run_name,
            "timestamp": timestamp,
            "config_hash": config_hash,
            "output_dir": str(run_dir),
        },
        "data": {
            "market": "hk",
            "provider": "rqdata",
        },
        "eval": {
            "ic": {"mean": 0.03, "ir": 0.4},
            "long_short": 0.02,
            "pred_nunique": 5,
            "feature_importance_nonzero": 1,
            "feature_importance_file": str(run_dir / "feature_importance.csv"),
            "rolling_ic": {
                "series_files": {
                    "6m": str(run_dir / "ic_rolling_6m.csv"),
                }
            },
            "scored_file": str(run_dir / "eval_scored.parquet"),
        },
        "backtest": {
            "enabled": True,
            "stats": {
                "periods": 24,
                "periods_per_year": 12.0,
                "total_return": 0.25,
                "ann_return": 0.12,
                "ann_vol": 0.08,
                "sharpe": 1.5,
                "max_drawdown": -0.09,
                "avg_turnover": 0.2,
                "avg_cost_drag": 0.01,
            },
            "rolling_sharpe": {
                "series_files": {
                    "6m": str(run_dir / "backtest_rolling_sharpe_6m.csv"),
                }
            },
        },
        "dataset": {
            "file": str(run_dir / "dataset.parquet"),
        },
        "fundamentals": {
            "enabled": True,
            "source": "file",
            "provider": "rqdata",
            "file": str(asset_paths["pipeline_file"]),
        },
        "industry": {
            "enabled": True,
            "source": "file",
            "file": str(asset_paths["industry_file"]),
        },
        "universe": {
            "by_date_file": str(asset_paths["universe_file"]),
        },
        "positions": {
            "current_file": str(run_dir / "positions_current.csv"),
            "by_rebalance_file": str(run_dir / "positions_by_rebalance.csv"),
            "diff_file": str(run_dir / "rebalance_diff.csv"),
        },
        "walk_forward": {
            "feature_importance_file": str(run_dir / "walk_forward_feature_importance.csv"),
        },
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (run_dir / "config.used.yml").write_text(
        yaml.safe_dump(
            {
                "market": "hk",
                "data": {
                    "provider": "rqdata",
                    "daily_asset_dir": str(asset_paths["daily_dir"]),
                },
                "fundamentals": {
                    "source": "file",
                    "file": str(asset_paths["pipeline_file"]),
                },
                "industry": {
                    "source": "file",
                    "file": str(asset_paths["industry_file"]),
                },
                "universe": {
                    "by_date_file": str(asset_paths["universe_file"]),
                },
                "model": {"type": "ridge"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (run_dir / "positions_current.csv").write_text("symbol,weight\n00005.HK,1.0\n", encoding="utf-8")
    (run_dir / "positions_by_rebalance.csv").write_text(
        "rebalance_date,symbol,weight\n20260131,00005.HK,1.0\n",
        encoding="utf-8",
    )
    (run_dir / "rebalance_diff.csv").write_text("symbol,delta\n00005.HK,0.1\n", encoding="utf-8")
    (run_dir / "backtest_net.csv").write_text("trade_date,net_return\n20260131,0.01\n", encoding="utf-8")
    (run_dir / "backtest_turnover.csv").write_text("trade_date,turnover\n20260131,0.2\n", encoding="utf-8")
    (run_dir / "backtest_rolling_sharpe_6m.csv").write_text(
        "trade_date,sharpe\n20260131,1.5\n",
        encoding="utf-8",
    )
    (run_dir / "ic_test.csv").write_text("trade_date,ic\n20260131,0.03\n", encoding="utf-8")
    (run_dir / "ic_rolling_6m.csv").write_text("trade_date,ic_mean\n20260131,0.03\n", encoding="utf-8")
    (run_dir / "quantile_returns.csv").write_text("trade_date,q1,q5\n20260131,0.0,0.1\n", encoding="utf-8")
    (run_dir / "feature_importance.csv").write_text("feature,importance\nf1,1.0\n", encoding="utf-8")
    (run_dir / "walk_forward_feature_importance.csv").write_text(
        "window,feature,importance\n1,f1,1.0\n",
        encoding="utf-8",
    )
    (run_dir / "debug_trace.txt").write_text("trace", encoding="utf-8")
    (run_dir / "eval_scored.parquet").write_text("scored", encoding="utf-8")
    (run_dir / "dataset.parquet").write_text("dataset", encoding="utf-8")
    return run_dir


def _prepare_demo_runs(repo_root: Path) -> Path:
    asset_paths = _prepare_demo_assets(repo_root)
    runs_root = repo_root / "artifacts" / "runs"
    _write_demo_run(
        runs_root,
        run_dir_name="alpha_20260101_120000_deadbeef",
        run_name="alpha",
        timestamp="20260101_120000",
        config_hash="deadbeef",
        asset_paths=asset_paths,
    )
    _write_demo_run(
        runs_root,
        run_dir_name="beta_20260102_130000_abcd1234",
        run_name="beta",
        timestamp="20260102_130000",
        config_hash="abcd1234",
        asset_paths=asset_paths,
    )
    return runs_root


def _configure_package_script(package_script: object, repo_root: Path, runs_root: Path) -> None:
    package_script.REPO_ROOT = repo_root
    package_script.RUNS_ROOT = runs_root
    package_script.ASSETS_ROOT = repo_root / "artifacts" / "assets"
    package_script._git_metadata = lambda _repo_root: {
        "commit": "deadbeef" * 5,
        "short_commit": "deadbeef",
        "branch": "main",
        "is_dirty": True,
    }


def _stage_demo_runs(tmp_path: Path) -> tuple[object, Path]:
    package_script = _load_module("csml.release_tools.package_runs")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    runs_root = _prepare_demo_runs(repo_root)

    _configure_package_script(package_script, repo_root, runs_root)

    stage_root = tmp_path / "stage"
    exit_code = package_script.main(
        [
            "--runs-dir",
            str(runs_root),
            "--dest",
            str(stage_root),
            "--name",
            "demo_runs",
            "--run-name-prefix",
            "alpha",
        ]
    )

    assert exit_code == 0
    return package_script, stage_root


def test_package_runs_stages_curated_files_and_summary(tmp_path):
    _, stage_root = _stage_demo_runs(tmp_path)

    alpha_dir = stage_root / "alpha_20260101_120000_deadbeef"
    assert alpha_dir.exists()
    assert (alpha_dir / "summary.json").exists()
    assert (alpha_dir / "positions_current.csv").exists()
    assert (alpha_dir / "backtest_net.csv").exists()
    assert (alpha_dir / "eval_scored.parquet").exists() is False
    assert not (stage_root / "beta_20260102_130000_abcd1234").exists()
    assert (stage_root / "runs_summary.csv").exists()

    root_manifest = yaml.safe_load((stage_root / "manifest.yml").read_text(encoding="utf-8"))
    assert root_manifest["distribution"]["name"] == "demo_runs"
    assert root_manifest["distribution"]["profile"] == "light"
    assert root_manifest["git"]["short_commit"] == "deadbeef"
    root_asset_refs = root_manifest["reproducibility"]["asset_references"]
    assert any(item["path"].endswith("daily_demo/manifest.yml") for item in root_asset_refs)
    assert any(item["path"].endswith("pipeline_fundamentals.manifest.yml") for item in root_asset_refs)
    assert any(item["path"].endswith("industry_labels_m.manifest.yml") for item in root_asset_refs)
    assert any(item["path"].endswith("by_date_demo.csv") and item["kind"] == "file" for item in root_asset_refs)
    assert sorted(root_manifest["runs"].keys()) == ["alpha_20260101_120000_deadbeef"]

    run_manifest = yaml.safe_load((alpha_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert run_manifest["git"]["short_commit"] == "deadbeef"
    assert run_manifest["run"]["run_name"] == "alpha"
    assert "positions_current.csv" in run_manifest["run"]["files"]
    assert any(
        item["path"].endswith("daily_demo/manifest.yml") and item.get("release_tag") == "assets-demo-20260318"
        for item in run_manifest["reproducibility"]["asset_references"]
    )


def test_package_runs_can_include_scored_and_dataset_files(tmp_path):
    package_script = _load_module("csml.release_tools.package_runs")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    runs_root = _prepare_demo_runs(repo_root)

    _configure_package_script(package_script, repo_root, runs_root)

    stage_root = tmp_path / "stage"
    exit_code = package_script.main(
        [
            "--runs-dir",
            str(runs_root),
            "--dest",
            str(stage_root),
            "--name",
            "demo_runs",
            "--run",
            "alpha_20260101_120000_deadbeef",
            "--include-scored",
            "--include-dataset",
        ]
    )

    assert exit_code == 0
    alpha_dir = stage_root / "alpha_20260101_120000_deadbeef"
    assert (alpha_dir / "eval_scored.parquet").exists()
    assert (alpha_dir / "dataset.parquet").exists()


def test_package_runs_profile_milestone_includes_scored_and_dataset_files(tmp_path):
    package_script = _load_module("csml.release_tools.package_runs")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    runs_root = _prepare_demo_runs(repo_root)

    _configure_package_script(package_script, repo_root, runs_root)

    stage_root = tmp_path / "stage"
    exit_code = package_script.main(
        [
            "--runs-dir",
            str(runs_root),
            "--dest",
            str(stage_root),
            "--name",
            "demo_runs",
            "--run",
            "alpha_20260101_120000_deadbeef",
            "--profile",
            "milestone",
        ]
    )

    assert exit_code == 0
    alpha_dir = stage_root / "alpha_20260101_120000_deadbeef"
    assert (alpha_dir / "eval_scored.parquet").exists()
    assert (alpha_dir / "dataset.parquet").exists()
    assert not (alpha_dir / "debug_trace.txt").exists()

    root_manifest = yaml.safe_load((stage_root / "manifest.yml").read_text(encoding="utf-8"))
    assert root_manifest["distribution"]["profile"] == "milestone"
    assert root_manifest["distribution"]["include_scored"] is True
    assert root_manifest["distribution"]["include_dataset"] is True
    assert root_manifest["distribution"]["include_full_run_dir"] is False


def test_package_runs_profile_full_includes_full_run_dir(tmp_path):
    package_script = _load_module("csml.release_tools.package_runs")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    runs_root = _prepare_demo_runs(repo_root)

    _configure_package_script(package_script, repo_root, runs_root)

    stage_root = tmp_path / "stage"
    exit_code = package_script.main(
        [
            "--runs-dir",
            str(runs_root),
            "--dest",
            str(stage_root),
            "--name",
            "demo_runs",
            "--run",
            "alpha_20260101_120000_deadbeef",
            "--profile",
            "full",
        ]
    )

    assert exit_code == 0
    alpha_dir = stage_root / "alpha_20260101_120000_deadbeef"
    assert (alpha_dir / "eval_scored.parquet").exists()
    assert (alpha_dir / "dataset.parquet").exists()
    assert (alpha_dir / "debug_trace.txt").exists()


def test_release_runs_builds_multiple_tarballs_for_selected_runs(tmp_path):
    package_script = _load_module("csml.release_tools.package_runs")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    runs_root = _prepare_demo_runs(repo_root)

    _configure_package_script(package_script, repo_root, runs_root)

    stage_root = tmp_path / "stage"
    exit_code = package_script.main(
        [
            "--runs-dir",
            str(runs_root),
            "--dest",
            str(stage_root),
            "--name",
            "demo_runs",
        ]
    )
    assert exit_code == 0

    release_script = _load_module("csml.release_tools.release_runs")
    tar_dir = tmp_path / "tarballs"
    exit_code = release_script.main(
        [
            "--staged-root",
            str(stage_root),
            "--tar-dir",
            str(tar_dir),
            "--run-name-prefix",
            "alpha",
            "--skip-upload",
        ]
    )

    assert exit_code == 0
    assert (tar_dir / "runs-demo_runs-alpha_20260101_120000_deadbeef.tar.gz").exists()
    assert not (tar_dir / "runs-demo_runs-beta_20260102_130000_abcd1234.tar.gz").exists()
    assert (stage_root / "README.md").exists()


def test_release_runs_creates_single_release_with_multiple_assets(tmp_path, monkeypatch):
    package_script = _load_module("csml.release_tools.package_runs")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    runs_root = _prepare_demo_runs(repo_root)

    _configure_package_script(package_script, repo_root, runs_root)

    stage_root = tmp_path / "stage"
    exit_code = package_script.main(
        [
            "--runs-dir",
            str(runs_root),
            "--dest",
            str(stage_root),
            "--name",
            "demo_runs",
        ]
    )
    assert exit_code == 0

    release_script = _load_module("csml.release_tools.release_runs")
    calls: list[list[str]] = []

    def _fake_run(cmd: list[str], *, dry_run: bool, capture: bool = False):
        calls.append(cmd)
        if cmd[:3] == ["gh", "release", "view"]:
            return subprocess.CompletedProcess(cmd, 1, "", "")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(release_script, "_run", _fake_run)
    monkeypatch.setattr(release_script, "_ensure_gh", lambda: None)

    tar_dir = tmp_path / "tarballs"
    exit_code = release_script.main(
        [
            "--staged-root",
            str(stage_root),
            "--tar-dir",
            str(tar_dir),
        ]
    )

    assert exit_code == 0
    create_cmd = next(cmd for cmd in calls if cmd[:3] == ["gh", "release", "create"])
    assert any(item.endswith("runs-demo_runs-alpha_20260101_120000_deadbeef.tar.gz") for item in create_cmd)
    assert any(item.endswith("runs-demo_runs-beta_20260102_130000_abcd1234.tar.gz") for item in create_cmd)


def test_release_runs_forwards_filters_to_package_step(tmp_path, monkeypatch):
    _, stage_root = _stage_demo_runs(tmp_path)
    release_script = _load_module("csml.release_tools.release_runs")

    calls: list[list[str]] = []

    def _fake_run(cmd: list[str], *, dry_run: bool, capture: bool = False):
        calls.append(cmd)
        if cmd[0].endswith("python") or cmd[0].endswith("python3") or cmd[0] == "python":
            return subprocess.CompletedProcess(
                cmd,
                0,
                f"Staged run parts at: {stage_root}\nRun alpha_20260101_120000_deadbeef: {stage_root / 'alpha_20260101_120000_deadbeef'}\n",
                "",
            )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(release_script, "_run", _fake_run)

    tar_dir = tmp_path / "tarballs"
    exit_code = release_script.main(
        [
            "--tar-dir",
            str(tar_dir),
            "--profile",
            "milestone",
            "--run-name-prefix",
            "alpha",
            "--latest-n",
            "1",
            "--skip-upload",
            "--name",
            "demo_runs",
        ]
    )

    assert exit_code == 0
    package_cmd = calls[0]
    assert package_cmd[1:3] == ["-m", "csml.release_tools.package_runs"]
    assert "--profile" in package_cmd
    assert package_cmd[package_cmd.index("--profile") + 1] == "milestone"
    assert "--run-name-prefix" in package_cmd
    assert package_cmd[package_cmd.index("--run-name-prefix") + 1] == "alpha"
    assert "--latest-n" in package_cmd
    assert package_cmd[package_cmd.index("--latest-n") + 1] == "1"
