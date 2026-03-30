import numpy as np
import pandas as pd

from csml.transform import (
    apply_cross_sectional_series_transform,
    apply_cross_sectional_transform,
    apply_score_postprocess,
    neutralize_cross_sectional_series,
)


def test_cross_sectional_zscore_by_date():
    df = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(
                ["2020-01-01"] * 3 + ["2020-01-02"] * 3
            ),
            "symbol": ["A", "B", "C"] * 2,
            "f1": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            "f2": [2.0, 3.0, 4.0, 1.0, 0.0, -1.0],
        }
    )
    out = apply_cross_sectional_transform(df, ["f1", "f2"], method="zscore", winsorize_pct=None)
    for date in out["trade_date"].unique():
        subset = out[out["trade_date"] == date]
        assert np.isclose(subset["f1"].mean(), 0.0, atol=1e-8)
        assert np.isclose(subset["f2"].mean(), 0.0, atol=1e-8)


def test_cross_sectional_series_transform_preserves_missing_values():
    df = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(
                ["2020-01-01", "2020-01-01", "2020-01-02", "2020-01-02"]
            ),
            "target": [1.0, 2.0, np.nan, 4.0],
        }
    )

    out = apply_cross_sectional_series_transform(df, "target", method="zscore")

    assert np.isclose(float(out.iloc[0]), -1.0)
    assert np.isclose(float(out.iloc[1]), 1.0)
    assert np.isnan(out.iloc[2])
    assert np.isclose(float(out.iloc[3]), 0.0)


def test_neutralize_cross_sectional_series_removes_linear_size_component():
    df = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2020-01-01"] * 4 + ["2020-01-02"] * 4),
            "pred": [1.0, 3.0, 5.0, 7.0, 2.0, 4.0, 6.0, 8.0],
            "log_mcap": [1.0, 2.0, 3.0, 4.0, 1.0, 2.0, 3.0, 4.0],
        }
    )

    neutralized = neutralize_cross_sectional_series(
        df,
        "pred",
        ["log_mcap"],
        strength=1.0,
        min_obs=4,
    )
    out = df.assign(pred_adj=neutralized)

    for _, group in out.groupby("trade_date", sort=False):
        assert float(group["pred_adj"].std(ddof=0)) < 1e-8


def test_apply_score_postprocess_strength_zero_returns_original_series():
    df = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2020-01-01"] * 3),
            "pred": [1.0, 2.0, 3.0],
            "log_mcap": [10.0, 11.0, 12.0],
        }
    )

    out = apply_score_postprocess(
        df,
        "pred",
        method="neutralize",
        columns=["log_mcap"],
        strength=0.0,
        min_obs=3,
    )

    assert out.tolist() == df["pred"].tolist()
