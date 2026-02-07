from types import SimpleNamespace

import pytest

from csxgb.project_tools import snapshot


def test_snapshot_runs_pipeline_then_holdings(monkeypatch):
    calls: dict[str, list] = {"pipeline": [], "holdings": []}

    monkeypatch.setattr(
        snapshot,
        "resolve_pipeline_config",
        lambda _cfg: SimpleNamespace(data={"live": {"enabled": True}}),
    )
    monkeypatch.setattr(snapshot.pipeline, "run", lambda cfg: calls["pipeline"].append(cfg))
    monkeypatch.setattr(snapshot.holdings, "main", lambda argv: calls["holdings"].append(argv))

    snapshot.main(["--config", "hk", "--as-of", "20260131", "--format", "json"])

    assert calls["pipeline"] == ["hk"]
    assert calls["holdings"] == [
        ["--source", "live", "--as-of", "20260131", "--config", "hk", "--format", "json"]
    ]


def test_snapshot_skip_run_does_not_call_pipeline(monkeypatch):
    calls: dict[str, list] = {"holdings": []}

    monkeypatch.setattr(
        snapshot,
        "resolve_pipeline_config",
        lambda _cfg: (_ for _ in ()).throw(AssertionError("resolve_pipeline_config should not run")),
    )
    monkeypatch.setattr(
        snapshot.pipeline,
        "run",
        lambda _cfg: (_ for _ in ()).throw(AssertionError("pipeline.run should not run")),
    )
    monkeypatch.setattr(snapshot.holdings, "main", lambda argv: calls["holdings"].append(argv))

    snapshot.main(["--config", "hk", "--skip-run"])

    assert calls["holdings"] == [["--source", "live", "--as-of", "t-1", "--config", "hk", "--format", "text"]]


def test_snapshot_run_dir_mode_skips_pipeline(monkeypatch):
    calls: dict[str, list] = {"holdings": []}

    monkeypatch.setattr(
        snapshot,
        "resolve_pipeline_config",
        lambda _cfg: (_ for _ in ()).throw(AssertionError("resolve_pipeline_config should not run")),
    )
    monkeypatch.setattr(
        snapshot.pipeline,
        "run",
        lambda _cfg: (_ for _ in ()).throw(AssertionError("pipeline.run should not run")),
    )
    monkeypatch.setattr(snapshot.holdings, "main", lambda argv: calls["holdings"].append(argv))

    snapshot.main(["--run-dir", "out/runs/demo", "--format", "csv"])

    assert calls["holdings"] == [
        ["--source", "live", "--as-of", "t-1", "--run-dir", "out/runs/demo", "--format", "csv"]
    ]


def test_snapshot_requires_live_enabled_when_running_pipeline(monkeypatch):
    monkeypatch.setattr(
        snapshot,
        "resolve_pipeline_config",
        lambda _cfg: SimpleNamespace(data={"live": {"enabled": False}}),
    )

    with pytest.raises(SystemExit, match="snapshot requires live.enabled=true in the config."):
        snapshot.main(["--config", "hk"])


def test_snapshot_requires_config_or_run_dir():
    with pytest.raises(SystemExit, match="snapshot requires --config or --run-dir."):
        snapshot.main([])
