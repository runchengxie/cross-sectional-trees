"""Packaged configuration templates.

This package provides backward compatibility by loading configs from configs/presets/.
"""

from pathlib import Path

# For backward compatibility, configs are now stored in configs/presets/
# This package provides the csml.config interface for existing code
_CONFIG_PRESETS_DIR = Path(__file__).parent.parent.parent / "configs" / "presets"


def _list_config_files():
    """List available config files."""
    if not _CONFIG_PRESETS_DIR.exists():
        return []
    return [f.name for f in _CONFIG_PRESETS_DIR.glob("*.yml")]


__all__ = ["_CONFIG_PRESETS_DIR", "_list_config_files"]
