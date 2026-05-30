from __future__ import annotations

import sys

from .._mdp_compat import load_market_data_platform_module

_symbols = load_market_data_platform_module("symbols")

canonicalize_symbol_columns = _symbols.canonicalize_symbol_columns
drop_legacy_symbol_columns = _symbols.drop_legacy_symbol_columns
ensure_symbol_columns = _symbols.ensure_symbol_columns
normalize_symbol_for_market = _symbols.normalize_symbol_for_market

sys.modules[__name__] = _symbols
