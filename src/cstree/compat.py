from __future__ import annotations

import numpy as np


def ensure_numpy_nan_alias() -> None:
    """Provide the legacy ``np.NaN`` alias expected by pandas_ta.

    Keep this centralized until the pandas_ta/NumPy combination used by the
    project no longer requires the alias. Do not add new scattered aliases.
    """
    if not hasattr(np, "NaN"):
        np.NaN = np.nan
