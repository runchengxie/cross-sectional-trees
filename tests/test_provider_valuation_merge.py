import importlib

import pandas as pd
import pytest


MERGE_SCRIPT = importlib.reload(
    importlib.import_module("csml.research.hk_selected_provider_valuation_merge")
)


def test_merge_frames_asof_uses_latest_provider_row_per_symbol():
    pit_df = pd.DataFrame(
        {
            "trade_date": ["20250320", "20250410", "20250320", "20250410", "20250320"],
            "ts_code": ["00005.HK", "00005.HK", "00011.HK", "00011.HK", "00012.HK"],
            "revenue": [100.0, 130.0, 200.0, 220.0, 50.0],
        }
    )
    provider_df = pd.DataFrame(
        {
            "trade_date": ["20250318", "20250409", "20250319"],
            "ts_code": ["00005.HK", "00005.HK", "00011.HK"],
            "market_cap": [1000.0, 1100.0, 1500.0],
            "pe_ttm": [8.0, 8.5, 10.0],
            "pb": [1.1, 1.15, 1.4],
        }
    )

    merged = MERGE_SCRIPT.merge_frames(pit_df, provider_df, merge_mode="asof")
    merged = merged.sort_values(["ts_code", "trade_date"]).reset_index(drop=True)

    row_00005_report = merged[(merged["ts_code"] == "00005.HK") & (merged["trade_date"] == "20250320")]
    row_00005_next = merged[(merged["ts_code"] == "00005.HK") & (merged["trade_date"] == "20250410")]
    row_00011_report = merged[(merged["ts_code"] == "00011.HK") & (merged["trade_date"] == "20250320")]
    row_00011_next = merged[(merged["ts_code"] == "00011.HK") & (merged["trade_date"] == "20250410")]
    row_missing = merged[(merged["ts_code"] == "00012.HK") & (merged["trade_date"] == "20250320")]

    assert row_00005_report["market_cap"].iloc[0] == pytest.approx(1000.0)
    assert row_00005_report["valuation_trade_date"].iloc[0] == "20250318"
    assert row_00005_report["valuation_age_days"].iloc[0] == pytest.approx(2.0)

    assert row_00005_next["market_cap"].iloc[0] == pytest.approx(1100.0)
    assert row_00005_next["valuation_trade_date"].iloc[0] == "20250409"
    assert row_00005_next["valuation_age_days"].iloc[0] == pytest.approx(1.0)

    expected_age = (
        pd.Timestamp("2025-04-10") - pd.Timestamp("2025-03-19")
    ).days
    assert row_00011_report["valuation_trade_date"].iloc[0] == "20250319"
    assert row_00011_report["valuation_age_days"].iloc[0] == pytest.approx(1.0)
    assert row_00011_next["valuation_age_days"].iloc[0] == pytest.approx(float(expected_age))

    assert pd.isna(row_missing["market_cap"].iloc[0])
    assert pd.isna(row_missing["valuation_trade_date"].iloc[0])
    assert pd.isna(row_missing["valuation_age_days"].iloc[0])
