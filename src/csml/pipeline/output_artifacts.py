from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from .backtest_reporting import (
    build_backtest_report,
    build_benchmark_compare_entry,
    build_benchmark_compare_summary_frame,
    slugify_report_name,
)
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
        "backtest_style_exposure_path": None,
        "backtest_industry_exposure_path": None,
        "backtest_active_exposure_summary_path": None,
        "backtest_report_path": None,
        "backtest_benchmark_compare_summary_path": None,
        "backtest_benchmark_compare_entries": [],
        "backtest_style_exposure_oos_path": None,
        "backtest_industry_exposure_oos_path": None,
        "backtest_active_exposure_summary_oos_path": None,
        "backtest_report_oos_path": None,
        "backtest_benchmark_compare_summary_oos_path": None,
        "backtest_benchmark_compare_oos_entries": [],
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
        if not ctx["bt_style_exposure"].empty:
            artifacts["backtest_style_exposure_path"] = run_dir / "backtest_style_exposure.csv"
            save_frame(ctx["bt_style_exposure"], artifacts["backtest_style_exposure_path"])
        if not ctx["bt_industry_exposure"].empty:
            artifacts["backtest_industry_exposure_path"] = (
                run_dir / "backtest_industry_exposure.csv"
            )
            save_frame(
                ctx["bt_industry_exposure"],
                artifacts["backtest_industry_exposure_path"],
            )
        if not ctx["bt_active_exposure_summary"].empty:
            artifacts["backtest_active_exposure_summary_path"] = (
                run_dir / "backtest_active_exposure_summary.csv"
            )
            save_frame(
                ctx["bt_active_exposure_summary"],
                artifacts["backtest_active_exposure_summary_path"],
            )
        primary_report = build_backtest_report(
            strategy_returns=ctx["bt_net_series"],
            periods_per_year=ctx["bt_stats"].get("periods_per_year", float("nan")),
            benchmark_returns=ctx["bt_benchmark_series"]
            if not ctx["bt_benchmark_series"].empty
            else None,
        )
        artifacts["backtest_report_path"] = run_dir / "backtest_report.csv"
        save_frame(primary_report.reset_index(), artifacts["backtest_report_path"])
        (
            artifacts["backtest_benchmark_compare_entries"],
            artifacts["backtest_benchmark_compare_summary_path"],
        ) = _write_benchmark_compare_outputs(
            compare_specs=ctx.get("benchmark_compare_specs") or [],
            strategy_returns=ctx["bt_net_series"],
            period_info=ctx["bt_periods"],
            trading_days_per_year=ctx["BACKTEST_TRADING_DAYS_PER_YEAR"],
            entry_price_col=ctx["execution_model"].entry_policy.price_col,
            exit_price_col=ctx["execution_model"].exit_policy.price_col,
            primary_benchmark_symbol=ctx.get("benchmark_symbol"),
            primary_returns_file_path=ctx.get("benchmark_returns_file_path"),
            run_dir=run_dir,
            summary_filename="backtest_benchmark_compare_summary.csv",
            report_prefix="backtest_benchmark_compare",
        )

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
        if not ctx["bt_style_exposure_oos"].empty:
            artifacts["backtest_style_exposure_oos_path"] = (
                run_dir / "backtest_style_exposure_oos.csv"
            )
            save_frame(
                ctx["bt_style_exposure_oos"],
                artifacts["backtest_style_exposure_oos_path"],
            )
        if not ctx["bt_industry_exposure_oos"].empty:
            artifacts["backtest_industry_exposure_oos_path"] = (
                run_dir / "backtest_industry_exposure_oos.csv"
            )
            save_frame(
                ctx["bt_industry_exposure_oos"],
                artifacts["backtest_industry_exposure_oos_path"],
            )
        if not ctx["bt_active_exposure_summary_oos"].empty:
            artifacts["backtest_active_exposure_summary_oos_path"] = (
                run_dir / "backtest_active_exposure_summary_oos.csv"
            )
            save_frame(
                ctx["bt_active_exposure_summary_oos"],
                artifacts["backtest_active_exposure_summary_oos_path"],
            )
        primary_report_oos = build_backtest_report(
            strategy_returns=ctx["bt_net_series_oos"],
            periods_per_year=ctx["bt_stats_oos"].get("periods_per_year", float("nan")),
            benchmark_returns=ctx["bt_benchmark_series_oos"]
            if not ctx["bt_benchmark_series_oos"].empty
            else None,
        )
        artifacts["backtest_report_oos_path"] = run_dir / "backtest_report_oos.csv"
        save_frame(primary_report_oos.reset_index(), artifacts["backtest_report_oos_path"])
        (
            artifacts["backtest_benchmark_compare_oos_entries"],
            artifacts["backtest_benchmark_compare_summary_oos_path"],
        ) = _write_benchmark_compare_outputs(
            compare_specs=ctx.get("benchmark_compare_specs") or [],
            strategy_returns=ctx["bt_net_series_oos"],
            period_info=ctx["bt_periods_oos"],
            trading_days_per_year=ctx["BACKTEST_TRADING_DAYS_PER_YEAR"],
            entry_price_col=ctx["execution_model"].entry_policy.price_col,
            exit_price_col=ctx["execution_model"].exit_policy.price_col,
            primary_benchmark_symbol=ctx.get("benchmark_symbol"),
            primary_returns_file_path=ctx.get("benchmark_returns_file_path"),
            run_dir=run_dir,
            summary_filename="backtest_benchmark_compare_summary_oos.csv",
            report_prefix="backtest_benchmark_compare_oos",
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


def _write_benchmark_compare_outputs(
    *,
    compare_specs: list[dict[str, Any]],
    strategy_returns: pd.Series,
    period_info: list[dict[str, Any]],
    trading_days_per_year: int,
    entry_price_col: str,
    exit_price_col: str,
    primary_benchmark_symbol: str | None,
    primary_returns_file_path: Path | None,
    run_dir: Path,
    summary_filename: str,
    report_prefix: str,
) -> tuple[list[dict[str, Any]], Path | None]:
    if not compare_specs:
        return [], None

    report_entries: list[dict[str, Any]] = []
    used_slugs: set[str] = set()
    for spec in compare_specs:
        entry = build_benchmark_compare_entry(
            name=spec["name"],
            source_type=str(spec.get("source_type") or "returns_file"),
            returns_file=(
                str(spec["returns_file_path"])
                if spec.get("returns_file_path") is not None
                else None
            ),
            symbol=str(spec["symbol"]).strip() if spec.get("symbol") else None,
            benchmark_df=spec.get("benchmark_df"),
            benchmark_return_series=spec.get("series"),
            strategy_returns=strategy_returns,
            period_info=period_info,
            trading_days_per_year=trading_days_per_year,
            entry_price_col=entry_price_col,
            exit_price_col=exit_price_col,
        )
        slug = slugify_report_name(str(spec["name"]))
        if slug in used_slugs:
            suffix = 2
            while f"{slug}_{suffix}" in used_slugs:
                suffix += 1
            slug = f"{slug}_{suffix}"
        used_slugs.add(slug)

        report_path = run_dir / f"{report_prefix}_{slug}.csv"
        save_frame(entry["report_frame"].reset_index(), report_path)
        report_entries.append(
            {
                "name": entry["name"],
                "source_type": entry["source_type"],
                "returns_file": entry["returns_file"],
                "symbol": entry["symbol"],
                "is_primary": bool(
                    (
                        primary_returns_file_path is not None
                        and entry["returns_file"] is not None
                        and Path(entry["returns_file"]) == primary_returns_file_path
                    )
                    or (
                        primary_benchmark_symbol is not None
                        and entry["symbol"] is not None
                        and entry["symbol"] == primary_benchmark_symbol
                    )
                ),
                "aligned_periods": entry["aligned_periods"],
                "benchmark": entry["benchmark"],
                "active": entry["active"],
                "report_file": str(report_path),
            }
        )

    summary_path = run_dir / summary_filename
    save_frame(build_benchmark_compare_summary_frame(report_entries), summary_path)
    return report_entries, summary_path
