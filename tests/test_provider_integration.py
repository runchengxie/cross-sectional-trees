import os

import pandas as pd
import pytest

from csml.data_interface import DataInterface


@pytest.mark.integration
def test_rqdata_provider_fetch_hk_fundamentals_real_account(tmp_path):
    if os.getenv("CSML_RUN_PROVIDER_INTEGRATION") != "1":
        pytest.skip("Set CSML_RUN_PROVIDER_INTEGRATION=1 to enable real provider integration tests.")

    username = os.getenv("RQDATA_USERNAME") or os.getenv("RQDATA_USER")
    password = os.getenv("RQDATA_PASSWORD")
    if not username or not password:
        pytest.skip("Set RQDATA_USERNAME/RQDATA_PASSWORD to run this integration test.")

    symbol = os.getenv("CSML_INTEGRATION_RQDATA_HK_SYMBOL", "00005.HK")
    end = (pd.Timestamp.now().normalize() - pd.Timedelta(days=2)).strftime("%Y%m%d")
    start = (pd.Timestamp.now().normalize() - pd.Timedelta(days=45)).strftime("%Y%m%d")

    di = DataInterface(
        market="hk",
        data_cfg={
            "provider": "rqdata",
            "rqdata": {
                "market": "hk",
                "init": {"username": username, "password": password},
            },
            "retry": {"max_attempts": 1},
        },
        cache_dir=tmp_path / "cache",
    )

    frame = di.fetch_fundamentals(
        symbol,
        start,
        end,
        {
            "source": "provider",
            "endpoint": "get_factor",
            "fields": ["hk_total_market_val", "pe_ratio_ttm", "pb_ratio_ttm"],
            "column_map": {
                "trade_date": "trade_date",
                "ts_code": "ts_code",
                "market_cap": "hk_total_market_val",
                "pe_ttm": "pe_ratio_ttm",
                "pb": "pb_ratio_ttm",
            },
        },
    )
    assert isinstance(frame, pd.DataFrame)
    assert not frame.empty
    assert {"trade_date", "ts_code", "market_cap", "pe_ttm", "pb"}.issubset(frame.columns)
