# HK Monthly Ranker A/B 与下一轮探索设计（2026-04-13）

> 状态提示：本页属于专题分析（`active deep-dive`），记录 monthly `no_ret` 族上的 ranker A/B、artifact 口径陷阱、ranker 原生小 sweep，以及后续固定分数组合网格。当前 monthly 默认入口仍是 [hk-monthly-current-state-20260330.md](./hk-monthly-current-state-20260330.md)。

本页解决什么：回答“把 round 4 gated winner 的 XGB 参数换成 ranker 后，比 regressor 和旧 ranker 好在哪里、差在哪里”，并记录第一波 ranker 原生小 sweep 与固定分数组合网格的结果。

本页不解决什么：不把单次 ranker A/B 升级成新主线，不替代 `summary.json` / `config.used.yml`，也不重新解释季度 ranker 主线。

适合谁：已经看过 `hk-monthly-pit-no-ret-tuning-follow-up-20260405.md`，并想决定 monthly 下一轮是继续调 regressor、ranker 还是 construction 的人。

读完你会得到什么：一个可复现 A/B 结论、一个关于 `latest` artifact 的复现风险提醒、第一波 ranker 原生 sweep 的 shortlist、固定分数组合网格结果，以及当前执行层候选路线的初步归因风险。

相关页面：[hk-monthly-current-state-20260330.md](./hk-monthly-current-state-20260330.md)、[hk-monthly-pit-no-ret-tuning-follow-up-20260405.md](./hk-monthly-pit-no-ret-tuning-follow-up-20260405.md)、[hk-monthly-benchmark-ladder-and-attribution-20260405.md](./hk-monthly-benchmark-ladder-and-attribution-20260405.md)、[hk-quarterly-benchmark-and-interpretation-20260405.md](./hk-quarterly-benchmark-and-interpretation-20260405.md)

页面性质：`research-note`

状态：`active deep-dive`

最后核对时间：`2026-04-13`

权威来源：本页列出的 run 目录下 `summary.json` / `run.log` / `config.used.yml`

冲突优先级：如果与具体 run 的 `summary.json` / `config.used.yml` 冲突，以 run 产物为准；如果与更晚样本或正式 sweep 结果冲突，以更晚样本或正式 sweep 为准

## 1. 术语速查

| 本页写法 | 含义 |
| --- | --- |
| gated winner | 通过当前 CV gate 的调参 winner |
| ranker 原生 sweep | 按 ranker 自身参数空间做的小范围搜索 |
| 固定分数组合网格 | 固定模型分数，只扫组合构造参数 |
| 执行层候选 | 主要改善执行和组合层表现的候选路线 |
| 带约束候选 | 带组合约束后仍有增量的候选路线 |

## 2. 先说结论

这次 A/B 的最重要结论是：

* monthly `no_ret` family 上，ranker 确实值得继续探索。
* 直接把 round 4 gated regressor winner 的参数换成 `xgb_ranker + rank:pairwise`，还不是足够好的最终答案。
* ranker 的组合路径有亮点，但信号证据不够干净：
  * CV fold 覆盖更完整
  * walk-forward Sharpe 改善
  * final OOS Sharpe 略高
  * 但 test / final OOS IC 明显弱于 regressor
  * final OOS long-short 变负
  * turnover 上升
  * active IR 更差

一句话收口：

* **下一轮最值得做的是 ranker 原生小 sweep，不要继续把 regressor 的最优参数原样套给 ranker。**

第一波 ranker 原生小 sweep 跑完后，需要把结论更新为：

* **ranker 原生调参已经找到一个更像样的 monthly 候选路线，但还不应直接升主线。**
* 最强候选是 `trial_016`：`max_depth=2`、`min_child_weight=20`、`reg_lambda=10`、`reg_alpha=1.0`、`subsample=0.7`、`colsample_bytree=0.7`。
* 它修掉了直接 ranker A/B 的两个硬伤：final OOS long-short 转正，final OOS turnover 明显下降。
* 但它的 walk-forward IC mean 仍为负，说明还需要一次复跑 / 组合网格验证，不能只凭 final OOS Sharpe 升级。

同口径复跑和固定分数组合网格跑完后，结论再更新一次：

* `trial_016` 同口径复跑完全贴回原 run，说明它不是单次产物噪音。
* 组合网格的最强组合是 `k15_bx25_be12`：`top_k=15`、`buffer_exit=25`、`buffer_entry=12`。
* 它把 final OOS Sharpe 从 `2.07` 提到 `2.26`，backtest avg turnover 从 `16.60%` 降到 `14.56%`，active IR 从 `0.38` 提到 `0.55`。
* 初步 attribution 说明，`k15_bx25_be12` 的 active IR 改善在多个 benchmark 下都成立，但组合更集中，并且长期明显偏向大盘、低波和质量暴露。
* walk-forward IC mean 仍是 `-7.13%`，所以这次改善更像执行 / 组合构造层增量；signal 稳定性还没有解决。
* 当前更准确的状态是：`trial_016 + k15_bx25_be12` 可以作为 monthly `no_ret` ranker 执行层候选；还不应替代 regressor gated winner 或 monthly 默认入口。

