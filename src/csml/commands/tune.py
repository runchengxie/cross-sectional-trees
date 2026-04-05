from __future__ import annotations

import argparse
import copy
import csv
import itertools
import json
import logging
import math
import random
import shutil
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from ..artifacts import RUNS_DIR as DEFAULT_RUNS_DIR, SWEEPS_DIR as DEFAULT_SWEEPS_DIR_PATH
from ..config_utils import resolve_pipeline_config

DEFAULT_SWEEPS_DIR = DEFAULT_SWEEPS_DIR_PATH.as_posix()
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_RANDOM_TRIALS = 20
DEFAULT_SAMPLER = "grid"


@dataclass(frozen=True)
class TuneChoice:
    label: str
    overrides: dict[str, Any]


@dataclass(frozen=True)
class TuneDimension:
    name: str
    choices: list[TuneChoice]


@dataclass(frozen=True)
class TuneJob:
    order: int
    run_name: str
    config_path: Path
    dimension_labels: dict[str, str]
    overrides: dict[str, Any]


@dataclass(frozen=True)
class ObjectiveSpec:
    eval_ic_ir_weight: float = 1.0
    walk_forward_test_ic_mean_weight: float = 0.5
    backtest_sharpe_weight: float = 0.5
    drawdown_penalty_weight: float = 0.25
    cost_drag_penalty_weight: float = 5.0
    turnover_penalty_weight: float = 0.1
    drop_degenerate: bool = True
    min_cv_ic_valid_folds: int = 0


def _resolve_path(path_text: str | Path) -> Path:
    candidate = Path(path_text).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (Path.cwd() / candidate).resolve()


def _default_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _load_yaml_mapping(path: Path, *, label: str) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"{label} not found: {path}")
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Failed to parse {label}: {path} ({exc})") from exc
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise SystemExit(f"{label} root must be a mapping: {path}")
    return payload


def _load_tune_spec(path_text: str | None) -> tuple[dict[str, Any], Path | None]:
    if path_text is None:
        return {}, None
    path = _resolve_path(path_text)
    payload = _load_yaml_mapping(path, label="Tune config")
    return payload, path


