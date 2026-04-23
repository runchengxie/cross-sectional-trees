import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import yaml

from cstree import data_providers
from cstree.data_tools import rqdata_assets


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
    assert [group.symbol for group in groups] == ["00013.HK", "00005.HK"]
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
