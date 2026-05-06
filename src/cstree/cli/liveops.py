from __future__ import annotations

from .common import append_arg, append_bool_switch, append_repeat_args


def handle_holdings(args) -> int:
    from ..liveops import holdings

    argv: list[str] = []
    append_arg(argv, "--config", getattr(args, "config", None))
    append_arg(argv, "--run-dir", getattr(args, "run_dir", None))
    append_arg(argv, "--artifacts-root", getattr(args, "artifacts_root", None))
    append_arg(argv, "--top-k", getattr(args, "top_k", None), formatter=str)
    append_arg(argv, "--as-of", getattr(args, "as_of", None))
    append_arg(argv, "--source", getattr(args, "source", None))
    append_arg(argv, "--format", getattr(args, "format", None))
    append_arg(argv, "--out", getattr(args, "out", None))
    holdings.main(argv)
    return 0


def handle_snapshot(args) -> int:
    from ..liveops import snapshot

    argv: list[str] = []
    append_arg(argv, "--config", getattr(args, "config", None))
    append_arg(argv, "--run-dir", getattr(args, "run_dir", None))
    append_arg(argv, "--artifacts-root", getattr(args, "artifacts_root", None))
    append_arg(argv, "--as-of", getattr(args, "as_of", None))
    append_bool_switch(argv, getattr(args, "skip_run", None), true_flag="--skip-run")
    append_arg(argv, "--top-k", getattr(args, "top_k", None), formatter=str)
    append_arg(argv, "--fail-on-quality", getattr(args, "fail_on_quality", None))
    append_arg(argv, "--format", getattr(args, "format", None))
    append_arg(argv, "--out", getattr(args, "out", None))
    snapshot.main(argv)
    return 0


def handle_alloc(args) -> int:
    from ..liveops import alloc

    argv: list[str] = []
    append_arg(argv, "--config", getattr(args, "config", None))
    append_arg(argv, "--run-dir", getattr(args, "run_dir", None))
    append_arg(argv, "--artifacts-root", getattr(args, "artifacts_root", None))
    append_arg(argv, "--positions-file", getattr(args, "positions_file", None))
    append_arg(argv, "--top-k", getattr(args, "top_k", None), formatter=str)
    append_arg(argv, "--as-of", getattr(args, "as_of", None))
    append_arg(argv, "--source", getattr(args, "source", None))
    append_arg(argv, "--side", getattr(args, "side", None))
    append_arg(argv, "--top-n", getattr(args, "top_n", None), formatter=str)
    append_arg(argv, "--cash", getattr(args, "cash", None), formatter=str)
    append_arg(argv, "--buffer-bps", getattr(args, "buffer_bps", None), formatter=str)
    append_arg(argv, "--price-field", getattr(args, "price_field", None))
    append_arg(
        argv,
        "--price-lookback-days",
        getattr(args, "price_lookback_days", None),
        formatter=str,
    )
    append_arg(argv, "--username", getattr(args, "username", None))
    append_arg(argv, "--password", getattr(args, "password", None))
    append_arg(argv, "--format", getattr(args, "format", None))
    append_arg(argv, "--out", getattr(args, "out", None))
    alloc.main(argv)
    return 0


