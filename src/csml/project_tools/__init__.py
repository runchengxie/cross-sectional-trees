"""CLI-accessible helper scripts bundled with the project.

.. deprecated::
    This package is deprecated. Use the following imports instead:

    - Commands: ``from csml.commands import run_grid, linear_sweep``
    - Data Tools: ``from csml.data_tools import build_hk_daily_asset_universe, ...``
    - Research: ``from csml.research import summarize_runs``
    - LiveOps: ``from csml.liveops import snapshot, holdings, alloc``
"""

import warnings

from .run_grid import main as run_grid
from .linear_sweep import main as linear_sweep

warnings.warn(
    "csml.project_tools is deprecated. Use csml.commands, csml.research, or csml.liveops instead.",
    DeprecationWarning,
    stacklevel=2,
)
