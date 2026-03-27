"""Pipeline runner for the HK + RQData workflow.
Usage:
    $ csml run
    $ csml run --config configs/presets/default.yml
    $ csml run --config hk
    # rqdatac auth may be required (RQDATA_USERNAME/RQDATA_PASSWORD)
"""
import argparse
import logging
import sys
from collections.abc import Mapping
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any

import numpy as np
# Workaround for pandas_ta NaN import issue
if not hasattr(np, "NaN"):
    np.NaN = np.nan
import pandas as pd
import pandas_ta as ta
import pyarrow  # ensures parquet support
from dotenv import load_dotenv
import yaml
import warnings

from ..artifacts import (
    CACHE_DIR as DEFAULT_CACHE_DIR,
    RUNS_DIR as DEFAULT_RUNS_DIR,
    resolve_repo_path,
)
from ..config_utils import resolve_pipeline_config
from ..date_utils import (
    is_relative_date_token as _is_relative_date_token,
    resolve_date_token as _resolve_date_token,
)
from ..data_interface import DataInterface
from ..data_providers import (
    fundamentals_provider_supported,
    normalize_market,
    resolve_provider,
)
from ..data_tools.symbols import (
    ensure_symbol_columns,
)
from ..dataset import DatasetSchema, build_dataset
from ..execution import (
    BpsCostModel,
    build_execution_model,
    describe_execution_model,
    required_pricing_columns,
)
from ..metrics import (
    bucket_ic_summary,
    daily_ic_series,
    summarize_ic,
)
from ..transform import apply_cross_sectional_series_transform, apply_cross_sectional_transform
from ..split import build_sample_weight, time_series_cv_ic
from ..modeling import build_model, fit_model, resolve_model_spec, feature_importance_frame
from ..backtest import backtest_topk
from .support import (
    _annotate_positions_window,
    _build_rebalance_diff,
    _ensure_symbol_alias,
    _parse_window_config,
    _prepare_panel_join_frame,
    _select_panel_join_columns,
    _summarize_walk_forward_feature_stability,
    apply_universe_by_date,
    load_symbols_file,
    load_universe_by_date,
    normalize_symbol_list,
    parse_feature_windows,
    save_frame,
    save_json,
    save_parquet,
    save_series,
)
from .dates import (
    _apply_model_train_window,
    _build_trade_date_slices,
    _slice_trade_date_range,
    _slice_trade_dates,
    _slice_with_train_window,
    build_walk_forward_windows,
)
from .data import _load_research_panel, _prepare_feature_dataset
from .eval import (
    _evaluate_period,
    _evaluate_walk_forward_window,
    _warn_if_delay_exit_lag,
    build_benchmark_series,
)
from .live import _prepare_live_snapshot
from .runtime import _prepare_split_context, config_hash, setup_logging
from .stats import (
    _compute_rolling_ic,
    _compute_rolling_sharpe,
    _ensure_execution_daily_fields,
    _latest_rolling_stats,
    _normalize_bucket_schemes,
    _normalize_window_months,
    _warn_if_purge_too_small,
)
from ..rebalance import estimate_rebalance_gap, get_rebalance_dates

warnings.filterwarnings("ignore")

logger = logging.getLogger("csml")


