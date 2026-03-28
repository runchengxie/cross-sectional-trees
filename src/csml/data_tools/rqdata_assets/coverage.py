from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
import sys

import numpy as np
import pandas as pd

from ...config_utils import resolve_pipeline_config
from ...rebalance import get_rebalance_dates
from ..symbols import ensure_symbol_columns
from .build import (
    _default_pipeline_fundamentals_path,
    _load_universe_by_date_frame,
    _pipeline_fundamentals_manifest_path,
    _resolve_build_fields,
)
from .shared import (
    DEFAULT_PIPELINE_FUNDAMENTALS_NAME,
    DERIVED_PIT_FEATURES,
    _load_manifest,
    _normalize_field_list,
    _normalize_frame_columns,
    _resolve_fields_with_overrides,
    _resolve_path,
)


def _resolve_fields(args) -> tuple[list[str], dict]:
    package = sys.modules.get("csml.data_tools.rqdata_assets")
    override = getattr(package, "_load_hk_financial_fields", None) if package is not None else None
    return _resolve_fields_with_overrides(
        args,
        load_hk_financial_fields_override=override,
    )


def _is_supported_pit_coverage_feature(feature: str, available_columns: set[str]) -> bool:
    if feature in available_columns:
        return True
    if feature == "days_since_report":
        return True
    if feature.startswith("delta_") or feature.startswith("growth_"):
        return _is_supported_pit_coverage_feature(feature.split("_", 1)[1], available_columns)
    return feature in DERIVED_PIT_FEATURES


def _compute_pit_coverage_series(
    frame: pd.DataFrame,
    feature: str,
    *,
    cache: dict[str, pd.Series],
) -> pd.Series:
    cached = cache.get(feature)
    if cached is not None:
        return cached

    index = frame.index

    def _nan_series() -> pd.Series:
        return pd.Series(np.nan, index=index, dtype=float)

    def _numeric(name: str) -> pd.Series:
        if name not in frame.columns:
            return _nan_series()
        return pd.to_numeric(frame[name], errors="coerce")

    def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
        valid_denominator = denominator.where(denominator.notna() & (denominator != 0))
        ratio = numerator / valid_denominator
        return ratio.replace([np.inf, -np.inf], np.nan)

    def _get(name: str) -> pd.Series:
        return _compute_pit_coverage_series(frame, name, cache=cache)

    if feature in frame.columns:
        series = _numeric(feature)
    elif feature == "sales":
        series = _get("revenue").combine_first(_get("operating_revenue"))
    elif feature == "debt":
        short_term_debt = _get("short_term_debt")
        long_term_loans = _get("long_term_loans")
        debt = short_term_debt.fillna(0.0) + long_term_loans.fillna(0.0)
        series = debt.where(~(short_term_debt.isna() & long_term_loans.isna()))
    elif feature == "profit_margin":
        series = _safe_ratio(_get("net_profit"), _get("sales"))
    elif feature == "operating_margin":
        series = _safe_ratio(_get("operating_profit"), _get("sales"))
    elif feature == "cfo_margin":
        series = _safe_ratio(_get("cash_flow_from_operating_activities"), _get("sales"))
    elif feature == "cfo_to_profit":
        series = _safe_ratio(_get("cash_flow_from_operating_activities"), _get("net_profit"))
    elif feature == "asset_turnover":
        series = _safe_ratio(_get("revenue"), _get("total_assets"))
    elif feature == "roa":
        series = _safe_ratio(_get("net_profit"), _get("total_assets"))
    elif feature == "leverage":
        series = _safe_ratio(_get("total_liabilities"), _get("total_assets"))
    elif feature == "cfo_to_assets":
        series = _safe_ratio(_get("cash_flow_from_operating_activities"), _get("total_assets"))
    elif feature == "debt_to_assets":
        series = _safe_ratio(_get("debt"), _get("total_assets"))
    elif feature == "debt_to_equity":
        series = _safe_ratio(_get("debt"), _get("total_equity"))
    elif feature == "cash_to_assets":
        series = _safe_ratio(_get("cash_and_equivalents"), _get("total_assets"))
    elif feature == "goodwill_to_assets":
        series = _safe_ratio(_get("goodwill"), _get("total_assets"))
    elif feature == "accrual_ratio":
        numerator = _get("net_profit") - _get("cash_flow_from_operating_activities")
        series = _safe_ratio(numerator, _get("total_assets"))
    elif feature == "receivables_to_revenue":
        series = _safe_ratio(_get("accounts_receivable"), _get("revenue"))
    elif feature == "inventory_to_revenue":
        series = _safe_ratio(_get("inventory"), _get("revenue"))
    elif feature == "working_capital_to_assets":
        working_capital = _get("accounts_receivable") + _get("inventory") - _get("accounts_payable")
        series = _safe_ratio(working_capital, _get("total_assets"))
    elif feature == "net_debt_to_assets":
        net_debt = _get("debt") - _get("cash_and_equivalents")
        series = _safe_ratio(net_debt, _get("total_assets"))
    elif feature == "days_since_report":
        series = pd.Series(0.0, index=index, dtype=float)
    elif feature.startswith("delta_"):
        base_feature = feature.removeprefix("delta_")
        base_series = _get(base_feature)
        series = base_series.groupby(frame["symbol"]).diff()
    elif feature.startswith("growth_"):
        base_feature = feature.removeprefix("growth_")
        current = _get(base_feature)
        previous = current.groupby(frame["symbol"]).shift()
        scale = ((current.abs() + previous.abs()) / 2.0).where(
            lambda values: values.notna() & (values != 0)
        )
        growth = (current - previous) / scale
        series = growth.replace([np.inf, -np.inf], np.nan)
    else:
        series = _nan_series()

    cache[feature] = series
    return series


