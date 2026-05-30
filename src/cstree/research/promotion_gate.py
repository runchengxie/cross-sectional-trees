from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

PROMOTION_STATUSES = ("promotable", "reviewable", "rejected", "non-comparable")

DEFAULT_COMPARABILITY_KEYS = (
    "market",
    "data.provider",
    "universe.mode",
    "universe.by_date_file",
    "label.target_col",
    "label.horizon_days",
    "label.shift_days",
    "label.train_target_transform",
    "features.list",
    "features.exclude",
    "model.type",
    "eval.rebalance_frequency",
    "backtest.rebalance_frequency",
    "backtest.transaction_cost_bps",
    "backtest.execution",
    "data.benchmark_returns_file",
)

DEFAULT_REQUIRED_EVIDENCE = (
    "main_eval",
    "backtest",
    "walk_forward",
    "final_oos",
    "cost_turnover",
)


@dataclass(frozen=True)
class PromotionHardRejections:
    constant_prediction: bool = True
    zero_feature_importance: bool = True
    require_final_oos: bool = True
    min_cv_ic_valid_folds: int = 0
    min_cpcv_path_count: int = 0


@dataclass(frozen=True)
class PromotionSoftThresholds:
    min_eval_ic_ir: float | None = 0.0
    min_eval_long_short: float | None = 0.0
    min_walk_forward_test_ic_mean: float | None = 0.0
    min_final_oos_ic_mean: float | None = 0.0
    min_final_oos_long_short: float | None = 0.0
    min_backtest_sharpe_delta: float | None = 0.0
    min_final_oos_sharpe_delta: float | None = None
    max_backtest_drawdown: float | None = 0.30
    max_backtest_avg_turnover: float | None = 0.70
    max_backtest_avg_cost_drag: float | None = 0.02
    min_cpcv_sharpe_median: float | None = None
    min_cpcv_sharpe_p25: float | None = None
    min_cpcv_positive_sharpe_ratio: float | None = None
    min_cpcv_ic_median: float | None = None
    min_cpcv_long_short_median: float | None = None
    max_cpcv_drawdown_p10: float | None = None
    min_cpcv_sharpe_median_delta: float | None = None
    min_cpcv_sharpe_p25_delta: float | None = None


@dataclass(frozen=True)
class PromotionCPCVConfig:
    baseline_report: Path | None = None
    candidate_report: Path | None = None


@dataclass(frozen=True)
class PromotionGateConfig:
    baseline_run: Path | None = None
    candidate_run: Path | None = None
    comparability_keys: tuple[str, ...] = DEFAULT_COMPARABILITY_KEYS
    required_evidence: tuple[str, ...] = DEFAULT_REQUIRED_EVIDENCE
    hard_rejections: PromotionHardRejections = field(default_factory=PromotionHardRejections)
    soft_thresholds: PromotionSoftThresholds = field(default_factory=PromotionSoftThresholds)
    cpcv: PromotionCPCVConfig = field(default_factory=PromotionCPCVConfig)


def _resolve_path(path_text: str | Path | None) -> Path | None:
    if path_text is None:
        return None
    candidate = Path(path_text).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (Path.cwd() / candidate).resolve()


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Failed to parse YAML config: {path} ({exc})") from exc
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise SystemExit(f"Promotion gate config must be a mapping: {path}")
    return payload


def _coerce_bool(value: Any, *, key: str) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        raise SystemExit(f"Missing boolean value: {key}")
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    raise SystemExit(f"Invalid boolean value for {key}: {value}")


def _coerce_float_or_none(value: Any, *, key: str) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"{key} must be numeric or null.") from exc
    if not np.isfinite(number):
        raise SystemExit(f"{key} must be finite or null.")
    return number


def _coerce_int(value: Any, *, key: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"{key} must be an integer.") from exc
    return number


def _coerce_str_tuple(value: Any, *, key: str, default: tuple[str, ...]) -> tuple[str, ...]:
    if value is None:
        return default
    if isinstance(value, str):
        values = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        values = [str(item).strip() for item in value]
    else:
        raise SystemExit(f"{key} must be a string or list.")
    cleaned = tuple(item for item in values if item)
    if not cleaned:
        raise SystemExit(f"{key} cannot be empty.")
    return cleaned


