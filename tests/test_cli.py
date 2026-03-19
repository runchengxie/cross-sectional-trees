from types import SimpleNamespace

from csml import cli
from csml.config_utils import resolve_pipeline_config
from csml.project_tools import alloc as alloc_tool
from csml.project_tools import holdings as holdings_tool
from csml.project_tools import run_grid as grid_tool
from csml.project_tools import linear_sweep as sweep_tool
from csml.research_tools import summarize_runs as summarize_tool


def test_cli_parses_run_command():
    parser = cli.build_parser()
    args = parser.parse_args(["run", "--config", "default"])
    assert args.command == "run"
    assert args.config == "default"
    assert callable(args.func)


def test_default_builtin_config_is_hk_first():
    resolved = resolve_pipeline_config(None)
    assert resolved.data["market"] == "hk"
    assert resolved.data["data"]["provider"] == "rqdata"


def test_cli_parses_holdings_snapshot_grid_summarize_alloc():
    parser = cli.build_parser()

    holdings = parser.parse_args(["holdings", "--config", "default"])
    assert holdings.command == "holdings"
    assert holdings.source == "auto"
    assert holdings.format == "text"

    alloc = parser.parse_args(["alloc", "--config", "default", "--top-n", "10"])
    assert alloc.command == "alloc"
    assert alloc.top_n == 10
    assert alloc.cash == 1_000_000
    assert alloc.source == "auto"
    assert alloc.side == "long"

    snapshot = parser.parse_args(["snapshot", "--config", "default", "--skip-run"])
    assert snapshot.command == "snapshot"
    assert snapshot.skip_run is True

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

    backup = parser.parse_args(
        [
            "backup-data",
            "--out-root",
            "artifacts/snapshots",
            "--name",
            "hk_frozen",
            "--config",
            "configs/presets/hk.yml",
            "--include-path",
            "artifacts/assets/universe",
            "--skip-missing",
        ]
    )
    assert backup.command == "backup-data"
    assert backup.out_root == "artifacts/snapshots"
    assert backup.name == "hk_frozen"
    assert backup.config == ["configs/presets/hk.yml"]
    assert backup.include_path == ["artifacts/assets/universe"]
    assert backup.skip_missing is True

    migrate = parser.parse_args(["migrate-artifacts", "--copy", "--dry-run"])
    assert migrate.command == "migrate-artifacts"
    assert migrate.copy is True
    assert migrate.dry_run is True
    assert callable(migrate.func)


def test_cli_parses_rqdata_quota_pretty():
    parser = cli.build_parser()
    args = parser.parse_args(["rqdata", "quota", "--pretty"])
    assert args.command == "rqdata"
    assert args.rq_command == "quota"
    assert args.pretty is True


def test_cli_parses_rqdata_asset_commands():
    parser = cli.build_parser()

    list_fields = parser.parse_args(
        [
            "rqdata",
            "list-hk-financial-fields",
            "--contains",
            "profit",
            "--out",
            "artifacts/exports/hk_fields.txt",
        ]
    )
    assert list_fields.command == "rqdata"
    assert list_fields.rq_command == "list-hk-financial-fields"
    assert list_fields.contains == ["profit"]
    assert list_fields.out == "artifacts/exports/hk_fields.txt"
    assert callable(list_fields.func)

    export_instruments = parser.parse_args(
        [
            "rqdata",
            "export-hk-instruments",
            "--config",
            "configs/presets/hk.yml",
            "--use-config-universe",
            "--limit",
            "100",
            "--out",
            "artifacts/assets/rqdata/hk/instruments/demo.parquet",
            "--force",
        ]
    )
    assert export_instruments.command == "rqdata"
    assert export_instruments.rq_command == "export-hk-instruments"
    assert export_instruments.config == "configs/presets/hk.yml"
    assert export_instruments.use_config_universe is True
    assert export_instruments.limit == 100
    assert export_instruments.out == "artifacts/assets/rqdata/hk/instruments/demo.parquet"
    assert export_instruments.force is True
    assert callable(export_instruments.func)

    daily = parser.parse_args(
        [
            "rqdata",
            "mirror-hk-daily",
            "--by-date-file",
            "artifacts/assets/universe/hk_connect_full_by_date.csv",
            "--start-date",
            "20000101",
            "--end-date",
            "20260311",
            "--field",
            "vwap",
            "--resume",
            "--include-suspended",
            "--name",
            "daily_demo",
        ]
    )
    assert daily.command == "rqdata"
    assert daily.rq_command == "mirror-hk-daily"
    assert daily.by_date_file == "artifacts/assets/universe/hk_connect_full_by_date.csv"
    assert daily.start_date == "20000101"
    assert daily.end_date == "20260311"
    assert daily.field == ["vwap"]
    assert daily.resume is True
    assert daily.skip_suspended is False
    assert daily.name == "daily_demo"
    assert callable(daily.func)

    pit = parser.parse_args(
        [
            "rqdata",
            "mirror-hk-pit-financials",
            "--config",
            "configs/presets/hk.yml",
            "--field-profile",
            "full",
            "--fields-file",
            "configs/field_profiles/hk_financial_fields_starter.txt",
            "--start-quarter",
            "2011q1",
            "--end-quarter",
            "2025q4",
            "--date",
            "20260310",
            "--batch-size",
            "10",
            "--resume",
            "--max-attempts",
            "5",
            "--backoff-seconds",
            "0.25",
            "--max-backoff-seconds",
            "2.0",
            "--name",
            "pit_demo",
        ]
    )
    assert pit.command == "rqdata"
    assert pit.rq_command == "mirror-hk-pit-financials"
    assert pit.config == "configs/presets/hk.yml"
    assert pit.field_profile == ["full"]
    assert pit.fields_file == ["configs/field_profiles/hk_financial_fields_starter.txt"]
    assert pit.start_quarter == "2011q1"
    assert pit.end_quarter == "2025q4"
    assert pit.batch_size == 10
    assert pit.resume is True
    assert pit.skip_existing is False
    assert pit.max_attempts == 5
    assert pit.backoff_seconds == 0.25
    assert pit.max_backoff_seconds == 2.0
    assert pit.name == "pit_demo"
    assert callable(pit.func)


