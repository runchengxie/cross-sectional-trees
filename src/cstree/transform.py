from __future__ import annotations

from collections.abc import Sequence
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

    out = data.copy()
    values = out[features].copy()
    date_index = out["trade_date"]

    if winsorize_pct:
        grouped = values.groupby(date_index, sort=False)
        lower = grouped.transform(lambda s: s.quantile(winsorize_pct))
        upper = grouped.transform(lambda s: s.quantile(1 - winsorize_pct))
        values = values.clip(lower=lower, upper=upper, axis=0)

    if method == "zscore":
        grouped = values.groupby(date_index, sort=False)
        mean = grouped.transform("mean")
        std = grouped.transform(lambda s: s.std(ddof=0)).replace(0, np.nan)
        values = (values - mean) / std
        values = values.fillna(0.0)
    elif method == "rank":
        values = values.groupby(date_index, sort=False).rank(method="average", pct=True) - 0.5

    out[features] = values
    return out


def apply_cross_sectional_series_transform(
    data: pd.DataFrame,
    column: str,
    method: str,
    winsorize_pct: Optional[float] = None,
) -> pd.Series:
    if method == "none":
        return data[column].copy()

    transformed = apply_cross_sectional_transform(
        data[["trade_date", column]].copy(),
        [column],
        method,
        winsorize_pct,
    )
    result = transformed[column]
    result[data[column].isna()] = np.nan
    return result


def neutralize_cross_sectional_series(
    data: pd.DataFrame,
    column: str,
    controls: Sequence[str],
    *,
    strength: float = 1.0,
    min_obs: Optional[int] = None,
) -> pd.Series:
    control_cols = [str(col).strip() for col in controls if str(col).strip()]
    if not control_cols:
        return data[column].copy()
    if strength < 0:
        raise ValueError("strength must be >= 0.")
    if strength == 0:
        return data[column].copy()

    out = data[column].copy()
    required_obs = max(
        int(min_obs) if min_obs is not None else 0,
        len(control_cols) + 1,
    )
    if required_obs <= 0:
        required_obs = len(control_cols) + 1

    for _, group in data.groupby("trade_date", sort=False):
        if group.empty:
            continue
        valid = group[column].notna()
        for control_col in control_cols:
            valid &= group[control_col].notna()
        if int(valid.sum()) < required_obs:
            continue

        group_valid = group.loc[valid, [column, *control_cols]].copy()
        y = pd.to_numeric(group_valid[column], errors="coerce").to_numpy(dtype=float)
        x = (
            group_valid[control_cols]
            .apply(pd.to_numeric, errors="coerce")
            .to_numpy(dtype=float)
        )
        if y.size < required_obs or x.ndim != 2 or x.shape[0] != y.size:
            continue

        design = np.column_stack([np.ones(y.size, dtype=float), x])
        coeffs, *_ = np.linalg.lstsq(design, y, rcond=None)
        fitted_exposure = x @ coeffs[1:]
        out.loc[group_valid.index] = y - strength * fitted_exposure
    return out


def apply_score_postprocess(
    data: pd.DataFrame,
    column: str,
    *,
    method: str,
    columns: Sequence[str],
    strength: float = 1.0,
    min_obs: Optional[int] = None,
) -> pd.Series:
    method_text = str(method or "none").strip().lower()
    if method_text == "none":
        return data[column].copy()
    missing_cols = [col for col in columns if col not in data.columns]
    if missing_cols:
        missing_text = ", ".join(sorted(set(missing_cols)))
        raise ValueError(f"Score postprocess columns not found: {missing_text}")
    if method_text == "neutralize":
        return neutralize_cross_sectional_series(
            data,
            column,
            columns,
            strength=strength,
            min_obs=min_obs,
        )
    raise ValueError(f"Unsupported score postprocess method: {method}")
