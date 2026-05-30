import sys
from types import SimpleNamespace

import pytest

from cstree import cli, pipeline as pipeline_module
from cstree.cli import common as cli_common
from cstree.config_utils import resolve_pipeline_config, resolve_repo_preset_path


def test_cli_parses_run_command():
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "run",
            "--config",
            "default",
            "--fail-on-quality",
            "warning",
            "--artifacts-root",
            "/tmp/cstree-artifacts",
        ]
    )
    assert args.command == "run"
    assert args.config == "default"
    assert args.fail_on_quality == "warning"
    assert args.artifacts_root == "/tmp/cstree-artifacts"
    assert callable(args.func)


def test_default_builtin_config_is_hk_first():
    resolved = resolve_pipeline_config(None)
    assert resolved.data["market"] == "hk"
    assert resolved.data["data"]["provider"] == "rqdata"
    assert resolved.data["data"]["source_mode"] == "platform_assets"
    assert resolved.data["fundamentals"]["source"] == "file"
def test_cli_rejects_removed_data_and_universe_commands():
    parser = cli.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["data", "query", "--sql", "select 1"])

    with pytest.raises(SystemExit):
        parser.parse_args(["universe", "hk-connect", "--config", "configs/presets/universe/hk_connect.yml"])


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
    monkeypatch.delenv("RQDATA_USERNAME", raising=False)
    monkeypatch.delenv("RQDATA_USER", raising=False)
    monkeypatch.delenv("RQDATA_PASSWORD", raising=False)
    monkeypatch.setattr(
        cli_common,
        "_patch_rqdatac_adjust_price_readonly",
        lambda logger: patch_calls.append(logger.name),
    )

    result = cli_common.init_rqdatac(SimpleNamespace(config=None, username=None, password=None))

    assert result is fake_rqdatac
    assert init_calls == [{}]
    assert patch_calls == ["market_data_platform.rqdata_runtime"]
def test_cli_parses_init_config():
    parser = cli.build_parser()

    init_cfg = parser.parse_args(
        ["init-config", "--market", "hk", "--out", "configs/presets/", "--force"]
    )
    assert init_cfg.command == "init-config"
    assert init_cfg.market == "hk"
    assert init_cfg.out == "configs/presets/"
    assert init_cfg.force is True
    assert callable(init_cfg.func)


def test_cli_main_run_calls_pipeline(monkeypatch):
    calls: list[tuple[str | None, str | None]] = []

    def fake_run(config, *, fail_on_quality=None):
        calls.append((config, fail_on_quality))

    monkeypatch.setattr(pipeline_module, "run", fake_run)

    assert cli.main(["run", "--config", "hk"]) == 0
    assert cli.main(["run", "--config", "hk", "--fail-on-quality", "error"]) == 0
    assert calls == [("hk", None), ("hk", "error")]


def test_cli_main_run_forwards_artifacts_root(monkeypatch):
    calls: list[tuple[str | None, str | None, str | None]] = []

    def fake_run(config, *, fail_on_quality=None, artifacts_root=None):
        calls.append((config, fail_on_quality, artifacts_root))

    monkeypatch.setattr(pipeline_module, "run", fake_run)

    assert cli.main(["run", "--config", "hk", "--artifacts-root", "/tmp/cstree-artifacts"]) == 0
    assert calls == [("hk", None, "/tmp/cstree-artifacts")]
def test_cli_main_init_config_writes_default_configs_dir(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    assert cli.main(["init-config", "--market", "hk"]) == 0

    out_path = tmp_path / "configs" / "hk.yml"
    assert out_path.exists()

    source_path = resolve_repo_preset_path("hk.yml")
    assert out_path.read_text(encoding="utf-8") == source_path.read_text(encoding="utf-8")
    assert capsys.readouterr().out.strip() == f"Wrote {out_path}"


def test_cli_main_init_config_supports_a_share_template(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    assert cli.main(["init-config", "--market", "a_share"]) == 0

    out_path = tmp_path / "configs" / "a_share.yml"
    assert out_path.exists()
    source_path = resolve_repo_preset_path("a_share.yml")
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
