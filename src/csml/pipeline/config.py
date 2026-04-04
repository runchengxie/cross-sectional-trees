from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import numpy as np

from ..artifacts import cache_dir_for
from ..artifacts import resolve_configured_artifacts_root
from ..artifacts import resolve_repo_path
from ..artifacts import runs_dir_for
from ..config_utils import resolve_pipeline_config
from ..data_providers import normalize_market, resolve_provider
from ..date_utils import is_relative_date_token as _is_relative_date_token
from ..date_utils import resolve_date_token as _resolve_date_token
from ..execution import BpsCostModel, build_execution_model, required_pricing_columns
from ..modeling import resolve_model_spec
from .runtime import config_hash, setup_logging
from .stats import _normalize_bucket_schemes, _normalize_window_months
from .stats import _ensure_execution_daily_fields
from .support import load_symbols_file, load_universe_by_date, normalize_symbol_list


def load_run_config(
    config_ref: str | Path | None,
    *,
    default_cache_dir: Path | None = None,
    artifacts_root_override: str | Path | None = None,
) -> dict[str, Any]:
    resolved = resolve_pipeline_config(config_ref)
    config = resolved.data
    config_label = resolved.label
    config_path = resolved.path
    config_source = resolved.source
    active_log_file = setup_logging(config)

    artifacts_root = resolve_configured_artifacts_root(
        config,
        override=artifacts_root_override,
    )
    data_cfg = config.get("data", {})
    market = normalize_market(config.get("market") or data_cfg.get("market"))
    universe_cfg = config.get("universe", {})
    label_cfg = config.get("label", {})
    features_cfg = config.get("features", {})
    fundamentals_cfg = config.get("fundamentals", {})
    model_cfg = config.get("model", {})
    eval_cfg = config.get("eval", {})
    backtest_cfg = config.get("backtest", {})
    live_cfg = config.get("live", {})
    if not isinstance(model_cfg, dict):
        raise SystemExit(
            "model must be a mapping with keys: type, params, sample_weight_mode."
        )
    if not isinstance(live_cfg, dict):
        live_cfg = {}

    load_dotenv()
    cache_dir_default = default_cache_dir or cache_dir_for(artifacts_root)
    cache_dir = resolve_repo_path(data_cfg.get("cache_dir", cache_dir_default.as_posix()))
    return {
        "config": config,
        "config_label": config_label,
        "config_path": config_path,
        "config_source": config_source,
        "active_log_file": active_log_file,
        "artifacts_root": artifacts_root,
        "data_cfg": data_cfg,
        "market": market,
        "universe_cfg": universe_cfg,
        "label_cfg": label_cfg,
        "features_cfg": features_cfg,
        "fundamentals_cfg": fundamentals_cfg,
        "model_cfg": model_cfg,
        "eval_cfg": eval_cfg,
        "backtest_cfg": backtest_cfg,
        "live_cfg": live_cfg,
        "cache_dir": cache_dir,
        "runs_dir": runs_dir_for(artifacts_root),
    }


def resolve_universe_inputs(
    universe_cfg: Mapping[str, Any] | None,
    *,
    market: str,
    logger: logging.Logger,
    default_symbols: list[str],
) -> dict[str, Any]:
    universe_cfg = universe_cfg if isinstance(universe_cfg, Mapping) else {}
    universe_mode = str(universe_cfg.get("mode", "auto")).strip().lower()
    if universe_mode not in {"auto", "pit", "static"}:
        raise SystemExit("universe.mode must be one of: auto, pit, static.")
    require_by_date = bool(universe_cfg.get("require_by_date", False))

    symbols = normalize_symbol_list(universe_cfg.get("symbols"))
    symbols_file = universe_cfg.get("symbols_file")
    by_date_file = universe_cfg.get("by_date_file")
    universe_by_date = None
    universe_mode_effective = universe_mode

    if not symbols and symbols_file:
        symbols = load_symbols_file(Path(symbols_file))

    if by_date_file:
        universe_by_date = load_universe_by_date(
            resolve_repo_path(by_date_file),
            market,
        )
        symbols_from_universe = sorted(universe_by_date["symbol"].unique().tolist())
        if symbols:
            symbols = sorted(set(symbols) | set(symbols_from_universe))
        else:
            symbols = symbols_from_universe
        universe_mode_effective = "pit"
        if universe_mode == "static":
            logger.warning(
                "universe.mode=static but by_date_file provided; using PIT universe."
            )
    else:
        if require_by_date or universe_mode == "pit":
            raise SystemExit(
                "universe.by_date_file is required when universe.mode=pit or require_by_date=true."
            )
        universe_mode_effective = "static"
        if universe_mode == "auto":
            logger.warning(
                "Universe-by-date not provided; using static symbols (survivorship bias). "
                "Set universe.mode=static to acknowledge or provide by_date_file for PIT."
            )

    if not symbols:
        symbols = default_symbols

    if not symbols:
        raise SystemExit("No symbols configured.")

    return {
        "UNIVERSE_MODE": universe_mode,
        "REQUIRE_BY_DATE": require_by_date,
        "symbols": symbols,
        "symbols_file": symbols_file,
        "by_date_file": by_date_file,
        "universe_by_date": universe_by_date,
        "universe_mode_effective": universe_mode_effective,
    }


