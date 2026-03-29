import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from csml import pipeline
from csml.data_interface import DataInterface
from csml.data_tools import rqdata_assets


def _build_frames(
    symbols: list[str],
    dates: pd.DatetimeIndex,
    *,
    close_map: dict[str, np.ndarray] | None = None,
    vol_map: dict[str, np.ndarray] | None = None,
    include_amount: bool = True,
) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    steps = np.arange(len(dates), dtype=float)
    close_map = close_map or {}
    vol_map = vol_map or {}
    for idx, symbol in enumerate(symbols):
        close = close_map.get(symbol)
        if close is None:
            close = 100.0 + steps + idx * 5.0
        vol = vol_map.get(symbol)
        if vol is None:
            vol = np.full(len(dates), 1000.0 + idx, dtype=float)
        payload = {
            "trade_date": [d.strftime("%Y%m%d") for d in dates],
            "symbol": symbol,
            "close": np.asarray(close, dtype=float),
            "vol": np.asarray(vol, dtype=float),
        }
        if include_amount:
            payload["amount"] = payload["close"] * payload["vol"]
        frames[symbol] = pd.DataFrame(payload)
    return frames


def _run_pipeline(tmp_path, monkeypatch, config, frames, basic_df=None) -> Path:
    def fake_init_client(self):
        self.client = None

    def fake_fetch_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        return frames[symbol].copy()

    def fake_load_basic(self, symbols=None) -> pd.DataFrame:
        return basic_df.copy() if basic_df is not None else pd.DataFrame()

    monkeypatch.setattr(DataInterface, "_init_client", fake_init_client)
    monkeypatch.setattr(DataInterface, "fetch_daily", fake_fetch_daily)
    monkeypatch.setattr(DataInterface, "load_basic", fake_load_basic)

    config_path = tmp_path / "config.yml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    pipeline.run(str(config_path))

    output_dir = Path(config["eval"]["output_dir"])
    run_dirs = sorted(output_dir.glob(f"{config['eval']['run_name']}_*"))
    assert len(run_dirs) == 1
    return run_dirs[0]


@pytest.mark.slow
def test_pipeline_filters_and_fallbacks(tmp_path, monkeypatch):
    dates = pd.date_range("2020-01-01", periods=12, freq="B")
    symbols = ["AAA", "BBB", "CCC"]
    vol_map = {
        "AAA": np.full(len(dates), 100.0),
        "BBB": np.full(len(dates), 120.0),
        "CCC": np.array([50.0, 0.0] + [60.0] * (len(dates) - 2)),
    }
    frames = _build_frames(symbols, dates, vol_map=vol_map, include_amount=False)
    basic_df = pd.DataFrame(
        {"symbol": symbols, "name": ["Alpha", "ST Beta", "Gamma"]}
    )

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
            "drop_suspended": True,
            "suspended_policy": "mark",
            "drop_st": True,
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
            "run_name": "filters",
            "walk_forward": {"enabled": False},
        },
        "backtest": {"enabled": False},
    }

    run_dir = _run_pipeline(tmp_path, monkeypatch, config, frames, basic_df=basic_df)
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["data"]["price_col"] == "close"
    assert summary["data"]["min_symbols_per_date"] == 2
    assert summary["fundamentals"]["enabled"] is False

    dataset = pd.read_parquet(run_dir / "dataset.parquet").reset_index()
    assert "BBB" not in dataset["symbol"].unique()
    ccc_rows = dataset[dataset["symbol"] == "CCC"]
    assert not ccc_rows.empty
    zero_vol_rows = ccc_rows[ccc_rows["vol"] == 0.0]
    assert not zero_vol_rows.empty
    assert zero_vol_rows["is_tradable"].eq(False).all()


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


