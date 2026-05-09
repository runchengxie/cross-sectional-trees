from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from ..execution import describe_execution_model
from ..execution_sim import describe_execution_sim_config


def _build_backtest_exposure_summary(
    *,
    style_path: Any,
    industry_path: Any,
    active_summary_path: Any,
    style_summary: Mapping[str, Any] | None,
    industry_summary: Mapping[str, Any] | None,
) -> dict[str, Any]:
    style_meta = style_summary if isinstance(style_summary, Mapping) else {}
    industry_meta = industry_summary if isinstance(industry_summary, Mapping) else {}
    latest_rebalance_date = style_meta.get("latest_rebalance_date")
    if latest_rebalance_date is None:
        latest_rebalance_date = industry_meta.get("latest_rebalance_date")
    latest_entry_date = style_meta.get("latest_entry_date")
    if latest_entry_date is None:
        latest_entry_date = industry_meta.get("latest_entry_date")
    return {
        "style_file": str(style_path) if style_path else None,
        "industry_file": str(industry_path) if industry_path else None,
        "active_summary_file": str(active_summary_path) if active_summary_path else None,
        "latest_rebalance_date": latest_rebalance_date,
        "latest_entry_date": latest_entry_date,
        "style_factors": style_meta.get("factors", {}),
        "latest_style": style_meta.get("latest", {}),
        "industry_column": industry_meta.get("industry_column"),
        "latest_industry": industry_meta.get("latest", {}),
    }


def _build_execution_sim_summary(
    *,
    summary: Mapping[str, Any] | None,
    config: Any,
    orders_path: Any,
    fills_path: Any,
) -> dict[str, Any]:
    if isinstance(summary, Mapping):
        out = dict(summary)
    else:
        out = {
            "enabled": bool(getattr(config, "enabled", False)),
            "status": "not_run" if getattr(config, "enabled", False) else "disabled",
            "config": describe_execution_sim_config(config),
        }
    out["orders_file"] = str(orders_path) if orders_path else None
    out["fills_file"] = str(fills_path) if fills_path else None
    return out


def _path_text(value: Any) -> str | None:
    return str(value) if value else None


def _date_text(value: Any) -> str | None:
    return value.strftime("%Y%m%d") if value else None


def _date_list_text(values: Any) -> list[str]:
    return [pd.to_datetime(date).strftime("%Y%m%d") for date in values]


def _build_run_section(ctx: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "name": ctx["run_name"],
        "timestamp": ctx["run_stamp"],
        "config_hash": ctx["run_hash"],
        "config_path": _path_text(ctx["config_path"]),
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
        "log_file": _path_text(ctx["active_log_file"]),
    }


def _build_data_section(ctx: Mapping[str, Any]) -> dict[str, Any]:
    return {
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
    }


def _build_dataset_section(
    *,
    ctx: Mapping[str, Any],
    art: Mapping[str, Any],
) -> dict[str, Any]:
    dataset = ctx["dataset"]
    return {
        "schema": dataset.schema.to_dict() if dataset is not None else None,
        "rows": int(len(dataset.frame)) if dataset is not None else 0,
        "file": _path_text(art["dataset_path"]),
        "index": [dataset.schema.date_col, dataset.schema.instrument_col]
        if dataset is not None
        else None,
    }


def _build_universe_section(ctx: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "mode": ctx["universe_mode_effective"],
        "by_date_file": _path_text(ctx["by_date_file"]),
        "require_by_date": ctx["REQUIRE_BY_DATE"],
        "drop_suspended": ctx["DROP_SUSPENDED"],
        "suspended_policy": ctx["SUSPENDED_POLICY"],
    }


def _build_label_section(ctx: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "horizon_days": ctx["LABEL_HORIZON_DAYS"],
        "horizon_days_effective": ctx["label_horizon_effective"],
        "horizon_mode": ctx["LABEL_HORIZON_MODE"],
        "rebalance_frequency": ctx["LABEL_REBALANCE_FREQUENCY"],
        "shift_days": ctx["LABEL_SHIFT_DAYS"],
        "winsorize_pct": ctx["WINSORIZE_PCT"],
        "train_target_transform": ctx["TRAIN_TARGET_TRANSFORM"],
    }


def _build_split_section(ctx: Mapping[str, Any]) -> dict[str, Any]:
    rebalance_gap_days = None
    if (
        ctx["SAMPLE_ON_REBALANCE_DATES"]
        and ctx["rebalance_gap_days"] is not None
        and np.isfinite(ctx["rebalance_gap_days"])
    ):
        rebalance_gap_days = float(ctx["rebalance_gap_days"])

    return {
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
        "rebalance_gap_days": rebalance_gap_days,
    }


