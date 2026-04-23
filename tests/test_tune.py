import csv
import json
from pathlib import Path

import pytest
import yaml

from cstree import pipeline as pipeline_mod
from cstree.commands import tune
from cstree.research import summarize_runs as summarize_tool


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_fake_summary(
    run_dir: Path,
    run_name: str,
    *,
    eval_ic_ir: float,
    wf_test_ic: float,
    backtest_sharpe: float,
    cv_ic_scores: list[float | None] | None = None,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    scores = cv_ic_scores if cv_ic_scores is not None else [0.02, 0.01, 0.03]
    mean = [float(value) for value in scores if value is not None]
    payload = {
        "run": {
            "name": run_name,
            "output_dir": str(run_dir),
        },
        "eval": {
            "ic": {"ir": eval_ic_ir},
            "cv_ic": {
                "mean": sum(mean) / len(mean) if mean else None,
                "std": 0.0 if mean else None,
                "scores": scores,
            },
            "constant_prediction": False,
            "zero_feature_importance": False,
        },
        "backtest": {
            "stats": {
                "sharpe": backtest_sharpe,
                "max_drawdown": -0.10,
                "avg_turnover": 0.25,
                "avg_cost_drag": 0.002,
            }
        },
        "walk_forward": {
            "results": [
                {"status": "ok", "test_ic": {"mean": wf_test_ic}},
                {"status": "ok", "test_ic": {"mean": wf_test_ic / 2}},
            ]
        },
    }
    (run_dir / "summary.json").write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def test_tune_generates_configs_runs_and_best_trial(tmp_path, monkeypatch):
    base_cfg = {
        "market": "hk",
        "model": {
            "type": "xgb_regressor",
            "params": {"learning_rate": 0.05, "max_depth": 3, "reg_lambda": 1.0},
            "sample_weight_mode": "date_equal",
        },
        "eval": {"output_dir": "artifacts/runs", "run_name": "base"},
    }
    base_config_path = tmp_path / "base.yml"
    base_config_path.write_text(yaml.safe_dump(base_cfg, sort_keys=False), encoding="utf-8")

    tune_spec = {
        "base_config": str(base_config_path),
        "run_name_prefix": "demo_",
        "tag": "unit_tune",
        "sweeps_dir": str(tmp_path / "sweeps"),
        "runs_dir": str(tmp_path / "runs"),
        "sampler": "grid",
        "search_space": [
            {"name": "lr", "path": "model.params.learning_rate", "values": [0.03, 0.05]},
            {
                "name": "sample_weight",
                "values": [
                    {
                        "label": "date_equal",
                        "overrides": {
                            "model.sample_weight_mode": "date_equal",
                            "model.sample_weight_params": None,
                        },
                    },
                    {
                        "label": "exp_h12",
                        "overrides": {
                            "model.sample_weight_mode": "exp_decay",
                            "model.sample_weight_params.halflife": 12,
                        },
                    },
                ],
            },
        ],
    }
    tune_spec_path = tmp_path / "tune.yml"
    tune_spec_path.write_text(yaml.safe_dump(tune_spec, sort_keys=False), encoding="utf-8")

    run_calls: list[str] = []

    def fake_pipeline_run(cfg_path: str) -> None:
        run_calls.append(cfg_path)
        cfg = yaml.safe_load(Path(cfg_path).read_text(encoding="utf-8"))
        run_name = cfg["eval"]["run_name"]
        output_dir = Path(cfg["eval"]["output_dir"]).expanduser()
        if not output_dir.is_absolute():
            output_dir = (Path.cwd() / output_dir).resolve()
        run_dir = output_dir / f"{run_name}_20260101_000000_deadbeef"

        learning_rate = float(cfg["model"]["params"]["learning_rate"])
        sample_weight_mode = str(cfg["model"].get("sample_weight_mode"))
        eval_ic_ir = 0.20 if sample_weight_mode == "exp_decay" else 0.10
        if learning_rate >= 0.05:
            eval_ic_ir += 0.03
        wf_test_ic = 0.06 if sample_weight_mode == "exp_decay" else 0.02
        backtest_sharpe = 0.80 if learning_rate >= 0.05 else 0.50
        _write_fake_summary(
            run_dir,
            run_name,
            eval_ic_ir=eval_ic_ir,
            wf_test_ic=wf_test_ic,
            backtest_sharpe=backtest_sharpe,
        )

    summarize_calls: list[list[str]] = []

    def fake_summarize_main(argv: list[str]) -> None:
        summarize_calls.append(list(argv))
        output_path = Path(argv[argv.index("--output") + 1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("run_name\n", encoding="utf-8")

    monkeypatch.setattr(pipeline_mod, "run", fake_pipeline_run)
    monkeypatch.setattr(summarize_tool, "main", fake_summarize_main)

    tune.main(["--tune-config", str(tune_spec_path)])

    assert len(run_calls) == 4

    tune_dir = tmp_path / "sweeps" / "unit_tune"
    jobs_csv = tune_dir / "jobs.csv"
    trial_results_csv = tune_dir / "trial_results.csv"
    best_trial_path = tune_dir / "best_trial.json"
    best_config_path = tune_dir / "best_config.yml"
    summary_csv = tune_dir / "runs_summary.csv"

    assert jobs_csv.exists()
    assert trial_results_csv.exists()
    assert best_trial_path.exists()
    assert best_config_path.exists()
    assert summary_csv.exists()

    jobs = _read_csv(jobs_csv)
    assert len(jobs) == 4
    assert jobs[0]["lr"] in {"0.03", "0.05"}
    assert jobs[0]["sample_weight"] in {"date_equal", "exp_h12"}

    generated_cfg = yaml.safe_load((tune_dir / "configs" / "trial_001.yml").read_text(encoding="utf-8"))
    assert generated_cfg["eval"]["run_name"].startswith("demo_unit_tune_trial_")

    results = _read_csv(trial_results_csv)
    assert len(results) == 4
    assert {row["status"] for row in results} == {"ok"}

    best_trial = json.loads(best_trial_path.read_text(encoding="utf-8"))
    assert best_trial["run_name"] == "demo_unit_tune_trial_004"
    assert best_trial["objective_score"] == pytest.approx(0.5925)

    best_cfg = yaml.safe_load(best_config_path.read_text(encoding="utf-8"))
    assert best_cfg["model"]["params"]["learning_rate"] == pytest.approx(0.05)
    assert best_cfg["model"]["sample_weight_mode"] == "exp_decay"
    assert best_cfg["model"]["sample_weight_params"]["halflife"] == 12

    assert len(summarize_calls) == 1
    summarize_argv = summarize_calls[0]
    assert summarize_argv[summarize_argv.index("--runs-dir") + 1] == str((tmp_path / "runs").resolve())
    assert summarize_argv[summarize_argv.index("--run-name-prefix") + 1] == "demo_unit_tune"


def test_tune_stops_on_first_failure(tmp_path, monkeypatch):
    base_cfg = {
        "model": {"type": "xgb_regressor", "params": {"learning_rate": 0.05}},
        "eval": {"output_dir": str(tmp_path / "runs"), "run_name": "base"},
    }
    base_config_path = tmp_path / "base.yml"
    base_config_path.write_text(yaml.safe_dump(base_cfg, sort_keys=False), encoding="utf-8")

    tune_spec = {
        "base_config": str(base_config_path),
        "tag": "stop_case",
        "sweeps_dir": str(tmp_path / "sweeps"),
        "sampler": "grid",
        "search_space": [
            {"name": "lr", "path": "model.params.learning_rate", "values": [0.03, 0.05]},
        ],
        "skip_summarize": True,
    }
    tune_spec_path = tmp_path / "tune.yml"
    tune_spec_path.write_text(yaml.safe_dump(tune_spec, sort_keys=False), encoding="utf-8")

    call_count = {"value": 0}

    def fake_pipeline_run(cfg_path: str) -> None:
        call_count["value"] += 1
        if call_count["value"] == 2:
            raise SystemExit("boom")
        cfg = yaml.safe_load(Path(cfg_path).read_text(encoding="utf-8"))
        run_name = cfg["eval"]["run_name"]
        run_dir = (tmp_path / "runs") / f"{run_name}_20260101_000000_deadbeef"
        _write_fake_summary(run_dir, run_name, eval_ic_ir=0.1, wf_test_ic=0.02, backtest_sharpe=0.5)

    monkeypatch.setattr(pipeline_mod, "run", fake_pipeline_run)

    with pytest.raises(SystemExit, match="Tune stopped on first failure"):
        tune.main(["--tune-config", str(tune_spec_path)])

    results = _read_csv(tmp_path / "sweeps" / "stop_case" / "trial_results.csv")
    assert len(results) == 2
    assert results[0]["status"] == "ok"
    assert results[1]["status"] == "failed"


def test_tune_dry_run_skips_pipeline_and_summarize(tmp_path, monkeypatch):
    base_cfg = {
        "model": {"type": "xgb_regressor", "params": {"learning_rate": 0.05}},
        "eval": {"output_dir": str(tmp_path / "runs"), "run_name": "base"},
    }
    base_config_path = tmp_path / "base.yml"
    base_config_path.write_text(yaml.safe_dump(base_cfg, sort_keys=False), encoding="utf-8")

    tune_spec = {
        "base_config": str(base_config_path),
        "tag": "dry_case",
        "sweeps_dir": str(tmp_path / "sweeps"),
        "sampler": "random",
        "n_trials": 2,
        "seed": 7,
        "search_space": [
            {"name": "lr", "path": "model.params.learning_rate", "values": [0.03, 0.05, 0.08]},
        ],
        "skip_summarize": False,
    }
    tune_spec_path = tmp_path / "tune.yml"
    tune_spec_path.write_text(yaml.safe_dump(tune_spec, sort_keys=False), encoding="utf-8")

    run_calls: list[str] = []
    summarize_calls: list[list[str]] = []
    monkeypatch.setattr(pipeline_mod, "run", lambda cfg_path: run_calls.append(cfg_path))
    monkeypatch.setattr(summarize_tool, "main", lambda argv: summarize_calls.append(list(argv)))

    tune.main(["--tune-config", str(tune_spec_path), "--dry-run"])

    assert run_calls == []
    assert summarize_calls == []

    jobs = _read_csv(tmp_path / "sweeps" / "dry_case" / "jobs.csv")
    assert len(jobs) == 2

    trial_results = _read_csv(tmp_path / "sweeps" / "dry_case" / "trial_results.csv")
    assert trial_results == []


def test_tune_filters_best_trial_by_min_cv_ic_valid_folds(tmp_path, monkeypatch):
    base_cfg = {
        "model": {"type": "xgb_regressor", "params": {"learning_rate": 0.05}},
        "eval": {"output_dir": str(tmp_path / "runs"), "run_name": "base"},
    }
    base_config_path = tmp_path / "base.yml"
    base_config_path.write_text(yaml.safe_dump(base_cfg, sort_keys=False), encoding="utf-8")

    tune_spec = {
        "base_config": str(base_config_path),
        "tag": "cv_gate_case",
        "sweeps_dir": str(tmp_path / "sweeps"),
        "skip_summarize": True,
        "objective": {
            "min_cv_ic_valid_folds": 2,
        },
        "search_space": [
            {"name": "lr", "path": "model.params.learning_rate", "values": [0.03, 0.05]},
        ],
    }
    tune_spec_path = tmp_path / "tune.yml"
    tune_spec_path.write_text(yaml.safe_dump(tune_spec, sort_keys=False), encoding="utf-8")

    def fake_pipeline_run(cfg_path: str) -> None:
        cfg = yaml.safe_load(Path(cfg_path).read_text(encoding="utf-8"))
        run_name = cfg["eval"]["run_name"]
        run_dir = (tmp_path / "runs") / f"{run_name}_20260101_000000_deadbeef"
        learning_rate = float(cfg["model"]["params"]["learning_rate"])
        if learning_rate < 0.05:
            _write_fake_summary(
                run_dir,
                run_name,
                eval_ic_ir=0.50,
                wf_test_ic=0.10,
                backtest_sharpe=1.20,
                cv_ic_scores=[None, None, None],
            )
            return
        _write_fake_summary(
            run_dir,
            run_name,
            eval_ic_ir=0.25,
            wf_test_ic=0.06,
            backtest_sharpe=0.80,
            cv_ic_scores=[0.02, None, 0.01],
        )

    monkeypatch.setattr(pipeline_mod, "run", fake_pipeline_run)

    tune.main(["--tune-config", str(tune_spec_path)])

    results = _read_csv(tmp_path / "sweeps" / "cv_gate_case" / "trial_results.csv")
    assert len(results) == 2

    first = results[0]
    second = results[1]

    assert first["eval_cv_ic_valid_folds"] == "0"
    assert first["flag_cv_ic_insufficient"] == "True"
    assert first["objective_score"] == ""

    assert second["eval_cv_ic_valid_folds"] == "2"
    assert second["flag_cv_ic_insufficient"] == "False"
    assert second["objective_score"] != ""

    best_trial = json.loads(
        (tmp_path / "sweeps" / "cv_gate_case" / "best_trial.json").read_text(encoding="utf-8")
    )
    assert best_trial["run_name"] == "base_tune_cv_gate_case_trial_002"
    assert best_trial["metrics"]["eval_cv_ic_valid_folds"] == 2


def test_repo_tune_spec_points_to_existing_base_config():
    repo_root = Path(__file__).resolve().parents[1]
    spec_path = repo_root / "configs" / "experiments" / "sweeps" / "hk_selected__xgb_regressor_tune_smoke.yml"

    payload = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    resolved_base = repo_root / payload["base_config"]

    assert resolved_base.exists()
    assert payload["run_name_prefix"] == "hk_tune_"
    assert payload["tag"] == "hk_xgb_regressor_tune_smoke"
    assert payload["sampler"] == "random"
    assert payload["n_trials"] == 8
    assert len(payload["search_space"]) == 5
