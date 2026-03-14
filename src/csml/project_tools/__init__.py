"""CLI-accessible helper scripts bundled with the project.

.. deprecated::
    This package is deprecated. Use the following imports instead:

    - Commands: ``from csml.commands import run_grid, linear_sweep``
    - Data Tools: ``from csml.data_tools import build_hk_daily_asset_universe, ...``
    - Research: ``from csml.research import summarize_runs``
    - LiveOps: ``from csml.liveops import snapshot, holdings, alloc``
"""

import warnings

# Use lazy imports to avoid circular import issues
# These imports will only happen when the attributes are actually accessed


def __getattr__(name):
    """Provide backwards compatibility with lazy imports to avoid circular dependencies."""
    if name == "run_grid":
        from csml.commands.run_grid import main as _run_grid
        return _run_grid
    elif name == "linear_sweep":
        from csml.commands.linear_sweep import main as _linear_sweep
        return _linear_sweep
    elif name in ("holdings", "snapshot", "alloc"):
        from csml import liveops as _liveops
        return getattr(_liveops, name)
    elif name == "summarize_runs":
        from csml.research_tools.summarize_runs import main as _summarize_runs
        return _summarize_runs
    elif name == "rqdata_assets":
        warnings.warn(
            "csml.project_tools.rqdata_assets is deprecated. "
            "Import directly from csml.data_tools.rqdata_assets instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        import csml.data_tools.rqdata_assets as _rqdata_assets
        return _rqdata_assets
    elif name in (
        "mirror_hk_daily",
        "mirror_hk_pit_financials",
        "mirror_hk_financial_details",
        "build_hk_pit_fundamentals_file",
        "export_hk_instruments",
        "list_hk_financial_fields",
        "inspect_hk_pit_coverage",
    ):
        import csml.data_tools.rqdata_assets as _rqdata_assets
        return getattr(_rqdata_assets, name)
    elif name == "build_hk_connect_universe":
        from csml.data_tools.build_hk_connect_universe import main as _build_hk_connect_universe
        return _build_hk_connect_universe
    elif name == "build_hk_daily_asset_universe":
        from csml.data_tools.build_hk_daily_asset_universe import main as _build_hk_daily_asset_universe
        return _build_hk_daily_asset_universe
    elif name == "fetch_index_components":
        from csml.data_tools.fetch_index_components import main as _fetch_index_components
        return _fetch_index_components
    elif name == "verify_tushare_tokens":
        from csml.data_tools.verify_tushare_tokens import main as _verify_tushare_tokens
        return _verify_tushare_tokens
    elif name == "migrate_artifacts":
        from csml.data_tools.migrate_artifacts import main as _migrate_artifacts
        return _migrate_artifacts
    elif name == "backup_data":
        from csml.data_tools.backup_data import main as _backup_data
        return _backup_data
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
