from types import SimpleNamespace

from csml import cli
from csml.config_utils import resolve_pipeline_config
from csml.project_tools import alloc as alloc_tool
from csml.project_tools import holdings as holdings_tool
from csml.project_tools import run_grid as grid_tool
from csml.project_tools import linear_sweep as sweep_tool


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
            "config/sweeps/hk_selected__linear_a.yml",
            "--config",
            "config/hk_selected__baseline.yml",
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
    assert sweep.sweep_config == "config/sweeps/hk_selected__linear_a.yml"
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
        ]
    )
    assert summarize.command == "summarize"
    assert summarize.runs_dir == ["artifacts/runs"]
    assert summarize.run_name_prefix == ["hk_grid"]
    assert summarize.since == "2026-01-01"
    assert summarize.latest_n == 3
    assert summarize.short_sample_periods == 24

    backup = parser.parse_args(
        [
            "backup-data",
            "--out-root",
            "artifacts/snapshots",
            "--name",
            "hk_frozen",
            "--config",
            "config/hk.yml",
            "--include-path",
            "artifacts/assets/universe",
            "--skip-missing",
        ]
    )
    assert backup.command == "backup-data"
    assert backup.out_root == "artifacts/snapshots"
    assert backup.name == "hk_frozen"
    assert backup.config == ["config/hk.yml"]
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
            "config/hk.yml",
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
    assert export_instruments.config == "config/hk.yml"
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
            "config/hk.yml",
            "--field-profile",
            "full",
            "--fields-file",
            "config/rqdata_assets/hk_financial_fields_starter.txt",
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
    assert pit.config == "config/hk.yml"
    assert pit.field_profile == ["full"]
    assert pit.fields_file == ["config/rqdata_assets/hk_financial_fields_starter.txt"]
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


def test_cli_parses_init_config_universe_rqdata_info_and_tushare_verify():
    parser = cli.build_parser()

    init_cfg = parser.parse_args(
        ["init-config", "--market", "hk", "--out", "config/", "--force"]
    )
    assert init_cfg.command == "init-config"
    assert init_cfg.market == "hk"
    assert init_cfg.out == "config/"
    assert init_cfg.force is True
    assert callable(init_cfg.func)

    rq_info = parser.parse_args(
        [
            "rqdata",
            "info",
            "--config",
            "config/hk.yml",
            "--username",
            "user",
            "--password",
            "pass",
        ]
    )
    assert rq_info.command == "rqdata"
    assert rq_info.rq_command == "info"
    assert rq_info.config == "config/hk.yml"
    assert rq_info.username == "user"
    assert rq_info.password == "pass"
    assert callable(rq_info.func)

    hk_connect = parser.parse_args(
        [
            "universe",
            "hk-connect",
            "--config",
            "config/universe.hk_connect.yml",
            "--",
            "--mode",
            "daily",
            "--start-date",
            "20250101",
        ]
    )
    assert hk_connect.command == "universe"
    assert hk_connect.uni_command == "hk-connect"
    assert hk_connect.config == "config/universe.hk_connect.yml"
    assert hk_connect.args == ["--", "--mode", "daily", "--start-date", "20250101"]
    assert callable(hk_connect.func)

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


def test_cli_handle_sweep_linear_passes_through_args(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(sweep_tool, "main", lambda argv: calls.append(argv))

    args = SimpleNamespace(
        sweep_config="config/sweeps/hk_selected__linear_a.yml",
        config="config/hk_selected__baseline.yml",
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
            "config/sweeps/hk_selected__linear_a.yml",
            "--config",
            "config/hk_selected__baseline.yml",
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
