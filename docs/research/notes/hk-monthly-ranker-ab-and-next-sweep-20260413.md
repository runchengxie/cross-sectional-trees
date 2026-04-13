# HK Monthly Ranker A/B 与下一轮探索设计（2026-04-13）

> 状态提示：本页属于 active deep-dive，用于记录 monthly `no_ret` family 上的 ranker A/B、artifact 口径陷阱，以及下一轮 ranker-native 小 sweep 的设计。当前 monthly 默认入口仍是 [hk-monthly-current-state-20260330.md](./hk-monthly-current-state-20260330.md)。

本页解决什么：回答“把 round 4 gated winner 的 XGB 参数换成 ranker 后，到底比 regressor 和旧 ranker 好在哪里、差在哪里”，并给出下一轮最小探索矩阵。

本页不解决什么：不把单次 ranker A/B 升级成新主线，不替代 `summary.json` / `config.used.yml`，也不重新解释季度 ranker 主线。

适合谁：已经看过 `hk-monthly-pit-no-ret-tuning-follow-up-20260405.md`，并想决定 monthly 下一轮是继续调 regressor、ranker 还是 construction 的人。

读完你会得到什么：一个可复现 A/B 结论、一个关于 `latest` artifact 的复现风险提醒，以及下一轮 ranker-native sweep 应该怎么收口。

相关页面：[hk-monthly-current-state-20260330.md](./hk-monthly-current-state-20260330.md)、[hk-monthly-pit-no-ret-tuning-follow-up-20260405.md](./hk-monthly-pit-no-ret-tuning-follow-up-20260405.md)、[hk-monthly-benchmark-ladder-and-attribution-20260405.md](./hk-monthly-benchmark-ladder-and-attribution-20260405.md)、[hk-quarterly-benchmark-and-interpretation-20260405.md](./hk-quarterly-benchmark-and-interpretation-20260405.md)

页面性质：`research-note`

状态：`active deep-dive`

最后核对时间：`2026-04-13`

权威来源：本页列出的 run 目录下 `summary.json` / `run.log` / `config.used.yml`

冲突优先级：如果与具体 run 的 `summary.json` / `config.used.yml` 冲突，以 run 产物为准；如果与更晚样本或正式 sweep 结果冲突，以更晚样本或正式 sweep 为准

## 1. 先说结论

这次 A/B 的最重要结论不是“ranker 已经赢了”，而是：

* monthly `no_ret` family 上，ranker 确实值得继续探索。
* 直接把 round 4 gated regressor winner 的参数换成 `xgb_ranker + rank:pairwise`，不是一个足够好的最终答案。
* ranker 的组合路径有亮点，但信号证据不够干净：
  * CV fold 覆盖更完整
  * walk-forward Sharpe 改善
  * final OOS Sharpe 略高
  * 但 test / final OOS IC 明显弱于 regressor
  * final OOS long-short 变负
  * turnover 上升
  * active IR 更差

一句话收口：

* **下一轮最值得做的是 ranker-native 小 sweep，而不是继续把 regressor 的最优参数原样套给 ranker。**

## 2. 为什么先写这页

这次复核过程中出现了一个容易误导后续研究的细节：

* 原 round 4 gated winner 是 `2026-04-05` 产物。
* 当前本地 `latest` asset 在 `2026-04-10` / `2026-04-11` 后已经刷新。
* 直接用原 `best_config.yml` 改成 ranker 并跑当前 `latest`，会在切分阶段失败：
  * `eval.final_oos.size leaves no in-sample dates.`

失败原因不是 ranker 本身，而是当前 `hk_selected_pit_research_by_date.csv` 已经变成更小的 universe：

| by-date file | symbols | dates | date range |
| --- | ---: | ---: | --- |
| `artifacts/assets/universe/hk_selected_pit_research_by_date.csv` | `91` | `73` | `20150130 -> 20260409` |
| `artifacts/assets/universe/hk_selected_pit_research_by_date_valuation_gate_20260401.csv` | `218` | `135` | `20150130 -> 20260331` |

