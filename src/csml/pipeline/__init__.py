from __future__ import annotations

from pathlib import Path

from ..backtest import backtest_topk
from ..metrics import bucket_ic_summary
from .dates import (
    _build_trade_date_slices,
    _slice_trade_date_range,
    _slice_trade_dates,
    build_walk_forward_windows,
)
from .eval import _warn_if_delay_exit_lag, build_benchmark_series
from .runner import main as _main
from .runner import run as _run
from .stats import _ensure_execution_daily_fields, _warn_if_purge_too_small
from .support import _annotate_positions_window, _build_rebalance_diff, load_universe_by_date


def run(config_ref: str | Path | None = None) -> None:
    _run(config_ref)


def main(argv: list[str] | None = None) -> None:
    _main(argv)


__all__ = [
    "run",
    "main",
    "backtest_topk",
    "bucket_ic_summary",
    "build_benchmark_series",
    "build_walk_forward_windows",
    "load_universe_by_date",
    "_annotate_positions_window",
    "_build_rebalance_diff",
    "_build_trade_date_slices",
    "_ensure_execution_daily_fields",
    "_slice_trade_date_range",
    "_slice_trade_dates",
    "_warn_if_delay_exit_lag",
    "_warn_if_purge_too_small",
]
