from __future__ import annotations

from pathlib import Path

from ..backtest import backtest_topk
from ..metrics import bucket_ic_summary
from .dates import build_walk_forward_windows
from .eval import build_benchmark_series
from .runner import main as _main
from .runner import run as _run
from .support import load_universe_by_date


def run(
    config_ref: str | Path | None = None,
    *,
    fail_on_quality: str | None = None,
    artifacts_root: str | Path | None = None,
) -> None:
    if fail_on_quality is None and artifacts_root is None:
        _run(config_ref)
        return
    _run(
        config_ref,
        fail_on_quality=fail_on_quality,
        artifacts_root=artifacts_root,
    )


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
