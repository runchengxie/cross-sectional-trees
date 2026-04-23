"""Public cstree namespace bridge.

The implementation still lives under :mod:`csml` during the compatibility
window. Public cstree modules intentionally delegate to the existing code.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_CSTREE_ROOT = Path(__file__).resolve().parent


class _CsmlAliasLoader(importlib.abc.Loader):
    def __init__(self, fullname: str, target_name: str) -> None:
        self._fullname = fullname
        self._target_name = target_name

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType:
        module = importlib.import_module(self._target_name)
        sys.modules[self._fullname] = module
        return module

    def exec_module(self, module: ModuleType) -> None:
        return None


class _CsmlAliasFinder(importlib.abc.MetaPathFinder):
    _PREFIX = __name__ + "."
    _TARGET_PREFIX = "csml."

    def find_spec(
        self,
        fullname: str,
        path: object | None = None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        if not fullname.startswith(self._PREFIX) or fullname in sys.modules:
            return None
        if _has_real_cstree_module(fullname, path):
            return None

        target_name = self._TARGET_PREFIX + fullname[len(self._PREFIX) :]
        target_spec = importlib.util.find_spec(target_name)
        if target_spec is None:
            return None

        return importlib.machinery.ModuleSpec(
            fullname,
            _CsmlAliasLoader(fullname, target_name),
            is_package=target_spec.submodule_search_locations is not None,
        )


def _has_real_cstree_module(fullname: str, path: object | None) -> bool:
    search_path = path if isinstance(path, list) else None
    real_spec = importlib.machinery.PathFinder.find_spec(fullname, search_path)
    if real_spec is None:
        return False

    locations = real_spec.submodule_search_locations or ()
    for location in locations:
        if _is_relative_to(Path(location).resolve(), _CSTREE_ROOT):
            return True

    origin = real_spec.origin
    if not origin or origin in {"built-in", "frozen", "namespace"}:
        return False
    return _is_relative_to(Path(origin).resolve(), _CSTREE_ROOT)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _install_csml_alias_finder() -> None:
    if not any(isinstance(finder, _CsmlAliasFinder) for finder in sys.meta_path):
        alias_finder = _CsmlAliasFinder()
        for index, finder in enumerate(sys.meta_path):
            if finder is importlib.machinery.PathFinder:
                sys.meta_path.insert(index, alias_finder)
                break
        else:
            sys.meta_path.append(alias_finder)


_install_csml_alias_finder()
