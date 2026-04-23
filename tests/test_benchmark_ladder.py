import pandas as pd
import yaml

from cstree.research import benchmark_ladder


def _write_returns(path, column, dates, values):
    pd.DataFrame({"date": pd.to_datetime(dates), column: values}).to_csv(path, index=False)


def test_benchmark_ladder_reports_ok_missing_and_incompatible(tmp_path):
    strategy = tmp_path / "strategy.csv"
    primary = tmp_path / "primary.csv"
    no_overlap = tmp_path / "no_overlap.csv"
    attribution = tmp_path / "attribution.csv"
    _write_returns(
        strategy,
        "strategy_return",
        ["2020-01-31", "2020-02-29", "2020-03-31"],
        [0.02, 0.01, -0.01],
    )
    _write_returns(
        primary,
        "benchmark_return",
        ["2020-01-31", "2020-02-29", "2020-03-31"],
        [0.01, 0.00, -0.02],
    )
    _write_returns(no_overlap, "benchmark_return", ["2021-01-31"], [0.01])
    attribution.write_text("bucket,active_return\nsector,0.01\n", encoding="utf-8")

    cfg = {
        "benchmark_ladder": {
            "strategy_returns_file": str(strategy),
            "periods_per_year": 12,
            "primary_benchmark": {
                "name": "primary",
                "returns_file": str(primary),
                "attribution_file": str(attribution),
            },
            "comparisons": [
                {"name": "missing", "source_type": "universe_equal_weight"},
                {"name": "no_overlap", "returns_file": str(no_overlap)},
            ],
        }
    }

    rows = benchmark_ladder.build_benchmark_ladder(cfg, config_dir=tmp_path)

    primary_row = next(row for row in rows if row["benchmark_name"] == "primary")
    missing_row = next(row for row in rows if row["benchmark_name"] == "missing")
    no_overlap_row = next(row for row in rows if row["benchmark_name"] == "no_overlap")
    assert primary_row["status"] == "ok"
    assert primary_row["attribution_available"] is True
    assert primary_row["aligned_periods"] == 3
    assert primary_row["information_ratio"] is not None
    assert missing_row["status"] == "unavailable"
    assert no_overlap_row["status"] == "incompatible"


def test_benchmark_ladder_cli_writes_csv(tmp_path):
    strategy = tmp_path / "strategy.csv"
    primary = tmp_path / "primary.csv"
    output = tmp_path / "ladder.csv"
    _write_returns(strategy, "strategy_return", ["2020-01-31", "2020-02-29"], [0.02, 0.01])
    _write_returns(primary, "benchmark_return", ["2020-01-31", "2020-02-29"], [0.01, 0.00])
    config_path = tmp_path / "ladder.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "benchmark_ladder": {
                    "strategy_returns_file": str(strategy),
                    "primary_benchmark": {"name": "primary", "returns_file": str(primary)},
                    "output_csv": str(output),
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    benchmark_ladder.run(
        type(
            "Args",
            (),
            {
                "config": str(config_path),
                "output": None,
                "output_json": None,
                "log_level": "INFO",
            },
        )()
    )

    assert output.exists()
    rows = pd.read_csv(output)
    assert rows.iloc[0]["benchmark_name"] == "primary"
