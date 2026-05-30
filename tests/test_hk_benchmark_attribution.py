import json
from pathlib import Path

import pandas as pd
import pytest

from cstree.research.hk_benchmark_attribution import main


def _write_symbol_parquet(root: Path, symbol: str, frame: pd.DataFrame) -> None:
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(data_dir / f"{symbol}.parquet", index=False)


def test_hk_benchmark_attribution_builder(tmp_path):
    periods_path = tmp_path / "periods.csv"
    periods_path.write_text(
        "rebalance_date,entry_date,exit_date\n20200131,20200203,20200228\n",
        encoding="utf-8",
    )

    by_date_path = tmp_path / "universe.csv"
    by_date_path.write_text(
        "trade_date,symbol,selected\n20200131,AAA,1\n20200131,BBB,1\n20200131,CCC,1\n",
        encoding="utf-8",
    )

    daily_root = tmp_path / "daily"
    _write_symbol_parquet(
        daily_root,
        "AAA",
        pd.DataFrame({"trade_date": ["20200203", "20200228"], "open": [100.0, 110.0], "close": [100.0, 110.0]}),
    )
    _write_symbol_parquet(
        daily_root,
        "BBB",
        pd.DataFrame({"trade_date": ["20200203", "20200228"], "open": [200.0, 180.0], "close": [200.0, 180.0]}),
    )
    _write_symbol_parquet(
        daily_root,
        "CCC",
        pd.DataFrame({"trade_date": ["20200203", "20200228"], "open": [50.0, 60.0], "close": [50.0, 60.0]}),
    )

    valuation_root = tmp_path / "valuation"
    _write_symbol_parquet(
        valuation_root,
        "AAA",
        pd.DataFrame({"trade_date": ["20200131"], "hk_total_market_val": [100.0]}),
    )
    _write_symbol_parquet(
        valuation_root,
        "BBB",
        pd.DataFrame({"trade_date": ["20200131"], "hk_total_market_val": [300.0]}),
    )
    _write_symbol_parquet(
        valuation_root,
        "CCC",
        pd.DataFrame({"trade_date": ["20200131"], "hk_total_market_val": [600.0]}),
    )

    industry_path = tmp_path / "industry_labels_m.parquet"
    pd.DataFrame(
        {
            "trade_date": ["20200131", "20200131", "20200131"],
            "symbol": ["AAA", "BBB", "CCC"],
            "first_industry_name": ["Tech", "Banks", "Tech"],
        }
    ).to_parquet(industry_path, index=False)

    out_dir = tmp_path / "attrib"
    result = main(
        [
            "--benchmark-name",
            "demo_capw",
            "--periods-file",
            str(periods_path),
            "--by-date-file",
            str(by_date_path),
            "--daily-asset-dir",
            str(daily_root),
            "--valuation-asset-dir",
            str(valuation_root),
            "--industry-file",
            str(industry_path),
            "--out-dir",
            str(out_dir),
        ]
    )
    assert result == 0

    component = pd.read_csv(out_dir / "component_contributions.csv")
    symbol_summary = pd.read_csv(out_dir / "symbol_summary.csv")
    industry_summary = pd.read_csv(out_dir / "industry_summary.csv")
    payload = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))

    assert component["weight"].sum() == pytest.approx(1.0)
    assert component["contribution"].sum() == pytest.approx(0.10)
    assert symbol_summary.iloc[0]["symbol"] == "CCC"
    assert industry_summary.iloc[0]["industry"] == "Tech"
    assert payload["benchmark_total_return"] == pytest.approx(0.10)
    assert payload["top_industry"] == "Tech"
