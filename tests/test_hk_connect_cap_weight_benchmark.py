from pathlib import Path

import pandas as pd
import pytest

from csml.research.hk_connect_cap_weight_benchmark import main


def _write_symbol_parquet(root: Path, symbol: str, frame: pd.DataFrame) -> None:
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(data_dir / f"{symbol}.parquet", index=False)


def test_hk_connect_cap_weight_benchmark_builder(tmp_path):
    periods_path = tmp_path / "periods.csv"
    periods_path.write_text(
        "\n".join(
            [
                "rebalance_date,entry_date,exit_date",
                "20200131,20200203,20200228",
                "20200228,20200302,20200331",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    by_date_path = tmp_path / "universe.csv"
    by_date_path.write_text(
        "\n".join(
            [
                "trade_date,symbol,selected",
                "20200131,AAA,1",
                "20200131,BBB,1",
                "20200228,AAA,1",
                "20200228,BBB,1",
                "20200228,CCC,1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    daily_root = tmp_path / "daily"
    _write_symbol_parquet(
        daily_root,
        "AAA",
        pd.DataFrame(
            {
                "trade_date": ["20200203", "20200228", "20200302", "20200331"],
                "open": [100.0, 111.0, 110.0, 99.0],
                "close": [101.0, 110.0, 112.0, 99.0],
            }
        ),
    )
    _write_symbol_parquet(
        daily_root,
        "BBB",
        pd.DataFrame(
            {
                "trade_date": ["20200203", "20200228", "20200302", "20200331"],
                "open": [200.0, 181.0, 180.0, 198.0],
                "close": [198.0, 180.0, 182.0, 198.0],
            }
        ),
    )
    _write_symbol_parquet(
        daily_root,
        "CCC",
        pd.DataFrame(
            {
                "trade_date": ["20200302", "20200331"],
                "open": [50.0, 60.0],
                "close": [52.0, 60.0],
            }
        ),
    )

    valuation_root = tmp_path / "valuation"
    _write_symbol_parquet(
        valuation_root,
        "AAA",
        pd.DataFrame(
            {
                "trade_date": ["20200131", "20200228"],
                "hk_total_market_val": [100.0, 120.0],
            }
        ),
    )
    _write_symbol_parquet(
        valuation_root,
        "BBB",
        pd.DataFrame(
            {
                "trade_date": ["20200131", "20200228"],
                "hk_total_market_val": [300.0, 180.0],
            }
        ),
    )
    _write_symbol_parquet(
        valuation_root,
        "CCC",
        pd.DataFrame(
            {
                "trade_date": ["20200228"],
                "hk_total_market_val": [100.0],
            }
        ),
    )

    out_path = tmp_path / "benchmark.csv"
    result = main(
        [
            "--periods-file",
            str(periods_path),
            "--by-date-file",
            str(by_date_path),
            "--daily-asset-dir",
            str(daily_root),
            "--valuation-asset-dir",
            str(valuation_root),
            "--out",
            str(out_path),
        ]
    )
    assert result == 0

    benchmark = pd.read_csv(out_path)
    assert benchmark["trade_date"].tolist() == [20200228, 20200331]
    assert benchmark["benchmark_return"].iloc[0] == pytest.approx(-0.05)
    assert benchmark["benchmark_return"].iloc[1] == pytest.approx(0.065)
    assert benchmark["coverage_pct"].tolist() == [100.0, 100.0]
