#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from cstree import data_providers
from cstree.config_utils import resolve_pipeline_config
from market_data_platform.symbols import drop_legacy_symbol_columns, ensure_symbol_columns
from market_data_platform.repo_paths import find_repo_root, resolve_repo_path as resolve_repo_relative_path
from market_data_platform.rqdata_runtime import init_rqdatac as _init_rqdatac_runtime

REPO_ROOT = find_repo_root(__file__)


DEFAULT_PIT_FILE = (
    "artifacts/assets/rqdata/hk/pit_financials/"
    "hk_selected_pit_2011_2025_latest/pipeline_fundamentals.parquet"
)
DEFAULT_OUTPUT_FILE = (
    "artifacts/assets/rqdata/hk/pit_financials/"
    "hk_selected_pit_2011_2025_latest/pipeline_fundamentals_with_provider_valuation.parquet"
)
DEFAULT_PROVIDER_CONFIG = "configs/experiments/baseline/hk_selected.yml"
DEFAULT_CACHE_DIR = "artifacts/cache/fundamentals/hk/provider_valuation_merge"


def resolve_repo_path(path_text: str | Path) -> Path:
    return resolve_repo_relative_path(path_text, repo_root=REPO_ROOT)


def _normalize_trade_date(series: pd.Series) -> pd.Series:
    values = pd.to_datetime(series, errors="coerce")
    return values.dt.strftime("%Y%m%d")


def _normalize_trade_date_dt(series: pd.Series) -> pd.Series:
    values = pd.to_datetime(series, errors="coerce")
    return values.dt.normalize()


