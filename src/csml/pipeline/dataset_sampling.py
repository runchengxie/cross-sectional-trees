from __future__ import annotations

import logging
import sys
from typing import Any

import numpy as np
import pandas as pd

from ..dataset import DatasetSchema, build_dataset
from ..rebalance import get_rebalance_dates
from ..transform import apply_cross_sectional_series_transform, apply_cross_sectional_transform
from .dates import _build_trade_date_slices, _slice_trade_dates
from .support import _ensure_symbol_alias, apply_universe_by_date

logger = logging.getLogger("csml")


def prepare_backtest_pricing_frame(
    *,
    df: pd.DataFrame,
    price_col: str,
    execution_pricing_cols: set[str],
    backtest_tradable_col: str | None,
) -> tuple[pd.DataFrame, list[str]]:
    execution_passthrough_cols = [
        col for col in execution_pricing_cols if col in df.columns and col != price_col
    ]
    backtest_pricing_cols = [
        "trade_date",
        "symbol",
        price_col,
        *execution_passthrough_cols,
    ]
    if backtest_tradable_col and backtest_tradable_col in df.columns:
        backtest_pricing_cols.append(backtest_tradable_col)
    backtest_pricing_cols = list(dict.fromkeys(backtest_pricing_cols))
    backtest_pricing_df = (
        df[backtest_pricing_cols]
        .drop_duplicates(subset=["trade_date", "symbol"])
        .copy()
    )
    price_passthrough_cols = list(
        dict.fromkeys(
            execution_passthrough_cols
            + [col for col in ("close", "tr_close") if col in df.columns and col != price_col]
        )
    )
    return backtest_pricing_df, price_passthrough_cols


def apply_feature_missing_fill(
    *,
    df: pd.DataFrame,
    features: list[str],
    feature_missing_features: list[str],
    feature_missing_method: str,
    feature_missing_add_indicators: bool,
    feature_missing_suffix: str,
) -> tuple[pd.DataFrame, list[str], list[str]]:
    out = df
    missing_fill_features = feature_missing_features or features
    missing_fill_features = [
        feature for feature in missing_fill_features if feature in features and feature in out.columns
    ]

    if feature_missing_add_indicators and missing_fill_features:
        indicator_features = []
        for feature in missing_fill_features:
            indicator_name = f"{feature}{feature_missing_suffix}"
            if indicator_name in out.columns and indicator_name not in features:
                sys.exit(
                    "features.missing.indicator_suffix collides with an existing column: "
                    f"{indicator_name}"
                )
            if indicator_name not in out.columns:
                out[indicator_name] = out[feature].isna().astype("int8")
            indicator_features.append(indicator_name)
        features = list(dict.fromkeys(features + indicator_features))

    if feature_missing_method != "none" and missing_fill_features:
        for feature in missing_fill_features:
            out[feature] = pd.to_numeric(out[feature], errors="coerce")
        if feature_missing_method == "zero":
            out[missing_fill_features] = out[missing_fill_features].fillna(0.0)
        elif feature_missing_method == "cross_sectional_median":
            by_date_median = out.groupby("trade_date")[missing_fill_features].transform("median")
            out[missing_fill_features] = out[missing_fill_features].fillna(by_date_median)
        remaining_missing = int(out[missing_fill_features].isna().sum().sum())
        logger.info(
            "Applied feature missing fill: method=%s, features=%s, add_indicators=%s, remaining_nans=%s.",
            feature_missing_method,
            len(missing_fill_features),
            feature_missing_add_indicators,
            remaining_missing,
        )

    return out, features, missing_fill_features


