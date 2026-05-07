import importlib.util
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_check_module():
    path = _repo_root() / "scripts" / "dev" / "check_c901_debt.py"
    spec = importlib.util.spec_from_file_location("check_c901_debt", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_c901_debt_registry_covers_pyproject_ignores():
    module = _load_check_module()

    c901_paths = module.load_c901_ignore_paths()
    registry_paths = module.load_registry_paths()

    assert len(c901_paths) == 30
    assert module.missing_registry_entries(c901_paths, registry_paths) == []


def test_c901_debt_registry_reports_missing_entries():
    module = _load_check_module()

    missing = module.missing_registry_entries(
        {"src/cstree/example.py", "src/cstree/covered.py"},
        {"src/cstree/covered.py"},
    )

    assert missing == ["src/cstree/example.py"]
