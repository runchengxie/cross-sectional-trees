#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from csml.repo_paths import find_repo_root, resolve_repo_path as resolve_repo_relative_path


REPO_ROOT = find_repo_root(__file__)
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "cache" / "intraday"
DEFAULT_FIELDS = ("open", "high", "low", "close", "volume", "total_turnover")


def resolve_repo_path(path_text: str | Path) -> Path:
    return resolve_repo_relative_path(path_text, repo_root=REPO_ROOT)


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _to_rq_order_book_id(symbol: str) -> str:
    text = str(symbol or "").strip().upper()
    if not text:
        return text
    if text.endswith(".XHKG"):
        return text
    if text.endswith(".XSHG") or text.endswith(".XSHE") or text.endswith(".SH") or text.endswith(".SZ"):
        raise SystemExit(
            f"Unsupported symbol '{symbol}'. This script currently supports only HK symbols."
        )
    if text.endswith(".HK"):
        text = text[:-3]
    if text.isdigit():
        text = text.zfill(5)
    return f"{text}.XHKG"


def _read_symbol_file(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".list"}:
        values = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
        return [value for value in values if value]

    if suffix in {".csv", ".parquet"}:
        if suffix == ".parquet":
            frame = pd.read_parquet(path)
        else:
            frame = pd.read_csv(path)
        for candidate in ("ts_code", "symbol", "stock_ticker", "order_book_id"):
            if candidate in frame.columns:
                values = frame[candidate].astype(str).str.strip()
                return sorted(values[values.ne("")].unique().tolist())
        raise SystemExit(
            f"Unsupported symbol file schema: {path}. Expected one of ts_code/symbol/stock_ticker/order_book_id."
        )

    raise SystemExit(f"Unsupported symbol file format: {path}")


def normalize_hk_symbols(symbols: list[str]) -> list[str]:
    mapped = [_to_rq_order_book_id(symbol) for symbol in symbols]
    return sorted(dict.fromkeys(mapped))


