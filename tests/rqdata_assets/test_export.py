import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import yaml

from csml import data_providers
from csml.data_tools import rqdata_assets

from tests.rqdata_assets._fakes import (
    _FakeRQInstrumentsClient,
)


def test_list_hk_financial_fields_filters_and_writes_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        rqdata_assets,
        "_load_hk_financial_fields",
        lambda: ["revenue", "net_profit", "cash_flow_from_operating_activities"],
    )
    out_path = tmp_path / "hk_fields.txt"

    assert (
        rqdata_assets.list_hk_financial_fields(
            SimpleNamespace(contains=["profit"], limit=None, out=str(out_path))
        )
        == 0
    )

    assert out_path.read_text(encoding="utf-8") == "net_profit\n"
    assert "Wrote 1 HK financial fields" in capsys.readouterr().out

def test_export_hk_instruments_writes_filtered_asset_and_manifest(tmp_path, monkeypatch, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(rqdata_assets, "_ensure_rqdatac_hk_plugin", lambda: None)
    client = _FakeRQInstrumentsClient()
    out_path = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "instruments" / "demo.parquet"

    result = rqdata_assets.export_hk_instruments(
        SimpleNamespace(
            config="hk",
            username=None,
            password=None,
            use_config_universe=False,
            instrument_type="CS",
            symbol=["00005.HK"],
            symbols_file=None,
            by_date_file=None,
            limit=None,
            out=str(out_path),
            force=False,
        ),
        client,
    )

    assert result == 0
    assert client.calls == [{"instrument_type": "CS", "market": "hk"}]
    frame = pd.read_parquet(out_path)
    assert frame["symbol"].tolist() == ["00005.HK"]
    assert int(frame["round_lot"].iloc[0]) == 400

    manifest = yaml.safe_load(Path(f"{out_path}.manifest.yml").read_text(encoding="utf-8"))
    assert manifest["dataset"] == "hk_instruments"
    assert manifest["instrument_type"] == "CS"
    assert manifest["totals"]["symbols"] == 1
    assert manifest["symbol_source"]["mode"] == "explicit"
    assert "Wrote 1 HK instruments" in capsys.readouterr().out

def test_export_hk_instruments_passes_through_instrument_type(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(rqdata_assets, "_ensure_rqdatac_hk_plugin", lambda: None)
    client = _FakeRQInstrumentsClient()
    out_path = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "instruments" / "etf.parquet"

    result = rqdata_assets.export_hk_instruments(
        SimpleNamespace(
            config=None,
            username=None,
            password=None,
            use_config_universe=False,
            instrument_type="etf",
            symbol=[],
            symbols_file=None,
            by_date_file=None,
            limit=1,
            out=str(out_path),
            force=False,
        ),
        client,
    )

    assert result == 0
    assert client.calls == [{"instrument_type": "ETF", "market": "hk"}]

    manifest = yaml.safe_load(Path(f"{out_path}.manifest.yml").read_text(encoding="utf-8"))
    assert manifest["instrument_type"] == "ETF"
