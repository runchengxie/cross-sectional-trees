## 1. Pipeline Reuse and CLI

- [x] 1.1 Extract a reusable research preparation helper from `src/cstree/pipeline/runner.py` that returns loaded config, dataset state, split metadata, model settings, evaluation settings, backtest settings, benchmark inputs, and service hooks without persisting a normal run.
- [x] 1.2 Keep `cstree run` behavior unchanged by routing the current runner through the extracted helper and preserving existing output persistence.
- [x] 1.3 Add `src/cstree/research/cpcv.py` with argument parsing, config loading, validation, output directory resolution, and a `run(args)` entrypoint.
- [x] 1.4 Register `cstree cpcv` in `src/cstree/cli/research.py` and cover it in CLI entrypoint tests.

## 2. Split and Purge Engine

- [x] 2.1 Implement deterministic chronological CPCV group assignment for eligible rebalance dates, including final-OOS exclusion by default.
- [x] 2.2 Implement combinatorial split generation with validation for `n_groups`, `test_groups`, expected split count, and expected path count.
- [x] 2.3 Implement label event-window derivation for fixed-horizon labels using `trade_date`, `shift_days`, and `horizon_days`.
- [x] 2.4 Implement label event-window derivation for `next_rebalance` labels using the existing next-rebalance mapping.
- [x] 2.5 Implement event-window purge and embargo filtering, recording purge mode and removed train-date counts per split.
- [x] 2.6 Add unit tests for group sizing, split counts, path counts, final-OOS exclusion, fixed-horizon purge, next-rebalance purge, and insufficient-data split status.

## 3. CPCV Evaluation and Reports

- [x] 3.1 Fit the configured model per valid split using existing model construction, sample weights, target transform, train-window, and score postprocess behavior.
- [x] 3.2 Score split test dates and compute IC, Pearson IC, long-short, top-k positive ratio, turnover, and cost drag with existing metric helpers.
- [x] 3.3 Run split/path backtests with existing portfolio, execution, cost, and benchmark conventions when backtest is enabled.
- [x] 3.4 Implement deterministic CPCV path assembly so each valid path covers every eligible test group exactly once when possible.
- [x] 3.5 Write `cpcv_splits.csv`, `cpcv_path_returns.csv`, `cpcv_path_metrics.csv`, and `cpcv_summary.json` with stable schemas.
- [x] 3.6 Add report tests that verify output schemas, summary distribution fields, deterministic ordering, and benchmark-active fields when benchmark data is available.

## 4. Promotion Gate Integration

- [x] 4.1 Extend promotion-gate config parsing with optional `cpcv` report paths and CPCV hard/soft threshold settings.
- [x] 4.2 Extend candidate evidence extraction to load `cpcv_summary.json` and expose path count, Sharpe distribution, IC median, long-short median, drawdown, turnover, and cost-drag metrics.
- [x] 4.3 Make `required_evidence: cpcv` reject missing candidate CPCV evidence.
- [x] 4.4 Add CPCV threshold failures to existing hard and soft failure lists, plus flat CSV output fields.
- [x] 4.5 Add promotion-gate tests for missing CPCV evidence, passing CPCV evidence, failing CPCV thresholds, and optional baseline-relative CPCV thresholds.

## 5. Documentation and Example Config

- [x] 5.1 Document `cstree cpcv` in `docs/cli.md` with monthly `n_groups=8`, `test_groups=2` examples.
- [x] 5.2 Document CPCV output files and fields in `docs/outputs.md`.
- [x] 5.3 Document CPCV configuration/default behavior in `docs/config.md`, including final-OOS exclusion and purge mode.
- [x] 5.4 Add CPCV to `docs/capabilities.md`, `docs/metrics.md`, and `docs/playbooks/hk-selected.md` as a shortlisted-candidate robustness sidecar.
- [x] 5.5 Add or update a small promotion-gate config example showing optional CPCV evidence thresholds.

## 6. Verification

- [x] 6.1 Run focused tests for CPCV, promotion-gate, CLI registration, split logic, and path/report generation.
- [x] 6.2 Run documentation/path contract tests: `uv run pytest tests/test_docs_contracts.py tests/test_repo_path_references.py tests/test_run_tests_script.py -q`.
- [x] 6.3 Run the repository fast test script or an equivalent focused regression set if runtime is acceptable.
- [x] 6.4 Manually inspect generated OpenSpec artifacts and command help text for consistency with the proposal and specs.
