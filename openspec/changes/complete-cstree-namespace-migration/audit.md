# Namespace Audit Baseline And Final Migration Result

Generated for change `complete-cstree-namespace-migration` on 2026-04-23.

Scope: `README.md`, `docs/`, `scripts/`, `src/`, `tests/`, and `pyproject.toml`. The audit intentionally excludes generated artifacts and local runtime outputs.

## Final Summary

- Public namespace: `cstree`
- Public environment variables: `CSTREE_*`
- Implementation owner: `src/cstree/`
- Removed legacy namespace: `csml`
- Removed legacy environment variable fallback: `CSML_*`
- Logger namespace: `cstree.*`

The repository has completed the final breaking migration stage. Public docs, generated commands, tests, packaging metadata, coverage settings, logger names, and internal imports now target `cstree`.

## Remaining `csml` Reference Categories

Only expected historical references remain:

- `docs/internal/cstree-namespace-migration.md` keeps the migration map and release-note text for users moving from old names.
- `openspec/changes/complete-cstree-namespace-migration/` keeps the proposal, design, spec, and this audit history.
- `tests/test_cstree_namespace.py` asserts the legacy import and module execution surfaces are removed.
- `docs/capabilities.md` explicitly says the legacy surfaces are no longer public compatibility.

No source implementation, packaging metadata, public script, or public behavior test imports `csml`.

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

Maintenance module:

- `python -m cstree.release_tools.hk_asset_workflow` exists for maintainer orchestration, but the user-facing documented driver remains `scripts/internal/run_hk_asset_workflow.py`.

## Final Removal Decisions

- `csml` console script: removed from `pyproject.toml`.
- `python -m csml...`: removed by deleting the `src/csml/` package.
- `import csml`: removed by deleting the `src/csml/` package; no shim is retained.
- `CSML_*`: removed as environment variable fallbacks.
- Logger namespace: moved to `cstree.*`.
- Coverage target and ruff per-file ignores: moved to `cstree`.

Final audit commands:

```bash
rg -n "csml|CSML_" README.md docs scripts src tests pyproject.toml .github
rg -n "cstree|CSTREE_" README.md docs scripts src tests pyproject.toml .github
```
