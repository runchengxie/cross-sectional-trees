import pandas as pd

from csml import pipeline
from csml.project_tools.symbols import ensure_symbol_columns


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


def test_load_universe_by_date_accepts_stock_ticker_column(tmp_path):
    path = tmp_path / "universe.csv"
    pd.DataFrame(
        {
            "trade_date": ["20200102", "20200102", "20200103"],
            "stock_ticker": ["AAA", "AAA", "BBB"],
            "selected": [1, 1, 0],
        }
    ).to_csv(path, index=False)

    out = pipeline.load_universe_by_date(path, market="us")
    assert list(out.columns) == ["trade_date", "symbol"]
    assert len(out) == 1
    assert out.iloc[0]["symbol"] == "AAA"


def test_load_universe_by_date_parses_integer_yyyymmdd_dates(tmp_path):
    path = tmp_path / "universe.csv"
    pd.DataFrame(
        {
            "rebalance_date": [20200102, 20200102, 20200131],
            "stock_ticker": ["00005.HK", "00005.HK", "00011.HK"],
            "selected": [1, 1, 1],
        }
    ).to_csv(path, index=False)

    out = pipeline.load_universe_by_date(path, market="hk")
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
    out = pipeline._annotate_positions_window(frame)
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
    diff = pipeline._build_rebalance_diff(frame)
    assert not diff.empty
    assert "symbol" in diff.columns
    assert "ts_code" not in diff.columns
    assert "stock_ticker" not in diff.columns
    assert diff["symbol"].tolist() == ["AAA", "BBB"]
