# HK Quarterly PIT 目标设计与方向切换总结（2026-03-24）

本页解决什么：把这轮 HK quarterly PIT + overlay 研究里关于 `label`、模型目标、方向切换和当前基线判断的结论收成一页。
本页不解决什么：不展开 CLI、配置字段细节，也不替代逐次 run 的原始实验记录。
适合谁：已经看过部分实验，但想快速知道“现在到底该怎么理解、怎么用”的读者。
读完你会得到什么：一套当前阶段可执行的研究口径，以及下一步优先级。
相关页面：`docs/research/hk-quarterly-pit-regime-shift-202603.md`、`docs/research/hk-h12-w16-target-transform-review-20260324.md`、`docs/concepts/model-selection.md`、`docs/concepts/benchmark-protocol.md`

页面性质：`research-note`
最后核对时间：`2026-03-24`
权威来源：当前研究 run、follow-up 配置和本页引用的汇总结果
冲突优先级：如果与具体 run 的 `config.used.yml` / `summary.json` 冲突，以 run 产物为准；如果与当前 playbook 冲突，以 playbook 的最新收口为准

## 1. 先记住 8 句

* `xgb_regressor + future_return` 不等于“预测相对排名”；它是在做绝对收益回归。
* “对收益率做横截面标准化，再预测相对排名”这条路，放到本项目里更接近 `xgb_regressor + zscore/rank train target`，或直接用 `xgb_ranker`。
* 绝对收益思路不是错路。它保留了幅度信息，也仍然是有价值的 benchmark。
* 但在这条 HK quarterly PIT + overlay 研究单元里，`raw target` 明显不够稳；把训练目标相对化后，regressor 结果确实变好了。
* 目前 regressor 路线的顺序已经比较清楚：`zscore > rank > raw`。
* 当前最稳的主基线仍然是 `xgb_ranker + h12_w16`；当前最值得继续追的 challenger 是 `xgb_regressor + zscore target + h12_w16`。
* `zscore regressor` 这条线出现了明显的阶段性方向切换：`2021-03-31` 到 `2023-09-29` 更像该用 `-1`，`2023-12-29` 到 `2025-09-29` 又更像该用 `+1`。
* 所以下一阶段不该撤掉 ranker 基线；更合理的做法是“主线继续押 ranker，副线继续研究相对化 target 和方向规则”。

## 2. 三种训练目标在本项目里分别是什么

| 路线 | 本项目里的对应方式 | 模型在学什么 | 当前理解 |
| --- | --- | --- | --- |
| 绝对收益回归 | `xgb_regressor + future_return` | “以后大概涨多少” | 保留幅度信息，适合做 benchmark，但在这条研究单元里稳定性偏弱 |
| 相对强弱回归 | `xgb_regressor + train_target_transform: zscore/rank` | “同一天里大概强多少” | 已经被实验支持，`zscore` 当前最好 |
| 直接排序学习 | `xgb_ranker + trade_date grouping` | “同一天谁该排前面” | 最贴近截面选股目标，当前仍是主基线 |

这里最容易混淆的一点是：

* `xgb_regressor` 本身不自动等于“相对排名学习”
* 关键在于它吃进去的训练标签是什么
* 只有当训练标签先做了每期横截面 `zscore/rank` 变换时，它才开始接近“相对强弱”这条思路

## 3. 为什么“相对化 label”值得加入框架

从研究逻辑上，它值得加，原因主要有三点：

* 截面选股最终关心的是同日谁更强，不一定需要模型死磕一个绝对收益点数。
* 每期先做 `zscore` 或 `rank`，能减少不同日期之间量纲变化和肥尾样本的干扰。
* 它和最终的 `IC / Top-K / long_short` 这类评价口径更贴近。

但这条路也不等于“绝对收益路线应该被废掉”：

* 绝对收益保留了幅度信息，对后续 `signal` 类权重仍有价值。
* 在这个项目里，绝对收益回归仍然应保留为 benchmark，而不是直接删掉。

所以更准确的定位是：

* `raw target` 是 benchmark 思路
* `rank/zscore target` 是值得正式加入的 challenger 思路

## 4. 已有实验到底说明了什么

### 4.1 第一轮四路对照

同一条 `h12_w16` anti-drift 骨架下，四路结果已经把方向拉开了：

| Arm | CV IC | Eval IC | WF 平均 Test IC | Final OOS IC | 全样本 Active Return |
| --- | ---: | ---: | ---: | ---: | ---: |
| Anchor ranker | 0.0492 | 0.0225 | 0.0611 | 0.0825 | -0.0277 |
| Regressor raw | 0.0359 | -0.0618 | -0.0100 | 0.0986 | 0.0195 |
| Regressor rank | 0.0698 | -0.0037 | 0.0199 | 0.0965 | -0.1064 |
| Regressor zscore | 0.0961 | -0.0061 | 0.0560 | 0.0911 | 0.1766 |

