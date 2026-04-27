## ADDED Requirements

### Requirement: Lint ratchet covers touched files

The development lint workflow SHALL apply high-signal checks to touched Python
files before those checks are made mandatory for the whole repository.

#### Scenario: Changed Python file has an import-order issue

- **WHEN** `scripts/dev/run_tests.sh lint` is run with changed Python files
- **THEN** import ordering is checked for those changed files

#### Scenario: Changed Python file adds a long line

- **WHEN** a changed or untracked Python file adds a line longer than the
  configured project line length
- **THEN** the lint workflow fails and reports the file and line

### Requirement: New complexity debt is blocked

The quality workflow SHALL prevent new complexity exemptions and discourage new
high-complexity functions unless the change explicitly documents why the debt is
temporary and how it will be reduced.

#### Scenario: New C901 file-level ignore is added

- **WHEN** a change adds a new `C901` file-level ignore
- **THEN** the change must update the internal maintenance debt inventory with
  the reason, risk, and follow-up validation plan

#### Scenario: Existing large function is refactored

- **WHEN** an apply step touches an existing large orchestration function
- **THEN** the step should extract or isolate at least one cohesive responsibility
  unless the task is a narrow bug fix

### Requirement: Baseline movement is tracked

Static quality baseline metrics SHALL be tracked when changes intentionally
alter large-file, large-function, long-line, or complexity-exemption counts.

#### Scenario: Refactor reduces large-function count

- **WHEN** a refactor reduces large-function or complexity counts
- **THEN** the maintenance debt inventory records the updated baseline or the
  task notes why the baseline was not updated

#### Scenario: Full strict lint is run diagnostically

- **WHEN** maintainers run a broader diagnostic Ruff rule set
- **THEN** the output is treated as planning input unless the selected rules are
  explicitly added to the default lint workflow

### Requirement: Quality changes remain incremental

Static-quality improvements SHALL avoid broad formatting-only churn unless that
churn is the explicit purpose of the apply step.

#### Scenario: Behavior refactor touches a module

- **WHEN** a behavior-preserving refactor touches a module
- **THEN** formatting and lint fixes are scoped to the touched code or the
  explicitly selected ratchet rules
