import importlib

import pandas as pd
import pytest

MERGE_SCRIPT = importlib.reload(
    importlib.import_module("cstree.research.hk_selected_provider_valuation_merge")
)


class _FakeRQDataClient:
    def __init__(self, frames_by_symbol: dict[str, pd.DataFrame]):
        self.frames_by_symbol = frames_by_symbol
        self.calls: list[tuple] = []

    def get_factor(self, order_book_id, factors, start_date, end_date, **kwargs):
        self.calls.append((order_book_id, tuple(factors), start_date, end_date, kwargs))
        return self.frames_by_symbol[order_book_id].copy()


def _hk_factor_frame(order_book_id: str, market_caps: list[float]) -> pd.DataFrame:
    index = pd.MultiIndex.from_product(
        [[order_book_id], pd.to_datetime(["2025-01-02", "2025-01-03"])],
        names=["order_book_id", "date"],
    )
    return pd.DataFrame(
        {
            "hk_total_market_val": market_caps,
            "pe_ratio_ttm": [8.0, 8.1],
            "pb_ratio_ttm": [1.1, 1.2],
        },
        index=index,
    )


def test_fetch_provider_frame_normalizes_to_symbol_from_real_fundamentals_fetch(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    client = _FakeRQDataClient(
        {
            "00005.XHKG": _hk_factor_frame("00005.XHKG", [1000.0, 1010.0]),
            "00011.XHKG": _hk_factor_frame("00011.XHKG", [1500.0, 1515.0]),
        }
    )
    cfg = {
        "data": {
            "provider": "rqdata",
            "rqdata": {"market": "hk"},
        },
        "fundamentals": {
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
        },
    }

    provider_df = MERGE_SCRIPT.fetch_provider_frame(
        symbols=["00005.HK", "00011.HK"],
        start_date="20250102",
        end_date="20250103",
        cache_dir=cache_dir,
        cfg=cfg,
        client=client,
    ).sort_values(["symbol", "trade_date"]).reset_index(drop=True)

    assert client.calls == [
        (
            "00005.XHKG",
            ("hk_total_market_val", "pe_ratio_ttm", "pb_ratio_ttm"),
            "20250102",
            "20250103",
            {"market": "hk"},
        ),
        (
            "00011.XHKG",
            ("hk_total_market_val", "pe_ratio_ttm", "pb_ratio_ttm"),
            "20250102",
            "20250103",
            {"market": "hk"},
        ),
    ]
    assert provider_df["trade_date"].tolist() == [
        "20250102",
        "20250103",
        "20250102",
        "20250103",
    ]
    assert provider_df["symbol"].tolist() == [
        "00005.HK",
        "00005.HK",
        "00011.HK",
        "00011.HK",
    ]
    assert "ts_code" not in provider_df.columns
    assert {"market_cap", "pe_ttm", "pb"}.issubset(provider_df.columns)


def test_merge_frames_asof_uses_latest_provider_row_per_symbol():
    pit_df = pd.DataFrame(
        {
            "trade_date": ["20250320", "20250410", "20250320", "20250410", "20250320"],
            "symbol": ["00005.HK", "00005.HK", "00011.HK", "00011.HK", "00012.HK"],
            "revenue": [100.0, 130.0, 200.0, 220.0, 50.0],
        }
    )
    provider_df = pd.DataFrame(
        {
            "trade_date": ["20250318", "20250409", "20250319"],
            "symbol": ["00005.HK", "00005.HK", "00011.HK"],
            "market_cap": [1000.0, 1100.0, 1500.0],
            "pe_ttm": [8.0, 8.5, 10.0],
            "pb": [1.1, 1.15, 1.4],
        }
    )

    merged = MERGE_SCRIPT.merge_frames(pit_df, provider_df, merge_mode="asof")
    merged = merged.sort_values(["symbol", "trade_date"]).reset_index(drop=True)

    row_00005_report = merged[(merged["symbol"] == "00005.HK") & (merged["trade_date"] == "20250320")]
    row_00005_next = merged[(merged["symbol"] == "00005.HK") & (merged["trade_date"] == "20250410")]
    row_00011_report = merged[(merged["symbol"] == "00011.HK") & (merged["trade_date"] == "20250320")]
    row_00011_next = merged[(merged["symbol"] == "00011.HK") & (merged["trade_date"] == "20250410")]
    row_missing = merged[(merged["symbol"] == "00012.HK") & (merged["trade_date"] == "20250320")]

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
