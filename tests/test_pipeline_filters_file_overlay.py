import json

import numpy as np
import pandas as pd
import pytest

from cstree.data_interface import DataInterface
from tests._pipeline_test_utils import _build_frames, _run_pipeline


@pytest.mark.slow
def test_pipeline_hk_file_fundamentals_provider_overlay_stays_daily(
    tmp_path, monkeypatch
):
    dates = pd.date_range("2025-03-10", periods=35, freq="B")
    symbols = ["00005.HK", "00011.HK"]
    frames = _build_frames(symbols, dates, include_amount=True)
    basic_df = pd.DataFrame(
        {"symbol": symbols, "name": ["HSBC", "Hang Seng"], "list_date": ["20000101", "20000101"]}
    )

    fundamentals_path = tmp_path / "pit_fundamentals.parquet"
    pd.DataFrame(
        {
            "trade_date": pd.to_datetime(
                ["2025-03-20", "2025-04-10", "2025-03-20", "2025-04-10"]
            ),
            "symbol": ["00005.HK", "00005.HK", "00011.HK", "00011.HK"],
            "net_profit": [10.0, 13.0, 20.0, 22.0],
        }
    ).to_parquet(fundamentals_path, index=False)

    seen_retry_flags = {}

    def fake_fetch_fundamentals(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        fundamentals_cfg,
        *,
        cache_dir=None,
        log_retry_failures=True,
        log_retry_traceback=True,
    ):
        assert fundamentals_cfg.get("endpoint") == "get_factor"
        seen_retry_flags[symbol] = (log_retry_failures, log_retry_traceback)
        base_cap = 1100.0 if symbol == "00005.HK" else 1500.0
        return pd.DataFrame(
            {
                "trade_date": ["20250410"],
                "symbol": [symbol],
                "market_cap": [base_cap],
                "pe_ttm": [8.5 if symbol == "00005.HK" else 10.2],
                "pb": [1.15 if symbol == "00005.HK" else 1.45],
            }
        )

    monkeypatch.setattr(DataInterface, "fetch_fundamentals", fake_fetch_fundamentals)

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
            "min_symbols_per_date": 2,
            "drop_suspended": False,
        },
        "fundamentals": {
            "enabled": True,
            "source": "file",
            "file": str(fundamentals_path),
            "column_map": {},
            "features": ["net_profit"],
            "auto_add_features": False,
            "allow_missing_features": False,
            "ffill": True,
            "required": True,
            "provider_overlay": {
                "enabled": True,
                "source": "provider",
                "endpoint": "get_factor",
                "features": ["market_cap", "pe_ttm", "pb"],
                "auto_add_features": False,
                "provider": "rqdata",
                "column_map": {
                    "trade_date": "trade_date",
                    "symbol": "symbol",
                    "market_cap": "market_cap",
                    "pe_ttm": "pe_ttm",
                    "pb": "pb",
                },
            },
        },
        "label": {
            "horizon_mode": "fixed",
            "horizon_days": 1,
            "shift_days": 0,
            "target_col": "future_return",
        },
        "features": {
            "list": ["net_profit", "days_since_report", "market_cap", "valuation_age_days"],
            "cross_sectional": {"method": "none"},
            "missing": {
                "method": "zero",
                "features": ["market_cap", "valuation_age_days"],
                "add_indicators": True,
            },
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
            "save_dataset": True,
            "output_dir": str(output_dir),
            "run_name": "hk-file-fundamentals-provider-overlay",
            "walk_forward": {"enabled": False},
        },
        "backtest": {"enabled": False},
    }

    run_dir = _run_pipeline(tmp_path, monkeypatch, config, frames, basic_df=basic_df)
    dataset = pd.read_parquet(run_dir / "dataset.parquet").reset_index()
    dataset["trade_date"] = pd.to_datetime(dataset["trade_date"])
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))

    report_row = dataset[
        (dataset["symbol"] == "00005.HK") & (dataset["trade_date"] == "2025-04-10")
    ]
    after_report_row = dataset[
        (dataset["symbol"] == "00005.HK") & (dataset["trade_date"] == "2025-04-11")
    ]

    assert report_row["net_profit"].iloc[0] == pytest.approx(13.0)
    assert after_report_row["days_since_report"].iloc[0] == pytest.approx(1.0)
    assert report_row["market_cap"].iloc[0] == pytest.approx(1100.0)
    assert report_row["market_cap_missing"].iloc[0] == pytest.approx(0.0)
    assert report_row["valuation_age_days_missing"].iloc[0] == pytest.approx(0.0)
    assert after_report_row["market_cap"].iloc[0] == pytest.approx(0.0)
    assert after_report_row["market_cap_missing"].iloc[0] == pytest.approx(1.0)
    assert after_report_row["valuation_age_days"].iloc[0] == pytest.approx(0.0)
    assert after_report_row["valuation_age_days_missing"].iloc[0] == pytest.approx(1.0)
    assert summary["fundamentals"]["provider_overlay"]["enabled"] is True
    assert summary["fundamentals"]["provider_overlay"]["provider"] == "rqdata"
    assert set(seen_retry_flags.values()) == {(False, False)}


