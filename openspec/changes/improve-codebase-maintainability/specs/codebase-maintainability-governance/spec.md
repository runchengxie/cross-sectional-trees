## ADDED Requirements

### Requirement: Maintainability work is tracked from an explicit inventory

The project SHALL track staged codebase maintainability work from an explicit inventory that records current hotspots, compatibility candidates, public boundary risks, static quality debt, and preferred validation commands.

#### Scenario: Preparing a maintainability implementation step

- **WHEN** a maintainer starts a cleanup task from this change
- **THEN** the relevant hotspot, compatibility candidate, or static quality issue is identified in internal maintenance documentation or the OpenSpec task list before code changes begin

#### Scenario: Completing a meaningful cleanup step

- **WHEN** a cleanup task materially changes large-function counts, compatibility status, facade boundaries, script ownership, or static quality gates
- **THEN** internal maintenance documentation is updated with the new status or an explicit reason why no documentation update is required

### Requirement: Large-module refactors preserve public behavior

The project SHALL refactor large orchestration modules through small behavior-preserving changes with focused verification for the touched boundary.

#### Scenario: Refactoring a pipeline boundary

- **WHEN** code in `src/cstree/pipeline/` is split into narrower helpers or request objects
- **THEN** the relevant pipeline runtime, train/eval, config, filter, or end-to-end tests are run or the reason they could not be run is recorded

#### Scenario: Refactoring an RQData asset boundary

- **WHEN** code in `src/cstree/data_tools/rqdata_assets/` is split into narrower helpers or modules
- **THEN** the relevant RQData asset tests are run without requiring a heavy real-data scan from `artifacts/assets/` or `artifacts/cache/`

### Requirement: Compatibility shims have explicit retention or retirement paths

The project SHALL manage legacy shims, legacy config keys, and legacy symbol aliases as compatibility boundaries with explicit retention or retirement decisions.

#### Scenario: Handling a legacy import shim

- **WHEN** a legacy import shim such as `cstree.pipeline.data` is changed or removed
- **THEN** repo-local usage is audited, canonical replacement imports are documented in code or internal notes, and targeted pipeline tests are run

#### Scenario: Handling legacy config and symbol aliases

- **WHEN** compatibility for legacy `universe` config keys or symbol aliases such as `ts_code` and `stock_ticker` is touched
- **THEN** canonical behavior remains centered on `research_universe` and `symbol`, while legacy input compatibility is preserved unless a breaking migration is explicitly declared

### Requirement: Public facades expose stable programmatic surfaces only

The project SHALL keep package-level and public API facades focused on stable programmatic entry points rather than test-only or private helper internals.

#### Scenario: Updating an RQData facade

- **WHEN** `rqdata_assets.public_api` or `rqdata_assets.__init__` is changed
- **THEN** documented or stable public functions remain importable and private helpers are either kept internal, moved to direct module imports in tests, or placed behind an explicitly named test-support boundary

#### Scenario: Verifying facade compatibility

- **WHEN** public facade exports are narrowed
- **THEN** CLI parser tests, package facade tests, and any affected RQData tests verify that stable commands and functions still resolve

### Requirement: Static quality advances through ratchets

The project SHALL improve PEP 8 and Ruff conformance through ratchets that prevent new quality debt while historical issues are reduced in scoped batches.

#### Scenario: Running the standard lint gate

- **WHEN** a cleanup task changes Python files
- **THEN** `scripts/dev/run_tests.sh lint` passes or the blocking failure is recorded with a follow-up task

#### Scenario: Expanding lint coverage

- **WHEN** additional Ruff rules are promoted from diagnostic-only to enforced checks
- **THEN** the promoted rules are documented, historical failures are fixed or isolated, and broad mechanical rewrites are avoided unless explicitly approved

### Requirement: Maintainer scripts are removed only after replacement is proven

The project SHALL retain private maintainer scripts until their callers, documentation, and tests have a verified replacement path.

#### Scenario: Evaluating an internal script for deletion

- **WHEN** a script under `scripts/internal/` is proposed for deletion
- **THEN** repo-local references, documentation references, tests, and known maintainer workflow notes are checked before deletion

#### Scenario: Replacing the HK asset workflow wrapper

- **WHEN** `scripts/internal/run_hk_asset_workflow.py` is replaced or removed
- **THEN** `scripts/dev/refresh_hk_current.sh`, `scripts/dev/run_hk_health_checks.sh`, related documentation, and release workflow tests are updated to use the replacement
