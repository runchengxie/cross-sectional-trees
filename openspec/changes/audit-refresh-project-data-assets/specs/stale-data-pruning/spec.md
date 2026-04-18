## ADDED Requirements

### Requirement: Conservative prune planning
The system SHALL generate a prune plan that only marks data assets as deletion candidates after checking current aliases, current contracts, release outputs, retained reports, and replacement snapshots.

#### Scenario: Snapshot still referenced
- **WHEN** a snapshot is still referenced by a current alias, current contract, release package, or retained workflow/report artifact
- **THEN** the prune plan SHALL mark the snapshot as protected
- **THEN** the prune plan SHALL state which reference kept the snapshot from being considered deletable

#### Scenario: Snapshot is an obsolete intermediate artifact
- **WHEN** a patch directory, failed rebuild output, or superseded snapshot is no longer referenced and a newer healthy replacement exists
- **THEN** the prune plan SHALL mark the artifact as a deletion candidate
- **THEN** the prune plan SHALL include the replacement reference and the reason code that justified the candidate classification

### Requirement: Deletion SHALL be review-gated
The system SHALL support a dry-run mode that emits the full prune plan without deleting anything, and SHALL require an explicit destructive flag before removing any file or directory.

#### Scenario: Dry-run cleanup review
- **WHEN** the operator runs the cleanup flow without an explicit delete flag
- **THEN** the system SHALL emit the same candidate list, byte estimates, and reasons that would be used for deletion
- **THEN** the system SHALL perform no filesystem deletions

#### Scenario: Destructive cleanup requested
- **WHEN** the operator runs the cleanup flow with an explicit delete flag and a candidate has already been classified as deletable
- **THEN** the system SHALL delete only the approved candidate paths
- **THEN** the system SHALL record which candidates were deleted, skipped, or failed so the cleanup result remains auditable
