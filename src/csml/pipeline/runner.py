"""Pipeline runner for the HK + RQData workflow.
Usage:
    $ csml run
    $ csml run --config configs/presets/default.yml
    $ csml run --config hk
    # rqdatac auth may be required (RQDATA_USERNAME/RQDATA_PASSWORD)
"""
import argparse
from collections.abc import Mapping
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np
from ..compat import ensure_numpy_nan_alias

ensure_numpy_nan_alias()
import pandas as pd

from ..artifacts import (
    resolve_repo_path,
)
from ..data_interface import DataInterface
from ..data_providers import fundamentals_provider_supported
from ..metrics import (
    bucket_ic_summary,
    daily_ic_series,
    summarize_ic,
)
from ..split import build_sample_weight, time_series_cv_ic
from ..modeling import build_model, fit_model, feature_importance_frame
from ..backtest import backtest_topk
from ..transform import apply_score_postprocess
from .config import (
    load_run_config,
    normalize_eval_settings,
    normalize_universe_filters,
    prepare_run_artifacts,
    resolve_runtime_settings,
    resolve_date_range_and_label_settings,
    resolve_universe_inputs,
)
from .support import (
    _annotate_positions_window,
    _ensure_symbol_alias,
    _parse_window_config,
    _prepare_panel_join_frame,
    _select_panel_join_columns,
    _summarize_walk_forward_feature_stability,
    apply_universe_by_date,
    parse_feature_windows,
)
from .dates import (
    _slice_with_train_window,
    build_walk_forward_windows,
)
from .data import _load_research_panel, _prepare_feature_dataset
from .eval import (
    _evaluate_period,
    _evaluate_walk_forward_window,
)
from .live import _prepare_live_snapshot
from .output import persist_run_outputs
from .quality import run_quality_preflight
from .runtime import _prepare_split_context
from .stats import (
    _compute_rolling_ic,
    _compute_rolling_sharpe,
    _ensure_execution_daily_fields,
    _latest_rolling_stats,
)
logger = logging.getLogger("csml")


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


def _build_output_context(
    *,
    loaded: Mapping[str, Any],
    universe_inputs: Mapping[str, Any],
    date_label_settings: Mapping[str, Any],
    eval_settings: Mapping[str, Any],
    universe_filters: Mapping[str, Any],
    runtime_settings: Mapping[str, Any],
    run_artifacts: Mapping[str, Any],
    panel_state: Mapping[str, Any],
    dataset_state: Mapping[str, Any],
    split_state: Mapping[str, Any],
    extras: Mapping[str, Any],
) -> dict[str, Any]:
    context: dict[str, Any] = {}
    for source in (
        loaded,
        universe_inputs,
        date_label_settings,
        eval_settings,
        universe_filters,
        runtime_settings,
        run_artifacts,
        panel_state,
        dataset_state,
        split_state,
        extras,
    ):
        context.update(source)
    return context


