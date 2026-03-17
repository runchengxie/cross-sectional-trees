"""CLI-accessible helper scripts bundled with the project.

.. deprecated::
    This package is deprecated. Use the following imports instead:

    - Commands: ``from csml.commands import run_grid, linear_sweep``
    - Data Tools: ``from csml.data_tools import build_hk_daily_asset_universe, ...``
    - Research: ``from csml.research import summarize_runs``
    - LiveOps: ``from csml.liveops import snapshot, holdings, alloc``
"""

from importlib import import_module
import warnings

# Use lazy imports to avoid circular import issues
# These imports will only happen when the attributes are actually accessed


def __getattr__(name):
    """Provide backwards compatibility with lazy imports to avoid circular dependencies."""
    if name == "run_grid":
        return import_module("csml.commands.run_grid")
    elif name == "linear_sweep":
        return import_module("csml.commands.linear_sweep")
    elif name in ("holdings", "snapshot", "alloc"):
        return import_module(f"csml.research_tools.{name}")
    elif name == "summarize_runs":
        return import_module("csml.research_tools.summarize_runs")
    elif name == "rqdata_assets":
        warnings.warn(
            "csml.project_tools.rqdata_assets is deprecated. "
            "Import directly from csml.data_tools.rqdata_assets instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return import_module("csml.data_tools.rqdata_assets")
    elif name in (
        "mirror_hk_daily",
        "mirror_hk_pit_financials",
        "mirror_hk_financial_details",
        "mirror_hk_ex_factors",
        "mirror_hk_dividends",
        "mirror_hk_shares",
        "build_hk_pit_fundamentals_file",
        "export_hk_instruments",
        "list_hk_financial_fields",
        "inspect_hk_pit_coverage",
    ):
        _rqdata_assets = import_module("csml.data_tools.rqdata_assets")
        return getattr(_rqdata_assets, name)
    elif name == "build_hk_connect_universe":
        return import_module("csml.data_tools.build_hk_connect_universe")
    elif name == "build_hk_daily_asset_universe":
        return import_module("csml.data_tools.build_hk_daily_asset_universe")
    elif name == "fetch_index_components":
        return import_module("csml.data_tools.fetch_index_components")
    elif name == "verify_tushare_tokens":
        return import_module("csml.data_tools.verify_tushare_tokens")
    elif name == "migrate_artifacts":
        return import_module("csml.data_tools.migrate_artifacts")
    elif name == "backup_data":
        return import_module("csml.data_tools.backup_data")
    elif name == "ensure_symbol_columns":
        from csml.data_tools.symbols import ensure_symbol_columns as _ensure_symbol_columns
        return _ensure_symbol_columns
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Emit deprecation warning when the module is imported
warnings.warn(
    "csml.project_tools is deprecated. Use csml.commands, csml.data_tools, csml.research, or csml.liveops instead.",
    DeprecationWarning,
    stacklevel=2,
)
