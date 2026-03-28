from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import yaml

from ..execution import describe_execution_model
from .support import _build_rebalance_diff, save_frame, save_json, save_parquet, save_series


def _pluck(context: Mapping[str, Any], *keys: str) -> tuple[Any, ...]:
    return tuple(context[key] for key in keys)


def persist_run_outputs(*, context: Mapping[str, Any]) -> None:
    (
        SAVE_ARTIFACTS,
        SAVE_DATASET,
        SAVE_SCORED_ARTIFACT,
        run_dir,
        config,
        run_name,
        run_stamp,
        run_hash,
        config_path,
        config_source,
        MODEL_TYPE,
        SAMPLE_WEIGHT_MODE,
        SAMPLE_WEIGHT_PARAMS,
        TRAIN_WINDOW_MODE,
        TRAIN_WINDOW_SIZE,
        TRAIN_WINDOW_UNIT,
        active_log_file,
    ) = _pluck(
        context,
        "SAVE_ARTIFACTS",
        "SAVE_DATASET",
        "SAVE_SCORED_ARTIFACT",
        "run_dir",
        "config",
        "run_name",
        "run_stamp",
        "run_hash",
        "config_path",
        "config_source",
        "MODEL_TYPE",
        "SAMPLE_WEIGHT_MODE",
        "SAMPLE_WEIGHT_PARAMS",
        "TRAIN_WINDOW_MODE",
        "TRAIN_WINDOW_SIZE",
        "TRAIN_WINDOW_UNIT",
        "active_log_file",
    )
    if not SAVE_ARTIFACTS:
        return

    (
        dataset,
        eval_scored_data,
        importance_df,
        importance_source,
        walk_forward_importance_df,
        walk_forward_feature_stability_df,
        ic_series,
        pearson_ic_series,
        REPORT_TRAIN_IC,
        train_ic_series,
        train_pearson_ic_series,
        quantile_ts,
        turnover_series,
        bucket_ic_records,
        rolling_ic_results,
        rolling_sharpe_results,
        final_oos_eval,
        ic_series_oos,
        pearson_ic_series_oos,
        quantile_ts_oos,
        turnover_series_oos,
        bucket_ic_records_oos,
        rolling_ic_oos_results,
        rolling_sharpe_oos_results,
        dropped_date_counts,
        bt_stats,
        bt_net_series,
        bt_gross_series,
        bt_turnover_series,
        bt_benchmark_series,
        bt_active_series,
        bt_periods,
        bt_stats_oos,
        bt_net_series_oos,
        bt_gross_series_oos,
        bt_turnover_series_oos,
        bt_benchmark_series_oos,
        bt_active_series_oos,
        bt_periods_oos,
        positions_by_rebalance,
        BACKTEST_ENABLED,
        LIVE_ENABLED,
        positions_by_rebalance_oos,
        positions_by_rebalance_live,
        perm_stats,
        walk_forward_results,
        pred_nunique,
        constant_prediction,
        feature_importance_nonzero,
        zero_feature_importance,
    ) = _pluck(
        context,
        "dataset",
        "eval_scored_data",
        "importance_df",
        "importance_source",
        "walk_forward_importance_df",
        "walk_forward_feature_stability_df",
        "ic_series",
        "pearson_ic_series",
        "REPORT_TRAIN_IC",
        "train_ic_series",
        "train_pearson_ic_series",
        "quantile_ts",
        "turnover_series",
        "bucket_ic_records",
        "rolling_ic_results",
        "rolling_sharpe_results",
        "final_oos_eval",
        "ic_series_oos",
        "pearson_ic_series_oos",
        "quantile_ts_oos",
        "turnover_series_oos",
        "bucket_ic_records_oos",
        "rolling_ic_oos_results",
        "rolling_sharpe_oos_results",
        "dropped_date_counts",
        "bt_stats",
        "bt_net_series",
        "bt_gross_series",
        "bt_turnover_series",
        "bt_benchmark_series",
        "bt_active_series",
        "bt_periods",
        "bt_stats_oos",
        "bt_net_series_oos",
        "bt_gross_series_oos",
        "bt_turnover_series_oos",
        "bt_benchmark_series_oos",
        "bt_active_series_oos",
        "bt_periods_oos",
        "positions_by_rebalance",
        "BACKTEST_ENABLED",
        "LIVE_ENABLED",
        "positions_by_rebalance_oos",
        "positions_by_rebalance_live",
        "perm_stats",
        "walk_forward_results",
        "pred_nunique",
        "constant_prediction",
        "feature_importance_nonzero",
        "zero_feature_importance",
    )
    (
        MARKET,
        provider,
        START_DATE,
        END_DATE,
        symbols,
        df_full,
        df_model_all,
        df_model,
        df_model_oos,
        FINAL_OOS_ENABLED,
        MIN_SYMBOLS_PER_DATE,
        universe_mode_effective,
        by_date_file,
        REQUIRE_BY_DATE,
        DROP_SUSPENDED,
        SUSPENDED_POLICY,
        LABEL_HORIZON_DAYS,
        LABEL_SHIFT_DAYS,
        LABEL_HORIZON_MODE,
        LABEL_REBALANCE_FREQUENCY,
        WINSORIZE_PCT,
        TRAIN_TARGET_TRANSFORM,
        label_horizon_effective,
        train_dates,
        train_dates_full,
        test_dates,
        purge_days,
        embargo_days,
        PURGE_STEPS,
        EMBARGO_STEPS,
        SAMPLE_ON_REBALANCE_DATES,
        rebalance_gap_days,
        ic_stats,
        pearson_ic_stats,
        train_ic_stats,
        train_ic_raw_stats,
        train_pearson_ic_stats,
        cv_stats,
        cv_stats_raw,
        SIGNAL_DIRECTION,
        SIGNAL_DIRECTION_MODE,
        error_metrics,
        hit_rate_stats,
        topk_positive_stats,
        ROLLING_WINDOWS_MONTHS,
        rolling_ic_obs_per_year,
        rolling_ic_latest,
        quantile_mean,
        EVAL_BUFFER_EXIT,
        EVAL_BUFFER_ENTRY,
        REBALANCE_FREQUENCY,
        eval_rebalance_dates,
    ) = _pluck(
        context,
        "MARKET",
        "provider",
        "START_DATE",
        "END_DATE",
        "symbols",
        "df_full",
        "df_model_all",
        "df_model",
        "df_model_oos",
        "FINAL_OOS_ENABLED",
        "MIN_SYMBOLS_PER_DATE",
        "universe_mode_effective",
        "by_date_file",
        "REQUIRE_BY_DATE",
        "DROP_SUSPENDED",
        "SUSPENDED_POLICY",
        "LABEL_HORIZON_DAYS",
        "LABEL_SHIFT_DAYS",
        "LABEL_HORIZON_MODE",
        "LABEL_REBALANCE_FREQUENCY",
        "WINSORIZE_PCT",
        "TRAIN_TARGET_TRANSFORM",
        "label_horizon_effective",
        "train_dates",
        "train_dates_full",
        "test_dates",
        "purge_days",
        "embargo_days",
        "PURGE_STEPS",
        "EMBARGO_STEPS",
        "SAMPLE_ON_REBALANCE_DATES",
        "rebalance_gap_days",
        "ic_stats",
        "pearson_ic_stats",
        "train_ic_stats",
        "train_ic_raw_stats",
        "train_pearson_ic_stats",
        "cv_stats",
        "cv_stats_raw",
        "SIGNAL_DIRECTION",
        "SIGNAL_DIRECTION_MODE",
        "error_metrics",
        "hit_rate_stats",
        "topk_positive_stats",
        "ROLLING_WINDOWS_MONTHS",
        "rolling_ic_obs_per_year",
        "rolling_ic_latest",
        "quantile_mean",
        "EVAL_BUFFER_EXIT",
        "EVAL_BUFFER_ENTRY",
        "REBALANCE_FREQUENCY",
        "eval_rebalance_dates",
    )
    (
        BACKTEST_EXIT_MODE,
        BACKTEST_EXIT_HORIZON_DAYS,
        BACKTEST_EXIT_PRICE_POLICY,
        BACKTEST_EXIT_FALLBACK_POLICY,
        BACKTEST_BUFFER_EXIT,
        BACKTEST_BUFFER_ENTRY,
        BACKTEST_LONG_ONLY,
        BACKTEST_WEIGHTING,
        BACKTEST_GROUP_COL,
        BACKTEST_MAX_NAMES_PER_GROUP,
        BACKTEST_TOP_K,
        BACKTEST_SHORT_K,
        BACKTEST_REBALANCE_FREQUENCY,
        backtest_rebalance_dates,
        BACKTEST_TRADING_DAYS_PER_YEAR,
        BACKTEST_TRADABLE_COL,
        BACKTEST_SIGNAL_DIRECTION,
        benchmark_symbol,
        BACKTEST_COST_BPS_REPORT,
        execution_model,
        bt_benchmark_stats,
        bt_active_stats,
        rolling_sharpe_latest,
    ) = _pluck(
        context,
        "BACKTEST_EXIT_MODE",
        "BACKTEST_EXIT_HORIZON_DAYS",
        "BACKTEST_EXIT_PRICE_POLICY",
        "BACKTEST_EXIT_FALLBACK_POLICY",
        "BACKTEST_BUFFER_EXIT",
        "BACKTEST_BUFFER_ENTRY",
        "BACKTEST_LONG_ONLY",
        "BACKTEST_WEIGHTING",
        "BACKTEST_GROUP_COL",
        "BACKTEST_MAX_NAMES_PER_GROUP",
        "BACKTEST_TOP_K",
        "BACKTEST_SHORT_K",
        "BACKTEST_REBALANCE_FREQUENCY",
        "backtest_rebalance_dates",
        "BACKTEST_TRADING_DAYS_PER_YEAR",
        "BACKTEST_TRADABLE_COL",
        "BACKTEST_SIGNAL_DIRECTION",
        "benchmark_symbol",
        "BACKTEST_COST_BPS_REPORT",
        "execution_model",
        "bt_benchmark_stats",
        "bt_active_stats",
        "rolling_sharpe_latest",
    )
    (
        FINAL_OOS_SIZE_RAW,
        final_oos_len,
        final_oos_start,
        final_oos_end,
        ic_stats_oos,
        pearson_ic_stats_oos,
        error_metrics_oos,
        hit_rate_stats_oos,
        topk_positive_stats_oos,
        rolling_ic_oos_obs_per_year,
        rolling_ic_latest_oos,
        quantile_mean_oos,
        bt_benchmark_stats_oos,
        bt_active_stats_oos,
        rolling_sharpe_latest_oos,
    ) = _pluck(
        context,
        "FINAL_OOS_SIZE_RAW",
        "final_oos_len",
        "final_oos_start",
        "final_oos_end",
        "ic_stats_oos",
        "pearson_ic_stats_oos",
        "error_metrics_oos",
        "hit_rate_stats_oos",
        "topk_positive_stats_oos",
        "rolling_ic_oos_obs_per_year",
        "rolling_ic_latest_oos",
        "quantile_mean_oos",
        "bt_benchmark_stats_oos",
        "bt_active_stats_oos",
        "rolling_sharpe_latest_oos",
    )
    (
        live_as_of,
        LIVE_TRAIN_MODE,
        FUNDAMENTALS_ENABLED,
        FUNDAMENTALS_SOURCE,
        FUNDAMENTALS_PROVIDER,
        FUNDAMENTALS_FILE,
        fund_cache_dir,
        FUNDAMENTALS_FEATURES,
        FUNDAMENTALS_LOG_MCAP,
        FUNDAMENTALS_MCAP_COL,
        FUNDAMENTALS_PROVIDER_OVERLAY_ENABLED,
        FUNDAMENTALS_PROVIDER_OVERLAY_SOURCE,
        FUNDAMENTALS_PROVIDER_OVERLAY_PROVIDER,
        provider_overlay_cache_dir,
        FUNDAMENTALS_PROVIDER_OVERLAY_FEATURES,
        INDUSTRY_ENABLED,
        INDUSTRY_SOURCE,
        INDUSTRY_FILE,
        INDUSTRY_KEEP_COLUMNS,
        passthrough_cols,
        INDUSTRY_FFILL,
        INDUSTRY_FFILL_LIMIT,
        WF_ENABLED,
        WF_N_WINDOWS,
        WF_TEST_SIZE,
        WF_STEP_SIZE,
        WF_ANCHOR_END,
        WF_FEATURE_TOP_K,
    ) = _pluck(
        context,
        "live_as_of",
        "LIVE_TRAIN_MODE",
        "FUNDAMENTALS_ENABLED",
        "FUNDAMENTALS_SOURCE",
        "FUNDAMENTALS_PROVIDER",
        "FUNDAMENTALS_FILE",
        "fund_cache_dir",
        "FUNDAMENTALS_FEATURES",
        "FUNDAMENTALS_LOG_MCAP",
        "FUNDAMENTALS_MCAP_COL",
        "FUNDAMENTALS_PROVIDER_OVERLAY_ENABLED",
        "FUNDAMENTALS_PROVIDER_OVERLAY_SOURCE",
        "FUNDAMENTALS_PROVIDER_OVERLAY_PROVIDER",
        "provider_overlay_cache_dir",
        "FUNDAMENTALS_PROVIDER_OVERLAY_FEATURES",
        "INDUSTRY_ENABLED",
        "INDUSTRY_SOURCE",
        "INDUSTRY_FILE",
        "INDUSTRY_KEEP_COLUMNS",
        "passthrough_cols",
        "INDUSTRY_FFILL",
        "INDUSTRY_FFILL_LIMIT",
        "WF_ENABLED",
        "WF_N_WINDOWS",
        "WF_TEST_SIZE",
        "WF_STEP_SIZE",
        "WF_ANCHOR_END",
        "WF_FEATURE_TOP_K",
    )

    rolling_ic_files: dict[str, str] = {}
    rolling_sharpe_files: dict[str, str] = {}
    rolling_ic_oos_files: dict[str, str] = {}
    rolling_sharpe_oos_files: dict[str, str] = {}
    bucket_ic_path: Optional[Path] = None
    bucket_ic_oos_path: Optional[Path] = None
    walk_forward_importance_path: Optional[Path] = None
    walk_forward_feature_stability_path: Optional[Path] = None
    dataset_path: Optional[Path] = None
    eval_scored_path: Optional[Path] = None
    feature_importance_path: Optional[Path] = None
    positions_by_rebalance_path: Optional[Path] = None
    positions_current_path: Optional[Path] = None
    positions_by_rebalance_oos_path: Optional[Path] = None
    positions_current_oos_path: Optional[Path] = None
    positions_by_rebalance_live_path: Optional[Path] = None
    positions_current_live_path: Optional[Path] = None
    positions_diff_path: Optional[Path] = None
    positions_diff_oos_path: Optional[Path] = None
    positions_diff_live_path: Optional[Path] = None

    if SAVE_DATASET:
        dataset_path = run_dir / "dataset.parquet"
        save_parquet(dataset.as_multiindex(), dataset_path)
    if SAVE_SCORED_ARTIFACT and eval_scored_data is not None and not eval_scored_data.empty:
        eval_scored_path = run_dir / "eval_scored.parquet"
        save_parquet(eval_scored_data, eval_scored_path)
    feature_importance_path = run_dir / "feature_importance.csv"
    save_frame(importance_df, feature_importance_path)
    if not walk_forward_importance_df.empty:
        walk_forward_importance_path = run_dir / "walk_forward_feature_importance.csv"
        save_frame(walk_forward_importance_df, walk_forward_importance_path)
    if not walk_forward_feature_stability_df.empty:
        walk_forward_feature_stability_path = run_dir / "walk_forward_feature_stability.csv"
        save_frame(walk_forward_feature_stability_df, walk_forward_feature_stability_path)
    save_series(ic_series, run_dir / "ic_test.csv", value_name="ic")
    save_series(pearson_ic_series, run_dir / "ic_pearson_test.csv", value_name="ic")
    if REPORT_TRAIN_IC:
        save_series(train_ic_series, run_dir / "ic_train.csv", value_name="ic")
        save_series(train_pearson_ic_series, run_dir / "ic_pearson_train.csv", value_name="ic")
    if not quantile_ts.empty:
        save_frame(quantile_ts.reset_index(), run_dir / "quantile_returns.csv")
    save_series(turnover_series, run_dir / "turnover_eval.csv", value_name="turnover")
    if bucket_ic_records:
        bucket_ic_path = run_dir / "bucket_ic.csv"
        save_frame(pd.DataFrame(bucket_ic_records), bucket_ic_path)
    if rolling_ic_results:
        for label, frame in rolling_ic_results.items():
            if frame.empty:
                continue
            out = frame.copy()
            out.index.name = "trade_date"
            path = run_dir / f"ic_rolling_{label}.csv"
            save_frame(out.reset_index(), path)
            rolling_ic_files[label] = str(path)
    if rolling_sharpe_results:
        for label, frame in rolling_sharpe_results.items():
            if frame.empty:
                continue
            out = frame.copy()
            out.index.name = "trade_date"
            path = run_dir / f"backtest_rolling_sharpe_{label}.csv"
            save_frame(out.reset_index(), path)
            rolling_sharpe_files[label] = str(path)
    if final_oos_eval is not None:
        save_series(ic_series_oos, run_dir / "ic_oos.csv", value_name="ic")
        save_series(pearson_ic_series_oos, run_dir / "ic_pearson_oos.csv", value_name="ic")
        if not quantile_ts_oos.empty:
            save_frame(quantile_ts_oos.reset_index(), run_dir / "quantile_returns_oos.csv")
        save_series(turnover_series_oos, run_dir / "turnover_eval_oos.csv", value_name="turnover")
        if bucket_ic_records_oos:
            bucket_ic_oos_path = run_dir / "bucket_ic_oos.csv"
            save_frame(pd.DataFrame(bucket_ic_records_oos), bucket_ic_oos_path)
        if rolling_ic_oos_results:
            for label, frame in rolling_ic_oos_results.items():
                if frame.empty:
                    continue
                out = frame.copy()
                out.index.name = "trade_date"
                path = run_dir / f"ic_rolling_{label}_oos.csv"
                save_frame(out.reset_index(), path)
                rolling_ic_oos_files[label] = str(path)
        if rolling_sharpe_oos_results:
            for label, frame in rolling_sharpe_oos_results.items():
                if frame.empty:
                    continue
                out = frame.copy()
                out.index.name = "trade_date"
                path = run_dir / f"backtest_rolling_sharpe_{label}_oos.csv"
                save_frame(out.reset_index(), path)
                rolling_sharpe_oos_files[label] = str(path)
    if not dropped_date_counts.empty:
        save_frame(
            dropped_date_counts.rename("symbol_count").reset_index(),
            run_dir / "dropped_dates.csv",
        )
    if bt_stats is not None:
        save_series(bt_net_series, run_dir / "backtest_net.csv", value_name="net_return")
        save_series(bt_gross_series, run_dir / "backtest_gross.csv", value_name="gross_return")
        save_series(bt_turnover_series, run_dir / "backtest_turnover.csv", value_name="turnover")
        if not bt_benchmark_series.empty:
            save_series(
                bt_benchmark_series,
                run_dir / "backtest_benchmark.csv",
                value_name="benchmark_return",
            )
        if not bt_active_series.empty:
            save_series(
                bt_active_series,
                run_dir / "backtest_active.csv",
                value_name="active_return",
            )
        if bt_periods:
            save_frame(pd.DataFrame(bt_periods), run_dir / "backtest_periods.csv")
    if bt_stats_oos is not None:
        save_series(bt_net_series_oos, run_dir / "backtest_net_oos.csv", value_name="net_return")
        save_series(
            bt_gross_series_oos,
            run_dir / "backtest_gross_oos.csv",
            value_name="gross_return",
        )
        save_series(
            bt_turnover_series_oos,
            run_dir / "backtest_turnover_oos.csv",
            value_name="turnover",
        )
        if not bt_benchmark_series_oos.empty:
            save_series(
                bt_benchmark_series_oos,
                run_dir / "backtest_benchmark_oos.csv",
                value_name="benchmark_return",
            )
        if not bt_active_series_oos.empty:
            save_series(
                bt_active_series_oos,
                run_dir / "backtest_active_oos.csv",
                value_name="active_return",
            )
        if bt_periods_oos:
            save_frame(pd.DataFrame(bt_periods_oos), run_dir / "backtest_periods_oos.csv")

    if (
        positions_by_rebalance is not None
        and not positions_by_rebalance.empty
        and (BACKTEST_ENABLED or not LIVE_ENABLED)
    ):
        positions_by_rebalance_path = run_dir / "positions_by_rebalance.csv"
        save_frame(positions_by_rebalance, positions_by_rebalance_path)
        entry_dates = pd.to_datetime(positions_by_rebalance["entry_date"], errors="coerce")
        if entry_dates.notna().any():
            latest_entry = entry_dates.max()
            positions_current = positions_by_rebalance[entry_dates == latest_entry].copy()
            if not positions_current.empty:
                positions_current_path = run_dir / "positions_current.csv"
                save_frame(positions_current, positions_current_path)
    if positions_by_rebalance_oos is not None and not positions_by_rebalance_oos.empty:
        positions_by_rebalance_oos_path = run_dir / "positions_by_rebalance_oos.csv"
        save_frame(positions_by_rebalance_oos, positions_by_rebalance_oos_path)
        oos_entry_dates = pd.to_datetime(positions_by_rebalance_oos["entry_date"], errors="coerce")
        if oos_entry_dates.notna().any():
            oos_latest_entry = oos_entry_dates.max()
            positions_current_oos = positions_by_rebalance_oos[oos_entry_dates == oos_latest_entry].copy()
            if not positions_current_oos.empty:
                positions_current_oos_path = run_dir / "positions_current_oos.csv"
                save_frame(positions_current_oos, positions_current_oos_path)

    if LIVE_ENABLED and positions_by_rebalance_live is not None and not positions_by_rebalance_live.empty:
        positions_by_rebalance_live_path = run_dir / "positions_by_rebalance_live.csv"
        save_frame(positions_by_rebalance_live, positions_by_rebalance_live_path)
        live_entry_dates = pd.to_datetime(positions_by_rebalance_live["entry_date"], errors="coerce")
        if live_entry_dates.notna().any():
            live_latest_entry = live_entry_dates.max()
            positions_current_live = positions_by_rebalance_live[
                live_entry_dates == live_latest_entry
            ].copy()
            if not positions_current_live.empty:
                positions_current_live_path = run_dir / "positions_current_live.csv"
                save_frame(positions_current_live, positions_current_live_path)

    if (
        positions_by_rebalance is not None
        and not positions_by_rebalance.empty
        and (BACKTEST_ENABLED or not LIVE_ENABLED)
    ):
        diff_frame = _build_rebalance_diff(positions_by_rebalance)
        if not diff_frame.empty:
            positions_diff_path = run_dir / "rebalance_diff.csv"
            save_frame(diff_frame, positions_diff_path)
    if positions_by_rebalance_oos is not None and not positions_by_rebalance_oos.empty:
        diff_oos = _build_rebalance_diff(positions_by_rebalance_oos)
        if not diff_oos.empty:
            positions_diff_oos_path = run_dir / "rebalance_diff_oos.csv"
            save_frame(diff_oos, positions_diff_oos_path)

    if LIVE_ENABLED and positions_by_rebalance_live is not None and not positions_by_rebalance_live.empty:
        diff_live = _build_rebalance_diff(positions_by_rebalance_live)
        if not diff_live.empty:
            positions_diff_live_path = run_dir / "rebalance_diff_live.csv"
            save_frame(diff_live, positions_diff_live_path)

    if perm_stats and perm_stats.get("scores"):
        save_frame(pd.DataFrame({"ic": perm_stats["scores"]}), run_dir / "permutation_test.csv")

    if walk_forward_results:
        save_frame(pd.DataFrame(walk_forward_results), run_dir / "walk_forward_summary.csv")

    live_positions_file = None
    live_current_file = None
    if LIVE_ENABLED:
        if positions_by_rebalance_live_path is not None:
            live_positions_file = positions_by_rebalance_live_path
        if positions_current_live_path is not None:
            live_current_file = positions_current_live_path

    summary = {
        "run": {
            "name": run_name,
            "timestamp": run_stamp,
            "config_hash": run_hash,
            "config_path": str(config_path) if config_path else None,
            "config_source": config_source,
            "model_type": MODEL_TYPE,
            "sample_weight_mode": SAMPLE_WEIGHT_MODE,
            "sample_weight_params": SAMPLE_WEIGHT_PARAMS,
            "train_window": {
                "mode": TRAIN_WINDOW_MODE,
                "size": TRAIN_WINDOW_SIZE,
                "unit": TRAIN_WINDOW_UNIT,
            },
            "output_dir": str(run_dir),
            "log_file": str(active_log_file) if active_log_file else None,
        },
        "data": {
            "market": MARKET,
            "provider": provider,
            "start_date": START_DATE,
            "end_date": END_DATE,
            "symbols": len(symbols),
            "rows": len(df_full),
            "rows_model": len(df_model_all),
            "rows_model_in_sample": len(df_model),
            "rows_model_oos": len(df_model_oos) if FINAL_OOS_ENABLED else 0,
            "min_symbols_per_date": MIN_SYMBOLS_PER_DATE,
            "dropped_dates": int(dropped_date_counts.shape[0]),
        },
        "dataset": {
            "schema": dataset.schema.to_dict() if dataset is not None else None,
            "rows": int(len(dataset.frame)) if dataset is not None else 0,
            "file": str(dataset_path) if dataset_path else None,
            "index": [dataset.schema.date_col, dataset.schema.instrument_col]
            if dataset is not None
            else None,
        },
        "universe": {
            "mode": universe_mode_effective,
            "by_date_file": str(by_date_file) if by_date_file else None,
            "require_by_date": REQUIRE_BY_DATE,
            "drop_suspended": DROP_SUSPENDED,
            "suspended_policy": SUSPENDED_POLICY,
        },
        "label": {
            "horizon_days": LABEL_HORIZON_DAYS,
            "horizon_days_effective": label_horizon_effective,
            "horizon_mode": LABEL_HORIZON_MODE,
            "rebalance_frequency": LABEL_REBALANCE_FREQUENCY,
            "shift_days": LABEL_SHIFT_DAYS,
            "winsorize_pct": WINSORIZE_PCT,
            "train_target_transform": TRAIN_TARGET_TRANSFORM,
        },
        "split": {
            "train_dates": len(train_dates),
            "train_dates_raw": len(train_dates_full),
            "test_dates": len(test_dates),
            "purge_days": purge_days,
            "embargo_days": embargo_days,
            "purge_steps": PURGE_STEPS,
            "embargo_steps": EMBARGO_STEPS,
            "train_window": {
                "mode": TRAIN_WINDOW_MODE,
                "size": TRAIN_WINDOW_SIZE,
                "unit": TRAIN_WINDOW_UNIT,
                "applied": bool(
                    TRAIN_WINDOW_MODE == "rolling" and len(train_dates) < len(train_dates_full)
                ),
            },
            "rebalance_gap_days": float(rebalance_gap_days)
            if SAMPLE_ON_REBALANCE_DATES
            and rebalance_gap_days is not None
            and np.isfinite(rebalance_gap_days)
            else None,
        },
        "eval": {
            "ic": ic_stats,
            "pearson_ic": pearson_ic_stats,
            "train_ic": train_ic_stats if REPORT_TRAIN_IC else None,
            "train_ic_raw": train_ic_raw_stats if train_ic_raw_stats else None,
            "train_pearson_ic": train_pearson_ic_stats if REPORT_TRAIN_IC else None,
            "cv_ic": cv_stats,
            "cv_ic_raw": cv_stats_raw,
            "signal_direction": SIGNAL_DIRECTION,
            "signal_direction_mode": SIGNAL_DIRECTION_MODE,
            "error_metrics": error_metrics,
            "hit_rate": hit_rate_stats,
            "topk_positive_ratio": topk_positive_stats,
            "bucket_ic": bucket_ic_records,
            "bucket_ic_file": str(bucket_ic_path) if bucket_ic_path else None,
            "rolling_ic": {
                "windows_months": ROLLING_WINDOWS_MONTHS,
                "obs_per_year": rolling_ic_obs_per_year,
                "latest": rolling_ic_latest,
                "series_files": rolling_ic_files,
            },
            "quantile_mean": quantile_mean.to_dict() if not quantile_mean.empty else {},
            "long_short": float(quantile_mean.iloc[-1] - quantile_mean.iloc[0])
            if not quantile_mean.empty
            else None,
            "turnover_mean": float(turnover_series.mean()) if not turnover_series.empty else None,
            "turnover_count": int(turnover_series.shape[0]),
            "buffer_exit": EVAL_BUFFER_EXIT,
            "buffer_entry": EVAL_BUFFER_ENTRY,
            "sample_on_rebalance_dates": SAMPLE_ON_REBALANCE_DATES,
            "rebalance_frequency": REBALANCE_FREQUENCY,
            "rebalance_dates": [
                pd.to_datetime(date).strftime("%Y%m%d") for date in eval_rebalance_dates
            ],
            "save_scored_artifact": SAVE_SCORED_ARTIFACT,
            "scored_file": str(eval_scored_path) if eval_scored_path else None,
            "scored_pred_col": "pred",
            "scored_signal_col": "signal_eval",
            "scored_signal_backtest_col": "signal_backtest",
            "pred_nunique": pred_nunique,
            "constant_prediction": constant_prediction,
            "feature_importance_file": str(feature_importance_path) if feature_importance_path else None,
            "feature_importance_source": importance_source,
            "feature_importance_nonzero": feature_importance_nonzero,
            "zero_feature_importance": zero_feature_importance,
            "permutation_test": perm_stats,
        },
        "backtest": {
            "enabled": BACKTEST_ENABLED,
            "exit_mode": BACKTEST_EXIT_MODE,
            "exit_horizon_days": BACKTEST_EXIT_HORIZON_DAYS,
            "exit_price_policy": BACKTEST_EXIT_PRICE_POLICY,
            "exit_fallback_policy": BACKTEST_EXIT_FALLBACK_POLICY,
            "buffer_exit": BACKTEST_BUFFER_EXIT,
            "buffer_entry": BACKTEST_BUFFER_ENTRY,
            "mode": "long_only" if BACKTEST_LONG_ONLY else "long_short",
            "weighting": BACKTEST_WEIGHTING,
            "group_col": BACKTEST_GROUP_COL,
            "max_names_per_group": BACKTEST_MAX_NAMES_PER_GROUP,
            "top_k": BACKTEST_TOP_K,
            "short_k": BACKTEST_SHORT_K,
            "rebalance_frequency": BACKTEST_REBALANCE_FREQUENCY,
            "rebalance_dates": [
                pd.to_datetime(date).strftime("%Y%m%d") for date in backtest_rebalance_dates
            ],
            "shift_days": LABEL_SHIFT_DAYS,
            "trading_days_per_year": BACKTEST_TRADING_DAYS_PER_YEAR,
            "tradable_col": BACKTEST_TRADABLE_COL,
            "signal_direction": BACKTEST_SIGNAL_DIRECTION,
            "benchmark_symbol": benchmark_symbol,
            "transaction_cost_bps": BACKTEST_COST_BPS_REPORT,
            "execution": describe_execution_model(execution_model),
            "stats": bt_stats,
            "benchmark": bt_benchmark_stats,
            "active": bt_active_stats,
            "rolling_sharpe": {
                "windows_months": ROLLING_WINDOWS_MONTHS,
                "latest": rolling_sharpe_latest,
                "series_files": rolling_sharpe_files,
            },
        },
        "final_oos": {
            "enabled": FINAL_OOS_ENABLED,
            "size": FINAL_OOS_SIZE_RAW,
            "dates": int(final_oos_len) if FINAL_OOS_ENABLED else 0,
            "start": final_oos_start.strftime("%Y%m%d") if final_oos_start else None,
            "end": final_oos_end.strftime("%Y%m%d") if final_oos_end else None,
            "ic": ic_stats_oos if final_oos_eval is not None else None,
            "pearson_ic": pearson_ic_stats_oos if final_oos_eval is not None else None,
            "error_metrics": error_metrics_oos if final_oos_eval is not None else None,
            "hit_rate": hit_rate_stats_oos if final_oos_eval is not None else None,
            "topk_positive_ratio": topk_positive_stats_oos if final_oos_eval is not None else None,
            "bucket_ic": bucket_ic_records_oos if final_oos_eval is not None else None,
            "bucket_ic_file": str(bucket_ic_oos_path) if bucket_ic_oos_path else None,
            "rolling_ic": {
                "windows_months": ROLLING_WINDOWS_MONTHS,
                "obs_per_year": rolling_ic_oos_obs_per_year,
                "latest": rolling_ic_latest_oos,
                "series_files": rolling_ic_oos_files,
            }
            if final_oos_eval is not None
            else None,
            "quantile_mean": quantile_mean_oos.to_dict()
            if final_oos_eval is not None and not quantile_mean_oos.empty
            else {},
            "long_short": float(quantile_mean_oos.iloc[-1] - quantile_mean_oos.iloc[0])
            if final_oos_eval is not None and not quantile_mean_oos.empty
            else None,
            "turnover_mean": float(turnover_series_oos.mean())
            if final_oos_eval is not None and not turnover_series_oos.empty
            else None,
            "turnover_count": int(turnover_series_oos.shape[0]) if final_oos_eval is not None else 0,
            "backtest": {
                "stats": bt_stats_oos,
                "benchmark": bt_benchmark_stats_oos,
                "active": bt_active_stats_oos,
                "rolling_sharpe": {
                    "windows_months": ROLLING_WINDOWS_MONTHS,
                    "latest": rolling_sharpe_latest_oos,
                    "series_files": rolling_sharpe_oos_files,
                },
            }
            if final_oos_eval is not None
            else None,
            "positions": {
                "by_rebalance_file": str(positions_by_rebalance_oos_path)
                if positions_by_rebalance_oos_path
                else None,
                "current_file": str(positions_current_oos_path) if positions_current_oos_path else None,
                "diff_file": str(positions_diff_oos_path) if positions_diff_oos_path else None,
            }
            if final_oos_eval is not None
            else None,
        },
        "positions": {
            "by_rebalance_file": str(positions_by_rebalance_path) if positions_by_rebalance_path else None,
            "current_file": str(positions_current_path) if positions_current_path else None,
            "diff_file": str(positions_diff_path) if positions_diff_path else None,
            "shift_days": LABEL_SHIFT_DAYS,
            "buffer_exit": BACKTEST_BUFFER_EXIT,
            "buffer_entry": BACKTEST_BUFFER_ENTRY,
            "window_fields": {
                "signal_asof": "signal_asof",
                "entry_date": "entry_date",
                "next_entry_date": "next_entry_date",
                "holding_window": "holding_window",
            },
        },
        "live": {
            "enabled": LIVE_ENABLED,
            "as_of": live_as_of.strftime("%Y%m%d") if LIVE_ENABLED and live_as_of else None,
            "train_mode": LIVE_TRAIN_MODE if LIVE_ENABLED else None,
            "positions_file": str(live_positions_file) if live_positions_file else None,
            "current_file": str(live_current_file) if live_current_file else None,
            "diff_file": str(positions_diff_live_path) if positions_diff_live_path else None,
        },
        "fundamentals": {
            "enabled": FUNDAMENTALS_ENABLED,
            "source": FUNDAMENTALS_SOURCE if FUNDAMENTALS_ENABLED else None,
            "provider": FUNDAMENTALS_PROVIDER if FUNDAMENTALS_ENABLED else None,
            "file": str(FUNDAMENTALS_FILE) if FUNDAMENTALS_FILE else None,
            "cache_dir": str(fund_cache_dir) if fund_cache_dir else None,
            "features": FUNDAMENTALS_FEATURES,
            "log_market_cap": FUNDAMENTALS_LOG_MCAP,
            "market_cap_col": FUNDAMENTALS_MCAP_COL,
            "provider_overlay": {
                "enabled": FUNDAMENTALS_PROVIDER_OVERLAY_ENABLED,
                "source": (
                    FUNDAMENTALS_PROVIDER_OVERLAY_SOURCE if FUNDAMENTALS_PROVIDER_OVERLAY_ENABLED else None
                ),
                "provider": (
                    FUNDAMENTALS_PROVIDER_OVERLAY_PROVIDER
                    if FUNDAMENTALS_PROVIDER_OVERLAY_ENABLED
                    else None
                ),
                "cache_dir": str(provider_overlay_cache_dir) if provider_overlay_cache_dir else None,
                "features": FUNDAMENTALS_PROVIDER_OVERLAY_FEATURES,
            },
        },
        "industry": {
            "enabled": INDUSTRY_ENABLED,
            "source": INDUSTRY_SOURCE if INDUSTRY_ENABLED else None,
            "file": str(INDUSTRY_FILE) if INDUSTRY_FILE else None,
            "keep_columns": INDUSTRY_KEEP_COLUMNS,
            "resolved_columns": passthrough_cols,
            "ffill": INDUSTRY_FFILL,
            "ffill_limit": INDUSTRY_FFILL_LIMIT,
        },
        "walk_forward": {
            "enabled": WF_ENABLED,
            "n_windows": WF_N_WINDOWS,
            "actual_windows": len(walk_forward_results),
            "test_size": WF_TEST_SIZE,
            "step_size": WF_STEP_SIZE,
            "anchor_end": WF_ANCHOR_END,
            "feature_top_k": WF_FEATURE_TOP_K,
            "feature_importance_windows": int(walk_forward_importance_df["window"].nunique())
            if not walk_forward_importance_df.empty
            else 0,
            "feature_importance_file": str(walk_forward_importance_path)
            if walk_forward_importance_path
            else None,
            "feature_stability_file": str(walk_forward_feature_stability_path)
            if walk_forward_feature_stability_path
            else None,
            "stable_top_features": walk_forward_feature_stability_df["feature"]
            .head(WF_FEATURE_TOP_K)
            .astype(str)
            .tolist()
            if not walk_forward_feature_stability_df.empty
            else [],
            "results": walk_forward_results,
        },
    }
    save_json(summary, run_dir / "summary.json")
    with (run_dir / "config.used.yml").open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config, handle, sort_keys=False)
    if LIVE_ENABLED:
        latest_payload = {
            "run_dir": str(run_dir),
            "run_name": run_name,
            "timestamp": run_stamp,
            "config_hash": run_hash,
            "summary_file": str(run_dir / "summary.json"),
            "as_of": summary.get("live", {}).get("as_of"),
            "positions_file": summary.get("live", {}).get("positions_file"),
            "current_file": summary.get("live", {}).get("current_file"),
            "diff_file": summary.get("live", {}).get("diff_file"),
        }
        save_json(latest_payload, run_dir.parent / "latest.json")
