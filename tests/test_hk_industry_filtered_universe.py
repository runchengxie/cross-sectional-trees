from __future__ import annotations

import json

import pandas as pd

from cstree.research.hk_industry_filtered_universe import main


def test_builds_nonfinancial_universe_from_latest_non_null_labels(tmp_path) -> None:
    by_date_path = tmp_path / "base.csv"
    industry_path = tmp_path / "industry.parquet"
    out_path = tmp_path / "nonfinancial.csv"
    summary_path = tmp_path / "nonfinancial.summary.json"

    pd.DataFrame(
        [
            {"trade_date": 20240131, "symbol": "00001.HK", "selected": 1},
            {"trade_date": 20240229, "symbol": "00001.HK", "selected": 1},
            {"trade_date": 20240131, "symbol": "00002.HK", "selected": 1},
            {"trade_date": 20240229, "symbol": "00002.HK", "selected": 1},
            {"trade_date": 20240131, "symbol": "00003.HK", "selected": 1},
        ]
    ).to_csv(by_date_path, index=False)

    pd.DataFrame(
        [
            {"trade_date": "2024-01-31", "symbol": "00001.HK", "first_industry_name": None},
            {"trade_date": "2024-02-29", "symbol": "00001.HK", "first_industry_name": "银行"},
            {"trade_date": "2024-01-31", "symbol": "00002.HK", "first_industry_name": "汽车"},
        ]
    ).to_parquet(industry_path, index=False)

    result = main(
        [
            "--by-date-file",
            str(by_date_path),
            "--industry-labels",
            str(industry_path),
            "--out",
            str(out_path),
            "--summary-out",
            str(summary_path),
        ]
    )

    assert result == 0

    output = pd.read_csv(out_path)
    assert output["symbol"].tolist() == ["00002.HK", "00002.HK", "00003.HK"]

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["summary"]["selected_target_symbols"] == 1
    assert summary["summary"]["output_symbols"] == 2


def test_only_mode_returns_financial_rows_only(tmp_path) -> None:
    by_date_path = tmp_path / "base.csv"
    industry_path = tmp_path / "industry.parquet"
    out_path = tmp_path / "financial.csv"

    pd.DataFrame(
        [
            {"trade_date": 20240131, "symbol": "00001.HK"},
            {"trade_date": 20240131, "symbol": "00002.HK"},
        ]
    ).to_csv(by_date_path, index=False)

    pd.DataFrame(
        [
            {"trade_date": "2024-02-29", "symbol": "00001.HK", "first_industry_name": "银行"},
            {"trade_date": "2024-02-29", "symbol": "00002.HK", "first_industry_name": "汽车"},
        ]
    ).to_parquet(industry_path, index=False)

    result = main(
        [
            "--by-date-file",
            str(by_date_path),
            "--industry-labels",
            str(industry_path),
            "--out",
            str(out_path),
            "--selection-mode",
            "only",
        ]
    )

    assert result == 0

    output = pd.read_csv(out_path)
    assert output["symbol"].tolist() == ["00001.HK"]
