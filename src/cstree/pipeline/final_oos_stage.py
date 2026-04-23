from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from ..modeling import build_model, fit_model
from ..split import build_sample_weight
from .dates import _slice_with_train_window
from .eval import _evaluate_period
from .stats import (
    _compute_rolling_ic,
    _compute_rolling_sharpe,
    _latest_rolling_stats,
)
from .support import _annotate_positions_window

logger = logging.getLogger("cstree")


def run_final_oos_stage(
    *,
    final_oos_enabled: bool,
    final_oos_dates: np.ndarray,
    df_full: pd.DataFrame,
    df_model_sorted: pd.DataFrame,
    all_date_start_rows: np.ndarray,
    all_date_end_rows: np.ndarray,
    all_date_to_pos: dict[pd.Timestamp, int],
    all_dates: np.ndarray,
    train_window_mode: str,
    train_window_size: int | None,
    train_window_unit: str | None,
    model_type: str,
    model_params: dict[str, Any],
    sample_weight_mode: str,
    sample_weight_params: dict[str, Any],
    features: list[str],
    train_target: str,
    period_eval_context: dict[str, Any],
    rolling_windows_months: list[int],
) -> dict[str, Any]:
    final_oos_eval = None
    ic_series_oos = pd.Series(dtype=float, name="ic")
    ic_stats_oos = {}
    pearson_ic_series_oos = pd.Series(dtype=float, name="ic_pearson")
    pearson_ic_stats_oos = {}
    error_metrics_oos = {}
    hit_rate_stats_oos = {}
    topk_positive_stats_oos = {}
    bucket_ic_records_oos: list[dict[str, Any]] = []
    quantile_ts_oos = pd.DataFrame()
    quantile_mean_oos = pd.Series(dtype=float)
    turnover_series_oos = pd.Series(dtype=float, name="turnover")
    positions_by_rebalance_oos = None
    bt_stats_oos = None
    bt_net_series_oos = pd.Series(dtype=float, name="net_return")
    bt_gross_series_oos = pd.Series(dtype=float, name="gross_return")
    bt_turnover_series_oos = pd.Series(dtype=float, name="turnover")
    bt_benchmark_series_oos = pd.Series(dtype=float, name="benchmark_return")
    bt_active_series_oos = pd.Series(dtype=float, name="active_return")
    bt_benchmark_stats_oos = None
    bt_active_stats_oos = None
    bt_periods_oos: list[dict[str, Any]] = []
    bt_style_exposure_oos = pd.DataFrame()
    bt_style_exposure_summary_oos: dict[str, Any] = {}
    bt_industry_exposure_oos = pd.DataFrame()
    bt_industry_exposure_summary_oos: dict[str, Any] = {}
    bt_active_exposure_summary_oos = pd.DataFrame()
    rolling_ic_oos_results: dict[str, pd.DataFrame] = {}
    rolling_ic_oos_obs_per_year = np.nan
    rolling_ic_latest_oos: dict[str, dict | None] = {}
    rolling_sharpe_oos_results: dict[str, pd.DataFrame] = {}
    rolling_sharpe_latest_oos: dict[str, dict | None] = {}

    if final_oos_enabled and final_oos_dates.size > 0:
        oos_start = pd.to_datetime(final_oos_dates[0])
        oos_end = pd.to_datetime(final_oos_dates[-1])
        oos_df_full = df_full[
            (df_full["trade_date"] >= oos_start) & (df_full["trade_date"] <= oos_end)
        ].copy()
        if oos_df_full.empty:
            logger.info(
                "Final OOS evaluation skipped: no data between %s and %s.",
                oos_start.date(),
                oos_end.date(),
            )
        else:
            logger.info("Fitting final model on all in-sample data for OOS evaluation ...")
            final_model = build_model(model_type, model_params)
            df_oos_train, _ = _slice_with_train_window(
                df_model_sorted,
                all_date_start_rows,
                all_date_end_rows,
                all_date_to_pos,
                all_dates,
                label="final_oos fit",
                train_window_mode=train_window_mode,
                train_window_size=train_window_size,
                train_window_unit=train_window_unit,
            )
            if df_oos_train.empty:
                logger.info("Final OOS evaluation skipped: model.train_window left no in-sample data.")
            else:
                final_weights = build_sample_weight(
                    df_oos_train,
                    sample_weight_mode,
                    params=sample_weight_params,
                )
                fit_model(
                    final_model,
                    model_type,
                    df_oos_train,
                    features=features,
                    target_col=train_target,
                    sample_weight=final_weights,
                )
                final_oos_eval = _evaluate_period(
                    "Final OOS",
                    final_model,
                    oos_df_full,
                    final_oos_dates,
                    context=period_eval_context,
                    run_perm_test=False,
                    allow_live_fallback=False,
                )
                ic_series_oos = final_oos_eval["ic_series"]
                ic_stats_oos = final_oos_eval["ic_stats"]
                pearson_ic_series_oos = final_oos_eval["pearson_ic_series"]
                pearson_ic_stats_oos = final_oos_eval["pearson_ic_stats"]
                error_metrics_oos = final_oos_eval["error_metrics"]
                hit_rate_stats_oos = final_oos_eval["hit_rate"]
                topk_positive_stats_oos = final_oos_eval["topk_positive_ratio"]
                bucket_ic_records_oos = final_oos_eval["bucket_ic"]
                quantile_ts_oos = final_oos_eval["quantile_ts"]
                quantile_mean_oos = final_oos_eval["quantile_mean"]
                turnover_series_oos = final_oos_eval["turnover_series"]
            if final_oos_eval is not None:
                positions_by_rebalance_oos = final_oos_eval["positions_by_rebalance"]
                bt_stats_oos = final_oos_eval["bt_stats"]
                bt_net_series_oos = final_oos_eval["bt_net_series"]
                bt_gross_series_oos = final_oos_eval["bt_gross_series"]
                bt_turnover_series_oos = final_oos_eval["bt_turnover_series"]
                bt_benchmark_series_oos = final_oos_eval["bt_benchmark_series"]
                bt_active_series_oos = final_oos_eval["bt_active_series"]
                bt_benchmark_stats_oos = final_oos_eval["bt_benchmark_stats"]
                bt_active_stats_oos = final_oos_eval["bt_active_stats"]
                bt_periods_oos = final_oos_eval["bt_periods"]
                bt_style_exposure_oos = final_oos_eval["bt_style_exposure"]
                bt_style_exposure_summary_oos = final_oos_eval["bt_style_exposure_summary"]
                bt_industry_exposure_oos = final_oos_eval["bt_industry_exposure"]
                bt_industry_exposure_summary_oos = final_oos_eval["bt_industry_exposure_summary"]
                bt_active_exposure_summary_oos = final_oos_eval["bt_active_exposure_summary"]
                if positions_by_rebalance_oos is not None and not positions_by_rebalance_oos.empty:
                    positions_by_rebalance_oos = _annotate_positions_window(positions_by_rebalance_oos)

    if final_oos_eval is not None:
        rolling_ic_oos_results, rolling_ic_oos_obs_per_year = _compute_rolling_ic(
            ic_series_oos, rolling_windows_months
        )
        rolling_ic_latest_oos = {
            label: _latest_rolling_stats(frame, ["ic_mean", "ic_ir"])
            for label, frame in rolling_ic_oos_results.items()
        }
        if bt_stats_oos is not None and not bt_net_series_oos.empty:
            periods_per_year_oos = bt_stats_oos.get("periods_per_year", np.nan)
            rolling_sharpe_oos_results = _compute_rolling_sharpe(
                bt_net_series_oos, rolling_windows_months, periods_per_year_oos
            )
            rolling_sharpe_latest_oos = {
                label: _latest_rolling_stats(frame, ["mean", "std", "sharpe"])
                for label, frame in rolling_sharpe_oos_results.items()
            }

    return {
        "final_oos_eval": final_oos_eval,
        "ic_series_oos": ic_series_oos,
        "ic_stats_oos": ic_stats_oos,
        "pearson_ic_series_oos": pearson_ic_series_oos,
        "pearson_ic_stats_oos": pearson_ic_stats_oos,
        "error_metrics_oos": error_metrics_oos,
        "hit_rate_stats_oos": hit_rate_stats_oos,
        "topk_positive_stats_oos": topk_positive_stats_oos,
        "bucket_ic_records_oos": bucket_ic_records_oos,
        "quantile_ts_oos": quantile_ts_oos,
        "quantile_mean_oos": quantile_mean_oos,
        "turnover_series_oos": turnover_series_oos,
        "positions_by_rebalance_oos": positions_by_rebalance_oos,
        "bt_stats_oos": bt_stats_oos,
        "bt_net_series_oos": bt_net_series_oos,
        "bt_gross_series_oos": bt_gross_series_oos,
        "bt_turnover_series_oos": bt_turnover_series_oos,
        "bt_benchmark_series_oos": bt_benchmark_series_oos,
        "bt_active_series_oos": bt_active_series_oos,
        "bt_benchmark_stats_oos": bt_benchmark_stats_oos,
        "bt_active_stats_oos": bt_active_stats_oos,
        "bt_periods_oos": bt_periods_oos,
        "bt_style_exposure_oos": bt_style_exposure_oos,
        "bt_style_exposure_summary_oos": bt_style_exposure_summary_oos,
        "bt_industry_exposure_oos": bt_industry_exposure_oos,
        "bt_industry_exposure_summary_oos": bt_industry_exposure_summary_oos,
        "bt_active_exposure_summary_oos": bt_active_exposure_summary_oos,
        "rolling_ic_oos_results": rolling_ic_oos_results,
        "rolling_ic_oos_obs_per_year": rolling_ic_oos_obs_per_year,
        "rolling_ic_latest_oos": rolling_ic_latest_oos,
        "rolling_sharpe_oos_results": rolling_sharpe_oos_results,
        "rolling_sharpe_latest_oos": rolling_sharpe_latest_oos,
    }
