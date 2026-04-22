## 1. Migration Policy And Inventory

- [ ] 1.1 Inventory every documented `python -m csml...` entry point in README, docs, and scripts documentation.
- [ ] 1.2 Decide and document the `csml` compatibility window and warning policy for this change.
- [ ] 1.3 Identify which `csml` surfaces are public, playbook-only, internal, or test-only.

## 2. cstree Namespace Bridge

- [ ] 2.1 Add a minimal `src/cstree/` package that delegates CLI behavior to `csml.cli`.
- [ ] 2.2 Add `cstree.release_tools.*` wrappers for documented release helper modules.
- [ ] 2.3 Add `cstree.research.*` wrappers for documented runnable research modules.
- [ ] 2.4 Ensure `python -m cstree...` wrappers call the same `main` implementations as the existing `csml` modules.
- [ ] 2.5 Keep existing `src/csml/` imports and `python -m csml...` paths working unchanged.

## 3. Environment Variable Aliases

- [ ] 3.1 Add `CSTREE_ARTIFACTS_ROOT`, `CSTREE_METADATA_DB_PATH`, and `CSTREE_WAREHOUSE_DB_PATH` as preferred aliases.
- [ ] 3.2 Preserve `CSML_ARTIFACTS_ROOT`, `CSML_METADATA_DB_PATH`, and `CSML_WAREHOUSE_DB_PATH` as fallbacks.
- [ ] 3.3 Add conflict tests proving `CSTREE_*` wins when both new and legacy names are set.
- [ ] 3.4 Update command help text and docs that describe artifact root or warehouse path precedence.

## 4. Documentation And Contract Tests

- [ ] 4.1 Update public docs so new examples prefer `cstree` CLI and `python -m cstree...` module paths where wrappers exist.
- [ ] 4.2 Keep compatibility notes for existing `csml` CLI, module paths, imports, and `CSML_*` variables.
- [ ] 4.3 Update docs contract tests to require the new `cstree` module paths and legacy compatibility notes.
- [ ] 4.4 Add CLI entry point tests proving `cstree` and `csml` remain equivalent during the compatibility window.
- [ ] 4.5 Add module execution smoke tests for each documented `cstree` wrapper.

## 5. Verification

- [ ] 5.1 Run targeted tests for CLI entry points, docs contracts, artifact path resolution, and wrapper modules.
- [ ] 5.2 Run `scripts/dev/run_tests.sh fast` after implementation.
- [ ] 5.3 Record any intentionally deferred `csml` removal work in a follow-up breaking-change proposal or task note.