第二波 ranker 原生邻域、bridge sweep 和 `trial_008` 固定分数组合网格跑完后，结论还要再更新一次：

* 第二波邻域说明：模型层没有找到一个能同时保住 `trial_016` 的 active IR、又把 walk-forward IC 稳定修正的桥接点。
* `trial_008` 变成更像 signal-candidate 的点：它的 walk-forward test IC mean 为 `0.07%`，同时 final OOS Sharpe 仍有 `1.99`。
* 固定 `trial_008` 后，组合网格的 objective winner 仍是 `k15_bx25_be12`。
* 它把 final OOS Sharpe 从 `1.99` 提到 `2.19`，final OOS backtest turnover 从 `18.36%` 降到 `15.50%`，final OOS active IR 从 `0.21` 提到 `0.38`。
* 更激进的 `k15_bx20_be10` 也值得保留：final OOS Sharpe `2.19`，active IR `0.58`，但 turnover 回到 `18.93%`。
* 接入 dated industry labels 后，`groupcap4` 能把 top industry 名字数压到 `<= 4`，同时仍把 `trial_008 + k15_bx25_be12` 的 final OOS Sharpe 保在 `2.20` 左右。
* `groupcap3` 在这条线上的 active IR 代价偏大，因此当前更准确的状态是：`trial_008 + k15_bx25_be12 + groupcap4` 应视为 monthly `no_ret` ranker 的主带约束候选，`trial_008 + k15_bx20_be10 + groupcap4` 是激进对照；`trial_016 + k15_bx25_be12` 仍是执行层上限参考，不是默认主线。

## 3. 为什么先写这页

这次复核过程中出现了一个容易误导后续研究的细节：

* 原 round 4 gated winner 是 `2026-04-05` 产物。
* 当前本地 `latest` asset 在 `2026-04-10` / `2026-04-11` 后已经刷新。
* 直接用原 `best_config.yml` 改成 ranker 并跑当前 `latest`，会在切分阶段失败：
  * `eval.final_oos.size leaves no in-sample dates.`

失败原因来自当前 `hk_selected_pit_research_by_date.csv` 已经变成更小的 universe，不能归因于 ranker 本身：

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

## 4. 本次 A/B 设置

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

## 5. 和原 round 4 winner 的复现检查

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
* ranker 差异主要来自 model/objective，数据漂移不是主要解释

## 6. Ranker A/B 结果

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

更准确的读法是：

* **ranker 解决了一部分验证可判分和组合路径问题，但没有保住 regressor 的信号强度。**

## 7. 和季度 ranker 主线的关系

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

## 8. 为什么不能直接升 ranker

这次 ranker A/B 最大的问题在证据结构，不在收益账面：

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

## 9. 下一轮最值得探索的方向

下一轮应做小范围 ranker 原生 sweep，避免“大扫模型”。

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

## 10. 下一轮 gate

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

## 11. 第一波 ranker 原生 sweep 结果

第一波按本页第 8 节设计跑了 16 个手工候选：

* sweep：`artifacts/sweeps/hk_m_pit_no_ret_ranker_native_r1_fixed20260402/`
* best objective run：`artifacts/runs/hk_sel_m_tune_hk_m_pit_no_ret_ranker_native_r1_fixed20260402_trial_016_20260413_113117_cad8e7e6/`
* result table：`artifacts/sweeps/hk_m_pit_no_ret_ranker_native_r1_fixed20260402/trial_results.csv`
* run summary table：`artifacts/sweeps/hk_m_pit_no_ret_ranker_native_r1_fixed20260402/runs_summary.csv`

### 11.1 主要候选

| trial | combo | strict gate | loose gate | test IC IR | WF IC mean | WF Sharpe mean | final OOS IC | final OOS long-short | final OOS Sharpe | final OOS turnover | final OOS active IR |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `016` | `d2_mcw20_l10_a1_sub07_col07` | yes | yes | `0.35` | `-7.13%` | `0.12` | `9.36%` | `0.73%` | `2.07` | `16.60%` | `0.38` |
| `008` | `d2_mcw10_l10_a05_sub07_col07` | no | yes | `0.15` | `0.07%` | `0.17` | `8.95%` | `0.99%` | `1.99` | `18.36%` | `0.21` |
| `015` | `d3_mcw10_l10_a1_sub085_col07` | no | yes | `0.17` | `0.19%` | `0.23` | `6.02%` | `0.04%` | `1.83` | `23.10%` | `0.05` |
| `010` | `d3_mcw10_l10_a02_sub085_col1` | no | yes | `-0.02` | `-0.94%` | `0.06` | `6.86%` | `0.03%` | `1.81` | `23.43%` | `-0.15` |

