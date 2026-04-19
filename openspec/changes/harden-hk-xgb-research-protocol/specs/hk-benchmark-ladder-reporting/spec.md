## ADDED Requirements

### Requirement: Benchmark ladder report
The system SHALL support HK benchmark ladder reporting without changing the primary training label or primary benchmark contract.

#### Scenario: Multiple benchmarks are configured
- **WHEN** a run config includes a primary benchmark and report-level benchmark comparisons
- **THEN** the benchmark ladder report SHALL preserve the primary benchmark metrics and SHALL add comparison rows for every configured report-level benchmark

#### Scenario: Benchmark comparison is unavailable
- **WHEN** a configured benchmark comparison file is missing or incompatible with run periods
- **THEN** the benchmark ladder report SHALL mark that comparison unavailable and include the reason

### Requirement: Universe-aligned benchmark support
The system SHALL support universe-aligned cap-weight and equal-weight benchmark files as first-class benchmark comparison inputs.

#### Scenario: Universe-aligned benchmarks are provided
- **WHEN** cap-weight and equal-weight benchmark return files are configured for the same research universe
- **THEN** benchmark comparison output SHALL include both benchmarks and allow active performance to be compared against each

### Requirement: Benchmark attribution link
The system SHALL allow benchmark attribution artifacts to be referenced from benchmark ladder outputs.

#### Scenario: Attribution artifact exists
- **WHEN** benchmark attribution output exists for a comparison benchmark
- **THEN** the benchmark ladder report SHALL include a path or metadata reference to the attribution artifact

#### Scenario: Attribution artifact is absent
- **WHEN** no attribution artifact is configured
- **THEN** the benchmark ladder report SHALL remain valid and SHALL mark attribution as unavailable
