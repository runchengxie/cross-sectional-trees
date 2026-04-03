import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import yaml

from csml.data_tools import rqdata_assets
from csml.research.hk_intraday_download import flatten_intraday_payload, normalize_hk_symbols
from csml.research.hk_intraday_slippage_report import (
    build_daily_metrics_from_inputs,
    build_liquidity_bucket_summary,
    compute_daily_slippage_metrics,
    resolve_input_parquet_paths,
    summarize_slippage_metrics,
)


def test_normalize_hk_symbols_maps_to_order_book_ids():
    assert normalize_hk_symbols(["700.HK", "00700.XHKG", "00005.HK"]) == [
        "00005.XHKG",
        "00700.XHKG",
    ]


def test_flatten_intraday_payload_flattens_multiindex_frame():
    index = pd.MultiIndex.from_tuples(
        [
            ("00700.XHKG", pd.Timestamp("2026-03-26 09:35:00")),
            ("00700.XHKG", pd.Timestamp("2026-03-26 09:40:00")),
        ],
        names=["order_book_id", "datetime"],
    )
    payload = pd.DataFrame(
        {
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.5, 101.5],
            "volume": [10_000.0, 15_000.0],
            "total_turnover": [1_002_500.0, 1_522_500.0],
        },
        index=index,
    )

    flat = flatten_intraday_payload(
        payload,
        order_book_to_symbol={"00700.XHKG": "00700.HK"},
    )

    assert list(flat.columns) == [
        "rq_order_book_id",
        "trade_datetime",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "symbol",
    ]
    assert flat["rq_order_book_id"].tolist() == ["00700.XHKG", "00700.XHKG"]
    assert flat["symbol"].tolist() == ["00700.HK", "00700.HK"]
    assert flat["amount"].tolist() == [1_002_500.0, 1_522_500.0]


def test_compute_daily_slippage_metrics_aggregates_session_prices():
    frame = pd.DataFrame(
        {
            "symbol": ["00700.HK", "00700.HK"],
            "trade_datetime": [
                pd.Timestamp("2026-03-26 09:35:00"),
                pd.Timestamp("2026-03-26 09:40:00"),
            ],
            "open": [100.0, 101.0],
            "high": [101.0, 102.5],
            "low": [99.0, 100.5],
            "close": [100.5, 102.0],
            "volume": [10.0, 30.0],
            "amount": [1_000.0, 3_150.0],
        }
    )

    daily = compute_daily_slippage_metrics(frame)

    assert len(daily) == 1
    row = daily.iloc[0]
    assert row["open_price"] == 100.0
    assert row["close_price"] == 102.0
    assert row["session_volume"] == 40.0
    assert row["session_amount"] == 4_150.0
    assert np.isclose(row["session_vwap"], 101.15625)
    assert np.isclose(row["buy_open_to_vwap_bps"], 115.625)
    assert np.isclose(row["buy_open_to_close_bps"], 200.0)


def test_compute_daily_slippage_metrics_accepts_rq_order_book_id_and_normalizes_symbol():
    frame = pd.DataFrame(
        {
            "rq_order_book_id": ["700.XHKG", "00700.XHKG"],
            "trade_datetime": [
                pd.Timestamp("2026-03-26 09:35:00"),
                pd.Timestamp("2026-03-26 09:40:00"),
            ],
            "open": [100.0, 101.0],
            "high": [101.0, 102.5],
            "low": [99.0, 100.5],
            "close": [100.5, 102.0],
            "volume": [10.0, 30.0],
            "amount": [1_000.0, 3_150.0],
        }
    )

    daily = compute_daily_slippage_metrics(frame)

    assert daily["symbol"].tolist() == ["00700.HK"]


def test_compute_daily_slippage_metrics_rejects_missing_symbol_aliases_with_symbol_first_message():
    frame = pd.DataFrame(
        {
            "trade_datetime": [pd.Timestamp("2026-03-26 09:35:00")],
            "open": [100.0],
            "close": [100.5],
            "volume": [10.0],
            "amount": [1_000.0],
        }
    )

    with pytest.raises(SystemExit, match="missing a canonical symbol column"):
        compute_daily_slippage_metrics(frame)


