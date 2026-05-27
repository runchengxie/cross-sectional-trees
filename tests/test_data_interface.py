import logging

import pytest

from cstree.config_utils import resolve_pipeline_config
from cstree.data_interface import DataInterface


def test_data_interface_rejects_unsupported_market(tmp_path):
    with pytest.raises(SystemExit, match="Supported markets: cn, hk"):
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


def test_data_interface_platform_assets_mode_rejects_provider_fallback(tmp_path, monkeypatch):
    import builtins

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "rqdatac":
            raise AssertionError("rqdatac should not be imported in platform asset mode")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    with pytest.raises(SystemExit, match="data.source_mode=platform_assets requires local RQData"):
        DataInterface(
            market="hk",
            data_cfg={
                "provider": "rqdata",
                "source_mode": "platform_assets",
                "rqdata": {
                    "daily_asset_dir": str(tmp_path / "missing_daily"),
                    "instruments_file": str(tmp_path / "missing_instruments.parquet"),
                },
            },
            cache_dir=tmp_path / "cache",
        )


def test_default_config_platform_assets_mode_skips_rqdatac_init(tmp_path, monkeypatch):
    data_root = tmp_path / "market-data-platform-artifacts"
    (data_root / "assets" / "rqdata" / "hk" / "daily" / "hk_all_daily_clean_latest" / "data").mkdir(
        parents=True
    )
    instruments = (
        data_root
        / "assets"
        / "rqdata"
        / "hk"
        / "instruments"
        / "hk_all_instruments_latest.parquet"
    )
    instruments.parent.mkdir(parents=True, exist_ok=True)
    instruments.write_bytes(b"PAR1")
    monkeypatch.setenv("DATA_PLATFORM_ROOT", str(data_root))

    import builtins

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "rqdatac":
            raise AssertionError("default config should not import rqdatac")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    resolved = resolve_pipeline_config("default").data
    interface = DataInterface(
        market=resolved["market"],
        data_cfg=resolved["data"],
        cache_dir=tmp_path / "cache",
    )

    assert interface.client is None


def test_fetch_fundamentals_can_suppress_retry_warning_logs(tmp_path, monkeypatch, caplog):
    interface = DataInterface.__new__(DataInterface)
    interface.market = "hk"
    interface.provider = "rqdata"
    interface.data_cfg = {"provider": "rqdata"}
    interface.cache_dir = tmp_path / "cache"
    interface.logger = logging.getLogger("cstree")
    interface.max_attempts = 1
    interface.backoff_seconds = 0.0
    interface.max_backoff_seconds = 0.0

    def _raise(*_args, **_kwargs):
        raise ValueError("order_book_ids: at least one valid instrument expected, got none")

    monkeypatch.setattr("cstree.data_interface.fetch_fundamentals", _raise)
    caplog.set_level("WARNING", logger="cstree")

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
