import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import yaml

from cstree import data_providers
from cstree.data_tools import rqdata_assets

from tests.rqdata_assets._fakes import (
    _FakeRQIndustryClient,
    _FakeRQSouthboundClient,
    _FakeRQAnnouncementClient,
)


def test_mirror_hk_southbound_writes_symbol_history_assets(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    (repo_root / "artifacts" / "assets" / "universe").mkdir(parents=True)
    by_date_file = repo_root / "artifacts" / "assets" / "universe" / "hk_connect_full_by_date.csv"
    by_date_file.write_text(
        "\n".join(
            [
                "trade_date,symbol,selected",
                "20250102,00005.HK,1",
                "20250102,00011.HK,1",
                "20250131,00012.HK,1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    client = _FakeRQSouthboundClient()
    args = SimpleNamespace(
        config=None,
        username=None,
        password=None,
        start_date="20250101",
        end_date="20250131",
        symbol=[],
        symbols_file=None,
        by_date_file="artifacts/assets/universe/hk_connect_full_by_date.csv",
        limit=None,
        trading_type=["both"],
        rebalance_frequency="D",
        out_root="artifacts/assets/rqdata",
        name="southbound_demo",
        resume=False,
        skip_existing=False,
        max_attempts=1,
        backoff_seconds=0.0,
        max_backoff_seconds=0.0,
    )

    assert rqdata_assets.mirror_hk_southbound(args, client) == 0

    assert client.hk.calls == [
        {"trading_type": "sh", "date": "20250102"},
        {"trading_type": "sz", "date": "20250102"},
        {"trading_type": "sh", "date": "20250131"},
        {"trading_type": "sz", "date": "20250131"},
    ]

    output_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "southbound" / "southbound_demo"
    assert (output_dir / "fields.txt").read_text(encoding="utf-8") == "trading_type\neligible\n"
    assert (output_dir / "dates.txt").read_text(encoding="utf-8") == "20250102\n20250131\n"
    assert (output_dir / "trading_types.txt").read_text(encoding="utf-8") == "sh\nsz\n"

    frame_5 = pd.read_parquet(output_dir / "data" / "00005.HK.parquet")
    assert frame_5["date"].tolist() == ["20250102"]
    assert frame_5["trading_type"].tolist() == ["sh"]
    assert frame_5["eligible"].tolist() == [1]

    frame_11 = pd.read_parquet(output_dir / "data" / "00011.HK.parquet")
    assert frame_11["date"].tolist() == ["20250102", "20250131"]
    assert frame_11["trading_type"].tolist() == ["sz", "sz"]

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["dataset"] == "southbound"
    assert manifest["api"] == "rqdatac.hk.get_southbound_eligible_secs"
    assert manifest["query"]["trading_types"] == ["sh", "sz"]
    assert manifest["query"]["rebalance_frequency"] == "D"
    assert manifest["totals"]["symbols_requested"] == 3
    assert manifest["totals"]["symbols_written"] == 2
    assert manifest["missing_symbols"] == ["00012.HK"]
    assert manifest["date_source"]["mode"] == "by_date_file"

    client.hk.calls.clear()
    args.resume = True
    assert rqdata_assets.mirror_hk_southbound(args, client) == 0
    assert client.hk.calls == []


def test_mirror_hk_southbound_resume_continues_from_completed_batch_checkpoint(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    (repo_root / "artifacts" / "assets" / "universe").mkdir(parents=True)
    by_date_file = repo_root / "artifacts" / "assets" / "universe" / "hk_connect_full_by_date.csv"
    by_date_file.write_text(
        "\n".join(
            [
                "trade_date,symbol,selected",
                "20250102,00005.HK,1",
                "20250102,00011.HK,1",
                "20250131,00012.HK,1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    class _InterruptingSouthboundClient(_FakeRQSouthboundClient):
        def __init__(self):
            super().__init__()
            original = self.hk.get_southbound_eligible_secs
            self._calls_seen = 0

            def _wrapped(trading_type=None, date=None):
                self._calls_seen += 1
                if self._calls_seen == 2:
                    self.hk.calls.append({"trading_type": trading_type, "date": date})
                    raise KeyboardInterrupt()
                return original(trading_type=trading_type, date=date)

            self.hk.get_southbound_eligible_secs = _wrapped

    args = SimpleNamespace(
        config=None,
        username=None,
        password=None,
        start_date="20250101",
        end_date="20250131",
        symbol=[],
        symbols_file=None,
        by_date_file="artifacts/assets/universe/hk_connect_full_by_date.csv",
        limit=None,
        trading_type=["both"],
        rebalance_frequency="D",
        out_root="artifacts/assets/rqdata",
        name="southbound_resume_demo",
        resume=False,
        skip_existing=False,
        max_attempts=1,
        backoff_seconds=0.0,
        max_backoff_seconds=0.0,
    )

    interrupting_client = _InterruptingSouthboundClient()
    with pytest.raises(KeyboardInterrupt):
        rqdata_assets.mirror_hk_southbound(args, interrupting_client)

    output_dir = (
        repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "southbound" / "southbound_resume_demo"
    )
    partial_manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert partial_manifest["status"] == "interrupted"
    assert partial_manifest["checkpoint"]["completed_batches"] == 1
    assert partial_manifest["checkpoint"]["pending_batches"] == 3
    assert partial_manifest["batches"] == [
        {
            "date": "20250102",
            "trading_type": "sh",
            "rows": 1,
            "symbols": 1,
            "status": "completed",
            "attempts": 1,
            "started_at": partial_manifest["batches"][0]["started_at"],
            "finished_at": partial_manifest["batches"][0]["finished_at"],
        }
    ]

    frame_5 = pd.read_parquet(output_dir / "data" / "00005.HK.parquet")
    assert frame_5["date"].tolist() == ["20250102"]
    assert frame_5["trading_type"].tolist() == ["sh"]

    resume_client = _FakeRQSouthboundClient()
    args.resume = True
    assert rqdata_assets.mirror_hk_southbound(args, resume_client) == 0
    assert resume_client.hk.calls == [
        {"trading_type": "sz", "date": "20250102"},
        {"trading_type": "sh", "date": "20250131"},
        {"trading_type": "sz", "date": "20250131"},
    ]

    frame_11 = pd.read_parquet(output_dir / "data" / "00011.HK.parquet")
    assert frame_11["date"].tolist() == ["20250102", "20250131"]
    assert frame_11["trading_type"].tolist() == ["sz", "sz"]

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    assert manifest["checkpoint"]["completed_batches"] == 4
    assert manifest["checkpoint"]["pending_batches"] == 0

def test_mirror_hk_announcement_writes_symbol_history_assets(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(rqdata_assets, "_ensure_rqdatac_hk_plugin", lambda: None)

    client = _FakeRQAnnouncementClient()
    args = SimpleNamespace(
        config=None,
        username=None,
        password=None,
        start_date="20250301",
        end_date="20250331",
        field=["title", "announcement_link"],
        fields_file=[],
        symbol=["00005.HK", "00011.HK", "00012.HK"],
        symbols_file=None,
        by_date_file=None,
        limit=None,
        batch_size=2,
        out_root="artifacts/assets/rqdata",
        name="announcement_demo",
        resume=False,
        skip_existing=False,
        max_attempts=1,
        backoff_seconds=0.0,
        max_backoff_seconds=0.0,
    )

    assert rqdata_assets.mirror_hk_announcement(args, client) == 0

    assert client.hk.calls == [
        {
            "order_book_ids": ["00005.XHKG", "00011.XHKG"],
            "start_date": "20250301",
            "end_date": "20250331",
            "fields": ["title", "announcement_link"],
            "market": "hk",
        },
        {
            "order_book_ids": ["00012.XHKG"],
            "start_date": "20250301",
            "end_date": "20250331",
            "fields": ["title", "announcement_link"],
            "market": "hk",
        },
    ]

    output_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "announcement" / "announcement_demo"
    assert (output_dir / "fields.txt").read_text(encoding="utf-8") == "title\nannouncement_link\n"
    assert (output_dir / "symbols.txt").read_text(encoding="utf-8") == "00005.HK\n00011.HK\n00012.HK\n"

    frame_5 = pd.read_parquet(output_dir / "data" / "00005.HK.parquet")
    assert frame_5["info_date"].tolist() == [pd.Timestamp("2025-03-20")]
    assert frame_5["title"].tolist() == ["FY2024 results"]

    frame_11 = pd.read_parquet(output_dir / "data" / "00011.HK.parquet")
    assert frame_11["info_date"].tolist() == [pd.Timestamp("2025-03-21"), pd.Timestamp("2025-03-24")]
    assert frame_11["announcement_link"].tolist() == [
        "https://example.com/00011-1",
        "https://example.com/00011-2",
    ]

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["dataset"] == "announcement"
    assert manifest["api"] == "rqdatac.hk.get_announcement"
    assert manifest["query"]["start_date"] == "20250301"
    assert manifest["query"]["end_date"] == "20250331"
    assert manifest["query"]["fields"] == ["title", "announcement_link"]
    assert manifest["totals"]["symbols_requested"] == 3
    assert manifest["totals"]["symbols_written"] == 2
    assert manifest["missing_symbols"] == ["00012.HK"]

    client.hk.calls.clear()
    args.resume = True
    assert rqdata_assets.mirror_hk_announcement(args, client) == 0
    assert client.hk.calls == [
        {
            "order_book_ids": ["00012.XHKG"],
            "start_date": "20250301",
            "end_date": "20250331",
            "fields": ["title", "announcement_link"],
            "market": "hk",
        }
    ]

def test_mirror_hk_instrument_industry_writes_snapshot_assets(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    (repo_root / "artifacts" / "assets" / "universe").mkdir(parents=True)
    (repo_root / "artifacts" / "assets" / "universe" / "hk_connect_full_by_date.csv").write_text(
        "\n".join(
            [
                "trade_date,symbol,selected",
                "20250131,00005.HK,1",
                "20250131,00700.HK,1",
                "20250228,00005.HK,1",
                "20250228,00700.HK,1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    client = _FakeRQIndustryClient()
    args = SimpleNamespace(
        config=None,
        username=None,
        password=None,
        start_date="20250101",
        end_date="20250228",
        symbol=[],
        symbols_file=None,
        by_date_file="artifacts/assets/universe/hk_connect_full_by_date.csv",
        limit=None,
        batch_size=20,
        out_root="artifacts/assets/rqdata",
        name="industry_snapshot_demo",
        resume=False,
        skip_existing=False,
        max_attempts=1,
        backoff_seconds=0.0,
        max_backoff_seconds=0.0,
        source="citics_2019",
        level="0",
        rebalance_frequency="M",
    )

    assert rqdata_assets.mirror_hk_instrument_industry(args, client) == 0

    assert client.instrument_calls == [
        {
            "order_book_ids": ["00005.XHKG", "00700.XHKG"],
            "source": "citics_2019",
            "level": 0,
            "date": "20250131",
            "market": "hk",
        },
        {
            "order_book_ids": ["00005.XHKG", "00700.XHKG"],
            "source": "citics_2019",
            "level": 0,
            "date": "20250228",
            "market": "hk",
        },
    ]

    output_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "instrument_industry" / "industry_snapshot_demo"
    frame = pd.read_parquet(output_dir / "data" / "00005.HK.parquet")
    assert frame["symbol"].tolist() == ["00005.HK", "00005.HK"]
    assert frame["date"].dt.strftime("%Y%m%d").tolist() == ["20250131", "20250228"]
    assert frame["first_industry_name"].tolist() == ["银行", "银行"]
    assert (output_dir / "dates.txt").read_text(encoding="utf-8") == "20250131\n20250228\n"

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["dataset"] == "instrument_industry"
    assert manifest["api"] == "rqdatac.get_instrument_industry"
    assert manifest["query"]["source"] == "citics_2019"
    assert manifest["query"]["level"] == 0
    assert manifest["query"]["rebalance_frequency"] == "M"
    assert manifest["totals"]["symbols_written"] == 2

def test_mirror_hk_industry_changes_writes_symbol_assets(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    client = _FakeRQIndustryClient()
    args = SimpleNamespace(
        config=None,
        username=None,
        password=None,
        start_date="20250101",
        end_date="20251231",
        symbol=["00005.HK", "00700.HK"],
        symbols_file=None,
        by_date_file=None,
        limit=None,
        batch_size=20,
        out_root="artifacts/assets/rqdata",
        name="industry_changes_demo",
        resume=False,
        skip_existing=False,
        max_attempts=1,
        backoff_seconds=0.0,
        max_backoff_seconds=0.0,
        source="citics_2019",
        level="1",
        mapping_date="20251231",
    )

    assert rqdata_assets.mirror_hk_industry_changes(args, client) == 0

    assert client.mapping_calls == [
        {"source": "citics_2019", "date": "20251231", "market": "hk"}
    ]
    assert client.change_calls == [
        {"industry": "40", "source": "citics_2019", "level": 1, "market": "hk"},
        {"industry": "63", "source": "citics_2019", "level": 1, "market": "hk"},
    ]

    output_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "industry_changes" / "industry_changes_demo"
    frame = pd.read_parquet(output_dir / "data" / "00005.HK.parquet")
    assert frame["symbol"].tolist() == ["00005.HK"]
    assert frame["industry_code"].tolist() == ["40"]
    assert frame["industry_name"].tolist() == ["银行"]
    assert frame["cancel_date"].dt.strftime("%Y%m%d").tolist() == ["22001231"]
    assert (output_dir / "industries.txt").read_text(encoding="utf-8") == "40\n63\n"
    assert (output_dir / "industry_catalog.parquet").exists()

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["dataset"] == "industry_changes"
    assert manifest["api"] == "rqdatac.get_industry_change"
    assert manifest["query"]["source"] == "citics_2019"
    assert manifest["query"]["level"] == 1
    assert manifest["query"]["mapping_date"] == "20251231"
    assert manifest["totals"]["symbols_written"] == 2
