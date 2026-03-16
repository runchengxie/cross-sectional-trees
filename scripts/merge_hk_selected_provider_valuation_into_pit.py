#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import pandas as pd
from dotenv import load_dotenv

from csml.config_utils import resolve_pipeline_config
from csml import data_providers


DEFAULT_PIT_FILE = (
    "artifacts/assets/rqdata/hk/pit_financials/"
    "hk_selected_pit_2011_2025_latest/pipeline_fundamentals.parquet"
)
DEFAULT_OUTPUT_FILE = (
    "artifacts/assets/rqdata/hk/pit_financials/"
    "hk_selected_pit_2011_2025_latest/pipeline_fundamentals_with_provider_valuation.parquet"
)
DEFAULT_PROVIDER_CONFIG = (
    "configs/local/hk_selected__quarterly_4way_g2_price_provider_valuation_xgb_ranker.yml"
)
DEFAULT_CACHE_DIR = "artifacts/cache/fundamentals/hk/provider_valuation_merge"


def resolve_repo_path(path_text: str | Path) -> Path:
    path = Path(path_text).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (REPO_ROOT / path).resolve()


def _normalize_trade_date(series: pd.Series) -> pd.Series:
    values = pd.to_datetime(series, errors="coerce")
    return values.dt.strftime("%Y%m%d")


def _normalize_symbol(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.upper()


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
    try:
        import rqdatac
    except ImportError as exc:
        raise SystemExit(
            "rqdatac is not installed. Run `uv sync --extra dev --extra rqdata` first."
        ) from exc

    load_dotenv()
    init_kwargs: dict[str, str] = {}
    rq_cfg = cfg.get("data", {}).get("rqdata", {}) if isinstance(cfg.get("data"), dict) else {}
    if isinstance(rq_cfg, dict) and isinstance(rq_cfg.get("init"), dict):
        init_kwargs.update(rq_cfg.get("init"))

    if username:
        init_kwargs["username"] = username
    if password:
        init_kwargs["password"] = password

    env_username = os.getenv("RQDATA_USERNAME") or os.getenv("RQDATA_USER")
    env_password = os.getenv("RQDATA_PASSWORD")
    if env_username and "username" not in init_kwargs:
        init_kwargs["username"] = env_username
    if env_password and "password" not in init_kwargs:
        init_kwargs["password"] = env_password

    try:
        rqdatac.init(**init_kwargs)
    except Exception as exc:
        raise SystemExit(f"rqdatac.init failed: {exc}") from exc
    return rqdatac


def load_pit_frame(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"PIT fundamentals file not found: {path}")
    frame = pd.read_parquet(path)
    required_cols = {"trade_date", "ts_code"}
    missing = required_cols.difference(frame.columns)
    if missing:
        raise SystemExit(f"PIT fundamentals file is missing columns: {sorted(missing)}")
    frame = frame.copy()
    frame["trade_date"] = _normalize_trade_date(frame["trade_date"])
    frame["ts_code"] = _normalize_symbol(frame["ts_code"])
    frame = frame.dropna(subset=["trade_date", "ts_code"])
    frame = frame.drop_duplicates(subset=["trade_date", "ts_code"]).reset_index(drop=True)
    return frame


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
    fundamentals_cfg = cfg.get("fundamentals", {}) if isinstance(cfg.get("fundamentals"), dict) else {}
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
    provider_df["trade_date"] = _normalize_trade_date(provider_df["trade_date"])
    provider_df["ts_code"] = _normalize_symbol(provider_df["ts_code"])
    provider_df = provider_df.dropna(subset=["trade_date", "ts_code"])
    provider_df = provider_df.drop_duplicates(subset=["trade_date", "ts_code"]).reset_index(drop=True)
    return provider_df


def merge_frames(pit_df: pd.DataFrame, provider_df: pd.DataFrame) -> pd.DataFrame:
    value_cols = [col for col in provider_df.columns if col not in {"trade_date", "ts_code"}]
    collisions = sorted((set(value_cols) & set(pit_df.columns)) - {"trade_date", "ts_code"})
    if collisions:
        raise SystemExit(
            "Provider valuation columns already exist in PIT file: "
            f"{collisions}. Remove them or choose a fresh PIT input file."
        )
    merged = pit_df.merge(
        provider_df[["trade_date", "ts_code"] + value_cols],
        on=["trade_date", "ts_code"],
        how="left",
    )
    return merged


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Merge provider valuation columns into HK selected PIT fundamentals parquet."
    )
    parser.add_argument("--pit-file", default=DEFAULT_PIT_FILE, help="Input PIT fundamentals parquet.")
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
    symbols = sorted(pit_df["ts_code"].dropna().unique().tolist())
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
    merged = merge_frames(pit_df, provider_df)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(output_path, index=False)

    added_cols = [col for col in provider_df.columns if col not in {"trade_date", "ts_code"}]
    non_null_rows = int(merged[added_cols].notna().any(axis=1).sum()) if added_cols else 0
    print(f"Wrote merged parquet: {output_path}")
    print(f"Rows: {len(merged)}")
    print(f"Added columns: {added_cols}")
    print(f"Rows with any provider valuation: {non_null_rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
