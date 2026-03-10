from pathlib import Path

import pytest

from csml.project_tools import migrate_artifacts


def test_migrate_artifacts_moves_legacy_paths_into_artifacts(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "cache").mkdir()
    (repo_root / "cache" / "prices.parquet").write_text("cache-data", encoding="utf-8")
    (repo_root / "out" / "universe").mkdir(parents=True)
    (repo_root / "out" / "universe" / "universe_by_date.csv").write_text(
        "trade_date,ts_code\n20250131,00005.HK\n",
        encoding="utf-8",
    )
    (repo_root / "data_mirror" / "snap_a").mkdir(parents=True)
    (repo_root / "data_mirror" / "snap_a" / "manifest.yml").write_text(
        "name: snap_a\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(repo_root)

    assert migrate_artifacts.main([]) == 0

    assert not (repo_root / "cache").exists()
    assert not (repo_root / "out" / "universe").exists()
    assert not (repo_root / "data_mirror").exists()
    assert (repo_root / "artifacts" / "cache" / "prices.parquet").exists()
    assert (repo_root / "artifacts" / "assets" / "universe" / "universe_by_date.csv").exists()
    assert (repo_root / "artifacts" / "snapshots" / "snap_a" / "manifest.yml").exists()


def test_migrate_artifacts_merges_into_existing_artifacts_dirs(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "out" / "universe").mkdir(parents=True)
    (repo_root / "out" / "universe" / "hk_connect_symbols.txt").write_text(
        "00005.HK\n",
        encoding="utf-8",
    )
    (repo_root / "artifacts" / "assets" / "universe").mkdir(parents=True)
    (repo_root / "artifacts" / "assets" / "universe" / "universe_by_date.csv").write_text(
        "trade_date,ts_code\n20250131,00005.HK\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(repo_root)

    assert migrate_artifacts.main([]) == 0

    assert not (repo_root / "out" / "universe").exists()
    assert (repo_root / "artifacts" / "assets" / "universe" / "universe_by_date.csv").exists()
    assert (repo_root / "artifacts" / "assets" / "universe" / "hk_connect_symbols.txt").exists()


def test_migrate_artifacts_conflict_requires_force(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "cache").mkdir()
    (repo_root / "cache" / "prices.parquet").write_text("old-cache", encoding="utf-8")
    (repo_root / "artifacts" / "cache").mkdir(parents=True)
    (repo_root / "artifacts" / "cache" / "prices.parquet").write_text(
        "new-cache",
        encoding="utf-8",
    )

    monkeypatch.chdir(repo_root)

    with pytest.raises(SystemExit, match="Refusing to overwrite existing artifact targets"):
        migrate_artifacts.main([])

    assert migrate_artifacts.main(["--force"]) == 0
    assert (repo_root / "artifacts" / "cache" / "prices.parquet").read_text(encoding="utf-8") == "old-cache"