def _resolve_pit_coverage_features(
    *,
    args,
    config_data: Mapping[str, object] | None,
    manifest: Mapping[str, object] | None,
    available_columns: Sequence[str],
) -> tuple[list[str], dict[str, object]]:
    if getattr(args, "field_profile", None) or getattr(args, "field", None) or getattr(args, "fields_file", None):
        raw_features, metadata = _resolve_fields(args)
        features = _normalize_field_list(raw_features)
        source = "explicit"
        requested_config_features: list[str] = []
    else:
        requested_config_features = []
        if config_data:
            fundamentals_cfg = config_data.get("fundamentals")
            if isinstance(fundamentals_cfg, Mapping):
                raw_config_features = fundamentals_cfg.get("features")
                if isinstance(raw_config_features, Sequence) and not isinstance(raw_config_features, str):
                    requested_config_features = _normalize_field_list(raw_config_features)
        if requested_config_features:
            features = requested_config_features
            metadata = {
                "count": len(features),
                "field_profile": [],
                "fields_file": [],
                "source": "config.fundamentals.features",
            }
            source = "config.fundamentals.features"
        else:
            features, metadata = _resolve_build_fields(
                args=args,
                manifest=manifest,
                available_columns=available_columns,
            )
            source = str(metadata.get("source") or "asset_manifest")

    available_set = set(_normalize_field_list(available_columns))
    supported_features = [
        feature for feature in features if _is_supported_pit_coverage_feature(feature, available_set)
    ]
    ignored_features = [feature for feature in features if feature not in supported_features]
    if not supported_features:
        raise SystemExit(
            "No PIT coverage features could be resolved. "
            "Check --field/--config or confirm the fundamentals file columns."
        )
    metadata = dict(metadata)
    metadata.update(
        {
            "source": source,
            "requested_features": features,
            "supported_features": supported_features,
            "ignored_features": ignored_features,
        }
    )
    return supported_features, metadata


def _resolve_trainable_pit_features(
    *,
    args,
    config_data: Mapping[str, object] | None,
    available_columns: Sequence[str],
    fallback_features: Sequence[str],
    fallback_metadata: Mapping[str, object],
) -> tuple[list[str], dict[str, object]]:
    explicit_requested = bool(
        getattr(args, "field_profile", None)
        or getattr(args, "field", None)
        or getattr(args, "fields_file", None)
    )
    available_set = set(_normalize_field_list(available_columns))
    if explicit_requested or not isinstance(config_data, Mapping):
        requested_features = list(fallback_metadata.get("requested_features") or fallback_features)
        supported_features = [
            feature
            for feature in fallback_features
            if _is_supported_pit_coverage_feature(feature, available_set)
        ]
        ignored_features = [feature for feature in requested_features if feature not in supported_features]
        return supported_features, {
            "source": str(fallback_metadata.get("source") or "explicit"),
            "requested_features": requested_features,
            "supported_features": supported_features,
            "ignored_features": ignored_features,
            "non_pit_ignored_features": ignored_features,
        }

    features_cfg = config_data.get("features")
    features_cfg = features_cfg if isinstance(features_cfg, Mapping) else {}
    fundamentals_cfg = config_data.get("fundamentals")
    fundamentals_cfg = fundamentals_cfg if isinstance(fundamentals_cfg, Mapping) else {}

    model_features = _normalize_field_list(features_cfg.get("list") or [])
    source = "config.features.list"
    if bool(fundamentals_cfg.get("enabled", False)) and bool(
        fundamentals_cfg.get("auto_add_features", True)
    ):
        fundamentals_features = _normalize_field_list(fundamentals_cfg.get("features") or [])
        if fundamentals_features:
            model_features = list(dict.fromkeys(model_features + fundamentals_features))
            source = "config.features.list+fundamentals.auto_add_features"

    if not model_features:
        requested_features = list(fallback_metadata.get("requested_features") or fallback_features)
        supported_features = [
            feature
            for feature in fallback_features
            if _is_supported_pit_coverage_feature(feature, available_set)
        ]
        ignored_features = [feature for feature in requested_features if feature not in supported_features]
        if not supported_features:
            raise SystemExit(
                "No PIT-backed model features resolved for trainable estimate. "
                "Pass --field/--config with PIT features or use --mode strict."
            )
        return supported_features, {
            "source": str(fallback_metadata.get("source") or "config.fallback"),
            "requested_features": requested_features,
            "supported_features": supported_features,
            "ignored_features": ignored_features,
            "non_pit_ignored_features": ignored_features,
        }

    supported_features = [
        feature for feature in model_features if _is_supported_pit_coverage_feature(feature, available_set)
    ]
    ignored_features = [feature for feature in model_features if feature not in supported_features]
    if not supported_features:
        raise SystemExit(
            "No PIT-backed model features resolved for trainable estimate. "
            "The config feature list only contains non-PIT features."
        )
    return supported_features, {
        "source": source,
        "requested_features": model_features,
        "supported_features": supported_features,
        "ignored_features": ignored_features,
        "non_pit_ignored_features": ignored_features,
    }


