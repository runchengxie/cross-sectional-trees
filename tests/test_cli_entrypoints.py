import tomllib
from pathlib import Path

from csml import cli


def test_cli_entrypoints_keep_cstree_and_csml_compatible():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    scripts = pyproject["project"]["scripts"]

    assert scripts["cstree"] == "csml.cli:main"
    assert scripts["csml"] == scripts["cstree"]


def test_cli_parser_can_use_either_public_program_name():
    assert cli.build_parser(prog="cstree").prog == "cstree"
    assert cli.build_parser(prog="csml").prog == "csml"
