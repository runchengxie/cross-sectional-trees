"""CLI-accessible helper scripts bundled with the project.

.. deprecated::
    This package is deprecated. Use the following imports instead:

    - Commands: ``from csml.commands import run_grid, linear_sweep``
    - Data Tools: ``from csml.data_tools import build_hk_daily_asset_universe, ...``
    - Research Tools: ``from csml.research_tools import summarize_runs, holdings, ...``
"""

import warnings

from .run_grid import main as run_grid
from .linear_sweep import main as linear_sweep

warnings.warn(
    "csml.project_tools is deprecated. Use csml.commands, csml.data_tools, or csml.research_tools instead.",
    DeprecationWarning,
    stacklevel=2,
)
