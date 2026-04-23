## 1. Namespace Audit Baseline

- [x] 1.1 Run a repository-wide `csml` / `cstree` / `CSML_*` / `CSTREE_*` audit and save a categorized summary in the change notes or follow-up implementation issue.
- [x] 1.2 Classify remaining `csml` references as compatibility contract, internal implementation, test monkeypatch or logger target, packaging metadata, documentation of legacy behavior, or accidental public usage.
- [x] 1.3 Identify public-facing accidental `csml` usage that can move to `cstree` without changing compatibility behavior.
- [x] 1.4 Confirm the documented public module inventory for `cstree.release_tools.*` and `cstree.research.*` paths.

## 2. Cstree-First Public Surface

- [x] 2.1 Update new or remaining public documentation examples to use `cstree` commands except where legacy compatibility is explicitly discussed.
- [x] 2.2 Update generated user-facing shell commands and script messages to prefer `cstree` or `python -m cstree...`.
- [x] 2.3 Migrate public behavior tests that are not specifically testing compatibility to import or execute `cstree` paths.
- [x] 2.4 Keep docs that describe the compatibility window explicit about `csml` being legacy compatibility, not the preferred user entry point.

## 3. Wrapper And Module Execution Hardening

- [x] 3.1 Add or verify explicit wrappers for every documented `python -m cstree.release_tools.*` module.
- [x] 3.2 Add or verify explicit wrappers for every documented `python -m cstree.research.*` module.
- [x] 3.3 Extend namespace tests so each documented `cstree` module execution path succeeds with `--help`.
- [x] 3.4 Extend import tests so public `cstree.<module>` surfaces resolve without callers importing `csml` directly.
- [x] 3.5 Keep implementation-sharing centralized through wrappers or aliasing rather than copying implementation files.

## 4. Compatibility Window Protection

- [x] 4.1 Keep the `csml` console script registered and covered by at least one compatibility test while the compatibility window is active.
- [x] 4.2 Keep targeted tests for documented legacy `python -m csml...` module paths while the compatibility window is active.
- [x] 4.3 Keep targeted tests for public `import csml` compatibility while the compatibility window is active.
- [x] 4.4 Keep `CSML_*` environment variable fallback tests while the compatibility window is active.
- [x] 4.5 Verify `CSTREE_*` environment variables take precedence when both preferred and legacy variables are set.

## 5. Pre-Breaking Readiness Gate

- [x] 5.1 Choose and document the first version that may remove the `csml` compatibility surface.
- [x] 5.2 Draft migration notes that map `csml` CLI commands, `python -m csml...` paths, imports, and `CSML_*` variables to their `cstree` replacements.
- [x] 5.3 Draft release notes that mark the final removal as breaking.
- [x] 5.4 Audit repository scripts, CI, docs, examples, and likely user automation for remaining legacy entry point usage before removal.
- [x] 5.5 Decide whether a pre-breaking release should emit deprecation warnings for `csml` usage or remain warning-free until removal.
- [x] 5.6 Define rollback criteria for restoring compatibility if the breaking release exposes unacceptable user impact.

## 6. Final Breaking Migration

- [ ] 6.1 Move implementation ownership to `src/cstree/` or otherwise make `cstree` the authoritative implementation package.
- [ ] 6.2 Update internal imports, monkeypatch targets, package discovery assumptions, and coverage settings to match the final package ownership decision.
- [ ] 6.3 Remove the legacy `csml` console script from packaging metadata.
- [ ] 6.4 Remove public `python -m csml...` compatibility paths or replace them with the explicitly approved final legacy behavior.
- [ ] 6.5 Remove public `import csml` compatibility or replace it with the explicitly approved final legacy behavior.
- [ ] 6.6 Remove `CSML_*` environment variable fallbacks and update configuration docs accordingly.
- [ ] 6.7 Decide and implement the final logger namespace strategy, including any test updates for `caplog` or logging filters.

## 7. Validation

- [x] 7.1 Run `scripts/dev/run_tests.sh fast` after each non-breaking implementation slice.
- [x] 7.2 Run docs contract and namespace-focused tests after documentation, wrapper, or module execution changes.
- [x] 7.3 Run packaging or console-script checks after modifying `pyproject.toml` entry points.
- [ ] 7.4 Before the final breaking release, run the full selected regression suite and verify docs, release notes, and migration notes match the implemented behavior.
