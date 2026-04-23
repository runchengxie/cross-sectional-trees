from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from ..data_tools.symbols import canonicalize_symbol_columns, ensure_symbol_columns, normalize_symbol_for_market
from . import holdings


def select_from_positions_file(
    positions_path: Path,
    as_of: pd.Timestamp,
    *,
    resolve_market_fn: Callable[[dict, list[str]], str | None],
) -> tuple[pd.DataFrame, pd.Timestamp]:
    if not positions_path.exists():
        raise SystemExit(f"Positions file not found: {positions_path}")
    df = pd.read_csv(positions_path)
    if df.empty:
        raise SystemExit(f"{positions_path.name} is empty.")
    if "entry_date" not in df.columns:
        raise SystemExit(f"{positions_path.name} is missing entry_date.")
    entry_dates = holdings._parse_date_column(df["entry_date"])
    if entry_dates.isna().all():
        raise SystemExit("Failed to parse entry_date column.")
    eligible = entry_dates <= as_of
    if not eligible.any():
        raise SystemExit("No holdings available before the requested --as-of date.")
    latest_entry = entry_dates[eligible].max()
    selection = df[entry_dates == latest_entry].copy()
    selection = ensure_symbol_columns(selection, context=positions_path.name)
    selection_market = resolve_market_fn({}, selection["symbol"].tolist())
    selection["symbol"] = selection["symbol"].map(
        lambda value: normalize_symbol_for_market(value, market=selection_market)
    )
    if selection.empty:
        raise SystemExit("No holdings found for the latest entry date.")
    return selection, latest_entry


def load_holdings_payload(args) -> dict:
    argv: list[str] = ["--as-of", args.as_of, "--source", args.source, "--format", "json"]
    if args.config:
        argv += ["--config", args.config]
    if args.run_dir:
        argv += ["--run-dir", args.run_dir]
    if getattr(args, "artifacts_root", None):
        argv += ["--artifacts-root", args.artifacts_root]
    if args.top_k is not None:
        argv += ["--top-k", str(args.top_k)]

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        holdings.main(argv)
    raw = buffer.getvalue().strip()
    if not raw:
        raise SystemExit("Failed to read holdings output.")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Failed to parse holdings output: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("Unexpected holdings output payload.")
    return payload


def prepare_selection(
    selection: pd.DataFrame,
    *,
    side: str,
    top_n: int,
    resolve_market_fn: Callable[[dict, list[str]], str | None],
) -> pd.DataFrame:
    prepared = canonicalize_symbol_columns(
        selection,
        context="Holdings payload",
        drop_order_book_id=True,
    )
    prepared_market = resolve_market_fn({}, prepared["symbol"].tolist())
    prepared["symbol"] = prepared["symbol"].map(
        lambda value: normalize_symbol_for_market(value, market=prepared_market)
    )
    if "side" not in prepared.columns:
        prepared["side"] = "long"
    if "rank" not in prepared.columns:
        prepared["rank"] = np.nan
    prepared["side"] = prepared["side"].astype(str).str.lower()
    if side != "all":
        prepared = prepared[prepared["side"] == side].copy()
    if prepared.empty:
        raise SystemExit(f"No holdings available for --side={side}.")
    prepared.sort_values(["side", "rank", "symbol"], inplace=True, na_position="last")
    prepared = prepared.head(top_n).copy()
    if prepared.empty:
        raise SystemExit("No holdings available after --top-n filtering.")
    prepared.reset_index(drop=True, inplace=True)
    return prepared
