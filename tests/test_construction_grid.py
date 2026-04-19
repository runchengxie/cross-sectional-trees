import json

import pandas as pd
import pytest
import yaml

from csml.research import construction_grid


def _scored_data() -> pd.DataFrame:
    dates = pd.to_datetime(["2020-01-03", "2020-01-10", "2020-01-17", "2020-01-24"])
    symbols = ["AAA", "BBB", "CCC"]
    rows = []
    for d_idx, trade_date in enumerate(dates):
        for s_idx, symbol in enumerate(symbols):
            score = float(3 - s_idx + d_idx * 0.01)
            rows.append(
                {
                    "trade_date": trade_date,
                    "symbol": symbol,
                    "close": 100.0 + d_idx * (3 - s_idx) + s_idx,
                    "future_return": 0.02 * (3 - s_idx),
                    "signal_eval": score,
                    "signal_backtest": score,
                    "sector_beta": float(s_idx),
                    "is_tradable": True,
                }
            )
    return pd.DataFrame(rows)


def _write_summary(run_dir, scored_file):
    dates = [d.strftime("%Y%m%d") for d in sorted(_scored_data()["trade_date"].unique())]
    payload = {
        "run": {"output_dir": str(run_dir)},
        "data": {"min_symbols_per_date": 2, "price_col": "close"},
        "label": {"target_col": "future_return", "horizon_days": 5, "shift_days": 0},
        "eval": {
            "rebalance_frequency": "W",
            "rebalance_dates": dates,
            "scored_file": str(scored_file),
            "scored_signal_col": "signal_eval",
            "scored_signal_backtest_col": "signal_backtest",
        },
        "backtest": {
            "enabled": True,
            "rebalance_frequency": "W",
            "rebalance_dates": dates,
            "shift_days": 0,
            "trading_days_per_year": 252,
            "exit_price_policy": "strict",
            "exit_fallback_policy": "ffill",
            "tradable_col": "is_tradable",
        },
    }
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
    return summary_path


def test_construction_grid_reuses_existing_scores(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    scored_file = run_dir / "eval_scored.parquet"
    _scored_data().to_parquet(scored_file)
    summary_path = _write_summary(run_dir, scored_file)

    benchmark = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-01-10", "2020-01-17", "2020-01-24"]),
            "benchmark_return": [0.001, 0.001, 0.001],
        }
    )
    benchmark_path = tmp_path / "benchmark.csv"
    benchmark.to_csv(benchmark_path, index=False)

    cfg = {
        "construction_grid": {
            "summary_file": str(summary_path),
            "output_csv": str(tmp_path / "grid.csv"),
            "variants": [
                {
                    "name": "k1_equal",
                    "top_k": 1,
                    "cost_bps": 10,
                    "weighting": "equal",
                    "benchmark_name": "bench",
                    "benchmark_returns_file": str(benchmark_path),
                },
                {
                    "name": "neutralized",
                    "top_k": 2,
                    "cost_bps": 20,
                    "weighting": "signal",
                    "score_postprocess": {
                        "method": "neutralize",
                        "columns": ["sector_beta"],
                        "min_obs": 2,
                    },
                },
            ],
        }
    }
    config_path = tmp_path / "construction.yml"
    config_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    rows = construction_grid.run(
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

    assert {row["variant"] for row in rows} == {"k1_equal", "neutralized"}
    assert {row["status"] for row in rows} == {"ok"}
    row = next(item for item in rows if item["variant"] == "k1_equal")
    assert row["information_ratio"] is not None
    assert row["backtest_avg_cost_drag"] is not None
    assert (tmp_path / "grid.csv").exists()


def test_construction_grid_fails_on_missing_required_column(tmp_path):
    scored_file = tmp_path / "bad.parquet"
    _scored_data().drop(columns=["close"]).to_parquet(scored_file)
    cfg = {
        "construction_grid": {
            "scored_file": str(scored_file),
            "variants": [{"name": "k1", "top_k": 1}],
        }
    }

    with pytest.raises(SystemExit, match="Missing required columns"):
        construction_grid.build_construction_grid(cfg, config_dir=tmp_path)

