import os
import subprocess
from pathlib import Path

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_script_with_fake_uv(tmp_path: Path, *script_args: str) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    repo_root = _repo_root()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    argv_log = tmp_path / "uv_argv.txt"
    fake_uv = fake_bin / "uv"
    fake_uv.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$@\" > \"$UV_ARGS_LOG\"\n",
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["UV_ARGS_LOG"] = str(argv_log)

    result = subprocess.run(
        ["bash", "scripts/dev/run_tests.sh", *script_args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    argv = argv_log.read_text(encoding="utf-8").splitlines() if argv_log.exists() else []
    return result, argv


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


@pytest.mark.parametrize(
    ("mode", "expected_argv"),
    [
        ("all", ["run", "pytest"]),
        ("fast", ["run", "pytest", "--no-cov", "-m", "not integration and not slow"]),
        ("unit", ["run", "pytest", "--no-cov", "-m", "not integration and not slow"]),
        ("slow", ["run", "pytest", "--no-cov", "-m", "slow and not integration"]),
        ("integration", ["run", "pytest", "--no-cov", "-m", "integration"]),
        ("coverage", ["run", "pytest", "--cov=csml", "--cov-report=term-missing"]),
    ],
)
def test_run_tests_script_mode_maps_to_expected_pytest_argv(tmp_path, mode, expected_argv):
    result, argv = _run_script_with_fake_uv(tmp_path, mode)

    assert result.returncode == 0, result.stderr
    assert argv == expected_argv


def test_run_tests_script_forwards_additional_pytest_args(tmp_path):
    result, argv = _run_script_with_fake_uv(
        tmp_path,
        "fast",
        "tests/test_metrics.py",
        "-k",
        "ic",
    )

    assert result.returncode == 0, result.stderr
    assert argv == [
        "run",
        "pytest",
        "--no-cov",
        "-m",
        "not integration and not slow",
        "tests/test_metrics.py",
        "-k",
        "ic",
    ]


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
