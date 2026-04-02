import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import yaml

from csml import data_providers
from csml.data_tools import rqdata_assets

from tests.rqdata_assets._fakes import (
    _FakeRQPitClient,
    _WhitespaceFieldRQPitClient,
    _FakeRQDetailsClient,
    _FlakyRQPitClient,
    _QuotaRQPitClient,
    _FieldFallbackRQPitClient,
)


def test_mirror_hk_pit_financials_uses_config_universe_with_legacy_symbol_column_and_writes_manifest(
    tmp_path, monkeypatch
):
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
    assert first["symbol"].tolist() == ["00005.HK", "00005.HK"]
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
    assert detail["symbol"].tolist() == ["00005.HK", "00005.HK"]
    assert detail["field"].tolist() == ["revenue", "revenue"]
    assert detail["subject"].tolist() == ["保费收入", "手续费收入"]

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["dataset"] == "financial_details"
    assert manifest["totals"]["symbols_requested"] == 2
    assert manifest["totals"]["symbols_written"] == 1
    assert manifest["missing_symbols"] == ["00011.HK"]
    assert manifest["field_coverage"] == [
        {
            "field": "revenue",
            "nonnull_rows": 2,
            "symbols_with_values": 1,
        }
    ]

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

def test_mirror_hk_pit_financials_resume_accepts_legacy_ts_code_storage_and_writes_audit(
    tmp_path, monkeypatch
):
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
    status_map = dict(zip(audit["symbol"], audit["status"]))
    assert status_map["00005.HK"] == "skipped_existing"
    assert status_map["00011.HK"] == "written"

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["totals"]["symbols_written"] == 2
    assert manifest["totals"]["symbols_newly_written"] == 1
    assert manifest["totals"]["symbols_skipped_existing"] == 1
    assert manifest["status_counts"]["skipped_existing"] == 1
    assert manifest["status_counts"]["written"] == 1

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
    assert audit.loc[audit["symbol"] == "00005.HK", "attempts"].iloc[0] == 2

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["batches"][0]["attempts"] == 2
    assert manifest["status"] == "completed"

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
    status_map = dict(zip(audit["symbol"], audit["status"]))
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
    assert audit.loc[audit["symbol"] == "00005.HK", "status"].iloc[0] == "written"
    assert (
        audit.loc[audit["symbol"] == "00005.HK", "dropped_fields"].iloc[0]
        == "goodwill_and_intangible_assets"
    )
