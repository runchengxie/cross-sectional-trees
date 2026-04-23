import json
from pathlib import Path

import pandas as pd
import pytest

from cstree.research.hk_monthly_run_compare import main


def _write_series(path: Path, *, dates: pd.DatetimeIndex, column: str, values: list[float]) -> None:
    pd.DataFrame({"trade_date": dates.strftime("%Y-%m-%d"), column: values}).to_csv(path, index=False)


def _write_run(
    root: Path,
    *,
    label: str,
    strategy_return: float,
    benchmark_return: float,
    turnover_base: float,
    ic_base: float,
    quality_active: float,
    industry_name: str,
) -> Path:
    run_dir = root / label
    run_dir.mkdir(parents=True, exist_ok=True)
    dates = pd.date_range("2024-04-30", periods=24, freq="ME")
    strategy_values = [strategy_return + 0.002 * ((idx % 4) - 1.5) for idx in range(len(dates))]
    benchmark_values = [benchmark_return + 0.001 * ((idx % 3) - 1.0) for idx in range(len(dates))]
    _write_series(
        run_dir / "backtest_net_oos.csv",
        dates=dates,
        column="net_return",
        values=strategy_values,
    )
    _write_series(
        run_dir / "backtest_benchmark_oos.csv",
        dates=dates,
        column="benchmark_return",
        values=benchmark_values,
    )
    _write_series(
        run_dir / "backtest_turnover_oos.csv",
        dates=dates,
        column="turnover",
        values=[turnover_base + 0.001 * idx for idx in range(len(dates))],
    )
    _write_series(
        run_dir / "ic_oos.csv",
        dates=dates,
        column="ic",
        values=[ic_base + 0.0005 * idx for idx in range(len(dates))],
    )
    pd.DataFrame(
        {
            "rebalance_date": dates.strftime("%Y%m%d"),
            "entry_date": dates.strftime("%Y-%m-%d"),
            "quality_active_net_vs_equal": [quality_active] * len(dates),
            "momentum_active_net_vs_equal": [0.2] * len(dates),
            "low_vol_active_net_vs_equal": [0.1] * len(dates),
            "industry_top_1_name": [industry_name] * len(dates),
            "industry_top_1_active": [0.08] * len(dates),
            "industry_top_1_portfolio_net_weight": [0.20] * len(dates),
        }
    ).to_csv(run_dir / "backtest_active_exposure_summary_oos.csv", index=False)
    positions_rows = []
    for date in dates:
        for idx in range(15):
            positions_rows.append(
                {
                    "rebalance_date": date.strftime("%Y%m%d"),
                    "entry_date": date.strftime("%Y-%m-%d"),
                    "symbol": f"{idx:05d}.HK",
                    "weight": 1.0 / 15.0,
                }
            )
    pd.DataFrame(positions_rows).to_csv(run_dir / "positions_by_rebalance_oos.csv", index=False)
    summary = {
        "run": {"name": label},
        "final_oos": {
            "enabled": True,
            "backtest": {
                "stats": {"periods_per_year": 12.0},
                "exposure": {
                    "active_summary_file": str((run_dir / "backtest_active_exposure_summary_oos.csv").resolve())
                },
            },
            "positions": {
                "by_rebalance_file": str((run_dir / "positions_by_rebalance_oos.csv").resolve())
            },
        },
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return run_dir


def test_hk_monthly_run_compare_writes_window_and_attribution_outputs(tmp_path):
    main_run = _write_run(
        tmp_path,
        label="main_run",
        strategy_return=0.03,
        benchmark_return=0.01,
        turnover_base=0.12,
        ic_base=0.05,
        quality_active=0.45,
        industry_name="Tech",
    )
    comp_run = _write_run(
        tmp_path,
        label="comp_run",
        strategy_return=0.025,
        benchmark_return=0.012,
        turnover_base=0.16,
        ic_base=0.03,
        quality_active=0.20,
        industry_name="Banks",
    )

    out_dir = tmp_path / "compare"
    result = main(
        [
            "--run",
            f"main={main_run}",
            "--run",
            f"comp={comp_run}",
            "--out-dir",
            str(out_dir),
        ]
    )
    assert result == 0

    window_metrics = pd.read_csv(out_dir / "window_metrics.csv")
    attribution = pd.read_csv(out_dir / "attribution_summary.csv")
    payload = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))

    assert sorted(window_metrics["window"].unique().tolist()) == ["12m", "24m", "6m", "full"]
    assert set(window_metrics["label"]) == {"main", "comp"}
    main_full = window_metrics[
        (window_metrics["label"] == "main") & (window_metrics["window"] == "full")
    ].iloc[0]
    comp_full = window_metrics[
        (window_metrics["label"] == "comp") & (window_metrics["window"] == "full")
    ].iloc[0]
    assert main_full["sharpe"] > comp_full["sharpe"]
    assert main_full["active_ir"] > comp_full["active_ir"]
    assert main_full["ic_mean"] > comp_full["ic_mean"]

    main_attr = attribution[
        (attribution["label"] == "main") & (attribution["window"] == "full")
    ].iloc[0]
    assert main_attr["industry_top1_name_mode"] == "Tech"
    assert main_attr["quality_active_abs_mean"] == pytest.approx(0.45)
    assert main_attr["avg_names_per_rebalance"] == pytest.approx(15.0)

    assert payload["winners"]["full"]["sharpe"] == "main"
    assert payload["winners"]["full"]["active_ir"] == "main"