@pytest.mark.slow
def test_pipeline_hk_file_fundamentals_built_from_pit_asset(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "pit_financials" / "pit_demo"
    data_dir = asset_dir / "data"
    data_dir.mkdir(parents=True)
    (asset_dir / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "pit_financials",
                "query": {"fields": ["revenue", "net_profit"]},
                "columns": [
                    "quarter",
                    "info_date",
                    "fiscal_year",
                    "standard",
                    "if_adjusted",
                    "rice_create_tm",
                    "revenue",
                    "net_profit",
                    "order_book_id",
                    "symbol",
                ],
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        {
            "quarter": ["2024q4"],
            "info_date": pd.to_datetime(["2025-03-20"]),
            "fiscal_year": pd.to_datetime(["2024-12-31"]),
            "standard": ["IFRS"],
            "if_adjusted": [0],
            "rice_create_tm": pd.to_datetime(["2025-03-20 09:00:00"]),
            "revenue": [100.0],
            "net_profit": [10.0],
            "order_book_id": ["00005.XHKG"],
            "symbol": ["00005.HK"],
        }
    ).to_parquet(data_dir / "00005.HK.parquet", index=False)
    pd.DataFrame(
        {
            "quarter": ["2025q1"],
            "info_date": pd.to_datetime(["2025-03-24"]),
            "fiscal_year": pd.to_datetime(["2025-12-31"]),
            "standard": ["IFRS"],
            "if_adjusted": [0],
            "rice_create_tm": pd.to_datetime(["2025-03-24 09:00:00"]),
            "revenue": [220.0],
            "net_profit": [22.0],
            "order_book_id": ["00011.XHKG"],
            "symbol": ["00011.HK"],
        }
    ).to_parquet(data_dir / "00011.HK.parquet", index=False)

    fundamentals_path = repo_root / "artifacts" / "assets" / "fundamentals" / "pit_fundamentals.parquet"
    assert (
        rqdata_assets.build_hk_pit_fundamentals_file(
            type(
                "Args",
                (),
                {
                    "asset_dir": str(asset_dir),
                    "field": [],
                    "fields_file": [],
                    "out": str(fundamentals_path),
                    "keep_meta": False,
                    "duplicate_policy": "keep-last",
                    "force": False,
                },
            )()
        )
        == 0
    )

    dates = pd.date_range("2025-03-10", periods=25, freq="B")
    symbols = ["00005.HK", "00011.HK"]
    frames = _build_frames(symbols, dates, include_amount=True)
    basic_df = pd.DataFrame(
        {"symbol": symbols, "name": ["HSBC", "Hang Seng"], "list_date": ["20000101", "20000101"]}
    )

    output_dir = repo_root / "runs"
    config = {
        "market": "hk",
        "data": {
            "provider": "rqdata",
            "start_date": "20250310",
            "end_date": "20250415",
            "cache_dir": str(repo_root / "cache"),
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
            "features": ["revenue", "net_profit"],
            "auto_add_features": True,
            "ffill": True,
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
            "save_dataset": True,
            "output_dir": str(output_dir),
            "run_name": "hk-file-fundamentals",
            "walk_forward": {"enabled": False},
        },
        "backtest": {"enabled": False},
    }

    run_dir = _run_pipeline(repo_root, monkeypatch, config, frames, basic_df=basic_df)
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["fundamentals"]["enabled"] is True
    assert summary["fundamentals"]["source"] == "file"

    dataset = pd.read_parquet(run_dir / "dataset.parquet").reset_index()
    dataset["trade_date"] = pd.to_datetime(dataset["trade_date"])
    before_00005 = dataset[(dataset["symbol"] == "00005.HK") & (dataset["trade_date"] == "2025-03-19")]
    on_00005 = dataset[(dataset["symbol"] == "00005.HK") & (dataset["trade_date"] == "2025-03-20")]
    after_00005 = dataset[(dataset["symbol"] == "00005.HK") & (dataset["trade_date"] == "2025-03-21")]
    before_00011 = dataset[(dataset["symbol"] == "00011.HK") & (dataset["trade_date"] == "2025-03-21")]
    on_00011 = dataset[(dataset["symbol"] == "00011.HK") & (dataset["trade_date"] == "2025-03-24")]

    assert before_00005["revenue"].isna().all()
    assert on_00005["revenue"].eq(100.0).all()
    assert after_00005["revenue"].eq(100.0).all()
    assert before_00011["revenue"].isna().all()
    assert on_00011["revenue"].eq(220.0).all()


@pytest.mark.slow
def test_pipeline_hk_file_fundamentals_derived_slow_features(tmp_path, monkeypatch):
    dates = pd.date_range("2025-03-10", periods=40, freq="B")
    symbols = ["00005.HK", "00011.HK"]
    frames = _build_frames(symbols, dates, include_amount=True)
    basic_df = pd.DataFrame(
        {"symbol": symbols, "name": ["HSBC", "Hang Seng"], "list_date": ["20000101", "20000101"]}
    )

    fundamentals_path = tmp_path / "pit_fundamentals.parquet"
    pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2025-03-20", "2025-03-20"]),
            "symbol": ["00005.HK", "00011.HK"],
            "revenue": [100.0, 220.0],
            "net_profit": [10.0, 22.0],
            "total_assets": [200.0, 440.0],
            "total_liabilities": [80.0, 176.0],
            "cash_flow_from_operating_activities": [16.0, 18.0],
            "accounts_receivable": [20.0, 44.0],
            "inventory": [15.0, 33.0],
        }
    ).to_parquet(fundamentals_path, index=False)

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
            "symbols": symbols,
            "min_symbols_per_date": 2,
            "drop_suspended": False,
        },
        "fundamentals": {
            "enabled": True,
            "source": "file",
            "file": str(fundamentals_path),
            "column_map": {},
            "features": [
                "profit_margin",
                "asset_turnover",
                "roa",
                "leverage",
                "cfo_to_assets",
                "accrual_ratio",
                "receivables_to_revenue",
                "inventory_to_revenue",
            ],
            "auto_add_features": True,
            "ffill": True,
            "required": True,
        },
        "label": {
            "horizon_mode": "fixed",
            "horizon_days": 1,
            "shift_days": 0,
            "target_col": "future_return",
        },
        "features": {
            "list": ["profit_margin"],
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
            "run_name": "hk-file-fundamentals-derived",
            "walk_forward": {"enabled": False},
        },
        "backtest": {"enabled": False},
    }

    run_dir = _run_pipeline(tmp_path, monkeypatch, config, frames, basic_df=basic_df)
    dataset = pd.read_parquet(run_dir / "dataset.parquet").reset_index()
    dataset["trade_date"] = pd.to_datetime(dataset["trade_date"])

    before_00005 = dataset[(dataset["symbol"] == "00005.HK") & (dataset["trade_date"] == "2025-03-19")]
    on_00005 = dataset[(dataset["symbol"] == "00005.HK") & (dataset["trade_date"] == "2025-03-20")]
    after_00005 = dataset[(dataset["symbol"] == "00005.HK") & (dataset["trade_date"] == "2025-03-21")]

    derived_cols = [
        "profit_margin",
        "asset_turnover",
        "roa",
        "leverage",
        "cfo_to_assets",
        "accrual_ratio",
        "receivables_to_revenue",
        "inventory_to_revenue",
    ]
    assert before_00005[derived_cols].isna().all().all()

    expected = {
        "profit_margin": 0.10,
        "asset_turnover": 0.50,
        "roa": 0.05,
        "leverage": 0.40,
        "cfo_to_assets": 0.08,
        "accrual_ratio": -0.03,
        "receivables_to_revenue": 0.20,
        "inventory_to_revenue": 0.15,
    }
    for column, expected_value in expected.items():
        assert on_00005[column].iloc[0] == pytest.approx(expected_value)
        assert after_00005[column].iloc[0] == pytest.approx(expected_value)


