## ADDED Requirements

### Requirement: ETF daily completeness verification
The system SHALL verify whether the ETF daily asset designated by the active alias covers the requested universe from `2000-01-01` through the effective target date, and SHALL distinguish local defects from provider-imposed gaps.

#### Scenario: ETF daily asset is complete
- **WHEN** the ETF daily alias resolves to a snapshot whose effective coverage starts no later than `2000-01-01` and whose latest date reaches the effective target date
- **THEN** the verification result SHALL mark ETF daily freshness and completeness as passing
- **THEN** the result SHALL include the checked path, effective date range, symbol count, and target date that was verified

#### Scenario: ETF daily asset has unresolved gaps
- **WHEN** the ETF daily verification finds missing files, stale symbols, missing target-date rows, or date-range gaps that are not explained by provider boundaries
- **THEN** the result SHALL classify the issue as a local completeness failure
- **THEN** the result SHALL include sample symbols or files and the exact affected date range needed for refresh or repair

### Requirement: Intraday freshness verification
The system SHALL verify whether the active stock intraday `5m` asset is refreshed through the effective target trading date and SHALL report latest trade-date coverage before returning a freshness verdict.

#### Scenario: Intraday asset is refreshed to target date
- **WHEN** the active intraday asset contains symbol-day coverage reaching the effective target trading date
- **THEN** the result SHALL mark the intraday freshness check as passing
- **THEN** the result SHALL include the latest trade date seen in the asset and the resolved snapshot path used for the verdict

#### Scenario: Intraday asset is stale or partially missing on target date
- **WHEN** the intraday verification finds that the latest trade date is older than the effective target date or that target-date symbol-days are missing for the active asset scope
- **THEN** the result SHALL classify the asset as stale or incomplete
- **THEN** the result SHALL include the target date, latest observed date, affected symbol-day counts, and representative samples

### Requirement: Refresh-aware verification flow
The system SHALL support a mode that runs the repository's existing refresh workflow before issuing the final ETF and intraday verdicts, and SHALL record both pre-refresh and post-refresh outcomes.

#### Scenario: Refresh mode enabled
- **WHEN** the operator requests refresh-aware verification
- **THEN** the system SHALL invoke the existing approved refresh workflow for the requested asset classes before re-running the relevant checks
- **THEN** the final report SHALL record the refresh action taken, the refreshed snapshot paths, and whether the post-refresh verdict improved
