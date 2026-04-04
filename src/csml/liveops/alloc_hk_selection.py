from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..data_tools.symbols import ensure_symbol_columns
from . import alloc as base_alloc
from . import holdings
from .alloc_hk_types import SelectedTicker


def selection_to_tickers(selection: pd.DataFrame) -> list[SelectedTicker]:
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


def load_selection(
    args,
    *,
    cfg: dict[str, object],
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
