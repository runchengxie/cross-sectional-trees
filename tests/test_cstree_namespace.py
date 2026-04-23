import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest


DOCUMENTED_RELEASE_WRAPPERS = (
    "release_tools.hk_asset_workflow",
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


@pytest.mark.parametrize(
    "module_path",
    (
        "artifacts",
        "current_assets",
        "data_interface",
        "data_providers",
        "metrics",
        "execution",
        "modeling",
        "pipeline",
        "liveops.alloc_hk",
        "data_tools.rqdata_assets",
    ),
)
def test_cstree_namespace_aliases_existing_csml_modules(module_path):
    cstree_module = importlib.import_module(f"cstree.{module_path}")
    csml_module = importlib.import_module(f"csml.{module_path}")

    assert cstree_module is csml_module


@pytest.mark.parametrize("module_path", DOCUMENTED_WRAPPERS)
def test_documented_cstree_wrapper_delegates_to_csml_main(module_path):
    cstree_module = importlib.import_module(f"cstree.{module_path}")
    csml_module = importlib.import_module(f"csml.{module_path}")

    assert cstree_module.main is csml_module.main


@pytest.mark.parametrize("module_path", DOCUMENTED_WRAPPERS)
def test_documented_cstree_wrapper_module_execution_help(module_path):
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