`strict gate` 使用第 9 节规则：`valid_folds >= 4 / 5`、`test_ic_ir > 0.20`、`walk_forward_test_ic_mean >= 0` 或 `walk_forward_sharpe_mean > 0`、`final_oos_ic_mean > 0`、`final_oos_long_short >= 0`、`final_oos_turnover <= 25%`、`final_oos_active_ir` 不低于直接 ranker A/B。

`loose gate` 只放宽 test IC IR，不放宽 final OOS signal / turnover / active 要求。

### 11.2 和直接 A/B 的增量

| 指标 | regressor fixed | direct ranker fixed | ranker 原生 trial016 |
| --- | ---: | ---: | ---: |
| test IC mean | `4.64%` | `2.26%` | `4.99%` |
| test IC IR | `0.35` | `0.15` | `0.35` |
| test long-short | `1.77%` | `1.46%` | `1.25%` |
| test Sharpe | `0.18` | `0.28` | `0.38` |
| test turnover | `31.07%` | `42.09%` | `39.52%` |
| walk-forward IC mean | `-9.11%` | `-2.60%` | `-7.13%` |
| walk-forward Sharpe mean | `-0.29` | `0.22` | `0.12` |
| final OOS IC mean | `9.11%` | `4.94%` | `9.36%` |
| final OOS long-short | `0.24%` | `-0.82%` | `0.73%` |
| final OOS Sharpe | `1.66` | `1.86` | `2.07` |
| final OOS max drawdown | `-8.50%` | `-6.24%` | `-6.21%` |
| final OOS turnover | `20.05%` | `27.30%` | `16.60%` |
| final OOS active IR | `-0.20` | `-0.53` | `0.38` |

怎么读：

* `trial_016` 已经不是“regressor 参数硬套 ranker”，它是 ranker 原生搜索下的强候选。
* 它相对 direct ranker fixed 的改善很干净：final OOS IC、long-short、Sharpe、turnover、active IR 全部改善。
* 它相对 regressor fixed 也有亮点：final OOS IC 接近或略高，Sharpe 更高，drawdown 更浅，turnover 更低，active IR 转正。
* 主要保留意见是 walk-forward IC mean 仍然较差；它靠 walk-forward Sharpe gate 过关，walk-forward IC 还没过关。

所以在 construction grid 前，更准确的状态是：

* **`trial_016` 可以升级为 monthly `no_ret` ranker 候选路线。**
* **它不应直接替代 regressor gated winner；当时下一步应做一次小范围 construction grid 和一次同口径复跑。**

### 11.3 同口径复跑与组合网格

先对 `trial_016` 做了同口径复跑：

* rerun：`artifacts/runs/hk_sel_m_tune_hk_m_pit_no_ret_ranker_native_r1_fixed20260402_trial_016_20260413_114009_cad8e7e6/`

复跑结果与原 `trial_016` 完全一致：

| 指标 | 原 `trial_016` | rerun |
| --- | ---: | ---: |
| test IC mean | `4.99%` | `4.99%` |
| test IC IR | `0.35` | `0.35` |
| test long-short | `1.25%` | `1.25%` |
| test Sharpe | `0.38` | `0.38` |
| final OOS IC mean | `9.36%` | `9.36%` |
| final OOS long-short | `0.73%` | `0.73%` |
| final OOS Sharpe | `2.07` | `2.07` |
| final OOS max drawdown | `-6.21%` | `-6.21%` |
| final OOS turnover | `16.60%` | `16.60%` |
| final OOS active IR | `0.38` | `0.38` |

随后固定 `trial_016` 的模型层参数，只扫 `top_k` / buffer：

* sweep：`artifacts/sweeps/hk_m_pit_no_ret_ranker_trial016_construction_r1_fixed20260402/`
* result table：`artifacts/sweeps/hk_m_pit_no_ret_ranker_trial016_construction_r1_fixed20260402/trial_results.csv`
* run summary table：`artifacts/sweeps/hk_m_pit_no_ret_ranker_trial016_construction_r1_fixed20260402/runs_summary.csv`

主要组合如下：

