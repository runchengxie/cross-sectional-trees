import argparse
import ast
import fnmatch
import re
import subprocess
from pathlib import Path

MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
INLINE_CODE_PATTERN = re.compile(r"`([^`\n]+)`")
INLINE_REPO_REF_DIR_PREFIXES = (
    "docs/",
    "scripts/",
    "tests/",
    ".github/workflows/",
)
EXPECTED_CAPABILITY_TOKENS = [
    "`cstree run`",
    "`cstree summarize`",
    "`cstree grid`",
    "`cstree tune`",
    "`cstree sweep-linear`",
    "`cstree holdings`",
    "`cstree snapshot`",
    "`cstree alloc`",
    "`cstree alloc-hk`",
    "`cstree export-targets`",
    "`cstree init-config`",
    "`cstree backup-data`",
    "`cstree data ...`",
    "`cstree universe ...`",
]
EXPECTED_TEST_WORKFLOW_JOBS = {
    "fast",
    "slow",
    "integration",
    "typecheck",
    "rqdata-extra-smoke",
    "duckdb-extra-smoke",
    "liveops-hk-extra-smoke",
    "stats-extra-smoke",
}
EXPECTED_TEST_WORKFLOW_SCRIPT_MODES = {"fast", "slow", "integration", "typecheck"}
EXPECTED_DEV_TEST_TOKENS = [
    "scripts/dev/run_tests.sh all",
    "scripts/dev/run_tests.sh fast",
    "scripts/dev/run_tests.sh unit",
    "scripts/dev/run_tests.sh slow",
    "scripts/dev/run_tests.sh integration",
    "scripts/dev/run_tests.sh coverage",
    "scripts/dev/run_tests.sh typecheck",
    "CSTREE_RUN_PROVIDER_INTEGRATION=1",
    "不完全等同于在 CI 环境下的完整复现",
]
EXPECTED_DEV_TEST_MATRIX_TOKENS = [
    "### 测试矩阵维度剖析",
    "不代表完整 CI",
    "最小 DuckDB query 执行",
    "xlsx 文件的基本写入能力",
]
EXPECTED_DEV_CHANGE_MAP_TOKENS = [
    "## 修改模块与对应测试指南",
    "`tests/test_data_warehouse.py`",
    "`tests/test_run_release_scripts.py`",
    "`tests/test_hk_intraday_download.py`",
]
EXPECTED_README_ENTRYPOINT_NAV_TOKENS = [
    "## 入口分层",
    "docs/capabilities.md",
    "docs/cli.md",
]
EXPECTED_README_PUBLIC_CLI_TOKENS = [
    "`cstree run`",
    "`cstree summarize`",
    "`cstree grid`",
    "`cstree tune`",
    "`cstree sweep-linear`",
    "`cstree holdings`",
    "`cstree snapshot`",
    "`cstree alloc`",
    "`cstree alloc-hk`",
    "`cstree export-targets`",
    "`cstree init-config`",
    "`cstree backup-data`",
    "cstree data",
    "cstree universe",
]
EXPECTED_CAPABILITIES_ENTRYPOINT_LAYER_TOKENS = [
    "## 入口分层与稳定性",
    "## 命名空间策略",
    "公开主线 CLI",
    "公开但非 CLI 模块工具",
    "`python -m cstree.release_tools.package_runs`",
    "`python -m cstree.research.hk_financial_details`",
    "`python -m cstree.research.hk_intraday_download`",
    "`CSTREE_*`",
    "`src/cstree/`",
    "`scripts/dev/run_tests.sh`",
    "不是 `cstree` CLI 子命令",
]
EXPECTED_ARTIFACT_ROOT_TOKENS = [
    "  metadata/",
    "  standardized/",
    "  reports/",
]
EXPECTED_RQDATA_OUTPUT_DATASETS = {
    "daily",
    "intraday",
    "pit_financials",
    "financial_details",
    "ex_factors",
    "dividends",
    "shares",
    "valuation",
    "exchange_rate",
    "announcement",
    "southbound",
    "instrument_industry",
    "industry_changes",
}
EXPECTED_LOCAL_ASSET_LAZY_INIT_TOKENS = [
    "`fundamentals.source=provider`",
    "`fundamentals.provider_overlay`",
    "lazy init `rqdatac`",
]
EXPECTED_WORKFLOW_SMOKE_SNIPPETS = [
    'cstree data query --sql "select 1 as value"',
    "alloc_hk_smoke.xlsx",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _tracked_repo_paths(repo_root: Path) -> set[str]:
    if not (repo_root / ".git").exists():
        return {
            path.relative_to(repo_root).as_posix()
            for path in repo_root.rglob("*")
            if path.is_file()
        }

    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z"],
        check=True,
        capture_output=True,
        text=False,
    )
    return {
        path
        for path in result.stdout.decode("utf-8").split("\0")
        if path
    }


