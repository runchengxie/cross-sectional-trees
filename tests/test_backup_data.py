from pathlib import Path

import pytest
import yaml

from csml.data_tools import backup_data


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
        "trade_date,symbol\n20250131,00005.HK\n",
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


def test_backup_data_places_repo_external_paths_under_external_prefix(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    external_file = tmp_path / "outside.txt"
    external_file.write_text("outside", encoding="utf-8")

    monkeypatch.chdir(repo_root)

    assert (
        backup_data.main(
            [
                "--out-root",
                "artifacts/snapshots",
                "--name",
                "external_only",
                "--no-cache",
                "--no-universe",
                "--include-path",
                str(external_file),
            ]
        )
        == 0
    )

    snapshot_dir = repo_root / "artifacts/snapshots" / "external_only"
    rel_target = backup_data._relative_target_path(external_file.resolve(), repo_root.resolve())
    copied_path = snapshot_dir / rel_target
    assert copied_path.exists()
    assert copied_path.read_text(encoding="utf-8") == "outside"

    manifest = yaml.safe_load((snapshot_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["entries"][0]["target"] == str(copied_path)


def test_backup_data_rejects_existing_snapshot_dir(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "artifacts" / "snapshots" / "hk_frozen").mkdir(parents=True)

    monkeypatch.chdir(repo_root)

    with pytest.raises(SystemExit, match="Refusing to overwrite existing snapshot"):
        backup_data.main(["--name", "hk_frozen"])


def test_backup_data_requires_at_least_one_selected_path(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    monkeypatch.chdir(repo_root)

    with pytest.raises(SystemExit, match="No paths selected for backup."):
        backup_data.main(["--name", "empty", "--no-cache", "--no-universe"])


def test_backup_data_cleans_output_dir_after_copy_failure(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "artifacts" / "cache").mkdir(parents=True)
    (repo_root / "artifacts" / "cache" / "prices.parquet").write_text(
        "cache-data",
        encoding="utf-8",
    )

    monkeypatch.chdir(repo_root)

    def _raise_copy(_source: Path, _target: Path) -> None:
        raise RuntimeError("copy failed")

    monkeypatch.setattr(backup_data, "_copy_path", _raise_copy)

    snapshot_dir = repo_root / "artifacts" / "snapshots" / "broken"
    with pytest.raises(RuntimeError, match="copy failed"):
        backup_data.main(["--name", "broken", "--no-universe"])

    assert not snapshot_dir.exists()
