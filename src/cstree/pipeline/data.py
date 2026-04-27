from __future__ import annotations

"""Compatibility re-exports for legacy pipeline data helpers.

Internal code should import from ``feature_dataset`` and ``panel_loader``
directly. Keep this shim only for short-term external import compatibility.
"""

import warnings

from ..compat import ensure_numpy_nan_alias
from .feature_dataset import _prepare_feature_dataset
from .panel_loader import _load_research_panel

warnings.warn(
    "cstree.pipeline.data is deprecated; import from "
    "cstree.pipeline.feature_dataset or cstree.pipeline.panel_loader instead.",
    DeprecationWarning,
    stacklevel=2,
)

ensure_numpy_nan_alias()

__all__ = ["_load_research_panel", "_prepare_feature_dataset"]
