## 1. Baseline And Guardrails

- [x] 1.1 Record the current maintainability baseline for large functions, long lines, and `C901` ignores in `docs/internal/maintenance-debt-inventory.md` if it has changed since the last inventory.
- [x] 1.2 Identify the targeted regression tests for pipeline, modeling, backtest, RQData asset health, and release workflow refactors before editing behavior code.
- [x] 1.3 Run the current lint gate and note any pre-existing failures or telemetry-only OpenSpec warnings separately from repository issues.

## 2. Pipeline Stage Contracts

- [x] 2.1 Add a pipeline contracts module with focused dataclasses or typed structures for train/eval inputs, settings, services, and results.
- [x] 2.2 Introduce a compatibility facade so `run_train_eval_stage` can be called through grouped contracts without breaking existing callers.
- [x] 2.3 Migrate `pipeline.runner.run` to pass grouped contracts into train/eval instead of expanding all train, eval, backtest, live, benchmark, and service parameters.
- [x] 2.4 Add or update pipeline regression tests that verify existing run artifacts, summary fields, and documented output paths are unchanged.

## 3. Period Evaluation Decomposition

- [x] 3.1 Extract prediction, score postprocess, and rebalance-date sampling helpers from `_evaluate_period`.
- [x] 3.2 Extract IC, Pearson IC, error metrics, hit rate, top-k positive ratio, quantile returns, turnover, and bucket IC calculation helpers.
- [x] 3.3 Extract backtest, benchmark, active-return, and exposure report assembly helpers while preserving existing result keys.
- [x] 3.4 Update final OOS evaluation to use the same period-evaluation contracts and helpers as the main test period.
- [x] 3.5 Run targeted evaluation, backtest, final OOS, and pipeline e2e tests after each extraction step.

## 4. Model Registry

- [x] 4.1 Add a `ModelSpec` registry that captures aliases, defaults, estimator factory, fit strategy, and feature-importance strategy for each supported model.
- [x] 4.2 Migrate `normalize_model_type`, `resolve_model_spec`, `build_model`, `build_model_from_config`, `fit_model`, and `feature_importance_frame` to use the registry.
- [x] 4.3 Preserve existing behavior for `xgb_regressor`, `xgb_ranker`, `ridge`, and `elasticnet`, including ranker groups and sample-weight handling.
- [x] 4.4 Add or update modeling and split tests for aliases, default params, ranker fit behavior, and feature-importance output.

## 5. Static Quality Ratchet

- [x] 5.1 Extend `scripts/dev/run_tests.sh lint` with changed-file high-signal checks that do not require whole-repository cleanup.
- [x] 5.2 Add checks or documentation that prevent new `C901` file-level ignores unless the maintenance debt inventory is updated.
- [x] 5.3 Fix or quarantine high-risk touched-file lint findings such as unused imports, unused variables, import ordering, and late-bound loop variables.
- [x] 5.4 Update `docs/dev.md` with the ratchet workflow and diagnostic commands for broader Ruff rule sets.

## 6. Large Module Follow-Ups

- [x] 6.1 Extract one cohesive responsibility from `rqdata_assets/asset_health.py` using existing `tests/rqdata_assets/` coverage and without running heavy asset scans by default.
- [x] 6.2 Extract one cohesive responsibility from release orchestration modules using release workflow regression tests.
- [x] 6.3 Update `docs/internal/maintenance-debt-inventory.md` after each large-module extraction with before/after counts and remaining `C901` rationale.

## 7. Verification

- [x] 7.1 Run targeted tests for each applied slice, using the verification matrix in `docs/internal/maintenance-debt-inventory.md`.
- [x] 7.2 Run `scripts/dev/run_tests.sh lint` after code changes and resolve any failures introduced by the change.
- [x] 7.3 Run `openspec status --change improve-pipeline-maintainability` and confirm the change remains apply-ready.
