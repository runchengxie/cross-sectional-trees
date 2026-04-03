from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def build_output_context(
    *,
    loaded: Mapping[str, Any],
    universe_inputs: Mapping[str, Any],
    date_label_settings: Mapping[str, Any],
    eval_settings: Mapping[str, Any],
    universe_filters: Mapping[str, Any],
    runtime_settings: Mapping[str, Any],
    run_artifacts: Mapping[str, Any],
    panel_state: Mapping[str, Any],
    dataset_state: Mapping[str, Any],
    split_state: Mapping[str, Any],
    extras: Mapping[str, Any],
) -> dict[str, Any]:
    context: dict[str, Any] = {}
    for source in (
        loaded,
        universe_inputs,
        date_label_settings,
        eval_settings,
        universe_filters,
        runtime_settings,
        run_artifacts,
        panel_state,
        dataset_state,
        split_state,
        extras,
    ):
        context.update(source)
    return context
