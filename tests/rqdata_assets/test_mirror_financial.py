import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import yaml

from cstree import data_providers
from cstree.data_tools import rqdata_assets

from tests.rqdata_assets._fakes import (
    _FakeRQPitClient,
    _WhitespaceFieldRQPitClient,
    _FakeRQDetailsClient,
    _FlakyRQPitClient,
    _QuotaRQPitClient,
    _FieldFallbackRQPitClient,
)


class _QuarterRangeRQPitClient:
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
        all_quarters = ["2024q4", "2025q1"]
        selected_quarters = [
            quarter for quarter in all_quarters if start_quarter <= quarter <= end_quarter
        ]
        values = {
            ("00005.XHKG", "2024q4"): (100.0, 10.0, "2025-03-20"),
            ("00005.XHKG", "2025q1"): (120.0, 12.0, "2025-08-20"),
            ("00011.XHKG", "2025q1"): (220.0, 22.0, "2025-08-25"),
        }
        rows: list[dict] = []
        index: list[tuple[str, str]] = []
        for order_book_id in order_book_ids:
            for quarter in selected_quarters:
                payload = values.get((order_book_id, quarter))
                if payload is None:
                    continue
                revenue, net_profit, info_date = payload
                rows.append(
                    {
                        "info_date": pd.Timestamp(info_date),
                        "fiscal_year": pd.Timestamp("2025-12-31"),
                        "standard": "IFRS",
                        "if_adjusted": 0,
                        "rice_create_tm": pd.Timestamp(f"{info_date} 09:00:00"),
                        "revenue": revenue,
                        "net_profit": net_profit,
                    }
                )
                index.append((order_book_id, quarter))
        if not rows:
            return pd.DataFrame(
                columns=list(fields),
                index=pd.MultiIndex.from_arrays([[], []], names=["order_book_id", "quarter"]),
            )
        return pd.DataFrame(
            rows,
            index=pd.MultiIndex.from_tuples(index, names=["order_book_id", "quarter"]),
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


def test_mirror_hk_pit_financials_quarter_chunk_size_composes_strict_snapshot(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    client = _QuarterRangeRQPitClient()
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
        quarter_chunk_size=1,
        out_root="artifacts/assets/rqdata",
        name="pit_partitioned_demo",
        resume=False,
        skip_existing=False,
        max_attempts=1,
        backoff_seconds=0.0,
        max_backoff_seconds=0.0,
    )

    assert rqdata_assets.mirror_hk_pit_financials(args, client) == 0
    assert client.calls == [
        {
            "order_book_ids": ["00005.XHKG", "00011.XHKG"],
            "fields": ["revenue", "net_profit"],
            "start_quarter": "2024q4",
            "end_quarter": "2024q4",
            "date": "20260310",
            "statements": "latest",
            "market": "hk",
        },
        {
            "order_book_ids": ["00005.XHKG", "00011.XHKG"],
            "fields": ["revenue", "net_profit"],
            "start_quarter": "2025q1",
            "end_quarter": "2025q1",
            "date": "20260310",
            "statements": "latest",
            "market": "hk",
        },
    ]

    output_dir = (
        repo_root
        / "artifacts"
        / "assets"
        / "rqdata"
        / "hk"
        / "pit_financials"
        / "pit_partitioned_demo"
    )
    first = pd.read_parquet(output_dir / "data" / "00005.HK.parquet")
    assert first["quarter"].tolist() == ["2024q4", "2025q1"]
    assert first["revenue"].tolist() == [100.0, 120.0]

    second = pd.read_parquet(output_dir / "data" / "00011.HK.parquet")
    assert second["quarter"].tolist() == ["2025q1"]
    assert second["revenue"].tolist() == [220.0]

    assert (
        output_dir
        / ".parts"
        / "hk"
        / "pit_financials"
        / "pit_partitioned_demo__part_2024q4_2024q4"
        / "manifest.yml"
    ).exists()
    assert (
        output_dir
        / ".parts"
        / "hk"
        / "pit_financials"
        / "pit_partitioned_demo__part_2025q1_2025q1"
        / "manifest.yml"
    ).exists()

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    assert manifest["api"] == "rqdatac.get_pit_financials_ex + quarter_partition_compose"
    assert manifest["partitioning"]["strategy"] == "quarter_window_parts"
    assert manifest["partitioning"]["strict_full_snapshot"] is True
    assert manifest["partitioning"]["quarter_chunk_size"] == 1
    assert [part["start_quarter"] for part in manifest["partitioning"]["parts"]] == [
        "2024q4",
        "2025q1",
    ]
    assert manifest["totals"]["symbols_requested"] == 2
    assert manifest["totals"]["symbols_written"] == 2


def test_patch_hk_pit_financials_merges_recent_quarters_from_base_snapshot(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    base_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "pit_financials" / "pit_base"
    base_data_dir = base_dir / "data"
    base_data_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(rqdata_assets, "_ensure_rqdatac_hk_plugin", lambda: None)

    pd.DataFrame(
        {
            "symbol": ["00005.HK", "00005.HK"],
            "order_book_id": ["00005.XHKG", "00005.XHKG"],
            "quarter": ["2023q4", "2024q4"],
            "info_date": pd.to_datetime(["2024-03-20", "2025-03-01"]),
            "revenue": [80.0, 90.0],
            "net_profit": [8.0, 9.0],
        }
    ).to_parquet(base_data_dir / "00005.HK.parquet", index=False)
    pd.DataFrame(
        {
            "symbol": ["00012.HK"],
            "order_book_id": ["00012.XHKG"],
            "quarter": ["2023q4"],
            "info_date": pd.to_datetime(["2024-03-22"]),
            "revenue": [70.0],
            "net_profit": [7.0],
        }
    ).to_parquet(base_data_dir / "00012.HK.parquet", index=False)
    (base_dir / "fields.txt").write_text("revenue\nnet_profit\n", encoding="utf-8")
    (base_dir / "symbols.txt").write_text(
        "00005.HK\n00012.HK\n00013.HK\n",
        encoding="utf-8",
    )
    (base_dir / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "pit_financials",
                "status": "completed",
                "query": {
                    "start_quarter": "2023q4",
                    "end_quarter": "2025q1",
                    "date": "20260424",
                    "statements": "latest",
                    "fields": ["revenue", "net_profit"],
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
        base_asset_dir=str(base_dir),
        target_date="20260430",
        patch_start_quarter="2024q4",
        patch_end_quarter="2025q1",
        statements="latest",
        symbol=[],
        symbols_file=None,
        limit=None,
        batch_size=20,
        out_root="artifacts/assets/rqdata",
        name="pit_patch_demo",
        resume=False,
        skip_existing=False,
        max_attempts=1,
        backoff_seconds=0.0,
        max_backoff_seconds=0.0,
    )

    assert rqdata_assets.patch_hk_pit_financials(args, client) == 0
    assert client.calls == [
        {
            "order_book_ids": ["00005.XHKG", "00012.XHKG", "00013.XHKG"],
            "fields": ["revenue", "net_profit"],
            "start_quarter": "2024q4",
            "end_quarter": "2025q1",
            "date": "20260430",
            "statements": "latest",
            "market": "hk",
        }
    ]

    output_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "pit_financials" / "pit_patch_demo"
    patched = pd.read_parquet(output_dir / "data" / "00005.HK.parquet")
    assert patched["quarter"].tolist() == ["2023q4", "2024q4", "2025q1"]
    assert patched["revenue"].tolist() == [80.0, 100.0, 120.0]
    assert patched["net_profit"].tolist() == [8.0, 10.0, 12.0]

    linked = pd.read_parquet(output_dir / "data" / "00012.HK.parquet")
    assert linked["quarter"].tolist() == ["2023q4"]

    audit = pd.read_csv(output_dir / "audit.csv")
    status_map = dict(zip(audit["symbol"], audit["status"]))
    assert status_map["00005.HK"] == "merged_patch"
    assert status_map["00012.HK"] == "linked_base"
    assert status_map["00013.HK"] == "missing_base_and_patch"

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    assert manifest["query"]["date"] == "20260430"
    assert manifest["patch"]["strict_full_snapshot"] is False
    assert manifest["patch"]["base_as_of"] == "20260424"
    assert manifest["status_counts"] == {
        "merged_patch": 1,
        "linked_base": 1,
        "missing_base_and_patch": 1,
    }
    assert manifest["totals"]["symbols_written"] == 2
    assert manifest["totals"]["symbols_missing_remote"] == 1


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
