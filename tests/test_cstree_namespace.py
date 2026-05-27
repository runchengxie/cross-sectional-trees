import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest


DOCUMENTED_RELEASE_MODULES = (
    "release_tools.package_runs",
    "release_tools.release_runs",
)
DOCUMENTED_RESEARCH_MODULES = (
    "research.hk_benchmark_attribution",
    "research.hk_connect_cap_weight_benchmark",
    "research.hk_financial_details",
    "research.hk_intraday_download",
    "research.hk_intraday_slippage_report",
    "research.hk_monthly_run_compare",
    "research.hk_selected_provider_valuation_audit",
)
DOCUMENTED_MODULES = DOCUMENTED_RELEASE_MODULES + DOCUMENTED_RESEARCH_MODULES
MAINTENANCE_MODULES = ()
CSTREE_MODULE_EXECUTION_PATHS = DOCUMENTED_MODULES + MAINTENANCE_MODULES
PUBLIC_ALIAS_MODULES = (
    "artifacts",
    "config_utils",
    "current_assets",
    "data_interface",
    "data_providers",
    "metrics",
    "execution",
    "modeling",
    "pipeline",
    "commands.linear_sweep",
    "commands.run_grid",
    "commands.tune",
    "data_tools.backup_data",
    "data_tools.build_hk_connect_universe",
    "data_tools.build_hk_daily_asset_universe",
    "data_tools.data_warehouse",
    "liveops.alloc",
    "liveops.alloc_hk",
    "liveops.export_targets",
    "liveops.holdings",
    "liveops.snapshot",
    "research.benchmark_ladder",
    "research.construction_grid",
    "research.feature_evidence",
    "research.promotion_gate",
    "research.summarize_runs",
)


@pytest.mark.parametrize(
    "module_path",
    PUBLIC_ALIAS_MODULES + DOCUMENTED_MODULES,
)
def test_public_cstree_modules_import(module_path):
    assert importlib.import_module(f"cstree.{module_path}") is not None


@pytest.mark.parametrize("module_path", CSTREE_MODULE_EXECUTION_PATHS)
def test_cstree_module_execution_help(module_path):
    env = os.environ.copy()
    src_path = str(Path.cwd() / "src")
    env["PYTHONPATH"] = (
        src_path if not env.get("PYTHONPATH") else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"
    )

    result = subprocess.run(
        [sys.executable, "-m", f"cstree.{module_path}", "--help"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()


def test_legacy_csml_import_surface_is_removed():
    env = os.environ.copy()
    src_path = str(Path.cwd() / "src")
    env["PYTHONPATH"] = (
        src_path if not env.get("PYTHONPATH") else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"
    )

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import importlib.util; raise SystemExit(importlib.util.find_spec('csml') is not None)",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0


def test_legacy_csml_module_execution_is_removed():
    env = os.environ.copy()
    src_path = str(Path.cwd() / "src")
    env["PYTHONPATH"] = (
        src_path if not env.get("PYTHONPATH") else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"
    )

    result = subprocess.run(
        [sys.executable, "-m", "csml.release_tools.package_runs", "--help"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode != 0
    assert "No module named" in result.stderr


def test_cstree_package_module_execution_help():
    env = os.environ.copy()
    src_path = str(Path.cwd() / "src")
    env["PYTHONPATH"] = (
        src_path if not env.get("PYTHONPATH") else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"
    )

    result = subprocess.run(
        [sys.executable, "-m", "cstree", "--help"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert "usage: " in result.stdout.lower()
