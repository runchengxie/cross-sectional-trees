from __future__ import annotations

import argparse
import sys

from .._mdp_compat import load_market_data_platform_module
from .common import append_arg, append_passthrough


def _run_market_data_platform_universe_builder(module_name: str, argv: list[str]) -> None:
    module = load_market_data_platform_module(f"hk_assets.{module_name}")
    print(
        "cstree universe hk-* is a compatibility wrapper; HK universe asset builders "
        "are owned by market-data-platform.",
        file=sys.stderr,
    )
    module.main(argv)


def handle_universe_hk_connect(args) -> int:
    argv: list[str] = []
    append_arg(argv, "--config", args.config)
    append_passthrough(argv, args.args)
    _run_market_data_platform_universe_builder("build_hk_connect_universe", argv)
    return 0


def handle_universe_hk_daily_assets(args) -> int:
    argv: list[str] = []
    append_arg(argv, "--config", args.config)
    append_passthrough(argv, args.args)
    _run_market_data_platform_universe_builder("build_hk_daily_asset_universe", argv)
    return 0


def register_universe_command(subparsers) -> None:
    universe = subparsers.add_parser("universe", help="Universe construction helpers")
    uni_sub = universe.add_subparsers(dest="uni_command", required=True)

    hk = uni_sub.add_parser("hk-connect", help="Build HK Connect universe")
    hk.add_argument("--config", help="YAML config path (optional).")
    hk.add_argument("args", nargs=argparse.REMAINDER)
    hk.set_defaults(func=handle_universe_hk_connect)

    hk_daily_assets = uni_sub.add_parser(
        "hk-daily-assets",
        help="Build HK full-market universe from local daily assets",
    )
    hk_daily_assets.add_argument("--config", help="YAML config path (optional).")
    hk_daily_assets.add_argument("args", nargs=argparse.REMAINDER)
    hk_daily_assets.set_defaults(func=handle_universe_hk_daily_assets)
