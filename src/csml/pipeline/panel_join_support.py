from __future__ import annotations

import logging
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from ..artifacts import CACHE_DIR as DEFAULT_CACHE_DIR, resolve_repo_path
from ..data_interface import DataInterface
from ..data_providers import normalize_market

logger = logging.getLogger("csml")


def resolve_panel_cache_dir(
    data_cfg: Mapping[str, Any],
    join_cfg: Mapping[str, Any],
    market: str,
) -> Path:
    configured = join_cfg.get("cache_dir")
    if configured:
        return resolve_repo_path(configured)
    base_dir = resolve_repo_path(
        data_cfg.get("cache_dir", DEFAULT_CACHE_DIR.as_posix())
    )
    return base_dir / "fundamentals" / normalize_market(market)


def load_panel_join_frames(
    *,
    source: str,
    file_path: Path | None,
    data_interface: DataInterface,
    symbols: list[str],
    start_date: str,
    end_date: str,
    data_cfg: Mapping[str, Any],
    join_cfg: Mapping[str, Any],
    market: str,
    item_label: str,
    log_retry_failures: bool = True,
    log_retry_traceback: bool = True,
) -> tuple[list[pd.DataFrame], Path | None]:
    frames: list[pd.DataFrame] = []
    cache_dir: Path | None = None
    if source == "file":
        if file_path is None:
            return frames, cache_dir
        if file_path.suffix.lower() in {".parquet", ".pq"}:
            frames.append(pd.read_parquet(file_path))
        else:
            frames.append(pd.read_csv(file_path))
        return frames, cache_dir

    cache_dir = resolve_panel_cache_dir(data_cfg, join_cfg, market)
    cache_dir.mkdir(parents=True, exist_ok=True)

    for symbol in symbols:
        logger.info("Fetching %s for %s (%s) ...", item_label, symbol, market)
        try:
            frame = data_interface.fetch_fundamentals(
                symbol,
                start_date,
                end_date,
                join_cfg,
                cache_dir=cache_dir,
                log_retry_failures=log_retry_failures,
                log_retry_traceback=log_retry_traceback,
            )
        except Exception as exc:
            logger.warning("Skipping %s for %s after retries (%s).", item_label, symbol, exc)
            frame = pd.DataFrame()
        if frame is not None and not frame.empty:
            frames.append(frame)
    return frames, cache_dir


def merge_panel_frame(
    panel_df: pd.DataFrame,
    join_df: pd.DataFrame,
    *,
    ffill: bool,
    ffill_limit: int | None,
    merge_label: str,
) -> tuple[pd.DataFrame, list[str]]:
    merge_cols = [
        col for col in join_df.columns if col not in {"trade_date", "symbol", "ts_code", "stock_ticker"}
    ]
    overlap_cols = sorted(set(merge_cols).intersection(panel_df.columns))
    if overlap_cols:
        sys.exit(
            f"{merge_label} columns already exist in panel and would be overwritten: {overlap_cols}"
        )
    merged = panel_df.merge(join_df, on=["trade_date", "symbol"], how="left")
    if ffill and merge_cols:
        merged.sort_values(["symbol", "trade_date"], inplace=True)
        merged[merge_cols] = merged.groupby("symbol")[merge_cols].ffill(limit=ffill_limit)
    return merged, merge_cols
