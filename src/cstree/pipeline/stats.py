from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger("cstree")
_EXECUTION_LIQUIDITY_PROXY_PATTERN = re.compile(r"^(adv|medadv)\d+_amount$")


def _warn_if_purge_too_small(
    *,
    purge_days_cfg: object | None,
    purge_days: int,
    label_horizon_effective: int,
    label_shift_days: int,
) -> None:
    """Warn when user-specified purge window is shorter than label span."""
    if purge_days_cfg is None:
        return
    required = max(0, int(label_horizon_effective) + int(label_shift_days))
    actual = max(0, int(purge_days))
    if actual >= required:
        return
    logger.warning(
        "eval.purge_days=%s is smaller than label span (%s = horizon_effective %s + shift_days %s); "
        "this may cause label leakage.",
        actual,
        required,
        int(label_horizon_effective),
        int(label_shift_days),
    )


def _rqdata_fields_for_standard_columns(columns: set[str]) -> list[str]:
    raw_map = {
        "close": "close",
        "open": "open",
        "high": "high",
        "low": "low",
        "vol": "volume",
        "amount": "total_turnover",
        "tr_close": "close",
    }
    fields: list[str] = []
    for column in sorted(columns):
        normalized = str(column).strip()
        raw = raw_map.get(normalized)
        if raw is None and _EXECUTION_LIQUIDITY_PROXY_PATTERN.fullmatch(normalized):
            raw = "total_turnover"
        if raw and raw not in fields:
            fields.append(raw)
    return fields


def _ensure_execution_daily_fields(
    *,
    data_cfg: Mapping[str, Any],
    provider: str,
    required_columns: set[str],
) -> None:
    if provider != "rqdata" or not isinstance(data_cfg, dict):
        return
    required_fields = _rqdata_fields_for_standard_columns(required_columns)
    if not required_fields:
        return

    rq_cfg = data_cfg.get("rqdata")
    if rq_cfg is None:
        rq_cfg = {}
        data_cfg["rqdata"] = rq_cfg
    if not isinstance(rq_cfg, dict):
        return

    current_fields_raw = rq_cfg.get("fields")
    if isinstance(current_fields_raw, str) and current_fields_raw in {"all", "*"}:
        return
    if current_fields_raw is None:
        current_fields = ["close", "volume", "total_turnover"]
    elif isinstance(current_fields_raw, (list, tuple)):
        current_fields = [str(field).strip() for field in current_fields_raw if str(field).strip()]
    else:
        current_fields = [str(current_fields_raw).strip()]

    updated_fields = list(dict.fromkeys(current_fields + required_fields))
    if updated_fields != current_fields:
        rq_cfg["fields"] = updated_fields
        logger.info(
            "Expanded data.rqdata.fields for execution pricing columns: %s",
            updated_fields,
        )


def _normalize_window_months(value: object | None, default: list[int]) -> list[int]:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return [int(value)]
    if isinstance(value, (list, tuple, set)):
        items = []
        for entry in value:
            if entry is None:
                continue
            try:
                num = int(entry)
            except (TypeError, ValueError):
                continue
            if num > 0:
                items.append(num)
        return sorted(set(items))
    return default


def _estimate_obs_per_year(series: pd.Series) -> float:
    if series is None or series.empty:
        return np.nan
    if not isinstance(series.index, pd.DatetimeIndex):
        return np.nan
    start = series.index.min()
    end = series.index.max()
    if start is pd.NaT or end is pd.NaT:
        return np.nan
    days = float((end - start).days)
    if days <= 0:
        return np.nan
    return float(series.shape[0] / (days / 365.25))


def _latest_rolling_stats(frame: pd.DataFrame, columns: list[str]) -> dict[str, float] | None:
    if frame is None or frame.empty:
        return None
    valid = frame.dropna(subset=columns, how="any")
    if valid.empty:
        return None
    last = valid.iloc[-1]
    return {col: float(last[col]) for col in columns}


def _compute_rolling_ic(
    ic_series: pd.Series, window_months: list[int]
) -> tuple[dict[str, pd.DataFrame], float]:
    results: dict[str, pd.DataFrame] = {}
    if ic_series is None or ic_series.empty:
        return results, np.nan
    obs_per_year = _estimate_obs_per_year(ic_series)
    if not np.isfinite(obs_per_year) or obs_per_year <= 0:
        return results, np.nan
    for months in window_months:
        window_obs = int(round(obs_per_year * months / 12))
        if window_obs < 2:
            continue
        rolling = ic_series.rolling(window_obs, min_periods=window_obs)
        mean = rolling.mean()
        std = rolling.std(ddof=0)
        ir = mean / std
        frame = pd.DataFrame({"ic_mean": mean, "ic_std": std, "ic_ir": ir})
        results[f"{months}m"] = frame
    return results, float(obs_per_year)


def _compute_rolling_sharpe(
    returns: pd.Series, window_months: list[int], periods_per_year: float
) -> dict[str, pd.DataFrame]:
    results: dict[str, pd.DataFrame] = {}
    if returns is None or returns.empty:
        return results
    if not np.isfinite(periods_per_year) or periods_per_year <= 0:
        return results
    for months in window_months:
        window_obs = int(round(periods_per_year * months / 12))
        if window_obs < 2:
            continue
        rolling = returns.rolling(window_obs, min_periods=window_obs)
        mean = rolling.mean()
        std = rolling.std(ddof=1)
        sharpe = mean / std * np.sqrt(periods_per_year)
        frame = pd.DataFrame({"mean": mean, "std": std, "sharpe": sharpe})
        results[f"{months}m"] = frame
    return results


def _normalize_bucket_schemes(raw_schemes: object | None) -> list[dict]:
    schemes: list[dict] = []
    if raw_schemes is None:
        return schemes
    if isinstance(raw_schemes, dict):
        raw_items = raw_schemes.get("schemes") or []
    else:
        raw_items = raw_schemes
    if isinstance(raw_items, (str, int, float)):
        raw_items = [raw_items]
    if not isinstance(raw_items, (list, tuple)):
        return schemes
    for item in raw_items:
        if isinstance(item, str):
            col = item.strip()
            if not col:
                continue
            schemes.append({"name": col, "column": col, "type": "category", "n_bins": 0})
            continue
        if not isinstance(item, dict):
            continue
        col = item.get("column") or item.get("col")
        if not col:
            continue
        name = item.get("name") or col
        bucket_type = str(item.get("type", "category")).strip().lower()
        n_bins = item.get("n_bins", item.get("bins", 3))
        try:
            n_bins = int(n_bins) if n_bins is not None else 0
        except (TypeError, ValueError):
            n_bins = 0
        schemes.append(
            {
                "name": str(name),
                "column": str(col),
                "type": bucket_type,
                "n_bins": n_bins,
            }
        )
    return schemes
