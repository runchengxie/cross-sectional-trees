# HK Monthly trial016 CFO2Y 组合层 guardrail 复核（2026-04-20）

> 状态提示：本页属于 active deep-dive，用于记录 `trial016` 与 `positive_cfo_ratio_2y` 的关系、这次 fixed-score overlay 复核结果，以及为什么当前只建议文档化，不建议马上工具化。当前 monthly 默认入口仍是 [hk-monthly-current-state-20260330.md](./hk-monthly-current-state-20260330.md)。

本页解决什么：回答“`trial016_construction_r1_fixed20260402_trial_002` 是否用了 2 年慢基本面因子，以及 `positive_cfo_ratio_2y` 是否值得作为实盘组合层优化”。

本页不解决什么：不把 ad hoc overlay runner 升级成正式 `construction-grid` 能力，也不把本次 fixed-score overlay 直接包装成 live-ready 生产配置。

适合谁：已经看过 [hk-monthly-ranker-ab-and-next-sweep-20260413.md](./hk-monthly-ranker-ab-and-next-sweep-20260413.md)，并想核对 `trial016`、`2Y CFO` 和当前最有实盘前景月频候选之间关系的人。

读完你会得到什么：`trial016` 没有直接使用 `positive_cfo_ratio_2y` 的确认、直接加特征为什么不理想、轻量 CFO2Y floor 为什么值得保留为组合层 guardrail，以及下一步何时才该工具化。

相关页面：[hk-monthly-current-state-20260330.md](./hk-monthly-current-state-20260330.md)、[hk-monthly-ranker-ab-and-next-sweep-20260413.md](./hk-monthly-ranker-ab-and-next-sweep-20260413.md)、[hk-monthly-slowfund-five-line-wrap-up-20260413.md](./hk-monthly-slowfund-five-line-wrap-up-20260413.md)、[../README.md](../README.md)

页面性质：`research-note`

状态：`active deep-dive`

最后核对时间：`2026-04-20`

权威来源：本页列出的 run 目录下 `summary.json` / `config.used.yml`，以及 `artifacts/reports/trial016_cfo2y_overlay_robustness_20260420_grid.csv`、`artifacts/reports/trial016_cfo2y_overlay_robustness_20260420_summary.csv`

冲突优先级：如果与具体 run 的 `summary.json` / `config.used.yml` 冲突，以 run 产物为准；如果与后续更晚 OOS、live snapshot 或正式工具化结果冲突，以更晚结果为准

## 1. 先说结论

这次最重要的结论有三条：

* `trial016_construction_r1_fixed20260402_trial_002` 没有直接使用 `positive_cfo_ratio_2y`；它的 `final_oos.size: 24` 是 OOS 评估长度，不是 2 年慢因子窗口。
* 把 `positive_cfo_ratio_2y` 直接加进 `trial016` 模型特征，不是一个好升级：IC、OOS long-short 和 active IR 都被稀释。
* 把 `positive_cfo_ratio_2y` 放在组合层做轻量 rank floor，则值得保留：当前最平衡版本是先排掉 CFO2Y 横截面底部约 `10%`，再按原 `trial016` 分数选 `top_k=15`。

一句话收口：

* `positive_cfo_ratio_2y` 当前更适合做 `trial016` 的防守型组合层 guardrail，而不是作为 `trial016` 的新 alpha 特征。

## 2. 这次到底比了什么

统一比较口径：

* 固定 `trial016_construction_r1_fixed20260402_trial_002` 的 scored signal
* 使用同一份 final OOS pricing / benchmark context
* 只改组合层选股方式
* 额外从 CFO2Y run 的 scored artifact 合并 `positive_cfo_ratio_2y`
* 成本压力测试使用成本倍率 `1.0 / 1.5 / 2.0`
* topK 测试使用 `10 / 12 / 15 / 18 / 20`

主要来源：

* base scored run：`artifacts/runs/hk_attr_trial016_final_oos_scored_for_overlay_20260419_212633_2278c080`
* CFO2Y scored run：`artifacts/runs/hk_attr_trial016_plus_cfo2y_final_oos_scored_for_overlay_20260419_211034_366dfb8f`
* robustness grid：`artifacts/reports/trial016_cfo2y_overlay_robustness_20260420_grid.csv`
* robustness summary：`artifacts/reports/trial016_cfo2y_overlay_robustness_20260420_summary.csv`

## 3. 直接加特征为什么不升级

`positive_cfo_ratio_2y` 直接作为模型特征加入 `trial016` 后，结果不像主线升级：

| line | eval IC | CV IC | WF IC | OOS IC | OOS L/S | full active IR | OOS active IR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base `trial016` | `0.0499` | `0.0257` | `-0.0713` | `0.0936` | `0.0073` | `0.5993` | `0.4355` |
| `trial016 + CFO2Y feature` | `0.0220` | `0.0170` | `-0.0317` | `0.0651` | `-0.0034` | `0.5511` | `0.2808` |

它确实有一些防守特征：

* OOS Sharpe 从 `2.15` 到 `2.38`
* OOS 最大回撤从 `-7.52%` 到 `-5.35%`
* beta 从约 `0.90` 降到更低

但作为 alpha feature 的代价太明显：

* eval / CV / OOS IC 都下降
* OOS long-short 转负
* active IR 下降

所以它不该被写成“`trial016` 使用 2Y 慢因子后更强”。更准确的说法是：

* `CFO2Y` 有防守属性，但直接并入模型会稀释 `trial016` 的排序信号。

## 4. 轻量 floor 的结果

当前最实用的 overlay 是：

