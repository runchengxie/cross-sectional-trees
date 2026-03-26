from __future__ import annotations

import hashlib
import logging
import math
import sys
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import yaml

from ..rebalance import estimate_rebalance_gap
from .dates import _build_trade_date_slices, _slice_trade_date_range, _slice_with_train_window
from .stats import _warn_if_purge_too_small

logger = logging.getLogger("csml")
_managed_stream_handler: Optional[logging.Handler] = None
_managed_file_handler: Optional[logging.Handler] = None


def _resolve_log_file(
    cfg: dict,
    *,
    default_log_file: Optional[Path] = None,
) -> Optional[Path]:
    log_cfg = cfg.get("logging") if isinstance(cfg, dict) else None
    log_cfg = log_cfg if isinstance(log_cfg, dict) else {}
    log_file = log_cfg.get("file")
    if log_file is None:
        return default_log_file
    log_path_text = str(log_file).strip()
    if not log_path_text:
        return default_log_file
    return Path(log_path_text).expanduser()


def setup_logging(
    cfg: dict,
    *,
    default_log_file: Optional[Path] = None,
) -> Optional[Path]:
    global _managed_stream_handler, _managed_file_handler

    log_cfg = cfg.get("logging") if isinstance(cfg, dict) else None
    log_cfg = log_cfg if isinstance(log_cfg, dict) else {}
    level_name = str(log_cfg.get("level", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)
    log_file = _resolve_log_file(cfg, default_log_file=default_log_file)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    if _managed_stream_handler is None or _managed_stream_handler not in root_logger.handlers:
        _managed_stream_handler = logging.StreamHandler()
        root_logger.addHandler(_managed_stream_handler)
    _managed_stream_handler.setFormatter(formatter)
    _managed_stream_handler.setLevel(logging.NOTSET)

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        resolved_target = log_file.resolve()
        existing_target = None
        if _managed_file_handler is not None:
            existing_target = Path(getattr(_managed_file_handler, "baseFilename", "")).resolve()
        if (
            _managed_file_handler is None
            or _managed_file_handler not in root_logger.handlers
            or existing_target != resolved_target
        ):
            if _managed_file_handler is not None:
                if _managed_file_handler in root_logger.handlers:
                    root_logger.removeHandler(_managed_file_handler)
                _managed_file_handler.close()
            _managed_file_handler = logging.FileHandler(log_file, encoding="utf-8")
            root_logger.addHandler(_managed_file_handler)
        _managed_file_handler.setFormatter(formatter)
        _managed_file_handler.setLevel(logging.NOTSET)
    elif _managed_file_handler is not None:
        if _managed_file_handler in root_logger.handlers:
            root_logger.removeHandler(_managed_file_handler)
        _managed_file_handler.close()
        _managed_file_handler = None
    return log_file


def config_hash(cfg: dict) -> str:
    dumped = yaml.safe_dump(cfg, sort_keys=True)
    return hashlib.md5(dumped.encode("utf-8")).hexdigest()[:8]


def _resolve_holdout_len(value: object | None, n_dates: int) -> int:
    if value is None:
        return 0
    if n_dates <= 0:
        return 0
    try:
        size = float(value)
    except (TypeError, ValueError):
        raise SystemExit("eval.final_oos.size must be a number.")
    if size <= 0:
        return 0
    if size < 1:
        return max(1, int(np.floor(n_dates * size)))
    return int(size)


def _days_to_steps(days: int, gap_days: Optional[float]) -> int:
    if days <= 0:
        return 0
    if gap_days is None or not np.isfinite(gap_days) or gap_days <= 0:
        return int(days)
    return max(0, int(math.ceil(days / gap_days)))


def _prepare_split_context(
    *,
    df_model_all_sorted: pd.DataFrame,
    all_dates_model_full: np.ndarray,
    model_date_start_rows: np.ndarray,
    model_date_end_rows: np.ndarray,
    model_date_to_pos: dict[pd.Timestamp, int],
    sample_on_rebalance_dates: bool,
    df_model_all: pd.DataFrame,
    all_dates_full: np.ndarray,
    label_horizon_days: int,
    label_horizon_mode: str,
    label_horizon_gap: float | None,
    label_shift_days: int,
    purge_days_cfg: int | None,
    embargo_days_cfg: int,
    test_size: float,
    final_oos_enabled: bool,
    final_oos_size_raw: object | None,
    train_window_mode: str,
    train_window_size: int | None,
    train_window_unit: str,
) -> dict[str, Any]:
    rebalance_gap_days = None
    if sample_on_rebalance_dates:
        sample_dates = sorted(df_model_all["trade_date"].unique())
        if len(sample_dates) >= 2:
            rebalance_gap_days = estimate_rebalance_gap(all_dates_full, sample_dates)
            if np.isfinite(rebalance_gap_days):
                logger.info(
                    "Sample-on-rebalance enabled: median gap %.1f trade days.",
                    rebalance_gap_days,
                )

    label_horizon_effective = label_horizon_days
    if label_horizon_mode == "next_rebalance" and label_horizon_gap is not None:
        if np.isfinite(label_horizon_gap):
            label_horizon_effective = int(round(label_horizon_gap))
    if purge_days_cfg is None:
        purge_days = int(label_horizon_effective + label_shift_days)
    else:
        purge_days = int(purge_days_cfg)
    _warn_if_purge_too_small(
        purge_days_cfg=purge_days_cfg,
        purge_days=purge_days,
        label_horizon_effective=label_horizon_effective,
        label_shift_days=label_shift_days,
    )
    embargo_days = int(embargo_days_cfg)

    if sample_on_rebalance_dates:
        purge_steps = _days_to_steps(purge_days, rebalance_gap_days)
        embargo_steps = _days_to_steps(embargo_days, rebalance_gap_days)
        if rebalance_gap_days is not None and np.isfinite(rebalance_gap_days):
            logger.info(
                "Converted embargo/purge from days to rebalance steps: "
                "embargo=%s->%s, purge=%s->%s (gap≈%.1f days).",
                embargo_days,
                embargo_steps,
                purge_days,
                purge_steps,
                rebalance_gap_days,
            )
        else:
            logger.warning(
                "Sample-on-rebalance enabled but rebalance gap could not be estimated; "
                "using raw embargo/purge values as steps."
            )
    else:
        purge_steps = purge_days
        embargo_steps = embargo_days

    effective_gap_steps = max(embargo_steps, purge_steps)

    df_model = df_model_all
    df_model_oos = pd.DataFrame()
    final_oos_dates = np.array([], dtype="datetime64[ns]")
    final_oos_len = 0
    final_oos_start = None
    final_oos_end = None
    if final_oos_enabled:
        final_oos_len = _resolve_holdout_len(final_oos_size_raw, len(all_dates_model_full))
        if final_oos_len <= 0:
            final_oos_enabled = False
        elif final_oos_len >= len(all_dates_model_full):
            sys.exit("eval.final_oos.size leaves no in-sample dates.")
        else:
            final_oos_start_pos = len(all_dates_model_full) - final_oos_len
            final_oos_dates = all_dates_model_full[-final_oos_len:]
            final_oos_start = pd.to_datetime(final_oos_dates[0])
            final_oos_end = pd.to_datetime(final_oos_dates[-1])
            df_model_oos = _slice_trade_date_range(
                df_model_all_sorted,
                model_date_start_rows,
                model_date_end_rows,
                final_oos_start_pos,
                len(all_dates_model_full) - 1,
            )
            df_model = _slice_trade_date_range(
                df_model_all_sorted,
                model_date_start_rows,
                model_date_end_rows,
                0,
                final_oos_start_pos - 1,
            )
            logger.info(
                "Final OOS holdout enabled: %s dates (%s -> %s).",
                final_oos_len,
                final_oos_start.strftime("%Y-%m-%d"),
                final_oos_end.strftime("%Y-%m-%d"),
            )

    logger.info("Splitting train/test by date ...")
    (
        df_model_sorted,
        all_dates,
        all_date_start_rows,
        all_date_end_rows,
        all_date_to_pos,
    ) = _build_trade_date_slices(df_model)
    if len(all_dates) < 10:
        sys.exit("Not enough dates for a meaningful split.")

    split_idx = int(len(all_dates) * (1 - test_size))
    train_end = split_idx
    if effective_gap_steps > 0:
        train_end = max(0, split_idx - effective_gap_steps)
    train_dates_full = all_dates[:train_end]
    test_dates = all_dates[split_idx:]
    train_df, train_dates = _slice_with_train_window(
        df_model_sorted,
        all_date_start_rows,
        all_date_end_rows,
        all_date_to_pos,
        train_dates_full,
        label="main train split",
        train_window_mode=train_window_mode,
        train_window_size=train_window_size,
        train_window_unit=train_window_unit,
    )
    test_df = _slice_trade_date_range(
        df_model_sorted,
        all_date_start_rows,
        all_date_end_rows,
        split_idx,
        len(all_dates) - 1,
    )

    if train_df.empty or test_df.empty:
        sys.exit("Not enough dates for train/test after embargo.")

    logger.info(
        "Train/test split: train_dates=%s/%s, test_dates=%s, purge_steps=%s, embargo_steps=%s.",
        len(train_dates),
        len(train_dates_full),
        len(test_dates),
        purge_steps,
        embargo_steps,
    )

    return {
        "df_model": df_model,
        "df_model_oos": df_model_oos,
        "final_oos_enabled": final_oos_enabled,
        "final_oos_dates": final_oos_dates,
        "final_oos_len": final_oos_len,
        "final_oos_start": final_oos_start,
        "final_oos_end": final_oos_end,
        "label_horizon_effective": label_horizon_effective,
        "purge_days": purge_days,
        "embargo_days": embargo_days,
        "purge_steps": purge_steps,
        "embargo_steps": embargo_steps,
        "effective_gap_steps": effective_gap_steps,
        "rebalance_gap_days": rebalance_gap_days,
        "df_model_sorted": df_model_sorted,
        "all_dates": all_dates,
        "all_date_start_rows": all_date_start_rows,
        "all_date_end_rows": all_date_end_rows,
        "all_date_to_pos": all_date_to_pos,
        "train_df": train_df,
        "train_dates": train_dates,
        "train_dates_full": train_dates_full,
        "test_df": test_df,
        "test_dates": test_dates,
    }