def resolve_date_range_and_label_settings(
    *,
    data_cfg: Mapping[str, Any] | None,
    label_cfg: Mapping[str, Any] | None,
    eval_cfg: Mapping[str, Any] | None,
    live_cfg: Mapping[str, Any] | None,
    market: str,
    provider: str,
    logger: logging.Logger,
) -> dict[str, Any]:
    data_cfg = data_cfg if isinstance(data_cfg, Mapping) else {}
    label_cfg = label_cfg if isinstance(label_cfg, Mapping) else {}
    eval_cfg = eval_cfg if isinstance(eval_cfg, Mapping) else {}
    live_cfg = live_cfg if isinstance(live_cfg, Mapping) else {}

    end_date_cfg = data_cfg.get("end_date", "today")
    if _is_relative_date_token(end_date_cfg) and not bool(live_cfg.get("enabled", False)):
        logger.warning(
            "data.end_date=%s is a relative token; prefer a fixed YYYYMMDD date for reproducibility.",
            end_date_cfg,
        )
    end_date = _resolve_date_token(
        end_date_cfg,
        default="today",
        market=market,
        provider=provider,
    )

    start_date_cfg = data_cfg.get("start_date")
    if start_date_cfg:
        start_date = datetime.strptime(str(start_date_cfg), "%Y%m%d")
    else:
        start_years = float(data_cfg.get("start_years", 5))
        start_date = end_date - timedelta(days=int(start_years * 365))

    start_date_text = start_date.strftime("%Y%m%d")
    end_date_text = end_date.strftime("%Y%m%d")
    price_col = data_cfg.get("price_col", "close")

    label_horizon_days = int(label_cfg.get("horizon_days", 5))
    label_shift_days = int(label_cfg.get("shift_days", 0))
    label_horizon_mode = str(label_cfg.get("horizon_mode", "fixed")).strip().lower()
    if label_horizon_mode not in {"fixed", "next_rebalance"}:
        raise SystemExit("label.horizon_mode must be one of: fixed, next_rebalance.")
    label_rebalance_frequency = label_cfg.get(
        "rebalance_frequency",
        eval_cfg.get("rebalance_frequency", "M"),
    )
    target = label_cfg.get("target_col", "future_return")
    train_target_transform = str(
        label_cfg.get("train_target_transform", "none")
    ).strip().lower()
    if train_target_transform not in {"none", "zscore", "rank"}:
        raise SystemExit(
            "label.train_target_transform must be one of: none, zscore, rank."
        )
    train_target = (
        target if train_target_transform == "none" else f"{target}__train_target"
    )
    winsorize_pct = label_cfg.get("winsorize_pct")
    if winsorize_pct is not None:
        winsorize_pct = float(winsorize_pct)
        if not 0 < winsorize_pct < 0.5:
            raise SystemExit("winsorize_pct must be between 0 and 0.5.")

    return {
        "end_date": end_date,
        "start_date": start_date,
        "START_DATE": start_date_text,
        "END_DATE": end_date_text,
        "PRICE_COL": price_col,
        "LABEL_HORIZON_DAYS": label_horizon_days,
        "LABEL_SHIFT_DAYS": label_shift_days,
        "LABEL_HORIZON_MODE": label_horizon_mode,
        "LABEL_REBALANCE_FREQUENCY": label_rebalance_frequency,
        "TARGET": target,
        "TRAIN_TARGET_TRANSFORM": train_target_transform,
        "TRAIN_TARGET": train_target,
        "WINSORIZE_PCT": winsorize_pct,
    }