def _build_eval_section(
    *,
    ctx: Mapping[str, Any],
    art: Mapping[str, Any],
    quantile_mean: pd.Series,
) -> dict[str, Any]:
    return {
        "ic": ctx["ic_stats"],
        "pearson_ic": ctx["pearson_ic_stats"],
        "train_ic": ctx["train_ic_stats"] if ctx["REPORT_TRAIN_IC"] else None,
        "train_ic_raw": ctx["train_ic_raw_stats"] if ctx["train_ic_raw_stats"] else None,
        "train_pearson_ic": ctx["train_pearson_ic_stats"]
        if ctx["REPORT_TRAIN_IC"]
        else None,
        "cv_ic": ctx["cv_stats"],
        "cv_ic_raw": ctx["cv_stats_raw"],
        "signal_direction": ctx["SIGNAL_DIRECTION"],
        "signal_direction_mode": ctx["SIGNAL_DIRECTION_MODE"],
        "error_metrics": ctx["error_metrics"],
        "hit_rate": ctx["hit_rate_stats"],
        "topk_positive_ratio": ctx["topk_positive_stats"],
        "bucket_ic": ctx["bucket_ic_records"],
        "bucket_ic_file": _path_text(art["bucket_ic_path"]),
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
        "rebalance_dates": _date_list_text(ctx["eval_rebalance_dates"]),
        "save_scored_artifact": ctx["SAVE_SCORED_ARTIFACT"],
        "scored_file": _path_text(art["eval_scored_path"]),
        "scored_pred_col": "pred",
        "scored_signal_col": "signal_eval",
        "scored_signal_backtest_col": "signal_backtest",
        "pred_nunique": ctx["pred_nunique"],
        "constant_prediction": ctx["constant_prediction"],
        "feature_importance_file": _path_text(art["feature_importance_path"]),
        "feature_importance_source": ctx["importance_source"],
        "feature_importance_nonzero": ctx["feature_importance_nonzero"],
        "zero_feature_importance": ctx["zero_feature_importance"],
        "permutation_test": ctx["perm_stats"],
    }


def _build_backtest_section(
    *,
    ctx: Mapping[str, Any],
    art: Mapping[str, Any],
) -> dict[str, Any]:
    benchmark_returns_file = None
    if ctx.get("benchmark_returns_file_path") is not None:
        benchmark_returns_file = str(ctx["benchmark_returns_file_path"])

    return {
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
        "rebalance_dates": _date_list_text(ctx["backtest_rebalance_dates"]),
        "shift_days": ctx["LABEL_SHIFT_DAYS"],
        "trading_days_per_year": ctx["BACKTEST_TRADING_DAYS_PER_YEAR"],
        "tradable_col": ctx["BACKTEST_TRADABLE_COL"],
        "signal_direction": ctx["BACKTEST_SIGNAL_DIRECTION"],
        "benchmark_symbol": ctx["benchmark_symbol"],
        "benchmark_returns_file": benchmark_returns_file,
        "transaction_cost_bps": ctx["BACKTEST_COST_BPS_REPORT"],
        "execution_source": ctx["BACKTEST_EXECUTION_SOURCE"],
        "execution": describe_execution_model(ctx["execution_model"]),
        "execution_sim": _build_execution_sim_summary(
            summary=ctx.get("execution_sim_summary"),
            config=ctx["execution_sim_config"],
            orders_path=art["execution_sim_orders_path"],
            fills_path=art["execution_sim_fills_path"],
        ),
        "stats": ctx["bt_stats"],
        "benchmark": ctx["bt_benchmark_stats"],
        "active": ctx["bt_active_stats"],
        "report_file": _path_text(art["backtest_report_path"]),
        "benchmark_compare": {
            "summary_file": _path_text(art["backtest_benchmark_compare_summary_path"]),
            "benchmarks": art["backtest_benchmark_compare_entries"],
        },
        "exposure": _build_backtest_exposure_summary(
            style_path=art["backtest_style_exposure_path"],
            industry_path=art["backtest_industry_exposure_path"],
            active_summary_path=art["backtest_active_exposure_summary_path"],
            style_summary=ctx.get("bt_style_exposure_summary"),
            industry_summary=ctx.get("bt_industry_exposure_summary"),
        ),
        "rolling_sharpe": {
            "windows_months": ctx["ROLLING_WINDOWS_MONTHS"],
            "latest": ctx["rolling_sharpe_latest"],
            "series_files": art["rolling_sharpe_files"],
        },
    }


