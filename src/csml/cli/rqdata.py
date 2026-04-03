from __future__ import annotations

import argparse
import json

from ..data_tools.rqdata_assets.command_registry import (
    RQDataAssetCommandSpec,
    rqdata_asset_command_specs,
)
from .common import augment_quota_payload, format_quota_pretty, init_rqdatac


def handle_rqdata_info(args) -> int:
    rqdatac = init_rqdatac(args)
    info = rqdatac.info()
    print(info)
    return 0


def handle_rqdata_quota(args) -> int:
    rqdatac = init_rqdatac(args)
    quota = rqdatac.user.get_quota()
    payload = quota
    if hasattr(quota, "to_dict"):
        try:
            payload = quota.to_dict(orient="records")
        except TypeError:
            payload = quota.to_dict()
    payload = augment_quota_payload(payload)
    if getattr(args, "pretty", False):
        print(format_quota_pretty(payload))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


def _add_rqdata_auth_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", help="Optional config path to load rqdata.init")
    parser.add_argument("--username", help="Override RQData username")
    parser.add_argument("--password", help="Override RQData password")


def _run_rqdata_asset_command(args, spec: RQDataAssetCommandSpec) -> int:
    from ..data_tools import rqdata_assets as rqdata_assets_tool

    runner = getattr(rqdata_assets_tool, spec.runner.__name__, spec.runner)
    if spec.requires_client:
        rqdatac = init_rqdatac(args)
        return int(runner(args, rqdatac) or 0)
    return int(runner(args) or 0)


def _make_rqdata_asset_handler(spec: RQDataAssetCommandSpec):
    def _handler(args) -> int:
        return _run_rqdata_asset_command(args, spec)

    return _handler


def _register_rqdata_asset_commands(rq_sub) -> None:
    for spec in rqdata_asset_command_specs():
        parser = rq_sub.add_parser(spec.name, help=spec.help)
        spec.add_args(parser)
        parser.set_defaults(func=_make_rqdata_asset_handler(spec))


def register_rqdata_command(subparsers) -> None:
    rqdata = subparsers.add_parser("rqdata", help="RQData utilities")
    rq_sub = rqdata.add_subparsers(dest="rq_command", required=True)

    rq_info = rq_sub.add_parser("info", help="Show rqdatac login/info")
    _add_rqdata_auth_args(rq_info)
    rq_info.set_defaults(func=handle_rqdata_info)

    rq_quota = rq_sub.add_parser("quota", help="Show rqdatac quota usage")
    _add_rqdata_auth_args(rq_quota)
    rq_quota.add_argument(
        "--pretty",
        action="store_true",
        help="Show human-friendly output with percent and progress bar",
    )
    rq_quota.set_defaults(func=handle_rqdata_quota)

    _register_rqdata_asset_commands(rq_sub)
