from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from ..pipeline.quality import enforce_liveops_quality_gate
from . import holdings
from .alloc_selection import load_holdings_payload

TARGET_CONTRACT = "quant-execution-engine.targets/v2"
KNOWN_MARKETS = {"HK", "US", "CN", "SG"}
MARKET_SUFFIXES = {
    ".HK": "HK",
    ".XHKG": "HK",
    ".US": "US",
    ".CN": "CN",
    ".SH": "CN",
    ".SZ": "CN",
    ".BJ": "CN",
    ".XSHG": "CN",
    ".XSHE": "CN",
    ".SG": "SG",
}


def _output_path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


def _market_code(value: object | None) -> str | None:
    text = str(value or "").strip().upper()
    if not text:
        return None
    aliases = {"A_SHARE": "CN", "ASHARE": "CN", "CN_A": "CN"}
    text = aliases.get(text, text)
    if text not in KNOWN_MARKETS:
        raise SystemExit(f"Unsupported execution target market: {value!r}.")
    return text


def _broker_symbol(base_symbol: str, market: str) -> str:
    if market == "HK" and base_symbol.isdigit():
        return base_symbol.lstrip("0") or "0"
    return base_symbol


def _execution_suffix(symbol_text: str, suffix: str, market: str) -> str:
    base = symbol_text[: -len(suffix)]
    if market == "CN" and suffix in {".SH", ".SZ", ".BJ", ".XSHG", ".XSHE"}:
        mapped_suffix = {".XSHG": ".SH", ".XSHE": ".SZ"}.get(suffix, suffix)
        return f"{base.zfill(6)}{mapped_suffix}"
    return _broker_symbol(base, market)


def _execution_symbol(symbol: object, market: object | None) -> tuple[str, str]:
    text = str(symbol or "").strip().upper()
    if not text:
        raise SystemExit("Execution target symbol cannot be empty.")
    requested_market = _market_code(market)
    for suffix, suffix_market in MARKET_SUFFIXES.items():
        if text.endswith(suffix):
            base = text[: -len(suffix)]
            if requested_market and requested_market != suffix_market:
                raise SystemExit(
                    f"Execution target symbol {text!r} conflicts with market {requested_market!r}."
                )
            return _execution_suffix(text, suffix, suffix_market), suffix_market
    if requested_market is None:
        raise SystemExit(f"Cannot infer execution target market for symbol {text!r}.")
    return _broker_symbol(text, requested_market), requested_market


def _target_entries(payload: dict[str, Any]) -> tuple[list[dict[str, object]], float, str]:
    rows = payload.get("holdings")
    if not isinstance(rows, list) or not rows:
        raise SystemExit("Invalid holdings payload: missing non-empty holdings list.")
    selection = pd.DataFrame(rows)
    if "symbol" not in selection.columns:
        raise SystemExit("Invalid holdings payload: missing symbol column.")
    if "weight" not in selection.columns:
        raise SystemExit("Invalid holdings payload: missing weight column.")

    sides = set(selection.get("side", pd.Series(["long"] * len(selection))).astype(str).str.lower())
    unsupported_sides = sorted(side for side in sides if side != "long")
    if unsupported_sides:
        raise SystemExit(
            "export-targets only supports long-only holdings because qexec targets "
            f"are non-negative positions; found side(s): {', '.join(unsupported_sides)}."
        )

    weights = pd.to_numeric(selection["weight"], errors="coerce")
    if weights.isna().any() or any(not math.isfinite(float(value)) for value in weights):
        raise SystemExit("Execution targets require finite numeric weights for every holding.")
    if (weights < 0).any():
        raise SystemExit("Execution targets require non-negative weights.")
    weight_sum = float(weights.sum())
    if weight_sum <= 0:
        raise SystemExit("Execution target weights must sum to a positive value.")
    if weight_sum > 1.0 + 1e-8:
        raise SystemExit(
            "Execution target weights cannot sum above 1.0; use --target-gross-exposure "
            "for explicit exposure scaling."
        )

    default_market = payload.get("market")
    targets: list[dict[str, object]] = []
    keys: set[tuple[str, str]] = set()
    for row_index, (_, row) in enumerate(selection.iterrows()):
        symbol, market = _execution_symbol(row["symbol"], default_market)
        key = (symbol, market)
        if key in keys:
            raise SystemExit(f"Duplicate execution target for {symbol}.{market}.")
        keys.add(key)
        targets.append(
            {
                "symbol": symbol,
                "market": market,
                "target_weight": float(weights.iloc[row_index]),
            }
        )
    markets = sorted({str(target["market"]) for target in targets})
    return targets, weight_sum, ",".join(markets)


