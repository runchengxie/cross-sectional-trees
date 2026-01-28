from __future__ import annotations

from typing import Literal, Optional

import numpy as np
import pandas as pd


def backtest_topk(
    data: pd.DataFrame,
    pred_col: str,
    price_col: str,
    rebalance_dates: list[pd.Timestamp],
    top_k: int,
    shift_days: int,
    cost_bps: float,
    trading_days_per_year: int,
    exit_mode: Literal["rebalance", "label_horizon"] = "rebalance",
    exit_horizon_days: Optional[int] = None,
):
    trade_dates = sorted(data["trade_date"].unique())
    if len(trade_dates) < 2:
        return None
    date_to_idx = {date: idx for idx, date in enumerate(trade_dates)}
    price_table = data.pivot(index="trade_date", columns="ts_code", values=price_col)

    net_returns = []
    gross_returns = []
    turnovers = []
    period_info = []
    prev_holdings = None

    for i, reb_date in enumerate(rebalance_dates):
        if reb_date not in date_to_idx:
            continue
        if exit_mode == "rebalance":
            if i >= len(rebalance_dates) - 1:
                break
            next_reb = rebalance_dates[i + 1]
            if next_reb not in date_to_idx:
                continue
            entry_idx = date_to_idx[reb_date] + shift_days
            exit_idx = date_to_idx[next_reb] + shift_days
        else:
            if exit_horizon_days is None:
                raise ValueError("exit_horizon_days is required for exit_mode='label_horizon'.")
            entry_idx = date_to_idx[reb_date] + shift_days
            exit_idx = entry_idx + exit_horizon_days

        if entry_idx >= len(trade_dates) or exit_idx >= len(trade_dates) or entry_idx >= exit_idx:
            continue

        entry_date = trade_dates[entry_idx]
        exit_date = trade_dates[exit_idx]
        day = data[data["trade_date"] == reb_date]
        if day.empty:
            continue

        k = min(top_k, len(day))
        if k <= 0:
            continue

        holdings = list(day.nlargest(k, pred_col)["ts_code"])
        entry_prices = price_table.loc[entry_date, holdings]
        exit_prices = price_table.loc[exit_date, holdings]
        valid = entry_prices.notna() & exit_prices.notna()
        if valid.sum() == 0:
            continue

        period_returns = (exit_prices[valid] / entry_prices[valid]) - 1.0
        gross = period_returns.mean()
        turnover = np.nan
        if prev_holdings is not None:
            overlap = len(set(holdings) & prev_holdings)
            turnover = 1 - overlap / k
        cost = 0.0 if prev_holdings is None else 2 * (cost_bps / 10000.0) * turnover
        net = gross - cost

        gross_returns.append(gross)
        net_returns.append(net)
        turnovers.append(turnover)
        period_info.append(
            {
                "rebalance_date": reb_date,
                "entry_idx": entry_idx,
                "exit_idx": exit_idx,
                "entry_date": entry_date,
                "exit_date": exit_date,
            }
        )
        prev_holdings = set(holdings)

    if not net_returns:
        return None

    index = [info["exit_date"] for info in period_info]
    net_series = pd.Series(net_returns, index=index, name="net_return")
    gross_series = pd.Series(gross_returns, index=index, name="gross_return")
    turnover_series = pd.Series(turnovers, index=index, name="turnover")

    nav = (1 + net_series).cumprod()
    total_return = nav.iloc[-1] - 1.0
    max_drawdown = (nav / nav.cummax() - 1.0).min()

    entry_first = period_info[0]["entry_idx"]
    exit_last = period_info[-1]["exit_idx"]
    total_days = exit_last - entry_first
    if total_days > 0:
        ann_return = (1 + total_return) ** (trading_days_per_year / total_days) - 1.0
    else:
        ann_return = np.nan

    holding_lengths = [info["exit_idx"] - info["entry_idx"] for info in period_info]
    avg_holding = np.mean(holding_lengths) if holding_lengths else np.nan
    periods_per_year = (
        trading_days_per_year / avg_holding
        if np.isfinite(avg_holding) and avg_holding > 0
        else np.nan
    )
    period_vol = net_series.std(ddof=1)
    if np.isfinite(period_vol) and period_vol > 0 and np.isfinite(periods_per_year):
        ann_vol = period_vol * np.sqrt(periods_per_year)
        sharpe = net_series.mean() / period_vol * np.sqrt(periods_per_year)
    else:
        ann_vol = np.nan
        sharpe = np.nan

    avg_turnover = turnover_series.dropna().mean() if turnover_series.notna().any() else np.nan
    avg_cost = 2 * (cost_bps / 10000.0) * avg_turnover if not np.isnan(avg_turnover) else np.nan

    stats = {
        "periods": len(net_series),
        "total_return": total_return,
        "ann_return": ann_return,
        "ann_vol": ann_vol,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "avg_turnover": avg_turnover,
        "avg_cost_drag": avg_cost,
    }
    return stats, net_series, gross_series, turnover_series, period_info
