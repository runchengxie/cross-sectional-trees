import tomllib
from pathlib import Path

from cstree import cli


def _top_level_commands(parser):
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if choices:
            return set(choices)
    return set()


def test_cli_entrypoints_expose_only_cstree():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    scripts = pyproject["project"]["scripts"]

    assert scripts["cstree"] == "cstree.cli:main"
    assert "csml" not in scripts


def test_cli_parser_uses_cstree_public_program_name():
    assert cli.build_parser(prog="cstree").prog == "cstree"


def test_cli_entrypoint_exposes_top_level_commands():
    assert _top_level_commands(cli.build_parser(prog="cstree"))
