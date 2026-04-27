import pandas as pd
import pytest

from cstree.research.hk_intraday_download import _read_symbol_file, build_parser, merge_batch_parts


def test_hk_intraday_download_parser_defaults_to_pre_adjusted_bars():
    parser = build_parser()
    args = parser.parse_args(
        [
            "--symbols-file",
            "symbols.txt",
            "--start-date",
            "20250327",
            "--end-date",
            "20260326",
            "--output",
            "artifacts/cache/intraday/demo.parquet",
        ]
    )
    assert args.adjust_type == "pre"


def test_hk_intraday_download_parser_accepts_none_adjustment():
    parser = build_parser()
    args = parser.parse_args(
        [
            "--symbols-file",
            "symbols.txt",
            "--start-date",
            "20250327",
            "--end-date",
            "20260326",
            "--output",
            "artifacts/cache/intraday/demo.parquet",
            "--adjust-type",
            "none",
        ]
    )
    assert args.adjust_type == "none"


def test_read_symbol_file_normalizes_legacy_hk_symbol_columns(tmp_path):
    path = tmp_path / "symbols.csv"
    pd.DataFrame(
        {
            "order_book_id": ["700.XHKG", "00005.XHKG", "00005.HK"],
        }
    ).to_csv(path, index=False)

    out = _read_symbol_file(path)

    assert out == ["00700.HK", "00005.HK"]


def test_read_symbol_file_rejects_missing_symbol_aliases_with_symbol_first_message(tmp_path):
    path = tmp_path / "symbols.csv"
    pd.DataFrame({"ticker": ["00005.HK"]}).to_csv(path, index=False)

    with pytest.raises(SystemExit, match="Expected a canonical symbol column; legacy aliases"):
        _read_symbol_file(path)


def test_merge_batch_parts_reports_observed_trade_date_range(tmp_path):
    parts_dir = tmp_path / "parts"
    parts_dir.mkdir()
    pd.DataFrame(
        {
            "rq_order_book_id": ["00005.XHKG", "00005.XHKG"],
            "trade_datetime": [
                pd.Timestamp("2026-04-20 09:35:00"),
                pd.Timestamp("2026-04-21 16:00:00"),
            ],
        }
    ).to_parquet(parts_dir / "batch_0001.parquet", index=False)
    pd.DataFrame(
        {
            "rq_order_book_id": ["00700.XHKG"],
            "trade_datetime": [pd.Timestamp("2026-04-23 09:35:00")],
        }
    ).to_parquet(parts_dir / "batch_0002.parquet", index=False)

    rows, symbols, min_trade_date, max_trade_date = merge_batch_parts(
        parts_dir,
        tmp_path / "merged.parquet",
    )

    assert rows == 3
    assert symbols == 2
    assert min_trade_date == "20260420"
    assert max_trade_date == "20260423"