def run(config_ref: str | Path | None = None) -> None:
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
    resolved = resolve_pipeline_config(config_ref)
    config = resolved.data
    config_label = resolved.label
    config_path = resolved.path
    config_source = resolved.source
    active_log_file = setup_logging(config)

    data_cfg = config.get("data", {})
    MARKET = normalize_market(config.get("market") or data_cfg.get("market"))
    universe_cfg = config.get("universe", {})
    label_cfg = config.get("label", {})
    features_cfg = config.get("features", {})
    fundamentals_cfg = config.get("fundamentals", {})
    model_cfg = config.get("model", {})
    eval_cfg = config.get("eval", {})
    backtest_cfg = config.get("backtest", {})
    live_cfg = config.get("live", {})
    if not isinstance(model_cfg, dict):
        sys.exit("model must be a mapping with keys: type, params, sample_weight_mode.")
    if not isinstance(live_cfg, dict):
        live_cfg = {}

    load_dotenv()
    CACHE_DIR = resolve_repo_path(
        data_cfg.get("cache_dir", DEFAULT_CACHE_DIR.as_posix())
    )
    data_interface = DataInterface(MARKET, data_cfg, cache_dir=CACHE_DIR, logger=logger)
    provider = data_interface.provider

    DEFAULT_SYMBOLS = [
        "00700.HK",
        "00005.HK",
        "00941.HK",
        "00001.HK",
        "00388.HK",
    ]

    UNIVERSE_MODE = str(universe_cfg.get("mode", "auto")).strip().lower()
    if UNIVERSE_MODE not in {"auto", "pit", "static"}:
        sys.exit("universe.mode must be one of: auto, pit, static.")
    REQUIRE_BY_DATE = bool(universe_cfg.get("require_by_date", False))

    symbols = normalize_symbol_list(universe_cfg.get("symbols"))
    symbols_file = universe_cfg.get("symbols_file")
    by_date_file = universe_cfg.get("by_date_file")
    universe_by_date = None
    universe_mode_effective = UNIVERSE_MODE

    if not symbols and symbols_file:
        symbols = load_symbols_file(Path(symbols_file))

    if by_date_file:
        universe_by_date = load_universe_by_date(
            resolve_repo_path(by_date_file),
            MARKET,
        )
        symbols_from_universe = sorted(universe_by_date["symbol"].unique().tolist())
        if symbols:
            symbols = sorted(set(symbols) | set(symbols_from_universe))
        else:
            symbols = symbols_from_universe
        universe_mode_effective = "pit"
        if UNIVERSE_MODE == "static":
            logger.warning("universe.mode=static but by_date_file provided; using PIT universe.")
    else:
        if REQUIRE_BY_DATE or UNIVERSE_MODE == "pit":
            sys.exit("universe.by_date_file is required when universe.mode=pit or require_by_date=true.")
        universe_mode_effective = "static"
        if UNIVERSE_MODE == "auto":
            logger.warning(
                "Universe-by-date not provided; using static symbols (survivorship bias). "
                "Set universe.mode=static to acknowledge or provide by_date_file for PIT."
            )

    if not symbols:
        symbols = DEFAULT_SYMBOLS

    if not symbols:
        sys.exit("No symbols configured.")

    end_date_cfg = data_cfg.get("end_date", "today")
    if _is_relative_date_token(end_date_cfg) and not bool(live_cfg.get("enabled", False)):
        logger.warning(
            "data.end_date=%s is a relative token; prefer a fixed YYYYMMDD date for reproducibility.",
            end_date_cfg,
        )
    end_date = _resolve_date_token(end_date_cfg, default="today", market=MARKET, provider=provider)

    start_date_cfg = data_cfg.get("start_date")
    if start_date_cfg:
        start_date = datetime.strptime(str(start_date_cfg), "%Y%m%d")
    else:
        start_years = float(data_cfg.get("start_years", 5))
        start_date = end_date - timedelta(days=int(start_years * 365))

    START_DATE = start_date.strftime("%Y%m%d")
    END_DATE = end_date.strftime("%Y%m%d")

    PRICE_COL = data_cfg.get("price_col", "close")

    LABEL_HORIZON_DAYS = int(label_cfg.get("horizon_days", 5))
    LABEL_SHIFT_DAYS = int(label_cfg.get("shift_days", 0))
    LABEL_HORIZON_MODE = str(label_cfg.get("horizon_mode", "fixed")).strip().lower()
    if LABEL_HORIZON_MODE not in {"fixed", "next_rebalance"}:
        sys.exit("label.horizon_mode must be one of: fixed, next_rebalance.")
    LABEL_REBALANCE_FREQUENCY = label_cfg.get("rebalance_frequency", eval_cfg.get("rebalance_frequency", "M"))
    TARGET = label_cfg.get("target_col", "future_return")
    TRAIN_TARGET_TRANSFORM = str(label_cfg.get("train_target_transform", "none")).strip().lower()
    if TRAIN_TARGET_TRANSFORM not in {"none", "zscore", "rank"}:
        sys.exit("label.train_target_transform must be one of: none, zscore, rank.")
    TRAIN_TARGET = TARGET if TRAIN_TARGET_TRANSFORM == "none" else f"{TARGET}__train_target"
    WINSORIZE_PCT = label_cfg.get("winsorize_pct")
    if WINSORIZE_PCT is not None:
        WINSORIZE_PCT = float(WINSORIZE_PCT)
        if not 0 < WINSORIZE_PCT < 0.5:
            sys.exit("winsorize_pct must be between 0 and 0.5.")

    TEST_SIZE = float(eval_cfg.get("test_size", 0.2))
    N_SPLITS = int(eval_cfg.get("n_splits", 5))
    N_QUANTILES = int(eval_cfg.get("n_quantiles", 5))
    TOP_K = int(eval_cfg.get("top_k", 20))
    REBALANCE_FREQUENCY = eval_cfg.get("rebalance_frequency", "W")
    TRANSACTION_COST_BPS = float(eval_cfg.get("transaction_cost_bps", 10))
    EVAL_BUFFER_EXIT = int(eval_cfg.get("buffer_exit", backtest_cfg.get("buffer_exit", 0) if isinstance(backtest_cfg, dict) else 0))
    EVAL_BUFFER_ENTRY = int(eval_cfg.get("buffer_entry", backtest_cfg.get("buffer_entry", 0) if isinstance(backtest_cfg, dict) else 0))
    SIGNAL_DIRECTION_MODE = str(eval_cfg.get("signal_direction_mode", "fixed")).strip().lower()
    if SIGNAL_DIRECTION_MODE not in {"fixed", "train_ic", "cv_ic"}:
        sys.exit("eval.signal_direction_mode must be one of: fixed, train_ic, cv_ic.")
    SIGNAL_DIRECTION_RAW = eval_cfg.get("signal_direction", 1.0)
    SIGNAL_DIRECTION = float(SIGNAL_DIRECTION_RAW) if SIGNAL_DIRECTION_RAW is not None else 1.0
    if SIGNAL_DIRECTION == 0:
        sys.exit("eval.signal_direction cannot be 0.")
    MIN_ABS_IC_TO_FLIP_RAW = eval_cfg.get("min_abs_ic_to_flip", 0.0)
    MIN_ABS_IC_TO_FLIP = float(MIN_ABS_IC_TO_FLIP_RAW) if MIN_ABS_IC_TO_FLIP_RAW is not None else 0.0
    if MIN_ABS_IC_TO_FLIP < 0:
        sys.exit("eval.min_abs_ic_to_flip must be >= 0.")
    EMBARGO_DAYS_RAW = eval_cfg.get("embargo_days")
    EMBARGO_DAYS_CFG = int(EMBARGO_DAYS_RAW) if EMBARGO_DAYS_RAW is not None else 0
    PURGE_DAYS_RAW = eval_cfg.get("purge_days")
    PURGE_DAYS_CFG = int(PURGE_DAYS_RAW) if PURGE_DAYS_RAW is not None else None
    PURGE_STEPS = None
    EMBARGO_STEPS = None
    EFFECTIVE_GAP_STEPS = None
    REPORT_TRAIN_IC = bool(eval_cfg.get("report_train_ic", True))
    SAMPLE_ON_REBALANCE_DATES = bool(eval_cfg.get("sample_on_rebalance_dates", False))
    rolling_cfg = eval_cfg.get("rolling") if isinstance(eval_cfg, dict) else None
    if isinstance(rolling_cfg, dict):
        rolling_enabled = bool(rolling_cfg.get("enabled", True))
        if rolling_enabled:
            ROLLING_WINDOWS_MONTHS = _normalize_window_months(
                rolling_cfg.get("windows_months"), [6, 12]
            )
        else:
            ROLLING_WINDOWS_MONTHS = []
    else:
        ROLLING_WINDOWS_MONTHS = _normalize_window_months(rolling_cfg, [6, 12])

    bucket_ic_cfg = eval_cfg.get("bucket_ic") if isinstance(eval_cfg, dict) else None
    BUCKET_IC_ENABLED = False
    BUCKET_IC_METHOD = "spearman"
    BUCKET_IC_MIN_COUNT = 0
    BUCKET_IC_SCHEMES = []
    if isinstance(bucket_ic_cfg, dict):
        BUCKET_IC_ENABLED = bool(bucket_ic_cfg.get("enabled", False))
        BUCKET_IC_METHOD = str(bucket_ic_cfg.get("method", "spearman")).strip().lower()
        BUCKET_IC_MIN_COUNT = int(bucket_ic_cfg.get("min_count", 0) or 0)
        BUCKET_IC_SCHEMES = _normalize_bucket_schemes(bucket_ic_cfg.get("schemes"))
    elif bucket_ic_cfg is not None:
        BUCKET_IC_ENABLED = bool(bucket_ic_cfg)
    if BUCKET_IC_METHOD not in {"spearman", "pearson"}:
        sys.exit("eval.bucket_ic.method must be one of: spearman, pearson.")
    if BUCKET_IC_ENABLED and not BUCKET_IC_SCHEMES:
        logger.warning("eval.bucket_ic.enabled=true but no schemes configured.")
    perm_cfg = eval_cfg.get("permutation_test") or {}
    if isinstance(perm_cfg, dict):
        PERM_TEST_ENABLED = bool(perm_cfg.get("enabled", False))
        PERM_TEST_RUNS = int(perm_cfg.get("n_runs", 1))
        PERM_TEST_SEED = perm_cfg.get("seed")
    else:
        PERM_TEST_ENABLED = bool(perm_cfg)
        PERM_TEST_RUNS = 1
        PERM_TEST_SEED = None
    if PERM_TEST_SEED is not None:
        PERM_TEST_SEED = int(PERM_TEST_SEED)
    if PERM_TEST_RUNS < 1:
        PERM_TEST_ENABLED = False

    wf_cfg = eval_cfg.get("walk_forward") or {}
    if isinstance(wf_cfg, dict):
        WF_ENABLED = bool(wf_cfg.get("enabled", False))
        WF_N_WINDOWS = int(wf_cfg.get("n_windows", 3))
        WF_TEST_SIZE = wf_cfg.get("test_size", TEST_SIZE)
        WF_STEP_SIZE = wf_cfg.get("step_size")
        WF_ANCHOR_END = bool(wf_cfg.get("anchor_end", True))
        WF_FEATURE_TOP_K = int(wf_cfg.get("feature_top_k", 5))
        WF_BACKTEST_ENABLED = bool(wf_cfg.get("backtest_enabled", backtest_cfg.get("enabled", True)))
        wf_perm_cfg = wf_cfg.get("permutation_test")
        if isinstance(wf_perm_cfg, dict):
            WF_PERM_TEST_ENABLED = bool(wf_perm_cfg.get("enabled", False))
            WF_PERM_TEST_RUNS = int(wf_perm_cfg.get("n_runs", PERM_TEST_RUNS))
            WF_PERM_TEST_SEED = wf_perm_cfg.get("seed", PERM_TEST_SEED)
        elif wf_perm_cfg is None:
            WF_PERM_TEST_ENABLED = False
            WF_PERM_TEST_RUNS = PERM_TEST_RUNS
            WF_PERM_TEST_SEED = PERM_TEST_SEED
        else:
            WF_PERM_TEST_ENABLED = bool(wf_perm_cfg)
            WF_PERM_TEST_RUNS = PERM_TEST_RUNS
            WF_PERM_TEST_SEED = PERM_TEST_SEED
    else:
        WF_ENABLED = bool(wf_cfg)
        WF_N_WINDOWS = 3
        WF_TEST_SIZE = TEST_SIZE
        WF_STEP_SIZE = None
        WF_ANCHOR_END = True
        WF_FEATURE_TOP_K = 5
        WF_BACKTEST_ENABLED = bool(backtest_cfg.get("enabled", True))
        WF_PERM_TEST_ENABLED = False
        WF_PERM_TEST_RUNS = PERM_TEST_RUNS
        WF_PERM_TEST_SEED = PERM_TEST_SEED
    if WF_PERM_TEST_SEED is not None:
        WF_PERM_TEST_SEED = int(WF_PERM_TEST_SEED)
    if WF_PERM_TEST_RUNS < 1:
        WF_PERM_TEST_ENABLED = False
    if WF_FEATURE_TOP_K < 1:
        sys.exit("eval.walk_forward.feature_top_k must be >= 1.")

    final_oos_cfg = eval_cfg.get("final_oos")
    FINAL_OOS_SIZE_RAW = None
    if isinstance(final_oos_cfg, dict):
        FINAL_OOS_SIZE_RAW = final_oos_cfg.get("size")
        FINAL_OOS_ENABLED = bool(final_oos_cfg.get("enabled", False) or FINAL_OOS_SIZE_RAW)
    elif final_oos_cfg is None:
        FINAL_OOS_ENABLED = False
    else:
        FINAL_OOS_SIZE_RAW = final_oos_cfg
        FINAL_OOS_ENABLED = bool(final_oos_cfg)

    SAVE_ARTIFACTS = bool(eval_cfg.get("save_artifacts", True))
    SAVE_SCORED_ARTIFACT = bool(eval_cfg.get("save_scored_artifact", False))
    SAVE_DATASET = bool(eval_cfg.get("save_dataset", False))
    OUTPUT_DIR = eval_cfg.get("output_dir", DEFAULT_RUNS_DIR.as_posix())
    RUN_NAME = eval_cfg.get("run_name")
    if SAVE_SCORED_ARTIFACT and not SAVE_ARTIFACTS:
        raise SystemExit("eval.save_scored_artifact=true requires eval.save_artifacts=true.")
    if SAVE_DATASET and not SAVE_ARTIFACTS:
        raise SystemExit("eval.save_dataset=true requires eval.save_artifacts=true.")

    MIN_SYMBOLS_PER_DATE = int(universe_cfg.get("min_symbols_per_date", N_QUANTILES))
    MIN_LISTED_DAYS = int(universe_cfg.get("min_listed_days", 0))
    MIN_TURNOVER = float(universe_cfg.get("min_turnover", 0))
    DROP_ST = bool(universe_cfg.get("drop_st", False))
    DROP_SUSPENDED = bool(universe_cfg.get("drop_suspended", True))
    SUSPENDED_POLICY = str(universe_cfg.get("suspended_policy", "mark")).strip().lower()
    if SUSPENDED_POLICY not in {"mark", "filter"}:
        sys.exit("universe.suspended_policy must be one of: mark, filter.")
    if MIN_SYMBOLS_PER_DATE < N_QUANTILES:
        MIN_SYMBOLS_PER_DATE = N_QUANTILES

    fundamentals_cfg = fundamentals_cfg if isinstance(fundamentals_cfg, dict) else {}
    FUNDAMENTALS_ENABLED = bool(fundamentals_cfg.get("enabled", False))
    FUNDAMENTALS_SOURCE = str(fundamentals_cfg.get("source", "provider")).strip().lower()
    if FUNDAMENTALS_SOURCE not in {"provider", "file"}:
        sys.exit("fundamentals.source must be one of: provider, file.")
    FUNDAMENTALS_FILE = fundamentals_cfg.get("file")
    FUNDAMENTALS_FEATURES = normalize_symbol_list(fundamentals_cfg.get("features"))
    FUNDAMENTALS_AUTO_ADD = bool(fundamentals_cfg.get("auto_add_features", True))
    FUNDAMENTALS_ALLOW_MISSING = bool(fundamentals_cfg.get("allow_missing_features", False))
    FUNDAMENTALS_FFILL = bool(fundamentals_cfg.get("ffill", True))
    FUNDAMENTALS_FFILL_LIMIT = fundamentals_cfg.get("ffill_limit")
    if FUNDAMENTALS_FFILL_LIMIT is not None:
        FUNDAMENTALS_FFILL_LIMIT = int(FUNDAMENTALS_FFILL_LIMIT)
    FUNDAMENTALS_LOG_MCAP = bool(fundamentals_cfg.get("log_market_cap", False))
    FUNDAMENTALS_MCAP_COL = str(fundamentals_cfg.get("market_cap_col", "market_cap")).strip()
    FUNDAMENTALS_LOG_MCAP_COL = str(fundamentals_cfg.get("log_market_cap_col", "log_mcap")).strip()
    FUNDAMENTALS_REQUIRED = bool(fundamentals_cfg.get("required", False))
    FUNDAMENTALS_PROVIDER = (
        resolve_provider({"provider": fundamentals_cfg.get("provider")})
        if fundamentals_cfg.get("provider")
        else provider
    )
    provider_overlay_cfg = fundamentals_cfg.get("provider_overlay")
    if provider_overlay_cfg is None:
        provider_overlay_cfg = {}
    if not isinstance(provider_overlay_cfg, Mapping):
        sys.exit("fundamentals.provider_overlay must be a mapping when provided.")
    FUNDAMENTALS_PROVIDER_OVERLAY_ENABLED = bool(provider_overlay_cfg.get("enabled", False))
    FUNDAMENTALS_PROVIDER_OVERLAY_SOURCE = str(
        provider_overlay_cfg.get("source", "provider")
    ).strip().lower()
    if FUNDAMENTALS_PROVIDER_OVERLAY_SOURCE not in {"provider"}:
        sys.exit("fundamentals.provider_overlay.source must be 'provider'.")
    FUNDAMENTALS_PROVIDER_OVERLAY_FEATURES = normalize_symbol_list(
        provider_overlay_cfg.get("features")
    )
    FUNDAMENTALS_PROVIDER_OVERLAY_AUTO_ADD = bool(
        provider_overlay_cfg.get("auto_add_features", True)
    )
    FUNDAMENTALS_PROVIDER_OVERLAY_REQUIRED = bool(
        provider_overlay_cfg.get("required", False)
    )
    FUNDAMENTALS_PROVIDER_OVERLAY_PROVIDER = (
        resolve_provider({"provider": provider_overlay_cfg.get("provider")})
        if provider_overlay_cfg.get("provider")
        else provider
    )
    industry_cfg = config.get("industry")
    if industry_cfg is None:
        industry_cfg = {}
    if not isinstance(industry_cfg, Mapping):
        sys.exit("industry must be a mapping when provided.")
    INDUSTRY_ENABLED = bool(industry_cfg.get("enabled", False))
    INDUSTRY_SOURCE = str(industry_cfg.get("source", "file")).strip().lower()
    if INDUSTRY_SOURCE not in {"file"}:
        sys.exit("industry.source must be 'file'.")
    INDUSTRY_FILE = industry_cfg.get("file")
    INDUSTRY_KEEP_COLUMNS = normalize_symbol_list(industry_cfg.get("keep_columns"))
    INDUSTRY_FFILL = bool(industry_cfg.get("ffill", False))
    INDUSTRY_FFILL_LIMIT = industry_cfg.get("ffill_limit")
    if INDUSTRY_FFILL_LIMIT is not None:
        INDUSTRY_FFILL_LIMIT = int(INDUSTRY_FFILL_LIMIT)
    INDUSTRY_REQUIRED = bool(industry_cfg.get("required", False))

    feature_list = features_cfg.get("list") or []
    FEATURES = normalize_symbol_list(feature_list) if feature_list else [
        "sma_20",
        "sma_60",
        "sma_120",
        "sma_5_diff",
        "sma_10_diff",
        "sma_20_diff",
        "sma_60_diff",
        "sma_120_diff",
        "rsi_7",
        "rsi_14",
        "rsi_21",
        "macd_hist",
        "ret_5",
        "ret_20",
        "ret_60",
        "rv_20",
        "rv_60",
        "volume_sma5_ratio",
        "volume_sma20_ratio",
        "volume_sma60_ratio",
        "log_vol",
        "vol",
    ]
    if FUNDAMENTALS_ENABLED and FUNDAMENTALS_AUTO_ADD and FUNDAMENTALS_FEATURES:
        FEATURES = list(dict.fromkeys(FEATURES + FUNDAMENTALS_FEATURES))
    if (
        FUNDAMENTALS_PROVIDER_OVERLAY_ENABLED
        and FUNDAMENTALS_PROVIDER_OVERLAY_AUTO_ADD
        and FUNDAMENTALS_PROVIDER_OVERLAY_FEATURES
    ):
        FEATURES = list(
            dict.fromkeys(FEATURES + FUNDAMENTALS_PROVIDER_OVERLAY_FEATURES)
        )
    WF_FEATURE_TOP_K = min(WF_FEATURE_TOP_K, max(1, len(FEATURES)))
    feature_params = features_cfg.get("params", {})
    cs_cfg = features_cfg.get("cross_sectional") or {}
    CS_METHOD = str(cs_cfg.get("method", "none")).strip().lower() if isinstance(cs_cfg, dict) else "none"
    CS_WINSORIZE_PCT = cs_cfg.get("winsorize_pct") if isinstance(cs_cfg, dict) else None
    if CS_WINSORIZE_PCT is not None:
        CS_WINSORIZE_PCT = float(CS_WINSORIZE_PCT)
        if not 0 < CS_WINSORIZE_PCT < 0.5:
            sys.exit("features.cross_sectional.winsorize_pct must be between 0 and 0.5.")
    if CS_METHOD not in {"none", "zscore", "rank"}:
        sys.exit("features.cross_sectional.method must be one of: none, zscore, rank.")
    missing_cfg = features_cfg.get("missing")
    if missing_cfg is None:
        missing_cfg = {}
    if not isinstance(missing_cfg, dict):
        sys.exit("features.missing must be a mapping when provided.")
    FEATURE_MISSING_METHOD = str(missing_cfg.get("method", "none")).strip().lower()
    if FEATURE_MISSING_METHOD not in {"none", "zero", "cross_sectional_median"}:
        sys.exit(
            "features.missing.method must be one of: none, zero, cross_sectional_median."
        )
    FEATURE_MISSING_FEATURES = normalize_symbol_list(missing_cfg.get("features"))
    FEATURE_MISSING_ADD_INDICATORS = bool(missing_cfg.get("add_indicators", False))
    FEATURE_MISSING_SUFFIX = str(missing_cfg.get("indicator_suffix", "_missing")).strip()
    if FEATURE_MISSING_ADD_INDICATORS and not FEATURE_MISSING_SUFFIX:
        sys.exit("features.missing.indicator_suffix cannot be empty.")

    try:
        MODEL_TYPE, MODEL_PARAMS = resolve_model_spec(model_cfg)
    except ValueError as exc:
        sys.exit(str(exc))
    MODEL_CFG = {"type": MODEL_TYPE, "params": MODEL_PARAMS}
    SAMPLE_WEIGHT_MODE = str(model_cfg.get("sample_weight_mode", "none")).strip().lower()
    SAMPLE_WEIGHT_PARAMS_RAW = model_cfg.get("sample_weight_params")
    if SAMPLE_WEIGHT_PARAMS_RAW is None:
        SAMPLE_WEIGHT_PARAMS = {}
    elif isinstance(SAMPLE_WEIGHT_PARAMS_RAW, Mapping):
        SAMPLE_WEIGHT_PARAMS = dict(SAMPLE_WEIGHT_PARAMS_RAW)
    else:
        sys.exit("model.sample_weight_params must be a mapping when provided.")
    if SAMPLE_WEIGHT_MODE in {"", "none", "null"}:
        SAMPLE_WEIGHT_MODE = "none"
    if SAMPLE_WEIGHT_MODE in {"date"}:
        SAMPLE_WEIGHT_MODE = "date_equal"
    if SAMPLE_WEIGHT_MODE in {"time_decay", "exp_decay", "exp"}:
        SAMPLE_WEIGHT_MODE = "exp_decay"
    if SAMPLE_WEIGHT_MODE not in {"none", "date_equal", "exp_decay"}:
        sys.exit("model.sample_weight_mode must be one of: none, date_equal, exp_decay.")
    if SAMPLE_WEIGHT_MODE == "exp_decay":
        halflife_raw = SAMPLE_WEIGHT_PARAMS.get("halflife", SAMPLE_WEIGHT_PARAMS.get("half_life"))
        decay_rate_raw = SAMPLE_WEIGHT_PARAMS.get("decay_rate", SAMPLE_WEIGHT_PARAMS.get("rate"))
        if halflife_raw is None and decay_rate_raw is None:
            sys.exit(
                "model.sample_weight_mode=exp_decay requires "
                "model.sample_weight_params.halflife or decay_rate."
            )
        if halflife_raw is not None:
            try:
                halflife = float(halflife_raw)
            except (TypeError, ValueError):
                sys.exit("model.sample_weight_params.halflife must be a number.")
            if not np.isfinite(halflife) or halflife <= 0:
                sys.exit("model.sample_weight_params.halflife must be > 0.")
        if decay_rate_raw is not None:
            try:
                decay_rate = float(decay_rate_raw)
            except (TypeError, ValueError):
                sys.exit("model.sample_weight_params.decay_rate must be a number.")
            if not np.isfinite(decay_rate) or decay_rate <= 0 or decay_rate > 1:
                sys.exit("model.sample_weight_params.decay_rate must be in (0, 1].")
        min_weight_raw = SAMPLE_WEIGHT_PARAMS.get("min_weight")
        if min_weight_raw is not None:
            try:
                min_weight = float(min_weight_raw)
            except (TypeError, ValueError):
                sys.exit("model.sample_weight_params.min_weight must be a number.")
            if not np.isfinite(min_weight) or min_weight < 0:
                sys.exit("model.sample_weight_params.min_weight must be >= 0.")

    train_window_cfg = model_cfg.get("train_window")
    if train_window_cfg is None:
        train_window_cfg = {}
    if not isinstance(train_window_cfg, Mapping):
        sys.exit("model.train_window must be a mapping when provided.")
    TRAIN_WINDOW_MODE = str(train_window_cfg.get("mode", "full")).strip().lower()
    if TRAIN_WINDOW_MODE in {"", "all", "expanding"}:
        TRAIN_WINDOW_MODE = "full"
    if TRAIN_WINDOW_MODE not in {"full", "rolling"}:
        sys.exit("model.train_window.mode must be one of: full, rolling.")
    TRAIN_WINDOW_SIZE = train_window_cfg.get("size")
    if TRAIN_WINDOW_SIZE is not None:
        try:
            TRAIN_WINDOW_SIZE = int(TRAIN_WINDOW_SIZE)
        except (TypeError, ValueError):
            sys.exit("model.train_window.size must be a positive integer.")
        if TRAIN_WINDOW_SIZE <= 0:
            sys.exit("model.train_window.size must be a positive integer.")
    TRAIN_WINDOW_UNIT = str(train_window_cfg.get("unit", "dates")).strip().lower()
    if TRAIN_WINDOW_UNIT not in {"dates", "years"}:
        sys.exit("model.train_window.unit must be one of: dates, years.")
    if TRAIN_WINDOW_MODE == "rolling" and TRAIN_WINDOW_SIZE is None:
        sys.exit("model.train_window.size is required when model.train_window.mode=rolling.")

    BACKTEST_ENABLED = bool(backtest_cfg.get("enabled", True))
    BACKTEST_TOP_K = int(backtest_cfg.get("top_k", TOP_K))
    BACKTEST_REBALANCE_FREQUENCY = backtest_cfg.get("rebalance_frequency", REBALANCE_FREQUENCY)
    BACKTEST_COST_BPS = float(backtest_cfg.get("transaction_cost_bps", TRANSACTION_COST_BPS))
    BACKTEST_TRADING_DAYS_PER_YEAR = int(backtest_cfg.get("trading_days_per_year", 252))
    BACKTEST_BENCHMARK = backtest_cfg.get("benchmark_symbol")
    BACKTEST_LONG_ONLY = bool(backtest_cfg.get("long_only", True))
    BACKTEST_BUFFER_EXIT = int(backtest_cfg.get("buffer_exit", 0))
    BACKTEST_BUFFER_ENTRY = int(backtest_cfg.get("buffer_entry", 0))
    BACKTEST_WEIGHTING = str(backtest_cfg.get("weighting", "equal")).strip().lower()
    if BACKTEST_WEIGHTING not in {"equal", "signal"}:
        sys.exit("backtest.weighting must be one of: equal, signal.")
    BACKTEST_GROUP_COL = backtest_cfg.get("group_col")
    if BACKTEST_GROUP_COL is not None:
        BACKTEST_GROUP_COL = str(BACKTEST_GROUP_COL).strip() or None
    BACKTEST_MAX_NAMES_PER_GROUP = backtest_cfg.get("max_names_per_group")
    if BACKTEST_MAX_NAMES_PER_GROUP is not None:
        try:
            BACKTEST_MAX_NAMES_PER_GROUP = int(BACKTEST_MAX_NAMES_PER_GROUP)
        except (TypeError, ValueError):
            sys.exit("backtest.max_names_per_group must be a positive integer.")
        if BACKTEST_MAX_NAMES_PER_GROUP <= 0:
            sys.exit("backtest.max_names_per_group must be a positive integer.")
    BACKTEST_SIGNAL_DIRECTION_RAW = backtest_cfg.get("signal_direction")
    if BACKTEST_SIGNAL_DIRECTION_RAW is not None:
        BACKTEST_SIGNAL_DIRECTION_RAW = float(BACKTEST_SIGNAL_DIRECTION_RAW)
        if BACKTEST_SIGNAL_DIRECTION_RAW == 0:
            sys.exit("backtest.signal_direction cannot be 0.")
    BACKTEST_SHORT_K = backtest_cfg.get("short_k")
    if BACKTEST_SHORT_K is not None:
        BACKTEST_SHORT_K = int(BACKTEST_SHORT_K)
    BACKTEST_EXIT_MODE = str(backtest_cfg.get("exit_mode", "rebalance")).strip().lower()
    if BACKTEST_EXIT_MODE not in {"rebalance", "label_horizon"}:
        sys.exit("backtest.exit_mode must be one of: rebalance, label_horizon.")
    BACKTEST_EXIT_HORIZON_DAYS = backtest_cfg.get("exit_horizon_days")
    BACKTEST_EXIT_PRICE_POLICY = str(backtest_cfg.get("exit_price_policy", "strict")).strip().lower()
    if BACKTEST_EXIT_PRICE_POLICY not in {"strict", "ffill", "delay"}:
        sys.exit("backtest.exit_price_policy must be one of: strict, ffill, delay.")
    BACKTEST_EXIT_FALLBACK_POLICY = str(
        backtest_cfg.get("exit_fallback_policy", "ffill")
    ).strip().lower()
    if BACKTEST_EXIT_FALLBACK_POLICY not in {"ffill", "none"}:
        sys.exit("backtest.exit_fallback_policy must be one of: ffill, none.")
    execution_cfg = backtest_cfg.get("execution") if isinstance(backtest_cfg, dict) else None
    execution_model = build_execution_model(
        execution_cfg,
        default_cost_bps=BACKTEST_COST_BPS,
        default_exit_price_policy=BACKTEST_EXIT_PRICE_POLICY,
        default_exit_fallback_policy=BACKTEST_EXIT_FALLBACK_POLICY,
        default_price_col=PRICE_COL,
    )
    BACKTEST_EXIT_PRICE_POLICY = execution_model.exit_policy.price_policy
    BACKTEST_EXIT_FALLBACK_POLICY = execution_model.exit_policy.fallback_policy
    EXECUTION_PRICING_COLS = required_pricing_columns(execution_model)
    _ensure_execution_daily_fields(
        data_cfg=data_cfg,
        provider=provider,
        required_columns=EXECUTION_PRICING_COLS | {PRICE_COL},
    )
    BACKTEST_COST_BPS_EFFECTIVE = BACKTEST_COST_BPS
    BACKTEST_COST_BPS_REPORT = None
    if isinstance(execution_model.cost_model, BpsCostModel):
        BACKTEST_COST_BPS_EFFECTIVE = float(execution_model.cost_model.bps)
        BACKTEST_COST_BPS_REPORT = BACKTEST_COST_BPS_EFFECTIVE
    BACKTEST_TRADABLE_COL = backtest_cfg.get("tradable_col", "is_tradable")
    if BACKTEST_TRADABLE_COL is not None:
        BACKTEST_TRADABLE_COL = str(BACKTEST_TRADABLE_COL).strip() or None
    if BACKTEST_EXIT_MODE == "label_horizon":
        if BACKTEST_EXIT_HORIZON_DAYS is None:
            BACKTEST_EXIT_HORIZON_DAYS = LABEL_HORIZON_DAYS
        BACKTEST_EXIT_HORIZON_DAYS = int(BACKTEST_EXIT_HORIZON_DAYS)

    LIVE_ENABLED = bool(live_cfg.get("enabled", False))
    LIVE_AS_OF = live_cfg.get("as_of", "t-1")
    LIVE_TRAIN_MODE = str(live_cfg.get("train_mode", "full")).strip().lower()
    if LIVE_TRAIN_MODE not in {"full", "train"}:
        sys.exit("live.train_mode must be one of: full, train.")
    if LIVE_ENABLED and not SAVE_ARTIFACTS:
        raise SystemExit(
            "live.enabled=true requires eval.save_artifacts=true to persist holdings."
        )

    run_name = str(RUN_NAME or config_label)
    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_hash = config_hash(config)
    run_dir = Path(OUTPUT_DIR) / f"{run_name}_{run_stamp}_{run_hash}"
    if SAVE_ARTIFACTS:
        run_dir.mkdir(parents=True, exist_ok=True)
        active_log_file = setup_logging(config, default_log_file=run_dir / "run.log")
        logger.info("Artifacts will be saved to %s", run_dir)

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
    fund_cache_dir = panel_state["fund_cache_dir"]
    provider_overlay_cache_dir = panel_state["provider_overlay_cache_dir"]
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
    dataset = dataset_state["dataset"]
    df_features = dataset_state["df_features"]
    df_full = dataset_state["df_full"]
    df_full_sorted = dataset_state["df_full_sorted"]
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
        "price_col": PRICE_COL,
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

    # Persist artifacts
    dataset_path: Optional[Path] = None
    eval_scored_path: Optional[Path] = None
    feature_importance_path: Optional[Path] = None
    if SAVE_ARTIFACTS:
        rolling_ic_files: dict[str, str] = {}
        rolling_sharpe_files: dict[str, str] = {}
        rolling_ic_oos_files: dict[str, str] = {}
        rolling_sharpe_oos_files: dict[str, str] = {}
        bucket_ic_path: Optional[Path] = None
        bucket_ic_oos_path: Optional[Path] = None
        walk_forward_importance_path: Optional[Path] = None
        walk_forward_feature_stability_path: Optional[Path] = None
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
            quantile_out = quantile_ts.reset_index()
            save_frame(quantile_out, run_dir / "quantile_returns.csv")
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
            save_series(
                pearson_ic_series_oos, run_dir / "ic_pearson_oos.csv", value_name="ic"
            )
            if not quantile_ts_oos.empty:
                quantile_oos_out = quantile_ts_oos.reset_index()
                save_frame(quantile_oos_out, run_dir / "quantile_returns_oos.csv")
            save_series(
                turnover_series_oos,
                run_dir / "turnover_eval_oos.csv",
                value_name="turnover",
            )
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
            dropped_df = dropped_date_counts.rename("symbol_count").reset_index()
            save_frame(dropped_df, run_dir / "dropped_dates.csv")
        if bt_stats is not None:
            save_series(bt_net_series, run_dir / "backtest_net.csv", value_name="net_return")
            save_series(bt_gross_series, run_dir / "backtest_gross.csv", value_name="gross_return")
            save_series(bt_turnover_series, run_dir / "backtest_turnover.csv", value_name="turnover")
            if not bt_benchmark_series.empty:
                save_series(
                    bt_benchmark_series, run_dir / "backtest_benchmark.csv", value_name="benchmark_return"
                )
            if not bt_active_series.empty:
                save_series(bt_active_series, run_dir / "backtest_active.csv", value_name="active_return")
            if bt_periods:
                save_frame(pd.DataFrame(bt_periods), run_dir / "backtest_periods.csv")
        if bt_stats_oos is not None:
            save_series(bt_net_series_oos, run_dir / "backtest_net_oos.csv", value_name="net_return")
            save_series(
                bt_gross_series_oos, run_dir / "backtest_gross_oos.csv", value_name="gross_return"
            )
            save_series(
                bt_turnover_series_oos, run_dir / "backtest_turnover_oos.csv", value_name="turnover"
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
            oos_entry_dates = pd.to_datetime(
                positions_by_rebalance_oos["entry_date"], errors="coerce"
            )
            if oos_entry_dates.notna().any():
                oos_latest_entry = oos_entry_dates.max()
                positions_current_oos = positions_by_rebalance_oos[
                    oos_entry_dates == oos_latest_entry
                ].copy()
                if not positions_current_oos.empty:
                    positions_current_oos_path = run_dir / "positions_current_oos.csv"
                    save_frame(positions_current_oos, positions_current_oos_path)

        if (
            LIVE_ENABLED
            and positions_by_rebalance_live is not None
            and not positions_by_rebalance_live.empty
        ):
            positions_by_rebalance_live_path = run_dir / "positions_by_rebalance_live.csv"
            save_frame(positions_by_rebalance_live, positions_by_rebalance_live_path)
            live_entry_dates = pd.to_datetime(
                positions_by_rebalance_live["entry_date"], errors="coerce"
            )
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
            save_frame(
                pd.DataFrame({"ic": perm_stats["scores"]}),
                run_dir / "permutation_test.csv",
            )

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
                        TRAIN_WINDOW_MODE == "rolling"
                        and len(train_dates) < len(train_dates_full)
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
                "feature_importance_file": str(feature_importance_path)
                if feature_importance_path
                else None,
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
                    pd.to_datetime(date).strftime("%Y%m%d")
                    for date in backtest_rebalance_dates
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
                "turnover_count": int(turnover_series_oos.shape[0])
                if final_oos_eval is not None
                else 0,
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
                    "current_file": str(positions_current_oos_path)
                    if positions_current_oos_path
                    else None,
                    "diff_file": str(positions_diff_oos_path) if positions_diff_oos_path else None,
                }
                if final_oos_eval is not None
                else None,
            },
            "positions": {
                "by_rebalance_file": str(positions_by_rebalance_path)
                if positions_by_rebalance_path
                else None,
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
                        FUNDAMENTALS_PROVIDER_OVERLAY_SOURCE
                        if FUNDAMENTALS_PROVIDER_OVERLAY_ENABLED
                        else None
                    ),
                    "provider": (
                        FUNDAMENTALS_PROVIDER_OVERLAY_PROVIDER
                        if FUNDAMENTALS_PROVIDER_OVERLAY_ENABLED
                        else None
                    ),
                    "cache_dir": (
                        str(provider_overlay_cache_dir)
                        if provider_overlay_cache_dir
                        else None
                    ),
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
                "stable_top_features": (
                    walk_forward_feature_stability_df["feature"]
                    .head(WF_FEATURE_TOP_K)
                    .astype(str)
                    .tolist()
                )
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

    # Optional: save the model
    # from joblib import dump; dump(model, "xgb_factor_model.joblib")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Cross-sectional factor pipeline")
    parser.add_argument(
        "--config",
        help="Path to YAML config or built-in name (default/hk).",
    )
    args = parser.parse_args(argv)
    run(args.config)


if __name__ == "__main__":
    main()
