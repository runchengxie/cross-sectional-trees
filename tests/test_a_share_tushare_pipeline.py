import json

import numpy as np
import pandas as pd
import pytest

from tests._pipeline_test_utils import _run_pipeline


@pytest.mark.slow
def test_pipeline_a_share_tushare_price_only_uses_daily_clean_overlays_and_filters(tmp_path, monkeypatch):
    dates = pd.date_range("2025-01-01", periods=18, freq="B")
    symbols = ["600519.SH", "000001.SZ", "300750.SZ"]
    frames = {}
    for idx, symbol in enumerate(symbols):
        frame = pd.DataFrame(
            {
                "trade_date": [d.strftime("%Y%m%d") for d in dates],
                "symbol": symbol,
                "close": 100.0 + np.arange(len(dates), dtype=float) + idx,
                "tr_close": 100.0 + np.arange(len(dates), dtype=float) + idx,
                "vol": np.full(len(dates), 1000.0 + idx),
                "amount": np.full(len(dates), 2_000_000.0 + idx),
                "pe_ttm": np.full(len(dates), 20.0 + idx),
                "pb": np.full(len(dates), 3.0 + idx),
                "ps_ttm": np.full(len(dates), 6.0 + idx),
                "total_mv": np.full(len(dates), 1_000_000.0 + idx),
                "turnover_rate": np.full(len(dates), 1.5 + idx),
                "is_st": symbol == "000001.SZ",
                "is_suspended": False,
                "is_limit_up": False,
                "is_limit_down": False,
            }
        )
        if symbol == "300750.SZ":
            frame.loc[0, "is_suspended"] = True
            frame.loc[1, "is_limit_up"] = True
        frames[symbol] = frame

    basic_df = pd.DataFrame(
        {
            "symbol": symbols,
            "name": ["贵州茅台", "ST 平安", "宁德时代"],
            "list_date": ["20010827", "19910403", "20180611"],
        }
    )
    output_dir = tmp_path / "runs"
    config = {
        "market": "a_share",
        "data": {
            "provider": "tushare",
            "source_mode": "platform_assets",
            "start_date": "20250101",
            "end_date": "20250131",
            "cache_dir": str(tmp_path / "cache"),
            "price_col": "tr_close",
            "tushare": {
                "daily_asset_dir": str(tmp_path / "assets" / "daily_clean"),
                "instruments_file": str(tmp_path / "assets" / "instruments.parquet"),
            },
        },
        "universe": {
            "mode": "static",
            "symbols": symbols,
            "min_symbols_per_date": 2,
            "drop_st": True,
            "drop_suspended": True,
            "drop_limit_up": True,
            "drop_limit_down": True,
            "suspended_policy": "filter",
            "min_turnover": 1_000_000,
            "min_listed_days": 0,
        },
        "fundamentals": {
            "enabled": True,
            "source": "provider",
            "provider_overlay": {
                "enabled": True,
                "source": "daily_clean",
                "features": ["pe_ttm", "pb", "ps_ttm", "turnover_rate", "total_mv"],
                "auto_add_features": True,
                "required": True,
            },
            "market_cap_col": "total_mv",
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
            "run_name": "a-share-tushare-price-only",
            "walk_forward": {"enabled": False},
        },
        "backtest": {
            "enabled": True,
            "tradable_col": "is_tradable",
            "execution": {
                "market": "a_share",
                "settlement": "T+1",
                "board_lot": 100,
                "price_limit_filter": True,
                "st_filter": True,
                "suspend_filter": True,
                "sell_stamp_duty_bps": 5,
            },
        },
    }

    run_dir = _run_pipeline(tmp_path, monkeypatch, config, frames, basic_df=basic_df)
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    dataset = pd.read_parquet(run_dir / "dataset.parquet").reset_index()

    assert summary["data"]["market"] == "a_share"
    assert summary["data"]["provider"] == "tushare"
    assert summary["fundamentals"]["provider_overlay"]["source"] == "daily_clean"
    assert {"pe_ttm", "pb", "ps_ttm", "turnover_rate", "total_mv", "log_mcap"}.issubset(
        dataset.columns
    )
    assert "000001.SZ" not in set(dataset["symbol"])
    target_dates = list(pd.to_datetime(["20250101", "20250102"]))
    suspended_or_limit = dataset[
        (dataset["symbol"] == "300750.SZ")
        & (dataset["trade_date"].isin(target_dates))
    ]
    assert len(suspended_or_limit) == 0
    assert dataset["pe_ttm"].notna().all()
    assert dataset["log_mcap"].notna().all()