def test_append_passthrough_strips_leading_separator():
    argv: list[str] = []
    cli._append_passthrough(argv, ["--", "--start-date", "20250101"])
    assert argv == ["--start-date", "20250101"]
    parser = cli.build_parser()

    details = parser.parse_args(
        [
            "rqdata",
            "mirror-hk-financial-details",
            "--symbol",
            "00005.HK",
            "--field",
            "revenue",
            "--start-quarter",
            "2024q1",
            "--end-quarter",
            "2025q4",
        ]
    )
    assert details.command == "rqdata"
    assert details.rq_command == "mirror-hk-financial-details"
    assert details.symbol == ["00005.HK"]
    assert details.field == ["revenue"]
    assert details.start_quarter == "2024q1"
    assert details.end_quarter == "2025q4"
    assert callable(details.func)

    ex_factors = parser.parse_args(
        [
            "rqdata",
            "mirror-hk-ex-factors",
            "--symbol",
            "00005.HK",
            "--start-date",
            "20100101",
            "--end-date",
            "20260317",
            "--batch-size",
            "5",
            "--resume",
        ]
    )
    assert ex_factors.command == "rqdata"
    assert ex_factors.rq_command == "mirror-hk-ex-factors"
    assert ex_factors.symbol == ["00005.HK"]
    assert ex_factors.start_date == "20100101"
    assert ex_factors.end_date == "20260317"
    assert ex_factors.batch_size == 5
    assert ex_factors.resume is True
    assert callable(ex_factors.func)

    dividends = parser.parse_args(
        [
            "rqdata",
            "mirror-hk-dividends",
            "--by-date-file",
            "artifacts/assets/universe/hk_connect_full_by_date.csv",
            "--start-date",
            "20100101",
            "--end-date",
            "20260317",
        ]
    )
    assert dividends.command == "rqdata"
    assert dividends.rq_command == "mirror-hk-dividends"
    assert dividends.by_date_file == "artifacts/assets/universe/hk_connect_full_by_date.csv"
    assert dividends.start_date == "20100101"
    assert dividends.end_date == "20260317"
    assert callable(dividends.func)

    shares = parser.parse_args(
        [
            "rqdata",
            "mirror-hk-shares",
            "--config",
            "configs/presets/hk.yml",
            "--field",
            "free_float",
            "--start-date",
            "20100101",
            "--end-date",
            "20260317",
            "--name",
            "shares_demo",
        ]
    )
    assert shares.command == "rqdata"
    assert shares.rq_command == "mirror-hk-shares"
    assert shares.config == "configs/presets/hk.yml"
    assert shares.field == ["free_float"]
    assert shares.start_date == "20100101"
    assert shares.end_date == "20260317"
    assert shares.name == "shares_demo"
    assert callable(shares.func)

    southbound = parser.parse_args(
        [
            "rqdata",
            "mirror-hk-southbound",
            "--by-date-file",
            "artifacts/assets/universe/hk_connect_full_by_date.csv",
            "--start-date",
            "20250101",
            "--end-date",
            "20250331",
            "--trading-type",
            "both",
            "--rebalance-frequency",
            "M",
            "--resume",
        ]
    )
    assert southbound.command == "rqdata"
    assert southbound.rq_command == "mirror-hk-southbound"
    assert southbound.by_date_file == "artifacts/assets/universe/hk_connect_full_by_date.csv"
    assert southbound.start_date == "20250101"
    assert southbound.end_date == "20250331"
    assert southbound.trading_type == ["both"]
    assert southbound.rebalance_frequency == "M"
    assert southbound.resume is True
    assert callable(southbound.func)

    instrument_industry = parser.parse_args(
        [
            "rqdata",
            "mirror-hk-instrument-industry",
            "--by-date-file",
            "artifacts/assets/universe/hk_connect_full_by_date.csv",
            "--start-date",
            "20250101",
            "--end-date",
            "20251231",
            "--level",
            "0",
            "--rebalance-frequency",
            "M",
        ]
    )
    assert instrument_industry.command == "rqdata"
    assert instrument_industry.rq_command == "mirror-hk-instrument-industry"
    assert instrument_industry.by_date_file == "artifacts/assets/universe/hk_connect_full_by_date.csv"
    assert instrument_industry.start_date == "20250101"
    assert instrument_industry.end_date == "20251231"
    assert instrument_industry.level == "0"
    assert instrument_industry.rebalance_frequency == "M"
    assert callable(instrument_industry.func)

    industry_changes = parser.parse_args(
        [
            "rqdata",
            "mirror-hk-industry-changes",
            "--symbol",
            "00005.HK",
            "--start-date",
            "20250101",
            "--end-date",
            "20251231",
            "--level",
            "1",
            "--mapping-date",
            "20251231",
        ]
    )
    assert industry_changes.command == "rqdata"
    assert industry_changes.rq_command == "mirror-hk-industry-changes"
    assert industry_changes.symbol == ["00005.HK"]
    assert industry_changes.start_date == "20250101"
    assert industry_changes.end_date == "20251231"
    assert industry_changes.level == "1"
    assert industry_changes.mapping_date == "20251231"
    assert callable(industry_changes.func)

    pit_fundamentals = parser.parse_args(
        [
            "rqdata",
            "build-hk-pit-fundamentals",
            "--asset-dir",
            "artifacts/assets/rqdata/hk/pit_financials/pit_demo",
            "--field-profile",
            "starter",
            "--field",
            "revenue",
            "--field",
            "net_profit",
            "--out",
            "artifacts/assets/fundamentals/pit_fundamentals.parquet",
            "--source-universe-by-date",
            "artifacts/assets/universe/hk_connect_full_by_date.csv",
            "--universe-by-date-out",
            "artifacts/assets/universe/hk_connect_full_research_by_date.csv",
            "--symbols-out",
            "artifacts/assets/universe/hk_connect_full_research_symbols.txt",
            "--keep-meta",
            "--duplicate-policy",
            "error",
            "--force",
        ]
    )
    assert pit_fundamentals.command == "rqdata"
    assert pit_fundamentals.rq_command == "build-hk-pit-fundamentals"
    assert pit_fundamentals.asset_dir == "artifacts/assets/rqdata/hk/pit_financials/pit_demo"
    assert pit_fundamentals.field_profile == ["starter"]
    assert pit_fundamentals.field == ["revenue", "net_profit"]
    assert pit_fundamentals.out == "artifacts/assets/fundamentals/pit_fundamentals.parquet"
    assert pit_fundamentals.source_universe_by_date == "artifacts/assets/universe/hk_connect_full_by_date.csv"
    assert pit_fundamentals.universe_by_date_out == "artifacts/assets/universe/hk_connect_full_research_by_date.csv"
    assert pit_fundamentals.symbols_out == "artifacts/assets/universe/hk_connect_full_research_symbols.txt"
    assert pit_fundamentals.keep_meta is True
    assert pit_fundamentals.duplicate_policy == "error"
    assert pit_fundamentals.force is True
    assert callable(pit_fundamentals.func)

    industry_labels = parser.parse_args(
        [
            "rqdata",
            "build-hk-industry-labels",
            "--asset-dir",
            "artifacts/assets/rqdata/hk/industry_changes/demo",
            "--source-universe-by-date",
            "artifacts/assets/universe/hk_connect_full_by_date.csv",
            "--frequency",
            "M",
            "--out",
            "artifacts/assets/industry/industry_labels_m.parquet",
            "--symbols-out",
            "artifacts/assets/industry/industry_symbols.txt",
            "--force",
        ]
    )
    assert industry_labels.command == "rqdata"
    assert industry_labels.rq_command == "build-hk-industry-labels"
    assert industry_labels.asset_dir == "artifacts/assets/rqdata/hk/industry_changes/demo"
    assert industry_labels.source_universe_by_date == "artifacts/assets/universe/hk_connect_full_by_date.csv"
    assert industry_labels.frequency == "M"
    assert industry_labels.out == "artifacts/assets/industry/industry_labels_m.parquet"
    assert industry_labels.symbols_out == "artifacts/assets/industry/industry_symbols.txt"
    assert industry_labels.force is True
    assert callable(industry_labels.func)

    pit_coverage = parser.parse_args(
        [
            "rqdata",
            "inspect-hk-pit-coverage",
            "--config",
            "configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml",
            "--mode",
            "trainable",
            "--min-symbols",
            "10",
            "--format",
            "json",
            "--out",
            "artifacts/reports/hk_pit_coverage.json",
        ]
    )
    assert pit_coverage.command == "rqdata"
    assert pit_coverage.rq_command == "inspect-hk-pit-coverage"
    assert pit_coverage.config == "configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml"
    assert pit_coverage.mode == "trainable"
    assert pit_coverage.min_symbols == 10
    assert pit_coverage.format == "json"
    assert pit_coverage.out == "artifacts/reports/hk_pit_coverage.json"
    assert callable(pit_coverage.func)


