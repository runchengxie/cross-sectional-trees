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
