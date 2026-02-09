from __future__ import annotations

import argparse
import copy
import csv
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from ..config_utils import resolve_pipeline_config

DEFAULT_BASE_CONFIG = "config/hk_selected.yml"
DEFAULT_RUN_NAME_PREFIX = "hk_sel_"
DEFAULT_SWEEPS_DIR = "out/sweeps"
DEFAULT_RIDGE_ALPHA = [0.01, 0.1, 1, 10, 100]
DEFAULT_ELASTICNET_ALPHA = [0.01, 0.1, 1]
DEFAULT_ELASTICNET_L1_RATIO = [0.1, 0.5, 0.9]
DEFAULT_LOG_LEVEL = "INFO"


@dataclass(frozen=True)
class SweepJob:
    model: str
    alpha: float
    l1_ratio: float | None
    run_name: str
    config_path: Path


def _resolve_path(path_text: str | Path) -> Path:
    candidate = Path(path_text).expanduser()
    if candidate.is_absolute():
        return candidate
    return (Path.cwd() / candidate).resolve()


def _format_float(value: float) -> str:
    return format(float(value), ".12g")


def _parse_float_grid(values: Any, default: list[float], field_name: str) -> list[float]:
    if values is None:
        return list(default)
    if isinstance(values, (str, int, float)):
        items = [values]
    elif isinstance(values, list):
        items = values
    else:
        raise SystemExit(f"Invalid --{field_name} values type: {type(values).__name__}")
    out: list[float] = []
    for entry in items:
        for part in str(entry).split(","):
            text = part.strip()
            if not text:
                continue
            try:
                out.append(float(text))
            except ValueError as exc:
                raise SystemExit(f"Invalid float in --{field_name}: {text}") from exc
    deduped = list(dict.fromkeys(out))
    if not deduped:
        raise SystemExit(f"--{field_name} produced no valid values.")
    return deduped


