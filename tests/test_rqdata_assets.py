from types import SimpleNamespace

import pandas as pd
import yaml

from csml.project_tools import rqdata_assets


class _FakeRQPitClient:
    def __init__(self):
        self.calls: list[dict] = []

    def get_pit_financials_ex(
        self,
        *,
        order_book_ids,
        fields,
        start_quarter,
        end_quarter,
        date=None,
        statements="latest",
        market="hk",
    ):
        self.calls.append(
            {
                "order_book_ids": list(order_book_ids),
                "fields": list(fields),
                "start_quarter": start_quarter,
                "end_quarter": end_quarter,
                "date": date,
                "statements": statements,
                "market": market,
            }
        )
        rows: list[dict] = []
        index: list[tuple[str, str]] = []
        for order_book_id in order_book_ids:
            if order_book_id == "00005.XHKG":
                rows.extend(
                    [
                        {
                            "info_date": pd.Timestamp("2025-03-20"),
                            "fiscal_year": pd.Timestamp("2024-12-31"),
                            "standard": "IFRS",
                            "if_adjusted": 0,
                            "rice_create_tm": pd.Timestamp("2025-03-20 09:00:00"),
                            "revenue": 100.0,
                            "net_profit": 10.0,
                        },
                        {
                            "info_date": pd.Timestamp("2025-08-20"),
                            "fiscal_year": pd.Timestamp("2025-12-31"),
                            "standard": "IFRS",
                            "if_adjusted": 0,
                            "rice_create_tm": pd.Timestamp("2025-08-20 09:00:00"),
                            "revenue": 120.0,
                            "net_profit": 12.0,
                        },
                    ]
                )
                index.extend([(order_book_id, "2024q4"), (order_book_id, "2025q1")])
            elif order_book_id == "00011.XHKG":
                rows.append(
                    {
                        "info_date": pd.Timestamp("2025-08-25"),
                        "fiscal_year": pd.Timestamp("2025-12-31"),
                        "standard": "IFRS",
                        "if_adjusted": 1,
                        "rice_create_tm": pd.Timestamp("2025-08-25 09:00:00"),
                        "revenue": 220.0,
                        "net_profit": 22.0,
                    }
                )
                index.append((order_book_id, "2025q1"))
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(
            rows,
            index=pd.MultiIndex.from_tuples(index, names=["order_book_id", "quarter"]),
        )


class _FakeRQHKApi:
    def __init__(self):
        self.calls: list[dict] = []

    def get_detailed_financial_items(
        self,
        *,
        order_book_ids,
        fields,
        start_quarter,
        end_quarter,
        date=None,
        statements="latest",
        market="hk",
    ):
        self.calls.append(
            {
                "order_book_ids": list(order_book_ids),
                "fields": list(fields),
                "start_quarter": start_quarter,
                "end_quarter": end_quarter,
                "date": date,
                "statements": statements,
                "market": market,
            }
        )
        rows = [
            {
                "info_date": pd.Timestamp("2025-03-20"),
                "fiscal_year": pd.Timestamp("2024-12-31"),
                "field": "revenue",
                "relationship": 1.0,
                "amount": 70.0,
                "currency": "港元",
                "subject": "保费收入",
                "standard": "IFRS",
                "if_adjusted": 0,
            },
            {
                "info_date": pd.Timestamp("2025-03-20"),
                "fiscal_year": pd.Timestamp("2024-12-31"),
                "field": "revenue",
                "relationship": 1.0,
                "amount": 30.0,
                "currency": "港元",
                "subject": "手续费收入",
                "standard": "IFRS",
                "if_adjusted": 0,
            },
        ]
        return pd.DataFrame(
            rows,
            index=pd.MultiIndex.from_tuples(
                [("00005.XHKG", "2024q4"), ("00005.XHKG", "2024q4")],
                names=["order_book_id", "quarter"],
            ),
        )


class _FakeRQDetailsClient:
    def __init__(self):
        self.hk = _FakeRQHKApi()


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


