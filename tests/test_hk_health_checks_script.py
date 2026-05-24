from __future__ import annotations

import subprocess
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_run_hk_health_checks_script_has_valid_bash_syntax():
    result = subprocess.run(
        ["bash", "-n", "scripts/dev/run_hk_health_checks.sh"],
        cwd=_repo_root(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_run_hk_health_checks_defaults_pit_to_current_contract_asset():
    script = (_repo_root() / "scripts" / "dev" / "run_hk_health_checks.sh").read_text(
        encoding="utf-8"
    )

    assert 'PIT_CONFIG=""' in script
    assert 'PIT_DIR="$(read_current_path pit)"' in script
    assert '--asset-dir "${PIT_DIR}"' in script
    assert '--symbols-file "${DAILY_CLEAN_DIR}/symbols.txt"' in script
    assert "--field operating_revenue" in script
    assert "configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml" not in script
