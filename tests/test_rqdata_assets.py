import json
from types import SimpleNamespace
from pathlib import Path

import pandas as pd
import yaml

from csml import data_providers
from csml.project_tools import rqdata_assets


class _FakeRQPitClient:
    def __init__(self):
        self.calls: list[dict] = []

    def get_pit_financials_ex(
        self,
        *,
        order_book_ids,
        fields,
        start_quarter,
        end_quarter,
        date=None,
        statements="latest",
        market="hk",
    ):
        self.calls.append(
            {
                "order_book_ids": list(order_book_ids),
                "fields": list(fields),
                "start_quarter": start_quarter,
                "end_quarter": end_quarter,
                "date": date,
                "statements": statements,
                "market": market,
            }
        )
        rows: list[dict] = []
        index: list[tuple[str, str]] = []
        for order_book_id in order_book_ids:
            if order_book_id == "00005.XHKG":
                rows.extend(
                    [
                        {
                            "info_date": pd.Timestamp("2025-03-20"),
                            "fiscal_year": pd.Timestamp("2024-12-31"),
                            "standard": "IFRS",
                            "if_adjusted": 0,
                            "rice_create_tm": pd.Timestamp("2025-03-20 09:00:00"),
                            "revenue": 100.0,
                            "net_profit": 10.0,
                        },
                        {
                            "info_date": pd.Timestamp("2025-08-20"),
                            "fiscal_year": pd.Timestamp("2025-12-31"),
                            "standard": "IFRS",
                            "if_adjusted": 0,
                            "rice_create_tm": pd.Timestamp("2025-08-20 09:00:00"),
                            "revenue": 120.0,
                            "net_profit": 12.0,
                        },
                    ]
                )
                index.extend([(order_book_id, "2024q4"), (order_book_id, "2025q1")])
            elif order_book_id == "00011.XHKG":
                rows.append(
                    {
                        "info_date": pd.Timestamp("2025-08-25"),
                        "fiscal_year": pd.Timestamp("2025-12-31"),
                        "standard": "IFRS",
                        "if_adjusted": 1,
                        "rice_create_tm": pd.Timestamp("2025-08-25 09:00:00"),
                        "revenue": 220.0,
                        "net_profit": 22.0,
                    }
                )
                index.append((order_book_id, "2025q1"))
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(
            rows,
            index=pd.MultiIndex.from_tuples(index, names=["order_book_id", "quarter"]),
        )


class _WhitespaceFieldRQPitClient:
    def __init__(self):
        self.calls: list[dict] = []

    def get_pit_financials_ex(
        self,
        *,
        order_book_ids,
        fields,
        start_quarter,
        end_quarter,
        date=None,
        statements="latest",
        market="hk",
    ):
        self.calls.append(
            {
                "order_book_ids": list(order_book_ids),
                "fields": list(fields),
                "start_quarter": start_quarter,
                "end_quarter": end_quarter,
                "date": date,
                "statements": statements,
                "market": market,
            }
        )
        return pd.DataFrame(
            [
                {
                    "info_date": pd.Timestamp("2025-03-20"),
                    "fiscal_year": pd.Timestamp("2024-12-31"),
                    "standard": "IFRS",
                    "if_adjusted": 0,
                    "rice_create_tm": pd.Timestamp("2025-03-20 09:00:00"),
                    "revenue": 100.0,
                    "goodwill_and_intangible_assets ": 55.0,
                }
            ],
            index=pd.MultiIndex.from_tuples(
                [("00005.XHKG", "2024q4")],
                names=["order_book_id", "quarter"],
            ),
        )


class _FakeRQHKApi:
    def __init__(self):
        self.calls: list[dict] = []

    def get_detailed_financial_items(
        self,
        *,
        order_book_ids,
        fields,
        start_quarter,
        end_quarter,
        date=None,
        statements="latest",
        market="hk",
    ):
        self.calls.append(
            {
                "order_book_ids": list(order_book_ids),
                "fields": list(fields),
                "start_quarter": start_quarter,
                "end_quarter": end_quarter,
                "date": date,
                "statements": statements,
                "market": market,
            }
        )
        rows = [
            {
                "info_date": pd.Timestamp("2025-03-20"),
                "fiscal_year": pd.Timestamp("2024-12-31"),
                "field": "revenue",
                "relationship": 1.0,
                "amount": 70.0,
                "currency": "港元",
                "subject": "保费收入",
                "standard": "IFRS",
                "if_adjusted": 0,
            },
            {
                "info_date": pd.Timestamp("2025-03-20"),
                "fiscal_year": pd.Timestamp("2024-12-31"),
                "field": "revenue",
                "relationship": 1.0,
                "amount": 30.0,
                "currency": "港元",
                "subject": "手续费收入",
                "standard": "IFRS",
                "if_adjusted": 0,
            },
        ]
        return pd.DataFrame(
            rows,
            index=pd.MultiIndex.from_tuples(
                [("00005.XHKG", "2024q4"), ("00005.XHKG", "2024q4")],
                names=["order_book_id", "quarter"],
            ),
        )


class _FakeRQDetailsClient:
    def __init__(self):
        self.hk = _FakeRQHKApi()


class _FakeRQInstrumentsClient:
    def __init__(self):
        self.calls: list[dict] = []

    def all_instruments(self, instrument_type, market="hk"):
        self.calls.append({"instrument_type": instrument_type, "market": market})
        return pd.DataFrame(
            [
                {
                    "order_book_id": "00005.XHKG",
                    "symbol": "HSBC HOLDINGS",
                    "listed_date": pd.Timestamp("2000-01-03"),
                    "de_listed_date": pd.NaT,
                    "round_lot": 400,
                    "board_type": "Main Board",
                    "status": "Active",
                },
                {
                    "order_book_id": "00700.XHKG",
                    "symbol": "TENCENT",
                    "listed_date": pd.Timestamp("2004-06-16"),
                    "de_listed_date": pd.NaT,
                    "round_lot": 100,
                    "board_type": "Main Board",
                    "status": "Active",
                },
            ]
        )


class _FakeRQDailyInstrument:
    def __init__(self, listed_date: str):
        self.listed_date = listed_date