def _normalize_symbol(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.upper()


def _normalize_symbol_frame(frame: pd.DataFrame, *, label: str) -> pd.DataFrame:
    frame = ensure_symbol_columns(frame, context=label).copy()
    frame["trade_date"] = _normalize_trade_date(frame["trade_date"])
    frame["symbol"] = _normalize_symbol(frame["symbol"])
    frame = frame.dropna(subset=["trade_date", "symbol"])
    frame = frame.drop_duplicates(subset=["trade_date", "symbol"]).reset_index(drop=True)
    frame = drop_legacy_symbol_columns(frame)
    return frame


def load_provider_config(path_text: str) -> dict:
    resolved = resolve_pipeline_config(path_text)
    cfg = resolved.data
    fundamentals_cfg = cfg.get("fundamentals") if isinstance(cfg, dict) else None
    if not isinstance(fundamentals_cfg, dict):
        raise SystemExit("provider config does not contain a fundamentals section.")
    if str(fundamentals_cfg.get("source", "")).strip().lower() != "provider":
        raise SystemExit("provider config must use fundamentals.source=provider.")
    return cfg


def init_rqdatac(cfg: dict, username: str | None, password: str | None):
    load_dotenv()
    data_cfg = cfg.get("data") if isinstance(cfg, dict) else None
    return _init_rqdatac_runtime(
        data_cfg=data_cfg,
        username=username,
        password=password,
        logger=logging.getLogger("cstree.research.provider_valuation_merge"),
        load_env=False,
        error_cls=SystemExit,
        import_error_message=(
            "rqdatac is not installed. Run `uv sync --extra dev --extra rqdata` first."
        ),
    )


def load_pit_frame(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"PIT fundamentals file not found: {path}")
    frame = pd.read_parquet(path)
    if "trade_date" not in frame.columns:
        raise SystemExit("PIT fundamentals file is missing required column: trade_date")
    return _normalize_symbol_frame(frame, label="PIT fundamentals file")


def fetch_provider_frame(
    *,
    symbols: list[str],
    start_date: str,
    end_date: str,
    cache_dir: Path,
    cfg: dict,
    client,
) -> pd.DataFrame:
    data_cfg = cfg.get("data", {}) if isinstance(cfg.get("data"), dict) else {}
    fundamentals_cfg = (
        cfg.get("fundamentals", {}) if isinstance(cfg.get("fundamentals"), dict) else {}
    )
    frames: list[pd.DataFrame] = []

    for idx, symbol in enumerate(symbols, start=1):
        print(f"[{idx}/{len(symbols)}] fetching provider valuation for {symbol} ...")
        frame = data_providers.fetch_fundamentals(
            "hk",
            symbol,
            start_date,
            end_date,
            cache_dir,
            client,
            data_cfg,
            fundamentals_cfg,
        )
        if frame is None or frame.empty:
            continue
        frames.append(frame)

    if not frames:
        raise SystemExit("No provider valuation data was fetched.")

    provider_df = pd.concat(frames, ignore_index=True)
    return _normalize_symbol_frame(provider_df, label="provider valuation frame")


def _value_columns_for_merge(
    pit_df: pd.DataFrame,
    provider_df: pd.DataFrame,
    *,
    extra_output_cols: list[str] | None = None,
) -> list[str]:
    value_cols = [col for col in provider_df.columns if col not in {"trade_date", "symbol"}]
    output_cols = value_cols + list(extra_output_cols or [])
    collisions = sorted((set(output_cols) & set(pit_df.columns)) - {"trade_date", "symbol"})
    if collisions:
        raise SystemExit(
            "Provider valuation columns already exist in PIT file: "
            f"{collisions}. Remove them or choose a fresh PIT input file."
        )
    return value_cols


def _merge_frames_exact(pit_df: pd.DataFrame, provider_df: pd.DataFrame) -> pd.DataFrame:
    value_cols = _value_columns_for_merge(pit_df, provider_df)
    merged = pit_df.merge(
        provider_df[["trade_date", "symbol"] + value_cols],
        on=["trade_date", "symbol"],
        how="left",
    )
    return merged


def _merge_frames_asof(
    pit_df: pd.DataFrame,
    provider_df: pd.DataFrame,
    *,
    source_date_col: str,
    age_col: str,
) -> pd.DataFrame:
    value_cols = _value_columns_for_merge(
        pit_df,
        provider_df,
        extra_output_cols=[source_date_col, age_col],
    )
    pit_work = pit_df.copy()
    provider_work = provider_df.copy()
    pit_work["trade_date_dt"] = _normalize_trade_date_dt(pit_work["trade_date"])
    provider_work["provider_trade_date_dt"] = _normalize_trade_date_dt(provider_work["trade_date"])
    provider_work[source_date_col] = _normalize_trade_date(provider_work["trade_date"])

    merged_groups: list[pd.DataFrame] = []
    for symbol, pit_group in pit_work.groupby("symbol", sort=False):
        pit_group = pit_group.sort_values("trade_date_dt").copy()
        provider_group = provider_work[provider_work["symbol"] == symbol].copy()
        if provider_group.empty:
            pit_group[source_date_col] = pd.NA
            pit_group[age_col] = pd.NA
            for col in value_cols:
                pit_group[col] = pd.NA
            merged_groups.append(pit_group)
            continue
        provider_group = provider_group.sort_values("provider_trade_date_dt")
        merged_group = pd.merge_asof(
            pit_group,
            provider_group[["provider_trade_date_dt", source_date_col, "symbol"] + value_cols],
            left_on="trade_date_dt",
            right_on="provider_trade_date_dt",
            by="symbol",
            direction="backward",
        )
        merged_group[age_col] = (
            merged_group["trade_date_dt"] - merged_group["provider_trade_date_dt"]
        ).dt.days
        merged_groups.append(merged_group)

    merged = pd.concat(merged_groups, ignore_index=True)
    merged = merged.drop(columns=["trade_date_dt", "provider_trade_date_dt"], errors="ignore")
    return merged


def merge_frames(
    pit_df: pd.DataFrame,
    provider_df: pd.DataFrame,
    *,
    merge_mode: str = "exact",
    source_date_col: str = "valuation_trade_date",
    age_col: str = "valuation_age_days",
) -> pd.DataFrame:
    mode = str(merge_mode).strip().lower()
    if mode == "exact":
        return _merge_frames_exact(pit_df, provider_df)
    if mode == "asof":
        return _merge_frames_asof(
            pit_df,
            provider_df,
            source_date_col=source_date_col,
            age_col=age_col,
        )
    raise SystemExit(f"Unsupported merge mode: {merge_mode}. Use exact or asof.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Merge provider valuation columns into HK selected PIT fundamentals parquet."
    )
    parser.add_argument(
        "--pit-file", default=DEFAULT_PIT_FILE, help="Input PIT fundamentals parquet."
    )
    parser.add_argument(
        "--provider-config",
        default=DEFAULT_PROVIDER_CONFIG,
        help="Config path that defines the provider valuation fields and rqdata init settings.",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_FILE,
        help="Output parquet path for the merged fundamentals file.",
    )
    parser.add_argument(
        "--cache-dir",
        default=DEFAULT_CACHE_DIR,
        help="Cache directory for provider valuation fetches.",
    )
    parser.add_argument("--username", help="Optional RQData username override.")
    parser.add_argument("--password", help="Optional RQData password override.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the output parquet if it already exists.",
    )
    parser.add_argument(
        "--merge-mode",
        choices=["exact", "asof"],
        default="exact",
        help="How to align provider valuation rows onto PIT dates. Default: exact.",
    )
    parser.add_argument(
        "--source-date-col",
        default="valuation_trade_date",
        help="Provider source date column emitted by --merge-mode asof. Default: valuation_trade_date.",
    )
    parser.add_argument(
        "--age-col",
        default="valuation_age_days",
        help="Provider age column emitted by --merge-mode asof. Default: valuation_age_days.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    pit_path = resolve_repo_path(args.pit_file)
    output_path = resolve_repo_path(args.output)
    cache_dir = resolve_repo_path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    if output_path.exists() and not args.overwrite:
        raise SystemExit(f"Output already exists: {output_path}. Pass --overwrite to replace it.")

    cfg = load_provider_config(args.provider_config)
    client = init_rqdatac(cfg, args.username, args.password)

    pit_df = load_pit_frame(pit_path)
    symbols = sorted(pit_df["symbol"].dropna().unique().tolist())
    start_date = str(pit_df["trade_date"].min())
    end_date = str(pit_df["trade_date"].max())

    print(f"PIT file: {pit_path}")
    print(f"Provider config: {args.provider_config}")
    print(f"Date range: {start_date} -> {end_date}")
    print(f"Symbols: {len(symbols)}")

    provider_df = fetch_provider_frame(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        cache_dir=cache_dir,
        cfg=cfg,
        client=client,
    )
    merged = merge_frames(
        pit_df,
        provider_df,
        merge_mode=args.merge_mode,
        source_date_col=args.source_date_col,
        age_col=args.age_col,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(output_path, index=False)

    added_cols = [col for col in provider_df.columns if col not in {"trade_date", "symbol"}]
    non_null_rows = int(merged[added_cols].notna().any(axis=1).sum()) if added_cols else 0
    print(f"Wrote merged parquet: {output_path}")
    print(f"Rows: {len(merged)}")
    print(f"Added columns: {added_cols}")
    print(f"Rows with any provider valuation: {non_null_rows}")
    print(f"Merge mode: {args.merge_mode}")
    if args.merge_mode == "asof" and args.age_col in merged.columns:
        age_series = pd.to_numeric(merged[args.age_col], errors="coerce")
        age_non_null = age_series.dropna()
        if not age_non_null.empty:
            print(
                "Provider valuation age (days): "
                f"median={age_non_null.median():.1f}, "
                f"p90={age_non_null.quantile(0.9):.1f}, "
                f"max={age_non_null.max():.1f}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
