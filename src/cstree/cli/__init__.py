from __future__ import annotations

import argparse

from .core import register_core_commands
from .liveops import register_liveops_commands
from .research import register_research_commands


def build_parser(*, prog: str | None = "cstree") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Cross-sectional HK Trees CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    register_core_commands(subparsers)
    register_research_commands(subparsers)
    register_liveops_commands(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser(prog=None if argv is None else "cstree")
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 1
    return int(func(args) or 0)


__all__ = ["build_parser", "main"]
