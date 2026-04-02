import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import yaml

from csml import data_providers
from csml.data_tools import rqdata_assets


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
            "symbol",
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
            "symbol": ["00005.HK", "00005.HK", "00005.HK"],
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
            "symbol": ["00011.HK"],
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
    assert fundamentals.columns.tolist() == ["trade_date", "symbol", "revenue", "net_profit"]
    assert fundamentals["trade_date"].tolist() == ["20250320", "20250820", "20250825"]
    assert fundamentals["symbol"].tolist() == ["00005.HK", "00005.HK", "00011.HK"]
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

def test_build_hk_pit_fundamentals_file_field_profile_full_overrides_manifest_selection(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "pit_financials" / "pit_demo"
    data_dir = asset_dir / "data"
    data_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    manifest = {
        "dataset": "pit_financials",
        "query": {"fields": ["revenue"]},
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
            "symbol",
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
            "net_profit": [10.0],
            "order_book_id": ["00005.XHKG"],
            "symbol": ["00005.HK"],
        }
    ).to_parquet(data_dir / "00005.HK.parquet", index=False)

    monkeypatch.setattr(rqdata_assets, "_load_hk_financial_fields", lambda: ["revenue", "net_profit"])
    out_path = repo_root / "artifacts" / "assets" / "fundamentals" / "pit_fundamentals_full.parquet"
    args = SimpleNamespace(
        asset_dir=str(asset_dir),
        field_profile=["full"],
        field=[],
        fields_file=[],
        out=str(out_path),
        source_universe_by_date=None,
        universe_by_date_out=None,
        symbols_out=None,
        keep_meta=False,
        duplicate_policy="keep-last",
        force=False,
    )

    assert rqdata_assets.build_hk_pit_fundamentals_file(args) == 0

    fundamentals = pd.read_parquet(out_path)
    assert fundamentals.columns.tolist() == ["trade_date", "symbol", "revenue", "net_profit"]

    output_manifest = yaml.safe_load(
        (
            repo_root
            / "artifacts"
            / "assets"
            / "fundamentals"
            / "pit_fundamentals_full.manifest.yml"
        ).read_text(encoding="utf-8")
    )
    assert output_manifest["query"]["fields"] == ["revenue", "net_profit"]
    assert output_manifest["query"]["field_profile"] == ["full"]
    assert output_manifest["query"]["field_source"] == "explicit"

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
            "symbol",
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
            "symbol": ["00005.HK"],
        }
    ).to_parquet(data_dir / "00005.HK.parquet", index=False)

    source_universe = repo_root / "artifacts" / "assets" / "universe" / "hk_connect_full_by_date.csv"
    source_universe.parent.mkdir(parents=True)
    pd.DataFrame(
        {
            "trade_date": ["20250320", "20250320"],
            "symbol": ["00005.HK", "00011.HK"],
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
        "symbol",
        "revenue",
        "goodwill_and_intangible_assets",
    ]
    assert fundamentals["goodwill_and_intangible_assets"].tolist() == [55.0]

    research_universe = pd.read_csv(research_universe_out)
    assert research_universe["symbol"].tolist() == ["00005.HK"]
    assert "stock_ticker" not in research_universe.columns
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

def test_build_hk_industry_labels_file_from_universe_grid(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "industry_changes" / "industry_demo"
    data_dir = asset_dir / "data"
    data_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    manifest = {
        "dataset": "industry_changes",
        "query": {"source": "citics_2019", "level": 1},
        "columns": [
            "symbol",
            "order_book_id",
            "start_date",
            "cancel_date",
            "industry_code",
            "industry_name",
            "industry_level",
            "industry_source",
            "first_industry_code",
            "first_industry_name",
        ],
    }
    (asset_dir / "manifest.yml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    pd.DataFrame(
        {
            "symbol": ["00005.HK", "00005.HK"],
            "order_book_id": ["00005.XHKG", "00005.XHKG"],
            "start_date": pd.to_datetime(["2025-01-01", "2025-03-15"]),
            "cancel_date": pd.to_datetime(["2025-03-15", "2200-12-31"]),
            "industry_code": ["40", "63"],
            "industry_name": ["银行", "传媒"],
            "industry_level": [1, 1],
            "industry_source": ["citics_2019", "citics_2019"],
            "first_industry_code": ["40", "63"],
            "first_industry_name": ["银行", "传媒"],
        }
    ).to_parquet(data_dir / "00005.HK.parquet", index=False)
    pd.DataFrame(
        {
            "symbol": ["00700.HK"],
            "order_book_id": ["00700.XHKG"],
            "start_date": pd.to_datetime(["2025-01-01"]),
            "cancel_date": pd.to_datetime(["2200-12-31"]),
            "industry_code": ["63"],
            "industry_name": ["传媒"],
            "industry_level": [1],
            "industry_source": ["citics_2019"],
            "first_industry_code": ["63"],
            "first_industry_name": ["传媒"],
        }
    ).to_parquet(data_dir / "00700.HK.parquet", index=False)

    universe_path = repo_root / "artifacts" / "assets" / "universe" / "hk_connect_full_by_date.csv"
    universe_path.parent.mkdir(parents=True, exist_ok=True)
    universe_path.write_text(
        "\n".join(
            [
                "trade_date,symbol,selected",
                "20250131,00005.HK,1",
                "20250228,00005.HK,1",
                "20250331,00005.HK,1",
                "20250131,00700.HK,1",
                "20250228,00700.HK,1",
                "20250331,00700.HK,1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    out_path = repo_root / "artifacts" / "assets" / "industry" / "industry_labels_m.parquet"
    symbols_out = repo_root / "artifacts" / "assets" / "industry" / "industry_symbols.txt"
    args = SimpleNamespace(
        asset_dir=str(asset_dir),
        source_universe_by_date=str(universe_path),
        daily_asset_dir=None,
        start_date=None,
        end_date=None,
        frequency="M",
        out=str(out_path),
        symbols_out=str(symbols_out),
        force=False,
    )

    assert rqdata_assets.build_hk_industry_labels_file(args) == 0

    labels = pd.read_parquet(out_path)
    assert labels["trade_date"].tolist() == [
        "20250131",
        "20250131",
        "20250228",
        "20250228",
        "20250331",
        "20250331",
    ]
    assert labels["symbol"].tolist() == [
        "00005.HK",
        "00700.HK",
        "00005.HK",
        "00700.HK",
        "00005.HK",
        "00700.HK",
    ]
    assert labels.loc[labels["symbol"] == "00005.HK", "industry_name"].tolist() == ["银行", "银行", "传媒"]
    assert labels.loc[labels["symbol"] == "00700.HK", "industry_name"].tolist() == ["传媒", "传媒", "传媒"]
    assert symbols_out.read_text(encoding="utf-8") == "00005.HK\n00700.HK\n"

    output_manifest = yaml.safe_load(
        (repo_root / "artifacts" / "assets" / "industry" / "industry_labels_m.manifest.yml").read_text(
            encoding="utf-8"
        )
    )
    assert output_manifest["dataset"] == "industry_labels_file"
    assert output_manifest["query"]["frequency"] == "M"
    assert output_manifest["grid"]["mode"] == "source_universe_by_date"
    assert output_manifest["totals"]["resolved_rows"] == 6

def test_build_hk_industry_labels_file_from_daily_assets_daily_frequency(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "industry_changes" / "industry_demo"
    data_dir = asset_dir / "data"
    data_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    manifest = {
        "dataset": "industry_changes",
        "query": {"source": "citics_2019", "level": 1},
    }
    (asset_dir / "manifest.yml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    pd.DataFrame(
        {
            "symbol": ["00005.HK", "00005.HK"],
            "order_book_id": ["00005.XHKG", "00005.XHKG"],
            "start_date": pd.to_datetime(["2025-01-01", "2025-03-15"]),
            "cancel_date": pd.to_datetime(["2025-03-15", "2200-12-31"]),
            "industry_code": ["40", "63"],
            "industry_name": ["银行", "传媒"],
            "industry_level": [1, 1],
            "industry_source": ["citics_2019", "citics_2019"],
        }
    ).to_parquet(data_dir / "00005.HK.parquet", index=False)

    daily_asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "daily_demo"
    (daily_asset_dir / "data").mkdir(parents=True)
    pd.DataFrame(
        {
            "trade_date": ["20250314", "20250317", "20250331"],
            "symbol": ["00005.HK", "00005.HK", "00005.HK"],
            "close": [10.0, 10.5, 11.0],
        }
    ).to_parquet(daily_asset_dir / "data" / "00005.HK.parquet", index=False)

    out_path = repo_root / "artifacts" / "assets" / "industry" / "industry_labels_d.parquet"
    args = SimpleNamespace(
        asset_dir=str(asset_dir),
        source_universe_by_date=None,
        daily_asset_dir=str(daily_asset_dir),
        start_date="20250314",
        end_date="20250331",
        frequency="D",
        out=str(out_path),
        symbols_out=None,
        force=False,
    )

    assert rqdata_assets.build_hk_industry_labels_file(args) == 0

    labels = pd.read_parquet(out_path)
    assert labels["trade_date"].tolist() == ["20250314", "20250317", "20250331"]
    assert labels["industry_name"].tolist() == ["银行", "传媒", "传媒"]

    output_manifest = yaml.safe_load(
        (repo_root / "artifacts" / "assets" / "industry" / "industry_labels_d.manifest.yml").read_text(
            encoding="utf-8"
        )
    )
    assert output_manifest["query"]["frequency"] == "D"
    assert output_manifest["grid"]["mode"] == "daily_asset_dir"
    assert output_manifest["totals"]["resolved_rows"] == 3
