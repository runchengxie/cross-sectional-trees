## Context

The current codebase already has useful domain boundaries: data provider
access, pipeline modules, research tools, live operations, release tooling, and
tests are separated at the directory level. The main maintainability pressure is
inside orchestration paths where stage state is passed through large dictionaries
or long argument lists.

The highest-priority examples are:

- `src/cstree/pipeline/train_eval_stage.py::run_train_eval_stage`, which has a
  very large keyword-only signature and mixes CV, model fit, live snapshot,
  period evaluation, walk-forward, backtest settings, and result assembly.
- `src/cstree/pipeline/runner.py::run`, which expands many config dictionaries
  into local variables and passes them onward.
- `src/cstree/pipeline/eval.py::_evaluate_period`, which combines scoring,
  metrics, backtest, benchmark, exposure, and report assembly.
- `src/cstree/modeling.py`, where model construction and fit behavior are still
  centralized through conditional branches.
- `pyproject.toml` and `scripts/dev/run_tests.sh`, where quality checks exist
  but are intentionally conservative and need a ratchet path.

This design keeps public behavior stable while making the code easier to change
in small, reviewable apply steps.

## Goals / Non-Goals

**Goals:**

- Reduce coupling between pipeline stages by introducing explicit state/config
  objects at stage boundaries.
- Keep the pipeline runner as an orchestrator, not a holder of every field in
  every downstream stage.
- Split evaluation logic by responsibility without changing the public output
  contract.
- Make model support extensible through a registry while preserving existing
  model aliases and helper APIs.
- Expand static quality checks incrementally, starting with touched-file and
  high-signal rules.
- Preserve existing CLI commands, config compatibility, artifact paths, and
  summary/output schemas unless a later proposal explicitly changes them.

**Non-Goals:**

- Do not change research methodology, labels, features, default presets, or
  benchmark interpretation in this change.
- Do not add new models as part of the initial refactor; make adding models
  safer later.
- Do not rewrite the whole pipeline in one apply step.
- Do not require full-repository PEP8 cleanup before normal development can
  continue.
- Do not run heavy RQData asset scans in agent sessions as part of validation.

## Decisions

### Decision 1: Use dataclasses or narrow typed structures for stage state

Introduce focused objects such as `PipelineSetupState`, `RuntimeSettings`,
`PanelState`, `FeatureDatasetState`, `SplitState`, `TrainEvalInputs`,
`TrainEvalSettings`, `BacktestSettings`, and `TrainEvalResult` as refactors touch
each boundary.

Rationale: the current dictionaries are flexible but make field ownership and
validity hard to see. Dataclasses give a low-dependency path that matches the
project's existing usage in execution, liveops, research, and config helpers.

Alternatives considered:

- Pydantic models: useful for runtime validation, but they add a dependency and
  are heavier than needed for the first pass.
- Full static typing with mypy/pyright first: valuable later, but typed state
  objects are a better prerequisite.

### Decision 2: Refactor one boundary at a time

Apply steps should first create compatibility-preserving wrappers, then migrate
callers, then remove obsolete dict unpacking only when tests cover the path.

Rationale: this project has many data, config, and artifact contracts. Small
steps reduce the chance of changing research outputs while improving structure.

Alternatives considered:

- Large pipeline rewrite: faster to describe but too risky for a research
  system with many compatibility paths.
- Pure helper extraction without typed state: lower initial effort, but it does
  not solve the main coupling problem.

### Decision 3: Split period evaluation by output responsibility

Keep `_evaluate_period` as a facade initially, then extract helpers for:

- prediction and score postprocess
- rebalance-date sampling
- IC, quantile, error, hit-rate, and top-k metrics
- backtest and live fallback handling
- benchmark and active returns
- exposure summaries
- result assembly

Rationale: preserving the facade lets existing callers and tests remain stable
while individual responsibilities become testable.

Alternatives considered:

- Replace `_evaluate_period` immediately with a class-based evaluator: this may
  be useful later, but a facade plus helpers is a safer first step.

### Decision 4: Introduce a model registry behind existing helpers

Keep `normalize_model_type`, `resolve_model_spec`, `build_model`,
`build_model_from_config`, `fit_model`, and `feature_importance_frame` as public
helpers. Implement them through a registry of model specs that define aliases,
defaults, factory, fit strategy, and feature-importance strategy.

Rationale: existing callers and tests keep working, while new model types can be
added without expanding conditional branches in multiple functions.

Alternatives considered:

- Keep the current conditionals until more models are needed: acceptable short
  term, but it keeps extension costs high.
- Introduce a plugin system: unnecessary for the current local model set.

### Decision 5: Expand quality checks with ratchets, not a whole-tree cleanup

The first quality steps should target changed files and high-signal rules:
unused imports, unused variables, import ordering, late-bound loop variables,
new long lines, and new complexity exemptions. Existing broad debt remains
tracked in the internal maintenance inventory until intentionally reduced.

Rationale: full-repository cleanup would create noisy diffs. A ratchet keeps new
work cleaner while allowing focused debt reduction.

Alternatives considered:

- Enable `E,F,W,I,B,UP,SIM,RUF` all at once: useful as a diagnostic command, but
  too disruptive as the default lint gate.
- Keep current lint indefinitely: too weak for the size of the codebase.

## Risks / Trade-offs

- Stage objects can become oversized if they mirror current dictionaries without
  ownership boundaries. Mitigation: keep objects focused by stage and split them
  when a field group has a different lifecycle.
- Behavior-preserving refactors can still change output ordering, defaults, or
  optional artifact fields. Mitigation: use targeted regression tests for each
  touched area and avoid broad formatting churn.
- A model registry can hide model-specific behavior if it is too abstract.
  Mitigation: model specs must make fit and importance behavior explicit.
- Static checks can block unrelated work if enabled too broadly. Mitigation:
  start with changed-file checks and document any baseline movement.
- RQData health and release modules may need domain fixtures to refactor safely.
  Mitigation: prefer small pure helper extractions and existing `tests/rqdata_assets/`
  or release workflow tests over heavy asset scans.

## Migration Plan

1. Add typed state/config objects around the train/eval boundary while keeping
   `run_train_eval_stage` callable through a compatibility facade.
2. Move period-evaluation helper groups out of `_evaluate_period` behind the
   existing return shape.
3. Introduce the model registry and update existing model tests without changing
   accepted config values.
4. Narrow runner unpacking by passing grouped state through stage functions.
5. Expand `scripts/dev/run_tests.sh lint` with touched-file ratchets and update
   `docs/dev.md` plus `docs/internal/maintenance-debt-inventory.md`.
6. Continue behavior-preserving extractions in RQData health and release
   orchestration modules as separate apply steps.

Rollback is straightforward for each step: keep facades in place, revert the
specific extraction or registry change, and rerun the targeted tests listed in
`tasks.md`.

## Open Questions

- Whether to introduce `TypedDict` for transitional dictionary state before
  replacing it with dataclasses in some modules.
- Whether optional type checking should be added as a separate later change
  after stage contracts are in place.
- Which quality rules should become default lint gates first after unused import,
  unused variable, import order, and late-binding checks.
