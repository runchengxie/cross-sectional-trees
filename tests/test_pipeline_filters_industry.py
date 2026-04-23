import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from cstree import pipeline
from cstree.data_interface import DataInterface
from cstree.data_tools import rqdata_assets
from tests._pipeline_test_utils import _build_frames, _run_pipeline


def test_pipeline_industry_file_missing_fails_before_daily_fetch(tmp_path, monkeypatch):
    fetch_calls = {"count": 0}

    def fake_init_client(self):
        self.client = None

    def fake_fetch_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        fetch_calls["count"] += 1
        return pd.DataFrame()

    monkeypatch.setattr(DataInterface, "_init_client", fake_init_client)
    monkeypatch.setattr(DataInterface, "fetch_daily", fake_fetch_daily)
    monkeypatch.setattr(DataInterface, "load_basic", lambda self, symbols=None: pd.DataFrame())

    missing_path = tmp_path / "missing_industry_labels.parquet"
    output_dir = tmp_path / "runs"
    config = {
        "market": "hk",
        "data": {
            "provider": "rqdata",
            "start_date": "20250310",
            "end_date": "20250515",
            "cache_dir": str(tmp_path / "cache"),
            "price_col": "close",
            "rqdata": {"market": "hk"},
        },
        "universe": {
            "mode": "static",
            "symbols": ["00005.HK", "00011.HK"],
            "min_symbols_per_date": 2,
            "drop_suspended": False,
        },
        "fundamentals": {"enabled": False},
        "industry": {
            "enabled": True,
            "source": "file",
            "file": str(missing_path),
            "required": True,
        },
        "label": {
            "horizon_mode": "fixed",
            "horizon_days": 1,
            "shift_days": 0,
            "target_col": "future_return",
        },
        "features": {
            "list": ["vol"],
            "cross_sectional": {"method": "none"},
        },
        "model": {
            "type": "xgb_regressor",
            "params": {
                "n_estimators": 5,
                "learning_rate": 0.1,
                "max_depth": 2,
                "subsample": 1.0,
                "colsample_bytree": 1.0,
                "random_state": 7,
                "objective": "reg:squarederror",
            },
            "sample_weight_mode": "none",
        },
        "eval": {
            "test_size": 0.2,
            "n_splits": 2,
            "n_quantiles": 2,
            "rebalance_frequency": "W",
            "top_k": 1,
            "signal_direction_mode": "fixed",
            "signal_direction": 1,
            "transaction_cost_bps": 0,
            "sample_on_rebalance_dates": False,
            "report_train_ic": False,
            "save_artifacts": True,
            "save_dataset": False,
            "output_dir": str(output_dir),
            "run_name": "hk-industry-missing",
            "walk_forward": {"enabled": False},
        },
        "backtest": {"enabled": False},
    }

    config_path = tmp_path / "config.yml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    with pytest.raises(SystemExit, match=f"Industry file not found: {missing_path}"):
        pipeline.run(str(config_path))

    assert fetch_calls["count"] == 0

