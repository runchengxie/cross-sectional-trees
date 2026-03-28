from __future__ import annotations

from pathlib import Path

from .fetch_runtime import _ensure_rqdatac_hk_plugin
from .mirror_workflow import _mirror_dataset
from .package_api import _package_attr
from .request_groups import _default_hk_instruments_out_path, _resolve_instrument_symbol_filter
from .shared import (
    _git_metadata,
    _load_hk_financial_fields as _load_hk_financial_fields_shared,
    _normalize_frame_columns,
    _normalize_hk_symbol,
    _resolve_path,
    _timestamp_now,
    _write_manifest,
)


def _load_hk_financial_fields() -> list[str]:
    loader = _package_attr(
        "_load_hk_financial_fields",
        default=_load_hk_financial_fields_shared,
    )
    return loader()


def list_hk_financial_fields(args) -> int:
    fields = _load_hk_financial_fields()
    contains = [
        str(item).strip().lower()
        for item in (getattr(args, "contains", None) or [])
        if str(item).strip()
    ]
    if contains:
        fields = [
            field for field in fields if all(token in field.lower() for token in contains)
        ]
    limit = getattr(args, "limit", None)
    if limit is not None:
        if limit <= 0:
            raise SystemExit("--limit must be > 0.")
        fields = fields[:limit]

    output = "\n".join(fields)
    if output:
        output += "\n"
    out = getattr(args, "out", None)
    if out:
        out_path = _resolve_path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(f"Wrote {len(fields)} HK financial fields to {out_path}")
    else:
        print(output, end="")
    return 0


def export_hk_instruments(args, rqdatac) -> int:
    _ensure_rqdatac_hk_plugin()
    symbol_filter, symbol_metadata = _resolve_instrument_symbol_filter(args)
    try:
        frame = rqdatac.all_instruments("CS", market="hk")
    except TypeError:
        frame = rqdatac.all_instruments("CS")
    if frame is None or frame.empty:
        raise SystemExit("rqdatac.all_instruments returned no HK instruments.")

    instruments = _normalize_frame_columns(frame.copy())
    if "order_book_id" not in instruments.columns:
        raise SystemExit("HK instruments payload is missing order_book_id.")
    instruments["order_book_id"] = instruments["order_book_id"].astype(str).str.strip()
    instruments["ts_code"] = instruments["order_book_id"].map(_normalize_hk_symbol)
    instruments = instruments[instruments["ts_code"] != ""].copy()

    if symbol_filter is not None:
        instruments = instruments[instruments["ts_code"].isin(symbol_filter)].copy()
    elif getattr(args, "limit", None) is not None:
        instruments = (
            instruments.sort_values(["ts_code", "order_book_id"], kind="mergesort")
            .head(args.limit)
            .copy()
        )

    if instruments.empty:
        raise SystemExit("No HK instruments matched the requested filter.")

    preferred_columns = [
        column
        for column in (
            "ts_code",
            "order_book_id",
            "symbol",
            "name",
            "listed_date",
            "de_listed_date",
            "round_lot",
            "board_type",
            "status",
        )
        if column in instruments.columns
    ]
    remaining_columns = [
        column for column in instruments.columns if column not in preferred_columns
    ]
    instruments = instruments[preferred_columns + remaining_columns].copy()
    instruments.sort_values(["ts_code", "order_book_id"], kind="mergesort", inplace=True)
    instruments.reset_index(drop=True, inplace=True)

    out_arg = getattr(args, "out", None)
    out_path = _resolve_path(out_arg) if out_arg else _default_hk_instruments_out_path()
    if not out_path.suffix:
        out_path = out_path.with_suffix(".parquet")
    if out_path.exists() and not getattr(args, "force", False):
        raise SystemExit(f"Refusing to overwrite existing output: {out_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.suffix.lower() == ".csv":
        instruments.to_csv(out_path, index=False)
    else:
        instruments.to_parquet(out_path, index=False)

    manifest_path = Path(f"{out_path}.manifest.yml")
    symbol_metadata = dict(symbol_metadata)
    symbol_metadata["count"] = int(instruments["ts_code"].nunique())
    manifest = {
        "name": out_path.stem,
        "created_at": _timestamp_now(),
        "dataset": "hk_instruments",
        "api": "rqdatac.all_instruments",
        "market": "hk",
        "config_ref": getattr(args, "config", None),
        "output_file": str(out_path),
        "format": out_path.suffix.lstrip(".").lower(),
        "symbol_source": symbol_metadata,
        "columns": instruments.columns.tolist(),
        "totals": {
            "rows": int(len(instruments)),
            "symbols": int(instruments["ts_code"].nunique()),
            "round_lot_nonnull": int(instruments["round_lot"].notna().sum())
            if "round_lot" in instruments.columns
            else 0,
        },
        "git": _git_metadata(Path.cwd().resolve()),
    }
    _write_manifest(manifest_path, manifest)
    print(
        f"Wrote {len(instruments)} HK instruments to {out_path} "
        f"(manifest: {manifest_path})"
    )
    return 0


def mirror_hk_pit_financials(args, rqdatac) -> int:
    return _mirror_dataset(
        args=args,
        rqdatac=rqdatac,
        dataset_name="pit_financials",
        api_name="rqdatac.get_pit_financials_ex",
        fetch_batch=lambda order_book_ids, fields, start_quarter, end_quarter, **kwargs: rqdatac.get_pit_financials_ex(
            order_book_ids=order_book_ids,
            fields=list(fields),
            start_quarter=start_quarter,
            end_quarter=end_quarter,
            market="hk",
            **kwargs,
        ),
    )


def mirror_hk_financial_details(args, rqdatac) -> int:
    _ensure_rqdatac_hk_plugin()
    hk_api = getattr(rqdatac, "hk", None)
    if hk_api is None or not hasattr(hk_api, "get_detailed_financial_items"):
        raise SystemExit(
            "rqdatac.hk.get_detailed_financial_items is unavailable. Check rqdatac-hk installation."
        )
    return _mirror_dataset(
        args=args,
        rqdatac=rqdatac,
        dataset_name="financial_details",
        api_name="rqdatac.hk.get_detailed_financial_items",
        fetch_batch=lambda order_book_ids, fields, start_quarter, end_quarter, **kwargs: hk_api.get_detailed_financial_items(
            order_book_ids=order_book_ids,
            fields=list(fields),
            start_quarter=start_quarter,
            end_quarter=end_quarter,
            market="hk",
            **kwargs,
        ),
    )
