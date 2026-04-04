from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any, Sequence

import numpy as np
import pandas as pd


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def is_missing_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (float, np.floating)) and math.isnan(float(value)):
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        return value.strip().lower() in {"", "none", "nan"}
    return False


def pick_last_non_missing(values: Sequence[Any]) -> Any:
    for value in reversed(list(values)):
        if not is_missing_value(value):
            return value
    return None


def pick_round_lot(values: Sequence[Any], *, logger) -> float:
    raw = pd.to_numeric(pd.Series(list(values)), errors="coerce")
    numeric = raw.dropna()
    if numeric.empty:
        return float("nan")
    unique_values = sorted({float(v) for v in numeric.tolist()})
    if len(unique_values) > 1:
        logger.warning(
            "Multiple round_lot values found %s; using mode then last non-missing.",
            unique_values,
        )

    counts = numeric.value_counts()
    if counts.empty:
        return float("nan")

    top_count = int(counts.max())
    mode_values = [float(val) for val, count in counts.items() if int(count) == top_count]
    if len(mode_values) == 1:
        return mode_values[0]

    for value in reversed(raw.tolist()):
        if pd.isna(value):
            continue
        value_float = float(value)
        if value_float in mode_values:
            return value_float
    return mode_values[0]


def coerce_scalar(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        if value.empty:
            return None
        value = value.iloc[-1]
    if isinstance(value, pd.Series):
        return pick_last_non_missing(value.tolist())
    return value


def get_attr_or_key(record: Any, key: str) -> Any:
    if isinstance(record, dict):
        return record.get(key)
    return getattr(record, key, None)


def to_timestamp(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce")
    if isinstance(ts, pd.Timestamp):
        return ts
    return pd.NaT


def to_date(value: Any) -> date:
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return pd.to_datetime(value).date()
