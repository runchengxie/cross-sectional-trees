from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from .support import _build_rebalance_diff, save_frame, save_parquet, save_series


def write_run_artifacts(*, context: Mapping[str, Any]) -> dict[str, Any]:
    ctx = context
    run_dir = ctx["run_dir"]

    artifacts: dict[str, Any] = {
        "rolling_ic_files": {},
        "rolling_sharpe_files": {},
        "rolling_ic_oos_files": {},
        "rolling_sharpe_oos_files": {},
        "bucket_ic_path": None,
        "bucket_ic_oos_path": None,
        "walk_forward_importance_path": None,
        "walk_forward_feature_stability_path": None,
        "dataset_path": None,
        "eval_scored_path": None,
        "feature_importance_path": None,
        "positions_by_rebalance_path": None,
        "positions_current_path": None,
        "positions_by_rebalance_oos_path": None,
        "positions_current_oos_path": None,
        "positions_by_rebalance_live_path": None,
        "positions_current_live_path": None,
        "positions_diff_path": None,
        "positions_diff_oos_path": None,
        "positions_diff_live_path": None,
        "live_positions_file": None,
        "live_current_file": None,
    }

    if ctx["SAVE_DATASET"]:
        artifacts["dataset_path"] = run_dir / "dataset.parquet"
        save_parquet(ctx["dataset"].as_multiindex(), artifacts["dataset_path"])
    if (
        ctx["SAVE_SCORED_ARTIFACT"]
        and ctx["eval_scored_data"] is not None
        and not ctx["eval_scored_data"].empty
    ):
        artifacts["eval_scored_path"] = run_dir / "eval_scored.parquet"
        save_parquet(ctx["eval_scored_data"], artifacts["eval_scored_path"])

    artifacts["feature_importance_path"] = run_dir / "feature_importance.csv"
    save_frame(ctx["importance_df"], artifacts["feature_importance_path"])
    if not ctx["walk_forward_importance_df"].empty:
        artifacts["walk_forward_importance_path"] = (
            run_dir / "walk_forward_feature_importance.csv"
        )
        save_frame(
            ctx["walk_forward_importance_df"],
            artifacts["walk_forward_importance_path"],
        )
    if not ctx["walk_forward_feature_stability_df"].empty:
        artifacts["walk_forward_feature_stability_path"] = (
            run_dir / "walk_forward_feature_stability.csv"
        )
        save_frame(
            ctx["walk_forward_feature_stability_df"],
            artifacts["walk_forward_feature_stability_path"],
        )

    save_series(ctx["ic_series"], run_dir / "ic_test.csv", value_name="ic")
    save_series(
        ctx["pearson_ic_series"],
        run_dir / "ic_pearson_test.csv",
        value_name="ic",
    )
    if ctx["REPORT_TRAIN_IC"]:
        save_series(ctx["train_ic_series"], run_dir / "ic_train.csv", value_name="ic")
        save_series(
            ctx["train_pearson_ic_series"],
            run_dir / "ic_pearson_train.csv",
            value_name="ic",
        )
    if not ctx["quantile_ts"].empty:
        save_frame(ctx["quantile_ts"].reset_index(), run_dir / "quantile_returns.csv")
    save_series(
        ctx["turnover_series"],
        run_dir / "turnover_eval.csv",
        value_name="turnover",
    )
    if ctx["bucket_ic_records"]:
        artifacts["bucket_ic_path"] = run_dir / "bucket_ic.csv"
        save_frame(pd.DataFrame(ctx["bucket_ic_records"]), artifacts["bucket_ic_path"])

    if ctx["rolling_ic_results"]:
        for label, frame in ctx["rolling_ic_results"].items():
            if frame.empty:
                continue
            out = frame.copy()
            out.index.name = "trade_date"
            path = run_dir / f"ic_rolling_{label}.csv"
            save_frame(out.reset_index(), path)
            artifacts["rolling_ic_files"][label] = str(path)

    if ctx["rolling_sharpe_results"]:
        for label, frame in ctx["rolling_sharpe_results"].items():
            if frame.empty:
                continue
            out = frame.copy()
            out.index.name = "trade_date"
            path = run_dir / f"backtest_rolling_sharpe_{label}.csv"
            save_frame(out.reset_index(), path)
            artifacts["rolling_sharpe_files"][label] = str(path)

    if ctx["final_oos_eval"] is not None:
        save_series(ctx["ic_series_oos"], run_dir / "ic_oos.csv", value_name="ic")
        save_series(
            ctx["pearson_ic_series_oos"],
            run_dir / "ic_pearson_oos.csv",
            value_name="ic",
        )
        if not ctx["quantile_ts_oos"].empty:
            save_frame(
                ctx["quantile_ts_oos"].reset_index(),
                run_dir / "quantile_returns_oos.csv",
            )
        save_series(
            ctx["turnover_series_oos"],
            run_dir / "turnover_eval_oos.csv",
            value_name="turnover",
        )
        if ctx["bucket_ic_records_oos"]:
            artifacts["bucket_ic_oos_path"] = run_dir / "bucket_ic_oos.csv"
            save_frame(
                pd.DataFrame(ctx["bucket_ic_records_oos"]),
                artifacts["bucket_ic_oos_path"],
            )
        if ctx["rolling_ic_oos_results"]:
            for label, frame in ctx["rolling_ic_oos_results"].items():
                if frame.empty:
                    continue
                out = frame.copy()
                out.index.name = "trade_date"
                path = run_dir / f"ic_rolling_{label}_oos.csv"
                save_frame(out.reset_index(), path)
                artifacts["rolling_ic_oos_files"][label] = str(path)
        if ctx["rolling_sharpe_oos_results"]:
            for label, frame in ctx["rolling_sharpe_oos_results"].items():
                if frame.empty:
                    continue
                out = frame.copy()
                out.index.name = "trade_date"
                path = run_dir / f"backtest_rolling_sharpe_{label}_oos.csv"
                save_frame(out.reset_index(), path)
                artifacts["rolling_sharpe_oos_files"][label] = str(path)

    if not ctx["dropped_date_counts"].empty:
        save_frame(
            ctx["dropped_date_counts"].rename("symbol_count").reset_index(),
            run_dir / "dropped_dates.csv",
        )

    if ctx["bt_stats"] is not None:
        save_series(
            ctx["bt_net_series"],
            run_dir / "backtest_net.csv",
            value_name="net_return",
        )
        save_series(
            ctx["bt_gross_series"],
            run_dir / "backtest_gross.csv",
            value_name="gross_return",
        )
        save_series(
            ctx["bt_turnover_series"],
            run_dir / "backtest_turnover.csv",
            value_name="turnover",
        )
        if not ctx["bt_benchmark_series"].empty:
            save_series(
                ctx["bt_benchmark_series"],
                run_dir / "backtest_benchmark.csv",
                value_name="benchmark_return",
            )
        if not ctx["bt_active_series"].empty:
            save_series(
                ctx["bt_active_series"],
                run_dir / "backtest_active.csv",
                value_name="active_return",
            )
        if ctx["bt_periods"]:
            save_frame(pd.DataFrame(ctx["bt_periods"]), run_dir / "backtest_periods.csv")

    if ctx["bt_stats_oos"] is not None:
        save_series(
            ctx["bt_net_series_oos"],
            run_dir / "backtest_net_oos.csv",
            value_name="net_return",
        )
        save_series(
            ctx["bt_gross_series_oos"],
            run_dir / "backtest_gross_oos.csv",
            value_name="gross_return",
        )
        save_series(
            ctx["bt_turnover_series_oos"],
            run_dir / "backtest_turnover_oos.csv",
            value_name="turnover",
        )
        if not ctx["bt_benchmark_series_oos"].empty:
            save_series(
                ctx["bt_benchmark_series_oos"],
                run_dir / "backtest_benchmark_oos.csv",
                value_name="benchmark_return",
            )
        if not ctx["bt_active_series_oos"].empty:
            save_series(
                ctx["bt_active_series_oos"],
                run_dir / "backtest_active_oos.csv",
                value_name="active_return",
            )
        if ctx["bt_periods_oos"]:
            save_frame(
                pd.DataFrame(ctx["bt_periods_oos"]),
                run_dir / "backtest_periods_oos.csv",
            )

    _write_position_outputs(
        positions=ctx["positions_by_rebalance"],
        run_dir=run_dir,
        by_rebalance_name="positions_by_rebalance.csv",
        current_name="positions_current.csv",
        diff_name="rebalance_diff.csv",
        artifacts=artifacts,
        by_rebalance_key="positions_by_rebalance_path",
        current_key="positions_current_path",
        diff_key="positions_diff_path",
        enabled=bool(ctx["BACKTEST_ENABLED"] or not ctx["LIVE_ENABLED"]),
    )
    _write_position_outputs(
        positions=ctx["positions_by_rebalance_oos"],
        run_dir=run_dir,
        by_rebalance_name="positions_by_rebalance_oos.csv",
        current_name="positions_current_oos.csv",
        diff_name="rebalance_diff_oos.csv",
        artifacts=artifacts,
        by_rebalance_key="positions_by_rebalance_oos_path",
        current_key="positions_current_oos_path",
        diff_key="positions_diff_oos_path",
        enabled=True,
    )
    _write_position_outputs(
        positions=ctx["positions_by_rebalance_live"],
        run_dir=run_dir,
        by_rebalance_name="positions_by_rebalance_live.csv",
        current_name="positions_current_live.csv",
        diff_name="rebalance_diff_live.csv",
        artifacts=artifacts,
        by_rebalance_key="positions_by_rebalance_live_path",
        current_key="positions_current_live_path",
        diff_key="positions_diff_live_path",
        enabled=bool(ctx["LIVE_ENABLED"]),
    )

    if ctx["LIVE_ENABLED"]:
        artifacts["live_positions_file"] = artifacts["positions_by_rebalance_live_path"]
        artifacts["live_current_file"] = artifacts["positions_current_live_path"]

    if ctx["walk_forward_results"]:
        save_frame(
            pd.DataFrame(ctx["walk_forward_results"]),
            run_dir / "walk_forward_summary.csv",
        )
    if ctx["perm_stats"] and ctx["perm_stats"].get("scores"):
        save_frame(
            pd.DataFrame({"ic": ctx["perm_stats"]["scores"]}),
            run_dir / "permutation_test.csv",
        )

    return artifacts


def _write_position_outputs(
    *,
    positions: pd.DataFrame | None,
    run_dir: Path,
    by_rebalance_name: str,
    current_name: str,
    diff_name: str,
    artifacts: dict[str, Any],
    by_rebalance_key: str,
    current_key: str,
    diff_key: str,
    enabled: bool,
) -> None:
    if positions is None or positions.empty or not enabled:
        return

    by_rebalance_path = run_dir / by_rebalance_name
    save_frame(positions, by_rebalance_path)
    artifacts[by_rebalance_key] = by_rebalance_path

    entry_dates = pd.to_datetime(positions["entry_date"], errors="coerce")
    if entry_dates.notna().any():
        latest_entry = entry_dates.max()
        current_positions = positions[entry_dates == latest_entry].copy()
        if not current_positions.empty:
            current_path = run_dir / current_name
            save_frame(current_positions, current_path)
            artifacts[current_key] = current_path

    diff_frame = _build_rebalance_diff(positions)
    if not diff_frame.empty:
        diff_path = run_dir / diff_name
        save_frame(diff_frame, diff_path)
        artifacts[diff_key] = diff_path
