from __future__ import annotations

import argparse

from ..config_utils import resolve_pipeline_config
from .. import pipeline
from . import holdings


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run a live snapshot and emit latest holdings."
    )
    parser.add_argument(
        "--config",
        help="Pipeline config path or built-in name.",
    )
    parser.add_argument(
        "--run-dir",
        help="Use an existing run directory (skips pipeline run).",
    )
    parser.add_argument(
        "--as-of",
        default="t-1",
        help="As-of date for holdings output (YYYYMMDD, YYYY-MM-DD, today, t-1).",
    )
    parser.add_argument(
        "--skip-run",
        action="store_true",
        help="Skip running the pipeline and only emit holdings from the latest run.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        help="Optional Top-K filter when selecting the latest run.",
    )
    parser.add_argument(
        "--format",
        default="text",
        choices=["text", "csv", "json"],
        help="Output format (text/csv/json). Default: text.",
    )
    parser.add_argument(
        "--out",
        help="Optional output path (default: stdout).",
    )
    args = parser.parse_args(argv)

    if not args.config and not args.run_dir:
        raise SystemExit("snapshot requires --config or --run-dir.")

    should_run = not args.skip_run and not args.run_dir
    if should_run:
        resolved = resolve_pipeline_config(args.config)
        cfg = resolved.data
        live_cfg = cfg.get("live") if isinstance(cfg, dict) else None
        live_cfg = live_cfg if isinstance(live_cfg, dict) else {}
        if not bool(live_cfg.get("enabled", False)):
            raise SystemExit("snapshot requires live.enabled=true in the config.")
        pipeline.run(args.config)

    hold_args: list[str] = ["--source", "live", "--as-of", args.as_of]
    if args.config:
        hold_args += ["--config", args.config]
    if args.run_dir:
        hold_args += ["--run-dir", args.run_dir]
    if args.top_k is not None:
        hold_args += ["--top-k", str(args.top_k)]
    if args.format:
        hold_args += ["--format", args.format]
    if args.out:
        hold_args += ["--out", args.out]
    holdings.main(hold_args)


if __name__ == "__main__":
    main()
