from __future__ import annotations

import importlib.util
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
