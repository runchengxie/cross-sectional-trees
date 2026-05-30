from pathlib import Path

import pytest
from market_data_platform.artifacts import (
    resolve_artifacts_root,
    resolve_configured_artifacts_root,
    resolve_metadata_db_path,
    resolve_warehouse_db_path,
)


def test_resolve_artifacts_root_uses_cstree_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CSTREE_ARTIFACTS_ROOT", "legacy-artifacts")

    assert resolve_artifacts_root() == (tmp_path / "legacy-artifacts").resolve()


def test_resolve_configured_artifacts_root_prefers_cstree_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CSTREE_ARTIFACTS_ROOT", "preferred-artifacts")

    resolved = resolve_configured_artifacts_root(
        {"paths": {"artifacts_root": "config-artifacts"}}
    )

    assert resolved == (tmp_path / "preferred-artifacts").resolve()


@pytest.mark.parametrize(
    ("resolver", "env_name", "expected"),
    [
        (
            resolve_artifacts_root,
            "CSTREE_ARTIFACTS_ROOT",
            Path("preferred-artifacts"),
        ),
        (
            resolve_metadata_db_path,
            "CSTREE_METADATA_DB_PATH",
            Path("preferred") / "catalog.sqlite",
        ),
        (
            resolve_warehouse_db_path,
            "CSTREE_WAREHOUSE_DB_PATH",
            Path("preferred") / "warehouse.duckdb",
        ),
    ],
)
def test_cstree_env_resolvers_use_cstree_env(
    resolver,
    env_name,
    expected,
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(env_name, expected.as_posix())

    assert resolver() == (tmp_path / expected).resolve()
