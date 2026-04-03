import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from csml import pipeline
from csml.data_interface import DataInterface
from csml.data_tools import rqdata_assets
from tests._pipeline_test_utils import _build_frames, _run_pipeline


@pytest.mark.slow
def test_pipeline_backtest_uses_unfiltered_pricing_panel_with_universe_by_date(
    tmp_path, monkeypatch
):
    dates = pd.date_range("2020-01-01", periods=15, freq="B")
    symbols = ["AAA.HK", "BBB.HK"]
    frames = _build_frames(symbols, dates, include_amount=False)

    universe_path = tmp_path / "universe_by_date.csv"
    pd.DataFrame(
        {
            "trade_date": ["20200101", "20200101", "20200113", "20200113", "20200116"],
            "symbol": ["AAA.HK", "BBB.HK", "AAA.HK", "BBB.HK", "BBB.HK"],
        }
    ).to_csv(universe_path, index=False)

    captured: dict[str, pd.DataFrame | None] = {}

    def fake_backtest_topk(data, *args, pricing_data=None, **kwargs):
        captured["data"] = data.copy()
        captured["pricing_data"] = pricing_data.copy() if pricing_data is not None else None
        return None

    monkeypatch.setattr(pipeline, "backtest_topk", fake_backtest_topk)

    output_dir = tmp_path / "runs"
    config = {
        "market": "hk",
        "data": {
            "provider": "rqdata",
            "start_date": "20200101",
            "end_date": "20200131",
            "cache_dir": str(tmp_path / "cache"),
            "price_col": "close",
        },
        "universe": {
            "mode": "pit",
            "symbols": symbols,
            "by_date_file": str(universe_path),
            "min_symbols_per_date": 1,
            "drop_suspended": False,
        },
        "fundamentals": {
            "enabled": False,
            "source": "provider",
            "required": False,
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
            "test_size": 0.5,
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
            "run_name": "pit_backtest_pricing",
            "walk_forward": {"enabled": False},
        },
        "backtest": {
            "enabled": True,
            "rebalance_frequency": "W",
            "top_k": 1,
            "transaction_cost_bps": 0,
            "exit_mode": "rebalance",
            "exit_price_policy": "delay",
        },
    }

    _run_pipeline(tmp_path, monkeypatch, config, frames)

    assert captured["pricing_data"] is not None
    selection_df = captured["data"]
    pricing_df = captured["pricing_data"]
    assert selection_df is not None
    assert pricing_df is not None

    dropped_date = pd.Timestamp("2020-01-17")
    selection_symbols = selection_df.loc[
        selection_df["trade_date"] == dropped_date, "symbol"
    ].tolist()
    pricing_symbols = pricing_df.loc[
        pricing_df["trade_date"] == dropped_date, "symbol"
    ].tolist()

    assert "AAA.HK" not in selection_symbols
    assert "AAA.HK" in pricing_symbols

@pytest.mark.slow
def test_pipeline_backtest_pricing_includes_execution_columns(tmp_path, monkeypatch):
    dates = pd.date_range("2020-01-01", periods=15, freq="B")
    symbols = ["AAA", "BBB"]
    frames = _build_frames(symbols, dates, include_amount=True)
    for frame in frames.values():
        frame["open"] = frame["close"] - 1.0

    captured: dict[str, pd.DataFrame | None] = {}

    def fake_backtest_topk(data, *args, pricing_data=None, **kwargs):
        captured["data"] = data.copy()
        captured["pricing_data"] = pricing_data.copy() if pricing_data is not None else None
        return None

    monkeypatch.setattr(pipeline, "backtest_topk", fake_backtest_topk)

    output_dir = tmp_path / "runs"
    config = {
        "market": "hk",
        "data": {
            "provider": "rqdata",
            "start_date": "20200101",
            "end_date": "20200131",
            "cache_dir": str(tmp_path / "cache"),
            "price_col": "close",
        },
        "universe": {
            "mode": "static",
            "symbols": symbols,
            "min_symbols_per_date": 1,
            "drop_suspended": False,
        },
        "fundamentals": {
            "enabled": True,
            "source": "provider",
            "required": False,
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
            "test_size": 0.5,
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
            "save_scored_artifact": True,
            "save_dataset": True,
            "output_dir": str(output_dir),
            "run_name": "execution_pricing_cols",
            "walk_forward": {"enabled": False},
        },
        "backtest": {
            "enabled": True,
            "rebalance_frequency": "W",
            "top_k": 1,
            "transaction_cost_bps": 0,
            "exit_mode": "rebalance",
            "exit_price_policy": "strict",
            "execution": {
                "entry_policy": {"price_col": "open"},
                "slippage_model": {
                    "name": "participation",
                    "amount_col": "amount",
                    "base_bps": 0,
                    "impact_bps": 10,
                    "portfolio_value": 1000,
                },
                "constraints": {"min_amount": 50, "amount_col": "amount"},
            },
        },
    }

    run_dir = _run_pipeline(tmp_path, monkeypatch, config, frames)
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    eval_scored = pd.read_parquet(run_dir / "eval_scored.parquet")
    assert summary["backtest"]["execution_source"] == "explicit_execution_config"
    assert summary["backtest"]["execution"]["entry_policy"]["price_col"] == "open"

    pricing_df = captured["pricing_data"]
    assert pricing_df is not None
    assert "open" in pricing_df.columns
    assert "close" in pricing_df.columns
    assert "amount" in pricing_df.columns
    assert {"open", "amount"}.issubset(eval_scored.columns)