def _build_oos_backtest_section(
    *,
    ctx: Mapping[str, Any],
    art: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "stats": ctx["bt_stats_oos"],
        "benchmark": ctx["bt_benchmark_stats_oos"],
        "active": ctx["bt_active_stats_oos"],
        "report_file": _path_text(art["backtest_report_oos_path"]),
        "benchmark_compare": {
            "summary_file": _path_text(
                art["backtest_benchmark_compare_summary_oos_path"]
            ),
            "benchmarks": art["backtest_benchmark_compare_oos_entries"],
        },
        "exposure": _build_backtest_exposure_summary(
            style_path=art["backtest_style_exposure_oos_path"],
            industry_path=art["backtest_industry_exposure_oos_path"],
            active_summary_path=art["backtest_active_exposure_summary_oos_path"],
            style_summary=ctx.get("bt_style_exposure_summary_oos"),
            industry_summary=ctx.get("bt_industry_exposure_summary_oos"),
        ),
        "rolling_sharpe": {
            "windows_months": ctx["ROLLING_WINDOWS_MONTHS"],
            "latest": ctx["rolling_sharpe_latest_oos"],
            "series_files": art["rolling_sharpe_oos_files"],
        },
    }


def _build_oos_positions_section(art: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "by_rebalance_file": _path_text(art["positions_by_rebalance_oos_path"]),
        "current_file": _path_text(art["positions_current_oos_path"]),
        "diff_file": _path_text(art["positions_diff_oos_path"]),
    }


def _build_final_oos_section(
    *,
    ctx: Mapping[str, Any],
    art: Mapping[str, Any],
    quantile_mean_oos: pd.Series,
) -> dict[str, Any]:
    has_oos_eval = ctx["final_oos_eval"] is not None

    return {
        "enabled": ctx["FINAL_OOS_ENABLED"],
        "size": ctx["FINAL_OOS_SIZE_RAW"],
        "dates": int(ctx["final_oos_len"]) if ctx["FINAL_OOS_ENABLED"] else 0,
        "start": _date_text(ctx["final_oos_start"]),
        "end": _date_text(ctx["final_oos_end"]),
        "ic": ctx["ic_stats_oos"] if has_oos_eval else None,
        "pearson_ic": ctx["pearson_ic_stats_oos"] if has_oos_eval else None,
        "error_metrics": ctx["error_metrics_oos"] if has_oos_eval else None,
        "hit_rate": ctx["hit_rate_stats_oos"] if has_oos_eval else None,
        "topk_positive_ratio": ctx["topk_positive_stats_oos"] if has_oos_eval else None,
        "bucket_ic": ctx["bucket_ic_records_oos"] if has_oos_eval else None,
        "bucket_ic_file": _path_text(art["bucket_ic_oos_path"]),
        "rolling_ic": {
            "windows_months": ctx["ROLLING_WINDOWS_MONTHS"],
            "obs_per_year": ctx["rolling_ic_oos_obs_per_year"],
            "latest": ctx["rolling_ic_latest_oos"],
            "series_files": art["rolling_ic_oos_files"],
        }
        if has_oos_eval
        else None,
        "quantile_mean": quantile_mean_oos.to_dict()
        if has_oos_eval and not quantile_mean_oos.empty
        else {},
        "long_short": float(quantile_mean_oos.iloc[-1] - quantile_mean_oos.iloc[0])
        if has_oos_eval and not quantile_mean_oos.empty
        else None,
        "turnover_mean": float(ctx["turnover_series_oos"].mean())
        if has_oos_eval and not ctx["turnover_series_oos"].empty
        else None,
        "turnover_count": int(ctx["turnover_series_oos"].shape[0])
        if has_oos_eval
        else 0,
        "backtest": _build_oos_backtest_section(ctx=ctx, art=art)
        if has_oos_eval
        else None,
        "positions": _build_oos_positions_section(art) if has_oos_eval else None,
    }


def _build_positions_section(
    *,
    ctx: Mapping[str, Any],
    art: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "by_rebalance_file": _path_text(art["positions_by_rebalance_path"]),
        "current_file": _path_text(art["positions_current_path"]),
        "diff_file": _path_text(art["positions_diff_path"]),
        "shift_days": ctx["LABEL_SHIFT_DAYS"],
        "buffer_exit": ctx["BACKTEST_BUFFER_EXIT"],
        "buffer_entry": ctx["BACKTEST_BUFFER_ENTRY"],
        "window_fields": {
            "signal_asof": "signal_asof",
            "entry_date": "entry_date",
            "next_entry_date": "next_entry_date",
            "holding_window": "holding_window",
        },
    }