def handle_alloc_hk(args) -> int:
    from ..liveops import alloc_hk

    argv: list[str] = []
    append_arg(argv, "--config", getattr(args, "config", None))
    append_arg(argv, "--run-dir", getattr(args, "run_dir", None))
    append_arg(argv, "--artifacts-root", getattr(args, "artifacts_root", None))
    append_arg(argv, "--positions-file", getattr(args, "positions_file", None))
    append_arg(argv, "--top-k", getattr(args, "top_k", None), formatter=str)
    append_arg(argv, "--as-of", getattr(args, "as_of", None))
    append_arg(argv, "--source", getattr(args, "source", None))
    append_arg(argv, "--side", getattr(args, "side", None))
    append_arg(argv, "--top-n", getattr(args, "top_n", None), formatter=str)
    append_repeat_args(argv, "--scenario-capital", getattr(args, "scenario_capital", None))
    append_repeat_args(argv, "--scenario-top-n", getattr(args, "scenario_top_n", None))
    append_arg(argv, "--cash", getattr(args, "cash", None), formatter=str)
    append_arg(argv, "--method", getattr(args, "method", None))
    append_bool_switch(
        argv,
        getattr(args, "require_stock_connect", None),
        true_flag="--require-stock-connect",
        false_flag="--allow-non-stock-connect",
    )
    append_arg(argv, "--execution-calendar", getattr(args, "execution_calendar", None))
    append_bool_switch(
        argv,
        getattr(args, "allow_connect_closed", None),
        true_flag="--allow-connect-closed",
    )
    append_arg(argv, "--history-years", getattr(args, "history_years", None), formatter=str)
    append_arg(argv, "--roll-window", getattr(args, "roll_window", None), formatter=str)
    append_arg(argv, "--sell-quantile", getattr(args, "sell_quantile", None), formatter=str)
    append_arg(
        argv,
        "--extreme-quantile",
        getattr(args, "extreme_quantile", None),
        formatter=str,
    )
    append_bool_switch(
        argv,
        getattr(args, "secondary_fill_enabled", None),
        true_flag="--secondary-fill",
        false_flag="--no-secondary-fill",
    )
    append_bool_switch(
        argv,
        getattr(args, "avoid_high_valuation", None),
        true_flag="--avoid-high-valuation",
        false_flag="--allow-high-valuation",
    )
    append_bool_switch(
        argv,
        getattr(args, "avoid_high_valuation_strict", None),
        true_flag="--avoid-high-valuation-strict",
    )
    append_bool_switch(
        argv,
        getattr(args, "allow_over_alloc", None),
        true_flag="--allow-over-alloc",
    )
    append_arg(argv, "--max-steps", getattr(args, "max_steps", None), formatter=str)
    append_arg(
        argv,
        "--max-over-alloc-ratio",
        getattr(args, "max_over_alloc_ratio", None),
        formatter=str,
    )
    append_arg(
        argv,
        "--max-over-alloc-amount",
        getattr(args, "max_over_alloc_amount", None),
        formatter=str,
    )
    append_arg(
        argv,
        "--max-over-alloc-lots-per-ticker",
        getattr(args, "max_over_alloc_lots_per_ticker", None),
        formatter=str,
    )
    append_arg(
        argv,
        "--cash-buffer-ratio",
        getattr(args, "cash_buffer_ratio", None),
        formatter=str,
    )
    append_arg(
        argv,
        "--cash-buffer-amount",
        getattr(args, "cash_buffer_amount", None),
        formatter=str,
    )
    append_arg(
        argv,
        "--estimated-fee-per-order",
        getattr(args, "estimated_fee_per_order", None),
        formatter=str,
    )
    append_arg(argv, "--username", getattr(args, "username", None))
    append_arg(argv, "--password", getattr(args, "password", None))
    append_arg(argv, "--fail-on-quality", getattr(args, "fail_on_quality", None))
    append_arg(argv, "--format", getattr(args, "format", None))
    append_arg(argv, "--out", getattr(args, "out", None))
    alloc_hk.main(argv)
    return 0


def _add_config_arg(parser, *, help_text: str) -> None:
    parser.add_argument(
        "--config",
        help=help_text,
    )


def _add_run_dir_arg(parser, *, help_text: str) -> None:
    parser.add_argument(
        "--run-dir",
        help=help_text,
    )


def _add_artifacts_root_arg(parser) -> None:
    parser.add_argument(
        "--artifacts-root",
        help="Optional artifacts root override used when resolving the default runs directory.",
    )


def _add_positions_file_arg(parser) -> None:
    parser.add_argument(
        "--positions-file",
        help="Explicit positions CSV path (overrides --config/--run-dir).",
    )


def _add_top_k_arg(parser) -> None:
    parser.add_argument(
        "--top-k",
        type=int,
        help="Optional Top-K filter when selecting the latest run.",
    )


def _add_as_of_arg(parser) -> None:
    parser.add_argument(
        "--as-of",
        default="t-1",
        help=(
            "As-of date (YYYYMMDD, YYYY-MM-DD, today, t-1, last_trading_day, "
            "last_completed_trading_day). Default: t-1."
        ),
    )


def _add_source_arg(parser) -> None:
    parser.add_argument(
        "--source",
        default="auto",
        choices=["auto", "backtest", "live"],
        help="Positions source (auto/backtest/live). Default: auto.",
    )


def _add_side_arg(parser) -> None:
    parser.add_argument(
        "--side",
        default="long",
        choices=["long", "short", "all"],
        help="Select side for allocation (long/short/all). Default: long.",
    )


def _add_rqdata_auth_args(parser) -> None:
    parser.add_argument("--username", help="Override RQData username.")
    parser.add_argument("--password", help="Override RQData password.")


def _add_output_args(parser, *, formats: list[str], default: str = "text", out_help: str) -> None:
    parser.add_argument(
        "--format",
        default=default,
        choices=formats,
        help=f"Output format ({'/'.join(formats)}). Default: {default}.",
    )
    parser.add_argument(
        "--out",
        help=out_help,
    )