def _doc_targets(repo_root: Path) -> list[Path]:
    return [
        repo_root / "README.md",
        repo_root / "AGENTS.md",
        repo_root / "scripts" / "README.md",
        *sorted((repo_root / "docs").rglob("*.md")),
    ]


def _split_fragment(target: str) -> str:
    return target.split("#", 1)[0]


def _is_external_link(target: str) -> bool:
    value = target.strip()
    return (
        not value
        or value.startswith("#")
        or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", value) is not None
    )


def _is_tracked_repo_target(repo_root: Path, resolved: Path, tracked_paths: set[str]) -> bool:
    try:
        relative_path = resolved.relative_to(repo_root).as_posix()
    except ValueError:
        return False

    if resolved.is_dir():
        prefix = f"{relative_path.rstrip('/')}/"
        return any(path == relative_path or path.startswith(prefix) for path in tracked_paths)

    return relative_path in tracked_paths


def _looks_like_inline_repo_ref(value: str) -> bool:
    if any(char.isspace() for char in value):
        return False
    normalized = _split_fragment(value.strip()).rstrip("/")
    if normalized in {"README.md", "AGENTS.md", "artifacts/README.md"}:
        return True
    return normalized.startswith(INLINE_REPO_REF_DIR_PREFIXES)


def _has_glob_magic(value: str) -> bool:
    return any(char in value for char in "*?[")