def flatten_intraday_payload(
    payload: pd.DataFrame,
    *,
    order_book_to_ts_code: dict[str, str],
) -> pd.DataFrame:
    if payload.empty:
        return pd.DataFrame(
            columns=[
                "rq_order_book_id",
                "trade_datetime",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "amount",
                "ts_code",
            ]
        )
    if not isinstance(payload.index, pd.MultiIndex):
        raise SystemExit("Expected rqdatac.get_price(..., frequency='5m') to return a MultiIndex DataFrame.")

    frame = payload.reset_index()
    order_book_col = "order_book_id" if "order_book_id" in frame.columns else frame.columns[0]
    datetime_col = "datetime" if "datetime" in frame.columns else frame.columns[1]
    rename_map = {
        order_book_col: "rq_order_book_id",
        datetime_col: "trade_datetime",
        "total_turnover": "amount",
    }
    frame = frame.rename(columns=rename_map)
    frame["trade_datetime"] = pd.to_datetime(frame["trade_datetime"], errors="coerce")
    frame = frame.dropna(subset=["trade_datetime", "rq_order_book_id"]).copy()
    frame["rq_order_book_id"] = frame["rq_order_book_id"].astype(str).str.upper()
    frame["ts_code"] = frame["rq_order_book_id"].map(order_book_to_ts_code)
    keep = [
        "rq_order_book_id",
        "trade_datetime",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "ts_code",
    ]
    for column in keep:
        if column not in frame.columns:
            frame[column] = pd.NA
    return frame[keep].sort_values(["rq_order_book_id", "trade_datetime"]).reset_index(drop=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download HK intraday bars from RQData and save a flat parquet cache."
    )
    parser.add_argument("--symbols-file", required=True, help="TXT/CSV/Parquet file containing HK symbols.")
    parser.add_argument("--start-date", required=True, help="Start date, e.g. 20250327.")
    parser.add_argument("--end-date", required=True, help="End date, e.g. 20260326.")
    parser.add_argument("--frequency", default="5m", help="Intraday frequency. Default: 5m.")
    parser.add_argument(
        "--fields",
        nargs="+",
        default=list(DEFAULT_FIELDS),
        help="RQData fields. Default: open high low close volume total_turnover.",
    )
    parser.add_argument("--batch-size", type=int, default=100, help="Symbols per get_price call.")
    parser.add_argument(
        "--output",
        required=True,
        help="Output parquet path. Relative paths resolve from repo root.",
    )
    parser.add_argument(
        "--meta-output",
        help="Optional metadata JSON path. Defaults to <output>.meta.json beside the parquet.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        import rqdatac
    except ImportError as exc:
        raise SystemExit("rqdatac is required. Install with: uv sync --extra rqdata") from exc

    rqdatac.init()

    symbol_file = resolve_repo_path(args.symbols_file)
    if not symbol_file.exists():
        raise SystemExit(f"Symbol file not found: {symbol_file}")

    symbols = _read_symbol_file(symbol_file)
    if not symbols:
        raise SystemExit(f"No symbols found in: {symbol_file}")

    order_book_ids = normalize_hk_symbols(symbols)
    order_book_to_ts_code = {
        order_book_id: symbol
        for symbol, order_book_id in zip(
            symbols,
            [_to_rq_order_book_id(symbol) for symbol in symbols],
            strict=False,
        )
    }

    output_path = resolve_repo_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path = (
        resolve_repo_path(args.meta_output)
        if args.meta_output
        else output_path.with_suffix(".meta.json")
    )
    meta_path.parent.mkdir(parents=True, exist_ok=True)

    quota_before = rqdatac.user.get_quota()
    chunks: list[pd.DataFrame] = []
    batch_rows: list[dict[str, int | str]] = []
    total = len(order_book_ids)
    for start in range(0, total, int(args.batch_size)):
        batch = order_book_ids[start : start + int(args.batch_size)]
        payload = rqdatac.get_price(
            batch,
            args.start_date,
            args.end_date,
            frequency=args.frequency,
            fields=list(args.fields),
            market="hk",
            expect_df=True,
        )
        frame = flatten_intraday_payload(payload, order_book_to_ts_code=order_book_to_ts_code)
        if not frame.empty:
            chunks.append(frame)
        batch_rows.append(
            {
                "batch": start // int(args.batch_size) + 1,
                "symbols": len(batch),
                "rows": int(len(frame)),
            }
        )
        print(
            f"batch {start // int(args.batch_size) + 1}: "
            f"{start + len(batch)}/{total} symbols, {len(frame)} rows"
        )

    if chunks:
        result = pd.concat(chunks, ignore_index=True)
        result = result.sort_values(["rq_order_book_id", "trade_datetime"]).reset_index(drop=True)
    else:
        result = flatten_intraday_payload(
            pd.DataFrame(),
            order_book_to_ts_code=order_book_to_ts_code,
        )

    result.to_parquet(output_path, index=False)
    quota_after = rqdatac.user.get_quota()

    meta = {
        "dataset": "hk_intraday_cache",
        "symbols_file": _display_path(symbol_file),
        "symbols_requested": int(len(symbols)),
        "symbols_downloaded": int(result["rq_order_book_id"].nunique()) if not result.empty else 0,
        "start_date": str(args.start_date),
        "end_date": str(args.end_date),
        "frequency": str(args.frequency),
        "fields": list(args.fields),
        "rows": int(len(result)),
        "columns": list(result.columns),
        "quota_before": quota_before,
        "quota_after": quota_after,
        "bytes_used_delta": float(quota_after["bytes_used"] - quota_before["bytes_used"]),
        "file_size_bytes": int(output_path.stat().st_size),
        "batches": batch_rows,
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"saved parquet: {output_path}")
    print(f"saved meta: {meta_path}")
    print(f"rows={len(result)} quota_delta={meta['bytes_used_delta']}")


if __name__ == "__main__":
    main()
