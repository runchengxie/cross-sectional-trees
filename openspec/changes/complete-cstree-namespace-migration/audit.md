# Namespace Audit Baseline

Generated for change `complete-cstree-namespace-migration` on 2026-04-23.

Scope: `README.md`, `docs/`, `scripts/`, `src/`, `tests/`, and `pyproject.toml`. The audit intentionally excludes generated artifacts and local runtime outputs.

## Summary

- Preferred public namespace: `cstree`
- Legacy compatibility namespace: `csml`
- Preferred environment variables: `CSTREE_*`
- Legacy fallback environment variables: `CSML_*`
- Implementation owner during the current compatibility window: `src/csml/`
- Public bridge during the current compatibility window: `src/cstree/`

The repository is already in the additive migration stage: public docs and generated commands prefer `cstree`, while `csml` remains intentionally available for existing automation.

## Remaining `csml` Reference Categories

### Compatibility Contract

- `pyproject.toml` keeps both console scripts:
  - `cstree = "cstree.cli:main"`
  - `csml = "csml.cli:main"`
- `docs/capabilities.md`, `docs/get-started.md`, `docs/config.md`, `docs/dev.md`, and `scripts/README.md` mention `csml` only to describe the compatibility window or legacy fallback behavior.
- `tests/test_cli_entrypoints.py` protects the registered `csml` console script and parser compatibility.
- `tests/test_cstree_namespace.py` now protects documented legacy `python -m csml.release_tools...` and `python -m csml.research...` module execution paths during the compatibility window.
- `tests/test_artifacts.py`, `tests/test_provider_integration.py`, and `scripts/dev/run_tests.sh` keep `CSML_*` fallback coverage or messaging.

### Internal Implementation Ownership

- `src/csml/` remains the implementation package until the final breaking gate approves an implementation ownership move.
- `pyproject.toml` ruff per-file ignores and `scripts/dev/run_tests.sh coverage` still target `csml` because coverage and complexity settings follow the implementation package.
- Logger names such as `csml`, `csml.cli.rqdata`, and `csml.research...` remain implementation-level observability identifiers.

### Cstree Bridge Implementation

- `src/cstree/__init__.py` installs the alias finder that maps import-only `cstree.*` surfaces to existing `csml.*` modules.
- Explicit `src/cstree/release_tools/*` and `src/cstree/research/*` wrappers delegate documented module execution paths to `csml` implementations instead of copying implementation files.
- Wrapper files necessarily import `csml.*`; these are intentional bridge references.

### Test Monkeypatch Or Logger Target

- Tests that patch implementation internals, assert logger names, or load implementation modules directly may continue to reference `csml` while implementation ownership remains under `src/csml/`.
- Release workflow tests still load `csml.release_tools.*` directly when they are exercising implementation internals, but generated commands are asserted as `python -m cstree...`.

### Documentation Of Legacy Behavior

- Documentation mentions `csml`, `CSML_*`, and `python -m csml...` only when describing compatibility, migration strategy, or legacy fallback precedence.
- No public docs should introduce new primary examples using `csml`.

### Accidental Public Usage

Converted in this implementation slice:

- Public CLI parser/dispatch tests now import through `cstree` where they model user-facing command behavior.
- Public liveops/data/universe/research behavior tests now import through `cstree` where they are not specifically testing compatibility or implementation internals.

Remaining direct `csml` test imports are treated as implementation, monkeypatch/logger, or explicit compatibility coverage and should be reviewed again before the final breaking gate.

## Public Module Inventory

Documented public release module tools:

- `python -m cstree.release_tools.package_assets`
- `python -m cstree.release_tools.release_assets`
- `python -m cstree.release_tools.package_runs`
- `python -m cstree.release_tools.release_runs`

Documented public research module tools:

- `python -m cstree.research.hk_asset_patch_merge`
- `python -m cstree.research.hk_benchmark_attribution`
- `python -m cstree.research.hk_connect_cap_weight_benchmark`
- `python -m cstree.research.hk_financial_details`
- `python -m cstree.research.hk_intraday_download`
- `python -m cstree.research.hk_intraday_slippage_report`
- `python -m cstree.research.hk_monthly_run_compare`
- `python -m cstree.research.hk_selected_provider_valuation_audit`

Maintenance wrapper:

- `python -m cstree.release_tools.hk_asset_workflow` exists for maintainer orchestration, but the user-facing documented driver remains `scripts/internal/run_hk_asset_workflow.py`.

## Follow-Up Before Final Removal

Before removing any `csml` compatibility surface, rerun an audit over repository docs, scripts, tests, CI, packaging metadata, and release notes:

```bash
rg -n "csml|CSML_" README.md docs scripts src tests pyproject.toml .github
rg -n "cstree|CSTREE_" README.md docs scripts src tests pyproject.toml .github
```

The final breaking gate must resolve whether to delete `csml` entirely or leave a short-lived targeted error shim with migration guidance.
