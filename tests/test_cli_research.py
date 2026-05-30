from cstree import cli
from cstree.commands import linear_sweep as sweep_tool, run_grid as grid_tool, tune as tune_tool
from cstree.research import (
    benchmark_ladder as benchmark_ladder_tool,
    construction_grid as construction_grid_tool,
    cpcv as cpcv_tool,
    feature_evidence as feature_evidence_tool,
    promotion_gate as promotion_gate_tool,
    summarize_runs as summarize_tool,
)


def test_cli_parses_research_commands():
    parser = cli.build_parser()

    grid = parser.parse_args(
        [
            "grid",
            "--config",
            "default",
            "--top-k",
            "5,10",
            "--cost-bps",
            "10,20",
            "--buffer-exit",
            "6",
            "--buffer-entry",
            "3",
            "--weighting",
            "equal,signal",
        ]
    )
    assert grid.command == "grid"
    assert grid.top_k == ["5,10"]
    assert grid.cost_bps == ["10,20"]
    assert grid.buffer_exit == ["6"]
    assert grid.buffer_entry == ["3"]
    assert grid.weighting == ["equal,signal"]

    tune_cmd = parser.parse_args(
        [
            "tune",
            "--tune-config",
            "configs/experiments/sweeps/hk_selected__xgb_regressor_tune_smoke.yml",
            "--config",
            "configs/experiments/baseline/hk_selected.yml",
            "--run-name-prefix",
            "hk_tune_",
            "--tag",
            "exp_tune",
            "--sampler",
            "random",
            "--n-trials",
            "8",
            "--seed",
            "7",
            "--dry-run",
        ]
    )
    assert tune_cmd.command == "tune"
    assert tune_cmd.tune_config == "configs/experiments/sweeps/hk_selected__xgb_regressor_tune_smoke.yml"
    assert tune_cmd.run_name_prefix == "hk_tune_"
    assert tune_cmd.tag == "exp_tune"
    assert tune_cmd.sampler == "random"
    assert tune_cmd.n_trials == 8
    assert tune_cmd.seed == 7
    assert tune_cmd.dry_run is True

    sweep = parser.parse_args(
        [
            "sweep-linear",
            "--sweep-config",
            "configs/experiments/sweeps/hk_selected__linear_a.yml",
            "--config",
            "configs/experiments/baseline/hk_selected.yml",
            "--run-name-prefix",
            "hk_sel_",
            "--tag",
            "exp_a",
            "--ridge-alpha",
            "0.01,0.1",
            "--elasticnet-alpha",
            "0.1",
            "--elasticnet-l1-ratio",
            "0.5",
            "--no-skip-ridge",
            "--dry-run",
        ]
    )
    assert sweep.command == "sweep-linear"
    assert sweep.sweep_config == "configs/experiments/sweeps/hk_selected__linear_a.yml"
    assert sweep.run_name_prefix == "hk_sel_"
    assert sweep.tag == "exp_a"
    assert sweep.ridge_alpha == ["0.01,0.1"]
    assert sweep.elasticnet_alpha == ["0.1"]
    assert sweep.elasticnet_l1_ratio == ["0.5"]
    assert sweep.skip_ridge is False
    assert sweep.dry_run is True

    summarize = parser.parse_args(
        [
            "summarize",
            "--runs-dir",
            "artifacts/runs",
            "--run-name-prefix",
            "hk_grid",
            "--since",
            "2026-01-01",
            "--latest-n",
            "3",
            "--exclude-flag-constant-prediction",
            "--exclude-flag-zero-feature-importance",
        ]
    )
    assert summarize.command == "summarize"
    assert summarize.runs_dir == ["artifacts/runs"]
    assert summarize.run_name_prefix == ["hk_grid"]
    assert summarize.since == "2026-01-01"
    assert summarize.latest_n == 3
    assert summarize.short_sample_periods == 24
    assert summarize.exclude_flag_constant_prediction is True
    assert summarize.exclude_flag_zero_feature_importance is True

    promotion_gate = parser.parse_args(
        [
            "promotion-gate",
            "--config",
            "configs/experiments/sweeps/hk_selected__promotion_gate.yml",
            "--baseline-run",
            "artifacts/runs/baseline",
            "--candidate-run",
            "artifacts/runs/candidate",
            "--output-json",
            "artifacts/reports/promotion.json",
        ]
    )
    assert promotion_gate.command == "promotion-gate"
    assert promotion_gate.baseline_run == "artifacts/runs/baseline"
    assert promotion_gate.output_json == "artifacts/reports/promotion.json"

    construction_grid = parser.parse_args(
        [
            "construction-grid",
            "--config",
            "configs/experiments/sweeps/hk_selected__construction_grid.yml",
            "--output",
            "artifacts/reports/construction.csv",
        ]
    )
    assert construction_grid.command == "construction-grid"
    assert construction_grid.output == "artifacts/reports/construction.csv"

    feature_evidence = parser.parse_args(
        [
            "feature-evidence",
            "permutation-importance",
            "--config",
            "configs/experiments/sweeps/hk_selected__feature_evidence.yml",
            "--output",
            "artifacts/reports/features.csv",
        ]
    )
    assert feature_evidence.command == "feature-evidence"
    assert feature_evidence.mode == "permutation-importance"

    factor_ic = parser.parse_args(
        [
            "feature-evidence",
            "factor-ic",
            "--config",
            "configs/experiments/sweeps/hk_selected__feature_evidence.yml",
            "--output",
            "artifacts/reports/factor_ic.csv",
        ]
    )
    assert factor_ic.command == "feature-evidence"
    assert factor_ic.mode == "factor-ic"

    benchmark_ladder = parser.parse_args(
        [
            "benchmark-ladder",
            "--config",
            "configs/experiments/sweeps/hk_selected__benchmark_ladder.yml",
            "--output-json",
            "artifacts/reports/benchmarks.json",
        ]
    )
    assert benchmark_ladder.command == "benchmark-ladder"
    assert benchmark_ladder.output_json == "artifacts/reports/benchmarks.json"

    cpcv = parser.parse_args(
        [
            "cpcv",
            "--config",
            "configs/experiments/baseline/hk_selected.yml",
            "--n-groups",
            "8",
            "--test-groups",
            "2",
            "--out",
            "artifacts/reports/cpcv_hk_selected",
            "--include-final-oos",
        ]
    )
    assert cpcv.command == "cpcv"
    assert cpcv.config == "configs/experiments/baseline/hk_selected.yml"
    assert cpcv.n_groups == 8
    assert cpcv.test_groups == 2
    assert cpcv.out == "artifacts/reports/cpcv_hk_selected"
    assert cpcv.include_final_oos is True



