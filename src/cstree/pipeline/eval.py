from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, Optional

import numpy as np
import pandas as pd

from ..backtest import backtest_topk, summarize_period_returns
from ..execution_sim import simulate_capacity_execution
from ..exposure import compute_backtest_exposure_analysis
from ..metrics import (
    assign_daily_quantile_bucket,
    bucket_ic_summary,
    daily_ic_series,
    estimate_turnover,
    hit_rate,
    quantile_returns,
    regression_error_metrics,
    summarize_active_returns,
    summarize_ic,
    topk_positive_ratio,
)
from ..modeling import build_model, feature_importance_frame, fit_model
from ..portfolio import build_positions_by_rebalance
from ..rebalance import estimate_rebalance_gap, get_rebalance_dates
from ..split import build_sample_weight, time_series_cv_ic
from ..transform import apply_score_postprocess
from .dates import (
    _apply_model_train_window,
    _build_trade_date_slices,
    _slice_trade_dates,
)
from .eval_benchmark import (
    build_benchmark_series,
    warn_if_delay_exit_lag as _warn_if_delay_exit_lag,
)

logger = logging.getLogger("cstree")


def _postprocess_pred_column(
    frame: pd.DataFrame,
    pred_col: str,
    *,
    method: str,
    columns: list[str],
    strength: float,
    min_obs: Optional[int],
) -> None:
    if method == "none":
        return
    frame[pred_col] = apply_score_postprocess(
        frame,
        pred_col,
        method=method,
        columns=columns,
        strength=strength,
        min_obs=min_obs,
    )


def _permute_target_within_date(
    data: pd.DataFrame,
    target_col: str,
    rng: np.random.Generator,
) -> pd.DataFrame:
    def _permute(group: pd.DataFrame) -> pd.DataFrame:
        group = group.copy()
        group[target_col] = rng.permutation(group[target_col].values)
        return group

    return data.groupby("trade_date", group_keys=False, sort=False).apply(_permute)


def _permutation_test_ic(
    train_data: pd.DataFrame,
    test_data: pd.DataFrame,
    n_runs: int,
    seed: Optional[int],
    signal_direction: float,
    *,
    model_type: str,
    model_params: Mapping[str, Any],
    features: list[str],
    fit_target_col: str,
    target_col: str,
    sample_weight_mode: str,
    sample_weight_params: Mapping[str, Any],
    eval_dates: Optional[list[pd.Timestamp]] = None,
    score_postprocess_method: str = "none",
    score_postprocess_columns: Optional[list[str]] = None,
    score_postprocess_strength: float = 1.0,
    score_postprocess_min_obs: Optional[int] = None,
) -> list[float]:
    scores = []
    eval_date_values = sorted(set(pd.to_datetime(eval_dates))) if eval_dates else None
    if eval_date_values:
        (
            test_data_sorted,
            _,
            test_date_start_rows,
            test_date_end_rows,
            test_date_to_pos,
        ) = _build_trade_date_slices(test_data)
        eval_test_data = _slice_trade_dates(
            test_data_sorted,
            test_date_start_rows,
            test_date_end_rows,
            test_date_to_pos,
            eval_date_values,
        )
    else:
        eval_test_data = test_data
    for idx in range(n_runs):
        run_seed = None if seed is None else seed + idx
        rng = np.random.default_rng(run_seed)
        perm_train = _permute_target_within_date(train_data, fit_target_col, rng)

        perm_model = build_model(model_type, model_params)
        perm_weights = build_sample_weight(
            perm_train,
            sample_weight_mode,
            params=sample_weight_params,
        )
        fit_model(
            perm_model,
            model_type,
            perm_train,
            features=features,
            target_col=fit_target_col,
            sample_weight=perm_weights,
        )

        perm_test = eval_test_data.copy()
        perm_test["pred"] = perm_model.predict(perm_test[features])
        _postprocess_pred_column(
            perm_test,
            "pred",
            method=score_postprocess_method,
            columns=score_postprocess_columns or [],
            strength=score_postprocess_strength,
            min_obs=score_postprocess_min_obs,
        )
        if signal_direction != 1.0:
            perm_test["pred"] = perm_test["pred"] * signal_direction

        ic_values = daily_ic_series(perm_test, target_col, "pred")
        scores.append(float(ic_values.mean()) if not ic_values.empty else np.nan)
    return scores


def _sample_rebalance_frame(
    frame: pd.DataFrame,
    *,
    frequency: str,
    valid_dates: Optional[set[pd.Timestamp]] = None,
    allowed_dates: Optional[np.ndarray] = None,
) -> tuple[pd.DataFrame, list[pd.Timestamp]]:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=frame.columns if frame is not None else []), []
    (
        frame_sorted,
        trade_dates_sorted,
        frame_date_start_rows,
        frame_date_end_rows,
        frame_date_to_pos,
    ) = _build_trade_date_slices(frame)
    rebalance_dates = get_rebalance_dates(trade_dates_sorted, frequency)
    if valid_dates:
        rebalance_dates = [d for d in rebalance_dates if d in valid_dates]
    if allowed_dates is not None:
        allowed_dates_set = set(pd.to_datetime(allowed_dates))
        rebalance_dates = [d for d in rebalance_dates if d in allowed_dates_set]
    sampled = _slice_trade_dates(
        frame_sorted,
        frame_date_start_rows,
        frame_date_end_rows,
        frame_date_to_pos,
        rebalance_dates,
    )
    return sampled, rebalance_dates


