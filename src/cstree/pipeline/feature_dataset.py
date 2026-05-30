from __future__ import annotations

import logging
import sys
from typing import Any

from ..compat import ensure_numpy_nan_alias
from .dataset_sampling import (
    apply_feature_missing_fill,
    build_modeling_dataset,
    prepare_backtest_pricing_frame,
)
from .feature_engineering import engineer_symbol_features

ensure_numpy_nan_alias()
import pandas as pd

logger = logging.getLogger("cstree")


def _build_feature_availability_diagnostics(
    df: pd.DataFrame,
    *,
    price_col: str,
    features: list[str],
    top_n: int = 5,
) -> dict[str, Any]:
    if df.empty or "trade_date" not in df.columns:
        return {
            "total_rows": int(len(df)),
            "total_dates": 0,
            "complete_rows": 0,
            "complete_dates": 0,
            "complete_row_ratio": 0.0,
            "complete_date_ratio": 0.0,
            "worst_features": [],
        }

    total_rows = int(len(df))
    total_dates = int(df["trade_date"].nunique())
    required = [price_col] + [feature for feature in features if feature in df.columns]
    if not required:
        return {
            "total_rows": total_rows,
            "total_dates": total_dates,
            "complete_rows": total_rows,
            "complete_dates": total_dates,
            "complete_row_ratio": 1.0,
            "complete_date_ratio": 1.0,
            "worst_features": [],
        }

    complete_mask = df[required].notna().all(axis=1)
    complete_rows = int(complete_mask.sum())
    complete_dates = int(df.loc[complete_mask, "trade_date"].nunique()) if complete_rows else 0

    feature_rows: list[dict[str, Any]] = []
    for feature in features:
        if feature not in df.columns:
            feature_rows.append(
                {
                    "feature": feature,
                    "missing_rows": total_rows,
                    "missing_pct": 100.0,
                    "dates_with_values": 0,
                }
            )
            continue
        missing_rows = int(df[feature].isna().sum())
        if missing_rows <= 0:
            continue
        dates_with_values = int(df.loc[df[feature].notna(), "trade_date"].nunique())
        feature_rows.append(
            {
                "feature": feature,
                "missing_rows": missing_rows,
                "missing_pct": round(missing_rows / total_rows * 100.0, 2)
                if total_rows
                else 0.0,
                "dates_with_values": dates_with_values,
            }
        )

    feature_rows.sort(
        key=lambda item: (
            item["missing_rows"],
            -item["dates_with_values"],
            item["feature"],
        ),
        reverse=True,
    )
    return {
        "total_rows": total_rows,
        "total_dates": total_dates,
        "complete_rows": complete_rows,
        "complete_dates": complete_dates,
        "complete_row_ratio": round(complete_rows / total_rows, 4) if total_rows else 0.0,
        "complete_date_ratio": round(complete_dates / total_dates, 4) if total_dates else 0.0,
        "worst_features": feature_rows[:top_n],
    }


