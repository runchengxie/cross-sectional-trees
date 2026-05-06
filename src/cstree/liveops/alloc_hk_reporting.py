from __future__ import annotations

import importlib
import re
from pathlib import Path
from typing import Any, Callable, Sequence

import pandas as pd

from . import alloc as base_alloc
from .alloc_hk_types import HkAllocSettings, ScenarioReport

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
    "symbol",
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
    "symbol": "股票代码",
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
    "execution_calendar",
    "execution_check_date",
    "execution_open",
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
    "execution_calendar": "执行日历",
    "execution_check_date": "执行日历检查日",
    "execution_open": "执行日历开放",
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
    "symbol",
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
    "symbol": "股票代码",
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


def to_yes_no(value: Any, *, is_missing_value_fn: Callable[[Any], bool]) -> str:
    if isinstance(value, bool):
        return "是" if value else "否"
    if is_missing_value_fn(value):
        return "否"
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "是"}:
        return "是"
    if text in {"false", "0", "no", "n", "否"}:
        return "否"
    return str(value)


def format_stock_connect(
    value: Any,
    *,
    is_missing_value_fn: Callable[[Any], bool],
    is_stock_connect_tradable_fn: Callable[[Any], bool],
) -> str:
    if isinstance(value, (list, tuple, set)):
        tokens = {str(item).strip().lower() for item in value if not is_missing_value_fn(item)}
        if "sh" in tokens and "sz" in tokens:
            return "沪/深"
        if "sh" in tokens:
            return "沪"
        if "sz" in tokens:
            return "深"
        return "是" if len(tokens) > 0 else "否"
    return "是" if is_stock_connect_tradable_fn(value) else "否"


def localize_price_source(value: Any, *, is_missing_value_fn: Callable[[Any], bool]) -> str:
    text = str(value).strip() if not is_missing_value_fn(value) else ""
    return PRICE_SOURCE_CN_MAP.get(text, text or "未知")


def localize_side(value: Any, *, is_missing_value_fn: Callable[[Any], bool]) -> str:
    text = str(value).strip().lower() if not is_missing_value_fn(value) else ""
    return SIDE_CN_MAP.get(text, text or "")


def localize_allocation_method(value: Any, *, is_missing_value_fn: Callable[[Any], bool]) -> str:
    text = str(value).strip().lower() if not is_missing_value_fn(value) else ""
    return ALLOCATION_METHOD_CN_MAP.get(text, text or "")


def prepare_allocation_export_df(
    allocation_df: pd.DataFrame,
    *,
    to_yes_no_fn: Callable[[Any], str],
    format_stock_connect_fn: Callable[[Any], str],
    localize_price_source_fn: Callable[[Any], str],
    localize_side_fn: Callable[[Any], str],
) -> pd.DataFrame:
    out = allocation_df.copy()
    if "tradable" in out.columns:
        out["tradable"] = out["tradable"].map(to_yes_no_fn)
    if "stock_connect" in out.columns:
        out["stock_connect"] = out["stock_connect"].map(format_stock_connect_fn)
    if "valuation" in out.columns:
        out["valuation"] = out["valuation"].map(lambda x: VALUATION_CN_MAP.get(str(x), str(x)))
    if "price_source" in out.columns:
        out["price_source"] = out["price_source"].map(localize_price_source_fn)
    if "side" in out.columns:
        out["side"] = out["side"].map(localize_side_fn)

    ordered_cols = [col for col in ALLOCATION_EXPORT_ORDER if col in out.columns]
    extra_cols = [col for col in out.columns if col not in ordered_cols]
    out = out[ordered_cols + extra_cols]
    return out.rename(columns=ALLOCATION_EXPORT_RENAME)


def prepare_summary_export_df(
    summary_df: pd.DataFrame,
    *,
    to_yes_no_fn: Callable[[Any], str],
    localize_price_source_fn: Callable[[Any], str],
    localize_allocation_method_fn: Callable[[Any], str],
) -> pd.DataFrame:
    out = summary_df.copy()
    if "pricing_source" in out.columns:
        out["pricing_source"] = out["pricing_source"].map(localize_price_source_fn)
    if "secondary_fill_enabled" in out.columns:
        out["secondary_fill_enabled"] = out["secondary_fill_enabled"].map(to_yes_no_fn)
    if "require_stock_connect" in out.columns:
        out["require_stock_connect"] = out["require_stock_connect"].map(to_yes_no_fn)
    if "execution_open" in out.columns:
        out["execution_open"] = out["execution_open"].map(to_yes_no_fn)
    if "allocation_method" in out.columns:
        out["allocation_method"] = out["allocation_method"].map(localize_allocation_method_fn)

    ordered_cols = [col for col in SUMMARY_EXPORT_ORDER if col in out.columns]
    extra_cols = [col for col in out.columns if col not in ordered_cols]
    out = out[ordered_cols + extra_cols]
    return out.rename(columns=SUMMARY_EXPORT_RENAME)


def prepare_sell_signals_export_df(
    sell_signals_df: pd.DataFrame,
    *,
    localize_side_fn: Callable[[Any], str],
) -> pd.DataFrame:
    out = sell_signals_df.copy()
    if "valuation" in out.columns:
        out["valuation"] = out["valuation"].map(lambda x: VALUATION_CN_MAP.get(str(x), str(x)))
    if "side" in out.columns:
        out["side"] = out["side"].map(localize_side_fn)

    ordered_cols = [col for col in SELL_SIGNALS_EXPORT_ORDER if col in out.columns]
    extra_cols = [col for col in out.columns if col not in ordered_cols]
    out = out[ordered_cols + extra_cols]
    return out.rename(columns=SELL_SIGNALS_EXPORT_RENAME)