@pytest.mark.slow
def test_pipeline_backtest_pricing_derives_lagged_adv_execution_columns(tmp_path, monkeypatch):
    dates = pd.date_range("2020-01-01", periods=15, freq="B")
    symbols = ["AAA", "BBB"]
    frames = _build_frames(symbols, dates, include_amount=True)
    for frame in frames.values():
        frame["open"] = frame["close"] - 1.0

    captured: dict[str, pd.DataFrame | None] = {}

    def fake_backtest_topk(data, *args, pricing_data=None, **kwargs):
        captured["pricing_data"] = pricing_data.copy() if pricing_data is not None else None
        return None

    monkeypatch.setattr(pipeline, "backtest_topk", fake_backtest_topk)

    output_dir = tmp_path / "runs"
    config = {
        "market": "hk",
        "data": {
            "provider": "rqdata",
            "start_date": "20200101",
            "end_date": "20200131",
            "cache_dir": str(tmp_path / "cache"),
            "price_col": "close",
        },
        "universe": {
            "mode": "static",
            "symbols": symbols,
            "min_symbols_per_date": 1,
            "drop_suspended": False,
        },
        "fundamentals": {"enabled": False},
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
            "test_size": 0.5,
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
            "save_scored_artifact": True,
            "save_dataset": True,
            "output_dir": str(output_dir),
            "run_name": "execution_adv_pricing_cols",
            "walk_forward": {"enabled": False},
        },
        "backtest": {
            "enabled": True,
            "rebalance_frequency": "W",
            "top_k": 1,
            "transaction_cost_bps": 0,
            "exit_mode": "rebalance",
            "exit_price_policy": "strict",
            "execution": {
                "entry_policy": {"price_col": "open"},
                "slippage_model": {
                    "name": "participation",
                    "amount_col": "adv3_amount",
                    "base_bps": 0,
                    "impact_bps": 10,
                    "portfolio_value": 1000,
                },
                "constraints": {"min_amount": 50, "amount_col": "adv3_amount"},
            },
        },
    }

    run_dir = _run_pipeline(tmp_path, monkeypatch, config, frames)
    eval_scored = pd.read_parquet(run_dir / "eval_scored.parquet")

    pricing_df = captured["pricing_data"]
    assert pricing_df is not None
    assert "adv3_amount" in pricing_df.columns
    assert "open" in eval_scored.columns
    assert "adv3_amount" in eval_scored.columns

    aaa = pricing_df[pricing_df["symbol"] == "AAA"].sort_values("trade_date").reset_index(drop=True)
    assert np.isnan(float(aaa.loc[0, "adv3_amount"]))
    assert float(aaa.loc[1, "adv3_amount"]) == pytest.approx(100000.0)
    assert float(aaa.loc[2, "adv3_amount"]) == pytest.approx(100500.0)
    assert float(aaa.loc[3, "adv3_amount"]) == pytest.approx(101000.0)

