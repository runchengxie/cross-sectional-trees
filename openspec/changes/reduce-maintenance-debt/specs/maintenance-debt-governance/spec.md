## ADDED Requirements

### Requirement: Maintenance Debt Inventory
The repository SHALL maintain an implementation-facing inventory for each maintenance-debt reduction phase that classifies candidates as compatibility shim, oversized module, command glue, maintainer script, static-quality debt, or public-boundary ambiguity.

#### Scenario: Candidate is inventoried before work starts
- **WHEN** a phase proposes to remove, relocate, split, or materially refactor a file
- **THEN** the inventory records the target files, current repo-local usages, relevant documentation references, risk level, proposed action, and validation commands

#### Scenario: Public entry is not mislabeled as dead code
- **WHEN** a candidate appears outside the quick-start path but is listed in `docs/capabilities.md`, `docs/cli.md`, `scripts/README.md`, or a playbook
- **THEN** the inventory marks it as public, research, release, or maintainer surface before any removal decision is made

### Requirement: Compatibility Exit Process
The repository SHALL retire compatibility code through an explicit audit and migration process before deleting or breaking legacy entry points.

#### Scenario: Legacy config compatibility is changed
- **WHEN** behavior around legacy `universe` config keys is modified
- **THEN** tests cover canonical `research_universe`, legacy `universe`, and the conflict case where both keys are present

#### Scenario: Legacy symbol aliases are changed
- **WHEN** behavior around `ts_code`, `stock_ticker`, or `order_book_id` compatibility is modified
- **THEN** tests cover canonical `symbol` inputs, supported legacy aliases, and outputs that must not reintroduce legacy columns where docs promise canonical `symbol`

#### Scenario: Import shim is removed
- **WHEN** `cstree.pipeline.data` or another re-export shim is removed
- **THEN** repo-local imports have already been migrated to canonical modules and a migration note identifies the supported replacement import path

### Requirement: Behavior-Preserving Large Module Splits
Large module refactors SHALL preserve public behavior unless a breaking change is explicitly proposed separately.

#### Scenario: Orchestration module is split
- **WHEN** a module such as `hk_asset_workflow.py`, `asset_health.py`, `coverage.py`, `build.py`, or `pipeline/eval.py` is split
- **THEN** the extracted modules have responsibility-oriented names and the original public entry point continues to work

#### Scenario: Large function is reduced
- **WHEN** a function over 250 lines is refactored
- **THEN** the replacement separates orchestration from parsing, scanning, computation, rendering, or persistence as applicable

#### Scenario: Complexity ignore is removed
- **WHEN** a file-level `C901` ignore is removed from `pyproject.toml`
- **THEN** the corresponding target tests pass and Ruff no longer reports a complexity violation for that file under the repository lint configuration

### Requirement: RQData Command Registration Simplification
RQData asset commands SHALL be registered from a clear declarative command definition rather than requiring maintainers to follow multiple layers of thin wrappers for ordinary changes.

#### Scenario: Command definition is updated
- **WHEN** a maintainer adds or changes an RQData asset command
- **THEN** the command name, help text, runner, client requirement, defaults, and argument builder are discoverable from the command spec path without editing unrelated command wrappers

#### Scenario: Existing CLI remains stable
- **WHEN** the RQData command registration internals are refactored
- **THEN** existing `cstree rqdata ...` command parsing tests continue to pass for the currently documented commands

### Requirement: Liveops CLI Registration Simplification
Liveops CLI registration SHALL be decomposed so command-specific options and handler argument forwarding are reviewable without reading one long parser function.

#### Scenario: Liveops command options are changed
- **WHEN** a maintainer changes `holdings`, `snapshot`, `alloc`, or `alloc-hk` options
- **THEN** the command-specific parser definition and handler forwarding are localized enough that unrelated liveops commands do not need to be edited

#### Scenario: Alloc-hk behavior is preserved
- **WHEN** `alloc-hk` parser registration or forwarding is refactored
- **THEN** tests cover representative existing options, boolean switches, repeated scenario arguments, and output format handling

### Requirement: Maintainer Script Boundary
Maintainer-only scripts SHALL either have a documented retained purpose or be removed/relocated with a replacement path.

#### Scenario: Maintainer script is kept
- **WHEN** a script under `scripts/internal/` remains in the repository
- **THEN** `scripts/README.md` or a relevant maintainer doc explains whether it is a retained driver, private helper, or compatibility wrapper

#### Scenario: Maintainer script is removed
- **WHEN** a script under `scripts/internal/` is removed
- **THEN** tests and docs that reference it are updated, and an equivalent `cstree` CLI or `python -m cstree...` path is documented if the workflow still exists

### Requirement: Incremental Static Quality Ratchet
Static quality gates SHALL become stricter incrementally without forcing broad unrelated formatting churn.

#### Scenario: Touched Python file has style debt
- **WHEN** a phase edits a Python file
- **THEN** that phase avoids introducing new long lines, unused imports, or new complexity exceptions in the edited file

#### Scenario: Existing debt is reduced
- **WHEN** a phase intentionally addresses lint or complexity debt
- **THEN** it reduces the relevant long-line count, large-function count, or `C901` ignore count and records the before/after scope in the implementation notes

### Requirement: Documentation and Test Alignment
Maintenance-debt changes SHALL keep documentation and regression tests aligned with the affected public or maintainer boundary.

#### Scenario: Public CLI or config behavior changes
- **WHEN** public CLI arguments, config keys, symbol behavior, artifact outputs, or provider rules change
- **THEN** the corresponding docs listed in `AGENTS.md` are updated in the same phase

#### Scenario: RQData or HK pipeline internals change
- **WHEN** a phase touches RQData assets, HK pipeline filtering, fundamentals provider behavior, or release workflow helpers
- **THEN** the phase runs or records the targeted tests that match the touched area, using offline tests by default and avoiding large asset scans unless explicitly required
