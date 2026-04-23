from __future__ import annotations

import sys


_MISSING = object()


def _package_attr(name: str, *, default=_MISSING):
    package = sys.modules.get("cstree.data_tools.rqdata_assets")
    if package is None:
        if default is not _MISSING:
            return default
        raise RuntimeError("cstree.data_tools.rqdata_assets package is not loaded.")
    value = getattr(package, name, _MISSING)
    if value is _MISSING:
        if default is not _MISSING:
            return default
        raise AttributeError(
            f"cstree.data_tools.rqdata_assets has no attribute {name!r}."
        )
    return value
