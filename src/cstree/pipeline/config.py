from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
from dotenv import load_dotenv
from market_data_platform.artifacts import (
    cache_dir_for,
    resolve_configured_artifacts_root,
    resolve_data_input_path,
    resolve_repo_path,
    runs_dir_for,
)
from market_data_platform.data_providers import normalize_market, resolve_provider

from ..config_utils import get_research_universe_config, resolve_pipeline_config
from ..date_utils import (
    is_relative_date_token as _is_relative_date_token,
    resolve_date_token as _resolve_date_token,
)
from ..execution import BpsCostModel, build_execution_model, required_pricing_columns
from ..execution_sim import (
    build_execution_sim_config,
    required_execution_sim_columns,
)
from ..modeling import resolve_model_spec
from .config_eval import normalize_eval_settings  # noqa: F401  # re-exported compatibility
from .runtime import config_hash, setup_logging
from .stats import _ensure_execution_daily_fields
from .support import (
    load_symbols_file,
    load_universe_by_date,
    normalize_symbol_list,
    normalize_universe_symbol,
)


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
    universe_cfg = get_research_universe_config(config)
    label_cfg = config.get("label", {})
    features_cfg = config.get("features", {})
    fundamentals_cfg = config.get("fundamentals", {})
    model_cfg = config.get("model", {})
    eval_cfg = config.get("eval", {})
    backtest_cfg = config.get("backtest", {})
    live_cfg = config.get("live", {})
    if not isinstance(model_cfg, dict):
        raise SystemExit("model must be a mapping with keys: type, params, sample_weight_mode.")
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
        raise SystemExit("research_universe.mode must be one of: auto, pit, static.")
    require_by_date = bool(universe_cfg.get("require_by_date", False))

    symbols = normalize_symbol_list(universe_cfg.get("symbols"))
    symbols_file = universe_cfg.get("symbols_file")
    by_date_file = universe_cfg.get("by_date_file")
    universe_by_date = None
    universe_mode_effective = universe_mode

    if not symbols and symbols_file:
        symbols = load_symbols_file(resolve_data_input_path(symbols_file))

    if by_date_file:
        universe_by_date = load_universe_by_date(
            resolve_data_input_path(by_date_file),
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
                "research_universe.mode=static but by_date_file provided; using PIT universe."
            )
    else:
        if require_by_date or universe_mode == "pit":
            raise SystemExit(
                "research_universe.by_date_file is required when "
                "research_universe.mode=pit or require_by_date=true."
            )
        universe_mode_effective = "static"
        if universe_mode == "auto":
            logger.warning(
                "Universe-by-date not provided; using static symbols (survivorship bias). "
                "Set research_universe.mode=static to acknowledge or provide by_date_file "
                "for PIT."
            )

    if not symbols:
        symbols = default_symbols

    symbols = list(dict.fromkeys(normalize_universe_symbol(symbol, market) for symbol in symbols))

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
    train_target_transform = str(label_cfg.get("train_target_transform", "none")).strip().lower()
    if train_target_transform not in {"none", "zscore", "rank"}:
        raise SystemExit("label.train_target_transform must be one of: none, zscore, rank.")
    train_target = target if train_target_transform == "none" else f"{target}__train_target"
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
        raise SystemExit("research_universe.suspended_policy must be one of: mark, filter.")
    return {
        "MIN_SYMBOLS_PER_DATE": min_symbols_per_date,
        "MIN_LISTED_DAYS": int(universe_cfg.get("min_listed_days", 0)),
        "MIN_TURNOVER": float(universe_cfg.get("min_turnover", 0)),
        "DROP_ST": bool(universe_cfg.get("drop_st", False)),
        "DROP_SUSPENDED": bool(universe_cfg.get("drop_suspended", True)),
        "SUSPENDED_POLICY": suspended_policy,
    }


_DEFAULT_FEATURES = (
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
)