class _FakeRQDailyMirrorClient:
    def __init__(self):
        self.price_calls: list[dict] = []
        self._listed_dates = {
            "00005.XHKG": "2000-01-03",
            "00011.XHKG": "2004-06-16",
            "00012.XHKG": "2026-01-15",
        }

    def instruments(self, order_book_id, market=None):
        return _FakeRQDailyInstrument(self._listed_dates.get(order_book_id, "2000-01-03"))

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
        if order_book_id == "00005.XHKG":
            return pd.DataFrame(
                {
                    "open": [10.0, 11.0],
                    "high": [11.0, 12.0],
                    "low": [9.5, 10.5],
                    "close": [10.5, 11.5],
                    "volume": [1000.0, 1200.0],
                    "total_turnover": [10000.0, 12000.0],
                },
                index=pd.to_datetime(["2025-01-02", "2025-01-03"]),
            )
        if order_book_id == "00011.XHKG":
            return pd.DataFrame(
                {
                    "open": [20.0],
                    "high": [21.0],
                    "low": [19.5],
                    "close": [20.5],
                    "volume": [2000.0],
                    "total_turnover": [30000.0],
                },
                index=pd.to_datetime(["2025-01-03"]),
            )
        return pd.DataFrame()


class _FakeRQExFactorClient:
    def __init__(self):
        self.calls: list[dict] = []

    def get_ex_factor(self, order_book_ids, start_date=None, end_date=None, market="hk"):
        self.calls.append(
            {
                "order_book_ids": list(order_book_ids),
                "start_date": start_date,
                "end_date": end_date,
                "market": market,
            }
        )
        rows = [
            {
                "order_book_id": "00005.XHKG",
                "ex_date": pd.Timestamp("2025-03-19"),
                "announcement_date": pd.Timestamp("2025-03-10"),
                "ex_factor": 0.98,
                "ex_cum_factor": 1.25,
                "ex_end_date": pd.Timestamp("2025-03-21"),
            },
            {
                "order_book_id": "00005.XHKG",
                "ex_date": pd.Timestamp("2025-09-19"),
                "announcement_date": pd.Timestamp("2025-09-10"),
                "ex_factor": 0.97,
                "ex_cum_factor": 1.21,
                "ex_end_date": pd.Timestamp("2025-09-23"),
            },
        ]
        frame = pd.DataFrame(rows).set_index("ex_date")
        frame.index.name = "ex_date"
        return frame


class _FakeRQDividendClient:
    def __init__(self):
        self.calls: list[dict] = []

    def get_dividend(self, order_book_ids, start_date=None, end_date=None, market="hk"):
        self.calls.append(
            {
                "order_book_ids": list(order_book_ids),
                "start_date": start_date,
                "end_date": end_date,
                "market": market,
            }
        )
        return pd.DataFrame(
            {
                "book_closure_date": [pd.Timestamp("2025-03-24"), pd.Timestamp("2025-09-24")],
                "ex_dividend_date": [pd.Timestamp("2025-03-19"), pd.Timestamp("2025-09-19")],
                "payable_date": [pd.Timestamp("2025-04-10"), pd.Timestamp("2025-10-10")],
                "dividend_cash_before_tax": [0.5, 0.6],
                "round_lot": [400, 400],
            },
            index=pd.MultiIndex.from_tuples(
                [
                    ("00005.XHKG", pd.Timestamp("2025-03-10")),
                    ("00005.XHKG", pd.Timestamp("2025-09-10")),
                ],
                names=["order_book_id", "declaration_announcement_date"],
            ),
        )


class _FakeRQSharesClient:
    def __init__(self):
        self.calls: list[dict] = []

    def get_shares(self, order_book_ids, start_date=None, end_date=None, fields=None, market="hk"):
        self.calls.append(
            {
                "order_book_ids": list(order_book_ids),
                "start_date": start_date,
                "end_date": end_date,
                "fields": list(fields or []),
                "market": market,
            }
        )
        return pd.DataFrame(
            {
                "total": [5_000_000_000, 5_100_000_000],
                "total_hk": [4_900_000_000, 5_000_000_000],
                "total_hk1": [4_800_000_000, 4_900_000_000],
            },
            index=pd.MultiIndex.from_tuples(
                [
                    ("00005.XHKG", pd.Timestamp("2025-01-31")),
                    ("00005.XHKG", pd.Timestamp("2025-06-30")),
                ],
                names=["order_book_id", "date"],
            ),
        )


class _FlakyRQPitClient:
    def __init__(self):
        self.calls: list[dict] = []
        self._delegate = _FakeRQPitClient()
        self._failed_once = False

    def get_pit_financials_ex(
        self,
        *,
        order_book_ids,
        fields,
        start_quarter,
        end_quarter,
        date=None,
        statements="latest",
        market="hk",
    ):
        self.calls.append(
            {
                "order_book_ids": list(order_book_ids),
                "fields": list(fields),
                "start_quarter": start_quarter,
                "end_quarter": end_quarter,
                "date": date,
                "statements": statements,
                "market": market,
            }
        )
        if not self._failed_once:
            self._failed_once = True
            raise ConnectionError("temporary network jitter")
        return self._delegate.get_pit_financials_ex(
            order_book_ids=order_book_ids,
            fields=fields,
            start_quarter=start_quarter,
            end_quarter=end_quarter,
            date=date,
            statements=statements,
            market=market,
        )


class _QuotaRQPitClient:
    def __init__(self):
        self.calls: list[dict] = []
        self._delegate = _FakeRQPitClient()

    def get_pit_financials_ex(
        self,
        *,
        order_book_ids,
        fields,
        start_quarter,
        end_quarter,
        date=None,
        statements="latest",
        market="hk",
    ):
        payload = {
            "order_book_ids": list(order_book_ids),
            "fields": list(fields),
            "start_quarter": start_quarter,
            "end_quarter": end_quarter,
            "date": date,
            "statements": statements,
            "market": market,
        }
        self.calls.append(payload)
        if len(self.calls) >= 2:
            raise RuntimeError("daily quota exceeded: bytes_limit reached")
        return self._delegate.get_pit_financials_ex(
            order_book_ids=order_book_ids,
            fields=fields,
            start_quarter=start_quarter,
            end_quarter=end_quarter,
            date=date,
            statements=statements,
            market=market,
        )