| trial | combo | test Sharpe | test turnover | WF IC mean | WF Sharpe mean | final OOS Sharpe | final OOS max drawdown | final OOS top-k turnover | final OOS backtest turnover | final OOS active IR |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | `k20_bx20_be10` | `0.38` | `39.52%` | `-7.13%` | `0.12` | `2.07` | `-6.21%` | `6.96%` | `16.60%` | `0.38` |
| `003` | `k15_bx25_be12` | `0.42` | `40.72%` | `-7.13%` | `0.14` | `2.26` | `-6.27%` | `4.06%` | `14.56%` | `0.55` |
| `002` | `k15_bx20_be10` | `0.51` | `45.63%` | `-7.13%` | `0.26` | `2.15` | `-7.52%` | `6.67%` | `16.97%` | `0.44` |
| `006` | `k20_bx25_be12` | `0.39` | `34.13%` | `-7.13%` | `0.09` | `2.16` | `-6.78%` | `5.00%` | `14.93%` | `0.41` |
| `007` | `k25_bx20_be10` | `0.34` | `33.89%` | `-7.13%` | `0.03` | `2.10` | `-6.00%` | `6.61%` | `17.48%` | `0.17` |

怎么读：

* `k15_bx25_be12` 是这轮组合网格里最值得保留的执行层候选。
* 它相对 `trial_016` baseline 同时改善 final OOS Sharpe、backtest turnover、active IR，并且 max drawdown 基本持平。
* `k15_bx20_be10` test / WF Sharpe 更好，但 final OOS drawdown 明显更深，且 turnover 没有明显下降。
* `k20_bx25_be12` 是保守备选：保留 `top_k=20`，也能降低 OOS turnover，但 active IR 不如 `k15_bx25_be12`。
* `k25_bx20_be10` 的 OOS max drawdown 最浅，但 active IR 太弱，不适合作为首选。

这轮 grid 没有改变的事实：

* model score、IC、long-short 完全相同，因为模型层没有变。
* walk-forward IC mean 仍为负。
* 因此它只能把 `trial_016` 从模型层候选推进成执行层候选，不能把它升级成已解决稳定性的主线。

### 11.4 Benchmark active attribution 和持仓集中度

对 `k15_bx25_be12` 做了一次初步 attribution / concentration check：

* challenger run：`artifacts/runs/hk_sel_m_tune_hk_m_pit_no_ret_ranker_trial016_construction_r1_fixed20260402_trial_003_20260413_114518_db1e1c92/`
* baseline run：`artifacts/runs/hk_sel_m_tune_hk_m_pit_no_ret_ranker_native_r1_fixed20260402_trial_016_20260413_114009_cad8e7e6/`
* 使用文件：`backtest_benchmark_compare_summary_oos.csv`、`backtest_report_oos.csv`、`positions_by_rebalance_oos.csv`、`backtest_periods_oos.csv`
* 单名归因用 `entry_date` 的 `open` 和 `exit_date` 的 `close` 复原 gross contribution；对 `backtest_gross_oos.csv` 的逐期复原误差为 `0.00%`，无 skipped position

先看 benchmark 层。`k15_bx25_be12` 相对 `k20_bx20_be10` 的 active 改善不是只换了 primary benchmark 才成立：

| benchmark | k15 active IR | k20 active IR | k15 active total | k20 active total | k15 beta | k20 beta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `hk_selected_pit_research_capw` | `0.55` | `0.38` | `11.49%` | `6.94%` | `0.89` | `0.96` |
| `hk_connect_full_capw` | `0.60` | `0.43` | `12.55%` | `7.96%` | `0.89` | `0.96` |
| `hk_selected_pit_research_eqw` | `0.52` | `0.41` | `19.17%` | `14.30%` | `0.60` | `0.65` |
| `hk_02800` | `0.64` | `0.52` | `20.57%` | `15.65%` | `0.66` | `0.71` |
| `hk_3432` | `0.80` | `0.68` | `29.75%` | `24.13%` | `0.50` | `0.54` |

需要注意：

* `hk_3432` 只有 `18` 个 aligned periods，不能作为主判断。
* primary cap-weight 口径下，`k15` 的 tracking error 从 `11.36%` 升到 `12.03%`，不是纯降风险。
* primary cap-weight 口径下，`k15` 的 beta 从 `0.96` 降到 `0.89`，alpha 从 `6.04%` 升到 `11.08%`；这支持它有 execution-layer 增量，但也提示它和 benchmark 的风险暴露已经不完全一样。

再看 active month concentration：

| 指标 | k15 `k15_bx25_be12` | k20 `k20_bx20_be10` |
| --- | ---: | ---: |
| aligned active months | `22` | `22` |
| positive / negative months | `13 / 9` | `12 / 10` |
| simple active return sum | `11.75%` | `7.69%` |
| largest active month | `2025-11-03: 7.83%` | `2025-11-03: 7.55%` |
| largest month / simple active sum | `66.67%` | `98.14%` |
| simple active sum ex largest month | `3.92%` | `0.14%` |
| simple monthly active IR ex largest month | `0.21` | `0.01` |

这张表的含义是：

* `k15` 的 active 仍然明显受 `2025-11` 这个月份影响。
* 但相对 `k20`，`k15` 去掉最大月份后还保留一点正 active；`k20` 去掉最大月份后几乎打平。
* `k15 - k20` 的 active improvement 主要来自 `2024-09`、`2026-02`、`2025-12` 等月份，不是简单把 `2025-11` 那个月权重放大。

