import numpy as np
import pandas as pd

from csml.research.hk_intraday_download import flatten_intraday_payload, normalize_hk_symbols
from csml.research.hk_intraday_slippage_report import (
    build_liquidity_bucket_summary,
    compute_daily_slippage_metrics,
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
        order_book_to_ts_code={"00700.XHKG": "00700.HK"},
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
        "ts_code",
    ]
    assert flat["rq_order_book_id"].tolist() == ["00700.XHKG", "00700.XHKG"]
    assert flat["ts_code"].tolist() == ["00700.HK", "00700.HK"]
    assert flat["amount"].tolist() == [1_002_500.0, 1_522_500.0]


def test_compute_daily_slippage_metrics_aggregates_session_prices():
    frame = pd.DataFrame(
        {
            "ts_code": ["00700.HK", "00700.HK"],
            "trade_datetime": [
                pd.Timestamp("2026-03-26 09:35:00"),
                pd.Timestamp("2026-03-26 09:40:00"),
            ],
            "open": [100.0, 101.0],
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
    assert np.isclose(row["session_vwap"], 103.75)
    assert np.isclose(row["buy_open_to_vwap_bps"], 375.0)
    assert np.isclose(row["buy_open_to_close_bps"], 200.0)


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

    assert summary["rows"] == 4
    assert summary["symbols"] == 4
    assert summary["trade_dates"] == 2
    assert np.isclose(summary["buy_open_to_vwap_bps"]["median"], 7.5)
    assert len(liquidity) == 2
    assert liquidity["count"].sum() == 4
