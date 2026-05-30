from __future__ import annotations

import json
import logging
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from ..execution_calendar import HK_CONNECT_CALENDAR, is_execution_open
from ..pipeline.quality import enforce_liveops_quality_gate
from . import alloc as base_alloc, alloc_hk_reporting as reporting
from .alloc_hk_allocation import (
    apply_secondary_fill as _apply_secondary_fill,
    build_allocation_table as _build_allocation_table,
    build_target_values as _build_target_values,
    calc_lots as _calc_lots,
)
from .alloc_hk_common import (
    is_missing_value as _is_missing_value,
    pick_round_lot as _pick_round_lot_impl,
)
from .alloc_hk_market_data import (
    is_stock_connect_tradable as _is_stock_connect_tradable,
    prefetch_market_data,
)
from .alloc_hk_selection import (
    load_selection as _load_selection,
    selection_to_tickers as _selection_to_tickers,
)
from .alloc_hk_sell_signals import build_sell_signals as _build_sell_signals
from .alloc_hk_settings import (
    parse_args as _parse_args,
    resolve_scenarios as _resolve_scenarios,
    resolve_settings as _resolve_settings,
)
from .alloc_hk_types import (
    HkAllocSettings,
    MarketDataBundle,
    ScenarioReport,
    SelectedTicker,
)

LOGGER = logging.getLogger(__name__)


VALUATION_CN_MAP = reporting.VALUATION_CN_MAP


def _pick_round_lot(values: Sequence[Any]) -> float:
    return _pick_round_lot_impl(values, logger=LOGGER)


def calc_lots(
    target_value: float,
    price: float,
    round_lot: float,
    tradable: bool,
) -> int:
    return _calc_lots(target_value, price, round_lot, tradable)


def build_target_values(
    total_capital: float,
    tickers: Sequence[SelectedTicker],
    allocation_method: str,
) -> dict[str, float]:
    return _build_target_values(total_capital, tickers, allocation_method)


def apply_secondary_fill(
    allocation_df: pd.DataFrame,
    total_capital: float,
    enabled: bool,
    avoid_high_valuation: bool,
    avoid_high_valuation_strict: bool,
    max_steps: int,
    allow_over_alloc: bool,
    max_over_alloc_ratio: float,
    max_over_alloc_amount: float,
    max_over_alloc_lots_per_ticker: int,
    cash_buffer_ratio: float,
    cash_buffer_amount: float,
    estimated_fee_per_order: float,
) -> tuple[pd.DataFrame, dict[str, float | int | bool]]:
    return _apply_secondary_fill(
        allocation_df=allocation_df,
        total_capital=total_capital,
        enabled=enabled,
        avoid_high_valuation=avoid_high_valuation,
        avoid_high_valuation_strict=avoid_high_valuation_strict,
        max_steps=max_steps,
        allow_over_alloc=allow_over_alloc,
        max_over_alloc_ratio=max_over_alloc_ratio,
        max_over_alloc_amount=max_over_alloc_amount,
        max_over_alloc_lots_per_ticker=max_over_alloc_lots_per_ticker,
        cash_buffer_ratio=cash_buffer_ratio,
        cash_buffer_amount=cash_buffer_amount,
        estimated_fee_per_order=estimated_fee_per_order,
    )