def _empty_period_result() -> dict[str, Any]:
    default_series = pd.Series(dtype=float)
    default_frame = pd.DataFrame()
    return {
        "ic_series": default_series,
        "ic_stats": {},
        "pearson_ic_series": default_series,
        "pearson_ic_stats": {},
        "error_metrics": {},
        "hit_rate": {},
        "topk_positive_ratio": {},
        "bucket_ic": [],
        "quantile_ts": default_frame,
        "quantile_mean": default_series,
        "turnover_series": default_series,
        "positions_by_rebalance": None,
        "bt_stats": None,
        "bt_net_series": pd.Series(dtype=float, name="net_return"),
        "bt_gross_series": pd.Series(dtype=float, name="gross_return"),
        "bt_turnover_series": pd.Series(dtype=float, name="turnover"),
        "bt_benchmark_series": pd.Series(dtype=float, name="benchmark_return"),
        "bt_active_series": pd.Series(dtype=float, name="active_return"),
        "bt_benchmark_stats": None,
        "bt_active_stats": None,
        "bt_periods": [],
        "bt_style_exposure": default_frame,
        "bt_style_exposure_summary": {},
        "bt_industry_exposure": default_frame,
        "bt_industry_exposure_summary": {},
        "bt_active_exposure_summary": default_frame,
        "execution_sim_summary": None,
        "execution_sim_orders": default_frame,
        "execution_sim_fills": default_frame,
        "perm_stats": None,
        "scored_data": default_frame,
        "eval_rebalance_dates": [],
        "backtest_rebalance_dates": [],
    }


def _score_period_frame(
    frame: pd.DataFrame,
    model_eval: Any,
    *,
    features: list[str],
    score_postprocess_method: str,
    score_postprocess_columns: list[str] | None,
    score_postprocess_strength: float,
    score_postprocess_min_obs: int | None,
    signal_direction: float,
    backtest_signal_direction: float,
    label_prefix: str,
) -> pd.DataFrame:
    scored = frame.copy()
    scored["pred"] = model_eval.predict(scored[features])
    _postprocess_pred_column(
        scored,
        "pred",
        method=score_postprocess_method,
        columns=score_postprocess_columns or [],
        strength=score_postprocess_strength,
        min_obs=score_postprocess_min_obs,
    )
    scored["signal_eval"] = scored["pred"] * signal_direction
    scored["signal_backtest"] = scored["pred"] * backtest_signal_direction
    if signal_direction != 1.0:
        logger.info("%sSignal direction applied to ranking: %s", label_prefix, signal_direction)
    return scored


def _record_primary_period_metrics(
    result: dict[str, Any],
    eval_df: pd.DataFrame,
    *,
    target: str,
    signal_col: str,
    label_prefix: str,
) -> None:
    ic_series = daily_ic_series(eval_df, target, signal_col)
    ic_stats = summarize_ic(ic_series)
    logger.info(
        "%sRebalance-date IC: mean=%.4f, std=%.4f, IR=%.2f, t=%.2f, p=%.4f (n=%s)",
        label_prefix,
        ic_stats["mean"],
        ic_stats["std"],
        ic_stats["ir"],
        ic_stats["t_stat"],
        ic_stats["p_value"],
        ic_stats["n"],
    )
    result["ic_series"] = ic_series
    result["ic_stats"] = ic_stats

    pearson_ic_series = daily_ic_series(eval_df, target, signal_col, method="pearson")
    pearson_ic_stats = summarize_ic(pearson_ic_series)
    logger.info(
        "%sRebalance-date Pearson IC: mean=%.4f, std=%.4f, IR=%.2f, t=%.2f, p=%.4f (n=%s)",
        label_prefix,
        pearson_ic_stats["mean"],
        pearson_ic_stats["std"],
        pearson_ic_stats["ir"],
        pearson_ic_stats["t_stat"],
        pearson_ic_stats["p_value"],
        pearson_ic_stats["n"],
    )
    result["pearson_ic_series"] = pearson_ic_series
    result["pearson_ic_stats"] = pearson_ic_stats

    error_metrics = regression_error_metrics(eval_df[target], eval_df[signal_col])
    result["error_metrics"] = error_metrics
    if error_metrics and error_metrics.get("n", 0) > 0:
        logger.info(
            "%sError metrics: MAE=%.6f, RMSE=%.6f, R2=%.4f (n=%s)",
            label_prefix,
            error_metrics.get("mae", np.nan),
            error_metrics.get("rmse", np.nan),
            error_metrics.get("r2", np.nan),
            error_metrics.get("n", 0),
        )

    hit_stats = hit_rate(eval_df[target], eval_df[signal_col])
    result["hit_rate"] = hit_stats
    if hit_stats and hit_stats.get("n", 0) > 0:
        logger.info(
            "%sHit rate: %.2f%% (n=%s)",
            label_prefix,
            hit_stats.get("hit_rate", np.nan) * 100,
            hit_stats.get("n", 0),
        )


