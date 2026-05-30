import pandas as pd
from market_data_platform.hk_assets import (
    build_hk_connect_universe as platform_hk_universe,
    build_hk_daily_asset_universe as platform_hk_daily_assets,
)

from cstree.data_tools import (
    build_hk_connect_universe as hk_universe,
    build_hk_daily_asset_universe as hk_daily_assets,
)


def test_hk_connect_universe_uses_market_data_platform_backend():
    assert hk_universe.normalize_date_token is platform_hk_universe.normalize_date_token
    assert hk_universe.format_output_path is platform_hk_universe.format_output_path


def test_hk_daily_asset_universe_uses_market_data_platform_backend():
    assert hk_daily_assets.build_universe_frame is platform_hk_daily_assets.build_universe_frame

    liq = pd.Series(
        [10.0, 30.0, 20.0],
        index=["00005.XHKG", "00700.XHKG", "00001.XHKG"],
    )

    selected = hk_daily_assets.select_liquid_symbols(liq, 0.0)

    assert selected.index.tolist() == ["00700.XHKG", "00001.XHKG", "00005.XHKG"]