def _build_live_section(
    *,
    ctx: Mapping[str, Any],
    art: Mapping[str, Any],
) -> dict[str, Any]:
    live_enabled = ctx["LIVE_ENABLED"]
    return {
        "enabled": live_enabled,
        "as_of": _date_text(ctx["live_as_of"]) if live_enabled else None,
        "signal_asof": _date_text(ctx["live_signal_asof"])
        if live_enabled and ctx.get("live_signal_asof") is not None
        else None,
        "entry_date": _date_text(ctx["live_entry_date"])
        if live_enabled and ctx.get("live_entry_date") is not None
        else None,
        "execution_calendar": ctx.get("live_execution_calendar") if live_enabled else None,
        "execution_open": ctx.get("live_execution_open") if live_enabled else None,
        "execution_status": ctx.get("live_execution_status") if live_enabled else None,
        "train_mode": ctx["LIVE_TRAIN_MODE"] if live_enabled else None,
        "positions_file": _path_text(art["live_positions_file"]),
        "current_file": _path_text(art["live_current_file"]),
        "diff_file": _path_text(art["positions_diff_live_path"]),
    }


def _build_quality_section(ctx: Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(ctx.get("quality_summary"), Mapping):
        return ctx["quality_summary"]
    return {"preflight": None}


def _build_fundamentals_section(ctx: Mapping[str, Any]) -> dict[str, Any]:
    overlay_enabled = ctx["FUNDAMENTALS_PROVIDER_OVERLAY_ENABLED"]
    return {
        "enabled": ctx["FUNDAMENTALS_ENABLED"],
        "source": ctx["FUNDAMENTALS_SOURCE"] if ctx["FUNDAMENTALS_ENABLED"] else None,
        "provider": ctx["FUNDAMENTALS_PROVIDER"] if ctx["FUNDAMENTALS_ENABLED"] else None,
        "file": _path_text(ctx["FUNDAMENTALS_FILE"]),
        "cache_dir": _path_text(ctx["fund_cache_dir"]),
        "features": ctx["FUNDAMENTALS_FEATURES"],
        "log_market_cap": ctx["FUNDAMENTALS_LOG_MCAP"],
        "market_cap_col": ctx["FUNDAMENTALS_MCAP_COL"],
        "provider_overlay": {
            "enabled": overlay_enabled,
            "source": ctx["FUNDAMENTALS_PROVIDER_OVERLAY_SOURCE"]
            if overlay_enabled
            else None,
            "provider": ctx["FUNDAMENTALS_PROVIDER_OVERLAY_PROVIDER"]
            if overlay_enabled
            else None,
            "cache_dir": _path_text(ctx["provider_overlay_cache_dir"]),
            "features": ctx["FUNDAMENTALS_PROVIDER_OVERLAY_FEATURES"],
        },
    }


def _build_industry_section(ctx: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "enabled": ctx["INDUSTRY_ENABLED"],
        "source": ctx["INDUSTRY_SOURCE"] if ctx["INDUSTRY_ENABLED"] else None,
        "file": _path_text(ctx["INDUSTRY_FILE"]),
        "keep_columns": ctx["INDUSTRY_KEEP_COLUMNS"],
        "resolved_columns": ctx["passthrough_cols"],
        "ffill": ctx["INDUSTRY_FFILL"],
        "ffill_limit": ctx["INDUSTRY_FFILL_LIMIT"],
    }


def _build_walk_forward_section(
    *,
    ctx: Mapping[str, Any],
    art: Mapping[str, Any],
) -> dict[str, Any]:
    stability_df = ctx["walk_forward_feature_stability_df"]
    return {
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
        "feature_importance_file": _path_text(art["walk_forward_importance_path"]),
        "feature_stability_file": _path_text(art["walk_forward_feature_stability_path"]),
        "stable_top_features": stability_df["feature"]
        .head(ctx["WF_FEATURE_TOP_K"])
        .astype(str)
        .tolist()
        if not stability_df.empty
        else [],
        "results": ctx["walk_forward_results"],
    }


def build_run_summary_sections(
    *,
    context: Mapping[str, Any],
    artifacts: Mapping[str, Any],
) -> dict[str, Any]:
    ctx = context
    art = artifacts

    return {
        "run": _build_run_section(ctx),
        "data": _build_data_section(ctx),
        "dataset": _build_dataset_section(ctx=ctx, art=art),
        "universe": _build_universe_section(ctx),
        "label": _build_label_section(ctx),
        "split": _build_split_section(ctx),
        "eval": _build_eval_section(
            ctx=ctx,
            art=art,
            quantile_mean=ctx["quantile_mean"],
        ),
        "backtest": _build_backtest_section(ctx=ctx, art=art),
        "final_oos": _build_final_oos_section(
            ctx=ctx,
            art=art,
            quantile_mean_oos=ctx["quantile_mean_oos"],
        ),
        "positions": _build_positions_section(ctx=ctx, art=art),
        "live": _build_live_section(ctx=ctx, art=art),
        "quality": _build_quality_section(ctx),
        "fundamentals": _build_fundamentals_section(ctx),
        "industry": _build_industry_section(ctx),
        "walk_forward": _build_walk_forward_section(ctx=ctx, art=art),
    }
