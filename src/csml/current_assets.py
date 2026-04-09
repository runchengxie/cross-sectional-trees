from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


HK_CURRENT_CONTRACT_RELATIVE_PATH = Path("metadata") / "current_assets" / "hk_current.json"
HK_CURRENT_PATH_SPECS = {
    "daily": ("assets", "rqdata", "hk", "daily", "hk_all_daily_latest"),
    "daily_clean": ("assets", "rqdata", "hk", "daily", "hk_all_daily_clean_latest"),
    "intraday": ("assets", "rqdata", "hk", "intraday", "hk_intraday_latest"),
    "etf_daily": ("assets", "rqdata", "hk", "daily", "hk_etf_daily_latest"),
    "etf_instruments": ("assets", "rqdata", "hk", "instruments", "hk_etf_instruments_latest.parquet"),
    "valuation": ("assets", "rqdata", "hk", "valuation", "hk_all_valuation_latest"),
    "instruments": ("assets", "rqdata", "hk", "instruments", "hk_all_instruments_latest.parquet"),
    "pit": ("assets", "rqdata", "hk", "pit_financials", "hk_all_2000_2025_full_market_latest"),
    "ex_factors": ("assets", "rqdata", "hk", "ex_factors", "hk_all_ex_factors_latest"),
    "dividends": ("assets", "rqdata", "hk", "dividends", "hk_all_dividends_latest"),
    "shares": ("assets", "rqdata", "hk", "shares", "hk_all_shares_latest"),
    "exchange_rate": ("assets", "rqdata", "hk", "exchange_rate", "hk_all_2000_20260319_exchange_rate_latest"),
    "southbound": ("assets", "rqdata", "hk", "southbound", "hk_connect_southbound_latest"),
    "financial_details": (
        "assets",
        "rqdata",
        "hk",
        "financial_details",
        "hk_financial_details_portable_bundle_20260324",
    ),
    "industry_changes": ("assets", "rqdata", "hk", "industry_changes", "hk_all_industry_changes_latest"),
    "universe_by_date": ("assets", "universe", "hk_all_full_by_date.csv"),
    "universe_symbols": ("assets", "universe", "hk_all_full_symbols.txt"),
    "universe_meta": ("assets", "universe", "hk_all_full_by_date.meta.yml"),
}


def default_hk_current_contract_path(artifacts_root: str | Path) -> Path:
    return Path(artifacts_root).expanduser().resolve() / HK_CURRENT_CONTRACT_RELATIVE_PATH


def hk_current_candidate_paths(artifacts_root: str | Path) -> dict[str, Path]:
    root = Path(artifacts_root).expanduser().resolve()
    return {
        asset_key: root.joinpath(*parts)
        for asset_key, parts in HK_CURRENT_PATH_SPECS.items()
    }


def infer_manifest_path(path: Path | None) -> Path | None:
    if path is None:
        return None
    candidates: list[Path] = []
    if path.is_dir():
        candidates.append(path / "manifest.yml")
    else:
        candidates.append(path.with_name(f"{path.stem}.manifest.yml"))
        candidates.append(path.parent / "manifest.yml")
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def load_manifest_summary(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        return None
    query = payload.get("query") if isinstance(payload.get("query"), Mapping) else {}
    output_dir = str(payload.get("output_dir") or "").strip()
    snapshot_name = Path(output_dir).name if output_dir else None
    query_end_date = None
    for key in ("end_date", "date", "mapping_date", "as_of_date"):
        value = query.get(key)
        if value is None:
            continue
        query_end_date = str(value).strip() or None
        if query_end_date:
            break
    return {
        "dataset": str(payload.get("dataset") or "").strip() or None,
        "status": str(payload.get("status") or "").strip() or None,
        "output_dir": output_dir or None,
        "snapshot_name": snapshot_name,
        "query_end_date": query_end_date,
    }


def _path_kind(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_dir():
        return "directory"
    if path.is_file():
        return "file"
    return "other"


def _detect_as_of(text: str | None) -> str | None:
    if not text:
        return None
    match = re.search(r"(\d{8})", str(text))
    return match.group(1) if match else None


def describe_current_path(path: Path) -> dict[str, Any]:
    alias_path = path.expanduser()
    if not alias_path.is_absolute():
        alias_path = alias_path.absolute()
    resolved_path = alias_path.resolve(strict=False)
    manifest_path = infer_manifest_path(alias_path)
    manifest = load_manifest_summary(manifest_path)
    as_of = None
    if isinstance(manifest, Mapping):
        as_of = str(manifest.get("query_end_date") or "").strip() or None
        if not as_of:
            as_of = _detect_as_of(manifest.get("snapshot_name"))
    if not as_of:
        as_of = _detect_as_of(resolved_path.name)
    return {
        "alias_path": str(alias_path),
        "exists": alias_path.exists(),
        "is_symlink": alias_path.is_symlink(),
        "path_kind": _path_kind(alias_path),
        "resolved_path": str(resolved_path),
        "resolved_name": resolved_path.name,
        "manifest_path": str(manifest_path) if manifest_path is not None else None,
        "manifest": manifest,
        "as_of": as_of,
    }


def build_hk_current_contract(
    artifacts_root: str | Path,
    *,
    generated_by: str | None = None,
    target_date: str | None = None,
) -> dict[str, Any]:
    artifacts_root_path = Path(artifacts_root).expanduser().resolve()
    contract_path = default_hk_current_contract_path(artifacts_root_path)
    return {
        "contract": {
            "name": "hk_current",
            "market": "hk",
            "version": 1,
            "artifacts_root": str(artifacts_root_path),
            "contract_path": str(contract_path),
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "generated_by": generated_by,
            "target_date": target_date,
        },
        "assets": {
            asset_key: describe_current_path(path)
            for asset_key, path in hk_current_candidate_paths(artifacts_root_path).items()
        },
    }


def write_current_contract(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def load_current_contract(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def current_contract_entry(contract: Mapping[str, Any] | None, asset_key: str) -> dict[str, Any] | None:
    if not isinstance(contract, Mapping):
        return None
    assets = contract.get("assets")
    if not isinstance(assets, Mapping):
        return None
    entry = assets.get(asset_key)
    return dict(entry) if isinstance(entry, Mapping) else None


def match_current_contract_entry(
    contract: Mapping[str, Any] | None,
    *,
    configured_path: Path | None,
    resolved_path: Path | None,
) -> tuple[str, dict[str, Any]] | None:
    if not isinstance(contract, Mapping):
        return None
    assets = contract.get("assets")
    if not isinstance(assets, Mapping):
        return None
    configured_text = str(configured_path) if configured_path is not None else None
    resolved_text = str(resolved_path) if resolved_path is not None else None
    for asset_key, entry in assets.items():
        if not isinstance(entry, Mapping):
            continue
        alias_path = str(entry.get("alias_path") or "").strip() or None
        contract_resolved = str(entry.get("resolved_path") or "").strip() or None
        if configured_text and alias_path and configured_text == alias_path:
            return str(asset_key), dict(entry)
        if resolved_text and contract_resolved and resolved_text == contract_resolved:
            return str(asset_key), dict(entry)
    return None
