import json
from pathlib import Path

import pytest

from cstree.pipeline import quality as pipeline_quality


def test_run_quality_preflight_reports_platform_migration(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()

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

    assert preflight["enabled"] is False
    assert preflight["gate_triggered"] is False
    assert preflight["fail_on_severity"] == "warning"
    assert preflight["checks"] == []
    assert preflight["overall_verdict"] is None
    assert "market-data-platform" in preflight["message"]
    assert "marketdata rqdata hk-assets" in preflight["message"]
    assert not (run_dir / "quality" / "hk_pit_coverage_preflight.json").exists()


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
