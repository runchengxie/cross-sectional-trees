## Why

The project already presents `cstree` as the preferred public CLI name, but the
actual Python namespace, module-level tools, compatibility tests, environment
variables, and documented release helpers still depend on `csml`. A staged
migration plan is needed before any compatibility layer can be deprecated or
removed without breaking documented workflows.

## What Changes

- Define `cstree` as the target public namespace for future CLI, module-level,
  and documentation references.
- Add a `cstree` Python module namespace or bridge before changing documented
  `python -m csml...` entry points.
- Introduce a formal deprecation path for `csml` CLI and module aliases, with
  tests that enforce both the new path and the compatibility window.
- Add `CSTREE_*` environment variable names while preserving `CSML_*` fallbacks
  during the compatibility period.
- Update documentation in phases so new examples use `cstree`, while legacy
  `csml` behavior is described as compatibility rather than primary usage.
- Do not remove the existing `csml` CLI alias, Python imports, or `CSML_*`
  environment variables in the first implementation phase.

## Capabilities

### New Capabilities

- `project-identity-migration`: Defines how the project migrates public identity
  from `csml` to `cstree` across CLI entry points, Python module execution,
  environment variables, documentation, and compatibility policy.

### Modified Capabilities

- None. This repository does not yet have OpenSpec capability specs.

## Impact

- Packaging metadata: `pyproject.toml` console scripts and package discovery.
- Python source layout: `src/csml/` and any future `src/cstree/` bridge or
  namespace package.
- Public commands: `cstree`, `csml`, and documented `python -m ...` module
  tools.
- Configuration and runtime defaults: `CSML_ARTIFACTS_ROOT`,
  `CSML_METADATA_DB_PATH`, and `CSML_WAREHOUSE_DB_PATH` compatibility behavior.
- Tests that currently import `csml`, assert CLI compatibility, or check
  documentation contracts.
- User documentation under `README.md`, `docs/`, and `scripts/README.md`.