再看 size / style exposure。这里 `backtest_industry_exposure_oos.csv` 的 `industry_col` 实际是 `size_bucket_q4`，不是正式行业：

| 暴露 | k15 | k20 | 读法 |
| --- | ---: | ---: | --- |
| `Q4_large` 平均组合权重 | `90.88%` | `89.32%` | 两者都高度大盘 |
| `Q4_large` 最低组合权重 | `80.00%` | `75.00%` | k15 更少离开大盘桶 |
| `Q4_large >= 80%` 月份占比 | `100.00%` | `95.65%` | k15 每期都至少八成大盘 |
| `Q4_large = 100%` 月份占比 | `30.43%` | `13.04%` | k15 更容易满仓大盘桶 |
| `low_vol` active vs equal 均值 | `0.98` | `0.95` | 两者都强低波 |
| `quality` active vs equal 均值 | `0.39` | `0.26` | k15 的质量暴露更强 |
| `momentum` active vs equal 均值 | `-0.05` | `-0.06` | 两者都不是 momentum chase |

持仓集中度也要标红：

| 指标 | k15 | k20 |
| --- | ---: | ---: |
| OOS positions | `326` | `409` |
| OOS unique symbols | `30` | `40` |
| avg names / period | `14.17` | `17.78` |
| avg period overlap | `92.80%` | `91.11%` |
| top 5 positive symbol contribution share | `43.80%` | `35.71%` |
| top 5 absolute symbol contribution share | `37.23%` | `28.79%` |

`k15` 的前五大 gross contribution 来源是：

| symbol | name | gross contribution |
| --- | --- | ---: |
| `02628.HK` | 中国人寿 | `10.79%` |
| `01919.HK` | 中远海控 | `8.31%` |
| `00005.HK` | 汇丰控股 | `7.73%` |
| `02388.HK` | 中银香港 | `6.67%` |
| `00700.HK` | 腾讯控股 | `5.91%` |

所以 attribution 后的判断是：

* `k15_bx25_be12` 的 active improvement 是真实可见的，不是 primary benchmark 特有现象。
* 它比 `k20_bx20_be10` 更像一个低 beta、大盘、低波、质量倾斜组合。
* 它也明显更集中，top symbols 和 top month 对结果贡献不小。
* 因此它适合作为执行层候选；下一步应该先做暴露防线 / 集中度防线 probe，不能马上升为 monthly 默认。

## 12. 组合网格之后怎么决策

同口径复跑和 construction grid 跑完后，建议把判断收口成三层：

### 12.1 Signal 层

`trial_016` 比 direct ranker fixed 明显更强，但 walk-forward IC mean 仍弱：

* 不能说 ranker signal 已经稳定优于 regressor
* 也不能说 construction grid 解决了 signal 稳定性
* 下一次模型层探索应优先围绕 walk-forward IC 做，避免继续追 final OOS Sharpe

### 12.2 Construction 层

`k15_bx25_be12` 是当前最清楚的增量：

* OOS Sharpe 更高
* OOS backtest turnover 更低
* active IR 更高
* max drawdown 基本持平

所以它可以保留为：

* monthly `no_ret` ranker 执行层候选

### 12.3 主线升级层

当前仍不应直接升主线，除非后续还能给出至少一个额外证据：

* rolling / walk-forward IC mean 转正，或至少显著收窄负值
* exposure guardrail 之后，active IR 仍能保留大部分
* `k15` 的个股贡献和月份贡献在更长窗口或前瞻验证里不过度集中

在这之前，`trial_016 + k15_bx25_be12` 更适合当 challenger，不适合当默认。初步 attribution 没有推翻它，但也没有消除集中度和暴露风险。

## 13. 当前推荐执行顺序

最务实的顺序是：

1. 写本页并固定证据边界。已完成。
2. 基于 dated asset 写一个 ranker 原生 tune spec。已完成。
3. 先跑 dry-run 检查 configs 和 jobs。已完成。
4. 跑 12-18 个小 trial。已完成，实际 16 个。
5. 统一 summarize。已完成。
6. 按本页 gate 选 shortlist，避免只看 best objective。当前 shortlist 是 `trial_016`，观察候选是 `trial_008` / `trial_015`。
7. 对 `trial_016` 做同口径复跑，确认不是单次 run 噪音。已完成。
8. 如果复跑仍成立，再做固定分数组合网格。已完成，当前首选是 `k15_bx25_be12`。
9. 做 benchmark active attribution 和 holding concentration 检查。已完成，结论是 active 改善成立，但集中度和大盘 / 低波 / 质量暴露风险仍需下一轮 guardrail。
10. 围绕 `trial_016` 补第二波 ranker 原生邻域 sweep，确认 walk-forward 修复是否能在不显著牺牲 active IR 的情况下成立。已完成，当前 signal-side 更像样的候选变成 `trial_008`。
11. 做一个小的 bridge sweep，测试 `trial_005` 和 `trial_016` 之间有没有可用桥接点。已完成，结论是没有真正 bridge 成功的新点。
12. 固定 `trial_008` 再做固定分数组合网格。已完成，当前平衡最好的组合是 `k15_bx25_be12`，更激进 comparator 是 `k15_bx20_be10`。
13. 下一步优先做 `trial_008 + k15_bx25_be12` 的固定分数暴露 / 集中度防线 probe，并用 `trial_008 + k15_bx20_be10` 做激进对照，避免继续扩模型 sweep。

