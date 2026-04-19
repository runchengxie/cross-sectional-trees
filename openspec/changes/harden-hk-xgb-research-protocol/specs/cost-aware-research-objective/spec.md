## ADDED Requirements

### Requirement: Cost-aware objective components
The system SHALL expose the components of research objective scoring, including predictive quality, walk-forward quality, backtest quality, drawdown penalty, cost drag penalty, and turnover penalty.

#### Scenario: Tune run computes objective score
- **WHEN** a tuning trial finishes with available evaluation and backtest summary metrics
- **THEN** the trial result SHALL include the objective score and each normalized component used to compute it

#### Scenario: Component metric is unavailable
- **WHEN** an objective component is unavailable for a trial
- **THEN** the system SHALL preserve the missing component as empty or null and SHALL apply the documented default behavior for scoring

### Requirement: Cost and turnover gating
The system SHALL support configured cost drag and turnover thresholds for HK research comparison outputs.

#### Scenario: Run exceeds turnover threshold
- **WHEN** a run's average turnover exceeds the configured threshold
- **THEN** summary and promotion outputs SHALL flag the run as high turnover

#### Scenario: Run exceeds cost drag threshold
- **WHEN** a run's average cost drag exceeds the configured threshold
- **THEN** summary and promotion outputs SHALL flag the run as high cost drag

### Requirement: Degenerate model exclusion
The system SHALL exclude degenerate runs from objective ranking when configured to drop degenerate results.

#### Scenario: Run has constant predictions
- **WHEN** objective ranking is configured to drop degenerate results and a run has constant predictions
- **THEN** the run SHALL have no objective score for ranking

#### Scenario: Run has zero feature importance
- **WHEN** objective ranking is configured to drop degenerate results and a run has zero feature importance
- **THEN** the run SHALL have no objective score for ranking
