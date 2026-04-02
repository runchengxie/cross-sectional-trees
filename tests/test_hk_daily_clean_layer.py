import json
from types import SimpleNamespace

import pandas as pd
import yaml

from csml.data_tools import rqdata_assets


def test_build_hk_daily_clean_layer_fixes_supported_anomalies_and_preserves_base_files(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "daily_demo"
    data_dir = asset_dir / "data"
    data_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    (asset_dir / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "daily",
                "query": {
                    "start_date": "20260301",
                    "end_date": "20260331",
                    "frequency": "1d",
                    "adjust_type": "pre",
                    "skip_suspended": True,
                    "fields": ["open", "high", "low", "close", "volume", "total_turnover"],
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    (asset_dir / "fields.txt").write_text(
        "open\nhigh\nlow\nclose\nvolume\ntotal_turnover\n",
        encoding="utf-8",
    )
    (asset_dir / "symbols.txt").write_text(
        "00005.HK\n00011.HK\n00700.HK\n00941.HK\n",
        encoding="utf-8",
    )

    pd.DataFrame(
        {
            "trade_date": ["20260330", "20260331"],
            "symbol": ["00005.HK", "00005.HK"],
            "order_book_id": ["00005.XHKG", "00005.XHKG"],
            "open": [10.0, 11.0],
            "high": [9.0, 11.5],
            "low": [8.5, 10.5],
            "close": [10.2, 11.2],
            "volume": [1000.0, 1100.0],
            "total_turnover": [10000.0, 11000.0],
        }
    ).to_parquet(data_dir / "00005.HK.parquet", index=False)
    pd.DataFrame(
        {
            "trade_date": ["20260327", "20260328", "20260331"],
            "symbol": ["00011.HK", "00011.HK", "00011.HK"],
            "order_book_id": ["00011.XHKG", "00011.XHKG", "00011.XHKG"],
            "open": [0.0, 0.0, 20.0],
            "high": [0.0, 0.0, 21.0],
            "low": [0.0, 0.0, 19.0],
            "close": [0.0, 0.0, 20.5],
            "volume": [0.0, 0.0, -50.0],
            "total_turnover": [0.0, 0.0, -500.0],
        }
    ).to_parquet(data_dir / "00011.HK.parquet", index=False)
    pd.DataFrame(
        {
            "trade_date": ["20260331"],
            "symbol": ["00700.HK"],
            "order_book_id": ["00700.XHKG"],
            "open": [30.0],
            "high": [31.0],
            "low": [29.0],
            "close": [30.5],
            "volume": [900.0],
            "total_turnover": [9000.0],
        }
    ).to_parquet(data_dir / "00700.HK.parquet", index=False)

    out_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "daily_clean_demo"
    alias_path = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "daily_clean_latest"
    args = SimpleNamespace(
        asset_dir=str(asset_dir),
        out_dir=str(out_dir),
        alias=str(alias_path),
        symbols_file=None,
        zero_price_min_run=2,
        overwrite=False,
    )

    assert rqdata_assets.build_hk_daily_clean_layer(args) == 0

    cleaned_00005 = pd.read_parquet(out_dir / "data" / "00005.HK.parquet")
    assert cleaned_00005.loc[0, "high"] == 10.2
    assert cleaned_00005.loc[0, "low"] == 8.5

    cleaned_00011 = pd.read_parquet(out_dir / "data" / "00011.HK.parquet")
    assert cleaned_00011.loc[0, ["open", "high", "low", "close", "volume", "total_turnover"]].isna().all()
    assert cleaned_00011.loc[1, ["open", "high", "low", "close", "volume", "total_turnover"]].isna().all()
    assert pd.isna(cleaned_00011.loc[2, "volume"])
    assert pd.isna(cleaned_00011.loc[2, "total_turnover"])

    assert (out_dir / "data" / "00700.HK.parquet").is_symlink()
    assert alias_path.is_symlink()
    assert alias_path.resolve() == out_dir.resolve()

    audit = pd.read_csv(out_dir / "audit.csv")
    status_map = dict(zip(audit["symbol"], audit["status"], strict=False))
    assert status_map["00005.HK"] == "cleaned"
    assert status_map["00011.HK"] == "cleaned"
    assert status_map["00700.HK"] == "linked_base"
    assert status_map["00941.HK"] == "missing_source_asset"
    missing_error = audit.loc[audit["symbol"] == "00941.HK", "error"].iloc[0]
    assert missing_error == "Source daily parquet is missing from the base asset snapshot."

    report = json.loads((out_dir / "cleaning_report.json").read_text(encoding="utf-8"))
    assert report["summary"]["symbols_cleaned"] == 2
    assert report["summary"]["symbols_linked_base"] == 1
    assert report["summary"]["symbols_missing_source_asset"] == 1
    assert report["summary"]["rows_price_bounds_fixed"] == 1
    assert report["summary"]["rows_zero_price_nulled"] == 2
    assert report["summary"]["rows_negative_volume_nulled"] == 1
    assert report["summary"]["rows_negative_total_turnover_nulled"] == 1
    assert report["summary"]["remaining_price_bounds_rows"] == 0
    assert report["summary"]["remaining_nonpositive_price_rows"] == 0
    assert report["summary"]["remaining_negative_volume_rows"] == 0
    assert report["summary"]["remaining_negative_total_turnover_rows"] == 0

    health_out = repo_root / "daily_clean_health.json"
    health_args = SimpleNamespace(
        asset_dir=str(out_dir),
        symbols_file=None,
        by_date_file=None,
        field=[],
        date_column=None,
        target_date="20260331",
        sample_limit=5,
        top_latest_dates=5,
        include_history=True,
        history_sample_limit=5,
        format="json",
        out=str(health_out),
    )
    assert rqdata_assets.inspect_hk_asset_health(health_args) == 0

    health = json.loads(health_out.read_text(encoding="utf-8"))
    assert health["summary"]["history_issue_count"] == 0
    assert health["quality_checks"] == []

    filtered_health_out = repo_root / "daily_clean_health_full_symbols.json"
    filtered_health_args = SimpleNamespace(
        asset_dir=str(out_dir),
        symbols_file=str(out_dir / "symbols.txt"),
        by_date_file=None,
        field=[],
        date_column=None,
        target_date="20260331",
        sample_limit=5,
        top_latest_dates=5,
        include_history=False,
        history_sample_limit=5,
        format="json",
        out=str(filtered_health_out),
    )
    assert rqdata_assets.inspect_hk_asset_health(filtered_health_args) == 0

    filtered_health = json.loads(filtered_health_out.read_text(encoding="utf-8"))
    assert filtered_health["audit_issue_groups"] == [
        {
            "status": "missing_source_asset",
            "issue_category": "Source daily parquet is missing from the base asset snapshot.",
            "error": "Source daily parquet is missing from the base asset snapshot.",
            "affected_symbols": 1,
            "sample_symbols": ["00941.HK"],
        }
    ]

    overwrite_args = SimpleNamespace(
        asset_dir=str(asset_dir),
        out_dir=str(out_dir),
        alias=str(alias_path),
        symbols_file=None,
        zero_price_min_run=2,
        overwrite=True,
    )
    assert rqdata_assets.build_hk_daily_clean_layer(overwrite_args) == 0


def test_build_hk_daily_clean_layer_applies_etf_second_pass_only_to_vanilla_products(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "etf_demo"
    data_dir = asset_dir / "data"
    data_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    (asset_dir / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "daily",
                "query": {
                    "start_date": "20260301",
                    "end_date": "20260331",
                    "frequency": "1d",
                    "fields": ["open", "high", "low", "close", "volume", "total_turnover"],
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    (asset_dir / "fields.txt").write_text(
        "open\nhigh\nlow\nclose\nvolume\ntotal_turnover\n",
        encoding="utf-8",
    )
    (asset_dir / "symbols.txt").write_text(
        "02800.HK\n07200.HK\n",
        encoding="utf-8",
    )

    pd.DataFrame(
        {
            "trade_date": ["20260330", "20260331"],
            "symbol": ["02800.HK", "02800.HK"],
            "order_book_id": ["02800.XHKG", "02800.XHKG"],
            "open": [0.0, 100.0],
            "high": [0.0, 101.0],
            "low": [0.0, 99.0],
            "close": [0.0, 100.5],
            "volume": [0.0, 1000.0],
            "total_turnover": [0.0, 100500.0],
        }
    ).to_parquet(data_dir / "02800.HK.parquet", index=False)
    pd.DataFrame(
        {
            "trade_date": ["20260330", "20260331"],
            "symbol": ["07200.HK", "07200.HK"],
            "order_book_id": ["07200.XHKG", "07200.XHKG"],
            "open": [0.0, 50.0],
            "high": [0.0, 51.0],
            "low": [0.0, 49.0],
            "close": [0.0, 50.5],
            "volume": [0.0, 500.0],
            "total_turnover": [0.0, 25250.0],
        }
    ).to_parquet(data_dir / "07200.HK.parquet", index=False)

    instruments_path = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "instruments" / "hk_etf_instruments_latest.parquet"
    instruments_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "symbol": ["02800.HK", "07200.HK"],
            "name": ["盈富基金", "南方两倍看多恒指"],
            "eng_symbol": ["TRACKER FUND", "2X HSI LONG"],
            "type": ["ETF", "ETF"],
        }
    ).to_parquet(instruments_path, index=False)

    out_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "etf_clean_demo"
    args = SimpleNamespace(
        asset_dir=str(asset_dir),
        out_dir=str(out_dir),
        alias=None,
        symbols_file=None,
        instruments_file=str(instruments_path),
        zero_price_min_run=5,
        etf_short_zero_max_run=2,
        overwrite=False,
    )

    assert rqdata_assets.build_hk_daily_clean_layer(args) == 0

    cleaned_vanilla = pd.read_parquet(out_dir / "data" / "02800.HK.parquet")
    assert cleaned_vanilla.loc[0, ["open", "high", "low", "close", "volume", "total_turnover"]].isna().all()

    special_path = out_dir / "data" / "07200.HK.parquet"
    assert special_path.is_symlink()
    cleaned_special = pd.read_parquet(special_path)
    assert cleaned_special.loc[0, ["open", "high", "low", "close", "volume", "total_turnover"]].tolist() == [
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    ]

    audit = pd.read_csv(out_dir / "audit.csv")
    status_map = dict(zip(audit["symbol"], audit["status"], strict=False))
    assert status_map == {
        "02800.HK": "cleaned",
        "07200.HK": "linked_base",
    }

    report = json.loads((out_dir / "cleaning_report.json").read_text(encoding="utf-8"))
    assert report["summary"]["rows_zero_price_nulled"] == 0
    assert report["summary"]["rows_etf_short_zero_nulled"] == 1
    assert report["summary"]["etf_short_zero_segments_nulled"] == 1
    assert report["summary"]["etf_short_zero_segments_flagged_special"] == 1
    assert report["summary"]["etf_short_zero_rows_flagged_special"] == 1
    assert report["summary"]["remaining_nonpositive_price_rows"] == 1
    assert report["etf_second_pass"]["enabled"] is True
    assert report["etf_second_pass"]["product_profile_counts"] == {
        "leveraged_or_inverse": 1,
        "vanilla": 1,
    }
    assert report["etf_second_pass"]["sample_flagged_segments"] == [
        {
            "symbol": "07200.HK",
            "product_profile": "leveraged_or_inverse",
            "reason": "special_product:leveraged_or_inverse",
            "run_length": 1,
            "start_trade_date": "2026-03-30",
            "end_trade_date": "2026-03-30",
        }
    ]
