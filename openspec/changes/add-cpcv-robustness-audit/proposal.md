## Why

The project already uses walk-forward, final OOS, benchmark evidence, tune/sweep summaries, and promotion gates to govern HK cross-sectional model research, but candidate runs can still look strong because one historical path or one recent regime is favorable. CPCV is worth adding now as a final robustness audit layer for shortlisted monthly candidates, especially because the current monthly PIT line has enough rebalance dates for multiple out-of-sample paths while the final OOS window is useful but still short for long-term robustness claims.

## What Changes

- Add a standalone CPCV research sidecar command that reruns a configured model over combinatorial purged cross-validation splits and emits path-level robustness distributions.
- Generate deterministic CPCV split, path return, path metric, and summary artifacts under `artifacts/reports/<tag>/` by default.
- Support monthly-first defaults such as `n_groups=8`, `test_groups=2`, optional `embargo_days`, and event-window purging based on signal/label windows rather than only a simple calendar gap.
- Reuse existing config, data loading, model fitting, scoring, portfolio construction, cost, benchmark, and summary conventions instead of replacing `cstree run`, walk-forward, or final OOS.
- Add optional CPCV evidence ingestion to `promotion-gate` so candidate promotion can require CPCV path counts and distribution thresholds.
- Document CPCV as a sidecar for top candidates after tune/sweep and before promotion, not as a default stage for every trial.

## Capabilities

### New Capabilities
- `cpcv-robustness-audit`: Defines the CPCV research sidecar, its split semantics, output artifacts, summary metrics, and optional promotion-gate evidence integration.

### Modified Capabilities

None. There are no existing OpenSpec specs in this repository yet; promotion-gate integration is covered by the new CPCV capability.

## Impact

- Affected CLI/API surface: `cstree cpcv`, `src/cstree/cli/research.py`, a new CPCV research module, and optional `promotion_gate` config/evidence fields.
- Affected outputs/docs: `docs/cli.md`, `docs/config.md`, `docs/outputs.md`, `docs/capabilities.md`, `docs/metrics.md`, and the HK selected playbook.
- Affected tests: new CPCV split/report tests, CLI registration tests, promotion-gate CPCV evidence tests, and documentation contract/path tests.
- Dependencies should remain unchanged unless implementation discovers a clear need; the first version should rely on pandas/numpy/sklearn and existing project helpers.
