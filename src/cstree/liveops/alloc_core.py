from __future__ import annotations

import argparse
import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from ..config_utils import resolve_pipeline_config
from market_data_platform.data_providers import normalize_market, resolve_provider
from market_data_platform.rqdata_runtime import (
    init_rqdatac as _init_rqdatac_runtime,
    patch_rqdatac_adjust_price_readonly as _patch_rqdatac_adjust_price_readonly,
)
from . import holdings
from .alloc_market_data import (
    extract_price_wide_frame as _extract_price_wide_frame_impl,
    fetch_latest_price_map as _fetch_latest_price_map_impl,
    fetch_round_lot_map as _fetch_round_lot_map_impl,
    resolve_price_date as _resolve_price_date_impl,
    to_rq_order_book_id as _to_rq_order_book_id_impl,
)
from .alloc_rendering import (
    display_width as _display_width_impl,
    format_table as _format_table_impl,
    ljust_display as _ljust_display_impl,
    money as _money_impl,
    render_text as _render_text_impl,
)
from .alloc_selection import (
    load_holdings_payload as _load_holdings_payload_impl,
    prepare_selection as _prepare_selection_impl,
    select_from_positions_file as _select_from_positions_file_impl,
)


@dataclass(frozen=True)
class _AllocationSelection:
    selection: pd.DataFrame
    entry_date: pd.Timestamp
    as_of: pd.Timestamp
    source: str
    payload_market: str | None
    run_dir: Path | None
    positions_path: Path | None


def _load_config(path: str | None) -> dict:
    if not path:
        return {}
    resolved = resolve_pipeline_config(path)
    return resolved.data


def _init_rqdatac(
    config_path: str | None,
    username: str | None,
    password: str | None,
):
    load_dotenv()
    cfg = _load_config(config_path)
    data_cfg = cfg.get("data") if isinstance(cfg, dict) else None
    return _init_rqdatac_runtime(
        data_cfg=data_cfg,
        username=username,
        password=password,
        logger=logging.getLogger("cstree.liveops.alloc"),
        load_env=False,
        error_cls=SystemExit,
        import_error_message="rqdatac is not installed. Install with: pip install '.[rqdata]'",
        patch_fn=_patch_rqdatac_adjust_price_readonly,
    )


def _resolve_market(cfg: dict, symbols: list[str]) -> str | None:
    data_cfg = cfg.get("data") if isinstance(cfg, dict) else None
    data_cfg = data_cfg if isinstance(data_cfg, dict) else {}
    rq_cfg = data_cfg.get("rqdata") if isinstance(data_cfg, dict) else None

    rq_market = rq_cfg.get("market") if isinstance(rq_cfg, dict) else None
    if rq_market:
        return normalize_market(rq_market, default=None)
    cfg_market = cfg.get("market") if isinstance(cfg, dict) else None
    if cfg_market:
        return normalize_market(cfg_market, default=None)
    data_market = data_cfg.get("market") if isinstance(data_cfg, dict) else None
    if data_market:
        return normalize_market(data_market, default=None)

    inferred: set[str] = set()
    for symbol in symbols:
        text = str(symbol or "").strip().upper()
        if text.endswith(".HK") or text.endswith(".XHKG"):
            inferred.add("hk")
    if len(inferred) == 1:
        return next(iter(inferred))
    return None


def _resolve_provider(cfg: dict) -> str | None:
    data_cfg = cfg.get("data") if isinstance(cfg, dict) else None
    data_cfg = data_cfg if isinstance(data_cfg, dict) else {}
    return resolve_provider(data_cfg, default=None)


def _to_rq_order_book_id(symbol: str, market: str | None) -> str:
    return _to_rq_order_book_id_impl(symbol, market)


def _resolve_price_date(rqdatac, as_of: pd.Timestamp, market: str | None) -> pd.Timestamp:
    return _resolve_price_date_impl(rqdatac, as_of, market)


def _extract_price_wide_frame(
    payload,
    field: str,
    order_book_ids: list[str],
) -> pd.DataFrame:
    return _extract_price_wide_frame_impl(payload, field, order_book_ids)


def _fetch_latest_price_map(
    rqdatac,
    order_book_ids: list[str],
    *,
    field: str,
    start_date: str,
    end_date: str,
    market: str | None,
) -> dict[str, float]:
    return _fetch_latest_price_map_impl(
        rqdatac,
        order_book_ids,
        field=field,
        start_date=start_date,
        end_date=end_date,
        market=market,
    )


def _fetch_round_lot_map(
    rqdatac,
    order_book_ids: list[str],
    market: str | None,
) -> dict[str, int]:
    return _fetch_round_lot_map_impl(rqdatac, order_book_ids, market)


def _display_width(text: str) -> int:
    return _display_width_impl(text)


def _ljust_display(text: str, width: int) -> str:
    return _ljust_display_impl(text, width)


def _format_table(rows: list[list[str]], headers: list[str]) -> str:
    return _format_table_impl(rows, headers)


def _money(value: float) -> str:
    return _money_impl(value)


