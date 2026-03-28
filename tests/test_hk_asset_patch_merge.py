from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from csml.research.hk_asset_patch_merge import merge_asset_patch


def _write_daily_snapshot(root: Path, name: str, *, end_date: str) -> Path:
    asset_dir = root / name
    data_dir = asset_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "trade_date": ["20260318"],
            "ts_code": ["00005.HK"],
            "order_book_id": ["00005.XHKG"],
            "open": [10.0],
            "close": [10.5],
        }
    ).to_parquet(data_dir / "00005.HK.parquet", index=False)
    (asset_dir / "fields.txt").write_text("open\nclose\n", encoding="utf-8")
    (asset_dir / "symbols.txt").write_text("00005.HK\n00006.HK\n", encoding="utf-8")
    (asset_dir / "audit.csv").write_text("", encoding="utf-8")
    (asset_dir / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "daily",
                "api": "rqdatac.get_price",
                "output_dir": str(asset_dir),
                "query": {
                    "start_date": "20000104",
                    "end_date": end_date,
                    "frequency": "1d",
                    "adjust_type": None,
                    "skip_suspended": True,
                    "fields": ["open", "close"],
                    "fields_file": [],
                    "field_source": "default",
                    "base_fields": ["open", "close"],
                },
                "symbol_source": {
                    "mode": "explicit",
                    "symbols_file": str(asset_dir / "symbols.txt"),
                    "count": 2,
                },
                "columns": ["trade_date", "ts_code", "order_book_id", "open", "close"],
                "totals": {"rows": 1},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return asset_dir


def _write_daily_patch(root: Path, name: str) -> Path:
    asset_dir = root / name
    data_dir = asset_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "trade_date": ["20260318", "20260319"],
            "ts_code": ["00005.HK", "00005.HK"],
            "order_book_id": ["00005.XHKG", "00005.XHKG"],
            "open": [11.0, 12.0],
            "close": [11.5, 12.5],
            "symbol": ["00005.HK", "00005.HK"],
        }
    ).to_parquet(data_dir / "00005.HK.parquet", index=False)
    pd.DataFrame(
        {
            "trade_date": ["20260319"],
            "ts_code": ["00006.HK"],
            "order_book_id": ["00006.XHKG"],
            "open": [20.0],
            "close": [21.0],
            "symbol": ["00006.HK"],
        }
    ).to_parquet(data_dir / "00006.HK.parquet", index=False)
    (asset_dir / "fields.txt").write_text("open\nclose\n", encoding="utf-8")
    (asset_dir / "symbols.txt").write_text("00005.HK\n00006.HK\n", encoding="utf-8")
    (asset_dir / "audit.csv").write_text("", encoding="utf-8")
    (asset_dir / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "daily",
                "api": "rqdatac.get_price",
                "output_dir": str(asset_dir),
                "query": {
                    "start_date": "20260319",
                    "end_date": "20260319",
                    "frequency": "1d",
                    "adjust_type": None,
                    "skip_suspended": True,
                    "fields": ["open", "close"],
                    "fields_file": [],
                    "field_source": "default",
                    "base_fields": ["open", "close"],
                },
                "symbol_source": {
                    "mode": "explicit",
                    "symbols_file": str(asset_dir / "symbols.txt"),
                    "count": 2,
                },
                "columns": ["trade_date", "ts_code", "order_book_id", "open", "close", "symbol"],
                "totals": {"rows": 3},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return asset_dir


def _write_valuation_snapshot(root: Path, name: str, *, end_date: str) -> Path:
    asset_dir = root / name
    data_dir = asset_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "ts_code": ["00005.HK"],
            "order_book_id": ["00005.XHKG"],
            "trade_date": ["20260324"],
            "hk_total_market_val": [100.0],
            "pe_ratio_ttm": [10.0],
        }
    ).to_parquet(data_dir / "00005.HK.parquet", index=False)
    (asset_dir / "fields.txt").write_text("hk_total_market_val\npe_ratio_ttm\n", encoding="utf-8")
    (asset_dir / "symbols.txt").write_text("00005.HK\n", encoding="utf-8")
    (asset_dir / "audit.csv").write_text("", encoding="utf-8")
    (asset_dir / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "valuation",
                "api": "rqdatac.get_factor",
                "output_dir": str(asset_dir),
                "query": {
                    "start_date": "20000101",
                    "end_date": end_date,
                    "date_column": "trade_date",
                    "fields": ["hk_total_market_val", "pe_ratio_ttm"],
                    "fields_file": [],
                    "field_source": "default",
                    "base_fields": ["hk_total_market_val", "pe_ratio_ttm"],
                },
                "symbol_source": {
                    "mode": "explicit",
                    "symbols_file": str(asset_dir / "symbols.txt"),
                    "count": 1,
                },
                "columns": [
                    "ts_code",
                    "order_book_id",
                    "trade_date",
                    "hk_total_market_val",
                    "pe_ratio_ttm",
                ],
                "totals": {"rows": 1},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return asset_dir


def _write_valuation_patch(root: Path, name: str) -> Path:
    asset_dir = root / name
    data_dir = asset_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "ts_code": ["00005.HK", "00005.HK"],
            "order_book_id": ["00005.XHKG", "00005.XHKG"],
            "trade_date": ["20260324", "20260326"],
            "hk_total_market_val": [101.0, 103.0],
            "pe_ratio_ttm": [11.0, 13.0],
        }
    ).to_parquet(data_dir / "00005.HK.parquet", index=False)
    (asset_dir / "fields.txt").write_text("hk_total_market_val\npe_ratio_ttm\n", encoding="utf-8")
    (asset_dir / "symbols.txt").write_text("00005.HK\n", encoding="utf-8")
    (asset_dir / "audit.csv").write_text("", encoding="utf-8")
    (asset_dir / "manifest.yml").write_text(
        yaml.safe_dump(
            {
                "dataset": "valuation",
                "api": "rqdatac.get_factor",
                "output_dir": str(asset_dir),
                "query": {
                    "start_date": "20260325",
                    "end_date": "20260326",
                    "date_column": "trade_date",
                    "fields": ["hk_total_market_val", "pe_ratio_ttm"],
                    "fields_file": [],
                    "field_source": "default",
                    "base_fields": ["hk_total_market_val", "pe_ratio_ttm"],
                },
                "symbol_source": {
                    "mode": "explicit",
                    "symbols_file": str(asset_dir / "symbols.txt"),
                    "count": 1,
                },
                "columns": [
                    "ts_code",
                    "order_book_id",
                    "trade_date",
                    "hk_total_market_val",
                    "pe_ratio_ttm",
                ],
                "totals": {"rows": 2},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return asset_dir


def test_merge_asset_patch_daily_updates_alias_and_preserves_base_schema(tmp_path: Path) -> None:
    base_dir = _write_daily_snapshot(tmp_path, "daily_base", end_date="20260318")
    patch_dir = _write_daily_patch(tmp_path, "daily_patch")
    out_dir = tmp_path / "daily_latest"
    alias_path = tmp_path / "daily_alias"

    result = merge_asset_patch(
        base_dir=base_dir,
        patch_dir=patch_dir,
        out_dir=out_dir,
        alias_path=alias_path,
        overwrite=False,
    )

    assert result["dataset"] == "daily"
    assert alias_path.is_symlink()
    assert alias_path.resolve() == out_dir.resolve()

    merged = pd.read_parquet(out_dir / "data" / "00005.HK.parquet")
    assert merged["trade_date"].tolist() == ["20260318", "20260319"]
    assert merged["symbol"].tolist() == ["00005.HK", "00005.HK"]
    assert merged["open"].tolist() == [11.0, 12.0]
    assert "ts_code" not in merged.columns

    patch_only = pd.read_parquet(out_dir / "data" / "00006.HK.parquet")
    assert patch_only["trade_date"].tolist() == ["20260319"]
    assert patch_only["symbol"].tolist() == ["00006.HK"]

    manifest = yaml.safe_load((out_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["columns"] == ["trade_date", "symbol", "order_book_id", "open", "close"]
    assert manifest["query"]["end_date"] == "20260319"
    assert manifest["totals"]["symbols_written"] == 2


def test_merge_asset_patch_dated_prefers_patch_row_for_overlap(tmp_path: Path) -> None:
    base_dir = _write_valuation_snapshot(tmp_path, "valuation_base", end_date="20260324")
    patch_dir = _write_valuation_patch(tmp_path, "valuation_patch")
    out_dir = tmp_path / "valuation_latest"

    result = merge_asset_patch(
        base_dir=base_dir,
        patch_dir=patch_dir,
        out_dir=out_dir,
        alias_path=None,
        overwrite=False,
    )

    assert result["dataset"] == "valuation"

    merged = pd.read_parquet(out_dir / "data" / "00005.HK.parquet")
    assert merged["symbol"].tolist() == ["00005.HK", "00005.HK"]
    assert merged["trade_date"].tolist() == ["20260324", "20260326"]
    assert merged["hk_total_market_val"].tolist() == [101.0, 103.0]
    assert "ts_code" not in merged.columns

    manifest = yaml.safe_load((out_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["columns"] == [
        "symbol",
        "order_book_id",
        "trade_date",
        "hk_total_market_val",
        "pe_ratio_ttm",
    ]
    assert manifest["query"]["end_date"] == "20260326"
    assert manifest["totals"]["rows"] == 2