def _ensure_mapping(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        value = {}
        parent[key] = value
    return value


def _default_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _build_ridge_job(
    base_cfg: dict[str, Any],
    *,
    run_name_prefix: str,
    alpha: float,
    config_dir: Path,
    runs_dir_override: str | None,
    sample_weight_mode: str,
    random_state: Any,
) -> SweepJob:
    alpha_text = _format_float(alpha)
    run_name = f"{run_name_prefix}ridge_a{alpha_text}"
    cfg = copy.deepcopy(base_cfg)

    model_cfg = _ensure_mapping(cfg, "model")
    model_cfg["type"] = "ridge"
    model_cfg["params"] = {"alpha": float(alpha)}
    if random_state is not None:
        model_cfg["params"]["random_state"] = random_state
    model_cfg["sample_weight_mode"] = sample_weight_mode

    eval_cfg = _ensure_mapping(cfg, "eval")
    eval_cfg["run_name"] = run_name
    if runs_dir_override is not None:
        eval_cfg["output_dir"] = runs_dir_override

    config_path = config_dir / f"ridge_a{alpha_text}.yml"
    _write_yaml(config_path, cfg)
    return SweepJob(
        model="ridge",
        alpha=float(alpha),
        l1_ratio=None,
        run_name=run_name,
        config_path=config_path,
    )


def _build_elasticnet_job(
    base_cfg: dict[str, Any],
    *,
    run_name_prefix: str,
    alpha: float,
    l1_ratio: float,
    config_dir: Path,
    runs_dir_override: str | None,
    sample_weight_mode: str,
    random_state: Any,
) -> SweepJob:
    alpha_text = _format_float(alpha)
    l1_text = _format_float(l1_ratio)
    run_name = f"{run_name_prefix}en_a{alpha_text}_l{l1_text}"
    cfg = copy.deepcopy(base_cfg)

    model_cfg = _ensure_mapping(cfg, "model")
    model_cfg["type"] = "elasticnet"
    model_cfg["params"] = {"alpha": float(alpha), "l1_ratio": float(l1_ratio)}
    if random_state is not None:
        model_cfg["params"]["random_state"] = random_state
    model_cfg["sample_weight_mode"] = sample_weight_mode

    eval_cfg = _ensure_mapping(cfg, "eval")
    eval_cfg["run_name"] = run_name
    if runs_dir_override is not None:
        eval_cfg["output_dir"] = runs_dir_override

    config_path = config_dir / f"elasticnet_a{alpha_text}_l{l1_text}.yml"
    _write_yaml(config_path, cfg)
    return SweepJob(
        model="elasticnet",
        alpha=float(alpha),
        l1_ratio=float(l1_ratio),
        run_name=run_name,
        config_path=config_path,
    )


def _write_jobs_csv(path: Path, jobs: list[SweepJob]) -> None:
    fieldnames = ["order", "model", "alpha", "l1_ratio", "run_name", "config_path"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for idx, job in enumerate(jobs, start=1):
            writer.writerow(
                {
                    "order": idx,
                    "model": job.model,
                    "alpha": job.alpha,
                    "l1_ratio": job.l1_ratio,
                    "run_name": job.run_name,
                    "config_path": str(job.config_path),
                }
            )


def _write_run_results_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = ["order", "run_name", "config_path", "status", "error"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


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


def _load_sweep_spec(path_text: str | None) -> tuple[dict[str, Any], Path | None]:
    if path_text is None:
        return {}, None
    path = _resolve_path(path_text)
    payload = _load_yaml_mapping(path, label="Sweep config")
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


def add_linear_sweep_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument(
        "--sweep-config",
        default=None,
        help="YAML file for sweep parameters (CLI args override this file)",
    )
    parser.add_argument(
        "--config",
        default=None,
        help=f"Base config path or built-in name (default: {DEFAULT_BASE_CONFIG})",
    )
    parser.add_argument(
        "--run-name-prefix",
        default=None,
        help=f"run_name prefix for all generated runs (default: {DEFAULT_RUN_NAME_PREFIX})",
    )
    parser.add_argument(
        "--sweeps-dir",
        default=None,
        help=f"Root directory for sweep artifacts (default: {DEFAULT_SWEEPS_DIR})",
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="Sweep tag used as subdirectory name (default: current timestamp)",
    )
    parser.add_argument(
        "--runs-dir",
        default=None,
        help="Override eval.output_dir for generated configs (default: keep base config value)",
    )
    parser.add_argument(
        "--ridge-alpha",
        action="append",
        default=None,
        help="Comma-separated ridge alpha values (default: 0.01,0.1,1,10,100)",
    )
    parser.add_argument(
        "--elasticnet-alpha",
        action="append",
        default=None,
        help="Comma-separated elasticnet alpha values (default: 0.01,0.1,1)",
    )
    parser.add_argument(
        "--elasticnet-l1-ratio",
        action="append",
        default=None,
        help="Comma-separated elasticnet l1_ratio values (default: 0.1,0.5,0.9)",
    )
    parser.add_argument(
        "--skip-ridge",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Skip ridge jobs",
    )
    parser.add_argument(
        "--skip-elasticnet",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Skip elasticnet jobs",
    )
    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Only generate configs/jobs.csv; do not run pipeline or summarize",
    )
    parser.add_argument(
        "--continue-on-error",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Continue remaining jobs if one run fails",
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
        help="Summary CSV path (default: <sweep-dir>/runs_summary.csv)",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Logging level",
    )
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    sweep_spec, sweep_spec_path = _load_sweep_spec(args.sweep_config)

    base_config_ref = str(
        _coalesce(
        args.config,
        _spec_lookup(sweep_spec, "base_config"),
        _spec_lookup(sweep_spec, "config"),
        DEFAULT_BASE_CONFIG,
    )
    )
    run_name_prefix = str(
        _coalesce(
        args.run_name_prefix,
        _spec_lookup(sweep_spec, "run_name_prefix"),
        DEFAULT_RUN_NAME_PREFIX,
    )
    )
    sweeps_dir = str(
        _coalesce(
        args.sweeps_dir,
        _spec_lookup(sweep_spec, "sweeps_dir"),
        DEFAULT_SWEEPS_DIR,
    )
    )
    tag = _coalesce(
        args.tag,
        _spec_lookup(sweep_spec, "tag"),
        _spec_lookup(sweep_spec, "sweep_tag"),
    )
    runs_dir_override_raw = _coalesce(
        args.runs_dir,
        _spec_lookup(sweep_spec, "runs_dir"),
    )
    runs_dir_override = None if runs_dir_override_raw is None else str(runs_dir_override_raw)
    summary_output_override = _coalesce(
        args.summary_output,
        _spec_lookup(sweep_spec, "summary_output", section="options"),
        _spec_lookup(sweep_spec, "summary_output"),
    )
    if run_name_prefix.strip() == "":
        raise SystemExit("run_name_prefix cannot be empty.")
    log_level = str(
        _coalesce(
            args.log_level,
            _spec_lookup(sweep_spec, "log_level", section="options"),
            _spec_lookup(sweep_spec, "log_level"),
            DEFAULT_LOG_LEVEL,
        )
    ).upper()
    if log_level not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
        raise SystemExit(f"Invalid log_level: {log_level}")

    ridge_alpha_values = _coalesce(
        args.ridge_alpha,
        _spec_lookup(sweep_spec, "ridge_alpha", section="grid"),
        _spec_lookup(sweep_spec, "ridge_alpha"),
    )
    elasticnet_alpha_values = _coalesce(
        args.elasticnet_alpha,
        _spec_lookup(sweep_spec, "elasticnet_alpha", section="grid"),
        _spec_lookup(sweep_spec, "elasticnet_alpha"),
    )
    elasticnet_l1_ratio_values = _coalesce(
        args.elasticnet_l1_ratio,
        _spec_lookup(sweep_spec, "elasticnet_l1_ratio", section="grid"),
        _spec_lookup(sweep_spec, "elasticnet_l1_ratio"),
    )

    skip_ridge = _coerce_bool(
        _coalesce(
            args.skip_ridge,
            _spec_lookup(sweep_spec, "skip_ridge", section="options"),
            _spec_lookup(sweep_spec, "skip_ridge"),
            False,
        ),
        field_name="skip_ridge",
    )
    skip_elasticnet = _coerce_bool(
        _coalesce(
            args.skip_elasticnet,
            _spec_lookup(sweep_spec, "skip_elasticnet", section="options"),
            _spec_lookup(sweep_spec, "skip_elasticnet"),
            False,
        ),
        field_name="skip_elasticnet",
    )
    dry_run = _coerce_bool(
        _coalesce(
            args.dry_run,
            _spec_lookup(sweep_spec, "dry_run", section="options"),
            _spec_lookup(sweep_spec, "dry_run"),
            False,
        ),
        field_name="dry_run",
    )
    continue_on_error = _coerce_bool(
        _coalesce(
            args.continue_on_error,
            _spec_lookup(sweep_spec, "continue_on_error", section="options"),
            _spec_lookup(sweep_spec, "continue_on_error"),
            False,
        ),
        field_name="continue_on_error",
    )
    skip_summarize = _coerce_bool(
        _coalesce(
            args.skip_summarize,
            _spec_lookup(sweep_spec, "skip_summarize", section="options"),
            _spec_lookup(sweep_spec, "skip_summarize"),
            False,
        ),
        field_name="skip_summarize",
    )

    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(levelname)s: %(message)s",
    )
    if sweep_spec_path:
        logging.info("Loaded sweep config: %s", sweep_spec_path)

    ridge_alphas = _parse_float_grid(ridge_alpha_values, DEFAULT_RIDGE_ALPHA, "ridge-alpha")
    en_alphas = _parse_float_grid(elasticnet_alpha_values, DEFAULT_ELASTICNET_ALPHA, "elasticnet-alpha")
    en_l1s = _parse_float_grid(
        elasticnet_l1_ratio_values,
        DEFAULT_ELASTICNET_L1_RATIO,
        "elasticnet-l1-ratio",
    )
    if skip_ridge and skip_elasticnet:
        raise SystemExit("Both --skip-ridge and --skip-elasticnet are set; no jobs to run.")

    resolved = resolve_pipeline_config(base_config_ref)
    base_cfg = copy.deepcopy(resolved.data)
    base_eval = base_cfg.get("eval", {}) if isinstance(base_cfg.get("eval"), dict) else {}
    base_model = base_cfg.get("model", {}) if isinstance(base_cfg.get("model"), dict) else {}
    base_params = base_model.get("params", {}) if isinstance(base_model.get("params"), dict) else {}

    runs_dir_text = runs_dir_override
    if runs_dir_text is None:
        runs_dir_text = str(base_eval.get("output_dir", "out/runs"))
    runs_dir = _resolve_path(runs_dir_text)

    sweep_tag = (str(tag) if tag is not None else _default_tag()).strip()
    if not sweep_tag:
        raise SystemExit("Sweep tag cannot be empty.")
    sweep_root = _resolve_path(sweeps_dir)
    sweep_dir = sweep_root / sweep_tag
    config_dir = sweep_dir / "configs"
    jobs_csv_path = sweep_dir / "jobs.csv"
    results_csv_path = sweep_dir / "run_results.csv"
    summary_output = (
        _resolve_path(summary_output_override)
        if summary_output_override is not None
        else sweep_dir / "runs_summary.csv"
    )

    sweep_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)

    sample_weight_mode = str(base_model.get("sample_weight_mode", "date_equal"))
    random_state = base_params.get("random_state", 42)

    jobs: list[SweepJob] = []
    if not skip_ridge:
        for alpha in ridge_alphas:
            jobs.append(
                _build_ridge_job(
                    base_cfg,
                    run_name_prefix=run_name_prefix,
                    alpha=alpha,
                    config_dir=config_dir,
                    runs_dir_override=runs_dir_override,
                    sample_weight_mode=sample_weight_mode,
                    random_state=random_state,
                )
            )
    if not skip_elasticnet:
        for alpha in en_alphas:
            for l1_ratio in en_l1s:
                jobs.append(
                    _build_elasticnet_job(
                        base_cfg,
                        run_name_prefix=run_name_prefix,
                        alpha=alpha,
                        l1_ratio=l1_ratio,
                        config_dir=config_dir,
                        runs_dir_override=runs_dir_override,
                        sample_weight_mode=sample_weight_mode,
                        random_state=random_state,
                    )
                )

    if not jobs:
        raise SystemExit("No sweep jobs generated.")
    run_names = [job.run_name for job in jobs]
    if len(run_names) != len(set(run_names)):
        raise SystemExit("Duplicate run_name detected in generated jobs. Adjust prefix/grid values.")

    _write_jobs_csv(jobs_csv_path, jobs)
    logging.info("Generated %d configs under %s", len(jobs), config_dir)
    logging.info("Jobs manifest written to %s", jobs_csv_path)

    run_results: list[dict[str, Any]] = []
    failed_count = 0
    started_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    if not dry_run:
        from .. import pipeline

        for idx, job in enumerate(jobs, start=1):
            status = "ok"
            error_text = ""
            logging.info("[%d/%d] Running %s", idx, len(jobs), job.run_name)
            try:
                pipeline.run(str(job.config_path))
            except KeyboardInterrupt:
                raise
            except SystemExit as exc:
                status = "failed"
                error_text = str(exc)
                failed_count += 1
                logging.error("Run failed: %s (%s)", job.run_name, error_text or "SystemExit")
                if not continue_on_error:
                    run_results.append(
                        {
                            "order": idx,
                            "run_name": job.run_name,
                            "config_path": str(job.config_path),
                            "status": status,
                            "error": error_text,
                        }
                    )
                    break
            except Exception as exc:  # pragma: no cover - defensive
                status = "failed"
                error_text = str(exc)
                failed_count += 1
                logging.error("Run failed: %s (%s)", job.run_name, error_text)
                if not continue_on_error:
                    run_results.append(
                        {
                            "order": idx,
                            "run_name": job.run_name,
                            "config_path": str(job.config_path),
                            "status": status,
                            "error": error_text,
                        }
                    )
                    break

            run_results.append(
                {
                    "order": idx,
                    "run_name": job.run_name,
                    "config_path": str(job.config_path),
                    "status": status,
                    "error": error_text,
                }
            )
    else:
        logging.info("Dry-run enabled: skip pipeline.run and summarize.")

    _write_run_results_csv(results_csv_path, run_results)
    logging.info("Run results written to %s", results_csv_path)

    summary_status = "skipped"
    summary_error = ""
    if not dry_run and not skip_summarize:
        from . import summarize_runs

        summarize_argv = [
            "--runs-dir",
            str(runs_dir),
            "--run-name-prefix",
            run_name_prefix,
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
        "sweep_dir": str(sweep_dir),
        "config_dir": str(config_dir),
        "jobs_csv": str(jobs_csv_path),
        "run_results_csv": str(results_csv_path),
        "summary_output": str(summary_output),
        "job_count": len(jobs),
        "failed_count": failed_count,
        "summary_status": summary_status,
        "summary_error": summary_error,
    }

    if dry_run:
        return result
    if failed_count > 0 and not continue_on_error:
        raise SystemExit("Sweep stopped on first failure. Re-run with --continue-on-error to keep going.")
    if failed_count > 0:
        raise SystemExit(f"Sweep finished with {failed_count} failed runs.")
    if summary_status == "failed":
        raise SystemExit(f"Runs finished, but summarize failed: {summary_error}")
    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate linear model sweep configs (ridge/elasticnet), run them, "
            "then summarize results."
        )
    )
    add_linear_sweep_args(parser)
    args = parser.parse_args(argv)
    run(args)


if __name__ == "__main__":
    main()
