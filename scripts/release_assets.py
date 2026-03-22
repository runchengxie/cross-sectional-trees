#!/usr/bin/env python3
"""Compatibility wrapper for scripts/release/release_assets.py."""

from pathlib import Path


_TARGET = Path(__file__).resolve().parent / "release" / "release_assets.py"
globals()["__file__"] = str(_TARGET)
with _TARGET.open("r", encoding="utf-8") as _handle:
    exec(compile(_handle.read(), str(_TARGET), "exec"), globals(), globals())
