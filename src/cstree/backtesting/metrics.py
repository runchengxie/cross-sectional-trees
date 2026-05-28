from __future__ import annotations

import numpy as np
import pandas as pd


def _drawdown_timing(nav: pd.Series) -> dict[str, float]:
    if nav is None:
        return {
            "drawdown_duration": np.nan,
            "recovery_time": np.nan,
            "drawdown_duration_days": np.nan,
            "recovery_time_days": np.nan,
        }
    nav = nav.dropna()
    if nav.empty:
        return {
            "drawdown_duration": np.nan,
            "recovery_time": np.nan,
            "drawdown_duration_days": np.nan,
            "recovery_time_days": np.nan,
        }

    running_max = nav.cummax()
    drawdown = nav / running_max - 1.0
    trough_date = drawdown.idxmin()
    try:
        trough_pos = nav.index.get_loc(trough_date)
    except KeyError:
        trough_pos = int(drawdown.values.argmin())
        trough_date = nav.index[trough_pos]

    peak_value = float(running_max.loc[trough_date])
    pre_peak = nav.loc[:trough_date]
    peak_candidates = pre_peak[pre_peak == peak_value]
    if peak_candidates.empty:
        peak_date = nav.index[0]
        peak_pos = 0
    else:
        peak_date = peak_candidates.index[-1]
        peak_pos = nav.index.get_loc(peak_date)

    drawdown_duration = float(trough_pos - peak_pos)

    post_nav = nav.loc[trough_date:]
    recovery_candidates = post_nav[post_nav >= peak_value]
    if recovery_candidates.empty:
        recovery_time = np.nan
        recovery_days = np.nan
    else:
        recovery_date = recovery_candidates.index[0]
        recovery_pos = nav.index.get_loc(recovery_date)
        recovery_time = float(recovery_pos - trough_pos)
        if isinstance(nav.index, pd.DatetimeIndex):
            recovery_days = float((recovery_date - trough_date).days)
        else:
            recovery_days = np.nan

    if isinstance(nav.index, pd.DatetimeIndex):
        drawdown_days = float((trough_date - peak_date).days)
    else:
        drawdown_days = np.nan

    return {
        "drawdown_duration": drawdown_duration,
        "recovery_time": recovery_time,
        "drawdown_duration_days": drawdown_days,
        "recovery_time_days": recovery_days,
    }


def summarize_period_returns(
    returns: pd.Series,
    period_info: list[dict],
    trading_days_per_year: int,
) -> dict:
    if returns is None or returns.empty:
        return {
            "periods": 0,
            "total_return": np.nan,
            "ann_return": np.nan,
            "ann_vol": np.nan,
            "sharpe": np.nan,
            "max_drawdown": np.nan,
            "avg_holding": np.nan,
            "periods_per_year": np.nan,
            "sortino": np.nan,
            "calmar": np.nan,
            "drawdown_duration": np.nan,
            "recovery_time": np.nan,
            "drawdown_duration_days": np.nan,
            "recovery_time_days": np.nan,
            "skew": np.nan,
            "kurtosis": np.nan,
            "var_95": np.nan,
            "cvar_95": np.nan,
            "avg_exit_lag_days": np.nan,
            "max_exit_lag_days": np.nan,
            "periods_with_delayed_exit": 0,
            "delayed_exit_ratio": np.nan,
        }

    nav = (1 + returns).cumprod()
    total_return = nav.iloc[-1] - 1.0
    max_drawdown = (nav / nav.cummax() - 1.0).min()

    total_days = np.nan
    if period_info:
        entry_first = period_info[0]["entry_idx"]
        exit_last = period_info[-1]["exit_idx"]
        total_days = exit_last - entry_first
    if np.isfinite(total_days) and total_days > 0:
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
    period_vol = returns.std(ddof=1)
    if np.isfinite(period_vol) and period_vol > 0 and np.isfinite(periods_per_year):
        ann_vol = period_vol * np.sqrt(periods_per_year)
        sharpe = returns.mean() / period_vol * np.sqrt(periods_per_year)
    else:
        ann_vol = np.nan
        sharpe = np.nan

    downside = np.minimum(returns.to_numpy(), 0.0)
    downside_std = float(np.sqrt(np.mean(downside**2))) if len(downside) > 0 else np.nan
    if np.isfinite(downside_std) and downside_std > 0 and np.isfinite(periods_per_year):
        sortino = float(returns.mean() / downside_std * np.sqrt(periods_per_year))
    else:
        sortino = np.nan

    if np.isfinite(max_drawdown) and max_drawdown < 0 and np.isfinite(ann_return):
        calmar = float(ann_return / abs(max_drawdown))
    else:
        calmar = np.nan

    timing = _drawdown_timing(nav)

    exit_lags: list[float] = []
    for info in period_info:
        lag_raw = info.get("exit_delay_steps")
        if lag_raw is None:
            planned_idx = info.get("planned_exit_idx")
            exit_idx = info.get("exit_idx")
            if planned_idx is not None and exit_idx is not None:
                lag_raw = int(exit_idx) - int(planned_idx)
        if lag_raw is None:
            continue
        try:
            lag = float(lag_raw)
        except (TypeError, ValueError):
            continue
        if np.isfinite(lag):
            exit_lags.append(max(0.0, lag))

    if exit_lags:
        avg_exit_lag = float(np.mean(exit_lags))
        max_exit_lag = float(np.max(exit_lags))
        delayed_periods = int(sum(lag > 0 for lag in exit_lags))
        delayed_ratio = delayed_periods / float(len(exit_lags))
    else:
        avg_exit_lag = np.nan
        max_exit_lag = np.nan
        delayed_periods = 0
        delayed_ratio = np.nan

    skew = float(returns.skew()) if returns.shape[0] > 2 else np.nan
    kurtosis = float(returns.kurtosis()) if returns.shape[0] > 3 else np.nan
    if returns.shape[0] > 0:
        var_95 = float(np.nanpercentile(returns, 5))
        tail = returns[returns <= var_95]
        cvar_95 = float(tail.mean()) if not tail.empty else np.nan
    else:
        var_95 = np.nan
        cvar_95 = np.nan

    return {
        "periods": len(returns),
        "total_return": total_return,
        "ann_return": ann_return,
        "ann_vol": ann_vol,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "avg_holding": avg_holding,
        "periods_per_year": periods_per_year,
        "sortino": sortino,
        "calmar": calmar,
        "drawdown_duration": timing["drawdown_duration"],
        "recovery_time": timing["recovery_time"],
        "drawdown_duration_days": timing["drawdown_duration_days"],
        "recovery_time_days": timing["recovery_time_days"],
        "skew": skew,
        "kurtosis": kurtosis,
        "var_95": var_95,
        "cvar_95": cvar_95,
        "avg_exit_lag_days": avg_exit_lag,
        "max_exit_lag_days": max_exit_lag,
        "periods_with_delayed_exit": delayed_periods,
        "delayed_exit_ratio": delayed_ratio,
    }