class _QuotaRQDailyMirrorClient(_FakeRQDailyMirrorClient):
    def get_price(self, order_book_id, start_date, end_date, frequency, **kwargs):
        if len(self.price_calls) >= 1:
            self.price_calls.append(
                {
                    "order_book_id": order_book_id,
                    "start_date": start_date,
                    "end_date": end_date,
                    "frequency": frequency,
                    "kwargs": dict(kwargs),
                }
            )
            raise RuntimeError("daily quota exceeded: bytes_limit reached")
        return super().get_price(order_book_id, start_date, end_date, frequency, **kwargs)


class _FieldFallbackRQPitClient:
    def __init__(self):
        self.calls: list[dict] = []
        self._delegate = _FakeRQPitClient()

    def get_pit_financials_ex(
        self,
        *,
        order_book_ids,
        fields,
        start_quarter,
        end_quarter,
        date=None,
        statements="latest",
        market="hk",
    ):
        self.calls.append(
            {
                "order_book_ids": list(order_book_ids),
                "fields": list(fields),
                "start_quarter": start_quarter,
                "end_quarter": end_quarter,
                "date": date,
                "statements": statements,
                "market": market,
            }
        )
        if "goodwill_and_intangible_assets" in fields:
            raise RuntimeError(
                "fields: got invalided value goodwill_and_intangible_assets, choose any in ['revenue', 'net_profit']"
            )
        return self._delegate.get_pit_financials_ex(
            order_book_ids=order_book_ids,
            fields=fields,
            start_quarter=start_quarter,
            end_quarter=end_quarter,
            date=date,
            statements=statements,
            market=market,
        )


def test_list_hk_financial_fields_filters_and_writes_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        rqdata_assets,
        "_load_hk_financial_fields",
        lambda: ["revenue", "net_profit", "cash_flow_from_operating_activities"],
    )
    out_path = tmp_path / "hk_fields.txt"

    assert (
        rqdata_assets.list_hk_financial_fields(
            SimpleNamespace(contains=["profit"], limit=None, out=str(out_path))
        )
        == 0
    )

    assert out_path.read_text(encoding="utf-8") == "net_profit\n"
    assert "Wrote 1 HK financial fields" in capsys.readouterr().out


def test_export_hk_instruments_writes_filtered_asset_and_manifest(tmp_path, monkeypatch, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(rqdata_assets, "_ensure_rqdatac_hk_plugin", lambda: None)
    client = _FakeRQInstrumentsClient()
    out_path = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "instruments" / "demo.parquet"

    result = rqdata_assets.export_hk_instruments(
        SimpleNamespace(
            config="hk",
            username=None,
            password=None,
            use_config_universe=False,
            symbol=["00005.HK"],
            symbols_file=None,
            by_date_file=None,
            limit=None,
            out=str(out_path),
            force=False,
        ),
        client,
    )

    assert result == 0
    assert client.calls == [{"instrument_type": "CS", "market": "hk"}]
    frame = pd.read_parquet(out_path)
    assert frame["ts_code"].tolist() == ["00005.HK"]
    assert int(frame["round_lot"].iloc[0]) == 400

    manifest = yaml.safe_load(Path(f"{out_path}.manifest.yml").read_text(encoding="utf-8"))
    assert manifest["dataset"] == "hk_instruments"
    assert manifest["totals"]["symbols"] == 1
    assert manifest["symbol_source"]["mode"] == "explicit"
    assert "Wrote 1 HK instruments" in capsys.readouterr().out


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

    output_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "daily_demo"
    data = pd.read_parquet(output_dir / "data" / "00005.HK.parquet")
    assert data["trade_date"].tolist() == ["20250102", "20250103"]
    assert data["ts_code"].tolist() == ["00005.HK", "00005.HK"]
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
    assert frame["ts_code"].tolist() == ["00005.HK", "00005.HK"]
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
    assert frame["ts_code"].tolist() == ["00005.HK", "00005.HK"]
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
    assert frame["ts_code"].tolist() == ["00005.HK", "00005.HK"]
    assert frame["total_hk1"].tolist() == [4_800_000_000, 4_900_000_000]

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["dataset"] == "shares"
    assert manifest["query"]["fields"] == list(rqdata_assets.DEFAULT_HK_SHARES_FIELDS)
    assert manifest["query"]["date_column"] == "date"
    assert manifest["totals"]["symbols_written"] == 1


def test_resolve_hk_dated_request_groups_uses_local_unique_ids(tmp_path):
    instruments_dir = tmp_path / "rqdata" / "hk" / "instruments"
    instruments_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "ts_code": "00013.HK",
                "order_book_id": "00013.XHKG",
                "unique_id": "00013_01.XHKG",
                "listed_date": "1978-01-03",
                "de_listed_date": "2015-06-03",
            },
            {
                "ts_code": "00013.HK",
                "order_book_id": "00013.XHKG",
                "unique_id": "00013_02.XHKG",
                "listed_date": "2021-06-30",
                "de_listed_date": "0000-00-00",
            },
            {
                "ts_code": "00005.HK",
                "order_book_id": "00005.XHKG",
                "unique_id": "00005_01.XHKG",
                "listed_date": "1980-01-02",
                "de_listed_date": "0000-00-00",
            },
        ]
    ).to_parquet(instruments_dir / "hk_all_instruments_20260317.parquet", index=False)

    groups, metadata, info = rqdata_assets._resolve_hk_dated_request_groups(
        ["00013.HK", "00005.HK"],
        start_date="20140101",
        end_date="20251231",
        out_root=str(tmp_path / "rqdata"),
    )

    assert info["mode"] == "local_hk_instruments_snapshot"
    assert [group.ts_code for group in groups] == ["00013.HK", "00005.HK"]
    assert groups[0].request_ids == ("00013_01.XHKG", "00013_02.XHKG")
    assert groups[0].order_book_ids == ("00013.XHKG",)
    assert groups[1].request_ids == ("00005_01.XHKG",)
    assert metadata["00013_02.XHKG"]["order_book_id"] == "00013.XHKG"
    assert metadata["00005_01.XHKG"]["unique_id"] == "00005_01.XHKG"