def _as_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _resolve_fundamentals_settings(
    fundamentals_cfg: Mapping[str, Any],
    *,
    provider: str,
) -> dict[str, Any]:
    fundamentals_enabled = bool(fundamentals_cfg.get("enabled", False))
    fundamentals_source = str(fundamentals_cfg.get("source", "provider")).strip().lower()
    if fundamentals_source not in {"provider", "file"}:
        raise SystemExit("fundamentals.source must be one of: provider, file.")
    fundamentals_ffill_limit = fundamentals_cfg.get("ffill_limit")
    if fundamentals_ffill_limit is not None:
        fundamentals_ffill_limit = int(fundamentals_ffill_limit)
    provider_overlay_cfg = fundamentals_cfg.get("provider_overlay")
    if provider_overlay_cfg is None:
        provider_overlay_cfg = {}
    if not isinstance(provider_overlay_cfg, Mapping):
        raise SystemExit("fundamentals.provider_overlay must be a mapping when provided.")
    overlay_source = str(provider_overlay_cfg.get("source", "provider")).strip().lower()
    if overlay_source not in {"provider", "daily_clean"}:
        raise SystemExit("fundamentals.provider_overlay.source must be one of: provider, daily_clean.")

    return {
        "fundamentals_cfg": fundamentals_cfg,
        "provider_overlay_cfg": provider_overlay_cfg,
        "FUNDAMENTALS_ENABLED": fundamentals_enabled,
        "FUNDAMENTALS_SOURCE": fundamentals_source,
        "FUNDAMENTALS_FILE": fundamentals_cfg.get("file"),
        "FUNDAMENTALS_FEATURES": normalize_symbol_list(fundamentals_cfg.get("features")),
        "FUNDAMENTALS_AUTO_ADD": bool(fundamentals_cfg.get("auto_add_features", True)),
        "FUNDAMENTALS_ALLOW_MISSING": bool(
            fundamentals_cfg.get("allow_missing_features", False)
        ),
        "FUNDAMENTALS_FFILL": bool(fundamentals_cfg.get("ffill", True)),
        "FUNDAMENTALS_FFILL_LIMIT": fundamentals_ffill_limit,
        "FUNDAMENTALS_LOG_MCAP": bool(fundamentals_cfg.get("log_market_cap", False)),
        "FUNDAMENTALS_MCAP_COL": str(
            fundamentals_cfg.get("market_cap_col", "market_cap")
        ).strip(),
        "FUNDAMENTALS_LOG_MCAP_COL": str(
            fundamentals_cfg.get("log_market_cap_col", "log_mcap")
        ).strip(),
        "FUNDAMENTALS_REQUIRED": bool(fundamentals_cfg.get("required", False)),
        "FUNDAMENTALS_PROVIDER": (
            resolve_provider({"provider": fundamentals_cfg.get("provider")})
            if fundamentals_cfg.get("provider")
            else provider
        ),
        "FUNDAMENTALS_PROVIDER_OVERLAY_ENABLED": bool(
            provider_overlay_cfg.get("enabled", False)
        ),
        "FUNDAMENTALS_PROVIDER_OVERLAY_SOURCE": overlay_source,
        "FUNDAMENTALS_PROVIDER_OVERLAY_FEATURES": normalize_symbol_list(
            provider_overlay_cfg.get("features")
        ),
        "FUNDAMENTALS_PROVIDER_OVERLAY_AUTO_ADD": bool(
            provider_overlay_cfg.get("auto_add_features", True)
        ),
        "FUNDAMENTALS_PROVIDER_OVERLAY_REQUIRED": bool(
            provider_overlay_cfg.get("required", False)
        ),
        "FUNDAMENTALS_PROVIDER_OVERLAY_PROVIDER": (
            resolve_provider({"provider": provider_overlay_cfg.get("provider")})
            if provider_overlay_cfg.get("provider")
            else provider
        ),
    }


def _resolve_industry_settings(industry_cfg: Mapping[str, Any]) -> dict[str, Any]:
    industry_source = str(industry_cfg.get("source", "file")).strip().lower()
    if industry_source not in {"file"}:
        raise SystemExit("industry.source must be 'file'.")
    industry_ffill_limit = industry_cfg.get("ffill_limit")
    if industry_ffill_limit is not None:
        industry_ffill_limit = int(industry_ffill_limit)
    return {
        "INDUSTRY_ENABLED": bool(industry_cfg.get("enabled", False)),
        "INDUSTRY_SOURCE": industry_source,
        "INDUSTRY_FILE": industry_cfg.get("file"),
        "INDUSTRY_KEEP_COLUMNS": normalize_symbol_list(industry_cfg.get("keep_columns")),
        "INDUSTRY_FFILL": bool(industry_cfg.get("ffill", False)),
        "INDUSTRY_FFILL_LIMIT": industry_ffill_limit,
        "INDUSTRY_REQUIRED": bool(industry_cfg.get("required", False)),
    }


