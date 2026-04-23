## 1. Inventory and Baseline

- [x] 1.1 Create `docs/internal/maintenance-debt-inventory.md` with candidate categories, target files, repo-local usages, doc references, risk level, proposed action, and validation command columns.
- [x] 1.2 Record the current baseline metrics for large files, functions over 250 lines, long-line counts, and `C901` ignore count in the inventory.
- [x] 1.3 Classify first-pass removal candidates, including `pipeline/data.py`, `compat.py`, legacy `universe`, legacy symbol aliases, and `scripts/internal/run_hk_asset_workflow.py`.
- [x] 1.4 Mark public, release, research, and maintainer surfaces from `docs/capabilities.md`, `docs/cli.md`, playbooks, and `scripts/README.md` so they are not treated as dead code.
- [x] 1.5 Add or update a narrow docs/test contract if needed so the inventory remains linked from maintainer documentation.

## 2. Compatibility Boundary Cleanup

- [x] 2.1 Replace repo-local imports from `src/cstree/pipeline/data.py` with canonical imports from `feature_dataset.py` and `panel_loader.py`.
- [x] 2.2 Decide whether `src/cstree/pipeline/data.py` remains as a documented temporary shim or is removed with a migration note.
- [x] 2.3 Audit `ensure_numpy_nan_alias` usage and determine whether it should remain in `compat.py`, move closer to `pandas_ta` import sites, or be removed after dependency validation.
- [x] 2.4 Add tests or strengthen existing tests for canonical `research_universe`, legacy `universe`, and mixed-key conflict handling.
- [x] 2.5 Add tests or strengthen existing tests for canonical `symbol` output and accepted legacy `ts_code` / `stock_ticker` / `order_book_id` inputs.
- [x] 2.6 Update `docs/config.md`, `docs/providers.md`, and `docs/outputs.md` if compatibility wording or migration guidance changes.

## 3. RQData Command Registration

- [x] 3.1 Extend or refactor `RQDataAssetCommandSpec` so command defaults, argument builder, runner, client requirement, and help text are discoverable from one declaration path.
- [x] 3.2 Reduce thin `_add_*_args` wrappers in `command_registry.py` where the wrapper only forwards constants to `args.py` or `args_mirror.py`.
- [x] 3.3 Keep shared argument builder code only where it removes real duplication across multiple commands.
- [x] 3.4 Narrow `public_api.py` and package `__init__.py` exports so tests and supported programmatic use do not require a broad private-name facade.
- [x] 3.5 Run `tests/test_cli_rqdata.py` and the relevant `tests/rqdata_assets/` files after each command registration phase.

## 4. Liveops CLI Registration

- [x] 4.1 Split `register_liveops_commands` into command-specific registration helpers or declarative specs for `holdings`, `snapshot`, `alloc`, and `alloc-hk`.
- [x] 4.2 Keep handler forwarding for each liveops command close to its parser definition or covered by a shared forwarding helper.
- [x] 4.3 Add or update parser tests for representative `alloc-hk` options, boolean switches, repeated scenario arguments, and output formats.
- [x] 4.4 Run `tests/test_cli_liveops.py`, `tests/test_alloc.py`, and `tests/test_alloc_hk.py`.

## 5. Large Module Splits

- [x] 5.1 Split one responsibility boundary from `src/cstree/data_tools/rqdata_assets/asset_health.py`, starting with report rendering or scan aggregation, and keep `inspect_hk_asset_health` as the stable entry point.
- [x] 5.2 Split one responsibility boundary from `src/cstree/data_tools/rqdata_assets/coverage.py`, starting with text rendering or trainable grid construction.
- [x] 5.3 Split one responsibility boundary from `src/cstree/data_tools/rqdata_assets/build.py`, starting with PIT universe filtering or output path resolution.
- [x] 5.4 Split one responsibility boundary from `src/cstree/pipeline/eval.py`, starting with period evaluation helpers or walk-forward evaluation helpers.
- [x] 5.5 Split one responsibility boundary from `src/cstree/release_tools/hk_asset_workflow.py`, starting with stage planning, command construction, or report collection.
- [x] 5.6 After each split, remove any now-unneeded `C901` ignore or record why it must remain.

## 6. Maintainer Scripts

- [x] 6.1 Audit `scripts/internal/` for scripts that are documented, tested, or still needed by the maintainer workflow.
- [x] 6.2 For retained scripts, document whether each script is a driver, private helper, or compatibility wrapper in `scripts/README.md`.
- [x] 6.3 For removed or relocated scripts, update tests and docs to point at the supported `cstree` CLI or `python -m cstree...` entry.
- [x] 6.4 Run `tests/test_package_repo_script.py`, `tests/test_refresh_hk_current_script.py`, and `tests/test_run_release_scripts.py` when affected.

## 7. Static Quality Ratchet

- [x] 7.1 Add a lightweight local metric command or documented snippet for large files, large functions, long lines, and `C901` ignores.
- [x] 7.2 Tighten Ruff or repository test scripts only for rules that can be enforced without broad unrelated churn.
- [x] 7.3 Require touched Python files in this change to avoid new long lines, unused imports, or new complexity exemptions.
- [x] 7.4 Update `docs/dev.md` if lint, format, or complexity expectations change.

## 8. Final Validation

- [x] 8.1 Run `scripts/dev/run_tests.sh fast` after the first complete behavior-preserving phase.
- [x] 8.2 Run targeted RQData, pipeline, liveops, and release tests matching the files changed in each later phase.
- [x] 8.3 Run `tests/test_docs_contracts.py` and `tests/test_repo_path_references.py` after documentation updates.
- [x] 8.4 Summarize before/after metrics and remaining open compatibility decisions in the inventory before archiving the change.
