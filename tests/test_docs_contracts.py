import argparse
import re
from pathlib import Path

from csml import cli


MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
INLINE_CODE_PATTERN = re.compile(r"`([^`\n]+)`")
INLINE_REPO_REF_DIR_PREFIXES = (
    "docs/",
    "scripts/",
    "tests/",
    ".github/workflows/",
)
EXPECTED_CAPABILITY_TOKENS = [
    "`csml run`",
    "`csml summarize`",
    "`csml grid`",
    "`csml sweep-linear`",
    "`csml holdings`",
    "`csml snapshot`",
    "`csml alloc`",
    "`csml alloc-hk`",
    "`csml init-config`",
    "`csml backup-data`",
    "`csml migrate-artifacts`",
    "`csml data ...`",
    "`csml rqdata ...`",
    "`csml universe ...`",
    "`csml tushare verify-token`",
]
EXPECTED_RQDATA_OUTPUT_DATASETS = {
    "daily",
    "pit_financials",
    "financial_details",
    "ex_factors",
    "dividends",
    "shares",
    "exchange_rate",
    "southbound",
    "instrument_industry",
    "industry_changes",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


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


def _looks_like_inline_repo_ref(value: str) -> bool:
    if any(char.isspace() for char in value):
        return False
    normalized = _split_fragment(value.strip()).rstrip("/")
    if normalized in {"README.md", "AGENTS.md", "artifacts/README.md"}:
        return True
    return normalized.startswith(INLINE_REPO_REF_DIR_PREFIXES)


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


def test_markdown_relative_links_exist():
    repo_root = _repo_root()
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
            if not resolved.exists():
                refs.append(target)
        if refs:
            missing[path.relative_to(repo_root).as_posix()] = sorted(set(refs))

    assert missing == {}


def test_inline_repo_path_references_exist():
    repo_root = _repo_root()
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
            resolved = (repo_root / target_path).resolve()
            if not resolved.exists():
                refs.append(value)
        if refs:
            missing[path.relative_to(repo_root).as_posix()] = sorted(set(refs))

    assert missing == {}


def test_docs_cli_covers_public_cli_leaf_commands():
    docs_cli = (_repo_root() / "docs" / "cli.md").read_text(encoding="utf-8")
    expected_headings = {
        f"### csml {' '.join(command_path)}"
        for command_path in _leaf_commands(_command_tree(cli.build_parser()))
    }
    missing = sorted(heading for heading in expected_headings if heading not in docs_cli)
    assert missing == []


def test_capabilities_doc_covers_public_command_families():
    capabilities = (_repo_root() / "docs" / "capabilities.md").read_text(encoding="utf-8")
    missing = sorted(token for token in EXPECTED_CAPABILITY_TOKENS if token not in capabilities)
    assert missing == []


def test_outputs_doc_lists_public_rqdata_output_datasets():
    outputs_text = (_repo_root() / "docs" / "outputs.md").read_text(encoding="utf-8")
    documented = _extract_outputs_dataset_bullets(outputs_text)
    assert documented == EXPECTED_RQDATA_OUTPUT_DATASETS
