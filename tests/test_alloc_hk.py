import io
import json
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

from cstree.liveops import alloc_hk


class _FakeInstrument:
    def __init__(self, order_book_id: str, round_lot: int, *, symbol: str, stock_connect):
        self.order_book_id = order_book_id
        self.round_lot = round_lot
        self.symbol = symbol
        self.stock_connect = stock_connect


def _install_fake_rqdatac(
    monkeypatch,
    *,
    close_none: dict[str, list[float]],
    close_pre: dict[str, list[float]],
    lot_map: dict[str, int],
    connect_map: dict[str, object],
) -> None:
    dates = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"])

    def init(**kwargs):
        return None

    def get_previous_trading_date(ref_date, n=1, market=None):
        return dates[0].date()

    def get_price(
        order_book_ids,
        start_date,
        end_date,
        frequency="1d",
        fields=None,
        adjust_type="none",
        market=None,
        expect_df=True,
    ):
        assert frequency == "1d"
        assert fields == ["close"]
        source = close_pre if adjust_type == "pre" else close_none
        return pd.DataFrame(
            {
                order_book_id: source[order_book_id]
                for order_book_id in order_book_ids
            },
            index=dates,
        )

    def instruments(order_book_ids, market=None):
        return [
            _FakeInstrument(
                order_book_id,
                lot_map[order_book_id],
                symbol=f"Name-{order_book_id}",
                stock_connect=connect_map[order_book_id],
            )
            for order_book_id in order_book_ids
        ]

    fake_module = types.SimpleNamespace(
        init=init,
        get_previous_trading_date=get_previous_trading_date,
        get_price=get_price,
        instruments=instruments,
    )
    monkeypatch.setitem(sys.modules, "rqdatac", fake_module)


def _write_positions(path) -> None:
    df = pd.DataFrame(
        {
            "entry_date": ["2020-01-02", "2020-01-02"],
            "rebalance_date": ["2020-01-01", "2020-01-01"],
            "symbol": ["0001.HK", "0002.HK"],
            "weight": [0.75, 0.25],
            "signal": [0.20, 0.10],
            "rank": [1, 2],
            "side": ["long", "long"],
        }
    )
    df.to_csv(path, index=False)