def _resolve_trainable_pit_settings(
    config_data: Mapping[str, object] | None,
    *,
    selected_features: Sequence[str],
) -> dict[str, object]:
    features_cfg = config_data.get("features") if isinstance(config_data, Mapping) else None
    features_cfg = features_cfg if isinstance(features_cfg, Mapping) else {}
    fundamentals_cfg = config_data.get("fundamentals") if isinstance(config_data, Mapping) else None
    fundamentals_cfg = fundamentals_cfg if isinstance(fundamentals_cfg, Mapping) else {}
    eval_cfg = config_data.get("eval") if isinstance(config_data, Mapping) else None
    eval_cfg = eval_cfg if isinstance(eval_cfg, Mapping) else {}
    label_cfg = config_data.get("label") if isinstance(config_data, Mapping) else None
    label_cfg = label_cfg if isinstance(label_cfg, Mapping) else {}

    missing_cfg = features_cfg.get("missing")
    missing_cfg = missing_cfg if isinstance(missing_cfg, Mapping) else {}
    missing_method = str(missing_cfg.get("method", "none")).strip().lower()
    if missing_method not in {"none", "zero", "cross_sectional_median"}:
        raise SystemExit(
            "features.missing.method must be one of: none, zero, cross_sectional_median."
        )
    missing_features = _normalize_field_list(missing_cfg.get("features") or [])
    if missing_features:
        missing_features = [feature for feature in missing_features if feature in selected_features]
    else:
        missing_features = list(selected_features)

    rebalance_frequency = str(
        eval_cfg.get("rebalance_frequency")
        or label_cfg.get("rebalance_frequency")
        or "Q"
    ).strip().upper()
    if not rebalance_frequency:
        rebalance_frequency = "Q"

    ffill_limit = fundamentals_cfg.get("ffill_limit")
    if ffill_limit in {"", "null"}:
        ffill_limit = None
    if ffill_limit is not None:
        try:
            ffill_limit = int(ffill_limit)
        except (TypeError, ValueError) as exc:
            raise SystemExit("fundamentals.ffill_limit must be an integer or null.") from exc

    return {
        "missing_method": missing_method,
        "missing_features": missing_features,
        "add_indicators": bool(missing_cfg.get("add_indicators", False)),
        "indicator_suffix": str(missing_cfg.get("indicator_suffix", "_missing")).strip() or "_missing",
        "rebalance_frequency": rebalance_frequency,
        "sample_on_rebalance_dates": bool(eval_cfg.get("sample_on_rebalance_dates", False)),
        "fundamentals_ffill": bool(fundamentals_cfg.get("ffill", True)),
        "fundamentals_ffill_limit": ffill_limit,
    }


def _build_trainable_period_grid(
    *,
    frame: pd.DataFrame,
    rebalance_frequency: str,
    sample_on_rebalance_dates: bool,
    universe_by_date: pd.DataFrame | None,
) -> tuple[pd.DataFrame, str]:
    if universe_by_date is not None and not universe_by_date.empty:
        universe = universe_by_date.copy()
        if sample_on_rebalance_dates:
            rebalance_dates = pd.to_datetime(
                get_rebalance_dates(sorted(universe["trade_date"].unique()), rebalance_frequency)
            )
            if len(rebalance_dates) > 0:
                universe = universe[universe["trade_date"].isin(set(rebalance_dates))].copy()
        universe["__period"] = universe["trade_date"].dt.to_period(rebalance_frequency)
        universe = universe.sort_values(["symbol", "trade_date"])
        grid = (
            universe.groupby(["symbol", "__period"], group_keys=False)
            .tail(1)[["trade_date", "symbol", "__period"]]
            .reset_index(drop=True)
        )
        return grid, "universe_by_date"

    disclosure_periods = frame[["trade_date", "symbol"]].copy()
    disclosure_periods["__period"] = disclosure_periods["trade_date"].dt.to_period(rebalance_frequency)
    disclosure_periods = disclosure_periods.sort_values(["symbol", "trade_date"])
    disclosure_periods = disclosure_periods.groupby(["symbol", "__period"], group_keys=False).tail(1)

    parts: list[pd.DataFrame] = []
    for symbol, symbol_periods in disclosure_periods.groupby("symbol"):
        start_period = symbol_periods["__period"].min()
        end_period = symbol_periods["__period"].max()
        if pd.isna(start_period) or pd.isna(end_period):
            continue
        period_range = pd.period_range(start=start_period, end=end_period, freq=rebalance_frequency)
        symbol_grid = pd.DataFrame({"__period": period_range})
        symbol_grid["symbol"] = symbol
        symbol_grid["trade_date"] = symbol_grid["__period"].dt.to_timestamp(how="end").dt.normalize()
        parts.append(symbol_grid[["trade_date", "symbol", "__period"]])
    if not parts:
        return disclosure_periods.iloc[0:0][["trade_date", "symbol", "__period"]].copy(), "disclosure_period_range"
    grid = pd.concat(parts, ignore_index=True)
    grid = grid.sort_values(["symbol", "__period"]).reset_index(drop=True)
    return grid, "disclosure_period_range"


