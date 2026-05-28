from __future__ import annotations

"""Compatibility surface for backtesting APIs.

This module keeps the historical `cstree.backtest` import path stable while the
implementation is split into `cstree.backtesting.*`.
"""

from .backtesting.engine import backtest_topk
from .backtesting.metrics import summarize_period_returns

__all__ = ["backtest_topk", "summarize_period_returns"]
