import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import yaml

from csml import data_providers
from csml.data_tools import rqdata_assets


def test_inspect_hk_asset_health_include_history_flags_prior_daily_anomalies(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "daily_history_demo"
    data_dir = asset_dir / "data"
    data_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    (asset_dir / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "daily",
                "query": {
                    "end_date": "20260331",
                    "fields": ["open", "high", "low", "close", "volume", "total_turnover"],
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    pd.DataFrame(
        {
            "trade_date": ["20260330", "20260331"],
            "open": [10.0, 11.0],
            "high": [9.0, 11.5],
            "low": [8.0, 10.5],
            "close": [10.2, 11.2],
            "volume": [1000.0, 1100.0],
            "total_turnover": [10000.0, 11000.0],
        }
    ).to_parquet(data_dir / "00005.HK.parquet", index=False)
    pd.DataFrame(
        {
            "trade_date": ["20260331"],
            "open": [20.0],
            "high": [21.0],
            "low": [19.0],
            "close": [20.5],
            "volume": [-50.0],
            "total_turnover": [-500.0],
        }
    ).to_parquet(data_dir / "00011.HK.parquet", index=False)

    pd.DataFrame(
        [
            {
                "symbol": "00005.HK",
                "order_book_id": "00005.XHKG",
                "status": "merged_patch",
                "max_trade_date": "20260331",
            },
            {
                "symbol": "00011.HK",
                "order_book_id": "00011.XHKG",
                "status": "merged_patch",
                "max_trade_date": "20260331",
            },
        ]
    ).to_csv(asset_dir / "audit.csv", index=False)

    out_path = repo_root / "daily_history_health.json"
    args = SimpleNamespace(
        asset_dir=str(asset_dir),
        symbols_file=None,
        by_date_file=None,
        field=[],
        date_column=None,
        target_date="20260331",
        sample_limit=5,
        top_latest_dates=5,
        include_history=True,
        history_sample_limit=3,
        format="json",
        out=str(out_path),
    )

    assert rqdata_assets.inspect_hk_asset_health(args) == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["include_history"] is True
    assert payload["summary"]["history_issue_count"] == 3
    assert payload["summary"]["history_rows_scanned"] == 3

    history = payload["history"]
    assert history["summary"] == {
        "dataset": "daily",
        "symbols_scanned": 2,
        "rows_scanned": 3,
        "date_min": "2026-03-30",
        "date_max": "2026-03-31",
        "issue_count": 3,
    }

    issues = {item["check"]: item for item in history["issues"]}
    assert issues["daily_price_bounds_violation_any_date"] == {
        "check": "daily_price_bounds_violation_any_date",
        "severity": "error",
        "affected_symbols": 1,
        "affected_rows": 1,
        "sample_rows": [
            {
                "symbol": "00005.HK",
                "trade_date": "2026-03-30",
                "open": 10,
                "high": 9,
                "low": 8,
                "close": 10.2,
            }
        ],
    }
    assert issues["daily_negative_volume_any_date"] == {
        "check": "daily_negative_volume_any_date",
        "severity": "error",
        "affected_symbols": 1,
        "affected_rows": 1,
        "sample_rows": [
            {
                "symbol": "00011.HK",
                "trade_date": "2026-03-31",
                "volume": -50,
            }
        ],
    }
    assert issues["daily_negative_total_turnover_any_date"] == {
        "check": "daily_negative_total_turnover_any_date",
        "severity": "error",
        "affected_symbols": 1,
        "affected_rows": 1,
        "sample_rows": [
            {
                "symbol": "00011.HK",
                "trade_date": "2026-03-31",
                "total_turnover": -500,
            }
        ],
    }

def test_inspect_hk_asset_health_include_history_reports_valuation_stale_runs(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "valuation" / "valuation_history_demo"
    data_dir = asset_dir / "data"
    data_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    (asset_dir / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "valuation",
                "query": {
                    "end_date": "20260331",
                    "fields": ["pe_ratio_ttm"],
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    pd.DataFrame(
        {
            "trade_date": ["20260320", "20260323", "20260324", "20260325", "20260326", "20260327"],
            "pe_ratio_ttm": [10.0, 10.0, 10.0, 10.0, 10.0, 10.0],
        }
    ).to_parquet(data_dir / "00005.HK.parquet", index=False)
    pd.DataFrame(
        {
            "trade_date": ["20260327", "20260330", "20260331"],
            "pe_ratio_ttm": [20.0, 21.0, 22.0],
        }
    ).to_parquet(data_dir / "00011.HK.parquet", index=False)

    pd.DataFrame(
        [
            {
                "symbol": "00005.HK",
                "order_book_id": "00005.XHKG",
                "status": "merged_patch",
                "max_date": "2026-03-31",
            },
            {
                "symbol": "00011.HK",
                "order_book_id": "00011.XHKG",
                "status": "merged_patch",
                "max_date": "2026-03-31",
            },
        ]
    ).to_csv(asset_dir / "audit.csv", index=False)

    out_path = repo_root / "valuation_history_health.json"
    args = SimpleNamespace(
        asset_dir=str(asset_dir),
        symbols_file=None,
        by_date_file=None,
        field=["pe_ratio_ttm"],
        date_column=None,
        target_date="20260331",
        sample_limit=5,
        top_latest_dates=5,
        include_history=True,
        history_sample_limit=3,
        format="json",
        out=str(out_path),
    )

    assert rqdata_assets.inspect_hk_asset_health(args) == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["include_history"] is True
    assert payload["summary"]["history_issue_count"] == 1
    assert payload["summary"]["history_rows_scanned"] == 9

    history = payload["history"]
    assert history["summary"] == {
        "dataset": "valuation",
        "symbols_scanned": 2,
        "rows_scanned": 9,
        "date_min": "2026-03-20",
        "date_max": "2026-03-31",
        "issue_count": 1,
    }
    assert history["issues"] == [
        {
            "check": "valuation_stale_run_any_date",
            "severity": "warning",
            "affected_symbols": 1,
            "affected_rows": 6,
            "sample_rows": [
                {
                    "symbol": "00005.HK",
                    "start_date": "2026-03-20",
                    "end_date": "2026-03-27",
                    "run_length": 6,
                    "span_days": 7,
                    "stale_value": 10,
                    "reference_context": "no_daily_reference",
                }
            ],
            "field": "pe_ratio_ttm",
            "stale_run_min_length": 5,
            "run_length_p50": 6,
            "run_length_p90": 6,
            "run_length_max": 6,
            "run_length_gt_3_symbols": 1,
            "run_length_gt_5_symbols": 1,
            "run_length_gt_10_symbols": 0,
        }
    ]

def test_inspect_hk_asset_health_include_history_classifies_provider_like_valuation_stale_runs_with_daily_reference(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "valuation" / "valuation_history_demo"
    data_dir = asset_dir / "data"
    data_dir.mkdir(parents=True)
    daily_asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "daily_ref_demo"
    daily_data_dir = daily_asset_dir / "data"
    daily_data_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    (asset_dir / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "valuation",
                "query": {
                    "end_date": "20260331",
                    "fields": ["pe_ratio_ttm"],
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    pd.DataFrame(
        {
            "trade_date": ["20260320", "20260323", "20260324", "20260325", "20260326", "20260327"],
            "pe_ratio_ttm": [10.0, 10.0, 10.0, 10.0, 10.0, 10.0],
        }
    ).to_parquet(data_dir / "00005.HK.parquet", index=False)
    pd.DataFrame(
        {
            "trade_date": ["20260320", "20260323", "20260324", "20260325", "20260326", "20260327"],
            "pe_ratio_ttm": [20.0, 20.0, 20.0, 20.0, 20.0, 20.0],
        }
    ).to_parquet(data_dir / "00011.HK.parquet", index=False)

    pd.DataFrame(
        {
            "trade_date": ["20260320", "20260323", "20260324", "20260325", "20260326", "20260327"],
            "close": [10.0, 10.0, 10.0, 10.0, 10.0, 10.0],
        }
    ).to_parquet(daily_data_dir / "00005.HK.parquet", index=False)
    pd.DataFrame(
        {
            "trade_date": ["20260320", "20260323", "20260324", "20260325", "20260326", "20260327"],
            "close": [20.0, 21.0, 22.0, 23.0, 24.0, 25.0],
        }
    ).to_parquet(daily_data_dir / "00011.HK.parquet", index=False)

    pd.DataFrame(
        [
            {
                "symbol": "00005.HK",
                "order_book_id": "00005.XHKG",
                "status": "merged_patch",
                "max_date": "2026-03-31",
            },
            {
                "symbol": "00011.HK",
                "order_book_id": "00011.XHKG",
                "status": "merged_patch",
                "max_date": "2026-03-31",
            },
        ]
    ).to_csv(asset_dir / "audit.csv", index=False)

    out_path = repo_root / "valuation_history_health_daily_ref.json"
    args = SimpleNamespace(
        asset_dir=str(asset_dir),
        symbols_file=None,
        by_date_file=None,
        field=["pe_ratio_ttm"],
        date_column=None,
        target_date="20260331",
        daily_asset_dir=str(daily_asset_dir),
        sample_limit=5,
        top_latest_dates=5,
        include_history=True,
        history_sample_limit=3,
        format="json",
        out=str(out_path),
    )

    assert rqdata_assets.inspect_hk_asset_health(args) == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["daily_reference_asset_dir"] == str(daily_asset_dir.resolve())
    history = payload["history"]
    assert history["issues"] == [
        {
            "check": "valuation_stale_run_any_date",
            "severity": "warning",
            "affected_symbols": 1,
            "affected_rows": 6,
            "sample_rows": [
                {
                    "symbol": "00011.HK",
                    "start_date": "2026-03-20",
                    "end_date": "2026-03-27",
                    "run_length": 6,
                    "span_days": 7,
                    "stale_value": 20,
                    "reference_context": "daily_price_changed",
                }
            ],
            "field": "pe_ratio_ttm",
            "stale_run_min_length": 5,
            "run_length_p50": 6,
            "run_length_p90": 6,
            "run_length_max": 6,
            "run_length_gt_3_symbols": 1,
            "run_length_gt_5_symbols": 1,
            "run_length_gt_10_symbols": 0,
        },
        {
            "check": "valuation_stale_run_provider_like_any_date",
            "severity": "info",
            "affected_symbols": 1,
            "affected_rows": 6,
            "sample_rows": [
                {
                    "symbol": "00005.HK",
                    "start_date": "2026-03-20",
                    "end_date": "2026-03-27",
                    "run_length": 6,
                    "span_days": 7,
                    "stale_value": 10,
                    "reference_context": "no_daily_price_change",
                }
            ],
            "field": "pe_ratio_ttm",
            "stale_run_min_length": 5,
            "run_length_p50": 6,
            "run_length_p90": 6,
            "run_length_max": 6,
            "run_length_gt_3_symbols": 1,
            "run_length_gt_5_symbols": 1,
            "run_length_gt_10_symbols": 0,
        }
    ]


def test_inspect_hk_asset_health_include_history_downgrades_valuation_stale_runs_with_ex_factor_events(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "valuation" / "valuation_history_demo"
    data_dir = asset_dir / "data"
    data_dir.mkdir(parents=True)
    daily_asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "daily_ref_demo"
    daily_data_dir = daily_asset_dir / "data"
    daily_data_dir.mkdir(parents=True)
    ex_factor_asset_dir = (
        repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "ex_factors" / "hk_all_ex_factors_latest"
    )
    ex_factor_data_dir = ex_factor_asset_dir / "data"
    ex_factor_data_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    (asset_dir / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "valuation",
                "query": {
                    "end_date": "20260331",
                    "fields": ["pe_ratio_ttm"],
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    pd.DataFrame(
        {
            "trade_date": ["20260320", "20260323", "20260324", "20260325", "20260326", "20260327"],
            "pe_ratio_ttm": [20.0, 20.0, 20.0, 20.0, 20.0, 20.0],
        }
    ).to_parquet(data_dir / "00011.HK.parquet", index=False)

    pd.DataFrame(
        {
            "trade_date": ["20260320", "20260323", "20260324", "20260325", "20260326", "20260327"],
            "close": [20.0, 21.0, 22.0, 23.0, 24.0, 25.0],
        }
    ).to_parquet(daily_data_dir / "00011.HK.parquet", index=False)

    pd.DataFrame(
        {
            "ex_date": ["20260324"],
            "ex_factor": [1.2],
        }
    ).to_parquet(ex_factor_data_dir / "00011.HK.parquet", index=False)

    pd.DataFrame(
        [
            {
                "symbol": "00011.HK",
                "order_book_id": "00011.XHKG",
                "status": "merged_patch",
                "max_date": "2026-03-31",
            }
        ]
    ).to_csv(asset_dir / "audit.csv", index=False)

    out_path = repo_root / "valuation_history_health_ex_factor_ref.json"
    args = SimpleNamespace(
        asset_dir=str(asset_dir),
        symbols_file=None,
        by_date_file=None,
        field=["pe_ratio_ttm"],
        date_column=None,
        target_date="20260331",
        daily_asset_dir=str(daily_asset_dir),
        sample_limit=5,
        top_latest_dates=5,
        include_history=True,
        history_sample_limit=3,
        format="json",
        out=str(out_path),
    )

    assert rqdata_assets.inspect_hk_asset_health(args) == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    history = payload["history"]
    assert history["issues"] == [
        {
            "check": "valuation_stale_run_provider_like_any_date",
            "severity": "info",
            "affected_symbols": 1,
            "affected_rows": 6,
            "sample_rows": [
                {
                    "symbol": "00011.HK",
                    "start_date": "2026-03-20",
                    "end_date": "2026-03-27",
                    "run_length": 6,
                    "span_days": 7,
                    "stale_value": 20,
                    "reference_context": "ex_factor_event_in_window",
                }
            ],
            "field": "pe_ratio_ttm",
            "stale_run_min_length": 5,
            "run_length_p50": 6,
            "run_length_p90": 6,
            "run_length_max": 6,
            "run_length_gt_3_symbols": 1,
            "run_length_gt_5_symbols": 1,
            "run_length_gt_10_symbols": 0,
        }
    ]


def test_inspect_hk_asset_health_include_history_downgrades_valuation_stale_runs_near_delisting_boundary(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "valuation" / "valuation_history_demo"
    data_dir = asset_dir / "data"
    data_dir.mkdir(parents=True)
    daily_asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "daily_ref_demo"
    daily_data_dir = daily_asset_dir / "data"
    daily_data_dir.mkdir(parents=True)
    instruments_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "instruments"
    instruments_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    (asset_dir / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "valuation",
                "query": {
                    "end_date": "20260331",
                    "fields": ["pe_ratio_ttm"],
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    pd.DataFrame(
        {
            "trade_date": ["20260320", "20260323", "20260324", "20260325", "20260326", "20260327"],
            "pe_ratio_ttm": [20.0, 20.0, 20.0, 20.0, 20.0, 20.0],
        }
    ).to_parquet(data_dir / "00011.HK.parquet", index=False)

    pd.DataFrame(
        {
            "trade_date": ["20260320", "20260323", "20260324", "20260325", "20260326", "20260327"],
            "close": [20.0, 21.0, 22.0, 23.0, 24.0, 25.0],
        }
    ).to_parquet(daily_data_dir / "00011.HK.parquet", index=False)

    pd.DataFrame(
        [
            {
                "symbol": "00011.HK",
                "order_book_id": "00011.XHKG",
                "listed_date": "2000-01-03",
                "de_listed_date": "2026-03-28",
                "status": "Delisted",
            },
            {
                "symbol": "00011.HK",
                "order_book_id": "00011.XHKG",
                "listed_date": "2026-04-10",
                "de_listed_date": "0000-00-00",
                "status": "Active",
            },
        ]
    ).to_parquet(instruments_dir / "hk_all_instruments_latest.parquet", index=False)

    pd.DataFrame(
        [
            {
                "symbol": "00011.HK",
                "order_book_id": "00011.XHKG",
                "status": "merged_patch",
                "max_date": "2026-03-31",
            }
        ]
    ).to_csv(asset_dir / "audit.csv", index=False)

    out_path = repo_root / "valuation_history_health_instrument_ref.json"
    args = SimpleNamespace(
        asset_dir=str(asset_dir),
        symbols_file=None,
        by_date_file=None,
        field=["pe_ratio_ttm"],
        date_column=None,
        target_date="20260331",
        daily_asset_dir=str(daily_asset_dir),
        sample_limit=5,
        top_latest_dates=5,
        include_history=True,
        history_sample_limit=3,
        format="json",
        out=str(out_path),
    )

    assert rqdata_assets.inspect_hk_asset_health(args) == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    history = payload["history"]
    assert history["issues"] == [
        {
            "check": "valuation_stale_run_provider_like_any_date",
            "severity": "info",
            "affected_symbols": 1,
            "affected_rows": 6,
            "sample_rows": [
                {
                    "symbol": "00011.HK",
                    "start_date": "2026-03-20",
                    "end_date": "2026-03-27",
                    "run_length": 6,
                    "span_days": 7,
                    "stale_value": 20,
                    "reference_context": "delisted_instrument_boundary",
                }
            ],
            "field": "pe_ratio_ttm",
            "stale_run_min_length": 5,
            "run_length_p50": 6,
            "run_length_p90": 6,
            "run_length_max": 6,
            "run_length_gt_3_symbols": 1,
            "run_length_gt_5_symbols": 1,
            "run_length_gt_10_symbols": 0,
        }
    ]


def test_inspect_hk_asset_health_include_history_downgrades_valuation_stale_runs_with_shares_events(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "valuation" / "valuation_history_demo"
    data_dir = asset_dir / "data"
    data_dir.mkdir(parents=True)
    daily_asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "daily_ref_demo"
    daily_data_dir = daily_asset_dir / "data"
    daily_data_dir.mkdir(parents=True)
    shares_asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "shares" / "hk_all_shares_latest"
    shares_data_dir = shares_asset_dir / "data"
    shares_data_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    (asset_dir / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "valuation",
                "query": {
                    "end_date": "20260331",
                    "fields": ["pe_ratio_ttm"],
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    pd.DataFrame(
        {
            "trade_date": ["20260320", "20260323", "20260324", "20260325", "20260326", "20260327"],
            "pe_ratio_ttm": [20.0, 20.0, 20.0, 20.0, 20.0, 20.0],
        }
    ).to_parquet(data_dir / "00011.HK.parquet", index=False)

    pd.DataFrame(
        {
            "trade_date": ["20260320", "20260323", "20260324", "20260325", "20260326", "20260327"],
            "close": [20.0, 21.0, 22.0, 23.0, 24.0, 25.0],
        }
    ).to_parquet(daily_data_dir / "00011.HK.parquet", index=False)

    pd.DataFrame(
        {
            "date": ["20260324"],
            "total": [100.0],
        }
    ).to_parquet(shares_data_dir / "00011.HK.parquet", index=False)

    pd.DataFrame(
        [
            {
                "symbol": "00011.HK",
                "order_book_id": "00011.XHKG",
                "status": "merged_patch",
                "max_date": "2026-03-31",
            }
        ]
    ).to_csv(asset_dir / "audit.csv", index=False)

    out_path = repo_root / "valuation_history_health_shares_ref.json"
    args = SimpleNamespace(
        asset_dir=str(asset_dir),
        symbols_file=None,
        by_date_file=None,
        field=["pe_ratio_ttm"],
        date_column=None,
        target_date="20260331",
        daily_asset_dir=str(daily_asset_dir),
        sample_limit=5,
        top_latest_dates=5,
        include_history=True,
        history_sample_limit=3,
        format="json",
        out=str(out_path),
    )

    assert rqdata_assets.inspect_hk_asset_health(args) == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    history = payload["history"]
    assert history["issues"] == [
        {
            "check": "valuation_stale_run_provider_like_any_date",
            "severity": "info",
            "affected_symbols": 1,
            "affected_rows": 6,
            "sample_rows": [
                {
                    "symbol": "00011.HK",
                    "start_date": "2026-03-20",
                    "end_date": "2026-03-27",
                    "run_length": 6,
                    "span_days": 7,
                    "stale_value": 20,
                    "reference_context": "shares_event_in_window",
                }
            ],
            "field": "pe_ratio_ttm",
            "stale_run_min_length": 5,
            "run_length_p50": 6,
            "run_length_p90": 6,
            "run_length_max": 6,
            "run_length_gt_3_symbols": 1,
            "run_length_gt_5_symbols": 1,
            "run_length_gt_10_symbols": 0,
        }
    ]


def test_inspect_hk_asset_health_include_history_downgrades_valuation_stale_runs_with_nearby_shares_events(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "valuation" / "valuation_history_demo"
    data_dir = asset_dir / "data"
    data_dir.mkdir(parents=True)
    daily_asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "daily_ref_demo"
    daily_data_dir = daily_asset_dir / "data"
    daily_data_dir.mkdir(parents=True)
    shares_asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "shares" / "hk_all_shares_latest"
    shares_data_dir = shares_asset_dir / "data"
    shares_data_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    (asset_dir / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "valuation",
                "query": {
                    "end_date": "20260331",
                    "fields": ["pe_ratio_ttm"],
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    pd.DataFrame(
        {
            "trade_date": ["20260324", "20260325", "20260326", "20260327", "20260330", "20260331"],
            "pe_ratio_ttm": [20.0, 20.0, 20.0, 20.0, 20.0, 20.0],
        }
    ).to_parquet(data_dir / "00011.HK.parquet", index=False)

    pd.DataFrame(
        {
            "trade_date": ["20260324", "20260325", "20260326", "20260327", "20260330", "20260331"],
            "close": [20.0, 21.0, 22.0, 23.0, 24.0, 25.0],
            "volume": [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            "total_turnover": [1000.0, 1000.0, 1000.0, 1000.0, 1000.0, 1000.0],
        }
    ).to_parquet(daily_data_dir / "00011.HK.parquet", index=False)

    pd.DataFrame(
        {
            "date": ["20260322"],
            "total": [100.0],
        }
    ).to_parquet(shares_data_dir / "00011.HK.parquet", index=False)

    pd.DataFrame(
        [
            {
                "symbol": "00011.HK",
                "order_book_id": "00011.XHKG",
                "status": "merged_patch",
                "max_date": "2026-03-31",
            }
        ]
    ).to_csv(asset_dir / "audit.csv", index=False)

    out_path = repo_root / "valuation_history_health_shares_near_ref.json"
    args = SimpleNamespace(
        asset_dir=str(asset_dir),
        symbols_file=None,
        by_date_file=None,
        field=["pe_ratio_ttm"],
        date_column=None,
        target_date="20260331",
        daily_asset_dir=str(daily_asset_dir),
        sample_limit=5,
        top_latest_dates=5,
        include_history=True,
        history_sample_limit=3,
        format="json",
        out=str(out_path),
    )

    assert rqdata_assets.inspect_hk_asset_health(args) == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    history = payload["history"]
    assert history["issues"] == [
        {
            "check": "valuation_stale_run_provider_like_any_date",
            "severity": "info",
            "affected_symbols": 1,
            "affected_rows": 6,
            "sample_rows": [
                {
                    "symbol": "00011.HK",
                    "start_date": "2026-03-24",
                    "end_date": "2026-03-31",
                    "run_length": 6,
                    "span_days": 7,
                    "stale_value": 20,
                    "reference_context": "shares_event_near_window",
                }
            ],
            "field": "pe_ratio_ttm",
            "stale_run_min_length": 5,
            "run_length_p50": 6,
            "run_length_p90": 6,
            "run_length_max": 6,
            "run_length_gt_3_symbols": 1,
            "run_length_gt_5_symbols": 1,
            "run_length_gt_10_symbols": 0,
        }
    ]


def test_inspect_hk_asset_health_include_history_downgrades_valuation_stale_runs_without_daily_trading_activity(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "valuation" / "valuation_history_demo"
    data_dir = asset_dir / "data"
    data_dir.mkdir(parents=True)
    daily_asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "daily_ref_demo"
    daily_data_dir = daily_asset_dir / "data"
    daily_data_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    (asset_dir / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "valuation",
                "query": {
                    "end_date": "20260331",
                    "fields": ["pe_ratio_ttm"],
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    pd.DataFrame(
        {
            "trade_date": ["20260324", "20260325", "20260326", "20260327", "20260330", "20260331"],
            "pe_ratio_ttm": [20.0, 20.0, 20.0, 20.0, 20.0, 20.0],
        }
    ).to_parquet(data_dir / "00011.HK.parquet", index=False)

    pd.DataFrame(
        {
            "trade_date": ["20260324", "20260325", "20260326", "20260327", "20260330", "20260331"],
            "close": [20.0, 21.0, 22.0, 23.0, 24.0, 25.0],
            "volume": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "total_turnover": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        }
    ).to_parquet(daily_data_dir / "00011.HK.parquet", index=False)

    pd.DataFrame(
        [
            {
                "symbol": "00011.HK",
                "order_book_id": "00011.XHKG",
                "status": "merged_patch",
                "max_date": "2026-03-31",
            }
        ]
    ).to_csv(asset_dir / "audit.csv", index=False)

    out_path = repo_root / "valuation_history_health_no_trading_ref.json"
    args = SimpleNamespace(
        asset_dir=str(asset_dir),
        symbols_file=None,
        by_date_file=None,
        field=["pe_ratio_ttm"],
        date_column=None,
        target_date="20260331",
        daily_asset_dir=str(daily_asset_dir),
        sample_limit=5,
        top_latest_dates=5,
        include_history=True,
        history_sample_limit=3,
        format="json",
        out=str(out_path),
    )

    assert rqdata_assets.inspect_hk_asset_health(args) == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    history = payload["history"]
    assert history["issues"] == [
        {
            "check": "valuation_stale_run_provider_like_any_date",
            "severity": "info",
            "affected_symbols": 1,
            "affected_rows": 6,
            "sample_rows": [
                {
                    "symbol": "00011.HK",
                    "start_date": "2026-03-24",
                    "end_date": "2026-03-31",
                    "run_length": 6,
                    "span_days": 7,
                    "stale_value": 20,
                    "reference_context": "no_daily_trading_activity",
                }
            ],
            "field": "pe_ratio_ttm",
            "stale_run_min_length": 5,
            "run_length_p50": 6,
            "run_length_p90": 6,
            "run_length_max": 6,
            "run_length_gt_3_symbols": 1,
            "run_length_gt_5_symbols": 1,
            "run_length_gt_10_symbols": 0,
        }
    ]


def test_assess_trainable_fill_dependence_marks_healthier_pit_only_route_green():
    assessment = rqdata_assets._assess_trainable_fill_dependence(
        trainable_estimate={
            "period_count_meeting_min_symbols_after_ffill": 6,
            "period_count_meeting_min_symbols_after_missing_fill": 8,
        },
        non_pit_features_ignored=[],
    )

    assert assessment["route_type"] == "pit_only"
    assert assessment["status"] == "green"
    assert assessment["retention_ratio_after_ffill"] == 0.75
    assert assessment["fill_dependency_ratio_from_missing_fill"] == 0.25
