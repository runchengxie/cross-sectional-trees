from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .stats import _normalize_bucket_schemes, _normalize_window_months
from .support import normalize_symbol_list


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
    eval_buffer_entry = int(eval_cfg.get("buffer_entry", backtest_cfg.get("buffer_entry", 0)))
    signal_direction_mode = str(eval_cfg.get("signal_direction_mode", "fixed")).strip().lower()
    if signal_direction_mode not in {"fixed", "train_ic", "cv_ic"}:
        raise SystemExit("eval.signal_direction_mode must be one of: fixed, train_ic, cv_ic.")
    signal_direction_raw = eval_cfg.get("signal_direction", 1.0)
    signal_direction = float(signal_direction_raw) if signal_direction_raw is not None else 1.0
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
        score_postprocess_method = str(score_postprocess_cfg.get("method", "none")).strip().lower()
        score_postprocess_columns = normalize_symbol_list(score_postprocess_cfg.get("columns"))
        score_postprocess_strength = float(score_postprocess_cfg.get("strength", 1.0))
        score_postprocess_min_obs_raw = score_postprocess_cfg.get("min_obs")
        if score_postprocess_min_obs_raw is not None:
            score_postprocess_min_obs = int(score_postprocess_min_obs_raw)
        enabled_raw = score_postprocess_cfg.get("enabled")
        score_postprocess_enabled = (
            bool(enabled_raw) if enabled_raw is not None else score_postprocess_method != "none"
        )
        if score_postprocess_method not in {"none", "neutralize"}:
            raise SystemExit("eval.score_postprocess.method must be one of: none, neutralize.")
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
                raise SystemExit("eval.score_postprocess.min_obs must be >= len(columns) + 1.")
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
        raise SystemExit("eval.save_scored_artifact=true requires eval.save_artifacts=true.")
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
