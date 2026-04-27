## Context

The repository already has clear user documentation, a maintained CLI surface, a sizeable offline test suite, and an internal maintenance debt inventory. The remaining problems are not architectural collapse; they are accumulated research-system debt: large orchestration functions, very wide parameter lists, compatibility shims without a firm retirement path, a broad RQData public facade, maintainer scripts with mixed lifetimes, and a Ruff configuration that catches high-risk failures but does not yet enforce broader PEP 8 / modern Python conventions across the whole tree.

The current local audit found 249 tracked Python files, about 89,020 Python lines, 169 functions over 100 lines, 29 functions over 250 lines, and 34 file-level `C901` ignores. The largest current hotspots include `data_tools/rqdata_assets/asset_health.py`, `pipeline/train_eval_stage.py`, `pipeline/runner.py`, `pipeline/config.py`, `backtest.py`, `pipeline/output_artifacts.py`, and RQData mirror/release orchestration modules.

The implementation must respect the repository rules in `AGENTS.md`: keep public docs focused, avoid committing `artifacts/`, prefer small scoped changes, preserve provider and HK asset workflows, and run tests matched to the touched area.

## Goals / Non-Goals

**Goals:**

- Reduce high-risk maintenance debt without changing documented CLI behavior, config compatibility, provider behavior, artifact schemas, or research semantics.
- Convert the audit findings into an executable sequence of small refactors that can be applied and verified independently.
- Establish clear rules for compatibility shims, legacy config/symbol aliases, public facades, maintainer scripts, and static quality ratchets.
- Improve cohesion by moving pure helpers, request objects, rendering/reporting code, and policy decisions into narrower modules.
- Keep tests and internal documentation updated as each cleanup step lands.

**Non-Goals:**

- No broad rewrite of the pipeline, RQData asset system, or release workflow.
- No breaking removal of public CLI commands, documented config keys, symbol aliases, provider behavior, or artifact fields.
- No full-repository auto-format or mass Ruff autofix pass as part of one change.
- No direct heavy scan of large `artifacts/assets/` or `artifacts/cache/` datasets from the agent session.
- No change to model results or backtest accounting except where explicitly covered by focused regression tests.

## Decisions

### Decision: Use staged, behavior-preserving refactors

Each implementation step will isolate one boundary and keep the public behavior stable. Refactors should prefer extracting pure helpers, dataclasses/request objects, rendering/report builders, path resolvers, and policy functions before changing control flow.

Alternative considered: rewrite the large modules around a new architecture in one pass. This was rejected because the pipeline and HK asset workflows are tied to many tests, docs, and historical compatibility paths; a single rewrite would make behavioral regressions hard to isolate.

### Decision: Prioritize by risk, not only file size

The first implementation targets are:

- `pipeline/train_eval_stage.py`: reduce the 98-argument implementation surface by continuing to use `TrainEvalRequest` and smaller stage helpers.
- `pipeline/runner.py`: split the top-level `run()` orchestration into stage setup, dataset load, train/eval execution, benchmark/backtest preparation, and output persistence boundaries.
- `data_tools/rqdata_assets/asset_health.py`: continue extracting scan, aggregation, severity, and report logic.
- `pipeline/config.py`, `backtest.py`, `output_artifacts.py`, and `mirror_workflow.py`: follow after higher-risk boundaries have stronger tests or clearer seams.

Alternative considered: start with the largest files only. This was rejected because some large files are lower-risk research/reporting tools, while smaller files with very wide arguments or public facade effects create more coupling.

### Decision: Treat compatibility as a managed boundary

Compatibility shims and legacy inputs remain until they have a documented replacement and a verified repo-local usage audit. `cstree.pipeline.data` is a deletion candidate because internal imports have moved to canonical modules, but it should first emit a deprecation warning or be removed only after confirming external import risk is acceptable. Legacy `universe` config support and symbol aliases such as `ts_code` / `stock_ticker` stay accepted at input boundaries while canonical outputs continue to converge on `research_universe` and `symbol`.

Alternative considered: delete all repo-local unused compatibility paths immediately. This was rejected because published packages, old experiment configs, local scripts, and stored data snapshots can depend on compatibility behavior even when the current repository does not import it.

### Decision: Narrow public facades separately from implementation refactors

`rqdata_assets.public_api` and package-level facade behavior should be handled as a boundary cleanup, not mixed into large algorithmic changes. Stable public functions should remain importable. Argument builders, private helpers, and test-only helpers should move toward direct module imports or explicit test support modules where necessary.

Alternative considered: collapse the facade while refactoring RQData health or mirror code. This was rejected because facade changes affect import compatibility and test structure independently from runtime behavior.

### Decision: Advance Ruff through ratchets

The current global Ruff rules remain conservative, while changed files are held to stricter checks such as import ordering, unused imports, unused variables, late-binding loop variables, new long lines, and new complexity ignores. Broader rules such as `UP`, `B`, `SIM`, and `RUF` should be introduced in batches only after measuring historical failures and fixing them in scoped changes.

Alternative considered: enable a strict full-tree Ruff profile immediately. This was rejected because the current diagnostic count is high enough to create noisy mechanical churn and obscure behavioral review.

### Decision: Keep maintainer scripts unless replacement is proven

Scripts in `scripts/internal/` are private helpers, but private does not mean unused. `run_hk_asset_workflow.py` must stay until the dev scripts that call it move to a supported module or CLI entry point. `package_repo.sh` is covered by tests and can stay private. `export_repo_source.py` is a low-priority cleanup candidate, but removal requires a usage decision and documentation update.

Alternative considered: delete low-frequency scripts based only on repo-local references. This was rejected because maintainer workflows may be local and not visible to static import search.

## Risks / Trade-offs

- Large-function extraction can accidentally change data ordering, default handling, or summary payloads -> use focused regression tests for each touched boundary and avoid changing multiple behavioral surfaces in one task.
- Deprecation warnings can make tests noisy -> add warnings intentionally, assert them in targeted tests, and avoid warning from hot internal paths where the repo already uses canonical imports.
- Facade narrowing can break external imports -> keep stable public exports, audit tests and docs, and stage private helper removals separately.
- Static quality expansion can create large mechanical diffs -> apply stricter checks first to changed files, then shrink historical violations in small batches.
- Script cleanup can disrupt local maintenance workflows -> preserve script entry points until replacement commands, docs, and tests are in place.
- Refactoring around RQData and asset health may tempt large data scans -> use synthetic fixtures and existing tests; heavy real-data inspections remain a local maintainer task.

## Migration Plan

1. Land governance docs/specs and keep the change behavior-neutral.
2. Apply one refactor boundary at a time, marking tasks complete only after targeted tests pass.
3. For any compatibility path, add deprecation notes or warnings before removal unless the user explicitly approves immediate deletion.
4. Update `docs/internal/maintenance-debt-inventory.md` after meaningful metric changes or boundary decisions.
5. Keep rollback simple by making each task a small patch that can be reverted independently.

## Open Questions

- Should `cstree.pipeline.data` be removed immediately for this project, or kept for one release window with a `DeprecationWarning`?
- Should `export_repo_source.py` remain as a private maintainer helper, move to a documented dev script, or be deleted after this cleanup pass?
- Which Ruff rule batch should become the next global gate after the current changed-file ratchet: import sorting, pyupgrade, bugbear, or Ruff-specific rules?
