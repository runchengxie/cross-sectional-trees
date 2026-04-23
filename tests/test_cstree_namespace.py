import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest


DOCUMENTED_RELEASE_WRAPPERS = (
    "release_tools.package_assets",
    "release_tools.release_assets",
    "release_tools.package_runs",
    "release_tools.release_runs",
)
DOCUMENTED_RESEARCH_WRAPPERS = (
    "research.hk_asset_patch_merge",
    "research.hk_benchmark_attribution",
    "research.hk_connect_cap_weight_benchmark",
    "research.hk_financial_details",
    "research.hk_intraday_download",
    "research.hk_intraday_slippage_report",
    "research.hk_monthly_run_compare",
    "research.hk_selected_provider_valuation_audit",
)
DOCUMENTED_WRAPPERS = DOCUMENTED_RELEASE_WRAPPERS + DOCUMENTED_RESEARCH_WRAPPERS
MAINTENANCE_WRAPPERS = ("release_tools.hk_asset_workflow",)
CSTREE_MODULE_EXECUTION_WRAPPERS = DOCUMENTED_WRAPPERS + MAINTENANCE_WRAPPERS
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
    "data_tools.rqdata_assets",
    "liveops.alloc",
    "liveops.alloc_hk",
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
    PUBLIC_ALIAS_MODULES,
)
def test_cstree_namespace_aliases_existing_csml_modules(module_path):
    cstree_module = importlib.import_module(f"cstree.{module_path}")
    csml_module = importlib.import_module(f"csml.{module_path}")

    assert cstree_module is csml_module


@pytest.mark.parametrize("module_path", CSTREE_MODULE_EXECUTION_WRAPPERS)
def test_cstree_wrapper_delegates_to_csml_main(module_path):
    cstree_module = importlib.import_module(f"cstree.{module_path}")
    csml_module = importlib.import_module(f"csml.{module_path}")

    assert cstree_module.main is csml_module.main


@pytest.mark.parametrize("module_path", CSTREE_MODULE_EXECUTION_WRAPPERS)
def test_cstree_wrapper_module_execution_help(module_path):
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


@pytest.mark.parametrize("module_path", DOCUMENTED_WRAPPERS)
def test_legacy_csml_documented_module_execution_help(module_path):
    env = os.environ.copy()
    src_path = str(Path.cwd() / "src")
    env["PYTHONPATH"] = (
        src_path if not env.get("PYTHONPATH") else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"
    )

    result = subprocess.run(
        [sys.executable, "-m", f"csml.{module_path}", "--help"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()


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
