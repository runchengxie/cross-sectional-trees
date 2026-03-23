from __future__ import annotations

import argparse
import importlib
import json
import logging
import math
import re
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import Any, Sequence
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from ..data_tools.symbols import ensure_symbol_columns
from ..research_tools import alloc as base_alloc
from ..research_tools import holdings

LOGGER = logging.getLogger(__name__)

STOCK_CONNECT_TRUE_VALUES: set[str] = {
    "1",
    "true",
    "yes",
    "y",
    "是",
    "沪港通",
    "深港通",
    "southbound",
    "eligible",
    "sh",
    "sz",
    "沪",
    "深",
}

STOCK_CONNECT_FALSE_VALUES: set[str] = {
    "",
    "0",
    "false",
    "no",
    "n",
    "none",
    "nan",
    "null",
    "否",
    "不是",
    "不可",
    "不支持",
    "not eligible",
}


VALUATION_CN_MAP: dict[str, str] = {
    "LOW": "偏低",
    "NEUTRAL": "中性",
    "HIGH": "偏高",
    "EXTREME": "极高",
    "NA": "NA",
}

PRICE_SOURCE_CN_MAP: dict[str, str] = {
    "snapshot": "快照最新价",
    "1m_close": "1分钟收盘",
    "1d_close": "日线收盘",
    "mixed": "混合",
}

SIDE_CN_MAP: dict[str, str] = {
    "long": "多头",
    "short": "空头",
    "all": "全部",
}

ALLOCATION_METHOD_CN_MAP: dict[str, str] = {
    "equal": "等权",
    "custom": "自定义权重",
}

ALLOCATION_EXPORT_ORDER: list[str] = [
    "stock_ticker",
    "name",
    "side",
    "rank",
    "signal",
    "weight",
    "lots",
    "price",
    "valuation",
    "overpriced_high",
    "order_book_id",
    "tradable",
    "stock_connect",
    "price_source",
    "pricing_date",
    "round_lot",
    "lot_cost",
    "target_value",
    "lots_base",
    "lots_extra",
    "shares",
    "est_value",
    "gap_to_target",
    "gap_ratio",
    "pct_1y",
    "z_1y",
    "overpriced_low",
    "overpriced_range",
]

ALLOCATION_EXPORT_RENAME: dict[str, str] = {
    "stock_ticker": "股票代码",
    "name": "名称",
    "side": "方向",
    "rank": "信号排名",
    "signal": "信号强度",
    "weight": "权重",
    "order_book_id": "查询代码",
    "tradable": "可交易",
    "stock_connect": "港股通",
    "price_source": "价格来源",
    "pricing_date": "定价日期",
    "price": "当前价格",
    "round_lot": "每手股数",
    "lot_cost": "每手成本",
    "target_value": "目标金额",
    "lots_base": "初始手数",
    "lots_extra": "补仓手数",
    "lots": "合计手数",
    "shares": "股数",
    "est_value": "预计金额",
    "gap_to_target": "与目标差额",
    "gap_ratio": "偏离比例",
    "valuation": "估值分层",
    "pct_1y": "1年分位",
    "z_1y": "1年Z分",
    "overpriced_low": "统计高位下沿(未复权)",
    "overpriced_high": "统计高位上沿(未复权)",
    "overpriced_range": "统计高位区间(未复权)",
}

SUMMARY_EXPORT_ORDER: list[str] = [
    "scenario_id",
    "scenario_capital",
    "scenario_top_n",
    "as_of",
    "pricing_date",
    "pricing_source",
    "pricing_source_detail",
    "selected_n",
    "total_capital",
    "allocation_method",
    "require_stock_connect",
    "total_est_value",
    "total_gap",
    "cash_used_ratio",
    "secondary_fill_enabled",
    "secondary_fill_steps",
    "secondary_fill_spent",
    "secondary_fill_fee_spent",
    "secondary_fill_cash_buffer",
    "secondary_fill_budget_after_buffer",
    "cash_remaining_after_fill",
]

SUMMARY_EXPORT_RENAME: dict[str, str] = {
    "scenario_id": "场景",
    "scenario_capital": "场景资金",
    "scenario_top_n": "场景TopN",
    "as_of": "统计日期",
    "pricing_date": "定价日期",
    "pricing_source": "价格来源",
    "pricing_source_detail": "价格来源明细",
    "selected_n": "标的数量",
    "total_capital": "总资金",
    "allocation_method": "分配方式",
    "require_stock_connect": "要求港股通",
    "total_est_value": "预计总金额",
    "total_gap": "总差额",
    "cash_used_ratio": "资金使用率",
    "secondary_fill_enabled": "启用二次补仓",
    "secondary_fill_steps": "补仓步数",
    "secondary_fill_spent": "补仓金额",
    "secondary_fill_fee_spent": "补仓估算费用",
    "secondary_fill_cash_buffer": "补仓现金缓冲",
    "secondary_fill_budget_after_buffer": "补仓可用资金",
    "cash_remaining_after_fill": "补仓后剩余现金",
}

SELL_SIGNALS_EXPORT_ORDER: list[str] = [
    "stock_ticker",
    "name",
    "side",
    "rank",
    "signal",
    "weight",
    "close_pre",
    "valuation",
    "sell_trigger",
    "extreme_trigger",
    "last_sell_signal_date",
    "pct_1y",
    "z_1y",
    "order_book_id",
    "as_of",
]

SELL_SIGNALS_EXPORT_RENAME: dict[str, str] = {
    "stock_ticker": "股票代码",
    "name": "名称",
    "side": "方向",
    "rank": "信号排名",
    "signal": "信号强度",
    "weight": "权重",
    "order_book_id": "查询代码",
    "as_of": "统计日期",
    "close_pre": "前复权收盘价",
    "pct_1y": "1年分位",
    "z_1y": "1年Z分",
    "sell_trigger": "偏高阈值",
    "extreme_trigger": "极高阈值",
    "last_sell_signal_date": "最近卖出信号日期",
    "valuation": "估值分层",
}


@dataclass(frozen=True)
class HkAllocSettings:
    cash: float = 1_000_000.0
    method: str = "equal"
    require_stock_connect: bool = True
    history_years: int = 3
    roll_window: int = 252
    sell_quantile: float = 0.95
    extreme_quantile: float = 0.99
    secondary_fill_enabled: bool = True
    secondary_fill_avoid_high_valuation: bool = True
    secondary_fill_avoid_high_valuation_strict: bool = False
    secondary_fill_max_steps: int = 5000
    secondary_fill_allow_over_alloc: bool = False
    secondary_fill_max_over_alloc_ratio: float = 0.0
    secondary_fill_max_over_alloc_amount: float = 0.0
    secondary_fill_max_over_alloc_lots_per_ticker: int = 1
    secondary_fill_cash_buffer_ratio: float = 0.0
    secondary_fill_cash_buffer_amount: float = 0.0
    secondary_fill_estimated_fee_per_order: float = 0.0


@dataclass(frozen=True)
class SelectedTicker:
    symbol: str
    name: str | None = None
    weight: float | None = None
    rank: int | None = None
    signal: float | None = None
    side: str = "long"


@dataclass(frozen=True)
class ScenarioReport:
    scenario_id: str
    allocation_df: pd.DataFrame
    summary_df: pd.DataFrame
    sell_signals_df: pd.DataFrame


@dataclass(frozen=True)
class MarketDataBundle:
    symbols: tuple[str, ...]
    order_book_ids: tuple[str, ...]
    symbol_to_oid: dict[str, str]
    instruments_df: pd.DataFrame
    latest_prices: pd.DataFrame
    close_none: pd.DataFrame
    close_pre: pd.DataFrame


def _parse_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "是"}:
        return True
    if text in {"false", "0", "no", "n", "否"}:
        return False
    return default


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _is_missing_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (float, np.floating)) and math.isnan(float(value)):
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        return value.strip().lower() in {"", "none", "nan"}
    return False


def _pick_last_non_missing(values: Sequence[Any]) -> Any:
    for value in reversed(list(values)):
        if not _is_missing_value(value):
            return value
    return None


def _pick_round_lot(values: Sequence[Any]) -> float:
    raw = pd.to_numeric(pd.Series(list(values)), errors="coerce")
    numeric = raw.dropna()
    if numeric.empty:
        return float("nan")
    unique_values = sorted({float(v) for v in numeric.tolist()})
    if len(unique_values) > 1:
        LOGGER.warning(
            "Multiple round_lot values found %s; using mode then last non-missing.",
            unique_values,
        )

    counts = numeric.value_counts()
    if counts.empty:
        return float("nan")

    top_count = int(counts.max())
    mode_values = [float(val) for val, count in counts.items() if int(count) == top_count]
    if len(mode_values) == 1:
        return mode_values[0]

    for value in reversed(raw.tolist()):
        if pd.isna(value):
            continue
        value_float = float(value)
        if value_float in mode_values:
            return value_float
    return mode_values[0]


