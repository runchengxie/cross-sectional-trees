import pandas as pd
import pytest

from csml import data_providers


class _FakeRQDataClient:
    def __init__(self, frame: pd.DataFrame):
        self.frame = frame
        self.calls: list[tuple] = []

    def get_factor(self, order_book_id, factors, start_date, end_date, **kwargs):
        self.calls.append((order_book_id, tuple(factors), start_date, end_date, kwargs))
        return self.frame.copy()


def _hk_factor_frame() -> pd.DataFrame:
    index = pd.MultiIndex.from_product(
        [["00005.XHKG"], pd.to_datetime(["2025-01-02", "2025-01-03"])],
        names=["order_book_id", "date"],
    )
    return pd.DataFrame(
        {
            "hk_total_market_val": [1000.0, 1010.0],
            "pe_ratio_ttm": [8.0, 8.1],
            "pb_ratio_ttm": [1.1, 1.2],
        },
        index=index,
    )


def test_fetch_fundamentals_rqdata_hk_provider_standardizes_and_caches(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    client = _FakeRQDataClient(_hk_factor_frame())
    data_cfg = {
        "provider": "rqdata",
        "rqdata": {"market": "hk"},
    }
    fundamentals_cfg = {
        "endpoint": "get_factor",
        "fields": ["hk_total_market_val", "pe_ratio_ttm", "pb_ratio_ttm"],
        "column_map": {
            "trade_date": "trade_date",
            "symbol": "symbol",
            "market_cap": "hk_total_market_val",
            "pe_ttm": "pe_ratio_ttm",
            "pb": "pb_ratio_ttm",
        },
    }

    first = data_providers.fetch_fundamentals(
        "hk",
        "00005.HK",
        "20250102",
        "20250103",
        cache_dir,
        client,
        data_cfg,
        fundamentals_cfg,
    )
    second = data_providers.fetch_fundamentals(
        "hk",
        "00005.HK",
        "20250102",
        "20250103",
        cache_dir,
        client,
        data_cfg,
        fundamentals_cfg,
    )

    assert client.calls == [
        (
            "00005.XHKG",
            ("hk_total_market_val", "pe_ratio_ttm", "pb_ratio_ttm"),
            "20250102",
            "20250103",
            {"market": "hk"},
        )
    ]
    assert first.equals(second)
    assert first["trade_date"].tolist() == ["20250102", "20250103"]
    assert first["symbol"].tolist() == ["00005.HK", "00005.HK"]
    assert "ts_code" not in first.columns
    assert {"market_cap", "pe_ttm", "pb"}.issubset(first.columns)
    assert len(list(cache_dir.glob("hk_rqdata_fundamentals_*.parquet"))) == 1


def test_fetch_fundamentals_cache_key_tracks_field_config(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    client = _FakeRQDataClient(_hk_factor_frame())
    data_cfg = {
        "provider": "rqdata",
        "rqdata": {"market": "hk"},
    }
    base_cfg = {
        "endpoint": "get_factor",
        "column_map": {
            "trade_date": "trade_date",
            "symbol": "symbol",
            "market_cap": "hk_total_market_val",
        },
    }

    data_providers.fetch_fundamentals(
        "hk",
        "00005.HK",
        "20250102",
        "20250103",
        cache_dir,
        client,
        data_cfg,
        {**base_cfg, "fields": ["hk_total_market_val"]},
    )
    data_providers.fetch_fundamentals(
        "hk",
        "00005.HK",
        "20250102",
        "20250103",
        cache_dir,
        client,
        data_cfg,
        {**base_cfg, "fields": ["hk_total_market_val", "pe_ratio_ttm"]},
    )

    assert len(client.calls) == 2
    assert len(list(cache_dir.glob("hk_rqdata_fundamentals_*.parquet"))) == 2


def test_fetch_fundamentals_rqdata_non_hk_market_rejected(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    client = _FakeRQDataClient(_hk_factor_frame())

    with pytest.raises(ValueError, match="market='hk'"):
        data_providers.fetch_fundamentals(
            "legacy-market",
            "AAPL",
            "20250102",
            "20250103",
            cache_dir,
            client,
            {"provider": "rqdata"},
            {"endpoint": "get_factor"},
        )