def _is_tracked_repo_glob(pattern: str, tracked_paths: set[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for path in tracked_paths)


def _command_tree(parser: argparse.ArgumentParser) -> dict[str, dict]:
    tree: dict[str, dict] = {}
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, subparser in action.choices.items():
                tree[name] = _command_tree(subparser)
    return tree


def _leaf_commands(tree: dict[str, dict], prefix: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    leaves: list[tuple[str, ...]] = []
    for name, subtree in sorted(tree.items()):
        path = prefix + (name,)
        if subtree:
            leaves.extend(_leaf_commands(subtree, path))
        else:
            leaves.append(path)
    return leaves


def _extract_outputs_dataset_bullets(text: str) -> set[str]:
    marker = "当前 `dataset` 包括："
    lines = text.splitlines()
    collecting = False
    datasets: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not collecting:
            if stripped == marker:
                collecting = True
            continue

        if not stripped:
            if datasets:
                break
            continue

        if not stripped.startswith("* "):
            if datasets:
                break
            continue

        match = re.match(r"\* `([^`]+)`", stripped)
        if match:
            datasets.append(match.group(1))

    if not datasets:
        raise AssertionError("Could not locate the dataset bullet list in docs/outputs.md")
    return set(datasets)


def _extract_workflow_job_names(text: str) -> set[str]:
    jobs_text = text.split("\njobs:\n", 1)[1]
    return set(re.findall(r"^  ([a-zA-Z0-9_-]+):$", jobs_text, flags=re.MULTILINE))


def _extract_run_tests_modes(text: str) -> set[str]:
    return set(re.findall(r"\./scripts/dev/run_tests\.sh ([a-zA-Z0-9_-]+)", text))


def test_docs_contract_module_imports_without_loading_cli_or_mdp():
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    module_imports = [
        node
        for node in tree.body
        if isinstance(node, ast.Import | ast.ImportFrom)
    ]

    assert all(
        not (
            isinstance(node, ast.ImportFrom)
            and node.module == "cstree"
            and any(alias.name == "cli" for alias in node.names)
        )
        for node in module_imports
    )
    assert all(
        not (
            isinstance(node, ast.Import)
            and any(alias.name == "cstree.cli" for alias in node.names)
        )
        for node in module_imports
    )


def test_markdown_relative_links_exist():
    repo_root = _repo_root()
    tracked_paths = _tracked_repo_paths(repo_root)
    missing: dict[str, list[str]] = {}

    for path in _doc_targets(repo_root):
        refs: list[str] = []
        for raw_target in MARKDOWN_LINK_PATTERN.findall(path.read_text(encoding="utf-8")):
            target = raw_target.strip().strip("<>")
            if _is_external_link(target):
                continue
            target_path = _split_fragment(target).strip()
            if not target_path:
                continue
            resolved = (path.parent / target_path).resolve()
            if not _is_tracked_repo_target(repo_root, resolved, tracked_paths):
                refs.append(target)
        if refs:
            missing[path.relative_to(repo_root).as_posix()] = sorted(set(refs))

    assert missing == {}


def test_inline_repo_path_references_exist():
    repo_root = _repo_root()
    tracked_paths = _tracked_repo_paths(repo_root)
    missing: dict[str, list[str]] = {}

    for path in _doc_targets(repo_root):
        refs: list[str] = []
        for raw_value in INLINE_CODE_PATTERN.findall(path.read_text(encoding="utf-8")):
            value = raw_value.strip()
            if not _looks_like_inline_repo_ref(value):
                continue
            target_path = _split_fragment(value).rstrip("/")
            if not target_path:
                continue

            if _has_glob_magic(target_path):
                if not _is_tracked_repo_glob(target_path, tracked_paths):
                    refs.append(value)
                continue

            resolved = (repo_root / target_path).resolve()
            if not _is_tracked_repo_target(repo_root, resolved, tracked_paths):
                refs.append(value)
        if refs:
            missing[path.relative_to(repo_root).as_posix()] = sorted(set(refs))

    assert missing == {}


def test_research_notes_are_indexed_in_research_readme():
    repo_root = _repo_root()
    readme = (repo_root / "docs" / "research" / "README.md").read_text(encoding="utf-8")
    listed = set(re.findall(r"`notes/([^`]+\.md)`", readme))
    actual = {
        path.name
        for path in sorted((repo_root / "docs" / "research" / "notes").glob("*.md"))
    }

    assert listed == actual


def test_research_notes_have_minimal_metadata():
    repo_root = _repo_root()
    missing: dict[str, list[str]] = {}

    for path in sorted((repo_root / "docs" / "research" / "notes").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        issues: list[str] = []

        if "页面性质：" not in text:
            issues.append("页面性质")
        if "最后核对时间：" not in text:
            issues.append("最后核对时间")

        kind_match = re.search(r"页面性质：\s*`([^`]+)`", text)
        if kind_match is None or kind_match.group(1) != "current-state":
            if "状态：" not in text and "> 状态提示：" not in text:
                issues.append("状态")

        if issues:
            missing[path.relative_to(repo_root).as_posix()] = issues

    assert missing == {}


def test_docs_cli_covers_public_cli_leaf_commands():
    from cstree import cli

    docs_cli = (_repo_root() / "docs" / "cli.md").read_text(encoding="utf-8")
    expected_headings = {
        f"### cstree {' '.join(command_path)}"
        for command_path in _leaf_commands(_command_tree(cli.build_parser()))
    }
    missing = sorted(heading for heading in expected_headings if heading not in docs_cli)
    assert missing == []


def test_capabilities_doc_covers_public_command_families():
    capabilities = (_repo_root() / "docs" / "capabilities.md").read_text(encoding="utf-8")
    missing = sorted(token for token in EXPECTED_CAPABILITY_TOKENS if token not in capabilities)
    assert missing == []


def test_readme_and_capabilities_cover_entrypoint_layers():
    repo_root = _repo_root()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    capabilities = (repo_root / "docs" / "capabilities.md").read_text(encoding="utf-8")

    missing_readme = sorted(token for token in EXPECTED_README_ENTRYPOINT_NAV_TOKENS if token not in readme)
    missing_readme_commands = sorted(token for token in EXPECTED_README_PUBLIC_CLI_TOKENS if token not in readme)
    missing_capabilities = sorted(
        token for token in EXPECTED_CAPABILITIES_ENTRYPOINT_LAYER_TOKENS if token not in capabilities
    )

    assert missing_readme == []
    assert missing_readme_commands == []
    assert missing_capabilities == []


def test_capabilities_doc_mentions_metadata_and_standardized_roots():
    capabilities = (_repo_root() / "docs" / "capabilities.md").read_text(encoding="utf-8")
    outputs = (_repo_root() / "docs" / "outputs.md").read_text(encoding="utf-8")

    missing_capabilities = sorted(token for token in EXPECTED_ARTIFACT_ROOT_TOKENS if token not in capabilities)
    missing_outputs = sorted(token for token in EXPECTED_ARTIFACT_ROOT_TOKENS if token not in outputs)

    assert missing_capabilities == []
    assert missing_outputs == []


def test_outputs_doc_lists_public_rqdata_output_datasets():
    outputs_text = (_repo_root() / "docs" / "outputs.md").read_text(encoding="utf-8")
    documented = _extract_outputs_dataset_bullets(outputs_text)
    assert documented == EXPECTED_RQDATA_OUTPUT_DATASETS


def test_get_started_doc_describes_default_alias_correctly():
    get_started = (_repo_root() / "docs" / "get-started.md").read_text(encoding="utf-8")

    assert "不等于 `configs/presets/default.yml`" not in get_started
    assert "会解析到仓库 `configs/` 下的 `configs/presets/default.yml`" in get_started


def test_local_asset_docs_describe_lazy_rqdatac_init_boundary():
    data_sources = (_repo_root() / "docs" / "concepts" / "data-sources.md").read_text(
        encoding="utf-8"
    )
    hk_data_assets = (_repo_root() / "docs" / "playbooks" / "hk-data-assets.md").read_text(
        encoding="utf-8"
    )

    missing_data_sources = sorted(
        token for token in EXPECTED_LOCAL_ASSET_LAZY_INIT_TOKENS if token not in data_sources
    )
    missing_hk_data_assets = sorted(
        token for token in EXPECTED_LOCAL_ASSET_LAZY_INIT_TOKENS if token not in hk_data_assets
    )

    assert missing_data_sources == []
    assert missing_hk_data_assets == []


def test_tests_workflow_uses_expected_jobs_and_run_tests_modes():
    workflow_text = (_repo_root() / ".github" / "workflows" / "tests.yml").read_text(
        encoding="utf-8"
    )
    assert _extract_workflow_job_names(workflow_text) == EXPECTED_TEST_WORKFLOW_JOBS
    assert _extract_run_tests_modes(workflow_text) == EXPECTED_TEST_WORKFLOW_SCRIPT_MODES
    missing_smokes = sorted(token for token in EXPECTED_WORKFLOW_SMOKE_SNIPPETS if token not in workflow_text)
    assert missing_smokes == []


def test_dev_doc_covers_test_entrypoints_and_ci_contract():
    dev_text = (_repo_root() / "docs" / "dev.md").read_text(encoding="utf-8")
    missing_tokens = sorted(token for token in EXPECTED_DEV_TEST_TOKENS if token not in dev_text)
    missing_jobs = sorted(
        job_name for job_name in EXPECTED_TEST_WORKFLOW_JOBS if f"`{job_name}`" not in dev_text
    )

    assert missing_tokens == []
    assert missing_jobs == []


def test_dev_doc_covers_test_matrix_and_change_based_mapping():
    dev_text = (_repo_root() / "docs" / "dev.md").read_text(encoding="utf-8")

    missing_matrix_tokens = sorted(token for token in EXPECTED_DEV_TEST_MATRIX_TOKENS if token not in dev_text)
    missing_mapping_tokens = sorted(token for token in EXPECTED_DEV_CHANGE_MAP_TOKENS if token not in dev_text)

    assert missing_matrix_tokens == []
    assert missing_mapping_tokens == []
