## ADDED Requirements

### Requirement: Feature family ablation
The system SHALL support feature family ablation reports for a fixed HK research unit.

#### Scenario: Family ablation is configured
- **WHEN** a feature ablation spec defines one or more feature families to remove from a baseline config
- **THEN** the system SHALL generate comparable run configs or jobs for the baseline and each family removal

#### Scenario: Ablation results are summarized
- **WHEN** family ablation runs complete
- **THEN** the summary SHALL compare predictive metrics, backtest metrics, turnover, cost drag, degeneracy flags, and feature importance availability by family

### Requirement: Permutation active-return importance
The system SHALL support optional permutation importance measured against realized strategy or active-return outcomes.

#### Scenario: Permutation active-return importance is requested
- **WHEN** scored data and realized returns are available for a run
- **THEN** the system SHALL compute feature or family importance by measuring the change in configured net strategy or active-return metric after permutation

#### Scenario: Required data is unavailable
- **WHEN** permutation active-return importance is requested but scored data, feature values, or realized returns are unavailable
- **THEN** the system SHALL fail with a clear message listing the missing inputs

### Requirement: Stability-aware feature reporting
The system SHALL combine feature importance evidence with walk-forward stability evidence when available.

#### Scenario: Walk-forward stability exists
- **WHEN** `walk_forward_feature_stability.csv` is available for a run
- **THEN** feature reporting SHALL include top-k hit rate and nonzero hit rate alongside model importance or ablation metrics

#### Scenario: Walk-forward stability is unavailable
- **WHEN** no walk-forward stability artifact is available
- **THEN** feature reporting SHALL mark stability evidence as unavailable rather than inferring stability from a single run