def _record_quantile_turnover_bucket_metrics(
    result: dict[str, Any],
    eval_df: pd.DataFrame,
    *,
    target: str,
    signal_col: str,
    label_prefix: str,
    n_quantiles: int,
    top_k: int,
    rebalance_dates_eval: list[pd.Timestamp],
    eval_buffer_exit: int,
    eval_buffer_entry: int,
    transaction_cost_bps: float,
    bucket_ic_enabled: bool,
    bucket_ic_schemes: list[dict[str, Any]],
    bucket_ic_method: str,
    bucket_ic_min_count: int,
    bucket_ic_summary_fn: Any,
) -> None:
    quantile_ts = quantile_returns(eval_df, signal_col, target, n_quantiles)
    quantile_mean = quantile_ts.mean() if not quantile_ts.empty else pd.Series(dtype=float)
    result["quantile_ts"] = quantile_ts
    result["quantile_mean"] = quantile_mean
    if not quantile_mean.empty:
        for q_idx, value in quantile_mean.items():
            logger.info("%sQ%s mean return: %.4f%%", label_prefix, int(q_idx) + 1, value * 100)
        long_short = quantile_mean.iloc[-1] - quantile_mean.iloc[0]
        logger.info("%sLong-short (Q%s-Q1): %.4f%%", label_prefix, n_quantiles, long_short * 100)
    else:
        logger.info(
            "%sQuantile returns not available - insufficient symbols per date.",
            label_prefix,
        )

    k = min(top_k, eval_df["symbol"].nunique()) if not eval_df.empty else 0
    if k > 0 and rebalance_dates_eval:
        turnover_series = estimate_turnover(
            eval_df,
            signal_col,
            k,
            rebalance_dates_eval,
            buffer_exit=eval_buffer_exit,
            buffer_entry=eval_buffer_entry,
        )
    else:
        turnover_series = pd.Series(dtype=float, name="turnover")
    result["turnover_series"] = turnover_series
    if not turnover_series.empty:
        turnover = turnover_series.mean()
        cost_drag = 2 * (transaction_cost_bps / 10000.0) * turnover
        logger.info(
            "%sTop-%s turnover per rebalance: %.2f%% (n=%s)",
            label_prefix,
            k,
            turnover * 100,
            len(turnover_series),
        )
        logger.info(
            "%sApprox cost drag per rebalance: %.2f%% at %s bps per side",
            label_prefix,
            cost_drag * 100,
            transaction_cost_bps,
        )

    topk_stats = topk_positive_ratio(eval_df, signal_col, target, k)
    result["topk_positive_ratio"] = topk_stats
    if topk_stats and topk_stats.get("n_dates", 0) > 0:
        logger.info(
            "%sTop-%s positive ratio: %.2f%% (n=%s)",
            label_prefix,
            k,
            topk_stats.get("topk_positive_ratio", np.nan) * 100,
            topk_stats.get("n_dates", 0),
        )

    if not bucket_ic_enabled or not bucket_ic_schemes:
        return
    bucket_frames = []
    for scheme in bucket_ic_schemes:
        col = scheme["column"]
        if col not in eval_df.columns:
            continue
        bucket_type = str(scheme.get("type", "category")).strip().lower()
        if bucket_type not in {"category", "quantile"}:
            bucket_type = "category"
        data_for_bucket = eval_df.copy()
        bucket_col = col
        if bucket_type == "quantile":
            n_bins = int(scheme.get("n_bins") or 0)
            if n_bins < 2:
                continue
            bucket_col = f"bucket_{scheme['name']}"
            data_for_bucket[bucket_col] = assign_daily_quantile_bucket(data_for_bucket, col, n_bins)
        summary_df = bucket_ic_summary_fn(
            data_for_bucket,
            target,
            signal_col,
            bucket_col,
            method=bucket_ic_method,
            min_count=bucket_ic_min_count,
        )
        if not summary_df.empty:
            summary_df.insert(0, "scheme", scheme["name"])
            summary_df.insert(1, "type", bucket_type)
            if bucket_type == "quantile":
                summary_df.insert(2, "n_bins", int(scheme.get("n_bins") or 0))
            summary_df["method"] = bucket_ic_method
            bucket_frames.append(summary_df)
    if bucket_frames:
        bucket_df = pd.concat(bucket_frames, ignore_index=True)
        result["bucket_ic"] = bucket_df.to_dict(orient="records")


def _record_backtest_outputs(
    result: dict[str, Any],
    bt_result: tuple | None,
    *,
    label_prefix: str,
    backtest_long_only: bool,
    backtest_exit_mode: str,
    backtest_exit_price_policy: str,
    benchmark_df: pd.DataFrame | None,
    benchmark_return_series: pd.Series,
    execution_model: Any,
    backtest_trading_days_per_year: int,
) -> None:
    if bt_result is None:
        logger.info("%sBacktest not available - insufficient data.", label_prefix)
        return

    stats, net_series, gross_series, bt_turnover_series, period_info = bt_result
    result["bt_stats"] = stats
    result["bt_net_series"] = net_series
    result["bt_gross_series"] = gross_series
    result["bt_turnover_series"] = bt_turnover_series
    result["bt_periods"] = period_info
    mode_text = "long-only" if backtest_long_only else "long-short"
    logger.info(
        "%sBacktest (%s, top-K, exit_mode=%s):",
        label_prefix,
        mode_text,
        backtest_exit_mode,
    )
    logger.info("%s  periods: %s", label_prefix, stats["periods"])
    logger.info("%s  total return: %.2f%%", label_prefix, stats["total_return"] * 100)
    logger.info("%s  ann return: %.2f%%", label_prefix, stats["ann_return"] * 100)
    logger.info("%s  ann vol: %.2f%%", label_prefix, stats["ann_vol"] * 100)
    logger.info("%s  sharpe: %.2f", label_prefix, stats["sharpe"])
    logger.info("%s  max drawdown: %.2f%%", label_prefix, stats["max_drawdown"] * 100)
    if not np.isnan(stats["avg_turnover"]):
        logger.info("%s  avg turnover: %.2f%%", label_prefix, stats["avg_turnover"] * 100)
        logger.info(
            "%s  avg cost drag: %.2f%%",
            label_prefix,
            stats["avg_cost_drag"] * 100,
        )
    _warn_if_delay_exit_lag(
        label_prefix=label_prefix,
        exit_price_policy=backtest_exit_price_policy,
        stats=stats,
    )

    bench_series, bench_periods = build_benchmark_series(
        benchmark_df,
        execution_model.entry_policy.price_col,
        execution_model.exit_policy.price_col,
        period_info,
        benchmark_return_series=benchmark_return_series,
    )
    if bench_series.empty:
        return
    result["bt_benchmark_series"] = bench_series
    bt_benchmark_stats = summarize_period_returns(
        bench_series, bench_periods, backtest_trading_days_per_year
    )
    result["bt_benchmark_stats"] = bt_benchmark_stats
    logger.info(
        "%s  benchmark total return: %.2f%%",
        label_prefix,
        bt_benchmark_stats["total_return"] * 100,
    )
    periods_per_year = stats.get("periods_per_year", np.nan)
    bt_active_stats, bt_active_series = summarize_active_returns(
        net_series, bench_series, periods_per_year
    )
    result["bt_active_stats"] = bt_active_stats
    result["bt_active_series"] = bt_active_series
    if bt_active_stats and bt_active_stats.get("n", 0) > 0:
        logger.info(
            "%s  active total return: %.2f%%",
            label_prefix,
            bt_active_stats["active_total_return"] * 100,
        )
        if np.isfinite(bt_active_stats.get("information_ratio", np.nan)):
            logger.info(
                "%s  information ratio: %.2f",
                label_prefix,
                bt_active_stats["information_ratio"],
            )
        if np.isfinite(bt_active_stats.get("beta", np.nan)):
            logger.info("%s  beta: %.2f", label_prefix, bt_active_stats["beta"])
        if np.isfinite(bt_active_stats.get("alpha", np.nan)):
            logger.info(
                "%s  alpha (ann): %.2f%%",
                label_prefix,
                bt_active_stats["alpha"] * 100,
            )


