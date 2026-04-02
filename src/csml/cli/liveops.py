from __future__ import annotations

from .common import append_arg, append_bool_switch, append_repeat_args


def handle_holdings(args) -> int:
    from ..liveops import holdings

    argv: list[str] = []
    append_arg(argv, "--config", getattr(args, "config", None))
    append_arg(argv, "--run-dir", getattr(args, "run_dir", None))
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


def register_liveops_commands(subparsers) -> None:
    holdings = subparsers.add_parser("holdings", help="Show latest holdings from saved runs")
    holdings.add_argument(
        "--config",
        help="Pipeline config path or built-in name (default: default).",
    )
    holdings.add_argument(
        "--run-dir",
        help="Explicit run directory to read (overrides --config).",
    )
    holdings.add_argument(
        "--top-k",
        type=int,
        help="Optional Top-K filter when selecting the latest run.",
    )
    holdings.add_argument(
        "--as-of",
        default="t-1",
        help=(
            "As-of date (YYYYMMDD, YYYY-MM-DD, today, t-1, last_trading_day, "
            "last_completed_trading_day). Default: t-1."
        ),
    )
    holdings.add_argument(
        "--source",
        default="auto",
        choices=["auto", "backtest", "live"],
        help="Positions source (auto/backtest/live). Default: auto.",
    )
    holdings.add_argument(
        "--format",
        default="text",
        choices=["text", "csv", "json"],
        help="Output format (text/csv/json). Default: text.",
    )
    holdings.add_argument(
        "--out",
        help="Optional output path (default: stdout).",
    )
    holdings.set_defaults(func=handle_holdings)

    alloc = subparsers.add_parser(
        "alloc",
        help="Compute equal-weight lot sizing from latest holdings using rqdata prices.",
    )
    alloc.add_argument(
        "--config",
        help="Pipeline config path or built-in name (default: default).",
    )
    alloc.add_argument(
        "--run-dir",
        help="Explicit run directory to read (overrides --config).",
    )
    alloc.add_argument(
        "--positions-file",
        help="Explicit positions CSV path (overrides --config/--run-dir).",
    )
    alloc.add_argument(
        "--top-k",
        type=int,
        help="Optional Top-K filter when selecting the latest run.",
    )
    alloc.add_argument(
        "--as-of",
        default="t-1",
        help=(
            "As-of date (YYYYMMDD, YYYY-MM-DD, today, t-1, last_trading_day, "
            "last_completed_trading_day). Default: t-1."
        ),
    )
    alloc.add_argument(
        "--source",
        default="auto",
        choices=["auto", "backtest", "live"],
        help="Positions source (auto/backtest/live). Default: auto.",
    )
    alloc.add_argument(
        "--side",
        default="long",
        choices=["long", "short", "all"],
        help="Select side for allocation (long/short/all). Default: long.",
    )
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
    alloc.add_argument("--username", help="Override RQData username.")
    alloc.add_argument("--password", help="Override RQData password.")
    alloc.add_argument(
        "--format",
        default="text",
        choices=["text", "csv", "json"],
        help="Output format (text/csv/json). Default: text.",
    )
    alloc.add_argument(
        "--out",
        help="Optional output path (default: stdout).",
    )
    alloc.set_defaults(func=handle_alloc)

    alloc_hk = subparsers.add_parser(
        "alloc-hk",
        help="HK pre-trade allocation with custom weights, valuation buckets, and secondary fill.",
    )
    alloc_hk.add_argument(
        "--config",
        help="Pipeline config path or built-in name (default: default).",
    )
    alloc_hk.add_argument(
        "--run-dir",
        help="Explicit run directory to read (overrides --config).",
    )
    alloc_hk.add_argument(
        "--positions-file",
        help="Explicit positions CSV path (overrides --config/--run-dir).",
    )
    alloc_hk.add_argument(
        "--top-k",
        type=int,
        help="Optional Top-K filter when selecting the latest run.",
    )
    alloc_hk.add_argument(
        "--as-of",
        default="t-1",
        help=(
            "As-of date (YYYYMMDD, YYYY-MM-DD, today, t-1, last_trading_day, "
            "last_completed_trading_day). Default: t-1."
        ),
    )
    alloc_hk.add_argument(
        "--source",
        default="auto",
        choices=["auto", "backtest", "live"],
        help="Positions source (auto/backtest/live). Default: auto.",
    )
    alloc_hk.add_argument(
        "--side",
        default="long",
        choices=["long", "short", "all"],
        help="Select side for allocation (long/short/all). Default: long.",
    )
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
    alloc_hk.add_argument("--history-years", type=int, help="Lookback years for valuation history.")
    alloc_hk.add_argument("--roll-window", type=int, help="Rolling window used for valuation thresholds.")
    alloc_hk.add_argument("--sell-quantile", type=float, help="Quantile used for HIGH valuation threshold.")
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
    alloc_hk.add_argument("--max-over-alloc-ratio", type=float, help="Over-allocation cap as a ratio of cash.")
    alloc_hk.add_argument("--max-over-alloc-amount", type=float, help="Over-allocation cap as an absolute amount.")
    alloc_hk.add_argument(
        "--max-over-alloc-lots-per-ticker",
        type=int,
        help="Per-ticker cap for over-allocation lots.",
    )
    alloc_hk.add_argument("--cash-buffer-ratio", type=float, help="Cash buffer ratio reserved before fill.")
    alloc_hk.add_argument("--cash-buffer-amount", type=float, help="Cash buffer amount reserved before fill.")
    alloc_hk.add_argument(
        "--estimated-fee-per-order",
        type=float,
        help="Estimated fee added to each secondary fill step.",
    )
    alloc_hk.add_argument("--username", help="Override RQData username.")
    alloc_hk.add_argument("--password", help="Override RQData password.")
    alloc_hk.add_argument(
        "--fail-on-quality",
        choices=["none", "info", "warning", "error"],
        default=None,
        help=(
            "Optional quality gate threshold. When omitted, alloc-hk reuses the threshold stored "
            "in the resolved run summary or from the config."
        ),
    )
    alloc_hk.add_argument(
        "--format",
        default="text",
        choices=["text", "csv", "json", "xlsx"],
        help="Output format (text/csv/json/xlsx). Default: text.",
    )
    alloc_hk.add_argument(
        "--out",
        help="Optional output path (default: stdout; required for xlsx).",
    )
    alloc_hk.set_defaults(func=handle_alloc_hk)

    snapshot = subparsers.add_parser(
        "snapshot",
        help="Run a live snapshot and emit latest holdings",
    )
    snapshot.add_argument(
        "--config",
        help="Pipeline config path or built-in name.",
    )
    snapshot.add_argument(
        "--run-dir",
        help="Use an existing run directory (skips pipeline run).",
    )
    snapshot.add_argument(
        "--as-of",
        default="t-1",
        help=(
            "As-of date (YYYYMMDD, YYYY-MM-DD, today, t-1, last_trading_day, "
            "last_completed_trading_day). Default: t-1."
        ),
    )
    snapshot.add_argument(
        "--skip-run",
        action="store_true",
        help="Skip running the pipeline and only emit holdings from the latest run.",
    )
    snapshot.add_argument(
        "--top-k",
        type=int,
        help="Optional Top-K filter when selecting the latest run.",
    )
    snapshot.add_argument(
        "--format",
        default="text",
        choices=["text", "csv", "json"],
        help="Output format (text/csv/json). Default: text.",
    )
    snapshot.add_argument(
        "--out",
        help="Optional output path (default: stdout).",
    )
    snapshot.add_argument(
        "--fail-on-quality",
        choices=["none", "info", "warning", "error"],
        default=None,
        help=(
            "Optional quality gate threshold. When omitted, snapshot reuses the threshold stored "
            "in the resolved run summary or from the config."
        ),
    )
    snapshot.set_defaults(func=handle_snapshot)