def _select_from_positions_file(
    positions_path: Path,
    as_of: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.Timestamp]:
    return _select_from_positions_file_impl(
        positions_path,
        as_of,
        resolve_market_fn=_resolve_market,
    )


def _load_holdings_payload(args) -> dict:
    return _load_holdings_payload_impl(args)


def _prepare_selection(
    selection: pd.DataFrame,
    *,
    side: str,
    top_n: int,
) -> pd.DataFrame:
    return _prepare_selection_impl(
        selection,
        side=side,
        top_n=top_n,
        resolve_market_fn=_resolve_market,
    )


def _allocate_equal_weight(
    selection: pd.DataFrame,
    *,
    cash: float,
    buffer_bps: float,
    symbol_to_order_book_id: dict[str, str],
    price_map: dict[str, float],
    lot_map: dict[str, int],
) -> tuple[pd.DataFrame, float, float, float]:
    if selection.empty:
        raise SystemExit("No holdings selected for allocation.")
    investable_cash = float(cash) * max(0.0, 1.0 - float(buffer_bps) / 10000.0)
    target_value = investable_cash / float(len(selection))

    rows: list[dict] = []
    for _, row in selection.iterrows():
        symbol = str(row["symbol"])
        order_book_id = symbol_to_order_book_id[symbol]
        price = float(price_map[order_book_id])
        round_lot = max(1, int(lot_map.get(order_book_id, 1)))
        lot_cost = price * round_lot
        lots = 0 if lot_cost <= 0 else int(math.floor(target_value / lot_cost))
        shares = lots * round_lot
        est_value = shares * price
        rank_value = row.get("rank")
        rows.append(
            {
                "symbol": symbol,
                "order_book_id": order_book_id,
                "side": str(row.get("side", "long")),
                "rank": int(rank_value) if pd.notna(rank_value) else None,
                "price": price,
                "round_lot": round_lot,
                "target_value": target_value,
                "lot_cost": lot_cost,
                "lots": lots,
                "shares": shares,
                "est_value": est_value,
            }
        )

    alloc_df = pd.DataFrame(rows)
    alloc_df["gap_to_target"] = alloc_df["target_value"] - alloc_df["est_value"]
    est_total = float(alloc_df["est_value"].sum())
    cash_left = investable_cash - est_total
    return alloc_df, investable_cash, est_total, cash_left


def _render_text(payload: dict, alloc_df: pd.DataFrame) -> str:
    return _render_text_impl(payload, alloc_df)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Size equal-weight holdings into shares/lots using rqdata prices and round_lot."
    )
    parser.add_argument(
        "--config",
        help="Pipeline config path or built-in name (default: default).",
    )
    parser.add_argument(
        "--run-dir",
        help="Explicit run directory to read (overrides --config).",
    )
    parser.add_argument(
        "--artifacts-root",
        help=(
            "Optional artifacts root override used when resolving the default runs directory. "
            "When omitted, alloc uses CSTREE_ARTIFACTS_ROOT, "
            "paths.artifacts_root, or artifacts/."
        ),
    )
    parser.add_argument(
        "--positions-file",
        help="Explicit positions CSV path (overrides --config/--run-dir).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        help="Optional Top-K filter when selecting the latest run.",
    )
    parser.add_argument(
        "--as-of",
        default="t-1",
        help="As-of date (YYYYMMDD, YYYY-MM-DD, today, t-1). Default: t-1.",
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
        help="Number of names to allocate equally from the sorted holdings list. Default: 20.",
    )
    parser.add_argument(
        "--cash",
        type=float,
        default=1_000_000,
        help="Total portfolio cash for sizing. Default: 1000000.",
    )
    parser.add_argument(
        "--buffer-bps",
        type=float,
        default=0.0,
        help="Cash buffer in bps reserved from investment (e.g., fees). Default: 0.",
    )
    parser.add_argument(
        "--price-field",
        default="close",
        help="Price field fetched from rqdata.get_price. Default: close.",
    )
    parser.add_argument(
        "--price-lookback-days",
        type=int,
        default=20,
        help="Price lookback window in calendar days before price date. Default: 20.",
    )
    parser.add_argument(
        "--username",
        help="Override RQData username.",
    )
    parser.add_argument(
        "--password",
        help="Override RQData password.",
    )
    parser.add_argument(
        "--format",
        default="text",
        choices=["text", "csv", "json"],
        help="Output format (text/csv/json). Default: text.",
    )
    parser.add_argument(
        "--out",
        help="Optional output path (default: stdout).",
    )
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    if args.top_n <= 0:
        raise SystemExit("--top-n must be a positive integer.")
    if args.cash <= 0:
        raise SystemExit("--cash must be positive.")
    if args.buffer_bps < 0:
        raise SystemExit("--buffer-bps must be non-negative.")
    if args.price_lookback_days <= 0:
        raise SystemExit("--price-lookback-days must be a positive integer.")