def build_modeling_dataset(
    *,
    df: pd.DataFrame,
    price_col: str,
    target: str,
    train_target: str,
    train_target_transform: str,
    features: list[str],
    price_passthrough_cols: list[str],
    passthrough_cols: list[str],
    winsorize_pct: float | None,
    cs_method: str,
    cs_winsorize_pct: float | None,
    sample_on_rebalance_dates: bool,
    rebalance_frequency: str,
    min_symbols_per_date: int,
    universe_by_date: pd.DataFrame | None,
    eval_extra_df: pd.DataFrame | None,
) -> dict[str, Any]:
    out = _ensure_symbol_alias(df)
    cols = (
        ["trade_date", "symbol", price_col]
        + features
        + price_passthrough_cols
        + passthrough_cols
        + (["is_tradable"] if "is_tradable" in out.columns else [])
        + [target]
    )
    cols = list(dict.fromkeys(cols))
    out = out[cols].copy()

    reference_trade_dates = np.sort(pd.to_datetime(out["trade_date"].unique()).to_numpy())
    if universe_by_date is not None:
        before_rows = len(out)
        out = apply_universe_by_date(out, universe_by_date)
        after_rows = len(out)
        logger.info("Applied universe-by-date filter: %s -> %s rows", before_rows, after_rows)
        if out.empty:
            sys.exit("Universe-by-date filter removed all rows.")

    required_cols = [price_col] + features
    df_features = out.dropna(subset=required_cols).reset_index(drop=True)

    if winsorize_pct:

        def _winsorize(group: pd.DataFrame) -> pd.DataFrame:
            lower = group[target].quantile(winsorize_pct)
            upper = group[target].quantile(1 - winsorize_pct)
            group[target] = group[target].clip(lower, upper)
            return group

        df_features = df_features.groupby("trade_date", group_keys=False).apply(_winsorize)

    if cs_method != "none":
        df_features = apply_cross_sectional_transform(
            df_features, features, cs_method, cs_winsorize_pct
        )

    if train_target != target:
        df_features[train_target] = apply_cross_sectional_series_transform(
            df_features,
            target,
            train_target_transform,
        )
        logger.info(
            "Applied training target transform: base=%s, method=%s, train_target=%s",
            target,
            train_target_transform,
            train_target,
        )

    dataset_schema = DatasetSchema(
        date_col="trade_date",
        instrument_col="symbol",
        price_col=price_col,
        label_col=target,
        tradable_col="is_tradable" if "is_tradable" in df_features.columns else None,
        feature_cols=features,
        extra_cols=[
            *price_passthrough_cols,
            *passthrough_cols,
            *([train_target] if train_target != target else []),
        ],
    )
    dataset = build_dataset(df_features, dataset_schema)
    df_features = dataset.frame
    complete_case_cols = [price_col, target, *features]
    if train_target != target:
        complete_case_cols.append(train_target)
    complete_case_cols = [
        column for column in list(dict.fromkeys(complete_case_cols)) if column in df_features.columns
    ]
    df_full = df_features.dropna(subset=complete_case_cols).reset_index(drop=True)
    if eval_extra_df is not None and not eval_extra_df.empty:
        eval_extra_df = eval_extra_df.drop_duplicates(subset=["trade_date", "symbol"])
        extra_eval_cols = [
            col
            for col in eval_extra_df.columns
            if col not in {"trade_date", "symbol"} and col not in df_full.columns
        ]
        if extra_eval_cols:
            df_full = df_full.merge(
                eval_extra_df[["trade_date", "symbol"] + extra_eval_cols],
                on=["trade_date", "symbol"],
                how="left",
            )

    (
        df_full_sorted,
        all_dates_full,
        full_date_start_rows,
        full_date_end_rows,
        full_date_to_pos,
    ) = _build_trade_date_slices(df_full)
    if sample_on_rebalance_dates:
        rebalance_dates_all = get_rebalance_dates(all_dates_full, rebalance_frequency)
        df_model_all = _slice_trade_dates(
            df_full_sorted,
            full_date_start_rows,
            full_date_end_rows,
            full_date_to_pos,
            rebalance_dates_all,
        )
    else:
        df_model_all = df_full_sorted

    date_counts = df_model_all.groupby("trade_date")["symbol"].nunique()
    valid_dates = date_counts[date_counts >= min_symbols_per_date].index
    dropped_date_counts = date_counts[date_counts < min_symbols_per_date].sort_index()
    (
        df_model_all_sorted,
        all_dates_model_full,
        model_date_start_rows,
        model_date_end_rows,
        model_date_to_pos,
    ) = _build_trade_date_slices(df_model_all)
    if len(valid_dates) != len(date_counts):
        df_model_all = _slice_trade_dates(
            df_model_all_sorted,
            model_date_start_rows,
            model_date_end_rows,
            model_date_to_pos,
            valid_dates.to_numpy(),
        )
        (
            df_model_all_sorted,
            all_dates_model_full,
            model_date_start_rows,
            model_date_end_rows,
            model_date_to_pos,
        ) = _build_trade_date_slices(df_model_all)
    else:
        df_model_all = df_model_all_sorted

    return {
        "dataset": dataset,
        "df_features": df_features,
        "df_full": df_full,
        "df_full_sorted": df_full_sorted,
        "reference_trade_dates": reference_trade_dates,
        "all_dates_full": all_dates_full,
        "full_date_start_rows": full_date_start_rows,
        "full_date_end_rows": full_date_end_rows,
        "full_date_to_pos": full_date_to_pos,
        "df_model_all": df_model_all,
        "df_model_all_sorted": df_model_all_sorted,
        "all_dates_model_full": all_dates_model_full,
        "model_date_start_rows": model_date_start_rows,
        "model_date_end_rows": model_date_end_rows,
        "model_date_to_pos": model_date_to_pos,
        "valid_dates": valid_dates,
        "valid_dates_set": set(pd.to_datetime(valid_dates)),
        "dropped_date_counts": dropped_date_counts,
    }
