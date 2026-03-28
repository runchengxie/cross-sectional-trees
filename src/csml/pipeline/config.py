from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from ..artifacts import CACHE_DIR as DEFAULT_CACHE_DIR
from ..artifacts import resolve_repo_path
from ..config_utils import resolve_pipeline_config
from ..data_providers import normalize_market
from ..date_utils import is_relative_date_token as _is_relative_date_token
from ..date_utils import resolve_date_token as _resolve_date_token
from .runtime import config_hash, setup_logging
from .stats import _normalize_bucket_schemes, _normalize_window_months
from .support import load_symbols_file, load_universe_by_date, normalize_symbol_list


def load_run_config(
    config_ref: str | Path | None,
    *,
    default_cache_dir: Path = DEFAULT_CACHE_DIR,
) -> dict[str, Any]:
    resolved = resolve_pipeline_config(config_ref)
    config = resolved.data
    config_label = resolved.label
    config_path = resolved.path
    config_source = resolved.source
    active_log_file = setup_logging(config)

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
    cache_dir = resolve_repo_path(data_cfg.get("cache_dir", default_cache_dir.as_posix()))
    return {
        "config": config,
        "config_label": config_label,
        "config_path": config_path,
        "config_source": config_source,
        "active_log_file": active_log_file,
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
    run_name_text = str(run_name or config_label)
    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_hash = config_hash(config)
    run_dir = Path(output_root) / f"{run_name_text}_{run_stamp}_{run_hash}"

    if save_artifacts:
        run_dir.mkdir(parents=True, exist_ok=True)
        active_log_file = setup_logging(config, default_log_file=run_dir / "run.log")
        logger.info("Artifacts will be saved to %s", run_dir)

    return {
        "OUTPUT_DIR": output_root,
        "run_name": run_name_text,
        "run_stamp": run_stamp,
        "run_hash": run_hash,
        "run_dir": run_dir,
        "active_log_file": active_log_file,
    }