def test_summarize_slippage_metrics_and_liquidity_buckets():
    daily = pd.DataFrame(
        {
            "symbol": ["A", "B", "C", "D"],
            "trade_date": pd.to_datetime(["2026-03-24", "2026-03-24", "2026-03-25", "2026-03-25"]),
            "bar_count": [66, 66, 66, 66],
            "session_amount": [1_000_000.0, 2_000_000.0, 3_000_000.0, 4_000_000.0],
            "buy_open_to_vwap_bps": [5.0, 10.0, -8.0, 20.0],
            "abs_open_to_vwap_bps": [5.0, 10.0, 8.0, 20.0],
            "buy_open_to_close_bps": [12.0, -6.0, 5.0, 25.0],
            "abs_open_to_close_bps": [12.0, 6.0, 5.0, 25.0],
        }
    )

    summary = summarize_slippage_metrics(daily)
    liquidity = build_liquidity_bucket_summary(daily, n_buckets=2)

    assert summary["vwap_method"] == "bar_price_volume_proxy"
    assert summary["rows"] == 4
    assert summary["symbols"] == 4
    assert summary["trade_dates"] == 2
    assert np.isclose(summary["buy_open_to_vwap_bps"]["median"], 7.5)
    assert len(liquidity) == 2
    assert liquidity["count"].sum() == 4


def test_resolve_input_parquet_paths_prefers_parts_dir(tmp_path):
    output_file = tmp_path / "hk_all_5m_sample.parquet"
    output_file.write_text("placeholder", encoding="utf-8")
    parts_dir = tmp_path / "hk_all_5m_sample.parts"
    parts_dir.mkdir()
    batch_a = parts_dir / "batch_0001.parquet"
    batch_b = parts_dir / "batch_0002.parquet"
    pd.DataFrame({"x": [1]}).to_parquet(batch_a, index=False)
    pd.DataFrame({"x": [2]}).to_parquet(batch_b, index=False)

    resolved = resolve_input_parquet_paths([str(output_file)])

    assert resolved == [batch_a, batch_b]


def test_build_daily_metrics_from_inputs_aggregates_part_files(tmp_path):
    parts_dir = tmp_path / "hk_all_5m_sample.parts"
    parts_dir.mkdir()
    batch_a = pd.DataFrame(
        {
            "symbol": ["00005.HK", "00005.HK"],
            "trade_datetime": [
                pd.Timestamp("2026-03-24 09:35:00"),
                pd.Timestamp("2026-03-24 09:40:00"),
            ],
            "open": [60.0, 61.0],
            "close": [60.5, 61.5],
            "volume": [10.0, 20.0],
            "amount": [600.0, 1_230.0],
        }
    )
    batch_b = pd.DataFrame(
        {
            "symbol": ["00700.HK", "00700.HK"],
            "trade_datetime": [
                pd.Timestamp("2026-03-25 09:35:00"),
                pd.Timestamp("2026-03-25 09:40:00"),
            ],
            "open": [500.0, 501.0],
            "close": [501.0, 502.0],
            "volume": [5.0, 15.0],
            "amount": [2_505.0, 7_530.0],
        }
    )
    batch_a.to_parquet(parts_dir / "batch_0001.parquet", index=False)
    batch_b.to_parquet(parts_dir / "batch_0002.parquet", index=False)

    daily = build_daily_metrics_from_inputs([str(parts_dir)])

    assert len(daily) == 2
    assert daily["symbol"].tolist() == ["00005.HK", "00700.HK"]
    assert daily["trade_date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-03-24", "2026-03-25"]


def test_resolve_input_parquet_paths_accepts_intraday_asset_dir(tmp_path):
    asset_dir = tmp_path / "artifacts" / "assets" / "rqdata" / "hk" / "intraday" / "demo_asset"
    data_dir = asset_dir / "data"
    data_dir.mkdir(parents=True)
    (asset_dir / "manifest.yml").write_text("dataset: intraday\n", encoding="utf-8")

    output_file = data_dir / "hk_all_5m_sample.parquet"
    output_file.write_text("placeholder", encoding="utf-8")
    parts_dir = data_dir / "hk_all_5m_sample.parts"
    parts_dir.mkdir()
    batch_a = parts_dir / "batch_0001.parquet"
    batch_b = parts_dir / "batch_0002.parquet"
    pd.DataFrame({"x": [1]}).to_parquet(batch_a, index=False)
    pd.DataFrame({"x": [2]}).to_parquet(batch_b, index=False)

    resolved = resolve_input_parquet_paths([str(asset_dir)])

    assert resolved == [batch_a, batch_b]


