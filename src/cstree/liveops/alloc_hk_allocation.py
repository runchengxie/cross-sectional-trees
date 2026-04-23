from __future__ import annotations

import math
from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd

from .alloc_hk_common import coerce_scalar as _coerce_scalar
from .alloc_hk_common import safe_float
from .alloc_hk_common import to_date as _to_date
from .alloc_hk_market_data import build_order_book_mapping as _build_order_book_mapping
from .alloc_hk_market_data import classify_valuation, compute_valuation_metrics
from .alloc_hk_market_data import is_stock_connect_tradable as _is_stock_connect_tradable
from .alloc_hk_market_data import subset_market_data as _subset_market_data
from .alloc_hk_types import HkAllocSettings, MarketDataBundle, SelectedTicker


def calc_lots(
    target_value: float,
    price: float,
    round_lot: float,
    tradable: bool,
) -> int:
    if not tradable:
        return 0
    if any(math.isnan(x) for x in [target_value, price, round_lot]):
        return 0
    if target_value <= 0 or price <= 0 or round_lot <= 0:
        return 0
    return int(math.floor(target_value / (price * round_lot)))


def build_target_values(
    total_capital: float,
    tickers: Sequence[SelectedTicker],
    allocation_method: str,
) -> dict[str, float]:
    if not tickers:
        raise SystemExit("No holdings selected for allocation.")
    if allocation_method == "equal":
        value = total_capital / len(tickers)
        return {item.symbol: value for item in tickers}
    if allocation_method != "custom":
        raise SystemExit(f"Unsupported allocation method: {allocation_method}")

    weight_map = {item.symbol: float(item.weight or 0.0) for item in tickers}
    if any(item.weight is None for item in tickers):
        raise SystemExit("custom allocation requires weight for each selected ticker.")
    total_weight = sum(weight_map.values())
    if total_weight <= 0:
        raise SystemExit("custom allocation weight sum must be > 0.")
    return {
        symbol: (weight / total_weight) * total_capital
        for symbol, weight in weight_map.items()
    }


