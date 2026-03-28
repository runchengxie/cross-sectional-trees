from __future__ import annotations

import argparse

from .common import append_arg, append_passthrough


def handle_universe_hk_connect(args) -> int:
    from ..data_tools import build_hk_connect_universe

    argv: list[str] = []
    append_arg(argv, "--config", args.config)
    append_passthrough(argv, args.args)
    build_hk_connect_universe.main(argv)
    return 0


def handle_universe_hk_daily_assets(args) -> int:
    from ..data_tools import build_hk_daily_asset_universe

    argv: list[str] = []
    append_arg(argv, "--config", args.config)
    append_passthrough(argv, args.args)
    build_hk_daily_asset_universe.main(argv)
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
