# HK Quarterly Benchmark 与解释层（2026-04-05）

> 状态提示：本页属于 active deep-dive，用于把 quarterly 线当前几条最容易混淆的 benchmark / challenger 放回同一解释框架。当前默认研究入口请先读 [hk-quarterly-current-state-20260329.md](./hk-quarterly-current-state-20260329.md)。

本页解决什么：把 quarterly 线当前最相关的主线、结构 challenger、最近 OOS 亮点和纯基本面 sidecar 的角色压成一页，避免把不同问题的答案混成同一种“赢家叙事”。  
本页不解决什么：不替代单次 run 的 `summary.json` / `config.used.yml`，也不把最近亮眼区间重新包装成新证据。  
适合谁：已经看过 quarterly `current-state`，但仍然觉得“为什么这条留着、那条不升级、那条又单开 sidecar”不够直观的人。  
读完你会得到什么：一套更简单的 quarterly 解释框架，知道每条路线在回答什么，以及为什么它们现在不能互相替代。  
相关页面：`docs/research/notes/hk-quarterly-current-state-20260329.md`、`docs/research/notes/hk-quarterly-holdings-analysis-20260329.md`、`docs/research/notes/hk-quarterly-construction-grid-20260329.md`、`docs/research/notes/hk-quarterly-oos-evidence-20260329.md`、`docs/research/notes/hk-quarterly-pure-fundamentals-20260329.md`

页面性质：`research-note`  
状态：`active deep-dive`，这页只做 quarterly 的 benchmark / challenger 解释层，不作为唯一默认入口  
最后核对时间：`2026-04-05`  
权威来源：`hk-quarterly-current-state-20260329.md` 及其引用的 balanced execution run、组合构造跟进页、最近 OOS 边界页和纯基本面路线页  
冲突优先级：如果与具体 run 的 `summary.json` / `config.used.yml` 冲突，以 run 产物为准；如果与更晚的 `current-state` 页面冲突，以更晚页面为准

## 1. 先记住 6 句

* quarterly 当前不是“谁最近最亮谁就升级”，而是几条路线在回答不同问题。
* `ranker h12_w16 + close + balanced execution` 仍是主线，不是因为它完美，而是因为它在现有证据里最稳。
* `reg_zscore h12_w16 + tr_close + balanced execution` 仍是第一 challenger，但它的最近 OOS 亮点不能覆盖前面整段测试和 walk-forward 的弱证据。
* `raw-scale dedup + groupcap3` 更像结构 challenger；它的价值主要在组合修形和持仓稳定性，不是重写信号故事。
* 纯 PIT 基本面路线值得保留，但更适合当独立 benchmark / challenger，不适合直接替掉当前 hybrid 主线。
* 所以当前更需要的是解释层和前瞻样本，而不是继续把不同路线的局部亮点拼成一个“已经验证通过”的总叙事。

## 2. 这几条路线分别在回答什么

### 2.1 主线：`ranker h12_w16 + close + balanced execution`

这条线回答的是：

* 在当前 quarterly hybrid 研究框架里，什么是相对最稳的默认锚点。
* 当我们讨论 `tr_close`、target transform、construction 或新特征时，应该先拿谁做基准。

它的角色是：

* 主 benchmark
* 当前最合理的默认入口

它不回答：

* 最近一段市场里谁最亮
* 纯基本面本身有没有独立 alpha

### 2.2 第一 challenger：`reg_zscore h12_w16 + tr_close + balanced execution`

这条线回答的是：

* target relative 化以后，当前 quarterly overlay 是否有更值得跟踪的回归 challenger。
* `tr_close` 在回归 challenger 上是不是净正向。

它的角色是：

* 正式 challenger
* 最近 regime 下更亮的候选

它不回答：

* 当前是否已经可以替代主线
* 最近 OOS 亮点是否已经足够当证据

### 2.3 结构 challenger：`raw-scale dedup + groupcap3`

这条线回答的是：

* 当前 quarterly 的主要问题，有多少其实来自组合构造和持仓稳定性，而不是模型名字本身。
* 在固定信号后，construction 层是不是还有值得继续做的小范围 follow-up。

它的角色是：

* 组合层 benchmark / challenger
* 用来判断“是否该继续扫模型，还是先修组合结构”

它不回答：

* 新信号是否更强
* 纯基本面能否独立成立

### 2.4 纯 PIT 基本面 sidecar

这条线回答的是：

* 如果把量价拿掉，只看 PIT 财务信息，季度横截面排序还有没有独立信息量。
* 当前 hybrid 结果里，基本面到底是不是只是次要成分。

它的角色是：

* 独立 benchmark / challenger
* 概念验证路线

它不回答：

* 当前 hybrid 主线应该立刻被替换
* 现在就该把纯基本面直接升成主线

## 3. 为什么最近亮点不能直接改写解释

最近 quarterly 最容易把人带偏的点，是把“最近一段 OOS 很亮”误读成“整个研究线已经拿到证据”。

当前更合理的说法还是：

* 最近 regime 下，确实出现了更亮的 challenger
* 但完整测试段和前面 walk-forward 还没有把它洗成稳健主线

所以 quarterly 这条线现在更像：

* 主线有默认锚点
* challenger 有局部亮点
* 结构 challenger 在解释组合层问题
* 纯基本面 sidecar 在回答“基本面本身有没有独立价值”

这些都重要，但不能彼此替代。

## 4. 为什么当前要把 benchmark / 解释层单独抽出来

如果不把解释层单独抽出来，`current-state` 很容易同时承载太多任务：

* 现行口径
* 哪些旧页降级
* 最近 OOS 亮点边界
* 组合构造故事
* 纯基本面路线意义

这会让 `current-state` 重新变成“一个什么都讲一点的大页”，而不是默认入口。

更合理的分工是：

* `current-state`：回答“今天到底该信什么、默认从哪条线出发”
* 本页：回答“这些 benchmark / challenger 为什么要同时保留、但又不能互相替代”
* holdings / construction / OOS / pure fundamentals：分别承接更细的专题解释

## 5. 现在最实用的读法

如果你当前在 quarterly 里看到一个亮点，先问自己它属于哪一类：

1. 如果它只是最近一段 OOS 变亮，先把它归到 challenger 观察，而不是主线升级。
2. 如果它主要改善换手、集中度或持仓稳定性，先把它归到结构 challenger，而不是说信号更强。
3. 如果它完全拿掉量价、只靠 PIT 财务还能站住，再把它当纯基本面 sidecar 的增量证据。

也就是说：

* 不同路线各有价值
* 但它们的价值类型不同

## 6. 一句话结论

quarterly 当前最需要的，不是再多一个“谁赢了”的结论，而是把主线、challenger、结构解释和纯基本面 sidecar 放回同一张图里理解。这样后面无论是继续做组合构造、等新样本，还是单开纯基本面路线，判断都会更干净。
