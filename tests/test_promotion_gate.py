import json

import yaml

from csml.research import promotion_gate


def _summary(*, sharpe=1.0, wf=0.03, final_ic=0.02, constant=False):
    return {
        "eval": {
            "ic": {"mean": 0.02, "ir": 0.4},
            "long_short": 0.01,
            "cv_ic": {"scores": [0.01, 0.02, None]},
            "constant_prediction": constant,
            "zero_feature_importance": False,
        },
        "backtest": {
            "stats": {
                "sharpe": sharpe,
                "max_drawdown": -0.10,
                "avg_turnover": 0.20,
                "avg_cost_drag": 0.002,
            }
        },
        "walk_forward": {
            "enabled": True,
            "results": [{"status": "ok", "test_ic": {"mean": wf}}],
        },
        "final_oos": {
            "enabled": True,
            "dates": ["2025-01-01", "2025-03-31"],
            "ic": {"mean": final_ic},
            "long_short": 0.01,
            "backtest": {"stats": {"sharpe": 0.8, "avg_turnover": 0.2, "avg_cost_drag": 0.002}},
        },
    }


def _write_run(path, summary, *, horizon=20):
    path.mkdir(parents=True, exist_ok=True)
    (path / "summary.json").write_text(json.dumps(summary, ensure_ascii=True), encoding="utf-8")
    (path / "config.used.yml").write_text(
        yaml.safe_dump({"label": {"horizon_days": horizon}}, sort_keys=False),
        encoding="utf-8",
    )


def test_promotion_gate_marks_promotable_candidate(tmp_path):
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    _write_run(baseline, _summary(sharpe=1.0))
    _write_run(candidate, _summary(sharpe=1.2))

    cfg = promotion_gate.load_promotion_gate_config(
        {
            "baseline_run": str(baseline),
            "candidate_run": str(candidate),
            "comparability_keys": ["label.horizon_days"],
        }
    )
    record = promotion_gate.build_promotion_record(cfg)

    assert record["promotion_status"] == "promotable"
    assert record["is_comparable"] is True
    assert promotion_gate.flatten_promotion_record(record)["candidate_backtest_sharpe"] == 1.2


def test_promotion_gate_rejects_hard_failure(tmp_path):
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    _write_run(baseline, _summary(sharpe=1.0))
    _write_run(candidate, _summary(sharpe=1.2, constant=True))

    record = promotion_gate.build_promotion_record(
        promotion_gate.load_promotion_gate_config(
            {
                "baseline_run": str(baseline),
                "candidate_run": str(candidate),
                "comparability_keys": ["label.horizon_days"],
            }
        )
    )

    assert record["promotion_status"] == "rejected"
    assert record["hard_failures"] == ["constant_prediction"]


def test_promotion_gate_distinguishes_reviewable_and_non_comparable(tmp_path):
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    other = tmp_path / "other"
    _write_run(baseline, _summary(sharpe=1.0), horizon=20)
    _write_run(candidate, _summary(sharpe=1.2), horizon=20)
    _write_run(other, _summary(sharpe=1.2), horizon=60)

    reviewable = promotion_gate.build_promotion_record(
        promotion_gate.load_promotion_gate_config(
            {
                "baseline_run": str(baseline),
                "candidate_run": str(candidate),
                "comparability_keys": ["label.horizon_days"],
                "soft_thresholds": {"min_backtest_sharpe_delta": 0.5},
            }
        )
    )
    non_comparable = promotion_gate.build_promotion_record(
        promotion_gate.load_promotion_gate_config(
            {
                "baseline_run": str(baseline),
                "candidate_run": str(other),
                "comparability_keys": ["label.horizon_days"],
            }
        )
    )

    assert reviewable["promotion_status"] == "reviewable"
    assert reviewable["soft_failures"] == ["min_backtest_sharpe_delta"]
    assert non_comparable["promotion_status"] == "non-comparable"
    assert non_comparable["comparability_mismatches"] == ["label.horizon_days"]

