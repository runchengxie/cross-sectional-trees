from __future__ import annotations

import sys

from .._mdp_compat import load_market_data_platform_module

sys.modules[__name__] = load_market_data_platform_module("hk_assets.build_hk_daily_asset_universe")
