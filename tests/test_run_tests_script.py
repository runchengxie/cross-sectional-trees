import subprocess
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_run_tests_script_has_valid_bash_syntax():
    repo_root = _repo_root()
    result = subprocess.run(
        ["bash", "-n", "scripts/dev/run_tests.sh"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_run_tests_script_help_lists_supported_modes():
    repo_root = _repo_root()
    result = subprocess.run(
        ["bash", "scripts/dev/run_tests.sh", "help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "fast" in result.stdout
    assert "slow" in result.stdout
    assert "integration" in result.stdout
    assert "coverage" in result.stdout


def test_run_tests_script_rejects_unknown_mode():
    repo_root = _repo_root()
    result = subprocess.run(
        ["bash", "scripts/dev/run_tests.sh", "unknown-mode"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "Unknown mode: unknown-mode" in result.stderr