所以本页的 A/B 统一固定到 dated asset：

* `artifacts/assets/rqdata/hk/daily/hk_all_2000_20260402_daily_clean_refetched_latest`
* `artifacts/assets/rqdata/hk/instruments/hk_all_instruments_20260402.parquet`
* `artifacts/assets/rqdata/hk/ex_factors/hk_all_2000_20260402_ex_factors_full_market_latest`
* `artifacts/assets/universe/hk_selected_pit_research_by_date_valuation_gate_20260401.csv`

这一步很重要：

* 后续 monthly sweep 不应再默认使用 `latest`
* 否则模型差异会和数据口径差异混在一起

## 3. 本次 A/B 设置

基准来自 round 4 gated winner：

* sweep：`artifacts/sweeps/hk_m_pit_no_ret_r4_cv_gate/`
* original best run：`artifacts/runs/hk_sel_m_tune_hk_m_pit_no_ret_r4_cv_gate_trial_020_20260405_234309_c27d0147/`
* original best config：`artifacts/sweeps/hk_m_pit_no_ret_r4_cv_gate/best_config.yml`

固定不动：

* `M-PIT + no_ret`
* `data.end_date = 20260327`
* `label.horizon_mode = next_rebalance`
* `eval.final_oos.size = 24`
* `top_k = 20`
* `buffer_exit = 20`
* `buffer_entry = 10`
* `exp_decay(halflife = 6)`
* `rolling train_window = 48 dates`
* feature recipe
* execution / cost 口径
* dated asset 口径

只改模型：

| A/B leg | model | objective |
| --- | --- | --- |
| regressor fixed | `xgb_regressor` | `reg:squarederror` |
| ranker fixed | `xgb_ranker` | `rank:pairwise` |

对应 run：

* regressor fixed run：`artifacts/runs/hk_sel_m_pit_no_ret_r4_trial020_regressor_ab_fixed20260402_20260413_110214_5604297b/`
* ranker fixed run：`artifacts/runs/hk_sel_m_pit_no_ret_r4_trial020_ranker_ab_fixed20260402_20260413_110312_85ffa390/`

## 4. 和原 round 4 winner 的复现检查

先看 regressor fixed 是否能贴回原 round 4。

| 指标 | original round 4 trial020 | regressor fixed |
| --- | ---: | ---: |
| symbols | `218` | `218` |
| rows_model | `9691` | `9691` |
| dropped_dates | `0` | `0` |
| CV IC mean | `0.032` | `0.032` |
| CV valid folds | `2 / 5` | `2 / 5` |
| test IC mean | `4.6%` | `4.6%` |
| test IC IR | `0.353` | `0.353` |
| test Sharpe | `0.178` | `0.178` |
| test max drawdown | `-47.5%` | `-47.5%` |
| test turnover | `31.1%` | `31.1%` |
| final OOS IC mean | `8.9%` | `9.1%` |
| final OOS Sharpe | `1.708` | `1.662` |
| final OOS max drawdown | `-8.5%` | `-8.5%` |
| final OOS turnover | `19.9%` | `20.0%` |

这个复现足够接近，说明：

* fixed dated asset A/B 是可用比较口径
* ranker 差异主要来自 model/objective，而不是数据漂移

## 5. Ranker A/B 结果