不要先做：

* 大范围 XGB sweep
* 新特征
* 新模型
* `latest` asset 下的直接复跑

这些都会让当前最关键的问题变混：

* **ranker 本身有没有稳定排序增量。**

## 14. 第二波邻域与 `trial_008` 组合构造跟进

这轮后续动作分三步：

* 第二波邻域 sweep：`artifacts/sweeps/hk_m_pit_no_ret_ranker_native_r2_fixed20260402/`
* bridge sweep：`artifacts/sweeps/hk_m_pit_no_ret_ranker_native_r3_bridge_fixed20260402/`
* 固定 `trial_008` 的 construction grid：`artifacts/sweeps/hk_m_pit_no_ret_ranker_trial008_construction_r1_fixed20260402/`

### 14.1 第二波邻域给了什么

第二波邻域最重要的结果是把 signal-side 和 implementation-side 的候选分开；objective winner 本身不是重点：

| trial | combo | test IC IR | WF IC mean | final OOS Sharpe | final OOS turnover | final OOS active IR |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `005` | `d2_mcw20_l10_a05_sub07_col07` | `0.38` | `-0.65%` | `1.95` | `17.00%` | `0.05` |
| `008` | `d2_mcw10_l10_a05_sub07_col07` | `0.15` | `0.07%` | `1.99` | `18.36%` | `0.21` |
| `016` | `d2_mcw20_l10_a1_sub07_col07` | `0.35` | `-7.13%` | `2.07` | `16.60%` | `0.38` |

怎么读：

* `trial_005` 证明 `reg_alpha = 0.5` 确实能修一部分 walk-forward IC。
* 但它把 final OOS active IR 从 `0.38` 明显拉低到 `0.05`，所以不能直接替代 `trial_016`。
* `trial_008` 虽然不是 objective winner，但它给出了当时最像 signal-candidate 的平衡：walk-forward IC mean 终于接近转正，同时 OOS Sharpe 和 active IR 还保留住一大段。

对应关键 run：

* `trial_005`：`artifacts/runs/hk_sel_m_tune_hk_m_pit_no_ret_ranker_native_r2_fixed20260402_trial_005_20260413_140040_9089382b/`
* `trial_008`：`artifacts/runs/hk_sel_m_tune_hk_m_pit_no_ret_ranker_native_r2_fixed20260402_trial_008_20260413_140214_b36dc50b/`

### 14.2 Bridge sweep 排除了什么

bridge sweep 的作用是回答：

* `trial_005` 的 walk-forward 修复，能不能和 `trial_016` 的 active IR / implementation 强度合并

结果是否定的。

| trial | combo | WF IC mean | final OOS Sharpe | final OOS active IR |
| --- | --- | ---: | ---: | ---: |
| `001` | `d2_mcw12_l10_a05_sub07_col07` | `-1.94%` | `2.02` | `0.25` |
| `005` | `d2_mcw18_l10_a05_sub07_col07` | `-3.63%` | `1.83` | `-0.02` |
| `006` | `d2_mcw18_l10_a075_sub07_col07` | `-4.42%` | `2.00` | `0.21` |

怎么读：

* 没有一个点能同时优于 `trial_008` 的 signal 证据和 `trial_016` 的 implementation 强度。
* 这一步的研究价值主要是排除了一段中间参数区；它没有给出新默认。

关键 sweep：

* `artifacts/sweeps/hk_m_pit_no_ret_ranker_native_r3_bridge_fixed20260402/`

### 14.3 固定 `trial_008` 后的组合网格

固定 `trial_008` 的模型层后，construction grid 真正给出了可保留的实现增量。

| combo | final OOS Sharpe | final OOS turnover | final OOS active IR | full-sample backtest Sharpe | full-sample backtest IR |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline `k20_bx20_be10` | `1.99` | `18.36%` | `0.21` | `0.35` | `0.35` |
| `k15_bx20_be10` | `2.19` | `18.93%` | `0.58` | `0.42` | `0.47` |
| `k20_bx25_be12` | `2.07` | `16.32%` | `0.43` | `0.33` | `0.31` |
| `k15_bx25_be12` | `2.19` | `15.50%` | `0.38` | `0.39` | `0.44` |
| `k20_bx15_be8` | `1.95` | `21.13%` | `0.31` | `0.36` | `0.35` |
| `k25_bx25_be12` | `2.00` | `17.24%` | `0.39` | `0.33` | `0.33` |

