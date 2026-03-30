# HK Monthly PIT Slow-Sleeve Probe（2026-03-30）

本页解决什么：回答“如果更接近主观投资风格，`M-PIT` 应该走季度调仓还是月度调仓 + 滚动评估”这个问题，并记录第一轮 `slow sleeve` 组合构造实验。  
本页不解决什么：不替代 `M-PIT` 信号本体的稳定性拆解，也不把 construction probe 误写成 signal fix。  
适合谁：已经接受 `M-PIT` 仍是月频研究主线，但希望把执行方式改得更慢、更黏、更像“季度看看、平时少动”的人。  
读完你会得到什么：为什么这里更适合“月度评分 + 慢执行”，仓库当前能用哪些旋钮模拟这种风格，以及第一轮 probe 的实际结果。  
相关页面：`docs/research/notes/hk-monthly-current-state-20260330.md`、`docs/research/notes/hk-monthly-pit-frozen-vs-latest-design-20260330.md`、`docs/research/notes/hk-monthly-pit-no-ret-follow-up-20260330.md`、`docs/research/notes/hk-monthly-time-window-design-20260330.md`、`docs/config.md`

页面性质：`research-note`  
状态：`active deep-dive`，不是 monthly 默认入口；默认入口仍是 `hk-monthly-current-state-20260330.md`  
最后核对时间：`2026-03-30`  
权威来源：本页列出的 run 目录下 `summary.json` / `config.used.yml` / `backtest_net*.csv`  
冲突优先级：如果与具体 run 的 `summary.json` / `config.used.yml` 冲突，以 run 产物为准

## 1. 先说结论

如果目标是更贴近“季度看看、平时少动、回头主要看过去 `1y/3y` 表现”的主观投资风格，当前仓库里更合理的实现方式不是直接退回纯季度研究框架，而是：

* 保留 `M-PIT` 的月度评分频率
* 继续允许月度调仓
* 但用更强的 `buffer_entry / buffer_exit` 把组合变得更黏
* 评价重点放在滚动 `12m / 24m / 36m`，而不是只盯单月 alpha

原因很简单：

* 月频样本远多于季频，研究统计更稳。
* 你想表达的核心诉求是“更慢的持有逻辑”，不一定是“更慢的信号频率”。
* 当前仓库已有现成 `buffer` 和 `rolling_sharpe` 产物，先用它们做第一轮 probe，信息比最高。

## 2. 这轮 probe 到底改了什么

这轮实验**只改组合构造和滚动评价窗口**，不改：

* `M-PIT` 特征集
* 模型
* 标签设计
* 数据时间边界

固定条件：

* 基线仍是 latest fixed-`24m` 的 `M-PIT diag`
* 数据口径仍是 `asof_20260327`
* `final_oos.size = 24`
* `industry / size diagnostics` 保持开启

当前仓库能直接用来模拟“慢执行”的旋钮主要有：

* `buffer_exit`
* `buffer_entry`
* `top_k`
* `eval.rolling.windows_months`

当前**没有**现成的 `min_hold` 配置键，所以这轮不碰“最短持有期”；如果后面 buffer frontier 明显见顶，再考虑补这个能力更合适。

## 3. 实验矩阵

### 3.1 参考基线

* `baseline latest_fixed24 diag`
  * 变体名：`hk_sel_m_pit_core_hybrid_sidecar_diag_tr_close_exec_balanced`
  * run：`artifacts/runs/hk_sel_m_pit_core_hybrid_sidecar_diag_tr_close_exec_balanced_20260330_155212_d2b52da6/`

### 3.2 Slow-Sleeve 变体

* `slow_bx15_be10`
  * 变体名：`hk_sel_m_pit_core_hybrid_sidecar_diag_slow_bx15_be10_tr_close_exec_balanced`
  * run：`artifacts/runs/hk_sel_m_pit_core_hybrid_sidecar_diag_slow_bx15_be10_tr_close_exec_balanced_20260330_175942_4428e5a0/`
  * 含义：`top_k=20` 不变，但只有当老持仓跌出更远、且新名字足够靠前时才换

* `slow_bx20_be10`
  * 变体名：`hk_sel_m_pit_core_hybrid_sidecar_diag_slow_bx20_be10_tr_close_exec_balanced`
  * run：`artifacts/runs/hk_sel_m_pit_core_hybrid_sidecar_diag_slow_bx20_be10_tr_close_exec_balanced_20260330_180023_e40db955/`
  * 含义：进一步偏向“让老持仓多留一会儿”

* `slow_bx15_be10_topk25`
  * 变体名：`hk_sel_m_pit_core_hybrid_sidecar_diag_slow_bx15_be10_topk25_tr_close_exec_balanced`
  * run：`artifacts/runs/hk_sel_m_pit_core_hybrid_sidecar_diag_slow_bx15_be10_topk25_tr_close_exec_balanced_20260330_180100_3a24e924/`
  * 含义：轻微放宽持仓数，再配 sticky buffer，看能不能让滚动年度表现更平滑

这 3 条配置都把 `eval.rolling.windows_months` 扩到了 `[12, 24, 36]`。  
注意：由于 `final_oos` 只有 `24` 个月，`36m` rolling 只对更长的测试段有意义，不会在 final OOS 段产生有效值。

## 4. 结果

### 4.1 Final OOS 结果

