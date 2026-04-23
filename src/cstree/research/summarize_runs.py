from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import re
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from ..artifacts import RUNS_DIR as DEFAULT_RUNS_DIR
from ..date_utils import is_relative_date_token
from ..sharpe_stats import annualized_sharpe_to_periodic, deflated_sharpe_ratio

RUN_DIR_PATTERN = re.compile(
    r"^(?P<run_name>.+)_(?P<timestamp>\d{8}_\d{6})_(?P<config_hash>[0-9a-fA-F]{8})$"
)
RUN_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"
DATETIME_PARSE_FORMATS = (
    RUN_TIMESTAMP_FORMAT,
    "%Y%m%d",
    "%Y-%m-%d",
    "%Y%m%d%H%M%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
)

FIELDNAMES = [
    "source_runs_dir",
    "run_dir",
    "run_name",
    "run_timestamp",
    "config_hash",
    "summary_path",
    "config_path",
    "inputs_lock_path",
    "provenance_source",
    "provenance_has_lock",
    "provenance_used_relative_start_date",
    "provenance_used_relative_end_date",
    "provenance_used_relative_live_as_of",
    "provenance_used_latest_pointer",
    "provenance_input_keys",
    "provenance_inputs_json",
    "provenance_cohort_key",
    "comparability_class",
    "comparability_reasons",
    "market",
    "data_provider",
    "data_start_date",
    "data_end_date",
    "data_end_date_config",
    "data_rows",
    "data_rows_model",
    "data_rows_model_in_sample",
    "data_rows_model_oos",
    "data_dropped_dates",
    "universe_mode",
    "label_horizon_days",
    "label_shift_days",
    "eval_top_k",
    "backtest_top_k",
    "transaction_cost_bps",
    "eval_rebalance_frequency",
    "backtest_rebalance_frequency",
    "backtest_exit_price_policy",
    "backtest_exit_fallback_policy",
    "backtest_weighting",
    "eval_buffer_exit",
    "eval_buffer_entry",
    "backtest_buffer_exit",
    "backtest_buffer_entry",
    "eval_ic_mean",
    "eval_ic_ir",
    "eval_long_short",
    "eval_turnover_mean",
    "walk_forward_test_ic_mean",
    "eval_pred_nunique",
    "feature_importance_nonzero",
    "backtest_periods",
    "backtest_periods_per_year",
    "backtest_total_return",
    "backtest_ann_return",
    "backtest_ann_vol",
    "backtest_sharpe",
    "backtest_skew",
    "backtest_kurtosis_excess",
    "backtest_max_drawdown",
    "backtest_avg_turnover",
    "backtest_avg_cost_drag",
    "backtest_tracking_error",
    "backtest_information_ratio",
    "backtest_beta",
    "backtest_alpha",
    "backtest_corr",
    "dsr",
    "dsr_sr0",
    "dsr_n_trials",
    "dsr_var_trials",
    "flag_short_sample",
    "flag_negative_long_short",
    "flag_high_turnover",
    "flag_high_cost_drag",
    "flag_relative_end_date",
    "flag_constant_prediction",
    "flag_zero_feature_importance",
    "objective_component_eval_ic_ir",
    "objective_component_walk_forward_test_ic_mean",
    "objective_component_backtest_sharpe",
    "objective_component_drawdown_penalty",
    "objective_component_cost_drag_penalty",
    "objective_component_turnover_penalty",
    "objective_score",
    "score",
    "status",
    "error",
]

DSR_GROUP_FIELDS = (
    "market",
    "label_horizon_days",
    "backtest_rebalance_frequency",
    "backtest_exit_price_policy",
    "backtest_weighting",
    "transaction_cost_bps",
    "backtest_top_k",
    "comparability_class",
    "provenance_cohort_key",
)

COMPARABILITY_CLASSES = ("direct", "risky", "unknown")
RELEVANT_PROVENANCE_INPUT_KEYS = (
    "daily_asset_dir",
    "instruments_file",
    "ex_factors_dir",
    "universe_by_date_file",
    "fundamentals_file",
    "industry_file",
    "benchmark_returns_file",
)

def _resolve_path(path_text: str | Path) -> Path:
    candidate = Path(path_text).expanduser()
    if candidate.is_absolute():
        return candidate
    return (Path.cwd() / candidate).resolve()


