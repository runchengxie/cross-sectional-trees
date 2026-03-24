import pandas as pd

from csml import data_providers


def _daily_frame(symbol: str, start: str, end: str, *, close_offset: float = 0.0) -> pd.DataFrame:
    dates = pd.date_range(pd.to_datetime(start), pd.to_datetime(end), freq="D")
    rows = []
    for idx, trade_date in enumerate(dates):
        rows.append(
            {
                "trade_date": trade_date.strftime("%Y%m%d"),
                "ts_code": symbol,
                "close": close_offset + float(idx + 1),
                "vol": 1000.0 + idx,
                "amount": 10000.0 + idx,
            }
        )
    return pd.DataFrame(rows)


def test_fetch_daily_symbol_cache_refresh_window_merges_monotonic(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    symbol = "AAA"
    cache_file = cache_dir / "us_tushare_daily_AAA.parquet"

    cached = _daily_frame(symbol, "20200101", "20200105", close_offset=0.0)
    cached.to_parquet(cache_file)

    fetch_ranges = []

    def fake_fetch(provider, market, symbol_value, start_date, end_date, client, data_cfg):
        fetch_ranges.append((start_date, end_date))
        return _daily_frame(symbol_value, start_date, end_date, close_offset=100.0)

    monkeypatch.setattr(data_providers, "_fetch_daily_from_provider", fake_fetch)

    data_cfg = {
        "provider": "tushare",
        "cache_mode": "symbol",
        "cache_refresh_days": 2,
        "cache_refresh_on_hit": False,
    }
    result = data_providers.fetch_daily(
        "us",
        symbol,
        "20200102",
        "20200107",
        cache_dir,
        client=None,
        data_cfg=data_cfg,
    )

    assert fetch_ranges == [("20200104", "20200107")]
    assert result["trade_date"].tolist() == [
        "20200102",
        "20200103",
        "20200104",
        "20200105",
        "20200106",
        "20200107",
    ]
    assert result["trade_date"].is_monotonic_increasing
    assert result["trade_date"].nunique() == len(result)

    merged = pd.read_parquet(cache_file).sort_values("trade_date").reset_index(drop=True)
    refreshed_close = float(merged.loc[merged["trade_date"] == "20200104", "close"].iloc[0])
    assert refreshed_close > 100.0


def test_fetch_daily_symbol_cache_refresh_on_hit_triggers_tail_refresh(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    symbol = "AAA"
    cache_file = cache_dir / "us_tushare_daily_AAA.parquet"

    cached = _daily_frame(symbol, "20200101", "20200105", close_offset=0.0)
    cached.to_parquet(cache_file)

    fetch_ranges = []

    def fake_fetch(provider, market, symbol_value, start_date, end_date, client, data_cfg):
        fetch_ranges.append((start_date, end_date))
        return _daily_frame(symbol_value, start_date, end_date, close_offset=200.0)

    monkeypatch.setattr(data_providers, "_fetch_daily_from_provider", fake_fetch)

    data_cfg = {
        "provider": "tushare",
        "cache_mode": "symbol",
        "cache_refresh_days": 2,
        "cache_refresh_on_hit": True,
    }
    result = data_providers.fetch_daily(
        "us",
        symbol,
        "20200102",
        "20200105",
        cache_dir,
        client=None,
        data_cfg=data_cfg,
    )

    assert fetch_ranges == [("20200104", "20200105")]
    assert result["trade_date"].tolist() == [
        "20200102",
        "20200103",
        "20200104",
        "20200105",
    ]


def test_fetch_daily_symbol_cache_skips_small_leading_calendar_gap(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    symbol = "AAA"
    cache_file = cache_dir / "us_tushare_daily_AAA.parquet"

    cached = _daily_frame(symbol, "20200102", "20200105", close_offset=0.0)
    cached.to_parquet(cache_file)

    fetch_ranges = []

    def fake_fetch(provider, market, symbol_value, start_date, end_date, client, data_cfg):
        fetch_ranges.append((start_date, end_date))
        return _daily_frame(symbol_value, start_date, end_date, close_offset=300.0)

    monkeypatch.setattr(data_providers, "_fetch_daily_from_provider", fake_fetch)

    data_cfg = {
        "provider": "tushare",
        "cache_mode": "symbol",
        "cache_refresh_days": 0,
        "cache_refresh_on_hit": False,
    }
    result = data_providers.fetch_daily(
        "us",
        symbol,
        "20200101",
        "20200105",
        cache_dir,
        client=None,
        data_cfg=data_cfg,
    )

    assert fetch_ranges == []
    assert result["trade_date"].tolist() == [
        "20200102",
        "20200103",
        "20200104",
        "20200105",
    ]


def test_fetch_daily_symbol_cache_fetches_large_leading_gap(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    symbol = "AAA"
    cache_file = cache_dir / "us_tushare_daily_AAA.parquet"

    cached = _daily_frame(symbol, "20200110", "20200112", close_offset=0.0)
    cached.to_parquet(cache_file)

    fetch_ranges = []

    def fake_fetch(provider, market, symbol_value, start_date, end_date, client, data_cfg):
        fetch_ranges.append((start_date, end_date))
        return _daily_frame(symbol_value, start_date, end_date, close_offset=400.0)

    monkeypatch.setattr(data_providers, "_fetch_daily_from_provider", fake_fetch)

    data_cfg = {
        "provider": "tushare",
        "cache_mode": "symbol",
        "cache_refresh_days": 0,
        "cache_refresh_on_hit": False,
    }
    result = data_providers.fetch_daily(
        "us",
        symbol,
        "20200101",
        "20200112",
        cache_dir,
        client=None,
        data_cfg=data_cfg,
    )

    assert fetch_ranges == [("20200101", "20200110")]
    assert result["trade_date"].tolist() == [
        "20200101",
        "20200102",
        "20200103",
        "20200104",
        "20200105",
        "20200106",
        "20200107",
        "20200108",
        "20200109",
        "20200110",
        "20200111",
        "20200112",
    ]


def test_fetch_daily_reads_from_local_asset_dir_without_remote_fetch(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    asset_dir = tmp_path / "daily_assets"
    data_dir = asset_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    symbol = "AAA"

    pd.DataFrame(
        {
            "trade_date": ["20200101", "20200102", "20200103"],
            "ts_code": [symbol, symbol, symbol],
            "close": [10.0, 11.0, 12.0],
            "volume": [100.0, 110.0, 120.0],
            "total_turnover": [1000.0, 1100.0, 1200.0],
        }
    ).to_parquet(data_dir / f"{symbol}.parquet")

    def fake_fetch(*args, **kwargs):
        raise AssertionError("remote provider should not be called when local asset is configured")

    monkeypatch.setattr(data_providers, "_fetch_daily_rqdata", fake_fetch)

    result = data_providers.fetch_daily(
        "hk",
        symbol,
        "20200102",
        "20200103",
        cache_dir,
        client=None,
        data_cfg={
            "provider": "rqdata",
            "cache_mode": "symbol",
            "cache_refresh_days": 0,
            "cache_refresh_on_hit": False,
            "column_map": {
                "trade_date": "trade_date",
                "ts_code": "ts_code",
                "close": "close",
                "vol": "volume",
                "amount": "total_turnover",
            },
            "rqdata": {
                "daily_asset_dir": str(asset_dir),
            },
        },
    )

    assert result["trade_date"].tolist() == ["20200102", "20200103"]
    assert result["close"].tolist() == [11.0, 12.0]


def test_fetch_daily_derives_tr_close_from_local_ex_factors(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    asset_dir = tmp_path / "daily_assets"
    ex_dir = tmp_path / "ex_factors"
    (asset_dir / "data").mkdir(parents=True, exist_ok=True)
    (ex_dir / "data").mkdir(parents=True, exist_ok=True)
    symbol = "AAA"

    pd.DataFrame(
        {
            "trade_date": ["20200101", "20200102", "20200103", "20200106"],
            "ts_code": [symbol, symbol, symbol, symbol],
            "close": [10.0, 10.0, 8.0, 9.0],
            "volume": [100.0, 100.0, 100.0, 100.0],
            "total_turnover": [1000.0, 1000.0, 800.0, 900.0],
        }
    ).to_parquet(asset_dir / "data" / f"{symbol}.parquet")
    pd.DataFrame(
        {
            "ex_date": [pd.Timestamp("2020-01-03")],
            "ex_cum_factor": [1.25],
        }
    ).to_parquet(ex_dir / "data" / f"{symbol}.parquet")

    def fake_fetch(*args, **kwargs):
        raise AssertionError("remote provider should not be called when local asset is configured")

    monkeypatch.setattr(data_providers, "_fetch_daily_rqdata", fake_fetch)

    result = data_providers.fetch_daily(
        "hk",
        symbol,
        "20200101",
        "20200106",
        cache_dir,
        client=None,
        data_cfg={
            "provider": "rqdata",
            "cache_mode": "symbol",
            "cache_refresh_days": 0,
            "cache_refresh_on_hit": False,
            "column_map": {
                "trade_date": "trade_date",
                "ts_code": "ts_code",
                "close": "close",
                "vol": "volume",
                "amount": "total_turnover",
            },
            "rqdata": {
                "daily_asset_dir": str(asset_dir),
                "ex_factors_dir": str(ex_dir),
            },
        },
    )

    assert result["tr_close"].round(4).tolist() == [10.0, 10.0, 10.0, 11.25]


def test_fetch_daily_backfills_tr_close_for_existing_cache(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    ex_dir = tmp_path / "ex_factors"
    (ex_dir / "data").mkdir(parents=True, exist_ok=True)
    symbol = "AAA"
    cache_file = cache_dir / "hk_rqdata_daily_AAA.parquet"

    pd.DataFrame(
        {
            "trade_date": ["20200101", "20200102", "20200103"],
            "ts_code": [symbol, symbol, symbol],
            "symbol": [symbol, symbol, symbol],
            "close": [10.0, 10.0, 8.0],
            "vol": [100.0, 100.0, 100.0],
            "amount": [1000.0, 1000.0, 800.0],
        }
    ).to_parquet(cache_file)
    pd.DataFrame(
        {
            "ex_date": [pd.Timestamp("2020-01-03")],
            "ex_cum_factor": [1.25],
        }
    ).to_parquet(ex_dir / "data" / f"{symbol}.parquet")

    result = data_providers.fetch_daily(
        "hk",
        symbol,
        "20200101",
        "20200103",
        cache_dir,
        client=None,
        data_cfg={
            "provider": "rqdata",
            "cache_mode": "symbol",
            "cache_refresh_days": 0,
            "cache_refresh_on_hit": False,
            "rqdata": {
                "ex_factors_dir": str(ex_dir),
            },
        },
    )

    assert result["tr_close"].round(4).tolist() == [10.0, 10.0, 10.0]
    cached = pd.read_parquet(cache_file)
    assert "tr_close" in cached.columns
    assert cached["tr_close"].round(4).tolist() == [10.0, 10.0, 10.0]


class _FakeRQInstrument:
    def __init__(self, listed_date: str):
        self.listed_date = listed_date


class _FakeRQDailyClient:
    def __init__(self, listed_date: str):
        self.listed_date = listed_date
        self.price_calls: list[tuple[str, str, str, str, dict]] = []

    def instruments(self, order_book_id, market=None):
        return _FakeRQInstrument(self.listed_date)

    def get_price(self, order_book_id, start_date, end_date, frequency, **kwargs):
        self.price_calls.append((order_book_id, start_date, end_date, frequency, kwargs))
        return pd.DataFrame(
            {
                "close": [10.0, 11.0],
                "volume": [100.0, 110.0],
                "total_turnover": [1000.0, 1100.0],
            },
            index=pd.to_datetime(["2015-03-20", "2015-03-23"]),
        )


def test_fetch_daily_rqdata_clamps_start_date_to_listing_date(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    data_providers._RQDATA_LISTED_DATE_CACHE.clear()
    client = _FakeRQDailyClient("2015-03-20")

    result = data_providers.fetch_daily(
        "hk",
        "01468.HK",
        "20150101",
        "20151231",
        cache_dir,
        client=client,
        data_cfg={
            "provider": "rqdata",
            "cache_mode": "range",
            "rqdata": {"market": "hk", "skip_suspended": True},
        },
    )

    assert client.price_calls == [
        (
            "01468.XHKG",
            "20150320",
            "20151231",
            "1d",
            {
                "fields": ["close", "volume", "total_turnover"],
                "skip_suspended": True,
                "market": "hk",
            },
        )
    ]
    assert result["trade_date"].tolist() == ["20150320", "20150323"]


def test_fetch_daily_rqdata_returns_empty_when_symbol_lists_after_requested_range(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    data_providers._RQDATA_LISTED_DATE_CACHE.clear()
    client = _FakeRQDailyClient("2016-01-05")

    result = data_providers.fetch_daily(
        "hk",
        "01468.HK",
        "20150101",
        "20151231",
        cache_dir,
        client=client,
        data_cfg={
            "provider": "rqdata",
            "cache_mode": "range",
            "rqdata": {"market": "hk", "skip_suspended": True},
        },
    )

    assert client.price_calls == []
    assert result.empty