def test_mirror_hk_pit_financials_uses_config_universe_and_writes_manifest(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    (repo_root / "config").mkdir(parents=True)
    (repo_root / "out" / "universe").mkdir(parents=True)
    (repo_root / "config" / "hk_assets.yml").write_text(
        "\n".join(
            [
                "market: hk",
                "universe:",
                "  mode: pit",
                "  symbols: []",
                "  symbols_file: null",
                "  by_date_file: out/universe/universe_by_date.csv",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (repo_root / "config" / "pit_fields.txt").write_text(
        "revenue\nnet_profit\n",
        encoding="utf-8",
    )
    (repo_root / "out" / "universe" / "universe_by_date.csv").write_text(
        "\n".join(
            [
                "trade_date,ts_code,selected",
                "20250131,5.HK,1",
                "20250131,00011.XHKG,1",
                "20250228,00005.HK,1",
                "20250228,00012.HK,0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(repo_root)

    client = _FakeRQPitClient()
    args = SimpleNamespace(
        config="config/hk_assets.yml",
        username=None,
        password=None,
        start_quarter="2024q4",
        end_quarter="2025q1",
        date="20260310",
        statements="latest",
        field=[],
        fields_file=["config/pit_fields.txt"],
        symbol=[],
        symbols_file=None,
        by_date_file=None,
        limit=None,
        batch_size=1,
        out_root="data_assets/rqdata",
        name="pit_demo",
    )

    assert rqdata_assets.mirror_hk_pit_financials(args, client) == 0

    assert client.calls == [
        {
            "order_book_ids": ["00005.XHKG"],
            "fields": ["revenue", "net_profit"],
            "start_quarter": "2024q4",
            "end_quarter": "2025q1",
            "date": "20260310",
            "statements": "latest",
            "market": "hk",
        },
        {
            "order_book_ids": ["00011.XHKG"],
            "fields": ["revenue", "net_profit"],
            "start_quarter": "2024q4",
            "end_quarter": "2025q1",
            "date": "20260310",
            "statements": "latest",
            "market": "hk",
        },
    ]

    output_dir = repo_root / "data_assets" / "rqdata" / "hk" / "pit_financials" / "pit_demo"
    assert (output_dir / "fields.txt").read_text(encoding="utf-8") == "revenue\nnet_profit\n"
    assert (output_dir / "symbols.txt").read_text(encoding="utf-8") == "00005.HK\n00011.HK\n"

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    assert manifest["dataset"] == "pit_financials"
    assert manifest["api"] == "rqdatac.get_pit_financials_ex"
    assert manifest["symbol_source"]["mode"] == "config_universe"
    assert manifest["query"]["fields"] == ["revenue", "net_profit"]
    assert manifest["totals"]["symbols_requested"] == 2
    assert manifest["totals"]["symbols_written"] == 2
    assert manifest["missing_symbols"] == []

    first = pd.read_parquet(output_dir / "data" / "00005.HK.parquet")
    assert first["ts_code"].tolist() == ["00005.HK", "00005.HK"]
    assert first["order_book_id"].tolist() == ["00005.XHKG", "00005.XHKG"]
    assert first["quarter"].tolist() == ["2024q4", "2025q1"]
    assert set(["revenue", "net_profit", "info_date", "fiscal_year"]).issubset(first.columns)


def test_mirror_hk_financial_details_tracks_missing_symbols(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(rqdata_assets, "_ensure_rqdatac_hk_plugin", lambda: None)

    client = _FakeRQDetailsClient()
    args = SimpleNamespace(
        config=None,
        username=None,
        password=None,
        start_quarter="2024q4",
        end_quarter="2024q4",
        date="20260310",
        statements="latest",
        field=["revenue"],
        fields_file=[],
        symbol=["5.hk", "00011.XHKG"],
        symbols_file=None,
        by_date_file=None,
        limit=None,
        batch_size=20,
        out_root="data_assets/rqdata",
        name="details_demo",
    )

    assert rqdata_assets.mirror_hk_financial_details(args, client) == 0

    assert client.hk.calls == [
        {
            "order_book_ids": ["00005.XHKG", "00011.XHKG"],
            "fields": ["revenue"],
            "start_quarter": "2024q4",
            "end_quarter": "2024q4",
            "date": "20260310",
            "statements": "latest",
            "market": "hk",
        }
    ]

    output_dir = repo_root / "data_assets" / "rqdata" / "hk" / "financial_details" / "details_demo"
    detail = pd.read_parquet(output_dir / "data" / "00005.HK.parquet")
    assert detail["ts_code"].tolist() == ["00005.HK", "00005.HK"]
    assert detail["field"].tolist() == ["revenue", "revenue"]
    assert detail["subject"].tolist() == ["保费收入", "手续费收入"]

    manifest = yaml.safe_load((output_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["dataset"] == "financial_details"
    assert manifest["totals"]["symbols_requested"] == 2
    assert manifest["totals"]["symbols_written"] == 1
    assert manifest["missing_symbols"] == ["00011.HK"]


def test_build_hk_pit_fundamentals_file_writes_pipeline_ready_output(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    asset_dir = repo_root / "data_assets" / "rqdata" / "hk" / "pit_financials" / "pit_demo"
    data_dir = asset_dir / "data"
    data_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    manifest = {
        "dataset": "pit_financials",
        "query": {"fields": ["revenue", "net_profit"]},
        "columns": [
            "quarter",
            "info_date",
            "fiscal_year",
            "standard",
            "if_adjusted",
            "rice_create_tm",
            "revenue",
            "net_profit",
            "order_book_id",
            "ts_code",
        ],
    }
    (asset_dir / "manifest.yml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    pd.DataFrame(
        {
            "quarter": ["2024q4", "2024q4", "2025q1"],
            "info_date": pd.to_datetime(["2025-03-20", "2025-03-20", "2025-08-20"]),
            "fiscal_year": pd.to_datetime(["2024-12-31", "2024-12-31", "2025-12-31"]),
            "standard": ["IFRS", "IFRS", "IFRS"],
            "if_adjusted": [0, 1, 0],
            "rice_create_tm": pd.to_datetime(
                ["2025-03-20 09:00:00", "2025-03-20 10:00:00", "2025-08-20 09:00:00"]
            ),
            "revenue": [100.0, 101.0, 120.0],
            "net_profit": [10.0, 11.0, 12.0],
            "order_book_id": ["00005.XHKG", "00005.XHKG", "00005.XHKG"],
            "ts_code": ["00005.HK", "00005.HK", "00005.HK"],
        }
    ).to_parquet(data_dir / "00005.HK.parquet", index=False)
    pd.DataFrame(
        {
            "quarter": ["2025q1"],
            "info_date": pd.to_datetime(["2025-08-25"]),
            "fiscal_year": pd.to_datetime(["2025-12-31"]),
            "standard": ["IFRS"],
            "if_adjusted": [0],
            "rice_create_tm": pd.to_datetime(["2025-08-25 09:00:00"]),
            "revenue": [220.0],
            "net_profit": [22.0],
            "order_book_id": ["00011.XHKG"],
            "ts_code": ["00011.HK"],
        }
    ).to_parquet(data_dir / "00011.HK.parquet", index=False)

    out_path = repo_root / "out" / "pit_fundamentals.parquet"
    args = SimpleNamespace(
        asset_dir=str(asset_dir),
        field=[],
        fields_file=[],
        out=str(out_path),
        keep_meta=False,
        duplicate_policy="keep-last",
        force=False,
    )

    assert rqdata_assets.build_hk_pit_fundamentals_file(args) == 0

    fundamentals = pd.read_parquet(out_path)
    assert fundamentals.columns.tolist() == ["trade_date", "ts_code", "revenue", "net_profit"]
    assert fundamentals["trade_date"].tolist() == ["20250320", "20250820", "20250825"]
    assert fundamentals["ts_code"].tolist() == ["00005.HK", "00005.HK", "00011.HK"]
    assert fundamentals["revenue"].tolist() == [101.0, 120.0, 220.0]
    assert fundamentals["net_profit"].tolist() == [11.0, 12.0, 22.0]

    output_manifest = yaml.safe_load(
        (repo_root / "out" / "pit_fundamentals.manifest.yml").read_text(encoding="utf-8")
    )
    assert output_manifest["dataset"] == "pit_fundamentals_file"
    assert output_manifest["query"]["fields"] == ["revenue", "net_profit"]
    assert output_manifest["totals"]["input_files"] == 2
    assert output_manifest["totals"]["output_rows"] == 3
    assert output_manifest["totals"]["duplicate_rows_seen"] == 2
    assert output_manifest["totals"]["duplicate_rows_dropped"] == 1