def import_openpyxl() -> Any:
    try:
        return importlib.import_module("openpyxl")
    except ImportError as exc:
        raise SystemExit(
            "openpyxl is required for --format xlsx. Install with: uv sync --extra liveops-hk"
        ) from exc


def make_unique_sheet_name(raw_name: str, existing: set[str]) -> str:
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
    *,
    import_openpyxl_fn: Callable[[], Any],
    prepare_allocation_export_df_fn: Callable[[pd.DataFrame], pd.DataFrame],
    prepare_summary_export_df_fn: Callable[[pd.DataFrame], pd.DataFrame],
    prepare_sell_signals_export_df_fn: Callable[[pd.DataFrame], pd.DataFrame],
) -> Path:
    import_openpyxl_fn()
    allocation_export = prepare_allocation_export_df_fn(allocation_df)
    summary_export = prepare_summary_export_df_fn(summary_df)
    sell_signals_export = prepare_sell_signals_export_df_fn(sell_signals_df)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        allocation_export.to_excel(writer, sheet_name="分配", index=False)
        summary_export.to_excel(writer, sheet_name="汇总", index=False)
        sell_signals_export.to_excel(writer, sheet_name="卖出信号", index=False)
    return output_path


def write_scenario_grid_report(
    output_path: Path,
    scenario_reports: Sequence[ScenarioReport],
    *,
    import_openpyxl_fn: Callable[[], Any],
    prepare_allocation_export_df_fn: Callable[[pd.DataFrame], pd.DataFrame],
    prepare_summary_export_df_fn: Callable[[pd.DataFrame], pd.DataFrame],
    prepare_sell_signals_export_df_fn: Callable[[pd.DataFrame], pd.DataFrame],
) -> Path:
    if len(scenario_reports) == 0:
        raise SystemExit("scenario_reports must not be empty.")

    import_openpyxl_fn()
    overview_df = pd.concat([item.summary_df for item in scenario_reports], ignore_index=True)
    overview_export = prepare_summary_export_df_fn(overview_df)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    used_sheet_names: set[str] = set()
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        overview_sheet = make_unique_sheet_name("场景总览", used_sheet_names)
        overview_export.to_excel(writer, sheet_name=overview_sheet, index=False)

        for report in scenario_reports:
            allocation_export = prepare_allocation_export_df_fn(report.allocation_df)
            summary_export = prepare_summary_export_df_fn(report.summary_df)
            sell_signals_export = prepare_sell_signals_export_df_fn(report.sell_signals_df)

            allocation_sheet = make_unique_sheet_name(f"{report.scenario_id}_分配", used_sheet_names)
            summary_sheet = make_unique_sheet_name(f"{report.scenario_id}_汇总", used_sheet_names)
            sell_sheet = make_unique_sheet_name(f"{report.scenario_id}_卖出", used_sheet_names)

            allocation_export.to_excel(writer, sheet_name=allocation_sheet, index=False)
            summary_export.to_excel(writer, sheet_name=summary_sheet, index=False)
            sell_signals_export.to_excel(writer, sheet_name=sell_sheet, index=False)
    return output_path


def render_text(
    payload: dict[str, Any],
    allocation_df: pd.DataFrame,
    *,
    to_yes_no_fn: Callable[[Any], str],
    format_stock_connect_fn: Callable[[Any], str],
    localize_price_source_fn: Callable[[Any], str],
) -> str:
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
        f"港股通约束: {to_yes_no_fn(payload['require_stock_connect'])}",
        f"执行日历: {payload['execution_calendar']}",
        f"价格来源: {localize_price_source_fn(summary['pricing_source'])}",
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
        "symbol",
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
                str(row["symbol"]),
                str(int(row["lots"])),
                f"{float(row['price']):.4f}" if pd.notna(row["price"]) else "nan",
                VALUATION_CN_MAP.get(str(row["valuation"]), str(row["valuation"])),
                format_stock_connect_fn(row.get("stock_connect")),
                base_alloc._money(float(row["target_value"])),
                base_alloc._money(float(row["est_value"])),
                base_alloc._money(float(row["gap_to_target"])),
            ]
        )
    lines.append(base_alloc._format_table(table_rows, table_headers))
    return "\n".join(lines)


def render_grid_text(
    root_payload: dict[str, Any],
    overview_df: pd.DataFrame,
    *,
    localize_price_source_fn: Callable[[Any], str],
) -> str:
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
                localize_price_source_fn(row.get("pricing_source")),
                base_alloc._money(float(row["total_est_value"])),
                base_alloc._money(float(row["total_gap"])),
                base_alloc._money(float(row["cash_remaining_after_fill"])),
            ]
        )
    lines.append(base_alloc._format_table(table_rows, table_headers))
    return "\n".join(lines)


def format_capital_tag(capital: float) -> str:
    if float(capital).is_integer() and int(capital) % 10_000 == 0:
        return f"{int(capital) // 10_000}w"
    if float(capital).is_integer():
        return str(int(capital))
    return str(capital).replace(".", "p")


def build_scenario_id(capital: float, top_n: int) -> str:
    return f"C{format_capital_tag(capital)}_N{int(top_n)}"


def build_payload(
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
        "execution_calendar": settings.execution_calendar,
        "allow_connect_closed": bool(settings.allow_connect_closed),
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
