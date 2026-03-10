from pathlib import Path

import yaml

from csml.project_tools import backup_data


def test_backup_data_copies_selected_paths_and_writes_manifest(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "artifacts" / "cache").mkdir(parents=True)
    (repo_root / "artifacts" / "cache" / "prices.parquet").write_text(
        "cache-data",
        encoding="utf-8",
    )
    (repo_root / "artifacts" / "assets" / "universe").mkdir(parents=True)
    (repo_root / "artifacts" / "assets" / "universe" / "universe_by_date.csv").write_text(
        "trade_date,ts_code\n20250131,00005.HK\n",
        encoding="utf-8",
    )
    (repo_root / "config").mkdir()
    (repo_root / "config" / "hk.yml").write_text("market: hk\n", encoding="utf-8")

    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(
        backup_data,
        "_git_metadata",
        lambda repo_root: {
            "commit": "deadbeef" * 5,
            "short_commit": "deadbeef",
            "branch": "main",
            "is_dirty": True,
        },
    )

    assert (
        backup_data.main(
            [
                "--out-root",
                "artifacts/snapshots",
                "--name",
                "hk_frozen",
                "--config",
                "config/hk.yml",
            ]
        )
        == 0
    )

    snapshot_dir = repo_root / "artifacts/snapshots" / "hk_frozen"
    assert (snapshot_dir / "artifacts" / "cache" / "prices.parquet").exists()
    assert (snapshot_dir / "artifacts" / "assets" / "universe" / "universe_by_date.csv").exists()
    assert (snapshot_dir / "config" / "hk.yml").exists()

    manifest = yaml.safe_load((snapshot_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["name"] == "hk_frozen"
    assert manifest["git"]["short_commit"] == "deadbeef"
    assert manifest["git"]["is_dirty"] is True
    assert manifest["totals"]["paths"] == 3
    assert manifest["totals"]["files"] == 3


def test_backup_data_skip_missing_allows_partial_snapshot(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "artifacts" / "cache").mkdir(parents=True)
    (repo_root / "artifacts" / "cache" / "prices.parquet").write_text(
        "cache-data",
        encoding="utf-8",
    )

    monkeypatch.chdir(repo_root)

    assert (
        backup_data.main(
            [
                "--out-root",
                "artifacts/snapshots",
                "--name",
                "partial",
                "--no-universe",
                "--include-path",
                "missing_dir",
                "--skip-missing",
            ]
        )
        == 0
    )

    snapshot_dir = repo_root / "artifacts/snapshots" / "partial"
    assert (snapshot_dir / "artifacts" / "cache" / "prices.parquet").exists()
    manifest = yaml.safe_load((snapshot_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["totals"]["paths"] == 1
