import numpy as np
import pandas as pd

from csml.transform import apply_cross_sectional_transform


def test_cross_sectional_zscore_by_date():
    df = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(
                ["2020-01-01"] * 3 + ["2020-01-02"] * 3
            ),
            "ts_code": ["A", "B", "C"] * 2,
            "f1": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            "f2": [2.0, 3.0, 4.0, 1.0, 0.0, -1.0],
        }
    )
    out = apply_cross_sectional_transform(df, ["f1", "f2"], method="zscore", winsorize_pct=None)
    for date in out["trade_date"].unique():
        subset = out[out["trade_date"] == date]
        assert np.isclose(subset["f1"].mean(), 0.0, atol=1e-8)
        assert np.isclose(subset["f2"].mean(), 0.0, atol=1e-8)
