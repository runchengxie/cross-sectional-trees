from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from ..metrics import daily_ic_series, summarize_ic
from ..modeling import build_model, feature_importance_frame, fit_model
from ..split import build_sample_weight, time_series_cv_ic
from ..transform import apply_score_postprocess
from .eval import _evaluate_period, _evaluate_walk_forward_window
from .live import _prepare_live_snapshot
from .stats import (
    _compute_rolling_ic,
    _compute_rolling_sharpe,
    _latest_rolling_stats,
)
from .support import (
    _annotate_positions_window,
    _summarize_walk_forward_feature_stability,
)
from .dates import build_walk_forward_windows

logger = logging.getLogger("cstree")


def run_train_eval_stage(
    *,
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    test_dates: np.ndarray,
    df_features: pd.DataFrame,
    df_full: pd.DataFrame,
    df_model_sorted: pd.DataFrame,
    all_dates: np.ndarray,
    all_date_start_rows: np.ndarray,
    all_date_end_rows: np.ndarray,
    all_date_to_pos: dict[pd.Timestamp, int],
    features: list[str],
    target: str,
    train_target: str,
    model_type: str,
    model_params: dict[str, Any],
    model_cfg: dict[str, Any],
    sample_weight_mode: str,
    sample_weight_params: dict[str, Any],
    n_splits: int,
    embargo_steps: int,
    purge_steps: int,
    train_window_mode: str,
    train_window_size: int | None,
    train_window_unit: str | None,
    signal_direction_mode: str,
    signal_direction: float,
    min_abs_ic_to_flip: float,
    score_postprocess_method: str,
    score_postprocess_columns: list[str] | None,
    score_postprocess_strength: float,
    score_postprocess_min_obs: int,
    report_train_ic: bool,
    live_enabled: bool,
    live_as_of: str | None,
    market: str,
    provider: str,
    live_train_mode: str,
    min_symbols_per_date: int,
    price_col: str,
    backtest_top_k: int,
    label_shift_days: int,
    backtest_weighting: str,
    backtest_buffer_exit: int,
    backtest_buffer_entry: int,
    backtest_long_only: bool,
    backtest_short_k: int | None,
    backtest_tradable_col: str | None,
    backtest_group_col: str | None,
    backtest_max_names_per_group: int | None,
    execution_model: dict[str, Any],
    rebalance_frequency: str,
    sample_on_rebalance_dates: bool,
    valid_dates_set: set[pd.Timestamp],
    perm_test_runs: int,
    perm_test_seed: int | None,
    label_horizon_mode: str,
    label_horizon_effective: int | float,
    n_quantiles: int,
    top_k: int,
    eval_buffer_exit: int,
    eval_buffer_entry: int,
    transaction_cost_bps: float,
    bucket_ic_enabled: bool,
    bucket_ic_schemes: list[dict[str, Any]],
    bucket_ic_method: str,
    bucket_ic_min_count: int,
    backtest_rebalance_frequency: str,
    backtest_enabled: bool,
    backtest_signal_direction_raw: float | None,
    backtest_cost_bps_effective: float,
    backtest_trading_days_per_year: int,
    backtest_exit_mode: str,
    backtest_exit_horizon_days: int,
    backtest_pricing_df: pd.DataFrame,
    backtest_exit_price_policy: str,
    backtest_exit_fallback_policy: str,
    benchmark_df: pd.DataFrame | None,
    benchmark_return_series: pd.Series,
    industry_source_df: pd.DataFrame,
    fundamentals_mcap_col: str,
    passthrough_cols: list[str],
    industry_keep_columns: list[str],
    price_passthrough_cols: list[str],
    bucket_cols: list[str],
    backtest_topk_fn: Any,
    bucket_ic_summary_fn: Any,
    rolling_windows_months: list[int],
    wf_enabled: bool,
    wf_n_windows: int,
    wf_test_size: float | int | None,
    wf_step_size: float | int | None,
    effective_gap_steps: int,
    wf_anchor_end: bool,
    wf_feature_top_k: int,
    wf_backtest_enabled: bool,
    wf_perm_test_enabled: bool,
    wf_perm_test_runs: int,
    wf_perm_test_seed: int | None,
) -> dict[str, Any]:
    logger.info("Time-series cross-validation (IC) ...")

    walk_forward_importance_rows: list[dict[str, Any]] = []

    cv_scores_raw = time_series_cv_ic(
        train_df,
        features,
        target,
        n_splits,
        embargo_steps,
        purge_steps,
        model_cfg,
        1.0,
        sample_weight_mode=sample_weight_mode,
        sample_weight_params=sample_weight_params,
        train_window_mode=train_window_mode,
        train_window_size=train_window_size,
        train_window_unit=train_window_unit,
        fit_target_col=train_target,
        score_postprocess_method=score_postprocess_method,
        score_postprocess_columns=score_postprocess_columns,
        score_postprocess_strength=score_postprocess_strength,
        score_postprocess_min_obs=score_postprocess_min_obs,
    )
    if cv_scores_raw:
        logger.info(
            "CV IC (raw): mean=%.4f, std=%.4f", np.nanmean(cv_scores_raw), np.nanstd(cv_scores_raw)
        )
        logger.info("CV fold ICs (raw): %s", [f"{s:.4f}" for s in cv_scores_raw])
    else:
        logger.info("CV IC not available - insufficient data after embargo/purge.")

    cv_scores_adj = None
    updated_signal_direction = signal_direction
    if signal_direction_mode == "cv_ic" and cv_scores_raw:
        cv_mean = float(np.nanmean(cv_scores_raw))
        if np.isfinite(cv_mean) and cv_mean != 0 and abs(cv_mean) >= min_abs_ic_to_flip:
            updated_signal_direction = float(np.sign(cv_mean))
            logger.info("Signal direction set from CV IC: %s", updated_signal_direction)
        else:
            logger.info(
                "CV IC mean below threshold (|mean| < %.4f); keeping signal direction: %s",
                min_abs_ic_to_flip,
                updated_signal_direction,
            )

    logger.info("Fitting model (%s) ...", model_type)
    model = build_model(model_type, model_params)
    train_weights = build_sample_weight(
        train_df,
        sample_weight_mode,
        params=sample_weight_params,
    )
    fit_model(
        model,
        model_type,
        train_df,
        features=features,
        target_col=train_target,
        sample_weight=train_weights,
    )

    logger.info("Evaluating model on train/test sets ...")
    test_start = pd.to_datetime(test_dates[0])
    test_end = pd.to_datetime(test_dates[-1])
    test_df_full = df_full[
        (df_full["trade_date"] >= test_start) & (df_full["trade_date"] <= test_end)
    ].copy()
    if test_df_full.empty:
        raise SystemExit("Not enough test data after applying the split window.")

    train_eval_df = train_df.copy()
    train_eval_df["pred"] = model.predict(train_eval_df[features])
    train_eval_df["pred"] = apply_score_postprocess(
        train_eval_df,
        "pred",
        method=score_postprocess_method,
        columns=score_postprocess_columns,
        strength=score_postprocess_strength,
        min_obs=score_postprocess_min_obs,
    )
    train_ic_raw_stats = {}
    if signal_direction_mode == "train_ic":
        train_ic_raw_series = daily_ic_series(train_eval_df, target, "pred")
        train_ic_raw_stats = summarize_ic(train_ic_raw_series)
        raw_mean = train_ic_raw_stats.get("mean", np.nan)
        if np.isfinite(raw_mean) and raw_mean != 0:
            updated_signal_direction = float(np.sign(raw_mean))
        else:
            updated_signal_direction = 1.0
        logger.info("Signal direction set from Train IC: %s", updated_signal_direction)

    train_signal_col = "pred"
    if updated_signal_direction != 1.0:
        train_eval_df["signal"] = train_eval_df["pred"] * updated_signal_direction
        train_signal_col = "signal"

    if cv_scores_raw:
        cv_scores_adj = [float(score) * updated_signal_direction for score in cv_scores_raw]
        if updated_signal_direction != 1.0:
            logger.info(
                "CV IC (adj): mean=%.4f, std=%.4f",
                np.nanmean(cv_scores_adj),
                np.nanstd(cv_scores_adj),
            )
            logger.info("CV fold ICs (adj): %s", [f"{s:.4f}" for s in cv_scores_adj])

    train_ic_series = pd.Series(dtype=float, name="ic")
    train_ic_stats = {}
    train_pearson_ic_series = pd.Series(dtype=float, name="ic_pearson")
    train_pearson_ic_stats = {}
    if report_train_ic:
        train_ic_series = daily_ic_series(train_eval_df, target, train_signal_col)
        train_ic_stats = summarize_ic(train_ic_series)
        logger.info(
            "Train Daily IC: mean=%.4f, std=%.4f, IR=%.2f, t=%.2f, p=%.4f (n=%s)",
            train_ic_stats["mean"],
            train_ic_stats["std"],
            train_ic_stats["ir"],
            train_ic_stats["t_stat"],
            train_ic_stats["p_value"],
            train_ic_stats["n"],
        )
        train_pearson_ic_series = daily_ic_series(
            train_eval_df, target, train_signal_col, method="pearson"
        )
        train_pearson_ic_stats = summarize_ic(train_pearson_ic_series)
        logger.info(
            "Train Daily Pearson IC: mean=%.4f, std=%.4f, IR=%.2f, t=%.2f, p=%.4f (n=%s)",
            train_pearson_ic_stats["mean"],
            train_pearson_ic_stats["std"],
            train_pearson_ic_stats["ir"],
            train_pearson_ic_stats["t_stat"],
            train_pearson_ic_stats["p_value"],
            train_pearson_ic_stats["n"],
        )

    live_state = _prepare_live_snapshot(
        df_features,
        model,
        context={
            "live_enabled": live_enabled,
            "live_as_of_token": live_as_of,
            "market": market,
            "provider": provider,
            "target": target,
            "live_train_mode": live_train_mode,
            "model_type": model_type,
            "model_params": model_params,
            "train_window_mode": train_window_mode,
            "train_window_size": train_window_size,
            "train_window_unit": train_window_unit,
            "sample_weight_mode": sample_weight_mode,
            "sample_weight_params": sample_weight_params,
            "train_target": train_target,
            "features": features,
            "signal_direction": updated_signal_direction,
            "score_postprocess_method": score_postprocess_method,
            "score_postprocess_columns": score_postprocess_columns,
            "score_postprocess_strength": score_postprocess_strength,
            "score_postprocess_min_obs": score_postprocess_min_obs,
            "backtest_rebalance_frequency": backtest_rebalance_frequency,
            "min_symbols_per_date": min_symbols_per_date,
            "price_col": price_col,
            "backtest_top_k": backtest_top_k,
            "label_shift_days": label_shift_days,
            "backtest_weighting": backtest_weighting,
            "backtest_buffer_exit": backtest_buffer_exit,
            "backtest_buffer_entry": backtest_buffer_entry,
            "backtest_long_only": backtest_long_only,
            "backtest_short_k": backtest_short_k,
            "backtest_tradable_col": backtest_tradable_col,
            "backtest_group_col": backtest_group_col,
            "backtest_max_names_per_group": backtest_max_names_per_group,
            "execution_model": execution_model,
        },
    )
    live_positions_ready = bool(live_state["live_positions_ready"])
    if live_enabled and not backtest_enabled and not live_positions_ready:
        raise SystemExit(
            "live.enabled=true but no live positions were generated; "
            "refusing to fall back to backtest holdings."
        )

    backtest_signal_direction = (
        updated_signal_direction
        if backtest_signal_direction_raw is None
        else backtest_signal_direction_raw
    )

    period_eval_context = {
        "features": features,
        "target": target,
        "signal_direction": updated_signal_direction,
        "backtest_signal_direction": backtest_signal_direction,
        "sample_on_rebalance_dates": sample_on_rebalance_dates,
        "score_postprocess_method": score_postprocess_method,
        "score_postprocess_columns": score_postprocess_columns,
        "score_postprocess_strength": score_postprocess_strength,
        "score_postprocess_min_obs": score_postprocess_min_obs,
        "rebalance_frequency": rebalance_frequency,
        "valid_dates_set": valid_dates_set,
        "perm_test_runs": perm_test_runs,
        "perm_test_seed": perm_test_seed,
        "model_type": model_type,
        "model_params": model_params,
        "train_target": train_target,
        "sample_weight_mode": sample_weight_mode,
        "sample_weight_params": sample_weight_params,
        "label_horizon_mode": label_horizon_mode,
        "label_horizon_effective": label_horizon_effective,
        "n_quantiles": n_quantiles,
        "top_k": top_k,
        "eval_buffer_exit": eval_buffer_exit,
        "eval_buffer_entry": eval_buffer_entry,
        "transaction_cost_bps": transaction_cost_bps,
        "bucket_ic_enabled": bucket_ic_enabled,
        "bucket_ic_schemes": bucket_ic_schemes,
        "bucket_ic_method": bucket_ic_method,
        "bucket_ic_min_count": bucket_ic_min_count,
        "backtest_rebalance_frequency": backtest_rebalance_frequency,
        "backtest_enabled": backtest_enabled,
        "live_enabled": live_enabled,
        "backtest_top_k": backtest_top_k,
        "label_shift_days": label_shift_days,
        "backtest_weighting": backtest_weighting,
        "backtest_buffer_exit": backtest_buffer_exit,
        "backtest_buffer_entry": backtest_buffer_entry,
        "backtest_long_only": backtest_long_only,
        "backtest_short_k": backtest_short_k,
        "backtest_tradable_col": backtest_tradable_col,
        "backtest_group_col": backtest_group_col,
        "backtest_max_names_per_group": backtest_max_names_per_group,
        "execution_model": execution_model,
        "positions_by_rebalance_live": live_state["positions_by_rebalance_live"],
        "backtest_cost_bps_effective": backtest_cost_bps_effective,
        "backtest_trading_days_per_year": backtest_trading_days_per_year,
        "backtest_exit_mode": backtest_exit_mode,
        "backtest_exit_horizon_days": backtest_exit_horizon_days,
        "backtest_pricing_df": backtest_pricing_df,
        "backtest_exit_price_policy": backtest_exit_price_policy,
        "backtest_exit_fallback_policy": backtest_exit_fallback_policy,
        "benchmark_df": benchmark_df,
        "benchmark_return_series": benchmark_return_series,
        "exposure_source_df": df_full,
        "industry_source_df": industry_source_df,
        "fundamentals_mcap_col": fundamentals_mcap_col,
        "industry_columns": list(dict.fromkeys(passthrough_cols + industry_keep_columns)),
        "price_col": price_col,
        "price_passthrough_cols": price_passthrough_cols,
        "passthrough_cols": passthrough_cols,
        "bucket_cols": bucket_cols,
        "backtest_topk_fn": backtest_topk_fn,
        "bucket_ic_summary_fn": bucket_ic_summary_fn,
    }

    eval_main = _evaluate_period(
        "Test",
        model,
        test_df_full,
        test_dates,
        context=period_eval_context,
        run_perm_test=True,
        perm_train_df=train_df,
        perm_test_df=test_df,
        allow_live_fallback=True,
    )

    rolling_ic_results, rolling_ic_obs_per_year = _compute_rolling_ic(
        eval_main["ic_series"], rolling_windows_months
    )
    rolling_ic_latest = {
        label: _latest_rolling_stats(frame, ["ic_mean", "ic_ir"])
        for label, frame in rolling_ic_results.items()
    }
    rolling_sharpe_results = {}
    rolling_sharpe_latest = {}
    if eval_main["bt_stats"] is not None and not eval_main["bt_net_series"].empty:
        periods_per_year = eval_main["bt_stats"].get("periods_per_year", np.nan)
        rolling_sharpe_results = _compute_rolling_sharpe(
            eval_main["bt_net_series"], rolling_windows_months, periods_per_year
        )
        rolling_sharpe_latest = {
            label: _latest_rolling_stats(frame, ["mean", "std", "sharpe"])
            for label, frame in rolling_sharpe_results.items()
        }

    positions_by_rebalance = eval_main["positions_by_rebalance"]
    positions_by_rebalance_live = live_state["positions_by_rebalance_live"]
    if positions_by_rebalance is not None and not positions_by_rebalance.empty:
        positions_by_rebalance = _annotate_positions_window(positions_by_rebalance)
    if positions_by_rebalance_live is not None and not positions_by_rebalance_live.empty:
        positions_by_rebalance_live = _annotate_positions_window(positions_by_rebalance_live)

    cv_stats_raw = None
    cv_stats = None
    if cv_scores_raw:
        cv_stats_raw = {
            "mean": float(np.nanmean(cv_scores_raw)),
            "std": float(np.nanstd(cv_scores_raw)),
            "scores": [float(score) for score in cv_scores_raw],
        }
        if cv_scores_adj is None:
            cv_scores_adj = [float(score) * updated_signal_direction for score in cv_scores_raw]
        cv_stats = {
            "mean": float(np.nanmean(cv_scores_adj)),
            "std": float(np.nanstd(cv_scores_adj)),
            "scores": [float(score) for score in cv_scores_adj],
        }

    walk_forward_results: list[dict] = []
    if wf_enabled:
        walk_forward_context = {
            "df_model_sorted": df_model_sorted,
            "all_date_start_rows": all_date_start_rows,
            "all_date_end_rows": all_date_end_rows,
            "all_date_to_pos": all_date_to_pos,
            "train_window_mode": train_window_mode,
            "train_window_size": train_window_size,
            "train_window_unit": train_window_unit,
            "signal_direction": updated_signal_direction,
            "signal_direction_mode": signal_direction_mode,
            "features": features,
            "target": target,
            "n_splits": n_splits,
            "embargo_steps": embargo_steps,
            "purge_steps": purge_steps,
            "model_cfg": model_cfg,
            "min_abs_ic_to_flip": min_abs_ic_to_flip,
            "sample_weight_mode": sample_weight_mode,
            "sample_weight_params": sample_weight_params,
            "train_target": train_target,
            "model_type": model_type,
            "model_params": model_params,
            "report_train_ic": report_train_ic,
            "sample_on_rebalance_dates": sample_on_rebalance_dates,
            "score_postprocess_method": score_postprocess_method,
            "score_postprocess_columns": score_postprocess_columns,
            "score_postprocess_strength": score_postprocess_strength,
            "score_postprocess_min_obs": score_postprocess_min_obs,
            "rebalance_frequency": rebalance_frequency,
            "valid_dates_set": valid_dates_set,
            "wf_perm_test_enabled": wf_perm_test_enabled,
            "wf_perm_test_runs": wf_perm_test_runs,
            "wf_perm_test_seed": wf_perm_test_seed,
            "n_quantiles": n_quantiles,
            "top_k": top_k,
            "eval_buffer_exit": eval_buffer_exit,
            "eval_buffer_entry": eval_buffer_entry,
            "wf_backtest_enabled": wf_backtest_enabled,
            "backtest_signal_direction_raw": backtest_signal_direction_raw,
            "df_full": df_full,
            "price_col": price_col,
            "backtest_rebalance_frequency": backtest_rebalance_frequency,
            "label_shift_days": label_shift_days,
            "backtest_cost_bps_effective": backtest_cost_bps_effective,
            "backtest_trading_days_per_year": backtest_trading_days_per_year,
            "backtest_exit_mode": backtest_exit_mode,
            "backtest_exit_horizon_days": backtest_exit_horizon_days,
            "backtest_long_only": backtest_long_only,
            "backtest_short_k": backtest_short_k,
            "backtest_buffer_exit": backtest_buffer_exit,
            "backtest_buffer_entry": backtest_buffer_entry,
            "backtest_group_col": backtest_group_col,
            "backtest_max_names_per_group": backtest_max_names_per_group,
            "backtest_tradable_col": backtest_tradable_col,
            "backtest_exit_price_policy": backtest_exit_price_policy,
            "backtest_exit_fallback_policy": backtest_exit_fallback_policy,
            "execution_model": execution_model,
            "backtest_pricing_df": backtest_pricing_df,
            "benchmark_df": benchmark_df,
            "benchmark_return_series": benchmark_return_series,
            "backtest_top_k": backtest_top_k,
            "wf_feature_top_k": wf_feature_top_k,
            "backtest_topk_fn": backtest_topk_fn,
        }
        try:
            walk_forward_test_size = float(wf_test_size)
        except (TypeError, ValueError):
            walk_forward_test_size = None
        windows = build_walk_forward_windows(
            all_dates,
            walk_forward_test_size,
            wf_n_windows,
            wf_step_size,
            effective_gap_steps,
            wf_anchor_end,
        )
        if not windows:
            logger.info("Walk-forward evaluation skipped: insufficient windows.")
        else:
            if len(windows) < wf_n_windows:
                logger.warning(
                    "Walk-forward requested %s windows but only %s fit "
                    "(test_size=%s, step_size=%s, anchor_end=%s). "
                    "Reduce eval.test_size / eval.walk_forward.test_size, "
                    "set a smaller eval.walk_forward.step_size, or lower n_windows.",
                    wf_n_windows,
                    len(windows),
                    walk_forward_test_size,
                    wf_step_size,
                    wf_anchor_end,
                )
            logger.info("Walk-forward evaluation: %s windows.", len(windows))
            for window_meta in windows:
                window_result, window_importance_rows = _evaluate_walk_forward_window(
                    window_meta,
                    context=walk_forward_context,
                )
                walk_forward_results.append(window_result)
                walk_forward_importance_rows.extend(window_importance_rows)
    walk_forward_importance_df = pd.DataFrame(walk_forward_importance_rows)
    walk_forward_feature_stability_df = _summarize_walk_forward_feature_stability(
        walk_forward_importance_df,
        wf_feature_top_k,
    )

    logger.info("Feature importance:")
    importance_df, importance_source = feature_importance_frame(model, features)
    logger.info("Feature importance source: %s", importance_source)
    for _, row in importance_df.iterrows():
        logger.info("  %-20s: %.4f", row["feature"], float(row["importance"]))

    pred_nunique: int | None = None
    constant_prediction: bool | None = None
    eval_scored_data = eval_main["scored_data"]
    if eval_scored_data is not None and not eval_scored_data.empty and "pred" in eval_scored_data.columns:
        pred_nunique = int(eval_scored_data["pred"].nunique(dropna=True))
        constant_prediction = pred_nunique <= 1

    feature_importance_nonzero: int | None = None
    zero_feature_importance: bool | None = None
    if not importance_df.empty and "importance" in importance_df.columns:
        importance_values = pd.to_numeric(importance_df["importance"], errors="coerce").fillna(0.0)
        feature_importance_nonzero = int((importance_values.abs() > 0.0).sum())
        zero_feature_importance = feature_importance_nonzero == 0

    return {
        "model": model,
        "signal_direction": updated_signal_direction,
        "train_ic_raw_stats": train_ic_raw_stats,
        "train_ic_series": train_ic_series,
        "train_ic_stats": train_ic_stats,
        "train_pearson_ic_series": train_pearson_ic_series,
        "train_pearson_ic_stats": train_pearson_ic_stats,
        "live_as_of": live_state["live_as_of"],
        "positions_by_rebalance_live": positions_by_rebalance_live,
        "live_positions_ready": live_positions_ready,
        "backtest_signal_direction": backtest_signal_direction,
        "period_eval_context": period_eval_context,
        "ic_series": eval_main["ic_series"],
        "ic_stats": eval_main["ic_stats"],
        "pearson_ic_series": eval_main["pearson_ic_series"],
        "pearson_ic_stats": eval_main["pearson_ic_stats"],
        "error_metrics": eval_main["error_metrics"],
        "hit_rate_stats": eval_main["hit_rate"],
        "topk_positive_stats": eval_main["topk_positive_ratio"],
        "bucket_ic_records": eval_main["bucket_ic"],
        "quantile_ts": eval_main["quantile_ts"],
        "quantile_mean": eval_main["quantile_mean"],
        "turnover_series": eval_main["turnover_series"],
        "eval_scored_data": eval_scored_data,
        "eval_rebalance_dates": eval_main["eval_rebalance_dates"],
        "backtest_rebalance_dates": eval_main["backtest_rebalance_dates"],
        "positions_by_rebalance": positions_by_rebalance,
        "bt_stats": eval_main["bt_stats"],
        "bt_net_series": eval_main["bt_net_series"],
        "bt_gross_series": eval_main["bt_gross_series"],
        "bt_turnover_series": eval_main["bt_turnover_series"],
        "bt_benchmark_series": eval_main["bt_benchmark_series"],
        "bt_active_series": eval_main["bt_active_series"],
        "bt_benchmark_stats": eval_main["bt_benchmark_stats"],
        "bt_active_stats": eval_main["bt_active_stats"],
        "bt_periods": eval_main["bt_periods"],
        "bt_style_exposure": eval_main["bt_style_exposure"],
        "bt_style_exposure_summary": eval_main["bt_style_exposure_summary"],
        "bt_industry_exposure": eval_main["bt_industry_exposure"],
        "bt_industry_exposure_summary": eval_main["bt_industry_exposure_summary"],
        "bt_active_exposure_summary": eval_main["bt_active_exposure_summary"],
        "perm_stats": eval_main["perm_stats"],
        "rolling_ic_results": rolling_ic_results,
        "rolling_ic_obs_per_year": rolling_ic_obs_per_year,
        "rolling_ic_latest": rolling_ic_latest,
        "rolling_sharpe_results": rolling_sharpe_results,
        "rolling_sharpe_latest": rolling_sharpe_latest,
        "cv_scores_raw": cv_scores_raw,
        "cv_stats_raw": cv_stats_raw,
        "cv_stats": cv_stats,
        "walk_forward_results": walk_forward_results,
        "walk_forward_importance_df": walk_forward_importance_df,
        "walk_forward_feature_stability_df": walk_forward_feature_stability_df,
        "importance_df": importance_df,
        "importance_source": importance_source,
        "pred_nunique": pred_nunique,
        "constant_prediction": constant_prediction,
        "feature_importance_nonzero": feature_importance_nonzero,
        "zero_feature_importance": zero_feature_importance,
    }
