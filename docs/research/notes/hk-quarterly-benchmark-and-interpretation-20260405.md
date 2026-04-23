# HK Quarterly Benchmark 与解释层（2026-04-05）

> 状态提示：本页属于专题分析（`active deep-dive`），用于把 quarterly 线当前几条容易混淆的基准路线和候选路线放回同一解释框架。当前默认研究入口请先读 [hk-quarterly-current-state-20260329.md](./hk-quarterly-current-state-20260329.md)。

本页解决什么：把 quarterly 线当前最相关的主线、结构候选、最近 OOS 亮点和纯基本面辅助路线的角色压成一页，避免把不同问题的答案混成同一种“赢家叙事”。
本页不解决什么：不替代单次 run 的 `summary.json` / `config.used.yml`，也不把最近亮眼区间重新包装成新证据。  
适合谁：已经看过 quarterly `current-state`，但仍然觉得“为什么这条留着、那条不升级、那条又单开辅助路线”不够直观的人。
读完你会得到什么：一套更简单的 quarterly 解释框架，知道每条路线在回答什么，以及为什么它们现在不能互相替代。  
相关页面：`docs/research/notes/hk-quarterly-current-state-20260329.md`、`docs/research/notes/hk-quarterly-holdings-analysis-20260329.md`、`docs/research/notes/hk-quarterly-construction-grid-20260329.md`、`docs/research/notes/hk-quarterly-oos-evidence-20260329.md`、`docs/research/notes/hk-quarterly-pure-fundamentals-20260329.md`

页面性质：`research-note`  
状态：`active deep-dive`，这页只做 quarterly 的基准 / 候选路线解释层，不作为默认入口
最后核对时间：`2026-04-05`  
权威来源：`hk-quarterly-current-state-20260329.md` 及其引用的 balanced execution run、组合构造跟进页、最近 OOS 边界页和纯基本面路线页  
冲突优先级：如果与具体 run 的 `summary.json` / `config.used.yml` 冲突，以 run 产物为准；如果与更晚的 `current-state` 页面冲突，以更晚页面为准

## 1. 术语速查

| 本页写法 | 含义 |
| --- | --- |
| 基准路线（benchmark） | 用来做对照的默认锚点 |
| 候选路线（challenger） | 有局部亮点，仍需继续验证的路线 |
| 结构候选（structural challenger） | 主要改善组合构造或持仓稳定性的路线 |
| 辅助路线（sidecar） | 独立回答一个问题，暂不替换主线 |
| 最终留出期（final OOS） | 不能参与训练或调参的最终评估区间 |

## 2. 先记住 6 句

* quarterly 当前有几条路线在回答不同问题，不能按“谁最近最亮谁就升级”处理。
* `ranker h12_w16 + close + balanced execution` 仍是主线，因为它在现有证据里最稳。
* `reg_zscore h12_w16 + tr_close + balanced execution` 仍是第一候选路线，但它的最近 OOS 亮点不能覆盖前面整段测试和 walk-forward 的弱证据。
* `raw-scale dedup + groupcap3` 更像结构候选；它的价值主要在组合修形和持仓稳定性，不负责重写信号故事。
* 纯 PIT 基本面路线值得保留，更适合当独立基准或候选路线，不适合直接替掉当前 hybrid 主线。
* 当前更需要解释层和前瞻样本，避免把不同路线的局部亮点拼成一个“已经验证通过”的总叙事。

## 3. 这几条路线分别在回答什么

### 3.1 主线：`ranker h12_w16 + close + balanced execution`

这条线回答的是：

* 在当前 quarterly hybrid 研究框架里，什么是相对最稳的默认锚点。
* 当我们讨论 `tr_close`、target transform、construction 或新特征时，应该先拿谁做基准。

它的角色是：

* 主基准
* 当前最合理的默认入口

边界：

* 最近一段市场里谁最亮
* 纯基本面本身有没有独立 alpha

### 3.2 第一候选路线：`reg_zscore h12_w16 + tr_close + balanced execution`

这条线回答的是：

* target relative 化以后，当前 quarterly overlay 是否有更值得跟踪的回归候选路线。
* `tr_close` 在回归候选路线上的效果是否为净正向。

它的角色是：

* 正式候选路线
* 最近 regime 下更亮的候选

边界：

* 当前是否已经可以替代主线
* 最近 OOS 亮点是否已经足够当证据

### 3.3 结构候选：`raw-scale dedup + groupcap3`

这条线回答的是：

* 当前 quarterly 的主要问题，有多少来自组合构造和持仓稳定性。
* 在固定信号后，组合构造层是否还有值得继续做的小范围跟进。

它的角色是：

* 组合层基准 / 候选路线
* 用来判断“是否该继续扫模型，还是先修组合结构”

边界：

* 新信号是否更强
* 纯基本面能否独立成立

### 3.4 纯 PIT 基本面辅助路线

这条线回答的是：

* 如果把量价拿掉，只看 PIT 财务信息，季度横截面排序还有没有独立信息量。
* 当前 hybrid 结果里，基本面是否只是次要成分。

它的角色是：

* 独立基准 / 候选路线
* 概念验证路线

边界：

* 当前 hybrid 主线应该立刻被替换
* 现在就该把纯基本面直接升成主线

## 4. 为什么最近亮点不能直接改写解释

最近 quarterly 最容易把人带偏的点，是把“最近一段 OOS 很亮”误读成“整个研究线已经拿到证据”。

当前更合理的说法还是：

* 最近 regime 下，确实出现了更亮的候选路线
* 但完整测试段和前面 walk-forward 还没有把它洗成稳健主线

所以 quarterly 这条线现在更像：

* 主线有默认锚点
* 候选路线有局部亮点
* 结构候选在解释组合层问题
* 纯基本面辅助路线在回答“基本面本身有没有独立价值”

这些都重要，但不能彼此替代。

## 5. 为什么当前要把基准解释层单独抽出来

如果不把解释层单独抽出来，`current-state` 很容易同时承载太多任务：

* 现行口径
* 哪些旧页降级
* 最近 OOS 亮点边界
* 组合构造故事
* 纯基本面路线意义

这会让 `current-state` 重新变成“一个什么都讲一点的大页”，削弱默认入口的作用。

更合理的分工是：

* `current-state`：回答“今天到底该信什么、默认从哪条线出发”
* 本页：回答“这些基准和候选路线为什么要同时保留、但又不能互相替代”
* holdings / construction / OOS / pure fundamentals：分别承接更细的专题解释

## 6. 现在最实用的读法

如果你当前在 quarterly 里看到一个亮点，先问自己它属于哪一类：

1. 如果它只是最近一段 OOS 变亮，先把它归到候选路线观察，暂不升级主线。
2. 如果它主要改善换手、集中度或持仓稳定性，先把它归到结构候选，暂不说信号更强。
3. 如果它完全拿掉量价、只靠 PIT 财务还能站住，再把它当纯基本面辅助路线的增量证据。

也就是说：

* 不同路线各有价值
* 但它们的价值类型不同

## 7. 一句话结论

quarterly 当前最需要的是把主线、候选路线、结构解释和纯基本面辅助路线放回同一张图里理解。这样后面无论是继续做组合构造、等新样本，还是单开纯基本面路线，判断都会更干净。
