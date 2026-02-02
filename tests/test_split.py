import pandas as pd

from csxgb.split import build_sample_weight, time_series_cv_ic


def test_time_series_cv_gap_skips_all():
    dates = pd.date_range("2020-01-01", periods=6, freq="D")
    df = pd.DataFrame(
        {
            "trade_date": dates.repeat(2),
            "ts_code": ["A", "B"] * len(dates),
            "f1": [1.0] * (len(dates) * 2),
            "target": [0.1] * (len(dates) * 2),
        }
    )
    scores = time_series_cv_ic(
        df,
        features=["f1"],
        target_col="target",
        n_splits=3,
        embargo_days=10,
        purge_days=10,
        model_params={"n_estimators": 1, "max_depth": 1, "learning_rate": 0.1},
        signal_direction=1.0,
    )
    assert scores == []


def test_build_sample_weight_date_equal():
    dates = pd.to_datetime(["2020-01-01", "2020-01-01", "2020-01-02"])
    df = pd.DataFrame(
        {
            "trade_date": dates,
            "ts_code": ["A", "B", "A"],
            "f1": [1.0, 2.0, 3.0],
            "target": [0.1, 0.2, 0.3],
        }
    )
    weights = build_sample_weight(df, "date_equal")
    assert weights is not None
    df = df.assign(weight=weights)
    sums = df.groupby("trade_date")["weight"].sum().values
    assert all(abs(value - 1.0) < 1e-12 for value in sums)