def test_cli_parses_init_config_universe_rqdata_info_and_tushare_verify():
    parser = cli.build_parser()

    init_cfg = parser.parse_args(
        ["init-config", "--market", "hk", "--out", "configs/presets/", "--force"]
    )
    assert init_cfg.command == "init-config"
    assert init_cfg.market == "hk"
    assert init_cfg.out == "configs/presets/"
    assert init_cfg.force is True
    assert callable(init_cfg.func)

    rq_info = parser.parse_args(
        [
            "rqdata",
            "info",
            "--config",
            "configs/presets/hk.yml",
            "--username",
            "user",
            "--password",
            "pass",
        ]
    )
    assert rq_info.command == "rqdata"
    assert rq_info.rq_command == "info"
    assert rq_info.config == "configs/presets/hk.yml"
    assert rq_info.username == "user"
    assert rq_info.password == "pass"
    assert callable(rq_info.func)

    hk_connect = parser.parse_args(
        [
            "universe",
            "hk-connect",
            "--config",
            "configs/presets/universe/hk_connect.yml",
            "--",
            "--mode",
            "daily",
            "--start-date",
            "20250101",
        ]
    )
    assert hk_connect.command == "universe"
    assert hk_connect.uni_command == "hk-connect"
    assert hk_connect.config == "configs/presets/universe/hk_connect.yml"
    assert hk_connect.args == ["--", "--mode", "daily", "--start-date", "20250101"]
    assert callable(hk_connect.func)

    hk_daily_assets = parser.parse_args(
        [
            "universe",
            "hk-daily-assets",
            "--config",
            "configs/presets/universe/hk_all_assets.yml",
            "--",
            "--start-date",
            "20000104",
            "--end-date",
            "20251231",
        ]
    )
    assert hk_daily_assets.command == "universe"
    assert hk_daily_assets.uni_command == "hk-daily-assets"
    assert hk_daily_assets.config == "configs/presets/universe/hk_all_assets.yml"
    assert hk_daily_assets.args == ["--", "--start-date", "20000104", "--end-date", "20251231"]
    assert callable(hk_daily_assets.func)

    index_components = parser.parse_args(
        [
            "universe",
            "index-components",
            "--",
            "--index-code",
            "000300.SH",
            "--month",
            "202501",
        ]
    )
    assert index_components.command == "universe"
    assert index_components.uni_command == "index-components"
    assert index_components.args == ["--", "--index-code", "000300.SH", "--month", "202501"]
    assert callable(index_components.func)

    verify_token = parser.parse_args(
        [
            "tushare",
            "verify-token",
            "--",
            "--test-symbol",
            "000001.SZ",
            "--verbose",
        ]
    )
    assert verify_token.command == "tushare"
    assert verify_token.tushare_command == "verify-token"
    assert verify_token.args == ["--", "--test-symbol", "000001.SZ", "--verbose"]
    assert callable(verify_token.func)


