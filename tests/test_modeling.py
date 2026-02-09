import numpy as np
import pandas as pd
import pytest

from csml.modeling import (
    build_model,
    feature_importance_frame,
    fit_model,
    resolve_model_spec,
)


def test_resolve_model_spec_defaults_to_xgb():
    model_type, params = resolve_model_spec(None)
    assert model_type == "xgb_regressor"
    assert params["objective"] == "reg:squarederror"


def test_resolve_model_spec_accepts_alias():
    model_type, params = resolve_model_spec({"type": "ridge_regressor", "params": {"alpha": 2.0}})
    assert model_type == "ridge"
    assert params == {"alpha": 2.0}


@pytest.mark.parametrize(
    ("model_type", "params", "expected_class"),
    [
        ("xgb_regressor", {"n_estimators": 1, "max_depth": 1, "learning_rate": 0.1}, "XGBRegressor"),
        (
            "xgb_ranker",
            {"n_estimators": 1, "max_depth": 1, "learning_rate": 0.1, "objective": "rank:pairwise"},
            "XGBRanker",
        ),
        ("ridge", {"alpha": 1.0}, "Ridge"),
        ("elasticnet", {"alpha": 0.1, "l1_ratio": 0.5}, "ElasticNet"),
    ],
)
def test_build_model_supported_types(model_type, params, expected_class):
    model = build_model(model_type, params)
    assert model.__class__.__name__ == expected_class


def test_feature_importance_frame_for_linear_model_uses_abs_coef():
    X = np.array(
        [
            [1.0, 0.0],
            [2.0, 0.0],
            [0.0, 1.0],
            [0.0, 2.0],
        ]
    )
    y = np.array([1.0, 2.0, -1.0, -2.0])
    model = build_model("ridge", {"alpha": 0.1})
    model.fit(X, y)

    importance_df, source = feature_importance_frame(model, ["f1", "f2"])
    assert source == "coef_abs"
    assert set(importance_df["feature"]) == {"f1", "f2"}
    assert importance_df["importance"].ge(0).all()


def test_resolve_model_spec_rejects_unknown_type():
    with pytest.raises(ValueError, match="Unsupported model.type"):
        resolve_model_spec({"type": "random_forest", "params": {}})


def test_fit_model_supports_ranker_groups():
    frame = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(
                ["2020-01-01", "2020-01-01", "2020-01-02", "2020-01-02"]
            ),
            "ts_code": ["A", "B", "A", "B"],
            "f1": [0.1, 0.9, 0.2, 0.8],
            "target": [0.0, 1.0, 0.0, 1.0],
        }
    )

    model = build_model(
        "xgb_ranker",
        {"n_estimators": 2, "max_depth": 1, "learning_rate": 0.1, "objective": "rank:pairwise"},
    )
    fit_model(model, "xgb_ranker", frame, features=["f1"], target_col="target")
    preds = model.predict(frame[["f1"]])
    assert preds.shape[0] == len(frame)