def _add_quality_gate_arg(parser, *, command: str) -> None:
    parser.add_argument(
        "--fail-on-quality",
        choices=["none", "info", "warning", "error"],
        default=None,
        help=(
            f"Optional quality gate threshold. When omitted, {command} reuses the "
            "threshold stored in the resolved run summary or from the config."
        ),
    )


def _register_holdings_command(subparsers) -> None:
    holdings = subparsers.add_parser("holdings", help="Show latest holdings from saved runs")
    _add_config_arg(
        holdings,
        help_text="Pipeline config path or built-in name (default: default).",
    )
    _add_run_dir_arg(
        holdings,
        help_text="Explicit run directory to read (overrides --config).",
    )
    _add_artifacts_root_arg(holdings)
    _add_top_k_arg(holdings)
    _add_as_of_arg(holdings)
    _add_source_arg(holdings)
    _add_output_args(
        holdings,
        formats=["text", "csv", "json"],
        out_help="Optional output path (default: stdout).",
    )
    holdings.set_defaults(func=handle_holdings)


def _register_alloc_command(subparsers) -> None:
    alloc = subparsers.add_parser(
        "alloc",
        help="Compute equal-weight lot sizing from latest holdings using rqdata prices.",
    )
    _add_config_arg(
        alloc,
        help_text="Pipeline config path or built-in name (default: default).",
    )
    _add_run_dir_arg(
        alloc,
        help_text="Explicit run directory to read (overrides --config).",
    )
    _add_artifacts_root_arg(alloc)
    _add_positions_file_arg(alloc)
    _add_top_k_arg(alloc)
    _add_as_of_arg(alloc)
    _add_source_arg(alloc)
    _add_side_arg(alloc)
    alloc.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="Number of names to allocate equally from sorted holdings. Default: 20.",
    )
    alloc.add_argument(
        "--cash",
        type=float,
        default=1_000_000,
        help="Total portfolio cash for sizing. Default: 1000000.",
    )
    alloc.add_argument(
        "--buffer-bps",
        type=float,
        default=0.0,
        help="Cash buffer in bps reserved from investment. Default: 0.",
    )
    alloc.add_argument(
        "--price-field",
        default="close",
        help="Price field fetched from rqdata.get_price. Default: close.",
    )
    alloc.add_argument(
        "--price-lookback-days",
        type=int,
        default=20,
        help="Price lookback window in calendar days before price date. Default: 20.",
    )
    _add_rqdata_auth_args(alloc)
    _add_output_args(
        alloc,
        formats=["text", "csv", "json"],
        out_help="Optional output path (default: stdout).",
    )
    alloc.set_defaults(func=handle_alloc)