def _get_nested(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _to_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(parsed):
        return None
    return parsed


def _is_true_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y", "on"}


def _is_relative_end_date(value: Any) -> bool | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return is_relative_date_token(text, default="today")


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _json_dumps_compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(np.mean(values))


def _parse_datetime_text(value: str) -> datetime | None:
    text = str(value).strip()
    if not text:
        return None
    for fmt in DATETIME_PARSE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _parse_run_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    return _parse_datetime_text(str(value))


def _parse_since(value: str | None) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    lowered = text.lower()
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if lowered in {"today", "now"}:
        return today
    if lowered in {"yesterday", "t-1"}:
        return today - timedelta(days=1)
    parsed = _parse_datetime_text(text)
    if parsed is None:
        raise SystemExit(
            "Invalid --since value. Supported formats: "
            "YYYYMMDD, YYYY-MM-DD, YYYYMMDD_HHMMSS, YYYY-MM-DDTHH:MM:SS"
        )
    return parsed


def _parse_prefixes(values: list[str] | None) -> list[str]:
    prefixes: list[str] = []
    for entry in values or []:
        for part in str(entry).split(","):
            text = part.strip()
            if text:
                prefixes.append(text)
    return list(dict.fromkeys(prefixes))


def _parse_run_dir_name(run_dir_name: str) -> tuple[str | None, str | None, str | None]:
    match = RUN_DIR_PATTERN.match(run_dir_name)
    if not match:
        return None, None, None
    return match.group("run_name"), match.group("timestamp"), match.group("config_hash")


def _resolve_artifact_path(
    run_dir: Path,
    *,
    path_value: Any = None,
    default_name: str | None = None,
) -> Path | None:
    candidates: list[Path] = []
    if path_value is not None:
        text = str(path_value).strip()
        if text:
            raw = Path(text).expanduser()
            if raw.is_absolute():
                candidates.append(raw)
            else:
                candidates.append((run_dir / raw).resolve())
                candidates.append((Path.cwd() / raw).resolve())
    if default_name:
        candidates.append((run_dir / default_name).resolve())
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists():
            return candidate
    return None


def _load_eval_pred_nunique(run_dir: Path, summary: dict[str, Any]) -> int | None:
    pred_nunique = _to_float(_get_nested(summary, "eval", "pred_nunique"))
    if pred_nunique is not None:
        return int(pred_nunique)

    scored_path = _resolve_artifact_path(
        run_dir,
        path_value=_get_nested(summary, "eval", "scored_file"),
        default_name="eval_scored.parquet",
    )
    if scored_path is None:
        return None
    try:
        scored = pd.read_parquet(scored_path, columns=["pred"])
    except Exception as exc:
        logging.debug("Unable to read scored artifact %s: %s", scored_path, exc)
        return None
    if "pred" not in scored.columns:
        return None
    return int(scored["pred"].nunique(dropna=True))


def _load_feature_importance_nonzero(run_dir: Path, summary: dict[str, Any]) -> int | None:
    nonzero = _to_float(_get_nested(summary, "eval", "feature_importance_nonzero"))
    if nonzero is not None:
        return int(nonzero)

    importance_path = _resolve_artifact_path(
        run_dir,
        path_value=_get_nested(summary, "eval", "feature_importance_file"),
        default_name="feature_importance.csv",
    )
    if importance_path is None:
        return None
    try:
        importance = pd.read_csv(importance_path, usecols=["importance"])
    except Exception as exc:
        logging.debug("Unable to read feature importance artifact %s: %s", importance_path, exc)
        return None
    if "importance" not in importance.columns:
        return None
    values = pd.to_numeric(importance["importance"], errors="coerce").fillna(0.0)
    return int((values.abs() > 0.0).sum())


def _populate_eval_diagnostics(
    row: dict[str, Any],
    summary: dict[str, Any],
    run_dir: Path,
) -> None:
    pred_nunique = _load_eval_pred_nunique(run_dir, summary)
    if pred_nunique is not None:
        row["eval_pred_nunique"] = pred_nunique

    constant_prediction = _first_non_empty(
        _get_nested(summary, "eval", "constant_prediction"),
        None if pred_nunique is None else pred_nunique <= 1,
    )
    if constant_prediction is not None:
        row["flag_constant_prediction"] = bool(constant_prediction)

    feature_importance_nonzero = _load_feature_importance_nonzero(run_dir, summary)
    if feature_importance_nonzero is not None:
        row["feature_importance_nonzero"] = feature_importance_nonzero

    zero_feature_importance = _first_non_empty(
        _get_nested(summary, "eval", "zero_feature_importance"),
        None if feature_importance_nonzero is None else feature_importance_nonzero <= 0,
    )
    if zero_feature_importance is not None:
        row["flag_zero_feature_importance"] = bool(zero_feature_importance)


def _iter_summary_files(runs_dirs: list[Path]) -> list[tuple[Path, Path]]:
    entries: list[tuple[Path, Path]] = []
    seen: set[Path] = set()
    for root in runs_dirs:
        if not root.exists():
            logging.warning("Runs dir not found; skip: %s", root)
            continue
        if not root.is_dir():
            logging.warning("Runs dir is not a directory; skip: %s", root)
            continue
        for summary_path in root.rglob("summary.json"):
            if not summary_path.is_file():
                continue
            resolved = summary_path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            entries.append((root, resolved))
    entries.sort(key=lambda item: item[1].stat().st_mtime, reverse=True)
    return entries


def _load_summary(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("summary.json top-level payload must be an object")
    return payload


def _load_used_config(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {}, None
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        return {}, f"config_parse_error: {exc}"
    if payload is None:
        return {}, None
    if not isinstance(payload, dict):
        return {}, "config_parse_error: config.used.yml top-level payload must be an object"
    return payload, None


def _extract_walk_forward_test_ic_mean(summary: dict[str, Any]) -> float | None:
    results = _get_nested(summary, "walk_forward", "results")
    if not isinstance(results, list):
        return None
    values: list[float] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        if str(item.get("status") or "").strip().lower() != "ok":
            continue
        value = _to_float(_get_nested(item, "test_ic", "mean"))
        if value is not None:
            values.append(value)
    return _mean(values)


def _load_inputs_lock(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        return None, f"inputs_lock_parse_error: {exc}"
    if not isinstance(payload, dict):
        return None, "inputs_lock_parse_error: inputs.lock.json top-level payload must be an object"
    return payload, None


def _normalize_manifest_summary(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    normalized: dict[str, Any] = {}
    for key in ("dataset", "status", "snapshot_name", "query_end_date", "output_dir"):
        text = _normalize_text(payload.get(key))
        if text is not None:
            normalized[key] = text
    return normalized or None


def _normalize_current_contract_summary(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    normalized: dict[str, Any] = {}
    for key in ("contract_name", "asset_key", "as_of"):
        text = _normalize_text(payload.get(key))
        if text is not None:
            normalized[key] = text
    return normalized or None


def _normalize_input_resolution_entry(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    normalized: dict[str, Any] = {}
    for key in ("raw", "configured_path", "resolved_path", "path_kind"):
        text = _normalize_text(payload.get(key))
        if text is not None:
            normalized[key] = text
    for key in ("exists", "is_symlink", "points_to_latest_name"):
        if key in payload and payload.get(key) is not None:
            normalized[key] = bool(payload.get(key))
    manifest = _normalize_manifest_summary(payload.get("manifest"))
    if manifest is not None:
        normalized["manifest"] = manifest
    current_contract = _normalize_current_contract_summary(payload.get("current_contract"))
    if current_contract is not None:
        normalized["current_contract"] = current_contract
    return normalized or None


def _extract_relevant_input_provenance(inputs_lock: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(inputs_lock, Mapping):
        return {}
    input_resolution = (
        inputs_lock.get("input_resolution")
        if isinstance(inputs_lock.get("input_resolution"), Mapping)
        else {}
    )
    normalized: dict[str, dict[str, Any]] = {}
    for key in RELEVANT_PROVENANCE_INPUT_KEYS:
        entry = _normalize_input_resolution_entry(input_resolution.get(key))
        if entry is not None:
            normalized[key] = entry
    return normalized


def _build_provenance_cohort_key(
    inputs_lock: Mapping[str, Any] | None,
    normalized_inputs: Mapping[str, Mapping[str, Any]],
) -> str | None:
    if not isinstance(inputs_lock, Mapping):
        return None
    resolved_dates_payload = (
        inputs_lock.get("resolved_dates")
        if isinstance(inputs_lock.get("resolved_dates"), Mapping)
        else {}
    )
    resolved_dates = {
        key: text
        for key in ("start_date", "end_date", "live_as_of")
        if (text := _normalize_text(resolved_dates_payload.get(key))) is not None
    }
    identities: dict[str, dict[str, Any]] = {}
    for key, entry in normalized_inputs.items():
        identity: dict[str, Any] = {}
        resolved_path = _normalize_text(entry.get("resolved_path"))
        if resolved_path is not None:
            identity["resolved_path"] = resolved_path
        manifest = entry.get("manifest") if isinstance(entry.get("manifest"), Mapping) else {}
        for field in ("dataset", "snapshot_name", "query_end_date"):
            text = _normalize_text(manifest.get(field))
            if text is not None:
                identity[field] = text
        current_contract = (
            entry.get("current_contract") if isinstance(entry.get("current_contract"), Mapping) else {}
        )
        for field in ("asset_key", "as_of"):
            text = _normalize_text(current_contract.get(field))
            if text is not None:
                identity[f"current_{field}"] = text
        if identity:
            identities[key] = identity
    if not resolved_dates and not identities:
        return None
    payload = {"resolved_dates": resolved_dates, "inputs": identities}
    return hashlib.md5(_json_dumps_compact(payload).encode("utf-8")).hexdigest()[:12]


def _classify_comparability(
    *,
    inputs_lock_path: Path,
    inputs_lock: Mapping[str, Any] | None,
    normalized_inputs: Mapping[str, Mapping[str, Any]],
) -> tuple[str, list[str]]:
    if not inputs_lock_path.exists():
        return "unknown", ["legacy_no_inputs_lock"]
    if not isinstance(inputs_lock, Mapping):
        return "unknown", ["inputs_lock_parse_error"]

    reasons: list[str] = []
    mutable_inputs = (
        inputs_lock.get("mutable_inputs")
        if isinstance(inputs_lock.get("mutable_inputs"), Mapping)
        else {}
    )
    mutable_reason_map = (
        ("used_relative_start_date", "relative_start_date"),
        ("used_relative_end_date", "relative_end_date"),
        ("used_relative_live_as_of", "relative_live_as_of"),
        ("used_latest_pointer", "used_latest_pointer"),
    )
    for field, reason in mutable_reason_map:
        if mutable_inputs.get(field) is not None and bool(mutable_inputs.get(field)):
            reasons.append(reason)

    unknown_reasons: list[str] = []
    resolved_inputs = inputs_lock.get("inputs") if isinstance(inputs_lock.get("inputs"), Mapping) else {}
    input_resolution = (
        inputs_lock.get("input_resolution")
        if isinstance(inputs_lock.get("input_resolution"), Mapping)
        else {}
    )
    for key in RELEVANT_PROVENANCE_INPUT_KEYS:
        if _normalize_text(resolved_inputs.get(key)) is None and key not in input_resolution:
            continue
        entry = normalized_inputs.get(key)
        if entry is None:
            unknown_reasons.append(f"missing_resolution_{key}")
            continue
        if _normalize_text(entry.get("resolved_path")) is None:
            unknown_reasons.append(f"missing_resolved_{key}")

    all_reasons = sorted(dict.fromkeys(reasons + unknown_reasons))
    if unknown_reasons:
        return "unknown", all_reasons
    if reasons:
        return "risky", all_reasons
    return "direct", []


def _populate_provenance(
    row: dict[str, Any],
    *,
    run_dir: Path,
    inputs_lock: Mapping[str, Any] | None,
) -> None:
    inputs_lock_path = run_dir / "inputs.lock.json"
    row["inputs_lock_path"] = str(inputs_lock_path) if inputs_lock_path.exists() else None
    row["provenance_source"] = "inputs_lock" if inputs_lock_path.exists() else "legacy"
    row["provenance_has_lock"] = inputs_lock_path.exists()

    if not isinstance(inputs_lock, Mapping):
        comparability_class, reasons = _classify_comparability(
            inputs_lock_path=inputs_lock_path,
            inputs_lock=inputs_lock,
            normalized_inputs={},
        )
        row["comparability_class"] = comparability_class
        row["comparability_reasons"] = "|".join(reasons) if reasons else None
        return

    mutable_inputs = (
        inputs_lock.get("mutable_inputs")
        if isinstance(inputs_lock.get("mutable_inputs"), Mapping)
        else {}
    )
    for field in (
        "used_relative_start_date",
        "used_relative_end_date",
        "used_relative_live_as_of",
        "used_latest_pointer",
    ):
        value = mutable_inputs.get(field)
        if value is not None:
            row[f"provenance_{field}"] = bool(value)

    normalized_inputs = _extract_relevant_input_provenance(inputs_lock)
    if normalized_inputs:
        row["provenance_input_keys"] = "|".join(sorted(normalized_inputs))
        row["provenance_inputs_json"] = json.dumps(
            normalized_inputs,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    row["provenance_cohort_key"] = _build_provenance_cohort_key(inputs_lock, normalized_inputs)
    comparability_class, reasons = _classify_comparability(
        inputs_lock_path=inputs_lock_path,
        inputs_lock=inputs_lock,
        normalized_inputs=normalized_inputs,
    )
    row["comparability_class"] = comparability_class
    row["comparability_reasons"] = "|".join(reasons) if reasons else None


def _init_row(source_runs_dir: Path, summary_path: Path) -> dict[str, Any]:
    row = {field: None for field in FIELDNAMES}
    row["source_runs_dir"] = str(source_runs_dir)
    row["summary_path"] = str(summary_path)
    row["run_dir"] = str(summary_path.parent)
    row["config_path"] = str(summary_path.parent / "config.used.yml")
    row["status"] = "ok"
    return row


def _apply_flags_and_score(row: dict[str, Any], args: argparse.Namespace) -> None:
    periods = _to_float(row.get("backtest_periods"))
    if periods is not None:
        row["flag_short_sample"] = periods < float(args.short_sample_periods)

    eval_long_short = _to_float(row.get("eval_long_short"))
    if eval_long_short is not None:
        row["flag_negative_long_short"] = eval_long_short < 0.0

    bt_turnover = _to_float(row.get("backtest_avg_turnover"))
    if bt_turnover is not None:
        row["flag_high_turnover"] = bt_turnover > float(args.high_turnover_threshold)

    bt_cost_drag = _to_float(row.get("backtest_avg_cost_drag"))
    if bt_cost_drag is not None:
        row["flag_high_cost_drag"] = bt_cost_drag > float(args.high_cost_drag_threshold)

    end_date_relative = row.get("provenance_used_relative_end_date")
    if end_date_relative is None:
        end_date_source = _first_non_empty(
            row.get("data_end_date_config"),
            row.get("data_end_date"),
        )
        end_date_relative = _is_relative_end_date(end_date_source)
    if end_date_relative is not None:
        row["flag_relative_end_date"] = end_date_relative

    if _is_true_flag(row.get("flag_constant_prediction")) or _is_true_flag(
        row.get("flag_zero_feature_importance")
    ):
        row["score"] = None
        return

    sharpe = _to_float(row.get("backtest_sharpe"))
    if sharpe is None:
        return
    max_drawdown = _to_float(row.get("backtest_max_drawdown"))
    avg_cost_drag = _to_float(row.get("backtest_avg_cost_drag"))
    eval_ic_ir = _to_float(row.get("eval_ic_ir"))
    wf_test_ic = _to_float(row.get("walk_forward_test_ic_mean"))
    avg_turnover = _to_float(row.get("backtest_avg_turnover"))
    drawdown_penalty = abs(max_drawdown) if max_drawdown is not None else 0.0
    cost_penalty = avg_cost_drag if avg_cost_drag is not None else 0.0
    turnover_penalty = avg_turnover if avg_turnover is not None else 0.0
    row["objective_component_eval_ic_ir"] = float(args.score_eval_ic_ir_weight) * (
        eval_ic_ir or 0.0
    )
    row["objective_component_walk_forward_test_ic_mean"] = (
        float(args.score_walk_forward_weight) * (wf_test_ic or 0.0)
    )
    row["objective_component_backtest_sharpe"] = (
        float(args.score_backtest_sharpe_weight) * sharpe
    )
    row["objective_component_drawdown_penalty"] = float(args.score_drawdown_weight) * drawdown_penalty
    row["objective_component_cost_drag_penalty"] = float(args.score_cost_weight) * cost_penalty
    row["objective_component_turnover_penalty"] = (
        float(args.score_turnover_weight) * turnover_penalty
    )
    row["score"] = (
        row["objective_component_eval_ic_ir"]
        + row["objective_component_walk_forward_test_ic_mean"]
        + row["objective_component_backtest_sharpe"]
        - row["objective_component_drawdown_penalty"]
        - row["objective_component_cost_drag_penalty"]
        - row["objective_component_turnover_penalty"]
    )
    row["objective_score"] = row["score"]


def _normalize_group_value(value: Any) -> Any:
    if value is None:
        return None
    numeric = _to_float(value)
    if numeric is not None and np.isfinite(numeric):
        if float(numeric).is_integer():
            return int(numeric)
        return float(numeric)
    if isinstance(value, str):
        text = value.strip()
        return text.lower() if text else None
    return value


def _dsr_group_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(_normalize_group_value(row.get(field)) for field in DSR_GROUP_FIELDS)


def _compute_grouped_dsr(rows: list[dict[str, Any]]) -> None:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(_dsr_group_key(row), []).append(row)

    for group_rows in grouped.values():
        n_trials = len(group_rows)
        periodic_sharpes: list[float] = []
        for row in group_rows:
            sharpe_ann = _to_float(row.get("backtest_sharpe"))
            periods_per_year = _to_float(row.get("backtest_periods_per_year"))
            sharpe = annualized_sharpe_to_periodic(sharpe_ann, periods_per_year)
            if np.isfinite(sharpe):
                periodic_sharpes.append(float(sharpe))
        var_trials = (
            float(np.var(periodic_sharpes, ddof=1))
            if len(periodic_sharpes) >= 2
            else np.nan
        )

        for row in group_rows:
            row["dsr_n_trials"] = n_trials
            row["dsr_var_trials"] = var_trials if np.isfinite(var_trials) else None
            if _is_true_flag(row.get("flag_short_sample")):
                continue
            if _is_true_flag(row.get("flag_constant_prediction")) or _is_true_flag(
                row.get("flag_zero_feature_importance")
            ):
                continue

            periods = _to_float(row.get("backtest_periods"))
            sharpe_ann = _to_float(row.get("backtest_sharpe"))
            periods_per_year = _to_float(row.get("backtest_periods_per_year"))
            sharpe = annualized_sharpe_to_periodic(sharpe_ann, periods_per_year)
            if periods is None or periods <= 1:
                continue
            if not np.isfinite(sharpe):
                continue

            skew = _to_float(row.get("backtest_skew"))
            kurtosis_excess = _to_float(row.get("backtest_kurtosis_excess"))
            skew_value = float(skew) if skew is not None and np.isfinite(skew) else 0.0
            kurtosis_value = (
                float(kurtosis_excess)
                if kurtosis_excess is not None and np.isfinite(kurtosis_excess)
                else 0.0
            )
            dsr, sr0 = deflated_sharpe_ratio(
                sharpe=float(sharpe),
                periods=periods,
                skew=skew_value,
                kurtosis_excess=kurtosis_value,
                n_trials=n_trials,
                var_sharpe=var_trials,
            )
            if np.isfinite(dsr):
                row["dsr"] = dsr
            if np.isfinite(sr0):
                row["dsr_sr0"] = sr0


def _extract_row(source_runs_dir: Path, summary_path: Path, args: argparse.Namespace) -> dict[str, Any]:
    row = _init_row(source_runs_dir, summary_path)
    errors: list[str] = []
    try:
        summary = _load_summary(summary_path)
    except Exception as exc:
        row["status"] = "failed"
        row["error"] = f"summary_parse_error: {exc}"
        return row

    run_dir = summary_path.parent
    config_path = run_dir / "config.used.yml"
    config, config_error = _load_used_config(config_path)
    if config_error:
        errors.append(config_error)
    inputs_lock_path = run_dir / "inputs.lock.json"
    inputs_lock, inputs_lock_error = _load_inputs_lock(inputs_lock_path)
    if inputs_lock_error:
        errors.append(inputs_lock_error)
    _populate_provenance(row, run_dir=run_dir, inputs_lock=inputs_lock)

    fallback_name, fallback_timestamp, fallback_hash = _parse_run_dir_name(run_dir.name)

    row["run_name"] = _first_non_empty(
        _get_nested(summary, "run", "name"),
        fallback_name,
    )
    row["run_timestamp"] = _first_non_empty(
        _get_nested(summary, "run", "timestamp"),
        fallback_timestamp,
    )
    row["config_hash"] = _first_non_empty(
        _get_nested(summary, "run", "config_hash"),
        fallback_hash,
    )

    row["market"] = _first_non_empty(
        _get_nested(summary, "data", "market"),
        config.get("market") if isinstance(config, dict) else None,
    )
    row["data_provider"] = _first_non_empty(
        _get_nested(summary, "data", "provider"),
        _get_nested(config, "data", "provider"),
    )
    row["data_start_date"] = _first_non_empty(
        _get_nested(summary, "data", "start_date"),
        _get_nested(config, "data", "start_date"),
    )
    row["data_end_date_config"] = _get_nested(config, "data", "end_date")
    row["data_end_date"] = _first_non_empty(
        _get_nested(summary, "data", "end_date"),
        row["data_end_date_config"],
    )
    row["data_rows"] = _get_nested(summary, "data", "rows")
    row["data_rows_model"] = _get_nested(summary, "data", "rows_model")
    row["data_rows_model_in_sample"] = _get_nested(summary, "data", "rows_model_in_sample")
    row["data_rows_model_oos"] = _get_nested(summary, "data", "rows_model_oos")
    row["data_dropped_dates"] = _get_nested(summary, "data", "dropped_dates")
    row["universe_mode"] = _first_non_empty(
        _get_nested(summary, "universe", "mode"),
        _get_nested(config, "universe", "mode"),
    )

    row["label_horizon_days"] = _first_non_empty(
        _get_nested(summary, "label", "horizon_days"),
        _get_nested(config, "label", "horizon_days"),
    )
    row["label_shift_days"] = _first_non_empty(
        _get_nested(summary, "label", "shift_days"),
        _get_nested(config, "label", "shift_days"),
    )

    row["eval_top_k"] = _first_non_empty(
        _get_nested(summary, "eval", "top_k"),
        _get_nested(config, "eval", "top_k"),
    )
    row["backtest_top_k"] = _first_non_empty(
        _get_nested(summary, "backtest", "top_k"),
        _get_nested(config, "backtest", "top_k"),
        row["eval_top_k"],
    )
    row["transaction_cost_bps"] = _first_non_empty(
        _get_nested(summary, "backtest", "transaction_cost_bps"),
        _get_nested(config, "backtest", "transaction_cost_bps"),
        _get_nested(config, "eval", "transaction_cost_bps"),
    )
    row["eval_rebalance_frequency"] = _first_non_empty(
        _get_nested(summary, "eval", "rebalance_frequency"),
        _get_nested(config, "eval", "rebalance_frequency"),
    )
    row["backtest_rebalance_frequency"] = _first_non_empty(
        _get_nested(summary, "backtest", "rebalance_frequency"),
        _get_nested(config, "backtest", "rebalance_frequency"),
        row["eval_rebalance_frequency"],
    )
    row["backtest_exit_price_policy"] = _first_non_empty(
        _get_nested(summary, "backtest", "exit_price_policy"),
        _get_nested(config, "backtest", "exit_price_policy"),
    )
    row["backtest_exit_fallback_policy"] = _first_non_empty(
        _get_nested(summary, "backtest", "exit_fallback_policy"),
        _get_nested(config, "backtest", "exit_fallback_policy"),
    )
    row["backtest_weighting"] = _first_non_empty(
        _get_nested(summary, "backtest", "weighting"),
        _get_nested(config, "backtest", "weighting"),
        "equal",
    )
    row["eval_buffer_exit"] = _first_non_empty(
        _get_nested(summary, "eval", "buffer_exit"),
        _get_nested(config, "eval", "buffer_exit"),
    )
    row["eval_buffer_entry"] = _first_non_empty(
        _get_nested(summary, "eval", "buffer_entry"),
        _get_nested(config, "eval", "buffer_entry"),
    )
    row["backtest_buffer_exit"] = _first_non_empty(
        _get_nested(summary, "backtest", "buffer_exit"),
        _get_nested(config, "backtest", "buffer_exit"),
        row["eval_buffer_exit"],
    )
    row["backtest_buffer_entry"] = _first_non_empty(
        _get_nested(summary, "backtest", "buffer_entry"),
        _get_nested(config, "backtest", "buffer_entry"),
        row["eval_buffer_entry"],
    )

    row["eval_ic_mean"] = _get_nested(summary, "eval", "ic", "mean")
    row["eval_ic_ir"] = _get_nested(summary, "eval", "ic", "ir")
    row["eval_long_short"] = _get_nested(summary, "eval", "long_short")
    row["eval_turnover_mean"] = _get_nested(summary, "eval", "turnover_mean")
    row["walk_forward_test_ic_mean"] = _extract_walk_forward_test_ic_mean(summary)
    _populate_eval_diagnostics(row, summary, run_dir)

    backtest_stats = _get_nested(summary, "backtest", "stats")
    if isinstance(backtest_stats, dict):
        row["backtest_periods"] = backtest_stats.get("periods")
        row["backtest_periods_per_year"] = backtest_stats.get("periods_per_year")
        row["backtest_total_return"] = backtest_stats.get("total_return")
        row["backtest_ann_return"] = backtest_stats.get("ann_return")
        row["backtest_ann_vol"] = backtest_stats.get("ann_vol")
        row["backtest_sharpe"] = backtest_stats.get("sharpe")
        row["backtest_skew"] = backtest_stats.get("skew")
        row["backtest_kurtosis_excess"] = backtest_stats.get("kurtosis")
        row["backtest_max_drawdown"] = backtest_stats.get("max_drawdown")
        row["backtest_avg_turnover"] = backtest_stats.get("avg_turnover")
        row["backtest_avg_cost_drag"] = backtest_stats.get("avg_cost_drag")
    else:
        row["status"] = "no_backtest"

    backtest_active = _get_nested(summary, "backtest", "active")
    if isinstance(backtest_active, dict):
        row["backtest_tracking_error"] = backtest_active.get("tracking_error")
        row["backtest_information_ratio"] = backtest_active.get("information_ratio")
        row["backtest_beta"] = backtest_active.get("beta")
        row["backtest_alpha"] = backtest_active.get("alpha")
        row["backtest_corr"] = backtest_active.get("corr")

    _apply_flags_and_score(row, args)
    if errors:
        row["error"] = "; ".join(errors)
    return row


def _resolve_output_path(args: argparse.Namespace, runs_dirs: list[Path]) -> Path:
    if args.output:
        return _resolve_path(args.output)
    default_root = (
        runs_dirs[0]
        if runs_dirs
        else _resolve_path(DEFAULT_RUNS_DIR)
    )
    return default_root / "runs_summary.csv"


def add_summarize_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument(
        "--runs-dir",
        action="append",
        default=None,
        help=(
            "Root directory to scan recursively for run folders (repeatable). "
            f"Default: {DEFAULT_RUNS_DIR.as_posix()}"
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output CSV path (default: <first-runs-dir>/runs_summary.csv)",
    )
    parser.add_argument(
        "--run-name-prefix",
        action="append",
        default=None,
        help=(
            "Only include runs whose run_name starts with this prefix "
            "(repeatable, supports comma-separated values)"
        ),
    )
    parser.add_argument(
        "--since",
        default=None,
        help=(
            "Only include runs at/after this run timestamp. Supported: "
            "YYYYMMDD, YYYY-MM-DD, YYYYMMDD_HHMMSS, YYYY-MM-DDTHH:MM:SS"
        ),
    )
    parser.add_argument(
        "--latest-n",
        type=int,
        default=None,
        help="Keep only the latest N runs after applying filters",
    )
    parser.add_argument(
        "--short-sample-periods",
        type=int,
        default=24,
        help="Flag short sample when backtest_periods is below this value (default: 24)",
    )
    parser.add_argument(
        "--high-turnover-threshold",
        type=float,
        default=0.7,
        help="Flag high turnover when backtest_avg_turnover exceeds this value (default: 0.7)",
    )
    parser.add_argument(
        "--high-cost-drag-threshold",
        type=float,
        default=0.02,
        help="Flag high cost drag when backtest_avg_cost_drag exceeds this value (default: 0.02)",
    )
    parser.add_argument(
        "--score-eval-ic-ir-weight",
        type=float,
        default=0.0,
        help="Score reward weight for eval_ic_ir (default: 0.0 to preserve legacy score behavior)",
    )
    parser.add_argument(
        "--score-walk-forward-weight",
        type=float,
        default=0.0,
        help=(
            "Score reward weight for walk_forward_test_ic_mean "
            "(default: 0.0 to preserve legacy score behavior)"
        ),
    )
    parser.add_argument(
        "--score-backtest-sharpe-weight",
        type=float,
        default=1.0,
        help="Score reward weight for backtest_sharpe (default: 1.0)",
    )
    parser.add_argument(
        "--score-drawdown-weight",
        type=float,
        default=0.5,
        help="Score penalty weight for |max_drawdown| (default: 0.5)",
    )
    parser.add_argument(
        "--score-cost-weight",
        type=float,
        default=10.0,
        help="Score penalty weight for avg_cost_drag (default: 10.0)",
    )
    parser.add_argument(
        "--score-turnover-weight",
        type=float,
        default=0.0,
        help="Score penalty weight for backtest_avg_turnover (default: 0.0)",
    )
    parser.add_argument(
        "--exclude-flag-short-sample",
        action="store_true",
        help="Exclude rows where flag_short_sample=true",
    )
    parser.add_argument(
        "--exclude-flag-high-turnover",
        action="store_true",
        help="Exclude rows where flag_high_turnover=true",
    )
    parser.add_argument(
        "--exclude-flag-high-cost-drag",
        action="store_true",
        help="Exclude rows where flag_high_cost_drag=true",
    )
    parser.add_argument(
        "--exclude-flag-negative-long-short",
        action="store_true",
        help="Exclude rows where flag_negative_long_short=true",
    )
    parser.add_argument(
        "--exclude-flag-relative-end-date",
        action="store_true",
        help="Exclude rows where data.end_date uses relative tokens such as today/t-1",
    )
    parser.add_argument(
        "--exclude-flag-constant-prediction",
        action="store_true",
        help="Exclude rows where flag_constant_prediction=true",
    )
    parser.add_argument(
        "--exclude-flag-zero-feature-importance",
        action="store_true",
        help="Exclude rows where flag_zero_feature_importance=true",
    )
    parser.add_argument(
        "--comparability-class",
        action="append",
        default=None,
        help=(
            "Only include runs whose comparability_class matches these values "
            f"(repeatable, supports comma-separated values; available: {', '.join(COMPARABILITY_CLASSES)})"
        ),
    )
    parser.add_argument(
        "--sort-by",
        default="timestamp",
        choices=["timestamp", "score", "dsr"],
        help="Sort rows by run timestamp, score, or DSR (default: timestamp)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Logging level",
    )
    return parser


def _allowed_comparability_classes(args: argparse.Namespace) -> set[str]:
    comparability_classes = _parse_prefixes(args.comparability_class)
    invalid_classes = [
        item for item in comparability_classes if item.lower() not in COMPARABILITY_CLASSES
    ]
    if invalid_classes:
        raise SystemExit(
            "Invalid --comparability-class value(s): "
            + ", ".join(sorted(dict.fromkeys(invalid_classes)))
            + f". Available: {', '.join(COMPARABILITY_CLASSES)}"
        )
    return {item.lower() for item in comparability_classes}


def _filter_candidates(
    candidates: list[tuple[datetime, dict[str, Any]]],
    args: argparse.Namespace,
    allowed_comparability_classes: set[str],
) -> list[tuple[datetime, dict[str, Any]]]:
    flag_filters = (
        ("exclude_flag_short_sample", "flag_short_sample"),
        ("exclude_flag_high_turnover", "flag_high_turnover"),
        ("exclude_flag_high_cost_drag", "flag_high_cost_drag"),
        ("exclude_flag_negative_long_short", "flag_negative_long_short"),
        ("exclude_flag_relative_end_date", "flag_relative_end_date"),
        ("exclude_flag_constant_prediction", "flag_constant_prediction"),
        ("exclude_flag_zero_feature_importance", "flag_zero_feature_importance"),
    )
    rows = candidates
    for arg_name, field_name in flag_filters:
        if getattr(args, arg_name):
            rows = [item for item in rows if not _is_true_flag(item[1].get(field_name))]
    if allowed_comparability_classes:
        rows = [
            item
            for item in rows
            if _normalize_text(item[1].get("comparability_class")) in allowed_comparability_classes
        ]
    return rows


def _sort_candidates(
    candidates: list[tuple[datetime, dict[str, Any]]],
    sort_by: str,
) -> None:
    if sort_by == "score":
        candidates.sort(
            key=lambda item: (
                _to_float(item[1].get("score")) is None,
                -(_to_float(item[1].get("score")) or 0.0),
                -item[0].timestamp(),
            )
        )
    elif sort_by == "dsr":
        candidates.sort(
            key=lambda item: (
                _to_float(item[1].get("dsr")) is None,
                -(_to_float(item[1].get("dsr")) or 0.0),
                -item[0].timestamp(),
            )
        )
    else:
        candidates.sort(key=lambda item: item[0], reverse=True)


def run(args: argparse.Namespace) -> Path:
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(levelname)s: %(message)s",
    )
    if args.latest_n is not None and int(args.latest_n) <= 0:
        raise SystemExit("--latest-n must be a positive integer.")

    runs_dirs = [
        _resolve_path(path)
        for path in (args.runs_dir or [DEFAULT_RUNS_DIR.as_posix()])
    ]
    run_name_prefixes = _parse_prefixes(args.run_name_prefix)
    allowed_comparability_classes = _allowed_comparability_classes(args)
    since_dt = _parse_since(args.since)
    summary_entries = _iter_summary_files(runs_dirs)
    if not summary_entries:
        targets = ", ".join(str(path) for path in runs_dirs)
        raise SystemExit(f"No summary.json files found under: {targets}")

    output_path = _resolve_output_path(args, runs_dirs)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for source_dir, summary_path in summary_entries:
        row = _extract_row(source_dir, summary_path, args)
        run_name = str(row.get("run_name") or "")
        if run_name_prefixes and not any(
            run_name.startswith(prefix) for prefix in run_name_prefixes
        ):
            continue
        row_dt = _parse_run_timestamp(row.get("run_timestamp"))
        if row_dt is None:
            row_dt = datetime.fromtimestamp(summary_path.stat().st_mtime)
        if since_dt is not None and row_dt < since_dt:
            continue
        candidates.append((row_dt, row))

    if not candidates:
        raise SystemExit("No runs matched current summarize filters.")

    candidates = _filter_candidates(candidates, args, allowed_comparability_classes)
    if not candidates:
        raise SystemExit("No runs matched current summarize filters.")

    _compute_grouped_dsr([row for _, row in candidates])

    _sort_candidates(candidates, str(args.sort_by))
    if args.latest_n is not None:
        candidates = candidates[: int(args.latest_n)]
    rows = [row for _, row in candidates]

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    logging.info("Summary written to %s (%d runs)", output_path, len(rows))
    return output_path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Summarize saved run results from summary.json + config.used.yml + inputs.lock.json"
    )
    add_summarize_args(parser)
    args = parser.parse_args(argv)
    run(args)


if __name__ == "__main__":
    main()
