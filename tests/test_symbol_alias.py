import pandas as pd
import pytest

from cstree.data_tools.symbols import (
    canonicalize_symbol_columns,
    drop_legacy_symbol_columns,
    ensure_symbol_columns,
)
from cstree.pipeline import load_universe_by_date
from cstree.pipeline.support import _annotate_positions_window, _build_rebalance_diff


def test_ensure_symbol_columns_accepts_stock_ticker_only():
    frame = pd.DataFrame({"stock_ticker": ["AAA", " BBB ", ""], "weight": [0.3, 0.4, 0.3]})
    out = ensure_symbol_columns(frame, context="positions.csv")
    assert out["symbol"].tolist() == ["AAA", "BBB", ""]
    assert "ts_code" not in out.columns
    assert out["stock_ticker"].tolist() == ["AAA", " BBB ", ""]


def test_ensure_symbol_columns_accepts_symbol_only():
    frame = pd.DataFrame({"symbol": ["AAA", " BBB ", ""], "weight": [0.3, 0.4, 0.3]})
    out = ensure_symbol_columns(frame, context="positions.csv")
    assert out["symbol"].tolist() == ["AAA", "BBB", ""]
    assert "ts_code" not in out.columns
    assert "stock_ticker" not in out.columns


def test_ensure_symbol_columns_accepts_order_book_id_only():
    frame = pd.DataFrame({"order_book_id": ["00005.XHKG", " 00700.XHKG "], "weight": [0.4, 0.6]})

    out = ensure_symbol_columns(frame, context="positions.csv")

    assert out["symbol"].tolist() == ["00005.XHKG", "00700.XHKG"]
    assert out["order_book_id"].tolist() == ["00005.XHKG", " 00700.XHKG "]


def test_ensure_symbol_columns_prefers_canonical_symbol_over_aliases():
    frame = pd.DataFrame(
        {
            "symbol": ["00005.HK", ""],
            "ts_code": ["SHOULD_NOT_WIN", "00011.HK"],
            "stock_ticker": ["5", "11"],
        }
    )

    out = ensure_symbol_columns(frame, context="positions.csv")

    assert out["symbol"].tolist() == ["00005.HK", "00011.HK"]


def test_ensure_symbol_columns_fails_without_any_symbol_alias():
    frame = pd.DataFrame({"weight": [1.0]})

    with pytest.raises(SystemExit, match="missing symbol/stock_ticker/ts_code/order_book_id"):
        ensure_symbol_columns(frame, context="positions.csv")


def test_canonicalize_symbol_columns_drops_legacy_aliases_but_keeps_order_book_id():
    frame = pd.DataFrame(
        {
            "ts_code": ["00005.HK"],
            "stock_ticker": ["5"],
            "order_book_id": ["00005.XHKG"],
            "weight": [1.0],
        }
    )

    out = canonicalize_symbol_columns(frame, context="positions.csv")

    assert out.columns.tolist() == ["order_book_id", "weight", "symbol"]
    assert out.iloc[0]["symbol"] == "00005.HK"
    assert "ts_code" not in out.columns
    assert "stock_ticker" not in out.columns


def test_canonicalize_symbol_columns_can_drop_order_book_id():
    frame = pd.DataFrame(
        {
            "order_book_id": ["00005.XHKG"],
            "weight": [1.0],
        }
    )

    out = canonicalize_symbol_columns(
        frame,
        context="positions.csv",
        drop_order_book_id=True,
    )

    assert out.columns.tolist() == ["weight", "symbol"]
    assert out.iloc[0]["symbol"] == "00005.XHKG"
    assert "order_book_id" not in out.columns


def test_drop_legacy_symbol_columns_preserves_attrs():
    frame = pd.DataFrame({"ts_code": ["AAA"], "value": [1]})
    frame.attrs["cache_key"] = "demo"

    out = drop_legacy_symbol_columns(frame)

    assert out.columns.tolist() == ["value"]
    assert out.attrs == {"cache_key": "demo"}


def test_load_universe_by_date_accepts_stock_ticker_column(tmp_path):
    path = tmp_path / "universe.csv"
    pd.DataFrame(
        {
            "trade_date": ["20200102", "20200102", "20200103"],
            "stock_ticker": ["5", "5", "11"],
            "selected": [1, 1, 0],
        }
    ).to_csv(path, index=False)

    out = load_universe_by_date(path, market="hk")
    assert list(out.columns) == ["trade_date", "symbol"]
    assert len(out) == 1
    assert out.iloc[0]["symbol"] == "00005.HK"


def test_load_universe_by_date_parses_integer_yyyymmdd_dates(tmp_path):
    path = tmp_path / "universe.csv"
    pd.DataFrame(
        {
            "rebalance_date": [20200102, 20200102, 20200131],
            "stock_ticker": ["00005.HK", "00005.HK", "00011.HK"],
            "selected": [1, 1, 1],
        }
    ).to_csv(path, index=False)

    out = load_universe_by_date(path, market="hk")
    assert out["trade_date"].tolist() == [
        pd.Timestamp("2020-01-02"),
        pd.Timestamp("2020-01-31"),
    ]
    assert out["symbol"].tolist() == ["00005.HK", "00011.HK"]


def test_annotate_positions_window_normalizes_to_symbol_only():
    frame = pd.DataFrame(
        {
            "rebalance_date": ["20200101", "20200108"],
            "entry_date": ["20200102", "20200109"],
            "ts_code": ["AAA", "BBB"],
            "weight": [0.5, 0.5],
            "signal": [0.1, 0.2],
            "rank": [1, 2],
            "side": ["long", "long"],
        }
    )
    out = _annotate_positions_window(frame)
    assert "symbol" in out.columns
    assert "ts_code" not in out.columns
    assert "stock_ticker" not in out.columns
    assert out["symbol"].tolist() == ["AAA", "BBB"]


def test_build_rebalance_diff_uses_symbol_only():
    frame = pd.DataFrame(
        {
            "entry_date": ["20200102", "20200102", "20200109"],
            "ts_code": ["AAA", "BBB", "AAA"],
            "side": ["long", "long", "long"],
            "weight": [0.5, 0.5, 1.0],
            "signal": [0.1, 0.2, 0.3],
            "rank": [1, 2, 1],
        }
    )
    diff = _build_rebalance_diff(frame)
    assert not diff.empty
    assert "symbol" in diff.columns
    assert "ts_code" not in diff.columns
    assert "stock_ticker" not in diff.columns
    assert diff["symbol"].tolist() == ["AAA", "BBB"]
