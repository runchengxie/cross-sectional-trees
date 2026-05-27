from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType


def _add_workspace_mdp_source() -> None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "market-data-platform" / "src"
        if candidate.is_dir():
            candidate_text = str(candidate)
            if candidate_text not in sys.path:
                sys.path.insert(0, candidate_text)
            return


def load_market_data_platform_module(module_name: str) -> ModuleType:
    qualified_name = f"market_data_platform.{module_name}"
    try:
        return importlib.import_module(qualified_name)
    except ModuleNotFoundError as exc:
        if exc.name != "market_data_platform":
            raise
        _add_workspace_mdp_source()
        try:
            return importlib.import_module(qualified_name)
        except ModuleNotFoundError as retry_exc:
            if retry_exc.name != "market_data_platform":
                raise
            raise ModuleNotFoundError(
                "market-data-platform is required for shared data platform helpers. "
                "Install it or run from the research-workspace checkout."
            ) from exc
