## Why

The project has already moved user-facing guidance toward `cstree`, but the implementation, tests, and compatibility contract still intentionally keep `csml` alive. A staged migration plan is needed so near-term work can keep strengthening the `cstree` public surface without accidentally treating the final `csml` removal as a cosmetic cleanup.

## What Changes

- Establish `cstree` as the preferred public namespace for new documentation, examples, shell scripts, CLI help, public module examples, and public-facing tests.
- Preserve the existing `csml` CLI, `python -m csml...`, `import csml`, and `CSML_*` compatibility surface during the current compatibility window.
- Expand or tighten tests that prove `cstree` public entry points work while legacy `csml` entry points remain compatible.
- Define a pre-breaking deprecation phase that audits external-facing references, release notes, migration notes, packaging metadata, environment variables, and compatibility tests before any removals.
- **BREAKING** In the final migration phase, remove the legacy `csml` console script, `python -m csml...` module execution paths, public `import csml` compatibility, and `CSML_*` environment variable fallbacks after the breaking-change gate is explicitly approved.
- **BREAKING** In the final migration phase, move the primary implementation namespace from `src/csml/` to `src/cstree/` or otherwise make `cstree` the implementation-owning package, with any remaining `csml` behavior either removed or reduced to a consciously versioned legacy shim.

## Capabilities

### New Capabilities

- `cstree-namespace-migration`: Defines the staged public namespace migration from `csml` to `cstree`, including compatibility-window behavior, cstree-first public entry points, deprecation gates, and final breaking-removal criteria.

### Modified Capabilities

- None. No existing OpenSpec capabilities are present in this repository yet.

## Impact

- Public CLI and packaging metadata: `pyproject.toml` console scripts, `cstree` and `csml` executable behavior, and generated shell command examples.
- Public Python module paths: `cstree.*` wrappers, `python -m cstree...`, legacy `csml.*` imports, and any explicit module execution tests.
- Configuration and environment variables: `CSTREE_*` preferred names and `CSML_*` fallback behavior until the final breaking phase.
- Documentation and examples: `README.md`, `docs/`, `scripts/README.md`, release notes, and generated command references.
- Tests and developer workflow: namespace wrapper tests, CLI tests, docs contract tests, public behavior tests, compatibility tests, and coverage configuration.
- Internal implementation layout: eventual ownership transfer from `src/csml/` to `src/cstree/`, including imports, logger names, monkeypatch targets, and module discovery.