@pytest.mark.slow
def test_pipeline_industry_file_join_preserves_labels_for_dataset_and_bucket_ic(
    tmp_path, monkeypatch
):
    dates = pd.date_range("2025-03-10", periods=35, freq="B")
    symbols = ["00005.HK", "00011.HK", "00700.HK", "00941.HK"]
    frames = _build_frames(symbols, dates, include_amount=True)
    basic_df = pd.DataFrame(
        {
            "symbol": symbols,
            "name": ["HSBC", "Hang Seng", "Tencent", "China Mobile"],
            "list_date": ["20000101"] * len(symbols),
        }
    )

    industry_path = tmp_path / "industry_labels_d.parquet"
    industry_rows = []
    for trade_date in dates:
        for symbol in symbols:
            industry_name = "银行" if symbol in {"00005.HK", "00011.HK"} else "传媒"
            industry_rows.append(
                {
                    "trade_date": trade_date,
                    "symbol": symbol,
                    "order_book_id": symbol.replace(".HK", ".XHKG"),
                    "industry_name": industry_name,
                    "first_industry_name": industry_name,
                }
            )
    pd.DataFrame(industry_rows).to_parquet(industry_path, index=False)

    bucket_calls = {"seen": False}

    def fake_bucket_ic_summary(
        data: pd.DataFrame,
        target_col: str,
        pred_col: str,
        bucket_col: str,
        *,
        method: str = "spearman",
        min_count: int = 0,
    ) -> pd.DataFrame:
        if bucket_col == "industry_name":
            bucket_calls["seen"] = True
            assert "industry_name" in data.columns
            return pd.DataFrame(
                {
                    "mean": [0.1, -0.1],
                    "std": [0.2, 0.3],
                    "ir": [0.5, -0.33],
                    "t_stat": [1.0, -1.0],
                    "p_value": [0.2, 0.3],
                    "n": [4, 4],
                    "bucket": ["银行", "传媒"],
                    "bucket_col": [bucket_col, bucket_col],
                }
            )
        return pd.DataFrame()

    monkeypatch.setattr(pipeline, "bucket_ic_summary", fake_bucket_ic_summary)

    output_dir = tmp_path / "runs"
    config = {
        "market": "hk",
        "data": {
            "provider": "rqdata",
            "start_date": "20250310",
            "end_date": "20250430",
            "cache_dir": str(tmp_path / "cache"),
            "price_col": "close",
            "rqdata": {"market": "hk"},
        },
        "universe": {
            "mode": "static",
            "symbols": symbols,
            "min_symbols_per_date": 4,
            "drop_suspended": False,
        },
        "fundamentals": {"enabled": False},
        "industry": {
            "enabled": True,
            "source": "file",
            "file": str(industry_path),
            "keep_columns": ["industry_name", "first_industry_name"],
            "required": True,
        },
        "label": {
            "horizon_mode": "fixed",
            "horizon_days": 1,
            "shift_days": 0,
            "target_col": "future_return",
        },
        "features": {
            "list": ["vol"],
            "cross_sectional": {"method": "none"},
        },
        "model": {
            "type": "xgb_regressor",
            "params": {
                "n_estimators": 5,
                "learning_rate": 0.1,
                "max_depth": 2,
                "subsample": 1.0,
                "colsample_bytree": 1.0,
                "random_state": 7,
                "objective": "reg:squarederror",
            },
            "sample_weight_mode": "none",
        },
        "eval": {
            "test_size": 0.2,
            "n_splits": 2,
            "n_quantiles": 2,
            "rebalance_frequency": "W",
            "top_k": 2,
            "signal_direction_mode": "fixed",
            "signal_direction": 1,
            "transaction_cost_bps": 0,
            "sample_on_rebalance_dates": False,
            "report_train_ic": False,
            "save_artifacts": True,
            "save_scored_artifact": True,
            "save_dataset": True,
            "output_dir": str(output_dir),
            "run_name": "hk-industry-join",
            "bucket_ic": {
                "enabled": True,
                "schemes": ["industry_name"],
            },
            "walk_forward": {"enabled": False},
        },
        "backtest": {"enabled": False},
    }

    run_dir = _run_pipeline(tmp_path, monkeypatch, config, frames, basic_df=basic_df)
    dataset = pd.read_parquet(run_dir / "dataset.parquet").reset_index()
    eval_scored = pd.read_parquet(run_dir / "eval_scored.parquet")
    bucket_ic = pd.read_csv(run_dir / "bucket_ic.csv")
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))

    assert {"industry_name", "first_industry_name"}.issubset(dataset.columns)
    assert {"industry_name", "first_industry_name"}.issubset(eval_scored.columns)
    assert dataset["industry_name"].isin({"银行", "传媒"}).all()
    assert bucket_calls["seen"] is True
    assert summary["industry"]["enabled"] is True
    assert summary["industry"]["resolved_columns"] == ["industry_name", "first_industry_name"]
    assert bucket_ic["scheme"].eq("industry_name").any()