def _register_alloc_hk_command(subparsers) -> None:
    alloc_hk = subparsers.add_parser(
        "alloc-hk",
        help="HK pre-trade allocation with custom weights, valuation buckets, and secondary fill.",
    )
    _add_config_arg(
        alloc_hk,
        help_text="Pipeline config path or built-in name (default: default).",
    )
    _add_run_dir_arg(
        alloc_hk,
        help_text="Explicit run directory to read (overrides --config).",
    )
    _add_artifacts_root_arg(alloc_hk)
    _add_positions_file_arg(alloc_hk)
    _add_top_k_arg(alloc_hk)
    _add_as_of_arg(alloc_hk)
    _add_source_arg(alloc_hk)
    _add_side_arg(alloc_hk)
    alloc_hk.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="Number of names to allocate from sorted holdings. Default: 20.",
    )
    alloc_hk.add_argument(
        "--scenario-capital",
        action="append",
        help="Scenario capital list (repeatable, supports comma-separated values).",
    )
    alloc_hk.add_argument(
        "--scenario-top-n",
        action="append",
        help="Scenario Top-N list (repeatable, supports comma-separated values).",
    )
    alloc_hk.add_argument(
        "--cash",
        type=float,
        help="Total portfolio cash for sizing. Overrides live.alloc_hk.cash.",
    )
    alloc_hk.add_argument(
        "--method",
        choices=["equal", "custom"],
        help="Sizing method. custom uses holdings weight.",
    )
    alloc_hk.add_argument(
        "--require-stock-connect",
        dest="require_stock_connect",
        action="store_true",
        default=None,
        help="Require stock_connect eligibility for tradable names.",
    )
    alloc_hk.add_argument(
        "--allow-non-stock-connect",
        dest="require_stock_connect",
        action="store_false",
        help="Allow non-stock-connect names to remain tradable.",
    )
    alloc_hk.add_argument(
        "--execution-calendar",
        choices=["market", "hk_market", "hk_connect", "stock_connect", "southbound"],
        help="Execution calendar used by the live gate. Default: hk_connect when stock-connect is required.",
    )
    alloc_hk.add_argument(
        "--allow-connect-closed",
        dest="allow_connect_closed",
        action="store_true",
        default=None,
        help="Allow allocation output even when the Stock Connect execution calendar is closed.",
    )
    alloc_hk.add_argument(
        "--history-years",
        type=int,
        help="Lookback years for valuation history.",
    )
    alloc_hk.add_argument(
        "--roll-window",
        type=int,
        help="Rolling window used for valuation thresholds.",
    )
    alloc_hk.add_argument(
        "--sell-quantile",
        type=float,
        help="Quantile used for HIGH valuation threshold.",
    )
    alloc_hk.add_argument(
        "--extreme-quantile",
        type=float,
        help="Quantile used for EXTREME valuation threshold.",
    )
    alloc_hk.add_argument(
        "--secondary-fill",
        dest="secondary_fill_enabled",
        action="store_true",
        default=None,
        help="Enable secondary fill after base lot sizing.",
    )
    alloc_hk.add_argument(
        "--no-secondary-fill",
        dest="secondary_fill_enabled",
        action="store_false",
        help="Disable secondary fill after base lot sizing.",
    )
    alloc_hk.add_argument(
        "--avoid-high-valuation",
        dest="avoid_high_valuation",
        action="store_true",
        default=None,
        help="Prefer LOW/NEUTRAL names first during secondary fill.",
    )
    alloc_hk.add_argument(
        "--allow-high-valuation",
        dest="avoid_high_valuation",
        action="store_false",
        help="Do not prefer LOW/NEUTRAL names during secondary fill.",
    )
    alloc_hk.add_argument(
        "--avoid-high-valuation-strict",
        dest="avoid_high_valuation_strict",
        action="store_true",
        default=None,
        help="Hard-block HIGH/EXTREME names during secondary fill.",
    )
    alloc_hk.add_argument(
        "--allow-over-alloc",
        dest="allow_over_alloc",
        action="store_true",
        default=None,
        help="Allow bounded over-allocation during secondary fill.",
    )
    alloc_hk.add_argument("--max-steps", type=int, help="Maximum secondary fill steps.")
    alloc_hk.add_argument(
        "--max-over-alloc-ratio",
        type=float,
        help="Over-allocation cap as a ratio of cash.",
    )
    alloc_hk.add_argument(
        "--max-over-alloc-amount",
        type=float,
        help="Over-allocation cap as an absolute amount.",
    )
    alloc_hk.add_argument(
        "--max-over-alloc-lots-per-ticker",
        type=int,
        help="Per-ticker cap for over-allocation lots.",
    )
    alloc_hk.add_argument(
        "--cash-buffer-ratio",
        type=float,
        help="Cash buffer ratio reserved before fill.",
    )
    alloc_hk.add_argument(
        "--cash-buffer-amount",
        type=float,
        help="Cash buffer amount reserved before fill.",
    )
    alloc_hk.add_argument(
        "--estimated-fee-per-order",
        type=float,
        help="Estimated fee added to each secondary fill step.",
    )
    _add_rqdata_auth_args(alloc_hk)
    _add_quality_gate_arg(alloc_hk, command="alloc-hk")
    _add_output_args(
        alloc_hk,
        formats=["text", "csv", "json", "xlsx"],
        out_help="Optional output path (default: stdout; required for xlsx).",
    )
    alloc_hk.set_defaults(func=handle_alloc_hk)


def _register_snapshot_command(subparsers) -> None:
    snapshot = subparsers.add_parser(
        "snapshot",
        help="Run a live snapshot and emit latest holdings",
    )
    _add_config_arg(snapshot, help_text="Pipeline config path or built-in name.")
    _add_run_dir_arg(
        snapshot,
        help_text="Use an existing run directory (skips pipeline run).",
    )
    _add_artifacts_root_arg(snapshot)
    _add_as_of_arg(snapshot)
    snapshot.add_argument(
        "--skip-run",
        action="store_true",
        help="Skip running the pipeline and only emit holdings from the latest run.",
    )
    _add_top_k_arg(snapshot)
    _add_output_args(
        snapshot,
        formats=["text", "csv", "json"],
        out_help="Optional output path (default: stdout).",
    )
    _add_quality_gate_arg(snapshot, command="snapshot")
    snapshot.set_defaults(func=handle_snapshot)


def register_liveops_commands(subparsers) -> None:
    _register_holdings_command(subparsers)
    _register_alloc_command(subparsers)
    _register_alloc_hk_command(subparsers)
    _register_snapshot_command(subparsers)
