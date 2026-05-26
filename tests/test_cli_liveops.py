from cstree import cli
from cstree.liveops import (
    alloc as alloc_tool,
    alloc_hk as alloc_hk_tool,
    export_targets as export_targets_tool,
    holdings as holdings_tool,
    snapshot as snapshot_tool,
)


def test_cli_parses_liveops_commands():
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

    alloc_hk = parser.parse_args(
        ["alloc-hk", "--config", "default", "--method", "custom", "--fail-on-quality", "warning"]
    )
    assert alloc_hk.command == "alloc-hk"
    assert alloc_hk.method == "custom"
    assert alloc_hk.top_n == 20
    assert alloc_hk.source == "auto"
    assert alloc_hk.side == "long"
    assert alloc_hk.scenario_capital is None
    assert alloc_hk.scenario_top_n is None
    assert alloc_hk.fail_on_quality == "warning"

    alloc_hk_xlsx = parser.parse_args(
        ["alloc-hk", "--config", "default", "--format", "xlsx", "--out", "a.xlsx"]
    )
    assert alloc_hk_xlsx.command == "alloc-hk"
    assert alloc_hk_xlsx.format == "xlsx"
    assert alloc_hk_xlsx.out == "a.xlsx"

    alloc_hk_grid = parser.parse_args(
        [
            "alloc-hk",
            "--config",
            "default",
            "--scenario-capital",
            "100000,200000",
            "--scenario-top-n",
            "5",
            "--scenario-top-n",
            "10",
        ]
    )
    assert alloc_hk_grid.command == "alloc-hk"
    assert alloc_hk_grid.scenario_capital == ["100000,200000"]
    assert alloc_hk_grid.scenario_top_n == ["5", "10"]

    alloc_hk_false_switches = parser.parse_args(
        [
            "alloc-hk",
            "--config",
            "default",
            "--allow-non-stock-connect",
            "--no-secondary-fill",
            "--allow-high-valuation",
        ]
    )
    assert alloc_hk_false_switches.require_stock_connect is False
    assert alloc_hk_false_switches.secondary_fill_enabled is False
    assert alloc_hk_false_switches.avoid_high_valuation is False

    snapshot = parser.parse_args(
        ["snapshot", "--config", "default", "--skip-run", "--fail-on-quality", "error"]
    )
    assert snapshot.command == "snapshot"
    assert snapshot.skip_run is True
    assert snapshot.fail_on_quality == "error"

    export_targets = parser.parse_args(
        ["export-targets", "--run-dir", "artifacts/live_runs/demo", "--out", "targets.json"]
    )
    assert export_targets.command == "export-targets"
    assert export_targets.target_source == "cross-sectional-trees"
    assert export_targets.target_gross_exposure == 1.0
    assert export_targets.out == "targets.json"