怎么读：

* `k15_bx25_be12` 是最平衡的组合：
  * final OOS Sharpe 与 `k15_bx20_be10` 基本持平
  * turnover 明显更低
  * active IR 明显高于 baseline
* `k15_bx20_be10` 是更激进的 comparator：
  * active IR 最强
  * 但 turnover 没有改善
* `k20_bx25_be12` 是保守备选：
  * turnover 更低
  * 但整体增量不如 `k15_bx25_be12`

对应关键 run：

* baseline `trial_008`：`artifacts/runs/hk_sel_m_tune_hk_m_pit_no_ret_ranker_native_r2_fixed20260402_trial_008_20260413_140214_b36dc50b/`
* `k15_bx25_be12`：`artifacts/runs/hk_sel_m_tune_hk_m_pit_no_ret_ranker_trial008_construction_r1_fixed20260402_trial_004_20260413_152359_03bd4147/`
* `k15_bx20_be10`：`artifacts/runs/hk_sel_m_tune_hk_m_pit_no_ret_ranker_trial008_construction_r1_fixed20260402_trial_002_20260413_152256_67b2d5da/`

### 14.4 和 `trial_016 + k15_bx25_be12` 怎么摆

当前三个最值得保留的点可以这样分层：

| 角色 | 组合 | 主要理由 |
| --- | --- | --- |
| signal + implementation 主候选 | `trial_008 + k15_bx25_be12` | walk-forward IC 证据最干净，同时 OOS Sharpe / turnover / active IR 都有明显实现增量 |
| 激进对照（aggressive comparator） | `trial_008 + k15_bx20_be10` | active IR 最强，但 turnover 没有同步改善 |
| 执行层上限参考（execution ceiling） | `trial_016 + k15_bx25_be12` | OOS Sharpe / active IR 仍是当前上限，但 walk-forward IC 仍明显为负 |

当前最合理的下一步是：

* 固定 `trial_008 + k15_bx25_be12 + groupcap4`
* 用 `trial_008 + k15_bx20_be10 + groupcap4` 当 aggressiveness 对照
* 停止继续扩 construction / guardrail 小网格，转向前瞻跟踪

### 14.5 Guardrail probe 结果

guardrail probe 分两轮：

* `artifacts/sweeps/hk_m_pit_no_ret_ranker_trial008_guardrail_r1_fixed20260402/`
* `artifacts/sweeps/hk_m_pit_no_ret_ranker_trial008_guardrail_r2_micro_fixed20260402/`

第一轮说明：

* `groupcap4` 是有效但温和的约束：
  * `k15_bx25_be12` 下 final OOS Sharpe 基本不变，从 `2.194` 到 `2.198`
  * final OOS active IR 从 `0.384` 降到 `0.337`
  * top industry 名字数从均值约 `4.35`、最高 `6`，压到均值约 `3.61`、最高 `4`
* `groupcap3` 约束太硬：
  * 虽然能把 top industry 名字数压到 `<= 3`
  * 但 `k15_bx25_be12` 下 final OOS active IR 只剩 `0.217`

第二轮 micro 说明：

* `gc4_k15_bx25_be12` 仍是平衡最好的 guarded control。
* `gc4_k15_bx20_be10` 的 active IR 更强，final OOS active IR 约 `0.52`，但 turnover 仍接近 `18.8%`，更适合作为 aggressive comparator。
* `gc4_k20_bx25_be12` 更分散，但 final OOS Sharpe 和 active IR 都明显回落，不值得继续保留成主分支。

所以当前 ranker 线的收口应理解成：

| 角色 | 组合 | 主要理由 |
| --- | --- | --- |
| 带约束候选（guarded challenger） | `trial_008 + k15_bx25_be12 + groupcap4` | 在最小行业约束下保住大部分 Sharpe / turnover / active IR 增量，且 top industry 名字数已压到 `<= 4` |
| 激进对照（aggressive comparator） | `trial_008 + k15_bx20_be10 + groupcap4` | active IR 更强、drawdown 更浅，但换手仍明显更高 |
| 执行层上限参考（execution ceiling） | `trial_016 + k15_bx25_be12` | 纯 OOS 实现仍亮，但 walk-forward IC 仍偏弱 |

### 14.6 主线 vs comparator 稳健性检查清单

在 `positive_cfo_ratio_3y` 和 `positive_cfo_ratio_2y` follow-up 之后，当前 monthly ranker 更准确的两条跟踪线应理解成：

