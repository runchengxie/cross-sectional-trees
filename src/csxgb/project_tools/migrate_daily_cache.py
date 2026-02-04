from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

from ..data_providers import _ensure_trade_date_str


DAILY_RANGE_PATTERN = re.compile(
    r"^(?P<prefix>.+)_daily_(?P<symbol>.+)_(?P<start>\d{8})_(?P<end>\d{8})\.parquet$"
)


def _collect_range_files(
    cache_dir: Path,
    prefix_filter: str | None,
    symbol_filter: set[str] | None,
) -> dict[Path, list[Path]]:
    groups: dict[Path, list[Path]] = defaultdict(list)
    for path in cache_dir.glob("*.parquet"):
        match = DAILY_RANGE_PATTERN.match(path.name)
        if not match:
            continue
        prefix = match.group("prefix")
        symbol = match.group("symbol")
        if prefix_filter and prefix != prefix_filter:
            continue
        if symbol_filter and symbol not in symbol_filter:
            continue
        target = cache_dir / f"{prefix}_daily_{symbol}.parquet"
        groups[target].append(path)
    return groups


def _merge_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    if not frames:
        return pd.DataFrame()
    merged = pd.concat(frames, ignore_index=True)
    merged = _ensure_trade_date_str(merged)
    if merged is None or merged.empty:
        return pd.DataFrame()
    merged = merged.drop_duplicates(subset=["ts_code", "trade_date"], keep="last")
    merged.sort_values(["ts_code", "trade_date"], inplace=True)
    return merged


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Migrate range-based daily cache files to symbol-based cache files."
    )
    parser.add_argument(
        "--cache-dir",
        default="cache",
        help="Cache directory containing daily parquet files (default: cache).",
    )
    parser.add_argument(
        "--prefix",
        help="Only migrate files with this cache prefix (market_provider_tag).",
    )
    parser.add_argument(
        "--symbol",
        action="append",
        help="Only migrate specific symbols (can be passed multiple times).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing symbol cache files instead of merging.",
    )
    parser.add_argument(
        "--prune-old",
        action="store_true",
        help="Delete old range cache files after migration.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned operations without writing files.",
    )
    args = parser.parse_args(argv)

    cache_dir = Path(args.cache_dir).expanduser().resolve()
    if not cache_dir.exists():
        raise SystemExit(f"Cache dir not found: {cache_dir}")

    symbol_filter = set(args.symbol) if args.symbol else None
    groups = _collect_range_files(cache_dir, args.prefix, symbol_filter)
    if not groups:
        print("No range-based daily cache files found.")
        return

    migrated = 0
    skipped = 0
    total_range_files = 0

    for target, files in sorted(groups.items(), key=lambda item: item[0].name):
        files = sorted(files, key=lambda path: path.name)
        total_range_files += len(files)
        if args.dry_run:
            print(f"[dry-run] {target.name}")
            for path in files:
                print(f"  - {path.name}")
            continue

        frames: list[pd.DataFrame] = []
        if target.exists() and not args.overwrite:
            existing = pd.read_parquet(target)
            existing = _ensure_trade_date_str(existing)
            if existing is not None and not existing.empty:
                frames.append(existing)

        for path in files:
            df = pd.read_parquet(path)
            df = _ensure_trade_date_str(df)
            if df is None or df.empty:
                continue
            frames.append(df)

        merged = _merge_frames(frames)
        if merged.empty:
            skipped += 1
            continue

        merged = merged.copy(deep=True)
        merged.to_parquet(target)
        migrated += 1

        if args.prune_old:
            for path in files:
                try:
                    path.unlink()
                except OSError:
                    print(f"Warning: failed to delete {path}")

    if args.dry_run:
        return

    print(
        f"Migrated {migrated} symbol caches from {total_range_files} range files "
        f"({skipped} skipped)."
    )


if __name__ == "__main__":
    main()