* 每个 rebalance date 内，对 `positive_cfo_ratio_2y` 做横截面 percentile rank
* 先排掉 CFO2Y rank 底部约 `10%`
* 在剩余池子里按原 `trial016` score 选 `top_k=15`
* 不改变原模型、不改变训练、不改变 alpha score

核心结果如下：

| 方案 | 总收益 | Sharpe | 最大回撤 | 平均换手 | 主动收益 | 主动 IR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 原 `trial016 top15` | `125.56%` | `2.153` | `-7.52%` | `16.97%` | `9.75%` | `0.438` |
| `CFO2Y rank floor top15` | `127.33%` | `2.182` | `-6.29%` | `16.26%` | `12.17%` | `0.563` |

这组改善比较干净：

* 总收益小幅提高
* Sharpe 小幅提高
* 最大回撤改善约 `1.23pct`
* 平均换手下降约 `0.71pct`
* 主动收益提高约 `2.42pct`
* 主动 IR 从 `0.438` 到 `0.563`

持仓层面也不是换成另一套组合：

* 与原 base 的平均 Jaccard overlap 约 `0.919`
* 每期约 `15` 个持仓里，平均仍有 `13.25` 个名字重合

这说明它更像最小 guardrail，而不是另起一条信号。

## 5. 成本压力测试怎么读

在 `top_k=15`、CFO2Y rank floor `0.1` 的口径下，成本放大后仍然相对同成本 base 有增量：

| 成本倍率 | 总收益 | Sharpe | 最大回撤 | 平均换手 | 主动收益 | 主动 IR | 相对 base 主动 IR 增量 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `1.0x` | `127.33%` | `2.182` | `-6.29%` | `16.26%` | `12.17%` | `0.563` | `+0.126` |
| `1.5x` | `125.25%` | `2.159` | `-6.40%` | `16.26%` | `11.15%` | `0.521` | `+0.125` |
| `2.0x` | `123.19%` | `2.137` | `-6.51%` | `16.26%` | `10.15%` | `0.479` | `+0.124` |

这不是靠降低成本倍率“挤出来”的结果。成本放大到 `2x` 后，仍然同时满足：

* 总收益高于同成本 base
* Sharpe 高于同成本 base
* 最大回撤更浅
* 平均换手更低
* 主动 IR 更高

## 6. topK 和阈值怎么读

`top_k=12` 的主动 IR 更高，但不一定更适合实盘主线：

| 方案 | 成本倍率 | 总收益 | Sharpe | 最大回撤 | 平均换手 | 主动 IR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `rank_floor 0.1 / top12` | `1.0x` | `127.27%` | `2.089` | `-8.00%` | `20.87%` | `0.612` |
| `rank_floor 0.1 / top15` | `1.0x` | `127.33%` | `2.182` | `-6.29%` | `16.26%` | `0.563` |

所以 `top12` 可以进 aggressive comparator，但不该替代 `top15` 主候选。

阈值方面：

* `rank_floor 0.1 / 0.2 / 0.3 / 0.4` 在当前 final OOS 的 `top15` 组合结果相同，说明底部 CFO2Y 名字本来就很少进入最终持仓。
* `rank_floor 0.5+` 或 `value_floor >= 0` 会显著提高主动收益 / 主动 IR，但 Sharpe 和最大回撤明显恶化。
* `value_floor -0.04 / -0.05 / -0.06 / -0.07 / -0.08` 稳健性不够，换手或主动表现都不如轻量 rank floor。

因此当前最保守、最不容易过拟合的表达不是“找到精确阈值”，而是：

* CFO2Y 只用来排掉横截面最差的一小段，不要让它主导排序。

## 7. 为什么现在不工具化

现在不建议马上把这层 overlay 升级成正式 `construction-grid` 能力。

原因是这次发现仍然是具体候选上的组合层 guardrail，还不是通用研究能力。若要正式工具化，至少要设计清楚：

* 如何从另一个 scored artifact 合并辅助因子
* live 选股时如何拿到同一辅助因子
* 横截面 rank floor 与 missing value 的默认处理
* 多因子 filter 的顺序
* 输出报告中如何记录过滤前后 universe / holdings overlap
* 正式配置如何避免隐式依赖本地 artifact

这些都能做，但现在还不该为了一次 fixed-score overlay 就扩公开 API。

当前建议是：

* 先把本页作为研究证据保存。
* 保留 ad hoc runner 和 robustness report 作复核材料。
* 等新样本、另一个独立候选或 live snapshot 也确认有效后，再考虑给 `construction-grid` 增加 `pre_filter` / `rank_floor` 能力。

## 8. 当前决策规则

现阶段建议这样落地：

* 主候选：`trial016_construction_r1_fixed20260402_trial_002 + CFO2Y rank floor 0.1 + top_k=15`
* aggressive comparator：同样 floor，但 `top_k=12`
* 不升级：`trial016 + CFO2Y feature`
* 不升级：硬 `value_floor`、`rank_floor 0.5+`、或 blend score
* 不工具化：先不把 overlay 写进正式 `construction-grid`

如果后续要把它推进到 shadow / paper 之外，先补三类证据：

* 新样本：至少多几个 rebalance dates，确认不是 final OOS 末段偶然结果。
* 另一个候选：看 CFO2Y floor 是否只对 `trial016` 有效。
* live 口径：确认当前 live snapshot 能稳定取得 `positive_cfo_ratio_2y`，且缺失处理不会改变候选池语义。

## 9. 一句话结论

`trial016` 没有直接用 2 年慢因子；`positive_cfo_ratio_2y` 直接加进模型不值得升级，但作为轻量组合层 floor 能在当前 final OOS 同时改善收益、Sharpe、回撤、换手和主动 IR。现在最合理的动作是先文档化并保留为 guardrail 候选，等新增样本确认后再决定是否工具化。
