## 1. Baseline And Guardrails

- [x] 1.1 Refresh `docs/internal/maintenance-debt-inventory.md` with the current tracked-file audit numbers and link the cleanup scope to this OpenSpec change.
- [x] 1.2 Add or update the validation matrix for this change so each touched boundary has a focused pytest or lint command.
- [x] 1.3 Run the docs/path maintenance checks after the inventory update and record any residual gap in the task notes or final apply summary.

## 2. Compatibility Boundaries

- [x] 2.1 Audit repo-local imports of `cstree.pipeline.data` and confirm internal code uses `pipeline.feature_dataset` and `pipeline.panel_loader` directly.
- [x] 2.2 Add a controlled deprecation path for `cstree.pipeline.data`, either with a targeted `DeprecationWarning` test or an explicit removal decision if immediate deletion is approved.
- [x] 2.3 Preserve and verify legacy `universe` config compatibility while keeping canonical output centered on `research_universe`.
- [x] 2.4 Preserve and verify legacy symbol alias compatibility for inputs such as `ts_code` and `stock_ticker` while keeping canonical output centered on `symbol`.
- [x] 2.5 Update internal notes so shim retention, migration, and deletion criteria are explicit.

## 3. Train/Eval Stage Refactor

- [x] 3.1 Inspect `pipeline/train_eval_stage.py` and identify the smallest safe extraction boundary from `_run_train_eval_stage_impl`.
- [x] 3.2 Reduce the wide parameter surface by moving one coherent group of stage inputs behind an existing or new request/context object.
- [x] 3.3 Extract one pure helper for model fitting, prediction assembly, cross-validation bookkeeping, or live/OOS snapshot construction.
- [x] 3.4 Run focused train/eval and modeling tests, including `tests/test_pipeline_train_eval_contracts.py` and any directly affected tests.
- [x] 3.5 Update the maintenance inventory with the new function-size or boundary status.

## 4. Pipeline Runner Refactor

- [x] 4.1 Inspect `pipeline/runner.py` and choose one behavior-preserving extraction from the top-level `run()` orchestration.
- [x] 4.2 Extract setup/config unpacking, dataset loading, benchmark/backtest preparation, or output persistence request assembly into a narrower helper.
- [x] 4.3 Keep public `cstree run` behavior and monkeypatchable test hooks intact.
- [x] 4.4 Run focused pipeline runtime/filter tests such as `tests/test_pipeline_runtime.py` and `tests/test_pipeline_filters_core.py`.
- [x] 4.5 Update the maintenance inventory with the new runner boundary status.

## 5. RQData Asset Health Refactor

- [x] 5.1 Inspect `data_tools/rqdata_assets/asset_health.py` and identify the next scan, aggregation, severity, or report boundary to extract.
- [x] 5.2 Extract one behavior-preserving helper/module from `inspect_hk_asset_health` without changing report schema or severity semantics.
- [x] 5.3 Add or update focused tests for the extracted asset health behavior using synthetic fixtures rather than heavy real-data scans.
- [x] 5.4 Run relevant `tests/rqdata_assets/` coverage for the touched health boundary.
- [x] 5.5 Update the maintenance inventory with the new asset health boundary status.

## 6. Public Facade And RQData API Boundary

- [x] 6.1 Audit `rqdata_assets.public_api` and package-level facade exports against CLI usage, tests, and stable programmatic entry points.
- [x] 6.2 Move test-only or private helper access toward direct module imports or an explicitly named test-support boundary where needed.
- [x] 6.3 Keep stable public RQData functions importable from the package facade.
- [x] 6.4 Run CLI parser, package facade, and affected RQData tests after facade changes.

## 7. Static Quality Ratchet

- [x] 7.1 Re-run the diagnostic Ruff rule set and record the current top categories of historical debt without making it a global gate.
- [x] 7.2 Fix newly touched-file issues for import order, unused imports, unused variables, late-binding loop variables, and added long lines.
- [x] 7.3 Evaluate one additional Ruff rule batch for future enforcement and document whether it is ready, deferred, or needs preparatory cleanup.
- [x] 7.4 Run `scripts/dev/run_tests.sh lint` and keep the changed-file ratchet passing.

## 8. Maintainer Scripts And Final Verification

- [x] 8.1 Audit `scripts/internal/` ownership and references, especially `run_hk_asset_workflow.py`, `package_repo.sh`, and `export_repo_source.py`.
- [x] 8.2 Keep or replace internal scripts only after documenting callers, tests, and migration paths.
- [x] 8.3 Run script/docs tests relevant to any script documentation changes.
- [x] 8.4 Run the final focused verification matrix for all touched areas.
- [x] 8.5 Summarize completed cleanup, remaining debt, and next recommended apply targets in `docs/internal/maintenance-debt-inventory.md` or the final apply summary.
