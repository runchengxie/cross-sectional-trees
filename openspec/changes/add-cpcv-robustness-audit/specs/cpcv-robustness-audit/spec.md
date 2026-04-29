## ADDED Requirements

### Requirement: CPCV Audit CLI
The system SHALL provide a standalone `cstree cpcv` command that runs a CPCV robustness audit from an existing pipeline config without running CPCV inside the default `cstree run` path.

#### Scenario: Run monthly CPCV audit
- **WHEN** a user runs `cstree cpcv --config configs/experiments/baseline/hk_selected.yml --n-groups 8 --test-groups 2 --out artifacts/reports/cpcv_hk_selected`
- **THEN** the system creates a CPCV report directory containing `cpcv_splits.csv`, `cpcv_path_returns.csv`, `cpcv_path_metrics.csv`, and `cpcv_summary.json`

#### Scenario: Reject invalid CPCV shape
- **WHEN** a user runs `cstree cpcv` with `test_groups >= n_groups`
- **THEN** the command exits with a clear validation error and writes no partial CPCV report

### Requirement: CPCV Split Construction
The system SHALL split eligible rebalance dates into deterministic chronological groups, evaluate every combination of `test_groups` test groups, and report the expected split and path counts.

#### Scenario: Monthly default split count
- **WHEN** CPCV is configured with `n_groups=8` and `test_groups=2`
- **THEN** `cpcv_splits.csv` contains 28 split rows and `cpcv_summary.json` records `path_count=7`

#### Scenario: Final OOS is reserved by default
- **WHEN** the pipeline config enables `eval.final_oos` and the user does not request final-OOS inclusion
- **THEN** CPCV split construction excludes the configured final OOS dates and records that exclusion in `cpcv_summary.json`

### Requirement: Event-Window Purging
The system SHALL purge training dates whose label event windows overlap any test label event window and SHALL record the purge mode and purge counts for every split.

#### Scenario: Fixed-horizon overlap is purged
- **WHEN** a fixed-horizon label config produces overlapping train and test label intervals
- **THEN** the overlapping train dates are removed from that split before model fitting and the removed count is written to `cpcv_splits.csv`

#### Scenario: Next-rebalance overlap is purged
- **WHEN** `label.horizon_mode=next_rebalance` is used
- **THEN** CPCV derives label end dates from the next rebalance mapping and purges train dates whose derived intervals overlap the test intervals

#### Scenario: Purge fallback is explicit
- **WHEN** event-window metadata cannot be derived for a supported config
- **THEN** the report records `purge_mode=fallback_gap` and the command logs that simple gap purging was used

### Requirement: CPCV Model Evaluation
The system SHALL fit the configured model on each purged training split, score the split test dates, and compute split/path metrics using the existing evaluation, backtest, cost, turnover, and benchmark conventions.

#### Scenario: Split produces metrics
- **WHEN** a split has enough surviving training and test data
- **THEN** the system records successful split status and contributes its scored test dates to CPCV path metrics

#### Scenario: Split has insufficient data
- **WHEN** purging leaves no valid training data or no valid test data for a split
- **THEN** the system records the split as `insufficient_data` and excludes it from successful path aggregation

### Requirement: CPCV Report Schema
The system SHALL write stable CPCV artifacts with enough metadata to reproduce the audit and review path-level robustness distributions.

#### Scenario: Summary contains distribution metrics
- **WHEN** a CPCV audit completes with at least one valid path
- **THEN** `cpcv_summary.json` includes `split_count`, `valid_split_count`, `path_count`, `valid_path_count`, `sharpe_mean`, `sharpe_median`, `sharpe_p25`, `sharpe_p10`, `sharpe_min`, `positive_sharpe_ratio`, `ic_median`, `long_short_median`, `max_drawdown_p10`, `turnover_median`, and `cost_drag_median`

#### Scenario: Path metrics are tabular
- **WHEN** CPCV path metrics are written
- **THEN** `cpcv_path_metrics.csv` contains one row per valid path with path id, date range, observation count, Sharpe, drawdown, IC, long-short, turnover, cost drag, and benchmark-active metrics when benchmark data is available

### Requirement: Promotion Gate CPCV Evidence
The system SHALL allow `promotion-gate` to require and threshold CPCV evidence from a candidate CPCV summary report.

#### Scenario: Missing required CPCV evidence rejects candidate
- **WHEN** `promotion_gate.required_evidence` includes `cpcv` and no candidate CPCV report is available
- **THEN** the promotion record includes `cpcv` in `missing_evidence` and the candidate is rejected

#### Scenario: CPCV thresholds affect promotion status
- **WHEN** candidate CPCV evidence is available but fails configured thresholds such as minimum path count, median Sharpe, Sharpe p25, positive Sharpe ratio, median IC, or worst-path drawdown
- **THEN** the promotion record includes the corresponding CPCV hard or soft failures and does not mark the candidate as promotable

### Requirement: CPCV Documentation
The system SHALL document CPCV as a research sidecar for shortlisted candidates and SHALL explain that CPCV complements, but does not replace, walk-forward and final OOS evidence.

#### Scenario: User finds CPCV workflow
- **WHEN** a user reads the CLI, outputs, metrics, capabilities, or HK selected playbook documentation
- **THEN** the documentation describes how to run CPCV, what files it writes, how to interpret the distribution metrics, and when to use monthly versus quarterly defaults
