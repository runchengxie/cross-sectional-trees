"""Pipeline runner for the HK + RQData workflow.
Usage:
    $ cstree run
    $ cstree run --config configs/presets/default.yml
    $ cstree run --config hk
    # rqdatac auth may be required (RQDATA_USERNAME/RQDATA_PASSWORD)
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from ..backtest import backtest_topk
from ..metrics import bucket_ic_summary
from .config import load_run_config
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
from .feature_dataset import _prepare_feature_dataset
from .final_oos_stage import run_final_oos_stage
from .output_orchestration import persist_pipeline_outputs
from .panel_loader import _load_research_panel
from .preflight import prepare_pipeline_setup, resolve_effective_data_inputs
from .quality import run_quality_preflight
from .runtime import _prepare_split_context
from .train_eval_stage import run_train_eval_stage

logger = logging.getLogger("cstree")

DEFAULT_SYMBOLS = [
    "00700.HK",
    "00005.HK",
    "00941.HK",
    "00001.HK",
    "00388.HK",
]


def _resolve_train_eval_service_hooks() -> tuple[Any, Any]:
    package_api = sys.modules.get(__package__)
    backtest_topk_fn = (
        getattr(package_api, "backtest_topk", backtest_topk)
        if package_api is not None
        else backtest_topk
    )
    bucket_ic_summary_fn = (
        getattr(package_api, "bucket_ic_summary", bucket_ic_summary)
        if package_api is not None
        else bucket_ic_summary
    )
    return backtest_topk_fn, bucket_ic_summary_fn


def _attach_benchmark_compare_frames(
    benchmark_compare_specs: list[dict[str, Any]],
    benchmark_compare_dfs: dict[str, pd.DataFrame],
) -> list[dict[str, Any]]:
    resolved_specs: list[dict[str, Any]] = []
    for spec in benchmark_compare_specs:
        resolved = dict(spec)
        if str(spec.get("source_type") or "") == "symbol":
            symbol = str(spec["symbol"]).strip()
            resolved["benchmark_df"] = benchmark_compare_dfs.get(symbol, pd.DataFrame())
            resolved["series"] = pd.Series(dtype=float, name="benchmark_return")
        resolved_specs.append(resolved)
    return resolved_specs


def _load_benchmark_return_series(path: Path) -> pd.Series:
    if not path.exists():
        raise SystemExit(f"Benchmark returns file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".parquet":
        frame = pd.read_parquet(path)
    else:
        frame = pd.read_csv(path)
    if frame is None or frame.empty:
        raise SystemExit(f"Benchmark returns file is empty: {path}")

    date_col = next(
        (
            candidate
            for candidate in ("trade_date", "date", "exit_date", "rebalance_date")
            if candidate in frame.columns
        ),
        None,
    )
    if date_col is None:
        raise SystemExit(
            "Benchmark returns file must include one of: trade_date, date, exit_date, rebalance_date."
        )

    value_col = next(
        (
            candidate
            for candidate in ("benchmark_return", "return", "net_return", "active_benchmark_return")
            if candidate in frame.columns
        ),
        None,
    )
    if value_col is None:
        raise SystemExit(
            "Benchmark returns file must include one of: benchmark_return, return, net_return."
        )

    work = frame[[date_col, value_col]].copy()
    raw_dates = work[date_col]
    date_strings = raw_dates.astype(str).str.strip()
    parsed_dates = pd.to_datetime(date_strings, format="%Y%m%d", errors="coerce")
    missing_dates = parsed_dates.isna()
    if missing_dates.any():
        parsed_dates.loc[missing_dates] = pd.to_datetime(
            date_strings.loc[missing_dates],
            errors="coerce",
        )
    work["trade_date"] = parsed_dates.dt.normalize()
    work["benchmark_return"] = pd.to_numeric(work[value_col], errors="coerce")
    work = work.dropna(subset=["trade_date", "benchmark_return"])
    if work.empty:
        raise SystemExit(f"Benchmark returns file has no valid rows: {path}")

    series = (
        work.sort_values("trade_date")
        .drop_duplicates(subset=["trade_date"], keep="last")
        .set_index("trade_date")["benchmark_return"]
        .astype(float)
    )
    series.name = "benchmark_return"
    return series


def prepare_research_context(
    config_ref: str | Path | None = None,
    *,
    fail_on_quality: str | None = None,
    artifacts_root: str | Path | None = None,
) -> dict[str, Any]:
    backtest_topk_fn, bucket_ic_summary_fn = _resolve_train_eval_service_hooks()
    loaded = load_run_config(
        config_ref,
        artifacts_root_override=artifacts_root,
    )
    data_cfg = loaded["data_cfg"]
    market = loaded["market"]
    artifacts_root_resolved = loaded["artifacts_root"]
    cache_dir = loaded["cache_dir"]
    setup = prepare_pipeline_setup(
        loaded=loaded,
        fail_on_quality=fail_on_quality,
        logger=logger,
        default_symbols=DEFAULT_SYMBOLS,
        quality_preflight_fn=run_quality_preflight,
    )
    data_interface = setup["data_interface"]
    provider = setup["provider"]
    universe_inputs = setup["universe_inputs"]
    date_label_settings = setup["date_label_settings"]
    eval_settings = setup["eval_settings"]
    universe_filters = setup["universe_filters"]
    industry_cfg = setup["industry_cfg"]
    runtime_settings = setup["runtime_settings"]
    run_artifacts = setup["run_artifacts"]
    quality_summary = setup["quality_summary"]

    data_inputs = resolve_effective_data_inputs(
        runtime_settings=runtime_settings,
        market=market,
        logger=logger,
        load_benchmark_return_series=_load_benchmark_return_series,
    )
    runtime_settings = data_inputs["runtime_settings"]
    fundamentals_cfg = runtime_settings["fundamentals_cfg"]
    provider_overlay_cfg = runtime_settings["provider_overlay_cfg"]
    execution_model = runtime_settings["execution_model"]
    execution_sim_config = runtime_settings["execution_sim_config"]
    benchmark_compare_specs = data_inputs["benchmark_compare_specs"]
    benchmark_compare_symbols = [
        str(spec["symbol"]).strip()
        for spec in benchmark_compare_specs
        if str(spec.get("source_type") or "") == "symbol" and spec.get("symbol")
    ]

    panel_state = _load_research_panel(
        data_interface=data_interface,
        symbols=universe_inputs["symbols"],
        market=market,
        start_date=date_label_settings["START_DATE"],
        end_date=date_label_settings["END_DATE"],
        execution_pricing_cols=runtime_settings["EXECUTION_PRICING_COLS"],
        price_col=date_label_settings["PRICE_COL"],
        benchmark_symbol=data_inputs["benchmark_symbol"],
        benchmark_compare_symbols=benchmark_compare_symbols,
        drop_st=universe_filters["DROP_ST"],
        min_listed_days=universe_filters["MIN_LISTED_DAYS"],
        drop_suspended=universe_filters["DROP_SUSPENDED"],
        suspended_policy=universe_filters["SUSPENDED_POLICY"],
        min_turnover=universe_filters["MIN_TURNOVER"],
        fundamentals_enabled=runtime_settings["FUNDAMENTALS_ENABLED"],
        fundamentals_source=runtime_settings["FUNDAMENTALS_SOURCE"],
        fundamentals_file_path=data_inputs["fundamentals_file_path"],
        data_cfg=data_cfg,
        fundamentals_cfg=fundamentals_cfg,
        requested_features=runtime_settings["FEATURES"],
        fundamentals_ffill=runtime_settings["FUNDAMENTALS_FFILL"],
        fundamentals_ffill_limit=runtime_settings["FUNDAMENTALS_FFILL_LIMIT"],
        fundamentals_log_mcap=runtime_settings["FUNDAMENTALS_LOG_MCAP"],
        fundamentals_mcap_col=runtime_settings["FUNDAMENTALS_MCAP_COL"],
        fundamentals_log_mcap_col=runtime_settings["FUNDAMENTALS_LOG_MCAP_COL"],
        fundamentals_auto_add=runtime_settings["FUNDAMENTALS_AUTO_ADD"],
        provider_overlay_enabled=runtime_settings["FUNDAMENTALS_PROVIDER_OVERLAY_ENABLED"],
        provider_overlay_cfg=provider_overlay_cfg,
        provider_overlay_auto_add=runtime_settings["FUNDAMENTALS_PROVIDER_OVERLAY_AUTO_ADD"],
        provider_overlay_features=runtime_settings["FUNDAMENTALS_PROVIDER_OVERLAY_FEATURES"],
        industry_enabled=runtime_settings["INDUSTRY_ENABLED"],
        industry_file_path=data_inputs["industry_file_path"],
        industry_cfg=industry_cfg,
        industry_keep_columns=runtime_settings["INDUSTRY_KEEP_COLUMNS"],
        industry_ffill=runtime_settings["INDUSTRY_FFILL"],
        industry_ffill_limit=runtime_settings["INDUSTRY_FFILL_LIMIT"],
        label_horizon_mode=date_label_settings["LABEL_HORIZON_MODE"],
        label_rebalance_frequency=date_label_settings["LABEL_REBALANCE_FREQUENCY"],
    )
    features = panel_state["features"]
    label_horizon_mode = panel_state["label_horizon_mode"]
    backtest_group_col = runtime_settings["BACKTEST_GROUP_COL"]

    dataset_state = _prepare_feature_dataset(
        df=panel_state["df"],
        features=features,
        feature_params=runtime_settings["feature_params"],
        price_col=date_label_settings["PRICE_COL"],
        target=date_label_settings["TARGET"],
        label_shift_days=date_label_settings["LABEL_SHIFT_DAYS"],
        label_horizon_days=date_label_settings["LABEL_HORIZON_DAYS"],
        label_horizon_mode=label_horizon_mode,
        label_next_rebalance_map=panel_state["label_next_rebalance_map"],
        fundamentals_allow_missing=runtime_settings["FUNDAMENTALS_ALLOW_MISSING"],
        bucket_ic_enabled=eval_settings["BUCKET_IC_ENABLED"],
        bucket_ic_schemes=eval_settings["BUCKET_IC_SCHEMES"],
        feature_missing_features=runtime_settings["FEATURE_MISSING_FEATURES"],
        feature_missing_method=runtime_settings["FEATURE_MISSING_METHOD"],
        feature_missing_add_indicators=runtime_settings["FEATURE_MISSING_ADD_INDICATORS"],
        feature_missing_suffix=runtime_settings["FEATURE_MISSING_SUFFIX"],
        industry_cols=panel_state["industry_cols"],
        execution_pricing_cols=runtime_settings["EXECUTION_PRICING_COLS"],
        backtest_tradable_col=runtime_settings["BACKTEST_TRADABLE_COL"],
        universe_by_date=universe_inputs["universe_by_date"],
        winsorize_pct=date_label_settings["WINSORIZE_PCT"],
        cs_method=runtime_settings["CS_METHOD"],
        cs_winsorize_pct=runtime_settings["CS_WINSORIZE_PCT"],
        train_target=date_label_settings["TRAIN_TARGET"],
        train_target_transform=date_label_settings["TRAIN_TARGET_TRANSFORM"],
        sample_on_rebalance_dates=eval_settings["SAMPLE_ON_REBALANCE_DATES"],
        rebalance_frequency=eval_settings["REBALANCE_FREQUENCY"],
        min_symbols_per_date=universe_filters["MIN_SYMBOLS_PER_DATE"],
    )
    features = dataset_state["features"]
    if backtest_group_col and backtest_group_col not in dataset_state["df_full"].columns:
        logger.warning(
            "backtest.group_col=%s not found in dataset; industry/group constraint disabled.",
            backtest_group_col,
        )
        backtest_group_col = None

    final_oos_size_raw = eval_settings["FINAL_OOS_SIZE_RAW"]
    if eval_settings["FINAL_OOS_ENABLED"] and final_oos_size_raw is None:
        final_oos_size_raw = eval_settings["TEST_SIZE"]
        logger.info(
            "final_oos.enabled=true but size not set; using eval.test_size=%s.",
            eval_settings["TEST_SIZE"],
        )
    split_state = _prepare_split_context(
        df_model_all_sorted=dataset_state["df_model_all_sorted"],
        all_dates_model_full=dataset_state["all_dates_model_full"],
        model_date_start_rows=dataset_state["model_date_start_rows"],
        model_date_end_rows=dataset_state["model_date_end_rows"],
        model_date_to_pos=dataset_state["model_date_to_pos"],
        reference_trade_dates=dataset_state["reference_trade_dates"],
        sample_on_rebalance_dates=eval_settings["SAMPLE_ON_REBALANCE_DATES"],
        df_model_all=dataset_state["df_model_all"],
        all_dates_full=dataset_state["all_dates_full"],
        label_horizon_days=date_label_settings["LABEL_HORIZON_DAYS"],
        label_horizon_mode=label_horizon_mode,
        label_horizon_gap=panel_state["label_horizon_gap"],
        label_shift_days=date_label_settings["LABEL_SHIFT_DAYS"],
        purge_days_cfg=eval_settings["PURGE_DAYS_CFG"],
        embargo_days_cfg=eval_settings["EMBARGO_DAYS_CFG"],
        test_size=eval_settings["TEST_SIZE"],
        final_oos_enabled=eval_settings["FINAL_OOS_ENABLED"],
        final_oos_size_raw=final_oos_size_raw,
        train_window_mode=runtime_settings["TRAIN_WINDOW_MODE"],
        train_window_size=runtime_settings["TRAIN_WINDOW_SIZE"],
        train_window_unit=runtime_settings["TRAIN_WINDOW_UNIT"],
    )

    train_eval_request = TrainEvalRequest(
        data=TrainEvalData(
            train_df=split_state["train_df"],
            test_df=split_state["test_df"],
            test_dates=split_state["test_dates"],
            df_features=dataset_state["df_features"],
            df_full=dataset_state["df_full"],
            df_model_sorted=split_state["df_model_sorted"],
            all_dates=split_state["all_dates"],
            all_date_start_rows=split_state["all_date_start_rows"],
            all_date_end_rows=split_state["all_date_end_rows"],
            all_date_to_pos=split_state["all_date_to_pos"],
            valid_dates_set=dataset_state["valid_dates_set"],
            backtest_pricing_df=dataset_state["backtest_pricing_df"],
            benchmark_df=panel_state["benchmark_df"],
            benchmark_return_series=data_inputs["benchmark_return_series"],
            industry_source_df=panel_state["industry_source_df"],
            passthrough_cols=dataset_state["passthrough_cols"],
            industry_keep_columns=runtime_settings["INDUSTRY_KEEP_COLUMNS"],
            price_passthrough_cols=dataset_state["price_passthrough_cols"],
            bucket_cols=dataset_state["bucket_cols"],
        ),
        feature_target=TrainEvalFeatureTarget(
            features=features,
            target=date_label_settings["TARGET"],
            train_target=date_label_settings["TRAIN_TARGET"],
            price_col=date_label_settings["PRICE_COL"],
            fundamentals_mcap_col=runtime_settings["FUNDAMENTALS_MCAP_COL"],
        ),
        model=TrainEvalModelSettings(
            model_type=runtime_settings["MODEL_TYPE"],
            model_params=runtime_settings["MODEL_PARAMS"],
            model_cfg=runtime_settings["MODEL_CFG"],
            sample_weight_mode=runtime_settings["SAMPLE_WEIGHT_MODE"],
            sample_weight_params=runtime_settings["SAMPLE_WEIGHT_PARAMS"],
            n_splits=eval_settings["N_SPLITS"],
            embargo_steps=split_state["embargo_steps"],
            purge_steps=split_state["purge_steps"],
            train_window_mode=runtime_settings["TRAIN_WINDOW_MODE"],
            train_window_size=runtime_settings["TRAIN_WINDOW_SIZE"],
            train_window_unit=runtime_settings["TRAIN_WINDOW_UNIT"],
        ),
        signal=TrainEvalSignalSettings(
            signal_direction_mode=eval_settings["SIGNAL_DIRECTION_MODE"],
            signal_direction=eval_settings["SIGNAL_DIRECTION"],
            min_abs_ic_to_flip=eval_settings["MIN_ABS_IC_TO_FLIP"],
            score_postprocess_method=eval_settings["SCORE_POSTPROCESS_METHOD"],
            score_postprocess_columns=eval_settings["SCORE_POSTPROCESS_COLUMNS"],
            score_postprocess_strength=eval_settings["SCORE_POSTPROCESS_STRENGTH"],
            score_postprocess_min_obs=eval_settings["SCORE_POSTPROCESS_MIN_OBS"],
            report_train_ic=eval_settings["REPORT_TRAIN_IC"],
        ),
        live=TrainEvalLiveSettings(
            live_enabled=runtime_settings["LIVE_ENABLED"],
            live_as_of=runtime_settings["LIVE_AS_OF"],
            market=market,
            provider=provider,
            live_train_mode=runtime_settings["LIVE_TRAIN_MODE"],
            min_symbols_per_date=universe_filters["MIN_SYMBOLS_PER_DATE"],
        ),
        backtest=TrainEvalBacktestSettings(
            backtest_top_k=runtime_settings["BACKTEST_TOP_K"],
            label_shift_days=date_label_settings["LABEL_SHIFT_DAYS"],
            backtest_weighting=runtime_settings["BACKTEST_WEIGHTING"],
            backtest_buffer_exit=runtime_settings["BACKTEST_BUFFER_EXIT"],
            backtest_buffer_entry=runtime_settings["BACKTEST_BUFFER_ENTRY"],
            backtest_long_only=runtime_settings["BACKTEST_LONG_ONLY"],
            backtest_short_k=runtime_settings["BACKTEST_SHORT_K"],
            backtest_tradable_col=runtime_settings["BACKTEST_TRADABLE_COL"],
            backtest_group_col=backtest_group_col,
            backtest_max_names_per_group=runtime_settings["BACKTEST_MAX_NAMES_PER_GROUP"],
            execution_model=execution_model,
            execution_sim_config=execution_sim_config,
            backtest_rebalance_frequency=runtime_settings["BACKTEST_REBALANCE_FREQUENCY"],
            backtest_enabled=runtime_settings["BACKTEST_ENABLED"],
            backtest_signal_direction_raw=runtime_settings["BACKTEST_SIGNAL_DIRECTION_RAW"],
            backtest_cost_bps_effective=runtime_settings["BACKTEST_COST_BPS_EFFECTIVE"],
            backtest_trading_days_per_year=runtime_settings["BACKTEST_TRADING_DAYS_PER_YEAR"],
            backtest_exit_mode=runtime_settings["BACKTEST_EXIT_MODE"],
            backtest_exit_horizon_days=runtime_settings["BACKTEST_EXIT_HORIZON_DAYS"],
            backtest_exit_price_policy=runtime_settings["BACKTEST_EXIT_PRICE_POLICY"],
            backtest_exit_fallback_policy=runtime_settings["BACKTEST_EXIT_FALLBACK_POLICY"],
        ),
        period=TrainEvalPeriodSettings(
            rebalance_frequency=eval_settings["REBALANCE_FREQUENCY"],
            sample_on_rebalance_dates=eval_settings["SAMPLE_ON_REBALANCE_DATES"],
            perm_test_runs=eval_settings["PERM_TEST_RUNS"],
            perm_test_seed=eval_settings["PERM_TEST_SEED"],
            label_horizon_mode=label_horizon_mode,
            label_horizon_effective=split_state["label_horizon_effective"],
            n_quantiles=eval_settings["N_QUANTILES"],
            top_k=eval_settings["TOP_K"],
            eval_buffer_exit=eval_settings["EVAL_BUFFER_EXIT"],
            eval_buffer_entry=eval_settings["EVAL_BUFFER_ENTRY"],
            transaction_cost_bps=eval_settings["TRANSACTION_COST_BPS"],
            bucket_ic_enabled=eval_settings["BUCKET_IC_ENABLED"],
            bucket_ic_schemes=eval_settings["BUCKET_IC_SCHEMES"],
            bucket_ic_method=eval_settings["BUCKET_IC_METHOD"],
            bucket_ic_min_count=eval_settings["BUCKET_IC_MIN_COUNT"],
            rolling_windows_months=eval_settings["ROLLING_WINDOWS_MONTHS"],
        ),
        walk_forward=TrainEvalWalkForwardSettings(
            wf_enabled=eval_settings["WF_ENABLED"],
            wf_n_windows=eval_settings["WF_N_WINDOWS"],
            wf_test_size=eval_settings["WF_TEST_SIZE"]
            if eval_settings["WF_TEST_SIZE"] is not None
            else eval_settings["TEST_SIZE"],
            wf_step_size=eval_settings["WF_STEP_SIZE"],
            effective_gap_steps=split_state["effective_gap_steps"],
            wf_anchor_end=eval_settings["WF_ANCHOR_END"],
            wf_feature_top_k=eval_settings["WF_FEATURE_TOP_K"],
            wf_backtest_enabled=eval_settings["WF_BACKTEST_ENABLED"],
            wf_perm_test_enabled=eval_settings["WF_PERM_TEST_ENABLED"],
            wf_perm_test_runs=eval_settings["WF_PERM_TEST_RUNS"],
            wf_perm_test_seed=eval_settings["WF_PERM_TEST_SEED"],
        ),
        services=TrainEvalServices(
            backtest_topk_fn=backtest_topk_fn,
            bucket_ic_summary_fn=bucket_ic_summary_fn,
        ),
    )

    return {
        "loaded": loaded,
        "data_cfg": data_cfg,
        "market": market,
        "artifacts_root": artifacts_root_resolved,
        "cache_dir": cache_dir,
        "provider": provider,
        "universe_inputs": universe_inputs,
        "date_label_settings": {**date_label_settings, "LABEL_HORIZON_MODE": label_horizon_mode},
        "eval_settings": {**eval_settings, "FINAL_OOS_SIZE_RAW": final_oos_size_raw},
        "universe_filters": universe_filters,
        "runtime_settings": runtime_settings,
        "run_artifacts": run_artifacts,
        "quality_summary": quality_summary,
        "data_inputs": data_inputs,
        "panel_state": panel_state,
        "dataset_state": dataset_state,
        "split_state": split_state,
        "benchmark_compare_specs": benchmark_compare_specs,
        "benchmark_compare_dfs": panel_state["benchmark_compare_dfs"],
        "backtest_group_col": backtest_group_col,
        "train_eval_request": train_eval_request,
    }


def _run_legacy(
    config_ref: str | Path | None = None,
    *,
    fail_on_quality: str | None = None,
    artifacts_root: str | Path | None = None,
) -> None:
    backtest_topk_fn, bucket_ic_summary_fn = _resolve_train_eval_service_hooks()
    loaded = load_run_config(
        config_ref,
        artifacts_root_override=artifacts_root,
    )
    data_cfg = loaded["data_cfg"]
    MARKET = loaded["market"]
    ARTIFACTS_ROOT = loaded["artifacts_root"]
    CACHE_DIR = loaded["cache_dir"]
    setup = prepare_pipeline_setup(
        loaded=loaded,
        fail_on_quality=fail_on_quality,
        logger=logger,
        default_symbols=DEFAULT_SYMBOLS,
        quality_preflight_fn=run_quality_preflight,
    )
    data_interface = setup["data_interface"]
    provider = setup["provider"]
    universe_inputs = setup["universe_inputs"]
    date_label_settings = setup["date_label_settings"]
    eval_settings = setup["eval_settings"]
    universe_filters = setup["universe_filters"]
    industry_cfg = setup["industry_cfg"]
    runtime_settings = setup["runtime_settings"]
    run_artifacts = setup["run_artifacts"]
    quality_summary = setup["quality_summary"]

    symbols = universe_inputs["symbols"]
    universe_by_date = universe_inputs["universe_by_date"]

    START_DATE = date_label_settings["START_DATE"]
    END_DATE = date_label_settings["END_DATE"]
    PRICE_COL = date_label_settings["PRICE_COL"]
    LABEL_HORIZON_DAYS = date_label_settings["LABEL_HORIZON_DAYS"]
    LABEL_SHIFT_DAYS = date_label_settings["LABEL_SHIFT_DAYS"]
    LABEL_HORIZON_MODE = date_label_settings["LABEL_HORIZON_MODE"]
    LABEL_REBALANCE_FREQUENCY = date_label_settings["LABEL_REBALANCE_FREQUENCY"]
    TARGET = date_label_settings["TARGET"]
    TRAIN_TARGET_TRANSFORM = date_label_settings["TRAIN_TARGET_TRANSFORM"]
    TRAIN_TARGET = date_label_settings["TRAIN_TARGET"]
    WINSORIZE_PCT = date_label_settings["WINSORIZE_PCT"]

    TEST_SIZE = eval_settings["TEST_SIZE"]
    N_SPLITS = eval_settings["N_SPLITS"]
    N_QUANTILES = eval_settings["N_QUANTILES"]
    TOP_K = eval_settings["TOP_K"]
    REBALANCE_FREQUENCY = eval_settings["REBALANCE_FREQUENCY"]
    TRANSACTION_COST_BPS = eval_settings["TRANSACTION_COST_BPS"]
    EVAL_BUFFER_EXIT = eval_settings["EVAL_BUFFER_EXIT"]
    EVAL_BUFFER_ENTRY = eval_settings["EVAL_BUFFER_ENTRY"]
    SIGNAL_DIRECTION_MODE = eval_settings["SIGNAL_DIRECTION_MODE"]
    SIGNAL_DIRECTION = eval_settings["SIGNAL_DIRECTION"]
    MIN_ABS_IC_TO_FLIP = eval_settings["MIN_ABS_IC_TO_FLIP"]
    EMBARGO_DAYS_CFG = eval_settings["EMBARGO_DAYS_CFG"]
    PURGE_DAYS_CFG = eval_settings["PURGE_DAYS_CFG"]
    PURGE_STEPS = eval_settings["PURGE_STEPS"]
    EMBARGO_STEPS = eval_settings["EMBARGO_STEPS"]
    EFFECTIVE_GAP_STEPS = eval_settings["EFFECTIVE_GAP_STEPS"]
    REPORT_TRAIN_IC = eval_settings["REPORT_TRAIN_IC"]
    SAMPLE_ON_REBALANCE_DATES = eval_settings["SAMPLE_ON_REBALANCE_DATES"]
    SCORE_POSTPROCESS_METHOD = eval_settings["SCORE_POSTPROCESS_METHOD"]
    SCORE_POSTPROCESS_COLUMNS = eval_settings["SCORE_POSTPROCESS_COLUMNS"]
    SCORE_POSTPROCESS_STRENGTH = eval_settings["SCORE_POSTPROCESS_STRENGTH"]
    SCORE_POSTPROCESS_MIN_OBS = eval_settings["SCORE_POSTPROCESS_MIN_OBS"]
    ROLLING_WINDOWS_MONTHS = eval_settings["ROLLING_WINDOWS_MONTHS"]
    BUCKET_IC_ENABLED = eval_settings["BUCKET_IC_ENABLED"]
    BUCKET_IC_METHOD = eval_settings["BUCKET_IC_METHOD"]
    BUCKET_IC_MIN_COUNT = eval_settings["BUCKET_IC_MIN_COUNT"]
    BUCKET_IC_SCHEMES = eval_settings["BUCKET_IC_SCHEMES"]
    PERM_TEST_RUNS = eval_settings["PERM_TEST_RUNS"]
    PERM_TEST_SEED = eval_settings["PERM_TEST_SEED"]
    WF_ENABLED = eval_settings["WF_ENABLED"]
    WF_N_WINDOWS = eval_settings["WF_N_WINDOWS"]
    WF_TEST_SIZE = eval_settings["WF_TEST_SIZE"]
    WF_STEP_SIZE = eval_settings["WF_STEP_SIZE"]
    WF_ANCHOR_END = eval_settings["WF_ANCHOR_END"]
    WF_FEATURE_TOP_K = eval_settings["WF_FEATURE_TOP_K"]
    WF_BACKTEST_ENABLED = eval_settings["WF_BACKTEST_ENABLED"]
    WF_PERM_TEST_ENABLED = eval_settings["WF_PERM_TEST_ENABLED"]
    WF_PERM_TEST_RUNS = eval_settings["WF_PERM_TEST_RUNS"]
    WF_PERM_TEST_SEED = eval_settings["WF_PERM_TEST_SEED"]
    FINAL_OOS_ENABLED = eval_settings["FINAL_OOS_ENABLED"]
    FINAL_OOS_SIZE_RAW = eval_settings["FINAL_OOS_SIZE_RAW"]
    MIN_SYMBOLS_PER_DATE = universe_filters["MIN_SYMBOLS_PER_DATE"]
    MIN_LISTED_DAYS = universe_filters["MIN_LISTED_DAYS"]
    MIN_TURNOVER = universe_filters["MIN_TURNOVER"]
    DROP_ST = universe_filters["DROP_ST"]
    DROP_SUSPENDED = universe_filters["DROP_SUSPENDED"]
    SUSPENDED_POLICY = universe_filters["SUSPENDED_POLICY"]
    data_inputs = resolve_effective_data_inputs(
        runtime_settings=runtime_settings,
        market=MARKET,
        logger=logger,
        load_benchmark_return_series=_load_benchmark_return_series,
    )
    runtime_settings = data_inputs["runtime_settings"]
    fundamentals_cfg = runtime_settings["fundamentals_cfg"]
    provider_overlay_cfg = runtime_settings["provider_overlay_cfg"]
    FUNDAMENTALS_ENABLED = runtime_settings["FUNDAMENTALS_ENABLED"]
    FUNDAMENTALS_SOURCE = runtime_settings["FUNDAMENTALS_SOURCE"]
    FUNDAMENTALS_AUTO_ADD = runtime_settings["FUNDAMENTALS_AUTO_ADD"]
    FUNDAMENTALS_ALLOW_MISSING = runtime_settings["FUNDAMENTALS_ALLOW_MISSING"]
    FUNDAMENTALS_FFILL = runtime_settings["FUNDAMENTALS_FFILL"]
    FUNDAMENTALS_FFILL_LIMIT = runtime_settings["FUNDAMENTALS_FFILL_LIMIT"]
    FUNDAMENTALS_LOG_MCAP = runtime_settings["FUNDAMENTALS_LOG_MCAP"]
    FUNDAMENTALS_MCAP_COL = runtime_settings["FUNDAMENTALS_MCAP_COL"]
    FUNDAMENTALS_LOG_MCAP_COL = runtime_settings["FUNDAMENTALS_LOG_MCAP_COL"]
    FUNDAMENTALS_PROVIDER_OVERLAY_ENABLED = runtime_settings[
        "FUNDAMENTALS_PROVIDER_OVERLAY_ENABLED"
    ]
    FUNDAMENTALS_PROVIDER_OVERLAY_FEATURES = runtime_settings[
        "FUNDAMENTALS_PROVIDER_OVERLAY_FEATURES"
    ]
    FUNDAMENTALS_PROVIDER_OVERLAY_AUTO_ADD = runtime_settings[
        "FUNDAMENTALS_PROVIDER_OVERLAY_AUTO_ADD"
    ]
    INDUSTRY_ENABLED = runtime_settings["INDUSTRY_ENABLED"]
    INDUSTRY_KEEP_COLUMNS = runtime_settings["INDUSTRY_KEEP_COLUMNS"]
    INDUSTRY_FFILL = runtime_settings["INDUSTRY_FFILL"]
    INDUSTRY_FFILL_LIMIT = runtime_settings["INDUSTRY_FFILL_LIMIT"]
    FEATURES = runtime_settings["FEATURES"]
    feature_params = runtime_settings["feature_params"]
    CS_METHOD = runtime_settings["CS_METHOD"]
    CS_WINSORIZE_PCT = runtime_settings["CS_WINSORIZE_PCT"]
    FEATURE_MISSING_METHOD = runtime_settings["FEATURE_MISSING_METHOD"]
    FEATURE_MISSING_FEATURES = runtime_settings["FEATURE_MISSING_FEATURES"]
    FEATURE_MISSING_ADD_INDICATORS = runtime_settings["FEATURE_MISSING_ADD_INDICATORS"]
    FEATURE_MISSING_SUFFIX = runtime_settings["FEATURE_MISSING_SUFFIX"]
    MODEL_TYPE = runtime_settings["MODEL_TYPE"]
    MODEL_PARAMS = runtime_settings["MODEL_PARAMS"]
    MODEL_CFG = runtime_settings["MODEL_CFG"]
    SAMPLE_WEIGHT_MODE = runtime_settings["SAMPLE_WEIGHT_MODE"]
    SAMPLE_WEIGHT_PARAMS = runtime_settings["SAMPLE_WEIGHT_PARAMS"]
    TRAIN_WINDOW_MODE = runtime_settings["TRAIN_WINDOW_MODE"]
    TRAIN_WINDOW_SIZE = runtime_settings["TRAIN_WINDOW_SIZE"]
    TRAIN_WINDOW_UNIT = runtime_settings["TRAIN_WINDOW_UNIT"]
    BACKTEST_ENABLED = runtime_settings["BACKTEST_ENABLED"]
    BACKTEST_TOP_K = runtime_settings["BACKTEST_TOP_K"]
    BACKTEST_REBALANCE_FREQUENCY = runtime_settings["BACKTEST_REBALANCE_FREQUENCY"]
    BACKTEST_TRADING_DAYS_PER_YEAR = runtime_settings["BACKTEST_TRADING_DAYS_PER_YEAR"]
    BACKTEST_LONG_ONLY = runtime_settings["BACKTEST_LONG_ONLY"]
    BACKTEST_BUFFER_EXIT = runtime_settings["BACKTEST_BUFFER_EXIT"]
    BACKTEST_BUFFER_ENTRY = runtime_settings["BACKTEST_BUFFER_ENTRY"]
    BACKTEST_WEIGHTING = runtime_settings["BACKTEST_WEIGHTING"]
    BACKTEST_GROUP_COL = runtime_settings["BACKTEST_GROUP_COL"]
    BACKTEST_MAX_NAMES_PER_GROUP = runtime_settings["BACKTEST_MAX_NAMES_PER_GROUP"]
    BACKTEST_SIGNAL_DIRECTION_RAW = runtime_settings["BACKTEST_SIGNAL_DIRECTION_RAW"]
    BACKTEST_SHORT_K = runtime_settings["BACKTEST_SHORT_K"]
    BACKTEST_EXIT_MODE = runtime_settings["BACKTEST_EXIT_MODE"]
    BACKTEST_EXIT_HORIZON_DAYS = runtime_settings["BACKTEST_EXIT_HORIZON_DAYS"]
    BACKTEST_EXIT_PRICE_POLICY = runtime_settings["BACKTEST_EXIT_PRICE_POLICY"]
    BACKTEST_EXIT_FALLBACK_POLICY = runtime_settings["BACKTEST_EXIT_FALLBACK_POLICY"]
    execution_model = runtime_settings["execution_model"]
    execution_sim_config = runtime_settings["execution_sim_config"]
    EXECUTION_PRICING_COLS = runtime_settings["EXECUTION_PRICING_COLS"]
    BACKTEST_COST_BPS_EFFECTIVE = runtime_settings["BACKTEST_COST_BPS_EFFECTIVE"]
    BACKTEST_TRADABLE_COL = runtime_settings["BACKTEST_TRADABLE_COL"]
    LIVE_ENABLED = runtime_settings["LIVE_ENABLED"]
    LIVE_AS_OF = runtime_settings["LIVE_AS_OF"]
    LIVE_TRAIN_MODE = runtime_settings["LIVE_TRAIN_MODE"]
    fundamentals_file_path = data_inputs["fundamentals_file_path"]
    industry_file_path = data_inputs["industry_file_path"]
    benchmark_symbol = data_inputs["benchmark_symbol"]
    benchmark_returns_file_path = data_inputs["benchmark_returns_file_path"]
    benchmark_return_series = data_inputs["benchmark_return_series"]
    benchmark_compare_specs = data_inputs["benchmark_compare_specs"]
    benchmark_compare_symbols = [
        str(spec["symbol"]).strip()
        for spec in benchmark_compare_specs
        if str(spec.get("source_type") or "") == "symbol" and spec.get("symbol")
    ]
    panel_state = _load_research_panel(
        data_interface=data_interface,
        symbols=symbols,
        market=MARKET,
        start_date=START_DATE,
        end_date=END_DATE,
        execution_pricing_cols=EXECUTION_PRICING_COLS,
        price_col=PRICE_COL,
        benchmark_symbol=benchmark_symbol,
        benchmark_compare_symbols=benchmark_compare_symbols,
        drop_st=DROP_ST,
        min_listed_days=MIN_LISTED_DAYS,
        drop_suspended=DROP_SUSPENDED,
        suspended_policy=SUSPENDED_POLICY,
        min_turnover=MIN_TURNOVER,
        fundamentals_enabled=FUNDAMENTALS_ENABLED,
        fundamentals_source=FUNDAMENTALS_SOURCE,
        fundamentals_file_path=fundamentals_file_path,
        data_cfg=data_cfg,
        fundamentals_cfg=fundamentals_cfg,
        requested_features=FEATURES,
        fundamentals_ffill=FUNDAMENTALS_FFILL,
        fundamentals_ffill_limit=FUNDAMENTALS_FFILL_LIMIT,
        fundamentals_log_mcap=FUNDAMENTALS_LOG_MCAP,
        fundamentals_mcap_col=FUNDAMENTALS_MCAP_COL,
        fundamentals_log_mcap_col=FUNDAMENTALS_LOG_MCAP_COL,
        fundamentals_auto_add=FUNDAMENTALS_AUTO_ADD,
        provider_overlay_enabled=FUNDAMENTALS_PROVIDER_OVERLAY_ENABLED,
        provider_overlay_cfg=provider_overlay_cfg,
        provider_overlay_auto_add=FUNDAMENTALS_PROVIDER_OVERLAY_AUTO_ADD,
        provider_overlay_features=FUNDAMENTALS_PROVIDER_OVERLAY_FEATURES,
        industry_enabled=INDUSTRY_ENABLED,
        industry_file_path=industry_file_path,
        industry_cfg=industry_cfg,
        industry_keep_columns=INDUSTRY_KEEP_COLUMNS,
        industry_ffill=INDUSTRY_FFILL,
        industry_ffill_limit=INDUSTRY_FFILL_LIMIT,
        label_horizon_mode=LABEL_HORIZON_MODE,
        label_rebalance_frequency=LABEL_REBALANCE_FREQUENCY,
    )
    df = panel_state["df"]
    benchmark_df = panel_state["benchmark_df"]
    benchmark_compare_dfs = panel_state["benchmark_compare_dfs"]
    industry_cols = panel_state["industry_cols"]
    industry_source_df = panel_state["industry_source_df"]
    FEATURES = panel_state["features"]
    LABEL_HORIZON_MODE = panel_state["label_horizon_mode"]
    label_next_rebalance_map = panel_state["label_next_rebalance_map"]
    label_horizon_gap = panel_state["label_horizon_gap"]

    # -----------------------------------------------------------------------------
    # 3. Feature engineering (per symbol) + label
    # -----------------------------------------------------------------------------
    dataset_state = _prepare_feature_dataset(
        df=df,
        features=FEATURES,
        feature_params=feature_params,
        price_col=PRICE_COL,
        target=TARGET,
        label_shift_days=LABEL_SHIFT_DAYS,
        label_horizon_days=LABEL_HORIZON_DAYS,
        label_horizon_mode=LABEL_HORIZON_MODE,
        label_next_rebalance_map=label_next_rebalance_map,
        fundamentals_allow_missing=FUNDAMENTALS_ALLOW_MISSING,
        bucket_ic_enabled=BUCKET_IC_ENABLED,
        bucket_ic_schemes=BUCKET_IC_SCHEMES,
        feature_missing_features=FEATURE_MISSING_FEATURES,
        feature_missing_method=FEATURE_MISSING_METHOD,
        feature_missing_add_indicators=FEATURE_MISSING_ADD_INDICATORS,
        feature_missing_suffix=FEATURE_MISSING_SUFFIX,
        industry_cols=industry_cols,
        execution_pricing_cols=EXECUTION_PRICING_COLS,
        backtest_tradable_col=BACKTEST_TRADABLE_COL,
        universe_by_date=universe_by_date,
        winsorize_pct=WINSORIZE_PCT,
        cs_method=CS_METHOD,
        cs_winsorize_pct=CS_WINSORIZE_PCT,
        train_target=TRAIN_TARGET,
        train_target_transform=TRAIN_TARGET_TRANSFORM,
        sample_on_rebalance_dates=SAMPLE_ON_REBALANCE_DATES,
        rebalance_frequency=REBALANCE_FREQUENCY,
        min_symbols_per_date=MIN_SYMBOLS_PER_DATE,
    )
    FEATURES = dataset_state["features"]
    df_features = dataset_state["df_features"]
    df_full = dataset_state["df_full"]
    reference_trade_dates = dataset_state["reference_trade_dates"]
    all_dates_full = dataset_state["all_dates_full"]
    df_model_all = dataset_state["df_model_all"]
    df_model_all_sorted = dataset_state["df_model_all_sorted"]
    all_dates_model_full = dataset_state["all_dates_model_full"]
    model_date_start_rows = dataset_state["model_date_start_rows"]
    model_date_end_rows = dataset_state["model_date_end_rows"]
    model_date_to_pos = dataset_state["model_date_to_pos"]
    valid_dates_set = dataset_state["valid_dates_set"]
    backtest_pricing_df = dataset_state["backtest_pricing_df"]
    bucket_cols = dataset_state["bucket_cols"]
    passthrough_cols = dataset_state["passthrough_cols"]
    price_passthrough_cols = dataset_state["price_passthrough_cols"]
    if BACKTEST_GROUP_COL and BACKTEST_GROUP_COL not in df_full.columns:
        logger.warning(
            "backtest.group_col=%s not found in dataset; industry/group constraint disabled.",
            BACKTEST_GROUP_COL,
        )
        BACKTEST_GROUP_COL = None

    # -----------------------------------------------------------------------------
    # 4. Train-test split (time-series by date)
    # -----------------------------------------------------------------------------
    if FINAL_OOS_ENABLED and FINAL_OOS_SIZE_RAW is None:
        FINAL_OOS_SIZE_RAW = TEST_SIZE
        logger.info(
            "final_oos.enabled=true but size not set; using eval.test_size=%s.",
            TEST_SIZE,
        )
    split_state = _prepare_split_context(
        df_model_all_sorted=df_model_all_sorted,
        all_dates_model_full=all_dates_model_full,
        model_date_start_rows=model_date_start_rows,
        model_date_end_rows=model_date_end_rows,
        model_date_to_pos=model_date_to_pos,
        reference_trade_dates=reference_trade_dates,
        sample_on_rebalance_dates=SAMPLE_ON_REBALANCE_DATES,
        df_model_all=df_model_all,
        all_dates_full=all_dates_full,
        label_horizon_days=LABEL_HORIZON_DAYS,
        label_horizon_mode=LABEL_HORIZON_MODE,
        label_horizon_gap=label_horizon_gap,
        label_shift_days=LABEL_SHIFT_DAYS,
        purge_days_cfg=PURGE_DAYS_CFG,
        embargo_days_cfg=EMBARGO_DAYS_CFG,
        test_size=TEST_SIZE,
        final_oos_enabled=FINAL_OOS_ENABLED,
        final_oos_size_raw=FINAL_OOS_SIZE_RAW,
        train_window_mode=TRAIN_WINDOW_MODE,
        train_window_size=TRAIN_WINDOW_SIZE,
        train_window_unit=TRAIN_WINDOW_UNIT,
    )
    FINAL_OOS_ENABLED = split_state["final_oos_enabled"]
    final_oos_dates = split_state["final_oos_dates"]
    label_horizon_effective = split_state["label_horizon_effective"]
    PURGE_STEPS = split_state["purge_steps"]
    EMBARGO_STEPS = split_state["embargo_steps"]
    EFFECTIVE_GAP_STEPS = split_state["effective_gap_steps"]
    df_model_sorted = split_state["df_model_sorted"]
    all_dates = split_state["all_dates"]
    all_date_start_rows = split_state["all_date_start_rows"]
    all_date_end_rows = split_state["all_date_end_rows"]
    all_date_to_pos = split_state["all_date_to_pos"]
    train_df = split_state["train_df"]
    test_df = split_state["test_df"]
    test_dates = split_state["test_dates"]

    # -----------------------------------------------------------------------------
    # 5. Train / eval / walk-forward stages
    # -----------------------------------------------------------------------------
    train_eval_request = TrainEvalRequest(
        data=TrainEvalData(
            train_df=train_df,
            test_df=test_df,
            test_dates=test_dates,
            df_features=df_features,
            df_full=df_full,
            df_model_sorted=df_model_sorted,
            all_dates=all_dates,
            all_date_start_rows=all_date_start_rows,
            all_date_end_rows=all_date_end_rows,
            all_date_to_pos=all_date_to_pos,
            valid_dates_set=valid_dates_set,
            backtest_pricing_df=backtest_pricing_df,
            benchmark_df=benchmark_df,
            benchmark_return_series=benchmark_return_series,
            industry_source_df=industry_source_df,
            passthrough_cols=passthrough_cols,
            industry_keep_columns=INDUSTRY_KEEP_COLUMNS,
            price_passthrough_cols=price_passthrough_cols,
            bucket_cols=bucket_cols,
        ),
        feature_target=TrainEvalFeatureTarget(
            features=FEATURES,
            target=TARGET,
            train_target=TRAIN_TARGET,
            price_col=PRICE_COL,
            fundamentals_mcap_col=FUNDAMENTALS_MCAP_COL,
        ),
        model=TrainEvalModelSettings(
            model_type=MODEL_TYPE,
            model_params=MODEL_PARAMS,
            model_cfg=MODEL_CFG,
            sample_weight_mode=SAMPLE_WEIGHT_MODE,
            sample_weight_params=SAMPLE_WEIGHT_PARAMS,
            n_splits=N_SPLITS,
            embargo_steps=EMBARGO_STEPS,
            purge_steps=PURGE_STEPS,
            train_window_mode=TRAIN_WINDOW_MODE,
            train_window_size=TRAIN_WINDOW_SIZE,
            train_window_unit=TRAIN_WINDOW_UNIT,
        ),
        signal=TrainEvalSignalSettings(
            signal_direction_mode=SIGNAL_DIRECTION_MODE,
            signal_direction=SIGNAL_DIRECTION,
            min_abs_ic_to_flip=MIN_ABS_IC_TO_FLIP,
            score_postprocess_method=SCORE_POSTPROCESS_METHOD,
            score_postprocess_columns=SCORE_POSTPROCESS_COLUMNS,
            score_postprocess_strength=SCORE_POSTPROCESS_STRENGTH,
            score_postprocess_min_obs=SCORE_POSTPROCESS_MIN_OBS,
            report_train_ic=REPORT_TRAIN_IC,
        ),
        live=TrainEvalLiveSettings(
            live_enabled=LIVE_ENABLED,
            live_as_of=LIVE_AS_OF,
            market=MARKET,
            provider=provider,
            live_train_mode=LIVE_TRAIN_MODE,
            min_symbols_per_date=MIN_SYMBOLS_PER_DATE,
        ),
        backtest=TrainEvalBacktestSettings(
            backtest_top_k=BACKTEST_TOP_K,
            label_shift_days=LABEL_SHIFT_DAYS,
            backtest_weighting=BACKTEST_WEIGHTING,
            backtest_buffer_exit=BACKTEST_BUFFER_EXIT,
            backtest_buffer_entry=BACKTEST_BUFFER_ENTRY,
            backtest_long_only=BACKTEST_LONG_ONLY,
            backtest_short_k=BACKTEST_SHORT_K,
            backtest_tradable_col=BACKTEST_TRADABLE_COL,
            backtest_group_col=BACKTEST_GROUP_COL,
            backtest_max_names_per_group=BACKTEST_MAX_NAMES_PER_GROUP,
            execution_model=execution_model,
            execution_sim_config=execution_sim_config,
            backtest_rebalance_frequency=BACKTEST_REBALANCE_FREQUENCY,
            backtest_enabled=BACKTEST_ENABLED,
            backtest_signal_direction_raw=BACKTEST_SIGNAL_DIRECTION_RAW,
            backtest_cost_bps_effective=BACKTEST_COST_BPS_EFFECTIVE,
            backtest_trading_days_per_year=BACKTEST_TRADING_DAYS_PER_YEAR,
            backtest_exit_mode=BACKTEST_EXIT_MODE,
            backtest_exit_horizon_days=BACKTEST_EXIT_HORIZON_DAYS,
            backtest_exit_price_policy=BACKTEST_EXIT_PRICE_POLICY,
            backtest_exit_fallback_policy=BACKTEST_EXIT_FALLBACK_POLICY,
        ),
        period=TrainEvalPeriodSettings(
            rebalance_frequency=REBALANCE_FREQUENCY,
            sample_on_rebalance_dates=SAMPLE_ON_REBALANCE_DATES,
            perm_test_runs=PERM_TEST_RUNS,
            perm_test_seed=PERM_TEST_SEED,
            label_horizon_mode=LABEL_HORIZON_MODE,
            label_horizon_effective=label_horizon_effective,
            n_quantiles=N_QUANTILES,
            top_k=TOP_K,
            eval_buffer_exit=EVAL_BUFFER_EXIT,
            eval_buffer_entry=EVAL_BUFFER_ENTRY,
            transaction_cost_bps=TRANSACTION_COST_BPS,
            bucket_ic_enabled=BUCKET_IC_ENABLED,
            bucket_ic_schemes=BUCKET_IC_SCHEMES,
            bucket_ic_method=BUCKET_IC_METHOD,
            bucket_ic_min_count=BUCKET_IC_MIN_COUNT,
            rolling_windows_months=ROLLING_WINDOWS_MONTHS,
        ),
        walk_forward=TrainEvalWalkForwardSettings(
            wf_enabled=WF_ENABLED,
            wf_n_windows=WF_N_WINDOWS,
            wf_test_size=WF_TEST_SIZE if WF_TEST_SIZE is not None else TEST_SIZE,
            wf_step_size=WF_STEP_SIZE,
            effective_gap_steps=EFFECTIVE_GAP_STEPS,
            wf_anchor_end=WF_ANCHOR_END,
            wf_feature_top_k=WF_FEATURE_TOP_K,
            wf_backtest_enabled=WF_BACKTEST_ENABLED,
            wf_perm_test_enabled=WF_PERM_TEST_ENABLED,
            wf_perm_test_runs=WF_PERM_TEST_RUNS,
            wf_perm_test_seed=WF_PERM_TEST_SEED,
        ),
        services=TrainEvalServices(
            backtest_topk_fn=backtest_topk_fn,
            bucket_ic_summary_fn=bucket_ic_summary_fn,
        ),
    )
    train_eval_state = run_train_eval_stage(
        request=train_eval_request,
    )
    period_eval_context = train_eval_state["period_eval_context"]

    final_oos_state = run_final_oos_stage(
        final_oos_enabled=FINAL_OOS_ENABLED,
        final_oos_dates=final_oos_dates,
        df_full=df_full,
        df_model_sorted=df_model_sorted,
        all_date_start_rows=all_date_start_rows,
        all_date_end_rows=all_date_end_rows,
        all_date_to_pos=all_date_to_pos,
        all_dates=all_dates,
        train_window_mode=TRAIN_WINDOW_MODE,
        train_window_size=TRAIN_WINDOW_SIZE,
        train_window_unit=TRAIN_WINDOW_UNIT,
        model_type=MODEL_TYPE,
        model_params=MODEL_PARAMS,
        sample_weight_mode=SAMPLE_WEIGHT_MODE,
        sample_weight_params=SAMPLE_WEIGHT_PARAMS,
        features=FEATURES,
        train_target=TRAIN_TARGET,
        period_eval_context=period_eval_context,
        rolling_windows_months=ROLLING_WINDOWS_MONTHS,
    )
    resolved_benchmark_compare_specs = _attach_benchmark_compare_frames(
        benchmark_compare_specs,
        benchmark_compare_dfs,
    )
    persist_pipeline_outputs(
        loaded=loaded,
        universe_inputs=universe_inputs,
        date_label_settings=date_label_settings,
        eval_settings=eval_settings,
        universe_filters=universe_filters,
        runtime_settings=runtime_settings,
        run_artifacts=run_artifacts,
        panel_state=panel_state,
        dataset_state=dataset_state,
        split_state=split_state,
        market=MARKET,
        artifacts_root=ARTIFACTS_ROOT,
        cache_dir=CACHE_DIR,
        provider=provider,
        quality_summary=quality_summary,
        benchmark_symbol=benchmark_symbol,
        benchmark_returns_file_path=benchmark_returns_file_path,
        benchmark_compare_specs=resolved_benchmark_compare_specs,
        label_horizon_mode=LABEL_HORIZON_MODE,
        final_oos_enabled=FINAL_OOS_ENABLED,
        final_oos_size_raw=FINAL_OOS_SIZE_RAW,
        purge_steps=PURGE_STEPS,
        embargo_steps=EMBARGO_STEPS,
        effective_gap_steps=EFFECTIVE_GAP_STEPS,
        backtest_group_col=BACKTEST_GROUP_COL,
        train_eval_state=train_eval_state,
        final_oos_state=final_oos_state,
    )

    # Optional: save the model
    # from joblib import dump; dump(model, "xgb_factor_model.joblib")


def run(
    config_ref: str | Path | None = None,
    *,
    fail_on_quality: str | None = None,
    artifacts_root: str | Path | None = None,
) -> None:
    context = prepare_research_context(
        config_ref,
        fail_on_quality=fail_on_quality,
        artifacts_root=artifacts_root,
    )
    train_eval_request = context["train_eval_request"]
    split_state = context["split_state"]
    runtime_settings = context["runtime_settings"]
    date_label_settings = context["date_label_settings"]
    eval_settings = context["eval_settings"]
    dataset_state = context["dataset_state"]
    data_inputs = context["data_inputs"]

    train_eval_state = run_train_eval_stage(request=train_eval_request)
    period_eval_context = train_eval_state["period_eval_context"]

    final_oos_state = run_final_oos_stage(
        final_oos_enabled=split_state["final_oos_enabled"],
        final_oos_dates=split_state["final_oos_dates"],
        df_full=dataset_state["df_full"],
        df_model_sorted=split_state["df_model_sorted"],
        all_date_start_rows=split_state["all_date_start_rows"],
        all_date_end_rows=split_state["all_date_end_rows"],
        all_date_to_pos=split_state["all_date_to_pos"],
        all_dates=split_state["all_dates"],
        train_window_mode=runtime_settings["TRAIN_WINDOW_MODE"],
        train_window_size=runtime_settings["TRAIN_WINDOW_SIZE"],
        train_window_unit=runtime_settings["TRAIN_WINDOW_UNIT"],
        model_type=runtime_settings["MODEL_TYPE"],
        model_params=runtime_settings["MODEL_PARAMS"],
        sample_weight_mode=runtime_settings["SAMPLE_WEIGHT_MODE"],
        sample_weight_params=runtime_settings["SAMPLE_WEIGHT_PARAMS"],
        features=train_eval_request.feature_target.features,
        train_target=date_label_settings["TRAIN_TARGET"],
        period_eval_context=period_eval_context,
        rolling_windows_months=eval_settings["ROLLING_WINDOWS_MONTHS"],
    )
    resolved_benchmark_compare_specs = _attach_benchmark_compare_frames(
        context["benchmark_compare_specs"],
        context["benchmark_compare_dfs"],
    )
    persist_pipeline_outputs(
        loaded=context["loaded"],
        universe_inputs=context["universe_inputs"],
        date_label_settings=date_label_settings,
        eval_settings=eval_settings,
        universe_filters=context["universe_filters"],
        runtime_settings=runtime_settings,
        run_artifacts=context["run_artifacts"],
        panel_state=context["panel_state"],
        dataset_state=dataset_state,
        split_state=split_state,
        market=context["market"],
        artifacts_root=context["artifacts_root"],
        cache_dir=context["cache_dir"],
        provider=context["provider"],
        quality_summary=context["quality_summary"],
        benchmark_symbol=data_inputs["benchmark_symbol"],
        benchmark_returns_file_path=data_inputs["benchmark_returns_file_path"],
        benchmark_compare_specs=resolved_benchmark_compare_specs,
        label_horizon_mode=date_label_settings["LABEL_HORIZON_MODE"],
        final_oos_enabled=split_state["final_oos_enabled"],
        final_oos_size_raw=eval_settings["FINAL_OOS_SIZE_RAW"],
        purge_steps=split_state["purge_steps"],
        embargo_steps=split_state["embargo_steps"],
        effective_gap_steps=split_state["effective_gap_steps"],
        backtest_group_col=context["backtest_group_col"],
        train_eval_state=train_eval_state,
        final_oos_state=final_oos_state,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Cross-sectional factor pipeline")
    parser.add_argument(
        "--config",
        help="Path to YAML config or built-in name (default/hk).",
    )
    parser.add_argument(
        "--fail-on-quality",
        choices=["none", "info", "warning", "error"],
        default=None,
        help=(
            "Optional quality gate threshold. Overrides quality.fail_on_severity in the config "
            "when provided."
        ),
    )
    parser.add_argument(
        "--artifacts-root",
        help=(
            "Optional artifacts root override. When omitted, the pipeline uses "
            "CSTREE_ARTIFACTS_ROOT, paths.artifacts_root, "
            "or the default artifacts/."
        ),
    )
    args = parser.parse_args(argv)
    if args.fail_on_quality is None and args.artifacts_root is None:
        run(args.config)
        return
    run(
        args.config,
        fail_on_quality=args.fail_on_quality,
        artifacts_root=args.artifacts_root,
    )


if __name__ == "__main__":
    main()