def test_alloc_hk_positions_file_custom_weights(tmp_path, monkeypatch, capsys):
    positions_path = tmp_path / "positions.csv"
    _write_positions(positions_path)

    _install_fake_rqdatac(
        monkeypatch,
        close_none={
            "00001.XHKG": [9.0, 9.5, 10.0],
            "00002.XHKG": [18.0, 19.0, 20.0],
        },
        close_pre={
            "00001.XHKG": [1.0, 0.5, 2.0],
            "00002.XHKG": [1.0, 1.1, 1.2],
        },
        lot_map={
            "00001.XHKG": 100,
            "00002.XHKG": 100,
        },
        connect_map={
            "00001.XHKG": ["sh", "sz"],
            "00002.XHKG": ["sh"],
        },
    )

    alloc_hk.main(
        [
            "--positions-file",
            str(positions_path),
            "--as-of",
            "2020-01-03",
            "--top-n",
            "2",
            "--cash",
            "100000",
            "--method",
            "custom",
            "--history-years",
            "1",
            "--roll-window",
            "2",
            "--format",
            "json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["allocation_method"] == "custom"
    assert payload["source"] == "positions_file"
    assert payload["selected_n"] == 2
    assert payload["pricing_source"] == "1d_close"
    assert payload["cash_left"] == 1000.0

    row_a = payload["allocations"][0]
    assert row_a["symbol"] == "00001.HK"
    assert row_a["target_value"] == 75000.0
    assert row_a["price"] == 10.0
    assert row_a["round_lot"] == 100.0
    assert row_a["lots"] == 75
    assert row_a["est_value"] == 75000.0
    assert row_a["price_source"] == "1d_close"

    row_b = payload["allocations"][1]
    assert row_b["symbol"] == "00002.HK"
    assert row_b["target_value"] == 25000.0
    assert row_b["lots"] == 12
    assert row_b["gap_to_target"] == 1000.0

    sell_rows = payload["sell_signals"]
    assert sell_rows[0]["symbol"] == "00001.HK"
    assert sell_rows[0]["last_sell_signal_date"] == "2020-01-03"


def test_alloc_hk_scenario_grid_json(tmp_path, monkeypatch, capsys):
    positions_path = tmp_path / "positions.csv"
    _write_positions(positions_path)

    _install_fake_rqdatac(
        monkeypatch,
        close_none={
            "00001.XHKG": [9.0, 9.5, 10.0],
            "00002.XHKG": [18.0, 19.0, 20.0],
        },
        close_pre={
            "00001.XHKG": [1.0, 0.5, 2.0],
            "00002.XHKG": [1.0, 1.1, 1.2],
        },
        lot_map={
            "00001.XHKG": 100,
            "00002.XHKG": 100,
        },
        connect_map={
            "00001.XHKG": ["sh", "sz"],
            "00002.XHKG": ["sh"],
        },
    )

    alloc_hk.main(
        [
            "--positions-file",
            str(positions_path),
            "--as-of",
            "2020-01-03",
            "--scenario-capital",
            "100000,200000",
            "--scenario-top-n",
            "1,2",
            "--method",
            "custom",
            "--history-years",
            "1",
            "--roll-window",
            "2",
            "--format",
            "json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "scenario_grid"
    assert payload["scenario_capitals"] == [100000.0, 200000.0]
    assert payload["scenario_top_ns"] == [1, 2]
    assert len(payload["scenario_overview"]) == 4
    assert len(payload["scenarios"]) == 4

    first = payload["scenarios"][0]
    assert first["scenario_id"] == "C10w_N1"
    assert first["scenario_capital"] == 100000.0
    assert first["scenario_top_n"] == 1
    assert first["requested_top_n"] == 1
    assert first["selected_n"] == 1
    assert len(first["allocations"]) == 1

    last = payload["scenarios"][-1]
    assert last["scenario_id"] == "C20w_N2"
    assert last["cash"] == 200000.0
    assert last["requested_top_n"] == 2
    assert len(last["allocations"]) == 2


def test_alloc_hk_scenario_grid_csv_emits_overview(tmp_path, monkeypatch, capsys):
    positions_path = tmp_path / "positions.csv"
    _write_positions(positions_path)

    _install_fake_rqdatac(
        monkeypatch,
        close_none={
            "00001.XHKG": [9.0, 9.5, 10.0],
            "00002.XHKG": [18.0, 19.0, 20.0],
        },
        close_pre={
            "00001.XHKG": [1.0, 0.5, 2.0],
            "00002.XHKG": [1.0, 1.1, 1.2],
        },
        lot_map={
            "00001.XHKG": 100,
            "00002.XHKG": 100,
        },
        connect_map={
            "00001.XHKG": ["sh", "sz"],
            "00002.XHKG": ["sh"],
        },
    )

    alloc_hk.main(
        [
            "--positions-file",
            str(positions_path),
            "--as-of",
            "2020-01-03",
            "--scenario-capital",
            "100000,200000",
            "--scenario-top-n",
            "1,2",
            "--method",
            "custom",
            "--history-years",
            "1",
            "--roll-window",
            "2",
            "--format",
            "csv",
        ]
    )

    overview = pd.read_csv(io.StringIO(capsys.readouterr().out))
    assert list(overview.columns[:3]) == ["as_of", "pricing_date", "pricing_source"]
    assert "scenario_id" in overview.columns
    assert "scenario_capital" in overview.columns
    assert "scenario_top_n" in overview.columns
    assert len(overview) == 4


def test_alloc_hk_quality_gate_blocks_before_market_data(monkeypatch):
    prepared = pd.DataFrame(
        {
            "symbol": ["00001.HK"],
            "weight": [1.0],
            "rank": [1],
            "signal": [0.2],
            "side": ["long"],
        }
    )

    monkeypatch.setattr(
        alloc_hk,
        "_resolve_settings",
        lambda _args: ({}, alloc_hk.HkAllocSettings(cash=100000.0, method="custom")),
    )
    monkeypatch.setattr(
        alloc_hk,
        "_resolve_scenarios",
        lambda _args, **_kwargs: ((100000.0,), (1,)),
    )
    monkeypatch.setattr(
        alloc_hk,
        "_load_selection",
        lambda *_args, **_kwargs: (
            prepared,
            pd.Timestamp("2020-01-02"),
            pd.Timestamp("2020-01-03"),
            "positions_file",
            None,
            Path("positions.csv"),
            "hk",
        ),
    )
    monkeypatch.setattr(
        alloc_hk,
        "enforce_liveops_quality_gate",
        lambda **_kwargs: (_ for _ in ()).throw(SystemExit("alloc-hk blocked by quality gate")),
    )
    monkeypatch.setattr(
        alloc_hk.base_alloc,
        "_init_rqdatac",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("_init_rqdatac should not run")
        ),
    )

    with pytest.raises(SystemExit, match="alloc-hk blocked by quality gate"):
        alloc_hk.main(
            [
                "--positions-file",
                "positions.csv",
                "--top-n",
                "1",
                "--method",
                "custom",
                "--fail-on-quality",
                "warning",
            ]
        )


def test_build_target_values_custom_weights() -> None:
    tickers = [
        alloc_hk.SelectedTicker(symbol="0001.HK", weight=1.0),
        alloc_hk.SelectedTicker(symbol="0002.HK", weight=3.0),
    ]

    out = alloc_hk.build_target_values(1_000_000.0, tickers, "custom")
    assert out["0001.HK"] == 250_000.0
    assert out["0002.HK"] == 750_000.0


def test_apply_secondary_fill_stays_within_gap_by_default() -> None:
    allocation = pd.DataFrame(
        [
            {
                "symbol": "0001.HK",
                "valuation": "LOW",
                "tradable": True,
                "price": 1.0,
                "lot_cost": 100.0,
                "target_value": 560.0,
                "lots": 5,
                "lots_extra": 0,
                "round_lot": 100,
                "shares": 500,
                "est_value": 500.0,
                "gap_to_target": 60.0,
            }
        ]
    )

    updated, stats = alloc_hk.apply_secondary_fill(
        allocation,
        total_capital=1_000.0,
        enabled=True,
        avoid_high_valuation=True,
        avoid_high_valuation_strict=False,
        max_steps=10,
        allow_over_alloc=False,
        max_over_alloc_ratio=0.0,
        max_over_alloc_amount=0.0,
        max_over_alloc_lots_per_ticker=1,
        cash_buffer_ratio=0.0,
        cash_buffer_amount=0.0,
        estimated_fee_per_order=0.0,
    )

    assert stats["secondary_fill_steps"] == 0
    assert float(updated.loc[0, "gap_to_target"]) == 60.0


def test_prepare_allocation_export_df_localizes_headers_and_values() -> None:
    allocation = pd.DataFrame(
        [
            {
                "symbol": "0001.HK",
                "name": "长和",
                "side": "long",
                "rank": 1,
                "signal": 0.2,
                "weight": 0.75,
                "order_book_id": "00001.XHKG",
                "tradable": True,
                "stock_connect": ["sh", "sz"],
                "price_source": "snapshot",
                "pricing_date": pd.Timestamp("2026-03-20").date(),
                "price": 50.0,
                "round_lot": 500,
                "lot_cost": 25_000.0,
                "target_value": 75_000.0,
                "lots_base": 3,
                "lots_extra": 0,
                "lots": 3,
                "shares": 1500,
                "est_value": 75_000.0,
                "gap_to_target": 0.0,
                "gap_ratio": 0.0,
                "valuation": "HIGH",
                "pct_1y": 0.98,
                "z_1y": 2.1,
                "overpriced_low": 48.0,
                "overpriced_high": 52.0,
                "overpriced_range": "[48.0000, 52.0000]",
            }
        ]
    )

    out = alloc_hk._prepare_allocation_export_df(allocation)
    assert list(out.columns[:6]) == ["股票代码", "名称", "方向", "信号排名", "信号强度", "权重"]
    assert out.loc[0, "方向"] == "多头"
    assert out.loc[0, "可交易"] == "是"
    assert out.loc[0, "港股通"] == "沪/深"
    assert out.loc[0, "价格来源"] == "快照最新价"
    assert out.loc[0, "估值分层"] == "偏高"


def test_prepare_summary_export_df_localizes_headers_and_values() -> None:
    summary = pd.DataFrame(
        [
            {
                "as_of": pd.Timestamp("2026-03-20").date(),
                "pricing_date": pd.Timestamp("2026-03-20").date(),
                "pricing_source": "snapshot",
                "pricing_source_detail": "snapshot:20",
                "selected_n": 20,
                "total_capital": 1_000_000.0,
                "allocation_method": "custom",
                "require_stock_connect": True,
                "total_est_value": 980_000.0,
                "total_gap": 20_000.0,
                "cash_used_ratio": 0.98,
                "secondary_fill_enabled": True,
                "secondary_fill_steps": 3,
                "secondary_fill_spent": 60_000.0,
                "secondary_fill_fee_spent": 100.0,
                "secondary_fill_cash_buffer": 2_000.0,
                "secondary_fill_budget_after_buffer": 998_000.0,
                "cash_remaining_after_fill": 19_900.0,
            }
        ]
    )

    out = alloc_hk._prepare_summary_export_df(summary)
    assert list(out.columns[:5]) == ["统计日期", "定价日期", "价格来源", "价格来源明细", "标的数量"]
    assert out.loc[0, "价格来源"] == "快照最新价"
    assert out.loc[0, "分配方式"] == "自定义权重"
    assert out.loc[0, "要求港股通"] == "是"
    assert out.loc[0, "启用二次补仓"] == "是"


def test_prepare_sell_signals_export_df_localizes_headers_and_values() -> None:
    sell_signals = pd.DataFrame(
        [
            {
                "symbol": "0001.HK",
                "name": "长和",
                "side": "short",
                "rank": 2,
                "signal": -0.1,
                "weight": 0.25,
                "order_book_id": "00001.XHKG",
                "as_of": pd.Timestamp("2026-03-20").date(),
                "close_pre": 49.5,
                "pct_1y": 0.97,
                "z_1y": 2.0,
                "sell_trigger": 48.0,
                "extreme_trigger": 52.0,
                "last_sell_signal_date": pd.Timestamp("2026-03-19").date(),
                "valuation": "HIGH",
            }
        ]
    )

    out = alloc_hk._prepare_sell_signals_export_df(sell_signals)
    assert list(out.columns[:6]) == ["股票代码", "名称", "方向", "信号排名", "信号强度", "权重"]
    assert out.loc[0, "方向"] == "空头"
    assert out.loc[0, "估值分层"] == "偏高"


def test_write_xlsx_report_requires_openpyxl(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        alloc_hk,
        "_import_openpyxl",
        lambda: (_ for _ in ()).throw(SystemExit("missing openpyxl")),
    )

    with pytest.raises(SystemExit, match="missing openpyxl"):
        alloc_hk.write_xlsx_report(
            tmp_path / "alloc_hk.xlsx",
            pd.DataFrame([{"symbol": "0001.HK"}]),
            pd.DataFrame([{"as_of": pd.Timestamp("2026-03-20").date()}]),
            pd.DataFrame([{"symbol": "0001.HK"}]),
        )


def test_write_scenario_grid_report_requires_openpyxl(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        alloc_hk,
        "_import_openpyxl",
        lambda: (_ for _ in ()).throw(SystemExit("missing openpyxl")),
    )

    with pytest.raises(SystemExit, match="missing openpyxl"):
        alloc_hk.write_scenario_grid_report(
            tmp_path / "alloc_hk_grid.xlsx",
            [
                alloc_hk.ScenarioReport(
                    scenario_id="C10w_N1",
                    allocation_df=pd.DataFrame([{"symbol": "0001.HK"}]),
                    summary_df=pd.DataFrame([{"as_of": pd.Timestamp("2026-03-20").date()}]),
                    sell_signals_df=pd.DataFrame([{"symbol": "0001.HK"}]),
                )
            ],
        )
