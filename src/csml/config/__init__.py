"""Repository-backed configuration template helpers.

This package keeps the legacy ``csml.config`` import surface, but the source of
truth is the repository ``configs/presets/`` tree rather than packaged YAML
resources.
"""

from pathlib import Path

from ..config_utils import resolve_repo_configs_dir


def _resolve_presets_dir() -> Path:
    try:
        return resolve_repo_configs_dir() / "presets"
    except SystemExit:
        return Path.cwd().resolve() / "configs" / "presets"


_CONFIG_PRESETS_DIR = _resolve_presets_dir()


def _list_config_files():
    """List available config files."""
    if not _CONFIG_PRESETS_DIR.exists():
        return []
    return [f.name for f in _CONFIG_PRESETS_DIR.glob("*.yml")]


__all__ = ["_CONFIG_PRESETS_DIR", "_list_config_files"]
