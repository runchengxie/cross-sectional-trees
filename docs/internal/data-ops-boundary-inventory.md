# Data Operations Boundary Inventory

This inventory records `cross-sectional-trees` surfaces that are easy to confuse with
shared market-data operations. Shared data production, validation, current-contract,
registry, universe building, standardized warehouse, backup, and data-asset release
workflows belong in `market-data-platform`.

## Hard-cut rule

`cross-sectional-trees` must not keep compatibility wrappers for platform APIs or
commands. Research code that needs platform functionality imports
`market_data_platform.*` directly. Old `cstree.*` data-platform entry points should
fail fast by being absent, not silently forward to MDP.

The following wrapper or platform-asset tail paths must not exist:

- `src/cstree/_mdp_compat.py`
- `src/cstree/artifacts.py`
- `src/cstree/current_assets.py`
- `src/cstree/data_provider_contracts.py`
- `src/cstree/data_providers.py`
- `src/cstree/data_tools/backup_data.py`
- `src/cstree/data_tools/build_hk_connect_universe.py`
- `src/cstree/data_tools/build_hk_daily_asset_universe.py`
- `src/cstree/data_tools/data_warehouse.py`
- `src/cstree/data_tools/symbols.py`
- `src/cstree/intraday_paths.py`
- `src/cstree/pit_feature_stats.py`
- `src/cstree/repo_paths.py`
- `src/cstree/rqdata_runtime.py`
- `src/cstree/cli/data.py`
- `src/cstree/cli/universe.py`
- `src/cstree/research/hk_intraday_download.py`
- `artifacts/metadata/dataset_registry.csv`
- `configs/presets/universe/hk_all_assets.yml`
- `configs/presets/universe/hk_connect.yml`

## Research-owned inventory

| Path | Classification | Owner | Reason |
| --- | --- | --- | --- |
| `src/cstree/data_interface.py` | `research-consumer` | `cross-sectional-trees` | Research runtime reads platform assets or explicit provider-online inputs. |
| `src/cstree/dataset.py` | `research-consumer` | `cross-sectional-trees` | Research dataset construction consumes configured inputs. |
| `src/cstree/pipeline/data.py` | `research-consumer` | `cross-sectional-trees` | Pipeline data loading consumes configured provider or local inputs. |
| `src/cstree/pipeline/dataset_sampling.py` | `research-consumer` | `cross-sectional-trees` | Sampling logic operates on in-memory research datasets. |
| `src/cstree/pipeline/feature_dataset.py` | `research-consumer` | `cross-sectional-trees` | Feature dataset assembly consumes platform-prepared assets. |
| `src/cstree/pipeline/industry_enrichment.py` | `research-consumer` | `cross-sectional-trees` | Industry labels are read as research inputs. |
| `src/cstree/pipeline/output_summary_metadata.py` | `research-consumer` | `cross-sectional-trees` | Run provenance records consume current contracts without refreshing them. |
| `src/cstree/pipeline/output_artifacts.py` | `research-output` | `cross-sectional-trees` | Writes research run artifacts such as positions, summaries, and scored outputs. |
| `src/cstree/liveops/alloc_market_data.py` | `research-consumer` | `cross-sectional-trees` | Live allocation reads latest market prices and lot sizes for target export. |
| `src/cstree/liveops/alloc_hk_market_data.py` | `research-consumer` | `cross-sectional-trees` | HK live allocation reads provider data for execution preparation. |
| `src/cstree/release_tools/__init__.py` | `research-output` | `cross-sectional-trees` | Namespace package for research run packaging helpers. |
| `src/cstree/release_tools/package_runs.py` | `research-output` | `cross-sectional-trees` | Packages research runs, not reusable market data assets. |
| `src/cstree/release_tools/release_runs.py` | `research-output` | `cross-sectional-trees` | Uploads research run packages, not data asset releases. |
| `src/cstree/research/hk_connect_cap_weight_benchmark.py` | `research-consumer` | `cross-sectional-trees` | Builds benchmark evidence from prepared daily, valuation, and universe inputs. |
| `src/cstree/research/hk_financial_details.py` | `research-consumer` | `cross-sectional-trees` | Analyzes prepared financial-details probes and mapping rules. |
| `src/cstree/research/hk_industry_filtered_universe.py` | `research-consumer` | `cross-sectional-trees` | Builds research-specific filtered universe files from prepared inputs. |
| `src/cstree/research/hk_intraday_slippage_report.py` | `research-consumer` | `cross-sectional-trees` | Consumes prepared intraday assets to calibrate research slippage assumptions. |
| `src/cstree/research/hk_selected_provider_valuation_audit.py` | `research-consumer` | `cross-sectional-trees` | Audits provider-overlay research runs and cached valuation inputs. |
| `src/cstree/research/hk_selected_provider_valuation_merge.py` | `research-consumer` | `cross-sectional-trees` | Research experiment helper for provider valuation overlays; does not publish assets. |
| `scripts/internal/package_repo.sh` | `repo-maintenance` | `cross-sectional-trees` | Packages repository source, not market data. |
| `scripts/dev/data_ops_boundary.py` | `repo-maintenance` | `cross-sectional-trees` | Governance check for this inventory. |

## Check

Run the boundary check before adding or moving any market-data-related source:

```bash
python scripts/dev/data_ops_boundary.py --check
```

The check is also part of `scripts/dev/run_tests.sh lint`.
