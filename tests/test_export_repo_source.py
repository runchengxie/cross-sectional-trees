from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_export_module():
    module_path = _repo_root() / "scripts" / "internal" / "export_repo_source.py"
    spec = importlib.util.spec_from_file_location("export_repo_source", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_export_repo_source_collects_configs_tree():
    export_module = _load_export_module()
    repo_root = _repo_root()
    exclude_files = set(export_module.EXCLUDE_FILES)
    exclude_files.add(export_module.OUTPUT_FILENAME)

    collected = export_module.collect_file_tree(repo_root, exclude_files)
    relative_paths = {path.relative_to(repo_root).as_posix() for path in collected}

    assert "configs/catalog.csv" in relative_paths
    assert "configs/presets/default.yml" in relative_paths


def test_export_repo_source_tree_marks_excludes_without_expanding_children(
    tmp_path: Path,
):
    export_module = _load_export_module()

    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "diagram.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts" / "secret.txt").write_text("should stay collapsed\n")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "raw.csv").write_text("a,b\n1,2\n")
    (tmp_path / "notes.ipynb").write_text(
        json.dumps(
            {
                "cells": [
                    {
                        "cell_type": "markdown",
                        "source": ["# Demo\n"],
                    }
                ]
            }
        )
    )

    output_name = "repo_source.txt"
    export_module.combine_project_files(tmp_path, output_name)

    exported = (tmp_path / output_name).read_text()

    assert "--- Full Project Source Tree ---" in exported
    assert "[exclude] artifacts/ (excluded root-only directory; subtree omitted)" in exported
    assert "[exclude] data/ (excluded root-only directory; subtree omitted)" in exported
    assert "[exclude] diagram.png (excluded extension)" in exported
    assert "[include] src/" in exported
    assert "[include] main.py" in exported
    assert "secret.txt" not in exported
    assert "raw.csv" not in exported

    assert "<src/main.py>" in exported
    assert "<notes.ipynb>" in exported
    assert "<docs/diagram.png>" not in exported
    assert "<artifacts/secret.txt>" not in exported
