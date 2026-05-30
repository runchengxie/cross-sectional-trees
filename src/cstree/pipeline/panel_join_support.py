from __future__ import annotations

import logging
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd
from market_data_platform.artifacts import CACHE_DIR as DEFAULT_CACHE_DIR, resolve_repo_path
from market_data_platform.data_providers import normalize_market

from ..data_interface import DataInterface

logger = logging.getLogger("cstree")


def frame_memory_mb(frame: pd.DataFrame) -> float:
    if frame is None or frame.empty:
        return 0.0
    return float(frame.memory_usage(index=True, deep=True).sum() / (1024 * 1024))


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
    file_columns: Sequence[str] | None = None,
    log_retry_failures: bool = True,
    log_retry_traceback: bool = True,
) -> tuple[list[pd.DataFrame], Path | None]:
    frames: list[pd.DataFrame] = []
    cache_dir: Path | None = None
    if source == "file":
        if file_path is None:
            return frames, cache_dir
        requested_columns = list(dict.fromkeys(str(col) for col in file_columns or [] if str(col)))
        if file_path.suffix.lower() in {".parquet", ".pq"}:
            available_columns = _parquet_columns(file_path)
            read_columns = _select_available_columns(requested_columns, available_columns)
            if requested_columns and read_columns:
                logger.info(
                    "Reading %s file with column projection: %s/%s columns.",
                    item_label,
                    len(read_columns),
                    len(available_columns) if available_columns is not None else "unknown",
                )
                try:
                    frames.append(pd.read_parquet(file_path, columns=read_columns))
                except Exception as exc:
                    logger.warning(
                        "Could not read projected %s columns from %s (%s); reading full file.",
                        item_label,
                        file_path,
                        exc,
                    )
                    frames.append(pd.read_parquet(file_path))
            else:
                frames.append(pd.read_parquet(file_path))
        else:
            available_columns = _csv_columns(file_path)
            read_columns = _select_available_columns(requested_columns, available_columns)
            if requested_columns and read_columns:
                logger.info(
                    "Reading %s file with column projection: %s/%s columns.",
                    item_label,
                    len(read_columns),
                    len(available_columns) if available_columns is not None else "unknown",
                )
                frames.append(pd.read_csv(file_path, usecols=read_columns))
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


def _parquet_columns(path: Path) -> list[str] | None:
    try:
        import pyarrow.parquet as pq
    except ImportError:
        return None
    try:
        return list(pq.read_schema(path).names)
    except Exception:
        return None


def _csv_columns(path: Path) -> list[str] | None:
    try:
        return list(pd.read_csv(path, nrows=0).columns)
    except Exception:
        return None


def _select_available_columns(
    requested_columns: Sequence[str],
    available_columns: Sequence[str] | None,
) -> list[str]:
    if not requested_columns:
        return []
    if available_columns is None:
        return list(dict.fromkeys(requested_columns))
    available = set(available_columns)
    return [column for column in requested_columns if column in available]
