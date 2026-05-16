import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import yaml

from cstree import data_providers
from cstree.data_tools import rqdata_assets

from tests.rqdata_assets._fakes import (
    _FakeRQDailyMirrorClient,
    _FakeRQValuationClient,
    _FakeRQValuationTradeDateColumnClient,
    _FakeRQExchangeRateClient,
    _FakeRQExFactorClient,
    _FakeRQDividendClient,
    _FakeRQSharesClient,
    _QuotaRQDailyMirrorClient,
    _SplitBatchRQDailyMirrorClient,
)


class _PermissionDeniedDailyClient(_FakeRQDailyMirrorClient):
    def get_price(self, order_book_id, start_date, end_date, frequency, **kwargs):
        self.price_calls.append(
            {
                "order_book_id": order_book_id,
                "start_date": start_date,
                "end_date": end_date,
                "frequency": frequency,
                "kwargs": dict(kwargs),
            }
        )
        raise RuntimeError(
            "no permission to access day bar for instruments with type ETF, please contact RiceQuant"
        )


def test_mirror_hk_daily_writes_manifest_and_assets(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    data_providers._RQDATA_LISTED_DATE_CACHE.clear()

    client = _FakeRQDailyMirrorClient()
    args = SimpleNamespace(
        config=None,
        username=None,
        password=None,
        start_date="20250101",
        end_date="20250103",
        field=[],
        fields_file=[],
        symbol=["00005.HK", "00011.XHKG"],
        symbols_file=None,
        by_date_file=None,
        limit=None,
        batch_size=20,
        adjust_type=None,
        skip_suspended=None,
        out_root="artifacts/assets/rqdata",
        name="daily_demo",
        resume=False,
        skip_existing=False,
        max_attempts=1,
        backoff_seconds=0.0,
        max_backoff_seconds=0.0,
    )

    assert rqdata_assets.mirror_hk_daily(args, client) == 0

    assert client.price_calls == [
        {
            "order_book_id": ["00005.XHKG", "00011.XHKG"],
            "start_date": "20250101",
            "end_date": "20250103",
            "frequency": "1d",
            "kwargs": {
                "fields": list(rqdata_assets.DEFAULT_HK_DAILY_FIELDS),
                "skip_suspended": True,
                "market": "hk",
            },
        },
    ]

    output_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "daily_demo"
    data = pd.read_parquet(output_dir / "data" / "00005.HK.parquet")
    assert data["trade_date"].tolist() == ["20250102", "20250103"]
    assert data["symbol"].tolist() == ["00005.HK", "00005.HK"]
    assert data["order_book_id"].tolist() == ["00005.XHKG", "00005.XHKG"]
    assert data["total_turnover"].tolist() == [10000.0, 12000.0]

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["dataset"] == "daily"
    assert manifest["api"] == "rqdatac.get_price"
    assert manifest["query"]["start_date"] == "20250101"
    assert manifest["query"]["end_date"] == "20250103"
    assert manifest["query"]["skip_suspended"] is True
    assert manifest["query"]["fields"] == list(rqdata_assets.DEFAULT_HK_DAILY_FIELDS)
    assert manifest["totals"]["symbols_requested"] == 2
    assert manifest["totals"]["symbols_written"] == 2
    assert manifest["missing_symbols"] == []


def test_mirror_hk_daily_provider_permission_preflight_fails_fast(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    data_providers._RQDATA_LISTED_DATE_CACHE.clear()

    client = _PermissionDeniedDailyClient()
    args = SimpleNamespace(
        config=None,
        username=None,
        password=None,
        start_date="20250101",
        end_date="20250103",
        field=[],
        fields_file=[],
        symbol=["02800.HK", "02801.HK"],
        symbols_file=None,
        by_date_file=None,
        limit=None,
        batch_size=20,
        adjust_type=None,
        skip_suspended=None,
        out_root="artifacts/assets/rqdata",
        name="etf_daily_permission_demo",
        resume=False,
        skip_existing=False,
        max_attempts=3,
        backoff_seconds=0.0,
        max_backoff_seconds=0.0,
        provider_permission_preflight=True,
        preflight_symbol=None,
    )

    assert rqdata_assets.mirror_hk_daily(args, client) == 78

    assert client.price_calls == [
        {
            "order_book_id": "02800.XHKG",
            "start_date": "20250101",
            "end_date": "20250103",
            "frequency": "1d",
            "kwargs": {
                "fields": list(rqdata_assets.DEFAULT_HK_DAILY_FIELDS),
                "skip_suspended": True,
                "market": "hk",
            },
        }
    ]

    output_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "etf_daily_permission_demo"
    audit = pd.read_csv(output_dir / "audit.csv")
    assert set(audit["status"]) == {"provider_permission_blocked"}
    assert audit["error"].str.contains("no permission to access day bar").all()

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["status"] == "blocked_provider_permission"
    assert manifest["totals"]["symbols_provider_permission_blocked"] == 2
    assert manifest["provider_permission_blocked_symbols"] == ["02800.HK", "02801.HK"]

def test_mirror_hk_valuation_writes_manifest_and_assets(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    client = _FakeRQValuationClient()
    args = SimpleNamespace(
        config=None,
        username=None,
        password=None,
        start_date="20250101",
        end_date="20250103",
        field=[],
        fields_file=[],
        symbol=["00005.HK", "00011.HK"],
        symbols_file=None,
        by_date_file=None,
        limit=None,
        batch_size=20,
        out_root="artifacts/assets/rqdata",
        name="valuation_demo",
        resume=False,
        skip_existing=False,
        max_attempts=1,
        backoff_seconds=0.0,
        max_backoff_seconds=0.0,
    )

    assert rqdata_assets.mirror_hk_valuation(args, client) == 0

    assert client.calls == [
        {
            "order_book_ids": ["00005.XHKG", "00011.XHKG"],
            "factors": list(rqdata_assets.DEFAULT_HK_VALUATION_FIELDS),
            "start_date": "20250101",
            "end_date": "20250103",
            "kwargs": {"market": "hk"},
        }
    ]

    output_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "valuation" / "valuation_demo"
    data = pd.read_parquet(output_dir / "data" / "00005.HK.parquet")
    assert data["trade_date"].tolist() == ["20250102", "20250103"]
    assert data["symbol"].tolist() == ["00005.HK", "00005.HK"]
    assert data["order_book_id"].tolist() == ["00005.XHKG", "00005.XHKG"]
    assert data["hk_total_market_val"].tolist() == [1000.0, 1010.0]

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["dataset"] == "valuation"
    assert manifest["api"] == "rqdatac.get_factor"
    assert manifest["query"]["start_date"] == "20250101"
    assert manifest["query"]["end_date"] == "20250103"
    assert manifest["query"]["date_column"] == "trade_date"
    assert manifest["query"]["fields"] == list(rqdata_assets.DEFAULT_HK_VALUATION_FIELDS)
    assert manifest["totals"]["symbols_requested"] == 2
    assert manifest["totals"]["symbols_written"] == 2
    assert manifest["missing_symbols"] == []

def test_mirror_hk_valuation_handles_payload_with_existing_trade_date_column(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    client = _FakeRQValuationTradeDateColumnClient()
    args = SimpleNamespace(
        config=None,
        username=None,
        password=None,
        start_date="20260327",
        end_date="20260327",
        field=[],
        fields_file=[],
        symbol=["00005.HK"],
        symbols_file=None,
        by_date_file=None,
        limit=None,
        batch_size=20,
        out_root="artifacts/assets/rqdata",
        name="valuation_trade_date_column_demo",
        resume=False,
        skip_existing=False,
        max_attempts=1,
        backoff_seconds=0.0,
        max_backoff_seconds=0.0,
    )

    assert rqdata_assets.mirror_hk_valuation(args, client) == 0

    output_dir = (
        repo_root
        / "artifacts"
        / "assets"
        / "rqdata"
        / "hk"
        / "valuation"
        / "valuation_trade_date_column_demo"
    )
    data = pd.read_parquet(output_dir / "data" / "00005.HK.parquet")
    assert data["trade_date"].tolist() == ["20260327"]
    assert data["order_book_id"].tolist() == ["00005.XHKG"]
    assert data["hk_total_market_val"].tolist() == [1000.0]

def test_mirror_hk_ex_factors_writes_manifest_and_assets(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    client = _FakeRQExFactorClient()
    args = SimpleNamespace(
        config=None,
        username=None,
        password=None,
        start_date="20250101",
        end_date="20251231",
        symbol=["00005.HK"],
        symbols_file=None,
        by_date_file=None,
        limit=None,
        batch_size=5,
        out_root="artifacts/assets/rqdata",
        name="ex_factor_demo",
        resume=False,
        skip_existing=False,
        max_attempts=1,
        backoff_seconds=0.0,
        max_backoff_seconds=0.0,
    )

    assert rqdata_assets.mirror_hk_ex_factors(args, client) == 0

    assert client.calls == [
        {
            "order_book_ids": ["00005.XHKG"],
            "start_date": "20250101",
            "end_date": "20251231",
            "market": "hk",
        }
    ]

    output_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "ex_factors" / "ex_factor_demo"
    frame = pd.read_parquet(output_dir / "data" / "00005.HK.parquet")
    assert frame["symbol"].tolist() == ["00005.HK", "00005.HK"]
    assert frame["order_book_id"].tolist() == ["00005.XHKG", "00005.XHKG"]
    assert frame["ex_factor"].tolist() == [0.98, 0.97]

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["dataset"] == "ex_factors"
    assert manifest["api"] == "rqdatac.get_ex_factor"
    assert manifest["query"]["start_date"] == "20250101"
    assert manifest["query"]["end_date"] == "20251231"
    assert manifest["query"]["date_column"] == "ex_date"
    assert manifest["totals"]["symbols_written"] == 1

def test_mirror_hk_dividends_tracks_missing_symbols(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    client = _FakeRQDividendClient()
    args = SimpleNamespace(
        config=None,
        username=None,
        password=None,
        start_date="20250101",
        end_date="20251231",
        symbol=["00005.HK", "00011.HK"],
        symbols_file=None,
        by_date_file=None,
        limit=None,
        batch_size=20,
        out_root="artifacts/assets/rqdata",
        name="dividend_demo",
        resume=False,
        skip_existing=False,
        max_attempts=1,
        backoff_seconds=0.0,
        max_backoff_seconds=0.0,
    )

    assert rqdata_assets.mirror_hk_dividends(args, client) == 0

    assert client.calls == [
        {
            "order_book_ids": ["00005.XHKG", "00011.XHKG"],
            "start_date": "20250101",
            "end_date": "20251231",
            "market": "hk",
        }
    ]

    output_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "dividends" / "dividend_demo"
    frame = pd.read_parquet(output_dir / "data" / "00005.HK.parquet")
    assert frame["symbol"].tolist() == ["00005.HK", "00005.HK"]
    assert frame["dividend_cash_before_tax"].tolist() == [0.5, 0.6]

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["dataset"] == "dividends"
    assert manifest["totals"]["symbols_requested"] == 2
    assert manifest["totals"]["symbols_written"] == 1
    assert manifest["missing_symbols"] == ["00011.HK"]

def test_mirror_hk_shares_uses_default_fields(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    client = _FakeRQSharesClient()
    args = SimpleNamespace(
        config=None,
        username=None,
        password=None,
        start_date="20250101",
        end_date="20251231",
        field=[],
        fields_file=[],
        symbol=["00005.HK"],
        symbols_file=None,
        by_date_file=None,
        limit=None,
        batch_size=5,
        out_root="artifacts/assets/rqdata",
        name="shares_demo",
        resume=False,
        skip_existing=False,
        max_attempts=1,
        backoff_seconds=0.0,
        max_backoff_seconds=0.0,
    )

    assert rqdata_assets.mirror_hk_shares(args, client) == 0

    assert client.calls == [
        {
            "order_book_ids": ["00005.XHKG"],
            "start_date": "20250101",
            "end_date": "20251231",
            "fields": list(rqdata_assets.DEFAULT_HK_SHARES_FIELDS),
            "market": "hk",
        }
    ]

    output_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "shares" / "shares_demo"
    frame = pd.read_parquet(output_dir / "data" / "00005.HK.parquet")
    assert frame["symbol"].tolist() == ["00005.HK", "00005.HK"]
    assert frame["total_hk1"].tolist() == [4_800_000_000, 4_900_000_000]

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["dataset"] == "shares"
    assert manifest["query"]["fields"] == list(rqdata_assets.DEFAULT_HK_SHARES_FIELDS)
    assert manifest["query"]["date_column"] == "date"
    assert manifest["totals"]["symbols_written"] == 1

def test_mirror_hk_exchange_rate_writes_single_snapshot_file(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    client = _FakeRQExchangeRateClient()
    args = SimpleNamespace(
        config=None,
        username=None,
        password=None,
        start_date="20250210",
        end_date="20250211",
        field=[],
        fields_file=[],
        out_root="artifacts/assets/rqdata",
        name="exchange_rate_demo",
        resume=False,
        max_attempts=1,
        backoff_seconds=0.0,
        max_backoff_seconds=0.0,
    )

    assert rqdata_assets.mirror_hk_exchange_rate(args, client) == 0

    assert client.calls == [
        {
            "start_date": "20250210",
            "end_date": "20250211",
            "fields": list(rqdata_assets.DEFAULT_HK_EXCHANGE_RATE_FIELDS),
        }
    ]

    output_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "exchange_rate" / "exchange_rate_demo"
    assert (output_dir / "fields.txt").read_text(encoding="utf-8") == (
        "\n".join(rqdata_assets.DEFAULT_HK_EXCHANGE_RATE_FIELDS) + "\n"
    )
    assert (output_dir / "dates.txt").read_text(encoding="utf-8") == "20250210\n20250211\n"
    assert (output_dir / "currency_pairs.txt").read_text(encoding="utf-8") == "HKDCNY\nHKDUSD\n"

    frame = pd.read_parquet(output_dir / "data" / "exchange_rate.parquet")
    assert frame["date"].tolist() == ["20250210", "20250210", "20250211"]
    assert frame["currency_pair"].tolist() == ["HKDCNY", "HKDUSD", "HKDCNY"]

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["dataset"] == "exchange_rate"
    assert manifest["api"] == "rqdatac.get_exchange_rate"
    assert manifest["query"]["start_date"] == "20250210"
    assert manifest["query"]["end_date"] == "20250211"
    assert manifest["query"]["fields"] == list(rqdata_assets.DEFAULT_HK_EXCHANGE_RATE_FIELDS)
    assert manifest["totals"]["rows"] == 3
    assert manifest["totals"]["dates"] == 2
    assert manifest["totals"]["currency_pairs"] == 2

def test_mirror_hk_daily_resume_accepts_legacy_ts_code_storage_and_writes_audit(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    output_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "daily_demo"
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)
    data_providers._RQDATA_LISTED_DATE_CACHE.clear()

    pd.DataFrame(
        {
            "trade_date": ["20250102"],
            "ts_code": ["00005.HK"],
            "order_book_id": ["00005.XHKG"],
            "open": [10.0],
            "high": [11.0],
            "low": [9.5],
            "close": [10.5],
            "volume": [1000.0],
            "total_turnover": [10000.0],
        }
    ).to_parquet(data_dir / "00005.HK.parquet", index=False)
    (output_dir / "fields.txt").write_text(
        "\n".join(rqdata_assets.DEFAULT_HK_DAILY_FIELDS) + "\n",
        encoding="utf-8",
    )
    (output_dir / "symbols.txt").write_text("00005.HK\n00011.HK\n", encoding="utf-8")
    (output_dir / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "daily",
                "query": {
                    "start_date": "20250101",
                    "end_date": "20250103",
                    "frequency": "1d",
                    "adjust_type": None,
                    "skip_suspended": True,
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    client = _FakeRQDailyMirrorClient()
    args = SimpleNamespace(
        config=None,
        username=None,
        password=None,
        start_date="2025-01-01",
        end_date="2025-01-03",
        field=[],
        fields_file=[],
        symbol=["00005.HK", "00011.HK"],
        symbols_file=None,
        by_date_file=None,
        limit=None,
        batch_size=20,
        adjust_type=None,
        skip_suspended=None,
        out_root="artifacts/assets/rqdata",
        name="daily_demo",
        resume=True,
        skip_existing=False,
        max_attempts=1,
        backoff_seconds=0.0,
        max_backoff_seconds=0.0,
    )

    assert rqdata_assets.mirror_hk_daily(args, client) == 0
    assert client.price_calls == [
        {
            "order_book_id": "00011.XHKG",
            "start_date": "20250101",
            "end_date": "20250103",
            "frequency": "1d",
            "kwargs": {
                "fields": list(rqdata_assets.DEFAULT_HK_DAILY_FIELDS),
                "skip_suspended": True,
                "market": "hk",
            },
        }
    ]

    audit = pd.read_csv(output_dir / "audit.csv")
    status_map = dict(zip(audit["symbol"], audit["status"]))
    assert status_map["00005.HK"] == "skipped_existing"
    assert status_map["00011.HK"] == "written"

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["totals"]["symbols_written"] == 2
    assert manifest["totals"]["symbols_newly_written"] == 1
    assert manifest["totals"]["symbols_skipped_existing"] == 1

def test_mirror_hk_daily_stops_on_quota_and_marks_remaining_symbols(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    data_providers._RQDATA_LISTED_DATE_CACHE.clear()

    client = _QuotaRQDailyMirrorClient()
    args = SimpleNamespace(
        config=None,
        username=None,
        password=None,
        start_date="20250101",
        end_date="20250103",
        field=[],
        fields_file=[],
        symbol=["00005.HK", "00011.HK", "00012.HK"],
        symbols_file=None,
        by_date_file=None,
        limit=None,
        batch_size=1,
        adjust_type=None,
        skip_suspended=None,
        out_root="artifacts/assets/rqdata",
        name="daily_quota_demo",
        resume=False,
        skip_existing=False,
        max_attempts=1,
        backoff_seconds=0.0,
        max_backoff_seconds=0.0,
    )

    assert rqdata_assets.mirror_hk_daily(args, client) == 2

    output_dir = (
        repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "daily_quota_demo"
    )
    audit = pd.read_csv(output_dir / "audit.csv")
    status_map = dict(zip(audit["symbol"], audit["status"]))
    assert status_map["00005.HK"] == "written"
    assert status_map["00011.HK"] == "quota_blocked"
    assert status_map["00012.HK"] == "quota_blocked"

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["status"] == "stopped_quota"
    assert manifest["totals"]["symbols_written"] == 1
    assert manifest["totals"]["symbols_quota_blocked"] == 2
    assert manifest["quota_blocked_symbols"] == ["00011.HK", "00012.HK"]

def test_mirror_hk_daily_splits_batch_after_error_and_still_writes_assets(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    client = _SplitBatchRQDailyMirrorClient()
    args = SimpleNamespace(
        config=None,
        username=None,
        password=None,
        start_date="20250101",
        end_date="20250103",
        field=[],
        fields_file=[],
        symbol=["00005.HK", "00011.HK"],
        symbols_file=None,
        by_date_file=None,
        limit=None,
        batch_size=20,
        adjust_type=None,
        skip_suspended=None,
        out_root="artifacts/assets/rqdata",
        name="daily_split_demo",
        resume=False,
        skip_existing=False,
        max_attempts=1,
        backoff_seconds=0.0,
        max_backoff_seconds=0.0,
    )

    assert rqdata_assets.mirror_hk_daily(args, client) == 0

    assert client.price_calls == [
        {
            "order_book_id": ["00005.XHKG", "00011.XHKG"],
            "start_date": "20250101",
            "end_date": "20250103",
            "frequency": "1d",
            "kwargs": {
                "fields": list(rqdata_assets.DEFAULT_HK_DAILY_FIELDS),
                "skip_suspended": True,
                "market": "hk",
            },
        },
        {
            "order_book_id": "00005.XHKG",
            "start_date": "20250101",
            "end_date": "20250103",
            "frequency": "1d",
            "kwargs": {
                "fields": list(rqdata_assets.DEFAULT_HK_DAILY_FIELDS),
                "skip_suspended": True,
                "market": "hk",
            },
        },
        {
            "order_book_id": "00011.XHKG",
            "start_date": "20250101",
            "end_date": "20250103",
            "frequency": "1d",
            "kwargs": {
                "fields": list(rqdata_assets.DEFAULT_HK_DAILY_FIELDS),
                "skip_suspended": True,
                "market": "hk",
            },
        },
    ]

    output_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "daily_split_demo"
    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    assert manifest["totals"]["symbols_written"] == 2
    assert manifest["batches"][0]["status"] == "split_after_error"
