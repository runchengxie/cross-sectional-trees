from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def apply_cross_sectional_transform(
    data: pd.DataFrame,
    features: list[str],
    method: str,
    winsorize_pct: Optional[float],
) -> pd.DataFrame:
    if method == "none":
        return data

    def _transform(values: pd.DataFrame) -> pd.DataFrame:
        if winsorize_pct:
            lower = values.quantile(winsorize_pct)
            upper = values.quantile(1 - winsorize_pct)
            values = values.clip(lower=lower, upper=upper, axis=1)
        if method == "zscore":
            mean = values.mean()
            std = values.std(ddof=0).replace(0, np.nan)
            values = (values - mean) / std
            values = values.fillna(0.0)
        elif method == "rank":
            values = values.rank(method="average", pct=True) - 0.5
        return values

    transformed = data.groupby("trade_date", group_keys=False, sort=False)[features].apply(_transform)
    out = data.copy()
    out[features] = transformed.reset_index(level=0, drop=True)
    return out