def test_cli_main_grid_passes_through_args(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(grid_tool, "main", lambda argv: calls.append(argv))

    assert (
        cli.main(
            [
                "grid",
                "--config",
                "hk",
                "--top-k",
                "5,10",
                "--top-k",
                "20",
                "--cost-bps",
                "15,25",
                "--buffer-exit",
                "6,8",
                "--buffer-entry",
                "3",
                "--output",
                "artifacts/runs/grid.csv",
                "--run-name-prefix",
                "hk_grid",
                "--log-level",
                "DEBUG",
            ]
        )
        == 0
    )
    assert calls == [
        [
            "--config",
            "hk",
            "--top-k",
            "5,10",
            "--top-k",
            "20",
            "--cost-bps",
            "15,25",
            "--buffer-exit",
            "6,8",
            "--buffer-entry",
            "3",
            "--output",
            "artifacts/runs/grid.csv",
            "--run-name-prefix",
            "hk_grid",
            "--log-level",
            "DEBUG",
        ]
    ]


def test_cli_main_summarize_passes_namespace_to_runner(monkeypatch):
    calls: list[object] = []
    monkeypatch.setattr(summarize_tool, "run", lambda args: calls.append(args))

    assert (
        cli.main(
            [
                "summarize",
                "--runs-dir",
                "artifacts/runs",
                "--output",
                "artifacts/runs/runs_summary.csv",
                "--run-name-prefix",
                "hk_sel_q_benchmark_",
                "--since",
                "2026-01-01",
                "--latest-n",
                "5",
                "--short-sample-periods",
                "24",
                "--high-turnover-threshold",
                "0.7",
                "--score-drawdown-weight",
                "0.5",
                "--score-cost-weight",
                "10.0",
                "--exclude-flag-constant-prediction",
                "--exclude-flag-zero-feature-importance",
                "--sort-by",
                "score",
                "--log-level",
                "INFO",
            ]
        )
        == 0
    )
    assert len(calls) == 1
    args = calls[0]
    assert args.runs_dir == ["artifacts/runs"]
    assert args.output == "artifacts/runs/runs_summary.csv"
    assert args.run_name_prefix == ["hk_sel_q_benchmark_"]
    assert args.exclude_flag_constant_prediction is True
    assert args.exclude_flag_zero_feature_importance is True


def test_cli_main_research_protocol_tools_pass_namespace_to_runners(monkeypatch):
    calls: dict[str, object] = {}

    def _capture(name):
        def _inner(args):
            calls[name] = args
            return 0

        return _inner

    monkeypatch.setattr(promotion_gate_tool, "run", _capture("promotion"))
    monkeypatch.setattr(construction_grid_tool, "run", _capture("construction"))
    monkeypatch.setattr(feature_evidence_tool, "run", _capture("feature"))
    monkeypatch.setattr(benchmark_ladder_tool, "run", _capture("benchmark"))
    monkeypatch.setattr(cpcv_tool, "run", _capture("cpcv"))

    assert cli.main(["promotion-gate", "--config", "gate.yml"]) == 0
    assert cli.main(["construction-grid", "--config", "construction.yml"]) == 0
    assert cli.main(["feature-evidence", "factor-ic", "--config", "features.yml"]) == 0
    assert cli.main(["benchmark-ladder", "--config", "ladder.yml"]) == 0
    assert cli.main(["cpcv", "--config", "cpcv.yml"]) == 0

    assert calls["promotion"].config == "gate.yml"
    assert calls["construction"].config == "construction.yml"
    assert calls["feature"].mode == "factor-ic"
    assert calls["benchmark"].config == "ladder.yml"
    assert calls["cpcv"].config == "cpcv.yml"


def test_cli_main_sweep_linear_passes_through_args(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(sweep_tool, "main", lambda argv: calls.append(argv))

    assert (
        cli.main(
            [
                "sweep-linear",
                "--sweep-config",
                "configs/experiments/sweeps/hk_selected__linear_a.yml",
                "--config",
                "configs/experiments/baseline/hk_selected.yml",
                "--run-name-prefix",
                "hk_sel_",
                "--sweeps-dir",
                "artifacts/sweeps",
                "--tag",
                "exp_1",
                "--runs-dir",
                "artifacts/runs",
                "--ridge-alpha",
                "0.01,0.1",
                "--ridge-alpha",
                "1",
                "--elasticnet-alpha",
                "0.01,0.1",
                "--elasticnet-l1-ratio",
                "0.1,0.5",
                "--no-skip-ridge",
                "--skip-elasticnet",
                "--dry-run",
                "--continue-on-error",
                "--no-skip-summarize",
                "--summary-output",
                "artifacts/sweeps/exp_1/runs_summary.csv",
                "--log-level",
                "DEBUG",
            ]
        )
        == 0
    )
    assert calls == [
        [
            "--sweep-config",
            "configs/experiments/sweeps/hk_selected__linear_a.yml",
            "--config",
            "configs/experiments/baseline/hk_selected.yml",
            "--run-name-prefix",
            "hk_sel_",
            "--sweeps-dir",
            "artifacts/sweeps",
            "--tag",
            "exp_1",
            "--runs-dir",
            "artifacts/runs",
            "--ridge-alpha",
            "0.01,0.1",
            "--ridge-alpha",
            "1",
            "--elasticnet-alpha",
            "0.01,0.1",
            "--elasticnet-l1-ratio",
            "0.1,0.5",
            "--no-skip-ridge",
            "--skip-elasticnet",
            "--dry-run",
            "--continue-on-error",
            "--no-skip-summarize",
            "--summary-output",
            "artifacts/sweeps/exp_1/runs_summary.csv",
            "--log-level",
            "DEBUG",
        ]
    ]


def test_cli_main_tune_passes_through_args(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(tune_tool, "main", lambda argv: calls.append(argv))

    assert (
        cli.main(
            [
                "tune",
                "--tune-config",
                "configs/experiments/sweeps/hk_selected__xgb_regressor_tune_smoke.yml",
                "--config",
                "configs/experiments/baseline/hk_selected.yml",
                "--run-name-prefix",
                "hk_tune_",
                "--sweeps-dir",
                "artifacts/sweeps",
                "--tag",
                "exp_tune",
                "--runs-dir",
                "artifacts/runs",
                "--sampler",
                "random",
                "--n-trials",
                "8",
                "--seed",
                "7",
                "--dry-run",
                "--continue-on-error",
                "--no-skip-summarize",
                "--summary-output",
                "artifacts/sweeps/exp_tune/runs_summary.csv",
                "--log-level",
                "DEBUG",
            ]
        )
        == 0
    )
    assert calls == [
        [
            "--tune-config",
            "configs/experiments/sweeps/hk_selected__xgb_regressor_tune_smoke.yml",
            "--config",
            "configs/experiments/baseline/hk_selected.yml",
            "--run-name-prefix",
            "hk_tune_",
            "--sweeps-dir",
            "artifacts/sweeps",
            "--tag",
            "exp_tune",
            "--runs-dir",
            "artifacts/runs",
            "--sampler",
            "random",
            "--n-trials",
            "8",
            "--seed",
            "7",
            "--dry-run",
            "--continue-on-error",
            "--no-skip-summarize",
            "--summary-output",
            "artifacts/sweeps/exp_tune/runs_summary.csv",
            "--log-level",
            "DEBUG",
        ]
    ]
