## 1. Protocol Foundations

- [x] 1.1 Define default HK promotion gate config fields for baseline run, candidate run, comparability keys, hard rejection flags, and soft thresholds.
- [x] 1.2 Add tests for loading and validating the promotion gate config.
- [x] 1.3 Document the promotion status values `promotable`, `reviewable`, `rejected`, and `non-comparable`.

## 2. Promotion Gate Reporting

- [x] 2.1 Implement a report builder that reads baseline and candidate `summary.json`, `config.used.yml`, and available walk-forward/final OOS artifacts.
- [x] 2.2 Implement comparability checks for universe, label, features, model lane, benchmark, rebalance frequency, and cost model fields.
- [x] 2.3 Implement hard rejection checks for constant prediction, zero feature importance, insufficient CV folds, and missing required final OOS evidence.
- [x] 2.4 Implement soft threshold checks for predictive quality, walk-forward stability, final OOS, drawdown, turnover, and cost drag.
- [x] 2.5 Add CLI or research-module entry point to write promotion reports as CSV and JSON.
- [x] 2.6 Add unit tests for complete, missing-evidence, non-comparable, rejected, reviewable, and promotable cases.

## 3. Cost-Aware Objective Normalization

- [x] 3.1 Audit `csml tune`, `csml run-grid`, and `summarize-runs` outputs for consistent objective component names.
- [x] 3.2 Add missing objective component columns for cost drag, turnover, drawdown, walk-forward test IC, and degeneracy flags where needed.
- [x] 3.3 Add high cost drag threshold flag alongside the existing high turnover and degeneracy flags.
- [x] 3.4 Update tests for objective score computation, missing component handling, high cost drag flags, and degenerate score exclusion.

## 4. Fixed-Score Portfolio Construction Comparison

- [x] 4.1 Define construction-grid config schema for top-k, buffer, weighting, score postprocess, exposure controls, benchmark settings, and cost assumptions.
- [x] 4.2 Implement scored-artifact validation for required columns and actionable missing-input errors.
- [x] 4.3 Implement fixed-score construction comparison that evaluates multiple variants without retraining.
- [x] 4.4 Include net return, gross return, Sharpe, drawdown, turnover, cost drag, active return, benchmark comparison, exposure availability, and period count in each variant row.
- [x] 4.5 Add tests for successful multi-variant grids, missing scored artifacts, invalid constraints, and insufficient names.

## 5. Profit-Aware Feature Evidence

- [x] 5.1 Define feature-family ablation config format and family naming conventions for HK selected research.
- [x] 5.2 Implement generation of baseline and `minus_<family>` run configs or jobs from a fixed research unit.
- [x] 5.3 Implement ablation summary output comparing predictive metrics, backtest metrics, turnover, cost drag, degeneracy flags, and feature importance availability.
- [x] 5.4 Implement optional permutation active-return importance from scored data, feature values, and realized returns.
- [x] 5.5 Add stability-aware feature report fields from `walk_forward_feature_stability.csv` when available.
- [x] 5.6 Add tests for family ablation job generation, ablation summaries, missing permutation inputs, and stability artifact handling.

## 6. HK Benchmark Ladder Reporting

- [x] 6.1 Normalize benchmark comparison output so primary benchmark metrics remain separate from report-level benchmark comparisons.
- [x] 6.2 Support universe-aligned cap-weight and equal-weight benchmark return files in benchmark ladder summaries.
- [x] 6.3 Add optional attribution artifact references to benchmark ladder output.
- [x] 6.4 Add tests for multiple benchmark comparisons, missing benchmark files, incompatible periods, and absent attribution artifacts.

## 7. Documentation And Validation

- [x] 7.1 Update `docs/concepts/benchmark-protocol.md` with the promotion gate and benchmark ladder workflow.
- [x] 7.2 Update `docs/metrics.md` with new promotion, cost-aware objective, construction comparison, and feature evidence fields.
- [x] 7.3 Update HK playbooks to describe the path from experiment to challenger to promoted baseline.
- [x] 7.4 Add or update example configs under `configs/experiments/sweeps/` for promotion gate and construction-grid workflows.
- [x] 7.5 Run targeted tests for tune/grid summaries, backtest metrics, promotion reporting, feature evidence, and benchmark reporting.
