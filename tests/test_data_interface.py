import logging

import pytest

from cstree.data_interface import DataInterface


def test_data_interface_rejects_non_hk_market(tmp_path):
    with pytest.raises(SystemExit, match="supports only market='hk'"):
        DataInterface(
            market="legacy-market",
            data_cfg={"provider": "rqdata", "retry": {"max_attempts": 1}},
            cache_dir=tmp_path / "cache",
        )


def test_data_interface_rejects_non_rqdata_provider(tmp_path):
    with pytest.raises(SystemExit, match="supports only provider='rqdata'"):
        DataInterface(
            market="hk",
            data_cfg={"provider": "legacy-provider", "retry": {"max_attempts": 1}},
            cache_dir=tmp_path / "cache",
        )


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


def test_fetch_fundamentals_can_suppress_retry_warning_logs(tmp_path, monkeypatch, caplog):
    interface = DataInterface.__new__(DataInterface)
    interface.market = "hk"
    interface.provider = "rqdata"
    interface.data_cfg = {"provider": "rqdata"}
    interface.cache_dir = tmp_path / "cache"
    interface.logger = logging.getLogger("csml")
    interface.max_attempts = 1
    interface.backoff_seconds = 0.0
    interface.max_backoff_seconds = 0.0

    def _raise(*_args, **_kwargs):
        raise ValueError("order_book_ids: at least one valid instrument expected, got none")

    monkeypatch.setattr("cstree.data_interface.fetch_fundamentals", _raise)
    caplog.set_level("WARNING", logger="csml")

    with pytest.raises(ValueError, match="order_book_ids"):
        interface.fetch_fundamentals(
            "02800.HK",
            "20250101",
            "20250131",
            {"endpoint": "get_factor"},
            log_retry_failures=False,
            log_retry_traceback=False,
        )

    assert not any(
        "Fundamentals load failed for 02800.HK" in record.getMessage()
        for record in caplog.records
    )
