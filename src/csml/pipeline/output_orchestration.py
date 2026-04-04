from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .output import persist_run_outputs
from .output_context import build_output_context


def persist_pipeline_outputs(
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
    market: str,
    artifacts_root: Path,
    cache_dir: Path,
    provider: str,
    quality_summary: Mapping[str, Any],
    benchmark_symbol: str | None,
    benchmark_returns_file_path: Path | None,
    benchmark_compare_specs: list[dict[str, Any]],
    label_horizon_mode: str,
    final_oos_enabled: bool,
    final_oos_size_raw: int | float | str | None,
    purge_steps: int,
    embargo_steps: int,
    effective_gap_steps: int,
    backtest_group_col: str | None,
    train_eval_state: Mapping[str, Any],
    final_oos_state: Mapping[str, Any],
) -> None:
    extras: dict[str, Any] = {
        "MARKET": market,
        "ARTIFACTS_ROOT": artifacts_root,
        "CACHE_DIR": cache_dir,
        "provider": provider,
        "quality_summary": quality_summary,
        "benchmark_symbol": benchmark_symbol,
        "benchmark_returns_file_path": benchmark_returns_file_path,
        "benchmark_compare_specs": benchmark_compare_specs,
        "LABEL_HORIZON_MODE": label_horizon_mode,
        "FINAL_OOS_ENABLED": final_oos_enabled,
        "FINAL_OOS_SIZE_RAW": final_oos_size_raw,
        "PURGE_STEPS": purge_steps,
        "EMBARGO_STEPS": embargo_steps,
        "EFFECTIVE_GAP_STEPS": effective_gap_steps,
        "BACKTEST_GROUP_COL": backtest_group_col,
        "SIGNAL_DIRECTION": train_eval_state.get("signal_direction"),
        "BACKTEST_SIGNAL_DIRECTION": train_eval_state.get("backtest_signal_direction"),
        "LIVE_AS_OF": train_eval_state.get("live_as_of"),
    }
    extras.update(train_eval_state)
    extras.update(final_oos_state)

    output_context = build_output_context(
        loaded=loaded,
        universe_inputs=universe_inputs,
        date_label_settings=date_label_settings,
        eval_settings=eval_settings,
        universe_filters=universe_filters,
        runtime_settings=runtime_settings,
        run_artifacts=run_artifacts,
        panel_state=panel_state,
        dataset_state=dataset_state,
        split_state=split_state,
        extras=extras,
    )
    persist_run_outputs(context=output_context)
