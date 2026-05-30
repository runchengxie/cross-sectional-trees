import importlib.util
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_boundary_module():
    path = _repo_root() / "scripts" / "dev" / "data_ops_boundary.py"
    spec = importlib.util.spec_from_file_location("data_ops_boundary", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_current_data_ops_boundary_inventory_has_no_issues():
    module = _load_boundary_module()

    report = module.build_report(_repo_root())

    assert report["issues"] == []
    assert "src/cstree/cli/data.py" in report["removed_wrappers"]
    assert "src/cstree/research/hk_selected_provider_valuation_merge.py" in report["research_owned_paths"]


def test_boundary_check_flags_unclassified_data_ops_source(tmp_path):
    module = _load_boundary_module()
    source = tmp_path / "src" / "cstree"
    source.mkdir(parents=True)
    (source / "rqdata_asset_refresh.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    docs = tmp_path / "docs" / "internal"
    docs.mkdir(parents=True)
    inventory = docs / "data-ops-boundary-inventory.md"
    inventory.write_text(
        "must not exist\n" + "\n".join(
            f"`{entry}`" for entry in module.REMOVED_WRAPPER_PATHS
        ) + "\n" + "\n".join(
            f"`{entry}`" for entry in module.RESEARCH_OWNED_PATHS
        ),
        encoding="utf-8",
    )

    issues = module.source_boundary_issues(tmp_path)

    assert any("rqdata_asset_refresh.py" in issue for issue in issues)


def test_boundary_check_requires_removed_wrappers_to_stay_deleted(tmp_path):
    module = _load_boundary_module()
    wrapper = tmp_path / "src" / "cstree" / "data_providers.py"
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    wrapper.write_text("# resurrected wrapper\n", encoding="utf-8")

    issues = module.source_boundary_issues(tmp_path)

    assert any(
        "data_providers.py" in issue and "must not exist" in issue for issue in issues
    )


def test_boundary_check_flags_stale_research_owned_docs(tmp_path):
    module = _load_boundary_module()
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "dev.md").write_text(
        "维护 HK / RQData 本地资产：HK 资产健康检查脚本、HK 资产维护 Driver\n",
        encoding="utf-8",
    )

    issues = module.documentation_issues(tmp_path)

    assert any("HK 资产健康检查脚本" in issue for issue in issues)
