import sys
from types import SimpleNamespace

import pytest

from csml import cli
from csml import pipeline as pipeline_module
from csml.cli import common as cli_common
from csml.config_utils import resolve_pipeline_config, resolve_repo_preset_path
from csml.data_tools import build_hk_connect_universe as hk_connect_tool
from csml.data_tools import build_hk_daily_asset_universe as hk_daily_assets_tool


def test_cli_parses_run_command():
    parser = cli.build_parser()
    args = parser.parse_args(["run", "--config", "default", "--fail-on-quality", "warning"])
    assert args.command == "run"
    assert args.config == "default"
    assert args.fail_on_quality == "warning"
    assert callable(args.func)


def test_default_builtin_config_is_hk_first():
    resolved = resolve_pipeline_config(None)
    assert resolved.data["market"] == "hk"
    assert resolved.data["data"]["provider"] == "rqdata"


def test_cli_parses_data_commands():
    parser = cli.build_parser()

    catalog = parser.parse_args(
        [
            "data",
            "catalog",
            "--artifacts-root",
            "artifacts",
            "--db-path",
            "artifacts/metadata/catalog.sqlite",
        ]
    )
    assert catalog.command == "data"
    assert catalog.data_command == "catalog"
    assert catalog.db_path == "artifacts/metadata/catalog.sqlite"
    assert callable(catalog.func)

    materialize = parser.parse_args(
        [
            "data",
            "materialize",
            "--name",
            "hk_daily_panel",
            "--preset",
            "rqdata-daily",
            "--asset-dir",
            "artifacts/assets/rqdata/hk/daily/hk_all_daily_latest",
            "--frequency",
            "M",
        ]
    )
    assert materialize.command == "data"
    assert materialize.data_command == "materialize"
    assert materialize.name == "hk_daily_panel"
    assert materialize.preset == "rqdata-daily"
    assert materialize.frequency == "M"
    assert callable(materialize.func)

    query = parser.parse_args(
        [
            "data",
            "query",
            "--sql",
            "select * from standardized.hk_daily_panel limit 5",
            "--format",
            "json",
        ]
    )
    assert query.command == "data"
    assert query.data_command == "query"
    assert query.format == "json"
    assert callable(query.func)


def test_append_passthrough_strips_leading_separator():
    argv: list[str] = []
    cli_common.append_passthrough(argv, ["--", "--start-date", "20250101"])
    assert argv == ["--start-date", "20250101"]


def test_init_rqdatac_applies_adjust_price_patch(monkeypatch):
    init_calls: list[dict] = []
    patch_calls: list[str] = []

    class _FakeRQDatac:
        def init(self, **kwargs):
            init_calls.append(dict(kwargs))

    fake_rqdatac = _FakeRQDatac()
    monkeypatch.setitem(sys.modules, "rqdatac", fake_rqdatac)
    monkeypatch.setattr(cli_common, "load_dotenv", lambda: None)
    monkeypatch.setattr(cli_common, "load_config", lambda path: {})
    monkeypatch.setattr(
        cli_common,
        "_patch_rqdatac_adjust_price_readonly",
        lambda logger: patch_calls.append(logger.name),
    )

    result = cli_common.init_rqdatac(SimpleNamespace(config=None, username=None, password=None))

    assert result is fake_rqdatac
    assert init_calls == [{}]
    assert patch_calls == ["csml.cli.rqdata"]


