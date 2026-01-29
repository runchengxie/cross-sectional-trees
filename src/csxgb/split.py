from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from xgboost import XGBRegressor

from .metrics import daily_ic_series


def time_series_cv_ic(
    data: pd.DataFrame,
    features: list[str],
    target_col: str,
    n_splits: int,
    embargo_days: int,
    purge_days: int,
    model_params: dict,
    signal_direction: float,
):
    dates = np.array(sorted(data["trade_date"].unique()))
    tscv = TimeSeriesSplit(n_splits=n_splits)
    scores = []
    gap = max(int(embargo_days), int(purge_days))
    for train_idx, val_idx in tscv.split(dates):
        if gap > 0:
            cutoff = val_idx[0] - gap
            train_idx = train_idx[train_idx < cutoff]
            if len(train_idx) == 0:
                continue
        tr_dates = dates[train_idx]
        va_dates = dates[val_idx]
        tr_df = data[data["trade_date"].isin(tr_dates)]
        va_df = data[data["trade_date"].isin(va_dates)].copy()

        model = XGBRegressor(**model_params)
        model.fit(tr_df[features], tr_df[target_col])
        va_df["pred"] = model.predict(va_df[features])
        if signal_direction != 1.0:
            va_df["pred"] = va_df["pred"] * signal_direction

        ic_values = daily_ic_series(va_df, target_col, "pred")
        scores.append(float(ic_values.mean()) if not ic_values.empty else np.nan)
    return scores
