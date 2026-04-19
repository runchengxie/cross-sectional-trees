## ADDED Requirements

### Requirement: Fixed-score construction comparison
The system SHALL support comparing portfolio construction variants from an existing scored artifact without retraining the model.

#### Scenario: Scored artifact is available
- **WHEN** a run provides a scored artifact with prediction scores, symbols, dates, prices, and returns needed for backtesting
- **THEN** the construction comparison SHALL evaluate configured construction variants from the same fixed scores

#### Scenario: Scored artifact is missing
- **WHEN** a construction comparison is requested but no scored artifact is available
- **THEN** the system SHALL fail with an actionable message explaining which artifact or config setting is required

### Requirement: Construction variant dimensions
The system SHALL allow construction variants to differ by top-k, buffer settings, weighting mode, signal postprocess, exposure controls, benchmark-relative settings, and cost assumptions.

#### Scenario: Multiple variants are configured
- **WHEN** a construction grid defines multiple top-k, buffer, weighting, postprocess, exposure, benchmark, or cost settings
- **THEN** the output SHALL contain one comparable result row per variant

### Requirement: Construction diagnostics
The system SHALL report construction diagnostics for each fixed-score variant.

#### Scenario: Variant finishes successfully
- **WHEN** a construction variant completes
- **THEN** the result SHALL include net return, gross return, Sharpe, drawdown, turnover, cost drag, active return, benchmark comparison, exposure summary availability, and period count

#### Scenario: Variant cannot form a portfolio
- **WHEN** a construction variant cannot form a portfolio because of insufficient names or invalid constraints
- **THEN** the result SHALL be marked failed and SHALL include the failure reason