def test_build_hk_intraday_asset_packages_cache_files_for_reuse(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    source_dir = repo_root / "artifacts" / "cache" / "intraday"
    source_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    output_file = source_dir / "hk_all_5m_demo.parquet"
    frame = pd.DataFrame(
        {
            "symbol": ["00005.HK", "00005.HK", "00700.HK"],
            "trade_datetime": [
                pd.Timestamp("2026-03-24 09:35:00"),
                pd.Timestamp("2026-03-24 09:40:00"),
                pd.Timestamp("2026-03-25 09:35:00"),
            ],
            "open": [60.0, 61.0, 500.0],
            "high": [60.5, 61.5, 501.0],
            "low": [59.5, 60.5, 499.0],
            "close": [60.2, 61.2, 500.5],
            "volume": [10.0, 20.0, 5.0],
            "amount": [602.0, 1224.0, 2502.5],
            "rq_order_book_id": ["00005.XHKG", "00005.XHKG", "00700.XHKG"],
        }
    )
    frame.to_parquet(output_file, index=False)

    meta_path = source_dir / "hk_all_5m_demo.meta.json"
    meta_path.write_text(
        json.dumps(
            {
                "dataset": "hk_intraday_cache",
                "start_date": "20260324",
                "end_date": "20260325",
                "frequency": "5m",
                "adjust_type": "pre",
                "rows": 3,
                "symbols_requested": 3,
                "symbols_downloaded": 2,
                "columns": [
                    "symbol",
                    "trade_datetime",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "amount",
                    "rq_order_book_id",
                ],
                "fields": ["open", "high", "low", "close", "volume", "total_turnover"],
                "bytes_used_delta": 123456,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    parts_dir = source_dir / "hk_all_5m_demo.parts"
    parts_dir.mkdir()
    frame.iloc[:2].to_parquet(parts_dir / "batch_0001.parquet", index=False)
    frame.iloc[2:].to_parquet(parts_dir / "batch_0002.parquet", index=False)

    args = SimpleNamespace(
        input=[str(output_file)],
        out_root="artifacts/assets/rqdata",
        name="hk_intraday_demo_latest",
        alias="artifacts/assets/rqdata/hk/intraday/hk_intraday_latest",
    )

    assert rqdata_assets.build_hk_intraday_asset(args) == 0

    asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "intraday" / "hk_intraday_demo_latest"
    assert asset_dir.exists()
    assert (asset_dir / "data" / output_file.name).exists()
    assert not (asset_dir / "data" / output_file.name).is_symlink()
    assert (asset_dir / "data" / meta_path.name).exists()
    assert (asset_dir / "data" / parts_dir.name / "batch_0001.parquet").exists()

    manifest = yaml.safe_load((asset_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["dataset"] == "intraday"
    assert manifest["source_kind"] == "packaged_from_local_intraday_cache"
    assert manifest["query"]["start_date"] == "20260324"
    assert manifest["query"]["end_date"] == "20260325"

    fields = (asset_dir / "fields.txt").read_text(encoding="utf-8").splitlines()
    assert fields == ["open", "high", "low", "close", "volume", "amount"]
    inputs = (asset_dir / "inputs.txt").read_text(encoding="utf-8").splitlines()
    assert inputs == [str(output_file)]

    alias_path = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "intraday" / "hk_intraday_latest"
    assert alias_path.is_symlink()
    assert alias_path.resolve() == asset_dir

    resolved = resolve_input_parquet_paths([str(asset_dir)])
    assert resolved == [
        asset_dir / "data" / "hk_all_5m_demo.parts" / "batch_0001.parquet",
        asset_dir / "data" / "hk_all_5m_demo.parts" / "batch_0002.parquet",
    ]

    second_args = SimpleNamespace(
        input=[str(output_file)],
        out_root="artifacts/assets/rqdata",
        name="hk_intraday_demo_latest_v2",
        alias="artifacts/assets/rqdata/hk/intraday/hk_intraday_latest",
    )
    assert rqdata_assets.build_hk_intraday_asset(second_args) == 0

    second_asset_dir = (
        repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "intraday" / "hk_intraday_demo_latest_v2"
    )
    assert second_asset_dir.exists()
    assert alias_path.is_symlink()
    assert alias_path.resolve() == second_asset_dir
    assert asset_dir.is_dir()