def build_allocation_table(
    *,
    settings: HkAllocSettings,
    tickers: Sequence[SelectedTicker],
    as_of: date,
    market_data: MarketDataBundle,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    return _build_allocation_table(
        settings=settings,
        tickers=tickers,
        as_of=as_of,
        market_data=market_data,
        apply_secondary_fill_fn=apply_secondary_fill,
    )


def build_sell_signals(
    *,
    settings: HkAllocSettings,
    tickers: Sequence[SelectedTicker],
    market_data: MarketDataBundle,
) -> pd.DataFrame:
    return _build_sell_signals(
        settings=settings,
        tickers=tickers,
        market_data=market_data,
    )


def _to_yes_no(value: Any) -> str:
    return reporting.to_yes_no(value, is_missing_value_fn=_is_missing_value)


def _format_stock_connect(value: Any) -> str:
    return reporting.format_stock_connect(
        value,
        is_missing_value_fn=_is_missing_value,
        is_stock_connect_tradable_fn=_is_stock_connect_tradable,
    )


def _localize_price_source(value: Any) -> str:
    return reporting.localize_price_source(value, is_missing_value_fn=_is_missing_value)


def _localize_side(value: Any) -> str:
    return reporting.localize_side(value, is_missing_value_fn=_is_missing_value)


def _localize_allocation_method(value: Any) -> str:
    return reporting.localize_allocation_method(
        value,
        is_missing_value_fn=_is_missing_value,
    )


def _prepare_allocation_export_df(allocation_df: pd.DataFrame) -> pd.DataFrame:
    return reporting.prepare_allocation_export_df(
        allocation_df,
        to_yes_no_fn=_to_yes_no,
        format_stock_connect_fn=_format_stock_connect,
        localize_price_source_fn=_localize_price_source,
        localize_side_fn=_localize_side,
    )


def _prepare_summary_export_df(summary_df: pd.DataFrame) -> pd.DataFrame:
    return reporting.prepare_summary_export_df(
        summary_df,
        to_yes_no_fn=_to_yes_no,
        localize_price_source_fn=_localize_price_source,
        localize_allocation_method_fn=_localize_allocation_method,
    )


def _prepare_sell_signals_export_df(sell_signals_df: pd.DataFrame) -> pd.DataFrame:
    return reporting.prepare_sell_signals_export_df(
        sell_signals_df,
        localize_side_fn=_localize_side,
    )


def _import_openpyxl() -> Any:
    return reporting.import_openpyxl()


def _make_unique_sheet_name(raw_name: str, existing: set[str]) -> str:
    return reporting.make_unique_sheet_name(raw_name, existing)


def write_xlsx_report(
    output_path: Path,
    allocation_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    sell_signals_df: pd.DataFrame,
) -> Path:
    return reporting.write_xlsx_report(
        output_path,
        allocation_df,
        summary_df,
        sell_signals_df,
        import_openpyxl_fn=_import_openpyxl,
        prepare_allocation_export_df_fn=_prepare_allocation_export_df,
        prepare_summary_export_df_fn=_prepare_summary_export_df,
        prepare_sell_signals_export_df_fn=_prepare_sell_signals_export_df,
    )


def write_scenario_grid_report(
    output_path: Path,
    scenario_reports: Sequence[ScenarioReport],
) -> Path:
    return reporting.write_scenario_grid_report(
        output_path,
        scenario_reports,
        import_openpyxl_fn=_import_openpyxl,
        prepare_allocation_export_df_fn=_prepare_allocation_export_df,
        prepare_summary_export_df_fn=_prepare_summary_export_df,
        prepare_sell_signals_export_df_fn=_prepare_sell_signals_export_df,
    )


def _render_text(payload: dict[str, Any], allocation_df: pd.DataFrame) -> str:
    return reporting.render_text(
        payload,
        allocation_df,
        to_yes_no_fn=_to_yes_no,
        format_stock_connect_fn=_format_stock_connect,
        localize_price_source_fn=_localize_price_source,
    )


def _render_grid_text(root_payload: dict[str, Any], overview_df: pd.DataFrame) -> str:
    return reporting.render_grid_text(
        root_payload,
        overview_df,
        localize_price_source_fn=_localize_price_source,
    )


def _format_capital_tag(capital: float) -> str:
    return reporting.format_capital_tag(capital)


def _build_scenario_id(capital: float, top_n: int) -> str:
    return reporting.build_scenario_id(capital, top_n)


def _build_payload(
    *,
    allocation_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    sell_signals_df: pd.DataFrame,
    as_of: pd.Timestamp,
    entry_date: pd.Timestamp,
    source: str,
    side: str,
    run_dir: Path | None,
    positions_path: Path | None,
    market: str,
    requested_top_n: int,
    settings: HkAllocSettings,
    scenario_id: str | None = None,
    scenario_cash: float | None = None,
    scenario_top_n: int | None = None,
) -> dict[str, Any]:
    return reporting.build_payload(
        allocation_df=allocation_df,
        summary_df=summary_df,
        sell_signals_df=sell_signals_df,
        as_of=as_of,
        entry_date=entry_date,
        source=source,
        side=side,
        run_dir=run_dir,
        positions_path=positions_path,
        market=market,
        requested_top_n=requested_top_n,
        settings=settings,
        scenario_id=scenario_id,
        scenario_cash=scenario_cash,
        scenario_top_n=scenario_top_n,
    )


def _enforce_stock_connect_execution_gate(
    *,
    settings: HkAllocSettings,
    as_of: pd.Timestamp,
    entry_date: pd.Timestamp,
    rqdatac_module: Any,
    market: str,
) -> tuple[pd.Timestamp, bool | None]:
    if not settings.require_stock_connect or settings.execution_calendar != HK_CONNECT_CALENDAR:
        return pd.Timestamp(as_of).normalize(), None
    check_date = max(pd.Timestamp(as_of).normalize(), pd.Timestamp(entry_date).normalize())
    is_open = is_execution_open(
        check_date,
        calendar=settings.execution_calendar,
        rqdatac_module=rqdatac_module,
        market=market,
    )
    if not is_open and not settings.allow_connect_closed:
        raise SystemExit(
            "alloc-hk blocked: Stock Connect southbound execution calendar is closed on "
            f"{check_date.strftime('%Y-%m-%d')}. Use --allow-connect-closed only for research/report-only output."
        )
    return check_date, bool(is_open)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    cfg, settings = _resolve_settings(args)
    scenario_capitals, scenario_top_ns = _resolve_scenarios(args, cfg=cfg, settings=settings)
    prepared, entry_date, as_of, source, run_dir, positions_path, payload_market = _load_selection(
        args,
        cfg=cfg,
        selection_top_n=max(scenario_top_ns),
    )
    enforce_liveops_quality_gate(
        command_name="alloc-hk",
        run_dir=run_dir,
        config_ref=args.config,
        fail_on_quality=args.fail_on_quality,
    )
    tickers = _selection_to_tickers(prepared)
    if not tickers:
        raise SystemExit("No holdings selected for allocation.")

    market = base_alloc._resolve_market(cfg, [item.symbol for item in tickers]) or payload_market or "hk"
    market = "hk" if market is None else str(market).lower()
    if market != "hk":
        raise SystemExit(f"alloc-hk currently only supports HK holdings. Resolved market={market!r}.")

    rqdatac = base_alloc._init_rqdatac(args.config, args.username, args.password)
    execution_check_date, execution_open = _enforce_stock_connect_execution_gate(
        settings=settings,
        as_of=as_of,
        entry_date=entry_date,
        rqdatac_module=rqdatac,
        market=market,
    )
    market_data = prefetch_market_data(
        rqdatac,
        tickers=tickers,
        as_of=as_of.date(),
        history_years=settings.history_years,
        roll_window=settings.roll_window,
    )
    scenario_reports: list[ScenarioReport] = []
    scenario_payloads: list[dict[str, Any]] = []

    for capital in scenario_capitals:
        scenario_settings = replace(settings, cash=float(capital))
        for top_n in scenario_top_ns:
            scenario_id = _build_scenario_id(float(capital), int(top_n))
            scenario_tickers = tickers[: int(top_n)]
            allocation_df, summary_df = build_allocation_table(
                settings=scenario_settings,
                tickers=scenario_tickers,
                as_of=as_of.date(),
                market_data=market_data,
            )
            sell_signals_df = build_sell_signals(
                settings=scenario_settings,
                tickers=scenario_tickers,
                market_data=market_data,
            )

            summary_df = summary_df.copy()
            summary_df["scenario_id"] = scenario_id
            summary_df["scenario_capital"] = float(capital)
            summary_df["scenario_top_n"] = int(top_n)
            summary_df["execution_calendar"] = settings.execution_calendar
            summary_df["execution_check_date"] = execution_check_date.strftime("%Y-%m-%d")
            summary_df["execution_open"] = execution_open

            scenario_reports.append(
                ScenarioReport(
                    scenario_id=scenario_id,
                    allocation_df=allocation_df,
                    summary_df=summary_df,
                    sell_signals_df=sell_signals_df,
                )
            )
            scenario_payloads.append(
                _build_payload(
                    allocation_df=allocation_df,
                    summary_df=summary_df,
                    sell_signals_df=sell_signals_df,
                    as_of=as_of,
                    entry_date=entry_date,
                    source=source,
                    side=args.side,
                    run_dir=run_dir,
                    positions_path=positions_path,
                    market=market,
                    requested_top_n=int(top_n),
                    settings=scenario_settings,
                    scenario_id=scenario_id,
                    scenario_cash=float(capital),
                    scenario_top_n=int(top_n),
                )
            )

    if len(scenario_reports) == 1:
        only = scenario_reports[0]
        payload = scenario_payloads[0]
        allocation_df = only.allocation_df
        summary_df = only.summary_df
        sell_signals_df = only.sell_signals_df
        overview_df = summary_df
    else:
        overview_df = pd.concat([item.summary_df for item in scenario_reports], ignore_index=True)
        payload = {
            "mode": "scenario_grid",
            "as_of": as_of.strftime("%Y-%m-%d"),
            "entry_date": entry_date.strftime("%Y-%m-%d"),
            "source": source,
            "side": args.side,
            "run_dir": str(run_dir) if run_dir is not None else None,
            "positions_file": str(positions_path) if positions_path is not None else None,
            "market": market,
            "scenario_capitals": [float(value) for value in scenario_capitals],
            "scenario_top_ns": [int(value) for value in scenario_top_ns],
            "scenario_overview": overview_df.to_dict(orient="records"),
            "scenarios": scenario_payloads,
        }

    if args.format == "xlsx":
        if not args.out:
            raise SystemExit("--out is required when --format xlsx.")
        out_path = Path(args.out).expanduser()
        if not out_path.is_absolute():
            out_path = (Path.cwd() / out_path).resolve()
        if len(scenario_reports) == 1:
            out_path = write_xlsx_report(out_path, allocation_df, summary_df, sell_signals_df)
        else:
            out_path = write_scenario_grid_report(out_path, scenario_reports)
        print(f"Wrote {out_path}")
        return

    if len(scenario_reports) == 1 and args.format == "text":
        content = _render_text(payload, allocation_df)
    elif len(scenario_reports) > 1 and args.format == "text":
        content = _render_grid_text(payload, overview_df)
    elif len(scenario_reports) == 1 and args.format == "csv":
        content = allocation_df.to_csv(index=False)
    elif len(scenario_reports) > 1 and args.format == "csv":
        content = overview_df.to_csv(index=False)
    else:
        content = json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    if args.out:
        out_path = Path(args.out).expanduser()
        if not out_path.is_absolute():
            out_path = (Path.cwd() / out_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        print(f"Wrote {out_path}")
    else:
        print(content)


if __name__ == "__main__":
    main()
