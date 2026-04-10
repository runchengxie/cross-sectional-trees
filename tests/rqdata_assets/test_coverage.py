import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import yaml

from csml import data_providers
from csml.data_tools import rqdata_assets


def test_inspect_hk_pit_coverage_supports_config_selected_derived_features(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "pit_financials" / "pit_demo"
    asset_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    (asset_dir / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "pit_financials",
                "query": {
                    "fields": [
                        "revenue",
                        "net_profit",
                        "total_assets",
                        "total_liabilities",
                        "cash_flow_from_operating_activities",
                        "accounts_receivable",
                    ]
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    fundamentals_path = asset_dir / "pipeline_fundamentals.parquet"
    pd.DataFrame(
        {
            "trade_date": ["20250320", "20250320", "20250820", "20250820"],
            "symbol": ["00005.HK", "00011.HK", "00005.HK", "00011.HK"],
            "revenue": [100.0, 200.0, 120.0, None],
            "net_profit": [10.0, 20.0, 12.0, 5.0],
            "total_assets": [1000.0, 2000.0, 1100.0, 2100.0],
            "total_liabilities": [500.0, 1000.0, 520.0, 1050.0],
            "cash_flow_from_operating_activities": [8.0, 16.0, 9.0, None],
            "accounts_receivable": [5.0, None, 6.0, 7.0],
        }
    ).to_parquet(fundamentals_path, index=False)

    (asset_dir / "pipeline_fundamentals.manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "pit_fundamentals_file",
                "source_asset_dir": str(asset_dir),
                "totals": {
                    "input_rows": 10,
                    "output_rows": 4,
                    "symbols": 2,
                    "dropped_all_missing_fields": 6,
                    "duplicate_rows_seen": 0,
                    "duplicate_rows_dropped": 0,
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    config_path = repo_root / "config" / "pit_inspect.yml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        yaml.safe_dump(
            {
                "fundamentals": {
                    "enabled": True,
                    "source": "file",
                    "file": str(fundamentals_path),
                    "features": [
                        "revenue",
                        "net_profit",
                        "profit_margin",
                        "asset_turnover",
                        "receivables_to_revenue",
                    ],
                },
                "universe": {"min_symbols_per_date": 2},
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    out_path = repo_root / "coverage.json"
    args = SimpleNamespace(
        config=str(config_path),
        asset_dir=None,
        fundamentals_file=None,
        field_profile=[],
        field=[],
        fields_file=[],
        min_symbols=None,
        top=10,
        quarter_limit=12,
        format="json",
        out=str(out_path),
        fail_on_severity="none",
    )

    assert rqdata_assets.inspect_hk_pit_coverage(args) == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["selection"]["source"] == "config.fundamentals.features"
    assert payload["selection"]["selected_features"] == [
        "revenue",
        "net_profit",
        "profit_margin",
        "asset_turnover",
        "receivables_to_revenue",
    ]
    assert payload["complete_case"]["complete_rows"] == 2
    assert payload["complete_case"]["quarter_count_meeting_min_symbols"] == 0
    assert payload["pipeline_manifest_totals"]["dropped_all_missing_fields"] == 6

    field_map = {item["feature"]: item for item in payload["field_coverage"]}
    assert field_map["profit_margin"]["nonnull_rows"] == 3
    assert field_map["asset_turnover"]["nonnull_rows"] == 3
    assert field_map["receivables_to_revenue"]["nonnull_rows"] == 2

    assert payload["quarter_coverage"] == [
        {
            "quarter": "2025Q1",
            "symbols_in_file": 2,
            "symbols_with_any_selected_feature": 2,
            "symbols_with_all_selected_features": 1,
        },
        {
            "quarter": "2025Q3",
            "symbols_in_file": 2,
            "symbols_with_any_selected_feature": 2,
            "symbols_with_all_selected_features": 1,
        },
    ]

def test_inspect_hk_pit_coverage_trainable_mode_estimates_fill_recovered_sample(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "pit_financials" / "pit_demo"
    asset_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    fundamentals_path = asset_dir / "pipeline_fundamentals.parquet"
    pd.DataFrame(
        {
            "trade_date": ["20250320", "20250820", "20250820"],
            "symbol": ["00005.HK", "00005.HK", "00011.HK"],
            "revenue": [100.0, 120.0, None],
            "net_profit": [10.0, 12.0, 5.0],
        }
    ).to_parquet(fundamentals_path, index=False)

    (asset_dir / "pipeline_fundamentals.manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "pit_fundamentals_file",
                "source_asset_dir": str(asset_dir),
                "totals": {
                    "input_rows": 3,
                    "output_rows": 3,
                    "symbols": 2,
                    "dropped_all_missing_fields": 0,
                    "duplicate_rows_seen": 0,
                    "duplicate_rows_dropped": 0,
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    universe_by_date = repo_root / "artifacts" / "assets" / "universe" / "pit_demo_by_date.csv"
    universe_by_date.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "trade_date": ["20250331", "20250930", "20250930"],
            "symbol": ["00005.HK", "00005.HK", "00011.HK"],
        }
    ).to_csv(universe_by_date, index=False)

    config_path = repo_root / "config" / "pit_trainable.yml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        yaml.safe_dump(
            {
                "fundamentals": {
                    "enabled": True,
                    "source": "file",
                    "file": str(fundamentals_path),
                    "features": ["revenue", "net_profit"],
                    "auto_add_features": False,
                    "ffill": True,
                },
                "features": {
                    "list": ["ret_60", "revenue", "net_profit", "profit_margin"],
                    "missing": {
                        "method": "cross_sectional_median",
                        "features": ["revenue", "profit_margin"],
                        "add_indicators": True,
                    },
                },
                "label": {"rebalance_frequency": "Q"},
                "eval": {
                    "rebalance_frequency": "Q",
                    "sample_on_rebalance_dates": True,
                },
                "universe": {
                    "min_symbols_per_date": 2,
                    "by_date_file": str(universe_by_date),
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    out_path = repo_root / "coverage_trainable.json"
    args = SimpleNamespace(
        config=str(config_path),
        asset_dir=None,
        fundamentals_file=None,
        field_profile=[],
        field=[],
        fields_file=[],
        mode="trainable",
        min_symbols=None,
        top=10,
        quarter_limit=12,
        format="json",
        out=str(out_path),
    )

    assert rqdata_assets.inspect_hk_pit_coverage(args) == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["selection"]["mode"] == "trainable"
    assert payload["selection"]["source"] == "config.features.list"
    assert payload["selection"]["selected_features"] == [
        "revenue",
        "net_profit",
        "profit_margin",
    ]
    assert payload["selection"]["ignored_features"] == ["ret_60"]

    trainable = payload["trainable_estimate"]
    assert trainable["feature_source"] == "config.features.list"
    assert trainable["missing_method"] == "cross_sectional_median"
    assert trainable["non_pit_features_ignored"] == ["ret_60"]
    assert trainable["period_count_meeting_min_symbols_after_ffill"] == 0
    assert trainable["period_count_meeting_min_symbols_after_missing_fill"] == 1
    fill_dependence = payload["fill_dependence_assessment"]
    assert fill_dependence["route_type"] == "hybrid"
    assert fill_dependence["status"] == "red"
    assert fill_dependence["retention_ratio_after_ffill"] == 0.0
    assert fill_dependence["fill_dependency_ratio_from_missing_fill"] == 1.0

    assert payload["trainable_period_coverage"] == [
        {
            "period": "2025Q1",
            "active_symbols": 1,
            "symbols_with_any_selected_features_after_ffill": 1,
            "symbols_with_all_selected_features_after_ffill": 1,
            "symbols_with_all_selected_features_after_missing_fill": 1,
        },
        {
            "period": "2025Q3",
            "active_symbols": 2,
            "symbols_with_any_selected_features_after_ffill": 2,
            "symbols_with_all_selected_features_after_ffill": 1,
            "symbols_with_all_selected_features_after_missing_fill": 2,
        },
    ]

def test_inspect_hk_pit_coverage_include_health_reports_target_date_staleness(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "pit_financials" / "pit_demo"
    asset_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    fundamentals_path = asset_dir / "pipeline_fundamentals.parquet"
    pd.DataFrame(
        {
            "trade_date": ["20250320", "20250320", "20250628", "20250628", "20250929"],
            "symbol": ["00005.HK", "00011.HK", "00005.HK", "00011.HK", "00005.HK"],
            "revenue": [100.0, 200.0, 110.0, None, 120.0],
            "net_profit": [10.0, 20.0, 11.0, 21.0, 12.0],
        }
    ).to_parquet(fundamentals_path, index=False)

    universe_by_date = repo_root / "artifacts" / "assets" / "universe" / "pit_health_by_date.csv"
    universe_by_date.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "trade_date": ["20250930", "20250930", "20250930"],
            "symbol": ["00005.HK", "00011.HK", "00700.HK"],
            "selected": [1, 1, 1],
        }
    ).to_csv(universe_by_date, index=False)

    config_path = repo_root / "config" / "pit_health.yml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        yaml.safe_dump(
            {
                "fundamentals": {
                    "enabled": True,
                    "source": "file",
                    "file": str(fundamentals_path),
                    "features": ["revenue", "net_profit"],
                },
                "universe": {
                    "min_symbols_per_date": 2,
                    "by_date_file": str(universe_by_date),
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    out_path = repo_root / "coverage_with_health.json"
    args = SimpleNamespace(
        config=str(config_path),
        asset_dir=None,
        fundamentals_file=None,
        field_profile=[],
        field=[],
        fields_file=[],
        mode="both",
        include_health=True,
        target_date="20250930",
        symbols_file=None,
        by_date_file=None,
        health_sample_limit=3,
        min_symbols=None,
        top=10,
        quarter_limit=12,
        format="json",
        out=str(out_path),
    )

    assert rqdata_assets.inspect_hk_pit_coverage(args) == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    health = payload["health"]
    assert health["source"] == {
        "target_date": "2025-09-30",
        "target_date_source": "explicit",
        "symbol_filter_source": "config_universe_by_date_target_date",
        "symbols_file": None,
        "by_date_file": str(universe_by_date),
    }

    summary = health["summary"]
    assert summary["symbols_scanned"] == 3
    assert summary["symbols_available_in_fundamentals"] == 2
    assert summary["symbols_missing_in_fundamentals"] == 1
    assert summary["symbols_with_any_row_before_target_date"] == 2
    assert summary["symbols_without_any_row_before_target_date"] == 1
    assert summary["symbols_with_any_selected_features_asof_target_date"] == 2
    assert summary["symbols_with_all_selected_features_asof_target_date"] == 2
    assert summary["all_selected_features_coverage_pct"] == 66.67
    assert summary["latest_report_age_days_max"] == 94
    assert summary["latest_report_age_gt_90d_symbols"] == 1
    assert summary["latest_report_age_gt_180d_symbols"] == 0
    assert summary["complete_symbol_oldest_feature_age_days_max"] == 194
    assert summary["complete_symbol_oldest_feature_age_gt_90d_symbols"] == 1
    assert summary["complete_symbol_oldest_feature_age_gt_180d_symbols"] == 1
    assert summary["rows_last_30d"] == 1
    assert summary["symbols_updated_last_30d"] == 1
    assert summary["rows_last_90d"] == 1
    assert summary["symbols_updated_last_90d"] == 1
    assert summary["rows_last_180d"] == 3
    assert summary["symbols_updated_last_180d"] == 2

    assert health["sample_symbols_without_rows"] == ["00700.HK"]
    assert health["sample_missing_asset_symbols"] == ["00700.HK"]
    assert health["recent_disclosures"] == [
        {"trade_date": "2025-03-20", "rows": 2, "symbols": 2},
        {"trade_date": "2025-06-28", "rows": 2, "symbols": 2},
        {"trade_date": "2025-09-29", "rows": 1, "symbols": 1},
    ]

    feature_map = {item["feature"]: item for item in health["feature_health"]}
    assert feature_map["revenue"]["symbols_with_clean_value_asof_target_date"] == 2
    assert feature_map["revenue"]["coverage_pct"] == 66.67
    assert feature_map["revenue"]["missing_symbols_asof_target_date"] == 1
    assert feature_map["revenue"]["age_days_max"] == 194
    assert feature_map["revenue"]["age_gt_90d_symbols"] == 1
    assert feature_map["revenue"]["age_gt_180d_symbols"] == 1
    assert feature_map["revenue"]["sample_oldest_symbols"] == [
        {"symbol": "00011.HK", "last_observed_date": "2025-03-20", "age_days": 194},
        {"symbol": "00005.HK", "last_observed_date": "2025-09-29", "age_days": 1},
    ]
    assert feature_map["revenue"]["sample_missing_symbols"] == ["00700.HK"]

    assert feature_map["net_profit"]["symbols_with_clean_value_asof_target_date"] == 2
    assert feature_map["net_profit"]["coverage_pct"] == 66.67
    assert feature_map["net_profit"]["missing_symbols_asof_target_date"] == 1
    assert feature_map["net_profit"]["age_days_max"] == 94
    assert feature_map["net_profit"]["age_gt_90d_symbols"] == 1
    assert feature_map["net_profit"]["age_gt_180d_symbols"] == 0

    checks = {(item["check"], item.get("field")): item for item in health["quality_checks"]}
    assert checks[("feature_stale_gt_180d_asof_target_date", "revenue")] == {
        "check": "feature_stale_gt_180d_asof_target_date",
        "field": "revenue",
        "severity": "info",
        "affected_symbols": 1,
        "affected_pct": 50.0,
        "sample_symbols": ["00011.HK"],
    }
    assert checks[("symbol_without_any_pit_row_before_target_date", None)] == {
        "check": "symbol_without_any_pit_row_before_target_date",
        "field": None,
        "severity": "error",
        "affected_symbols": 1,
        "affected_pct": 33.33,
        "sample_symbols": ["00700.HK"],
    }
    assert health["quality_verdict"] == {
        "color": "red",
        "overall_severity": "error",
        "issue_count": 2,
        "severity_counts": {
            "error": 1,
            "warning": 0,
            "info": 1,
        },
        "fail_on_severity": "none",
        "gate_triggered": False,
        "gate_status": "pass",
        "failing_issue_count": 0,
        "sample_failing_checks": [],
        "message": "2 quality issue(s) detected, including at least one error.",
    }
    assert payload["quality_verdict"] == health["quality_verdict"]

def test_inspect_hk_pit_coverage_fail_on_severity_auto_enables_health(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "pit_financials" / "pit_demo"
    asset_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    fundamentals_path = asset_dir / "pipeline_fundamentals.parquet"
    pd.DataFrame(
        {
            "trade_date": ["20250320", "20250320", "20250628"],
            "symbol": ["00005.HK", "00011.HK", "00005.HK"],
            "revenue": [100.0, 200.0, 110.0],
        }
    ).to_parquet(fundamentals_path, index=False)

    by_date_file = repo_root / "artifacts" / "assets" / "universe" / "pit_gate_by_date.csv"
    by_date_file.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "trade_date": ["20250930", "20250930"],
            "symbol": ["00005.HK", "00700.HK"],
            "selected": [1, 1],
        }
    ).to_csv(by_date_file, index=False)

    out_path = repo_root / "pit_gate.json"
    args = SimpleNamespace(
        config=None,
        asset_dir=str(asset_dir),
        fundamentals_file=None,
        field_profile=[],
        field=["revenue"],
        fields_file=[],
        mode="strict",
        include_health=False,
        target_date="20250930",
        symbols_file=None,
        by_date_file=str(by_date_file),
        health_sample_limit=3,
        min_symbols=2,
        top=10,
        quarter_limit=12,
        format="json",
        out=str(out_path),
        fail_on_severity="warning",
    )

    assert rqdata_assets.inspect_hk_pit_coverage(args) == 2

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["health"] is not None
    assert payload["quality_verdict"]["fail_on_severity"] == "warning"
    assert payload["quality_verdict"]["gate_triggered"] is True
    assert payload["quality_verdict"]["gate_status"] == "fail"
    assert payload["quality_verdict"]["sample_failing_checks"] == [
        "symbol_without_any_pit_row_before_target_date",
        "selected_feature_set_below_min_symbols_asof_target_date",
    ]

def test_inspect_hk_pit_coverage_marks_gt_365d_as_warning(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "pit_financials" / "pit_demo"
    asset_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    fundamentals_path = asset_dir / "pipeline_fundamentals.parquet"
    pd.DataFrame(
        {
            "trade_date": ["20240320", "20250929"],
            "symbol": ["00011.HK", "00005.HK"],
            "revenue": [200.0, 100.0],
        }
    ).to_parquet(fundamentals_path, index=False)

    by_date_file = repo_root / "artifacts" / "assets" / "universe" / "pit_gt365_by_date.csv"
    by_date_file.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "trade_date": ["20250930", "20250930"],
            "symbol": ["00005.HK", "00011.HK"],
            "selected": [1, 1],
        }
    ).to_csv(by_date_file, index=False)

    out_path = repo_root / "pit_gt365.json"
    args = SimpleNamespace(
        config=None,
        asset_dir=str(asset_dir),
        fundamentals_file=None,
        field_profile=[],
        field=["revenue"],
        fields_file=[],
        mode="strict",
        include_health=True,
        target_date="20250930",
        symbols_file=None,
        by_date_file=str(by_date_file),
        health_sample_limit=3,
        min_symbols=1,
        top=10,
        quarter_limit=12,
        format="json",
        out=str(out_path),
        fail_on_severity="warning",
    )

    assert rqdata_assets.inspect_hk_pit_coverage(args) == 2

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    checks = {(item["check"], item.get("field")): item for item in payload["health"]["quality_checks"]}
    assert checks[("feature_stale_gt_365d_asof_target_date", "revenue")] == {
        "check": "feature_stale_gt_365d_asof_target_date",
        "field": "revenue",
        "severity": "warning",
        "affected_symbols": 1,
        "affected_pct": 50.0,
        "sample_symbols": ["00011.HK"],
    }