def _resolve_feature_settings(
    features_cfg: Mapping[str, Any],
    *,
    fundamentals_settings: Mapping[str, Any],
    wf_feature_top_k: int,
) -> dict[str, Any]:
    feature_list = features_cfg.get("list") or []
    features = normalize_symbol_list(feature_list) if feature_list else list(_DEFAULT_FEATURES)
    fundamentals_features = fundamentals_settings["FUNDAMENTALS_FEATURES"]
    if (
        fundamentals_settings["FUNDAMENTALS_ENABLED"]
        and fundamentals_settings["FUNDAMENTALS_AUTO_ADD"]
        and fundamentals_features
    ):
        features = list(dict.fromkeys(features + fundamentals_features))
    overlay_features = fundamentals_settings["FUNDAMENTALS_PROVIDER_OVERLAY_FEATURES"]
    if (
        fundamentals_settings["FUNDAMENTALS_PROVIDER_OVERLAY_ENABLED"]
        and fundamentals_settings["FUNDAMENTALS_PROVIDER_OVERLAY_AUTO_ADD"]
        and overlay_features
    ):
        features = list(dict.fromkeys(features + overlay_features))

    cs_cfg = features_cfg.get("cross_sectional") or {}
    cs_method = (
        str(cs_cfg.get("method", "none")).strip().lower() if isinstance(cs_cfg, Mapping) else "none"
    )
    cs_winsorize_pct = cs_cfg.get("winsorize_pct") if isinstance(cs_cfg, Mapping) else None
    if cs_winsorize_pct is not None:
        cs_winsorize_pct = float(cs_winsorize_pct)
        if not 0 < cs_winsorize_pct < 0.5:
            raise SystemExit("features.cross_sectional.winsorize_pct must be between 0 and 0.5.")
    if cs_method not in {"none", "zscore", "rank"}:
        raise SystemExit("features.cross_sectional.method must be one of: none, zscore, rank.")

    missing_cfg = features_cfg.get("missing")
    if missing_cfg is None:
        missing_cfg = {}
    if not isinstance(missing_cfg, Mapping):
        raise SystemExit("features.missing must be a mapping when provided.")
    feature_missing_method = str(missing_cfg.get("method", "none")).strip().lower()
    if feature_missing_method not in {"none", "zero", "cross_sectional_median"}:
        raise SystemExit(
            "features.missing.method must be one of: none, zero, cross_sectional_median."
        )
    feature_missing_suffix = str(missing_cfg.get("indicator_suffix", "_missing")).strip()
    if bool(missing_cfg.get("add_indicators", False)) and not feature_missing_suffix:
        raise SystemExit("features.missing.indicator_suffix cannot be empty.")

    return {
        "FEATURES": features,
        "feature_params": features_cfg.get("params", {}),
        "CS_METHOD": cs_method,
        "CS_WINSORIZE_PCT": cs_winsorize_pct,
        "FEATURE_MISSING_METHOD": feature_missing_method,
        "FEATURE_MISSING_FEATURES": normalize_symbol_list(missing_cfg.get("features")),
        "FEATURE_MISSING_ADD_INDICATORS": bool(missing_cfg.get("add_indicators", False)),
        "FEATURE_MISSING_SUFFIX": feature_missing_suffix,
        "WF_FEATURE_TOP_K": min(wf_feature_top_k, max(1, len(features))),
    }


def _normalize_sample_weight_params(raw_value: object | None) -> dict[str, Any]:
    if raw_value is None:
        return {}
    if isinstance(raw_value, Mapping):
        return dict(raw_value)
    raise SystemExit("model.sample_weight_params must be a mapping when provided.")


def _canonical_sample_weight_mode(raw_value: object) -> str:
    sample_weight_mode = str(raw_value).strip().lower()
    if sample_weight_mode in {"", "none", "null"}:
        return "none"
    if sample_weight_mode in {"date"}:
        return "date_equal"
    if sample_weight_mode in {"time_decay", "exp_decay", "exp"}:
        return "exp_decay"
    if sample_weight_mode not in {"none", "date_equal", "exp_decay"}:
        raise SystemExit("model.sample_weight_mode must be one of: none, date_equal, exp_decay.")
    return sample_weight_mode


