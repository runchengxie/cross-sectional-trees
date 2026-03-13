import pytest

from csml.data_interface import DataInterface


def test_data_interface_ignores_legacy_tushare_alias(tmp_path, monkeypatch):
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    monkeypatch.delenv("TUSHARE_TOKEN_2", raising=False)
    monkeypatch.setenv("TUSHARE_API_KEY", "legacy-only")

    with pytest.raises(SystemExit, match="Please set TUSHARE_TOKEN or TUSHARE_TOKEN_2 first."):
        DataInterface(
            market="cn",
            data_cfg={"provider": "tushare", "retry": {"max_attempts": 1}},
            cache_dir=tmp_path / "cache",
        )


def test_data_interface_loads_primary_tushare_tokens_only(tmp_path, monkeypatch):
    monkeypatch.setenv("TUSHARE_TOKEN", "primary")
    monkeypatch.setenv("TUSHARE_TOKEN_2", "secondary")
    monkeypatch.setenv("TUSHARE_API_KEY", "legacy-only")

    def _fail_make_client(_self, _token):
        raise RuntimeError("stop after token collection")

    monkeypatch.setattr(DataInterface, "_make_tushare_client", _fail_make_client)

    with pytest.raises(RuntimeError, match="stop after token collection"):
        DataInterface(
            market="cn",
            data_cfg={"provider": "tushare", "retry": {"max_attempts": 1}},
            cache_dir=tmp_path / "cache",
        )

    interface = DataInterface.__new__(DataInterface)
    tokens = DataInterface._load_tushare_tokens(interface)
    assert tokens == ["primary", "secondary"]


def test_data_interface_skips_rqdatac_init_when_local_assets_configured(tmp_path, monkeypatch):
    asset_dir = tmp_path / "daily_assets"
    (asset_dir / "data").mkdir(parents=True, exist_ok=True)
    instruments = tmp_path / "hk_instruments.parquet"
    instruments.write_bytes(b"PAR1")

    import builtins

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "rqdatac":
            raise AssertionError("rqdatac should not be imported in local asset mode")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    interface = DataInterface(
        market="hk",
        data_cfg={
            "provider": "rqdata",
            "rqdata": {
                "daily_asset_dir": str(asset_dir),
                "instruments_file": str(instruments),
            },
        },
        cache_dir=tmp_path / "cache",
    )

    assert interface.client is None