def apply_secondary_fill(
    allocation_df: pd.DataFrame,
    total_capital: float,
    enabled: bool,
    avoid_high_valuation: bool,
    avoid_high_valuation_strict: bool,
    max_steps: int,
    allow_over_alloc: bool,
    max_over_alloc_ratio: float,
    max_over_alloc_amount: float,
    max_over_alloc_lots_per_ticker: int,
    cash_buffer_ratio: float,
    cash_buffer_amount: float,
    estimated_fee_per_order: float,
) -> tuple[pd.DataFrame, dict[str, float | int | bool]]:
    updated = allocation_df.copy()
    if "lots_extra" not in updated.columns:
        updated["lots_extra"] = 0
    updated["lots_extra"] = pd.to_numeric(updated["lots_extra"], errors="coerce").fillna(0).astype(int)

    def recompute_position_columns(frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.copy()
        for idx, row in out.iterrows():
            lots_raw = safe_float(row.get("lots", 0))
            lots = max(int(lots_raw) if not math.isnan(lots_raw) else 0, 0)
            round_lot = safe_float(row.get("round_lot", np.nan))
            price = safe_float(row.get("price", np.nan))
            lot_cost_existing = safe_float(row.get("lot_cost", np.nan))
            if (math.isnan(price) or price <= 0) and round_lot > 0 and not math.isnan(round_lot):
                if lot_cost_existing > 0:
                    price = lot_cost_existing / round_lot
            target_value = safe_float(row.get("target_value", np.nan))
            tradable = bool(row.get("tradable", False))

            shares = int(round(lots * round_lot)) if round_lot > 0 and not math.isnan(round_lot) else 0
            est_value = float(shares * price) if price > 0 and not math.isnan(price) else 0.0
            lot_cost = float(price * round_lot) if tradable and price > 0 and round_lot > 0 else float("nan")
            if math.isnan(target_value):
                target_value = 0.0

            out.at[idx, "lots"] = lots
            out.at[idx, "shares"] = shares
            out.at[idx, "est_value"] = est_value
            out.at[idx, "lot_cost"] = lot_cost
            out.at[idx, "gap_to_target"] = float(target_value - est_value)
        return out

    buffer_amount = float(total_capital * max(cash_buffer_ratio, 0.0) + max(cash_buffer_amount, 0.0))
    available_budget = max(float(total_capital - buffer_amount), 0.0)

    if not enabled or updated.empty:
        updated = recompute_position_columns(updated)
        return (
            updated,
            {
                "secondary_fill_enabled": bool(enabled),
                "secondary_fill_steps": 0,
                "secondary_fill_spent": 0.0,
                "secondary_fill_fee_spent": 0.0,
                "secondary_fill_cash_buffer": float(buffer_amount),
                "secondary_fill_budget_after_buffer": float(available_budget),
                "cash_remaining_after_fill": max(total_capital - float(updated["est_value"].sum()), 0.0),
            },
        )

    eps = 1e-9
    over_alloc_caps: list[float] = []
    if allow_over_alloc and max_over_alloc_ratio > 0:
        over_alloc_caps.append(float(total_capital * max_over_alloc_ratio))
    if allow_over_alloc and max_over_alloc_amount > 0:
        over_alloc_caps.append(float(max_over_alloc_amount))
    max_over_alloc_value = min(over_alloc_caps) if over_alloc_caps else (float("inf") if allow_over_alloc else 0.0)

    valuation_rank = {"LOW": 0, "NEUTRAL": 1, "HIGH": 2, "EXTREME": 3, "NA": 4}
    disallowed_when_avoid = {"HIGH", "EXTREME"}
    over_alloc_count_by_idx: dict[Any, int] = {idx: 0 for idx in updated.index}

    def candidate_rows(cash_left: float) -> pd.DataFrame:
        candidates = updated[
            (updated["tradable"] == True)
            & (updated["lot_cost"] > 0)
            & (updated["gap_to_target"] > eps)
        ].copy()
        if candidates.empty:
            return candidates

        candidates["required_cash"] = pd.to_numeric(candidates["lot_cost"], errors="coerce").fillna(0.0) + max(
            estimated_fee_per_order, 0.0
        )
        candidates = candidates[candidates["required_cash"] <= cash_left + eps]
        if candidates.empty:
            return candidates

        candidates["new_gap"] = candidates["gap_to_target"] - candidates["lot_cost"]
        candidates["improves_gap"] = (candidates["new_gap"].abs() + eps) < candidates["gap_to_target"].abs()
        candidates = candidates[candidates["improves_gap"] == True]
        if candidates.empty:
            return candidates

        if not allow_over_alloc:
            candidates = candidates[candidates["new_gap"] >= -eps]
        else:
            candidates = candidates[candidates["new_gap"] >= (-max_over_alloc_value - eps)]
            if max_over_alloc_lots_per_ticker <= 0:
                candidates = candidates[candidates["new_gap"] >= -eps]
            else:
                over_limit_mask = []
                for idx, row in candidates.iterrows():
                    over_after = float(row["new_gap"]) < -eps
                    over_count = int(over_alloc_count_by_idx.get(idx, 0))
                    over_limit_mask.append(not (over_after and over_count >= max_over_alloc_lots_per_ticker))
                candidates = candidates.loc[over_limit_mask]
        if candidates.empty:
            return candidates

        if avoid_high_valuation:
            preferred = candidates[~candidates["valuation"].isin(disallowed_when_avoid)]
            if not preferred.empty:
                return preferred
            if avoid_high_valuation_strict:
                return preferred
        return candidates

    def ranking_key(row: pd.Series) -> tuple[float, float, float, str]:
        valuation = str(row.get("valuation", "NA"))
        rank = valuation_rank.get(valuation, 5)
        deviation_after_lot = abs(float(row["gap_to_target"]) - float(row["lot_cost"]))
        lot_cost = float(row["lot_cost"])
        symbol = str(row.get("symbol", ""))
        return (float(rank), deviation_after_lot, lot_cost, symbol)

    cash_left = max(available_budget - float(updated["est_value"].sum()), 0.0)
    tradable_costs = pd.to_numeric(updated.loc[updated["tradable"] == True, "lot_cost"], errors="coerce")
    tradable_costs = tradable_costs[tradable_costs > 0]
    if tradable_costs.empty:
        step_limit = 0
    else:
        min_required_cash = float(tradable_costs.min() + max(estimated_fee_per_order, 0.0))
        if min_required_cash <= 0:
            step_limit = max_steps
        else:
            theoretical_limit = int(math.floor(cash_left / min_required_cash)) + 1
            step_limit = min(max_steps, max(theoretical_limit, 0))

    steps = 0
    spent = 0.0
    fee_spent = 0.0

    while cash_left > eps and steps < step_limit:
        candidates = candidate_rows(cash_left)
        if candidates.empty:
            break

        selected_idx = min(candidates.index, key=lambda idx: ranking_key(candidates.loc[idx]))
        row = updated.loc[selected_idx]
        lot_cost = float(row["lot_cost"])
        required_cash = lot_cost + max(estimated_fee_per_order, 0.0)
        if lot_cost <= 0 or required_cash > cash_left + eps:
            break

        updated.at[selected_idx, "lots"] = int(row["lots"]) + 1
        updated.at[selected_idx, "lots_extra"] = int(row.get("lots_extra", 0)) + 1

        new_gap = float(row["gap_to_target"]) - lot_cost
        if new_gap < -eps:
            over_alloc_count_by_idx[selected_idx] = int(over_alloc_count_by_idx.get(selected_idx, 0)) + 1

        cash_left -= required_cash
        spent += lot_cost
        fee_spent += max(estimated_fee_per_order, 0.0)
        steps += 1

    updated = recompute_position_columns(updated)
    cash_left = max(total_capital - float(updated["est_value"].sum()) - float(fee_spent), 0.0)
    return (
        updated,
        {
            "secondary_fill_enabled": bool(enabled),
            "secondary_fill_steps": int(steps),
            "secondary_fill_spent": float(spent),
            "secondary_fill_fee_spent": float(fee_spent),
            "secondary_fill_cash_buffer": float(buffer_amount),
            "secondary_fill_budget_after_buffer": float(available_budget),
            "cash_remaining_after_fill": float(cash_left),
        },
    )


def build_allocation_table(
    *,
    settings: HkAllocSettings,
    tickers: Sequence[SelectedTicker],
    as_of,
    market_data: MarketDataBundle,
    apply_secondary_fill_fn: Callable[..., tuple[pd.DataFrame, dict[str, float | int | bool]]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    _, order_book_ids, symbol_to_oid = _build_order_book_mapping(tickers)
    instruments_df, latest_prices, close_hist, _ = _subset_market_data(market_data, order_book_ids)

    percentile, zscore, q_high, q_extreme = compute_valuation_metrics(
        close_hist,
        window=settings.roll_window,
        sell_quantile=settings.sell_quantile,
        extreme_quantile=settings.extreme_quantile,
    )

    if close_hist.empty:
        raise SystemExit("No historical HK price data returned; check RQData permissions or ticker list.")
    latest_row = close_hist.index.max()
    target_values = build_target_values(settings.cash, tickers, settings.method)

    rows: list[dict[str, Any]] = []
    for item in tickers:
        symbol = item.symbol
        oid = symbol_to_oid[symbol]

        instrument_symbol = None
        if oid in instruments_df.index and "symbol" in instruments_df.columns:
            instrument_symbol = _coerce_scalar(instruments_df.loc[oid, "symbol"])
        round_lot = (
            safe_float(instruments_df.loc[oid, "round_lot"])
            if oid in instruments_df.index and "round_lot" in instruments_df.columns
            else float("nan")
        )
        stock_connect = (
            _coerce_scalar(instruments_df.loc[oid, "stock_connect"])
            if oid in instruments_df.index and "stock_connect" in instruments_df.columns
            else None
        )
        price = safe_float(latest_prices.at[oid, "price"])
        price_source = str(latest_prices.at[oid, "price_source"])
        pricing_date = _to_date(latest_prices.at[oid, "pricing_date"])

        is_connect_tradable = _is_stock_connect_tradable(stock_connect)
        tradable = (
            (not settings.require_stock_connect or is_connect_tradable)
            and price > 0
            and round_lot > 0
        )

        target_value = float(target_values[symbol])
        lots = calc_lots(target_value, price, round_lot, tradable)
        lot_cost = float(price * round_lot) if tradable else float("nan")
        shares = int(lots * round_lot) if round_lot > 0 and not math.isnan(round_lot) else 0
        est_value = float(shares * price) if price > 0 and not math.isnan(price) else 0.0
        gap_to_target = float(target_value - est_value)

        pct = safe_float(percentile.loc[latest_row, oid]) if oid in percentile.columns else np.nan
        z_1y = safe_float(zscore.loc[latest_row, oid]) if oid in zscore.columns else np.nan
        high_line = safe_float(q_high.loc[latest_row, oid]) if oid in q_high.columns else np.nan
        extreme_line = safe_float(q_extreme.loc[latest_row, oid]) if oid in q_extreme.columns else np.nan

        if math.isnan(high_line) or math.isnan(extreme_line):
            overpriced_range = None
        else:
            overpriced_range = f"[{high_line:.4f}, {extreme_line:.4f}]"

        rows.append(
            {
                "symbol": symbol,
                "name": item.name or (str(instrument_symbol).strip() if instrument_symbol else None),
                "side": item.side,
                "rank": item.rank,
                "signal": item.signal,
                "weight": item.weight,
                "order_book_id": oid,
                "price": price,
                "price_source": price_source,
                "pricing_date": pricing_date,
                "round_lot": round_lot,
                "stock_connect": stock_connect,
                "target_value": target_value,
                "lot_cost": lot_cost,
                "lots": lots,
                "lots_extra": 0,
                "shares": shares,
                "est_value": est_value,
                "gap_to_target": gap_to_target,
                "pct_1y": pct,
                "z_1y": z_1y,
                "valuation": classify_valuation(
                    pct,
                    z_1y,
                    sell_quantile=settings.sell_quantile,
                    extreme_quantile=settings.extreme_quantile,
                ),
                "overpriced_low": high_line,
                "overpriced_high": extreme_line,
                "overpriced_range": overpriced_range,
                "tradable": tradable,
            }
        )

    allocation_df = pd.DataFrame(rows)
    allocation_df, fill_stats = apply_secondary_fill_fn(
        allocation_df,
        total_capital=settings.cash,
        enabled=settings.secondary_fill_enabled,
        avoid_high_valuation=settings.secondary_fill_avoid_high_valuation,
        avoid_high_valuation_strict=settings.secondary_fill_avoid_high_valuation_strict,
        max_steps=settings.secondary_fill_max_steps,
        allow_over_alloc=settings.secondary_fill_allow_over_alloc,
        max_over_alloc_ratio=settings.secondary_fill_max_over_alloc_ratio,
        max_over_alloc_amount=settings.secondary_fill_max_over_alloc_amount,
        max_over_alloc_lots_per_ticker=settings.secondary_fill_max_over_alloc_lots_per_ticker,
        cash_buffer_ratio=settings.secondary_fill_cash_buffer_ratio,
        cash_buffer_amount=settings.secondary_fill_cash_buffer_amount,
        estimated_fee_per_order=settings.secondary_fill_estimated_fee_per_order,
    )

    allocation_df["lots_base"] = allocation_df["lots"] - allocation_df["lots_extra"]
    allocation_df["gap_ratio"] = np.where(
        allocation_df["target_value"] > 0,
        allocation_df["gap_to_target"] / allocation_df["target_value"],
        np.nan,
    )

    pricing_dates = pd.to_datetime(latest_prices["pricing_date"], errors="coerce").dropna()
    summary_pricing_date = _to_date(pricing_dates.max()) if not pricing_dates.empty else as_of
    source_counts = latest_prices["price_source"].value_counts(dropna=False).to_dict()
    source_parts = [f"{str(source)}:{int(count)}" for source, count in source_counts.items()]
    summary_pricing_source = next(iter(source_counts.keys())) if len(source_counts) == 1 else "mixed"

    summary_df = pd.DataFrame(
        [
            {
                "as_of": as_of,
                "pricing_date": summary_pricing_date,
                "pricing_source": summary_pricing_source,
                "pricing_source_detail": ", ".join(source_parts),
                "selected_n": len(tickers),
                "total_capital": settings.cash,
                "allocation_method": settings.method,
                "require_stock_connect": settings.require_stock_connect,
                "total_est_value": float(allocation_df["est_value"].sum()),
                "total_gap": float(allocation_df["gap_to_target"].sum()),
                "cash_used_ratio": (
                    float(allocation_df["est_value"].sum()) / settings.cash
                    if settings.cash > 0
                    else np.nan
                ),
                "secondary_fill_enabled": fill_stats["secondary_fill_enabled"],
                "secondary_fill_steps": fill_stats["secondary_fill_steps"],
                "secondary_fill_spent": fill_stats["secondary_fill_spent"],
                "secondary_fill_fee_spent": fill_stats["secondary_fill_fee_spent"],
                "secondary_fill_cash_buffer": fill_stats["secondary_fill_cash_buffer"],
                "secondary_fill_budget_after_buffer": fill_stats["secondary_fill_budget_after_buffer"],
                "cash_remaining_after_fill": fill_stats["cash_remaining_after_fill"],
            }
        ]
    )
    return allocation_df, summary_df
