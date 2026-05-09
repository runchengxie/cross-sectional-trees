import json
from types import SimpleNamespace

import pandas as pd

from cstree.data_tools import rqdata_assets


def _hk_5m_timestamps(date_text: str) -> list[pd.Timestamp]:
    return [
        *pd.date_range(f"{date_text} 09:35:00", f"{date_text} 12:00:00", freq="5min").tolist(),
        *pd.date_range(f"{date_text} 13:05:00", f"{date_text} 16:00:00", freq="5min").tolist(),
    ]


def _hk_5m_morning_timestamps(date_text: str) -> list[pd.Timestamp]:
    return pd.date_range(f"{date_text} 09:35:00", f"{date_text} 12:00:00", freq="5min").tolist()


def test_inspect_hk_intraday_health_infers_market_wide_half_days(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    intraday_path = repo_root / "artifacts" / "cache" / "intraday" / "hk_half_day_5m.parquet"
    intraday_path.parent.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    date_text = "2025-12-24"
    rows: list[dict[str, object]] = []
    for symbol_index in range(50):
        symbol = f"{symbol_index + 1:05d}.HK"
        for bar_index, timestamp in enumerate(_hk_5m_morning_timestamps(date_text)):
            price = 100.0 + symbol_index + bar_index * 0.01
            rows.append(
                {
                    "symbol": symbol,
                    "trade_datetime": timestamp,
                    "open": price,
                    "high": price + 0.1,
                    "low": price - 0.1,
                    "close": price + 0.05,
                    "volume": 10.0,
                    "amount": price * 10.0,
                }
            )
    pd.DataFrame(rows).to_parquet(intraday_path, index=False)

    out_path = repo_root / "intraday_half_day_health.json"
    args = SimpleNamespace(
        input=[str(intraday_path)],
        daily_asset_dir=None,
        sample_limit=5,
        expected_bars_per_day=66,
        numeric_rtol=1e-6,
        numeric_atol=1e-8,
        format="json",
        out=str(out_path),
        fail_on_severity="none",
    )

    assert rqdata_assets.inspect_hk_intraday_health(args) == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["inferred_half_day_dates"] == ["2025-12-24"]
    assert payload["summary"]["symbol_days_with_missing_bars"] == 0
    assert payload["summary"]["symbol_days_with_unexpected_bar_count"] == 0
    assert payload["quality_checks"] == []


def test_inspect_hk_intraday_health_classifies_daily_reconciliation_boundaries(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    intraday_path = repo_root / "artifacts" / "cache" / "intraday" / "hk_reconciliation_boundaries.parquet"
    intraday_path.parent.mkdir(parents=True)
    daily_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "daily_demo"
    (daily_dir / "data").mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    rows: list[dict[str, object]] = []
    for date_text in ("2024-05-02", "2024-05-03"):
        for timestamp in _hk_5m_timestamps(date_text):
            rows.append(
                {
                    "symbol": "00007.HK",
                    "trade_datetime": timestamp,
                    "open": 0.032,
                    "high": 0.032,
                    "low": 0.032,
                    "close": 0.032,
                    "volume": 0.0,
                    "amount": 0.0,
                }
            )
            rows.append(
                {
                    "symbol": "00008.HK",
                    "trade_datetime": timestamp,
                    "open": 1.0,
                    "high": 1.1,
                    "low": 0.9,
                    "close": 1.0,
                    "volume": 10.0,
                    "amount": 10.0,
                }
            )
    for timestamp in _hk_5m_timestamps("2024-05-02"):
        rows.append(
            {
                "symbol": "00009.HK",
                "trade_datetime": timestamp,
                "open": 2.0,
                "high": 2.1,
                "low": 1.9,
                "close": 2.0,
                "volume": 10.0,
                "amount": 20.0,
            }
        )
    pd.DataFrame(rows).to_parquet(intraday_path, index=False)

    for symbol in ("00007.HK", "00008.HK"):
        pd.DataFrame(
            {
                "trade_date": ["20240328"],
                "open": [1.0],
                "high": [1.0],
                "low": [1.0],
                "close": [1.0],
                "volume": [100.0],
                "total_turnover": [100.0],
            }
        ).to_parquet(daily_dir / "data" / f"{symbol}.parquet", index=False)
    pd.DataFrame(
        {
            "trade_date": ["20240502", "20240503"],
            "open": [2.0, 2.1],
            "high": [2.1, 2.2],
            "low": [1.9, 2.0],
            "close": [2.0, 2.1],
            "volume": [660.0, 100.0],
            "total_turnover": [1320.0, 210.0],
        }
    ).to_parquet(daily_dir / "data" / "00009.HK.parquet", index=False)

    out_path = repo_root / "intraday_reconciliation_boundaries.json"
    args = SimpleNamespace(
        input=[str(intraday_path)],
        daily_asset_dir=str(daily_dir),
        sample_limit=5,
        expected_bars_per_day=66,
        numeric_rtol=1e-6,
        numeric_atol=1e-8,
        format="json",
        out=str(out_path),
        fail_on_severity="none",
    )

    assert rqdata_assets.inspect_hk_intraday_health(args) == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    reconciliation_summary = payload["daily_reconciliation"]["summary"]
    assert reconciliation_summary["missing_daily_symbol_days"] == 0
    assert reconciliation_summary["inactive_zero_volume_intraday_after_daily_end_symbol_days"] == 2
    assert reconciliation_summary["intraday_after_daily_end_with_trading_symbol_days"] == 2
    assert reconciliation_summary["daily_active_symbol_days_missing_intraday"] == 1

    checks = {item["check"]: item for item in payload["quality_checks"]}
    assert "intraday_daily_rows_missing_from_asset" not in checks
    assert checks["inactive_zero_volume_intraday_after_daily_end"]["severity"] == "info"
    assert checks["inactive_zero_volume_intraday_after_daily_end"]["affected_items"] == 2
    assert checks["intraday_after_daily_end_with_trading"]["affected_items"] == 2
    assert checks["daily_active_but_intraday_missing"]["affected_items"] == 1


def test_inspect_hk_intraday_health_reports_integrity_and_daily_reconciliation(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    intraday_path = repo_root / "artifacts" / "cache" / "intraday" / "hk_all_5m_demo.parquet"
    intraday_path.parent.mkdir(parents=True)
    daily_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "daily_demo"
    (daily_dir / "data").mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    date_text = "2026-03-31"
    base_times = _hk_5m_timestamps(date_text)

    rows: list[dict[str, object]] = []
    missing_time = pd.Timestamp(f"{date_text} 10:00:00")
    for idx, timestamp in enumerate(base_times):
        if timestamp == missing_time:
            continue
        price = 100.0 + idx
        rows.append(
            {
                "symbol": "00005.HK",
                "trade_datetime": timestamp,
                "open": price,
                "high": price + 0.5,
                "low": price - 0.5,
                "close": price + 0.2,
                "volume": 10.0,
                "amount": (price + 0.2) * 10.0,
            }
        )
    rows.append(
        {
            "symbol": "00005.HK",
            "trade_datetime": pd.Timestamp(f"{date_text} 09:35:00"),
            "open": 100.0,
            "high": 100.5,
            "low": 99.5,
            "close": 100.2,
            "volume": 10.0,
            "amount": 1002.0,
        }
    )
    rows.append(
        {
            "symbol": "00005.HK",
            "trade_datetime": pd.Timestamp(f"{date_text} 09:31:00"),
            "open": 99.0,
            "high": 99.2,
            "low": 98.8,
            "close": 99.1,
            "volume": -5.0,
            "amount": -495.5,
        }
    )

    for idx, timestamp in enumerate(base_times):
        price = 200.0 + idx
        rows.append(
            {
                "symbol": "00011.HK",
                "trade_datetime": timestamp,
                "open": price,
                "high": price + 0.5,
                "low": price - 0.5,
                "close": price + 0.2,
                "volume": 20.0,
                "amount": (price + 0.2) * 20.0,
            }
        )
    rows.append(
        {
            "symbol": "00011.HK",
            "trade_datetime": pd.Timestamp(f"{date_text} 12:05:00"),
            "open": 260.0,
            "high": 260.5,
            "low": 259.5,
            "close": 260.2,
            "volume": 20.0,
            "amount": 5204.0,
        }
    )

    intraday_frame = pd.DataFrame(rows).sort_values(["symbol", "trade_datetime"]).reset_index(drop=True)
    intraday_frame.to_parquet(intraday_path, index=False)

    symbol_00005 = intraday_frame.loc[intraday_frame["symbol"] == "00005.HK"].copy()
    symbol_00005 = symbol_00005.drop_duplicates(subset=["symbol", "trade_datetime"], keep="last")
    symbol_00005 = symbol_00005.sort_values("trade_datetime").reset_index(drop=True)
    pd.DataFrame(
        {
            "trade_date": ["20260331"],
            "open": [float(symbol_00005["open"].iloc[0])],
            "high": [float(symbol_00005["high"].max())],
            "low": [float(symbol_00005["low"].min())],
            "close": [float(symbol_00005["close"].iloc[-1])],
            "volume": [float(symbol_00005["volume"].sum())],
            "total_turnover": [float(symbol_00005["amount"].sum())],
        }
    ).to_parquet(daily_dir / "data" / "00005.HK.parquet", index=False)

    pd.DataFrame(
        {
            "trade_date": ["20260331"],
            "open": [200.0],
            "high": [265.5],
            "low": [199.5],
            "close": [999.0],
            "volume": [1340.0],
            "total_turnover": [float(intraday_frame.loc[intraday_frame["symbol"] == "00011.HK", "amount"].sum())],
        }
    ).to_parquet(daily_dir / "data" / "00011.HK.parquet", index=False)

    out_path = repo_root / "intraday_health.json"
    args = SimpleNamespace(
        input=[str(intraday_path)],
        daily_asset_dir=str(daily_dir),
        sample_limit=5,
        expected_bars_per_day=66,
        numeric_rtol=1e-6,
        numeric_atol=1e-8,
        format="json",
        out=str(out_path),
        fail_on_severity="none",
    )

    assert rqdata_assets.inspect_hk_intraday_health(args) == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    summary = payload["summary"]
    assert summary["rows_scanned"] == 134
    assert summary["symbols_scanned"] == 2
    assert summary["symbol_days_scanned"] == 2
    assert summary["trade_date_min"] == "2026-03-31"
    assert summary["trade_date_max"] == "2026-03-31"
    assert summary["duplicate_timestamp_groups"] == 1
    assert summary["duplicate_timestamp_rows"] == 2
    assert summary["symbol_days_with_missing_bars"] == 1
    assert summary["missing_bar_rows"] == 1
    assert summary["off_schedule_bar_rows"] == 2
    assert summary["negative_volume_rows"] == 1
    assert summary["negative_amount_rows"] == 1
    assert summary["symbol_days_with_unexpected_bar_count"] == 1
    assert summary["daily_reconciliation_symbol_days"] == 2
    assert summary["daily_reconciliation_missing_daily_rows"] == 0

    assert payload["sample_duplicate_timestamps"] == [
        {
            "symbol": "00005.HK",
            "trade_datetime": "2026-03-31 09:35:00",
            "duplicate_rows": 2,
        }
    ]
    assert payload["sample_missing_symbol_days"] == [
        {
            "symbol": "00005.HK",
            "trade_date": "2026-03-31",
            "observed_bars": 66,
            "missing_bars": 1,
            "sample_missing_times": "10:00",
        }
    ]
    assert payload["sample_negative_rows"] == [
        {
            "symbol": "00005.HK",
            "trade_datetime": "2026-03-31 09:31:00",
            "field": "volume",
            "value": -5.0,
        },
        {
            "symbol": "00005.HK",
            "trade_datetime": "2026-03-31 09:31:00",
            "field": "amount",
            "value": -495.5,
        },
    ]
    assert payload["sample_unexpected_bar_count_symbol_days"] == [
        {
            "symbol": "00011.HK",
            "trade_date": "2026-03-31",
            "observed_bars": 67,
            "expected_bars": 66,
        }
    ]
    assert payload["sample_off_schedule_rows"] == [
        {
            "symbol": "00005.HK",
            "trade_datetime": "2026-03-31 09:31:00",
            "time_key": "09:31",
        },
        {
            "symbol": "00011.HK",
            "trade_datetime": "2026-03-31 12:05:00",
            "time_key": "12:05",
        },
    ]

    checks = {item["check"]: item for item in payload["quality_checks"]}
    assert checks["duplicate_intraday_timestamps"]["affected_items"] == 1
    assert checks["intraday_missing_bars_vs_expected_schedule"]["affected_items"] == 1
    assert checks["intraday_unexpected_session_bar_count"]["affected_items"] == 1
    assert checks["intraday_negative_volume_rows"]["affected_items"] == 1
    assert checks["intraday_negative_amount_rows"]["affected_items"] == 1
    assert checks["intraday_off_schedule_bar_rows"]["affected_items"] == 2
    assert checks["daily_close_mismatch"]["affected_items"] == 1

    assert payload["daily_reconciliation"]["summary"]["mismatch_counts"] == {
        "daily_close_mismatch": 1
    }
    assert payload["daily_reconciliation"]["summary"]["suppressed_mismatch_counts"] == {}
    assert payload["daily_reconciliation"]["sample_mismatch_rows"] == [
        {
            "symbol": "00011.HK",
            "trade_date": "2026-03-31",
            "field": "daily_close_mismatch",
            "intraday_value": 265.2,
            "daily_value": 999.0,
        }
    ]
    assert payload["quality_verdict"] == {
        "color": "red",
        "overall_severity": "error",
        "issue_count": 7,
        "severity_counts": {
            "error": 3,
            "warning": 4,
            "info": 0,
        },
        "fail_on_severity": "none",
        "gate_triggered": False,
        "gate_status": "pass",
        "failing_issue_count": 0,
        "sample_failing_checks": [],
        "message": "7 quality issue(s) detected, including at least one error.",
    }

    fail_out_path = repo_root / "intraday_health_fail_warning.json"
    fail_args = SimpleNamespace(
        input=[str(intraday_path)],
        daily_asset_dir=str(daily_dir),
        sample_limit=5,
        expected_bars_per_day=66,
        numeric_rtol=1e-6,
        numeric_atol=1e-8,
        format="json",
        out=str(fail_out_path),
        fail_on_severity="warning",
    )
    assert rqdata_assets.inspect_hk_intraday_health(fail_args) == 2


def test_inspect_hk_intraday_health_marks_price_mismatch_as_adjustment_basis_info(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    intraday_path = repo_root / "artifacts" / "cache" / "intraday" / "hk_adjusted_5m.parquet"
    intraday_path.parent.mkdir(parents=True)
    daily_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "daily_demo"
    (daily_dir / "data").mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    date_text = "2026-04-09"
    pd.DataFrame(
        [
            {
                "symbol": "00005.HK",
                "trade_datetime": timestamp,
                "open": 10.0,
                "high": 10.0,
                "low": 10.0,
                "close": 10.0,
                "volume": 1.0,
                "amount": 10.0,
            }
            for timestamp in _hk_5m_timestamps(date_text)
        ]
    ).to_parquet(intraday_path, index=False)
    pd.DataFrame(
        {
            "trade_date": ["20260409"],
            "open": [20.0],
            "high": [20.0],
            "low": [20.0],
            "close": [20.0],
            "volume": [66.0],
            "total_turnover": [660.0],
        }
    ).to_parquet(daily_dir / "data" / "00005.HK.parquet", index=False)

    out_path = repo_root / "intraday_adjustment_basis.json"
    args = SimpleNamespace(
        input=[str(intraday_path)],
        daily_asset_dir=str(daily_dir),
        sample_limit=5,
        expected_bars_per_day=66,
        numeric_rtol=1e-6,
        numeric_atol=1e-8,
        intraday_adjust_type="pre",
        daily_adjust_type="none",
        format="json",
        out=str(out_path),
        fail_on_severity="none",
    )

    assert rqdata_assets.inspect_hk_intraday_health(args) == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["daily_reconciliation_price_adjustment_basis_mismatch"] is True
    checks = {item["check"]: item for item in payload["quality_checks"]}
    assert checks["daily_close_mismatch"]["severity"] == "info"
    assert checks["daily_close_mismatch"]["classification"] == "adjustment-basis-mismatch"


def test_inspect_hk_intraday_health_suppresses_minor_ohl_reconciliation_noise(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    intraday_path = repo_root / "artifacts" / "cache" / "intraday" / "hk_all_5m_demo.parquet"
    intraday_path.parent.mkdir(parents=True)
    daily_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "daily_demo"
    (daily_dir / "data").mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    date_text = "2026-03-31"
    base_times = _hk_5m_timestamps(date_text)
    rows: list[dict[str, object]] = []
    for idx, timestamp in enumerate(base_times):
        price = 100.0 + idx * 0.1
        rows.append(
            {
                "symbol": "00005.HK",
                "trade_datetime": timestamp,
                "open": price,
                "high": price + 0.3,
                "low": price - 0.3,
                "close": price + 0.1,
                "volume": 10.0,
                "amount": (price + 0.1) * 10.0,
            }
        )
        price_2 = 200.0 + idx * 0.1
        rows.append(
            {
                "symbol": "00011.HK",
                "trade_datetime": timestamp,
                "open": price_2,
                "high": price_2 + 0.3,
                "low": price_2 - 0.3,
                "close": price_2 + 0.1,
                "volume": 20.0,
                "amount": (price_2 + 0.1) * 20.0,
            }
        )
    intraday_frame = pd.DataFrame(rows).sort_values(["symbol", "trade_datetime"]).reset_index(drop=True)
    intraday_frame.to_parquet(intraday_path, index=False)

    symbol_00005 = intraday_frame.loc[intraday_frame["symbol"] == "00005.HK"].copy()
    symbol_00011 = intraday_frame.loc[intraday_frame["symbol"] == "00011.HK"].copy()
    pd.DataFrame(
        {
            "trade_date": ["20260331"],
            "open": [float(symbol_00005["open"].iloc[0]) + 0.15],
            "high": [float(symbol_00005["high"].max()) - 0.05],
            "low": [float(symbol_00005["low"].min()) + 0.10],
            "close": [float(symbol_00005["close"].iloc[-1])],
            "volume": [float(symbol_00005["volume"].sum())],
            "total_turnover": [float(symbol_00005["amount"].sum())],
        }
    ).to_parquet(daily_dir / "data" / "00005.HK.parquet", index=False)
    pd.DataFrame(
        {
            "trade_date": ["20260331"],
            "open": [float(symbol_00011["open"].iloc[0])],
            "high": [float(symbol_00011["high"].max())],
            "low": [float(symbol_00011["low"].min()) + 2.0],
            "close": [float(symbol_00011["close"].iloc[-1])],
            "volume": [float(symbol_00011["volume"].sum())],
            "total_turnover": [float(symbol_00011["amount"].sum())],
        }
    ).to_parquet(daily_dir / "data" / "00011.HK.parquet", index=False)

    out_path = repo_root / "intraday_health_minor_ohl.json"
    args = SimpleNamespace(
        input=[str(intraday_path)],
        daily_asset_dir=str(daily_dir),
        sample_limit=5,
        expected_bars_per_day=66,
        numeric_rtol=1e-6,
        numeric_atol=1e-8,
        format="json",
        out=str(out_path),
        fail_on_severity="none",
    )

    assert rqdata_assets.inspect_hk_intraday_health(args) == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    checks = {item["check"]: item for item in payload["quality_checks"]}
    assert "daily_open_mismatch" not in checks
    assert "daily_high_mismatch" not in checks
    assert "daily_low_mismatch" in checks
    assert checks["daily_low_mismatch"]["affected_items"] == 1
    assert payload["daily_reconciliation"]["summary"]["mismatch_counts"] == {
        "daily_low_mismatch": 1
    }
    assert payload["daily_reconciliation"]["summary"]["suppressed_mismatch_counts"] == {
        "daily_high_mismatch": 1,
        "daily_low_mismatch": 1,
        "daily_open_mismatch": 1,
    }
