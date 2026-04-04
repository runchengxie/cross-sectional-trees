from __future__ import annotations

from collections.abc import Callable, Mapping
import logging
from pathlib import Path
import sys
from typing import Any

import pandas as pd

from ..artifacts import resolve_repo_path
from ..data_interface import DataInterface
from ..data_providers import fundamentals_provider_supported
from .config import (
    normalize_eval_settings,
    normalize_universe_filters,
    prepare_run_artifacts,
    resolve_date_range_and_label_settings,
    resolve_runtime_settings,
    resolve_universe_inputs,
)
from .quality import run_quality_preflight


def prepare_pipeline_setup(
    *,
    loaded: Mapping[str, Any],
    fail_on_quality: str | None,
    logger: logging.Logger,
    default_symbols: list[str],
    quality_preflight_fn: Callable[..., Mapping[str, Any]] = run_quality_preflight,
) -> dict[str, Any]:
    config = loaded["config"]
    config_label = loaded["config_label"]
    active_log_file = loaded["active_log_file"]
    data_cfg = loaded["data_cfg"]
    market = loaded["market"]
    universe_cfg = loaded["universe_cfg"]
    label_cfg = loaded["label_cfg"]
    features_cfg = loaded["features_cfg"]
    fundamentals_cfg = loaded["fundamentals_cfg"]
    model_cfg = loaded["model_cfg"]
    eval_cfg = loaded["eval_cfg"]
    backtest_cfg = loaded["backtest_cfg"]
    live_cfg = loaded["live_cfg"]
    cache_dir = loaded["cache_dir"]
    default_runs_dir = loaded["runs_dir"]

    data_interface = DataInterface(market, data_cfg, cache_dir=cache_dir, logger=logger)
    provider = data_interface.provider

    universe_inputs = resolve_universe_inputs(
        universe_cfg,
        market=market,
        logger=logger,
        default_symbols=default_symbols,
    )
    date_label_settings = resolve_date_range_and_label_settings(
        data_cfg=data_cfg,
        label_cfg=label_cfg,
        eval_cfg=eval_cfg,
        live_cfg=live_cfg,
        market=market,
        provider=provider,
        logger=logger,
    )
    eval_settings = normalize_eval_settings(eval_cfg, backtest_cfg=backtest_cfg)
    if eval_settings["BUCKET_IC_ENABLED"] and not eval_settings["BUCKET_IC_SCHEMES"]:
        logger.warning("eval.bucket_ic.enabled=true but no schemes configured.")

    universe_filters = normalize_universe_filters(
        universe_cfg,
        n_quantiles=eval_settings["N_QUANTILES"],
    )
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
        market=market,
        price_col=date_label_settings["PRICE_COL"],
        label_horizon_days=date_label_settings["LABEL_HORIZON_DAYS"],
        label_shift_days=date_label_settings["LABEL_SHIFT_DAYS"],
        label_horizon_mode=date_label_settings["LABEL_HORIZON_MODE"],
        label_rebalance_frequency=date_label_settings["LABEL_REBALANCE_FREQUENCY"],
        train_target=date_label_settings["TRAIN_TARGET"],
        eval_top_k=eval_settings["TOP_K"],
        eval_rebalance_frequency=eval_settings["REBALANCE_FREQUENCY"],
        eval_transaction_cost_bps=eval_settings["TRANSACTION_COST_BPS"],
        eval_buffer_exit=eval_settings["EVAL_BUFFER_EXIT"],
        eval_buffer_entry=eval_settings["EVAL_BUFFER_ENTRY"],
        wf_feature_top_k=eval_settings["WF_FEATURE_TOP_K"],
    )
    if runtime_settings["LIVE_ENABLED"] and not eval_settings["SAVE_ARTIFACTS"]:
        raise SystemExit(
            "live.enabled=true requires eval.save_artifacts=true to persist holdings."
        )

    output_dir = eval_settings["OUTPUT_DIR"] or default_runs_dir.as_posix()
    run_artifacts = prepare_run_artifacts(
        config=config,
        config_label=config_label,
        output_dir=output_dir,
        run_name=eval_settings["RUN_NAME"],
        save_artifacts=eval_settings["SAVE_ARTIFACTS"],
        active_log_file=active_log_file,
        default_runs_dir=default_runs_dir,
        logger=logger,
    )
    quality_preflight = quality_preflight_fn(
        config=config,
        run_dir=run_artifacts["run_dir"] if eval_settings["SAVE_ARTIFACTS"] else None,
        save_artifacts=eval_settings["SAVE_ARTIFACTS"],
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
    if isinstance(quality_overall_verdict, Mapping) and bool(
        quality_overall_verdict.get("gate_triggered")
    ):
        quality_report = None
        quality_checks = (
            quality_preflight.get("checks")
            if isinstance(quality_preflight.get("checks"), list)
            else []
        )
        for item in quality_checks:
            if isinstance(item, Mapping) and item.get("report_file"):
                quality_report = str(item.get("report_file"))
                break
        detail = f" Report: {quality_report}" if quality_report else ""
        raise SystemExit(
            f"Pipeline quality gate failed: {quality_overall_verdict.get('message')}{detail}"
        )

    return {
        "data_interface": data_interface,
        "provider": provider,
        "universe_inputs": universe_inputs,
        "date_label_settings": date_label_settings,
        "eval_settings": eval_settings,
        "universe_filters": universe_filters,
        "industry_cfg": industry_cfg,
        "runtime_settings": runtime_settings,
        "run_artifacts": run_artifacts,
        "quality_summary": quality_summary,
    }


def resolve_effective_data_inputs(
    *,
    runtime_settings: Mapping[str, Any],
    market: str,
    logger: logging.Logger,
    load_benchmark_return_series: Callable[[Path], pd.Series],
) -> dict[str, Any]:
    effective_runtime_settings = dict(runtime_settings)
    fundamentals_enabled = bool(runtime_settings["FUNDAMENTALS_ENABLED"])
    fundamentals_source = runtime_settings["FUNDAMENTALS_SOURCE"]
    fundamentals_file = runtime_settings["FUNDAMENTALS_FILE"]
    fundamentals_features = runtime_settings["FUNDAMENTALS_FEATURES"]
    fundamentals_auto_add = runtime_settings["FUNDAMENTALS_AUTO_ADD"]
    fundamentals_required = runtime_settings["FUNDAMENTALS_REQUIRED"]
    fundamentals_provider = runtime_settings["FUNDAMENTALS_PROVIDER"]
    overlay_enabled = bool(runtime_settings["FUNDAMENTALS_PROVIDER_OVERLAY_ENABLED"])
    overlay_features = runtime_settings["FUNDAMENTALS_PROVIDER_OVERLAY_FEATURES"]
    overlay_auto_add = runtime_settings["FUNDAMENTALS_PROVIDER_OVERLAY_AUTO_ADD"]
    overlay_required = runtime_settings["FUNDAMENTALS_PROVIDER_OVERLAY_REQUIRED"]
    overlay_provider = runtime_settings["FUNDAMENTALS_PROVIDER_OVERLAY_PROVIDER"]
    industry_enabled = bool(runtime_settings["INDUSTRY_ENABLED"])
    industry_file = runtime_settings["INDUSTRY_FILE"]
    industry_required = runtime_settings["INDUSTRY_REQUIRED"]
    features = list(runtime_settings["FEATURES"])
    backtest_benchmark = runtime_settings["BACKTEST_BENCHMARK"]
    backtest_benchmark_returns_file = runtime_settings["BACKTEST_BENCHMARK_RETURNS_FILE"]
    backtest_benchmark_compare = runtime_settings["BACKTEST_BENCHMARK_COMPARE"]

    fundamentals_file_path: Path | None = None
    industry_file_path: Path | None = None

    if fundamentals_enabled:
        if fundamentals_source == "provider" and not fundamentals_provider_supported(
            fundamentals_provider, market
        ):
            message = (
                "Fundamentals provider mode currently supports only RQData market=hk; "
                "use source=file instead."
            )
            if fundamentals_required:
                sys.exit(message)
            logger.warning("%s Fundamentals disabled.", message)
            fundamentals_enabled = False
        if fundamentals_source == "file" and not fundamentals_file:
            message = "fundamentals.file is required when fundamentals.source=file."
            if fundamentals_required:
                sys.exit(message)
            logger.warning("%s Fundamentals disabled.", message)
            fundamentals_enabled = False
        if fundamentals_source == "file" and fundamentals_enabled:
            fundamentals_file_path = resolve_repo_path(fundamentals_file)
            if not fundamentals_file_path.exists():
                message = f"Fundamentals file not found: {fundamentals_file_path}"
                if fundamentals_required:
                    sys.exit(message)
                logger.warning("%s Fundamentals disabled.", message)
                fundamentals_enabled = False

    if industry_enabled:
        if not industry_file:
            message = "industry.file is required when industry.enabled=true."
            if industry_required:
                sys.exit(message)
            logger.warning("%s Industry join disabled.", message)
            industry_enabled = False
        else:
            industry_file_path = resolve_repo_path(industry_file)
            if not industry_file_path.exists():
                message = f"Industry file not found: {industry_file_path}"
                if industry_required:
                    sys.exit(message)
                logger.warning("%s Industry join disabled.", message)
                industry_enabled = False

    if overlay_enabled:
        if not fundamentals_enabled or fundamentals_source != "file":
            message = (
                "fundamentals.provider_overlay requires fundamentals.enabled=true "
                "and fundamentals.source=file."
            )
            if overlay_required:
                sys.exit(message)
            logger.warning("%s Provider overlay disabled.", message)
            overlay_enabled = False
        elif not fundamentals_provider_supported(overlay_provider, market):
            message = (
                "fundamentals.provider_overlay currently supports only RQData market=hk."
            )
            if overlay_required:
                sys.exit(message)
            logger.warning("%s Provider overlay disabled.", message)
            overlay_enabled = False

    if not fundamentals_enabled and fundamentals_auto_add and fundamentals_features:
        features = [feat for feat in features if feat not in fundamentals_features]
    if not overlay_enabled and overlay_auto_add and overlay_features:
        features = [feat for feat in features if feat not in overlay_features]

    benchmark_symbol = str(backtest_benchmark).strip() if backtest_benchmark else None
    benchmark_returns_file_path = (
        resolve_repo_path(backtest_benchmark_returns_file)
        if backtest_benchmark_returns_file
        else None
    )
    benchmark_return_series = (
        load_benchmark_return_series(benchmark_returns_file_path)
        if benchmark_returns_file_path is not None
        else pd.Series(dtype=float, name="benchmark_return")
    )
    benchmark_compare_specs: list[dict[str, Any]] = []
    for spec in backtest_benchmark_compare:
        returns_file_path = resolve_repo_path(spec["returns_file"])
        series = (
            benchmark_return_series.copy()
            if benchmark_returns_file_path is not None
            and returns_file_path == benchmark_returns_file_path
            else load_benchmark_return_series(returns_file_path)
        )
        benchmark_compare_specs.append(
            {
                "name": spec["name"],
                "returns_file_path": returns_file_path,
                "series": series,
            }
        )

    effective_runtime_settings.update(
        {
            "FUNDAMENTALS_ENABLED": fundamentals_enabled,
            "INDUSTRY_ENABLED": industry_enabled,
            "FUNDAMENTALS_PROVIDER_OVERLAY_ENABLED": overlay_enabled,
            "FEATURES": features,
        }
    )
    return {
        "runtime_settings": effective_runtime_settings,
        "fundamentals_file_path": fundamentals_file_path,
        "industry_file_path": industry_file_path,
        "benchmark_symbol": benchmark_symbol,
        "benchmark_returns_file_path": benchmark_returns_file_path,
        "benchmark_return_series": benchmark_return_series,
        "benchmark_compare_specs": benchmark_compare_specs,
    }