def _load_selection_from_positions_file(
    args: argparse.Namespace,
    *,
    cfg_market: str | None,
    cfg_provider: str | None,
) -> _AllocationSelection:
    as_of = holdings._resolve_as_of(
        args.as_of,
        market=cfg_market,
        provider=cfg_provider,
    )
    positions_path = Path(args.positions_file).expanduser()
    if not positions_path.is_absolute():
        positions_path = (Path.cwd() / positions_path).resolve()
    selection, entry_date = _select_from_positions_file(positions_path, as_of)
    return _AllocationSelection(
        selection=selection,
        entry_date=entry_date,
        as_of=as_of,
        source="positions_file",
        payload_market=None,
        run_dir=None,
        positions_path=positions_path,
    )


def _load_selection_from_holdings_payload(
    args: argparse.Namespace,
    *,
    cfg_market: str | None,
    cfg_provider: str | None,
) -> _AllocationSelection:
    payload = _load_holdings_payload(args)
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
    positions_value = payload.get("positions_file")
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
    return _AllocationSelection(
        selection=selection,
        entry_date=entry_date,
        as_of=as_of,
        source=str(payload.get("source") or args.source),
        payload_market=payload_market,
        run_dir=Path(str(run_value)) if run_value else None,
        positions_path=Path(str(positions_value)) if positions_value else None,
    )


def _load_allocation_selection(
    args: argparse.Namespace,
    *,
    cfg_market: str | None,
    cfg_provider: str | None,
) -> _AllocationSelection:
    if args.positions_file:
        return _load_selection_from_positions_file(
            args,
            cfg_market=cfg_market,
            cfg_provider=cfg_provider,
        )
    return _load_selection_from_holdings_payload(
        args,
        cfg_market=cfg_market,
        cfg_provider=cfg_provider,
    )


def _write_allocation_output(args: argparse.Namespace, content: str) -> None:
    if not args.out:
        print(content)
        return
    out_path = Path(args.out).expanduser()
    if not out_path.is_absolute():
        out_path = (Path.cwd() / out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    print(f"Wrote {out_path}")


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _validate_args(args)

    cfg = _load_config(args.config)
    cfg_provider = _resolve_provider(cfg)
    cfg_market = _resolve_market(cfg, [])
    selection_state = _load_allocation_selection(
        args,
        cfg_market=cfg_market,
        cfg_provider=cfg_provider,
    )

    prepared = _prepare_selection(selection_state.selection, side=args.side, top_n=args.top_n)
    symbols = [str(value) for value in prepared["symbol"].tolist()]
    market = _resolve_market(cfg, symbols) or selection_state.payload_market

    rqdatac = _init_rqdatac(args.config, args.username, args.password)
    price_date = _resolve_price_date(rqdatac, selection_state.as_of, market)
    start_date = (price_date - pd.Timedelta(days=int(args.price_lookback_days))).strftime(
        "%Y%m%d"
    )
    end_date = price_date.strftime("%Y%m%d")

    symbol_to_order_book_id: dict[str, str] = {}
    order_book_ids: list[str] = []
    for symbol in symbols:
        order_book_id = _to_rq_order_book_id(symbol, market)
        symbol_to_order_book_id[symbol] = order_book_id
        if order_book_id not in order_book_ids:
            order_book_ids.append(order_book_id)

    price_map = _fetch_latest_price_map(
        rqdatac,
        order_book_ids,
        field=args.price_field,
        start_date=start_date,
        end_date=end_date,
        market=market,
    )
    lot_map = _fetch_round_lot_map(rqdatac, order_book_ids, market)

    alloc_df, investable_cash, est_total, cash_left = _allocate_equal_weight(
        prepared,
        cash=float(args.cash),
        buffer_bps=float(args.buffer_bps),
        symbol_to_order_book_id=symbol_to_order_book_id,
        price_map=price_map,
        lot_map=lot_map,
    )
    total_gap_to_target = float(alloc_df["gap_to_target"].sum())

    payload = {
        "as_of": selection_state.as_of.strftime("%Y-%m-%d"),
        "entry_date": selection_state.entry_date.strftime("%Y-%m-%d"),
        "price_date": price_date.strftime("%Y-%m-%d"),
        "source": selection_state.source,
        "side": args.side,
        "run_dir": str(selection_state.run_dir) if selection_state.run_dir is not None else None,
        "positions_file": (
            str(selection_state.positions_path)
            if selection_state.positions_path is not None
            else None
        ),
        "market": market,
        "requested_top_n": int(args.top_n),
        "selected_n": int(len(alloc_df)),
        "equal_weight": 1.0 / float(len(alloc_df)),
        "cash": float(args.cash),
        "buffer_bps": float(args.buffer_bps),
        "investable_cash": float(investable_cash),
        "estimated_value": float(est_total),
        "cash_left": float(cash_left),
        "total_gap_to_target": total_gap_to_target,
        "price_field": args.price_field,
        "allocations": alloc_df.to_dict(orient="records"),
    }

    if args.format == "text":
        content = _render_text(payload, alloc_df)
    elif args.format == "csv":
        content = alloc_df.to_csv(index=False)
    else:
        content = json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    _write_allocation_output(args, content)


if __name__ == "__main__":
    main()
