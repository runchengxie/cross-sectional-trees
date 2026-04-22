## ADDED Requirements

### Requirement: Preferred CLI identity preserves compatibility
The system SHALL expose `cstree` as the preferred command-line identity while
preserving the existing `csml` command-line entry point during the documented
compatibility period.

#### Scenario: Both CLI entry points invoke the same command surface
- **WHEN** a user runs either `cstree --help` or `csml --help`
- **THEN** the same supported subcommands and options are available

#### Scenario: Parser program name remains entry-point specific
- **WHEN** help is generated through the `cstree` entry point
- **THEN** the displayed program name is `cstree`
- **WHEN** help is generated through the `csml` entry point
- **THEN** the displayed program name is `csml`

### Requirement: Public cstree module namespace exists before documentation migration
The system SHALL provide `cstree` module entry points for public module-level
tools before documentation replaces corresponding `python -m csml...` examples
with `python -m cstree...` examples.

#### Scenario: Release tool module wrappers execute through cstree
- **WHEN** a documented release helper is available as
  `python -m csml.release_tools.<tool>`
- **THEN** the equivalent `python -m cstree.release_tools.<tool>` entry point
  delegates to the same implementation

#### Scenario: Research tool module wrappers are limited to documented surfaces
- **WHEN** a research module is documented as a runnable public or playbook tool
- **THEN** the equivalent `python -m cstree.research.<tool>` entry point exists
- **WHEN** a research module is not documented as a runnable public or playbook
  tool
- **THEN** the migration does not need to create a `cstree` wrapper for that
  module

### Requirement: Environment variable aliases preserve legacy automation
The system SHALL accept `CSTREE_*` environment variable names for public runtime
path overrides while preserving existing `CSML_*` names as fallback aliases
during the compatibility period.

#### Scenario: New environment variable name is accepted
- **WHEN** `CSTREE_ARTIFACTS_ROOT` is set and no explicit CLI override is
  provided
- **THEN** default artifact paths resolve from `CSTREE_ARTIFACTS_ROOT`

#### Scenario: Legacy environment variable remains accepted
- **WHEN** `CSML_ARTIFACTS_ROOT` is set and `CSTREE_ARTIFACTS_ROOT` is not set
- **THEN** default artifact paths continue to resolve from `CSML_ARTIFACTS_ROOT`

#### Scenario: New environment variable wins conflicts
- **WHEN** both `CSTREE_ARTIFACTS_ROOT` and `CSML_ARTIFACTS_ROOT` are set
- **THEN** default artifact paths resolve from `CSTREE_ARTIFACTS_ROOT`

### Requirement: Documentation states primary and compatibility surfaces
The system SHALL document `cstree` as the preferred public identity and `csml`
as a compatibility identity wherever both names are intentionally supported.

#### Scenario: New user-facing examples prefer cstree
- **WHEN** documentation gives a new command or module execution example
- **THEN** the example uses the `cstree` CLI or `cstree` module path when that
  surface exists

#### Scenario: Compatibility behavior remains discoverable
- **WHEN** documentation mentions migration-sensitive entry points,
  environment variables, or module paths
- **THEN** it explains whether the `csml` spelling is primary, compatible, or
  deprecated

### Requirement: csml removal requires an explicit breaking-change gate
The system MUST NOT remove `csml` CLI, import, module execution, or environment
variable compatibility until a separate breaking-change plan documents the
removal version, migration path, tests, and release-note requirements.

#### Scenario: Initial migration keeps csml working
- **WHEN** the first implementation phase for this change is complete
- **THEN** existing documented `csml` CLI, module execution, import, and
  `CSML_*` environment variable behaviors still work

#### Scenario: Breaking removal is deferred
- **WHEN** maintainers want to remove a `csml` compatibility surface
- **THEN** they create or update a breaking-change proposal before deleting that
  surface