| 角色 | 组合 | 当前定位 |
| --- | --- | --- |
| 主带约束候选（guarded challenger） | `trial_008 + positive_cfo_ratio_3y + k15_bx25_be12 + groupcap4` | 当前主动收益最强、实现层最平衡的正 CFO 版本 |
| 激进对照（aggressive comparator） | `trial_008 + positive_cfo_ratio_2y + k15_bx20_be10 + groupcap4` | 更高 Sharpe、较高 active IR，但故事更偏 implementation |

下一轮不该再继续扩慢因子包，也不该重新开模型大 sweep，而应先完成下面这份稳健性检查。

#### 14.6.1 固定口径

先固定不再变化的东西：

* dated `2026-04-02` asset 口径
* `trial_008` ranker 原生模型参数
* `groupcap4`
* benchmark ladder 与 execution cost 口径
* `final_oos.size = 24`

否则会把“正 CFO 版本差异”和“数据口径漂移”混在一起。

#### 13.6.2 必看结果

每次复核这两条线，先只看下面 6 个指标：

* final OOS `Sharpe`
* final OOS `active IR`
* final OOS `active total return`
* final OOS `avg turnover`
* walk-forward `test IC mean`
* `rows_model` / `rows_model_oos`

原因很简单：

* `3Y` 主线当前赢在 `active IR` 和 `active total return`
* `2Y` aggressive comparator 当前赢在 `Sharpe`
* 两条线都没有真正修好 walk-forward

所以只看 objective 或只看单个 `IC IR` 都会误判。

#### 13.6.3 先做 4 组切片

先不要加新因子，先把这 4 组切片看清楚：

* 最近 `6m`
* 最近 `12m`
* 最近 `24m`
* full final OOS `24m`

每组都对比：

* `Sharpe`
* `active IR`
* `active total return`
* `avg turnover`
* `IC mean`

目标是回答：

* `3Y` 的主动收益优势是不是集中在旧窗口
* `2Y` 的 Sharpe 优势是不是只来自最近一小段

#### 14.6.4 必做 attribution

这两条线至少要补 3 类 attribution：

* 行业：
  看 top industry 名字数、行业贡献和是否仍然被少数行业主导
* 市值 / 风格：
  看大盘、低波、质量暴露是否有明显分化
* 持仓集中：
  看 top 5 symbol contribution share 和单票权重尾部

这里真正要回答的是：

* `3Y` 为什么 active IR 更高
* `2Y` 为什么 Sharpe 更高但主动收益没有同步拉开

#### 14.6.5 实现层检查

两条线都要补这 3 个实现层 sanity check：

* turnover 是否在最近窗口突然抬升
* cost drag 是否明显放大
* aggressive comparator 的高 Sharpe 是否主要靠更低 beta / 更贴 benchmark

如果 `2Y` 的 Sharpe 优势主要来自更低 beta，且 active total return 没有同步更高，就不该把它误读成主线升级。

#### 14.6.6 当前决策规则

在没有新增样本前，当前临时决策规则建议固定成：

* 如果优先看主动收益和更平衡的实现层，继续保留 `3Y` 主线
* 如果优先看更高 Sharpe，并接受更激进 construction，把 `2Y` 保留为 comparator
* 在 walk-forward 没明显修复前，不把任何一条线包装成“已成熟可重仓”的版本

#### 14.6.7 `accrual_ratio` 怎么处理

`accrual_ratio` 现在只保留为 watchlist，不直接并入主线。

理由是：

* 它能把 eval / IC 指标抬高
* 但它没有打赢 `positive_cfo_ratio_3y` control 的 `Sharpe / active IR / active total return`

所以下一步如果碰它，应该当成：

* signal-side watchlist
* 或轻量 filter / gating 候选

避免重新开一个慢因子 pack。

#### 14.6.8 最小对比入口

为了避免每次都手工翻 `summary.json` 和 OOS CSV，当前这两条线的固定对比入口建议直接用：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m csml.research.hk_monthly_run_compare \
  --run main=artifacts/runs/hk_tune_hk_selected_monthly_pit_no_ret_ranker_trial008_gc4_positive_cfo_construction_r1_trial_001_20260413_182023_86054f72 \
  --run comp=artifacts/runs/hk_tune_hk_selected_monthly_pit_no_ret_ranker_trial008_gc4_positive_cfo_construction_r1_trial_004_20260413_182239_fdedb9db \
  --out-dir artifacts/reports/hk_monthly_positive_cfo_compare_20260413
```

这个入口会固定产出两张表：

* `window_metrics.csv`：`6m / 12m / 24m / full` 下的 `Sharpe / active IR / active total return / avg turnover / IC mean / IC IR`
* `attribution_summary.csv`：同样窗口下的轻量 exposure / industry / 持仓持续性摘要

定位上它不是新的主工作流，只是为了把这份稳健性检查清单低摩擦地重复执行。
