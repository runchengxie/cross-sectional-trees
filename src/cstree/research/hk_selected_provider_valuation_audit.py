#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from collections.abc import Mapping
from pathlib import Path

import pandas as pd
import yaml

from cstree.data_providers import (
    _cache_tag,
    _fundamentals_cache_file,
    normalize_market,
    resolve_provider,
)
from cstree.data_tools.symbols import drop_legacy_symbol_columns, ensure_symbol_columns
from cstree.rebalance import get_rebalance_dates
from cstree.repo_paths import find_repo_root, resolve_repo_path as resolve_repo_relative_path

REPO_ROOT = find_repo_root(__file__)
DEFAULT_REPORT_DIR = REPO_ROOT / "artifacts" / "reports"
VALUATION_COLUMNS = ("market_cap", "pe_ttm", "pb", "log_mcap")


def resolve_repo_path(path_text: str | Path) -> Path:
    return resolve_repo_relative_path(path_text, repo_root=REPO_ROOT)


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    return payload if isinstance(payload, dict) else {}


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def _read_frame(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    raise SystemExit(f"Unsupported file format: {path}")


def _normalize_trade_date(series: pd.Series) -> pd.Series:
    values = pd.to_datetime(series, errors="coerce")
    return values.dt.normalize()


def _normalize_symbol(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.upper()


def _normalize_symbol_frame(frame: pd.DataFrame, *, label: str) -> pd.DataFrame:
    frame = ensure_symbol_columns(frame, context=label).copy()
    frame["trade_date"] = _normalize_trade_date(frame["trade_date"])
    frame["symbol"] = _normalize_symbol(frame["symbol"])
    if "valuation_trade_date" in frame.columns:
        frame["valuation_trade_date"] = _normalize_trade_date(frame["valuation_trade_date"])
    frame = frame.dropna(subset=["trade_date", "symbol"])
    frame = frame.drop_duplicates(subset=["trade_date", "symbol"]).reset_index(drop=True)
    frame = drop_legacy_symbol_columns(frame)
    frame = frame.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    return frame


def _mapping_value(mapping: Mapping[str, object] | None, key: str) -> object:
    if not isinstance(mapping, Mapping):
        return None
    return mapping.get(key)


def load_run_metadata(run_dir: Path) -> tuple[dict, dict]:
    config_used = _load_yaml(run_dir / "config.used.yml")
    summary = _load_json(run_dir / "summary.json")
    if not config_used and not summary:
        raise SystemExit(f"Run directory does not contain config.used.yml or summary.json: {run_dir}")
    return config_used, summary


def resolve_scored_file(run_dir: Path, summary: dict, override: str | None) -> Path:
    if override:
        path = resolve_repo_path(override)
    else:
        eval_cfg = summary.get("eval")
        scored_ref = _mapping_value(eval_cfg, "scored_file")
        path = resolve_repo_path(str(scored_ref)) if scored_ref else (run_dir / "eval_scored.parquet").resolve()
    if not path.exists():
        raise SystemExit(f"Scored file not found: {path}")
    return path


def _resolve_provider_overlay_cache_dir(
    data_cfg: Mapping[str, object] | None,
    overlay_cfg: Mapping[str, object] | None,
    summary_overlay_cfg: Mapping[str, object] | None,
    market: str,
) -> Path:
    configured = _mapping_value(summary_overlay_cfg, "cache_dir")
    if configured:
        return resolve_repo_path(str(configured))
    configured = _mapping_value(overlay_cfg, "cache_dir")
    if configured:
        return resolve_repo_path(str(configured))
    base_dir = resolve_repo_path(str(_mapping_value(data_cfg, "cache_dir") or "artifacts/cache"))
    return base_dir / "fundamentals" / normalize_market(market)


def resolve_valuation_source(
    config_used: dict,
    summary: dict,
    override: str | None,
) -> tuple[str, object]:
    if override:
        fundamentals_path = resolve_repo_path(str(override))
        if not fundamentals_path.exists():
            raise SystemExit(f"Fundamentals file not found: {fundamentals_path}")
        return "file", fundamentals_path

    config_fundamentals = config_used.get("fundamentals")
    summary_fundamentals = summary.get("fundamentals")
    overlay_cfg = (
        _mapping_value(config_fundamentals, "provider_overlay")
        if isinstance(config_fundamentals, Mapping)
        else None
    )
    summary_overlay_cfg = (
        _mapping_value(summary_fundamentals, "provider_overlay")
        if isinstance(summary_fundamentals, Mapping)
        else None
    )
    overlay_enabled = bool(
        _mapping_value(overlay_cfg, "enabled")
        if _mapping_value(overlay_cfg, "enabled") is not None
        else _mapping_value(summary_overlay_cfg, "enabled")
    )
    if overlay_enabled:
        if not isinstance(overlay_cfg, Mapping):
            raise SystemExit(
                "Run summary indicates fundamentals.provider_overlay.enabled=true, "
                "but config.used.yml does not contain a valid provider_overlay mapping."
            )
        return "provider_overlay", dict(overlay_cfg)

    source = str(
        _mapping_value(config_fundamentals, "source")
        or _mapping_value(summary_fundamentals, "source")
        or ""
    ).strip().lower()
    if source != "file":
        raise SystemExit(
            "This audit script currently supports only fundamentals.source=file runs. "
            f"Resolved source={source or '<missing>'}."
        )
    file_ref = _mapping_value(config_fundamentals, "file") or _mapping_value(summary_fundamentals, "file")
    if not file_ref:
        raise SystemExit("Could not resolve fundamentals.file from config.used.yml or summary.json.")
    fundamentals_path = resolve_repo_path(str(file_ref))
    if not fundamentals_path.exists():
        raise SystemExit(f"Fundamentals file not found: {fundamentals_path}")
    return source, fundamentals_path


def load_eval_sample(path: Path) -> pd.DataFrame:
    frame = _read_frame(path)
    if "trade_date" not in frame.columns:
        raise SystemExit("Scored file is missing required column: trade_date")
    frame = _normalize_symbol_frame(frame, label="scored file")
    if frame.empty:
        raise SystemExit(f"Scored file has no valid trade_date/symbol rows: {path}")
    return frame


def restrict_eval_sample_to_rebalance_dates(
    eval_sample: pd.DataFrame,
    config_used: dict,
    summary: dict,
) -> pd.DataFrame:
    eval_cfg = config_used.get("eval")
    summary_eval = summary.get("eval")
    sample_on_rebalance_dates = bool(
        _mapping_value(eval_cfg, "sample_on_rebalance_dates")
        if _mapping_value(eval_cfg, "sample_on_rebalance_dates") is not None
        else _mapping_value(summary_eval, "sample_on_rebalance_dates")
    )
    rebalance_frequency = str(
        _mapping_value(eval_cfg, "rebalance_frequency")
        or _mapping_value(summary_eval, "rebalance_frequency")
        or ""
    ).strip()
    if not sample_on_rebalance_dates or not rebalance_frequency:
        return eval_sample

    trade_dates = sorted(eval_sample["trade_date"].dropna().unique().tolist())
    rebalance_dates = set(get_rebalance_dates(trade_dates, rebalance_frequency))
    filtered = eval_sample[eval_sample["trade_date"].isin(rebalance_dates)].copy()
    if filtered.empty:
        raise SystemExit(
            "Resolved sample_on_rebalance_dates=true, but no eval rows matched the "
            f"derived rebalance dates for frequency={rebalance_frequency}."
        )
    return filtered.sort_values(["symbol", "trade_date"]).reset_index(drop=True)


def load_fundamentals_frame(path: Path) -> tuple[pd.DataFrame, list[str]]:
    frame = _read_frame(path)
    if "trade_date" not in frame.columns:
        raise SystemExit("Fundamentals file is missing required column: trade_date")
    frame = _normalize_symbol_frame(frame, label="fundamentals file")
    provider_cols = [name for name in VALUATION_COLUMNS if name in frame.columns]
    if not provider_cols:
        raise SystemExit(
            "Fundamentals file does not contain any provider valuation columns: "
            f"{', '.join(VALUATION_COLUMNS)}"
        )
    return frame, provider_cols


def load_provider_overlay_frame(
    *,
    config_used: dict,
    summary: dict,
    overlay_cfg: Mapping[str, object],
    eval_sample: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str], Path]:
    market = str(config_used.get("market") or "").strip().lower()
    if not market:
        raise SystemExit("Could not resolve market from config.used.yml.")
    data_cfg = config_used.get("data")
    if not isinstance(data_cfg, Mapping):
        data_cfg = {}
    summary_fundamentals = summary.get("fundamentals")
    summary_overlay_cfg = (
        _mapping_value(summary_fundamentals, "provider_overlay")
        if isinstance(summary_fundamentals, Mapping)
        else None
    )
    overlay_cache_dir = _resolve_provider_overlay_cache_dir(
        data_cfg,
        overlay_cfg,
        summary_overlay_cfg,
        market,
    )
    overlay_cache_dir.mkdir(parents=True, exist_ok=True)

    start_cfg = _mapping_value(data_cfg, "start_date")
    end_cfg = _mapping_value(data_cfg, "end_date")
    start_date = str(start_cfg).strip() if start_cfg else eval_sample["trade_date"].min().strftime("%Y%m%d")
    end_date = str(end_cfg).strip() if end_cfg else eval_sample["trade_date"].max().strftime("%Y%m%d")
    provider = (
        resolve_provider({"provider": _mapping_value(overlay_cfg, "provider")})
        if _mapping_value(overlay_cfg, "provider")
        else resolve_provider(data_cfg)
    )
    tag = _cache_tag(data_cfg)
    overlay_frames: list[pd.DataFrame] = []
    cache_hits = 0
    symbols = sorted(eval_sample["symbol"].unique().tolist())
    for symbol in symbols:
        cache_file = _fundamentals_cache_file(
            overlay_cache_dir,
            market,
            provider,
            symbol,
            start_date,
            end_date,
            tag,
            overlay_cfg,
        )
        if not cache_file.exists():
            continue
        cache_hits += 1
        frame = pd.read_parquet(cache_file)
        if frame is not None and not frame.empty:
            overlay_frames.append(frame)
    if not overlay_frames:
        raise SystemExit(
            "Provider overlay is enabled, but no cached valuation data could be loaded for the eval sample. "
            f"Checked {len(symbols)} symbols under {overlay_cache_dir} with window {start_date}..{end_date}; "
            "re-run the model first or point the audit to the same cache directory used by the run."
        )
    frame = _normalize_symbol_frame(pd.concat(overlay_frames, ignore_index=True), label="provider overlay cache")
    provider_cols = [name for name in VALUATION_COLUMNS if name in frame.columns]
    if not provider_cols:
        raise SystemExit(
            "Provider overlay data does not contain any valuation columns: "
            f"{', '.join(VALUATION_COLUMNS)}"
        )
    if "valuation_trade_date" not in frame.columns:
        frame["valuation_trade_date"] = frame["trade_date"]
    frame.attrs["cache_symbol_hits"] = cache_hits
    frame.attrs["cache_symbol_total"] = len(symbols)
    return frame, provider_cols, overlay_cache_dir


def reconstruct_eval_valuation_panel(
    eval_sample: pd.DataFrame,
    fundamentals: pd.DataFrame,
    provider_cols: list[str],
    *,
    merge_mode: str,
) -> pd.DataFrame:
    keep_cols = ["trade_date", "symbol"] + provider_cols
    if "valuation_trade_date" in fundamentals.columns:
        keep_cols.append("valuation_trade_date")
    right = fundamentals[keep_cols].copy().sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    right["fundamentals_trade_date"] = right["trade_date"]

    if merge_mode == "exact":
        merged = eval_sample.merge(right, on=["trade_date", "symbol"], how="left")
    elif merge_mode == "backward_asof":
        provider_fill_cols = provider_cols + ["fundamentals_trade_date"]
        if "valuation_trade_date" in right.columns:
            provider_fill_cols.append("valuation_trade_date")

        right_groups = {
            symbol: group.drop(columns=["symbol"]).sort_values("trade_date").reset_index(drop=True)
            for symbol, group in right.groupby("symbol", sort=False)
        }
        merged_parts: list[pd.DataFrame] = []
        for symbol, left_group in eval_sample.groupby("symbol", sort=False):
            left_part = left_group.sort_values("trade_date").reset_index(drop=True)
            right_part = right_groups.get(symbol)
            if right_part is None or right_part.empty:
                empty_part = left_part.copy()
                for column in provider_fill_cols:
                    if column.endswith("_trade_date"):
                        empty_part[column] = pd.NaT
                    else:
                        empty_part[column] = float("nan")
                merged_parts.append(empty_part)
                continue
            merged_part = pd.merge_asof(
                left_part,
                right_part,
                on="trade_date",
                direction="backward",
            )
            merged_part["symbol"] = symbol
            merged_parts.append(merged_part)
        merged = pd.concat(merged_parts, ignore_index=True)
    else:
        raise SystemExit(f"Unsupported merge_mode: {merge_mode}")

    merged["valuation_nonnull_any"] = merged[provider_cols].notna().any(axis=1)
    if "valuation_trade_date" in merged.columns:
        merged["valuation_age_days"] = (merged["trade_date"] - merged["valuation_trade_date"]).dt.days
    else:
        merged["valuation_age_days"] = pd.Series(pd.NA, index=merged.index, dtype="Int64")
    return merged


def _round_number(value: float | int | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return round(float(value), 2)


def summarize_by_trade_date(panel: pd.DataFrame, provider_cols: list[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for trade_date, group in panel.groupby("trade_date", sort=True):
        total_rows = int(len(group))
        nonnull_any = int(group["valuation_nonnull_any"].sum())
        age_sample = group.loc[group["valuation_nonnull_any"], "valuation_age_days"].dropna()
        row = {
            "trade_date": trade_date.strftime("%Y-%m-%d"),
            "rows": total_rows,
            "valuation_nonnull_rows": nonnull_any,
            "valuation_coverage_pct": _round_number(nonnull_any / total_rows * 100.0 if total_rows else None),
            "age_rows": int(age_sample.shape[0]),
            "valuation_age_days_mean": _round_number(age_sample.mean() if not age_sample.empty else None),
            "valuation_age_days_median": _round_number(age_sample.median() if not age_sample.empty else None),
            "valuation_age_days_p90": _round_number(age_sample.quantile(0.9) if not age_sample.empty else None),
            "valuation_age_days_max": _round_number(age_sample.max() if not age_sample.empty else None),
        }
        for column in provider_cols:
            nonnull_col = int(group[column].notna().sum())
            row[f"{column}_coverage_pct"] = _round_number(
                nonnull_col / total_rows * 100.0 if total_rows else None
            )
        rows.append(row)
    return pd.DataFrame(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit provider valuation coverage on an HK run by reconstructing eval rows "
            "with file-backed backward-asof or provider-overlay exact-merge semantics."
        )
    )
    parser.add_argument("--run-dir", required=True, help="Run directory containing config.used.yml and eval_scored.parquet.")
    parser.add_argument("--scored-file", help="Optional eval_scored file override.")
    parser.add_argument("--fundamentals-file", help="Optional fundamentals.file override.")
    parser.add_argument(
        "--out",
        help=(
            "Optional CSV output path. Default: "
            "artifacts/reports/<run_dir_name>_provider_valuation_audit.csv"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    run_dir = resolve_repo_path(args.run_dir)
    if not run_dir.exists():
        raise SystemExit(f"Run directory not found: {run_dir}")

    config_used, summary = load_run_metadata(run_dir)
    scored_path = resolve_scored_file(run_dir, summary, args.scored_file)
    eval_sample = load_eval_sample(scored_path)
    eval_sample = restrict_eval_sample_to_rebalance_dates(eval_sample, config_used, summary)
    valuation_source, valuation_payload = resolve_valuation_source(
        config_used, summary, args.fundamentals_file
    )
    overlay_cache_dir: Path | None = None
    overlay_cache_hits: tuple[int, int] | None = None
    if valuation_source == "file":
        fundamentals_path = valuation_payload
        assert isinstance(fundamentals_path, Path)
        fundamentals, provider_cols = load_fundamentals_frame(fundamentals_path)
        panel = reconstruct_eval_valuation_panel(
            eval_sample,
            fundamentals,
            provider_cols,
            merge_mode="backward_asof",
        )
    elif valuation_source == "provider_overlay":
        overlay_cfg = valuation_payload
        assert isinstance(overlay_cfg, Mapping)
        fundamentals, provider_cols, overlay_cache_dir = load_provider_overlay_frame(
            config_used=config_used,
            summary=summary,
            overlay_cfg=overlay_cfg,
            eval_sample=eval_sample,
        )
        overlay_cache_hits = (
            int(fundamentals.attrs.get("cache_symbol_hits", 0)),
            int(fundamentals.attrs.get("cache_symbol_total", 0)),
        )
        fundamentals_path = overlay_cache_dir
        panel = reconstruct_eval_valuation_panel(
            eval_sample,
            fundamentals,
            provider_cols,
            merge_mode="exact",
        )
    else:
        raise SystemExit(f"Unsupported valuation source: {valuation_source}")
    report = summarize_by_trade_date(panel, provider_cols)

    out_path = (
        resolve_repo_path(args.out)
        if args.out
        else (DEFAULT_REPORT_DIR / f"{run_dir.name}_provider_valuation_audit.csv").resolve()
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(out_path, index=False)

    overall_nonnull = int(panel["valuation_nonnull_any"].sum())
    overall_rows = int(len(panel))
    age_all = panel.loc[panel["valuation_nonnull_any"], "valuation_age_days"].dropna()

    print(f"Run dir: {run_dir}")
    print(f"Scored file: {scored_path}")
    print(f"Valuation source: {valuation_source}")
    if valuation_source == "file":
        print(f"Fundamentals file: {fundamentals_path}")
    elif overlay_cache_dir is not None:
        print(f"Provider overlay cache dir: {overlay_cache_dir}")
        if overlay_cache_hits is not None:
            print(f"Provider overlay cache hits: {overlay_cache_hits[0]}/{overlay_cache_hits[1]} symbols")
    print(f"Provider columns: {provider_cols}")
    print(f"Eval rows: {overall_rows}")
    print(f"Eval dates: {panel['trade_date'].nunique()}")
    print(f"Coverage(any valuation col): {_round_number(overall_nonnull / overall_rows * 100.0 if overall_rows else None)}%")
    if not age_all.empty:
        print(
            "valuation_age_days: "
            f"mean={_round_number(age_all.mean())}, "
            f"median={_round_number(age_all.median())}, "
            f"p90={_round_number(age_all.quantile(0.9))}, "
            f"max={_round_number(age_all.max())}"
        )
    else:
        print("valuation_age_days: unavailable (valuation_trade_date not present or fully missing)")
    print(f"Wrote report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
