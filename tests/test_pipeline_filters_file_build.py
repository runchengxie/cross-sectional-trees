import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from cstree import pipeline
from cstree.data_interface import DataInterface
from cstree.data_tools import rqdata_assets
from cstree.pipeline.fundamentals_enrichment import apply_fundamentals_enrichment
from tests._pipeline_test_utils import _build_frames, _run_pipeline


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


def test_file_fundamentals_reads_and_merges_only_needed_columns(tmp_path, monkeypatch):
    fundamentals_path = tmp_path / "pipeline_fundamentals.parquet"
    pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2025-01-31", "2025-02-28"]),
            "symbol": ["00005.HK", "00005.HK"],
            "revenue": [100.0, 120.0],
            "operating_revenue": [95.0, 118.0],
            "net_profit": [10.0, 12.0],
            "unused_wide_col": [1.0, 2.0],
        }
    ).to_parquet(fundamentals_path, index=False)

    original_read_parquet = pd.read_parquet
    read_columns = {}

    def recording_read_parquet(path, *args, **kwargs):
        if Path(path) == fundamentals_path:
            read_columns["columns"] = kwargs.get("columns")
        return original_read_parquet(path, *args, **kwargs)

    monkeypatch.setattr(pd, "read_parquet", recording_read_parquet)

    panel_df = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2025-02-28", "2025-03-03"]),
            "symbol": ["00005.HK", "00005.HK"],
            "close": [10.0, 10.5],
        }
    )

    result = apply_fundamentals_enrichment(
        panel_df=panel_df,
        data_interface=object(),
        symbols=["00005.HK"],
        start_date="20250101",
        end_date="20250331",
        market="hk",
        data_cfg={},
        fundamentals_cfg={
            "enabled": True,
            "source": "file",
            "file": str(fundamentals_path),
            "column_map": {},
            "features": [],
        },
        requested_features=["growth_sales", "profit_margin", "days_since_report"],
        fundamentals_enabled=True,
        fundamentals_source="file",
        fundamentals_file_path=fundamentals_path,
        fundamentals_ffill=True,
        fundamentals_ffill_limit=None,
        fundamentals_log_mcap=False,
        fundamentals_mcap_col="market_cap",
        fundamentals_log_mcap_col="log_mcap",
        fundamentals_auto_add=False,
        provider_overlay_enabled=False,
        provider_overlay_cfg={},
        provider_overlay_auto_add=False,
        provider_overlay_features=[],
    )

    assert read_columns["columns"] is not None
    assert "unused_wide_col" not in read_columns["columns"]
    assert "unused_wide_col" not in result["df"].columns
    assert "revenue" not in result["df"].columns
    assert "growth_sales" in result["df"].columns
    assert "profit_margin" in result["df"].columns
    assert "days_since_report" in result["df"].columns