| 指标 | regressor fixed | ranker fixed |
| --- | ---: | ---: |
| model | `xgb_regressor` | `xgb_ranker` |
| objective | `reg:squarederror` | `rank:pairwise` |
| CV IC mean | `0.032` | `0.033` |
| CV valid folds | `2 / 5` | `5 / 5` |
| test IC mean | `4.6%` | `2.3%` |
| test IC IR | `0.353` | `0.149` |
| test Sharpe | `0.178` | `0.277` |
| test max drawdown | `-47.5%` | `-51.2%` |
| test turnover | `31.1%` | `42.1%` |
| walk-forward IC mean | `-0.091` | `-0.026` |
| walk-forward Sharpe mean | `-0.285` | `0.221` |
| final OOS IC mean | `9.1%` | `4.9%` |
| final OOS IC IR | `0.354` | `0.208` |
| final OOS long-short | `0.2%` | `-0.8%` |
| final OOS Sharpe | `1.662` | `1.859` |
| final OOS max drawdown | `-8.5%` | `-6.2%` |
| final OOS turnover | `20.0%` | `27.3%` |
| final OOS active IR | `-0.195` | `-0.526` |

怎么读：

* ranker 的 `CV valid folds` 明显更好，这说明它没有复现 regressor winner 的 early-fold collapse 问题。
* ranker 的 walk-forward Sharpe 和 final OOS Sharpe 更好，这说明它不是无效分支。
* 但 ranker 的 test / final OOS IC 都明显弱，final OOS long-short 还变负。
* ranker 的 turnover 更高，且 active IR 更差。

所以不能说：

* ranker 已经优于 regressor

更准确是：

* **ranker 解决了一部分验证可判分和组合路径问题，但没有保住 regressor 的信号强度。**

## 6. 和季度 ranker 主线的关系

季度当前主线仍是：

* `ranker h12_w16 + close + balanced execution`
* run：`artifacts/runs/hk_sel_q_g4_fixed_pit_overlay_xgb_rank_antidrift_h12_w16_exec_balanced_local_20260328_235502_6e283435/`

它和本页 monthly ranker 不是严格 A/B：

* 一个是季度
* 一个是月频
* universe / rows_model / label cadence 都不同
* 不能直接说谁全局更强

只做方向性对照：

| 指标 | quarterly ranker mainline | monthly tuned ranker A/B |
| --- | ---: | ---: |
| frequency | `Q` | `M` |
| symbols | `328` | `218` |
| rows_model | `2336` | `9691` |
| test IC mean | `-2.4%` | `2.3%` |
| test IC IR | `-0.150` | `0.149` |
| test Sharpe | `-0.061` | `0.277` |
| test turnover | `55.7%` | `42.1%` |
| walk-forward IC mean | `3.4%` | `-2.6%` |
| walk-forward Sharpe mean | `-1.258` | `0.221` |
| final OOS IC mean | `3.8%` | `4.9%` |
| final OOS Sharpe | `2.039` | `1.859` |
| final OOS turnover | `71.1%` | `27.3%` |

这张表支持的结论有限：

* monthly tuned ranker 的 turnover 明显更低
* monthly tuned ranker 的 test 段更好
* quarterly mainline 的 final OOS Sharpe 仍更高
* 两者的 walk-forward IC 方向相反

所以不能把本页结果写成：

* monthly ranker 已经替代 quarterly ranker

只能写成：

* **monthly ranker 是一个值得单独推进的分支，但它回答的是 monthly `no_ret` family 的问题，不是季度主线替换问题。**

## 7. 为什么不能直接升 ranker

这次 ranker A/B 最大的问题不是收益账面，而是证据结构：

* signal 层：
  * test IC IR 比 regressor 低
  * final OOS IC IR 比 regressor 低
  * final OOS long-short 为负
* implementation 层：
  * final OOS Sharpe 更高
  * drawdown 更浅
  * 但 turnover 更高
* benchmark / active 层：
  * active IR 明显更差

这组证据说明：

* ranker 的组合结果可能吃到了一些路径或暴露结构
* 不能把 final OOS Sharpe 单独当作升级依据
* 下一轮必须同时看 IC、walk-forward、turnover 和 active metrics

## 8. 下一轮最值得探索的方向

下一轮不是“大扫模型”，而是小范围 ranker-native sweep。

目标：

* 不追求单次最高 OOS Sharpe
* 找一个同时满足信号、组合和换手 gate 的 ranker 候选

固定不动：

