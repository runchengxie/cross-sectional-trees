## ADDED Requirements

### Requirement: Promotion gate evidence
The system SHALL provide a HK research promotion gate that evaluates a candidate run against an explicit baseline run or baseline profile using comparable evidence.

#### Scenario: Candidate has complete promotion evidence
- **WHEN** a candidate run has main evaluation metrics, backtest metrics, walk-forward metrics, final OOS metrics, cost and turnover metrics, degeneracy flags, feature stability data, and benchmark comparison data
- **THEN** the promotion gate SHALL produce a review record containing all required evidence and the candidate's promotion status

#### Scenario: Candidate is missing required evidence
- **WHEN** a candidate run lacks any required evidence category for the configured gate
- **THEN** the promotion gate SHALL mark the candidate as not promotable and list the missing evidence categories

### Requirement: Baseline comparability check
The system SHALL check that candidate and baseline runs are comparable before reporting a promotion decision.

#### Scenario: Research unit differs
- **WHEN** candidate and baseline runs differ in configured non-model research inputs such as universe, label, feature set, benchmark, rebalance frequency, or cost model
- **THEN** the promotion gate SHALL mark the comparison as non-comparable and SHALL NOT mark the candidate as promotable

#### Scenario: Research unit matches
- **WHEN** candidate and baseline runs match the configured comparability keys
- **THEN** the promotion gate SHALL include the comparison in the promotion decision

### Requirement: Promotion status
The system SHALL assign a promotion status using configured thresholds and hard rejection flags.

#### Scenario: Candidate fails a hard rejection flag
- **WHEN** a candidate has constant predictions, zero feature importance, insufficient valid CV folds, or missing final OOS evidence required by the gate
- **THEN** the promotion gate SHALL mark the candidate as rejected

#### Scenario: Candidate passes configured thresholds
- **WHEN** a candidate passes all hard rejection checks and meets configured thresholds for predictive quality, walk-forward stability, final OOS, cost drag, turnover, and drawdown
- **THEN** the promotion gate SHALL mark the candidate as promotable

#### Scenario: Candidate is mixed
- **WHEN** a candidate passes hard rejection checks but fails one or more soft thresholds
- **THEN** the promotion gate SHALL mark the candidate as reviewable and list the failed thresholds