def _validate_exp_decay_sample_weight_params(sample_weight_params: Mapping[str, Any]) -> None:
    halflife_raw = sample_weight_params.get("halflife", sample_weight_params.get("half_life"))
    decay_rate_raw = sample_weight_params.get("decay_rate", sample_weight_params.get("rate"))
    if halflife_raw is None and decay_rate_raw is None:
        raise SystemExit(
            "model.sample_weight_mode=exp_decay requires "
            "model.sample_weight_params.halflife or decay_rate."
        )
    if halflife_raw is not None:
        try:
            halflife = float(halflife_raw)
        except (TypeError, ValueError) as exc:
            raise SystemExit("model.sample_weight_params.halflife must be a number.") from exc
        if not np.isfinite(halflife) or halflife <= 0:
            raise SystemExit("model.sample_weight_params.halflife must be > 0.")
    if decay_rate_raw is not None:
        try:
            decay_rate = float(decay_rate_raw)
        except (TypeError, ValueError) as exc:
            raise SystemExit("model.sample_weight_params.decay_rate must be a number.") from exc
        if not np.isfinite(decay_rate) or decay_rate <= 0 or decay_rate > 1:
            raise SystemExit("model.sample_weight_params.decay_rate must be in (0, 1].")
    min_weight_raw = sample_weight_params.get("min_weight")
    if min_weight_raw is not None:
        try:
            min_weight = float(min_weight_raw)
        except (TypeError, ValueError) as exc:
            raise SystemExit("model.sample_weight_params.min_weight must be a number.") from exc
        if not np.isfinite(min_weight) or min_weight < 0:
            raise SystemExit("model.sample_weight_params.min_weight must be >= 0.")


def _resolve_sample_weight_settings(model_cfg: Mapping[str, Any]) -> dict[str, Any]:
    sample_weight_mode = _canonical_sample_weight_mode(
        model_cfg.get("sample_weight_mode", "none")
    )
    sample_weight_params = _normalize_sample_weight_params(model_cfg.get("sample_weight_params"))
    if sample_weight_mode == "exp_decay":
        _validate_exp_decay_sample_weight_params(sample_weight_params)
    return {
        "SAMPLE_WEIGHT_MODE": sample_weight_mode,
        "SAMPLE_WEIGHT_PARAMS": sample_weight_params,
    }


def _resolve_train_window_settings(model_cfg: Mapping[str, Any]) -> dict[str, Any]:
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
            raise SystemExit("model.train_window.size must be a positive integer.") from exc
        if train_window_size <= 0:
            raise SystemExit("model.train_window.size must be a positive integer.")
    train_window_unit = str(train_window_cfg.get("unit", "dates")).strip().lower()
    if train_window_unit not in {"dates", "years"}:
        raise SystemExit("model.train_window.unit must be one of: dates, years.")
    if train_window_mode == "rolling" and train_window_size is None:
        raise SystemExit(
            "model.train_window.size is required when model.train_window.mode=rolling."
        )
    return {
        "TRAIN_WINDOW_MODE": train_window_mode,
        "TRAIN_WINDOW_SIZE": train_window_size,
        "TRAIN_WINDOW_UNIT": train_window_unit,
    }


def _resolve_model_settings(model_cfg: Mapping[str, Any]) -> dict[str, Any]:
    try:
        model_type, model_params = resolve_model_spec(model_cfg)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    return {
        "MODEL_TYPE": model_type,
        "MODEL_PARAMS": model_params,
        "MODEL_CFG": {"type": model_type, "params": model_params},
        **_resolve_sample_weight_settings(model_cfg),
        **_resolve_train_window_settings(model_cfg),
    }


def _normalize_positive_int_or_none(raw_value: object | None, *, error_message: str) -> int | None:
    if raw_value is None:
        return None
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise SystemExit(error_message) from exc
    if value <= 0:
        raise SystemExit(error_message)
    return value


def _normalize_optional_text(raw_value: object | None) -> str | None:
    if raw_value is None:
        return None
    return str(raw_value).strip() or None


def _normalize_backtest_tearsheet_enabled(backtest_cfg: Mapping[str, Any]) -> bool:
    raw_value = backtest_cfg.get("tearsheet")
    if raw_value is None:
        raw_value = backtest_cfg.get("tearsheet_enabled", False)
    if isinstance(raw_value, bool):
        return raw_value
    if isinstance(raw_value, Mapping):
        return bool(raw_value.get("enabled", False))
    if raw_value is None:
        return False
    raise SystemExit("backtest.tearsheet must be a boolean or a mapping with enabled.")


