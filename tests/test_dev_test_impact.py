import importlib.util
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_test_impact_module():
    path = _repo_root() / "scripts" / "dev" / "test_impact.py"
    spec = importlib.util.spec_from_file_location("dev_test_impact", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_test_impact_maps_pipeline_runner_to_focused_tests():
    module = _load_test_impact_module()

    commands = module.recommended_commands(["src/cstree/pipeline/runner.py"])

    assert commands == [
        "uv run python -m pytest tests/test_pipeline_runtime.py "
        "tests/test_pipeline_filters_core.py -q",
        "scripts/dev/run_tests.sh lint",
    ]


def test_test_impact_covers_representative_high_risk_paths():
    module = _load_test_impact_module()

    cases = {
        "src/cstree/backtest.py": "tests/test_backtest.py",
        "src/cstree/liveops/alloc_core.py": "tests/test_alloc.py",
        "src/cstree/liveops/export_targets.py": "tests/test_export_targets.py",
        "src/cstree/release_tools/package_runs.py": "tests/test_run_release_scripts.py",
        "scripts/dev/data_ops_boundary.py": "tests/test_data_ops_boundary.py",
        "docs/dev.md": "tests/test_docs_contracts.py",
        "scripts/dev/run_tests.sh": "tests/test_run_tests_script.py",
    }

    for path, expected_fragment in cases.items():
        commands = module.recommended_commands([path])
        assert any(expected_fragment in command for command in commands)
        assert commands[-1] == "scripts/dev/run_tests.sh lint"


def test_test_impact_falls_back_for_unknown_paths():
    module = _load_test_impact_module()

    commands = module.recommended_commands(["src/cstree/unmapped_module.py"])

    assert commands == [
        "scripts/dev/run_tests.sh fast",
        "scripts/dev/run_tests.sh lint",
    ]


def test_test_impact_cli_outputs_json():
    repo_root = _repo_root()
    result = subprocess.run(
        [
            "python",
            "scripts/dev/test_impact.py",
            "--json",
            "src/cstree/backtest.py",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "tests/test_backtest.py" in result.stdout
