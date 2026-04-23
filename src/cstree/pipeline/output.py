from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .output_artifacts import write_run_artifacts
from .output_summary import build_run_summary, write_run_metadata


def persist_run_outputs(*, context: Mapping[str, Any]) -> None:
    if not context["SAVE_ARTIFACTS"]:
        return

    artifacts = write_run_artifacts(context=context)
    summary = build_run_summary(context=context, artifacts=artifacts)
    write_run_metadata(context=context, summary=summary)
