from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .output_summary_metadata import write_run_metadata
from .output_summary_sections import build_run_summary_sections


def build_run_summary(
    *,
    context: Mapping[str, Any],
    artifacts: Mapping[str, Any],
) -> dict[str, Any]:
    return build_run_summary_sections(context=context, artifacts=artifacts)


__all__ = ["build_run_summary", "write_run_metadata"]
