## Context

The HK selected research stack already supports XGB regressors/rankers, walk-forward diagnostics, final OOS evaluation, benchmark comparison, cost drag, turnover metrics, scored artifacts, and run summarization. Recent research conclusions point to `xgb_ranker + h12_w16` as the current stable baseline, with `xgb_regressor + zscore target` and anti-drift work as the main challengers.

The US random-forest project adds useful discipline: the model is only one part of a full research protocol that includes rolling OOS, holdout, transaction costs, portfolio construction, feature selection, and diagnostics. This design adapts that protocol discipline to the existing HK XGB stack without making random forest a phase-one model.

## Goals / Non-Goals

**Goals:**
- Define a promotion gate so HK XGB challengers are evaluated against the current baseline using comparable evidence.
- Make turnover and cost drag visible in tuning, grid comparison, and run summary decisions.
- Allow fixed model scores to be reused for portfolio construction comparisons.
- Add feature selection evidence that is tied to realized strategy outcomes, not only model importance.
- Standardize benchmark ladder reporting so alpha, beta, universe, and cap-weight effects are easier to separate.

**Non-Goals:**
- Do not add random forest as a supported `model.type` in this change.
- Do not replace the current HK baseline automatically.
- Do not introduce an order-level execution simulator or broker-specific cost model.
- Do not require large artifact scans as part of routine proposal validation.

## Decisions

### Decision 1: Add a promotion-gate report instead of replacing ad hoc summaries

The first implementation should add a deterministic report layer that reads existing run outputs and marks a candidate as promotable, reviewable, or rejected. This keeps the pipeline stable while making research decisions stricter.

Alternative considered: enforce promotion gates inside `csml run`. That would make exploratory work slower and brittle. The report layer lets researchers run experiments freely, then apply the stricter gate when deciding whether a candidate is worth promotion.

### Decision 2: Reuse existing objective components before adding a new optimizer

`csml tune` already has weights for evaluation IC IR, walk-forward test IC, Sharpe, drawdown, cost drag, and turnover. The change should first standardize these fields across tune/grid/summarize outputs and document their expected meanings.

Alternative considered: add a multi-objective optimizer immediately. That is heavier than needed. A transparent scalar score plus component columns is easier to audit and aligns with current tooling.

### Decision 3: Treat portfolio construction as a fixed-score experiment

Portfolio construction comparisons should consume existing scored artifacts where possible. This isolates the question "did construction improve the strategy?" from "did the model learn a different signal?"

Alternative considered: rerun full training for every top-k, buffer, and weighting variant. That is expensive and confounds model variance with construction choices.

### Decision 4: Start with family-level and permutation-based feature evidence

The feature protocol should require family-level ablation first, then optional permutation active-return importance. This matches the repository's existing family-oriented benchmark guidance and avoids over-trusting tree importance.

Alternative considered: sequential feature selection for every HK run. That is too expensive for large HK assets and should remain optional.

### Decision 5: Keep benchmark ladder as reporting context, not a hidden label change

The benchmark ladder should report ETF, universe-aligned cap-weight, equal-weight, and attribution comparisons without silently changing the training label. This preserves comparability across existing `future_return`, ranker, and zscore-target research lines.

Alternative considered: train directly on benchmark-relative classification labels. That would create a different research problem and should be proposed separately if needed.

## Risks / Trade-offs

- Promotion gates may reject promising early ideas -> keep exploratory runs possible and apply gates only to promotion decisions.
- Fixed-score construction grids may miss interactions between model training and portfolio constraints -> use them as first-pass construction evidence, then rerun full pipeline for finalists.
- Cost and turnover penalties can over-favor inert low-turnover strategies -> require positive predictive evidence and degeneracy checks alongside cost-aware scoring.
- Permutation active-return importance can be noisy -> aggregate by window and family, and report hit rates instead of relying on a single run.
- Benchmark ladder reporting can add too many outputs -> keep main benchmark unchanged and put extra benchmarks in report-level comparison files.

## Migration Plan

1. Add specs and docs for the stricter HK research protocol.
2. Extend summary/tune/grid outputs with missing normalized fields before adding new commands.
3. Add promotion-gate reporting on top of existing run directories.
4. Add fixed-score portfolio construction comparison using existing scored artifacts.
5. Add feature family ablation and optional permutation active-return reports.
6. Update HK playbooks to describe how a candidate moves from experiment to challenger to baseline.

Rollback is straightforward because phase-one work should be additive: remove the new report commands/configs and keep existing `csml run` behavior unchanged.

## Open Questions

- What default numeric thresholds should define "promotable" versus "reviewable" for HK quarterly and monthly lines?
- Should promotion gates compare against only `xgb_ranker h12_w16`, or support a named baseline run directory for every research lane?
- Should benchmark ladder attribution be required for all promoted runs, or only when benchmark active performance is a deciding factor?
