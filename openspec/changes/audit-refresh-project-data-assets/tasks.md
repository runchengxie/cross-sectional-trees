## 1. Audit Entry And Inventory

- [x] 1.1 Add a unified audit entrypoint and report schema that can emit inventory, freshness, repair, and prune sections for one target date
- [x] 1.2 Implement metadata-first inventory collection from `hk_current.json`, alias paths, manifests, snapshot directories, and relevant report/release references
- [x] 1.3 Add reference/provenance classification so each inventoried snapshot is marked as current, retained, unreferenced, or metadata-inconsistent

## 2. Refresh Verification

- [x] 2.1 Implement ETF daily completeness verification from `2000-01-01` through the effective target date with explicit local-gap vs provider-boundary classification
- [x] 2.2 Implement stock intraday `5m` freshness verification using latest trade-date coverage and optional daily reconciliation details
- [x] 2.3 Add a refresh-aware mode that invokes the existing refresh workflow and records pre-refresh vs post-refresh verification outcomes

## 3. Health Aggregation And Repair

- [x] 3.1 Aggregate `current_health`, `asset_health`, `intraday_health`, PIT coverage, and workflow reports into one normalized severity summary
- [x] 3.2 Generate repair candidates classified as `repoint`, `patch-refresh`, `targeted-rebuild`, `manual-review`, or `provider-boundary`
- [x] 3.3 Execute only approved automatic repair actions and require post-repair verification before reporting resolution or repointing aliases

## 4. Prune Planning, Tests, And Docs

- [x] 4.1 Implement conservative prune-plan generation with reference checks, reason codes, and dry-run output for deletion candidates
- [x] 4.2 Add explicit delete-mode handling that removes only approved candidates and records deleted, skipped, and failed paths
- [x] 4.3 Add or update tests for inventory, ETF/intraday verification, repair classification, and prune gating, then update the relevant maintenance documentation and scripts
