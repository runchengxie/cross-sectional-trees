import tomllib
from pathlib import Path

from csml import cli
from cstree import cli as cstree_cli


def _top_level_commands(parser):
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if choices:
            return set(choices)
    return set()


def test_cli_entrypoints_keep_cstree_and_csml_compatible():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    scripts = pyproject["project"]["scripts"]

    assert scripts["cstree"] == "cstree.cli:main"
    assert scripts["csml"] == "csml.cli:main"
    assert cstree_cli.main is cli.main
    assert cstree_cli.build_parser is cli.build_parser


def test_cli_parser_can_use_either_public_program_name():
    assert cli.build_parser(prog="cstree").prog == "cstree"
    assert cli.build_parser(prog="csml").prog == "csml"


def test_cli_entrypoints_expose_same_top_level_commands():
    assert _top_level_commands(cstree_cli.build_parser(prog="cstree")) == _top_level_commands(
        cli.build_parser(prog="csml")
    )
