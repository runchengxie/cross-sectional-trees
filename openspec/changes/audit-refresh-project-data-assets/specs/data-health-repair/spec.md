## ADDED Requirements

### Requirement: Unified health summary
The system SHALL aggregate the outputs of current-health, asset-health, intraday-health, PIT coverage, and workflow reports into a single severity-based summary for the requested target date.

#### Scenario: Aggregating multiple health reports
- **WHEN** the audit consumes more than one underlying report for the same target date
- **THEN** the unified summary SHALL preserve the source report paths and per-source issue counts
- **THEN** the unified summary SHALL compute a normalized overall severity and a merged issue list without discarding source-specific context

#### Scenario: Underlying report missing
- **WHEN** an expected report is missing and the audit must generate or skip it
- **THEN** the unified summary SHALL record whether the report was regenerated, skipped, or unavailable
- **THEN** the summary SHALL treat missing evidence as an explicit audit condition rather than silently assuming success

### Requirement: Repair candidates SHALL be classified by safe action
The system SHALL classify detected data issues into at least `repoint`, `patch-refresh`, `targeted-rebuild`, `manual-review`, or `provider-boundary`, and SHALL attach the evidence needed to justify each action.

#### Scenario: Repairable patch candidate
- **WHEN** a freshness or completeness issue can be resolved by reusing an existing snapshot or running a bounded patch refresh
- **THEN** the repair candidate SHALL be labeled with the corresponding safe action
- **THEN** the candidate SHALL include the asset name, target date, affected range, minimum severity, and the command or workflow phase required to attempt the repair

#### Scenario: Non-repairable provider boundary
- **WHEN** a reported gap is explained by a known provider limitation rather than local corruption
- **THEN** the repair candidate SHALL be labeled as `provider-boundary`
- **THEN** the summary SHALL exclude the gap from auto-repair execution while still surfacing it in the final verdict

### Requirement: Automatic repair SHALL require post-repair verification
The system SHALL re-run the relevant health checks after any automatic repair action before it may repoint aliases or report the issue as resolved.

#### Scenario: Automatic repair succeeds
- **WHEN** an automatic repair action completes without command failure
- **THEN** the system SHALL re-run the affected verification checks before marking the issue resolved
- **THEN** the report SHALL include both the original issue evidence and the post-repair verification result

#### Scenario: Automatic repair does not clear the issue
- **WHEN** the post-repair verification still reports the issue or reports a worse severity
- **THEN** the system SHALL leave the candidate unresolved
- **THEN** the report SHALL retain the failed action history and recommend the next manual path instead of silently repointing aliases
