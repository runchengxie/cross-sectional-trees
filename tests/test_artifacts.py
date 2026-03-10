from csml.artifacts import LEGACY_ARTIFACT_PATHS, resolve_repo_path


def test_resolve_repo_path_handles_relative_and_absolute_inputs(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    relative = resolve_repo_path("artifacts/runs")
    assert relative == (repo_root / "artifacts" / "runs").resolve()

    absolute_input = repo_root / "artifacts" / "cache"
    absolute = resolve_repo_path(absolute_input)
    assert absolute == absolute_input.resolve()


def test_legacy_artifact_paths_cover_expected_legacy_roots():
    legacy_roots = {legacy.as_posix() for legacy, _ in LEGACY_ARTIFACT_PATHS}
    assert legacy_roots == {
        "cache",
        "out/fundamentals",
        "data_assets/rqdata",
        "out/universe",
        "out/runs",
        "out/live_runs",
        "out/sweeps",
        "data_mirror",
    }