@pytest.mark.slow
def test_pipeline_hk_file_fundamentals_missing_fill_with_indicators(tmp_path, monkeypatch):
    dates = pd.date_range("2025-03-10", periods=25, freq="B")
    symbols = ["00005.HK", "00011.HK", "00016.HK"]
    frames = _build_frames(symbols, dates, include_amount=True)
    basic_df = pd.DataFrame(
        {"symbol": symbols, "name": ["HSBC", "Hang Seng", "Sun Hung Kai"], "list_date": ["20000101"] * 3}
    )

    fundamentals_path = tmp_path / "pit_fundamentals.parquet"
    pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2025-03-20", "2025-03-20", "2025-03-20"]),
            "symbol": symbols,
            "revenue": [100.0, 200.0, 300.0],
            "net_profit": [10.0, 20.0, np.nan],
        }
    ).to_parquet(fundamentals_path, index=False)

    output_dir = tmp_path / "runs"
    config = {
        "market": "hk",
        "data": {
            "provider": "rqdata",
            "start_date": "20250310",
            "end_date": "20250415",
            "cache_dir": str(tmp_path / "cache"),
            "price_col": "close",
            "rqdata": {"market": "hk"},
        },
        "universe": {
            "mode": "static",
            "symbols": symbols,
            "min_symbols_per_date": 3,
            "drop_suspended": False,
        },
        "fundamentals": {
            "enabled": True,
            "source": "file",
            "file": str(fundamentals_path),
            "column_map": {},
            "features": ["revenue", "net_profit"],
            "auto_add_features": False,
            "allow_missing_features": True,
            "ffill": True,
            "required": True,
        },
        "label": {
            "horizon_mode": "fixed",
            "horizon_days": 1,
            "shift_days": 0,
            "target_col": "future_return",
        },
        "features": {
            "list": ["profit_margin"],
            "cross_sectional": {"method": "none"},
            "missing": {
                "method": "cross_sectional_median",
                "features": ["profit_margin"],
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
            "run_name": "hk-file-fundamentals-missing-fill",
            "walk_forward": {"enabled": False},
        },
        "backtest": {"enabled": False},
    }

    run_dir = _run_pipeline(tmp_path, monkeypatch, config, frames, basic_df=basic_df)
    dataset = pd.read_parquet(run_dir / "dataset.parquet").reset_index()
    dataset["trade_date"] = pd.to_datetime(dataset["trade_date"])

    filled_row = dataset[
        (dataset["symbol"] == "00016.HK") & (dataset["trade_date"] == "2025-03-20")
    ]
    observed_row = dataset[
        (dataset["symbol"] == "00005.HK") & (dataset["trade_date"] == "2025-03-20")
    ]

    assert filled_row["profit_margin"].iloc[0] == pytest.approx(0.10)
    assert filled_row["profit_margin_missing"].iloc[0] == pytest.approx(1.0)
    assert observed_row["profit_margin_missing"].iloc[0] == pytest.approx(0.0)


@pytest.mark.slow
def test_pipeline_hk_file_fundamentals_supports_sales_delta_and_report_age(tmp_path, monkeypatch):
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
            "revenue": [100.0, 130.0, 200.0, 220.0],
            "operating_revenue": [np.nan, np.nan, np.nan, np.nan],
            "net_profit": [10.0, 13.0, 20.0, 22.0],
        }
    ).to_parquet(fundamentals_path, index=False)

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
            "features": ["revenue", "operating_revenue", "net_profit"],
            "auto_add_features": False,
            "allow_missing_features": True,
            "ffill": True,
            "required": True,
        },
        "label": {
            "horizon_mode": "fixed",
            "horizon_days": 1,
            "shift_days": 0,
            "target_col": "future_return",
        },
        "features": {
            "list": ["sales", "delta_sales", "days_since_report"],
            "cross_sectional": {"method": "none"},
            "missing": {"method": "zero", "features": ["delta_sales"]},
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
            "run_name": "hk-file-fundamentals-delta-sales",
            "walk_forward": {"enabled": False},
        },
        "backtest": {"enabled": False},
    }

    run_dir = _run_pipeline(tmp_path, monkeypatch, config, frames, basic_df=basic_df)
    dataset = pd.read_parquet(run_dir / "dataset.parquet").reset_index()
    dataset["trade_date"] = pd.to_datetime(dataset["trade_date"])

    report_row = dataset[
        (dataset["symbol"] == "00005.HK") & (dataset["trade_date"] == "2025-04-10")
    ]
    after_report_row = dataset[
        (dataset["symbol"] == "00005.HK") & (dataset["trade_date"] == "2025-04-11")
    ]

    assert report_row["sales"].iloc[0] == pytest.approx(130.0)
    assert report_row["delta_sales"].iloc[0] == pytest.approx(30.0)
    assert report_row["days_since_report"].iloc[0] == pytest.approx(0.0)
    assert after_report_row["days_since_report"].iloc[0] == pytest.approx(1.0)


