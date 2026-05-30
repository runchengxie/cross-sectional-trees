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
    assert "typecheck" in result.stdout
    assert "main pytest suite without coverage" in result.stdout
    assert "Does not include optional-extra smoke jobs" in result.stdout
    assert "Real provider integration uses CSTREE_RUN_PROVIDER_INTEGRATION=1" in result.stdout
    assert "it is not the full CI matrix" in result.stdout
    assert "c901-debt" in result.stdout
    assert "data-ops-boundary" in result.stdout
    assert "maintainability" in result.stdout


def test_run_tests_script_lint_ratchet_mentions_high_signal_rules():
    repo_root = _repo_root()
    script = (repo_root / "scripts/dev/run_tests.sh").read_text(encoding="utf-8")

    assert "--select I,F401,F841,B023" in script
    assert "check_added_c901_ignores" in script
    assert "check_c901_debt_registry" in script
    assert "check_data_ops_boundary" in script
    assert "scripts/dev/check_c901_debt.py" in script
    assert "scripts/dev/data_ops_boundary.py" in script
    assert "scripts/dev/maintainability_metrics.py" in script
    assert "maintenance-debt-inventory.md" in script


@pytest.mark.parametrize(
    ("mode", "expected_argv"),
    [
        ("all", ["run", "python", "-m", "pytest"]),
        ("fast", ["run", "python", "-m", "pytest", "--no-cov", "-m", "not integration and not slow"]),
        ("unit", ["run", "python", "-m", "pytest", "--no-cov", "-m", "not integration and not slow"]),
        ("slow", ["run", "python", "-m", "pytest", "--no-cov", "-m", "slow and not integration"]),
        ("integration", ["run", "python", "-m", "pytest", "--no-cov", "-m", "integration"]),
        ("coverage", ["run", "python", "-m", "pytest", "--cov=cstree", "--cov-report=term-missing"]),
        ("typecheck", ["tool", "run", "--from", "pyright", "pyright"]),
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
        "python",
        "-m",
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


def test_run_tests_script_c901_debt_mode_runs_validator():
    repo_root = _repo_root()
    result = subprocess.run(
        ["bash", "scripts/dev/run_tests.sh", "c901-debt"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_run_tests_script_data_ops_boundary_mode_runs_validator():
    repo_root = _repo_root()
    result = subprocess.run(
        ["bash", "scripts/dev/run_tests.sh", "data-ops-boundary"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_run_tests_script_maintainability_mode_outputs_metrics():
    repo_root = _repo_root()
    result = subprocess.run(
        ["bash", "scripts/dev/run_tests.sh", "maintainability", "--json", "--limit", "1"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert '"c901_file_ignores": 9' in result.stdout
