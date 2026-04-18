## ADDED Requirements

### Requirement: Unified asset inventory report
The system SHALL generate a machine-readable inventory report for local market data assets by inspecting current contracts, alias paths, manifests, and snapshot directories under the configured artifacts root.

#### Scenario: Inventorying current assets
- **WHEN** an operator runs the audit without restricting asset classes
- **THEN** the system SHALL emit one inventory record for each discovered current asset and each explicitly scanned snapshot family
- **THEN** each inventory record SHALL include asset key or family, resolved path, path kind, existence, manifest status, and the best available freshness fields such as `as_of`, `query_end_date`, or latest observed trade date

#### Scenario: Recording missing metadata
- **WHEN** an asset exists on disk but its manifest or alias metadata is missing or inconsistent
- **THEN** the inventory report SHALL preserve the asset record
- **THEN** the inventory report SHALL classify the metadata issue with an explicit reason code instead of dropping the asset from the summary

### Requirement: Inventory SHALL expose provenance and reference context
The system SHALL annotate each inventoried asset with the references that keep it relevant, including current aliases, current contracts, release/package outputs, and workflow reports when available.

#### Scenario: Asset referenced by current alias
- **WHEN** a snapshot is the resolved target of a current alias or current contract entry
- **THEN** the inventory report SHALL mark the snapshot as referenced by current state
- **THEN** the report SHALL expose the alias path and resolved path relationship needed for later prune decisions

#### Scenario: Asset not referenced by any known pointer
- **WHEN** a scanned snapshot is not referenced by current aliases, current contracts, release outputs, or retained workflow reports
- **THEN** the inventory report SHALL mark the snapshot as unreferenced
- **THEN** the report SHALL keep enough provenance fields for a later cleanup planner to justify whether the snapshot is safe to prune