| 变体 | Final OOS IC | 年化 / Sharpe | 平均换手 | 最大回撤 | 最新 `12m` rolling Sharpe |
| --- | ---: | ---: | ---: | ---: | ---: |
| `baseline` | `-7.30%` | `26.0% / 0.84` | `44.4%` | `-15.6%` | `1.64` |
| `slow_bx15_be10` | `-7.30%` | `23.1% / 0.78` | `38.1%` | `-16.1%` | `1.54` |
| `slow_bx20_be10` | `-7.30%` | `25.3% / 0.82` | `33.6%` | `-14.4%` | `1.52` |
| `slow_bx15_be10_topk25` | `-7.30%` | `25.9% / 0.84` | `35.3%` | `-15.9%` | `1.74` |

### 4.2 更长窗口的测试段滚动 Sharpe

| 变体 | 测试段年化 / Sharpe | 测试段平均换手 | 最新 `24m` rolling Sharpe | 最新 `36m` rolling Sharpe |
| --- | ---: | ---: | ---: | ---: |
| `baseline` | `-7.4% / -0.07` | `42.3%` | `-0.55` | `-0.71` |
| `slow_bx15_be10` | `-5.4% / -0.00` | `36.2%` | `-0.46` | `-0.64` |
| `slow_bx20_be10` | `-4.0% / 0.04` | `30.8%` | `-0.48` | `-0.60` |
| `slow_bx15_be10_topk25` | `-4.6% / 0.00` | `32.6%` | `-0.67` | `-0.73` |

## 5. 怎么读这组结果

### 5.1 这轮没有“修好信号”

这点要先说死：

* `Final OOS IC` 在 4 条线里完全一样，都是 `-7.30%`
* 这是预期内结果，因为这轮只改了 construction，不改打分

所以这轮 probe 回答的问题不是：

* `M-PIT` 的 latest weakness 有没有被修好

而是：

* 在 signal 不变的前提下，能不能用更慢的执行方式把实现做得更贴近主观投资风格

### 5.2 `slow_bx20_be10` 是当前最合理的 slow-sleeve 候选

如果目标是“尽量少动，但别把表现毁掉”，这条最平衡：

* `Final OOS` 换手从 `44.4%` 压到 `33.6%`
* `Final OOS` 年化 / Sharpe 只小幅回落到 `25.3% / 0.82`
* `Final OOS` 最大回撤还略有改善，从 `-15.6%` 到 `-14.4%`
* 测试段 `24m / 36m` rolling Sharpe 也比 baseline 稍好

更直白地说，它最像“还是月频研究骨架，但执行上更愿意拿着不动”的版本。

### 5.3 `slow_bx15_be10_topk25` 更像实现 comparator，不像默认慢模板

这条的优点是：

* `Final OOS` 年化 / Sharpe 几乎守住基线
* 最新 `12m` OOS rolling Sharpe 反而最高
* 换手也明显下降

但它的问题是：

* 更长的测试段 `24m / 36m` rolling Sharpe 反而弱于 baseline
* 它更像“最近一段做得顺”，不够像更稳的长期慢模板

所以这条值得保留为 comparator，但我不会先把它当默认 slow sleeve。

### 5.4 `slow_bx15_be10` 价值有限

它确实降低了换手，但：

* `Final OOS` 年化 / Sharpe 掉得更明显
* 相比 `bx20_be10` 没有拿到更好的长期滚动结果

因此这条没有形成独立优势。

## 6. 当前结论

截至这轮 probe，更合理的落点是：

* **研究骨架**：仍然是 `M-PIT` 月频主线
* **慢执行模板**：优先保留 `slow_bx20_be10`
* **实现 comparator**：可以顺手保留 `slow_bx15_be10_topk25`

后续状态更新：

* 后续 follow-up 已在 `slow_bx20_be10` 的基础上继续测试 `no_ret` 版本，当前更值得继续推进的候选已变成 `M-PIT + no_ret + bx20 / be10`；具体见 `hk-monthly-pit-no-ret-follow-up-20260330.md`。

这意味着，你想要的那种“季度看看、平时少动、回头看过去 `1y/3y`”风格，**不需要先把项目大改成季度研究框架**。  
更高信息比的路径是：

1. 继续用月频 `M-PIT` 做研究
2. 在组合构造层把它变慢
3. 用滚动 `12m / 24m / 36m` 来评价它

## 7. 下一步建议

### 7.1 研究主线不变

这轮结果不改变 monthly 现行主线：

* `M-PIT` 仍然是研究主线
* 下一优先仍是 latest 窗口的逐月漂移拆解

### 7.2 慢执行 sidecar 可以先固定到 `bx20 / be10`

如果你现在就想保留一条更贴近个人投资直觉的 sidecar，我会先保留：

* `top_k = 20`
* `buffer_exit = 20`
* `buffer_entry = 10`

### 7.3 真要继续往“更像主观投资”方向推进，下一刀也不该直接砍到季度

更合理的顺序是：

1. 先把 `slow_bx20_be10` 当执行 sidecar 继续观察
2. 如果 buffer frontier 已经见顶，再考虑补一个真正的 `min_hold` 能力
3. 最后才考虑是不是要做“季度 review / 月度 exception”这一类更重的执行逻辑

一句话收口：

* **季度更像执行节奏**
* **月频更适合研究骨架**
* **当前最好的折中不是回去做季度主线，而是保留月频 `M-PIT`，再把 construction 做慢**
