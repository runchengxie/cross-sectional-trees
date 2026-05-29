# Data Operations Boundary Inventory

This inventory records `cross-sectional-trees` surfaces that are easy to confuse with
shared market-data operations. Shared data production, validation, current-contract,
registry, and data-asset release workflows belong in `market-data-platform`.

## Classifications

| Classification | Meaning |
| --- | --- |
| `compat-wrapper` | Retained only to protect old callers; delegates to `market-data-platform`. |
| `research-consumer` | Reads configured platform/provider/local inputs for research workflows. |
| `research-output` | Packages or releases research run outputs, not reusable market data assets. |
| `repo-maintenance` | Maintains source code packaging or repository hygiene. |

## Inventory

| Path | Classification | Owner | Replacement / canonical entry | Reason |
| --- | --- | --- | --- | --- |
| `src/cstree/artifacts.py` | `compat-wrapper` | `market-data-platform` | `market_data_platform.artifacts` | Shared artifact path constants are platform-owned. |
| `src/cstree/current_assets.py` | `compat-wrapper` | `market-data-platform` | `market_data_platform.current_assets` | Current contract helpers are platform-owned. |
| `src/cstree/data_provider_contracts.py` | `compat-wrapper` | `market-data-platform` | `market_data_platform.data_provider_contracts` | Provider contract definitions are shared platform APIs. |
| `src/cstree/data_providers.py` | `compat-wrapper` | `market-data-platform` | `market_data_platform.data_providers` | Provider adapters and local asset readers are shared platform APIs. |
| `src/cstree/data_tools/backup_data.py` | `compat-wrapper` | `market-data-platform` | `marketdata backup-data` | Data snapshot implementation is platform-owned. |
| `src/cstree/data_tools/build_hk_connect_universe.py` | `compat-wrapper` | `market-data-platform` | `market_data_platform.hk_assets.build_hk_connect_universe` | HK universe asset builders are platform-owned. |
| `src/cstree/data_tools/build_hk_daily_asset_universe.py` | `compat-wrapper` | `market-data-platform` | `market_data_platform.hk_assets.build_hk_daily_asset_universe` | HK universe asset builders are platform-owned. |
| `src/cstree/data_tools/data_warehouse.py` | `compat-wrapper` | `market-data-platform` | `marketdata data ...` | Catalog, standardized materialization, and query helpers are platform-owned. |
| `src/cstree/data_tools/symbols.py` | `compat-wrapper` | `market-data-platform` | `market_data_platform.symbols` | Symbol normalization is shared platform API. |
| `src/cstree/intraday_paths.py` | `compat-wrapper` | `market-data-platform` | `market_data_platform.intraday_paths` | Intraday asset path helpers are shared platform API. |
| `src/cstree/pit_feature_stats.py` | `compat-wrapper` | `market-data-platform` | `market_data_platform.pit_feature_stats` | PIT feature coverage utilities are shared platform API. |
| `src/cstree/repo_paths.py` | `compat-wrapper` | `market-data-platform` | `market_data_platform.repo_paths` | Repository path helpers are shared platform API. |
| `src/cstree/rqdata_runtime.py` | `compat-wrapper` | `market-data-platform` | `market_data_platform.rqdata_runtime` | RQData runtime initialization is shared platform API. |
| `src/cstree/cli/data.py` | `compat-wrapper` | `market-data-platform` | `marketdata data ...` | CLI is retained as a compatibility alias for platform data helpers. |
| `src/cstree/cli/universe.py` | `compat-wrapper` | `market-data-platform` | `market_data_platform.hk_assets` universe builders | CLI is retained as a compatibility alias for HK universe asset builders. |
| `src/cstree/cli/research.py` | `compat-wrapper` | `market-data-platform` | `marketdata backup-data` | Only the `backup-data` subcommand delegates to platform snapshot implementation. |
| `src/cstree/research/hk_intraday_download.py` | `compat-wrapper` | `market-data-platform` | `marketdata rqdata refresh-hk-intraday` | Legacy module path delegates to platform intraday download implementation. |
| `src/cstree/data_interface.py` | `research-consumer` | `cross-sectional-trees` | N/A | Research runtime reads platform assets or explicit provider-online inputs. |
| `src/cstree/dataset.py` | `research-consumer` | `cross-sectional-trees` | N/A | Research dataset construction consumes configured inputs. |
| `src/cstree/pipeline/data.py` | `research-consumer` | `cross-sectional-trees` | N/A | Pipeline data loading consumes configured provider or local inputs. |
| `src/cstree/pipeline/dataset_sampling.py` | `research-consumer` | `cross-sectional-trees` | N/A | Sampling logic operates on in-memory research datasets. |
| `src/cstree/pipeline/feature_dataset.py` | `research-consumer` | `cross-sectional-trees` | N/A | Feature dataset assembly consumes platform-prepared assets. |
| `src/cstree/pipeline/industry_enrichment.py` | `research-consumer` | `cross-sectional-trees` | N/A | Industry labels are read as research inputs. |
| `src/cstree/pipeline/output_summary_metadata.py` | `research-consumer` | `cross-sectional-trees` | N/A | Run provenance records consumed current contracts without refreshing them. |
| `src/cstree/pipeline/output_artifacts.py` | `research-output` | `cross-sectional-trees` | N/A | Writes research run artifacts such as positions, summaries, and scored outputs. |
| `src/cstree/liveops/alloc_market_data.py` | `research-consumer` | `cross-sectional-trees` | N/A | Live allocation reads latest market prices and lot sizes for target export. |
| `src/cstree/liveops/alloc_hk_market_data.py` | `research-consumer` | `cross-sectional-trees` | N/A | HK live allocation reads provider data for execution preparation. |
| `src/cstree/release_tools/package_runs.py` | `research-output` | `cross-sectional-trees` | N/A | Packages research runs, not reusable market data assets. |
| `src/cstree/release_tools/__init__.py` | `research-output` | `cross-sectional-trees` | N/A | Namespace package for research run packaging helpers. |
| `src/cstree/release_tools/release_runs.py` | `research-output` | `cross-sectional-trees` | N/A | Uploads research run packages, not data asset releases. |
| `src/cstree/research/hk_connect_cap_weight_benchmark.py` | `research-consumer` | `cross-sectional-trees` | N/A | Builds benchmark evidence from prepared daily, valuation, and universe inputs. |
| `src/cstree/research/hk_financial_details.py` | `research-consumer` | `cross-sectional-trees` | N/A | Analyzes prepared financial-details probes and mapping rules. |
| `src/cstree/research/hk_industry_filtered_universe.py` | `research-consumer` | `cross-sectional-trees` | N/A | Builds research-specific filtered universe files from prepared inputs. |
| `src/cstree/research/hk_intraday_slippage_report.py` | `research-consumer` | `cross-sectional-trees` | N/A | Consumes prepared intraday assets to calibrate research slippage assumptions. |
| `src/cstree/research/hk_selected_provider_valuation_audit.py` | `research-consumer` | `cross-sectional-trees` | N/A | Audits provider-overlay research runs and cached valuation inputs. |
| `src/cstree/research/hk_selected_provider_valuation_merge.py` | `research-consumer` | `cross-sectional-trees` | N/A | Research experiment helper for provider valuation overlays; does not publish assets. |
| `scripts/internal/package_repo.sh` | `repo-maintenance` | `cross-sectional-trees` | N/A | Packages repository source, not market data. |
| `scripts/dev/data_ops_boundary.py` | `repo-maintenance` | `cross-sectional-trees` | N/A | Governance check for this inventory. |

## Check

Run the boundary check before adding or moving any market-data-related source:

```bash
python scripts/dev/data_ops_boundary.py --check
```

The check is also part of `scripts/dev/run_tests.sh lint`.
