from __future__ import annotations

from pathlib import Path

from .. import pipeline
from ..config_utils import resolve_pipeline_filename, resolve_repo_preset_path


def handle_run(args) -> int:
    artifacts_root = getattr(args, "artifacts_root", None)
    fail_on_quality = getattr(args, "fail_on_quality", None)
    if fail_on_quality is None and artifacts_root is None:
        pipeline.run(args.config)
    elif artifacts_root is None:
        pipeline.run(args.config, fail_on_quality=fail_on_quality)
    elif fail_on_quality is None:
        pipeline.run(args.config, artifacts_root=artifacts_root)
    else:
        pipeline.run(
            args.config,
            fail_on_quality=fail_on_quality,
            artifacts_root=artifacts_root,
        )
    return 0


def handle_init_config(args) -> int:
    filename = resolve_pipeline_filename(args.market)

    source_path = resolve_repo_preset_path(filename)
    if not source_path.exists():
        raise SystemExit(f"Preset not found: {source_path}")
    content = source_path.read_text(encoding="utf-8")

    if args.out:
        out_path = Path(args.out)
        if out_path.exists() and out_path.is_dir():
            out_path = out_path / filename
        elif not out_path.suffix:
            out_path.mkdir(parents=True, exist_ok=True)
            out_path = out_path / filename
    else:
        out_dir = Path.cwd() / "configs"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / filename

    if out_path.exists() and not args.force:
        raise SystemExit(f"Refusing to overwrite existing file: {out_path}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


def register_core_commands(subparsers) -> None:
    run = subparsers.add_parser(
        "run",
        help="Run the main training/eval/backtest pipeline",
    )
    run.add_argument(
        "--config",
        help="Path to YAML config or built-in name (default/hk/a_share).",
    )
    run.add_argument(
        "--fail-on-quality",
        choices=["none", "info", "warning", "error"],
        default=None,
        help=(
            "Optional quality gate threshold. Overrides quality.fail_on_severity in the config "
            "when provided."
        ),
    )
    run.add_argument(
        "--artifacts-root",
        help=(
            "Optional artifacts root override. When omitted, the pipeline uses "
            "CSTREE_ARTIFACTS_ROOT, paths.artifacts_root, "
            "or the default artifacts/."
        ),
    )
    run.set_defaults(func=handle_run)

    init_cfg = subparsers.add_parser(
        "init-config",
        help="Export a repository preset template to the filesystem",
    )
    init_cfg.add_argument(
        "--market",
        default="default",
        help="Template to export (default/hk/a_share).",
    )
    init_cfg.add_argument(
        "--out",
        help="Output path or directory (default: ./configs/<template>.yml).",
    )
    init_cfg.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files.",
    )
    init_cfg.set_defaults(func=handle_init_config)
