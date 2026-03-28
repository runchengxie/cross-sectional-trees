from __future__ import annotations

from pathlib import Path

from ..backtest import backtest_topk
from ..metrics import bucket_ic_summary
from .dates import build_walk_forward_windows
from .eval import build_benchmark_series
from .runner import main as _main
from .runner import run as _run
from .support import load_universe_by_date


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
]