def _spec_lookup(spec: dict[str, Any], key: str, section: str | None = None) -> Any:
    if key in spec:
        return spec.get(key)
    if section:
        block = spec.get(section)
        if isinstance(block, dict) and key in block:
            return block.get(key)
    return None


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _coerce_bool(value: Any, *, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        raise SystemExit(f"Missing boolean value: {field_name}")
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    raise SystemExit(f"Invalid boolean value for {field_name}: {value}")


def _ensure_mapping(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        value = {}
        parent[key] = value
    return value


def _format_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return format(value, ".12g")
    return str(value)


def _normalize_choice_label(value: Any) -> str:
    text = _format_scalar(value).strip()
    return text if text else "choice"


def _normalize_dimension_name(raw_name: Any, *, fallback: str) -> str:
    text = str(raw_name or "").strip()
    return text if text else fallback


def _normalize_choice(
    choice_raw: Any,
    *,
    path: str | None,
    dimension_name: str,
    index: int,
) -> TuneChoice:
    if isinstance(choice_raw, dict):
        label_raw = choice_raw.get("label")
        value_present = "value" in choice_raw
        value = choice_raw.get("value")
        overrides_raw = choice_raw.get("overrides")
        if overrides_raw is not None and not isinstance(overrides_raw, dict):
            raise SystemExit(
                f"search_space[{dimension_name}] choice #{index} overrides must be a mapping."
            )
        overrides = {str(key): copy.deepcopy(val) for key, val in (overrides_raw or {}).items()}
        if path is not None and value_present:
            overrides = {path: copy.deepcopy(value), **overrides}
        if path is None and not overrides:
            raise SystemExit(
                f"search_space[{dimension_name}] choice #{index} requires overrides when path is omitted."
            )
        if path is not None and not value_present and not overrides:
            raise SystemExit(
                f"search_space[{dimension_name}] choice #{index} requires either value or overrides."
            )
        label = str(label_raw).strip() if label_raw is not None else ""
        if not label:
            if value_present:
                label = _normalize_choice_label(value)
            elif len(overrides) == 1:
                label = _normalize_choice_label(next(iter(overrides.values())))
            else:
                label = f"choice_{index}"
        return TuneChoice(label=label, overrides=overrides)

    if path is None:
        raise SystemExit(
            f"search_space[{dimension_name}] scalar choice #{index} requires a dimension path."
        )
    return TuneChoice(
        label=_normalize_choice_label(choice_raw),
        overrides={path: copy.deepcopy(choice_raw)},
    )


def _parse_search_space(search_space_raw: Any) -> list[TuneDimension]:
    if not isinstance(search_space_raw, list) or not search_space_raw:
        raise SystemExit("Tune search_space must be a non-empty list.")

    dimensions: list[TuneDimension] = []
    seen_names: set[str] = set()
    for idx, raw in enumerate(search_space_raw, start=1):
        if not isinstance(raw, dict):
            raise SystemExit(f"search_space item #{idx} must be a mapping.")
        path_raw = raw.get("path")
        path = str(path_raw).strip() if path_raw is not None else None
        if path == "":
            path = None
        name = _normalize_dimension_name(
            raw.get("name"),
            fallback=(path.split(".")[-1] if path else f"dim_{idx}"),
        )
        if name in seen_names:
            raise SystemExit(f"Duplicate tune dimension name: {name}")
        seen_names.add(name)

        values_raw = raw.get("values")
        if not isinstance(values_raw, list) or not values_raw:
            raise SystemExit(f"search_space[{name}] values must be a non-empty list.")
        choices = [
            _normalize_choice(choice_raw, path=path, dimension_name=name, index=choice_idx)
            for choice_idx, choice_raw in enumerate(values_raw, start=1)
        ]
        dimensions.append(TuneDimension(name=name, choices=choices))
    return dimensions


def _merge_choice_overrides(
    dimension_names: list[str],
    selected_choices: tuple[TuneChoice, ...],
) -> tuple[dict[str, str], dict[str, Any]]:
    labels: dict[str, str] = {}
    overrides: dict[str, Any] = {}
    for dimension_name, choice in zip(dimension_names, selected_choices, strict=True):
        labels[dimension_name] = choice.label
        for path, value in choice.overrides.items():
            if path in overrides and overrides[path] != value:
                raise SystemExit(
                    f"Conflicting tune overrides for path {path}: "
                    f"{overrides[path]!r} vs {value!r}."
                )
            overrides[path] = copy.deepcopy(value)
    return labels, overrides


def _enumerate_combinations(dimensions: list[TuneDimension]) -> list[tuple[dict[str, str], dict[str, Any]]]:
    dimension_names = [dimension.name for dimension in dimensions]
    combos: list[tuple[dict[str, str], dict[str, Any]]] = []
    for selected in itertools.product(*(dimension.choices for dimension in dimensions)):
        combos.append(_merge_choice_overrides(dimension_names, selected))
    return combos


def _select_combinations(
    combinations: list[tuple[dict[str, str], dict[str, Any]]],
    *,
    sampler: str,
    n_trials: int | None,
    seed: int,
) -> list[tuple[dict[str, str], dict[str, Any]]]:
    sampler_text = str(sampler or DEFAULT_SAMPLER).strip().lower()
    if sampler_text not in {"grid", "random"}:
        raise SystemExit("sampler must be one of: grid, random.")
    if sampler_text == "grid":
        return list(combinations)

    total = len(combinations)
    if total == 0:
        return []
    trial_count = DEFAULT_RANDOM_TRIALS if n_trials is None else int(n_trials)
    if trial_count < 1:
        raise SystemExit("n_trials must be >= 1.")
    if trial_count >= total:
        return list(combinations)
    rng = random.Random(int(seed))
    selected_idx = sorted(rng.sample(range(total), trial_count))
    return [combinations[idx] for idx in selected_idx]


def _set_nested_value(payload: dict[str, Any], path: str, value: Any) -> None:
    parts = [part.strip() for part in str(path).split(".") if part.strip()]
    if not parts:
        raise SystemExit("Tune override path cannot be empty.")
    current = payload
    for part in parts[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    current[parts[-1]] = copy.deepcopy(value)


def _build_job(
    base_cfg: dict[str, Any],
    *,
    order: int,
    run_name_prefix: str,
    sweep_tag: str,
    config_dir: Path,
    runs_dir_override: str | None,
    dimension_labels: dict[str, str],
    overrides: dict[str, Any],
) -> TuneJob:
    run_name = f"{run_name_prefix}{sweep_tag}_trial_{order:03d}"
    cfg = copy.deepcopy(base_cfg)
    for path, value in overrides.items():
        _set_nested_value(cfg, path, value)

    eval_cfg = _ensure_mapping(cfg, "eval")
    eval_cfg["run_name"] = run_name
    if runs_dir_override is not None:
        eval_cfg["output_dir"] = runs_dir_override

    config_path = config_dir / f"trial_{order:03d}.yml"
    _write_yaml(config_path, cfg)
    return TuneJob(
        order=order,
        run_name=run_name,
        config_path=config_path,
        dimension_labels=dict(dimension_labels),
        overrides=dict(overrides),
    )


def _write_jobs_csv(path: Path, jobs: list[TuneJob], dimension_names: list[str]) -> None:
    fieldnames = ["order", "run_name", "config_path", *dimension_names, "overrides_json"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for job in jobs:
            row = {
                "order": job.order,
                "run_name": job.run_name,
                "config_path": str(job.config_path),
                "overrides_json": json.dumps(job.overrides, ensure_ascii=True, sort_keys=True),
            }
            for name in dimension_names:
                row[name] = job.dimension_labels.get(name)
            writer.writerow(row)


def _write_trial_results_csv(path: Path, rows: list[dict[str, Any]], dimension_names: list[str]) -> None:
    metric_fields = [
        "summary_path",
        "objective_score",
        "eval_ic_ir",
        "eval_cv_ic_mean",
        "eval_cv_ic_valid_folds",
        "eval_cv_ic_total_folds",
        "walk_forward_test_ic_mean",
        "backtest_sharpe",
        "backtest_max_drawdown",
        "backtest_avg_turnover",
        "backtest_avg_cost_drag",
        "flag_constant_prediction",
        "flag_zero_feature_importance",
        "flag_cv_ic_insufficient",
        "status",
        "error",
        "dimensions_json",
    ]
    fieldnames = ["order", "run_name", "config_path", *dimension_names, *metric_fields]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            clean_row = {key: row.get(key) for key in fieldnames if key != "dimensions_json"}
            clean_row["dimensions_json"] = json.dumps(
                row.get("dimensions", {}),
                ensure_ascii=True,
                sort_keys=True,
            )
            writer.writerow(clean_row)


def _find_latest_summary(output_dir: Path, run_name: str, *, min_mtime: float | None = None) -> Path | None:
    pattern = f"{run_name}_*/summary.json"
    candidates = list(output_dir.glob(pattern))
    if min_mtime is not None:
        candidates = [item for item in candidates if item.stat().st_mtime >= min_mtime]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def _get_nested(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _to_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(sum(values) / len(values))


def _to_int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number


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


def _extract_cv_ic_stats(summary: dict[str, Any]) -> tuple[float | None, int | None, int | None]:
    cv_ic_mean = _to_float(_get_nested(summary, "eval", "cv_ic", "mean"))
    cv_scores = _get_nested(summary, "eval", "cv_ic", "scores")
    if isinstance(cv_scores, list):
        total_folds = len(cv_scores)
        valid_folds = sum(1 for score in cv_scores if _to_float(score) is not None)
        return cv_ic_mean, valid_folds, total_folds
    if cv_ic_mean is not None:
        return cv_ic_mean, 1, None
    return None, 0, None


def _parse_objective_spec(spec: dict[str, Any]) -> ObjectiveSpec:
    objective_cfg = spec.get("objective")
    if objective_cfg is None:
        return ObjectiveSpec()
    if not isinstance(objective_cfg, dict):
        raise SystemExit("objective must be a mapping when provided.")

    def _get_number(key: str, default: float) -> float:
        raw = objective_cfg.get(key, default)
        try:
            return float(raw)
        except (TypeError, ValueError) as exc:
            raise SystemExit(f"objective.{key} must be a number.") from exc

    min_cv_ic_valid_folds_raw = objective_cfg.get("min_cv_ic_valid_folds", 0)
    try:
        min_cv_ic_valid_folds = int(min_cv_ic_valid_folds_raw)
    except (TypeError, ValueError) as exc:
        raise SystemExit("objective.min_cv_ic_valid_folds must be an integer.") from exc
    if min_cv_ic_valid_folds < 0:
        raise SystemExit("objective.min_cv_ic_valid_folds must be >= 0.")

    return ObjectiveSpec(
        eval_ic_ir_weight=_get_number("eval_ic_ir_weight", 1.0),
        walk_forward_test_ic_mean_weight=_get_number("walk_forward_test_ic_mean_weight", 0.5),
        backtest_sharpe_weight=_get_number("backtest_sharpe_weight", 0.5),
        drawdown_penalty_weight=_get_number("drawdown_penalty_weight", 0.25),
        cost_drag_penalty_weight=_get_number("cost_drag_penalty_weight", 5.0),
        turnover_penalty_weight=_get_number("turnover_penalty_weight", 0.1),
        drop_degenerate=_coerce_bool(
            objective_cfg.get("drop_degenerate", True),
            field_name="objective.drop_degenerate",
        ),
        min_cv_ic_valid_folds=min_cv_ic_valid_folds,
    )


def _score_summary(summary: dict[str, Any], objective: ObjectiveSpec) -> dict[str, Any]:
    eval_ic_ir = _to_float(_get_nested(summary, "eval", "ic", "ir"))
    eval_cv_ic_mean, eval_cv_ic_valid_folds, eval_cv_ic_total_folds = _extract_cv_ic_stats(summary)
    walk_forward_test_ic_mean = _extract_walk_forward_test_ic_mean(summary)
    backtest_sharpe = _to_float(_get_nested(summary, "backtest", "stats", "sharpe"))
    backtest_max_drawdown = _to_float(_get_nested(summary, "backtest", "stats", "max_drawdown"))
    backtest_avg_turnover = _to_float(_get_nested(summary, "backtest", "stats", "avg_turnover"))
    backtest_avg_cost_drag = _to_float(_get_nested(summary, "backtest", "stats", "avg_cost_drag"))
    flag_constant_prediction = bool(_get_nested(summary, "eval", "constant_prediction") or False)
    flag_zero_feature_importance = bool(_get_nested(summary, "eval", "zero_feature_importance") or False)
    flag_cv_ic_insufficient = (
        objective.min_cv_ic_valid_folds > 0
        and (eval_cv_ic_valid_folds or 0) < objective.min_cv_ic_valid_folds
    )

    objective_score: float | None = None
    if (
        not (objective.drop_degenerate and (flag_constant_prediction or flag_zero_feature_importance))
        and not flag_cv_ic_insufficient
    ):
        if eval_ic_ir is not None:
            objective_score = (
                objective.eval_ic_ir_weight * eval_ic_ir
                + objective.walk_forward_test_ic_mean_weight * (walk_forward_test_ic_mean or 0.0)
                + objective.backtest_sharpe_weight * (backtest_sharpe or 0.0)
                - objective.drawdown_penalty_weight * abs(backtest_max_drawdown or 0.0)
                - objective.cost_drag_penalty_weight * (backtest_avg_cost_drag or 0.0)
                - objective.turnover_penalty_weight * (backtest_avg_turnover or 0.0)
            )

    return {
        "objective_score": objective_score,
        "eval_ic_ir": eval_ic_ir,
        "eval_cv_ic_mean": eval_cv_ic_mean,
        "eval_cv_ic_valid_folds": eval_cv_ic_valid_folds,
        "eval_cv_ic_total_folds": eval_cv_ic_total_folds,
        "walk_forward_test_ic_mean": walk_forward_test_ic_mean,
        "backtest_sharpe": backtest_sharpe,
        "backtest_max_drawdown": backtest_max_drawdown,
        "backtest_avg_turnover": backtest_avg_turnover,
        "backtest_avg_cost_drag": backtest_avg_cost_drag,
        "flag_constant_prediction": flag_constant_prediction,
        "flag_zero_feature_importance": flag_zero_feature_importance,
        "flag_cv_ic_insufficient": flag_cv_ic_insufficient,
    }


def _select_best_result(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    valid = [
        row
        for row in rows
        if row.get("status") == "ok" and _to_float(row.get("objective_score")) is not None
    ]
    if not valid:
        return None
    return max(valid, key=lambda row: float(row["objective_score"]))


def _write_best_trial_files(
    *,
    sweep_dir: Path,
    best_row: dict[str, Any],
) -> None:
    best_payload = {
        "run_name": best_row["run_name"],
        "config_path": best_row["config_path"],
        "summary_path": best_row["summary_path"],
        "objective_score": _to_float(best_row.get("objective_score")),
        "dimensions": best_row.get("dimensions", {}),
        "metrics": {
            "eval_ic_ir": _to_float(best_row.get("eval_ic_ir")),
            "eval_cv_ic_mean": _to_float(best_row.get("eval_cv_ic_mean")),
            "eval_cv_ic_valid_folds": _to_int(best_row.get("eval_cv_ic_valid_folds")),
            "eval_cv_ic_total_folds": _to_int(best_row.get("eval_cv_ic_total_folds")),
            "walk_forward_test_ic_mean": _to_float(best_row.get("walk_forward_test_ic_mean")),
            "backtest_sharpe": _to_float(best_row.get("backtest_sharpe")),
            "backtest_max_drawdown": _to_float(best_row.get("backtest_max_drawdown")),
            "backtest_avg_turnover": _to_float(best_row.get("backtest_avg_turnover")),
            "backtest_avg_cost_drag": _to_float(best_row.get("backtest_avg_cost_drag")),
            "flag_constant_prediction": bool(best_row.get("flag_constant_prediction")),
            "flag_zero_feature_importance": bool(best_row.get("flag_zero_feature_importance")),
            "flag_cv_ic_insufficient": bool(best_row.get("flag_cv_ic_insufficient")),
        },
    }
    best_trial_path = sweep_dir / "best_trial.json"
    best_trial_path.write_text(json.dumps(best_payload, ensure_ascii=True, indent=2), encoding="utf-8")

    best_config_src = _resolve_path(str(best_row["config_path"]))
    shutil.copyfile(best_config_src, sweep_dir / "best_config.yml")


def add_tune_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument(
        "--tune-config",
        default=None,
        help="YAML file for tune search space and options (CLI args override this file)",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Base config path, built-in name, or existing run config.used.yml",
    )
    parser.add_argument(
        "--run-name-prefix",
        default=None,
        help="run_name prefix for generated trials (default: <base-label>_tune_)",
    )
    parser.add_argument(
        "--sweeps-dir",
        default=None,
        help=f"Root directory for tune artifacts (default: {DEFAULT_SWEEPS_DIR})",
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="Tune tag used as subdirectory name and run_name suffix (default: current timestamp)",
    )
    parser.add_argument(
        "--runs-dir",
        default=None,
        help="Override eval.output_dir for generated configs (default: keep base config value)",
    )
    parser.add_argument(
        "--sampler",
        default=None,
        choices=["grid", "random"],
        help="Trial sampler: grid or random (default: from tune-config or grid)",
    )
    parser.add_argument(
        "--n-trials",
        type=int,
        default=None,
        help=f"Number of random trials to sample (default: {DEFAULT_RANDOM_TRIALS} when sampler=random)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed used when sampler=random (default: 42)",
    )
    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Only generate trial configs/jobs.csv; do not run pipeline or summarize",
    )
    parser.add_argument(
        "--continue-on-error",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Continue remaining trials if one run fails",
    )
    parser.add_argument(
        "--skip-summarize",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Skip automatic summarize step after runs",
    )
    parser.add_argument(
        "--summary-output",
        default=None,
        help="Summary CSV path (default: <tune-dir>/runs_summary.csv)",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Logging level",
    )
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    tune_spec, tune_spec_path = _load_tune_spec(args.tune_config)

    base_config_ref = _coalesce(
        args.config,
        _spec_lookup(tune_spec, "base_config"),
        _spec_lookup(tune_spec, "config"),
    )
    if base_config_ref is None:
        raise SystemExit("Tune requires --config or tune-config base_config.")

    sweep_root_text = str(
        _coalesce(
            args.sweeps_dir,
            _spec_lookup(tune_spec, "sweeps_dir"),
            DEFAULT_SWEEPS_DIR,
        )
    )
    tag = _coalesce(
        args.tag,
        _spec_lookup(tune_spec, "tag"),
        _spec_lookup(tune_spec, "tune_tag"),
    )
    runs_dir_override_raw = _coalesce(
        args.runs_dir,
        _spec_lookup(tune_spec, "runs_dir"),
    )
    runs_dir_override = None if runs_dir_override_raw is None else str(runs_dir_override_raw)
    sampler = str(
        _coalesce(
            args.sampler,
            _spec_lookup(tune_spec, "sampler", section="search"),
            _spec_lookup(tune_spec, "sampler"),
            DEFAULT_SAMPLER,
        )
    ).lower()
    n_trials = _coalesce(
        args.n_trials,
        _spec_lookup(tune_spec, "n_trials", section="search"),
        _spec_lookup(tune_spec, "n_trials"),
    )
    seed = int(
        _coalesce(
            args.seed,
            _spec_lookup(tune_spec, "seed", section="search"),
            _spec_lookup(tune_spec, "seed"),
            42,
        )
    )
    dry_run = _coerce_bool(
        _coalesce(
            args.dry_run,
            _spec_lookup(tune_spec, "dry_run", section="options"),
            _spec_lookup(tune_spec, "dry_run"),
            False,
        ),
        field_name="dry_run",
    )
    continue_on_error = _coerce_bool(
        _coalesce(
            args.continue_on_error,
            _spec_lookup(tune_spec, "continue_on_error", section="options"),
            _spec_lookup(tune_spec, "continue_on_error"),
            False,
        ),
        field_name="continue_on_error",
    )
    skip_summarize = _coerce_bool(
        _coalesce(
            args.skip_summarize,
            _spec_lookup(tune_spec, "skip_summarize", section="options"),
            _spec_lookup(tune_spec, "skip_summarize"),
            False,
        ),
        field_name="skip_summarize",
    )
    summary_output_override = _coalesce(
        args.summary_output,
        _spec_lookup(tune_spec, "summary_output", section="options"),
        _spec_lookup(tune_spec, "summary_output"),
    )
    log_level = str(
        _coalesce(
            args.log_level,
            _spec_lookup(tune_spec, "log_level", section="options"),
            _spec_lookup(tune_spec, "log_level"),
            DEFAULT_LOG_LEVEL,
        )
    ).upper()
    if log_level not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
        raise SystemExit(f"Invalid log_level: {log_level}")

    search_space_raw = _coalesce(
        _spec_lookup(tune_spec, "search_space"),
        _spec_lookup(tune_spec, "space", section="search"),
    )
    dimensions = _parse_search_space(search_space_raw)
    objective_spec = _parse_objective_spec(tune_spec)

    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(levelname)s: %(message)s",
    )
    if tune_spec_path:
        logging.info("Loaded tune config: %s", tune_spec_path)

    resolved = resolve_pipeline_config(str(base_config_ref))
    base_cfg = copy.deepcopy(resolved.data)
    run_name_prefix = str(
        _coalesce(args.run_name_prefix, _spec_lookup(tune_spec, "run_name_prefix"), f"{resolved.label}_tune_")
    )
    if run_name_prefix.strip() == "":
        raise SystemExit("run_name_prefix cannot be empty.")

    base_eval = base_cfg.get("eval", {}) if isinstance(base_cfg.get("eval"), dict) else {}
    runs_dir_text = runs_dir_override or str(base_eval.get("output_dir", DEFAULT_RUNS_DIR.as_posix()))
    runs_dir = _resolve_path(runs_dir_text)

    sweep_tag = (str(tag) if tag is not None else _default_tag()).strip()
    if not sweep_tag:
        raise SystemExit("Tune tag cannot be empty.")
    safe_tag = sweep_tag.replace(" ", "_")
    sweep_dir = _resolve_path(sweep_root_text) / sweep_tag
    config_dir = sweep_dir / "configs"
    jobs_csv_path = sweep_dir / "jobs.csv"
    results_csv_path = sweep_dir / "trial_results.csv"
    summary_output = (
        _resolve_path(summary_output_override)
        if summary_output_override is not None
        else sweep_dir / "runs_summary.csv"
    )

    sweep_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)

    combinations = _enumerate_combinations(dimensions)
    selected = _select_combinations(combinations, sampler=sampler, n_trials=n_trials, seed=seed)
    if not selected:
        raise SystemExit("No tune jobs generated.")

    jobs = [
        _build_job(
            base_cfg,
            order=idx,
            run_name_prefix=run_name_prefix,
            sweep_tag=safe_tag,
            config_dir=config_dir,
            runs_dir_override=runs_dir_override,
            dimension_labels=labels,
            overrides=overrides,
        )
        for idx, (labels, overrides) in enumerate(selected, start=1)
    ]
    run_names = [job.run_name for job in jobs]
    if len(run_names) != len(set(run_names)):
        raise SystemExit("Duplicate run_name detected in generated tune jobs. Adjust prefix/tag values.")

    dimension_names = [dimension.name for dimension in dimensions]
    _write_jobs_csv(jobs_csv_path, jobs, dimension_names)
    logging.info("Generated %d trial configs under %s", len(jobs), config_dir)
    logging.info("Jobs manifest written to %s", jobs_csv_path)

    trial_results: list[dict[str, Any]] = []
    failed_count = 0
    started_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    if not dry_run:
        from .. import pipeline

        for job in jobs:
            row: dict[str, Any] = {
                "order": job.order,
                "run_name": job.run_name,
                "config_path": str(job.config_path),
                "summary_path": None,
                "objective_score": None,
                "eval_ic_ir": None,
                "eval_cv_ic_mean": None,
                "eval_cv_ic_valid_folds": None,
                "eval_cv_ic_total_folds": None,
                "walk_forward_test_ic_mean": None,
                "backtest_sharpe": None,
                "backtest_max_drawdown": None,
                "backtest_avg_turnover": None,
                "backtest_avg_cost_drag": None,
                "flag_constant_prediction": None,
                "flag_zero_feature_importance": None,
                "flag_cv_ic_insufficient": None,
                "status": "ok",
                "error": "",
                "dimensions": dict(job.dimension_labels),
            }
            for name in dimension_names:
                row[name] = job.dimension_labels.get(name)

            logging.info("[%d/%d] Running %s", job.order, len(jobs), job.run_name)
            job_start_time = time.time()
            try:
                pipeline.run(str(job.config_path))
                summary_path = _find_latest_summary(runs_dir, job.run_name, min_mtime=job_start_time - 1)
                if summary_path is None:
                    raise SystemExit(f"Run finished, but summary.json not found for run_name={job.run_name}.")
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                metrics = _score_summary(summary, objective_spec)
                row["summary_path"] = str(summary_path)
                row.update(metrics)
            except KeyboardInterrupt:
                raise
            except SystemExit as exc:
                row["status"] = "failed"
                row["error"] = str(exc)
                failed_count += 1
                logging.error("Run failed: %s (%s)", job.run_name, row["error"] or "SystemExit")
                trial_results.append(row)
                if not continue_on_error:
                    break
                continue
            except Exception as exc:  # pragma: no cover - defensive
                row["status"] = "failed"
                row["error"] = str(exc)
                failed_count += 1
                logging.error("Run failed: %s (%s)", job.run_name, row["error"])
                trial_results.append(row)
                if not continue_on_error:
                    break
                continue

            trial_results.append(row)
    else:
        logging.info("Dry-run enabled: skip pipeline.run and summarize.")

    _write_trial_results_csv(results_csv_path, trial_results, dimension_names)
    logging.info("Trial results written to %s", results_csv_path)

    best_row = _select_best_result(trial_results)
    if best_row is not None:
        _write_best_trial_files(sweep_dir=sweep_dir, best_row=best_row)

    summary_status = "skipped"
    summary_error = ""
    if not dry_run and not skip_summarize:
        from ..research import summarize_runs

        summarize_argv = [
            "--runs-dir",
            str(runs_dir),
            "--run-name-prefix",
            run_name_prefix + safe_tag,
            "--since",
            started_at,
            "--output",
            str(summary_output),
            "--log-level",
            log_level,
        ]
        try:
            summarize_runs.main(summarize_argv)
            summary_status = "ok"
        except SystemExit as exc:
            summary_status = "failed"
            summary_error = str(exc)
            logging.error("Summarize failed: %s", summary_error or "SystemExit")

    result = {
        "tune_dir": str(sweep_dir),
        "config_dir": str(config_dir),
        "jobs_csv": str(jobs_csv_path),
        "trial_results_csv": str(results_csv_path),
        "summary_output": str(summary_output),
        "job_count": len(jobs),
        "failed_count": failed_count,
        "best_run_name": best_row["run_name"] if best_row is not None else None,
        "summary_status": summary_status,
        "summary_error": summary_error,
    }

    if dry_run:
        return result
    if failed_count > 0 and not continue_on_error:
        raise SystemExit("Tune stopped on first failure. Re-run with --continue-on-error to keep going.")
    if failed_count > 0:
        raise SystemExit(f"Tune finished with {failed_count} failed runs.")
    if summary_status == "failed":
        raise SystemExit(f"Runs finished, but summarize failed: {summary_error}")
    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate and run repo-native tuning trials from a YAML search spec, "
            "then summarize results."
        )
    )
    add_tune_args(parser)
    args = parser.parse_args(argv)
    run(args)


if __name__ == "__main__":
    main()
