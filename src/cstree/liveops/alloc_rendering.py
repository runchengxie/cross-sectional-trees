from __future__ import annotations

import unicodedata

import pandas as pd


def display_width(text: str) -> int:
    width = 0
    for char in text:
        if unicodedata.combining(char):
            continue
        if unicodedata.east_asian_width(char) in {"F", "W"}:
            width += 2
            continue
        width += 1
    return width


def ljust_display(text: str, width: int) -> str:
    return text + (" " * max(0, width - display_width(text)))


def format_table(rows: list[list[str]], headers: list[str]) -> str:
    widths = [display_width(header) for header in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], display_width(cell))
    header_line = "  ".join(ljust_display(header, widths[idx]) for idx, header in enumerate(headers))
    sep_line = "  ".join("-" * widths[idx] for idx in range(len(headers)))
    lines = [header_line, sep_line]
    for row in rows:
        lines.append("  ".join(ljust_display(row[idx], widths[idx]) for idx in range(len(headers))))
    return "\n".join(lines)


def money(value: float) -> str:
    return f"{value:,.2f}"


def render_text(payload: dict, alloc_df: pd.DataFrame) -> str:
    lines = [
        f"截至日期: {payload['as_of']}",
        f"建仓日期: {payload['entry_date']}",
        f"价格日期: {payload['price_date']}",
        f"来源: {payload['source']}",
        f"方向: {payload['side']}",
        f"Top-N 请求/实际: {payload['requested_top_n']} / {payload['selected_n']}",
        f"总资金: {money(float(payload['cash']))}",
        f"可投资资金: {money(float(payload['investable_cash']))}",
        f"预计持仓金额: {money(float(payload['estimated_value']))}",
        f"预计剩余现金: {money(float(payload['cash_left']))}",
        f"目标缺口合计: {money(float(payload['total_gap_to_target']))}",
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
        "每手股数",
        "目标金额",
        "股数",
        "预计金额",
        "目标缺口",
    ]
    table_rows: list[list[str]] = []
    for _, row in alloc_df.iterrows():
        table_rows.append(
            [
                str(row["symbol"]),
                str(int(row["lots"])),
                f"{float(row['price']):.4f}",
                str(int(row["round_lot"])),
                money(float(row["target_value"])),
                str(int(row["shares"])),
                money(float(row["est_value"])),
                money(float(row["gap_to_target"])),
            ]
        )
    lines.append(format_table(table_rows, table_headers))
    return "\n".join(lines)