def test_cli_parses_init_config_and_universe():
    parser = cli.build_parser()

    init_cfg = parser.parse_args(
        ["init-config", "--market", "hk", "--out", "configs/presets/", "--force"]
    )
    assert init_cfg.command == "init-config"
    assert init_cfg.market == "hk"
    assert init_cfg.out == "configs/presets/"
    assert init_cfg.force is True
    assert callable(init_cfg.func)

    hk_connect = parser.parse_args(
        [
            "universe",
            "hk-connect",
            "--config",
            "configs/presets/universe/hk_connect.yml",
            "--",
            "--mode",
            "daily",
            "--start-date",
            "20250101",
        ]
    )
    assert hk_connect.command == "universe"
    assert hk_connect.uni_command == "hk-connect"
    assert hk_connect.config == "configs/presets/universe/hk_connect.yml"
    assert hk_connect.args == ["--", "--mode", "daily", "--start-date", "20250101"]
    assert callable(hk_connect.func)

    hk_daily_assets = parser.parse_args(
        [
            "universe",
            "hk-daily-assets",
            "--config",
            "configs/presets/universe/hk_all_assets.yml",
            "--",
            "--start-date",
            "20000104",
            "--end-date",
            "20251231",
        ]
    )
    assert hk_daily_assets.command == "universe"
    assert hk_daily_assets.uni_command == "hk-daily-assets"
    assert hk_daily_assets.config == "configs/presets/universe/hk_all_assets.yml"
    assert hk_daily_assets.args == ["--", "--start-date", "20000104", "--end-date", "20251231"]
    assert callable(hk_daily_assets.func)


def test_cli_main_run_calls_pipeline(monkeypatch):
    calls: list[tuple[str | None, str | None]] = []

    def fake_run(config, *, fail_on_quality=None):
        calls.append((config, fail_on_quality))

    monkeypatch.setattr(pipeline_module, "run", fake_run)

    assert cli.main(["run", "--config", "hk"]) == 0
    assert cli.main(["run", "--config", "hk", "--fail-on-quality", "error"]) == 0
    assert calls == [("hk", None), ("hk", "error")]


def test_cli_main_universe_wrappers_pass_through_args(monkeypatch):
    hk_connect_calls: list[list[str]] = []
    hk_daily_calls: list[list[str]] = []

    monkeypatch.setattr(hk_connect_tool, "main", lambda argv: hk_connect_calls.append(argv))
    monkeypatch.setattr(hk_daily_assets_tool, "main", lambda argv: hk_daily_calls.append(argv))

    assert (
        cli.main(
            [
                "universe",
                "hk-connect",
                "--config",
                "configs/presets/universe/hk_connect.yml",
                "--",
                "--mode",
                "daily",
                "--start-date",
                "20250101",
            ]
        )
        == 0
    )

    assert (
        cli.main(
            [
                "universe",
                "hk-daily-assets",
                "--config",
                "configs/presets/universe/hk_all_assets.yml",
                "--",
                "--start-date",
                "20000104",
                "--end-date",
                "20251231",
            ]
        )
        == 0
    )

    assert hk_connect_calls == [
        [
            "--config",
            "configs/presets/universe/hk_connect.yml",
            "--mode",
            "daily",
            "--start-date",
            "20250101",
        ]
    ]
    assert hk_daily_calls == [
        [
            "--config",
            "configs/presets/universe/hk_all_assets.yml",
            "--start-date",
            "20000104",
            "--end-date",
            "20251231",
        ]
    ]


def test_cli_main_init_config_writes_default_configs_dir(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    assert cli.main(["init-config", "--market", "hk"]) == 0

    out_path = tmp_path / "configs" / "hk.yml"
    assert out_path.exists()

    source_path = resolve_repo_preset_path("hk.yml")
    assert out_path.read_text(encoding="utf-8") == source_path.read_text(encoding="utf-8")
    assert capsys.readouterr().out.strip() == f"Wrote {out_path}"


def test_cli_main_init_config_directory_output_and_overwrite_guard(tmp_path):
    out_dir = tmp_path / "exports"

    assert cli.main(["init-config", "--market", "hk", "--out", str(out_dir)]) == 0
    out_path = out_dir / "hk.yml"
    assert out_path.exists()

    with pytest.raises(SystemExit, match="Refusing to overwrite existing file"):
        cli.main(["init-config", "--market", "hk", "--out", str(out_dir)])

    assert cli.main(["init-config", "--market", "hk", "--out", str(out_dir), "--force"]) == 0