def _format_feature_availability_rows(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<none>"
    return ", ".join(
        (
            f"{item['feature']}"
            f"(missing={item['missing_pct']:.2f}%, dates={item['dates_with_values']})"
        )
        for item in items
    )


def _prepare_feature_dataset(
    *,
    df: pd.DataFrame,
    features: list[str],
    feature_params: dict,
    price_col: str,
    target: str,
    label_shift_days: int,
    label_horizon_days: int,
    label_horizon_mode: str,
    label_next_rebalance_map: dict[pd.Timestamp, pd.Timestamp] | None,
    fundamentals_allow_missing: bool,
    bucket_ic_enabled: bool,
    bucket_ic_schemes: list[dict[str, Any]],
    feature_missing_features: list[str],
    feature_missing_method: str,
    feature_missing_add_indicators: bool,
    feature_missing_suffix: str,
    industry_cols: list[str],
    execution_pricing_cols: set[str],
    backtest_tradable_col: str | None,
    universe_by_date: pd.DataFrame | None,
    winsorize_pct: float | None,
    cs_method: str,
    cs_winsorize_pct: float | None,
    train_target: str,
    train_target_transform: str,
    sample_on_rebalance_dates: bool,
    rebalance_frequency: str,
    min_symbols_per_date: int,
) -> dict[str, Any]:
    logger.info("Engineering features ...")
    if price_col not in df.columns:
        if price_col == "tr_close":
            sys.exit(
                "Price column 'tr_close' not found in data. "
                "Configure data.rqdata.ex_factors_dir for local RQData assets, "
                "or provide tr_close directly in the source daily data."
            )
        sys.exit(f"Price column '{price_col}' not found in data.")
    if not features:
        sys.exit("Feature list is empty.")

    features = list(features)
    df = df.groupby("symbol", group_keys=False).apply(
        lambda group: engineer_symbol_features(
            group,
            features=features,
            feature_params=feature_params,
            price_col=price_col,
            target=target,
            label_shift_days=label_shift_days,
            label_horizon_days=label_horizon_days,
            label_horizon_mode=label_horizon_mode,
            label_next_rebalance_map=label_next_rebalance_map,
        )
    )

    missing_features = [feat for feat in features if feat not in df.columns]
    if missing_features:
        if fundamentals_allow_missing:
            logger.warning("Dropping missing features: %s", missing_features)
            features = [feat for feat in features if feat in df.columns]
        else:
            sys.exit(f"Missing features after engineering: {missing_features}")

    eval_extra_df = None
    bucket_cols = []
    if bucket_ic_enabled and bucket_ic_schemes:
        bucket_cols = list(dict.fromkeys([scheme["column"] for scheme in bucket_ic_schemes]))
        missing_bucket_cols = [col for col in bucket_cols if col not in df.columns]
        if missing_bucket_cols:
            logger.warning("Bucket IC columns missing in data: %s", missing_bucket_cols)
        bucket_cols = [col for col in bucket_cols if col in df.columns]
        if bucket_cols:
            eval_extra_df = df[["trade_date", "symbol"] + bucket_cols].copy()

    backtest_pricing_df, price_passthrough_cols = prepare_backtest_pricing_frame(
        df=df,
        price_col=price_col,
        execution_pricing_cols=execution_pricing_cols,
        backtest_tradable_col=backtest_tradable_col,
    )
    passthrough_cols = list(dict.fromkeys(industry_cols))

    df, features, missing_fill_features = apply_feature_missing_fill(
        df=df,
        features=features,
        feature_missing_features=feature_missing_features,
        feature_missing_method=feature_missing_method,
        feature_missing_add_indicators=feature_missing_add_indicators,
        feature_missing_suffix=feature_missing_suffix,
    )

    feature_availability_diagnostics = _build_feature_availability_diagnostics(
        df,
        price_col=price_col,
        features=features,
    )
    if (
        feature_availability_diagnostics["total_dates"] >= 20
        and (
            feature_availability_diagnostics["complete_dates"] < 20
            or feature_availability_diagnostics["complete_date_ratio"] < 0.25
        )
    ):
        logger.warning(
            "Feature availability collapse before complete-case filter: "
            "complete_dates=%s/%s, complete_rows=%s/%s. "
            "Worst features after missing fill: %s. "
            "If this is a quarterly PIT config, run "
            "`marketdata rqdata hk-assets -- inspect-hk-pit-coverage --config ...` "
            "or trim the low-coverage feature block.",
            feature_availability_diagnostics["complete_dates"],
            feature_availability_diagnostics["total_dates"],
            feature_availability_diagnostics["complete_rows"],
            feature_availability_diagnostics["total_rows"],
            _format_feature_availability_rows(
                feature_availability_diagnostics["worst_features"]
            ),
        )

    modeling_state = build_modeling_dataset(
        df=df,
        price_col=price_col,
        target=target,
        train_target=train_target,
        train_target_transform=train_target_transform,
        features=features,
        price_passthrough_cols=price_passthrough_cols,
        passthrough_cols=passthrough_cols,
        winsorize_pct=winsorize_pct,
        cs_method=cs_method,
        cs_winsorize_pct=cs_winsorize_pct,
        sample_on_rebalance_dates=sample_on_rebalance_dates,
        rebalance_frequency=rebalance_frequency,
        min_symbols_per_date=min_symbols_per_date,
        universe_by_date=universe_by_date,
        eval_extra_df=eval_extra_df,
    )

    if not modeling_state["dropped_date_counts"].empty:
        logger.info(
            "Dropped %s dates with < %s symbols (min=%s, max=%s).",
            len(modeling_state["dropped_date_counts"]),
            min_symbols_per_date,
            int(modeling_state["dropped_date_counts"].min()),
            int(modeling_state["dropped_date_counts"].max()),
        )
    if len(modeling_state["all_dates_model_full"]) < 10:
        logger.warning(
            "Only %s model dates remain after feature filtering%s: %s. "
            "Worst features after missing fill: %s.",
            len(modeling_state["all_dates_model_full"]),
            " and sample-on-rebalance" if sample_on_rebalance_dates else "",
            [
                pd.Timestamp(date).strftime("%Y-%m-%d")
                for date in modeling_state["all_dates_model_full"]
            ],
            _format_feature_availability_rows(
                feature_availability_diagnostics["worst_features"]
            ),
        )

    return {
        "features": features,
        "backtest_pricing_df": backtest_pricing_df,
        "bucket_cols": bucket_cols,
        "passthrough_cols": passthrough_cols,
        "price_passthrough_cols": price_passthrough_cols,
        "feature_availability_diagnostics": feature_availability_diagnostics,
        **modeling_state,
    }
