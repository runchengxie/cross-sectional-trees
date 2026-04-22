## 1. Migration Policy And Inventory

- [x] 1.1 Inventory every documented `python -m csml...` entry point in README, docs, and scripts documentation.
- [x] 1.2 Decide and document the `csml` compatibility window and warning policy for this change.
- [x] 1.3 Identify which `csml` surfaces are public, playbook-only, internal, or test-only.

## 2. cstree Namespace Bridge

- [x] 2.1 Add a minimal `src/cstree/` package that delegates CLI behavior to `csml.cli`.
- [x] 2.2 Add `cstree.release_tools.*` wrappers for documented release helper modules.
- [x] 2.3 Add `cstree.research.*` wrappers for documented runnable research modules.
- [x] 2.4 Ensure `python -m cstree...` wrappers call the same `main` implementations as the existing `csml` modules.
- [x] 2.5 Keep existing `src/csml/` imports and `python -m csml...` paths working unchanged.

## 3. Environment Variable Aliases

- [x] 3.1 Add `CSTREE_ARTIFACTS_ROOT`, `CSTREE_METADATA_DB_PATH`, and `CSTREE_WAREHOUSE_DB_PATH` as preferred aliases.
- [x] 3.2 Preserve `CSML_ARTIFACTS_ROOT`, `CSML_METADATA_DB_PATH`, and `CSML_WAREHOUSE_DB_PATH` as fallbacks.
- [x] 3.3 Add conflict tests proving `CSTREE_*` wins when both new and legacy names are set.
- [x] 3.4 Update command help text and docs that describe artifact root or warehouse path precedence.

## 4. Documentation And Contract Tests

- [x] 4.1 Update public docs so new examples prefer `cstree` CLI and `python -m cstree...` module paths where wrappers exist.
- [x] 4.2 Keep compatibility notes for existing `csml` CLI, module paths, imports, and `CSML_*` variables.
- [x] 4.3 Update docs contract tests to require the new `cstree` module paths and legacy compatibility notes.
- [x] 4.4 Add CLI entry point tests proving `cstree` and `csml` remain equivalent during the compatibility window.
- [x] 4.5 Add module execution smoke tests for each documented `cstree` wrapper.

## 5. Verification

- [x] 5.1 Run targeted tests for CLI entry points, docs contracts, artifact path resolution, and wrapper modules.
- [x] 5.2 Run `scripts/dev/run_tests.sh fast` after implementation.
- [x] 5.3 Record any intentionally deferred `csml` removal work in a follow-up breaking-change proposal or task note.

## Deferred Removal Note

`csml` removal is intentionally deferred. The current implementation keeps `csml`
CLI, import, module execution, and `CSML_*` environment variable compatibility
through the `0.x` compatibility window and does not emit deprecation warnings by
default. Removing any of those surfaces requires a separate breaking-change
proposal that names the removal version, migration path, tests, and release note
requirements.
