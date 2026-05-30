from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from ..data_interface import DataInterface
from market_data_platform.symbols import DEFAULT_SYMBOL_PRIORITY
from .panel_join_support import load_panel_join_frames, merge_panel_frame
from .support import _prepare_panel_join_frame, _select_panel_join_columns

logger = logging.getLogger("cstree")


def apply_industry_enrichment(
    *,
    panel_df: pd.DataFrame,
    data_interface: DataInterface,
    symbols: list[str],
    start_date: str,
    end_date: str,
    market: str,
    data_cfg: Mapping[str, Any],
    industry_cfg: Mapping[str, Any],
    industry_enabled: bool,
    industry_file_path: Path | None,
    industry_keep_columns: list[str],
    industry_ffill: bool,
    industry_ffill_limit: int | None,
) -> dict[str, Any]:
    df = panel_df
    industry_cols: list[str] = []
    industry_source_df = pd.DataFrame()

    if not industry_enabled:
        return {
            "df": df,
            "industry_cols": industry_cols,
            "industry_source_df": industry_source_df,
        }

    industry_frames, _ = load_panel_join_frames(
        source="file",
        file_path=industry_file_path,
        data_interface=data_interface,
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        data_cfg=data_cfg,
        join_cfg=industry_cfg,
        market=market,
        item_label="industry labels",
    )
    if industry_frames:
        industry_df = pd.concat(industry_frames, ignore_index=True)
        industry_df = _prepare_panel_join_frame(
            industry_df,
            industry_cfg.get("column_map"),
            item_label="Industry",
            symbol_priority=DEFAULT_SYMBOL_PRIORITY,
        )
        industry_df = _select_panel_join_columns(
            industry_df,
            keep_columns=industry_keep_columns,
            item_label="Industry",
        )
        industry_source_df = industry_df.copy()
        df, industry_cols = merge_panel_frame(
            df,
            industry_df,
            ffill=industry_ffill,
            ffill_limit=industry_ffill_limit,
            merge_label="Industry",
        )
        logger.info(
            "Merged industry labels: %s rows, %s columns.",
            len(industry_df),
            len(industry_cols),
        )
    else:
        logger.warning("Industry join enabled but no industry data was loaded.")

    return {
        "df": df,
        "industry_cols": industry_cols,
        "industry_source_df": industry_source_df,
    }
