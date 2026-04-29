## Context

The repository is already a governed HK cross-sectional research framework. The public workflow includes `cstree run`, `tune`, `sweep-linear`, `grid`, `promotion-gate`, `feature-evidence`, `construction-grid`, and `benchmark-ladder`. The main pipeline already computes CV IC, walk-forward windows, final OOS, backtests, turnover, cost drag, benchmark evidence, and feature stability. Current promotion checks read `summary.json` and `config.used.yml` from saved runs and classify candidates as promotable, reviewable, rejected, or non-comparable.

The missing piece is a sidecar that asks whether a shortlisted candidate remains acceptable across many out-of-sample historical paths. Monthly HK selected research is the first target because it has enough rebalance dates for CPCV-style path distributions. Quarterly research can use the same tool more cautiously with smaller group counts.

## Goals / Non-Goals

**Goals:**

- Add a standalone `cstree cpcv` research command for shortlisted candidates.
- Reuse existing model, scoring, portfolio, backtest, benchmark, and report conventions.
- Build deterministic combinatorial purged splits and path metrics.
- Use event-window purge semantics when label windows can be derived from the configured label mode.
- Emit small, structured reports suitable for review and promotion-gate ingestion.
- Allow `promotion-gate` to require candidate CPCV evidence without making CPCV mandatory for all research runs.

**Non-Goals:**

- Do not replace walk-forward, final OOS, benchmark ladder, or current promotion checks.
- Do not run CPCV automatically inside every `cstree run`, `tune`, or `sweep-linear` trial.
- Do not introduce a new modeling framework or new external dependency in the first version.
- Do not treat quarterly CPCV as a hard statistical proof when there are too few rebalance dates per group.

## Decisions

1. CPCV is a standalone research sidecar.

   The command will be registered beside the existing research commands as `cstree cpcv`. It accepts a normal pipeline config plus CPCV overrides such as `--n-groups`, `--test-groups`, `--out`, `--embargo-days`, and an optional final-OOS inclusion flag.

   Alternative considered: make CPCV a new `eval.cpcv` stage inside `cstree run`. That would make ordinary runs much heavier and would blur the current separation between normal pipeline evidence and expensive candidate audits.

2. CPCV reuses pipeline preparation but owns its split loop.

   Implementation should extract or reuse the same setup steps that `pipeline.runner.run` already performs: config resolution, panel loading, feature dataset creation, split metadata, model/backtest settings, and benchmark inputs. The CPCV module then creates its own split definitions and calls existing helpers such as `fit_model`, scoring/postprocess helpers, metrics functions, and `backtest_topk`.

   Alternative considered: spawn many full `cstree run` executions with generated configs. That would duplicate artifacts, make reports harder to compare, and make path assembly awkward.

3. Final OOS remains reserved by default.

   If the config has `eval.final_oos.enabled=true`, CPCV will default to the remaining in-sample labeled rebalance dates. Users can explicitly include final OOS dates for stress analysis, but that mode must be recorded in `cpcv_summary.json`.

   Alternative considered: always use every labeled date. That gives more path observations, but weakens the project convention that final OOS answers a separate holdout question.

4. Split construction is combinatorial and deterministic.

   Eligible rebalance dates are divided into `n_groups` contiguous chronological groups with group sizes differing by at most one date. Each split tests one `test_groups` combination and trains on all remaining groups after purge/embargo. The command validates `1 <= test_groups < n_groups`, enough dates per group, and enough surviving training dates.

   The expected split count is `comb(n_groups, test_groups)`. The expected CPCV path count is `comb(n_groups - 1, test_groups - 1)`, so `n_groups=8`, `test_groups=2` yields 28 splits and 7 paths.

5. Purging uses label event windows, not only a simple gap.

   Each rebalance date gets a label interval derived from the configured `signal_date`, `entry_date`, and label end date. For `label.horizon_mode=fixed`, the interval uses `shift_days` and `horizon_days`. For `next_rebalance`, it uses the next rebalance date mapping already available during feature construction. A training date is purged when its label interval overlaps any test interval. Embargo is then applied after test intervals using the configured or overridden embargo days.

   If an implementation cannot derive event windows for a configuration, it must not silently claim event purging. It may fall back to the existing effective gap only when the report records `purge_mode=fallback_gap` and the CLI logs the limitation.

6. Reports are small and promotion-friendly.

   The sidecar writes:

   - `cpcv_splits.csv`: split membership, date ranges, counts, purge counts, and status.
   - `cpcv_path_returns.csv`: path-level return observations with dates, net return, gross return, benchmark return, and active return when available.
   - `cpcv_path_metrics.csv`: one row per CPCV path with Sharpe, drawdown, IC, long-short, turnover, cost drag, and benchmark-active metrics when available.
   - `cpcv_summary.json`: config, split counts, path counts, defaults used, and distribution statistics.

   Summary statistics should include mean, median, p25, p10, min, and positive ratio for Sharpe; median IC and long-short; and conservative drawdown, turnover, and cost-drag quantiles.

7. Promotion-gate CPCV integration is optional and explicit.

   `promotion-gate` should accept a `cpcv` evidence block and allow `required_evidence` to include `cpcv`. Candidate CPCV evidence is read from `cpcv_summary.json`; baseline CPCV evidence is optional and only required for baseline-relative thresholds. Missing required CPCV evidence rejects the candidate. Threshold failures are reported through existing hard/soft failure lists and flat CSV fields.

## Risks / Trade-offs

- CPCV can be expensive -> Keep it out of the main run path, document it for top candidates, and make the first version monthly-first.
- Event-window purge may expose missing metadata -> Derive windows from existing label settings where possible, record the purge mode, and test fixed and next-rebalance cases.
- CPCV paths can be overinterpreted on sparse quarterly samples -> Document quarterly as stress observation unless group sizes are large enough.
- Reusing internal pipeline setup may require refactoring `runner.run` -> Keep any extraction behavior-preserving and cover it with existing pipeline tests.
- Path assembly is easy to get wrong -> Unit test split counts, path counts, group coverage, and deterministic output ordering for several `n_groups/test_groups` combinations.