@pytest.mark.slow
def test_pipeline_price_features_follow_price_col(tmp_path, monkeypatch):
    dates = pd.date_range("2020-01-01", periods=20, freq="B")
    symbols = ["AAA", "BBB", "CCC"]
    frames: dict[str, pd.DataFrame] = {}
    for idx, symbol in enumerate(symbols):
        tr_close = np.arange(1, len(dates) + 1, dtype=float) + idx
        close = np.full(len(dates), 100.0 + idx, dtype=float)
        vol = np.full(len(dates), 1000.0 + idx, dtype=float)
        frames[symbol] = pd.DataFrame(
            {
                "trade_date": [d.strftime("%Y%m%d") for d in dates],
                "symbol": symbol,
                "close": close,
                "tr_close": tr_close,
                "vol": vol,
                "amount": close * vol,
            }
        )

    output_dir = tmp_path / "runs"
    config = {
        "market": "hk",
        "data": {
            "provider": "rqdata",
            "start_date": "20200101",
            "end_date": "20200131",
            "cache_dir": str(tmp_path / "cache"),
            "price_col": "tr_close",
        },
        "universe": {
            "mode": "static",
            "symbols": symbols,
            "min_symbols_per_date": 1,
            "drop_suspended": False,
        },
        "fundamentals": {"enabled": False},
        "label": {
            "horizon_mode": "fixed",
            "horizon_days": 1,
            "shift_days": 0,
            "target_col": "future_return",
        },
        "features": {
            "list": ["sma_3"],
            "params": {"sma_windows": [3]},
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
            "run_name": "price_col_tr_close",
            "walk_forward": {"enabled": False},
        },
        "backtest": {"enabled": False},
    }

    run_dir = _run_pipeline(tmp_path, monkeypatch, config, frames)
    dataset = pd.read_parquet(run_dir / "dataset.parquet").reset_index()
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    aaa = dataset[dataset["symbol"] == "AAA"].sort_values("trade_date").reset_index(drop=True)
    probe_date = pd.Timestamp("2020-01-07")
    observed = float(aaa.loc[aaa["trade_date"] == probe_date, "sma_3"].iloc[0])
    assert observed == pytest.approx((3.0 + 4.0 + 5.0) / 3.0)
    assert float(aaa.loc[aaa["trade_date"] == probe_date, "close"].iloc[0]) == 100.0
    assert float(aaa.loc[aaa["trade_date"] == probe_date, "tr_close"].iloc[0]) == 5.0
    assert summary["data"]["price_col"] == "tr_close"
    assert summary["data"]["price_col_diagnostics"]["tr_close_source_counts"] == {
        "input_frame": 3
    }


