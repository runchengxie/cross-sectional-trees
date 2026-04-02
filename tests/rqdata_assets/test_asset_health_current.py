import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import yaml

from csml import data_providers
from csml.data_tools import rqdata_assets


def test_inspect_hk_asset_health_reports_stale_symbols_and_ffill_candidates(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "valuation" / "valuation_demo"
    data_dir = asset_dir / "data"
    data_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    (asset_dir / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "valuation",
                "query": {
                    "start_date": "20260301",
                    "end_date": "20260331",
                    "fields": [
                        "hk_total_market_val",
                        "pe_ratio_ttm",
                        "pb_ratio_ttm",
                    ],
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
            "hk_total_market_val": [100.0, 101.0],
            "pe_ratio_ttm": [10.0, None],
            "pb_ratio_ttm": [1.0, None],
        }
    ).to_parquet(data_dir / "00005.HK.parquet", index=False)
    pd.DataFrame(
        {
            "trade_date": ["20260329", "20260331"],
            "hk_total_market_val": [200.0, 201.0],
            "pe_ratio_ttm": [20.0, 21.0],
            "pb_ratio_ttm": [None, None],
        }
    ).to_parquet(data_dir / "00011.HK.parquet", index=False)
    pd.DataFrame(
        {
            "trade_date": ["20260327"],
            "hk_total_market_val": [300.0],
            "pe_ratio_ttm": [30.0],
            "pb_ratio_ttm": [3.0],
        }
    ).to_parquet(data_dir / "00700.HK.parquet", index=False)

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
            {
                "symbol": "00700.HK",
                "order_book_id": "00700.XHKG",
                "status": "linked_base",
                "max_date": "2026-03-27",
            },
        ]
    ).to_csv(asset_dir / "audit.csv", index=False)

    out_path = repo_root / "asset_health.json"
    args = SimpleNamespace(
        asset_dir=str(asset_dir),
        field=[],
        date_column=None,
        target_date=None,
        sample_limit=5,
        top_latest_dates=5,
        format="json",
        out=str(out_path),
        fail_on_severity="none",
    )

    assert rqdata_assets.inspect_hk_asset_health(args) == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    summary = payload["summary"]
    assert summary["dataset"] == "valuation"
    assert summary["target_date"] == "2026-03-31"
    assert summary["target_date_source"] == "audit_latest_date"
    assert summary["selection_source"] == "default_valuation_fields"
    assert summary["selected_fields"] == [
        "hk_total_market_val",
        "pe_ratio_ttm",
        "pb_ratio_ttm",
    ]
    assert summary["manifest_query_date"] == "2026-03-31"
    assert summary["symbols_scanned"] == 3
    assert summary["symbols_with_target_date_row"] == 2
    assert summary["symbols_without_target_date_row"] == 1
    assert summary["target_date_coverage_pct"] == 66.67
    assert summary["latest_date_min"] == "2026-03-27"
    assert summary["latest_date_max"] == "2026-03-31"
    assert summary["audit_status_counts"] == {"linked_base": 1, "merged_patch": 2}

    assert payload["latest_date_distribution"] == [
        {"latest_date": "2026-03-31", "symbols": 2},
        {"latest_date": "2026-03-27", "symbols": 1},
    ]
    assert payload["sample_stale_symbols"] == [
        {
            "symbol": "00700.HK",
            "latest_date": "2026-03-27",
            "status": "linked_base",
        }
    ]

    field_map = {item["field"]: item for item in payload["field_coverage"]}
    assert field_map["hk_total_market_val"]["nonnull_on_target_date"] == 2
    assert field_map["hk_total_market_val"]["clean_nonmissing_on_target_date"] == 2
    assert field_map["hk_total_market_val"]["missing_on_target_date"] == 0
    assert field_map["pe_ratio_ttm"]["nonnull_on_target_date"] == 1
    assert field_map["pe_ratio_ttm"]["clean_nonmissing_on_target_date"] == 1
    assert field_map["pe_ratio_ttm"]["missing_on_target_date"] == 1
    assert field_map["pe_ratio_ttm"]["missing_but_prior_nonnull"] == 1
    assert field_map["pe_ratio_ttm"]["missing_and_never_nonnull"] == 0
    assert field_map["pe_ratio_ttm"]["unusable_but_prior_clean"] == 1
    assert field_map["pe_ratio_ttm"]["ffill_age_days_max"] == 1
    assert field_map["pe_ratio_ttm"]["sample_oldest_ffill_symbols"] == [
        {
            "symbol": "00005.HK",
            "last_nonnull_date": "2026-03-30",
            "age_days": 1,
        }
    ]
    assert field_map["pe_ratio_ttm"]["sample_missing_symbols"] == ["00005.HK"]
    assert field_map["pe_ratio_ttm"]["sample_prior_nonnull_symbols"] == ["00005.HK"]
    assert field_map["pb_ratio_ttm"]["nonnull_on_target_date"] == 0
    assert field_map["pb_ratio_ttm"]["clean_nonmissing_on_target_date"] == 0
    assert field_map["pb_ratio_ttm"]["missing_on_target_date"] == 2
    assert field_map["pb_ratio_ttm"]["missing_but_prior_nonnull"] == 1
    assert field_map["pb_ratio_ttm"]["missing_and_never_nonnull"] == 1
    assert field_map["pb_ratio_ttm"]["unusable_but_prior_clean"] == 1
    assert field_map["pb_ratio_ttm"]["ffill_age_days_max"] == 1
    assert field_map["pb_ratio_ttm"]["sample_missing_symbols"] == ["00005.HK", "00011.HK"]
    assert field_map["pb_ratio_ttm"]["sample_prior_nonnull_symbols"] == ["00005.HK"]
    assert payload["quality_checks"] == [
        {
            "check": "field_all_clean_missing_on_target_date",
            "field": "pb_ratio_ttm",
            "severity": "error",
            "affected_symbols": 2,
            "affected_pct": 100.0,
            "sample_symbols": ["00005.HK", "00011.HK"],
        }
    ]
    assert payload["quality_verdict"] == {
        "color": "red",
        "overall_severity": "error",
        "issue_count": 1,
        "severity_counts": {
            "error": 1,
            "warning": 0,
            "info": 0,
        },
        "fail_on_severity": "none",
        "gate_triggered": False,
        "gate_status": "pass",
        "failing_issue_count": 0,
        "sample_failing_checks": [],
        "message": "1 quality issue(s) detected, including at least one error.",
    }