def _coerce_scalar(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        if value.empty:
            return None
        value = value.iloc[-1]
    if isinstance(value, pd.Series):
        return _pick_last_non_missing(value.tolist())
    return value


def _get_attr_or_key(record: Any, key: str) -> Any:
    if isinstance(record, dict):
        return record.get(key)
    return getattr(record, key, None)


def _to_timestamp(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce")
    if isinstance(ts, pd.Timestamp):
        return ts
    return pd.NaT


def _to_date(value: Any) -> date:
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return pd.to_datetime(value).date()


def _nested_mapping(mapping: Any, *keys: str) -> dict[str, Any]:
    current = mapping if isinstance(mapping, dict) else {}
    for key in keys:
        next_value = current.get(key) if isinstance(current, dict) else {}
        current = next_value if isinstance(next_value, dict) else {}
    return current


def _parse_float_list(values: Sequence[Any] | None) -> list[float]:
    if values is None:
        return []
    items: list[float] = []
    for entry in values:
        if isinstance(entry, str):
            parts: Sequence[Any] = entry.split(",")
        else:
            parts = [entry]
        for part in parts:
            text = str(part).strip()
            if not text:
                continue
            items.append(float(text))
    return items


def _parse_int_list(values: Sequence[Any] | None) -> list[int]:
    if values is None:
        return []
    items: list[int] = []
    for entry in values:
        if isinstance(entry, str):
            parts: Sequence[Any] = entry.split(",")
        else:
            parts = [entry]
        for part in parts:
            text = str(part).strip()
            if not text:
                continue
            items.append(int(text))
    return items


def _dedupe_preserve_order(values: Sequence[Any]) -> list[Any]:
    return list(dict.fromkeys(values))


def _resolve_settings(args: argparse.Namespace) -> tuple[dict[str, Any], HkAllocSettings]:
    cfg = base_alloc._load_config(getattr(args, "config", None))
    hk_cfg = _nested_mapping(cfg, "live", "alloc_hk")
    valuation_cfg = hk_cfg.get("valuation") if isinstance(hk_cfg.get("valuation"), dict) else {}
    fill_cfg = hk_cfg.get("secondary_fill") if isinstance(hk_cfg.get("secondary_fill"), dict) else {}

    settings = HkAllocSettings(
        cash=float(args.cash) if args.cash is not None else float(hk_cfg.get("cash", 1_000_000.0)),
        method=str(args.method or hk_cfg.get("method", "equal")).strip().lower(),
        require_stock_connect=(
            _parse_bool(args.require_stock_connect, True)
            if args.require_stock_connect is not None
            else _parse_bool(hk_cfg.get("require_stock_connect"), True)
        ),
        history_years=(
            int(args.history_years)
            if args.history_years is not None
            else int(valuation_cfg.get("history_years", 3))
        ),
        roll_window=(
            int(args.roll_window)
            if args.roll_window is not None
            else int(valuation_cfg.get("roll_window", 252))
        ),
        sell_quantile=(
            float(args.sell_quantile)
            if args.sell_quantile is not None
            else float(valuation_cfg.get("sell_quantile", 0.95))
        ),
        extreme_quantile=(
            float(args.extreme_quantile)
            if args.extreme_quantile is not None
            else float(valuation_cfg.get("extreme_quantile", 0.99))
        ),
        secondary_fill_enabled=(
            _parse_bool(args.secondary_fill_enabled, True)
            if args.secondary_fill_enabled is not None
            else _parse_bool(fill_cfg.get("enabled"), True)
        ),
        secondary_fill_avoid_high_valuation=(
            _parse_bool(args.avoid_high_valuation, True)
            if args.avoid_high_valuation is not None
            else _parse_bool(fill_cfg.get("avoid_high_valuation"), True)
        ),
        secondary_fill_avoid_high_valuation_strict=(
            _parse_bool(args.avoid_high_valuation_strict, False)
            if args.avoid_high_valuation_strict is not None
            else _parse_bool(fill_cfg.get("avoid_high_valuation_strict"), False)
        ),
        secondary_fill_max_steps=(
            int(args.max_steps)
            if args.max_steps is not None
            else int(fill_cfg.get("max_steps", 5000))
        ),
        secondary_fill_allow_over_alloc=(
            _parse_bool(args.allow_over_alloc, False)
            if args.allow_over_alloc is not None
            else _parse_bool(fill_cfg.get("allow_over_alloc"), False)
        ),
        secondary_fill_max_over_alloc_ratio=(
            float(args.max_over_alloc_ratio)
            if args.max_over_alloc_ratio is not None
            else float(fill_cfg.get("max_over_alloc_ratio", 0.0))
        ),
        secondary_fill_max_over_alloc_amount=(
            float(args.max_over_alloc_amount)
            if args.max_over_alloc_amount is not None
            else float(fill_cfg.get("max_over_alloc_amount", 0.0))
        ),
        secondary_fill_max_over_alloc_lots_per_ticker=(
            int(args.max_over_alloc_lots_per_ticker)
            if args.max_over_alloc_lots_per_ticker is not None
            else int(fill_cfg.get("max_over_alloc_lots_per_ticker", 1))
        ),
        secondary_fill_cash_buffer_ratio=(
            float(args.cash_buffer_ratio)
            if args.cash_buffer_ratio is not None
            else float(fill_cfg.get("cash_buffer_ratio", 0.0))
        ),
        secondary_fill_cash_buffer_amount=(
            float(args.cash_buffer_amount)
            if args.cash_buffer_amount is not None
            else float(fill_cfg.get("cash_buffer_amount", 0.0))
        ),
        secondary_fill_estimated_fee_per_order=(
            float(args.estimated_fee_per_order)
            if args.estimated_fee_per_order is not None
            else float(fill_cfg.get("estimated_fee_per_order", 0.0))
        ),
    )

    if settings.cash <= 0:
        raise SystemExit("--cash must be positive.")
    if settings.method not in {"equal", "custom"}:
        raise SystemExit("--method must be one of: equal, custom.")
    if settings.history_years <= 0:
        raise SystemExit("history_years must be > 0.")
    if settings.roll_window <= 1:
        raise SystemExit("roll_window must be > 1.")
    if not (0.0 < settings.sell_quantile < 1.0):
        raise SystemExit("sell_quantile must be in (0, 1).")
    if not (0.0 < settings.extreme_quantile < 1.0):
        raise SystemExit("extreme_quantile must be in (0, 1).")
    if settings.sell_quantile >= settings.extreme_quantile:
        raise SystemExit("sell_quantile must be less than extreme_quantile.")
    if settings.secondary_fill_max_steps <= 0:
        raise SystemExit("secondary_fill.max_steps must be > 0.")
    if settings.secondary_fill_max_over_alloc_ratio < 0:
        raise SystemExit("secondary_fill.max_over_alloc_ratio must be >= 0.")
    if settings.secondary_fill_max_over_alloc_amount < 0:
        raise SystemExit("secondary_fill.max_over_alloc_amount must be >= 0.")
    if settings.secondary_fill_max_over_alloc_lots_per_ticker < 0:
        raise SystemExit("secondary_fill.max_over_alloc_lots_per_ticker must be >= 0.")
    if settings.secondary_fill_cash_buffer_ratio < 0:
        raise SystemExit("secondary_fill.cash_buffer_ratio must be >= 0.")
    if settings.secondary_fill_cash_buffer_amount < 0:
        raise SystemExit("secondary_fill.cash_buffer_amount must be >= 0.")
    if settings.secondary_fill_estimated_fee_per_order < 0:
        raise SystemExit("secondary_fill.estimated_fee_per_order must be >= 0.")
    if (
        settings.secondary_fill_allow_over_alloc
        and settings.secondary_fill_max_over_alloc_lots_per_ticker == 0
    ):
        raise SystemExit(
            "secondary_fill.max_over_alloc_lots_per_ticker must be > 0 when allow_over_alloc=true."
        )

    return cfg, settings


def _resolve_scenarios(
    args: argparse.Namespace,
    *,
    cfg: dict[str, Any],
    settings: HkAllocSettings,
) -> tuple[tuple[float, ...], tuple[int, ...]]:
    scenarios_cfg = _nested_mapping(cfg, "live", "alloc_hk", "scenarios")
    raw_capitals: Sequence[Any] | None = args.scenario_capital
    raw_top_ns: Sequence[Any] | None = args.scenario_top_n

    if raw_capitals is None:
        cfg_capitals = scenarios_cfg.get("capitals")
        if isinstance(cfg_capitals, (list, tuple)):
            raw_capitals = list(cfg_capitals)
    if raw_top_ns is None:
        cfg_top_ns = scenarios_cfg.get("top_ns")
        if isinstance(cfg_top_ns, (list, tuple)):
            raw_top_ns = list(cfg_top_ns)

    capitals = _parse_float_list(raw_capitals) if raw_capitals is not None else [settings.cash]
    top_ns = _parse_int_list(raw_top_ns) if raw_top_ns is not None else [args.top_n]

    if not capitals:
        capitals = [settings.cash]
    if not top_ns:
        top_ns = [args.top_n]

    capitals = _dedupe_preserve_order(capitals)
    top_ns = _dedupe_preserve_order(top_ns)

    for idx, capital in enumerate(capitals):
        if capital <= 0:
            raise SystemExit(f"scenario capital at index {idx} must be > 0.")
    for idx, top_n in enumerate(top_ns):
        if top_n <= 0:
            raise SystemExit(f"scenario top_n at index {idx} must be > 0.")

    return tuple(float(value) for value in capitals), tuple(int(value) for value in top_ns)


def _selection_to_tickers(selection: pd.DataFrame) -> list[SelectedTicker]:
    tickers: list[SelectedTicker] = []
    for _, row in selection.iterrows():
        weight_raw = pd.to_numeric(pd.Series([row.get("weight")]), errors="coerce").iloc[0]
        rank_raw = pd.to_numeric(pd.Series([row.get("rank")]), errors="coerce").iloc[0]
        signal_raw = pd.to_numeric(pd.Series([row.get("signal")]), errors="coerce").iloc[0]
        name_value = None
        for column in ("name", "stock_name", "display_name", "security_name"):
            if column in selection.columns and pd.notna(row.get(column)):
                name_value = str(row.get(column)).strip() or None
                if name_value:
                    break
        tickers.append(
            SelectedTicker(
                symbol=str(row["symbol"]).strip(),
                name=name_value,
                weight=float(weight_raw) if pd.notna(weight_raw) else None,
                rank=int(rank_raw) if pd.notna(rank_raw) else None,
                signal=float(signal_raw) if pd.notna(signal_raw) else None,
                side=str(row.get("side", "long")).strip().lower() or "long",
            )
        )
    return tickers


def _load_selection(
    args: argparse.Namespace,
    *,
    cfg: dict[str, Any],
    selection_top_n: int | None = None,
) -> tuple[pd.DataFrame, pd.Timestamp, pd.Timestamp, str, Path | None, Path | None, str | None]:
    cfg_provider = base_alloc._resolve_provider(cfg)
    cfg_market = base_alloc._resolve_market(cfg, [])

    run_dir: Path | None = None
    positions_path: Path | None = None

    if args.positions_file:
        as_of = holdings._resolve_as_of(
            args.as_of,
            market=cfg_market,
            provider=cfg_provider,
        )
        positions_path = Path(args.positions_file).expanduser()
        if not positions_path.is_absolute():
            positions_path = (Path.cwd() / positions_path).resolve()
        selection, entry_date = base_alloc._select_from_positions_file(positions_path, as_of)
        source = "positions_file"
        payload_market = None
    else:
        payload = base_alloc._load_holdings_payload(args)
        rows = payload.get("holdings")
        if not isinstance(rows, list):
            raise SystemExit("Invalid holdings payload: missing holdings list.")
        selection = pd.DataFrame(rows)
        if selection.empty:
            raise SystemExit("Holdings payload is empty.")
        entry_date = pd.to_datetime(payload.get("entry_date"), errors="coerce")
        if pd.isna(entry_date) and "entry_date" in selection.columns:
            parsed_entries = holdings._parse_date_column(selection["entry_date"])
            if parsed_entries.notna().any():
                entry_date = parsed_entries.max()
        if pd.isna(entry_date):
            raise SystemExit("Failed to parse entry_date from holdings payload.")
        entry_date = pd.Timestamp(entry_date).normalize()
        run_value = payload.get("run_dir")
        if run_value:
            run_dir = Path(str(run_value))
        positions_value = payload.get("positions_file")
        if positions_value:
            positions_path = Path(str(positions_value))
        source = str(payload.get("source") or args.source)
        payload_market = holdings._normalize_market(payload.get("market"))
        payload_provider = holdings._normalize_provider(payload.get("data_provider"))
        as_of_payload = pd.to_datetime(payload.get("as_of"), errors="coerce")
        if pd.notna(as_of_payload):
            as_of = pd.Timestamp(as_of_payload).normalize()
        else:
            as_of = holdings._resolve_as_of(
                args.as_of,
                market=payload_market or cfg_market,
                provider=payload_provider or cfg_provider,
            )

    selection = ensure_symbol_columns(selection, context="alloc-hk input")
    top_n_value = int(selection_top_n) if selection_top_n is not None else int(args.top_n)
    prepared = base_alloc._prepare_selection(selection, side=args.side, top_n=top_n_value)
    return prepared, entry_date, as_of, source, run_dir, positions_path, payload_market


def _build_order_book_mapping(
    tickers: Sequence[SelectedTicker],
) -> tuple[list[str], list[str], dict[str, str]]:
    symbols = [item.symbol for item in tickers]
    order_book_ids = [base_alloc._to_rq_order_book_id(symbol, "hk") for symbol in symbols]
    symbol_to_oid = dict(zip(symbols, order_book_ids))
    return symbols, order_book_ids, symbol_to_oid


def _normalize_close_output(px: pd.DataFrame | None, order_book_ids: Sequence[str]) -> pd.DataFrame:
    if px is None:
        return pd.DataFrame(columns=list(order_book_ids))

    if isinstance(px.index, pd.MultiIndex):
        close = px["close"].unstack(0)
    elif isinstance(px.columns, pd.MultiIndex):
        close = (
            px["close"]
            if "close" in px.columns.get_level_values(0)
            else px.xs("close", axis=1, level=1)
        )
    else:
        if list(px.columns) == ["close"]:
            close = px.rename(columns={"close": order_book_ids[0]})
        else:
            close = px.copy()

    if isinstance(close, pd.Series):
        close = close.to_frame(name=order_book_ids[0])

    close.index = pd.to_datetime(close.index)
    close = close.sort_index()

    for oid in order_book_ids:
        if oid not in close.columns:
            close[oid] = np.nan

    return close[list(order_book_ids)]


def fetch_instruments(rqdatac_module: Any, order_book_ids: Sequence[str], market: str) -> pd.DataFrame:
    instruments = rqdatac_module.instruments(list(order_book_ids), market=market)
    if not isinstance(instruments, list):
        instruments = [instruments]

    rows: list[dict[str, Any]] = []
    for ins in instruments:
        if ins is None:
            continue
        rows.append(
            {
                "order_book_id": ins.order_book_id,
                "symbol": getattr(ins, "symbol", None),
                "round_lot": safe_float(getattr(ins, "round_lot", np.nan)),
                "stock_connect": getattr(ins, "stock_connect", None),
            }
        )

    if not rows:
        return pd.DataFrame(columns=["symbol", "round_lot", "stock_connect"])

    raw = pd.DataFrame(rows)
    grouped = (
        raw.groupby("order_book_id", sort=False, as_index=True)
        .agg(
            symbol=("symbol", lambda s: _pick_last_non_missing(s.tolist())),
            round_lot=("round_lot", _pick_round_lot),
            stock_connect=("stock_connect", lambda s: _pick_last_non_missing(s.tolist())),
        )
    )
    return grouped


def fetch_close_prices(
    rqdatac_module: Any,
    order_book_ids: Sequence[str],
    start_date: date,
    end_date: date,
    market: str,
    adjust_type: str,
) -> pd.DataFrame:
    px = rqdatac_module.get_price(
        list(order_book_ids),
        start_date=start_date,
        end_date=end_date,
        frequency="1d",
        fields=["close"],
        adjust_type=adjust_type,
        market=market,
        expect_df=True,
    )
    return _normalize_close_output(px, order_book_ids)


def _empty_live_price_frame(order_book_ids: Sequence[str]) -> pd.DataFrame:
    return pd.DataFrame(
        index=list(order_book_ids),
        data={"price": np.nan, "pricing_ts": pd.NaT},
    )


def fetch_snapshot_prices(
    rqdatac_module: Any,
    order_book_ids: Sequence[str],
    market: str,
) -> pd.DataFrame:
    empty = _empty_live_price_frame(order_book_ids)

    try:
        snapshots = rqdatac_module.current_snapshot(list(order_book_ids), market=market)
    except Exception:
        return empty

    if snapshots is None:
        return empty
    if not isinstance(snapshots, list):
        snapshots = [snapshots]

    rows: list[dict[str, Any]] = []
    for snap in snapshots:
        if snap is None:
            continue

        oid = _get_attr_or_key(snap, "order_book_id")
        if _is_missing_value(oid):
            continue

        last = safe_float(_get_attr_or_key(snap, "last"))
        close = safe_float(_get_attr_or_key(snap, "close"))
        price = last if last > 0 else close if close > 0 else np.nan
        pricing_ts = _to_timestamp(_get_attr_or_key(snap, "datetime"))
        rows.append(
            {
                "order_book_id": str(oid),
                "price": price,
                "pricing_ts": pricing_ts,
            }
        )

    if not rows:
        return empty

    snap_df = pd.DataFrame(rows).drop_duplicates(subset=["order_book_id"], keep="last")
    snap_df = snap_df.set_index("order_book_id")[["price", "pricing_ts"]]
    empty.update(snap_df)
    return empty


def fetch_current_minute_prices(
    rqdatac_module: Any,
    order_book_ids: Sequence[str],
    market: str,
) -> pd.DataFrame:
    empty = _empty_live_price_frame(order_book_ids)

    minute_df: pd.DataFrame | None
    try:
        minute_df = rqdatac_module.current_minute(list(order_book_ids), fields=["close"], market=market)
    except TypeError:
        try:
            minute_df = rqdatac_module.current_minute(list(order_book_ids), market=market)
        except Exception:
            return empty
    except Exception:
        return empty

    if minute_df is None or minute_df.empty:
        return empty

    frame = minute_df.reset_index()
    if "order_book_id" not in frame.columns:
        return empty

    price_field = "close" if "close" in frame.columns else "last" if "last" in frame.columns else None
    if price_field is None:
        return empty
    if "datetime" not in frame.columns:
        frame["datetime"] = pd.NaT

    frame["price"] = pd.to_numeric(frame[price_field], errors="coerce")
    frame["pricing_ts"] = pd.to_datetime(frame["datetime"], errors="coerce")
    frame = frame.sort_values(["order_book_id", "pricing_ts"], na_position="last")
    frame = frame.groupby("order_book_id", as_index=False).tail(1)

    latest = frame.set_index("order_book_id")[["price", "pricing_ts"]]
    empty.update(latest)
    return empty


def _should_try_live_prices(as_of: date, market: str) -> bool:
    market_key = str(market).strip().lower()
    if market_key == "hk":
        today = datetime.now(ZoneInfo("Asia/Hong_Kong")).date()
        return as_of == today
    return as_of == datetime.now().date()


def _get_previous_trading_date(
    rqdatac_module: Any,
    ref_date: date,
    n: int,
    market: str,
) -> date:
    try:
        result = rqdatac_module.get_previous_trading_date(ref_date, n=n, market=market)
    except TypeError:
        result = rqdatac_module.get_previous_trading_date(ref_date, n, market=market)
    return _to_date(result)


def build_latest_price_frame(
    rqdatac_module: Any,
    order_book_ids: Sequence[str],
    as_of: date,
    market: str,
) -> pd.DataFrame:
    price_start = _get_previous_trading_date(rqdatac_module, as_of, n=10, market=market)
    close_today = fetch_close_prices(
        rqdatac_module,
        order_book_ids,
        start_date=price_start,
        end_date=as_of,
        market=market,
        adjust_type="none",
    )
    if close_today.empty:
        raise SystemExit("No recent HK close price returned for allocation.")

    close_today_clean = close_today.dropna(how="all")
    if close_today_clean.empty:
        raise SystemExit("Recent HK close prices are all missing for the selected tickers.")

    latest_close_ts = pd.Timestamp(close_today_clean.index[-1])
    latest_close_row = close_today_clean.iloc[-1].reindex(list(order_book_ids))

    price_frame = pd.DataFrame(
        index=list(order_book_ids),
        data={
            "price": pd.to_numeric(latest_close_row, errors="coerce"),
            "price_source": "1d_close",
            "pricing_ts": latest_close_ts,
        },
    )

    if _should_try_live_prices(as_of=as_of, market=market):
        snapshot_frame = fetch_snapshot_prices(rqdatac_module, order_book_ids, market=market)
        minute_frame = fetch_current_minute_prices(rqdatac_module, order_book_ids, market=market)

        for oid in order_book_ids:
            snapshot_price = safe_float(snapshot_frame.at[oid, "price"])
            if snapshot_price > 0:
                price_frame.at[oid, "price"] = snapshot_price
                price_frame.at[oid, "price_source"] = "snapshot"
                snapshot_ts = _to_timestamp(snapshot_frame.at[oid, "pricing_ts"])
                if pd.notna(snapshot_ts):
                    price_frame.at[oid, "pricing_ts"] = snapshot_ts
                continue

            minute_price = safe_float(minute_frame.at[oid, "price"])
            if minute_price > 0:
                price_frame.at[oid, "price"] = minute_price
                price_frame.at[oid, "price_source"] = "1m_close"
                minute_ts = _to_timestamp(minute_frame.at[oid, "pricing_ts"])
                if pd.notna(minute_ts):
                    price_frame.at[oid, "pricing_ts"] = minute_ts

    price_frame["pricing_date"] = pd.to_datetime(price_frame["pricing_ts"], errors="coerce").dt.date
    fallback_date = _to_date(latest_close_ts)
    price_frame["pricing_date"] = price_frame["pricing_date"].fillna(fallback_date)
    return price_frame


def _last_value_percentile(values: np.ndarray) -> float:
    if values.size == 0 or np.isnan(values[-1]):
        return np.nan
    valid = values[~np.isnan(values)]
    if valid.size == 0:
        return np.nan
    return float(np.mean(valid <= values[-1]))


def compute_valuation_metrics(
    close_pre: pd.DataFrame,
    window: int,
    sell_quantile: float,
    extreme_quantile: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    q_high = close_pre.rolling(window=window, min_periods=window).quantile(sell_quantile)
    q_extreme = close_pre.rolling(window=window, min_periods=window).quantile(extreme_quantile)
    percentile = close_pre.rolling(window=window, min_periods=window).apply(_last_value_percentile, raw=True)

    log_price = np.log(close_pre.where(close_pre > 0))
    mean = log_price.rolling(window=window, min_periods=window).mean()
    std = log_price.rolling(window=window, min_periods=window).std()
    zscore = (log_price - mean) / std

    return percentile, zscore, q_high, q_extreme


def classify_valuation(
    percentile: float,
    zscore: float,
    sell_quantile: float,
    extreme_quantile: float,
) -> str:
    if math.isnan(percentile) and math.isnan(zscore):
        return "NA"
    if (
        not math.isnan(percentile)
        and percentile >= extreme_quantile
    ) or (
        not math.isnan(zscore)
        and zscore >= 2.5
    ):
        return "EXTREME"
    if (
        not math.isnan(percentile)
        and percentile >= sell_quantile
    ) or (
        not math.isnan(zscore)
        and zscore >= 2.0
    ):
        return "HIGH"
    if (
        not math.isnan(percentile)
        and percentile <= (1 - sell_quantile)
    ) or (
        not math.isnan(zscore)
        and zscore <= -2.0
    ):
        return "LOW"
    return "NEUTRAL"


def calc_lots(
    target_value: float,
    price: float,
    round_lot: float,
    tradable: bool,
) -> int:
    if not tradable:
        return 0
    if any(math.isnan(x) for x in [target_value, price, round_lot]):
        return 0
    if target_value <= 0 or price <= 0 or round_lot <= 0:
        return 0
    return int(math.floor(target_value / (price * round_lot)))


def build_target_values(
    total_capital: float,
    tickers: Sequence[SelectedTicker],
    allocation_method: str,
) -> dict[str, float]:
    if not tickers:
        raise SystemExit("No holdings selected for allocation.")
    if allocation_method == "equal":
        value = total_capital / len(tickers)
        return {item.symbol: value for item in tickers}
    if allocation_method != "custom":
        raise SystemExit(f"Unsupported allocation method: {allocation_method}")

    weight_map = {item.symbol: float(item.weight or 0.0) for item in tickers}
    if any(item.weight is None for item in tickers):
        raise SystemExit("custom allocation requires weight for each selected ticker.")
    total_weight = sum(weight_map.values())
    if total_weight <= 0:
        raise SystemExit("custom allocation weight sum must be > 0.")
    return {
        symbol: (weight / total_weight) * total_capital
        for symbol, weight in weight_map.items()
    }


def _is_stock_connect_tradable(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if _is_missing_value(value):
        return False
    if isinstance(value, (list, tuple, set)):
        return any(_is_stock_connect_tradable(item) for item in value)

    text = re.sub(r"\s+", " ", str(value).strip().lower())
    if text in STOCK_CONNECT_TRUE_VALUES:
        return True
    if text in STOCK_CONNECT_FALSE_VALUES:
        return False

    tokens = [token for token in re.split(r"[,\s/|]+", text) if token]
    if tokens:
        if any(token in STOCK_CONNECT_TRUE_VALUES for token in tokens):
            return True
        if all(token in STOCK_CONNECT_FALSE_VALUES for token in tokens):
            return False
    return False


def prefetch_market_data(
    rqdatac_module: Any,
    tickers: Sequence[SelectedTicker],
    as_of: date,
    *,
    history_years: int,
    roll_window: int,
) -> MarketDataBundle:
    symbols, order_book_ids, symbol_to_oid = _build_order_book_mapping(tickers)
    if not order_book_ids:
        raise SystemExit("No holdings selected for market data prefetch.")

    instruments_df = fetch_instruments(rqdatac_module, order_book_ids, market="hk")
    latest_prices = build_latest_price_frame(
        rqdatac_module,
        order_book_ids=order_book_ids,
        as_of=as_of,
        market="hk",
    )

    hist_days = max(history_years * 252, roll_window + 5)
    hist_start = _get_previous_trading_date(rqdatac_module, as_of, n=hist_days, market="hk")

    close_none = fetch_close_prices(
        rqdatac_module,
        order_book_ids,
        start_date=hist_start,
        end_date=as_of,
        market="hk",
        adjust_type="none",
    )
    close_pre = fetch_close_prices(
        rqdatac_module,
        order_book_ids,
        start_date=hist_start,
        end_date=as_of,
        market="hk",
        adjust_type="pre",
    )

    return MarketDataBundle(
        symbols=tuple(symbols),
        order_book_ids=tuple(order_book_ids),
        symbol_to_oid=symbol_to_oid,
        instruments_df=instruments_df,
        latest_prices=latest_prices,
        close_none=close_none,
        close_pre=close_pre,
    )


def _subset_market_data(
    bundle: MarketDataBundle,
    order_book_ids: Sequence[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    missing = [oid for oid in order_book_ids if oid not in bundle.order_book_ids]
    if missing:
        raise SystemExit(f"Market data bundle missing order_book_ids: {', '.join(missing)}")

    instruments = bundle.instruments_df.reindex(list(order_book_ids))
    latest_prices = bundle.latest_prices.reindex(list(order_book_ids))
    close_none = bundle.close_none.reindex(columns=list(order_book_ids))
    close_pre = bundle.close_pre.reindex(columns=list(order_book_ids))
    return instruments, latest_prices, close_none, close_pre


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
    updated = allocation_df.copy()
    if "lots_extra" not in updated.columns:
        updated["lots_extra"] = 0
    updated["lots_extra"] = pd.to_numeric(updated["lots_extra"], errors="coerce").fillna(0).astype(int)

    def recompute_position_columns(frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.copy()
        for idx, row in out.iterrows():
            lots_raw = safe_float(row.get("lots", 0))
            lots = max(int(lots_raw) if not math.isnan(lots_raw) else 0, 0)
            round_lot = safe_float(row.get("round_lot", np.nan))
            price = safe_float(row.get("price", np.nan))
            lot_cost_existing = safe_float(row.get("lot_cost", np.nan))
            if (math.isnan(price) or price <= 0) and round_lot > 0 and not math.isnan(round_lot):
                if lot_cost_existing > 0:
                    price = lot_cost_existing / round_lot
            target_value = safe_float(row.get("target_value", np.nan))
            tradable = bool(row.get("tradable", False))

            shares = int(round(lots * round_lot)) if round_lot > 0 and not math.isnan(round_lot) else 0
            est_value = float(shares * price) if price > 0 and not math.isnan(price) else 0.0
            lot_cost = float(price * round_lot) if tradable and price > 0 and round_lot > 0 else float("nan")
            if math.isnan(target_value):
                target_value = 0.0

            out.at[idx, "lots"] = lots
            out.at[idx, "shares"] = shares
            out.at[idx, "est_value"] = est_value
            out.at[idx, "lot_cost"] = lot_cost
            out.at[idx, "gap_to_target"] = float(target_value - est_value)
        return out

    buffer_amount = float(total_capital * max(cash_buffer_ratio, 0.0) + max(cash_buffer_amount, 0.0))
    available_budget = max(float(total_capital - buffer_amount), 0.0)

    if not enabled or updated.empty:
        updated = recompute_position_columns(updated)
        return (
            updated,
            {
                "secondary_fill_enabled": bool(enabled),
                "secondary_fill_steps": 0,
                "secondary_fill_spent": 0.0,
                "secondary_fill_fee_spent": 0.0,
                "secondary_fill_cash_buffer": float(buffer_amount),
                "secondary_fill_budget_after_buffer": float(available_budget),
                "cash_remaining_after_fill": max(total_capital - float(updated["est_value"].sum()), 0.0),
            },
        )

    eps = 1e-9
    over_alloc_caps: list[float] = []
    if allow_over_alloc and max_over_alloc_ratio > 0:
        over_alloc_caps.append(float(total_capital * max_over_alloc_ratio))
    if allow_over_alloc and max_over_alloc_amount > 0:
        over_alloc_caps.append(float(max_over_alloc_amount))
    max_over_alloc_value = min(over_alloc_caps) if over_alloc_caps else (float("inf") if allow_over_alloc else 0.0)

    valuation_rank = {"LOW": 0, "NEUTRAL": 1, "HIGH": 2, "EXTREME": 3, "NA": 4}
    disallowed_when_avoid = {"HIGH", "EXTREME"}
    over_alloc_count_by_idx: dict[Any, int] = {idx: 0 for idx in updated.index}

    def candidate_rows(cash_left: float) -> pd.DataFrame:
        candidates = updated[
            (updated["tradable"] == True)
            & (updated["lot_cost"] > 0)
            & (updated["gap_to_target"] > eps)
        ].copy()
        if candidates.empty:
            return candidates

        candidates["required_cash"] = pd.to_numeric(candidates["lot_cost"], errors="coerce").fillna(0.0) + max(
            estimated_fee_per_order, 0.0
        )
        candidates = candidates[candidates["required_cash"] <= cash_left + eps]
        if candidates.empty:
            return candidates

        candidates["new_gap"] = candidates["gap_to_target"] - candidates["lot_cost"]
        candidates["improves_gap"] = (candidates["new_gap"].abs() + eps) < candidates["gap_to_target"].abs()
        candidates = candidates[candidates["improves_gap"] == True]
        if candidates.empty:
            return candidates

        if not allow_over_alloc:
            candidates = candidates[candidates["new_gap"] >= -eps]
        else:
            candidates = candidates[candidates["new_gap"] >= (-max_over_alloc_value - eps)]
            if max_over_alloc_lots_per_ticker <= 0:
                candidates = candidates[candidates["new_gap"] >= -eps]
            else:
                over_limit_mask = []
                for idx, row in candidates.iterrows():
                    over_after = float(row["new_gap"]) < -eps
                    over_count = int(over_alloc_count_by_idx.get(idx, 0))
                    over_limit_mask.append(not (over_after and over_count >= max_over_alloc_lots_per_ticker))
                candidates = candidates.loc[over_limit_mask]
        if candidates.empty:
            return candidates

        if avoid_high_valuation:
            preferred = candidates[~candidates["valuation"].isin(disallowed_when_avoid)]
            if not preferred.empty:
                return preferred
            if avoid_high_valuation_strict:
                return preferred
        return candidates

    def ranking_key(row: pd.Series) -> tuple[float, float, float, str]:
        valuation = str(row.get("valuation", "NA"))
        rank = valuation_rank.get(valuation, 5)
        deviation_after_lot = abs(float(row["gap_to_target"]) - float(row["lot_cost"]))
        lot_cost = float(row["lot_cost"])
        symbol = str(row.get("symbol", ""))
        return (float(rank), deviation_after_lot, lot_cost, symbol)

    cash_left = max(available_budget - float(updated["est_value"].sum()), 0.0)
    tradable_costs = pd.to_numeric(updated.loc[updated["tradable"] == True, "lot_cost"], errors="coerce")
    tradable_costs = tradable_costs[tradable_costs > 0]
    if tradable_costs.empty:
        step_limit = 0
    else:
        min_required_cash = float(tradable_costs.min() + max(estimated_fee_per_order, 0.0))
        if min_required_cash <= 0:
            step_limit = max_steps
        else:
            theoretical_limit = int(math.floor(cash_left / min_required_cash)) + 1
            step_limit = min(max_steps, max(theoretical_limit, 0))

    steps = 0
    spent = 0.0
    fee_spent = 0.0

    while cash_left > eps and steps < step_limit:
        candidates = candidate_rows(cash_left)
        if candidates.empty:
            break

        selected_idx = min(candidates.index, key=lambda idx: ranking_key(candidates.loc[idx]))
        row = updated.loc[selected_idx]
        lot_cost = float(row["lot_cost"])
        required_cash = lot_cost + max(estimated_fee_per_order, 0.0)
        if lot_cost <= 0 or required_cash > cash_left + eps:
            break

        updated.at[selected_idx, "lots"] = int(row["lots"]) + 1
        updated.at[selected_idx, "lots_extra"] = int(row.get("lots_extra", 0)) + 1

        new_gap = float(row["gap_to_target"]) - lot_cost
        if new_gap < -eps:
            over_alloc_count_by_idx[selected_idx] = int(over_alloc_count_by_idx.get(selected_idx, 0)) + 1

        cash_left -= required_cash
        spent += lot_cost
        fee_spent += max(estimated_fee_per_order, 0.0)
        steps += 1

    updated = recompute_position_columns(updated)
    cash_left = max(total_capital - float(updated["est_value"].sum()) - float(fee_spent), 0.0)
    return (
        updated,
        {
            "secondary_fill_enabled": bool(enabled),
            "secondary_fill_steps": int(steps),
            "secondary_fill_spent": float(spent),
            "secondary_fill_fee_spent": float(fee_spent),
            "secondary_fill_cash_buffer": float(buffer_amount),
            "secondary_fill_budget_after_buffer": float(available_budget),
            "cash_remaining_after_fill": float(cash_left),
        },
    )


def build_allocation_table(
    *,
    settings: HkAllocSettings,
    tickers: Sequence[SelectedTicker],
    as_of: date,
    market_data: MarketDataBundle,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    symbols, order_book_ids, symbol_to_oid = _build_order_book_mapping(tickers)
    instruments_df, latest_prices, close_hist, _ = _subset_market_data(market_data, order_book_ids)

    percentile, zscore, q_high, q_extreme = compute_valuation_metrics(
        close_hist,
        window=settings.roll_window,
        sell_quantile=settings.sell_quantile,
        extreme_quantile=settings.extreme_quantile,
    )

    if close_hist.empty:
        raise SystemExit("No historical HK price data returned; check RQData permissions or ticker list.")
    latest_row = close_hist.index.max()
    target_values = build_target_values(settings.cash, tickers, settings.method)

    rows: list[dict[str, Any]] = []
    for item in tickers:
        symbol = item.symbol
        oid = symbol_to_oid[symbol]

        instrument_symbol = None
        if oid in instruments_df.index and "symbol" in instruments_df.columns:
            instrument_symbol = _coerce_scalar(instruments_df.loc[oid, "symbol"])
        round_lot = (
            safe_float(instruments_df.loc[oid, "round_lot"])
            if oid in instruments_df.index and "round_lot" in instruments_df.columns
            else float("nan")
        )
        stock_connect = (
            _coerce_scalar(instruments_df.loc[oid, "stock_connect"])
            if oid in instruments_df.index and "stock_connect" in instruments_df.columns
            else None
        )
        price = safe_float(latest_prices.at[oid, "price"])
        price_source = str(latest_prices.at[oid, "price_source"])
        pricing_date = _to_date(latest_prices.at[oid, "pricing_date"])

        is_connect_tradable = _is_stock_connect_tradable(stock_connect)
        tradable = (
            (not settings.require_stock_connect or is_connect_tradable)
            and price > 0
            and round_lot > 0
        )

        target_value = float(target_values[symbol])
        lots = calc_lots(target_value, price, round_lot, tradable)
        lot_cost = float(price * round_lot) if tradable else float("nan")
        shares = int(lots * round_lot) if round_lot > 0 and not math.isnan(round_lot) else 0
        est_value = float(shares * price) if price > 0 and not math.isnan(price) else 0.0
        gap_to_target = float(target_value - est_value)

        pct = safe_float(percentile.loc[latest_row, oid]) if oid in percentile.columns else np.nan
        z_1y = safe_float(zscore.loc[latest_row, oid]) if oid in zscore.columns else np.nan
        high_line = safe_float(q_high.loc[latest_row, oid]) if oid in q_high.columns else np.nan
        extreme_line = safe_float(q_extreme.loc[latest_row, oid]) if oid in q_extreme.columns else np.nan

        if math.isnan(high_line) or math.isnan(extreme_line):
            overpriced_range = None
        else:
            overpriced_range = f"[{high_line:.4f}, {extreme_line:.4f}]"

        rows.append(
            {
                "symbol": symbol,
                "ts_code": symbol,
                "stock_ticker": symbol,
                "name": item.name or (str(instrument_symbol).strip() if instrument_symbol else None),
                "side": item.side,
                "rank": item.rank,
                "signal": item.signal,
                "weight": item.weight,
                "order_book_id": oid,
                "price": price,
                "price_source": price_source,
                "pricing_date": pricing_date,
                "round_lot": round_lot,
                "stock_connect": stock_connect,
                "target_value": target_value,
                "lot_cost": lot_cost,
                "lots": lots,
                "lots_extra": 0,
                "shares": shares,
                "est_value": est_value,
                "gap_to_target": gap_to_target,
                "pct_1y": pct,
                "z_1y": z_1y,
                "valuation": classify_valuation(
                    pct,
                    z_1y,
                    sell_quantile=settings.sell_quantile,
                    extreme_quantile=settings.extreme_quantile,
                ),
                "overpriced_low": high_line,
                "overpriced_high": extreme_line,
                "overpriced_range": overpriced_range,
                "tradable": tradable,
            }
        )

    allocation_df = pd.DataFrame(rows)
    allocation_df, fill_stats = apply_secondary_fill(
        allocation_df,
        total_capital=settings.cash,
        enabled=settings.secondary_fill_enabled,
        avoid_high_valuation=settings.secondary_fill_avoid_high_valuation,
        avoid_high_valuation_strict=settings.secondary_fill_avoid_high_valuation_strict,
        max_steps=settings.secondary_fill_max_steps,
        allow_over_alloc=settings.secondary_fill_allow_over_alloc,
        max_over_alloc_ratio=settings.secondary_fill_max_over_alloc_ratio,
        max_over_alloc_amount=settings.secondary_fill_max_over_alloc_amount,
        max_over_alloc_lots_per_ticker=settings.secondary_fill_max_over_alloc_lots_per_ticker,
        cash_buffer_ratio=settings.secondary_fill_cash_buffer_ratio,
        cash_buffer_amount=settings.secondary_fill_cash_buffer_amount,
        estimated_fee_per_order=settings.secondary_fill_estimated_fee_per_order,
    )

    allocation_df["lots_base"] = allocation_df["lots"] - allocation_df["lots_extra"]
    allocation_df["gap_ratio"] = np.where(
        allocation_df["target_value"] > 0,
        allocation_df["gap_to_target"] / allocation_df["target_value"],
        np.nan,
    )

    pricing_dates = pd.to_datetime(latest_prices["pricing_date"], errors="coerce").dropna()
    summary_pricing_date = _to_date(pricing_dates.max()) if not pricing_dates.empty else as_of
    source_counts = latest_prices["price_source"].value_counts(dropna=False).to_dict()
    source_parts = [f"{str(source)}:{int(count)}" for source, count in source_counts.items()]
    summary_pricing_source = next(iter(source_counts.keys())) if len(source_counts) == 1 else "mixed"

    summary_df = pd.DataFrame(
        [
            {
                "as_of": as_of,
                "pricing_date": summary_pricing_date,
                "pricing_source": summary_pricing_source,
                "pricing_source_detail": ", ".join(source_parts),
                "selected_n": len(tickers),
                "total_capital": settings.cash,
                "allocation_method": settings.method,
                "require_stock_connect": settings.require_stock_connect,
                "total_est_value": float(allocation_df["est_value"].sum()),
                "total_gap": float(allocation_df["gap_to_target"].sum()),
                "cash_used_ratio": (
                    float(allocation_df["est_value"].sum()) / settings.cash
                    if settings.cash > 0
                    else np.nan
                ),
                "secondary_fill_enabled": fill_stats["secondary_fill_enabled"],
                "secondary_fill_steps": fill_stats["secondary_fill_steps"],
                "secondary_fill_spent": fill_stats["secondary_fill_spent"],
                "secondary_fill_fee_spent": fill_stats["secondary_fill_fee_spent"],
                "secondary_fill_cash_buffer": fill_stats["secondary_fill_cash_buffer"],
                "secondary_fill_budget_after_buffer": fill_stats["secondary_fill_budget_after_buffer"],
                "cash_remaining_after_fill": fill_stats["cash_remaining_after_fill"],
            }
        ]
    )
    return allocation_df, summary_df


def build_sell_signals(
    *,
    settings: HkAllocSettings,
    tickers: Sequence[SelectedTicker],
    market_data: MarketDataBundle,
) -> pd.DataFrame:
    symbols, order_book_ids, symbol_to_oid = _build_order_book_mapping(tickers)
    instruments_df, _, _, close_pre = _subset_market_data(market_data, order_book_ids)
    if close_pre.empty:
        raise SystemExit("No historical HK price data returned; cannot build sell signals.")

    percentile, zscore, q_high, q_extreme = compute_valuation_metrics(
        close_pre,
        window=settings.roll_window,
        sell_quantile=settings.sell_quantile,
        extreme_quantile=settings.extreme_quantile,
    )

    sell_trigger = q_high.shift(1)
    extreme_trigger = q_extreme.shift(1)
    signal = (close_pre >= sell_trigger) & (close_pre.shift(1) < sell_trigger)
    latest_row = close_pre.index.max()

    rows: list[dict[str, Any]] = []
    for item in tickers:
        symbol = item.symbol
        oid = symbol_to_oid[symbol]
        instrument_symbol = None
        if oid in instruments_df.index and "symbol" in instruments_df.columns:
            instrument_symbol = _coerce_scalar(instruments_df.loc[oid, "symbol"])

        col_signal = signal[oid].fillna(False)
        signal_dates = col_signal.index[col_signal]
        last_signal_date = signal_dates.max() if len(signal_dates) > 0 else pd.NaT

        current_price = safe_float(close_pre.loc[latest_row, oid]) if oid in close_pre.columns else np.nan
        pct = safe_float(percentile.loc[latest_row, oid]) if oid in percentile.columns else np.nan
        z_1y = safe_float(zscore.loc[latest_row, oid]) if oid in zscore.columns else np.nan
        high_line = safe_float(sell_trigger.loc[latest_row, oid]) if oid in sell_trigger.columns else np.nan
        extreme_line = safe_float(extreme_trigger.loc[latest_row, oid]) if oid in extreme_trigger.columns else np.nan

        rows.append(
            {
                "symbol": symbol,
                "ts_code": symbol,
                "stock_ticker": symbol,
                "name": item.name or (str(instrument_symbol).strip() if instrument_symbol else None),
                "side": item.side,
                "rank": item.rank,
                "signal": item.signal,
                "weight": item.weight,
                "order_book_id": oid,
                "as_of": _to_date(latest_row),
                "close_pre": current_price,
                "pct_1y": pct,
                "z_1y": z_1y,
                "sell_trigger": high_line,
                "extreme_trigger": extreme_line,
                "last_sell_signal_date": _to_date(last_signal_date) if pd.notna(last_signal_date) else None,
                "valuation": classify_valuation(
                    pct,
                    z_1y,
                    sell_quantile=settings.sell_quantile,
                    extreme_quantile=settings.extreme_quantile,
                ),
            }
        )

    return pd.DataFrame(rows)


def _to_yes_no(value: Any) -> str:
    if isinstance(value, bool):
        return "是" if value else "否"
    if _is_missing_value(value):
        return "否"
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "是"}:
        return "是"
    if text in {"false", "0", "no", "n", "否"}:
        return "否"
    return str(value)


def _format_stock_connect(value: Any) -> str:
    if isinstance(value, (list, tuple, set)):
        tokens = {str(item).strip().lower() for item in value if not _is_missing_value(item)}
        if "sh" in tokens and "sz" in tokens:
            return "沪/深"
        if "sh" in tokens:
            return "沪"
        if "sz" in tokens:
            return "深"
        return "是" if len(tokens) > 0 else "否"
    return "是" if _is_stock_connect_tradable(value) else "否"


def _localize_price_source(value: Any) -> str:
    text = str(value).strip() if not _is_missing_value(value) else ""
    return PRICE_SOURCE_CN_MAP.get(text, text or "未知")


def _localize_side(value: Any) -> str:
    text = str(value).strip().lower() if not _is_missing_value(value) else ""
    return SIDE_CN_MAP.get(text, text or "")


def _localize_allocation_method(value: Any) -> str:
    text = str(value).strip().lower() if not _is_missing_value(value) else ""
    return ALLOCATION_METHOD_CN_MAP.get(text, text or "")


def _prepare_allocation_export_df(allocation_df: pd.DataFrame) -> pd.DataFrame:
    out = allocation_df.copy()
    if "tradable" in out.columns:
        out["tradable"] = out["tradable"].map(_to_yes_no)
    if "stock_connect" in out.columns:
        out["stock_connect"] = out["stock_connect"].map(_format_stock_connect)
    if "valuation" in out.columns:
        out["valuation"] = out["valuation"].map(lambda x: VALUATION_CN_MAP.get(str(x), str(x)))
    if "price_source" in out.columns:
        out["price_source"] = out["price_source"].map(_localize_price_source)
    if "side" in out.columns:
        out["side"] = out["side"].map(_localize_side)

    ordered_cols = [col for col in ALLOCATION_EXPORT_ORDER if col in out.columns]
    extra_cols = [col for col in out.columns if col not in ordered_cols]
    out = out[ordered_cols + extra_cols]
    return out.rename(columns=ALLOCATION_EXPORT_RENAME)


def _prepare_summary_export_df(summary_df: pd.DataFrame) -> pd.DataFrame:
    out = summary_df.copy()
    if "pricing_source" in out.columns:
        out["pricing_source"] = out["pricing_source"].map(_localize_price_source)
    if "secondary_fill_enabled" in out.columns:
        out["secondary_fill_enabled"] = out["secondary_fill_enabled"].map(_to_yes_no)
    if "require_stock_connect" in out.columns:
        out["require_stock_connect"] = out["require_stock_connect"].map(_to_yes_no)
    if "allocation_method" in out.columns:
        out["allocation_method"] = out["allocation_method"].map(_localize_allocation_method)

    ordered_cols = [col for col in SUMMARY_EXPORT_ORDER if col in out.columns]
    extra_cols = [col for col in out.columns if col not in ordered_cols]
    out = out[ordered_cols + extra_cols]
    return out.rename(columns=SUMMARY_EXPORT_RENAME)


def _prepare_sell_signals_export_df(sell_signals_df: pd.DataFrame) -> pd.DataFrame:
    out = sell_signals_df.copy()
    if "valuation" in out.columns:
        out["valuation"] = out["valuation"].map(lambda x: VALUATION_CN_MAP.get(str(x), str(x)))
    if "side" in out.columns:
        out["side"] = out["side"].map(_localize_side)

    ordered_cols = [col for col in SELL_SIGNALS_EXPORT_ORDER if col in out.columns]
    extra_cols = [col for col in out.columns if col not in ordered_cols]
    out = out[ordered_cols + extra_cols]
    return out.rename(columns=SELL_SIGNALS_EXPORT_RENAME)


def _import_openpyxl() -> Any:
    try:
        return importlib.import_module("openpyxl")
    except ImportError as exc:
        raise SystemExit(
            "openpyxl is required for --format xlsx. Install with: uv sync --extra liveops-hk"
        ) from exc


def _make_unique_sheet_name(raw_name: str, existing: set[str]) -> str:
    safe = re.sub(r"[:\\\\/?*\\[\\]]", "_", str(raw_name)).strip()
    safe = safe or "Sheet"
    safe = safe[:31]
    if safe not in existing:
        existing.add(safe)
        return safe

    base = safe
    counter = 2
    while True:
        suffix = f"_{counter}"
        candidate = f"{base[: max(31 - len(suffix), 1)]}{suffix}"
        if candidate not in existing:
            existing.add(candidate)
            return candidate
        counter += 1


def write_xlsx_report(
    output_path: Path,
    allocation_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    sell_signals_df: pd.DataFrame,
) -> Path:
    _import_openpyxl()
    allocation_export = _prepare_allocation_export_df(allocation_df)
    summary_export = _prepare_summary_export_df(summary_df)
    sell_signals_export = _prepare_sell_signals_export_df(sell_signals_df)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        allocation_export.to_excel(writer, sheet_name="分配", index=False)
        summary_export.to_excel(writer, sheet_name="汇总", index=False)
        sell_signals_export.to_excel(writer, sheet_name="卖出信号", index=False)
    return output_path


def write_scenario_grid_report(
    output_path: Path,
    scenario_reports: Sequence[ScenarioReport],
) -> Path:
    if len(scenario_reports) == 0:
        raise SystemExit("scenario_reports must not be empty.")

    _import_openpyxl()
    overview_df = pd.concat([item.summary_df for item in scenario_reports], ignore_index=True)
    overview_export = _prepare_summary_export_df(overview_df)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    used_sheet_names: set[str] = set()
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        overview_sheet = _make_unique_sheet_name("场景总览", used_sheet_names)
        overview_export.to_excel(writer, sheet_name=overview_sheet, index=False)

        for report in scenario_reports:
            allocation_export = _prepare_allocation_export_df(report.allocation_df)
            summary_export = _prepare_summary_export_df(report.summary_df)
            sell_signals_export = _prepare_sell_signals_export_df(report.sell_signals_df)

            allocation_sheet = _make_unique_sheet_name(f"{report.scenario_id}_分配", used_sheet_names)
            summary_sheet = _make_unique_sheet_name(f"{report.scenario_id}_汇总", used_sheet_names)
            sell_sheet = _make_unique_sheet_name(f"{report.scenario_id}_卖出", used_sheet_names)

            allocation_export.to_excel(writer, sheet_name=allocation_sheet, index=False)
            summary_export.to_excel(writer, sheet_name=summary_sheet, index=False)
            sell_signals_export.to_excel(writer, sheet_name=sell_sheet, index=False)
    return output_path


def _render_text(payload: dict[str, Any], allocation_df: pd.DataFrame) -> str:
    summary = payload["summary"]
    lines = [
        f"截至日期: {payload['as_of']}",
        f"建仓日期: {payload['entry_date']}",
        f"定价日期: {payload['pricing_date']}",
        f"来源: {payload['source']}",
        f"方向: {payload['side']}",
        f"Top-N 请求/实际: {payload['requested_top_n']} / {payload['selected_n']}",
        f"总资金: {base_alloc._money(float(payload['cash']))}",
        f"分配方式: {payload['allocation_method']}",
        f"港股通约束: {_to_yes_no(payload['require_stock_connect'])}",
        f"价格来源: {_localize_price_source(summary['pricing_source'])}",
        f"预计持仓金额: {base_alloc._money(float(summary['total_est_value']))}",
        f"目标缺口合计: {base_alloc._money(float(summary['total_gap']))}",
        f"补仓后剩余现金: {base_alloc._money(float(summary['cash_remaining_after_fill']))}",
    ]
    if payload.get("run_dir"):
        lines.append(f"运行目录: {payload['run_dir']}")
    if payload.get("positions_file"):
        lines.append(f"持仓文件: {payload['positions_file']}")
    lines.append("")

    table_headers = [
        "stock_ticker",
        "lots",
        "价格",
        "估值分层",
        "港股通",
        "目标金额",
        "预计金额",
        "目标缺口",
    ]
    table_rows: list[list[str]] = []
    for _, row in allocation_df.iterrows():
        table_rows.append(
            [
                str(row["stock_ticker"]),
                str(int(row["lots"])),
                f"{float(row['price']):.4f}" if pd.notna(row["price"]) else "nan",
                VALUATION_CN_MAP.get(str(row["valuation"]), str(row["valuation"])),
                _format_stock_connect(row.get("stock_connect")),
                base_alloc._money(float(row["target_value"])),
                base_alloc._money(float(row["est_value"])),
                base_alloc._money(float(row["gap_to_target"])),
            ]
        )
    lines.append(base_alloc._format_table(table_rows, table_headers))
    return "\n".join(lines)


def _render_grid_text(root_payload: dict[str, Any], overview_df: pd.DataFrame) -> str:
    lines = [
        f"截至日期: {root_payload['as_of']}",
        f"建仓日期: {root_payload['entry_date']}",
        f"来源: {root_payload['source']}",
        f"方向: {root_payload['side']}",
        f"场景数量: {len(root_payload['scenarios'])}",
        f"资金列表: {', '.join(base_alloc._money(float(value)) for value in root_payload['scenario_capitals'])}",
        f"Top-N 列表: {', '.join(str(value) for value in root_payload['scenario_top_ns'])}",
    ]
    if root_payload.get("run_dir"):
        lines.append(f"运行目录: {root_payload['run_dir']}")
    if root_payload.get("positions_file"):
        lines.append(f"持仓文件: {root_payload['positions_file']}")
    lines.append("")

    table_headers = [
        "场景",
        "资金",
        "Top-N",
        "价格来源",
        "预计持仓金额",
        "目标缺口",
        "剩余现金",
    ]
    table_rows: list[list[str]] = []
    for _, row in overview_df.iterrows():
        table_rows.append(
            [
                str(row.get("scenario_id", "")),
                base_alloc._money(float(row["total_capital"])),
                str(int(row["scenario_top_n"])),
                _localize_price_source(row.get("pricing_source")),
                base_alloc._money(float(row["total_est_value"])),
                base_alloc._money(float(row["total_gap"])),
                base_alloc._money(float(row["cash_remaining_after_fill"])),
            ]
        )
    lines.append(base_alloc._format_table(table_rows, table_headers))
    return "\n".join(lines)


def _format_capital_tag(capital: float) -> str:
    if float(capital).is_integer() and int(capital) % 10_000 == 0:
        return f"{int(capital) // 10_000}w"
    if float(capital).is_integer():
        return str(int(capital))
    return str(capital).replace(".", "p")


def _build_scenario_id(capital: float, top_n: int) -> str:
    return f"C{_format_capital_tag(capital)}_N{int(top_n)}"


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
    summary = summary_df.iloc[0].to_dict()
    payload = {
        "as_of": as_of.strftime("%Y-%m-%d"),
        "entry_date": entry_date.strftime("%Y-%m-%d"),
        "pricing_date": str(summary["pricing_date"]),
        "source": source,
        "side": side,
        "run_dir": str(run_dir) if run_dir is not None else None,
        "positions_file": str(positions_path) if positions_path is not None else None,
        "market": market,
        "requested_top_n": int(requested_top_n),
        "selected_n": int(len(allocation_df)),
        "cash": float(settings.cash),
        "allocation_method": settings.method,
        "require_stock_connect": bool(settings.require_stock_connect),
        "pricing_source": summary["pricing_source"],
        "pricing_source_detail": summary["pricing_source_detail"],
        "estimated_value": float(summary["total_est_value"]),
        "cash_left": float(summary["cash_remaining_after_fill"]),
        "total_gap_to_target": float(summary["total_gap"]),
        "summary": summary,
        "allocations": allocation_df.to_dict(orient="records"),
        "sell_signals": sell_signals_df.to_dict(orient="records"),
    }
    if scenario_id is not None:
        payload["scenario_id"] = scenario_id
    if scenario_cash is not None:
        payload["scenario_capital"] = float(scenario_cash)
    if scenario_top_n is not None:
        payload["scenario_top_n"] = int(scenario_top_n)
    return payload


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute HK pre-trade lot sizing and valuation diagnostics from latest holdings.",
    )
    parser.add_argument("--config", help="Pipeline config path or built-in name (default: default).")
    parser.add_argument("--run-dir", help="Explicit run directory to read (overrides --config).")
    parser.add_argument("--positions-file", help="Explicit positions CSV path (overrides --config/--run-dir).")
    parser.add_argument("--top-k", type=int, help="Optional Top-K filter when selecting the latest run.")
    parser.add_argument(
        "--as-of",
        default="t-1",
        help=(
            "As-of date (YYYYMMDD, YYYY-MM-DD, today, t-1, last_trading_day, "
            "last_completed_trading_day). Default: t-1."
        ),
    )
    parser.add_argument(
        "--source",
        default="auto",
        choices=["auto", "backtest", "live"],
        help="Positions source (auto/backtest/live). Default: auto.",
    )
    parser.add_argument(
        "--side",
        default="long",
        choices=["long", "short", "all"],
        help="Select side for allocation (long/short/all). Default: long.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="Number of names to allocate from sorted holdings. Default: 20.",
    )
    parser.add_argument(
        "--scenario-capital",
        action="append",
        default=None,
        help="Scenario capital list (repeatable, supports comma-separated values).",
    )
    parser.add_argument(
        "--scenario-top-n",
        action="append",
        default=None,
        help="Scenario Top-N list (repeatable, supports comma-separated values).",
    )
    parser.add_argument("--cash", type=float, help="Total portfolio cash for sizing. Overrides live.alloc_hk.cash.")
    parser.add_argument(
        "--method",
        choices=["equal", "custom"],
        help="Sizing method. custom uses holdings weight. Overrides live.alloc_hk.method.",
    )
    parser.add_argument(
        "--require-stock-connect",
        dest="require_stock_connect",
        action="store_true",
        default=None,
        help="Require stock_connect eligibility for tradable names.",
    )
    parser.add_argument(
        "--allow-non-stock-connect",
        dest="require_stock_connect",
        action="store_false",
        help="Allow non-stock-connect names to remain tradable.",
    )
    parser.add_argument("--history-years", type=int, help="Lookback years for valuation history.")
    parser.add_argument("--roll-window", type=int, help="Rolling window used for valuation thresholds.")
    parser.add_argument("--sell-quantile", type=float, help="Quantile used for HIGH valuation threshold.")
    parser.add_argument("--extreme-quantile", type=float, help="Quantile used for EXTREME valuation threshold.")
    parser.add_argument(
        "--secondary-fill",
        dest="secondary_fill_enabled",
        action="store_true",
        default=None,
        help="Enable secondary fill after base lot sizing.",
    )
    parser.add_argument(
        "--no-secondary-fill",
        dest="secondary_fill_enabled",
        action="store_false",
        help="Disable secondary fill after base lot sizing.",
    )
    parser.add_argument(
        "--avoid-high-valuation",
        dest="avoid_high_valuation",
        action="store_true",
        default=None,
        help="Prefer LOW/NEUTRAL names first during secondary fill.",
    )
    parser.add_argument(
        "--allow-high-valuation",
        dest="avoid_high_valuation",
        action="store_false",
        help="Do not prefer LOW/NEUTRAL names during secondary fill.",
    )
    parser.add_argument(
        "--avoid-high-valuation-strict",
        dest="avoid_high_valuation_strict",
        action="store_true",
        default=None,
        help="Hard-block HIGH/EXTREME names during secondary fill.",
    )
    parser.add_argument(
        "--allow-over-alloc",
        dest="allow_over_alloc",
        action="store_true",
        default=None,
        help="Allow bounded over-allocation during secondary fill.",
    )
    parser.add_argument("--max-steps", type=int, help="Maximum secondary fill steps.")
    parser.add_argument("--max-over-alloc-ratio", type=float, help="Over-allocation cap as a ratio of cash.")
    parser.add_argument("--max-over-alloc-amount", type=float, help="Over-allocation cap as an absolute amount.")
    parser.add_argument(
        "--max-over-alloc-lots-per-ticker",
        type=int,
        help="Per-ticker cap for over-allocation lots.",
    )
    parser.add_argument("--cash-buffer-ratio", type=float, help="Cash buffer ratio reserved before fill.")
    parser.add_argument("--cash-buffer-amount", type=float, help="Cash buffer amount reserved before fill.")
    parser.add_argument(
        "--estimated-fee-per-order",
        type=float,
        help="Estimated fee added to each secondary fill step.",
    )
    parser.add_argument("--username", help="Override RQData username.")
    parser.add_argument("--password", help="Override RQData password.")
    parser.add_argument(
        "--format",
        default="text",
        choices=["text", "csv", "json", "xlsx"],
        help="Output format (text/csv/json/xlsx). Default: text.",
    )
    parser.add_argument("--out", help="Optional output path (default: stdout; required for xlsx).")
    args = parser.parse_args(argv)

    if args.top_n <= 0:
        raise SystemExit("--top-n must be a positive integer.")
    return args


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    cfg, settings = _resolve_settings(args)
    scenario_capitals, scenario_top_ns = _resolve_scenarios(args, cfg=cfg, settings=settings)
    prepared, entry_date, as_of, source, run_dir, positions_path, payload_market = _load_selection(
        args,
        cfg=cfg,
        selection_top_n=max(scenario_top_ns),
    )
    tickers = _selection_to_tickers(prepared)
    if not tickers:
        raise SystemExit("No holdings selected for allocation.")

    market = base_alloc._resolve_market(cfg, [item.symbol for item in tickers]) or payload_market or "hk"
    market = "hk" if market is None else str(market).lower()
    if market != "hk":
        raise SystemExit(f"alloc-hk currently only supports HK holdings. Resolved market={market!r}.")

    rqdatac = base_alloc._init_rqdatac(args.config, args.username, args.password)
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
