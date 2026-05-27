from __future__ import annotations

import sys

from ._mdp_compat import load_market_data_platform_module

sys.modules[__name__] = load_market_data_platform_module("current_assets")