这轮最重要的结论不是“最近谁涨得更多”，而是：

* `raw target` 在这条研究单元里明显不稳
* `rank target` 已经比 `raw target` 更像样
* `zscore target` 又进一步强于 `rank target`
* 但 `anchor ranker` 仍然是最稳的主基线

### 4.2 第二轮小扫

围绕 `zscore regressor` 做 `halflife × train_window` 的小范围 follow-up 后，结果更清楚了：

* `train_window=16` 明显优于 `20`
* `w12` 没有打出比 `w16` 更强的综合表现
* `zscore h12_w16` 是更均衡的 challenger
* `zscore h18_w16` 是近期最亮的 challenger

所以 regressor 路线当前最值得保留的两个点是：

* `reg_zscore_h12_w16`
* `reg_zscore_h18_w16`

### 4.3 第三轮最小复验

`anchor ranker h12_w16`、`reg_zscore_h12_w16`、`reg_zscore_h18_w16` 的第三轮复验把上一轮结果原样复现了。

这一步的意义不是产生新赢家，而是确认：

* 当前排序没有因为一次偶然 run 改变
* `anchor ranker` 仍是主基线
* `reg_zscore_h12_w16` 仍是主 challenger

## 5. 方向实验告诉了什么

专门对 `reg_zscore_h12_w16` 跑 `auto_cv / fixed +1 / fixed -1` 后，结论已经很明确：

| Direction 设置 | Eval IC | Final OOS IC | WF 平均 Test IC | 当前解释 |
| --- | ---: | ---: | ---: | --- |
| `auto_cv` | -0.0061 | 0.0911 | 0.0560 | 整体验证更像 `+1`，但 6 个 WF 窗口都选成 `-1` |
| `fixed +1` | -0.0061 | 0.0911 | -0.0560 | 最近阶段对，但较早阶段错 |
| `fixed -1` | 0.0061 | -0.0911 | 0.0560 | 较早阶段对，但最近阶段错 |

这组结果最重要的含义是：

* 这更像**真的发生了阶段性方向切换**
* 不是“自动判方向的方法在乱跳”

更白话地说：

* `2021-03-31` 到 `2023-09-29` 这段，分数越高更像代表“弱”，所以更该用 `-1`
* `2023-12-29` 到 `2025-09-29` 这段，分数越高又更像代表“强”，所以更该用 `+1`

这说明同一个模型分数，在不同阶段的经济含义变了。更贴切的说法不是“模型突然坏了”，而是“市场换了口味”。

## 6. 为什么 ranker h12_w16 还能这么强

`ranker h12_w16` 不是完全免疫市场切换，但它比 regressor 更抗这种切换。

最简单的理解是：

* regressor 更像在猜“未来涨多少”
* ranker 更像只回答“今天这堆股票里谁该排前面”

在市场切换时，先失真的往往是“涨多少”这种绝对映射；“谁相对更强”通常更容易保住。

`ranker h12_w16` 当前还能稳住，主要靠三点：

* 它的目标函数更贴近截面选股最终任务
* 它按 `trade_date` 分组学同日排序，较少受跨日期收益尺度变化影响
* `h12_w16` 这套 anti-drift 机制让它更依赖近阶段样本，同时又不把窗口拉得太长

所以更准确的表述不是：

* “ranker 完全没有方向问题”

而是：

* “在同样的市场切换下，ranker 保住了更多相对排序能力，因此仍然是当前更稳的主基线”

## 7. 当前该怎么用

当前最合适的定位是：

* 主基线：`xgb_ranker h12_w16`
* 主 challenger：`xgb_regressor + zscore target + h12_w16`
* 次 challenger：`xgb_regressor + zscore target + h18_w16`
* 降级路线：`xgb_regressor + raw target`

如果要把它们放进执行优先级：

1. `ranker h12_w16` 继续作为 `paper -> shadow -> 小仓位 canary` 的主方案。
2. `reg_zscore_h12_w16` 继续作为最值得跟踪的 challenger。
3. `reg_zscore_h18_w16` 保留在研究池，但不替代主基线。
4. 不要因为 regressor 近期亮眼就撤掉 ranker 基线。

## 8. 下一步优先级

当前更合理的下一步，不是继续重复同配置，而是分成主线和副线：

* 主线：继续押 `ranker h12_w16`
* 副线：继续研究“相对化 target + 方向规则”

方向规则这条副线，建议从简单规则开始，不要一上来就做复杂的 regime classifier：

* 用最近若干个 rebalance 的 IC 符号决定 `+1 / -1`
* 用最近一段 `Top-K active return` 的符号决定 `+1 / -1`
* 尽量把它设计成模型无关的上层规则，而不是只给 regressor 打补丁

一句话收口：

* 相对化 label 已经从“一个想法”升级成“正式研究主线之一”
* 但当前真正能扛住市场切换、最适合继续向前推进的主方案，仍然是 `ranker h12_w16`