def _resolve_backtest_base_settings(
    backtest_cfg: Mapping[str, Any],
    *,
    eval_top_k: int,
    eval_rebalance_frequency: str,
    eval_transaction_cost_bps: float,
    label_horizon_days: int,
) -> dict[str, Any]:
    backtest_benchmark = backtest_cfg.get("benchmark_symbol")
    if backtest_benchmark is not None:
        backtest_benchmark = str(backtest_benchmark).strip() or None
    backtest_benchmark_returns_file = backtest_cfg.get("benchmark_returns_file")
    if backtest_benchmark_returns_file is not None:
        backtest_benchmark_returns_file = str(backtest_benchmark_returns_file).strip() or None
    if backtest_benchmark and backtest_benchmark_returns_file:
        raise SystemExit(
            "backtest.benchmark_symbol and backtest.benchmark_returns_file are mutually exclusive."
        )

    backtest_weighting = str(backtest_cfg.get("weighting", "equal")).strip().lower()
    if backtest_weighting not in {"equal", "signal"}:
        raise SystemExit("backtest.weighting must be one of: equal, signal.")
    backtest_group_col = backtest_cfg.get("group_col")
    if backtest_group_col is not None:
        backtest_group_col = str(backtest_group_col).strip() or None
    backtest_signal_direction_raw = backtest_cfg.get("signal_direction")
    if backtest_signal_direction_raw is not None:
        backtest_signal_direction_raw = float(backtest_signal_direction_raw)
        if backtest_signal_direction_raw == 0:
            raise SystemExit("backtest.signal_direction cannot be 0.")

    backtest_exit_mode = str(backtest_cfg.get("exit_mode", "rebalance")).strip().lower()
    if backtest_exit_mode not in {"rebalance", "label_horizon"}:
        raise SystemExit("backtest.exit_mode must be one of: rebalance, label_horizon.")
    backtest_exit_horizon_days = backtest_cfg.get("exit_horizon_days")
    if backtest_exit_mode == "label_horizon":
        if backtest_exit_horizon_days is None:
            backtest_exit_horizon_days = label_horizon_days
        backtest_exit_horizon_days = int(backtest_exit_horizon_days)

    return {
        "BACKTEST_ENABLED": bool(backtest_cfg.get("enabled", True)),
        "BACKTEST_TOP_K": int(backtest_cfg.get("top_k", eval_top_k)),
        "BACKTEST_REBALANCE_FREQUENCY": backtest_cfg.get(
            "rebalance_frequency",
            eval_rebalance_frequency,
        ),
        "BACKTEST_COST_BPS": float(
            backtest_cfg.get("transaction_cost_bps", eval_transaction_cost_bps)
        ),
        "BACKTEST_TRADING_DAYS_PER_YEAR": int(backtest_cfg.get("trading_days_per_year", 252)),
        "BACKTEST_BENCHMARK": backtest_benchmark,
        "BACKTEST_BENCHMARK_RETURNS_FILE": backtest_benchmark_returns_file,
        "BACKTEST_BENCHMARK_COMPARE": _normalize_benchmark_compare(
            backtest_cfg.get("benchmark_compare")
        ),
        "BACKTEST_TEARSHEET_ENABLED": _normalize_backtest_tearsheet_enabled(backtest_cfg),
        "BACKTEST_LONG_ONLY": bool(backtest_cfg.get("long_only", True)),
        "BACKTEST_BUFFER_EXIT": int(backtest_cfg.get("buffer_exit", 0)),
        "BACKTEST_BUFFER_ENTRY": int(backtest_cfg.get("buffer_entry", 0)),
        "BACKTEST_WEIGHTING": backtest_weighting,
        "BACKTEST_GROUP_COL": backtest_group_col,
        "BACKTEST_MAX_NAMES_PER_GROUP": _normalize_positive_int_or_none(
            backtest_cfg.get("max_names_per_group"),
            error_message="backtest.max_names_per_group must be a positive integer.",
        ),
        "BACKTEST_SIGNAL_DIRECTION_RAW": backtest_signal_direction_raw,
        "BACKTEST_SHORT_K": (
            int(backtest_cfg.get("short_k")) if backtest_cfg.get("short_k") is not None else None
        ),
        "BACKTEST_EXIT_MODE": backtest_exit_mode,
        "BACKTEST_EXIT_HORIZON_DAYS": backtest_exit_horizon_days,
        "BACKTEST_EXIT_PRICE_POLICY": str(
            backtest_cfg.get("exit_price_policy", "strict")
        ).strip().lower(),
        "BACKTEST_EXIT_FALLBACK_POLICY": str(
            backtest_cfg.get("exit_fallback_policy", "ffill")
        ).strip().lower(),
        "BACKTEST_TRADABLE_COL": _normalize_optional_text(
            backtest_cfg.get("tradable_col", "is_tradable")
        ),
    }


