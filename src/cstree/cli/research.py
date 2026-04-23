from __future__ import annotations

from .common import (
    append_arg,
    append_bool_switch,
    append_repeat_args,
)


def handle_grid(args) -> int:
    from ..commands import run_grid

    argv: list[str] = []
    append_arg(argv, "--config", getattr(args, "config", None))
    append_repeat_args(argv, "--top-k", getattr(args, "top_k", None))
    append_repeat_args(argv, "--cost-bps", getattr(args, "cost_bps", None))
    append_repeat_args(argv, "--buffer-exit", getattr(args, "buffer_exit", None))
    append_repeat_args(argv, "--buffer-entry", getattr(args, "buffer_entry", None))
    append_repeat_args(argv, "--weighting", getattr(args, "weighting", None))
    append_arg(argv, "--output", getattr(args, "output", None))
    append_arg(argv, "--run-name-prefix", getattr(args, "run_name_prefix", None))
    append_arg(argv, "--log-level", getattr(args, "log_level", None))
    run_grid.main(argv)
    return 0


def handle_tune(args) -> int:
    from ..commands import tune

    argv: list[str] = []
    append_arg(argv, "--tune-config", getattr(args, "tune_config", None))
    append_arg(argv, "--config", getattr(args, "config", None))
    append_arg(argv, "--run-name-prefix", getattr(args, "run_name_prefix", None))
    append_arg(argv, "--sweeps-dir", getattr(args, "sweeps_dir", None))
    append_arg(argv, "--tag", getattr(args, "tag", None))
    append_arg(argv, "--runs-dir", getattr(args, "runs_dir", None))
    append_arg(argv, "--sampler", getattr(args, "sampler", None))
    append_arg(argv, "--n-trials", getattr(args, "n_trials", None))
    append_arg(argv, "--seed", getattr(args, "seed", None))
    append_bool_switch(
        argv,
        getattr(args, "dry_run", None),
        true_flag="--dry-run",
        false_flag="--no-dry-run",
    )
    append_bool_switch(
        argv,
        getattr(args, "continue_on_error", None),
        true_flag="--continue-on-error",
        false_flag="--no-continue-on-error",
    )
    append_bool_switch(
        argv,
        getattr(args, "skip_summarize", None),
        true_flag="--skip-summarize",
        false_flag="--no-skip-summarize",
    )
    append_arg(argv, "--summary-output", getattr(args, "summary_output", None))
    append_arg(argv, "--log-level", getattr(args, "log_level", None))
    tune.main(argv)
    return 0


def handle_sweep_linear(args) -> int:
    from ..commands import linear_sweep

    argv: list[str] = []
    append_arg(argv, "--sweep-config", getattr(args, "sweep_config", None))
    append_arg(argv, "--config", getattr(args, "config", None))
    append_arg(argv, "--run-name-prefix", getattr(args, "run_name_prefix", None))
    append_arg(argv, "--sweeps-dir", getattr(args, "sweeps_dir", None))
    append_arg(argv, "--tag", getattr(args, "tag", None))
    append_arg(argv, "--runs-dir", getattr(args, "runs_dir", None))
    append_repeat_args(argv, "--ridge-alpha", getattr(args, "ridge_alpha", None))
    append_repeat_args(argv, "--elasticnet-alpha", getattr(args, "elasticnet_alpha", None))
    append_repeat_args(argv, "--elasticnet-l1-ratio", getattr(args, "elasticnet_l1_ratio", None))
    append_bool_switch(
        argv,
        getattr(args, "skip_ridge", None),
        true_flag="--skip-ridge",
        false_flag="--no-skip-ridge",
    )
    append_bool_switch(
        argv,
        getattr(args, "skip_elasticnet", None),
        true_flag="--skip-elasticnet",
        false_flag="--no-skip-elasticnet",
    )
    append_bool_switch(
        argv,
        getattr(args, "dry_run", None),
        true_flag="--dry-run",
        false_flag="--no-dry-run",
    )
    append_bool_switch(
        argv,
        getattr(args, "continue_on_error", None),
        true_flag="--continue-on-error",
        false_flag="--no-continue-on-error",
    )
    append_bool_switch(
        argv,
        getattr(args, "skip_summarize", None),
        true_flag="--skip-summarize",
        false_flag="--no-skip-summarize",
    )
    append_arg(argv, "--summary-output", getattr(args, "summary_output", None))
    append_arg(argv, "--log-level", getattr(args, "log_level", None))
    linear_sweep.main(argv)
    return 0


