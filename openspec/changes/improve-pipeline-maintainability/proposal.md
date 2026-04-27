## Why

The project has a sound research workflow, but several core paths now rely on
large orchestration functions, long parameter lists, and untyped dictionary
state. This makes future model, evaluation, and data-quality changes harder to
review, test, and apply incrementally.

## What Changes

- Introduce explicit pipeline stage contracts so the runner passes typed state
  objects between setup, panel loading, dataset preparation, split, train/eval,
  final OOS, and output persistence.
- Reduce the train/eval parameter surface by grouping related inputs into
  focused state/config/service objects.
- Split period evaluation into smaller units for scoring, metrics, backtest,
  exposure, benchmark, and result assembly while preserving existing outputs.
- Add a model registry extension point for model defaults, construction, fit
  behavior, and feature-importance extraction.
- Add a static-quality ratchet that can be applied to touched files first and
  expanded over time without forcing a whole-repository cleanup.
- Continue the existing large-module debt plan by treating RQData health and
  release orchestration refactors as behavior-preserving extractions with
  targeted regression tests.
- No planned breaking changes to public CLI commands, config keys, artifact
  layout, or documented output schemas.

## Capabilities

### New Capabilities

- `pipeline-stage-contracts`: Internal contracts for pipeline stage inputs,
  outputs, and orchestration boundaries.
- `model-registry`: Extensible model specification and fitting registry for
  supported estimators.
- `static-quality-ratchet`: Development guardrails for lint, complexity, line
  length, and touched-file quality checks.

### Modified Capabilities

- None.

## Impact

- Affected code: `src/cstree/pipeline/*`, `src/cstree/modeling.py`,
  `src/cstree/split.py`, selected `src/cstree/data_tools/rqdata_assets/*`,
  selected `src/cstree/release_tools/*`, `scripts/dev/run_tests.sh`, and tests.
- Affected docs: `docs/dev.md`, `docs/internal/maintenance-debt-inventory.md`,
  and public docs only if a documented CLI/config/output contract changes.
- Public compatibility: existing CLI commands, config aliases, output files,
  and summary fields should remain compatible unless a later change explicitly
  proposes a migration.
- Dependencies: no new runtime dependency is required by default. Optional
  type-checking or lint tools may be proposed as development-only additions.
