from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNet, Ridge
from xgboost import XGBRanker, XGBRegressor

SUPPORTED_MODEL_TYPES = ("xgb_regressor", "xgb_ranker", "ridge", "elasticnet")

_MODEL_ALIASES: dict[str, str] = {
    "xgb": "xgb_regressor",
    "xgboost": "xgb_regressor",
    "xgb_regressor": "xgb_regressor",
    "xgbregressor": "xgb_regressor",
    "xgb_ranker": "xgb_ranker",
    "xgb_rank": "xgb_ranker",
    "xgboost_ranker": "xgb_ranker",
    "ranker": "xgb_ranker",
    "ridge": "ridge",
    "ridge_regressor": "ridge",
    "ridge_regression": "ridge",
    "elasticnet": "elasticnet",
    "elastic_net": "elasticnet",
    "elasticnet_regressor": "elasticnet",
    "elasticnet_regression": "elasticnet",
}

_DEFAULT_MODEL_PARAMS: dict[str, dict[str, Any]] = {
    "xgb_regressor": {
        "n_estimators": 300,
        "learning_rate": 0.05,
        "max_depth": 3,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_alpha": 0.0,
        "reg_lambda": 1.0,
        "objective": "reg:squarederror",
        "random_state": 42,
    },
    "xgb_ranker": {
        "n_estimators": 300,
        "learning_rate": 0.05,
        "max_depth": 3,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_alpha": 0.0,
        "reg_lambda": 1.0,
        "objective": "rank:pairwise",
        "random_state": 42,
    },
    "ridge": {
        "alpha": 1.0,
        "fit_intercept": True,
        "random_state": 42,
    },
    "elasticnet": {
        "alpha": 0.1,
        "l1_ratio": 0.5,
        "fit_intercept": True,
        "max_iter": 5000,
        "random_state": 42,
    },
}


def normalize_model_type(value: object | None) -> str:
    text = str(value or "xgb_regressor").strip().lower().replace("-", "_")
    model_type = _MODEL_ALIASES.get(text)
    if model_type:
        return model_type
    supported = ", ".join(SUPPORTED_MODEL_TYPES)
    raise ValueError(f"Unsupported model.type: {value}. Supported values: {supported}.")


def resolve_model_spec(model_cfg: Mapping[str, Any] | None) -> tuple[str, dict[str, Any]]:
    if model_cfg is None:
        model_cfg = {}
    if not isinstance(model_cfg, Mapping):
        raise ValueError("model must be a mapping with keys: type, params.")
    model_type = normalize_model_type(model_cfg.get("type"))
    params_raw = model_cfg.get("params") or {}
    if not isinstance(params_raw, Mapping):
        raise ValueError("model.params must be a mapping.")
    model_params = dict(params_raw)
    if not model_params:
        model_params = dict(_DEFAULT_MODEL_PARAMS[model_type])
    return model_type, model_params


def build_model(model_type: str, model_params: Mapping[str, Any]) -> Any:
    params = dict(model_params)
    model_key = normalize_model_type(model_type)
    if model_key == "xgb_regressor":
        return XGBRegressor(**params)
    if model_key == "xgb_ranker":
        return XGBRanker(**params)
    if model_key == "ridge":
        return Ridge(**params)
    if model_key == "elasticnet":
        return ElasticNet(**params)
    supported = ", ".join(SUPPORTED_MODEL_TYPES)
    raise ValueError(f"Unsupported model.type: {model_type}. Supported values: {supported}.")


def build_model_from_config(model_cfg: Mapping[str, Any] | None) -> tuple[Any, str, dict[str, Any]]:
    model_type, model_params = resolve_model_spec(model_cfg)
    return build_model(model_type, model_params), model_type, model_params


def fit_model(
    model: Any,
    model_type: str,
    train_data: pd.DataFrame,
    *,
    features: Sequence[str],
    target_col: str,
    sample_weight: Sequence[float] | np.ndarray | None = None,
    date_col: str = "trade_date",
) -> Any:
    model_key = normalize_model_type(model_type)
    if model_key == "xgb_ranker":
        train_sorted = train_data.sort_values(date_col)
        groups = train_sorted.groupby(date_col, sort=False)[date_col].size().tolist()
        if not groups:
            raise ValueError("xgb_ranker requires non-empty grouped training data.")
        x_train = train_sorted[list(features)]
        y_train = train_sorted[target_col]
        if sample_weight is not None:
            weight_series = pd.Series(np.asarray(sample_weight, dtype=float), index=train_data.index)
            sorted_weight = weight_series.loc[train_sorted.index].to_numpy()
            model.fit(x_train, y_train, group=groups, sample_weight=sorted_weight)
        else:
            model.fit(x_train, y_train, group=groups)
        return model

    x_train = train_data[list(features)]
    y_train = train_data[target_col]
    if sample_weight is not None:
        model.fit(x_train, y_train, sample_weight=np.asarray(sample_weight, dtype=float))
    else:
        model.fit(x_train, y_train)
    return model


def feature_importance_frame(
    model: Any,
    features: Sequence[str],
) -> tuple[pd.DataFrame, str]:
    n_features = len(features)
    source = "none"
    if hasattr(model, "feature_importances_"):
        raw = np.asarray(getattr(model, "feature_importances_"), dtype=float).reshape(-1)
        source = "feature_importances"
    elif hasattr(model, "coef_"):
        coef = np.asarray(getattr(model, "coef_"), dtype=float)
        if coef.ndim > 1:
            coef = np.mean(np.abs(coef), axis=0)
        else:
            coef = np.abs(coef)
        raw = np.asarray(coef, dtype=float).reshape(-1)
        source = "coef_abs"
    else:
        raw = np.zeros(n_features, dtype=float)

    if raw.size < n_features:
        raw = np.pad(raw, (0, n_features - raw.size), constant_values=np.nan)
    elif raw.size > n_features:
        raw = raw[:n_features]

    frame = pd.DataFrame(
        {
            "feature": list(features),
            "importance": raw,
        }
    ).sort_values("importance", ascending=False)
    return frame, source