* dated asset
* `M-PIT + no_ret`
* `h6 + rolling 48`
* `top_k = 20` 初始不动
* `buffer_exit = 20`
* `buffer_entry = 10`
* execution / cost 口径

优先扫：

| 维度 | 候选值 | 原因 |
| --- | --- | --- |
| `max_depth` | `2, 3` | ranker 当前 train IC 过高，先压模型复杂度 |
| `min_child_weight` | `5, 10, 20` | 抑制过拟合和小截面噪音 |
| `reg_lambda` | `5.0, 10.0` | ranker 比 regressor 更需要保守正则 |
| `reg_alpha` | `0.2, 0.5, 1.0` | 避开原 regressor 中 `0.3` 附近的 CV collapse 疑点，同时看更强 L1 是否压住 ranker |
| `subsample` | `0.7, 0.85` | 降低树间相关和 top-k 抖动 |
| `colsample_bytree` | `0.7, 1.0` | 观察是否能减少单一基本面特征过度主导 |

第一波不要全笛卡尔大扫。建议先做 12-18 个手工挑选 trial：

* 以 `max_depth=2/3`、`min_child_weight=10`、`reg_lambda=5/10` 为主轴
* 只保留少数 `min_child_weight=5` 和 `20` 的边界探针
* `buffer` 第一波先不扫，避免把 model 和 construction 混在一起

## 9. 下一轮 gate

下一轮 best selection 不应只用一个 objective。

建议 gate：

| gate | 建议 |
| --- | --- |
| CV 可判分 | `valid_folds >= 4 / 5` |
| test IC | `test_ic_ir > 0.20`，或至少不能低于当前 ranker A/B 太多 |
| walk-forward | `walk_forward_test_ic_mean >= 0` 或 `walk_forward_sharpe_mean > 0` 至少满足一个 |
| turnover | `final_oos_turnover <= 25%`，允许少数强候选放宽到 `30%` |
| final OOS signal | `final_oos_ic_mean > 0` 且 `final_oos_long_short` 不应明显为负 |
| active | `final_oos_active_ir` 不应比当前 ranker A/B 继续恶化 |

如果 gate 之间冲突，优先级建议是：

1. CV 可判分
2. test / walk-forward signal
3. final OOS signal
4. turnover
5. final OOS Sharpe

原因：

* final OOS Sharpe 太容易被 2024-2026 regime 和 benchmark 背景放大
* 如果 signal 层不稳，Sharpe 再亮也只能当线索，不能当主线证据

## 10. 下一轮之后怎么决策

下一轮 ranker-native sweep 跑完后，建议只做三种判断：

### 10.1 如果 ranker 同时改善 IC 和 turnover

可以把它升级为：

* monthly `no_ret` ranker challenger

但仍不应直接替代 regressor gated winner，除非：

* test IC 不低于 regressor 太多
* final OOS long-short 转正
* active IR 不继续恶化

### 10.2 如果 ranker 只改善 Sharpe，不改善 IC

保留为：

* implementation / construction sidecar

下一步转向：

* fixed-signal construction grid
* buffer / top_k / group cap

### 10.3 如果 ranker IC 继续弱、turnover 继续高

暂时降级：

* 不继续扫 ranker
* 回到 regressor gated winner
* 优先做 construction 和 benchmark attribution

## 11. 当前推荐执行顺序

最务实的顺序是：

1. 写本页并固定证据边界。
2. 基于 dated asset 写一个 ranker-native tune spec。
3. 先跑 dry-run 检查 configs 和 jobs。
4. 跑 12-18 个小 trial。
5. 统一 summarize。
6. 按本页 gate 选 shortlist，而不是只看 best objective。
7. 如果 ranker shortlist 存在，再做第二步 construction grid。

不要先做：

* 大范围 XGB sweep
* 新特征
* 新模型
* `latest` asset 下的直接复跑

这些都会让当前最关键的问题变混：

* **ranker 本身有没有稳定排序增量。**
