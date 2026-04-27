## Why

The project has grown from a research tool into a larger HK data, pipeline, liveops, and release system, and the current codebase now carries visible maintenance debt in large orchestration functions, broad compatibility surfaces, and conservative static quality gates. This change establishes a staged, behavior-preserving plan to reduce that debt without breaking documented CLI, provider, asset, or research workflows.

## What Changes

- Add a maintainability governance capability for staged refactors, compatibility shims, public facade boundaries, and static quality ratchets.
- Refactor the largest orchestration surfaces in small, verified steps, starting with `pipeline/train_eval_stage.py`, `pipeline/runner.py`, `data_tools/rqdata_assets/asset_health.py`, and adjacent high-risk modules.
- Define an explicit policy for legacy shims such as `cstree.pipeline.data`, legacy `universe` config support, and symbol aliases like `ts_code` / `stock_ticker`.
- Narrow public API and package facade boundaries for RQData asset helpers while preserving stable documented entry points.
- Continue improving Ruff / PEP 8 conformance through ratchets that prevent new debt and gradually reduce historical violations.
- Keep scripts under `scripts/internal/` unless there is a verified replacement path, usage audit, documentation update, and test coverage.
- Update internal maintenance documentation and targeted tests alongside each implementation step.

## Capabilities

### New Capabilities

- `codebase-maintainability-governance`: Defines how the project tracks, prioritizes, and verifies staged codebase maintainability improvements without changing public behavior.

### Modified Capabilities

- None.

## Impact

- Affected source areas include `src/cstree/pipeline/`, `src/cstree/data_tools/rqdata_assets/`, `src/cstree/release_tools/`, selected compatibility shims, static quality tooling, and internal maintenance documentation.
- Public CLI behavior, documented config compatibility, provider behavior, artifact formats, and HK asset workflows must remain backward compatible unless a later change explicitly declares a breaking migration.
- Tests will focus on the touched module boundaries, including pipeline runtime, train/eval contracts, RQData asset health, release workflow helpers, config compatibility, symbol alias compatibility, and static quality ratchets.
