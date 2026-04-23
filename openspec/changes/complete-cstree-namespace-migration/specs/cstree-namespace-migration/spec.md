## ADDED Requirements

### Requirement: Cstree-first public naming

The system SHALL use `cstree` as the preferred public namespace for new user-facing documentation, examples, generated commands, public CLI references, public module execution examples, and public behavior tests.

#### Scenario: New public CLI documentation is added

- **WHEN** a new public CLI command or example is documented
- **THEN** the documented command uses `cstree` unless the surrounding text is explicitly describing legacy `csml` compatibility

#### Scenario: New public module execution documentation is added

- **WHEN** a public module tool is documented with `python -m`
- **THEN** the documented module path uses `cstree.<module>` unless the surrounding text is explicitly describing legacy `csml` compatibility

#### Scenario: New generated shell command is added

- **WHEN** repository code or scripts generate a user-facing command string for this project
- **THEN** the generated command uses `cstree` or `python -m cstree...` for the public entry point

### Requirement: Compatibility window preserves csml entry points

The system MUST preserve the existing `csml` compatibility surface until the final breaking migration gate is explicitly approved.

#### Scenario: Legacy console script is invoked during compatibility window

- **WHEN** a user invokes the `csml` console script during the compatibility window
- **THEN** the command remains available and dispatches to the same behavior as the corresponding `cstree` command

#### Scenario: Legacy module path is executed during compatibility window

- **WHEN** a user runs a documented legacy `python -m csml...` module path during the compatibility window
- **THEN** the module remains executable or remains covered by an explicit compatibility policy

#### Scenario: Legacy Python import is used during compatibility window

- **WHEN** code imports a public `csml` module during the compatibility window
- **THEN** the import remains valid unless that module was never part of the documented or tested compatibility surface

### Requirement: Cstree namespace wrappers are testable

The system SHALL provide testable `cstree` entry points for documented public module paths and importable public surfaces.

#### Scenario: Documented cstree module tool is executed

- **WHEN** a documented public module tool is executed as `python -m cstree.<module> --help`
- **THEN** the command exits successfully and prints help text

#### Scenario: Public cstree import surface is imported

- **WHEN** a public import surface is imported through `cstree.<module>`
- **THEN** the import resolves to the intended implementation or wrapper without requiring callers to import `csml`

#### Scenario: New public module tool is introduced

- **WHEN** a new module tool is made public in docs or scripts
- **THEN** a corresponding `cstree` wrapper or alias coverage test is added before release

### Requirement: Environment variable precedence is cstree-first

The system SHALL prefer `CSTREE_*` environment variables over legacy `CSML_*` environment variables during the compatibility window, while retaining `CSML_*` as fallback aliases until the final breaking phase.

#### Scenario: Preferred and legacy variables are both set

- **WHEN** both a `CSTREE_*` variable and its legacy `CSML_*` counterpart are set
- **THEN** the `CSTREE_*` value takes precedence

#### Scenario: Only legacy variable is set during compatibility window

- **WHEN** only the legacy `CSML_*` variable is set during the compatibility window
- **THEN** the system accepts it as a fallback value

#### Scenario: Documentation mentions environment variables

- **WHEN** documentation describes environment variable configuration during the compatibility window
- **THEN** it lists `CSTREE_*` as preferred and `CSML_*` as legacy compatibility

### Requirement: Remaining csml references are categorized

The system SHALL categorize remaining `csml` references before each migration phase so reviewers can distinguish intentional compatibility or implementation references from accidental public usage.

#### Scenario: Namespace audit is performed

- **WHEN** maintainers audit `csml` references before a migration phase
- **THEN** each remaining reference is classified as compatibility contract, internal implementation, test monkeypatch or logger target, packaging metadata, documentation of legacy behavior, or accidental public usage

#### Scenario: Accidental public usage is found

- **WHEN** an audit finds accidental public-facing `csml` usage during the compatibility window
- **THEN** that usage is migrated to `cstree` or documented as an intentional compatibility reference

### Requirement: Breaking removal requires an explicit gate

The system MUST NOT remove the legacy `csml` CLI, public module paths, public imports, or `CSML_*` environment variable fallbacks until a breaking-change gate has been completed.

#### Scenario: A removal is proposed before the gate

- **WHEN** a change proposes removing a legacy `csml` entry point before the breaking gate is complete
- **THEN** the change is rejected or re-scoped to compatibility-window hardening

#### Scenario: Breaking gate is completed

- **WHEN** the breaking gate is completed
- **THEN** it identifies the target version, migration path, test changes, documentation updates, release notes, and rollback plan for removing `csml`

#### Scenario: Final breaking phase is implemented

- **WHEN** the final breaking phase removes legacy `csml` behavior
- **THEN** packaging metadata, docs, tests, environment variable handling, module execution paths, and import expectations are updated to the `cstree`-only contract

### Requirement: Final implementation ownership is cstree

After the final breaking migration, the system SHALL make `cstree` the implementation-owning public package and MUST NOT require users to depend on `csml` names for supported behavior.

#### Scenario: User installs final breaking release

- **WHEN** a user installs the final breaking release
- **THEN** the supported console script is `cstree` and supported public imports use `cstree`

#### Scenario: Internal package ownership is reviewed after final move

- **WHEN** the implementation namespace has moved to `cstree`
- **THEN** internal imports, coverage targets, logger strategy, monkeypatch targets, and release tooling are reviewed and updated to match the final package ownership decision
