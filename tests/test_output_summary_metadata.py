import os
import json
from pathlib import Path

import yaml

from cstree.pipeline.output_summary_metadata import build_inputs_lock


def test_build_inputs_lock_records_symlink_resolution_and_manifest_metadata(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    snapshot_dir = tmp_path / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "hk_all_2000_20260327_daily_clean"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "daily",
                "status": "completed",
                "output_dir": str(snapshot_dir),
                "query": {
                    "start_date": "20000101",
                    "end_date": "20260327",
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    expected_manifest_summary = {
        "dataset": "daily",
        "status": "completed",
        "output_dir": str(snapshot_dir),
        "snapshot_name": snapshot_dir.name,
        "query_start_date": "20000101",
        "query_end_date": "20260327",
        "totals": {},
    }

    alias_path = tmp_path / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "hk_all_daily_clean_latest"
    alias_path.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(os.path.relpath(snapshot_dir, start=alias_path.parent), alias_path, target_is_directory=True)

    current_contract_path = tmp_path / "artifacts" / "metadata" / "current_assets" / "hk_current.json"
    current_contract_path.parent.mkdir(parents=True, exist_ok=True)
    current_contract_path.write_text(
        json.dumps(
            {
                "contract": {
                    "name": "hk_current",
                    "market": "hk",
                    "version": 1,
                },
                "assets": {
                    "daily_clean": {
                        "alias_path": str(alias_path.absolute()),
                        "resolved_path": str(snapshot_dir.resolve()),
                        "manifest_path": str(snapshot_dir / "manifest.yml"),
                        "manifest": expected_manifest_summary,
                        "as_of": "20260327",
                        "exists": True,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    run_dir = tmp_path / "artifacts" / "runs" / "demo_20260409_deadbeef"
    context = {
        "data_cfg": {
            "start_date": "20200101",
            "end_date": "20200331",
            "rqdata": {
                "daily_asset_dir": "artifacts/assets/rqdata/hk/daily/hk_all_daily_clean_latest",
            },
        },
        "eval_cfg": {},
        "live_cfg": {},
        "ARTIFACTS_ROOT": tmp_path / "artifacts",
        "run_dir": run_dir,
        "config_path": tmp_path / "config.yml",
        "config_source": "file",
        "START_DATE": "20200101",
        "END_DATE": "20200331",
        "LIVE_AS_OF": None,
        "CACHE_DIR": "cache",
        "by_date_file": None,
        "FUNDAMENTALS_FILE": None,
        "INDUSTRY_FILE": None,
        "BACKTEST_BENCHMARK_RETURNS_FILE": None,
        "BACKTEST_BENCHMARK_COMPARE": [],
    }

    payload = build_inputs_lock(context)

    assert payload["inputs"]["cache_dir"] == str(cache_dir.resolve())
    assert payload["inputs"]["daily_asset_dir"] == str(snapshot_dir.resolve())
    assert payload["source_manifests"]["daily_asset_dir_manifest"] == str(snapshot_dir / "manifest.yml")
    assert payload["current_contracts"] == {"hk_current": str(current_contract_path)}

    daily_resolution = payload["input_resolution"]["daily_asset_dir"]
    assert daily_resolution["raw"] == "artifacts/assets/rqdata/hk/daily/hk_all_daily_clean_latest"
    assert daily_resolution["configured_path"] == str(alias_path.absolute())
    assert daily_resolution["resolved_path"] == str(snapshot_dir.resolve())
    assert daily_resolution["path_kind"] == "directory"
    assert daily_resolution["exists"] is True
    assert daily_resolution["is_symlink"] is True
    assert daily_resolution["points_to_latest_name"] is True
    assert daily_resolution["manifest_path"] == str(snapshot_dir / "manifest.yml")
    assert daily_resolution["manifest"] == expected_manifest_summary
    assert daily_resolution["current_contract"] == {
        "contract_name": "hk_current",
        "contract_path": str(current_contract_path),
        "asset_key": "daily_clean",
        "alias_path": str(alias_path.absolute()),
        "resolved_path": str(snapshot_dir.resolve()),
        "manifest_path": str(snapshot_dir / "manifest.yml"),
        "manifest": expected_manifest_summary,
        "as_of": "20260327",
    }
