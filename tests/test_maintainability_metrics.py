import importlib.util
import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_metrics_module():
    path = _repo_root() / "scripts" / "dev" / "maintainability_metrics.py"
    spec = importlib.util.spec_from_file_location("maintainability_metrics", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_collect_metrics_counts_fixture_files(tmp_path):
    module = _load_metrics_module()
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    pycache_dir = src_dir / "__pycache__"
    pycache_dir.mkdir()

    long_line = "x = '" + ("a" * 101) + "'"
    large_body = "\n".join(f"    value_{index} = {index}" for index in range(101))
    (src_dir / "module.py").write_text(
        "\n".join(
            [
                long_line,
                "",
                "def large_function():",
                large_body,
                "    return value_100",
            ]
        ),
        encoding="utf-8",
    )
    (scripts_dir / "tool.py").write_text("def small():\n    return 1\n", encoding="utf-8")
    (tests_dir / "test_tool.py").write_text(
        "def test_small():\n    assert True\n",
        encoding="utf-8",
    )
    (pycache_dir / "ignored.py").write_text("def ignored():\n    pass\n", encoding="utf-8")

    metrics = module.collect_metrics(tmp_path, limit=5)

    assert metrics.python_files == 3
    assert metrics.long_lines_over_100 == 1
    assert metrics.functions_over_100 == 1
    assert metrics.functions_over_250 == 0
    assert metrics.c901_file_ignores == 0
    assert metrics.largest_functions[0].name == "large_function"


def test_repo_metrics_include_c901_and_public_api_counts():
    module = _load_metrics_module()

    metrics = module.collect_metrics(_repo_root(), limit=3)

    assert metrics.c901_file_ignores == 10
    assert metrics.python_files >= 200
    assert metrics.functions_over_500 == 0


def test_maintainability_metrics_cli_outputs_json():
    repo_root = _repo_root()
    result = subprocess.run(
        [
            "python",
            "scripts/dev/maintainability_metrics.py",
            "--json",
            "--limit",
            "2",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["c901_file_ignores"] == 10
    assert len(payload["largest_functions"]) == 2


def test_maintainability_metrics_cli_outputs_markdown():
    repo_root = _repo_root()
    result = subprocess.run(
        [
            "python",
            "scripts/dev/maintainability_metrics.py",
            "--markdown",
            "--limit",
            "1",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "| Python files |" in result.stdout
    assert "Largest functions:" in result.stdout
