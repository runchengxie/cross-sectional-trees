## Why

The repository has accumulated maintenance debt after repeated HK/RQData, liveops, and release-flow changes: compatibility shims remain in the main path, command registration glue is thick, and several orchestration modules are large enough to make routine changes hard to review. Static inspection of the current tree shows this is primarily structure aging and boundary growth, not evidence for a broad feature purge.

## What Changes

- Establish a maintenance-debt reduction track that audits candidates before removal, with explicit usage checks, documentation checks, and regression tests for each phase.
- Retire or isolate legacy compatibility surfaces where safe, including `src/cstree/pipeline/data.py`, `src/cstree/compat.py`, legacy `universe` config handling, and legacy symbol aliases such as `ts_code` and `stock_ticker`.
- Split oversized orchestration modules along existing boundaries, starting with `src/cstree/release_tools/hk_asset_workflow.py`, `src/cstree/data_tools/rqdata_assets/asset_health.py`, `src/cstree/data_tools/rqdata_assets/coverage.py`, `src/cstree/data_tools/rqdata_assets/build.py`, and `src/cstree/pipeline/eval.py`.
- Flatten RQData asset command registration by moving defaults, argument builders, runner binding, and help text closer to `RQDataAssetCommandSpec`, reducing thin wrapper layers across `args.py`, `args_mirror.py`, `command_registry.py`, `public_api.py`, and package `__init__.py`.
- Refactor the liveops CLI registration path so `register_liveops_commands` no longer owns a long hand-written argparse block for every option.
- Review maintainer-only scripts under `scripts/internal/` and either document their retained purpose or remove/relocate entries that are no longer used.
- Tighten lint/style gates incrementally instead of enabling a disruptive broad ruleset at once; start with line-length enforcement for touched files, import hygiene, and progressively shrinking `C901` ignores.
- Update user and maintainer docs when public CLI, config compatibility, symbol handling, script locations, or artifact contracts change.

## Capabilities

### New Capabilities

- `maintenance-debt-governance`: Defines how this repository audits, prioritizes, refactors, and verifies legacy compatibility code, large modules, command glue, maintainer scripts, and static quality gates without changing public behavior accidentally.

### Modified Capabilities

- None.

## Impact

- Affected code: `src/cstree/pipeline/`, `src/cstree/data_tools/rqdata_assets/`, `src/cstree/release_tools/`, `src/cstree/cli/liveops.py`, `src/cstree/config_utils.py`, `src/cstree/data_tools/symbols.py`, and selected `scripts/internal/` entries.
- Affected docs: `README.md`, `docs/README.md`, `docs/cli.md`, `docs/config.md`, `docs/outputs.md`, `docs/providers.md`, `docs/dev.md`, `docs/troubleshooting.md`, and `scripts/README.md` as needed by each phase.
- Public behavior should remain compatible during refactor phases unless a compatibility surface is explicitly marked for deprecation/removal and covered by migration notes.
- Regression coverage should focus on CLI command parsing, config compatibility, symbol normalization, RQData asset tooling, pipeline evaluation, and release workflow helpers.