def normalize_eval_settings(
    eval_cfg: Mapping[str, Any] | None,
    *,
    backtest_cfg: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    eval_cfg = eval_cfg if isinstance(eval_cfg, Mapping) else {}
    backtest_cfg = backtest_cfg if isinstance(backtest_cfg, Mapping) else {}

    test_size = float(eval_cfg.get("test_size", 0.2))
    n_splits = int(eval_cfg.get("n_splits", 5))
    n_quantiles = int(eval_cfg.get("n_quantiles", 5))
    top_k = int(eval_cfg.get("top_k", 20))
    rebalance_frequency = eval_cfg.get("rebalance_frequency", "W")
    transaction_cost_bps = float(eval_cfg.get("transaction_cost_bps", 10))
    eval_buffer_exit = int(eval_cfg.get("buffer_exit", backtest_cfg.get("buffer_exit", 0)))
    eval_buffer_entry = int(
        eval_cfg.get("buffer_entry", backtest_cfg.get("buffer_entry", 0))
    )
    signal_direction_mode = str(
        eval_cfg.get("signal_direction_mode", "fixed")
    ).strip().lower()
    if signal_direction_mode not in {"fixed", "train_ic", "cv_ic"}:
        raise SystemExit(
            "eval.signal_direction_mode must be one of: fixed, train_ic, cv_ic."
        )
    signal_direction_raw = eval_cfg.get("signal_direction", 1.0)
    signal_direction = (
        float(signal_direction_raw) if signal_direction_raw is not None else 1.0
    )
    if signal_direction == 0:
        raise SystemExit("eval.signal_direction cannot be 0.")
    min_abs_ic_to_flip_raw = eval_cfg.get("min_abs_ic_to_flip", 0.0)
    min_abs_ic_to_flip = (
        float(min_abs_ic_to_flip_raw) if min_abs_ic_to_flip_raw is not None else 0.0
    )
    if min_abs_ic_to_flip < 0:
        raise SystemExit("eval.min_abs_ic_to_flip must be >= 0.")
    embargo_days_raw = eval_cfg.get("embargo_days")
    embargo_days_cfg = int(embargo_days_raw) if embargo_days_raw is not None else 0
    purge_days_raw = eval_cfg.get("purge_days")
    purge_days_cfg = int(purge_days_raw) if purge_days_raw is not None else None
    report_train_ic = bool(eval_cfg.get("report_train_ic", True))
    sample_on_rebalance_dates = bool(eval_cfg.get("sample_on_rebalance_dates", False))

    score_postprocess_cfg = eval_cfg.get("score_postprocess")
    score_postprocess_enabled = False
    score_postprocess_method = "none"
    score_postprocess_columns: list[str] = []
    score_postprocess_strength = 1.0
    score_postprocess_min_obs: int | None = None
    if score_postprocess_cfg is not None:
        if not isinstance(score_postprocess_cfg, Mapping):
            raise SystemExit("eval.score_postprocess must be a mapping when provided.")
        score_postprocess_method = str(
            score_postprocess_cfg.get("method", "none")
        ).strip().lower()
        score_postprocess_columns = normalize_symbol_list(
            score_postprocess_cfg.get("columns")
        )
        score_postprocess_strength = float(
            score_postprocess_cfg.get("strength", 1.0)
        )
        score_postprocess_min_obs_raw = score_postprocess_cfg.get("min_obs")
        if score_postprocess_min_obs_raw is not None:
            score_postprocess_min_obs = int(score_postprocess_min_obs_raw)
        enabled_raw = score_postprocess_cfg.get("enabled")
        score_postprocess_enabled = (
            bool(enabled_raw)
            if enabled_raw is not None
            else score_postprocess_method != "none"
        )
        if score_postprocess_method not in {"none", "neutralize"}:
            raise SystemExit(
                "eval.score_postprocess.method must be one of: none, neutralize."
            )
        if score_postprocess_strength < 0 or score_postprocess_strength > 1:
            raise SystemExit("eval.score_postprocess.strength must be between 0 and 1.")
        if score_postprocess_min_obs is not None and score_postprocess_min_obs < 2:
            raise SystemExit("eval.score_postprocess.min_obs must be >= 2.")
        if score_postprocess_enabled and score_postprocess_method == "neutralize":
            if not score_postprocess_columns:
                raise SystemExit(
                    "eval.score_postprocess.columns is required when method=neutralize."
                )
            required_min_obs = len(score_postprocess_columns) + 1
            if (
                score_postprocess_min_obs is not None
                and score_postprocess_min_obs < required_min_obs
            ):
                raise SystemExit(
                    "eval.score_postprocess.min_obs must be >= len(columns) + 1."
                )
        else:
            score_postprocess_method = "none"
            score_postprocess_columns = []
            score_postprocess_min_obs = None
    if score_postprocess_enabled and score_postprocess_min_obs is None:
        score_postprocess_min_obs = max(5, len(score_postprocess_columns) + 1)

    rolling_cfg = eval_cfg.get("rolling") if isinstance(eval_cfg, Mapping) else None
    if isinstance(rolling_cfg, Mapping):
        rolling_enabled = bool(rolling_cfg.get("enabled", True))
        if rolling_enabled:
            rolling_windows_months = _normalize_window_months(
                rolling_cfg.get("windows_months"),
                [6, 12],
            )
        else:
            rolling_windows_months = []
    else:
        rolling_windows_months = _normalize_window_months(rolling_cfg, [6, 12])

    bucket_ic_cfg = eval_cfg.get("bucket_ic") if isinstance(eval_cfg, Mapping) else None
    bucket_ic_enabled = False
    bucket_ic_method = "spearman"
    bucket_ic_min_count = 0
    bucket_ic_schemes = []
    if isinstance(bucket_ic_cfg, Mapping):
        bucket_ic_enabled = bool(bucket_ic_cfg.get("enabled", False))
        bucket_ic_method = str(bucket_ic_cfg.get("method", "spearman")).strip().lower()
        bucket_ic_min_count = int(bucket_ic_cfg.get("min_count", 0) or 0)
        bucket_ic_schemes = _normalize_bucket_schemes(bucket_ic_cfg.get("schemes"))
    elif bucket_ic_cfg is not None:
        bucket_ic_enabled = bool(bucket_ic_cfg)
    if bucket_ic_method not in {"spearman", "pearson"}:
        raise SystemExit("eval.bucket_ic.method must be one of: spearman, pearson.")

    perm_cfg = eval_cfg.get("permutation_test") or {}
    if isinstance(perm_cfg, Mapping):
        perm_test_enabled = bool(perm_cfg.get("enabled", False))
        perm_test_runs = int(perm_cfg.get("n_runs", 1))
        perm_test_seed = perm_cfg.get("seed")
    else:
        perm_test_enabled = bool(perm_cfg)
        perm_test_runs = 1
        perm_test_seed = None
    if perm_test_seed is not None:
        perm_test_seed = int(perm_test_seed)
    if perm_test_runs < 1:
        perm_test_enabled = False

    wf_cfg = eval_cfg.get("walk_forward") or {}
    if isinstance(wf_cfg, Mapping):
        wf_enabled = bool(wf_cfg.get("enabled", False))
        wf_n_windows = int(wf_cfg.get("n_windows", 3))
        wf_test_size = wf_cfg.get("test_size", test_size)
        wf_step_size = wf_cfg.get("step_size")
        wf_anchor_end = bool(wf_cfg.get("anchor_end", True))
        wf_feature_top_k = int(wf_cfg.get("feature_top_k", 5))
        wf_backtest_enabled = bool(
            wf_cfg.get("backtest_enabled", backtest_cfg.get("enabled", True))
        )
        wf_perm_cfg = wf_cfg.get("permutation_test")
        if isinstance(wf_perm_cfg, Mapping):
            wf_perm_test_enabled = bool(wf_perm_cfg.get("enabled", False))
            wf_perm_test_runs = int(wf_perm_cfg.get("n_runs", perm_test_runs))
            wf_perm_test_seed = wf_perm_cfg.get("seed", perm_test_seed)
        elif wf_perm_cfg is None:
            wf_perm_test_enabled = False
            wf_perm_test_runs = perm_test_runs
            wf_perm_test_seed = perm_test_seed
        else:
            wf_perm_test_enabled = bool(wf_perm_cfg)
            wf_perm_test_runs = perm_test_runs
            wf_perm_test_seed = perm_test_seed
    else:
        wf_enabled = bool(wf_cfg)
        wf_n_windows = 3
        wf_test_size = test_size
        wf_step_size = None
        wf_anchor_end = True
        wf_feature_top_k = 5
        wf_backtest_enabled = bool(backtest_cfg.get("enabled", True))
        wf_perm_test_enabled = False
        wf_perm_test_runs = perm_test_runs
        wf_perm_test_seed = perm_test_seed
    if wf_perm_test_seed is not None:
        wf_perm_test_seed = int(wf_perm_test_seed)
    if wf_perm_test_runs < 1:
        wf_perm_test_enabled = False
    if wf_feature_top_k < 1:
        raise SystemExit("eval.walk_forward.feature_top_k must be >= 1.")

    final_oos_cfg = eval_cfg.get("final_oos")
    final_oos_size_raw = None
    if isinstance(final_oos_cfg, Mapping):
        final_oos_size_raw = final_oos_cfg.get("size")
        final_oos_enabled = bool(final_oos_cfg.get("enabled", False) or final_oos_size_raw)
    elif final_oos_cfg is None:
        final_oos_enabled = False
    else:
        final_oos_size_raw = final_oos_cfg
        final_oos_enabled = bool(final_oos_cfg)

    save_artifacts = bool(eval_cfg.get("save_artifacts", True))
    save_scored_artifact = bool(eval_cfg.get("save_scored_artifact", False))
    save_dataset = bool(eval_cfg.get("save_dataset", False))
    output_dir = eval_cfg.get("output_dir")
    run_name = eval_cfg.get("run_name")
    if save_scored_artifact and not save_artifacts:
        raise SystemExit(
            "eval.save_scored_artifact=true requires eval.save_artifacts=true."
        )
    if save_dataset and not save_artifacts:
        raise SystemExit("eval.save_dataset=true requires eval.save_artifacts=true.")

    return {
        "TEST_SIZE": test_size,
        "N_SPLITS": n_splits,
        "N_QUANTILES": n_quantiles,
        "TOP_K": top_k,
        "REBALANCE_FREQUENCY": rebalance_frequency,
        "TRANSACTION_COST_BPS": transaction_cost_bps,
        "EVAL_BUFFER_EXIT": eval_buffer_exit,
        "EVAL_BUFFER_ENTRY": eval_buffer_entry,
        "SIGNAL_DIRECTION_MODE": signal_direction_mode,
        "SIGNAL_DIRECTION": signal_direction,
        "MIN_ABS_IC_TO_FLIP": min_abs_ic_to_flip,
        "EMBARGO_DAYS_CFG": embargo_days_cfg,
        "PURGE_DAYS_CFG": purge_days_cfg,
        "PURGE_STEPS": None,
        "EMBARGO_STEPS": None,
        "EFFECTIVE_GAP_STEPS": None,
        "REPORT_TRAIN_IC": report_train_ic,
        "SAMPLE_ON_REBALANCE_DATES": sample_on_rebalance_dates,
        "SCORE_POSTPROCESS_ENABLED": score_postprocess_enabled,
        "SCORE_POSTPROCESS_METHOD": score_postprocess_method,
        "SCORE_POSTPROCESS_COLUMNS": score_postprocess_columns,
        "SCORE_POSTPROCESS_STRENGTH": score_postprocess_strength,
        "SCORE_POSTPROCESS_MIN_OBS": score_postprocess_min_obs,
        "ROLLING_WINDOWS_MONTHS": rolling_windows_months,
        "BUCKET_IC_ENABLED": bucket_ic_enabled,
        "BUCKET_IC_METHOD": bucket_ic_method,
        "BUCKET_IC_MIN_COUNT": bucket_ic_min_count,
        "BUCKET_IC_SCHEMES": bucket_ic_schemes,
        "PERM_TEST_ENABLED": perm_test_enabled,
        "PERM_TEST_RUNS": perm_test_runs,
        "PERM_TEST_SEED": perm_test_seed,
        "WF_ENABLED": wf_enabled,
        "WF_N_WINDOWS": wf_n_windows,
        "WF_TEST_SIZE": wf_test_size,
        "WF_STEP_SIZE": wf_step_size,
        "WF_ANCHOR_END": wf_anchor_end,
        "WF_FEATURE_TOP_K": wf_feature_top_k,
        "WF_BACKTEST_ENABLED": wf_backtest_enabled,
        "WF_PERM_TEST_ENABLED": wf_perm_test_enabled,
        "WF_PERM_TEST_RUNS": wf_perm_test_runs,
        "WF_PERM_TEST_SEED": wf_perm_test_seed,
        "FINAL_OOS_ENABLED": final_oos_enabled,
        "FINAL_OOS_SIZE_RAW": final_oos_size_raw,
        "SAVE_ARTIFACTS": save_artifacts,
        "SAVE_SCORED_ARTIFACT": save_scored_artifact,
        "SAVE_DATASET": save_dataset,
        "OUTPUT_DIR": output_dir,
        "RUN_NAME": run_name,
    }


def normalize_universe_filters(
    universe_cfg: Mapping[str, Any] | None,
    *,
    n_quantiles: int,
) -> dict[str, Any]:
    universe_cfg = universe_cfg if isinstance(universe_cfg, Mapping) else {}
    min_symbols_per_date = int(universe_cfg.get("min_symbols_per_date", n_quantiles))
    if min_symbols_per_date < n_quantiles:
        min_symbols_per_date = n_quantiles
    suspended_policy = str(universe_cfg.get("suspended_policy", "mark")).strip().lower()
    if suspended_policy not in {"mark", "filter"}:
        raise SystemExit("universe.suspended_policy must be one of: mark, filter.")
    return {
        "MIN_SYMBOLS_PER_DATE": min_symbols_per_date,
        "MIN_LISTED_DAYS": int(universe_cfg.get("min_listed_days", 0)),
        "MIN_TURNOVER": float(universe_cfg.get("min_turnover", 0)),
        "DROP_ST": bool(universe_cfg.get("drop_st", False)),
        "DROP_SUSPENDED": bool(universe_cfg.get("drop_suspended", True)),
        "SUSPENDED_POLICY": suspended_policy,
    }


def resolve_runtime_settings(
    *,
    data_cfg: Mapping[str, Any] | None,
    features_cfg: Mapping[str, Any] | None,
    fundamentals_cfg: Mapping[str, Any] | None,
    industry_cfg: Mapping[str, Any] | None,
    model_cfg: Mapping[str, Any] | None,
    backtest_cfg: Mapping[str, Any] | None,
    live_cfg: Mapping[str, Any] | None,
    provider: str,
    market: str,
    price_col: str,
    label_horizon_days: int,
    label_shift_days: int,
    label_horizon_mode: str,
    label_rebalance_frequency: str,
    train_target: str,
    eval_top_k: int,
    eval_rebalance_frequency: str,
    eval_transaction_cost_bps: float,
    eval_buffer_exit: int,
    eval_buffer_entry: int,
    wf_feature_top_k: int,
) -> dict[str, Any]:
    data_cfg = data_cfg if isinstance(data_cfg, Mapping) else {}
    features_cfg = features_cfg if isinstance(features_cfg, Mapping) else {}
    fundamentals_cfg = fundamentals_cfg if isinstance(fundamentals_cfg, Mapping) else {}
    industry_cfg = industry_cfg if isinstance(industry_cfg, Mapping) else {}
    model_cfg = model_cfg if isinstance(model_cfg, Mapping) else {}
    backtest_cfg = backtest_cfg if isinstance(backtest_cfg, Mapping) else {}
    live_cfg = live_cfg if isinstance(live_cfg, Mapping) else {}

    fundamentals_enabled = bool(fundamentals_cfg.get("enabled", False))
    fundamentals_source = str(
        fundamentals_cfg.get("source", "provider")
    ).strip().lower()
    if fundamentals_source not in {"provider", "file"}:
        raise SystemExit("fundamentals.source must be one of: provider, file.")
    fundamentals_file = fundamentals_cfg.get("file")
    fundamentals_features = normalize_symbol_list(fundamentals_cfg.get("features"))
    fundamentals_auto_add = bool(fundamentals_cfg.get("auto_add_features", True))
    fundamentals_allow_missing = bool(
        fundamentals_cfg.get("allow_missing_features", False)
    )
    fundamentals_ffill = bool(fundamentals_cfg.get("ffill", True))
    fundamentals_ffill_limit = fundamentals_cfg.get("ffill_limit")
    if fundamentals_ffill_limit is not None:
        fundamentals_ffill_limit = int(fundamentals_ffill_limit)
    fundamentals_log_mcap = bool(fundamentals_cfg.get("log_market_cap", False))
    fundamentals_mcap_col = str(
        fundamentals_cfg.get("market_cap_col", "market_cap")
    ).strip()
    fundamentals_log_mcap_col = str(
        fundamentals_cfg.get("log_market_cap_col", "log_mcap")
    ).strip()
    fundamentals_required = bool(fundamentals_cfg.get("required", False))
    fundamentals_provider = (
        resolve_provider({"provider": fundamentals_cfg.get("provider")})
        if fundamentals_cfg.get("provider")
        else provider
    )
    provider_overlay_cfg = fundamentals_cfg.get("provider_overlay")
    if provider_overlay_cfg is None:
        provider_overlay_cfg = {}
    if not isinstance(provider_overlay_cfg, Mapping):
        raise SystemExit("fundamentals.provider_overlay must be a mapping when provided.")
    fundamentals_provider_overlay_enabled = bool(
        provider_overlay_cfg.get("enabled", False)
    )
    fundamentals_provider_overlay_source = str(
        provider_overlay_cfg.get("source", "provider")
    ).strip().lower()
    if fundamentals_provider_overlay_source not in {"provider"}:
        raise SystemExit("fundamentals.provider_overlay.source must be 'provider'.")
    fundamentals_provider_overlay_features = normalize_symbol_list(
        provider_overlay_cfg.get("features")
    )
    fundamentals_provider_overlay_auto_add = bool(
        provider_overlay_cfg.get("auto_add_features", True)
    )
    fundamentals_provider_overlay_required = bool(
        provider_overlay_cfg.get("required", False)
    )
    fundamentals_provider_overlay_provider = (
        resolve_provider({"provider": provider_overlay_cfg.get("provider")})
        if provider_overlay_cfg.get("provider")
        else provider
    )

    industry_enabled = bool(industry_cfg.get("enabled", False))
    industry_source = str(industry_cfg.get("source", "file")).strip().lower()
    if industry_source not in {"file"}:
        raise SystemExit("industry.source must be 'file'.")
    industry_file = industry_cfg.get("file")
    industry_keep_columns = normalize_symbol_list(industry_cfg.get("keep_columns"))
    industry_ffill = bool(industry_cfg.get("ffill", False))
    industry_ffill_limit = industry_cfg.get("ffill_limit")
    if industry_ffill_limit is not None:
        industry_ffill_limit = int(industry_ffill_limit)
    industry_required = bool(industry_cfg.get("required", False))

    feature_list = features_cfg.get("list") or []
    features = normalize_symbol_list(feature_list) if feature_list else [
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
    if fundamentals_enabled and fundamentals_auto_add and fundamentals_features:
        features = list(dict.fromkeys(features + fundamentals_features))
    if (
        fundamentals_provider_overlay_enabled
        and fundamentals_provider_overlay_auto_add
        and fundamentals_provider_overlay_features
    ):
        features = list(
            dict.fromkeys(features + fundamentals_provider_overlay_features)
        )
    wf_feature_top_k = min(wf_feature_top_k, max(1, len(features)))
    feature_params = features_cfg.get("params", {})
    cs_cfg = features_cfg.get("cross_sectional") or {}
    cs_method = (
        str(cs_cfg.get("method", "none")).strip().lower()
        if isinstance(cs_cfg, Mapping)
        else "none"
    )
    cs_winsorize_pct = (
        cs_cfg.get("winsorize_pct") if isinstance(cs_cfg, Mapping) else None
    )
    if cs_winsorize_pct is not None:
        cs_winsorize_pct = float(cs_winsorize_pct)
        if not 0 < cs_winsorize_pct < 0.5:
            raise SystemExit(
                "features.cross_sectional.winsorize_pct must be between 0 and 0.5."
            )
    if cs_method not in {"none", "zscore", "rank"}:
        raise SystemExit(
            "features.cross_sectional.method must be one of: none, zscore, rank."
        )
    missing_cfg = features_cfg.get("missing")
    if missing_cfg is None:
        missing_cfg = {}
    if not isinstance(missing_cfg, Mapping):
        raise SystemExit("features.missing must be a mapping when provided.")
    feature_missing_method = str(
        missing_cfg.get("method", "none")
    ).strip().lower()
    if feature_missing_method not in {"none", "zero", "cross_sectional_median"}:
        raise SystemExit(
            "features.missing.method must be one of: none, zero, cross_sectional_median."
        )
    feature_missing_features = normalize_symbol_list(missing_cfg.get("features"))
    feature_missing_add_indicators = bool(
        missing_cfg.get("add_indicators", False)
    )
    feature_missing_suffix = str(
        missing_cfg.get("indicator_suffix", "_missing")
    ).strip()
    if feature_missing_add_indicators and not feature_missing_suffix:
        raise SystemExit("features.missing.indicator_suffix cannot be empty.")

    try:
        model_type, model_params = resolve_model_spec(model_cfg)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    model_cfg_resolved = {"type": model_type, "params": model_params}
    sample_weight_mode = str(
        model_cfg.get("sample_weight_mode", "none")
    ).strip().lower()
    sample_weight_params_raw = model_cfg.get("sample_weight_params")
    if sample_weight_params_raw is None:
        sample_weight_params = {}
    elif isinstance(sample_weight_params_raw, Mapping):
        sample_weight_params = dict(sample_weight_params_raw)
    else:
        raise SystemExit("model.sample_weight_params must be a mapping when provided.")
    if sample_weight_mode in {"", "none", "null"}:
        sample_weight_mode = "none"
    if sample_weight_mode in {"date"}:
        sample_weight_mode = "date_equal"
    if sample_weight_mode in {"time_decay", "exp_decay", "exp"}:
        sample_weight_mode = "exp_decay"
    if sample_weight_mode not in {"none", "date_equal", "exp_decay"}:
        raise SystemExit(
            "model.sample_weight_mode must be one of: none, date_equal, exp_decay."
        )
    if sample_weight_mode == "exp_decay":
        halflife_raw = sample_weight_params.get(
            "halflife",
            sample_weight_params.get("half_life"),
        )
        decay_rate_raw = sample_weight_params.get(
            "decay_rate",
            sample_weight_params.get("rate"),
        )
        if halflife_raw is None and decay_rate_raw is None:
            raise SystemExit(
                "model.sample_weight_mode=exp_decay requires "
                "model.sample_weight_params.halflife or decay_rate."
            )
        if halflife_raw is not None:
            try:
                halflife = float(halflife_raw)
            except (TypeError, ValueError) as exc:
                raise SystemExit(
                    "model.sample_weight_params.halflife must be a number."
                ) from exc
            if not np.isfinite(halflife) or halflife <= 0:
                raise SystemExit(
                    "model.sample_weight_params.halflife must be > 0."
                )
        if decay_rate_raw is not None:
            try:
                decay_rate = float(decay_rate_raw)
            except (TypeError, ValueError) as exc:
                raise SystemExit(
                    "model.sample_weight_params.decay_rate must be a number."
                ) from exc
            if not np.isfinite(decay_rate) or decay_rate <= 0 or decay_rate > 1:
                raise SystemExit(
                    "model.sample_weight_params.decay_rate must be in (0, 1]."
                )
        min_weight_raw = sample_weight_params.get("min_weight")
        if min_weight_raw is not None:
            try:
                min_weight = float(min_weight_raw)
            except (TypeError, ValueError) as exc:
                raise SystemExit(
                    "model.sample_weight_params.min_weight must be a number."
                ) from exc
            if not np.isfinite(min_weight) or min_weight < 0:
                raise SystemExit(
                    "model.sample_weight_params.min_weight must be >= 0."
                )

    train_window_cfg = model_cfg.get("train_window")
    if train_window_cfg is None:
        train_window_cfg = {}
    if not isinstance(train_window_cfg, Mapping):
        raise SystemExit("model.train_window must be a mapping when provided.")
    train_window_mode = str(train_window_cfg.get("mode", "full")).strip().lower()
    if train_window_mode in {"", "all", "expanding"}:
        train_window_mode = "full"
    if train_window_mode not in {"full", "rolling"}:
        raise SystemExit("model.train_window.mode must be one of: full, rolling.")
    train_window_size = train_window_cfg.get("size")
    if train_window_size is not None:
        try:
            train_window_size = int(train_window_size)
        except (TypeError, ValueError) as exc:
            raise SystemExit(
                "model.train_window.size must be a positive integer."
            ) from exc
        if train_window_size <= 0:
            raise SystemExit("model.train_window.size must be a positive integer.")
    train_window_unit = str(train_window_cfg.get("unit", "dates")).strip().lower()
    if train_window_unit not in {"dates", "years"}:
        raise SystemExit("model.train_window.unit must be one of: dates, years.")
    if train_window_mode == "rolling" and train_window_size is None:
        raise SystemExit(
            "model.train_window.size is required when model.train_window.mode=rolling."
        )

    backtest_enabled = bool(backtest_cfg.get("enabled", True))
    backtest_top_k = int(backtest_cfg.get("top_k", eval_top_k))
    backtest_rebalance_frequency = backtest_cfg.get(
        "rebalance_frequency",
        eval_rebalance_frequency,
    )
    backtest_cost_bps = float(
        backtest_cfg.get("transaction_cost_bps", eval_transaction_cost_bps)
    )
    backtest_trading_days_per_year = int(
        backtest_cfg.get("trading_days_per_year", 252)
    )
    backtest_benchmark = backtest_cfg.get("benchmark_symbol")
    if backtest_benchmark is not None:
        backtest_benchmark = str(backtest_benchmark).strip() or None
    backtest_benchmark_returns_file = backtest_cfg.get("benchmark_returns_file")
    if backtest_benchmark_returns_file is not None:
        backtest_benchmark_returns_file = (
            str(backtest_benchmark_returns_file).strip() or None
        )
    if backtest_benchmark and backtest_benchmark_returns_file:
        raise SystemExit(
            "backtest.benchmark_symbol and backtest.benchmark_returns_file are mutually exclusive."
        )
    backtest_benchmark_compare = _normalize_benchmark_compare(
        backtest_cfg.get("benchmark_compare")
    )
    backtest_long_only = bool(backtest_cfg.get("long_only", True))
    backtest_buffer_exit = int(backtest_cfg.get("buffer_exit", 0))
    backtest_buffer_entry = int(backtest_cfg.get("buffer_entry", 0))
    backtest_weighting = str(backtest_cfg.get("weighting", "equal")).strip().lower()
    if backtest_weighting not in {"equal", "signal"}:
        raise SystemExit("backtest.weighting must be one of: equal, signal.")
    backtest_group_col = backtest_cfg.get("group_col")
    if backtest_group_col is not None:
        backtest_group_col = str(backtest_group_col).strip() or None
    backtest_max_names_per_group = backtest_cfg.get("max_names_per_group")
    if backtest_max_names_per_group is not None:
        try:
            backtest_max_names_per_group = int(backtest_max_names_per_group)
        except (TypeError, ValueError) as exc:
            raise SystemExit(
                "backtest.max_names_per_group must be a positive integer."
            ) from exc
        if backtest_max_names_per_group <= 0:
            raise SystemExit(
                "backtest.max_names_per_group must be a positive integer."
            )
    backtest_signal_direction_raw = backtest_cfg.get("signal_direction")
    if backtest_signal_direction_raw is not None:
        backtest_signal_direction_raw = float(backtest_signal_direction_raw)
        if backtest_signal_direction_raw == 0:
            raise SystemExit("backtest.signal_direction cannot be 0.")
    backtest_short_k = backtest_cfg.get("short_k")
    if backtest_short_k is not None:
        backtest_short_k = int(backtest_short_k)
    backtest_exit_mode = str(backtest_cfg.get("exit_mode", "rebalance")).strip().lower()
    if backtest_exit_mode not in {"rebalance", "label_horizon"}:
        raise SystemExit(
            "backtest.exit_mode must be one of: rebalance, label_horizon."
        )
    backtest_exit_horizon_days = backtest_cfg.get("exit_horizon_days")
    backtest_exit_price_policy = str(
        backtest_cfg.get("exit_price_policy", "strict")
    ).strip().lower()
    if backtest_exit_price_policy not in {"strict", "ffill", "delay"}:
        raise SystemExit(
            "backtest.exit_price_policy must be one of: strict, ffill, delay."
        )
    backtest_exit_fallback_policy = str(
        backtest_cfg.get("exit_fallback_policy", "ffill")
    ).strip().lower()
    if backtest_exit_fallback_policy not in {"ffill", "none"}:
        raise SystemExit(
            "backtest.exit_fallback_policy must be one of: ffill, none."
        )
    execution_cfg = (
        backtest_cfg.get("execution") if isinstance(backtest_cfg, Mapping) else None
    )
    backtest_execution_source = (
        "explicit_execution_config"
        if isinstance(execution_cfg, Mapping) and bool(execution_cfg)
        else "default_flat_cost"
    )
    execution_model = build_execution_model(
        execution_cfg,
        default_cost_bps=backtest_cost_bps,
        default_exit_price_policy=backtest_exit_price_policy,
        default_exit_fallback_policy=backtest_exit_fallback_policy,
        default_price_col=price_col,
    )
    backtest_exit_price_policy = execution_model.exit_policy.price_policy
    backtest_exit_fallback_policy = execution_model.exit_policy.fallback_policy
    execution_pricing_cols = required_pricing_columns(execution_model)
    _ensure_execution_daily_fields(
        data_cfg=data_cfg,
        provider=provider,
        required_columns=execution_pricing_cols | {price_col},
    )
    backtest_cost_bps_effective = backtest_cost_bps
    backtest_cost_bps_report = None
    if isinstance(execution_model.cost_model, BpsCostModel):
        backtest_cost_bps_effective = float(execution_model.cost_model.bps)
        backtest_cost_bps_report = backtest_cost_bps_effective
    backtest_tradable_col = backtest_cfg.get("tradable_col", "is_tradable")
    if backtest_tradable_col is not None:
        backtest_tradable_col = str(backtest_tradable_col).strip() or None
    if backtest_exit_mode == "label_horizon":
        if backtest_exit_horizon_days is None:
            backtest_exit_horizon_days = label_horizon_days
        backtest_exit_horizon_days = int(backtest_exit_horizon_days)

    live_enabled = bool(live_cfg.get("enabled", False))
    live_as_of = live_cfg.get("as_of", "t-1")
    live_train_mode = str(live_cfg.get("train_mode", "full")).strip().lower()
    if live_train_mode not in {"full", "train"}:
        raise SystemExit("live.train_mode must be one of: full, train.")

    return {
        "fundamentals_cfg": fundamentals_cfg,
        "provider_overlay_cfg": provider_overlay_cfg,
        "FUNDAMENTALS_ENABLED": fundamentals_enabled,
        "FUNDAMENTALS_SOURCE": fundamentals_source,
        "FUNDAMENTALS_FILE": fundamentals_file,
        "FUNDAMENTALS_FEATURES": fundamentals_features,
        "FUNDAMENTALS_AUTO_ADD": fundamentals_auto_add,
        "FUNDAMENTALS_ALLOW_MISSING": fundamentals_allow_missing,
        "FUNDAMENTALS_FFILL": fundamentals_ffill,
        "FUNDAMENTALS_FFILL_LIMIT": fundamentals_ffill_limit,
        "FUNDAMENTALS_LOG_MCAP": fundamentals_log_mcap,
        "FUNDAMENTALS_MCAP_COL": fundamentals_mcap_col,
        "FUNDAMENTALS_LOG_MCAP_COL": fundamentals_log_mcap_col,
        "FUNDAMENTALS_REQUIRED": fundamentals_required,
        "FUNDAMENTALS_PROVIDER": fundamentals_provider,
        "FUNDAMENTALS_PROVIDER_OVERLAY_ENABLED": fundamentals_provider_overlay_enabled,
        "FUNDAMENTALS_PROVIDER_OVERLAY_SOURCE": fundamentals_provider_overlay_source,
        "FUNDAMENTALS_PROVIDER_OVERLAY_FEATURES": fundamentals_provider_overlay_features,
        "FUNDAMENTALS_PROVIDER_OVERLAY_AUTO_ADD": fundamentals_provider_overlay_auto_add,
        "FUNDAMENTALS_PROVIDER_OVERLAY_REQUIRED": fundamentals_provider_overlay_required,
        "FUNDAMENTALS_PROVIDER_OVERLAY_PROVIDER": fundamentals_provider_overlay_provider,
        "INDUSTRY_ENABLED": industry_enabled,
        "INDUSTRY_SOURCE": industry_source,
        "INDUSTRY_FILE": industry_file,
        "INDUSTRY_KEEP_COLUMNS": industry_keep_columns,
        "INDUSTRY_FFILL": industry_ffill,
        "INDUSTRY_FFILL_LIMIT": industry_ffill_limit,
        "INDUSTRY_REQUIRED": industry_required,
        "FEATURES": features,
        "feature_params": feature_params,
        "CS_METHOD": cs_method,
        "CS_WINSORIZE_PCT": cs_winsorize_pct,
        "FEATURE_MISSING_METHOD": feature_missing_method,
        "FEATURE_MISSING_FEATURES": feature_missing_features,
        "FEATURE_MISSING_ADD_INDICATORS": feature_missing_add_indicators,
        "FEATURE_MISSING_SUFFIX": feature_missing_suffix,
        "MODEL_TYPE": model_type,
        "MODEL_PARAMS": model_params,
        "MODEL_CFG": model_cfg_resolved,
        "SAMPLE_WEIGHT_MODE": sample_weight_mode,
        "SAMPLE_WEIGHT_PARAMS": sample_weight_params,
        "TRAIN_WINDOW_MODE": train_window_mode,
        "TRAIN_WINDOW_SIZE": train_window_size,
        "TRAIN_WINDOW_UNIT": train_window_unit,
        "BACKTEST_ENABLED": backtest_enabled,
        "BACKTEST_TOP_K": backtest_top_k,
        "BACKTEST_REBALANCE_FREQUENCY": backtest_rebalance_frequency,
        "BACKTEST_COST_BPS": backtest_cost_bps,
        "BACKTEST_TRADING_DAYS_PER_YEAR": backtest_trading_days_per_year,
        "BACKTEST_BENCHMARK": backtest_benchmark,
        "BACKTEST_BENCHMARK_RETURNS_FILE": backtest_benchmark_returns_file,
        "BACKTEST_BENCHMARK_COMPARE": backtest_benchmark_compare,
        "BACKTEST_LONG_ONLY": backtest_long_only,
        "BACKTEST_BUFFER_EXIT": backtest_buffer_exit,
        "BACKTEST_BUFFER_ENTRY": backtest_buffer_entry,
        "BACKTEST_WEIGHTING": backtest_weighting,
        "BACKTEST_GROUP_COL": backtest_group_col,
        "BACKTEST_MAX_NAMES_PER_GROUP": backtest_max_names_per_group,
        "BACKTEST_SIGNAL_DIRECTION_RAW": backtest_signal_direction_raw,
        "BACKTEST_SHORT_K": backtest_short_k,
        "BACKTEST_EXIT_MODE": backtest_exit_mode,
        "BACKTEST_EXIT_HORIZON_DAYS": backtest_exit_horizon_days,
        "BACKTEST_EXIT_PRICE_POLICY": backtest_exit_price_policy,
        "BACKTEST_EXIT_FALLBACK_POLICY": backtest_exit_fallback_policy,
        "execution_model": execution_model,
        "EXECUTION_PRICING_COLS": execution_pricing_cols,
        "BACKTEST_COST_BPS_EFFECTIVE": backtest_cost_bps_effective,
        "BACKTEST_COST_BPS_REPORT": backtest_cost_bps_report,
        "BACKTEST_EXECUTION_SOURCE": backtest_execution_source,
        "BACKTEST_TRADABLE_COL": backtest_tradable_col,
        "LIVE_ENABLED": live_enabled,
        "LIVE_AS_OF": live_as_of,
        "LIVE_TRAIN_MODE": live_train_mode,
        "WF_FEATURE_TOP_K": wf_feature_top_k,
    }


def _normalize_benchmark_compare(raw_value: object | None) -> list[dict[str, str]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, (list, tuple)):
        raise SystemExit(
            "backtest.benchmark_compare must be a list of compare benchmark specs."
        )

    normalized: list[dict[str, str]] = []
    for idx, item in enumerate(raw_value):
        name: str | None = None
        returns_file: str | None = None
        symbol: str | None = None
        if isinstance(item, str):
            returns_file = str(item).strip() or None
        elif isinstance(item, Mapping):
            name_raw = item.get("name")
            if name_raw is not None:
                name = str(name_raw).strip() or None
            returns_file_raw = (
                item.get("returns_file")
                or item.get("file")
                or item.get("path")
            )
            if returns_file_raw is not None:
                returns_file = str(returns_file_raw).strip() or None
            symbol_raw = item.get("symbol") or item.get("benchmark_symbol")
            if symbol_raw is not None:
                symbol = str(symbol_raw).strip() or None
        else:
            raise SystemExit(
                "backtest.benchmark_compare entries must be either strings or mappings."
            )

        if bool(returns_file) == bool(symbol):
            raise SystemExit(
                f"backtest.benchmark_compare[{idx}] must provide exactly one of returns_file or symbol."
            )
        if not name:
            name = Path(returns_file).stem if returns_file else str(symbol)
        spec = {"name": name}
        if returns_file:
            spec["source_type"] = "returns_file"
            spec["returns_file"] = returns_file
        else:
            spec["source_type"] = "symbol"
            spec["symbol"] = str(symbol)
        normalized.append(spec)
    return normalized


def prepare_run_artifacts(
    *,
    config: dict[str, Any],
    config_label: str,
    output_dir: str | None,
    run_name: str | None,
    save_artifacts: bool,
    active_log_file: Path | None,
    default_runs_dir: Path,
    logger: logging.Logger,
) -> dict[str, Any]:
    output_root = output_dir or default_runs_dir.as_posix()
    output_root_path = resolve_repo_path(output_root)
    run_name_text = str(run_name or config_label)
    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_hash = config_hash(config)
    run_dir = output_root_path / f"{run_name_text}_{run_stamp}_{run_hash}"

    if save_artifacts:
        run_dir.mkdir(parents=True, exist_ok=True)
        active_log_file = setup_logging(config, default_log_file=run_dir / "run.log")
        logger.info("Artifacts will be saved to %s", run_dir)

    return {
        "OUTPUT_DIR": str(output_root_path),
        "run_name": run_name_text,
        "run_stamp": run_stamp,
        "run_hash": run_hash,
        "run_dir": run_dir,
        "active_log_file": active_log_file,
    }
