## ADDED Requirements

### Requirement: Pipeline stages use explicit contracts

Pipeline stage functions SHALL accept and return explicit stage state or
configuration contracts when they are newly introduced or substantially
refactored.

#### Scenario: Refactored stage boundary

- **WHEN** a pipeline stage boundary is refactored
- **THEN** related inputs and outputs are grouped into named contracts instead of
  being passed as a long unstructured parameter list or an unbounded dictionary

#### Scenario: Contract ownership is visible

- **WHEN** a maintainer reads a stage function signature
- **THEN** the signature identifies the stage data, settings, and services the
  stage owns or consumes

### Requirement: Runner remains an orchestrator

The pipeline runner SHALL coordinate stage execution without expanding every
downstream configuration field into local variables solely for pass-through.

#### Scenario: Runner calls train and evaluation

- **WHEN** the runner invokes train/eval behavior
- **THEN** it passes grouped stage contracts rather than a flat list of model,
  evaluation, backtest, live, benchmark, and service parameters

#### Scenario: Runner output compatibility

- **WHEN** the runner completes successfully after a refactor
- **THEN** existing run artifacts, summary fields, and documented output paths
  remain compatible with the pre-refactor behavior

### Requirement: Evaluation responsibilities are separable

Period evaluation SHALL expose separable units for scoring, metrics, backtest,
benchmark, exposure, and result assembly while preserving the current external
result shape.

#### Scenario: Evaluating a test period

- **WHEN** a test period is evaluated
- **THEN** scoring, metric calculation, backtest reporting, benchmark alignment,
  exposure reporting, and result assembly can be tested independently

#### Scenario: Final OOS uses shared evaluation behavior

- **WHEN** final OOS evaluation runs
- **THEN** it reuses the same period-evaluation contracts and helpers as the
  main test period unless a documented difference is required

### Requirement: Public pipeline compatibility is preserved

Pipeline refactors SHALL preserve public CLI commands, accepted config keys,
compatibility aliases, and documented output schemas unless a later proposal
explicitly defines a migration.

#### Scenario: Existing config runs after refactor

- **WHEN** an existing supported pipeline config is run after a maintainability
  refactor
- **THEN** the command accepts the same public config keys and produces the same
  documented artifact categories

#### Scenario: Compatibility aliases remain at boundaries

- **WHEN** legacy config aliases or symbol aliases are accepted today
- **THEN** they remain accepted at the documented boundary until a separate
  compatibility-removal proposal is approved
