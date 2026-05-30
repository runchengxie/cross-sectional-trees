from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from market_data_platform.symbols import canonicalize_symbol_columns
from .execution import ExecutionModel, SelectionConstraints
from .execution_calendar import build_execution_date_map


def normalize_weighting_mode(weighting: str | None) -> str:
    mode = str(weighting or "equal").strip().lower()
    if mode not in {"equal", "signal"}:
        raise ValueError("weighting must be one of: equal, signal.")
    return mode


def _equal_weights(holdings: list[str]) -> pd.Series:
    if not holdings:
        return pd.Series(dtype=float)
    return pd.Series(np.repeat(1.0 / len(holdings), len(holdings)), index=holdings, dtype=float)


def normalize_position_weights(weights: pd.Series) -> pd.Series:
    if weights is None or weights.empty:
        return pd.Series(dtype=float)
    cleaned = pd.to_numeric(weights, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if cleaned.empty:
        return pd.Series(dtype=float)
    total = float(cleaned.sum())
    if not np.isfinite(total) or total <= 0:
        return _equal_weights(list(cleaned.index))
    return cleaned / total


def build_position_weights(
    day: pd.DataFrame,
    holdings: list[str],
    pred_col: str,
    *,
    side: str,
    weighting: str = "equal",
) -> pd.Series:
    mode = normalize_weighting_mode(weighting)
    base = _equal_weights(holdings)
    if mode == "equal" or base.empty:
        return base

    if side not in {"long", "short"}:
        raise ValueError("side must be one of: long, short.")

    signal = pd.to_numeric(
        day.set_index("symbol").reindex(holdings)[pred_col],
        errors="coerce",
    )
    if side == "short":
        signal = -signal
    if signal.empty or signal.isna().all():
        return base

    signal = signal.fillna(float(signal.mean()) if signal.notna().any() else 0.0)
    std = float(signal.std(ddof=0))
    if not np.isfinite(std) or std <= 0:
        return base

    scaled = ((signal - float(signal.mean())) / std).clip(-5.0, 5.0)
    raw = np.exp(scaled.to_numpy(dtype=float))
    total = float(np.sum(raw))
    if not np.isfinite(total) or total <= 0:
        return base
    return normalize_position_weights(pd.Series(raw, index=signal.index, dtype=float))


def apply_rebalance_buffer(
    ranked_codes: list[str],
    prev_holdings: Optional[set[str]],
    k: int,
    buffer_exit: int,
    buffer_entry: int,
) -> list[str]:
    if not ranked_codes or k <= 0:
        return []
    if prev_holdings is None or (buffer_exit <= 0 and buffer_entry <= 0):
        return list(ranked_codes)

    keep_limit = min(len(ranked_codes), k + max(0, buffer_exit))
    entry_limit = min(len(ranked_codes), max(0, k - max(0, buffer_entry)))

    keep_set = set(ranked_codes[:keep_limit]) & prev_holdings
    candidate_order: list[str] = [code for code in ranked_codes if code in keep_set]

    preferred = set(ranked_codes[:entry_limit]) if entry_limit > 0 else set()
    for code in ranked_codes:
        if len(candidate_order) >= k:
            break
        if code in candidate_order:
            continue
        if preferred and code not in preferred:
            continue
        candidate_order.append(code)

    if len(candidate_order) < k:
        for code in ranked_codes:
            if len(candidate_order) >= k:
                break
            if code in candidate_order:
                continue
            candidate_order.append(code)

    return candidate_order


def select_holdings(
    day: pd.DataFrame,
    entry_date: pd.Timestamp,
    k: int,
    pred_col: str,
    *,
    ascending: bool,
    price_table: pd.DataFrame,
    tradable_table: Optional[pd.DataFrame],
    amount_table: Optional[pd.DataFrame],
    constraints: Optional[SelectionConstraints],
    prev_holdings: Optional[set[str]],
    buffer_exit: int,
    buffer_entry: int,
    group_col: Optional[str] = None,
    max_names_per_group: Optional[int] = None,
    entry_lookup_date: pd.Timestamp | None = None,
) -> tuple[list[str], pd.Series]:
    if day.empty or k <= 0:
        return [], pd.Series(dtype=float)
    lookup_date = entry_lookup_date or entry_date
    if lookup_date not in price_table.index:
        return [], pd.Series(dtype=float)
    constraints = constraints or SelectionConstraints()

    ranked = day.sort_values(pred_col, ascending=ascending)
    ranked_codes = ranked["symbol"].tolist()
    candidate_order = apply_rebalance_buffer(
        ranked_codes,
        prev_holdings,
        k,
        buffer_exit,
        buffer_entry,
    )
    group_map = None
    if (
        group_col
        and max_names_per_group is not None
        and max_names_per_group > 0
        and group_col in day.columns
    ):
        group_map = day.set_index("symbol")[group_col].to_dict()

    entry_prices = price_table.loc[lookup_date]
    amount_values = None
    if constraints.min_amount is not None:
        if amount_table is None or lookup_date not in amount_table.index:
            return [], pd.Series(dtype=float)
        amount_values = amount_table.loc[lookup_date]
    tradable_flags = None
    if tradable_table is not None:
        if lookup_date not in tradable_table.index:
            return [], pd.Series(dtype=float)
        tradable_flags = tradable_table.loc[lookup_date]

    holdings: list[str] = []
    group_counts: dict[object, int] = {}
    for symbol in candidate_order:
        if len(holdings) >= k:
            break
        price = entry_prices.get(symbol, np.nan)
        if not np.isfinite(price):
            continue
        if constraints.min_price is not None and float(price) < float(constraints.min_price):
            continue
        if constraints.min_amount is not None:
            amount = amount_values.get(symbol, np.nan) if amount_values is not None else np.nan
            if not np.isfinite(amount) or float(amount) < float(constraints.min_amount):
                continue
        if tradable_flags is not None and not bool(tradable_flags.get(symbol, False)):
            continue
        if group_map is not None:
            group_value = group_map.get(symbol)
            if pd.notna(group_value):
                current_count = group_counts.get(group_value, 0)
                if current_count >= max_names_per_group:
                    continue
                group_counts[group_value] = current_count + 1
        holdings.append(symbol)
    if not holdings:
        return [], pd.Series(dtype=float)
    return holdings, entry_prices.reindex(holdings)


def build_positions_by_rebalance(
    data: pd.DataFrame,
    pred_col: str,
    price_col: str,
    rebalance_dates: list[pd.Timestamp],
    top_k: int,
    shift_days: int,
    *,
    weighting: str = "equal",
    buffer_exit: int = 0,
    buffer_entry: int = 0,
    long_only: bool = True,
    short_k: Optional[int] = None,
    tradable_col: Optional[str] = None,
    group_col: Optional[str] = None,
    max_names_per_group: Optional[int] = None,
    execution: Optional[ExecutionModel] = None,
    entry_dates_by_rebalance: Optional[dict[pd.Timestamp, pd.Timestamp]] = None,
) -> pd.DataFrame:
    if data is not None and not data.empty:
        data = canonicalize_symbol_columns(data, context="Portfolio data")
        data = data.copy()
        data["trade_date"] = pd.to_datetime(data["trade_date"]).dt.normalize()
    weighting_mode = normalize_weighting_mode(weighting)
    entry_price_col = execution.entry_policy.price_col if execution is not None else price_col
    selection_constraints = (
        execution.selection_constraints if execution is not None else SelectionConstraints()
    )
    if data.empty or not rebalance_dates or top_k <= 0:
        return pd.DataFrame(
            columns=[
                "rebalance_date",
                "entry_date",
                "symbol",
                "weight",
                "signal",
                "rank",
                "side",
            ]
        )
    if entry_price_col not in data.columns:
        raise ValueError(f"Portfolio entry price column not found: {entry_price_col}")

    trade_dates = [pd.Timestamp(date).normalize() for date in sorted(data["trade_date"].unique())]
    if len(trade_dates) < 2 and not entry_dates_by_rebalance:
        return pd.DataFrame(
            columns=[
                "rebalance_date",
                "entry_date",
                "symbol",
                "weight",
                "signal",
                "rank",
                "side",
            ]
        )
    date_to_idx = {date: idx for idx, date in enumerate(trade_dates)}
    price_table = data.pivot(index="trade_date", columns="symbol", values=entry_price_col)
    day_groups = {date: group for date, group in data.groupby("trade_date", sort=False)}
    explicit_entry_dates = {
        pd.Timestamp(key).normalize(): pd.Timestamp(value).normalize()
        for key, value in (entry_dates_by_rebalance or {}).items()
    }
    calendar_entry_dates = {}
    if not explicit_entry_dates and execution is not None:
        calendar_entry_dates = build_execution_date_map(
            rebalance_dates,
            shift_days,
            trade_dates,
            calendar=execution.calendar,
            open_dates=execution.calendar_open_dates,
            closed_dates=execution.calendar_closed_dates,
        )

    tradable_table = None
    if tradable_col and tradable_col in data.columns:
        tradable_table = data.pivot(index="trade_date", columns="symbol", values=tradable_col)
        tradable_table = tradable_table.fillna(False).astype(bool)
    amount_table = None
    amount_col = selection_constraints.amount_col
    if selection_constraints.min_amount is not None:
        if amount_col not in data.columns:
            raise ValueError(f"Portfolio liquidity column not found: {amount_col}")
        amount_table = data.pivot(index="trade_date", columns="symbol", values=amount_col)

    results: list[dict[str, object]] = []
    prev_holdings: Optional[set[str]] = None
    prev_short_holdings: Optional[set[str]] = None

    for reb_date in rebalance_dates:
        reb_date = pd.Timestamp(reb_date).normalize()
        if reb_date not in date_to_idx:
            continue
        entry_date = explicit_entry_dates.get(reb_date) or calendar_entry_dates.get(reb_date)
        entry_lookup_date = None
        if entry_date is None:
            entry_idx = date_to_idx[reb_date] + shift_days
            if entry_idx >= len(trade_dates):
                continue
            entry_date = trade_dates[entry_idx]
        entry_date = pd.Timestamp(entry_date).normalize()
        if entry_date not in date_to_idx:
            entry_lookup_date = reb_date
        day = day_groups.get(reb_date)
        if day is None or day.empty:
            continue

        k = min(int(top_k), len(day))
        if k <= 0:
            continue

        if long_only:
            holdings, _ = select_holdings(
                day,
                entry_date,
                k,
                pred_col,
                ascending=False,
                price_table=price_table,
                tradable_table=tradable_table,
                amount_table=amount_table,
                constraints=selection_constraints,
                prev_holdings=prev_holdings,
                buffer_exit=buffer_exit,
                buffer_entry=buffer_entry,
                group_col=group_col,
                max_names_per_group=max_names_per_group,
                entry_lookup_date=entry_lookup_date,
            )
            if not holdings:
                continue
            weights = build_position_weights(
                day,
                holdings,
                pred_col,
                side="long",
                weighting=weighting_mode,
            )
            if weights.empty:
                continue
            ranked_codes = day.sort_values(pred_col, ascending=False)["symbol"].tolist()
            rank_map = {code: idx + 1 for idx, code in enumerate(ranked_codes)}
            signal_map = day.set_index("symbol")[pred_col].to_dict()
            for code in holdings:
                results.append(
                    {
                        "rebalance_date": reb_date.strftime("%Y%m%d"),
                        "entry_date": entry_date.strftime("%Y%m%d"),
                        "symbol": code,
                        "weight": float(weights.get(code, 0.0)),
                        "signal": float(signal_map.get(code, np.nan)),
                        "rank": int(rank_map.get(code, 0)),
                        "side": "long",
                    }
                )
            prev_holdings = set(holdings)
            continue

        short_k_final = short_k if short_k is not None else k
        short_k_final = min(int(short_k_final), len(day) - k)
        if short_k_final <= 0:
            continue

        long_holdings, _ = select_holdings(
            day,
            entry_date,
            k,
            pred_col,
            ascending=False,
            price_table=price_table,
            tradable_table=tradable_table,
            amount_table=amount_table,
            constraints=selection_constraints,
            prev_holdings=prev_holdings,
            buffer_exit=buffer_exit,
            buffer_entry=buffer_entry,
            group_col=group_col,
            max_names_per_group=max_names_per_group,
            entry_lookup_date=entry_lookup_date,
        )
        short_holdings, _ = select_holdings(
            day,
            entry_date,
            short_k_final,
            pred_col,
            ascending=True,
            price_table=price_table,
            tradable_table=tradable_table,
            amount_table=amount_table,
            constraints=selection_constraints,
            prev_holdings=prev_short_holdings,
            buffer_exit=buffer_exit,
            buffer_entry=buffer_entry,
            group_col=group_col,
            max_names_per_group=max_names_per_group,
            entry_lookup_date=entry_lookup_date,
        )
        if not long_holdings or not short_holdings:
            continue

        long_weights = build_position_weights(
            day,
            long_holdings,
            pred_col,
            side="long",
            weighting=weighting_mode,
        )
        short_weights = build_position_weights(
            day,
            short_holdings,
            pred_col,
            side="short",
            weighting=weighting_mode,
        )
        if long_weights.empty or short_weights.empty:
            continue
        long_ranked = day.sort_values(pred_col, ascending=False)["symbol"].tolist()
        short_ranked = day.sort_values(pred_col, ascending=True)["symbol"].tolist()
        long_rank_map = {code: idx + 1 for idx, code in enumerate(long_ranked)}
        short_rank_map = {code: idx + 1 for idx, code in enumerate(short_ranked)}
        signal_map = day.set_index("symbol")[pred_col].to_dict()

        for code in long_holdings:
            results.append(
                {
                    "rebalance_date": reb_date.strftime("%Y%m%d"),
                    "entry_date": entry_date.strftime("%Y%m%d"),
                    "symbol": code,
                    "weight": float(long_weights.get(code, 0.0)),
                    "signal": float(signal_map.get(code, np.nan)),
                    "rank": int(long_rank_map.get(code, 0)),
                    "side": "long",
                }
            )
        for code in short_holdings:
            results.append(
                {
                    "rebalance_date": reb_date.strftime("%Y%m%d"),
                    "entry_date": entry_date.strftime("%Y%m%d"),
                    "symbol": code,
                    "weight": float(-short_weights.get(code, 0.0)),
                    "signal": float(signal_map.get(code, np.nan)),
                    "rank": int(short_rank_map.get(code, 0)),
                    "side": "short",
                }
            )

        prev_holdings = set(long_holdings)
        prev_short_holdings = set(short_holdings)

    if not results:
        return pd.DataFrame(
            columns=[
                "rebalance_date",
                "entry_date",
                "symbol",
                "weight",
                "signal",
                "rank",
                "side",
            ]
        )

    output = pd.DataFrame(results)
    output.sort_values(["entry_date", "side", "rank", "symbol"], inplace=True)
    return output.reset_index(drop=True)