def _merge_execution_cfg(
    *,
    execution_cfg: Mapping[str, Any],
    backtest_cfg: Mapping[str, Any],
) -> Mapping[str, Any]:
    backtest_execution_cfg = backtest_cfg.get("execution")
    if not isinstance(backtest_execution_cfg, Mapping):
        return execution_cfg

    merged_execution_cfg = dict(execution_cfg)
    for key, value in backtest_execution_cfg.items():
        if isinstance(value, Mapping) and isinstance(merged_execution_cfg.get(key), Mapping):
            nested = dict(merged_execution_cfg[key])
            nested.update(value)
            merged_execution_cfg[key] = nested
        else:
            merged_execution_cfg[key] = value
    return merged_execution_cfg


def _resolve_backtest_execution_settings(
    *,
    data_cfg: Mapping[str, Any],
    execution_cfg: Mapping[str, Any],
    backtest_cfg: Mapping[str, Any],
    backtest_settings: Mapping[str, Any],
    provider: str,
    price_col: str,
) -> dict[str, Any]:
    execution_cfg_resolved = _merge_execution_cfg(
        execution_cfg=execution_cfg,
        backtest_cfg=backtest_cfg,
    )
    backtest_execution_source = (
        "explicit_execution_config"
        if isinstance(execution_cfg_resolved, Mapping) and bool(execution_cfg_resolved)
        else "default_flat_cost"
    )
    exit_price_policy = backtest_settings["BACKTEST_EXIT_PRICE_POLICY"]
    if exit_price_policy not in {"strict", "ffill", "delay"}:
        raise SystemExit("backtest.exit_price_policy must be one of: strict, ffill, delay.")
    exit_fallback_policy = backtest_settings["BACKTEST_EXIT_FALLBACK_POLICY"]
    if exit_fallback_policy not in {"ffill", "none"}:
        raise SystemExit("backtest.exit_fallback_policy must be one of: ffill, none.")

    execution_model = build_execution_model(
        execution_cfg_resolved,
        default_cost_bps=backtest_settings["BACKTEST_COST_BPS"],
        default_exit_price_policy=exit_price_policy,
        default_exit_fallback_policy=exit_fallback_policy,
        default_price_col=price_col,
    )
    backtest_cost_bps_effective = backtest_settings["BACKTEST_COST_BPS"]
    backtest_cost_bps_report = None
    if isinstance(execution_model.cost_model, BpsCostModel):
        backtest_cost_bps_effective = float(execution_model.cost_model.bps)
        backtest_cost_bps_report = backtest_cost_bps_effective

    default_sim_liquidity_col = str(
        getattr(execution_model.slippage_model, "amount_col", "medadv20_amount")
        or "medadv20_amount"
    )
    default_sim_portfolio_value = float(
        getattr(execution_model.slippage_model, "portfolio_value", 1_000_000.0)
        or 1_000_000.0
    )
    try:
        execution_sim_config = build_execution_sim_config(
            backtest_cfg.get("execution_sim"),
            default_portfolio_value=default_sim_portfolio_value,
            default_liquidity_col=default_sim_liquidity_col,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    execution_sim_pricing_cols = required_execution_sim_columns(
        execution_sim_config,
        price_col=execution_model.entry_policy.price_col,
        tradable_col=backtest_settings["BACKTEST_TRADABLE_COL"],
    )
    execution_pricing_cols = required_pricing_columns(execution_model) | execution_sim_pricing_cols
    _ensure_execution_daily_fields(
        data_cfg=data_cfg,
        provider=provider,
        required_columns=execution_pricing_cols | {price_col},
    )
    return {
        "BACKTEST_EXIT_PRICE_POLICY": execution_model.exit_policy.price_policy,
        "BACKTEST_EXIT_FALLBACK_POLICY": execution_model.exit_policy.fallback_policy,
        "execution_model": execution_model,
        "execution_sim_config": execution_sim_config,
        "EXECUTION_SIM_PRICING_COLS": execution_sim_pricing_cols,
        "EXECUTION_PRICING_COLS": execution_pricing_cols,
        "BACKTEST_COST_BPS_EFFECTIVE": backtest_cost_bps_effective,
        "BACKTEST_COST_BPS_REPORT": backtest_cost_bps_report,
        "BACKTEST_EXECUTION_SOURCE": backtest_execution_source,
    }


def _resolve_backtest_settings(
    *,
    data_cfg: Mapping[str, Any],
    execution_cfg: Mapping[str, Any],
    backtest_cfg: Mapping[str, Any],
    provider: str,
    price_col: str,
    label_horizon_days: int,
    eval_top_k: int,
    eval_rebalance_frequency: str,
    eval_transaction_cost_bps: float,
) -> dict[str, Any]:
    backtest_settings = _resolve_backtest_base_settings(
        backtest_cfg,
        eval_top_k=eval_top_k,
        eval_rebalance_frequency=eval_rebalance_frequency,
        eval_transaction_cost_bps=eval_transaction_cost_bps,
        label_horizon_days=label_horizon_days,
    )
    backtest_settings.update(
        _resolve_backtest_execution_settings(
            data_cfg=data_cfg,
            execution_cfg=execution_cfg,
            backtest_cfg=backtest_cfg,
            backtest_settings=backtest_settings,
            provider=provider,
            price_col=price_col,
        )
    )
    return backtest_settings


def _resolve_live_settings(live_cfg: Mapping[str, Any]) -> dict[str, Any]:
    live_train_mode = str(live_cfg.get("train_mode", "full")).strip().lower()
    if live_train_mode not in {"full", "train"}:
        raise SystemExit("live.train_mode must be one of: full, train.")
    return {
        "LIVE_ENABLED": bool(live_cfg.get("enabled", False)),
        "LIVE_AS_OF": live_cfg.get("as_of", "t-1"),
        "LIVE_SIGNAL_ASOF": live_cfg.get("signal_asof"),
        "LIVE_ENTRY_DATE": live_cfg.get("entry_date"),
        "LIVE_TRAIN_MODE": live_train_mode,
    }


def resolve_runtime_settings(
    *,
    data_cfg: Mapping[str, Any] | None,
    execution_cfg: Mapping[str, Any] | None,
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
    data_cfg = _as_mapping(data_cfg)
    execution_cfg = _as_mapping(execution_cfg)
    features_cfg = _as_mapping(features_cfg)
    fundamentals_cfg = _as_mapping(fundamentals_cfg)
    industry_cfg = _as_mapping(industry_cfg)
    model_cfg = _as_mapping(model_cfg)
    backtest_cfg = _as_mapping(backtest_cfg)
    live_cfg = _as_mapping(live_cfg)

    fundamentals_settings = _resolve_fundamentals_settings(
        fundamentals_cfg,
        provider=provider,
    )
    return {
        **fundamentals_settings,
        **_resolve_industry_settings(industry_cfg),
        **_resolve_feature_settings(
            features_cfg,
            fundamentals_settings=fundamentals_settings,
            wf_feature_top_k=wf_feature_top_k,
        ),
        **_resolve_model_settings(model_cfg),
        **_resolve_backtest_settings(
            data_cfg=data_cfg,
            execution_cfg=execution_cfg,
            backtest_cfg=backtest_cfg,
            provider=provider,
            price_col=price_col,
            label_horizon_days=label_horizon_days,
            eval_top_k=eval_top_k,
            eval_rebalance_frequency=eval_rebalance_frequency,
            eval_transaction_cost_bps=eval_transaction_cost_bps,
        ),
        **_resolve_live_settings(live_cfg),
    }

def _normalize_benchmark_compare(raw_value: object | None) -> list[dict[str, str]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, (list, tuple)):
        raise SystemExit("backtest.benchmark_compare must be a list of compare benchmark specs.")

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
            returns_file_raw = item.get("returns_file") or item.get("file") or item.get("path")
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
