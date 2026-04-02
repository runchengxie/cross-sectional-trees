import numpy as np
import pandas as pd
import pytest

from tests._pipeline_test_utils import _build_frames, _run_pipeline


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
