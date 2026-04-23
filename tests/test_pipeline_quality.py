import json
from pathlib import Path

import pytest

from cstree.pipeline import quality as pipeline_quality


def test_run_quality_preflight_runs_hk_pit_gate_and_persists_report(tmp_path, monkeypatch):
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    def fake_inspect(args):
        payload = {
            "source": {"fundamentals_file": args.fundamentals_file},
            "selection": {"count": 2, "min_symbols_threshold": 5},
            "health": {"target_date": "2026-03-31"},
            "quality_verdict": {
                "color": "red",
                "overall_severity": "error",
                "issue_count": 2,
                "severity_counts": {"error": 1, "warning": 1, "info": 0},
                "fail_on_severity": "warning",
                "gate_triggered": True,
                "gate_status": "fail",
                "failing_issue_count": 2,
                "sample_failing_checks": [
                    "symbol_without_any_pit_row_before_target_date",
                    "selected_feature_set_below_min_symbols_asof_target_date",
                ],
                "message": "2 quality issue(s) met fail_on_severity=warning; the inspection gate was triggered.",
            },
        }
        Path(args.out).write_text(json.dumps(payload), encoding="utf-8")
        return 2

    monkeypatch.setattr(pipeline_quality.rqdata_assets, "inspect_hk_pit_coverage", fake_inspect)

    preflight = pipeline_quality.run_quality_preflight(
        config={
            "market": "hk",
            "data": {"provider": "rqdata"},
            "fundamentals": {
                "enabled": True,
                "source": "file",
                "file": "artifacts/assets/rqdata/hk/pit/demo/pipeline_fundamentals.parquet",
                "features": ["revenue", "net_profit"],
            },
            "universe": {
                "by_date_file": "artifacts/assets/universe/hk_selected_pit_research_by_date.csv",
                "min_symbols_per_date": 5,
            },
            "quality": {"fail_on_severity": "warning"},
        },
        run_dir=run_dir,
        save_artifacts=True,
    )

    assert preflight["enabled"] is True
    assert preflight["gate_triggered"] is True
    assert preflight["overall_verdict"]["gate_triggered"] is True
    assert preflight["checks"][0]["name"] == "hk_pit_coverage_health"
    assert preflight["checks"][0]["report_file"] == str(
        run_dir / "quality" / "hk_pit_coverage_preflight.json"
    )
    assert Path(preflight["checks"][0]["report_file"]).exists()


def test_enforce_liveops_quality_gate_uses_saved_summary_threshold(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    summary = {
        "quality": {
            "preflight": {
                "enabled": True,
                "fail_on_severity": "warning",
                "checks": [],
                "overall_verdict": {
                    "color": "red",
                    "overall_severity": "error",
                    "issue_count": 1,
                    "severity_counts": {"error": 1, "warning": 0, "info": 0},
                    "fail_on_severity": "warning",
                    "gate_triggered": True,
                    "gate_status": "fail",
                    "failing_issue_count": 1,
                    "sample_failing_checks": ["hk_pit_coverage_health"],
                    "message": "1 quality issue(s) met fail_on_severity=warning; the inspection gate was triggered.",
                },
                "gate_triggered": True,
                "message": "1 quality issue(s) met fail_on_severity=warning; the inspection gate was triggered.",
            }
        }
    }
    (run_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")

    with pytest.raises(SystemExit, match="snapshot blocked by quality gate"):
        pipeline_quality.enforce_liveops_quality_gate(
            command_name="snapshot",
            run_dir=run_dir,
            config_ref=None,
            fail_on_quality=None,
        )