def test_inspect_hk_asset_health_supports_symbol_filters_and_extended_sanity_checks(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "custom" / "custom_demo"
    data_dir = asset_dir / "data"
    data_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    (asset_dir / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "custom",
                "query": {
                    "end_date": "20260331",
                    "fields": ["metric_num", "metric_text"],
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    pd.DataFrame(
        {
            "trade_date": ["20260328", "20260331"],
            "metric_num": [5.0, None],
            "metric_text": ["ok", "N/A"],
        }
    ).to_parquet(data_dir / "00005.HK.parquet", index=False)
    pd.DataFrame(
        {
            "trade_date": ["20260331"],
            "metric_num": [0.0],
            "metric_text": ["ok"],
        }
    ).to_parquet(data_dir / "00011.HK.parquet", index=False)
    pd.DataFrame(
        {
            "trade_date": ["20260331"],
            "metric_num": [float("inf")],
            "metric_text": ["--"],
        }
    ).to_parquet(data_dir / "00700.HK.parquet", index=False)
    pd.DataFrame(
        {
            "trade_date": ["20260331"],
            "metric_num": [99.0],
            "metric_text": ["ok"],
        }
    ).to_parquet(data_dir / "00941.HK.parquet", index=False)

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
            {
                "symbol": "00700.HK",
                "order_book_id": "00700.XHKG",
                "status": "merged_patch",
                "max_date": "2026-03-31",
            },
            {
                "symbol": "00941.HK",
                "order_book_id": "00941.XHKG",
                "status": "merged_patch",
                "max_date": "2026-03-31",
            },
        ]
    ).to_csv(asset_dir / "audit.csv", index=False)

    symbols_file = repo_root / "symbols.txt"
    symbols_file.write_text("00011.HK\n", encoding="utf-8")

    by_date_file = repo_root / "universe_by_date.csv"
    pd.DataFrame(
        {
            "trade_date": ["20260331", "20260331", "20260330"],
            "symbol": ["00005.HK", "00700.HK", "00941.HK"],
            "selected": [1, "yes", 1],
        }
    ).to_csv(by_date_file, index=False)

    out_path = repo_root / "filtered_asset_health.json"
    args = SimpleNamespace(
        asset_dir=str(asset_dir),
        symbols_file=str(symbols_file),
        by_date_file=str(by_date_file),
        field=["metric_num", "metric_text"],
        date_column=None,
        target_date="20260331",
        sample_limit=5,
        top_latest_dates=5,
        format="json",
        out=str(out_path),
        fail_on_severity="none",
    )

    assert rqdata_assets.inspect_hk_asset_health(args) == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    summary = payload["summary"]
    assert summary["symbol_filter_source"] == "symbols_file+by_date_file_target_date"
    assert summary["symbols_scanned"] == 3
    assert summary["symbols_available_in_asset_dir"] == 4
    assert summary["symbols_missing_asset_file"] == 0
    assert summary["symbols_with_target_date_row"] == 3
    assert summary["symbols_without_target_date_row"] == 0
    assert payload["latest_date_distribution"] == [{"latest_date": "2026-03-31", "symbols": 3}]

    field_map = {item["field"]: item for item in payload["field_coverage"]}

    metric_num = field_map["metric_num"]
    assert metric_num["nonnull_on_target_date"] == 2
    assert metric_num["clean_nonmissing_on_target_date"] == 1
    assert metric_num["missing_on_target_date"] == 1
    assert metric_num["placeholder_on_target_date"] == 0
    assert metric_num["nonfinite_on_target_date"] == 1
    assert metric_num["zero_on_target_date"] == 1
    assert metric_num["unusable_but_prior_clean"] == 1
    assert metric_num["ffill_age_days_min"] == 3
    assert metric_num["ffill_age_days_p50"] == 3
    assert metric_num["ffill_age_days_p90"] == 3
    assert metric_num["ffill_age_days_max"] == 3
    assert metric_num["unique_clean_values_on_target_date"] == 1
    assert metric_num["most_common_clean_value_on_target_date"] == 0
    assert metric_num["most_common_clean_value_symbols"] == 1
    assert metric_num["most_common_clean_value_pct_of_clean_nonmissing"] == 100.0
    assert metric_num["is_constant_across_clean_values_on_target_date"] is True
    assert metric_num["sample_nonfinite_symbols"] == ["00700.HK"]
    assert metric_num["sample_zero_symbols"] == ["00011.HK"]
    assert metric_num["sample_oldest_ffill_symbols"] == [
        {
            "symbol": "00005.HK",
            "last_nonnull_date": "2026-03-28",
            "age_days": 3,
        }
    ]

    metric_text = field_map["metric_text"]
    assert metric_text["nonnull_on_target_date"] == 3
    assert metric_text["clean_nonmissing_on_target_date"] == 1
    assert metric_text["missing_on_target_date"] == 0
    assert metric_text["placeholder_on_target_date"] == 2
    assert metric_text["nonfinite_on_target_date"] == 0
    assert metric_text["zero_on_target_date"] == 0
    assert metric_text["unusable_but_prior_clean"] == 1
    assert metric_text["ffill_age_days_max"] == 3
    assert metric_text["unique_clean_values_on_target_date"] == 1
    assert metric_text["most_common_clean_value_on_target_date"] == "ok"
    assert metric_text["most_common_clean_value_symbols"] == 1
    assert metric_text["is_constant_across_clean_values_on_target_date"] is True
    assert metric_text["sample_placeholder_symbols"] == ["00005.HK", "00700.HK"]
    assert metric_text["sample_oldest_ffill_symbols"] == [
        {
            "symbol": "00005.HK",
            "last_nonnull_date": "2026-03-28",
            "age_days": 3,
        }
    ]

    checks = {(item["check"], item.get("field")): item for item in payload["quality_checks"]}
    assert checks[("field_nonfinite_values_on_target_date", "metric_num")] == {
        "check": "field_nonfinite_values_on_target_date",
        "field": "metric_num",
        "severity": "error",
        "affected_symbols": 1,
        "affected_pct": 33.33,
        "sample_symbols": ["00700.HK"],
    }
    assert checks[("field_all_clean_values_zero_on_target_date", "metric_num")] == {
        "check": "field_all_clean_values_zero_on_target_date",
        "field": "metric_num",
        "severity": "warning",
        "affected_symbols": 1,
        "affected_pct": 100.0,
        "sample_symbols": ["00011.HK"],
    }
    assert checks[("field_placeholder_values_on_target_date", "metric_text")] == {
        "check": "field_placeholder_values_on_target_date",
        "field": "metric_text",
        "severity": "warning",
        "affected_symbols": 2,
        "affected_pct": 66.67,
        "sample_symbols": ["00005.HK", "00700.HK"],
    }
    assert checks[("field_ffill_age_gt_1d", "metric_num")] == {
        "check": "field_ffill_age_gt_1d",
        "field": "metric_num",
        "severity": "info",
        "affected_symbols": 1,
        "affected_pct": 50.0,
        "sample_symbols": ["00005.HK"],
    }
    assert checks[("field_ffill_age_gt_1d", "metric_text")] == {
        "check": "field_ffill_age_gt_1d",
        "field": "metric_text",
        "severity": "info",
        "affected_symbols": 1,
        "affected_pct": 50.0,
        "sample_symbols": ["00005.HK"],
    }
    assert payload["quality_verdict"] == {
        "color": "red",
        "overall_severity": "error",
        "issue_count": 5,
        "severity_counts": {
            "error": 1,
            "warning": 2,
            "info": 2,
        },
        "fail_on_severity": "none",
        "gate_triggered": False,
        "gate_status": "pass",
        "failing_issue_count": 0,
        "sample_failing_checks": [],
        "message": "5 quality issue(s) detected, including at least one error.",
    }

    fail_out_path = repo_root / "filtered_asset_health_fail_warning.json"
    fail_args = SimpleNamespace(
        asset_dir=str(asset_dir),
        symbols_file=str(symbols_file),
        by_date_file=str(by_date_file),
        field=["metric_num", "metric_text"],
        date_column=None,
        target_date="20260331",
        sample_limit=5,
        top_latest_dates=5,
        format="json",
        out=str(fail_out_path),
        fail_on_severity="warning",
    )
    assert rqdata_assets.inspect_hk_asset_health(fail_args) == 2

def test_inspect_hk_asset_health_flags_daily_price_rule_violations(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "daily_bad_demo"
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
            "trade_date": ["20260331"],
            "open": [10.0],
            "high": [9.0],
            "low": [11.0],
            "close": [-1.0],
            "volume": [-100.0],
            "total_turnover": [-200.0],
        }
    ).to_parquet(data_dir / "00005.HK.parquet", index=False)

    pd.DataFrame(
        [
            {
                "symbol": "00005.HK",
                "order_book_id": "00005.XHKG",
                "status": "merged_patch",
                "max_trade_date": "20260331",
            }
        ]
    ).to_csv(asset_dir / "audit.csv", index=False)

    out_path = repo_root / "daily_bad_health.json"
    args = SimpleNamespace(
        asset_dir=str(asset_dir),
        symbols_file=None,
        by_date_file=None,
        field=[],
        date_column=None,
        target_date="20260331",
        sample_limit=5,
        top_latest_dates=5,
        format="json",
        out=str(out_path),
    )

    assert rqdata_assets.inspect_hk_asset_health(args) == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    checks = {(item["check"], item.get("field")): item for item in payload["quality_checks"]}
    assert checks[("daily_price_bounds_violation", None)] == {
        "check": "daily_price_bounds_violation",
        "field": None,
        "severity": "error",
        "affected_symbols": 1,
        "affected_pct": 100.0,
        "sample_symbols": ["00005.HK"],
    }
    assert checks[("daily_nonpositive_price", None)] == {
        "check": "daily_nonpositive_price",
        "field": None,
        "severity": "error",
        "affected_symbols": 1,
        "affected_pct": 100.0,
        "sample_symbols": ["00005.HK"],
    }
    assert checks[("daily_negative_volume", None)] == {
        "check": "daily_negative_volume",
        "field": None,
        "severity": "error",
        "affected_symbols": 1,
        "affected_pct": 100.0,
        "sample_symbols": ["00005.HK"],
    }
    assert checks[("daily_negative_total_turnover", None)] == {
        "check": "daily_negative_total_turnover",
        "field": None,
        "severity": "error",
        "affected_symbols": 1,
        "affected_pct": 100.0,
        "sample_symbols": ["00005.HK"],
    }

