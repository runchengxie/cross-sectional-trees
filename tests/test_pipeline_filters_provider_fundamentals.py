import json

import numpy as np
import pandas as pd
import pytest

from cstree.data_interface import DataInterface
from tests._pipeline_test_utils import _build_frames, _run_pipeline


@pytest.mark.slow
def test_pipeline_hk_rqdata_provider_fundamentals_enabled(tmp_path, monkeypatch):
    dates = pd.date_range("2025-01-01", periods=12, freq="B")
    symbols = ["00005.HK", "00011.HK"]
    frames = _build_frames(symbols, dates, include_amount=True)
    basic_df = pd.DataFrame(
        {"symbol": symbols, "name": ["HSBC", "Hang Seng"], "list_date": ["20000101", "20000101"]}
    )

    seen_cache_dirs = {}
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
        seen_cache_dirs[symbol] = str(cache_dir) if cache_dir is not None else None
        seen_retry_flags[symbol] = (log_retry_failures, log_retry_traceback)
        return pd.DataFrame(
            {
                "trade_date": [d.strftime("%Y%m%d") for d in dates],
                "symbol": symbol,
                "market_cap": np.linspace(1000.0, 1100.0, len(dates)),
                "pe_ttm": np.linspace(8.0, 9.0, len(dates)),
                "pb": np.linspace(1.0, 1.1, len(dates)),
            }
        )

    monkeypatch.setattr(DataInterface, "fetch_fundamentals", fake_fetch_fundamentals)

    output_dir = tmp_path / "runs"
    config = {
        "market": "hk",
        "data": {
            "provider": "rqdata",
            "start_date": "20250101",
            "end_date": "20250131",
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
            "source": "provider",
            "endpoint": "get_factor",
            "fields": ["hk_total_market_val", "pe_ratio_ttm", "pb_ratio_ttm"],
            "column_map": {
                "trade_date": "trade_date",
                "symbol": "symbol",
                "market_cap": "hk_total_market_val",
                "pe_ttm": "pe_ratio_ttm",
                "pb": "pb_ratio_ttm",
            },
            "features": ["market_cap", "pe_ttm", "pb", "log_mcap"],
            "auto_add_features": True,
            "ffill": True,
            "log_market_cap": True,
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
            "save_dataset": True,
            "output_dir": str(output_dir),
            "run_name": "hk-fundamentals",
            "walk_forward": {"enabled": False},
        },
        "backtest": {"enabled": False},
    }

    run_dir = _run_pipeline(tmp_path, monkeypatch, config, frames, basic_df=basic_df)
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["fundamentals"]["enabled"] is True
    assert summary["fundamentals"]["source"] == "provider"
    assert summary["fundamentals"]["provider"] == "rqdata"
    assert summary["fundamentals"]["cache_dir"] == str(tmp_path / "cache" / "fundamentals" / "hk")
    assert summary["eval"]["feature_importance_file"]
    assert summary["eval"]["feature_importance_nonzero"] >= 0
    assert summary["eval"]["pred_nunique"] >= 1
    assert summary["eval"]["constant_prediction"] == (summary["eval"]["pred_nunique"] <= 1)
    assert summary["eval"]["zero_feature_importance"] == (
        summary["eval"]["feature_importance_nonzero"] == 0
    )

    dataset = pd.read_parquet(run_dir / "dataset.parquet").reset_index()
    assert {"market_cap", "pe_ttm", "pb", "log_mcap"}.issubset(dataset.columns)
    assert dataset["market_cap"].notna().all()
    assert dataset["pe_ttm"].notna().all()
    assert dataset["pb"].notna().all()
    assert dataset["log_mcap"].notna().all()
    assert set(seen_cache_dirs.values()) == {str(tmp_path / "cache" / "fundamentals" / "hk")}
    assert set(seen_retry_flags.values()) == {(True, True)}

@pytest.mark.slow
def test_pipeline_hk_provider_fundamentals_excludes_benchmark_symbol(
    tmp_path, monkeypatch
):
    dates = pd.date_range("2025-01-01", periods=20, freq="B")
    symbols = ["00005.HK", "00011.HK"]
    benchmark_symbol = "02800.HK"
    frames = _build_frames(symbols + [benchmark_symbol], dates, include_amount=True)
    seen_symbols: list[str] = []

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
        seen_symbols.append(symbol)
        return pd.DataFrame(
            {
                "trade_date": [d.strftime("%Y%m%d") for d in dates],
                "symbol": symbol,
                "market_cap": np.linspace(1000.0, 1100.0, len(dates)),
                "pe_ttm": np.linspace(8.0, 9.0, len(dates)),
                "pb": np.linspace(1.0, 1.1, len(dates)),
            }
        )

    monkeypatch.setattr(DataInterface, "fetch_fundamentals", fake_fetch_fundamentals)

    output_dir = tmp_path / "runs"
    config = {
        "market": "hk",
        "data": {
            "provider": "rqdata",
            "start_date": "20250101",
            "end_date": "20250131",
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
            "source": "provider",
            "endpoint": "get_factor",
            "fields": ["hk_total_market_val", "pe_ratio_ttm", "pb_ratio_ttm"],
            "column_map": {
                "trade_date": "trade_date",
                "symbol": "symbol",
                "market_cap": "hk_total_market_val",
                "pe_ttm": "pe_ratio_ttm",
                "pb": "pb_ratio_ttm",
            },
            "features": ["market_cap", "pe_ttm", "pb", "log_mcap"],
            "auto_add_features": True,
            "ffill": True,
            "log_market_cap": True,
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
            "save_dataset": True,
            "output_dir": str(output_dir),
            "run_name": "hk-fundamentals-benchmark-skip",
            "walk_forward": {"enabled": False},
        },
        "backtest": {
            "enabled": False,
            "benchmark_symbol": benchmark_symbol,
        },
    }

    _run_pipeline(tmp_path, monkeypatch, config, frames)

    assert set(seen_symbols) == set(symbols)
    assert benchmark_symbol not in seen_symbols