@pytest.mark.slow
def test_pipeline_backtest_outputs_style_and_industry_exposure_artifacts(
    tmp_path, monkeypatch
):
    dates = pd.date_range("2025-01-02", periods=95, freq="B")
    symbols = ["00005.HK", "00011.HK", "00700.HK", "00941.HK"]
    steps = np.arange(len(dates), dtype=float)
    close_map = {
        "00005.HK": 90.0 + 0.55 * steps + 2.0 * np.sin(steps / 8.0),
        "00011.HK": 75.0 + 0.20 * steps + 1.5 * np.cos(steps / 9.0),
        "00700.HK": 110.0 + 0.85 * steps + 3.0 * np.sin(steps / 7.0 + 0.3),
        "00941.HK": 100.0 + 0.35 * steps + 1.0 * np.cos(steps / 11.0 + 0.7),
    }
    vol_map = {
        "00005.HK": 1400.0 + 20.0 * np.sin(steps / 6.0),
        "00011.HK": 1250.0 + 15.0 * np.cos(steps / 7.0),
        "00700.HK": 2000.0 + 40.0 * np.sin(steps / 5.0),
        "00941.HK": 1700.0 + 25.0 * np.cos(steps / 8.0),
    }
    frames = _build_frames(
        symbols,
        dates,
        close_map=close_map,
        vol_map=vol_map,
        include_amount=True,
    )
    basic_df = pd.DataFrame(
        {
            "symbol": symbols,
            "name": ["HSBC", "Hang Seng", "Tencent", "China Mobile"],
            "list_date": ["20000101"] * len(symbols),
        }
    )

    fundamentals_rows = []
    industry_rows = []
    base_caps = {
        "00005.HK": 1200.0,
        "00011.HK": 1000.0,
        "00700.HK": 2200.0,
        "00941.HK": 1800.0,
    }
    base_pe = {
        "00005.HK": 8.5,
        "00011.HK": 10.0,
        "00700.HK": 18.0,
        "00941.HK": 12.0,
    }
    base_pb = {
        "00005.HK": 0.9,
        "00011.HK": 1.1,
        "00700.HK": 2.8,
        "00941.HK": 1.6,
    }
    base_roe = {
        "00005.HK": 0.12,
        "00011.HK": 0.09,
        "00700.HK": 0.18,
        "00941.HK": 0.14,
    }
    base_beta = {
        "00005.HK": 0.80,
        "00011.HK": 0.65,
        "00700.HK": 1.20,
        "00941.HK": 0.95,
    }
    industries = {
        "00005.HK": "银行",
        "00011.HK": "银行",
        "00700.HK": "传媒",
        "00941.HK": "传媒",
    }
    for idx, trade_date in enumerate(dates):
        for symbol in symbols:
            fundamentals_rows.append(
                {
                    "trade_date": trade_date,
                    "symbol": symbol,
                    "market_cap": base_caps[symbol] + idx * 6.0,
                    "pe_ttm": base_pe[symbol] + 0.02 * idx,
                    "pb": base_pb[symbol] + 0.01 * np.sin(idx / 10.0),
                    "roe": base_roe[symbol] + 0.001 * np.cos(idx / 12.0),
                    "beta": base_beta[symbol] + 0.01 * np.sin(idx / 9.0),
                }
            )
            industry_rows.append(
                {
                    "trade_date": trade_date,
                    "symbol": symbol,
                    "industry_name": industries[symbol],
                }
            )

    fundamentals_path = tmp_path / "fundamentals.parquet"
    pd.DataFrame(fundamentals_rows).to_parquet(fundamentals_path, index=False)
    industry_path = tmp_path / "industry.parquet"
    pd.DataFrame(industry_rows).to_parquet(industry_path, index=False)

    output_dir = tmp_path / "runs"
    config = {
        "market": "hk",
        "data": {
            "provider": "rqdata",
            "start_date": "20250102",
            "end_date": "20250520",
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
        "fundamentals": {
            "enabled": True,
            "source": "file",
            "file": str(fundamentals_path),
            "features": ["market_cap", "pe_ttm", "pb", "roe", "beta"],
            "auto_add_features": False,
            "allow_missing_features": False,
            "ffill": False,
            "required": True,
        },
        "industry": {
            "enabled": True,
            "source": "file",
            "file": str(industry_path),
            "keep_columns": ["industry_name"],
            "required": True,
        },
        "label": {
            "horizon_mode": "fixed",
            "horizon_days": 1,
            "shift_days": 0,
            "target_col": "future_return",
        },
        "features": {
            "list": ["ret_20", "rv_20", "market_cap", "pe_ttm", "pb", "roe", "beta"],
            "cross_sectional": {"method": "none"},
        },
        "model": {
            "type": "xgb_regressor",
            "params": {
                "n_estimators": 20,
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
            "test_size": 0.25,
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
            "save_dataset": False,
            "output_dir": str(output_dir),
            "run_name": "backtest_exposure_outputs",
            "walk_forward": {"enabled": False},
        },
        "backtest": {
            "enabled": True,
            "top_k": 2,
            "rebalance_frequency": "W",
            "transaction_cost_bps": 0,
            "long_only": True,
            "exit_mode": "rebalance",
            "exit_price_policy": "delay",
        },
    }

    run_dir = _run_pipeline(tmp_path, monkeypatch, config, frames, basic_df=basic_df)
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    style_path = run_dir / "backtest_style_exposure.csv"
    industry_output_path = run_dir / "backtest_industry_exposure.csv"
    active_summary_path = run_dir / "backtest_active_exposure_summary.csv"
    style = pd.read_csv(style_path)
    industry = pd.read_csv(industry_output_path)
    active_summary = pd.read_csv(active_summary_path)

    assert style_path.exists()
    assert industry_output_path.exists()
    assert active_summary_path.exists()
    assert set(style["factor"]) == {"size", "value", "quality", "momentum", "low_vol", "beta"}
    assert set(industry["industry"]) == {"银行", "传媒"}
    assert summary["backtest"]["exposure"]["style_file"] == str(style_path)
    assert summary["backtest"]["exposure"]["industry_file"] == str(industry_output_path)
    assert summary["backtest"]["exposure"]["active_summary_file"] == str(active_summary_path)
    assert summary["backtest"]["exposure"]["industry_column"] == "industry_name"
    assert summary["backtest"]["exposure"]["latest_rebalance_date"] is not None
    assert summary["backtest"]["exposure"]["style_factors"]["size"]["available"] is True
    assert summary["backtest"]["exposure"]["style_factors"]["value"]["available"] is True
    assert summary["backtest"]["exposure"]["style_factors"]["quality"]["available"] is True
    assert summary["backtest"]["exposure"]["style_factors"]["momentum"]["available"] is True
    assert summary["backtest"]["exposure"]["style_factors"]["low_vol"]["available"] is True
    assert summary["backtest"]["exposure"]["style_factors"]["beta"]["available"] is True
    assert set(summary["backtest"]["exposure"]["latest_style"].keys()) == {
        "size",
        "value",
        "quality",
        "momentum",
        "low_vol",
        "beta",
    }
    assert summary["backtest"]["exposure"]["latest_industry"]["top_absolute_active"]
    assert {
        "rebalance_date",
        "entry_date",
        "size_active_net_vs_cap",
        "momentum_active_net_vs_cap",
        "industry_reference",
        "industry_top_1_name",
        "industry_top_1_active",
    }.issubset(active_summary.columns)
