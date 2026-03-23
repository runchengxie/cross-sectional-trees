# HK 季度 PIT Overlay 失效与抗漂移修正记录（2026-03）

本页记录这条 HK 季度 `PIT core + provider valuation overlay` 研究线的最新结论。

截至 `2026-03-23`，仓库里这条线最新已执行的 run 停在 `2026-03-22`。下文以这批结果为准；如果后续又跑出新实验，应先更新这页，再让其他文档引用它。

相关页面：

* [`docs/research/README.md`](./README.md)
* [`docs/playbooks/hk-selected.md`](../playbooks/hk-selected.md)
* [`docs/config.md`](../config.md)
* [`docs/outputs.md`](../outputs.md)

## 1. 核心结论

如果只看这一页，先记住下面 6 句：

* 旧基线 [`hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker.yml`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker.yml) 在 `final_oos` 已经出现横截面排序失效。它还有 `+45.2%` 的绝对收益，但 `IC = -0.1003`、`long_short = -6.56%`、主动收益 `-10.6%`，说明高分股已经开始跑输低分股。
* 换成 [`xgb_regressor`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_regressor_validate.yml) 或 [`ridge`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_ridge_validate.yml) 后，`final_oos IC` 仍然为负；[`elasticnet`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_elasticnet_validate.yml) 直接退化成常数预测。
* 这轮问题更像 `regime shift / concept drift`。旧训练窗学到的映射关系，在 `2023-12-29` 到 `2025-09-29` 这段真留出集上失效了。
* 只做近期样本加权还不够。`exp_decay` 单独版把负 IC 缓和到 `-0.0597`，但没有修好排序关系。
* 第一版真正把 `final_oos IC` 翻回正值的配置，是 `halflife=12 + rolling=16`。它对应的当前基线是 [`hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_validate.yml`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_validate.yml)。
* 这条线已经进入 `paper -> shadow -> 小仓位 canary` 的准备阶段，但还不支持单模型、唯一主信号、直接大仓上线。

## 2. 问题是什么

这里说的排序失效，而是指模型给高分的股票，整体上已经不再比低分股票更好。

旧基线最关键的异常，是收益和排序开始脱钩：

| 观察点 | 结果 | 含义 |
| --- | --- | --- |
| 旧基线 `final_oos` | `IC = -0.1003`，`long_short = -6.56%`，主动收益 `-10.6%`，但组合绝对收益仍有 `+45.2%` | 市场里还有上涨机会，但模型排序已经失真 |
| 分位收益 | 最低分桶均值 `12.6%`，最高分桶 `6.0%` | 高分股整体上已经跑输低分股 |
| Dense validation | `walk_forward` 的 6 个测试窗 `test_ic` 全为正，但 `final_oos IC` 仍是 `-0.0926` | 更像是新阶段出现了 regime shift，而不是旧阶段就一直无效 |
| 执行完整性 | `backtest_periods_oos.csv` 里 `exit_delay_steps` 全为 `0` | 这次负 IC 不能归因到执行 bug |

当前更准确的说法是：

* 旧模型会把排序逻辑和市场贝塔混在一起。
* 如果后续还只盯 `total_return`，很容易误把阶段性行情当成模型有效。

## 3. 为什么判断是漂移

同一条数据路线换模型后，问题仍然存在：

| 配置 | `final_oos IC` | `final_oos long_short` | 主动收益 | 当前定位 |
| --- | --- | --- | --- | --- |
| [`xgb_ranker` 旧基线](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker.yml) | `-0.1003` | `-6.56%` | `-10.6%` | 旧基线已失效 |
| [`xgb_regressor` 对照](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_regressor_validate.yml) | `-0.0951` | `-4.83%` | `-15.4%` | 证明这不是 ranker 特有问题 |
| [`ridge` 对照](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_ridge_validate.yml) | `-0.1159` | `-4.49%` | `+3.30%` | 可以做温和 sleeve，不是修复方案 |
| [`elasticnet` 对照](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_elasticnet_validate.yml) | `NaN` | 退化 | `pred_nunique = 1` | 当前口径下应排除 |

从这组结果能得出两点：

* 主要矛盾是训练窗里的旧关系污染了新阶段
* 这轮研究的主线应该是怎么改训练机制，切换模型（ `ranker / regressor / linear` ）并不能实质上解决问题

## 4. 什么方案真正开始修复问题

这一段只保留已经跑完、并且对决策有直接价值的结论。

| 配置 | `final_oos IC` | `final_oos long_short` | 主动收益 | 当前结论 |
| --- | --- | --- | --- | --- |
| 旧基线 | `-0.1003` | `-6.56%` | `-10.6%` | 排序失效 |
| [`exp_decay`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_exp_decay_validate.yml) | `-0.0597` | `-2.11%` | `-9.50%` | 方向改善，但还不够 |
| [`exp_decay + rolling=16`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_exp_decay_rolling_validate.yml) | `+0.0825` | `+0.68%` | `+13.7%` | 第一版真正翻正，应提升为新基线 |
| [`exp_decay + rolling=16 + group cap=3`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_exp_decay_rolling_groupcap_validate.yml) | `+0.0825` | `+0.68%` | `+6.9%` | 信号没变，但收益和夏普下降，不适合默认开启 |

这组结果的实际含义是：

* `exp_decay` 单独版说明“近期样本更重要”这个方向是对的。
* 真正起决定作用的是 `rolling` 主训练窗。只给近期样本更高权重还不够，还要把更早的数据直接丢掉。
* 组合层 `group cap` 可以当风险控制工具，但它没有修复信号本身，所以不该被表述成主解。