def test_inspect_hk_asset_health_flags_duplicate_dates_and_dedupes_target_day(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "custom" / "duplicate_demo"
    data_dir = asset_dir / "data"
    data_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    (asset_dir / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "custom",
                "query": {
                    "end_date": "20260331",
                    "fields": ["metric_text"],
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    pd.DataFrame(
        {
            "trade_date": ["20260330", "20260331", "20260331"],
            "metric_text": ["ok", "N/A", "good"],
        }
    ).to_parquet(data_dir / "00005.HK.parquet", index=False)
    pd.DataFrame(
        {
            "trade_date": ["20260331"],
            "metric_text": ["fine"],
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

    out_path = repo_root / "duplicate_asset_health.json"
    args = SimpleNamespace(
        asset_dir=str(asset_dir),
        symbols_file=None,
        by_date_file=None,
        field=["metric_text"],
        date_column=None,
        target_date="20260331",
        sample_limit=5,
        top_latest_dates=5,
        format="json",
        out=str(out_path),
    )

    assert rqdata_assets.inspect_hk_asset_health(args) == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    summary = payload["summary"]
    assert summary["symbols_with_duplicate_dates"] == 1
    assert summary["duplicate_date_groups"] == 1
    assert summary["duplicate_date_rows"] == 2

    field_map = {item["field"]: item for item in payload["field_coverage"]}
    metric_text = field_map["metric_text"]
    assert metric_text["clean_nonmissing_on_target_date"] == 2
    assert metric_text["placeholder_on_target_date"] == 0
    assert metric_text["sample_placeholder_symbols"] == []

    checks = {(item["check"], item.get("field")): item for item in payload["quality_checks"]}
    assert checks[("symbol_duplicate_dates_in_asset_file", None)] == {
        "check": "symbol_duplicate_dates_in_asset_file",
        "field": None,
        "severity": "error",
        "affected_symbols": 1,
        "affected_pct": 50.0,
        "duplicate_date_groups": 1,
        "duplicate_rows": 2,
        "sample_symbols": ["00005.HK"],
    }

def test_inspect_hk_asset_health_parses_compact_audit_dates_written_as_floats(tmp_path, monkeypatch):
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
                    "fields": ["open", "high", "low", "close", "volume", "total_turnover"],
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    base_rows = {
        "open": [10.0, 11.0],
        "high": [10.5, 11.5],
        "low": [9.5, 10.5],
        "close": [10.2, 11.2],
        "volume": [1000, 1100],
        "total_turnover": [10000.0, 11000.0],
    }
    pd.DataFrame({"trade_date": ["20260330", "20260331"], **base_rows}).to_parquet(
        data_dir / "00005.HK.parquet",
        index=False,
    )
    pd.DataFrame({"trade_date": ["20260328", "20260331"], **base_rows}).to_parquet(
        data_dir / "00011.HK.parquet",
        index=False,
    )
    pd.DataFrame(
        {
            "trade_date": ["20260327"],
            "open": [30.0],
            "high": [31.0],
            "low": [29.0],
            "close": [30.5],
            "volume": [900],
            "total_turnover": [9000.0],
        }
    ).to_parquet(data_dir / "00700.HK.parquet", index=False)

    pd.DataFrame(
        [
            {
                "symbol": "00005.HK",
                "order_book_id": "00005.XHKG",
                "status": "merged_patch",
                "max_trade_date": 20260331.0,
            },
            {
                "symbol": "00011.HK",
                "order_book_id": "00011.XHKG",
                "status": "merged_patch",
                "max_trade_date": 20260331.0,
            },
            {
                "symbol": "00700.HK",
                "order_book_id": "00700.XHKG",
                "status": "linked_base",
                "max_trade_date": 20260327.0,
            },
        ]
    ).to_csv(asset_dir / "audit.csv", index=False)

    out_path = repo_root / "daily_asset_health.json"
    args = SimpleNamespace(
        asset_dir=str(asset_dir),
        field=[],
        date_column=None,
        target_date="20260331",
        sample_limit=5,
        top_latest_dates=5,
        format="json",
        out=str(out_path),
    )

    assert rqdata_assets.inspect_hk_asset_health(args) == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["selected_fields"] == [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "total_turnover",
    ]
    assert payload["latest_date_distribution"] == [
        {"latest_date": "2026-03-31", "symbols": 2},
        {"latest_date": "2026-03-27", "symbols": 1},
    ]
    assert payload["sample_stale_symbols"] == [
        {
            "symbol": "00700.HK",
            "latest_date": "2026-03-27",
            "status": "linked_base",
        }
    ]

def test_inspect_hk_asset_health_reports_missing_asset_file_details_and_audit_issue_groups(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "valuation" / "valuation_missing_demo"
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
            "trade_date": ["20260331"],
            "pe_ratio_ttm": [10.0],
        }
    ).to_parquet(data_dir / "00005.HK.parquet", index=False)

    pd.DataFrame(
        [
            {
                "symbol": "00005.HK",
                "order_book_id": "00005.XHKG",
                "status": "merged_patch",
                "max_date": "2026-03-31",
                "error": None,
            },
            {
                "symbol": "00011.HK",
                "order_book_id": "00011.XHKG",
                "status": "failed",
                "max_date": None,
                "error": "no permission to access day bar",
            },
            {
                "symbol": "00700.HK",
                "order_book_id": "00700.XHKG",
                "status": "failed",
                "max_date": None,
                "error": "no permission to access day bar",
            },
        ]
    ).to_csv(asset_dir / "audit.csv", index=False)

    symbols_file = repo_root / "symbols.txt"
    symbols_file.write_text("00005.HK\n00011.HK\n00700.HK\n", encoding="utf-8")

    out_path = repo_root / "valuation_missing_health.json"
    args = SimpleNamespace(
        asset_dir=str(asset_dir),
        symbols_file=str(symbols_file),
        by_date_file=None,
        field=["pe_ratio_ttm"],
        date_column=None,
        target_date="20260331",
        sample_limit=5,
        top_latest_dates=5,
        include_history=False,
        history_sample_limit=5,
        format="json",
        out=str(out_path),
    )

    assert rqdata_assets.inspect_hk_asset_health(args) == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["symbols_scanned"] == 3
    assert payload["summary"]["symbols_missing_asset_file"] == 2
    assert payload["summary"]["audit_status_counts"] == {"failed": 2, "merged_patch": 1}
    assert payload["sample_missing_asset_file_details"] == [
        {
            "symbol": "00011.HK",
            "status": "failed",
            "error": "no permission to access day bar",
        },
        {
            "symbol": "00700.HK",
            "status": "failed",
            "error": "no permission to access day bar",
        },
    ]
    assert payload["audit_issue_groups"] == [
        {
            "status": "failed",
            "issue_category": "no_permission_day_bar",
            "error": "no permission to access day bar",
            "affected_symbols": 2,
            "sample_symbols": ["00011.HK", "00700.HK"],
        }
    ]
