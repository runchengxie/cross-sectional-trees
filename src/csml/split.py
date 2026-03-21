from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit

from .metrics import daily_ic_series
from .modeling import build_model, fit_model, resolve_model_spec


def build_sample_weight(
    data: pd.DataFrame,
    mode: str | None,
    *,
    date_col: str = "trade_date",
    params: Mapping[str, object] | None = None,
) -> np.ndarray | None:
    if mode is None:
        return None
    mode_text = str(mode).strip().lower()
    if mode_text in {"", "none", "null"}:
        return None
    if mode_text in {"date_equal", "date"}:
        counts = data.groupby(date_col, sort=False)[date_col].transform("count")
        return (1.0 / counts).to_numpy()
    if mode_text in {"time_decay", "exp_decay", "exp"}:
        if params is not None and not isinstance(params, Mapping):
            raise ValueError("sample_weight_params must be a mapping.")
        params_map = dict(params or {})
        halflife_raw = params_map.get("halflife", params_map.get("half_life"))
        decay_rate_raw = params_map.get("decay_rate", params_map.get("rate"))
        min_weight_raw = params_map.get("min_weight", 0.0)
        try:
            min_weight = float(min_weight_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("sample_weight_params.min_weight must be a number.") from exc
        if min_weight < 0:
            raise ValueError("sample_weight_params.min_weight must be >= 0.")

        if halflife_raw is not None:
            try:
                halflife = float(halflife_raw)
            except (TypeError, ValueError) as exc:
                raise ValueError("sample_weight_params.halflife must be a number.") from exc
            if not np.isfinite(halflife) or halflife <= 0:
                raise ValueError("sample_weight_params.halflife must be > 0.")

            def _decay(age: np.ndarray) -> np.ndarray:
                return np.power(0.5, age / halflife)

        elif decay_rate_raw is not None:
            try:
                decay_rate = float(decay_rate_raw)
            except (TypeError, ValueError) as exc:
                raise ValueError("sample_weight_params.decay_rate must be a number.") from exc
            if not np.isfinite(decay_rate) or decay_rate <= 0 or decay_rate > 1:
                raise ValueError("sample_weight_params.decay_rate must be in (0, 1].")

            def _decay(age: np.ndarray) -> np.ndarray:
                return np.power(decay_rate, age)

        else:
            raise ValueError(
                "exp_decay/time_decay sample_weight_mode requires either "
                "sample_weight_params.halflife or sample_weight_params.decay_rate."
            )

        date_values = pd.to_datetime(data[date_col], errors="coerce")
        if date_values.isna().any():
            raise ValueError(f"sample weights require valid dates in column: {date_col}")
        unique_dates = pd.Index(date_values.unique()).sort_values()
        if unique_dates.empty:
            return None
        unique_ages = float(len(unique_dates) - 1) - np.arange(len(unique_dates), dtype=float)
        unique_date_weights = _decay(unique_ages)
        if min_weight > 0:
            unique_date_weights = np.maximum(unique_date_weights, min_weight)
        mean_weight = float(np.nanmean(unique_date_weights))
        if np.isfinite(mean_weight) and mean_weight > 0:
            unique_date_weights = unique_date_weights / mean_weight
        date_weight_map = pd.Series(unique_date_weights, index=unique_dates, dtype=float)
        date_weights = date_values.map(date_weight_map).to_numpy(dtype=float)
        counts = data.groupby(date_col, sort=False)[date_col].transform("count").to_numpy(dtype=float)
        return date_weights / counts
    raise ValueError(f"Unsupported sample_weight_mode: {mode}")


def select_train_window_dates(
    dates: np.ndarray | list[pd.Timestamp],
    *,
    mode: str | None = None,
    size: int | None = None,
    unit: str = "dates",
) -> np.ndarray:
    mode_text = str(mode or "full").strip().lower()
    if mode_text in {"", "full", "all", "expanding"}:
        return np.asarray(pd.to_datetime(dates).unique(), dtype="datetime64[ns]")
    if mode_text not in {"rolling", "recent"}:
        raise ValueError("train_window.mode must be one of: full, rolling.")
    if size is None:
        raise ValueError("train_window.size is required when train_window.mode=rolling.")
    try:
        size_value = int(size)
    except (TypeError, ValueError) as exc:
        raise ValueError("train_window.size must be a positive integer.") from exc
    if size_value <= 0:
        raise ValueError("train_window.size must be a positive integer.")

    date_index = pd.Index(pd.to_datetime(dates).unique()).sort_values()
    if date_index.empty:
        return np.array([], dtype="datetime64[ns]")

    unit_text = str(unit or "dates").strip().lower()
    if unit_text == "dates":
        return np.asarray(date_index[-size_value:], dtype="datetime64[ns]")
    if unit_text == "years":
        end_date = pd.Timestamp(date_index[-1])
        cutoff = end_date - pd.DateOffset(years=size_value)
        selected = date_index[date_index >= cutoff]
        if selected.empty:
            selected = date_index[-1:]
        return np.asarray(selected, dtype="datetime64[ns]")
    raise ValueError("train_window.unit must be one of: dates, years.")


def time_series_cv_ic(
    data: pd.DataFrame,
    features: list[str],
    target_col: str,
    n_splits: int,
    embargo_days: int,
    purge_days: int,
    model_cfg: Mapping[str, object] | None = None,
    signal_direction: float = 1.0,
    sample_weight_mode: str | None = None,
    sample_weight_params: Mapping[str, object] | None = None,
    date_col: str = "trade_date",
    *,
    model_params: Mapping[str, object] | None = None,
    train_window_mode: str | None = None,
    train_window_size: int | None = None,
    train_window_unit: str = "dates",
):
    if model_cfg is not None and model_params is not None:
        raise ValueError("Provide either model_cfg or model_params, not both.")
    if model_params is not None:
        resolved_type, resolved_params = resolve_model_spec(
            {"type": "xgb_regressor", "params": dict(model_params)}
        )
    elif model_cfg is None:
        resolved_type, resolved_params = resolve_model_spec({})
    elif "type" in model_cfg or "params" in model_cfg:
        resolved_type, resolved_params = resolve_model_spec(model_cfg)
    else:
        resolved_type, resolved_params = resolve_model_spec(
            {"type": "xgb_regressor", "params": dict(model_cfg)}
        )

    sorted_data = data.sort_values(date_col, kind="mergesort").reset_index(drop=True)
    date_values = sorted_data[date_col].to_numpy()
    if date_values.size == 0:
        return []

    dates, date_start_rows = np.unique(date_values, return_index=True)
    date_end_rows = np.empty_like(date_start_rows)
    if len(date_start_rows) > 1:
        date_end_rows[:-1] = date_start_rows[1:]
    date_end_rows[-1] = len(sorted_data)

    tscv = TimeSeriesSplit(n_splits=n_splits)
    scores = []
    gap = max(int(embargo_days), int(purge_days))
    for train_idx, val_idx in tscv.split(dates):
        if gap > 0:
            cutoff = val_idx[0] - gap
            train_idx = train_idx[train_idx < cutoff]
            if len(train_idx) == 0:
                continue
        train_dates = select_train_window_dates(
            dates[train_idx],
            mode=train_window_mode,
            size=train_window_size,
            unit=train_window_unit,
        )
        if len(train_dates) == 0:
            continue
        train_start_date = pd.to_datetime(train_dates[0])
        train_idx = train_idx[pd.to_datetime(dates[train_idx]) >= train_start_date]
        if len(train_idx) == 0:
            continue

        tr_start = date_start_rows[train_idx[0]]
        tr_end = date_end_rows[train_idx[-1]]
        va_start = date_start_rows[val_idx[0]]
        va_end = date_end_rows[val_idx[-1]]
        tr_df = sorted_data.iloc[tr_start:tr_end]
        va_df = sorted_data.iloc[va_start:va_end].copy()

        model = build_model(resolved_type, resolved_params)
        sample_weight = build_sample_weight(
            tr_df,
            sample_weight_mode,
            date_col=date_col,
            params=sample_weight_params,
        )
        fit_model(
            model,
            resolved_type,
            tr_df,
            features=features,
            target_col=target_col,
            sample_weight=sample_weight,
            date_col=date_col,
        )
        va_df["pred"] = model.predict(va_df[features])
        if signal_direction != 1.0:
            va_df["pred"] = va_df["pred"] * signal_direction

        if date_col == "trade_date":
            ic_input = va_df
        else:
            ic_input = va_df.rename(columns={date_col: "trade_date"})
        ic_values = daily_ic_series(ic_input, target_col, "pred")
        scores.append(float(ic_values.mean()) if not ic_values.empty else np.nan)
    return scores