def handle_summarize(args) -> int:
    from ..research import summarize_runs

    summarize_runs.run(args)
    return 0


def handle_promotion_gate(args) -> int:
    from ..research import promotion_gate

    return promotion_gate.run(args)


def handle_construction_grid(args) -> int:
    from ..research import construction_grid

    construction_grid.run(args)
    return 0


def handle_feature_evidence(args) -> int:
    from ..research import feature_evidence

    feature_evidence.run(args)
    return 0


def handle_benchmark_ladder(args) -> int:
    from ..research import benchmark_ladder

    benchmark_ladder.run(args)
    return 0


def handle_backup_data(args) -> int:
    from ..data_tools import backup_data

    argv: list[str] = []
    append_arg(argv, "--preset", getattr(args, "preset", None))
    append_arg(argv, "--out-root", getattr(args, "out_root", None))
    append_arg(argv, "--name", getattr(args, "name", None))
    append_repeat_args(argv, "--config", getattr(args, "config", None))
    append_repeat_args(argv, "--include-path", getattr(args, "include_path", None))
    append_bool_switch(argv, getattr(args, "no_cache", None), true_flag="--no-cache")
    append_bool_switch(
        argv,
        getattr(args, "no_universe", None),
        true_flag="--no-universe",
    )
    append_bool_switch(
        argv,
        getattr(args, "skip_missing", None),
        true_flag="--skip-missing",
    )
    backup_data.main(argv)
    return 0


def register_research_commands(subparsers) -> None:
    from ..commands import linear_sweep, run_grid, tune
    from ..data_tools import backup_data as backup_data_tool
    from ..research import benchmark_ladder as benchmark_ladder_tool
    from ..research import construction_grid as construction_grid_tool
    from ..research import feature_evidence as feature_evidence_tool
    from ..research import promotion_gate as promotion_gate_tool
    from ..research import summarize_runs

    grid = subparsers.add_parser(
        "grid",
        help="Run Top-K × cost grid and summarize results",
    )
    run_grid.add_grid_args(grid)
    grid.set_defaults(func=handle_grid)

    tune_cmd = subparsers.add_parser(
        "tune",
        help="Run repo-native model tuning trials from a search spec and auto summarize",
    )
    tune.add_tune_args(tune_cmd)
    tune_cmd.set_defaults(func=handle_tune)

    sweep_linear = subparsers.add_parser(
        "sweep-linear",
        help="Run HK selected ridge/elasticnet hyper-parameter sweep and auto summarize",
    )
    linear_sweep.add_linear_sweep_args(sweep_linear)
    sweep_linear.set_defaults(func=handle_sweep_linear)

    summarize = subparsers.add_parser(
        "summarize",
        help="Aggregate saved runs into a summary CSV",
    )
    summarize_runs.add_summarize_args(summarize)
    summarize.set_defaults(func=handle_summarize)

    promotion_gate = subparsers.add_parser(
        "promotion-gate",
        help="Evaluate a candidate run against a baseline promotion gate",
    )
    promotion_gate_tool.add_promotion_gate_args(promotion_gate)
    promotion_gate.set_defaults(func=handle_promotion_gate)

    construction_grid = subparsers.add_parser(
        "construction-grid",
        help="Compare portfolio construction variants from an existing scored artifact",
    )
    construction_grid_tool.add_construction_grid_args(construction_grid)
    construction_grid.set_defaults(func=handle_construction_grid)

    feature_evidence = subparsers.add_parser(
        "feature-evidence",
        help="Generate and summarize profit-aware feature evidence reports",
    )
    feature_evidence_tool.add_feature_evidence_args(feature_evidence)
    feature_evidence.set_defaults(func=handle_feature_evidence)

    benchmark_ladder = subparsers.add_parser(
        "benchmark-ladder",
        help="Compare strategy returns against a benchmark ladder",
    )
    benchmark_ladder_tool.add_benchmark_ladder_args(benchmark_ladder)
    benchmark_ladder.set_defaults(func=handle_benchmark_ladder)

    backup_data = subparsers.add_parser(
        "backup-data",
        help="Create a private local snapshot of caches, universe files, and configs",
    )
    backup_data_tool.add_backup_data_args(backup_data)
    backup_data.set_defaults(func=handle_backup_data)