还要保留两条克制：

* 这批 `final_oos` 只有 `8` 个 rebalance 日期，统计把握还不硬。
* `h12_w16` 的分位收益还不是完全单调，`Q4` 仍略高于 `Q5`。所以更准确的说法是“信号开始恢复”，不是“因子已经完全稳定”。

## 5. 当前推荐怎么用

`2026-03-22` 这天，`halflife × rolling_window` 的 `3 × 3` 参数点已经全部执行完。全量结果里最实用的结论不是“谁回测最高”，而是“谁最适合拿去做下一阶段的低风险验证”。

### 5.1 当前默认基线

当前默认基线是：

* [`hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_validate.yml`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_validate.yml)

它等价于：

* `halflife = 12`
* `rolling train_window.size = 16`

推荐它是因为它在下面几项上同时过线：

* `final_oos IC = +0.0825`
* `walk_forward` 6 个测试窗 `test_ic` 全正
* `walk_forward` 6 个窗的 `signal_direction` 全是 `-1.0`
* `final_oos beta = 0.44`
* `final_oos` 没有延迟退出

一句话概括：`h12_w16` 是当前最均衡、最适合做 canary 的版本。

### 5.2 当前更实用的分工

| 版本 | 当前角色 | 关键原因 |
| --- | --- | --- |
| [`h12_w16`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_validate.yml) | 默认 canary 基线 | `final_oos IC` 最高，`walk_forward` 最稳定，方向没有来回翻 |
| [`h06_w16`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h06_w16_validate.yml) | 并行 challenger | 收益弹性最强，`final_oos long_short = +4.33%`、主动收益 `+30.9%`，但最后一窗方向翻到 `1.0`，稳定性略弱 |
| [`h12_w12`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w12_validate.yml) | 偏防守备选 | `max_drawdown = -1.75%`，但 `cv_ic` 近零，`walk_forward` 有 `4` 正 `2` 负 |
| [`h18_w12`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h18_w12_validate.yml) | 研究池保留 | `final_oos` 不差，但 `walk_forward` 已经是 `3` 正 `3` 负，方向切换更明显 |

这轮 9 个点里还有两个额外信息值得保留：

* `rolling = 20` 的三个点都重新回到了 `final_oos IC < 0`，说明窗口一拉长，旧 regime 污染又回来了。
* [`h18_w16`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h18_w16_validate.yml) 虽然 `final_oos IC` 仍为正，但 `long_short` 已经转负，不适合升级成默认基线。

所以当前更稳妥的顺序是：

1. `h12_w16` 先做 `paper -> shadow -> 小仓位 canary`
2. `h06_w16` 作为并行 challenger
3. `h12_w12` 作为防守型备选
4. 其余点继续留在研究池，不直接升为默认配置

## 6. 如果进入 canary，应该盯什么

无论最终先上哪个版本，至少固定监控下面 4 类信号：

* 排序是否继续有效：连续 `2` 期 `IC < 0`，或连续 `2` 期 `top_k_positive_ratio < 50%`，就要重新评估。
* 主动收益是否重新退化成高 beta 暴露：如果组合绝对收益还在，但主动收益转负、`beta` 明显向 `1` 靠近，说明排序可能又开始漂了。
* 方向是否重新乱跳：`cv_ic`、最近几窗 `walk_forward test_ic`、live 打分方向如果互相冲突，要优先排查。
* 行业暴露是否过度集中：即使默认不启用 `group cap`，也要持续看前 `20` 持仓的行业分布，避免组合重新退化成主题押注。

## 7. 历史实验归档

下面这些实验已经完成。它们仍然有价值，但更适合放在附录。

| 实验 | 它回答了什么 | 当前一句话结论 |
| --- | --- | --- |
| [`validate_dense_wf`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_validate_dense_wf.yml) | 负 IC 是不是真问题 | 是真问题；更密的 `walk_forward` 只让漂移画像更清楚 |
| [`xgb_regressor_validate`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_regressor_validate.yml) | 是不是 ranker 特别脆 | 不是；回归器也一起失真 |
| [`ridge_validate`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_ridge_validate.yml) | 简单线性映射会不会更稳 | 能当温和 sleeve，但没有修复排序 |
| [`elasticnet_validate`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_elasticnet_validate.yml) | 稀疏线性模型能不能更稳 | 当前口径下直接退化，应排除 |
| [`construction_grid`](../../configs/experiments/sweeps/hk_selected__quarterly_pit_core_hybrid_provider_overlay_construction_grid.yml) | 只调 `top_k / buffer` 有多大帮助 | 只有二阶影响；`top_k = 20` 好于 `25`，`buffer` 基本不改结论，而且这张表只覆盖 `2` 个 backtest periods，不适合过度外推 |

## 8. 复现入口

如果只是复现当前主结论，优先跑下面这些配置：

* 旧基线：[`hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker.yml`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker.yml)
* 标准诊断：[`hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_validate_dense_wf.yml`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_validate_dense_wf.yml)
* 当前抗漂移基线：[`hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_validate.yml`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_validate.yml)
* 当前三个最值得继续观察的点：[`h12_w16`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_validate.yml)、[`h06_w16`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h06_w16_validate.yml)、[`h12_w12`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w12_validate.yml)

如果只是看文档层面的最新建议，不需要再从头阅读旧的实验流水账；本页已经把当前仍然有效的信息整理成了最终口径。