def _build_scored_data(
    eval_df_full: pd.DataFrame,
    *,
    price_col: str,
    target: str,
    price_passthrough_cols: list[str],
    passthrough_cols: list[str],
    bucket_cols: list[str],
    backtest_tradable_col: str | None,
) -> pd.DataFrame:
    scored_cols = [
        "trade_date",
        "symbol",
        price_col,
        target,
        "pred",
        "signal_eval",
        "signal_backtest",
    ]
    scored_cols.extend(price_passthrough_cols)
    scored_cols.extend(passthrough_cols)
    scored_cols.extend(bucket_cols)
    scored_cols = list(dict.fromkeys(scored_cols))
    if backtest_tradable_col and backtest_tradable_col in eval_df_full.columns:
        scored_cols.append(backtest_tradable_col)
    return eval_df_full[scored_cols].copy()


def _record_exposure_outputs(
    result: dict[str, Any],
    *,
    eval_df_full: pd.DataFrame,
    exposure_source_df: pd.DataFrame | None,
    positions_by_rebalance: pd.DataFrame | None,
    backtest_enabled: bool,
    backtest_pricing_df: pd.DataFrame,
    price_col: str,
    benchmark_df: pd.DataFrame | None,
    benchmark_return_series: pd.Series,
    fundamentals_mcap_col: str | None,
    industry_columns: list[str],
    industry_source_df: pd.DataFrame | None,
) -> None:
    if not backtest_enabled:
        return
    if positions_by_rebalance is None or positions_by_rebalance.empty:
        return
    exposure = compute_backtest_exposure_analysis(
        exposure_source_df if exposure_source_df is not None else eval_df_full,
        positions_by_rebalance,
        pricing_data=backtest_pricing_df,
        price_col=price_col,
        benchmark_df=benchmark_df,
        benchmark_return_series=benchmark_return_series,
        market_cap_col=fundamentals_mcap_col,
        industry_columns=industry_columns,
        industry_source_data=industry_source_df,
    )
    result["bt_style_exposure"] = exposure["style"]
    result["bt_style_exposure_summary"] = exposure["style_summary"]
    result["bt_industry_exposure"] = exposure["industry"]
    result["bt_industry_exposure_summary"] = exposure["industry_summary"]
    result["bt_active_exposure_summary"] = exposure["active_summary"]