def _estimate_trainable_pit_coverage(
    *,
    frame: pd.DataFrame,
    feature_frame: pd.DataFrame,
    selected_features: Sequence[str],
    config_data: Mapping[str, object] | None,
    min_symbols: int,
    feature_source: str,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    settings = _resolve_trainable_pit_settings(config_data, selected_features=selected_features)
    rebalance_frequency = str(settings["rebalance_frequency"])

    universe_cfg = config_data.get("universe") if isinstance(config_data, Mapping) else None
    universe_cfg = universe_cfg if isinstance(universe_cfg, Mapping) else {}
    universe_by_date = None
    universe_by_date_file = universe_cfg.get("by_date_file")
    if universe_by_date_file:
        candidate = _resolve_path(str(universe_by_date_file))
        if candidate.exists():
            universe_by_date = _load_universe_by_date_frame(candidate)

    period_grid, grid_source = _build_trainable_period_grid(
        frame=frame,
        rebalance_frequency=rebalance_frequency,
        sample_on_rebalance_dates=bool(settings["sample_on_rebalance_dates"]),
        universe_by_date=universe_by_date,
    )
    if period_grid.empty:
        return (
            {
                "feature_source": feature_source,
                "pit_features_considered": len(selected_features),
                "non_pit_features_ignored": [],
                "rebalance_frequency": rebalance_frequency,
                "sample_on_rebalance_dates": bool(settings["sample_on_rebalance_dates"]),
                "grid_source": grid_source,
                "fundamentals_ffill": bool(settings["fundamentals_ffill"]),
                "fundamentals_ffill_limit": settings["fundamentals_ffill_limit"],
                "missing_method": str(settings["missing_method"]),
                "missing_features_considered": len(settings["missing_features"]),
                "indicator_features_added": len(settings["missing_features"])
                if bool(settings["add_indicators"])
                else 0,
                "active_rows": 0,
                "active_symbols": 0,
                "periods": 0,
                "rows_with_all_selected_features_after_ffill": 0,
                "rows_with_all_selected_features_after_missing_fill": 0,
                "period_symbols_median_after_ffill": 0,
                "period_symbols_max_after_ffill": 0,
                "period_count_meeting_min_symbols_after_ffill": 0,
                "period_symbols_median_after_missing_fill": 0,
                "period_symbols_max_after_missing_fill": 0,
                "period_count_meeting_min_symbols_after_missing_fill": 0,
            },
            [],
        )

    disclosure = (
        frame.loc[:, ["trade_date", "symbol"]]
        .assign(__period=frame["trade_date"].dt.to_period(rebalance_frequency))
        .join(feature_frame[selected_features])
        .sort_values(["symbol", "trade_date"])
        .groupby(["symbol", "__period"], group_keys=False)
        .tail(1)[["symbol", "__period", *selected_features]]
        .reset_index(drop=True)
    )

    pre_fill = period_grid.merge(disclosure, on=["symbol", "__period"], how="left")
    pre_fill = pre_fill.sort_values(["symbol", "__period"]).reset_index(drop=True)
    if bool(settings["fundamentals_ffill"]) and selected_features:
        pre_fill[selected_features] = pre_fill.groupby("symbol")[selected_features].ffill(
            limit=settings["fundamentals_ffill_limit"]
        )

    post_fill = pre_fill.copy()
    missing_features = list(settings["missing_features"])
    if missing_features:
        for feature in missing_features:
            post_fill[feature] = pd.to_numeric(post_fill[feature], errors="coerce")
        if str(settings["missing_method"]) == "zero":
            post_fill[missing_features] = post_fill[missing_features].fillna(0.0)
        elif str(settings["missing_method"]) == "cross_sectional_median":
            period_medians = post_fill.groupby("__period")[missing_features].transform("median")
            post_fill[missing_features] = post_fill[missing_features].fillna(period_medians)

    any_mask = (
        pre_fill[selected_features].notna().any(axis=1)
        if selected_features
        else pd.Series(True, index=pre_fill.index)
    )
    pre_all_mask = (
        pre_fill[selected_features].notna().all(axis=1)
        if selected_features
        else pd.Series(True, index=pre_fill.index)
    )
    post_all_mask = (
        post_fill[selected_features].notna().all(axis=1)
        if selected_features
        else pd.Series(True, index=post_fill.index)
    )

    period_table = (
        period_grid.groupby("__period")["symbol"].nunique().rename("active_symbols").to_frame()
    )
    period_table["symbols_with_any_selected_features_after_ffill"] = (
        pre_fill.loc[any_mask].groupby("__period")["symbol"].nunique()
    )
    period_table["symbols_with_all_selected_features_after_ffill"] = (
        pre_fill.loc[pre_all_mask].groupby("__period")["symbol"].nunique()
    )
    period_table["symbols_with_all_selected_features_after_missing_fill"] = (
        post_fill.loc[post_all_mask].groupby("__period")["symbol"].nunique()
    )
    period_table = period_table.fillna(0).astype(int).reset_index()
    period_table = period_table.sort_values("__period").reset_index(drop=True)
    period_table["period"] = period_table["__period"].astype(str)

    after_ffill_counts = period_table["symbols_with_all_selected_features_after_ffill"]
    after_missing_counts = period_table["symbols_with_all_selected_features_after_missing_fill"]

    estimate = {
        "feature_source": feature_source,
        "pit_features_considered": len(selected_features),
        "rebalance_frequency": rebalance_frequency,
        "sample_on_rebalance_dates": bool(settings["sample_on_rebalance_dates"]),
        "grid_source": grid_source,
        "fundamentals_ffill": bool(settings["fundamentals_ffill"]),
        "fundamentals_ffill_limit": settings["fundamentals_ffill_limit"],
        "missing_method": str(settings["missing_method"]),
        "missing_features_considered": len(missing_features),
        "indicator_features_added": len(missing_features) if bool(settings["add_indicators"]) else 0,
        "active_rows": int(len(period_grid)),
        "active_symbols": int(period_grid["symbol"].nunique()),
        "periods": int(period_table["period"].nunique()),
        "rows_with_all_selected_features_after_ffill": int(pre_all_mask.sum()),
        "rows_with_all_selected_features_after_missing_fill": int(post_all_mask.sum()),
        "period_symbols_median_after_ffill": int(after_ffill_counts.median()) if not period_table.empty else 0,
        "period_symbols_max_after_ffill": int(after_ffill_counts.max()) if not period_table.empty else 0,
        "period_count_meeting_min_symbols_after_ffill": int((after_ffill_counts >= min_symbols).sum()),
        "period_symbols_median_after_missing_fill": int(after_missing_counts.median())
        if not period_table.empty
        else 0,
        "period_symbols_max_after_missing_fill": int(after_missing_counts.max())
        if not period_table.empty
        else 0,
        "period_count_meeting_min_symbols_after_missing_fill": int(
            (after_missing_counts >= min_symbols).sum()
        ),
    }

    output_rows = period_table[
        [
            "period",
            "active_symbols",
            "symbols_with_any_selected_features_after_ffill",
            "symbols_with_all_selected_features_after_ffill",
            "symbols_with_all_selected_features_after_missing_fill",
        ]
    ]
    return estimate, output_rows.to_dict(orient="records")


def _assess_trainable_fill_dependence(
    *,
    trainable_estimate: Mapping[str, object],
    non_pit_features_ignored: Sequence[str],
) -> dict[str, object]:
    after_ffill = int(trainable_estimate.get("period_count_meeting_min_symbols_after_ffill") or 0)
    after_missing_fill = int(
        trainable_estimate.get("period_count_meeting_min_symbols_after_missing_fill") or 0
    )
    route_type = "hybrid" if list(non_pit_features_ignored) else "pit_only"
    thresholds = {
        "pit_only": {"green": 0.60, "yellow": 0.30},
        "hybrid": {"green": 0.40, "yellow": 0.15},
    }
    route_thresholds = thresholds[route_type]
    recovered_periods = max(after_missing_fill - after_ffill, 0)
    retention_ratio = (
        round(float(after_ffill / after_missing_fill), 4) if after_missing_fill > 0 else 0.0
    )
    fill_dependency_ratio = (
        round(float(recovered_periods / after_missing_fill), 4) if after_missing_fill > 0 else 0.0
    )

    if after_missing_fill <= 0:
        status = "red"
        message = "缺失填补后仍然没有季度样本达到 min_symbols。先停下来检查资产或特征集。"
        next_step = "先重建 PIT 资产或缩窄 PIT 特征，再决定是否继续这条研究线。"
    elif retention_ratio >= route_thresholds["green"]:
        status = "green"
        message = "这条配置对横截面填补的依赖在可接受范围内。"
        next_step = "可以继续跑基线或模型比较，同时保留这份体检结果。"
    elif retention_ratio >= route_thresholds["yellow"]:
        status = "yellow"
        message = "这条配置能训练，但对横截面填补有明显依赖。"
        next_step = "先看拖后腿字段，再考虑缩窄 PIT 特征或补资产覆盖。"
    else:
        status = "red"
        message = "这条配置主要靠横截面填补在维持季度样本。"
        next_step = "先收窄 PIT 特征或补资产覆盖，再做模型比较。"

    return {
        "route_type": route_type,
        "status": status,
        "periods_after_ffill": after_ffill,
        "periods_after_missing_fill": after_missing_fill,
        "recovered_periods_from_missing_fill": recovered_periods,
        "retention_ratio_after_ffill": retention_ratio,
        "fill_dependency_ratio_from_missing_fill": fill_dependency_ratio,
        "green_threshold": route_thresholds["green"],
        "yellow_threshold": route_thresholds["yellow"],
        "message": message,
        "next_step": next_step,
    }


def _render_hk_pit_coverage_text(payload: Mapping[str, object], *, top: int, quarter_limit: int) -> str:
    lines: list[str] = []
    source = payload.get("source") if isinstance(payload.get("source"), Mapping) else {}
    selection = payload.get("selection") if isinstance(payload.get("selection"), Mapping) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    complete_case = payload.get("complete_case") if isinstance(payload.get("complete_case"), Mapping) else {}
    trainable_estimate = (
        payload.get("trainable_estimate") if isinstance(payload.get("trainable_estimate"), Mapping) else {}
    )
    fill_dependence = (
        payload.get("fill_dependence_assessment")
        if isinstance(payload.get("fill_dependence_assessment"), Mapping)
        else {}
    )
    manifest_totals = (
        payload.get("pipeline_manifest_totals")
        if isinstance(payload.get("pipeline_manifest_totals"), Mapping)
        else {}
    )

    lines.append("HK PIT Coverage")
    if source:
        config_ref = source.get("config")
        if config_ref:
            lines.append(f"config: {config_ref}")
        fundamentals_file = source.get("fundamentals_file")
        if fundamentals_file:
            lines.append(f"fundamentals_file: {fundamentals_file}")
        asset_dir = source.get("asset_dir")
        if asset_dir:
            lines.append(f"asset_dir: {asset_dir}")

    lines.append("")
    lines.append("Selection")
    lines.append(f"mode: {selection.get('mode')}")
    lines.append(f"feature_source: {selection.get('source')}")
    lines.append(f"selected_features: {selection.get('count')}")
    ignored_features = selection.get("ignored_features")
    if ignored_features:
        lines.append("ignored_features: " + ", ".join(str(item) for item in ignored_features))

    lines.append("")
    lines.append("Summary")
    for key in [
        "rows",
        "symbols",
        "dates",
        "quarters",
        "min_trade_date",
        "max_trade_date",
        "median_symbols_per_date",
        "max_symbols_per_date",
    ]:
        if key in summary:
            lines.append(f"{key}: {summary.get(key)}")

    if manifest_totals:
        lines.append("")
        lines.append("Pipeline Manifest")
        for key in [
            "input_rows",
            "output_rows",
            "symbols",
            "dropped_all_missing_fields",
            "duplicate_rows_seen",
            "duplicate_rows_dropped",
        ]:
            if key in manifest_totals:
                lines.append(f"{key}: {manifest_totals.get(key)}")

    lines.append("")
    lines.append("Complete Case")
    for key in [
        "complete_rows",
        "complete_row_pct",
        "complete_symbols",
        "complete_quarters",
        "quarter_complete_symbols_median",
        "quarter_complete_symbols_max",
        "quarter_count_meeting_min_symbols",
    ]:
        if key in complete_case:
            lines.append(f"{key}: {complete_case.get(key)}")

    field_rows = payload.get("field_coverage") if isinstance(payload.get("field_coverage"), list) else []
    if field_rows:
        lines.append("")
        lines.append(f"Worst Features (top {min(top, len(field_rows))})")
        field_df = pd.DataFrame(field_rows).head(top)
        field_df = field_df[
            [
                "feature",
                "row_coverage_pct",
                "symbol_coverage_pct",
                "quarter_coverage_pct",
                "complete_case_row_lift_if_dropped",
            ]
        ]
        lines.append(field_df.to_string(index=False))

    quarter_rows = payload.get("quarter_coverage") if isinstance(payload.get("quarter_coverage"), list) else []
    if quarter_rows:
        lines.append("")
        lines.append(f"Recent Quarters (last {min(quarter_limit, len(quarter_rows))})")
        quarter_df = pd.DataFrame(quarter_rows).tail(quarter_limit)
        quarter_df = quarter_df[
            [
                "quarter",
                "symbols_in_file",
                "symbols_with_any_selected_feature",
                "symbols_with_all_selected_features",
            ]
        ]
        lines.append(quarter_df.to_string(index=False))

    if trainable_estimate:
        lines.append("")
        lines.append("Trainable Estimate")
        for key in [
            "feature_source",
            "pit_features_considered",
            "rebalance_frequency",
            "sample_on_rebalance_dates",
            "grid_source",
            "fundamentals_ffill",
            "fundamentals_ffill_limit",
            "missing_method",
            "missing_features_considered",
            "indicator_features_added",
            "active_rows",
            "active_symbols",
            "periods",
            "rows_with_all_selected_features_after_ffill",
            "rows_with_all_selected_features_after_missing_fill",
            "period_symbols_median_after_ffill",
            "period_symbols_max_after_ffill",
            "period_count_meeting_min_symbols_after_ffill",
            "period_symbols_median_after_missing_fill",
            "period_symbols_max_after_missing_fill",
            "period_count_meeting_min_symbols_after_missing_fill",
        ]:
            if key in trainable_estimate:
                lines.append(f"{key}: {trainable_estimate.get(key)}")
        non_pit_features = trainable_estimate.get("non_pit_features_ignored")
        if non_pit_features:
            lines.append("non_pit_features_ignored: " + ", ".join(str(item) for item in non_pit_features))

    if fill_dependence:
        lines.append("")
        lines.append("Fill Dependence")
        for key in [
            "route_type",
            "status",
            "periods_after_ffill",
            "periods_after_missing_fill",
            "recovered_periods_from_missing_fill",
            "retention_ratio_after_ffill",
            "fill_dependency_ratio_from_missing_fill",
            "green_threshold",
            "yellow_threshold",
            "message",
            "next_step",
        ]:
            if key in fill_dependence:
                lines.append(f"{key}: {fill_dependence.get(key)}")

    trainable_rows = (
        payload.get("trainable_period_coverage")
        if isinstance(payload.get("trainable_period_coverage"), list)
        else []
    )
    if trainable_rows:
        lines.append("")
        lines.append(f"Estimated Trainable Periods (last {min(quarter_limit, len(trainable_rows))})")
        trainable_df = pd.DataFrame(trainable_rows).tail(quarter_limit)
        trainable_df = trainable_df[
            [
                "period",
                "active_symbols",
                "symbols_with_any_selected_features_after_ffill",
                "symbols_with_all_selected_features_after_ffill",
                "symbols_with_all_selected_features_after_missing_fill",
            ]
        ]
        lines.append(trainable_df.to_string(index=False))

    return "\n".join(lines).strip() + "\n"


def inspect_hk_pit_coverage(args) -> int:
    resolved_config = resolve_pipeline_config(args.config) if getattr(args, "config", None) else None
    config_data = resolved_config.data if resolved_config else None

    asset_dir = _resolve_path(args.asset_dir) if getattr(args, "asset_dir", None) else None
    fundamentals_file = _resolve_path(args.fundamentals_file) if getattr(args, "fundamentals_file", None) else None
    if config_data and fundamentals_file is None:
        fundamentals_cfg = config_data.get("fundamentals") if isinstance(config_data, Mapping) else None
        if isinstance(fundamentals_cfg, Mapping):
            fundamentals_file_ref = fundamentals_cfg.get("file")
            if fundamentals_cfg.get("source", "file") == "file" and fundamentals_file_ref:
                fundamentals_file = _resolve_path(str(fundamentals_file_ref))

    if asset_dir is None and fundamentals_file is not None and fundamentals_file.name == DEFAULT_PIPELINE_FUNDAMENTALS_NAME:
        asset_dir = fundamentals_file.parent
    if asset_dir is not None and fundamentals_file is None:
        fundamentals_file = _default_pipeline_fundamentals_path(asset_dir)

    if fundamentals_file is None:
        raise SystemExit(
            "No fundamentals source resolved. Pass --config, --asset-dir, or --fundamentals-file."
        )
    if not fundamentals_file.exists():
        raise SystemExit(f"Fundamentals file not found: {fundamentals_file}")

    if asset_dir is None:
        manifest_candidate = _pipeline_fundamentals_manifest_path(fundamentals_file)
        pipeline_manifest = _load_manifest(manifest_candidate) if manifest_candidate.exists() else None
        if isinstance(pipeline_manifest, Mapping):
            source_asset_dir = pipeline_manifest.get("source_asset_dir")
            if source_asset_dir:
                candidate = _resolve_path(str(source_asset_dir))
                if candidate.exists():
                    asset_dir = candidate
    asset_manifest = _load_manifest(asset_dir / "manifest.yml") if asset_dir and (asset_dir / "manifest.yml").exists() else None
    pipeline_manifest_path = _pipeline_fundamentals_manifest_path(fundamentals_file)
    pipeline_manifest = _load_manifest(pipeline_manifest_path) if pipeline_manifest_path.exists() else None

    if fundamentals_file.suffix.lower() in {".parquet", ".pq"}:
        frame = pd.read_parquet(fundamentals_file)
    else:
        frame = pd.read_csv(fundamentals_file)
    frame = _normalize_frame_columns(frame)
    frame = ensure_symbol_columns(frame, context=f"Fundamentals file {fundamentals_file.name}")
    if "trade_date" not in frame.columns or "symbol" not in frame.columns:
        raise SystemExit(
            "Fundamentals file must include trade_date and a canonical symbol column "
            f"(legacy ts_code inputs remain compatible): {fundamentals_file}"
        )

    trade_dates = pd.to_datetime(frame["trade_date"], errors="coerce")
    valid_trade_date = trade_dates.notna()
    invalid_trade_dates = int((~valid_trade_date).sum())
    frame = frame.loc[valid_trade_date].copy()
    trade_dates = trade_dates.loc[valid_trade_date].dt.normalize()
    frame["trade_date"] = trade_dates
    frame["symbol"] = frame["symbol"].astype(str).str.strip()
    frame = frame.drop(columns=["ts_code", "stock_ticker"], errors="ignore")
    frame = frame.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    trade_dates = frame["trade_date"]
    available_columns = frame.columns.tolist()

    mode = str(getattr(args, "mode", "strict") or "strict").strip().lower()
    if mode not in {"strict", "trainable", "both"}:
        raise SystemExit("mode must be one of: strict, trainable, both")

    manifest_for_fields = pipeline_manifest if isinstance(pipeline_manifest, Mapping) else asset_manifest
    strict_features, strict_selection_meta = _resolve_pit_coverage_features(
        args=args,
        config_data=config_data,
        manifest=manifest_for_fields if isinstance(manifest_for_fields, Mapping) else None,
        available_columns=available_columns,
    )
    if mode == "strict":
        selected_features = strict_features
        selection_meta = strict_selection_meta
    else:
        selected_features, selection_meta = _resolve_trainable_pit_features(
            args=args,
            config_data=config_data,
            available_columns=available_columns,
            fallback_features=strict_features,
            fallback_metadata=strict_selection_meta,
        )
    min_symbols = getattr(args, "min_symbols", None)
    if min_symbols is None and isinstance(config_data, Mapping):
        universe_cfg = config_data.get("universe")
        if isinstance(universe_cfg, Mapping):
            min_symbols = universe_cfg.get("min_symbols_per_date")
    if min_symbols is None:
        min_symbols = 5
    min_symbols = int(min_symbols)

    feature_cache: dict[str, pd.Series] = {}
    feature_series = {
        feature: _compute_pit_coverage_series(frame, feature, cache=feature_cache)
        for feature in selected_features
    }
    feature_frame = pd.DataFrame(feature_series, index=frame.index)

    total_rows = int(len(frame))
    total_symbols = int(frame["symbol"].nunique())
    total_dates = int(trade_dates.nunique())
    quarter_labels = trade_dates.dt.to_period("Q").astype(str)
    total_quarters = int(pd.Index(quarter_labels).nunique())
    date_counts = frame.groupby("trade_date")["symbol"].nunique()

    if selected_features:
        complete_rows_mask = feature_frame.notna().all(axis=1)
    else:
        complete_rows_mask = pd.Series(True, index=frame.index)
    complete_rows = int(complete_rows_mask.sum())
    complete_symbols = int(frame.loc[complete_rows_mask, "symbol"].nunique())

    quarter_latest = (
        frame.loc[:, ["trade_date", "symbol"]]
        .assign(__quarter=quarter_labels)
        .join(feature_frame)
        .sort_values(["__quarter", "symbol", "trade_date"])
        .groupby(["__quarter", "symbol"], group_keys=False)
        .tail(1)
        .reset_index(drop=True)
    )
    quarter_feature_frame = (
        quarter_latest[selected_features] if selected_features else pd.DataFrame(index=quarter_latest.index)
    )
    quarter_any_mask = quarter_feature_frame.notna().any(axis=1) if selected_features else pd.Series(True, index=quarter_latest.index)
    quarter_complete_mask = (
        quarter_feature_frame.notna().all(axis=1)
        if selected_features
        else pd.Series(True, index=quarter_latest.index)
    )
    quarter_table = (
        quarter_latest.groupby("__quarter")["symbol"].nunique().rename("symbols_in_file").to_frame()
    )
    quarter_table["symbols_with_any_selected_feature"] = (
        quarter_latest.loc[quarter_any_mask].groupby("__quarter")["symbol"].nunique()
    )
    quarter_table["symbols_with_all_selected_features"] = (
        quarter_latest.loc[quarter_complete_mask].groupby("__quarter")["symbol"].nunique()
    )
    quarter_table = quarter_table.fillna(0).astype(int).reset_index().rename(columns={"__quarter": "quarter"})
    quarter_table = quarter_table.sort_values("quarter").reset_index(drop=True)

    complete_quarters = int((quarter_table["symbols_with_all_selected_features"] > 0).sum())
    quarter_count_meeting_min_symbols = int(
        (quarter_table["symbols_with_all_selected_features"] >= min_symbols).sum()
    )

    field_rows: list[dict[str, object]] = []
    base_complete_rows = complete_rows
    for feature in selected_features:
        series = feature_series[feature]
        mask = series.notna()
        relaxed_features = [item for item in selected_features if item != feature]
        if relaxed_features:
            relaxed_complete = int(feature_frame[relaxed_features].notna().all(axis=1).sum())
        else:
            relaxed_complete = total_rows
        quarters_with_values = int(pd.Index(quarter_labels[mask]).nunique()) if mask.any() else 0
        field_rows.append(
            {
                "feature": feature,
                "nonnull_rows": int(mask.sum()),
                "row_coverage_pct": round(float(mask.mean() * 100.0), 2),
                "symbols_with_values": int(frame.loc[mask, "symbol"].nunique()),
                "symbol_coverage_pct": round(
                    float(frame.loc[mask, "symbol"].nunique() / total_symbols * 100.0) if total_symbols else 0.0,
                    2,
                ),
                "quarters_with_values": quarters_with_values,
                "quarter_coverage_pct": round(
                    float(quarters_with_values / total_quarters * 100.0) if total_quarters else 0.0,
                    2,
                ),
                "complete_case_row_lift_if_dropped": int(relaxed_complete - base_complete_rows),
            }
        )
    field_rows.sort(
        key=lambda item: (
            float(item["row_coverage_pct"]),
            -int(item["complete_case_row_lift_if_dropped"]),
            str(item["feature"]),
        )
    )

    trainable_estimate: dict[str, object] | None = None
    trainable_period_rows: list[dict[str, object]] | None = None
    fill_dependence_assessment: dict[str, object] | None = None
    if mode in {"trainable", "both"}:
        trainable_estimate, trainable_period_rows = _estimate_trainable_pit_coverage(
            frame=frame,
            feature_frame=feature_frame,
            selected_features=selected_features,
            config_data=config_data,
            min_symbols=min_symbols,
            feature_source=str(selection_meta.get("source") or "explicit"),
        )
        non_pit_ignored = list(selection_meta.get("non_pit_ignored_features") or [])
        if non_pit_ignored:
            trainable_estimate["non_pit_features_ignored"] = non_pit_ignored
        fill_dependence_assessment = _assess_trainable_fill_dependence(
            trainable_estimate=trainable_estimate,
            non_pit_features_ignored=non_pit_ignored,
        )

    payload = {
        "source": {
            "config": resolved_config.source if resolved_config else None,
            "fundamentals_file": str(fundamentals_file),
            "asset_dir": str(asset_dir) if asset_dir else None,
        },
        "selection": {
            "mode": mode,
            "source": selection_meta.get("source"),
            "count": len(selected_features),
            "requested_features": list(selection_meta.get("requested_features") or []),
            "selected_features": selected_features,
            "ignored_features": list(selection_meta.get("ignored_features") or []),
            "min_symbols_threshold": min_symbols,
        },
        "summary": {
            "rows": total_rows,
            "symbols": total_symbols,
            "dates": total_dates,
            "quarters": total_quarters,
            "min_trade_date": trade_dates.min().strftime("%Y-%m-%d") if total_rows else None,
            "max_trade_date": trade_dates.max().strftime("%Y-%m-%d") if total_rows else None,
            "median_symbols_per_date": int(date_counts.median()) if not date_counts.empty else 0,
            "max_symbols_per_date": int(date_counts.max()) if not date_counts.empty else 0,
            "invalid_trade_dates_dropped": invalid_trade_dates,
        },
        "pipeline_manifest_totals": (
            dict(pipeline_manifest.get("totals"))
            if isinstance(pipeline_manifest, Mapping) and isinstance(pipeline_manifest.get("totals"), Mapping)
            else None
        ),
        "complete_case": {
            "complete_rows": complete_rows,
            "complete_row_pct": round(float(complete_rows / total_rows * 100.0) if total_rows else 0.0, 2),
            "complete_symbols": complete_symbols,
            "complete_quarters": complete_quarters,
            "quarter_complete_symbols_median": int(quarter_table["symbols_with_all_selected_features"].median())
            if not quarter_table.empty
            else 0,
            "quarter_complete_symbols_max": int(quarter_table["symbols_with_all_selected_features"].max())
            if not quarter_table.empty
            else 0,
            "quarter_count_meeting_min_symbols": quarter_count_meeting_min_symbols,
        },
        "field_coverage": field_rows,
        "quarter_coverage": quarter_table.to_dict(orient="records"),
        "trainable_estimate": trainable_estimate,
        "fill_dependence_assessment": fill_dependence_assessment,
        "trainable_period_coverage": trainable_period_rows,
    }

    output_format = str(getattr(args, "format", "text") or "text").strip().lower()
    if output_format not in {"text", "json"}:
        raise SystemExit("format must be one of: text, json")
    if output_format == "json":
        rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    else:
        rendered = _render_hk_pit_coverage_text(
            payload,
            top=int(getattr(args, "top", 10) or 10),
            quarter_limit=int(getattr(args, "quarter_limit", 12) or 12),
        )

    out_path = _resolve_path(args.out) if getattr(args, "out", None) else None
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0
