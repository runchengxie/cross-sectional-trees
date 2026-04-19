## Why

The HK XGB strategy already has walk-forward, final OOS, cost, benchmark, and diagnostics primitives, but research decisions still risk being made from isolated headline metrics. This change turns the strongest lessons from the US random-forest project into explicit HK research protocol requirements so future challenger runs are promoted only when they pass stability, cost, portfolio, feature, and benchmark checks.

## What Changes

- Add a formal promotion gate for HK XGB research runs that combines main evaluation, walk-forward, final OOS, turnover, cost drag, degeneracy flags, and feature stability.
- Make cost and turnover first-class research objective inputs for tuning, grid comparison, and run summaries instead of optional after-the-fact diagnostics.
- Define a portfolio construction comparison layer that can evaluate fixed model scores under multiple top-k, buffer, weighting, neutralization, exposure, and benchmark-relative construction choices.
- Add profit-aware feature selection and ablation requirements, including family-level ablation and permutation active-return importance.
- Standardize benchmark ladder reporting for HK research so ETF, universe-aligned cap-weight, equal-weight, and attribution views can be compared without changing the primary run contract.
- Keep random forest itself out of the first implementation phase; it remains a later model-family challenger after the protocol is stable.

## Capabilities

### New Capabilities
- `hk-research-promotion-gates`: Defines the required evidence a HK XGB candidate must satisfy before it can replace or challenge the current baseline.
- `cost-aware-research-objective`: Covers objective scoring and summaries that incorporate turnover and cost drag consistently.
- `portfolio-construction-comparison`: Covers fixed-score portfolio construction experiments and diagnostics.
- `profit-aware-feature-selection`: Covers feature family ablation, permutation active-return importance, and stability-aware feature reporting.
- `hk-benchmark-ladder-reporting`: Covers benchmark comparison and attribution reporting for HK strategy evaluation.

### Modified Capabilities

None. This repository does not yet have existing OpenSpec specs.

## Impact

- Affected code areas likely include `src/csml/commands/tune.py`, `src/csml/commands/run_grid.py`, `src/csml/research/summarize_runs.py`, `src/csml/pipeline/eval.py`, `src/csml/backtest.py`, `src/csml/transform.py`, and HK research modules under `src/csml/research/`.
- Affected configs likely include HK selected variants and sweeps under `configs/experiments/variants/` and `configs/experiments/sweeps/`.
- Affected documentation likely includes `docs/concepts/benchmark-protocol.md`, `docs/concepts/model-landscape.md`, `docs/metrics.md`, and HK research notes/playbooks.
- No external dependency is required for phase one. Any optimizer or random-forest model addition should be proposed separately after the protocol is accepted.