def test_cli_main_holdings_passes_through_args(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(holdings_tool, "main", lambda argv: calls.append(argv))

    assert (
        cli.main(
            [
                "holdings",
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
        )
        == 0
    )
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


def test_cli_main_alloc_passes_through_args(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(alloc_tool, "main", lambda argv: calls.append(argv))

    assert (
        cli.main(
            [
                "alloc",
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
        )
        == 0
    )
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


def test_cli_main_alloc_hk_passes_through_args(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(alloc_hk_tool, "main", lambda argv: calls.append(argv))

    assert (
        cli.main(
            [
                "alloc-hk",
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
                "--method",
                "custom",
                "--require-stock-connect",
                "--history-years",
                "3",
                "--roll-window",
                "252",
                "--sell-quantile",
                "0.95",
                "--extreme-quantile",
                "0.99",
                "--secondary-fill",
                "--avoid-high-valuation",
                "--avoid-high-valuation-strict",
                "--allow-over-alloc",
                "--max-steps",
                "123",
                "--max-over-alloc-ratio",
                "0.002",
                "--max-over-alloc-amount",
                "1500.0",
                "--max-over-alloc-lots-per-ticker",
                "1",
                "--cash-buffer-ratio",
                "0.003",
                "--cash-buffer-amount",
                "2000.0",
                "--estimated-fee-per-order",
                "30.0",
                "--username",
                "user",
                "--password",
                "pass",
                "--fail-on-quality",
                "warning",
                "--format",
                "json",
                "--out",
                "artifacts/exports/alloc_hk.json",
            ]
        )
        == 0
    )
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
            "--method",
            "custom",
            "--require-stock-connect",
            "--history-years",
            "3",
            "--roll-window",
            "252",
            "--sell-quantile",
            "0.95",
            "--extreme-quantile",
            "0.99",
            "--secondary-fill",
            "--avoid-high-valuation",
            "--avoid-high-valuation-strict",
            "--allow-over-alloc",
            "--max-steps",
            "123",
            "--max-over-alloc-ratio",
            "0.002",
            "--max-over-alloc-amount",
            "1500.0",
            "--max-over-alloc-lots-per-ticker",
            "1",
            "--cash-buffer-ratio",
            "0.003",
            "--cash-buffer-amount",
            "2000.0",
            "--estimated-fee-per-order",
            "30.0",
            "--username",
            "user",
            "--password",
            "pass",
            "--fail-on-quality",
            "warning",
            "--format",
            "json",
            "--out",
            "artifacts/exports/alloc_hk.json",
        ]
    ]


def test_cli_main_alloc_hk_passes_false_switches(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(alloc_hk_tool, "main", lambda argv: calls.append(argv))

    assert (
        cli.main(
            [
                "alloc-hk",
                "--config",
                "hk",
                "--allow-non-stock-connect",
                "--no-secondary-fill",
                "--allow-high-valuation",
            ]
        )
        == 0
    )
    assert calls == [
        [
            "--config",
            "hk",
            "--as-of",
            "t-1",
            "--source",
            "auto",
            "--side",
            "long",
            "--top-n",
            "20",
            "--allow-non-stock-connect",
            "--no-secondary-fill",
            "--allow-high-valuation",
            "--format",
            "text",
        ]
    ]


def test_cli_main_snapshot_passes_through_args(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(snapshot_tool, "main", lambda argv: calls.append(argv))

    assert (
        cli.main(
            [
                "snapshot",
                "--config",
                "hk",
                "--run-dir",
                "artifacts/runs/demo",
                "--as-of",
                "20260131",
                "--skip-run",
                "--top-k",
                "15",
                "--fail-on-quality",
                "warning",
                "--format",
                "csv",
                "--out",
                "artifacts/live/snapshot.csv",
            ]
        )
        == 0
    )
    assert calls == [
        [
            "--config",
            "hk",
            "--run-dir",
            "artifacts/runs/demo",
            "--as-of",
            "20260131",
            "--skip-run",
            "--top-k",
            "15",
            "--fail-on-quality",
            "warning",
            "--format",
            "csv",
            "--out",
            "artifacts/live/snapshot.csv",
        ]
    ]


def test_cli_main_export_targets_passes_through_args(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(export_targets_tool, "main", lambda argv: calls.append(argv))

    assert (
        cli.main(
            [
                "export-targets",
                "--config",
                "hk",
                "--run-dir",
                "artifacts/live_runs/demo",
                "--artifacts-root",
                "/data/cstree",
                "--top-k",
                "15",
                "--as-of",
                "20260526",
                "--target-source",
                "hk-live",
                "--target-gross-exposure",
                "0.8",
                "--fail-on-quality",
                "warning",
                "--out",
                "artifacts/exports/targets.json",
                "--lineage-out",
                "artifacts/exports/targets.lineage.json",
            ]
        )
        == 0
    )
    assert calls == [
        [
            "--config",
            "hk",
            "--run-dir",
            "artifacts/live_runs/demo",
            "--artifacts-root",
            "/data/cstree",
            "--top-k",
            "15",
            "--as-of",
            "20260526",
            "--target-source",
            "hk-live",
            "--target-gross-exposure",
            "0.8",
            "--fail-on-quality",
            "warning",
            "--out",
            "artifacts/exports/targets.json",
            "--lineage-out",
            "artifacts/exports/targets.lineage.json",
        ]
    ]
