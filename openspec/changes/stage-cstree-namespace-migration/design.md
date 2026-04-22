## Context

The repository currently uses `cstree` as the preferred user-facing CLI name,
while `csml` remains embedded in several public and semi-public contracts:

- Console scripts expose both `cstree` and `csml`, both targeting
  `csml.cli:main`.
- The importable source package is `src/csml/`; no `src/cstree/` package exists.
- Documentation still publishes module tools such as
  `python -m csml.release_tools.package_assets`.
- Runtime settings use `CSML_*` environment variables.
- Tests explicitly assert CLI compatibility and import `csml` modules directly.

This change should make `cstree` the target identity without treating the
existing `csml` surface as disposable. The first implementation must be
additive.

## Goals / Non-Goals

**Goals:**

- Provide a staged path for `cstree` CLI, Python module, environment variable,
  documentation, and test coverage.
- Preserve existing `csml` entry points during the initial compatibility window.
- Make new public examples and tests prove that `cstree` works beyond the CLI
  script name.
- Define the gates required before any future breaking removal of `csml`.

**Non-Goals:**

- Do not rename `src/csml/` in the first implementation phase.
- Do not remove the `csml` console script or existing `python -m csml...`
  module paths in this change.
- Do not rewrite all internal imports from `csml` to `cstree` as a cosmetic
  refactor.
- Do not change package distribution name `cross-sectional-hk-trees` unless a
  separate packaging decision requires it.

## Decisions

### Add a `cstree` bridge package before renaming internals

Create a small `src/cstree/` namespace for documented public surfaces. The
bridge should delegate to the existing `csml` implementation instead of moving
all code at once.

Initial public bridge targets should include:

- `cstree.cli` delegating to `csml.cli`.
- `cstree.release_tools.*` wrappers for documented release tools.
- `cstree.research.*` wrappers only for research modules currently documented
  as runnable with `python -m csml...`.

Rationale: direct directory renames would touch nearly every import, test, and
documentation contract at once. Explicit wrappers keep the migration bounded
and make the public surface auditable.

Alternative considered: alias the entire package dynamically with `sys.modules`
or import hooks. That is broader and harder to reason about for `python -m`
execution, coverage, and stack traces. Explicit wrappers are noisier but safer.

### Treat `csml` as compatibility, not dead code

Keep `csml` imports and CLI working while adding `cstree` equivalents. Tests
should assert equivalence for documented surfaces during the compatibility
period.

Rationale: README, CLI docs, and tests currently promise compatibility. Removing
the alias now would be a breaking change, not cleanup.

Alternative considered: remove `csml` immediately and update all tests. That
would invalidate documented workflows and historical scripts without first
giving users a migration path.

### Add `CSTREE_*` environment variables as aliases

Introduce `CSTREE_ARTIFACTS_ROOT`, `CSTREE_METADATA_DB_PATH`, and
`CSTREE_WAREHOUSE_DB_PATH` while preserving the existing `CSML_*` names as
fallbacks. If both names are present, the `CSTREE_*` value should win because it
is the new preferred spelling.

Rationale: environment variables are user-facing automation contracts. They
need the same compatibility window as CLI and module entry points.

Alternative considered: rename variables in place. That would break shell
profiles, CI jobs, and local scripts.

### Document phases instead of a single breaking rename

Documentation should move in phases:

1. Current state: `cstree` preferred CLI, `csml` compatibility documented.
2. Bridge state: `python -m cstree...` documented first, with `csml` noted as
   legacy-compatible.
3. Deprecation state: warnings and release notes identify when `csml` will be
   removed.
4. Removal state: only after tests, docs, and release policy are updated in a
   separate breaking-change proposal.

Rationale: the project has both user-facing docs and maintenance scripts. A
phased plan keeps each contract visible.

## Risks / Trade-offs

- Duplicate wrapper modules can drift from `csml` implementations -> keep
  wrappers thin and cover each documented wrapper with smoke tests.
- Users may be confused by two valid namespaces -> docs must state `cstree` is
  preferred and `csml` is compatibility.
- Environment variable precedence can surprise existing users -> document the
  exact precedence and test conflicts.
- A future full rename may still be large -> defer the destructive rename until
  bridge usage and deprecation warnings have shipped.

## Migration Plan

1. Add `src/cstree/` bridge modules for the documented public surfaces.
2. Update package discovery and console script tests so `cstree` imports and
   module execution are covered.
3. Add `CSTREE_*` environment variable constants and fallback resolution.
4. Update docs to prefer `python -m cstree...` where bridge modules exist, while
   retaining `python -m csml...` as legacy-compatible.
5. Add deprecation policy text for `csml` that names the compatibility window
   and removal gates.
6. In a later breaking-change proposal, remove `csml` only after the bridge and
   deprecation period have been released and validated.

Rollback strategy: because the first phase is additive, rollback can remove the
new `src/cstree/` wrappers, `CSTREE_*` aliases, and documentation changes while
leaving existing `csml` behavior intact.

## Open Questions

- How many release cycles should the `csml` compatibility window last?
- Should deprecation warnings be emitted by default, only in module execution,
  or only under an opt-in warning mode?
- Should all research modules receive `cstree` wrappers, or only the modules
  currently documented as public runnable tools?