@pytest.mark.slow
def test_pipeline_hk_file_fundamentals_recomputes_valuation_age_days(
    tmp_path, monkeypatch
):
    dates = pd.date_range("2025-03-10", periods=35, freq="B")
    symbols = ["00005.HK", "00011.HK"]
    frames = _build_frames(symbols, dates, include_amount=True)
    basic_df = pd.DataFrame(
        {"symbol": symbols, "name": ["HSBC", "Hang Seng"], "list_date": ["20000101", "20000101"]}
    )

    fundamentals_path = tmp_path / "pit_fundamentals_with_provider.parquet"
    pd.DataFrame(
        {
            "trade_date": pd.to_datetime(
                ["2025-03-20", "2025-04-10", "2025-03-20", "2025-04-10"]
            ),
            "symbol": ["00005.HK", "00005.HK", "00011.HK", "00011.HK"],
            "market_cap": [1000.0, 1100.0, 1500.0, 1550.0],
            "pe_ttm": [8.0, 8.5, 10.0, 10.2],
            "pb": [1.1, 1.15, 1.4, 1.45],
            "valuation_trade_date": pd.to_datetime(
                ["2025-03-18", "2025-04-09", "2025-03-19", "2025-04-08"]
            ),
            "valuation_age_days": [999.0, 999.0, 999.0, 999.0],
        }
    ).to_parquet(fundamentals_path, index=False)

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
            "features": ["market_cap", "pe_ttm", "pb"],
            "auto_add_features": False,
            "allow_missing_features": False,
            "ffill": True,
            "required": True,
        },
        "label": {
            "horizon_mode": "fixed",
            "horizon_days": 1,
            "shift_days": 0,
            "target_col": "future_return",
        },
        "features": {
            "list": ["market_cap", "valuation_age_days"],
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
            "run_name": "hk-file-fundamentals-valuation-age",
            "walk_forward": {"enabled": False},
        },
        "backtest": {"enabled": False},
    }

    run_dir = _run_pipeline(tmp_path, monkeypatch, config, frames, basic_df=basic_df)
    dataset = pd.read_parquet(run_dir / "dataset.parquet").reset_index()
    dataset["trade_date"] = pd.to_datetime(dataset["trade_date"])

    report_row = dataset[
        (dataset["symbol"] == "00005.HK") & (dataset["trade_date"] == "2025-04-10")
    ]
    after_report_row = dataset[
        (dataset["symbol"] == "00005.HK") & (dataset["trade_date"] == "2025-04-11")
    ]

    assert report_row["valuation_age_days"].iloc[0] == pytest.approx(1.0)
    assert after_report_row["valuation_age_days"].iloc[0] == pytest.approx(2.0)
    assert report_row["valuation_age_days"].iloc[0] != pytest.approx(999.0)


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
def test_pipeline_hk_file_fundamentals_supports_growth_and_structure_ratios(
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
            "revenue": [100.0, 130.0, 200.0, 220.0],
            "net_profit": [10.0, 15.0, 20.0, 18.0],
            "short_term_debt": [30.0, 35.0, 50.0, 48.0],
            "long_term_loans": [10.0, 15.0, 20.0, 22.0],
            "cash_and_equivalents": [25.0, 20.0, 40.0, 35.0],
            "total_assets": [200.0, 220.0, 400.0, 420.0],
            "total_equity": [100.0, 110.0, 220.0, 215.0],
            "accounts_receivable": [20.0, 22.0, 35.0, 36.0],
            "inventory": [15.0, 18.0, 30.0, 32.0],
            "accounts_payable": [12.0, 13.0, 20.0, 19.0],
            "goodwill": [5.0, 6.0, 8.0, 8.0],
        }
    ).to_parquet(fundamentals_path, index=False)

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
            "features": [
                "revenue",
                "net_profit",
                "short_term_debt",
                "long_term_loans",
                "cash_and_equivalents",
                "total_assets",
                "total_equity",
                "accounts_receivable",
                "inventory",
                "accounts_payable",
                "goodwill",
            ],
            "auto_add_features": False,
            "allow_missing_features": True,
            "ffill": True,
            "required": True,
        },
        "label": {
            "horizon_mode": "fixed",
            "horizon_days": 1,
            "shift_days": 0,
            "target_col": "future_return",
        },
        "features": {
            "list": [
                "growth_sales",
                "growth_net_profit",
                "debt",
                "growth_debt",
                "debt_to_assets",
                "debt_to_equity",
                "cash_to_assets",
                "working_capital_to_assets",
                "goodwill_to_assets",
                "net_debt_to_assets",
            ],
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
            "run_name": "hk-file-fundamentals-growth-structure",
            "walk_forward": {"enabled": False},
        },
        "backtest": {"enabled": False},
    }

    run_dir = _run_pipeline(tmp_path, monkeypatch, config, frames, basic_df=basic_df)
    dataset = pd.read_parquet(run_dir / "dataset.parquet").reset_index()
    dataset["trade_date"] = pd.to_datetime(dataset["trade_date"])

    report_row = dataset[
        (dataset["symbol"] == "00005.HK") & (dataset["trade_date"] == "2025-04-10")
    ]

    assert report_row["growth_sales"].iloc[0] == pytest.approx(30.0 / 115.0)
    assert report_row["growth_net_profit"].iloc[0] == pytest.approx(5.0 / 12.5)
    assert report_row["debt"].iloc[0] == pytest.approx(50.0)
    assert report_row["growth_debt"].iloc[0] == pytest.approx(10.0 / 45.0)
    assert report_row["debt_to_assets"].iloc[0] == pytest.approx(50.0 / 220.0)
    assert report_row["debt_to_equity"].iloc[0] == pytest.approx(50.0 / 110.0)
    assert report_row["cash_to_assets"].iloc[0] == pytest.approx(20.0 / 220.0)
    assert report_row["working_capital_to_assets"].iloc[0] == pytest.approx(27.0 / 220.0)
    assert report_row["goodwill_to_assets"].iloc[0] == pytest.approx(6.0 / 220.0)
    assert report_row["net_debt_to_assets"].iloc[0] == pytest.approx(30.0 / 220.0)