def test_cli_handle_holdings_passes_through_args(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(holdings_tool, "main", lambda argv: calls.append(argv))

    args = SimpleNamespace(
        config="hk",
        run_dir="artifacts/runs/demo",
        top_k=10,
        as_of="20260131",
        source="live",
        format="json",
        out="artifacts/exports/holdings.json",
    )
    assert cli._handle_holdings(args) == 0
    assert calls == [
        [
            "--config",
            "hk",
            "--run-dir",
            "artifacts/runs/demo",
            "--top-k",
            "10",
            "--as-of",
            "20260131",
            "--source",
            "live",
            "--format",
            "json",
            "--out",
            "artifacts/exports/holdings.json",
        ]
    ]


def test_cli_handle_alloc_passes_through_args(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(alloc_tool, "main", lambda argv: calls.append(argv))

    args = SimpleNamespace(
        config="hk",
        run_dir="artifacts/runs/demo",
        positions_file="artifacts/runs/demo/positions.csv",
        top_k=5,
        as_of="20260131",
        source="live",
        side="long",
        top_n=20,
        cash=1_000_000.0,
        buffer_bps=50.0,
        price_field="close",
        price_lookback_days=30,
        username="user",
        password="pass",
        format="json",
        out="artifacts/exports/alloc.json",
    )
    assert cli._handle_alloc(args) == 0
    assert calls == [
        [
            "--config",
            "hk",
            "--run-dir",
            "artifacts/runs/demo",
            "--positions-file",
            "artifacts/runs/demo/positions.csv",
            "--top-k",
            "5",
            "--as-of",
            "20260131",
            "--source",
            "live",
            "--side",
            "long",
            "--top-n",
            "20",
            "--cash",
            "1000000.0",
            "--buffer-bps",
            "50.0",
            "--price-field",
            "close",
            "--price-lookback-days",
            "30",
            "--username",
            "user",
            "--password",
            "pass",
            "--format",
            "json",
            "--out",
            "artifacts/exports/alloc.json",
        ]
    ]


def test_cli_handle_grid_passes_through_args(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(grid_tool, "main", lambda argv: calls.append(argv))

    args = SimpleNamespace(
        config="hk",
        top_k=["5,10", "20"],
        cost_bps=["15,25"],
        buffer_exit=["6,8"],
        buffer_entry=["3"],
        output="artifacts/runs/grid.csv",
        run_name_prefix="hk_grid",
        log_level="DEBUG",
        args=["--extra", "1"],
    )
    assert cli._handle_grid(args) == 0
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
            "--extra",
            "1",
        ]
    ]


def test_cli_handle_summarize_passes_namespace_to_runner(monkeypatch):
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(summarize_tool, "run", lambda args: calls.append(args))

    args = SimpleNamespace(
        runs_dir=["artifacts/runs"],
        output="artifacts/runs/runs_summary.csv",
        run_name_prefix=["hk_sel_q_benchmark_"],
        since="2026-01-01",
        latest_n=5,
        short_sample_periods=24,
        high_turnover_threshold=0.7,
        score_drawdown_weight=0.5,
        score_cost_weight=10.0,
        exclude_flag_short_sample=False,
        exclude_flag_high_turnover=False,
        exclude_flag_negative_long_short=False,
        exclude_flag_relative_end_date=False,
        exclude_flag_constant_prediction=True,
        exclude_flag_zero_feature_importance=True,
        sort_by="score",
        log_level="INFO",
    )

    assert cli._handle_summarize(args) == 0
    assert calls == [args]


def test_cli_handle_sweep_linear_passes_through_args(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(sweep_tool, "main", lambda argv: calls.append(argv))

    args = SimpleNamespace(
        sweep_config="configs/experiments/sweeps/hk_selected__linear_a.yml",
        config="configs/experiments/baseline/hk_selected.yml",
        run_name_prefix="hk_sel_",
        sweeps_dir="artifacts/sweeps",
        tag="exp_1",
        runs_dir="artifacts/runs",
        ridge_alpha=["0.01,0.1", "1"],
        elasticnet_alpha=["0.01,0.1"],
        elasticnet_l1_ratio=["0.1,0.5"],
        skip_ridge=False,
        skip_elasticnet=True,
        dry_run=True,
        continue_on_error=True,
        skip_summarize=False,
        summary_output="artifacts/sweeps/exp_1/runs_summary.csv",
        log_level="DEBUG",
        args=None,
    )
    assert cli._handle_sweep_linear(args) == 0
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
