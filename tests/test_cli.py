from csxgb import cli


def test_cli_parses_run_command():
    parser = cli.build_parser()
    args = parser.parse_args(["run", "--config", "default"])
    assert args.command == "run"
    assert args.config == "default"
    assert callable(args.func)


def test_cli_parses_holdings_snapshot_grid_summarize():
    parser = cli.build_parser()

    holdings = parser.parse_args(["holdings", "--config", "default"])
    assert holdings.command == "holdings"
    assert holdings.source == "auto"
    assert holdings.format == "text"

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