def test_pipeline_hk_file_fundamentals_missing_file_fails_before_daily_fetch(tmp_path, monkeypatch):
    fetch_calls = {"count": 0}

    def fake_init_client(self):
        self.client = None

    def fake_fetch_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        fetch_calls["count"] += 1
        return pd.DataFrame()

    monkeypatch.setattr(DataInterface, "_init_client", fake_init_client)
    monkeypatch.setattr(DataInterface, "fetch_daily", fake_fetch_daily)
    monkeypatch.setattr(DataInterface, "load_basic", lambda self, symbols=None: pd.DataFrame())

    missing_path = tmp_path / "missing_pit_fundamentals.parquet"
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
        "fundamentals": {
            "enabled": True,
            "source": "file",
            "file": str(missing_path),
            "column_map": {},
            "features": ["revenue", "net_profit"],
            "auto_add_features": True,
            "ffill": True,
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
            "run_name": "hk-file-fundamentals-missing",
            "walk_forward": {"enabled": False},
        },
        "backtest": {"enabled": False},
    }

    config_path = tmp_path / "config.yml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    with pytest.raises(SystemExit, match=f"Fundamentals file not found: {missing_path}"):
        pipeline.run(str(config_path))

    assert fetch_calls["count"] == 0


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
def test_pipeline_feature_formulas(tmp_path, monkeypatch):
    dates = pd.date_range("2020-01-01", periods=20, freq="B")
    symbols = ["AAA", "BBB"]
    close_map = {
        "AAA": np.arange(1, len(dates) + 1, dtype=float),
        "BBB": np.full(len(dates), 2.0),
    }
    vol_map = {
        "AAA": np.arange(1, len(dates) + 1, dtype=float) * 10.0,
        "BBB": np.full(len(dates), 5.0),
    }
    frames = _build_frames(symbols, dates, close_map=close_map, vol_map=vol_map, include_amount=True)

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
            "min_symbols_per_date": 2,
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
            "list": [
                "sma_3",
                "sma_3_diff",
                "volume_sma3_ratio",
                "ret_3",
                "rv_3",
                "log_vol",
                "vol",
            ],
            "params": {
                "sma_windows": [3],
                "volume_sma_windows": [3],
                "ret_windows": [3],
                "rv_windows": [3],
            },
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
            "run_name": "features",
            "walk_forward": {"enabled": False},
        },
        "backtest": {"enabled": False},
    }

    run_dir = _run_pipeline(tmp_path, monkeypatch, config, frames)
    dataset = pd.read_parquet(run_dir / "dataset.parquet").reset_index()
    aaa = dataset[dataset["symbol"] == "AAA"].sort_values("trade_date").reset_index(drop=True)

    close = pd.Series(close_map["AAA"], index=dates)
    vol = pd.Series(vol_map["AAA"], index=dates)
    sma3 = close.rolling(3).mean()
    sma3_diff = sma3.pct_change()
    vol_ratio = vol / vol.rolling(3).mean()
    ret3 = close.pct_change(3)
    rv3 = close.pct_change().rolling(3).std(ddof=0)
    log_vol = np.log1p(vol)
    expected = pd.DataFrame(
        {
            "trade_date": dates,
            "sma_3": sma3,
            "sma_3_diff": sma3_diff,
            "volume_sma3_ratio": vol_ratio,
            "ret_3": ret3,
            "rv_3": rv3,
            "log_vol": log_vol,
        }
    ).dropna(subset=["sma_3", "sma_3_diff", "volume_sma3_ratio", "ret_3", "rv_3", "log_vol"])
    expected = expected[expected["trade_date"].isin(aaa["trade_date"])].reset_index(drop=True)

    np.testing.assert_allclose(aaa["sma_3"].to_numpy(), expected["sma_3"].to_numpy(), rtol=1e-6, atol=1e-6)
    np.testing.assert_allclose(
        aaa["sma_3_diff"].to_numpy(), expected["sma_3_diff"].to_numpy(), rtol=1e-6, atol=1e-6
    )
    np.testing.assert_allclose(
        aaa["volume_sma3_ratio"].to_numpy(),
        expected["volume_sma3_ratio"].to_numpy(),
        rtol=1e-6,
        atol=1e-6,
    )
    np.testing.assert_allclose(aaa["ret_3"].to_numpy(), expected["ret_3"].to_numpy(), rtol=1e-6, atol=1e-6)
    np.testing.assert_allclose(aaa["rv_3"].to_numpy(), expected["rv_3"].to_numpy(), rtol=1e-6, atol=1e-6)
    np.testing.assert_allclose(aaa["log_vol"].to_numpy(), expected["log_vol"].to_numpy(), rtol=1e-6, atol=1e-6)
