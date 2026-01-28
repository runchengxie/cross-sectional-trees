import pandas as pd

from csxgb.split import time_series_cv_ic


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
