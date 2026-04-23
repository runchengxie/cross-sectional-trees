## Context

The repository is already in an additive namespace migration. User-facing docs and examples prefer `cstree`; `pyproject.toml` exposes both `cstree` and `csml`; `src/cstree/` is a public bridge that delegates to the implementation still living under `src/csml/`; and `docs/capabilities.md` explicitly keeps `csml` CLI, module paths, imports, and `CSML_*` environment variables alive during the current compatibility window.

The remaining work is cross-cutting because the namespace appears in CLI entry points, module execution paths, tests, generated shell commands, docs, environment variable fallbacks, logger names, coverage configuration, and monkeypatch targets. Treating this as a simple string replacement would break documented compatibility and make it hard to stage the final breaking change.

## Goals / Non-Goals

**Goals:**

- Make new public-facing usage consistently `cstree` first.
- Keep the current `csml` compatibility surface stable until a final breaking gate is explicitly approved.
- Provide a phase-by-phase migration path that can be implemented incrementally.
- Define testable requirements for `cstree` wrappers, `csml` compatibility, docs, environment variables, and final removal criteria.
- Separate near-term non-breaking work from the final breaking package/namespace move.

**Non-Goals:**

- Do not remove `csml` in the near-term phases.
- Do not rename every internal import purely for cosmetics while the implementation still lives in `src/csml/`.
- Do not change research, data, provider, or artifact semantics as part of the namespace migration.
- Do not introduce deprecation warnings by default during the current compatibility window unless a later proposal decides that warning behavior explicitly.

## Decisions

### Stage the migration as a lifecycle, not a single rename

The migration will be split into non-breaking cstree-first phases, a pre-breaking deprecation/readiness phase, and a final breaking-removal phase.

Alternative considered: rename `src/csml/` to `src/cstree/` immediately and delete the bridge. That would violate current documentation, break the registered `csml` console script, and invalidate tests that intentionally protect compatibility.

### Keep the additive bridge until the breaking gate

Before the final breaking phase, `cstree.*` remains the preferred public namespace while delegating to existing `csml.*` implementation modules through explicit wrappers and the current alias finder. New public modules should either have explicit `cstree` wrappers when they are documented module execution paths, or be covered by namespace alias tests when they are import-only surfaces.

Alternative considered: duplicate implementation files under both packages. That creates two sources of truth and makes behavior drift likely.

### Prefer cstree in public tests while preserving compatibility tests

Tests that model public usage should import or execute `cstree` paths. Tests that assert backward compatibility should keep targeted `csml` imports, `csml` CLI checks, and legacy environment variable checks. Internal tests may continue to use `csml` while the implementation package is still `src/csml/`, especially for monkeypatch targets and logger assertions.

Alternative considered: migrate all tests to `cstree` immediately. That would hide regressions in the compatibility surface and make monkeypatches less direct while aliases still resolve to `csml` modules.

### Treat environment variables as a precedence contract

During the compatibility window, `CSTREE_*` names are preferred and `CSML_*` names remain fallback aliases. The final breaking phase removes `CSML_*` fallbacks only after docs, tests, and release notes have a concrete migration path.

Alternative considered: warn whenever `CSML_*` is used. The current docs avoid default deprecation warnings because many automation workflows treat stderr or warnings as failures.

### Defer logger namespace changes

Logger names such as `csml.*` are implementation-level observability identifiers during the compatibility window. They should not be mass-renamed until the implementation-owning package moves to `cstree`, because tests, caplog assertions, and user logging filters may depend on the current hierarchy.

Alternative considered: rename loggers early to match the public namespace. That creates a mixed state where `csml` implementation modules emit `cstree` logger names without actually moving implementation ownership.

## Risks / Trade-offs

- [Risk] The alias finder could mask missing explicit wrappers for documented `python -m cstree...` tools. -> Mitigation: keep an inventory of documented module execution paths and require subprocess `--help` tests for each public wrapper.
- [Risk] Leaving internal imports under `csml` can look like incomplete migration. -> Mitigation: document the distinction between public surface migration and implementation package ownership, and audit remaining references by category.
- [Risk] Removing compatibility too early would break scripts, shell history, CI jobs, and local automation. -> Mitigation: require a pre-breaking checklist with docs, tests, release notes, and explicit approval before removal.
- [Risk] A final package move can invalidate monkeypatch targets, coverage settings, logger filters, and generated commands. -> Mitigation: perform that move as its own breaking phase with focused tests for import paths, CLI scripts, logging expectations, and packaging metadata.
- [Risk] Long compatibility windows increase maintenance burden. -> Mitigation: keep compatibility wrappers small, tested, and centralized; do not duplicate implementation.

## Migration Plan

### Phase 1: Cstree-first public surface

Keep `csml` compatibility. Migrate new or remaining public docs, command examples, generated shell commands, and public behavior tests to prefer `cstree`. Add or update tests that `cstree` CLI help, `python -m cstree`, documented release/research module tools, and `CSTREE_*` environment variables work.

Rollback: revert individual docs/tests/wrapper changes. The `csml` implementation and compatibility surface remain unchanged.

### Phase 2: Compatibility-window hardening

Maintain a categorized audit of remaining `csml` references: compatibility contract, internal implementation, test monkeypatch/loggers, packaging metadata, and accidental public usage. Convert accidental public usage to `cstree`; keep intentional compatibility references. Expand wrapper inventory tests for documented public modules.

Rollback: keep existing `csml` paths and remove only the newly added cstree-first checks if they expose a false assumption.

### Phase 3: Pre-breaking readiness

Before removing `csml`, prepare a breaking-change plan with target version, migration guide, release notes, docs changes, packaging updates, test updates, and an external script impact audit. Decide whether to add explicit deprecation warnings or remain warning-free until the breaking release.

Rollback: continue the compatibility window and defer the breaking phase.

### Phase 4: Final breaking migration

Move implementation ownership to `src/cstree/` or make `cstree` otherwise authoritative. Remove the legacy `csml` console script, public `python -m csml...` paths, public `import csml`, and `CSML_*` environment variable fallbacks. Update tests, docs, coverage settings, logger strategy, and release notes to the final `cstree`-only state.

Rollback: only feasible before release by restoring the compatibility package and console script. After release, rollback requires a patch release that restores compatibility or clearly documents the regression.

## Open Questions

- What version should be the first allowed breaking release for removing `csml`?
- Should the final breaking release include a short-lived `csml` package that raises targeted import errors with migration guidance, or should the package disappear entirely?
- Should logger names move from `csml.*` to `cstree.*` in the final package move, and is a transitional logging alias needed?
- Should `CSML_*` environment variables emit warnings in a pre-breaking release, or remain silent until removal?
