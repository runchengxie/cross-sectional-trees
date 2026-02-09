from types import SimpleNamespace

from csml import cli
from csml.project_tools import alloc as alloc_tool
from csml.project_tools import holdings as holdings_tool
from csml.project_tools import run_grid as grid_tool


def test_cli_parses_run_command():
    parser = cli.build_parser()
    args = parser.parse_args(["run", "--config", "default"])
    assert args.command == "run"
    assert args.config == "default"
    assert callable(args.func)


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

    grid = parser.parse_args(["grid", "--config", "default", "--top-k", "5,10", "--cost-bps", "10,20"])
    assert grid.command == "grid"
    assert grid.top_k == ["5,10"]
    assert grid.cost_bps == ["10,20"]

    summarize = parser.parse_args(
        [
            "summarize",
            "--runs-dir",
            "out/runs",
            "--run-name-prefix",
            "hk_grid",
            "--since",
            "2026-01-01",
            "--latest-n",
            "3",
        ]
    )
    assert summarize.command == "summarize"
    assert summarize.runs_dir == ["out/runs"]
    assert summarize.run_name_prefix == ["hk_grid"]
    assert summarize.since == "2026-01-01"
    assert summarize.latest_n == 3
    assert summarize.short_sample_periods == 24


def test_cli_parses_rqdata_quota_pretty():
    parser = cli.build_parser()
    args = parser.parse_args(["rqdata", "quota", "--pretty"])
    assert args.command == "rqdata"
    assert args.rq_command == "quota"
    assert args.pretty is True


def test_cli_handle_holdings_passes_through_args(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(holdings_tool, "main", lambda argv: calls.append(argv))

    args = SimpleNamespace(
        config="hk",
        run_dir="out/runs/demo",
        top_k=10,
        as_of="20260131",
        source="live",
        format="json",
        out="out/holdings.json",
    )
    assert cli._handle_holdings(args) == 0
    assert calls == [
        [
            "--config",
            "hk",
            "--run-dir",
            "out/runs/demo",
            "--top-k",
            "10",
            "--as-of",
            "20260131",
            "--source",
            "live",
            "--format",
            "json",
            "--out",
            "out/holdings.json",
        ]
    ]


def test_cli_handle_alloc_passes_through_args(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(alloc_tool, "main", lambda argv: calls.append(argv))

    args = SimpleNamespace(
        config="hk",
        run_dir="out/runs/demo",
        positions_file="out/runs/demo/positions.csv",
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
        out="out/alloc.json",
    )
    assert cli._handle_alloc(args) == 0
    assert calls == [
        [
            "--config",
            "hk",
            "--run-dir",
            "out/runs/demo",
            "--positions-file",
            "out/runs/demo/positions.csv",
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
            "out/alloc.json",
        ]
    ]


def test_cli_handle_grid_passes_through_args(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(grid_tool, "main", lambda argv: calls.append(argv))

    args = SimpleNamespace(
        config="hk",
        top_k=["5,10", "20"],
        cost_bps=["15,25"],
        output="out/runs/grid.csv",
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
            "--output",
            "out/runs/grid.csv",
            "--run-name-prefix",
            "hk_grid",
            "--log-level",
            "DEBUG",
            "--extra",
            "1",
        ]
    ]
