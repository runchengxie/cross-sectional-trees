from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import pandas as pd

from ..date_utils import resolve_date_token as _resolve_date_token
from ..modeling import build_model, fit_model
from ..transform import apply_score_postprocess
from .dates import _build_trade_date_slices, _slice_with_train_window
from ..portfolio import build_positions_by_rebalance
from ..rebalance import get_rebalance_dates
from ..split import build_sample_weight


logger = logging.getLogger("csml")


def _prepare_live_snapshot(
    df_features: pd.DataFrame,
    model: Any,
    *,
    context: Mapping[str, Any],
) -> dict[str, Any]:
    live_state = {
        "live_as_of": None,
        "positions_by_rebalance_live": None,
        "live_positions_ready": False,
    }
    if not bool(context["live_enabled"]):
        return live_state

    market = context["market"]
    provider = context["provider"]
    live_as_of = _resolve_date_token(
        context["live_as_of_token"],
        default="t-1",
        market=market,
        provider=provider,
    )
    live_state["live_as_of"] = live_as_of

    target = context["target"]
    df_live = df_features[df_features["trade_date"] <= live_as_of].copy()
    if df_live.empty:
        logger.warning("Live snapshot skipped: no data on or before %s.", live_as_of.date())
        return live_state

    df_live_labeled = df_live[df_live[target].notna()].copy()
    if df_live_labeled.empty:
        logger.warning("Live snapshot skipped: no labeled data on or before %s.", live_as_of.date())
        return live_state

    live_model = model
    if context["live_train_mode"] == "full":
        live_model = build_model(context["model_type"], context["model_params"])
        (
            df_live_labeled_sorted,
            live_all_dates,
            live_date_start_rows,
            live_date_end_rows,
            live_date_to_pos,
        ) = _build_trade_date_slices(df_live_labeled)
        df_live_train, _ = _slice_with_train_window(
            df_live_labeled_sorted,
            live_date_start_rows,
            live_date_end_rows,
            live_date_to_pos,
            live_all_dates,
            label="live full fit",
            train_window_mode=context["train_window_mode"],
            train_window_size=context["train_window_size"],
            train_window_unit=context["train_window_unit"],
        )
        if df_live_train.empty:
            logger.warning("Live snapshot skipped: model.train_window left no in-sample data.")
            live_model = None
        else:
            live_weights = build_sample_weight(
                df_live_train,
                context["sample_weight_mode"],
                params=context["sample_weight_params"],
            )
            fit_model(
                live_model,
                context["model_type"],
                df_live_train,
                features=context["features"],
                target_col=context["train_target"],
                sample_weight=live_weights,
            )

    if live_model is None:
        logger.warning("Live snapshot skipped: no live model was fitted.")
        return live_state

    df_live["pred"] = live_model.predict(df_live[context["features"]])
    df_live["pred"] = apply_score_postprocess(
        df_live,
        "pred",
        method=context["score_postprocess_method"],
        columns=context["score_postprocess_columns"],
        strength=context["score_postprocess_strength"],
        min_obs=context["score_postprocess_min_obs"],
    )
    live_pred_col = "pred"
    signal_direction = context["signal_direction"]
    if signal_direction != 1.0:
        df_live["signal"] = df_live["pred"] * signal_direction
        live_pred_col = "signal"

    live_dates = sorted(df_live["trade_date"].unique())
    live_rebalance = get_rebalance_dates(live_dates, context["backtest_rebalance_frequency"])
    live_counts = df_live.groupby("trade_date")["symbol"].nunique()
    live_valid_dates = set(live_counts[live_counts >= context["min_symbols_per_date"]].index)
    live_rebalance = [date for date in live_rebalance if date in live_valid_dates]

    backtest_tradable_col = context["backtest_tradable_col"]
    backtest_group_col = context["backtest_group_col"]
    positions_by_rebalance_live = build_positions_by_rebalance(
        df_live,
        pred_col=live_pred_col,
        price_col=context["price_col"],
        rebalance_dates=live_rebalance,
        top_k=context["backtest_top_k"],
        shift_days=context["label_shift_days"],
        weighting=context["backtest_weighting"],
        buffer_exit=context["backtest_buffer_exit"],
        buffer_entry=context["backtest_buffer_entry"],
        long_only=context["backtest_long_only"],
        short_k=context["backtest_short_k"],
        tradable_col=backtest_tradable_col if backtest_tradable_col in df_live.columns else None,
        group_col=backtest_group_col if backtest_group_col in df_live.columns else None,
        max_names_per_group=context["backtest_max_names_per_group"],
        execution=context["execution_model"],
    )
    if positions_by_rebalance_live is None or positions_by_rebalance_live.empty:
        logger.warning("Live snapshot skipped: no positions generated.")
        return live_state

    live_state["positions_by_rebalance_live"] = positions_by_rebalance_live
    live_state["live_positions_ready"] = True

    entry_dates_live = pd.to_datetime(
        positions_by_rebalance_live["entry_date"], errors="coerce"
    )
    if entry_dates_live.notna().any():
        latest_entry = entry_dates_live.max()
        holdings_count = int((entry_dates_live == latest_entry).sum())
        logger.info(
            "Live snapshot ready: as_of=%s, entry_date=%s, holdings=%s",
            live_as_of.strftime("%Y-%m-%d"),
            latest_entry.strftime("%Y-%m-%d"),
            holdings_count,
        )
    return live_state