@pytest.mark.slow
def test_pipeline_hk_file_fundamentals_provider_overlay_required_fails_when_empty(
    tmp_path, monkeypatch
):
    dates = pd.date_range("2025-03-10", periods=35, freq="B")
    symbols = ["00005.HK", "00011.HK"]
    frames = _build_frames(symbols, dates, include_amount=True)
    basic_df = pd.DataFrame(
        {"symbol": symbols, "name": ["HSBC", "Hang Seng"], "list_date": ["20000101", "20000101"]}
    )

    fundamentals_path = tmp_path / "pit_fundamentals.parquet"
    pd.DataFrame(
        {
            "trade_date": pd.to_datetime(
                ["2025-03-20", "2025-04-10", "2025-03-20", "2025-04-10"]
            ),
            "symbol": ["00005.HK", "00005.HK", "00011.HK", "00011.HK"],
            "net_profit": [10.0, 13.0, 20.0, 22.0],
        }
    ).to_parquet(fundamentals_path, index=False)

    def fake_fetch_fundamentals(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        fundamentals_cfg,
        *,
        cache_dir=None,
        log_retry_failures=True,
        log_retry_traceback=True,
    ):
        return pd.DataFrame()

    monkeypatch.setattr(DataInterface, "fetch_fundamentals", fake_fetch_fundamentals)

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
            "min_symbols_per_date": 2,
            "drop_suspended": False,
        },
        "fundamentals": {
            "enabled": True,
            "source": "file",
            "file": str(fundamentals_path),
            "column_map": {},
            "features": ["net_profit"],
            "auto_add_features": False,
            "allow_missing_features": False,
            "ffill": True,
            "required": True,
            "provider_overlay": {
                "enabled": True,
                "source": "provider",
                "endpoint": "get_factor",
                "features": ["pb"],
                "auto_add_features": False,
                "provider": "rqdata",
                "required": True,
                "column_map": {
                    "trade_date": "trade_date",
                    "symbol": "symbol",
                    "pb": "pb",
                },
            },
        },
        "label": {
            "horizon_mode": "fixed",
            "horizon_days": 1,
            "shift_days": 0,
            "target_col": "future_return",
        },
        "features": {
            "list": ["net_profit"],
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
            "save_dataset": True,
            "output_dir": str(output_dir),
            "run_name": "hk-file-fundamentals-provider-overlay-required-empty",
            "walk_forward": {"enabled": False},
        },
        "backtest": {"enabled": False},
    }

    with pytest.raises(SystemExit, match="Provider overlay enabled but no overlay data was loaded."):
        _run_pipeline(tmp_path, monkeypatch, config, frames, basic_df=basic_df)
