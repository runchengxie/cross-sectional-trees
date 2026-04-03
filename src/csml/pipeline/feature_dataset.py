from __future__ import annotations

import logging
import sys
from collections.abc import Mapping
from typing import Any, Optional

import numpy as np

from ..compat import ensure_numpy_nan_alias
from ..dataset import DatasetSchema, build_dataset
from ..rebalance import get_rebalance_dates
from ..transform import apply_cross_sectional_series_transform, apply_cross_sectional_transform
from .dates import _build_trade_date_slices, _slice_trade_dates
from .support import (
    _ensure_symbol_alias,
    _parse_window_config,
    apply_universe_by_date,
    parse_feature_windows,
)

ensure_numpy_nan_alias()
import pandas as pd
import pandas_ta as ta

logger = logging.getLogger("csml")


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
    feature_params: Mapping[str, Any],
    price_col: str,
    target: str,
    label_shift_days: int,
    label_horizon_days: int,
    label_horizon_mode: str,
    label_next_rebalance_map: Optional[dict[pd.Timestamp, pd.Timestamp]],
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
    universe_by_date: Optional[pd.DataFrame],
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

    def add_features(group: pd.DataFrame) -> pd.DataFrame:
        group = group.sort_values("trade_date").copy()
        needed = set(features)
        price_series = pd.to_numeric(group[price_col], errors="coerce")

        def _safe_ratio(
            numerator_col: str,
            denominator_col: str,
            out_col: str,
        ) -> None:
            if out_col not in needed:
                return
            if numerator_col not in group.columns or denominator_col not in group.columns:
                return
            numerator = pd.to_numeric(group[numerator_col], errors="coerce")
            denominator = pd.to_numeric(group[denominator_col], errors="coerce")
            valid_denominator = denominator.where(denominator.notna() & (denominator != 0))
            ratio = numerator / valid_denominator
            group[out_col] = ratio.replace([np.inf, -np.inf], np.nan)

        sma_windows = set(parse_feature_windows(features, "sma_"))
        sma_windows.update(parse_feature_windows(features, "sma_", "_diff"))
        if not sma_windows:
            sma_windows = _parse_window_config(feature_params.get("sma_windows"))
        for win in sorted(sma_windows):
            group[f"sma_{win}"] = ta.sma(price_series, length=win)
            if f"sma_{win}_diff" in needed:
                group[f"sma_{win}_diff"] = group[f"sma_{win}"].pct_change()

        rsi_lengths = set(parse_feature_windows(features, "rsi_"))
        if not rsi_lengths:
            rsi_lengths = _parse_window_config(feature_params.get("rsi"))
        for length in sorted(rsi_lengths):
            group[f"rsi_{length}"] = ta.rsi(price_series, length=length)

        if "macd_hist" in needed:
            macd_cfg = feature_params.get("macd", [12, 26, 9])
            macd_fast, macd_slow, macd_signal = macd_cfg
            macd = ta.macd(price_series, fast=macd_fast, slow=macd_slow, signal=macd_signal)
            col_name = f"MACDh_{macd_fast}_{macd_slow}_{macd_signal}"
            if macd is not None and col_name in macd.columns:
                group["macd_hist"] = macd[col_name]
            else:
                group["macd_hist"] = np.nan

        volume_windows = set(parse_feature_windows(features, "volume_sma", "_ratio"))
        if not volume_windows:
            volume_windows = _parse_window_config(feature_params.get("volume_sma_windows"))
        for win in sorted(volume_windows):
            volume_sma = ta.sma(group["vol"], length=win)
            if volume_sma is None:
                volume_sma = group["vol"].rolling(window=win).mean()
            group[f"volume_sma{win}"] = volume_sma
            if f"volume_sma{win}_ratio" in needed:
                group[f"volume_sma{win}_ratio"] = group["vol"] / group[f"volume_sma{win}"]

        ret_windows = set(parse_feature_windows(features, "ret_"))
        if not ret_windows:
            ret_windows = _parse_window_config(feature_params.get("ret_windows"))
        for win in sorted(ret_windows):
            group[f"ret_{win}"] = price_series.pct_change(win)

        rv_windows = set(parse_feature_windows(features, "rv_"))
        if not rv_windows:
            rv_windows = _parse_window_config(feature_params.get("rv_windows"))
        if rv_windows:
            daily_return = price_series.pct_change()
            daily_return = daily_return.replace([np.inf, -np.inf], np.nan)
            for win in sorted(rv_windows):
                group[f"rv_{win}"] = daily_return.rolling(window=win).std(ddof=0)

        if "log_vol" in needed:
            group["log_vol"] = np.log1p(group["vol"].clip(lower=0))

        if (
            "sales" in needed
            or "profit_margin" in needed
            or "operating_margin" in needed
            or "cfo_margin" in needed
        ):
            revenue = (
                pd.to_numeric(group["revenue"], errors="coerce")
                if "revenue" in group.columns
                else pd.Series(np.nan, index=group.index, dtype=float)
            )
            operating_revenue = (
                pd.to_numeric(group["operating_revenue"], errors="coerce")
                if "operating_revenue" in group.columns
                else pd.Series(np.nan, index=group.index, dtype=float)
            )
            group["sales"] = revenue.combine_first(operating_revenue)
        if (
            "debt" in needed
            or "debt_to_assets" in needed
            or "debt_to_equity" in needed
            or "net_debt_to_assets" in needed
        ):
            short_term_debt = (
                pd.to_numeric(group["short_term_debt"], errors="coerce")
                if "short_term_debt" in group.columns
                else pd.Series(np.nan, index=group.index, dtype=float)
            )
            long_term_loans = (
                pd.to_numeric(group["long_term_loans"], errors="coerce")
                if "long_term_loans" in group.columns
                else pd.Series(np.nan, index=group.index, dtype=float)
            )
            debt = short_term_debt.fillna(0.0) + long_term_loans.fillna(0.0)
            group["debt"] = debt.where(~(short_term_debt.isna() & long_term_loans.isna()))

        _safe_ratio("net_profit", "sales", "profit_margin")
        _safe_ratio("operating_profit", "sales", "operating_margin")
        _safe_ratio(
            "cash_flow_from_operating_activities",
            "sales",
            "cfo_margin",
        )
        _safe_ratio(
            "cash_flow_from_operating_activities",
            "net_profit",
            "cfo_to_profit",
        )
        _safe_ratio("revenue", "total_assets", "asset_turnover")
        _safe_ratio("net_profit", "total_assets", "roa")
        _safe_ratio("total_liabilities", "total_assets", "leverage")
        _safe_ratio(
            "cash_flow_from_operating_activities",
            "total_assets",
            "cfo_to_assets",
        )
        _safe_ratio("debt", "total_assets", "debt_to_assets")
        _safe_ratio("debt", "total_equity", "debt_to_equity")
        _safe_ratio("cash_and_equivalents", "total_assets", "cash_to_assets")
        _safe_ratio("goodwill", "total_assets", "goodwill_to_assets")
        if "accrual_ratio" in needed:
            if (
                "net_profit" in group.columns
                and "cash_flow_from_operating_activities" in group.columns
                and "total_assets" in group.columns
            ):
                net_profit = pd.to_numeric(group["net_profit"], errors="coerce")
                cfo = pd.to_numeric(group["cash_flow_from_operating_activities"], errors="coerce")
                total_assets = pd.to_numeric(group["total_assets"], errors="coerce")
                valid_assets = total_assets.where(total_assets.notna() & (total_assets != 0))
                accrual = (net_profit - cfo) / valid_assets
                group["accrual_ratio"] = accrual.replace([np.inf, -np.inf], np.nan)
        _safe_ratio("accounts_receivable", "revenue", "receivables_to_revenue")
        _safe_ratio("inventory", "revenue", "inventory_to_revenue")
        if "working_capital_to_assets" in needed:
            if (
                "accounts_receivable" in group.columns
                and "inventory" in group.columns
                and "accounts_payable" in group.columns
                and "total_assets" in group.columns
            ):
                receivables = pd.to_numeric(group["accounts_receivable"], errors="coerce")
                inventory = pd.to_numeric(group["inventory"], errors="coerce")
                payables = pd.to_numeric(group["accounts_payable"], errors="coerce")
                total_assets = pd.to_numeric(group["total_assets"], errors="coerce")
                valid_assets = total_assets.where(total_assets.notna() & (total_assets != 0))
                working_capital = receivables + inventory - payables
                ratio = working_capital / valid_assets
                group["working_capital_to_assets"] = ratio.replace([np.inf, -np.inf], np.nan)
        if "net_debt_to_assets" in needed:
            if (
                "debt" in group.columns
                and "cash_and_equivalents" in group.columns
                and "total_assets" in group.columns
            ):
                debt = pd.to_numeric(group["debt"], errors="coerce")
                cash_and_equivalents = pd.to_numeric(group["cash_and_equivalents"], errors="coerce")
                total_assets = pd.to_numeric(group["total_assets"], errors="coerce")
                valid_assets = total_assets.where(total_assets.notna() & (total_assets != 0))
                net_debt = debt - cash_and_equivalents
                ratio = net_debt / valid_assets
                group["net_debt_to_assets"] = ratio.replace([np.inf, -np.inf], np.nan)

        if label_shift_days > 0:
            shifted_price = group[price_col].shift(-label_shift_days)
        else:
            shifted_price = group[price_col]
        entry_price = shifted_price
        if label_horizon_mode == "next_rebalance" and label_next_rebalance_map is not None:
            exit_base = group["trade_date"].map(label_next_rebalance_map)
            shifted_by_date = pd.Series(shifted_price.values, index=group["trade_date"])
            exit_price = exit_base.map(shifted_by_date)
        else:
            exit_price = shifted_price.shift(-label_horizon_days)
        group[target] = exit_price / entry_price - 1.0

        return group

    df = df.groupby("symbol", group_keys=False).apply(add_features)

    missing_features = [feat for feat in features if feat not in df.columns]
    if missing_features:
        if fundamentals_allow_missing:
            logger.warning("Dropping missing features: %s", missing_features)
            features = [feat for feat in features if feat in df.columns]
        else:
            sys.exit(f"Missing features after engineering: {missing_features}")

    meta_cols = ["is_tradable"] if "is_tradable" in df.columns else []
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

    missing_fill_features = feature_missing_features or features
    missing_fill_features = [
        feature for feature in missing_fill_features if feature in features and feature in df.columns
    ]
    if feature_missing_add_indicators and missing_fill_features:
        indicator_features = []
        for feature in missing_fill_features:
            indicator_name = f"{feature}{feature_missing_suffix}"
            if indicator_name in df.columns and indicator_name not in features:
                sys.exit(
                    "features.missing.indicator_suffix collides with an existing column: "
                    f"{indicator_name}"
                )
            if indicator_name not in df.columns:
                df[indicator_name] = df[feature].isna().astype(np.int8)
            indicator_features.append(indicator_name)
        features = list(dict.fromkeys(features + indicator_features))

    df = _ensure_symbol_alias(df)
    execution_passthrough_cols = [
        col for col in execution_pricing_cols if col in df.columns and col != price_col
    ]
    price_passthrough_cols = list(
        dict.fromkeys(
            execution_passthrough_cols
            + [col for col in ("close", "tr_close") if col in df.columns and col != price_col]
        )
    )

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

    passthrough_cols = list(dict.fromkeys(industry_cols))
    cols = (
        ["trade_date", "symbol", price_col]
        + features
        + price_passthrough_cols
        + passthrough_cols
        + meta_cols
        + [target]
    )
    cols = list(dict.fromkeys(cols))
    df = df[cols].copy()

    reference_trade_dates = np.sort(pd.to_datetime(df["trade_date"].unique()).to_numpy())

    if universe_by_date is not None:
        before_rows = len(df)
        df = apply_universe_by_date(df, universe_by_date)
        after_rows = len(df)
        logger.info("Applied universe-by-date filter: %s -> %s rows", before_rows, after_rows)
        if df.empty:
            sys.exit("Universe-by-date filter removed all rows.")

    if feature_missing_method != "none" and missing_fill_features:
        for feature in missing_fill_features:
            df[feature] = pd.to_numeric(df[feature], errors="coerce")
        if feature_missing_method == "zero":
            df[missing_fill_features] = df[missing_fill_features].fillna(0.0)
        elif feature_missing_method == "cross_sectional_median":
            by_date_median = df.groupby("trade_date")[missing_fill_features].transform("median")
            df[missing_fill_features] = df[missing_fill_features].fillna(by_date_median)
        remaining_missing = int(df[missing_fill_features].isna().sum().sum())
        logger.info(
            "Applied feature missing fill: method=%s, features=%s, add_indicators=%s, remaining_nans=%s.",
            feature_missing_method,
            len(missing_fill_features),
            feature_missing_add_indicators,
            remaining_missing,
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
            "If this is a quarterly PIT config, run `csml rqdata inspect-hk-pit-coverage --config ...` "
            "or trim the low-coverage feature block.",
            feature_availability_diagnostics["complete_dates"],
            feature_availability_diagnostics["total_dates"],
            feature_availability_diagnostics["complete_rows"],
            feature_availability_diagnostics["total_rows"],
            _format_feature_availability_rows(
                feature_availability_diagnostics["worst_features"]
            ),
        )

    required_cols = [price_col] + features
    df_features = df.dropna(subset=required_cols).reset_index(drop=True)

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
    if not dropped_date_counts.empty:
        logger.info(
            "Dropped %s dates with < %s symbols (min=%s, max=%s).",
            len(dropped_date_counts),
            min_symbols_per_date,
            int(dropped_date_counts.min()),
            int(dropped_date_counts.max()),
        )
    if len(all_dates_model_full) < 10:
        logger.warning(
            "Only %s model dates remain after feature filtering%s: %s. "
            "Worst features after missing fill: %s.",
            len(all_dates_model_full),
            " and sample-on-rebalance" if sample_on_rebalance_dates else "",
            [pd.Timestamp(date).strftime("%Y-%m-%d") for date in all_dates_model_full],
            _format_feature_availability_rows(
                feature_availability_diagnostics["worst_features"]
            ),
        )

    return {
        "features": features,
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
        "backtest_pricing_df": backtest_pricing_df,
        "bucket_cols": bucket_cols,
        "passthrough_cols": passthrough_cols,
        "price_passthrough_cols": price_passthrough_cols,
        "feature_availability_diagnostics": feature_availability_diagnostics,
    }
