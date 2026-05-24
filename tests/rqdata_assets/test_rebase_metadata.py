from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from cstree.current_assets import default_hk_current_contract_path, hk_current_candidate_paths
from cstree.data_tools.rqdata_assets.rebase_metadata import rebase_hk_asset_metadata


def _args(artifacts_root: Path, old_root: Path, new_root: Path, *, execute: bool, out: Path):
    return SimpleNamespace(
        artifacts_root=str(artifacts_root),
        from_prefix=str(old_root),
        to_prefix=str(new_root),
        max_file_bytes=5_000_000,
        execute=execute,
        format="json",
        out=str(out),
    )


def test_rebase_hk_asset_metadata_dry_run_does_not_modify_live_manifest(tmp_path):
    old_root = tmp_path / "old-repo"
    new_root = tmp_path / "new-repo"
    artifacts_root = new_root / "artifacts"
    manifest_path = artifacts_root / "assets" / "rqdata" / "hk" / "daily" / "snapshot" / "manifest.yml"
    manifest_path.parent.mkdir(parents=True)
    original = f"dataset: daily\noutput_dir: {old_root}/artifacts/assets/rqdata/hk/daily/snapshot\n"
    manifest_path.write_text(original, encoding="utf-8")
    report_path = tmp_path / "dry_run.json"

    assert rebase_hk_asset_metadata(
        _args(artifacts_root, old_root, new_root, execute=False, out=report_path)
    ) == 0

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["summary"]["files_changed"] == 1
    assert payload["summary"]["current_contract_rebuilt"] is False
    assert manifest_path.read_text(encoding="utf-8") == original


def test_rebase_hk_asset_metadata_matches_literal_old_symlink_prefix(tmp_path):
    old_real_root = tmp_path / "old-real-repo"
    old_real_root.mkdir()
    old_root = tmp_path / "old-link-repo"
    old_root.symlink_to(old_real_root, target_is_directory=True)
    new_root = tmp_path / "new-repo"
    artifacts_root = new_root / "artifacts"
    manifest_path = artifacts_root / "assets" / "rqdata" / "hk" / "daily" / "snapshot" / "manifest.yml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        f"output_dir: {old_root}/artifacts/assets/rqdata/hk/daily/snapshot\n",
        encoding="utf-8",
    )
    report_path = tmp_path / "dry_run_symlink_prefix.json"

    assert rebase_hk_asset_metadata(
        _args(artifacts_root, old_root, new_root, execute=False, out=report_path)
    ) == 0

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["summary"]["from_prefix"] == str(old_root)
    assert payload["summary"]["files_changed"] == 1


def test_rebase_hk_asset_metadata_rejects_nonpositive_scan_limit(tmp_path):
    args = _args(
        tmp_path / "new-repo" / "artifacts",
        tmp_path / "old-repo",
        tmp_path / "new-repo",
        execute=False,
        out=tmp_path / "invalid_limit.json",
    )
    args.max_file_bytes = 0

    with pytest.raises(SystemExit, match="--max-file-bytes must be > 0"):
        rebase_hk_asset_metadata(args)


def test_rebase_hk_asset_metadata_updates_manifests_and_rebuilds_current_contract(tmp_path):
    old_root = tmp_path / "old-repo"
    new_root = tmp_path / "new-repo"
    artifacts_root = new_root / "artifacts"
    candidate_paths = hk_current_candidate_paths(artifacts_root)
    daily_snapshot = (
        artifacts_root
        / "assets"
        / "rqdata"
        / "hk"
        / "daily"
        / "hk_all_2000_20260410_daily_latest"
    )
    daily_snapshot.mkdir(parents=True)
    (daily_snapshot / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "daily",
                "status": "completed",
                "output_dir": str(
                    old_root
                    / "artifacts"
                    / "assets"
                    / "rqdata"
                    / "hk"
                    / "daily"
                    / daily_snapshot.name
                ),
                "query": {"end_date": "20260410"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    candidate_paths["daily"].parent.mkdir(parents=True, exist_ok=True)
    candidate_paths["daily"].symlink_to(daily_snapshot.name, target_is_directory=True)

    contract_path = default_hk_current_contract_path(artifacts_root)
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(
        json.dumps(
            {
                "contract": {
                    "target_date": "20260410",
                    "artifacts_root": str(old_root / "artifacts"),
                },
                "assets": {},
            }
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "execute.json"

    assert rebase_hk_asset_metadata(
        _args(artifacts_root, old_root, new_root, execute=True, out=report_path)
    ) == 0

    manifest = yaml.safe_load((daily_snapshot / "manifest.yml").read_text(encoding="utf-8"))
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert manifest["output_dir"] == str(daily_snapshot)
    assert contract["contract"]["generated_by"] == "rebase-hk-asset-metadata"
    assert contract["assets"]["daily"]["resolved_path"] == str(daily_snapshot)
    assert payload["summary"]["current_contract_rebuilt"] is True
    assert (artifacts_root / "metadata" / "dataset_registry.csv").exists()
