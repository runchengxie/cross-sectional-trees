from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from ..metrics import daily_ic_series, summarize_ic
from ..modeling import build_model, feature_importance_frame, fit_model
from ..split import build_sample_weight, time_series_cv_ic
from ..transform import apply_score_postprocess
from .contracts import (
    TrainEvalBacktestSettings,
    TrainEvalData,
    TrainEvalFeatureTarget,
    TrainEvalLiveSettings,
    TrainEvalModelSettings,
    TrainEvalPeriodSettings,
    TrainEvalRequest,
    TrainEvalServices,
    TrainEvalSignalSettings,
    TrainEvalWalkForwardSettings,
)
from .dates import build_walk_forward_windows
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

logger = logging.getLogger("cstree")


@dataclass(frozen=True)
class _TrainFitResult:
    model: Any
    train_eval_df: pd.DataFrame
    updated_signal_direction: float
    train_signal_col: str
    train_ic_raw_stats: dict[str, Any]
    train_ic_series: pd.Series
    train_ic_stats: dict[str, Any]
    train_pearson_ic_series: pd.Series
    train_pearson_ic_stats: dict[str, Any]
    cv_scores_adj: list[float] | None


def run_train_eval_stage(
    *,
    request: TrainEvalRequest | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    if request is not None:
        if kwargs:
            raise TypeError("Pass either request or keyword stage fields, not both.")
        return _run_train_eval_stage_impl(request)
    return _run_train_eval_stage_impl(_train_eval_request_from_kwargs(kwargs))


def _train_eval_request_from_kwargs(kwargs: dict[str, Any]) -> TrainEvalRequest:
    used: set[str] = set()

    def get(name: str) -> Any:
        used.add(name)
        try:
            return kwargs[name]
        except KeyError as exc:
            raise TypeError(f"Missing train/eval stage field: {name}") from exc

    request = TrainEvalRequest(
        data=TrainEvalData(
            train_df=get("train_df"),
            test_df=get("test_df"),
            test_dates=get("test_dates"),
            df_features=get("df_features"),
            df_full=get("df_full"),
            df_model_sorted=get("df_model_sorted"),
            all_dates=get("all_dates"),
            all_date_start_rows=get("all_date_start_rows"),
            all_date_end_rows=get("all_date_end_rows"),
            all_date_to_pos=get("all_date_to_pos"),
            valid_dates_set=get("valid_dates_set"),
            backtest_pricing_df=get("backtest_pricing_df"),
            benchmark_df=get("benchmark_df"),
            benchmark_return_series=get("benchmark_return_series"),
            industry_source_df=get("industry_source_df"),
            passthrough_cols=get("passthrough_cols"),
            industry_keep_columns=get("industry_keep_columns"),
            price_passthrough_cols=get("price_passthrough_cols"),
            bucket_cols=get("bucket_cols"),
        ),
        feature_target=TrainEvalFeatureTarget(
            features=get("features"),
            target=get("target"),
            train_target=get("train_target"),
            price_col=get("price_col"),
            fundamentals_mcap_col=get("fundamentals_mcap_col"),
        ),
        model=TrainEvalModelSettings(
            model_type=get("model_type"),
            model_params=get("model_params"),
            model_cfg=get("model_cfg"),
            sample_weight_mode=get("sample_weight_mode"),
            sample_weight_params=get("sample_weight_params"),
            n_splits=get("n_splits"),
            embargo_steps=get("embargo_steps"),
            purge_steps=get("purge_steps"),
            train_window_mode=get("train_window_mode"),
            train_window_size=get("train_window_size"),
            train_window_unit=get("train_window_unit"),
        ),
        signal=TrainEvalSignalSettings(
            signal_direction_mode=get("signal_direction_mode"),
            signal_direction=get("signal_direction"),
            min_abs_ic_to_flip=get("min_abs_ic_to_flip"),
            score_postprocess_method=get("score_postprocess_method"),
            score_postprocess_columns=get("score_postprocess_columns"),
            score_postprocess_strength=get("score_postprocess_strength"),
            score_postprocess_min_obs=get("score_postprocess_min_obs"),
            report_train_ic=get("report_train_ic"),
        ),
        live=TrainEvalLiveSettings(
            live_enabled=get("live_enabled"),
            live_as_of=get("live_as_of"),
            live_signal_asof=get("live_signal_asof"),
            live_entry_date=get("live_entry_date"),
            market=get("market"),
            provider=get("provider"),
            live_train_mode=get("live_train_mode"),
            min_symbols_per_date=get("min_symbols_per_date"),
        ),
        backtest=TrainEvalBacktestSettings(
            backtest_top_k=get("backtest_top_k"),
            label_shift_days=get("label_shift_days"),
            backtest_weighting=get("backtest_weighting"),
            backtest_buffer_exit=get("backtest_buffer_exit"),
            backtest_buffer_entry=get("backtest_buffer_entry"),
            backtest_long_only=get("backtest_long_only"),
            backtest_short_k=get("backtest_short_k"),
            backtest_tradable_col=get("backtest_tradable_col"),
            backtest_group_col=get("backtest_group_col"),
            backtest_max_names_per_group=get("backtest_max_names_per_group"),
            execution_model=get("execution_model"),
            execution_sim_config=get("execution_sim_config"),
            backtest_rebalance_frequency=get("backtest_rebalance_frequency"),
            backtest_enabled=get("backtest_enabled"),
            backtest_signal_direction_raw=get("backtest_signal_direction_raw"),
            backtest_cost_bps_effective=get("backtest_cost_bps_effective"),
            backtest_trading_days_per_year=get("backtest_trading_days_per_year"),
            backtest_exit_mode=get("backtest_exit_mode"),
            backtest_exit_horizon_days=get("backtest_exit_horizon_days"),
            backtest_exit_price_policy=get("backtest_exit_price_policy"),
            backtest_exit_fallback_policy=get("backtest_exit_fallback_policy"),
        ),
        period=TrainEvalPeriodSettings(
            rebalance_frequency=get("rebalance_frequency"),
            sample_on_rebalance_dates=get("sample_on_rebalance_dates"),
            perm_test_runs=get("perm_test_runs"),
            perm_test_seed=get("perm_test_seed"),
            label_horizon_mode=get("label_horizon_mode"),
            label_horizon_effective=get("label_horizon_effective"),
            n_quantiles=get("n_quantiles"),
            top_k=get("top_k"),
            eval_buffer_exit=get("eval_buffer_exit"),
            eval_buffer_entry=get("eval_buffer_entry"),
            transaction_cost_bps=get("transaction_cost_bps"),
            bucket_ic_enabled=get("bucket_ic_enabled"),
            bucket_ic_schemes=get("bucket_ic_schemes"),
            bucket_ic_method=get("bucket_ic_method"),
            bucket_ic_min_count=get("bucket_ic_min_count"),
            rolling_windows_months=get("rolling_windows_months"),
        ),
        walk_forward=TrainEvalWalkForwardSettings(
            wf_enabled=get("wf_enabled"),
            wf_n_windows=get("wf_n_windows"),
            wf_test_size=get("wf_test_size"),
            wf_step_size=get("wf_step_size"),
            effective_gap_steps=get("effective_gap_steps"),
            wf_anchor_end=get("wf_anchor_end"),
            wf_feature_top_k=get("wf_feature_top_k"),
            wf_backtest_enabled=get("wf_backtest_enabled"),
            wf_perm_test_enabled=get("wf_perm_test_enabled"),
            wf_perm_test_runs=get("wf_perm_test_runs"),
            wf_perm_test_seed=get("wf_perm_test_seed"),
        ),
        services=TrainEvalServices(
            backtest_topk_fn=get("backtest_topk_fn"),
            bucket_ic_summary_fn=get("bucket_ic_summary_fn"),
        ),
    )
    unknown = sorted(set(kwargs) - used)
    if unknown:
        raise TypeError(f"Unexpected train/eval stage fields: {', '.join(unknown)}")
    return request


def _fit_model_and_score_train(
    train_df: pd.DataFrame,
    *,
    feature_target: TrainEvalFeatureTarget,
    model_settings: TrainEvalModelSettings,
    signal_settings: TrainEvalSignalSettings,
    cv_scores_raw: list[float],
) -> _TrainFitResult:
    features = feature_target.features
    target = feature_target.target
    train_target = feature_target.train_target
    updated_signal_direction = signal_settings.signal_direction

    logger.info("Fitting model (%s) ...", model_settings.model_type)
    model = build_model(model_settings.model_type, model_settings.model_params)
    train_weights = build_sample_weight(
        train_df,
        model_settings.sample_weight_mode,
        params=model_settings.sample_weight_params,
    )
    fit_model(
        model,
        model_settings.model_type,
        train_df,
        features=features,
        target_col=train_target,
        sample_weight=train_weights,
    )

    train_eval_df = train_df.copy()
    train_eval_df["pred"] = model.predict(train_eval_df[features])
    train_eval_df["pred"] = apply_score_postprocess(
        train_eval_df,
        "pred",
        method=signal_settings.score_postprocess_method,
        columns=signal_settings.score_postprocess_columns,
        strength=signal_settings.score_postprocess_strength,
        min_obs=signal_settings.score_postprocess_min_obs,
    )
    train_ic_raw_stats = {}
    if signal_settings.signal_direction_mode == "train_ic":
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

    cv_scores_adj = None
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
    if signal_settings.report_train_ic:
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

    return _TrainFitResult(
        model=model,
        train_eval_df=train_eval_df,
        updated_signal_direction=updated_signal_direction,
        train_signal_col=train_signal_col,
        train_ic_raw_stats=train_ic_raw_stats,
        train_ic_series=train_ic_series,
        train_ic_stats=train_ic_stats,
        train_pearson_ic_series=train_pearson_ic_series,
        train_pearson_ic_stats=train_pearson_ic_stats,
        cv_scores_adj=cv_scores_adj,
    )


def _build_period_eval_context(
    request: TrainEvalRequest,
    *,
    live_state: dict[str, Any],
    updated_signal_direction: float,
    backtest_signal_direction: float,
) -> dict[str, Any]:
    data = request.data
    feature_target = request.feature_target
    model_settings = request.model
    signal_settings = request.signal
    live_settings = request.live
    backtest_settings = request.backtest
    period_settings = request.period
    services = request.services

    return {
        "features": feature_target.features,
        "target": feature_target.target,
        "signal_direction": updated_signal_direction,
        "backtest_signal_direction": backtest_signal_direction,
        "sample_on_rebalance_dates": period_settings.sample_on_rebalance_dates,
        "score_postprocess_method": signal_settings.score_postprocess_method,
        "score_postprocess_columns": signal_settings.score_postprocess_columns,
        "score_postprocess_strength": signal_settings.score_postprocess_strength,
        "score_postprocess_min_obs": signal_settings.score_postprocess_min_obs,
        "rebalance_frequency": period_settings.rebalance_frequency,
        "valid_dates_set": data.valid_dates_set,
        "perm_test_runs": period_settings.perm_test_runs,
        "perm_test_seed": period_settings.perm_test_seed,
        "model_type": model_settings.model_type,
        "model_params": model_settings.model_params,
        "train_target": feature_target.train_target,
        "sample_weight_mode": model_settings.sample_weight_mode,
        "sample_weight_params": model_settings.sample_weight_params,
        "label_horizon_mode": period_settings.label_horizon_mode,
        "label_horizon_effective": period_settings.label_horizon_effective,
        "n_quantiles": period_settings.n_quantiles,
        "top_k": period_settings.top_k,
        "eval_buffer_exit": period_settings.eval_buffer_exit,
        "eval_buffer_entry": period_settings.eval_buffer_entry,
        "transaction_cost_bps": period_settings.transaction_cost_bps,
        "bucket_ic_enabled": period_settings.bucket_ic_enabled,
        "bucket_ic_schemes": period_settings.bucket_ic_schemes,
        "bucket_ic_method": period_settings.bucket_ic_method,
        "bucket_ic_min_count": period_settings.bucket_ic_min_count,
        "backtest_rebalance_frequency": backtest_settings.backtest_rebalance_frequency,
        "backtest_enabled": backtest_settings.backtest_enabled,
        "live_enabled": live_settings.live_enabled,
        "backtest_top_k": backtest_settings.backtest_top_k,
        "label_shift_days": backtest_settings.label_shift_days,
        "backtest_weighting": backtest_settings.backtest_weighting,
        "backtest_buffer_exit": backtest_settings.backtest_buffer_exit,
        "backtest_buffer_entry": backtest_settings.backtest_buffer_entry,
        "backtest_long_only": backtest_settings.backtest_long_only,
        "backtest_short_k": backtest_settings.backtest_short_k,
        "backtest_tradable_col": backtest_settings.backtest_tradable_col,
        "backtest_group_col": backtest_settings.backtest_group_col,
        "backtest_max_names_per_group": backtest_settings.backtest_max_names_per_group,
        "execution_model": backtest_settings.execution_model,
        "execution_sim_config": backtest_settings.execution_sim_config,
        "positions_by_rebalance_live": live_state["positions_by_rebalance_live"],
        "backtest_cost_bps_effective": backtest_settings.backtest_cost_bps_effective,
        "backtest_trading_days_per_year": backtest_settings.backtest_trading_days_per_year,
        "backtest_exit_mode": backtest_settings.backtest_exit_mode,
        "backtest_exit_horizon_days": backtest_settings.backtest_exit_horizon_days,
        "backtest_pricing_df": data.backtest_pricing_df,
        "backtest_exit_price_policy": backtest_settings.backtest_exit_price_policy,
        "backtest_exit_fallback_policy": backtest_settings.backtest_exit_fallback_policy,
        "benchmark_df": data.benchmark_df,
        "benchmark_return_series": data.benchmark_return_series,
        "exposure_source_df": data.df_full,
        "industry_source_df": data.industry_source_df,
        "fundamentals_mcap_col": feature_target.fundamentals_mcap_col,
        "industry_columns": list(
            dict.fromkeys(data.passthrough_cols + data.industry_keep_columns)
        ),
        "price_col": feature_target.price_col,
        "price_passthrough_cols": data.price_passthrough_cols,
        "passthrough_cols": data.passthrough_cols,
        "bucket_cols": data.bucket_cols,
        "backtest_topk_fn": services.backtest_topk_fn,
        "bucket_ic_summary_fn": services.bucket_ic_summary_fn,
    }


def _build_walk_forward_context(
    request: TrainEvalRequest,
    *,
    updated_signal_direction: float,
) -> dict[str, Any]:
    data = request.data
    feature_target = request.feature_target
    model_settings = request.model
    signal_settings = request.signal
    backtest_settings = request.backtest
    period_settings = request.period
    walk_forward_settings = request.walk_forward
    services = request.services

    return {
        "df_model_sorted": data.df_model_sorted,
        "all_date_start_rows": data.all_date_start_rows,
        "all_date_end_rows": data.all_date_end_rows,
        "all_date_to_pos": data.all_date_to_pos,
        "train_window_mode": model_settings.train_window_mode,
        "train_window_size": model_settings.train_window_size,
        "train_window_unit": model_settings.train_window_unit,
        "signal_direction": updated_signal_direction,
        "signal_direction_mode": signal_settings.signal_direction_mode,
        "features": feature_target.features,
        "target": feature_target.target,
        "n_splits": model_settings.n_splits,
        "embargo_steps": model_settings.embargo_steps,
        "purge_steps": model_settings.purge_steps,
        "model_cfg": model_settings.model_cfg,
        "min_abs_ic_to_flip": signal_settings.min_abs_ic_to_flip,
        "sample_weight_mode": model_settings.sample_weight_mode,
        "sample_weight_params": model_settings.sample_weight_params,
        "train_target": feature_target.train_target,
        "model_type": model_settings.model_type,
        "model_params": model_settings.model_params,
        "report_train_ic": signal_settings.report_train_ic,
        "sample_on_rebalance_dates": period_settings.sample_on_rebalance_dates,
        "score_postprocess_method": signal_settings.score_postprocess_method,
        "score_postprocess_columns": signal_settings.score_postprocess_columns,
        "score_postprocess_strength": signal_settings.score_postprocess_strength,
        "score_postprocess_min_obs": signal_settings.score_postprocess_min_obs,
        "rebalance_frequency": period_settings.rebalance_frequency,
        "valid_dates_set": data.valid_dates_set,
        "wf_perm_test_enabled": walk_forward_settings.wf_perm_test_enabled,
        "wf_perm_test_runs": walk_forward_settings.wf_perm_test_runs,
        "wf_perm_test_seed": walk_forward_settings.wf_perm_test_seed,
        "n_quantiles": period_settings.n_quantiles,
        "top_k": period_settings.top_k,
        "eval_buffer_exit": period_settings.eval_buffer_exit,
        "eval_buffer_entry": period_settings.eval_buffer_entry,
        "wf_backtest_enabled": walk_forward_settings.wf_backtest_enabled,
        "backtest_signal_direction_raw": backtest_settings.backtest_signal_direction_raw,
        "df_full": data.df_full,
        "price_col": feature_target.price_col,
        "backtest_rebalance_frequency": backtest_settings.backtest_rebalance_frequency,
        "label_shift_days": backtest_settings.label_shift_days,
        "backtest_cost_bps_effective": backtest_settings.backtest_cost_bps_effective,
        "backtest_trading_days_per_year": backtest_settings.backtest_trading_days_per_year,
        "backtest_exit_mode": backtest_settings.backtest_exit_mode,
        "backtest_exit_horizon_days": backtest_settings.backtest_exit_horizon_days,
        "backtest_long_only": backtest_settings.backtest_long_only,
        "backtest_short_k": backtest_settings.backtest_short_k,
        "backtest_buffer_exit": backtest_settings.backtest_buffer_exit,
        "backtest_buffer_entry": backtest_settings.backtest_buffer_entry,
        "backtest_group_col": backtest_settings.backtest_group_col,
        "backtest_max_names_per_group": backtest_settings.backtest_max_names_per_group,
        "backtest_tradable_col": backtest_settings.backtest_tradable_col,
        "backtest_exit_price_policy": backtest_settings.backtest_exit_price_policy,
        "backtest_exit_fallback_policy": backtest_settings.backtest_exit_fallback_policy,
        "execution_model": backtest_settings.execution_model,
        "execution_sim_config": backtest_settings.execution_sim_config,
        "backtest_pricing_df": data.backtest_pricing_df,
        "benchmark_df": data.benchmark_df,
        "benchmark_return_series": data.benchmark_return_series,
        "backtest_top_k": backtest_settings.backtest_top_k,
        "wf_feature_top_k": walk_forward_settings.wf_feature_top_k,
        "backtest_topk_fn": services.backtest_topk_fn,
    }


def _run_walk_forward_evaluation(
    request: TrainEvalRequest,
    *,
    updated_signal_direction: float,
) -> tuple[list[dict], pd.DataFrame, pd.DataFrame]:
    walk_forward_settings = request.walk_forward
    walk_forward_results: list[dict] = []
    walk_forward_importance_rows: list[dict[str, Any]] = []
    if walk_forward_settings.wf_enabled:
        walk_forward_context = _build_walk_forward_context(
            request,
            updated_signal_direction=updated_signal_direction,
        )
        try:
            walk_forward_test_size = float(walk_forward_settings.wf_test_size)
        except (TypeError, ValueError):
            walk_forward_test_size = None
        windows = build_walk_forward_windows(
            request.data.all_dates,
            walk_forward_test_size,
            walk_forward_settings.wf_n_windows,
            walk_forward_settings.wf_step_size,
            walk_forward_settings.effective_gap_steps,
            walk_forward_settings.wf_anchor_end,
        )
        if not windows:
            logger.info("Walk-forward evaluation skipped: insufficient windows.")
        else:
            if len(windows) < walk_forward_settings.wf_n_windows:
                logger.warning(
                    "Walk-forward requested %s windows but only %s fit "
                    "(test_size=%s, step_size=%s, anchor_end=%s). "
                    "Reduce eval.test_size / eval.walk_forward.test_size, "
                    "set a smaller eval.walk_forward.step_size, or lower n_windows.",
                    walk_forward_settings.wf_n_windows,
                    len(windows),
                    walk_forward_test_size,
                    walk_forward_settings.wf_step_size,
                    walk_forward_settings.wf_anchor_end,
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
        walk_forward_settings.wf_feature_top_k,
    )
    return walk_forward_results, walk_forward_importance_df, walk_forward_feature_stability_df


def _run_train_eval_stage_impl(request: TrainEvalRequest) -> dict[str, Any]:
    data = request.data
    feature_target = request.feature_target
    model_settings = request.model
    signal_settings = request.signal
    live_settings = request.live
    backtest_settings = request.backtest
    period_settings = request.period

    train_df = data.train_df
    test_df = data.test_df
    test_dates = data.test_dates
    df_features = data.df_features
    df_full = data.df_full

    features = feature_target.features
    target = feature_target.target
    train_target = feature_target.train_target
    price_col = feature_target.price_col

    model_type = model_settings.model_type
    model_params = model_settings.model_params
    model_cfg = model_settings.model_cfg
    sample_weight_mode = model_settings.sample_weight_mode
    sample_weight_params = model_settings.sample_weight_params
    n_splits = model_settings.n_splits
    embargo_steps = model_settings.embargo_steps
    purge_steps = model_settings.purge_steps
    train_window_mode = model_settings.train_window_mode
    train_window_size = model_settings.train_window_size
    train_window_unit = model_settings.train_window_unit

    signal_direction_mode = signal_settings.signal_direction_mode
    signal_direction = signal_settings.signal_direction
    min_abs_ic_to_flip = signal_settings.min_abs_ic_to_flip
    score_postprocess_method = signal_settings.score_postprocess_method
    score_postprocess_columns = signal_settings.score_postprocess_columns
    score_postprocess_strength = signal_settings.score_postprocess_strength
    score_postprocess_min_obs = signal_settings.score_postprocess_min_obs

    live_enabled = live_settings.live_enabled
    live_as_of = live_settings.live_as_of
    live_signal_asof = live_settings.live_signal_asof
    live_entry_date = live_settings.live_entry_date
    market = live_settings.market
    provider = live_settings.provider
    live_train_mode = live_settings.live_train_mode
    min_symbols_per_date = live_settings.min_symbols_per_date

    backtest_top_k = backtest_settings.backtest_top_k
    label_shift_days = backtest_settings.label_shift_days
    backtest_weighting = backtest_settings.backtest_weighting
    backtest_buffer_exit = backtest_settings.backtest_buffer_exit
    backtest_buffer_entry = backtest_settings.backtest_buffer_entry
    backtest_long_only = backtest_settings.backtest_long_only
    backtest_short_k = backtest_settings.backtest_short_k
    backtest_tradable_col = backtest_settings.backtest_tradable_col
    backtest_group_col = backtest_settings.backtest_group_col
    backtest_max_names_per_group = backtest_settings.backtest_max_names_per_group
    execution_model = backtest_settings.execution_model
    backtest_rebalance_frequency = backtest_settings.backtest_rebalance_frequency
    backtest_enabled = backtest_settings.backtest_enabled
    backtest_signal_direction_raw = backtest_settings.backtest_signal_direction_raw

    rolling_windows_months = period_settings.rolling_windows_months

    logger.info("Time-series cross-validation (IC) ...")

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

    fit_state = _fit_model_and_score_train(
        train_df,
        feature_target=feature_target,
        model_settings=model_settings,
        signal_settings=signal_settings,
        cv_scores_raw=cv_scores_raw,
    )
    model = fit_state.model
    updated_signal_direction = fit_state.updated_signal_direction
    train_ic_raw_stats = fit_state.train_ic_raw_stats
    train_ic_series = fit_state.train_ic_series
    train_ic_stats = fit_state.train_ic_stats
    train_pearson_ic_series = fit_state.train_pearson_ic_series
    train_pearson_ic_stats = fit_state.train_pearson_ic_stats
    cv_scores_adj = fit_state.cv_scores_adj

    logger.info("Evaluating model on train/test sets ...")
    test_start = pd.to_datetime(test_dates[0])
    test_end = pd.to_datetime(test_dates[-1])
    test_df_full = df_full[
        (df_full["trade_date"] >= test_start) & (df_full["trade_date"] <= test_end)
    ].copy()
    if test_df_full.empty:
        raise SystemExit("Not enough test data after applying the split window.")

    live_state = _prepare_live_snapshot(
        df_features,
        model,
        context={
            "live_enabled": live_enabled,
            "live_as_of_token": live_as_of,
            "live_signal_asof_token": live_signal_asof,
            "live_entry_date_token": live_entry_date,
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

    period_eval_context = _build_period_eval_context(
        request,
        live_state=live_state,
        updated_signal_direction=updated_signal_direction,
        backtest_signal_direction=backtest_signal_direction,
    )

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

    (
        walk_forward_results,
        walk_forward_importance_df,
        walk_forward_feature_stability_df,
    ) = _run_walk_forward_evaluation(
        request,
        updated_signal_direction=updated_signal_direction,
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
        "live_signal_asof": live_state["live_signal_asof"],
        "live_entry_date": live_state["live_entry_date"],
        "live_execution_calendar": live_state["live_execution_calendar"],
        "live_execution_open": live_state["live_execution_open"],
        "live_execution_status": live_state["live_execution_status"],
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
        "execution_sim_summary": eval_main["execution_sim_summary"],
        "execution_sim_orders": eval_main["execution_sim_orders"],
        "execution_sim_fills": eval_main["execution_sim_fills"],
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
