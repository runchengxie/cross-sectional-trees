#!/usr/bin/env python3
"""Compatibility wrapper for scripts/research/merge_hk_selected_provider_valuation_into_pit.py."""

from pathlib import Path


_TARGET = (
    Path(__file__).resolve().parent
    / "research"
    / "merge_hk_selected_provider_valuation_into_pit.py"
)
globals()["__file__"] = str(_TARGET)
with _TARGET.open("r", encoding="utf-8") as _handle:
    exec(compile(_handle.read(), str(_TARGET), "exec"), globals(), globals())
