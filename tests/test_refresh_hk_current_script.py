import os
import subprocess
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _fake_tooling(
    tmp_path: Path,
    *,
    python_exit_code: int = 0,
) -> tuple[dict[str, str], Path, Path]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()

    python_args_log = tmp_path / "python_args.txt"
    uv_args_log = tmp_path / "uv_args.txt"

    fake_python = fake_bin / "python"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$@\" > \"$PYTHON_ARGS_LOG\"\n"
        "exit \"$PYTHON_EXIT_CODE\"\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)

    fake_uv = fake_bin / "uv"
    fake_uv.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$@\" > \"$UV_ARGS_LOG\"\n",
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["PYTHON_ARGS_LOG"] = str(python_args_log)
    env["PYTHON_EXIT_CODE"] = str(python_exit_code)
    env["UV_ARGS_LOG"] = str(uv_args_log)
    return env, python_args_log, uv_args_log


def test_refresh_hk_current_script_has_valid_bash_syntax():
    result = subprocess.run(
        ["bash", "-n", "scripts/dev/refresh_hk_current.sh"],
        cwd=_repo_root(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_refresh_hk_current_script_help_describes_lightweight_flow():
    result = subprocess.run(
        ["bash", "scripts/dev/refresh_hk_current.sh", "--help"],
        cwd=_repo_root(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--refresh-mode patch" in result.stdout
    assert "--with-package" in result.stdout
    assert "--backup-name NAME" in result.stdout
    assert "tail-window patch refresh" in result.stdout


def test_refresh_hk_current_script_forwards_patch_workflow_defaults(tmp_path):
    env, python_args_log, uv_args_log = _fake_tooling(tmp_path)

    result = subprocess.run(
        [
            "bash",
            "scripts/dev/refresh_hk_current.sh",
            "--target-date",
            "20260410",
            "--config",
            "configs/demo.yml",
            "--with-package",
            "--dry-run",
            "--",
            "--refresh-asset",
            "daily",
        ],
        cwd=_repo_root(),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert python_args_log.read_text(encoding="utf-8").splitlines() == [
        "scripts/internal/run_hk_asset_workflow.py",
        "--phase",
        "refresh",
        "--phase",
        "inspect",
        "--target-date",
        "20260410",
        "--refresh-mode",
        "patch",
        "--gate-on-severity",
        "warning",
        "--inspect-fail-on-severity",
        "none",
        "--daily-patch-lookback-days",
        "20",
        "--dated-patch-lookback-days",
        "40",
        "--phase",
        "package",
        "--resume",
        "--config",
        "configs/demo.yml",
        "--dry-run",
        "--refresh-asset",
        "daily",
    ]
    assert not uv_args_log.exists()


def test_refresh_hk_current_script_runs_optional_backup_after_success(tmp_path):
    env, python_args_log, uv_args_log = _fake_tooling(tmp_path)

    result = subprocess.run(
        [
            "bash",
            "scripts/dev/refresh_hk_current.sh",
            "--target-date",
            "20260410",
            "--no-resume",
            "--gate-on-severity",
            "error",
            "--inspect-fail-on-severity",
            "warning",
            "--backup-name",
            "hk_current_frozen_20260410",
        ],
        cwd=_repo_root(),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    workflow_args = python_args_log.read_text(encoding="utf-8").splitlines()
    assert "--resume" not in workflow_args
    assert "--phase" in workflow_args
    assert "--refresh-mode" in workflow_args
    assert uv_args_log.read_text(encoding="utf-8").splitlines() == [
        "run",
        "cstree",
        "backup-data",
        "--preset",
        "hk_current",
        "--name",
        "hk_current_frozen_20260410",
        "--no-cache",
    ]


def test_refresh_hk_current_script_skips_backup_when_workflow_fails(tmp_path):
    env, _, uv_args_log = _fake_tooling(tmp_path, python_exit_code=2)

    result = subprocess.run(
        [
            "bash",
            "scripts/dev/refresh_hk_current.sh",
            "--target-date",
            "20260410",
            "--backup-name",
            "hk_current_frozen_20260410",
        ],
        cwd=_repo_root(),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 2
    assert not uv_args_log.exists()
