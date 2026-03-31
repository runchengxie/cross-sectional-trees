import shutil
import subprocess
from pathlib import Path

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "script_path",
    [
        ".githooks/pre-commit",
        ".githooks/pre-push",
        "scripts/dev/install_git_hooks.sh",
    ],
)
def test_git_hook_scripts_have_valid_bash_syntax(script_path: str):
    repo_root = _repo_root()
    result = subprocess.run(
        ["bash", "-n", script_path],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_install_git_hooks_script_sets_repo_local_hook_path(tmp_path: Path):
    source_root = _repo_root()
    repo_root = tmp_path / "repo"
    (repo_root / ".githooks").mkdir(parents=True)
    (repo_root / "scripts" / "dev").mkdir(parents=True)

    shutil.copy2(source_root / ".githooks" / "pre-commit", repo_root / ".githooks" / "pre-commit")
    shutil.copy2(source_root / ".githooks" / "pre-push", repo_root / ".githooks" / "pre-push")
    shutil.copy2(
        source_root / "scripts" / "dev" / "install_git_hooks.sh",
        repo_root / "scripts" / "dev" / "install_git_hooks.sh",
    )

    init = subprocess.run(
        ["git", "init"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert init.returncode == 0, init.stderr

    result = subprocess.run(
        ["bash", "scripts/dev/install_git_hooks.sh"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    hook_path = subprocess.run(
        ["git", "config", "--local", "--get", "core.hooksPath"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert hook_path.returncode == 0, hook_path.stderr
    assert hook_path.stdout.strip() == ".githooks"