def _evaluate_walk_forward_window(
    window_meta: dict,
    *,
    context: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    df_model_sorted = context["df_model_sorted"]
    all_date_start_rows = context["all_date_start_rows"]
    all_date_end_rows = context["all_date_end_rows"]
    all_date_to_pos = context["all_date_to_pos"]
    train_window_mode = context["train_window_mode"]
    train_window_size = context["train_window_size"]
    train_window_unit = context["train_window_unit"]
    signal_direction = context["signal_direction"]
    signal_direction_mode = context["signal_direction_mode"]
    features = context["features"]
    target = context["target"]
    n_splits = context["n_splits"]
    embargo_steps = context["embargo_steps"]
    purge_steps = context["purge_steps"]
    model_cfg = context["model_cfg"]
    min_abs_ic_to_flip = context["min_abs_ic_to_flip"]
    sample_weight_mode = context["sample_weight_mode"]
    sample_weight_params = context["sample_weight_params"]
    train_target = context["train_target"]
    model_type = context["model_type"]
    model_params = context["model_params"]
    report_train_ic = context["report_train_ic"]
    sample_on_rebalance_dates = context["sample_on_rebalance_dates"]
    rebalance_frequency = context["rebalance_frequency"]
    valid_dates_set = context["valid_dates_set"]
    score_postprocess_method = context["score_postprocess_method"]
    score_postprocess_columns = context["score_postprocess_columns"]
    score_postprocess_strength = context["score_postprocess_strength"]
    score_postprocess_min_obs = context["score_postprocess_min_obs"]
    wf_perm_test_enabled = context["wf_perm_test_enabled"]
    wf_perm_test_runs = context["wf_perm_test_runs"]
    wf_perm_test_seed = context["wf_perm_test_seed"]
    n_quantiles = context["n_quantiles"]
    top_k = context["top_k"]
    eval_buffer_exit = context["eval_buffer_exit"]
    eval_buffer_entry = context["eval_buffer_entry"]
    wf_backtest_enabled = context["wf_backtest_enabled"]
    backtest_signal_direction_raw = context["backtest_signal_direction_raw"]
    df_full = context["df_full"]
    price_col = context["price_col"]
    backtest_rebalance_frequency = context["backtest_rebalance_frequency"]
    label_shift_days = context["label_shift_days"]
    backtest_cost_bps_effective = context["backtest_cost_bps_effective"]
    backtest_trading_days_per_year = context["backtest_trading_days_per_year"]
    backtest_exit_mode = context["backtest_exit_mode"]
    backtest_exit_horizon_days = context["backtest_exit_horizon_days"]
    backtest_long_only = context["backtest_long_only"]
    backtest_short_k = context["backtest_short_k"]
    backtest_buffer_exit = context["backtest_buffer_exit"]
    backtest_buffer_entry = context["backtest_buffer_entry"]
    backtest_group_col = context["backtest_group_col"]
    backtest_max_names_per_group = context["backtest_max_names_per_group"]
    backtest_tradable_col = context["backtest_tradable_col"]
    backtest_exit_price_policy = context["backtest_exit_price_policy"]
    backtest_exit_fallback_policy = context["backtest_exit_fallback_policy"]
    execution_model = context["execution_model"]
    backtest_pricing_df = context["backtest_pricing_df"]
    benchmark_df = context["benchmark_df"]
    benchmark_return_series = context["benchmark_return_series"]
    backtest_top_k = context["backtest_top_k"]
    wf_feature_top_k = context["wf_feature_top_k"]
    backtest_topk_fn = context.get("backtest_topk_fn", backtest_topk)

    window_id = int(window_meta["window"])
    train_dates = _apply_model_train_window(
        window_meta["train_dates"],
        label=f"walk_forward window {window_id}",
        train_window_mode=train_window_mode,
        train_window_size=train_window_size,
        train_window_unit=train_window_unit,
    )
    test_dates = window_meta["test_dates"]
    train_df_w = _slice_trade_dates(
        df_model_sorted,
        all_date_start_rows,
        all_date_end_rows,
        all_date_to_pos,
        train_dates,
    )
    test_df_w = _slice_trade_dates(
        df_model_sorted,
        all_date_start_rows,
        all_date_end_rows,
        all_date_to_pos,
        test_dates,
    )
    result = {
        "window": window_id,
        "train_start": pd.to_datetime(train_dates[0]).strftime("%Y-%m-%d")
        if len(train_dates)
        else pd.to_datetime(window_meta["train_start"]).strftime("%Y-%m-%d"),
        "train_end": pd.to_datetime(train_dates[-1]).strftime("%Y-%m-%d")
        if len(train_dates)
        else pd.to_datetime(window_meta["train_end"]).strftime("%Y-%m-%d"),
        "test_start": pd.to_datetime(window_meta["test_start"]).strftime("%Y-%m-%d"),
        "test_end": pd.to_datetime(window_meta["test_end"]).strftime("%Y-%m-%d"),
        "status": "ok",
    }
    if train_df_w.empty or test_df_w.empty:
        result["status"] = "insufficient_data"
        return result, []

    direction = signal_direction
    cv_stats = None
    if signal_direction_mode == "cv_ic":
        cv_scores_w = time_series_cv_ic(
            train_df_w,
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
        )
        if cv_scores_w:
            cv_mean = float(np.nanmean(cv_scores_w))
            cv_std = float(np.nanstd(cv_scores_w))
            if np.isfinite(cv_mean) and cv_mean != 0 and abs(cv_mean) >= min_abs_ic_to_flip:
                direction = float(np.sign(cv_mean))
            cv_stats = {
                "mean": cv_mean,
                "std": cv_std,
                "scores": [float(score) for score in cv_scores_w],
            }

    model_w = build_model(model_type, model_params)
    train_weights_w = build_sample_weight(
        train_df_w,
        sample_weight_mode,
        params=sample_weight_params,
    )
    fit_model(
        model_w,
        model_type,
        train_df_w,
        features=features,
        target_col=train_target,
        sample_weight=train_weights_w,
    )
    importance_df_w, importance_source_w = feature_importance_frame(model_w, features)
    importance_rows: list[dict[str, Any]] = []
    if not importance_df_w.empty:
        for _, row in importance_df_w.iterrows():
            importance_rows.append(
                {
                    "window": window_id,
                    "train_start": result["train_start"],
                    "train_end": result["train_end"],
                    "test_start": result["test_start"],
                    "test_end": result["test_end"],
                    "feature": str(row["feature"]),
                    "importance": float(row["importance"]),
                    "importance_source": importance_source_w,
                }
            )

    train_eval = train_df_w.copy()
    train_eval["pred"] = model_w.predict(train_eval[features])
    _postprocess_pred_column(
        train_eval,
        "pred",
        method=score_postprocess_method,
        columns=score_postprocess_columns,
        strength=score_postprocess_strength,
        min_obs=score_postprocess_min_obs,
    )
    train_ic_raw_stats = None
    if signal_direction_mode == "train_ic":
        train_ic_raw = daily_ic_series(train_eval, target, "pred")
        train_ic_raw_stats = summarize_ic(train_ic_raw)
        raw_mean = train_ic_raw_stats.get("mean", np.nan)
        if np.isfinite(raw_mean) and raw_mean != 0:
            direction = float(np.sign(raw_mean))
        else:
            direction = 1.0

    train_signal_col = "pred"
    if direction != 1.0:
        train_eval["signal"] = train_eval["pred"] * direction
        train_signal_col = "signal"

    train_ic_stats = {}
    if report_train_ic:
        train_ic_stats = summarize_ic(daily_ic_series(train_eval, target, train_signal_col))

    test_eval = test_df_w.copy()
    test_eval["pred"] = model_w.predict(test_eval[features])
    _postprocess_pred_column(
        test_eval,
        "pred",
        method=score_postprocess_method,
        columns=score_postprocess_columns,
        strength=score_postprocess_strength,
        min_obs=score_postprocess_min_obs,
    )
    test_eval["signal_eval"] = test_eval["pred"] * direction
    eval_allowed_dates_w = test_dates if sample_on_rebalance_dates else None
    eval_df_w, rebalance_dates_w = _sample_rebalance_frame(
        test_eval,
        frequency=rebalance_frequency,
        valid_dates=valid_dates_set,
        allowed_dates=eval_allowed_dates_w,
    )

    signal_col_w = "signal_eval"
    ic_stats_w = summarize_ic(daily_ic_series(eval_df_w, target, signal_col_w))
    pearson_ic_stats_w = summarize_ic(
        daily_ic_series(eval_df_w, target, signal_col_w, method="pearson")
    )
    error_metrics_w = regression_error_metrics(eval_df_w[target], eval_df_w[signal_col_w])
    hit_rate_w = hit_rate(eval_df_w[target], eval_df_w[signal_col_w])

    perm_stats_w = None
    if wf_perm_test_enabled:
        perm_scores = _permutation_test_ic(
            train_df_w,
            test_df_w,
            wf_perm_test_runs,
            wf_perm_test_seed,
            direction,
            model_type=model_type,
            model_params=model_params,
            features=features,
            fit_target_col=train_target,
            target_col=target,
            sample_weight_mode=sample_weight_mode,
            sample_weight_params=sample_weight_params,
            eval_dates=rebalance_dates_w,
            score_postprocess_method=score_postprocess_method,
            score_postprocess_columns=score_postprocess_columns,
            score_postprocess_strength=score_postprocess_strength,
            score_postprocess_min_obs=score_postprocess_min_obs,
        )
        if perm_scores:
            perm_stats_w = {
                "mean": float(np.nanmean(perm_scores)),
                "std": float(np.nanstd(perm_scores)),
                "scores": [float(score) for score in perm_scores],
                "runs": int(len(perm_scores)),
            }

    quantile_ts_w = quantile_returns(eval_df_w, signal_col_w, target, n_quantiles)
    quantile_mean_w = quantile_ts_w.mean() if not quantile_ts_w.empty else pd.Series(dtype=float)
    long_short_w = (
        float(quantile_mean_w.iloc[-1] - quantile_mean_w.iloc[0])
        if not quantile_mean_w.empty
        else None
    )

    k_w = min(top_k, eval_df_w["symbol"].nunique())
    if k_w > 0 and rebalance_dates_w:
        turnover_series_w = estimate_turnover(
            eval_df_w,
            signal_col_w,
            k_w,
            rebalance_dates_w,
            buffer_exit=eval_buffer_exit,
            buffer_entry=eval_buffer_entry,
        )
    else:
        turnover_series_w = pd.Series(dtype=float, name="turnover")
    turnover_mean_w = float(turnover_series_w.mean()) if not turnover_series_w.empty else None

    topk_positive_w = topk_positive_ratio(eval_df_w, signal_col_w, target, k_w)

    bt_stats_w = None
    bt_benchmark_stats_w = None
    bt_active_stats_w = None
    if wf_backtest_enabled:
        bt_direction = (
            direction if backtest_signal_direction_raw is None else backtest_signal_direction_raw
        )
        bt_pred_col = "pred"
        test_start = pd.to_datetime(window_meta["test_start"])
        test_end = pd.to_datetime(window_meta["test_end"])
        test_full_w = df_full[
            (df_full["trade_date"] >= test_start) & (df_full["trade_date"] <= test_end)
        ].copy()
        if test_full_w.empty:
            bt_result_w = None
        else:
            test_full_w["pred"] = model_w.predict(test_full_w[features])
            _postprocess_pred_column(
                test_full_w,
                "pred",
                method=score_postprocess_method,
                columns=score_postprocess_columns,
                strength=score_postprocess_strength,
                min_obs=score_postprocess_min_obs,
            )
            if bt_direction != 1.0:
                test_full_w["signal_bt"] = test_full_w["pred"] * bt_direction
                bt_pred_col = "signal_bt"
            bt_rebalance = get_rebalance_dates(
                sorted(test_full_w["trade_date"].unique()), backtest_rebalance_frequency
            )
            if valid_dates_set:
                bt_rebalance = [d for d in bt_rebalance if d in valid_dates_set]
            try:
                bt_result_w = backtest_topk_fn(
                    test_full_w,
                    pred_col=bt_pred_col,
                    price_col=price_col,
                    rebalance_dates=bt_rebalance,
                    top_k=backtest_top_k,
                    shift_days=label_shift_days,
                    cost_bps=backtest_cost_bps_effective,
                    trading_days_per_year=backtest_trading_days_per_year,
                    exit_mode=backtest_exit_mode,
                    exit_horizon_days=backtest_exit_horizon_days,
                    long_only=backtest_long_only,
                    short_k=backtest_short_k,
                    buffer_exit=backtest_buffer_exit,
                    buffer_entry=backtest_buffer_entry,
                    group_col=backtest_group_col if backtest_group_col in test_full_w.columns else None,
                    max_names_per_group=backtest_max_names_per_group,
                    tradable_col=backtest_tradable_col
                    if backtest_tradable_col in backtest_pricing_df.columns
                    else None,
                    exit_price_policy=backtest_exit_price_policy,
                    exit_fallback_policy=backtest_exit_fallback_policy,
                    execution=execution_model,
                    pricing_data=backtest_pricing_df,
                )
            except ValueError:
                bt_result_w = None
        if bt_result_w is not None:
            bt_stats_w, bt_net_w, _, _, bt_periods_w = bt_result_w
            bench_series_w, bench_periods_w = build_benchmark_series(
                benchmark_df,
                execution_model.entry_policy.price_col,
                execution_model.exit_policy.price_col,
                bt_periods_w,
                benchmark_return_series=benchmark_return_series,
            )
            if not bench_series_w.empty:
                bt_benchmark_stats_w = summarize_period_returns(
                    bench_series_w,
                    bench_periods_w,
                    backtest_trading_days_per_year,
                )
                periods_per_year = bt_stats_w.get("periods_per_year", np.nan)
                bt_active_stats_w, _ = summarize_active_returns(
                    bt_net_w, bench_series_w, periods_per_year
                )

    result.update(
        {
            "signal_direction": direction,
            "signal_direction_mode": signal_direction_mode,
            "cv_ic": cv_stats,
            "train_ic": train_ic_stats if report_train_ic else None,
            "train_ic_raw": train_ic_raw_stats,
            "test_ic": ic_stats_w,
            "test_pearson_ic": pearson_ic_stats_w,
            "error_metrics": error_metrics_w,
            "hit_rate": hit_rate_w,
            "topk_positive_ratio": topk_positive_w,
            "long_short": long_short_w,
            "turnover_mean": turnover_mean_w,
            "backtest": {
                "stats": bt_stats_w,
                "benchmark": bt_benchmark_stats_w,
                "active": bt_active_stats_w,
            }
            if wf_backtest_enabled
            else None,
            "permutation_test": perm_stats_w,
            "feature_importance_source": importance_source_w,
            "feature_importance_top": [
                {"feature": str(item["feature"]), "importance": float(item["importance"])}
                for _, item in importance_df_w.head(wf_feature_top_k).iterrows()
            ],
        }
    )
    return result, importance_rows


def _evaluate_period(
    label: str,
    model_eval: Any,
    test_df_full: pd.DataFrame,
    test_dates: np.ndarray,
    *,
    context: Mapping[str, Any],
    run_perm_test: bool,
    perm_train_df: Optional[pd.DataFrame] = None,
    perm_test_df: Optional[pd.DataFrame] = None,
    allow_live_fallback: bool = True,
) -> dict[str, Any]:
    features = context["features"]
    target = context["target"]
    signal_direction = context["signal_direction"]
    backtest_signal_direction = context["backtest_signal_direction"]
    sample_on_rebalance_dates = context["sample_on_rebalance_dates"]
    rebalance_frequency = context["rebalance_frequency"]
    valid_dates_set = context["valid_dates_set"]
    perm_test_runs = context["perm_test_runs"]
    perm_test_seed = context["perm_test_seed"]
    model_type = context["model_type"]
    model_params = context["model_params"]
    train_target = context["train_target"]
    sample_weight_mode = context["sample_weight_mode"]
    sample_weight_params = context["sample_weight_params"]
    score_postprocess_method = context["score_postprocess_method"]
    score_postprocess_columns = context["score_postprocess_columns"]
    score_postprocess_strength = context["score_postprocess_strength"]
    score_postprocess_min_obs = context["score_postprocess_min_obs"]
    label_horizon_mode = context["label_horizon_mode"]
    label_horizon_effective = context["label_horizon_effective"]
    n_quantiles = context["n_quantiles"]
    top_k = context["top_k"]
    eval_buffer_exit = context["eval_buffer_exit"]
    eval_buffer_entry = context["eval_buffer_entry"]
    transaction_cost_bps = context["transaction_cost_bps"]
    bucket_ic_enabled = context["bucket_ic_enabled"]
    bucket_ic_schemes = context["bucket_ic_schemes"]
    bucket_ic_method = context["bucket_ic_method"]
    bucket_ic_min_count = context["bucket_ic_min_count"]
    backtest_rebalance_frequency = context["backtest_rebalance_frequency"]
    backtest_enabled = context["backtest_enabled"]
    live_enabled = context["live_enabled"]
    backtest_top_k = context["backtest_top_k"]
    label_shift_days = context["label_shift_days"]
    backtest_weighting = context["backtest_weighting"]
    backtest_buffer_exit = context["backtest_buffer_exit"]
    backtest_buffer_entry = context["backtest_buffer_entry"]
    backtest_long_only = context["backtest_long_only"]
    backtest_short_k = context["backtest_short_k"]
    backtest_tradable_col = context["backtest_tradable_col"]
    backtest_group_col = context["backtest_group_col"]
    backtest_max_names_per_group = context["backtest_max_names_per_group"]
    execution_model = context["execution_model"]
    execution_sim_config = context["execution_sim_config"]
    positions_by_rebalance_live = context["positions_by_rebalance_live"]
    backtest_cost_bps_effective = context["backtest_cost_bps_effective"]
    backtest_trading_days_per_year = context["backtest_trading_days_per_year"]
    backtest_exit_mode = context["backtest_exit_mode"]
    backtest_exit_horizon_days = context["backtest_exit_horizon_days"]
    backtest_pricing_df = context["backtest_pricing_df"]
    backtest_exit_price_policy = context["backtest_exit_price_policy"]
    backtest_exit_fallback_policy = context["backtest_exit_fallback_policy"]
    benchmark_df = context["benchmark_df"]
    benchmark_return_series = context["benchmark_return_series"]
    exposure_source_df = context.get("exposure_source_df")
    industry_source_df = context.get("industry_source_df")
    fundamentals_mcap_col = context.get("fundamentals_mcap_col")
    industry_columns = context.get("industry_columns", [])
    price_col = context["price_col"]
    price_passthrough_cols = context.get("price_passthrough_cols", [])
    passthrough_cols = context["passthrough_cols"]
    bucket_cols = context["bucket_cols"]
    backtest_topk_fn = context.get("backtest_topk_fn", backtest_topk)
    bucket_ic_summary_fn = context.get("bucket_ic_summary_fn", bucket_ic_summary)

    label_prefix = f"[{label}] " if label else ""
    result = _empty_period_result()
    if test_df_full is None or test_df_full.empty:
        logger.info("%sEvaluation skipped: no data.", label_prefix)
        return result

    eval_df_full = _score_period_frame(
        test_df_full,
        model_eval,
        features=features,
        score_postprocess_method=score_postprocess_method,
        score_postprocess_columns=score_postprocess_columns,
        score_postprocess_strength=score_postprocess_strength,
        score_postprocess_min_obs=score_postprocess_min_obs,
        signal_direction=signal_direction,
        backtest_signal_direction=backtest_signal_direction,
        label_prefix=label_prefix,
    )

    eval_allowed_dates = test_dates if sample_on_rebalance_dates else None
    eval_df, rebalance_dates_eval = _sample_rebalance_frame(
        eval_df_full,
        frequency=rebalance_frequency,
        valid_dates=valid_dates_set,
        allowed_dates=eval_allowed_dates,
    )
    result["eval_rebalance_dates"] = rebalance_dates_eval

    signal_col = "signal_eval"
    _record_primary_period_metrics(
        result,
        eval_df,
        target=target,
        signal_col=signal_col,
        label_prefix=label_prefix,
    )

    if run_perm_test:
        if perm_train_df is None or perm_test_df is None:
            raise SystemExit("Permutation test requested but data was not provided.")
        logger.info("%sPermutation test (shuffle train labels within date) ...", label_prefix)
        perm_scores = _permutation_test_ic(
            perm_train_df,
            perm_test_df,
            perm_test_runs,
            perm_test_seed,
            signal_direction,
            model_type=model_type,
            model_params=model_params,
            features=features,
            fit_target_col=train_target,
            target_col=target,
            sample_weight_mode=sample_weight_mode,
            sample_weight_params=sample_weight_params,
            eval_dates=rebalance_dates_eval,
            score_postprocess_method=score_postprocess_method,
            score_postprocess_columns=score_postprocess_columns,
            score_postprocess_strength=score_postprocess_strength,
            score_postprocess_min_obs=score_postprocess_min_obs,
        )
        if perm_scores:
            perm_mean = np.nanmean(perm_scores)
            perm_std = np.nanstd(perm_scores)
            logger.info(
                "%sPermutation IC: mean=%.4f, std=%.4f, runs=%s",
                label_prefix,
                perm_mean,
                perm_std,
                len(perm_scores),
            )
            logger.info("%sPermutation ICs: %s", label_prefix, [f"{s:.4f}" for s in perm_scores])
            result["perm_stats"] = {
                "mean": float(perm_mean),
                "std": float(perm_std),
                "scores": [float(score) for score in perm_scores],
                "runs": int(len(perm_scores)),
            }

    trade_dates_sorted_full = sorted(eval_df_full["trade_date"].unique())
    rebalance_dates_full = get_rebalance_dates(trade_dates_sorted_full, rebalance_frequency)
    rebalance_gap = estimate_rebalance_gap(trade_dates_sorted_full, rebalance_dates_full)
    if (
        backtest_exit_mode == "rebalance"
        and np.isfinite(rebalance_gap)
        and label_horizon_mode == "fixed"
    ):
        gap_diff = abs(rebalance_gap - label_horizon_effective)
        if gap_diff >= max(3.0, rebalance_gap * 0.25):
            logger.warning(
                "%sLabel horizon (%s days) differs from rebalance gap (median %.1f days).",
                label_prefix,
                label_horizon_effective,
                rebalance_gap,
            )

    _record_quantile_turnover_bucket_metrics(
        result,
        eval_df,
        target=target,
        signal_col=signal_col,
        label_prefix=label_prefix,
        n_quantiles=n_quantiles,
        top_k=top_k,
        rebalance_dates_eval=rebalance_dates_eval,
        eval_buffer_exit=eval_buffer_exit,
        eval_buffer_entry=eval_buffer_entry,
        transaction_cost_bps=transaction_cost_bps,
        bucket_ic_enabled=bucket_ic_enabled,
        bucket_ic_schemes=bucket_ic_schemes,
        bucket_ic_method=bucket_ic_method,
        bucket_ic_min_count=bucket_ic_min_count,
        bucket_ic_summary_fn=bucket_ic_summary_fn,
    )

    _, bt_rebalance = _sample_rebalance_frame(
        eval_df_full,
        frequency=backtest_rebalance_frequency,
        valid_dates=valid_dates_set,
    )
    result["backtest_rebalance_dates"] = bt_rebalance
    bt_pred_col = "signal_backtest"

    positions_by_rebalance = None
    if backtest_enabled or not live_enabled or not allow_live_fallback:
        positions_by_rebalance = build_positions_by_rebalance(
            eval_df_full,
            pred_col=bt_pred_col,
            price_col=price_col,
            rebalance_dates=bt_rebalance,
            top_k=backtest_top_k,
            shift_days=label_shift_days,
            weighting=backtest_weighting,
            buffer_exit=backtest_buffer_exit,
            buffer_entry=backtest_buffer_entry,
            long_only=backtest_long_only,
            short_k=backtest_short_k,
            tradable_col=backtest_tradable_col if backtest_tradable_col in eval_df_full.columns else None,
            group_col=backtest_group_col if backtest_group_col in eval_df_full.columns else None,
            max_names_per_group=backtest_max_names_per_group,
            execution=execution_model,
        )
    if allow_live_fallback and live_enabled and not backtest_enabled:
        positions_by_rebalance = positions_by_rebalance_live
    result["positions_by_rebalance"] = positions_by_rebalance

    if (
        backtest_enabled
        and getattr(execution_sim_config, "enabled", False)
        and positions_by_rebalance is not None
        and not positions_by_rebalance.empty
    ):
        sim_result = simulate_capacity_execution(
            positions_by_rebalance,
            backtest_pricing_df,
            execution_sim_config,
            price_col=execution_model.entry_policy.price_col,
            tradable_col=backtest_tradable_col
            if backtest_tradable_col in backtest_pricing_df.columns
            else None,
        )
        result["execution_sim_summary"] = sim_result.summary
        result["execution_sim_orders"] = sim_result.orders
        result["execution_sim_fills"] = sim_result.fills
        if sim_result.summary.get("status") == "ok":
            logger.info(
                "%sExecution sim: fill ratio %.2f%%, unfilled %.2f",
                label_prefix,
                float(sim_result.summary.get("fill_ratio", np.nan)) * 100,
                float(sim_result.summary.get("unfilled_notional", 0.0)),
            )

    bt_result = None
    bt_attempted = False
    if backtest_enabled:
        bt_attempted = True
        try:
            bt_result = backtest_topk_fn(
                eval_df_full,
                pred_col=bt_pred_col,
                price_col=price_col,
                rebalance_dates=bt_rebalance,
                top_k=backtest_top_k,
                shift_days=label_shift_days,
                cost_bps=backtest_cost_bps_effective,
                trading_days_per_year=backtest_trading_days_per_year,
                exit_mode=backtest_exit_mode,
                exit_horizon_days=backtest_exit_horizon_days,
                long_only=backtest_long_only,
                short_k=backtest_short_k,
                weighting=backtest_weighting,
                buffer_exit=backtest_buffer_exit,
                buffer_entry=backtest_buffer_entry,
                group_col=backtest_group_col if backtest_group_col in eval_df_full.columns else None,
                max_names_per_group=backtest_max_names_per_group,
                tradable_col=backtest_tradable_col
                if backtest_tradable_col in backtest_pricing_df.columns
                else None,
                exit_price_policy=backtest_exit_price_policy,
                exit_fallback_policy=backtest_exit_fallback_policy,
                execution=execution_model,
                pricing_data=backtest_pricing_df,
            )
        except ValueError as exc:
            logger.warning("%sBacktest skipped: %s", label_prefix, exc)
            bt_result = None

    if bt_attempted:
        _record_backtest_outputs(
            result,
            bt_result,
            label_prefix=label_prefix,
            backtest_long_only=backtest_long_only,
            backtest_exit_mode=backtest_exit_mode,
            backtest_exit_price_policy=backtest_exit_price_policy,
            benchmark_df=benchmark_df,
            benchmark_return_series=benchmark_return_series,
            execution_model=execution_model,
            backtest_trading_days_per_year=backtest_trading_days_per_year,
        )

    result["scored_data"] = _build_scored_data(
        eval_df_full,
        price_col=price_col,
        target=target,
        price_passthrough_cols=price_passthrough_cols,
        passthrough_cols=passthrough_cols,
        bucket_cols=bucket_cols,
        backtest_tradable_col=backtest_tradable_col,
    )

    _record_exposure_outputs(
        result,
        eval_df_full=eval_df_full,
        exposure_source_df=exposure_source_df,
        positions_by_rebalance=positions_by_rebalance,
        backtest_enabled=backtest_enabled,
        backtest_pricing_df=backtest_pricing_df,
        price_col=price_col,
        benchmark_df=benchmark_df,
        benchmark_return_series=benchmark_return_series,
        fundamentals_mcap_col=fundamentals_mcap_col,
        industry_columns=industry_columns,
        industry_source_df=industry_source_df,
    )
    return result