def _lineage_payload(
    *,
    holdings_payload: dict[str, Any],
    targets_path: Path,
    target_source: str,
    target_gross_exposure: float,
    weight_sum: float,
    target_count: int,
    markets: str,
    run_dir: Path,
    fail_on_quality: str | None,
) -> dict[str, object]:
    upstream_files: dict[str, str] = {}
    for name in ("summary.json", "config.used.yml", "inputs.lock.json"):
        candidate = run_dir / name
        if candidate.exists():
            upstream_files[name] = str(candidate)
    return {
        "schema_version": 1,
        "artifact_type": "cstree.execution_targets_lineage",
        "target_contract": TARGET_CONTRACT,
        "targets_file": str(targets_path),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_source": target_source,
        "target_gross_exposure": target_gross_exposure,
        "selection": {
            "as_of": holdings_payload.get("as_of"),
            "entry_date": holdings_payload.get("entry_date"),
            "signal_asof": holdings_payload.get("signal_asof"),
            "data_end_date": holdings_payload.get("data_end_date"),
            "market": markets,
            "source": holdings_payload.get("source"),
            "run_dir": str(run_dir),
            "positions_file": holdings_payload.get("positions_file"),
            "target_count": target_count,
            "weight_sum": weight_sum,
        },
        "quality_gate": {
            "checked": True,
            "fail_on_quality_override": fail_on_quality,
        },
        "upstream_files": upstream_files,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export canonical qexec targets JSON from saved live holdings.",
    )
    parser.add_argument("--config", help="Pipeline config path or built-in name.")
    parser.add_argument("--run-dir", help="Explicit saved run directory to read (overrides --config).")
    parser.add_argument(
        "--artifacts-root",
        help="Optional artifacts root override used when resolving the default runs directory.",
    )
    parser.add_argument("--top-k", type=int, help="Optional Top-K filter when selecting the latest run.")
    parser.add_argument(
        "--as-of",
        default="t-1",
        help="As-of date used to select live holdings. Default: t-1.",
    )
    parser.add_argument(
        "--target-source",
        default="cross-sectional-trees",
        help="Source label written to qexec targets JSON. Default: cross-sectional-trees.",
    )
    parser.add_argument(
        "--target-gross-exposure",
        type=float,
        default=1.0,
        help="Target exposure multiplier passed to qexec. Default: 1.0.",
    )
    parser.add_argument(
        "--fail-on-quality",
        choices=["none", "info", "warning", "error"],
        default=None,
        help="Optional quality threshold applied before exporting live targets.",
    )
    parser.add_argument("--out", required=True, help="Output path for canonical targets JSON.")
    parser.add_argument(
        "--lineage-out",
        help="Optional lineage sidecar output path. Default: <out>.lineage.json.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    if not args.config and not args.run_dir:
        raise SystemExit("export-targets requires --config or --run-dir.")
    if args.target_gross_exposure < 0 or not math.isfinite(args.target_gross_exposure):
        raise SystemExit("--target-gross-exposure must be finite and non-negative.")

    run_dir = holdings._resolve_run_dir(
        args.config,
        args.run_dir,
        args.top_k,
        artifacts_root=args.artifacts_root,
    )
    enforce_liveops_quality_gate(
        command_name="export-targets",
        run_dir=run_dir,
        config_ref=args.config,
        fail_on_quality=args.fail_on_quality,
    )
    holdings_args = argparse.Namespace(
        config=None,
        run_dir=str(run_dir),
        artifacts_root=None,
        top_k=args.top_k,
        as_of=args.as_of,
        source="live",
    )
    payload = load_holdings_payload(holdings_args)
    targets, weight_sum, markets = _target_entries(payload)

    targets_path = _output_path(args.out)
    lineage_path = (
        _output_path(args.lineage_out)
        if args.lineage_out
        else targets_path.with_suffix(f"{targets_path.suffix}.lineage.json")
    )
    if targets_path == lineage_path:
        raise SystemExit("--lineage-out must not overwrite --out.")
    targets_payload = {
        "asof": payload.get("as_of"),
        "source": args.target_source,
        "target_gross_exposure": float(args.target_gross_exposure),
        "targets": targets,
    }
    lineage = _lineage_payload(
        holdings_payload=payload,
        targets_path=targets_path,
        target_source=args.target_source,
        target_gross_exposure=float(args.target_gross_exposure),
        weight_sum=weight_sum,
        target_count=len(targets),
        markets=markets,
        run_dir=run_dir,
        fail_on_quality=args.fail_on_quality,
    )
    targets_path.parent.mkdir(parents=True, exist_ok=True)
    lineage_path.parent.mkdir(parents=True, exist_ok=True)
    targets_path.write_text(json.dumps(targets_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lineage_path.write_text(json.dumps(lineage, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {targets_path}")
    print(f"Wrote {lineage_path}")


if __name__ == "__main__":
    main()