def load_promotion_gate_config(path_or_payload: str | Path | dict[str, Any]) -> PromotionGateConfig:
    if isinstance(path_or_payload, dict):
        payload = path_or_payload
    else:
        path = _resolve_path(path_or_payload)
        assert path is not None
        payload = _load_yaml(path)
    gate_payload = payload.get("promotion_gate", payload)
    if not isinstance(gate_payload, dict):
        raise SystemExit("promotion_gate must be a mapping.")

    hard_raw = gate_payload.get("hard_rejections") or {}
    if not isinstance(hard_raw, dict):
        raise SystemExit("promotion_gate.hard_rejections must be a mapping.")
    default_hard = PromotionHardRejections()
    hard = PromotionHardRejections(
        constant_prediction=_coerce_bool(
            hard_raw.get("constant_prediction", default_hard.constant_prediction),
            key="hard_rejections.constant_prediction",
        ),
        zero_feature_importance=_coerce_bool(
            hard_raw.get("zero_feature_importance", default_hard.zero_feature_importance),
            key="hard_rejections.zero_feature_importance",
        ),
        require_final_oos=_coerce_bool(
            hard_raw.get("require_final_oos", default_hard.require_final_oos),
            key="hard_rejections.require_final_oos",
        ),
        min_cv_ic_valid_folds=max(
            0,
            _coerce_int(
                hard_raw.get("min_cv_ic_valid_folds", default_hard.min_cv_ic_valid_folds),
                key="hard_rejections.min_cv_ic_valid_folds",
            ),
        ),
        min_cpcv_path_count=max(
            0,
            _coerce_int(
                hard_raw.get("min_cpcv_path_count", default_hard.min_cpcv_path_count),
                key="hard_rejections.min_cpcv_path_count",
            ),
        ),
    )

    soft_raw = gate_payload.get("soft_thresholds") or {}
    if not isinstance(soft_raw, dict):
        raise SystemExit("promotion_gate.soft_thresholds must be a mapping.")
    default_soft = PromotionSoftThresholds()
    soft = PromotionSoftThresholds(
        **{
            field_name: _coerce_float_or_none(
                soft_raw.get(field_name, getattr(default_soft, field_name)),
                key=f"soft_thresholds.{field_name}",
            )
            for field_name in default_soft.__dataclass_fields__
        }
    )
    cpcv_raw = gate_payload.get("cpcv") or {}
    if not isinstance(cpcv_raw, dict):
        raise SystemExit("promotion_gate.cpcv must be a mapping.")
    cpcv_cfg = PromotionCPCVConfig(
        baseline_report=_resolve_path(
            cpcv_raw.get("baseline_report", gate_payload.get("baseline_cpcv_report"))
        ),
        candidate_report=_resolve_path(
            cpcv_raw.get("candidate_report", gate_payload.get("candidate_cpcv_report"))
        ),
    )

    return PromotionGateConfig(
        baseline_run=_resolve_path(gate_payload.get("baseline_run")),
        candidate_run=_resolve_path(gate_payload.get("candidate_run")),
        comparability_keys=_coerce_str_tuple(
            gate_payload.get("comparability_keys"),
            key="comparability_keys",
            default=DEFAULT_COMPARABILITY_KEYS,
        ),
        required_evidence=_coerce_str_tuple(
            gate_payload.get("required_evidence"),
            key="required_evidence",
            default=DEFAULT_REQUIRED_EVIDENCE,
        ),
        hard_rejections=hard,
        soft_thresholds=soft,
        cpcv=cpcv_cfg,
    )


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _load_run(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    summary = _load_json(run_dir / "summary.json")
    config_path = run_dir / "config.used.yml"
    config = {}
    if config_path.exists():
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        config = payload if isinstance(payload, dict) else {}
    return summary, config


def _load_cpcv_summary(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"available": False, "path": None}
    payload = _load_json(path)
    if not payload:
        return {"available": False, "path": str(path)}
    return {
        "available": True,
        "path": str(path),
        "path_count": _to_float(payload.get("path_count")),
        "valid_path_count": _to_float(payload.get("valid_path_count")),
        "sharpe_median": _to_float(payload.get("sharpe_median")),
        "sharpe_p25": _to_float(payload.get("sharpe_p25")),
        "sharpe_min": _to_float(payload.get("sharpe_min")),
        "positive_sharpe_ratio": _to_float(payload.get("positive_sharpe_ratio")),
        "ic_median": _to_float(payload.get("ic_median")),
        "long_short_median": _to_float(payload.get("long_short_median")),
        "max_drawdown_p10": _to_float(payload.get("max_drawdown_p10")),
        "turnover_median": _to_float(payload.get("turnover_median")),
        "cost_drag_median": _to_float(payload.get("cost_drag_median")),
    }


def _get_nested(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for key in path.split("."):
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


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=True, sort_keys=True, default=str)


def _to_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _cv_valid_folds(summary: dict[str, Any]) -> int | None:
    scores = _get_nested(summary, "eval.cv_ic.scores")
    if isinstance(scores, list):
        return sum(1 for score in scores if _to_float(score) is not None)
    return 1 if _to_float(_get_nested(summary, "eval.cv_ic.mean")) is not None else 0


def _walk_forward_test_ic_mean(summary: dict[str, Any]) -> float | None:
    results = _get_nested(summary, "walk_forward.results")
    if not isinstance(results, list):
        return None
    values: list[float] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        if str(item.get("status", "")).lower() != "ok":
            continue
        value = _to_float(_get_nested(item, "test_ic.mean"))
        if value is not None:
            values.append(value)
    return float(np.mean(values)) if values else None


def _feature_stability(run_dir: Path, summary: dict[str, Any]) -> dict[str, Any]:
    path_text = _get_nested(summary, "walk_forward.feature_stability_file")
    candidates: list[Path] = []
    if path_text:
        raw = Path(str(path_text)).expanduser()
        candidates.extend([raw if raw.is_absolute() else (run_dir / raw), (Path.cwd() / raw)])
    candidates.append(run_dir / "walk_forward_feature_stability.csv")
    for path in candidates:
        if not path.exists():
            continue
        try:
            frame = pd.read_csv(path)
        except Exception:
            continue
        if frame.empty:
            return {"available": False, "path": str(path), "top_k_hit_rate": None, "nonzero_hit_rate": None}
        return {
            "available": True,
            "path": str(path),
            "top_k_hit_rate": _to_float(frame.get("top_k_hit_rate", pd.Series(dtype=float)).max()),
            "nonzero_hit_rate": _to_float(frame.get("nonzero_hit_rate", pd.Series(dtype=float)).max()),
        }
    return {"available": False, "path": None, "top_k_hit_rate": None, "nonzero_hit_rate": None}


def _evidence(
    run_dir: Path,
    summary: dict[str, Any],
    *,
    cpcv_report: Path | None = None,
) -> dict[str, Any]:
    bt_stats = _get_nested(summary, "backtest.stats") or {}
    final_bt_stats = _get_nested(summary, "final_oos.backtest.stats") or {}
    return {
        "main_eval": {
            "eval_ic_mean": _to_float(_get_nested(summary, "eval.ic.mean")),
            "eval_ic_ir": _to_float(_get_nested(summary, "eval.ic.ir")),
            "eval_long_short": _to_float(_get_nested(summary, "eval.long_short")),
            "cv_ic_valid_folds": _cv_valid_folds(summary),
        },
        "backtest": {
            "sharpe": _to_float(bt_stats.get("sharpe")) if isinstance(bt_stats, dict) else None,
            "max_drawdown": _to_float(bt_stats.get("max_drawdown")) if isinstance(bt_stats, dict) else None,
            "avg_turnover": _to_float(bt_stats.get("avg_turnover")) if isinstance(bt_stats, dict) else None,
            "avg_cost_drag": _to_float(bt_stats.get("avg_cost_drag")) if isinstance(bt_stats, dict) else None,
        },
        "walk_forward": {
            "enabled": bool(_get_nested(summary, "walk_forward.enabled")),
            "test_ic_mean": _walk_forward_test_ic_mean(summary),
            "actual_windows": _get_nested(summary, "walk_forward.actual_windows"),
        },
        "final_oos": {
            "enabled": bool(_get_nested(summary, "final_oos.enabled")),
            "dates": _get_nested(summary, "final_oos.dates"),
            "ic_mean": _to_float(_get_nested(summary, "final_oos.ic.mean")),
            "long_short": _to_float(_get_nested(summary, "final_oos.long_short")),
            "sharpe": _to_float(final_bt_stats.get("sharpe")) if isinstance(final_bt_stats, dict) else None,
            "avg_turnover": _to_float(final_bt_stats.get("avg_turnover")) if isinstance(final_bt_stats, dict) else None,
            "avg_cost_drag": _to_float(final_bt_stats.get("avg_cost_drag")) if isinstance(final_bt_stats, dict) else None,
        },
        "feature_stability": _feature_stability(run_dir, summary),
        "benchmark": {
            "active_information_ratio": _to_float(_get_nested(summary, "backtest.active.information_ratio")),
            "benchmark_compare_file": _get_nested(summary, "backtest.benchmark_compare.summary_file"),
        },
        "cpcv": _load_cpcv_summary(cpcv_report),
    }


def _missing_evidence(evidence: dict[str, Any], required: tuple[str, ...]) -> list[str]:
    missing: list[str] = []
    for category in required:
        if category == "main_eval":
            if evidence["main_eval"]["eval_ic_ir"] is None and evidence["main_eval"]["eval_ic_mean"] is None:
                missing.append(category)
        elif category == "backtest":
            if evidence["backtest"]["sharpe"] is None:
                missing.append(category)
        elif category == "walk_forward":
            if evidence["walk_forward"]["test_ic_mean"] is None:
                missing.append(category)
        elif category == "final_oos":
            if not evidence["final_oos"]["enabled"] or evidence["final_oos"]["ic_mean"] is None:
                missing.append(category)
        elif category == "cost_turnover":
            if evidence["backtest"]["avg_turnover"] is None or evidence["backtest"]["avg_cost_drag"] is None:
                missing.append(category)
        elif category == "feature_stability":
            if not evidence["feature_stability"]["available"]:
                missing.append(category)
        elif category == "benchmark":
            if evidence["benchmark"]["active_information_ratio"] is None:
                missing.append(category)
        elif category == "cpcv":
            if not evidence["cpcv"]["available"]:
                missing.append(category)
    return missing


def _comparability(
    baseline_config: dict[str, Any],
    candidate_config: dict[str, Any],
    keys: tuple[str, ...],
) -> tuple[bool, list[str]]:
    mismatches: list[str] = []
    for key in keys:
        left = _get_nested(baseline_config, key)
        right = _get_nested(candidate_config, key)
        if _norm(left) != _norm(right):
            mismatches.append(key)
    return not mismatches, mismatches


def _soft_failures(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    thresholds: PromotionSoftThresholds,
) -> list[str]:
    failures: list[str] = []

    checks = (
        ("min_eval_ic_ir", candidate["main_eval"]["eval_ic_ir"], thresholds.min_eval_ic_ir, ">="),
        (
            "min_eval_long_short",
            candidate["main_eval"]["eval_long_short"],
            thresholds.min_eval_long_short,
            ">=",
        ),
        (
            "min_walk_forward_test_ic_mean",
            candidate["walk_forward"]["test_ic_mean"],
            thresholds.min_walk_forward_test_ic_mean,
            ">=",
        ),
        ("min_final_oos_ic_mean", candidate["final_oos"]["ic_mean"], thresholds.min_final_oos_ic_mean, ">="),
        (
            "min_final_oos_long_short",
            candidate["final_oos"]["long_short"],
            thresholds.min_final_oos_long_short,
            ">=",
        ),
        (
            "max_backtest_drawdown",
            None if candidate["backtest"]["max_drawdown"] is None else abs(candidate["backtest"]["max_drawdown"]),
            thresholds.max_backtest_drawdown,
            "<=",
        ),
        (
            "max_backtest_avg_turnover",
            candidate["backtest"]["avg_turnover"],
            thresholds.max_backtest_avg_turnover,
            "<=",
        ),
        (
            "max_backtest_avg_cost_drag",
            candidate["backtest"]["avg_cost_drag"],
            thresholds.max_backtest_avg_cost_drag,
            "<=",
        ),
        (
            "min_cpcv_sharpe_median",
            candidate["cpcv"].get("sharpe_median"),
            thresholds.min_cpcv_sharpe_median,
            ">=",
        ),
        (
            "min_cpcv_sharpe_p25",
            candidate["cpcv"].get("sharpe_p25"),
            thresholds.min_cpcv_sharpe_p25,
            ">=",
        ),
        (
            "min_cpcv_positive_sharpe_ratio",
            candidate["cpcv"].get("positive_sharpe_ratio"),
            thresholds.min_cpcv_positive_sharpe_ratio,
            ">=",
        ),
        (
            "min_cpcv_ic_median",
            candidate["cpcv"].get("ic_median"),
            thresholds.min_cpcv_ic_median,
            ">=",
        ),
        (
            "min_cpcv_long_short_median",
            candidate["cpcv"].get("long_short_median"),
            thresholds.min_cpcv_long_short_median,
            ">=",
        ),
        (
            "max_cpcv_drawdown_p10",
            candidate["cpcv"].get("max_drawdown_p10"),
            thresholds.max_cpcv_drawdown_p10,
            "<=",
        ),
    )
    for name, value, threshold, op in checks:
        if threshold is None:
            continue
        if value is None or (op == ">=" and value < threshold) or (op == "<=" and value > threshold):
            failures.append(name)

    if thresholds.min_backtest_sharpe_delta is not None:
        base = baseline["backtest"]["sharpe"]
        cand = candidate["backtest"]["sharpe"]
        if base is None or cand is None or cand - base < thresholds.min_backtest_sharpe_delta:
            failures.append("min_backtest_sharpe_delta")

    if thresholds.min_final_oos_sharpe_delta is not None:
        base = baseline["final_oos"]["sharpe"]
        cand = candidate["final_oos"]["sharpe"]
        if base is None or cand is None or cand - base < thresholds.min_final_oos_sharpe_delta:
            failures.append("min_final_oos_sharpe_delta")

    if thresholds.min_cpcv_sharpe_median_delta is not None:
        base = baseline["cpcv"].get("sharpe_median")
        cand = candidate["cpcv"].get("sharpe_median")
        if base is None or cand is None or cand - base < thresholds.min_cpcv_sharpe_median_delta:
            failures.append("min_cpcv_sharpe_median_delta")

    if thresholds.min_cpcv_sharpe_p25_delta is not None:
        base = baseline["cpcv"].get("sharpe_p25")
        cand = candidate["cpcv"].get("sharpe_p25")
        if base is None or cand is None or cand - base < thresholds.min_cpcv_sharpe_p25_delta:
            failures.append("min_cpcv_sharpe_p25_delta")

    return failures


def build_promotion_record(config: PromotionGateConfig) -> dict[str, Any]:
    if config.baseline_run is None or config.candidate_run is None:
        raise SystemExit("Promotion gate requires baseline_run and candidate_run.")
    baseline_summary, baseline_config = _load_run(config.baseline_run)
    candidate_summary, candidate_config = _load_run(config.candidate_run)

    comparable, mismatches = _comparability(
        baseline_config,
        candidate_config,
        config.comparability_keys,
    )
    baseline_evidence = _evidence(
        config.baseline_run,
        baseline_summary,
        cpcv_report=config.cpcv.baseline_report,
    )
    candidate_evidence = _evidence(
        config.candidate_run,
        candidate_summary,
        cpcv_report=config.cpcv.candidate_report,
    )
    missing = _missing_evidence(candidate_evidence, config.required_evidence)

    hard_failures: list[str] = []
    hard = config.hard_rejections
    if hard.constant_prediction and _bool(_get_nested(candidate_summary, "eval.constant_prediction")):
        hard_failures.append("constant_prediction")
    if hard.zero_feature_importance and _bool(_get_nested(candidate_summary, "eval.zero_feature_importance")):
        hard_failures.append("zero_feature_importance")
    if hard.require_final_oos and "final_oos" in missing:
        hard_failures.append("missing_final_oos")
    valid_folds = candidate_evidence["main_eval"]["cv_ic_valid_folds"]
    if hard.min_cv_ic_valid_folds > 0 and (valid_folds or 0) < hard.min_cv_ic_valid_folds:
        hard_failures.append("insufficient_cv_ic_valid_folds")
    if hard.min_cpcv_path_count > 0:
        cpcv_paths = candidate_evidence["cpcv"]["valid_path_count"]
        if cpcv_paths is None or cpcv_paths < hard.min_cpcv_path_count:
            hard_failures.append("insufficient_cpcv_path_count")

    soft_failures = _soft_failures(baseline_evidence, candidate_evidence, config.soft_thresholds)

    if not comparable:
        status = "non-comparable"
    elif hard_failures or missing:
        status = "rejected"
    elif soft_failures:
        status = "reviewable"
    else:
        status = "promotable"

    return {
        "baseline_run": str(config.baseline_run),
        "candidate_run": str(config.candidate_run),
        "promotion_status": status,
        "is_comparable": comparable,
        "comparability_mismatches": mismatches,
        "missing_evidence": missing,
        "hard_failures": hard_failures,
        "soft_failures": soft_failures,
        "config": {
            **asdict(config),
            "baseline_run": str(config.baseline_run),
            "candidate_run": str(config.candidate_run),
        },
        "baseline_evidence": baseline_evidence,
        "candidate_evidence": candidate_evidence,
    }


def flatten_promotion_record(record: dict[str, Any]) -> dict[str, Any]:
    cand = record.get("candidate_evidence") or {}
    base = record.get("baseline_evidence") or {}
    return {
        "baseline_run": record.get("baseline_run"),
        "candidate_run": record.get("candidate_run"),
        "promotion_status": record.get("promotion_status"),
        "is_comparable": record.get("is_comparable"),
        "comparability_mismatches": "|".join(record.get("comparability_mismatches") or []),
        "missing_evidence": "|".join(record.get("missing_evidence") or []),
        "hard_failures": "|".join(record.get("hard_failures") or []),
        "soft_failures": "|".join(record.get("soft_failures") or []),
        "baseline_backtest_sharpe": _get_nested(base, "backtest.sharpe"),
        "candidate_backtest_sharpe": _get_nested(cand, "backtest.sharpe"),
        "candidate_eval_ic_ir": _get_nested(cand, "main_eval.eval_ic_ir"),
        "candidate_walk_forward_test_ic_mean": _get_nested(cand, "walk_forward.test_ic_mean"),
        "candidate_final_oos_ic_mean": _get_nested(cand, "final_oos.ic_mean"),
        "candidate_final_oos_long_short": _get_nested(cand, "final_oos.long_short"),
        "candidate_backtest_avg_turnover": _get_nested(cand, "backtest.avg_turnover"),
        "candidate_backtest_avg_cost_drag": _get_nested(cand, "backtest.avg_cost_drag"),
        "baseline_cpcv_sharpe_median": _get_nested(base, "cpcv.sharpe_median"),
        "baseline_cpcv_sharpe_p25": _get_nested(base, "cpcv.sharpe_p25"),
        "candidate_cpcv_path_count": _get_nested(cand, "cpcv.path_count"),
        "candidate_cpcv_valid_path_count": _get_nested(cand, "cpcv.valid_path_count"),
        "candidate_cpcv_sharpe_median": _get_nested(cand, "cpcv.sharpe_median"),
        "candidate_cpcv_sharpe_p25": _get_nested(cand, "cpcv.sharpe_p25"),
        "candidate_cpcv_sharpe_min": _get_nested(cand, "cpcv.sharpe_min"),
        "candidate_cpcv_positive_sharpe_ratio": _get_nested(cand, "cpcv.positive_sharpe_ratio"),
        "candidate_cpcv_ic_median": _get_nested(cand, "cpcv.ic_median"),
        "candidate_cpcv_long_short_median": _get_nested(cand, "cpcv.long_short_median"),
        "candidate_cpcv_max_drawdown_p10": _get_nested(cand, "cpcv.max_drawdown_p10"),
        "candidate_cpcv_turnover_median": _get_nested(cand, "cpcv.turnover_median"),
        "candidate_cpcv_cost_drag_median": _get_nested(cand, "cpcv.cost_drag_median"),
    }


def write_promotion_report(
    record: dict[str, Any],
    *,
    output_json: str | Path | None = None,
    output_csv: str | Path | None = None,
) -> None:
    if output_json:
        path = _resolve_path(output_json)
        assert path is not None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, ensure_ascii=True, indent=2, default=str), encoding="utf-8")
    if output_csv:
        path = _resolve_path(output_csv)
        assert path is not None
        path.parent.mkdir(parents=True, exist_ok=True)
        row = flatten_promotion_record(record)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(row))
            writer.writeheader()
            writer.writerow(row)


def add_promotion_gate_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--config", required=True, help="Promotion gate YAML config.")
    parser.add_argument("--baseline-run", default=None, help="Override baseline run directory.")
    parser.add_argument("--candidate-run", default=None, help="Override candidate run directory.")
    parser.add_argument("--output-json", default=None, help="Output JSON report path.")
    parser.add_argument("--output-csv", default=None, help="Output CSV report path.")
    return parser


def run(args: argparse.Namespace) -> int:
    cfg = load_promotion_gate_config(args.config)
    payload = asdict(cfg)
    if args.baseline_run:
        payload["baseline_run"] = args.baseline_run
    if args.candidate_run:
        payload["candidate_run"] = args.candidate_run
    cfg = load_promotion_gate_config(payload)
    record = build_promotion_record(cfg)
    write_promotion_report(record, output_json=args.output_json, output_csv=args.output_csv)
    if not args.output_json and not args.output_csv:
        print(json.dumps(record, ensure_ascii=True, indent=2, default=str))
    return 0