def test_resolve_fields_supports_field_profile(monkeypatch):
    monkeypatch.setattr(
        rqdata_assets,
        "_load_hk_financial_fields",
        lambda: ["revenue", "net_profit", "income_tax", "goodwill_and_intangible_assets "],
    )

    fields, metadata = rqdata_assets._resolve_fields(
        SimpleNamespace(
            field_profile=["starter", "full"],
            field=["revenue"],
            fields_file=[],
        )
    )

    assert fields[:3] == ["revenue", "operating_revenue", "operating_profit"]
    assert "income_tax" in fields
    assert "goodwill_and_intangible_assets " in fields
    assert metadata["field_profile"] == ["starter", "full"]


def test_validate_resume_inputs_preserves_whitespace_fields(tmp_path, monkeypatch):
    output_dir = tmp_path / "pit_demo"
    output_dir.mkdir(parents=True)
    (output_dir / "fields.txt").write_text(
        "revenue\ngoodwill_and_intangible_assets \n",
        encoding="utf-8",
    )
    (output_dir / "symbols.txt").write_text("00005.HK\n", encoding="utf-8")
    (output_dir / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "pit_financials",
                "query": {
                    "start_quarter": "2024q4",
                    "end_quarter": "2025q1",
                    "date": "20260310",
                    "statements": "latest",
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        rqdata_assets,
        "_load_hk_financial_fields",
        lambda: ["revenue", "goodwill_and_intangible_assets "],
    )
    fields, _ = rqdata_assets._resolve_fields(
        SimpleNamespace(
            field_profile=["full"],
            field=[],
            fields_file=[],
        )
    )

    assert fields == ["revenue", "goodwill_and_intangible_assets "]
    rqdata_assets._validate_resume_inputs(
        output_dir=output_dir,
        dataset_name="pit_financials",
        fields=fields,
        symbols=["00005.HK"],
        start_quarter="2024q4",
        end_quarter="2025q1",
        statements="latest",
        query_date="20260310",
    )


def test_mirror_hk_pit_financials_uses_config_universe_and_writes_manifest(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    (repo_root / "config").mkdir(parents=True)
    (repo_root / "artifacts" / "assets" / "universe").mkdir(parents=True)
    (repo_root / "config" / "hk_assets.yml").write_text(
        "\n".join(
            [
                "market: hk",
                "universe:",
                "  mode: pit",
                "  symbols: []",
                "  symbols_file: null",
                "  by_date_file: artifacts/assets/universe/universe_by_date.csv",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (repo_root / "config" / "pit_fields.txt").write_text(
        "revenue\nnet_profit\n",
        encoding="utf-8",
    )
    (repo_root / "artifacts" / "assets" / "universe" / "universe_by_date.csv").write_text(
        "\n".join(
            [
                "trade_date,ts_code,selected",
                "20250131,5.HK,1",
                "20250131,00011.XHKG,1",
                "20250228,00005.HK,1",
                "20250228,00012.HK,0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(repo_root)

    client = _FakeRQPitClient()
    args = SimpleNamespace(
        config="config/hk_assets.yml",
        username=None,
        password=None,
        start_quarter="2024q4",
        end_quarter="2025q1",
        date="20260310",
        statements="latest",
        field=[],
        fields_file=["config/pit_fields.txt"],
        symbol=[],
        symbols_file=None,
        by_date_file=None,
        limit=None,
        batch_size=1,
        out_root="artifacts/assets/rqdata",
        name="pit_demo",
    )

    assert rqdata_assets.mirror_hk_pit_financials(args, client) == 0

    assert client.calls == [
        {
            "order_book_ids": ["00005.XHKG"],
            "fields": ["revenue", "net_profit"],
            "start_quarter": "2024q4",
            "end_quarter": "2025q1",
            "date": "20260310",
            "statements": "latest",
            "market": "hk",
        },
        {
            "order_book_ids": ["00011.XHKG"],
            "fields": ["revenue", "net_profit"],
            "start_quarter": "2024q4",
            "end_quarter": "2025q1",
            "date": "20260310",
            "statements": "latest",
            "market": "hk",
        },
    ]

    output_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "pit_financials" / "pit_demo"
    assert (output_dir / "fields.txt").read_text(encoding="utf-8") == "revenue\nnet_profit\n"
    assert (output_dir / "symbols.txt").read_text(encoding="utf-8") == "00005.HK\n00011.HK\n"

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    assert manifest["dataset"] == "pit_financials"
    assert manifest["api"] == "rqdatac.get_pit_financials_ex"
    assert manifest["symbol_source"]["mode"] == "config_universe"
    assert manifest["query"]["fields"] == ["revenue", "net_profit"]
    assert manifest["totals"]["symbols_requested"] == 2
    assert manifest["totals"]["symbols_written"] == 2
    assert manifest["missing_symbols"] == []

    first = pd.read_parquet(output_dir / "data" / "00005.HK.parquet")
    assert first["ts_code"].tolist() == ["00005.HK", "00005.HK"]
    assert first["order_book_id"].tolist() == ["00005.XHKG", "00005.XHKG"]
    assert first["quarter"].tolist() == ["2024q4", "2025q1"]
    assert set(["revenue", "net_profit", "info_date", "fiscal_year"]).issubset(first.columns)


def test_mirror_hk_financial_details_tracks_missing_symbols(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(rqdata_assets, "_ensure_rqdatac_hk_plugin", lambda: None)

    client = _FakeRQDetailsClient()
    args = SimpleNamespace(
        config=None,
        username=None,
        password=None,
        start_quarter="2024q4",
        end_quarter="2024q4",
        date="20260310",
        statements="latest",
        field=["revenue"],
        fields_file=[],
        symbol=["5.hk", "00011.XHKG"],
        symbols_file=None,
        by_date_file=None,
        limit=None,
        batch_size=20,
        out_root="artifacts/assets/rqdata",
        name="details_demo",
    )

    assert rqdata_assets.mirror_hk_financial_details(args, client) == 0

    assert client.hk.calls == [
        {
            "order_book_ids": ["00005.XHKG", "00011.XHKG"],
            "fields": ["revenue"],
            "start_quarter": "2024q4",
            "end_quarter": "2024q4",
            "date": "20260310",
            "statements": "latest",
            "market": "hk",
        }
    ]

    output_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "financial_details" / "details_demo"
    detail = pd.read_parquet(output_dir / "data" / "00005.HK.parquet")
    assert detail["ts_code"].tolist() == ["00005.HK", "00005.HK"]
    assert detail["field"].tolist() == ["revenue", "revenue"]
    assert detail["subject"].tolist() == ["保费收入", "手续费收入"]

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["dataset"] == "financial_details"
    assert manifest["totals"]["symbols_requested"] == 2
    assert manifest["totals"]["symbols_written"] == 1
    assert manifest["missing_symbols"] == ["00011.HK"]


def test_build_hk_pit_fundamentals_file_writes_pipeline_ready_output(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "pit_financials" / "pit_demo"
    data_dir = asset_dir / "data"
    data_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    manifest = {
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
            "ts_code",
        ],
    }
    (asset_dir / "manifest.yml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    pd.DataFrame(
        {
            "quarter": ["2024q4", "2024q4", "2025q1"],
            "info_date": pd.to_datetime(["2025-03-20", "2025-03-20", "2025-08-20"]),
            "fiscal_year": pd.to_datetime(["2024-12-31", "2024-12-31", "2025-12-31"]),
            "standard": ["IFRS", "IFRS", "IFRS"],
            "if_adjusted": [0, 1, 0],
            "rice_create_tm": pd.to_datetime(
                ["2025-03-20 09:00:00", "2025-03-20 10:00:00", "2025-08-20 09:00:00"]
            ),
            "revenue": [100.0, 101.0, 120.0],
            "net_profit": [10.0, 11.0, 12.0],
            "order_book_id": ["00005.XHKG", "00005.XHKG", "00005.XHKG"],
            "ts_code": ["00005.HK", "00005.HK", "00005.HK"],
        }
    ).to_parquet(data_dir / "00005.HK.parquet", index=False)
    pd.DataFrame(
        {
            "quarter": ["2025q1"],
            "info_date": pd.to_datetime(["2025-08-25"]),
            "fiscal_year": pd.to_datetime(["2025-12-31"]),
            "standard": ["IFRS"],
            "if_adjusted": [0],
            "rice_create_tm": pd.to_datetime(["2025-08-25 09:00:00"]),
            "revenue": [220.0],
            "net_profit": [22.0],
            "order_book_id": ["00011.XHKG"],
            "ts_code": ["00011.HK"],
        }
    ).to_parquet(data_dir / "00011.HK.parquet", index=False)

    out_path = repo_root / "artifacts" / "assets" / "fundamentals" / "pit_fundamentals.parquet"
    args = SimpleNamespace(
        asset_dir=str(asset_dir),
        field=[],
        fields_file=[],
        out=str(out_path),
        keep_meta=False,
        duplicate_policy="keep-last",
        force=False,
    )

    assert rqdata_assets.build_hk_pit_fundamentals_file(args) == 0

    fundamentals = pd.read_parquet(out_path)
    assert fundamentals.columns.tolist() == ["trade_date", "ts_code", "revenue", "net_profit"]
    assert fundamentals["trade_date"].tolist() == ["20250320", "20250820", "20250825"]
    assert fundamentals["ts_code"].tolist() == ["00005.HK", "00005.HK", "00011.HK"]
    assert fundamentals["revenue"].tolist() == [101.0, 120.0, 220.0]
    assert fundamentals["net_profit"].tolist() == [11.0, 12.0, 22.0]

    output_manifest = yaml.safe_load(
        (
            repo_root
            / "artifacts"
            / "assets"
            / "fundamentals"
            / "pit_fundamentals.manifest.yml"
        ).read_text(encoding="utf-8")
    )
    assert output_manifest["dataset"] == "pit_fundamentals_file"
    assert output_manifest["query"]["fields"] == ["revenue", "net_profit"]
    assert output_manifest["totals"]["input_files"] == 2
    assert output_manifest["totals"]["output_rows"] == 3
    assert output_manifest["totals"]["duplicate_rows_seen"] == 2
    assert output_manifest["totals"]["duplicate_rows_dropped"] == 1


def test_build_hk_pit_fundamentals_file_normalizes_whitespace_fields_and_derives_universe(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "pit_financials" / "pit_demo"
    data_dir = asset_dir / "data"
    data_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    manifest = {
        "dataset": "pit_financials",
        "query": {"fields": ["revenue", "goodwill_and_intangible_assets"]},
        "columns": [
            "quarter",
            "info_date",
            "fiscal_year",
            "standard",
            "if_adjusted",
            "rice_create_tm",
            "revenue",
            "goodwill_and_intangible_assets ",
            "order_book_id",
            "ts_code",
        ],
    }
    (asset_dir / "manifest.yml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
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
            "goodwill_and_intangible_assets ": [55.0],
            "order_book_id": ["00005.XHKG"],
            "ts_code": ["00005.HK"],
        }
    ).to_parquet(data_dir / "00005.HK.parquet", index=False)

    source_universe = repo_root / "artifacts" / "assets" / "universe" / "hk_connect_full_by_date.csv"
    source_universe.parent.mkdir(parents=True)
    pd.DataFrame(
        {
            "trade_date": ["20250320", "20250320"],
            "ts_code": ["00005.HK", "00011.HK"],
            "stock_ticker": ["00005.HK", "00011.HK"],
            "selected": [1, 1],
        }
    ).to_csv(source_universe, index=False)

    out_path = repo_root / "artifacts" / "assets" / "fundamentals" / "pit_fundamentals_full.parquet"
    research_universe_out = (
        repo_root / "artifacts" / "assets" / "universe" / "hk_connect_full_research_by_date.csv"
    )
    symbols_out = repo_root / "artifacts" / "assets" / "universe" / "hk_connect_full_research_symbols.txt"
    args = SimpleNamespace(
        asset_dir=str(asset_dir),
        field=[],
        fields_file=[],
        out=str(out_path),
        source_universe_by_date=str(source_universe),
        universe_by_date_out=str(research_universe_out),
        symbols_out=str(symbols_out),
        keep_meta=False,
        duplicate_policy="keep-last",
        force=False,
    )

    assert rqdata_assets.build_hk_pit_fundamentals_file(args) == 0

    fundamentals = pd.read_parquet(out_path)
    assert fundamentals.columns.tolist() == [
        "trade_date",
        "ts_code",
        "revenue",
        "goodwill_and_intangible_assets",
    ]
    assert fundamentals["goodwill_and_intangible_assets"].tolist() == [55.0]

    research_universe = pd.read_csv(research_universe_out)
    assert research_universe["ts_code"].tolist() == ["00005.HK"]
    assert research_universe["stock_ticker"].tolist() == ["00005.HK"]
    assert symbols_out.read_text(encoding="utf-8") == "00005.HK\n"

    output_manifest = yaml.safe_load(
        (
            repo_root
            / "artifacts"
            / "assets"
            / "fundamentals"
            / "pit_fundamentals_full.manifest.yml"
        ).read_text(encoding="utf-8")
    )
    assert output_manifest["query"]["fields"] == ["revenue", "goodwill_and_intangible_assets"]
    assert output_manifest["outputs"]["symbols_file"] == str(symbols_out)
    assert output_manifest["outputs"]["universe_by_date_file"] == str(research_universe_out)
    assert output_manifest["filtered_universe"]["symbols"] == 1


def test_inspect_hk_pit_coverage_supports_config_selected_derived_features(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "pit_financials" / "pit_demo"
    asset_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    (asset_dir / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "pit_financials",
                "query": {
                    "fields": [
                        "revenue",
                        "net_profit",
                        "total_assets",
                        "total_liabilities",
                        "cash_flow_from_operating_activities",
                        "accounts_receivable",
                    ]
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    fundamentals_path = asset_dir / "pipeline_fundamentals.parquet"
    pd.DataFrame(
        {
            "trade_date": ["20250320", "20250320", "20250820", "20250820"],
            "ts_code": ["00005.HK", "00011.HK", "00005.HK", "00011.HK"],
            "revenue": [100.0, 200.0, 120.0, None],
            "net_profit": [10.0, 20.0, 12.0, 5.0],
            "total_assets": [1000.0, 2000.0, 1100.0, 2100.0],
            "total_liabilities": [500.0, 1000.0, 520.0, 1050.0],
            "cash_flow_from_operating_activities": [8.0, 16.0, 9.0, None],
            "accounts_receivable": [5.0, None, 6.0, 7.0],
        }
    ).to_parquet(fundamentals_path, index=False)

    (asset_dir / "pipeline_fundamentals.manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "pit_fundamentals_file",
                "source_asset_dir": str(asset_dir),
                "totals": {
                    "input_rows": 10,
                    "output_rows": 4,
                    "symbols": 2,
                    "dropped_all_missing_fields": 6,
                    "duplicate_rows_seen": 0,
                    "duplicate_rows_dropped": 0,
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    config_path = repo_root / "config" / "pit_inspect.yml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        yaml.safe_dump(
            {
                "fundamentals": {
                    "enabled": True,
                    "source": "file",
                    "file": str(fundamentals_path),
                    "features": [
                        "revenue",
                        "net_profit",
                        "profit_margin",
                        "asset_turnover",
                        "receivables_to_revenue",
                    ],
                },
                "universe": {"min_symbols_per_date": 2},
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    out_path = repo_root / "coverage.json"
    args = SimpleNamespace(
        config=str(config_path),
        asset_dir=None,
        fundamentals_file=None,
        field_profile=[],
        field=[],
        fields_file=[],
        min_symbols=None,
        top=10,
        quarter_limit=12,
        format="json",
        out=str(out_path),
    )

    assert rqdata_assets.inspect_hk_pit_coverage(args) == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["selection"]["source"] == "config.fundamentals.features"
    assert payload["selection"]["selected_features"] == [
        "revenue",
        "net_profit",
        "profit_margin",
        "asset_turnover",
        "receivables_to_revenue",
    ]
    assert payload["complete_case"]["complete_rows"] == 2
    assert payload["complete_case"]["quarter_count_meeting_min_symbols"] == 0
    assert payload["pipeline_manifest_totals"]["dropped_all_missing_fields"] == 6

    field_map = {item["feature"]: item for item in payload["field_coverage"]}
    assert field_map["profit_margin"]["nonnull_rows"] == 3
    assert field_map["asset_turnover"]["nonnull_rows"] == 3
    assert field_map["receivables_to_revenue"]["nonnull_rows"] == 2

    assert payload["quarter_coverage"] == [
        {
            "quarter": "2025Q1",
            "symbols_in_file": 2,
            "symbols_with_any_selected_feature": 2,
            "symbols_with_all_selected_features": 1,
        },
        {
            "quarter": "2025Q3",
            "symbols_in_file": 2,
            "symbols_with_any_selected_feature": 2,
            "symbols_with_all_selected_features": 1,
        },
    ]


def test_inspect_hk_pit_coverage_trainable_mode_estimates_fill_recovered_sample(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "pit_financials" / "pit_demo"
    asset_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    fundamentals_path = asset_dir / "pipeline_fundamentals.parquet"
    pd.DataFrame(
        {
            "trade_date": ["20250320", "20250820", "20250820"],
            "ts_code": ["00005.HK", "00005.HK", "00011.HK"],
            "revenue": [100.0, 120.0, None],
            "net_profit": [10.0, 12.0, 5.0],
        }
    ).to_parquet(fundamentals_path, index=False)

    (asset_dir / "pipeline_fundamentals.manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "pit_fundamentals_file",
                "source_asset_dir": str(asset_dir),
                "totals": {
                    "input_rows": 3,
                    "output_rows": 3,
                    "symbols": 2,
                    "dropped_all_missing_fields": 0,
                    "duplicate_rows_seen": 0,
                    "duplicate_rows_dropped": 0,
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    universe_by_date = repo_root / "artifacts" / "assets" / "universe" / "pit_demo_by_date.csv"
    universe_by_date.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "trade_date": ["20250331", "20250930", "20250930"],
            "ts_code": ["00005.HK", "00005.HK", "00011.HK"],
        }
    ).to_csv(universe_by_date, index=False)

    config_path = repo_root / "config" / "pit_trainable.yml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        yaml.safe_dump(
            {
                "fundamentals": {
                    "enabled": True,
                    "source": "file",
                    "file": str(fundamentals_path),
                    "features": ["revenue", "net_profit"],
                    "auto_add_features": False,
                    "ffill": True,
                },
                "features": {
                    "list": ["ret_60", "revenue", "net_profit", "profit_margin"],
                    "missing": {
                        "method": "cross_sectional_median",
                        "features": ["revenue", "profit_margin"],
                        "add_indicators": True,
                    },
                },
                "label": {"rebalance_frequency": "Q"},
                "eval": {
                    "rebalance_frequency": "Q",
                    "sample_on_rebalance_dates": True,
                },
                "universe": {
                    "min_symbols_per_date": 2,
                    "by_date_file": str(universe_by_date),
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    out_path = repo_root / "coverage_trainable.json"
    args = SimpleNamespace(
        config=str(config_path),
        asset_dir=None,
        fundamentals_file=None,
        field_profile=[],
        field=[],
        fields_file=[],
        mode="trainable",
        min_symbols=None,
        top=10,
        quarter_limit=12,
        format="json",
        out=str(out_path),
    )

    assert rqdata_assets.inspect_hk_pit_coverage(args) == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["selection"]["mode"] == "trainable"
    assert payload["selection"]["source"] == "config.features.list"
    assert payload["selection"]["selected_features"] == [
        "revenue",
        "net_profit",
        "profit_margin",
    ]
    assert payload["selection"]["ignored_features"] == ["ret_60"]

    trainable = payload["trainable_estimate"]
    assert trainable["feature_source"] == "config.features.list"
    assert trainable["missing_method"] == "cross_sectional_median"
    assert trainable["non_pit_features_ignored"] == ["ret_60"]
    assert trainable["period_count_meeting_min_symbols_after_ffill"] == 0
    assert trainable["period_count_meeting_min_symbols_after_missing_fill"] == 1
    fill_dependence = payload["fill_dependence_assessment"]
    assert fill_dependence["route_type"] == "hybrid"
    assert fill_dependence["status"] == "red"
    assert fill_dependence["retention_ratio_after_ffill"] == 0.0
    assert fill_dependence["fill_dependency_ratio_from_missing_fill"] == 1.0

    assert payload["trainable_period_coverage"] == [
        {
            "period": "2025Q1",
            "active_symbols": 1,
            "symbols_with_any_selected_features_after_ffill": 1,
            "symbols_with_all_selected_features_after_ffill": 1,
            "symbols_with_all_selected_features_after_missing_fill": 1,
        },
        {
            "period": "2025Q3",
            "active_symbols": 2,
            "symbols_with_any_selected_features_after_ffill": 2,
            "symbols_with_all_selected_features_after_ffill": 1,
            "symbols_with_all_selected_features_after_missing_fill": 2,
        },
    ]


def test_assess_trainable_fill_dependence_marks_healthier_pit_only_route_green():
    assessment = rqdata_assets._assess_trainable_fill_dependence(
        trainable_estimate={
            "period_count_meeting_min_symbols_after_ffill": 6,
            "period_count_meeting_min_symbols_after_missing_fill": 8,
        },
        non_pit_features_ignored=[],
    )

    assert assessment["route_type"] == "pit_only"
    assert assessment["status"] == "green"
    assert assessment["retention_ratio_after_ffill"] == 0.75
    assert assessment["fill_dependency_ratio_from_missing_fill"] == 0.25


def test_mirror_hk_pit_financials_normalizes_whitespace_field_columns(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    client = _WhitespaceFieldRQPitClient()
    args = SimpleNamespace(
        config=None,
        username=None,
        password=None,
        start_quarter="2024q4",
        end_quarter="2025q1",
        date="20260310",
        statements="latest",
        field=["revenue", "goodwill_and_intangible_assets"],
        fields_file=[],
        symbol=["00005.HK"],
        symbols_file=None,
        by_date_file=None,
        limit=None,
        batch_size=1,
        out_root="artifacts/assets/rqdata",
        name="pit_whitespace_fields_demo",
        resume=False,
        skip_existing=False,
        max_attempts=1,
        backoff_seconds=0.0,
        max_backoff_seconds=0.0,
    )

    assert rqdata_assets.mirror_hk_pit_financials(args, client) == 0

    output_dir = (
        repo_root
        / "artifacts"
        / "assets"
        / "rqdata"
        / "hk"
        / "pit_financials"
        / "pit_whitespace_fields_demo"
    )
    data = pd.read_parquet(output_dir / "data" / "00005.HK.parquet")
    assert "goodwill_and_intangible_assets" in data.columns
    assert "goodwill_and_intangible_assets " not in data.columns

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert "goodwill_and_intangible_assets" in manifest["columns"]
    assert "goodwill_and_intangible_assets " not in manifest["columns"]


def test_mirror_hk_pit_financials_resume_skips_existing_and_writes_audit(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    output_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "pit_financials" / "pit_demo"
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

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
            "ts_code": ["00005.HK"],
        }
    ).to_parquet(data_dir / "00005.HK.parquet", index=False)
    (output_dir / "fields.txt").write_text("revenue\nnet_profit\n", encoding="utf-8")
    (output_dir / "symbols.txt").write_text("00005.HK\n00011.HK\n", encoding="utf-8")
    (output_dir / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "pit_financials",
                "query": {
                    "start_quarter": "2024q4",
                    "end_quarter": "2025q1",
                    "date": "20260310",
                    "statements": "latest",
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    client = _FakeRQPitClient()
    args = SimpleNamespace(
        config=None,
        username=None,
        password=None,
        start_quarter="2024q4",
        end_quarter="2025q1",
        date="20260310",
        statements="latest",
        field=["revenue", "net_profit"],
        fields_file=[],
        symbol=["00005.HK", "00011.HK"],
        symbols_file=None,
        by_date_file=None,
        limit=None,
        batch_size=20,
        out_root="artifacts/assets/rqdata",
        name="pit_demo",
        resume=True,
        skip_existing=False,
        max_attempts=1,
        backoff_seconds=0.0,
        max_backoff_seconds=0.0,
    )

    assert rqdata_assets.mirror_hk_pit_financials(args, client) == 0
    assert client.calls == [
        {
            "order_book_ids": ["00011.XHKG"],
            "fields": ["revenue", "net_profit"],
            "start_quarter": "2024q4",
            "end_quarter": "2025q1",
            "date": "20260310",
            "statements": "latest",
            "market": "hk",
        }
    ]

    audit = pd.read_csv(output_dir / "audit.csv")
    status_map = dict(zip(audit["ts_code"], audit["status"]))
    assert status_map["00005.HK"] == "skipped_existing"
    assert status_map["00011.HK"] == "written"

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["totals"]["symbols_written"] == 2
    assert manifest["totals"]["symbols_newly_written"] == 1
    assert manifest["totals"]["symbols_skipped_existing"] == 1
    assert manifest["status_counts"]["skipped_existing"] == 1
    assert manifest["status_counts"]["written"] == 1


def test_mirror_hk_daily_resume_skips_existing_and_writes_audit(tmp_path, monkeypatch):
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
    status_map = dict(zip(audit["ts_code"], audit["status"]))
    assert status_map["00005.HK"] == "skipped_existing"
    assert status_map["00011.HK"] == "written"

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["totals"]["symbols_written"] == 2
    assert manifest["totals"]["symbols_newly_written"] == 1
    assert manifest["totals"]["symbols_skipped_existing"] == 1


def test_mirror_hk_pit_financials_retries_and_records_attempts(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    client = _FlakyRQPitClient()
    args = SimpleNamespace(
        config=None,
        username=None,
        password=None,
        start_quarter="2024q4",
        end_quarter="2025q1",
        date="20260310",
        statements="latest",
        field=["revenue", "net_profit"],
        fields_file=[],
        symbol=["00005.HK"],
        symbols_file=None,
        by_date_file=None,
        limit=None,
        batch_size=1,
        out_root="artifacts/assets/rqdata",
        name="pit_retry_demo",
        resume=False,
        skip_existing=False,
        max_attempts=2,
        backoff_seconds=0.0,
        max_backoff_seconds=0.0,
    )

    assert rqdata_assets.mirror_hk_pit_financials(args, client) == 0
    assert len(client.calls) == 2

    output_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "pit_financials" / "pit_retry_demo"
    audit = pd.read_csv(output_dir / "audit.csv")
    assert audit.loc[audit["ts_code"] == "00005.HK", "attempts"].iloc[0] == 2

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["batches"][0]["attempts"] == 2
    assert manifest["status"] == "completed"


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
    status_map = dict(zip(audit["ts_code"], audit["status"]))
    assert status_map["00005.HK"] == "written"
    assert status_map["00011.HK"] == "quota_blocked"
    assert status_map["00012.HK"] == "quota_blocked"

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["status"] == "stopped_quota"
    assert manifest["totals"]["symbols_written"] == 1
    assert manifest["totals"]["symbols_quota_blocked"] == 2
    assert manifest["quota_blocked_symbols"] == ["00011.HK", "00012.HK"]


def test_mirror_hk_pit_financials_stops_on_quota_and_marks_remaining_symbols(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    client = _QuotaRQPitClient()
    args = SimpleNamespace(
        config=None,
        username=None,
        password=None,
        start_quarter="2024q4",
        end_quarter="2025q1",
        date="20260310",
        statements="latest",
        field=["revenue", "net_profit"],
        fields_file=[],
        symbol=["00005.HK", "00011.HK", "00012.HK"],
        symbols_file=None,
        by_date_file=None,
        limit=None,
        batch_size=1,
        out_root="artifacts/assets/rqdata",
        name="pit_quota_demo",
        resume=False,
        skip_existing=False,
        max_attempts=1,
        backoff_seconds=0.0,
        max_backoff_seconds=0.0,
    )

    assert rqdata_assets.mirror_hk_pit_financials(args, client) == 2

    output_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "pit_financials" / "pit_quota_demo"
    audit = pd.read_csv(output_dir / "audit.csv")
    status_map = dict(zip(audit["ts_code"], audit["status"]))
    assert status_map["00005.HK"] == "written"
    assert status_map["00011.HK"] == "quota_blocked"
    assert status_map["00012.HK"] == "quota_blocked"

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["status"] == "stopped_quota"
    assert manifest["totals"]["symbols_written"] == 1
    assert manifest["totals"]["symbols_quota_blocked"] == 2
    assert manifest["quota_blocked_symbols"] == ["00011.HK", "00012.HK"]


def test_mirror_hk_pit_financials_drops_invalid_field_per_symbol_and_keeps_schema(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    client = _FieldFallbackRQPitClient()
    args = SimpleNamespace(
        config=None,
        username=None,
        password=None,
        start_quarter="2024q4",
        end_quarter="2025q1",
        date="20260310",
        statements="latest",
        field=["revenue", "goodwill_and_intangible_assets"],
        fields_file=[],
        symbol=["00005.HK"],
        symbols_file=None,
        by_date_file=None,
        limit=None,
        batch_size=1,
        out_root="artifacts/assets/rqdata",
        name="pit_field_fallback_demo",
        resume=False,
        skip_existing=False,
        max_attempts=1,
        backoff_seconds=0.0,
        max_backoff_seconds=0.0,
    )

    assert rqdata_assets.mirror_hk_pit_financials(args, client) == 0
    assert len(client.calls) == 2
    assert client.calls[0]["fields"] == ["revenue", "goodwill_and_intangible_assets"]
    assert client.calls[1]["fields"] == ["revenue"]

    output_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "pit_financials" / "pit_field_fallback_demo"
    data = pd.read_parquet(output_dir / "data" / "00005.HK.parquet")
    assert "revenue" in data.columns
    assert "goodwill_and_intangible_assets" in data.columns
    assert data["goodwill_and_intangible_assets"].isna().all()

    audit = pd.read_csv(output_dir / "audit.csv")
    assert audit.loc[audit["ts_code"] == "00005.HK", "status"].iloc[0] == "written"
    assert (
        audit.loc[audit["ts_code"] == "00005.HK", "dropped_fields"].iloc[0]
        == "goodwill_and_intangible_assets"
    )
