from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd
import yaml

from ..execution import describe_execution_model
from .support import save_json


def build_run_summary(
    *,
    context: Mapping[str, Any],
    artifacts: Mapping[str, Any],
) -> dict[str, Any]:
    ctx = context
    art = artifacts
    dataset = ctx["dataset"]
    quantile_mean = ctx["quantile_mean"]
    quantile_mean_oos = ctx["quantile_mean_oos"]

    return {
        "run": {
            "name": ctx["run_name"],
            "timestamp": ctx["run_stamp"],
            "config_hash": ctx["run_hash"],
            "config_path": str(ctx["config_path"]) if ctx["config_path"] else None,
            "config_source": ctx["config_source"],
            "model_type": ctx["MODEL_TYPE"],
            "sample_weight_mode": ctx["SAMPLE_WEIGHT_MODE"],
            "sample_weight_params": ctx["SAMPLE_WEIGHT_PARAMS"],
            "train_window": {
                "mode": ctx["TRAIN_WINDOW_MODE"],
                "size": ctx["TRAIN_WINDOW_SIZE"],
                "unit": ctx["TRAIN_WINDOW_UNIT"],
            },
            "output_dir": str(ctx["run_dir"]),
            "log_file": str(ctx["active_log_file"]) if ctx["active_log_file"] else None,
        },
        "data": {
            "market": ctx["MARKET"],
            "provider": ctx["provider"],
            "start_date": ctx["START_DATE"],
            "end_date": ctx["END_DATE"],
            "price_col": ctx["PRICE_COL"],
            "price_col_diagnostics": ctx["price_col_diagnostics"],
            "symbols": len(ctx["symbols"]),
            "rows": len(ctx["df_full"]),
            "rows_model": len(ctx["df_model_all"]),
            "rows_model_in_sample": len(ctx["df_model"]),
            "rows_model_oos": len(ctx["df_model_oos"]) if ctx["FINAL_OOS_ENABLED"] else 0,
            "min_symbols_per_date": ctx["MIN_SYMBOLS_PER_DATE"],
            "dropped_dates": int(ctx["dropped_date_counts"].shape[0]),
        },
        "dataset": {
            "schema": dataset.schema.to_dict() if dataset is not None else None,
            "rows": int(len(dataset.frame)) if dataset is not None else 0,
            "file": str(art["dataset_path"]) if art["dataset_path"] else None,
            "index": [dataset.schema.date_col, dataset.schema.instrument_col]
            if dataset is not None
            else None,
        },
        "universe": {
            "mode": ctx["universe_mode_effective"],
            "by_date_file": str(ctx["by_date_file"]) if ctx["by_date_file"] else None,
            "require_by_date": ctx["REQUIRE_BY_DATE"],
            "drop_suspended": ctx["DROP_SUSPENDED"],
            "suspended_policy": ctx["SUSPENDED_POLICY"],
        },
        "label": {
            "horizon_days": ctx["LABEL_HORIZON_DAYS"],
            "horizon_days_effective": ctx["label_horizon_effective"],
            "horizon_mode": ctx["LABEL_HORIZON_MODE"],
            "rebalance_frequency": ctx["LABEL_REBALANCE_FREQUENCY"],
            "shift_days": ctx["LABEL_SHIFT_DAYS"],
            "winsorize_pct": ctx["WINSORIZE_PCT"],
            "train_target_transform": ctx["TRAIN_TARGET_TRANSFORM"],
        },
        "split": {
            "train_dates": len(ctx["train_dates"]),
            "train_dates_raw": len(ctx["train_dates_full"]),
            "test_dates": len(ctx["test_dates"]),
            "purge_days": ctx["purge_days"],
            "embargo_days": ctx["embargo_days"],
            "purge_steps": ctx["PURGE_STEPS"],
            "embargo_steps": ctx["EMBARGO_STEPS"],
            "train_window": {
                "mode": ctx["TRAIN_WINDOW_MODE"],
                "size": ctx["TRAIN_WINDOW_SIZE"],
                "unit": ctx["TRAIN_WINDOW_UNIT"],
                "applied": bool(
                    ctx["TRAIN_WINDOW_MODE"] == "rolling"
                    and len(ctx["train_dates"]) < len(ctx["train_dates_full"])
                ),
            },
            "rebalance_gap_days": float(ctx["rebalance_gap_days"])
            if ctx["SAMPLE_ON_REBALANCE_DATES"]
            and ctx["rebalance_gap_days"] is not None
            and np.isfinite(ctx["rebalance_gap_days"])
            else None,
        },
        "eval": {
            "ic": ctx["ic_stats"],
            "pearson_ic": ctx["pearson_ic_stats"],
            "train_ic": ctx["train_ic_stats"] if ctx["REPORT_TRAIN_IC"] else None,
            "train_ic_raw": ctx["train_ic_raw_stats"] if ctx["train_ic_raw_stats"] else None,
            "train_pearson_ic": (
                ctx["train_pearson_ic_stats"] if ctx["REPORT_TRAIN_IC"] else None
            ),
            "cv_ic": ctx["cv_stats"],
            "cv_ic_raw": ctx["cv_stats_raw"],
            "signal_direction": ctx["SIGNAL_DIRECTION"],
            "signal_direction_mode": ctx["SIGNAL_DIRECTION_MODE"],
            "error_metrics": ctx["error_metrics"],
            "hit_rate": ctx["hit_rate_stats"],
            "topk_positive_ratio": ctx["topk_positive_stats"],
            "bucket_ic": ctx["bucket_ic_records"],
            "bucket_ic_file": str(art["bucket_ic_path"]) if art["bucket_ic_path"] else None,
            "rolling_ic": {
                "windows_months": ctx["ROLLING_WINDOWS_MONTHS"],
                "obs_per_year": ctx["rolling_ic_obs_per_year"],
                "latest": ctx["rolling_ic_latest"],
                "series_files": art["rolling_ic_files"],
            },
            "quantile_mean": quantile_mean.to_dict() if not quantile_mean.empty else {},
            "long_short": float(quantile_mean.iloc[-1] - quantile_mean.iloc[0])
            if not quantile_mean.empty
            else None,
            "turnover_mean": float(ctx["turnover_series"].mean())
            if not ctx["turnover_series"].empty
            else None,
            "turnover_count": int(ctx["turnover_series"].shape[0]),
            "buffer_exit": ctx["EVAL_BUFFER_EXIT"],
            "buffer_entry": ctx["EVAL_BUFFER_ENTRY"],
            "sample_on_rebalance_dates": ctx["SAMPLE_ON_REBALANCE_DATES"],
            "rebalance_frequency": ctx["REBALANCE_FREQUENCY"],
            "rebalance_dates": [
                pd.to_datetime(date).strftime("%Y%m%d")
                for date in ctx["eval_rebalance_dates"]
            ],
            "save_scored_artifact": ctx["SAVE_SCORED_ARTIFACT"],
            "scored_file": str(art["eval_scored_path"]) if art["eval_scored_path"] else None,
            "scored_pred_col": "pred",
            "scored_signal_col": "signal_eval",
            "scored_signal_backtest_col": "signal_backtest",
            "pred_nunique": ctx["pred_nunique"],
            "constant_prediction": ctx["constant_prediction"],
            "feature_importance_file": (
                str(art["feature_importance_path"])
                if art["feature_importance_path"]
                else None
            ),
            "feature_importance_source": ctx["importance_source"],
            "feature_importance_nonzero": ctx["feature_importance_nonzero"],
            "zero_feature_importance": ctx["zero_feature_importance"],
            "permutation_test": ctx["perm_stats"],
        },
        "backtest": {
            "enabled": ctx["BACKTEST_ENABLED"],
            "exit_mode": ctx["BACKTEST_EXIT_MODE"],
            "exit_horizon_days": ctx["BACKTEST_EXIT_HORIZON_DAYS"],
            "exit_price_policy": ctx["BACKTEST_EXIT_PRICE_POLICY"],
            "exit_fallback_policy": ctx["BACKTEST_EXIT_FALLBACK_POLICY"],
            "buffer_exit": ctx["BACKTEST_BUFFER_EXIT"],
            "buffer_entry": ctx["BACKTEST_BUFFER_ENTRY"],
            "mode": "long_only" if ctx["BACKTEST_LONG_ONLY"] else "long_short",
            "weighting": ctx["BACKTEST_WEIGHTING"],
            "group_col": ctx["BACKTEST_GROUP_COL"],
            "max_names_per_group": ctx["BACKTEST_MAX_NAMES_PER_GROUP"],
            "top_k": ctx["BACKTEST_TOP_K"],
            "short_k": ctx["BACKTEST_SHORT_K"],
            "rebalance_frequency": ctx["BACKTEST_REBALANCE_FREQUENCY"],
            "rebalance_dates": [
                pd.to_datetime(date).strftime("%Y%m%d")
                for date in ctx["backtest_rebalance_dates"]
            ],
            "shift_days": ctx["LABEL_SHIFT_DAYS"],
            "trading_days_per_year": ctx["BACKTEST_TRADING_DAYS_PER_YEAR"],
            "tradable_col": ctx["BACKTEST_TRADABLE_COL"],
            "signal_direction": ctx["BACKTEST_SIGNAL_DIRECTION"],
            "benchmark_symbol": ctx["benchmark_symbol"],
            "benchmark_returns_file": (
                str(ctx["benchmark_returns_file_path"])
                if ctx.get("benchmark_returns_file_path") is not None
                else None
            ),
            "transaction_cost_bps": ctx["BACKTEST_COST_BPS_REPORT"],
            "execution_source": ctx["BACKTEST_EXECUTION_SOURCE"],
            "execution": describe_execution_model(ctx["execution_model"]),
            "stats": ctx["bt_stats"],
            "benchmark": ctx["bt_benchmark_stats"],
            "active": ctx["bt_active_stats"],
            "rolling_sharpe": {
                "windows_months": ctx["ROLLING_WINDOWS_MONTHS"],
                "latest": ctx["rolling_sharpe_latest"],
                "series_files": art["rolling_sharpe_files"],
            },
        },
        "final_oos": {
            "enabled": ctx["FINAL_OOS_ENABLED"],
            "size": ctx["FINAL_OOS_SIZE_RAW"],
            "dates": int(ctx["final_oos_len"]) if ctx["FINAL_OOS_ENABLED"] else 0,
            "start": ctx["final_oos_start"].strftime("%Y%m%d")
            if ctx["final_oos_start"]
            else None,
            "end": ctx["final_oos_end"].strftime("%Y%m%d")
            if ctx["final_oos_end"]
            else None,
            "ic": ctx["ic_stats_oos"] if ctx["final_oos_eval"] is not None else None,
            "pearson_ic": (
                ctx["pearson_ic_stats_oos"]
                if ctx["final_oos_eval"] is not None
                else None
            ),
            "error_metrics": (
                ctx["error_metrics_oos"] if ctx["final_oos_eval"] is not None else None
            ),
            "hit_rate": (
                ctx["hit_rate_stats_oos"] if ctx["final_oos_eval"] is not None else None
            ),
            "topk_positive_ratio": (
                ctx["topk_positive_stats_oos"]
                if ctx["final_oos_eval"] is not None
                else None
            ),
            "bucket_ic": (
                ctx["bucket_ic_records_oos"] if ctx["final_oos_eval"] is not None else None
            ),
            "bucket_ic_file": (
                str(art["bucket_ic_oos_path"]) if art["bucket_ic_oos_path"] else None
            ),
            "rolling_ic": {
                "windows_months": ctx["ROLLING_WINDOWS_MONTHS"],
                "obs_per_year": ctx["rolling_ic_oos_obs_per_year"],
                "latest": ctx["rolling_ic_latest_oos"],
                "series_files": art["rolling_ic_oos_files"],
            }
            if ctx["final_oos_eval"] is not None
            else None,
            "quantile_mean": quantile_mean_oos.to_dict()
            if ctx["final_oos_eval"] is not None and not quantile_mean_oos.empty
            else {},
            "long_short": float(quantile_mean_oos.iloc[-1] - quantile_mean_oos.iloc[0])
            if ctx["final_oos_eval"] is not None and not quantile_mean_oos.empty
            else None,
            "turnover_mean": float(ctx["turnover_series_oos"].mean())
            if ctx["final_oos_eval"] is not None and not ctx["turnover_series_oos"].empty
            else None,
            "turnover_count": (
                int(ctx["turnover_series_oos"].shape[0])
                if ctx["final_oos_eval"] is not None
                else 0
            ),
            "backtest": {
                "stats": ctx["bt_stats_oos"],
                "benchmark": ctx["bt_benchmark_stats_oos"],
                "active": ctx["bt_active_stats_oos"],
                "rolling_sharpe": {
                    "windows_months": ctx["ROLLING_WINDOWS_MONTHS"],
                    "latest": ctx["rolling_sharpe_latest_oos"],
                    "series_files": art["rolling_sharpe_oos_files"],
                },
            }
            if ctx["final_oos_eval"] is not None
            else None,
            "positions": {
                "by_rebalance_file": str(art["positions_by_rebalance_oos_path"])
                if art["positions_by_rebalance_oos_path"]
                else None,
                "current_file": str(art["positions_current_oos_path"])
                if art["positions_current_oos_path"]
                else None,
                "diff_file": str(art["positions_diff_oos_path"])
                if art["positions_diff_oos_path"]
                else None,
            }
            if ctx["final_oos_eval"] is not None
            else None,
        },
        "positions": {
            "by_rebalance_file": str(art["positions_by_rebalance_path"])
            if art["positions_by_rebalance_path"]
            else None,
            "current_file": str(art["positions_current_path"])
            if art["positions_current_path"]
            else None,
            "diff_file": str(art["positions_diff_path"])
            if art["positions_diff_path"]
            else None,
            "shift_days": ctx["LABEL_SHIFT_DAYS"],
            "buffer_exit": ctx["BACKTEST_BUFFER_EXIT"],
            "buffer_entry": ctx["BACKTEST_BUFFER_ENTRY"],
            "window_fields": {
                "signal_asof": "signal_asof",
                "entry_date": "entry_date",
                "next_entry_date": "next_entry_date",
                "holding_window": "holding_window",
            },
        },
        "live": {
            "enabled": ctx["LIVE_ENABLED"],
            "as_of": ctx["live_as_of"].strftime("%Y%m%d")
            if ctx["LIVE_ENABLED"] and ctx["live_as_of"]
            else None,
            "train_mode": ctx["LIVE_TRAIN_MODE"] if ctx["LIVE_ENABLED"] else None,
            "positions_file": str(art["live_positions_file"])
            if art["live_positions_file"]
            else None,
            "current_file": str(art["live_current_file"])
            if art["live_current_file"]
            else None,
            "diff_file": str(art["positions_diff_live_path"])
            if art["positions_diff_live_path"]
            else None,
        },
        "fundamentals": {
            "enabled": ctx["FUNDAMENTALS_ENABLED"],
            "source": ctx["FUNDAMENTALS_SOURCE"] if ctx["FUNDAMENTALS_ENABLED"] else None,
            "provider": (
                ctx["FUNDAMENTALS_PROVIDER"] if ctx["FUNDAMENTALS_ENABLED"] else None
            ),
            "file": str(ctx["FUNDAMENTALS_FILE"]) if ctx["FUNDAMENTALS_FILE"] else None,
            "cache_dir": str(ctx["fund_cache_dir"]) if ctx["fund_cache_dir"] else None,
            "features": ctx["FUNDAMENTALS_FEATURES"],
            "log_market_cap": ctx["FUNDAMENTALS_LOG_MCAP"],
            "market_cap_col": ctx["FUNDAMENTALS_MCAP_COL"],
            "provider_overlay": {
                "enabled": ctx["FUNDAMENTALS_PROVIDER_OVERLAY_ENABLED"],
                "source": (
                    ctx["FUNDAMENTALS_PROVIDER_OVERLAY_SOURCE"]
                    if ctx["FUNDAMENTALS_PROVIDER_OVERLAY_ENABLED"]
                    else None
                ),
                "provider": (
                    ctx["FUNDAMENTALS_PROVIDER_OVERLAY_PROVIDER"]
                    if ctx["FUNDAMENTALS_PROVIDER_OVERLAY_ENABLED"]
                    else None
                ),
                "cache_dir": str(ctx["provider_overlay_cache_dir"])
                if ctx["provider_overlay_cache_dir"]
                else None,
                "features": ctx["FUNDAMENTALS_PROVIDER_OVERLAY_FEATURES"],
            },
        },
        "industry": {
            "enabled": ctx["INDUSTRY_ENABLED"],
            "source": ctx["INDUSTRY_SOURCE"] if ctx["INDUSTRY_ENABLED"] else None,
            "file": str(ctx["INDUSTRY_FILE"]) if ctx["INDUSTRY_FILE"] else None,
            "keep_columns": ctx["INDUSTRY_KEEP_COLUMNS"],
            "resolved_columns": ctx["passthrough_cols"],
            "ffill": ctx["INDUSTRY_FFILL"],
            "ffill_limit": ctx["INDUSTRY_FFILL_LIMIT"],
        },
        "walk_forward": {
            "enabled": ctx["WF_ENABLED"],
            "n_windows": ctx["WF_N_WINDOWS"],
            "actual_windows": len(ctx["walk_forward_results"]),
            "test_size": ctx["WF_TEST_SIZE"],
            "step_size": ctx["WF_STEP_SIZE"],
            "anchor_end": ctx["WF_ANCHOR_END"],
            "feature_top_k": ctx["WF_FEATURE_TOP_K"],
            "feature_importance_windows": int(
                ctx["walk_forward_importance_df"]["window"].nunique()
            )
            if not ctx["walk_forward_importance_df"].empty
            else 0,
            "feature_importance_file": str(art["walk_forward_importance_path"])
            if art["walk_forward_importance_path"]
            else None,
            "feature_stability_file": str(art["walk_forward_feature_stability_path"])
            if art["walk_forward_feature_stability_path"]
            else None,
            "stable_top_features": ctx["walk_forward_feature_stability_df"]["feature"]
            .head(ctx["WF_FEATURE_TOP_K"])
            .astype(str)
            .tolist()
            if not ctx["walk_forward_feature_stability_df"].empty
            else [],
            "results": ctx["walk_forward_results"],
        },
    }


def write_run_metadata(
    *,
    context: Mapping[str, Any],
    summary: Mapping[str, Any],
) -> None:
    ctx = context
    run_dir = ctx["run_dir"]

    save_json(summary, run_dir / "summary.json")
    with (run_dir / "config.used.yml").open("w", encoding="utf-8") as handle:
        yaml.safe_dump(ctx["config"], handle, sort_keys=False)

    if ctx["LIVE_ENABLED"]:
        latest_payload = {
            "run_dir": str(run_dir),
            "run_name": ctx["run_name"],
            "timestamp": ctx["run_stamp"],
            "config_hash": ctx["run_hash"],
            "summary_file": str(run_dir / "summary.json"),
            "as_of": summary.get("live", {}).get("as_of"),
            "positions_file": summary.get("live", {}).get("positions_file"),
            "current_file": summary.get("live", {}).get("current_file"),
            "diff_file": summary.get("live", {}).get("diff_file"),
        }
        save_json(latest_payload, run_dir.parent / "latest.json")