def run(
    config_ref: str | Path | None = None,
    *,
    fail_on_quality: str | None = None,
    artifacts_root: str | Path | None = None,
) -> None:
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
    loaded = load_run_config(
        config_ref,
        artifacts_root_override=artifacts_root,
    )
    config = loaded["config"]
    config_label = loaded["config_label"]
    config_path = loaded["config_path"]
    config_source = loaded["config_source"]
    active_log_file = loaded["active_log_file"]
    data_cfg = loaded["data_cfg"]
    MARKET = loaded["market"]
    universe_cfg = loaded["universe_cfg"]
    label_cfg = loaded["label_cfg"]
    features_cfg = loaded["features_cfg"]
    fundamentals_cfg = loaded["fundamentals_cfg"]
    model_cfg = loaded["model_cfg"]
    eval_cfg = loaded["eval_cfg"]
    backtest_cfg = loaded["backtest_cfg"]
    live_cfg = loaded["live_cfg"]
    ARTIFACTS_ROOT = loaded["artifacts_root"]
    CACHE_DIR = loaded["cache_dir"]
    DEFAULT_RUNS_DIR = loaded["runs_dir"]
    data_interface = DataInterface(MARKET, data_cfg, cache_dir=CACHE_DIR, logger=logger)
    provider = data_interface.provider

    DEFAULT_SYMBOLS = [
        "00700.HK",
        "00005.HK",
        "00941.HK",
        "00001.HK",
        "00388.HK",
    ]
    universe_inputs = resolve_universe_inputs(
        universe_cfg,
        market=MARKET,
        logger=logger,
        default_symbols=DEFAULT_SYMBOLS,
    )
    UNIVERSE_MODE = universe_inputs["UNIVERSE_MODE"]
    REQUIRE_BY_DATE = universe_inputs["REQUIRE_BY_DATE"]
    symbols = universe_inputs["symbols"]
    symbols_file = universe_inputs["symbols_file"]
    by_date_file = universe_inputs["by_date_file"]
    universe_by_date = universe_inputs["universe_by_date"]
    universe_mode_effective = universe_inputs["universe_mode_effective"]

    date_label_settings = resolve_date_range_and_label_settings(
        data_cfg=data_cfg,
        label_cfg=label_cfg,
        eval_cfg=eval_cfg,
        live_cfg=live_cfg,
        market=MARKET,
        provider=provider,
        logger=logger,
    )
    end_date = date_label_settings["end_date"]
    start_date = date_label_settings["start_date"]
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

    eval_settings = normalize_eval_settings(eval_cfg, backtest_cfg=backtest_cfg)
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
    SCORE_POSTPROCESS_ENABLED = eval_settings["SCORE_POSTPROCESS_ENABLED"]
    SCORE_POSTPROCESS_METHOD = eval_settings["SCORE_POSTPROCESS_METHOD"]
    SCORE_POSTPROCESS_COLUMNS = eval_settings["SCORE_POSTPROCESS_COLUMNS"]
    SCORE_POSTPROCESS_STRENGTH = eval_settings["SCORE_POSTPROCESS_STRENGTH"]
    SCORE_POSTPROCESS_MIN_OBS = eval_settings["SCORE_POSTPROCESS_MIN_OBS"]
    ROLLING_WINDOWS_MONTHS = eval_settings["ROLLING_WINDOWS_MONTHS"]
    BUCKET_IC_ENABLED = eval_settings["BUCKET_IC_ENABLED"]
    BUCKET_IC_METHOD = eval_settings["BUCKET_IC_METHOD"]
    BUCKET_IC_MIN_COUNT = eval_settings["BUCKET_IC_MIN_COUNT"]
    BUCKET_IC_SCHEMES = eval_settings["BUCKET_IC_SCHEMES"]
    PERM_TEST_ENABLED = eval_settings["PERM_TEST_ENABLED"]
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
    SAVE_ARTIFACTS = eval_settings["SAVE_ARTIFACTS"]
    SAVE_SCORED_ARTIFACT = eval_settings["SAVE_SCORED_ARTIFACT"]
    SAVE_DATASET = eval_settings["SAVE_DATASET"]
    OUTPUT_DIR = eval_settings["OUTPUT_DIR"] or DEFAULT_RUNS_DIR.as_posix()
    RUN_NAME = eval_settings["RUN_NAME"]
    if BUCKET_IC_ENABLED and not BUCKET_IC_SCHEMES:
        logger.warning("eval.bucket_ic.enabled=true but no schemes configured.")

    universe_filters = normalize_universe_filters(
        universe_cfg,
        n_quantiles=N_QUANTILES,
    )
    MIN_SYMBOLS_PER_DATE = universe_filters["MIN_SYMBOLS_PER_DATE"]
    MIN_LISTED_DAYS = universe_filters["MIN_LISTED_DAYS"]
    MIN_TURNOVER = universe_filters["MIN_TURNOVER"]
    DROP_ST = universe_filters["DROP_ST"]
    DROP_SUSPENDED = universe_filters["DROP_SUSPENDED"]
    SUSPENDED_POLICY = universe_filters["SUSPENDED_POLICY"]
    industry_cfg = config.get("industry") or {}

    runtime_settings = resolve_runtime_settings(
        data_cfg=data_cfg,
        features_cfg=features_cfg,
        fundamentals_cfg=fundamentals_cfg,
        industry_cfg=industry_cfg,
        model_cfg=model_cfg,
        backtest_cfg=backtest_cfg,
        live_cfg=live_cfg,
        provider=provider,
        market=MARKET,
        price_col=PRICE_COL,
        label_horizon_days=LABEL_HORIZON_DAYS,
        label_shift_days=LABEL_SHIFT_DAYS,
        label_horizon_mode=LABEL_HORIZON_MODE,
        label_rebalance_frequency=LABEL_REBALANCE_FREQUENCY,
        train_target=TRAIN_TARGET,
        eval_top_k=TOP_K,
        eval_rebalance_frequency=REBALANCE_FREQUENCY,
        eval_transaction_cost_bps=TRANSACTION_COST_BPS,
        eval_buffer_exit=EVAL_BUFFER_EXIT,
        eval_buffer_entry=EVAL_BUFFER_ENTRY,
        wf_feature_top_k=WF_FEATURE_TOP_K,
    )
    fundamentals_cfg = runtime_settings["fundamentals_cfg"]
    provider_overlay_cfg = runtime_settings["provider_overlay_cfg"]
    FUNDAMENTALS_ENABLED = runtime_settings["FUNDAMENTALS_ENABLED"]
    FUNDAMENTALS_SOURCE = runtime_settings["FUNDAMENTALS_SOURCE"]
    FUNDAMENTALS_FILE = runtime_settings["FUNDAMENTALS_FILE"]
    FUNDAMENTALS_FEATURES = runtime_settings["FUNDAMENTALS_FEATURES"]
    FUNDAMENTALS_AUTO_ADD = runtime_settings["FUNDAMENTALS_AUTO_ADD"]
    FUNDAMENTALS_ALLOW_MISSING = runtime_settings["FUNDAMENTALS_ALLOW_MISSING"]
    FUNDAMENTALS_FFILL = runtime_settings["FUNDAMENTALS_FFILL"]
    FUNDAMENTALS_FFILL_LIMIT = runtime_settings["FUNDAMENTALS_FFILL_LIMIT"]
    FUNDAMENTALS_LOG_MCAP = runtime_settings["FUNDAMENTALS_LOG_MCAP"]
    FUNDAMENTALS_MCAP_COL = runtime_settings["FUNDAMENTALS_MCAP_COL"]
    FUNDAMENTALS_LOG_MCAP_COL = runtime_settings["FUNDAMENTALS_LOG_MCAP_COL"]
    FUNDAMENTALS_REQUIRED = runtime_settings["FUNDAMENTALS_REQUIRED"]
    FUNDAMENTALS_PROVIDER = runtime_settings["FUNDAMENTALS_PROVIDER"]
    FUNDAMENTALS_PROVIDER_OVERLAY_ENABLED = runtime_settings[
        "FUNDAMENTALS_PROVIDER_OVERLAY_ENABLED"
    ]
    FUNDAMENTALS_PROVIDER_OVERLAY_SOURCE = runtime_settings[
        "FUNDAMENTALS_PROVIDER_OVERLAY_SOURCE"
    ]
    FUNDAMENTALS_PROVIDER_OVERLAY_FEATURES = runtime_settings[
        "FUNDAMENTALS_PROVIDER_OVERLAY_FEATURES"
    ]
    FUNDAMENTALS_PROVIDER_OVERLAY_AUTO_ADD = runtime_settings[
        "FUNDAMENTALS_PROVIDER_OVERLAY_AUTO_ADD"
    ]
    FUNDAMENTALS_PROVIDER_OVERLAY_REQUIRED = runtime_settings[
        "FUNDAMENTALS_PROVIDER_OVERLAY_REQUIRED"
    ]
    FUNDAMENTALS_PROVIDER_OVERLAY_PROVIDER = runtime_settings[
        "FUNDAMENTALS_PROVIDER_OVERLAY_PROVIDER"
    ]
    INDUSTRY_ENABLED = runtime_settings["INDUSTRY_ENABLED"]
    INDUSTRY_SOURCE = runtime_settings["INDUSTRY_SOURCE"]
    INDUSTRY_FILE = runtime_settings["INDUSTRY_FILE"]
    INDUSTRY_KEEP_COLUMNS = runtime_settings["INDUSTRY_KEEP_COLUMNS"]
    INDUSTRY_FFILL = runtime_settings["INDUSTRY_FFILL"]
    INDUSTRY_FFILL_LIMIT = runtime_settings["INDUSTRY_FFILL_LIMIT"]
    INDUSTRY_REQUIRED = runtime_settings["INDUSTRY_REQUIRED"]
    FEATURES = runtime_settings["FEATURES"]
    feature_params = runtime_settings["feature_params"]
    CS_METHOD = runtime_settings["CS_METHOD"]
    CS_WINSORIZE_PCT = runtime_settings["CS_WINSORIZE_PCT"]
    FEATURE_MISSING_METHOD = runtime_settings["FEATURE_MISSING_METHOD"]
    FEATURE_MISSING_FEATURES = runtime_settings["FEATURE_MISSING_FEATURES"]
    FEATURE_MISSING_ADD_INDICATORS = runtime_settings[
        "FEATURE_MISSING_ADD_INDICATORS"
    ]
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
    BACKTEST_COST_BPS = runtime_settings["BACKTEST_COST_BPS"]
    BACKTEST_TRADING_DAYS_PER_YEAR = runtime_settings[
        "BACKTEST_TRADING_DAYS_PER_YEAR"
    ]
    BACKTEST_BENCHMARK = runtime_settings["BACKTEST_BENCHMARK"]
    BACKTEST_BENCHMARK_RETURNS_FILE = runtime_settings[
        "BACKTEST_BENCHMARK_RETURNS_FILE"
    ]
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
    BACKTEST_EXIT_FALLBACK_POLICY = runtime_settings[
        "BACKTEST_EXIT_FALLBACK_POLICY"
    ]
    execution_model = runtime_settings["execution_model"]
    EXECUTION_PRICING_COLS = runtime_settings["EXECUTION_PRICING_COLS"]
    BACKTEST_COST_BPS_EFFECTIVE = runtime_settings["BACKTEST_COST_BPS_EFFECTIVE"]
    BACKTEST_COST_BPS_REPORT = runtime_settings["BACKTEST_COST_BPS_REPORT"]
    BACKTEST_EXECUTION_SOURCE = runtime_settings["BACKTEST_EXECUTION_SOURCE"]
    BACKTEST_TRADABLE_COL = runtime_settings["BACKTEST_TRADABLE_COL"]
    LIVE_ENABLED = runtime_settings["LIVE_ENABLED"]
    LIVE_AS_OF = runtime_settings["LIVE_AS_OF"]
    LIVE_TRAIN_MODE = runtime_settings["LIVE_TRAIN_MODE"]
    WF_FEATURE_TOP_K = runtime_settings["WF_FEATURE_TOP_K"]
    if LIVE_ENABLED and not SAVE_ARTIFACTS:
        raise SystemExit(
            "live.enabled=true requires eval.save_artifacts=true to persist holdings."
        )

    run_artifacts = prepare_run_artifacts(
        config=config,
        config_label=config_label,
        output_dir=OUTPUT_DIR,
        run_name=RUN_NAME,
        save_artifacts=SAVE_ARTIFACTS,
        active_log_file=active_log_file,
        default_runs_dir=DEFAULT_RUNS_DIR,
        logger=logger,
    )
    OUTPUT_DIR = run_artifacts["OUTPUT_DIR"]
    run_name = run_artifacts["run_name"]
    run_stamp = run_artifacts["run_stamp"]
    run_hash = run_artifacts["run_hash"]
    run_dir = run_artifacts["run_dir"]
    active_log_file = run_artifacts["active_log_file"]
    quality_preflight = run_quality_preflight(
        config=config,
        run_dir=run_dir if SAVE_ARTIFACTS else None,
        save_artifacts=SAVE_ARTIFACTS,
        fail_on_quality=fail_on_quality,
        logger=logger,
    )
    quality_summary = {"preflight": quality_preflight}
    quality_overall_verdict = (
        quality_preflight.get("overall_verdict")
        if isinstance(quality_preflight, Mapping)
        and isinstance(quality_preflight.get("overall_verdict"), Mapping)
        else None
    )
    if isinstance(quality_overall_verdict, Mapping) and bool(quality_overall_verdict.get("gate_triggered")):
        quality_report = None
        quality_checks = quality_preflight.get("checks") if isinstance(quality_preflight.get("checks"), list) else []
        for item in quality_checks:
            if isinstance(item, Mapping) and item.get("report_file"):
                quality_report = str(item.get("report_file"))
                break
        detail = f" Report: {quality_report}" if quality_report else ""
        raise SystemExit(
            f"Pipeline quality gate failed: {quality_overall_verdict.get('message')}{detail}"
        )

    fundamentals_cols: list[str] = []
    industry_cols: list[str] = []
    fund_cache_dir: Optional[Path] = None
    fundamentals_file_path: Optional[Path] = None
    industry_file_path: Optional[Path] = None
    provider_overlay_cache_dir: Optional[Path] = None
    if FUNDAMENTALS_ENABLED:
        if FUNDAMENTALS_SOURCE == "provider" and not fundamentals_provider_supported(
            FUNDAMENTALS_PROVIDER, MARKET
        ):
            message = (
                "Fundamentals provider mode currently supports only RQData market=hk; "
                "use source=file instead."
            )
            if FUNDAMENTALS_REQUIRED:
                sys.exit(message)
            logger.warning("%s Fundamentals disabled.", message)
            FUNDAMENTALS_ENABLED = False
        if FUNDAMENTALS_SOURCE == "file" and not FUNDAMENTALS_FILE:
            message = "fundamentals.file is required when fundamentals.source=file."
            if FUNDAMENTALS_REQUIRED:
                sys.exit(message)
            logger.warning("%s Fundamentals disabled.", message)
            FUNDAMENTALS_ENABLED = False
        if FUNDAMENTALS_SOURCE == "file" and FUNDAMENTALS_ENABLED:
            fundamentals_file_path = resolve_repo_path(FUNDAMENTALS_FILE)
            if not fundamentals_file_path.exists():
                message = f"Fundamentals file not found: {fundamentals_file_path}"
                if FUNDAMENTALS_REQUIRED:
                    sys.exit(message)
                logger.warning("%s Fundamentals disabled.", message)
                FUNDAMENTALS_ENABLED = False
    if INDUSTRY_ENABLED:
        if not INDUSTRY_FILE:
            message = "industry.file is required when industry.enabled=true."
            if INDUSTRY_REQUIRED:
                sys.exit(message)
            logger.warning("%s Industry join disabled.", message)
            INDUSTRY_ENABLED = False
        else:
            industry_file_path = resolve_repo_path(INDUSTRY_FILE)
            if not industry_file_path.exists():
                message = f"Industry file not found: {industry_file_path}"
                if INDUSTRY_REQUIRED:
                    sys.exit(message)
                logger.warning("%s Industry join disabled.", message)
                INDUSTRY_ENABLED = False
    if FUNDAMENTALS_PROVIDER_OVERLAY_ENABLED:
        if not FUNDAMENTALS_ENABLED or FUNDAMENTALS_SOURCE != "file":
            message = (
                "fundamentals.provider_overlay requires fundamentals.enabled=true "
                "and fundamentals.source=file."
            )
            if FUNDAMENTALS_PROVIDER_OVERLAY_REQUIRED:
                sys.exit(message)
            logger.warning("%s Provider overlay disabled.", message)
            FUNDAMENTALS_PROVIDER_OVERLAY_ENABLED = False
        elif not fundamentals_provider_supported(
            FUNDAMENTALS_PROVIDER_OVERLAY_PROVIDER, MARKET
        ):
            message = (
                "fundamentals.provider_overlay currently supports only RQData market=hk."
            )
            if FUNDAMENTALS_PROVIDER_OVERLAY_REQUIRED:
                sys.exit(message)
            logger.warning("%s Provider overlay disabled.", message)
            FUNDAMENTALS_PROVIDER_OVERLAY_ENABLED = False

    if not FUNDAMENTALS_ENABLED and FUNDAMENTALS_AUTO_ADD and FUNDAMENTALS_FEATURES:
        FEATURES = [feat for feat in FEATURES if feat not in FUNDAMENTALS_FEATURES]
    if (
        not FUNDAMENTALS_PROVIDER_OVERLAY_ENABLED
        and FUNDAMENTALS_PROVIDER_OVERLAY_AUTO_ADD
        and FUNDAMENTALS_PROVIDER_OVERLAY_FEATURES
    ):
        FEATURES = [
            feat
            for feat in FEATURES
            if feat not in FUNDAMENTALS_PROVIDER_OVERLAY_FEATURES
        ]

    # -----------------------------------------------------------------------------
    # 2. Data download
    # -----------------------------------------------------------------------------
    benchmark_symbol = str(BACKTEST_BENCHMARK).strip() if BACKTEST_BENCHMARK else None
    benchmark_returns_file_path = (
        resolve_repo_path(BACKTEST_BENCHMARK_RETURNS_FILE)
        if BACKTEST_BENCHMARK_RETURNS_FILE
        else None
    )
    benchmark_return_series = (
        _load_benchmark_return_series(benchmark_returns_file_path)
        if benchmark_returns_file_path is not None
        else pd.Series(dtype=float, name="benchmark_return")
    )
    panel_state = _load_research_panel(
        data_interface=data_interface,
        symbols=symbols,
        market=MARKET,
        start_date=START_DATE,
        end_date=END_DATE,
        execution_pricing_cols=EXECUTION_PRICING_COLS,
        price_col=PRICE_COL,
        benchmark_symbol=benchmark_symbol,
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
    symbols_for_non_price = panel_state["symbols_for_non_price"]
    fundamentals_cols = panel_state["fundamentals_cols"]
    industry_cols = panel_state["industry_cols"]
    industry_source_df = panel_state["industry_source_df"]
    fund_cache_dir = panel_state["fund_cache_dir"]
    provider_overlay_cache_dir = panel_state["provider_overlay_cache_dir"]
    FEATURES = panel_state["features"]
    LABEL_HORIZON_MODE = panel_state["label_horizon_mode"]
    label_next_rebalance_map = panel_state["label_next_rebalance_map"]
    label_horizon_gap = panel_state["label_horizon_gap"]
    price_col_diagnostics = panel_state["price_col_diagnostics"]

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
    dataset = dataset_state["dataset"]
    df_features = dataset_state["df_features"]
    df_full = dataset_state["df_full"]
    df_full_sorted = dataset_state["df_full_sorted"]
    reference_trade_dates = dataset_state["reference_trade_dates"]
    all_dates_full = dataset_state["all_dates_full"]
    full_date_start_rows = dataset_state["full_date_start_rows"]
    full_date_end_rows = dataset_state["full_date_end_rows"]
    full_date_to_pos = dataset_state["full_date_to_pos"]
    df_model_all = dataset_state["df_model_all"]
    df_model_all_sorted = dataset_state["df_model_all_sorted"]
    all_dates_model_full = dataset_state["all_dates_model_full"]
    model_date_start_rows = dataset_state["model_date_start_rows"]
    model_date_end_rows = dataset_state["model_date_end_rows"]
    model_date_to_pos = dataset_state["model_date_to_pos"]
    valid_dates = dataset_state["valid_dates"]
    valid_dates_set = dataset_state["valid_dates_set"]
    dropped_date_counts = dataset_state["dropped_date_counts"]
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
    df_model = split_state["df_model"]
    df_model_oos = split_state["df_model_oos"]
    final_oos_dates = split_state["final_oos_dates"]
    final_oos_len = split_state["final_oos_len"]
    final_oos_start = split_state["final_oos_start"]
    final_oos_end = split_state["final_oos_end"]
    label_horizon_effective = split_state["label_horizon_effective"]
    purge_days = split_state["purge_days"]
    embargo_days = split_state["embargo_days"]
    PURGE_STEPS = split_state["purge_steps"]
    EMBARGO_STEPS = split_state["embargo_steps"]
    EFFECTIVE_GAP_STEPS = split_state["effective_gap_steps"]
    rebalance_gap_days = split_state["rebalance_gap_days"]
    df_model_sorted = split_state["df_model_sorted"]
    all_dates = split_state["all_dates"]
    all_date_start_rows = split_state["all_date_start_rows"]
    all_date_end_rows = split_state["all_date_end_rows"]
    all_date_to_pos = split_state["all_date_to_pos"]
    train_df = split_state["train_df"]
    train_dates = split_state["train_dates"]
    train_dates_full = split_state["train_dates_full"]
    test_df = split_state["test_df"]
    test_dates = split_state["test_dates"]

    # -----------------------------------------------------------------------------
    # 5. Cross-validation on dates (IC metric)
    # -----------------------------------------------------------------------------
    logger.info("Time-series cross-validation (IC) ...")

    walk_forward_importance_rows: list[dict[str, Any]] = []

    cv_scores_raw = time_series_cv_ic(
        train_df,
        FEATURES,
        TARGET,
        N_SPLITS,
        EMBARGO_STEPS,
        PURGE_STEPS,
        MODEL_CFG,
        1.0,
        sample_weight_mode=SAMPLE_WEIGHT_MODE,
        sample_weight_params=SAMPLE_WEIGHT_PARAMS,
        train_window_mode=TRAIN_WINDOW_MODE,
        train_window_size=TRAIN_WINDOW_SIZE,
        train_window_unit=TRAIN_WINDOW_UNIT,
        fit_target_col=TRAIN_TARGET,
        score_postprocess_method=SCORE_POSTPROCESS_METHOD,
        score_postprocess_columns=SCORE_POSTPROCESS_COLUMNS,
        score_postprocess_strength=SCORE_POSTPROCESS_STRENGTH,
        score_postprocess_min_obs=SCORE_POSTPROCESS_MIN_OBS,
    )
    if cv_scores_raw:
        logger.info(
            "CV IC (raw): mean=%.4f, std=%.4f", np.nanmean(cv_scores_raw), np.nanstd(cv_scores_raw)
        )
        logger.info("CV fold ICs (raw): %s", [f"{s:.4f}" for s in cv_scores_raw])
    else:
        logger.info("CV IC not available - insufficient data after embargo/purge.")

    cv_scores_adj = None
    if SIGNAL_DIRECTION_MODE == "cv_ic" and cv_scores_raw:
        cv_mean = float(np.nanmean(cv_scores_raw))
        if np.isfinite(cv_mean) and cv_mean != 0 and abs(cv_mean) >= MIN_ABS_IC_TO_FLIP:
            SIGNAL_DIRECTION = float(np.sign(cv_mean))
            logger.info("Signal direction set from CV IC: %s", SIGNAL_DIRECTION)
        else:
            logger.info(
                "CV IC mean below threshold (|mean| < %.4f); keeping signal direction: %s",
                MIN_ABS_IC_TO_FLIP,
                SIGNAL_DIRECTION,
            )

    # -----------------------------------------------------------------------------
    # 6. Fit final model
    # -----------------------------------------------------------------------------
    logger.info("Fitting model (%s) ...", MODEL_TYPE)
    model = build_model(MODEL_TYPE, MODEL_PARAMS)
    train_weights = build_sample_weight(
        train_df,
        SAMPLE_WEIGHT_MODE,
        params=SAMPLE_WEIGHT_PARAMS,
    )
    fit_model(
        model,
        MODEL_TYPE,
        train_df,
        features=FEATURES,
        target_col=TRAIN_TARGET,
        sample_weight=train_weights,
    )

    # -----------------------------------------------------------------------------
    # 7. Evaluation (cross-sectional factor style)
    # -----------------------------------------------------------------------------
    logger.info("Evaluating model on train/test sets ...")

    test_start = pd.to_datetime(test_dates[0])
    test_end = pd.to_datetime(test_dates[-1])
    test_df_full = df_full[
        (df_full["trade_date"] >= test_start) & (df_full["trade_date"] <= test_end)
    ].copy()
    if test_df_full.empty:
        sys.exit("Not enough test data after applying the split window.")

    train_eval_df = train_df.copy()
    train_eval_df["pred"] = model.predict(train_eval_df[FEATURES])
    train_eval_df["pred"] = apply_score_postprocess(
        train_eval_df,
        "pred",
        method=SCORE_POSTPROCESS_METHOD,
        columns=SCORE_POSTPROCESS_COLUMNS,
        strength=SCORE_POSTPROCESS_STRENGTH,
        min_obs=SCORE_POSTPROCESS_MIN_OBS,
    )
    train_ic_raw_stats = {}
    if SIGNAL_DIRECTION_MODE == "train_ic":
        train_ic_raw_series = daily_ic_series(train_eval_df, TARGET, "pred")
        train_ic_raw_stats = summarize_ic(train_ic_raw_series)
        raw_mean = train_ic_raw_stats.get("mean", np.nan)
        if np.isfinite(raw_mean) and raw_mean != 0:
            SIGNAL_DIRECTION = float(np.sign(raw_mean))
        else:
            SIGNAL_DIRECTION = 1.0
        logger.info("Signal direction set from Train IC: %s", SIGNAL_DIRECTION)

    train_signal_col = "pred"
    if SIGNAL_DIRECTION != 1.0:
        train_eval_df["signal"] = train_eval_df["pred"] * SIGNAL_DIRECTION
        train_signal_col = "signal"

    if cv_scores_raw:
        cv_scores_adj = [float(score) * SIGNAL_DIRECTION for score in cv_scores_raw]
        if SIGNAL_DIRECTION != 1.0:
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
    if REPORT_TRAIN_IC:
        train_ic_series = daily_ic_series(train_eval_df, TARGET, train_signal_col)
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
            train_eval_df, TARGET, train_signal_col, method="pearson"
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
            "live_enabled": LIVE_ENABLED,
            "live_as_of_token": LIVE_AS_OF,
            "market": MARKET,
            "provider": provider,
            "target": TARGET,
            "live_train_mode": LIVE_TRAIN_MODE,
            "model_type": MODEL_TYPE,
            "model_params": MODEL_PARAMS,
            "train_window_mode": TRAIN_WINDOW_MODE,
            "train_window_size": TRAIN_WINDOW_SIZE,
            "train_window_unit": TRAIN_WINDOW_UNIT,
            "sample_weight_mode": SAMPLE_WEIGHT_MODE,
            "sample_weight_params": SAMPLE_WEIGHT_PARAMS,
            "train_target": TRAIN_TARGET,
            "features": FEATURES,
            "signal_direction": SIGNAL_DIRECTION,
            "score_postprocess_method": SCORE_POSTPROCESS_METHOD,
            "score_postprocess_columns": SCORE_POSTPROCESS_COLUMNS,
            "score_postprocess_strength": SCORE_POSTPROCESS_STRENGTH,
            "score_postprocess_min_obs": SCORE_POSTPROCESS_MIN_OBS,
            "backtest_rebalance_frequency": BACKTEST_REBALANCE_FREQUENCY,
            "min_symbols_per_date": MIN_SYMBOLS_PER_DATE,
            "price_col": PRICE_COL,
            "backtest_top_k": BACKTEST_TOP_K,
            "label_shift_days": LABEL_SHIFT_DAYS,
            "backtest_weighting": BACKTEST_WEIGHTING,
            "backtest_buffer_exit": BACKTEST_BUFFER_EXIT,
            "backtest_buffer_entry": BACKTEST_BUFFER_ENTRY,
            "backtest_long_only": BACKTEST_LONG_ONLY,
            "backtest_short_k": BACKTEST_SHORT_K,
            "backtest_tradable_col": BACKTEST_TRADABLE_COL,
            "backtest_group_col": BACKTEST_GROUP_COL,
            "backtest_max_names_per_group": BACKTEST_MAX_NAMES_PER_GROUP,
            "execution_model": execution_model,
        },
    )
    live_as_of = live_state["live_as_of"]
    positions_by_rebalance_live = live_state["positions_by_rebalance_live"]
    live_positions_ready = bool(live_state["live_positions_ready"])

    if LIVE_ENABLED and not BACKTEST_ENABLED and not live_positions_ready:
        raise SystemExit(
            "live.enabled=true but no live positions were generated; "
            "refusing to fall back to backtest holdings."
        )

    BACKTEST_SIGNAL_DIRECTION = (
        SIGNAL_DIRECTION if BACKTEST_SIGNAL_DIRECTION_RAW is None else BACKTEST_SIGNAL_DIRECTION_RAW
    )

    period_eval_context = {
        "features": FEATURES,
        "target": TARGET,
        "signal_direction": SIGNAL_DIRECTION,
        "backtest_signal_direction": BACKTEST_SIGNAL_DIRECTION,
        "sample_on_rebalance_dates": SAMPLE_ON_REBALANCE_DATES,
        "score_postprocess_method": SCORE_POSTPROCESS_METHOD,
        "score_postprocess_columns": SCORE_POSTPROCESS_COLUMNS,
        "score_postprocess_strength": SCORE_POSTPROCESS_STRENGTH,
        "score_postprocess_min_obs": SCORE_POSTPROCESS_MIN_OBS,
        "rebalance_frequency": REBALANCE_FREQUENCY,
        "valid_dates_set": valid_dates_set,
        "perm_test_runs": PERM_TEST_RUNS,
        "perm_test_seed": PERM_TEST_SEED,
        "model_type": MODEL_TYPE,
        "model_params": MODEL_PARAMS,
        "train_target": TRAIN_TARGET,
        "sample_weight_mode": SAMPLE_WEIGHT_MODE,
        "sample_weight_params": SAMPLE_WEIGHT_PARAMS,
        "label_horizon_mode": LABEL_HORIZON_MODE,
        "label_horizon_effective": label_horizon_effective,
        "n_quantiles": N_QUANTILES,
        "top_k": TOP_K,
        "eval_buffer_exit": EVAL_BUFFER_EXIT,
        "eval_buffer_entry": EVAL_BUFFER_ENTRY,
        "transaction_cost_bps": TRANSACTION_COST_BPS,
        "bucket_ic_enabled": BUCKET_IC_ENABLED,
        "bucket_ic_schemes": BUCKET_IC_SCHEMES,
        "bucket_ic_method": BUCKET_IC_METHOD,
        "bucket_ic_min_count": BUCKET_IC_MIN_COUNT,
        "backtest_rebalance_frequency": BACKTEST_REBALANCE_FREQUENCY,
        "backtest_enabled": BACKTEST_ENABLED,
        "live_enabled": LIVE_ENABLED,
        "backtest_top_k": BACKTEST_TOP_K,
        "label_shift_days": LABEL_SHIFT_DAYS,
        "backtest_weighting": BACKTEST_WEIGHTING,
        "backtest_buffer_exit": BACKTEST_BUFFER_EXIT,
        "backtest_buffer_entry": BACKTEST_BUFFER_ENTRY,
        "backtest_long_only": BACKTEST_LONG_ONLY,
        "backtest_short_k": BACKTEST_SHORT_K,
        "backtest_tradable_col": BACKTEST_TRADABLE_COL,
        "backtest_group_col": BACKTEST_GROUP_COL,
        "backtest_max_names_per_group": BACKTEST_MAX_NAMES_PER_GROUP,
        "execution_model": execution_model,
        "positions_by_rebalance_live": positions_by_rebalance_live,
        "backtest_cost_bps_effective": BACKTEST_COST_BPS_EFFECTIVE,
        "backtest_trading_days_per_year": BACKTEST_TRADING_DAYS_PER_YEAR,
        "backtest_exit_mode": BACKTEST_EXIT_MODE,
        "backtest_exit_horizon_days": BACKTEST_EXIT_HORIZON_DAYS,
        "backtest_pricing_df": backtest_pricing_df,
        "backtest_exit_price_policy": BACKTEST_EXIT_PRICE_POLICY,
        "backtest_exit_fallback_policy": BACKTEST_EXIT_FALLBACK_POLICY,
        "benchmark_df": benchmark_df,
        "benchmark_return_series": benchmark_return_series,
        "exposure_source_df": df_full,
        "industry_source_df": industry_source_df,
        "fundamentals_mcap_col": FUNDAMENTALS_MCAP_COL,
        "industry_columns": list(dict.fromkeys(passthrough_cols + INDUSTRY_KEEP_COLUMNS)),
        "price_col": PRICE_COL,
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
        run_perm_test=PERM_TEST_ENABLED,
        perm_train_df=train_df,
        perm_test_df=test_df,
        allow_live_fallback=True,
    )

    ic_series = eval_main["ic_series"]
    ic_stats = eval_main["ic_stats"]
    pearson_ic_series = eval_main["pearson_ic_series"]
    pearson_ic_stats = eval_main["pearson_ic_stats"]
    error_metrics = eval_main["error_metrics"]
    hit_rate_stats = eval_main["hit_rate"]
    topk_positive_stats = eval_main["topk_positive_ratio"]
    bucket_ic_records = eval_main["bucket_ic"]
    quantile_ts = eval_main["quantile_ts"]
    quantile_mean = eval_main["quantile_mean"]
    turnover_series = eval_main["turnover_series"]
    eval_scored_data = eval_main["scored_data"]
    eval_rebalance_dates = eval_main["eval_rebalance_dates"]
    backtest_rebalance_dates = eval_main["backtest_rebalance_dates"]
    positions_by_rebalance = eval_main["positions_by_rebalance"]
    bt_stats = eval_main["bt_stats"]
    bt_net_series = eval_main["bt_net_series"]
    bt_gross_series = eval_main["bt_gross_series"]
    bt_turnover_series = eval_main["bt_turnover_series"]
    bt_benchmark_series = eval_main["bt_benchmark_series"]
    bt_active_series = eval_main["bt_active_series"]
    bt_benchmark_stats = eval_main["bt_benchmark_stats"]
    bt_active_stats = eval_main["bt_active_stats"]
    bt_periods = eval_main["bt_periods"]
    bt_style_exposure = eval_main["bt_style_exposure"]
    bt_style_exposure_summary = eval_main["bt_style_exposure_summary"]
    bt_industry_exposure = eval_main["bt_industry_exposure"]
    bt_industry_exposure_summary = eval_main["bt_industry_exposure_summary"]
    bt_active_exposure_summary = eval_main["bt_active_exposure_summary"]
    perm_stats = eval_main["perm_stats"]

    rolling_ic_results, rolling_ic_obs_per_year = _compute_rolling_ic(
        ic_series, ROLLING_WINDOWS_MONTHS
    )
    rolling_ic_latest = {
        label: _latest_rolling_stats(frame, ["ic_mean", "ic_ir"])
        for label, frame in rolling_ic_results.items()
    }
    rolling_sharpe_results = {}
    rolling_sharpe_latest = {}
    if bt_stats is not None and not bt_net_series.empty:
        periods_per_year = bt_stats.get("periods_per_year", np.nan)
        rolling_sharpe_results = _compute_rolling_sharpe(
            bt_net_series, ROLLING_WINDOWS_MONTHS, periods_per_year
        )
        rolling_sharpe_latest = {
            label: _latest_rolling_stats(frame, ["mean", "std", "sharpe"])
            for label, frame in rolling_sharpe_results.items()
        }

    if positions_by_rebalance is not None and not positions_by_rebalance.empty:
        positions_by_rebalance = _annotate_positions_window(positions_by_rebalance)
    if positions_by_rebalance_live is not None and not positions_by_rebalance_live.empty:
        positions_by_rebalance_live = _annotate_positions_window(positions_by_rebalance_live)
    positions_by_rebalance_path: Optional[Path] = None
    positions_current_path: Optional[Path] = None
    positions_by_rebalance_live_path: Optional[Path] = None
    positions_current_live_path: Optional[Path] = None
    positions_diff_path: Optional[Path] = None
    positions_diff_live_path: Optional[Path] = None

    cv_stats_raw = None
    cv_stats = None
    if cv_scores_raw:
        cv_stats_raw = {
            "mean": float(np.nanmean(cv_scores_raw)),
            "std": float(np.nanstd(cv_scores_raw)),
            "scores": [float(score) for score in cv_scores_raw],
        }
        if cv_scores_adj is None:
            cv_scores_adj = [float(score) * SIGNAL_DIRECTION for score in cv_scores_raw]
        cv_stats = {
            "mean": float(np.nanmean(cv_scores_adj)),
            "std": float(np.nanstd(cv_scores_adj)),
            "scores": [float(score) for score in cv_scores_adj],
        }

    walk_forward_results: list[dict] = []
    if WF_ENABLED:
        walk_forward_context = {
            "df_model_sorted": df_model_sorted,
            "all_date_start_rows": all_date_start_rows,
            "all_date_end_rows": all_date_end_rows,
            "all_date_to_pos": all_date_to_pos,
            "train_window_mode": TRAIN_WINDOW_MODE,
            "train_window_size": TRAIN_WINDOW_SIZE,
            "train_window_unit": TRAIN_WINDOW_UNIT,
            "signal_direction": SIGNAL_DIRECTION,
            "signal_direction_mode": SIGNAL_DIRECTION_MODE,
            "features": FEATURES,
            "target": TARGET,
            "n_splits": N_SPLITS,
            "embargo_steps": EMBARGO_STEPS,
            "purge_steps": PURGE_STEPS,
            "model_cfg": MODEL_CFG,
            "min_abs_ic_to_flip": MIN_ABS_IC_TO_FLIP,
            "sample_weight_mode": SAMPLE_WEIGHT_MODE,
            "sample_weight_params": SAMPLE_WEIGHT_PARAMS,
            "train_target": TRAIN_TARGET,
            "model_type": MODEL_TYPE,
            "model_params": MODEL_PARAMS,
            "report_train_ic": REPORT_TRAIN_IC,
            "sample_on_rebalance_dates": SAMPLE_ON_REBALANCE_DATES,
            "score_postprocess_method": SCORE_POSTPROCESS_METHOD,
            "score_postprocess_columns": SCORE_POSTPROCESS_COLUMNS,
            "score_postprocess_strength": SCORE_POSTPROCESS_STRENGTH,
            "score_postprocess_min_obs": SCORE_POSTPROCESS_MIN_OBS,
            "rebalance_frequency": REBALANCE_FREQUENCY,
            "valid_dates_set": valid_dates_set,
            "wf_perm_test_enabled": WF_PERM_TEST_ENABLED,
            "wf_perm_test_runs": WF_PERM_TEST_RUNS,
            "wf_perm_test_seed": WF_PERM_TEST_SEED,
            "n_quantiles": N_QUANTILES,
            "top_k": TOP_K,
            "eval_buffer_exit": EVAL_BUFFER_EXIT,
            "eval_buffer_entry": EVAL_BUFFER_ENTRY,
            "wf_backtest_enabled": WF_BACKTEST_ENABLED,
            "backtest_signal_direction_raw": BACKTEST_SIGNAL_DIRECTION_RAW,
            "df_full": df_full,
            "price_col": PRICE_COL,
            "backtest_rebalance_frequency": BACKTEST_REBALANCE_FREQUENCY,
            "label_shift_days": LABEL_SHIFT_DAYS,
            "backtest_cost_bps_effective": BACKTEST_COST_BPS_EFFECTIVE,
            "backtest_trading_days_per_year": BACKTEST_TRADING_DAYS_PER_YEAR,
            "backtest_exit_mode": BACKTEST_EXIT_MODE,
            "backtest_exit_horizon_days": BACKTEST_EXIT_HORIZON_DAYS,
            "backtest_long_only": BACKTEST_LONG_ONLY,
            "backtest_short_k": BACKTEST_SHORT_K,
            "backtest_buffer_exit": BACKTEST_BUFFER_EXIT,
            "backtest_buffer_entry": BACKTEST_BUFFER_ENTRY,
            "backtest_group_col": BACKTEST_GROUP_COL,
            "backtest_max_names_per_group": BACKTEST_MAX_NAMES_PER_GROUP,
            "backtest_tradable_col": BACKTEST_TRADABLE_COL,
            "backtest_exit_price_policy": BACKTEST_EXIT_PRICE_POLICY,
            "backtest_exit_fallback_policy": BACKTEST_EXIT_FALLBACK_POLICY,
            "execution_model": execution_model,
            "backtest_pricing_df": backtest_pricing_df,
            "benchmark_df": benchmark_df,
            "benchmark_return_series": benchmark_return_series,
            "backtest_top_k": BACKTEST_TOP_K,
            "wf_feature_top_k": WF_FEATURE_TOP_K,
            "backtest_topk_fn": backtest_topk_fn,
        }
        try:
            wf_test_size = float(WF_TEST_SIZE)
        except (TypeError, ValueError):
            wf_test_size = TEST_SIZE
        windows = build_walk_forward_windows(
            all_dates,
            wf_test_size,
            WF_N_WINDOWS,
            WF_STEP_SIZE,
            EFFECTIVE_GAP_STEPS,
            WF_ANCHOR_END,
        )
        if not windows:
            logger.info("Walk-forward evaluation skipped: insufficient windows.")
        else:
            if len(windows) < WF_N_WINDOWS:
                logger.warning(
                    "Walk-forward requested %s windows but only %s fit "
                    "(test_size=%s, step_size=%s, anchor_end=%s). "
                    "Reduce eval.test_size / eval.walk_forward.test_size, "
                    "set a smaller eval.walk_forward.step_size, or lower n_windows.",
                    WF_N_WINDOWS,
                    len(windows),
                    wf_test_size,
                    WF_STEP_SIZE,
                    WF_ANCHOR_END,
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
        WF_FEATURE_TOP_K,
    )

    final_oos_eval = None
    ic_series_oos = pd.Series(dtype=float, name="ic")
    ic_stats_oos = {}
    pearson_ic_series_oos = pd.Series(dtype=float, name="ic_pearson")
    pearson_ic_stats_oos = {}
    error_metrics_oos = {}
    hit_rate_stats_oos = {}
    topk_positive_stats_oos = {}
    bucket_ic_records_oos = []
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
    bt_periods_oos: list[dict] = []
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
    positions_by_rebalance_oos_path: Optional[Path] = None
    positions_current_oos_path: Optional[Path] = None
    positions_diff_oos_path: Optional[Path] = None
    if FINAL_OOS_ENABLED and final_oos_dates.size > 0:
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
            final_model = build_model(MODEL_TYPE, MODEL_PARAMS)
            (
                df_oos_train,
                _,
            ) = _slice_with_train_window(
                df_model_sorted,
                all_date_start_rows,
                all_date_end_rows,
                all_date_to_pos,
                all_dates,
                label="final_oos fit",
                train_window_mode=TRAIN_WINDOW_MODE,
                train_window_size=TRAIN_WINDOW_SIZE,
                train_window_unit=TRAIN_WINDOW_UNIT,
            )
            if df_oos_train.empty:
                logger.info("Final OOS evaluation skipped: model.train_window left no in-sample data.")
            else:
                final_weights = build_sample_weight(
                    df_oos_train,
                    SAMPLE_WEIGHT_MODE,
                    params=SAMPLE_WEIGHT_PARAMS,
                )
                fit_model(
                    final_model,
                    MODEL_TYPE,
                    df_oos_train,
                    features=FEATURES,
                    target_col=TRAIN_TARGET,
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
            ic_series_oos, ROLLING_WINDOWS_MONTHS
        )
        rolling_ic_latest_oos = {
            label: _latest_rolling_stats(frame, ["ic_mean", "ic_ir"])
            for label, frame in rolling_ic_oos_results.items()
        }
        if bt_stats_oos is not None and not bt_net_series_oos.empty:
            periods_per_year_oos = bt_stats_oos.get("periods_per_year", np.nan)
            rolling_sharpe_oos_results = _compute_rolling_sharpe(
                bt_net_series_oos, ROLLING_WINDOWS_MONTHS, periods_per_year_oos
            )
            rolling_sharpe_latest_oos = {
                label: _latest_rolling_stats(frame, ["mean", "std", "sharpe"])
                for label, frame in rolling_sharpe_oos_results.items()
            }

    # Feature importance
    logger.info("Feature importance:")
    importance_df, importance_source = feature_importance_frame(model, FEATURES)
    logger.info("Feature importance source: %s", importance_source)
    for _, row in importance_df.iterrows():
        logger.info("  %-20s: %.4f", row["feature"], float(row["importance"]))

    pred_nunique: Optional[int] = None
    constant_prediction: Optional[bool] = None
    if eval_scored_data is not None and not eval_scored_data.empty and "pred" in eval_scored_data.columns:
        pred_nunique = int(eval_scored_data["pred"].nunique(dropna=True))
        constant_prediction = pred_nunique <= 1

    feature_importance_nonzero: Optional[int] = None
    zero_feature_importance: Optional[bool] = None
    if not importance_df.empty and "importance" in importance_df.columns:
        importance_values = pd.to_numeric(importance_df["importance"], errors="coerce").fillna(0.0)
        feature_importance_nonzero = int((importance_values.abs() > 0.0).sum())
        zero_feature_importance = feature_importance_nonzero == 0

    output_context = _build_output_context(
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
        extras={
            "MARKET": MARKET,
            "provider": provider,
            "quality_summary": quality_summary,
            "benchmark_symbol": benchmark_symbol,
            "benchmark_returns_file_path": benchmark_returns_file_path,
            "train_ic_raw_stats": train_ic_raw_stats,
            "train_ic_series": train_ic_series,
            "train_ic_stats": train_ic_stats,
            "train_pearson_ic_series": train_pearson_ic_series,
            "train_pearson_ic_stats": train_pearson_ic_stats,
            "live_as_of": live_as_of,
            "positions_by_rebalance_live": positions_by_rebalance_live,
            "BACKTEST_SIGNAL_DIRECTION": BACKTEST_SIGNAL_DIRECTION,
            "ic_series": ic_series,
            "ic_stats": ic_stats,
            "pearson_ic_series": pearson_ic_series,
            "pearson_ic_stats": pearson_ic_stats,
            "error_metrics": error_metrics,
            "hit_rate_stats": hit_rate_stats,
            "topk_positive_stats": topk_positive_stats,
            "bucket_ic_records": bucket_ic_records,
            "quantile_ts": quantile_ts,
            "quantile_mean": quantile_mean,
            "turnover_series": turnover_series,
            "eval_scored_data": eval_scored_data,
            "eval_rebalance_dates": eval_rebalance_dates,
            "backtest_rebalance_dates": backtest_rebalance_dates,
            "positions_by_rebalance": positions_by_rebalance,
            "bt_stats": bt_stats,
            "bt_net_series": bt_net_series,
            "bt_gross_series": bt_gross_series,
            "bt_turnover_series": bt_turnover_series,
            "bt_benchmark_series": bt_benchmark_series,
            "bt_active_series": bt_active_series,
            "bt_benchmark_stats": bt_benchmark_stats,
            "bt_active_stats": bt_active_stats,
            "bt_periods": bt_periods,
            "bt_style_exposure": bt_style_exposure,
            "bt_style_exposure_summary": bt_style_exposure_summary,
            "bt_industry_exposure": bt_industry_exposure,
            "bt_industry_exposure_summary": bt_industry_exposure_summary,
            "bt_active_exposure_summary": bt_active_exposure_summary,
            "perm_stats": perm_stats,
            "rolling_ic_results": rolling_ic_results,
            "rolling_ic_obs_per_year": rolling_ic_obs_per_year,
            "rolling_ic_latest": rolling_ic_latest,
            "rolling_sharpe_results": rolling_sharpe_results,
            "rolling_sharpe_latest": rolling_sharpe_latest,
            "cv_stats_raw": cv_stats_raw,
            "cv_stats": cv_stats,
            "walk_forward_results": walk_forward_results,
            "walk_forward_importance_df": walk_forward_importance_df,
            "walk_forward_feature_stability_df": walk_forward_feature_stability_df,
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
            "importance_df": importance_df,
            "importance_source": importance_source,
            "pred_nunique": pred_nunique,
            "constant_prediction": constant_prediction,
            "feature_importance_nonzero": feature_importance_nonzero,
            "zero_feature_importance": zero_feature_importance,
        },
    )
    persist_run_outputs(context=output_context)

    # Optional: save the model
    # from joblib import dump; dump(model, "xgb_factor_model.joblib")


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
            "Optional artifacts root override. When omitted, the pipeline uses paths.artifacts_root, "
            "CSML_ARTIFACTS_ROOT, or the default artifacts/."
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