@pytest.mark.slow
def test_pipeline_industry_sparse_labels_do_not_collapse_model_dates(
    tmp_path, monkeypatch
):
    dates = pd.date_range("2025-03-10", periods=45, freq="B")
    symbols = ["00005.HK", "00011.HK", "00700.HK", "00941.HK"]
    frames = _build_frames(symbols, dates, include_amount=True)
    basic_df = pd.DataFrame(
        {
            "symbol": symbols,
            "name": ["HSBC", "Hang Seng", "Tencent", "China Mobile"],
            "list_date": ["20000101"] * len(symbols),
        }
    )

    industry_path = tmp_path / "industry_labels_sparse.parquet"
    sparse_dates = dates[::5]
    industry_rows = []
    for trade_date in sparse_dates:
        for symbol in symbols:
            industry_name = "银行" if symbol in {"00005.HK", "00011.HK"} else "传媒"
            industry_rows.append(
                {
                    "trade_date": trade_date,
                    "symbol": symbol,
                    "industry_name": industry_name,
                    "first_industry_name": industry_name,
                }
            )
    pd.DataFrame(industry_rows).to_parquet(industry_path, index=False)

    output_dir = tmp_path / "runs"
    config = {
        "market": "hk",
        "data": {
            "provider": "rqdata",
            "start_date": "20250310",
            "end_date": "20250531",
            "cache_dir": str(tmp_path / "cache"),
            "price_col": "close",
            "rqdata": {"market": "hk"},
        },
        "universe": {
            "mode": "static",
            "symbols": symbols,
            "min_symbols_per_date": 4,
            "drop_suspended": False,
        },
        "fundamentals": {"enabled": False},
        "industry": {
            "enabled": True,
            "source": "file",
            "file": str(industry_path),
            "keep_columns": ["industry_name", "first_industry_name"],
            "required": True,
            "ffill": False,
        },
        "label": {
            "horizon_mode": "fixed",
            "horizon_days": 1,
            "shift_days": 0,
            "target_col": "future_return",
        },
        "features": {
            "list": ["vol"],
            "cross_sectional": {"method": "none"},
        },
        "model": {
            "type": "xgb_regressor",
            "params": {
                "n_estimators": 5,
                "learning_rate": 0.1,
                "max_depth": 2,
                "subsample": 1.0,
                "colsample_bytree": 1.0,
                "random_state": 7,
                "objective": "reg:squarederror",
            },
            "sample_weight_mode": "none",
        },
        "eval": {
            "test_size": 0.2,
            "n_splits": 2,
            "n_quantiles": 2,
            "rebalance_frequency": "W",
            "top_k": 2,
            "signal_direction_mode": "fixed",
            "signal_direction": 1,
            "transaction_cost_bps": 0,
            "sample_on_rebalance_dates": False,
            "report_train_ic": False,
            "save_artifacts": True,
            "save_scored_artifact": True,
            "save_dataset": True,
            "output_dir": str(output_dir),
            "run_name": "hk-industry-sparse",
            "walk_forward": {"enabled": False},
        },
        "backtest": {"enabled": False},
    }

    run_dir = _run_pipeline(tmp_path, monkeypatch, config, frames, basic_df=basic_df)
    dataset = pd.read_parquet(run_dir / "dataset.parquet").reset_index()
    eval_scored = pd.read_parquet(run_dir / "eval_scored.parquet")
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))

    assert {"industry_name", "first_industry_name"}.issubset(dataset.columns)
    assert {"industry_name", "first_industry_name"}.issubset(eval_scored.columns)
    assert dataset["industry_name"].isna().any()
    assert dataset["trade_date"].nunique() >= 30
    assert eval_scored["trade_date"].nunique() >= 5
    assert summary["industry"]["enabled"] is True
    assert summary["industry"]["resolved_columns"] == ["industry_name", "first_industry_name"]
