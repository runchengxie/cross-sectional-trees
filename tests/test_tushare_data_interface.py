import builtins

import pandas as pd

from cstree.data_interface import DataInterface


def test_data_interface_accepts_tushare_platform_assets_without_rqdatac(tmp_path, monkeypatch):
    asset_dir = tmp_path / "a_share_daily_clean"
    (asset_dir / "data").mkdir(parents=True, exist_ok=True)
    instruments = tmp_path / "a_share_instruments.parquet"
    pd.DataFrame(
        {
            "ts_code": ["600519.SH"],
            "name": ["贵州茅台"],
            "list_date": ["20010827"],
        }
    ).to_parquet(instruments)

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "rqdatac":
            raise AssertionError("rqdatac should not be imported for TuShare platform assets")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    interface = DataInterface(
        market="a_share",
        data_cfg={
            "provider": "tushare",
            "source_mode": "platform_assets",
            "tushare": {
                "daily_asset_dir": str(asset_dir),
                "instruments_file": str(instruments),
            },
        },
        cache_dir=tmp_path / "cache",
    )

    assert interface.provider == "tushare"
    assert interface.client is None
