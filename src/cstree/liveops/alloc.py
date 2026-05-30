from __future__ import annotations

"""Compatibility shell for the base live allocation CLI.

Keep public helper names stable here so `alloc_hk` and existing tests can keep
importing `cstree.liveops.alloc`, while the implementation lives in
`alloc_core.py`.
"""

import logging

from dotenv import load_dotenv

from market_data_platform.rqdata_runtime import (
    init_rqdatac as _init_rqdatac_runtime,
    patch_rqdatac_adjust_price_readonly as _patch_rqdatac_adjust_price_readonly,
)
from . import alloc_core as _core
from .alloc_core import (
    _allocate_equal_weight,
    _display_width,
    _extract_price_wide_frame,
    _fetch_latest_price_map,
    _fetch_round_lot_map,
    _format_table,
    _init_rqdatac,
    _ljust_display,
    _load_config,
    _load_holdings_payload,
    _money,
    _prepare_selection,
    _render_text,
    _resolve_market,
    _resolve_price_date,
    _resolve_provider,
    _select_from_positions_file,
    _to_rq_order_book_id,
    main,
)

__all__ = [
    "_allocate_equal_weight",
    "_display_width",
    "_extract_price_wide_frame",
    "_fetch_latest_price_map",
    "_fetch_round_lot_map",
    "_format_table",
    "_init_rqdatac",
    "_patch_rqdatac_adjust_price_readonly",
    "_ljust_display",
    "_load_config",
    "_load_holdings_payload",
    "_money",
    "_prepare_selection",
    "_render_text",
    "_resolve_market",
    "_resolve_price_date",
    "_resolve_provider",
    "_select_from_positions_file",
    "_to_rq_order_book_id",
    "main",
]


def _init_rqdatac(
    config_path: str | None,
    username: str | None,
    password: str | None,
):
    load_dotenv()
    cfg = _load_config(config_path)
    data_cfg = cfg.get("data") if isinstance(cfg, dict) else None
    return _init_rqdatac_runtime(
        data_cfg=data_cfg,
        username=username,
        password=password,
        logger=logging.getLogger("cstree.liveops.alloc"),
        load_env=False,
        error_cls=SystemExit,
        import_error_message="rqdatac is not installed. Install with: pip install '.[rqdata]'",
        patch_fn=_patch_rqdatac_adjust_price_readonly,
    )


# Preserve the public helper surface expected by callers and monkeypatch-based tests.
_core._init_rqdatac = _init_rqdatac


if __name__ == "__main__":
    main()
