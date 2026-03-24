from csml.artifacts import resolve_repo_path


def test_resolve_repo_path_handles_relative_and_absolute_inputs(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    relative = resolve_repo_path("artifacts/runs")
    assert relative == (repo_root / "artifacts" / "runs").resolve()

    absolute_input = repo_root / "artifacts" / "cache"
    absolute = resolve_repo_path(absolute_input)
    assert absolute == absolute_input.resolve()
