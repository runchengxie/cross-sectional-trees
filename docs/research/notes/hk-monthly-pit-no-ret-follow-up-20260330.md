# HK Monthly PIT No-Ret Follow-Up（2026-03-30）

本页解决什么：回答“如果保留 `M-PIT` 的财报主轴和波动/流动性 sidecar，但去掉直接 trailing-return 动量输入，结果会不会更干净”这个问题，并记录第一轮 `no_ret` robustness follow-up。  
本页不解决什么：不替代 `M-PIT` baseline 的 frozen-vs-latest 稳定性拆解，也不把这轮结果误写成“monthly 已完全验证完成”。  
适合谁：已经接受 `M-PIT` 更像月频研究主线，但不希望它被直接 momentum 输入带偏的人。  
读完你会得到什么：`no_ret` 到底改了什么、为什么这条思路在经济含义上更贴近“基本面主导”、它在不同时间口径下的表现，以及它现在在 monthly 主线里的定位。  
相关页面：`docs/research/notes/hk-monthly-current-state-20260330.md`、`docs/research/notes/hk-monthly-pit-slow-sleeve-probes-20260330.md`、`docs/research/notes/hk-monthly-pit-frozen-vs-latest-design-20260330.md`、`docs/research/notes/hk-monthly-time-window-design-20260330.md`、`docs/config.md`

页面性质：`research-note`  
状态：`active deep-dive`（目前monthly 默认入口仍是 `hk-monthly-current-state-20260330.md` ） 
最后核对时间：`2026-03-30`  
权威来源：本页列出的 run 目录下 `summary.json` / `config.used.yml` / `feature_importance.csv`  
冲突优先级：如果与具体 run 的 `summary.json` / `config.used.yml` 冲突，以 run 产物为准

## 1. 先说结论

这轮 follow-up 到目前为止给出的信号：

* 相比以往的run，移除了 trailing-return 的动量特征：
  * 保留 `M-PIT`
  * 保留 `bx20 / be10` 这条慢执行模板
  * 去掉 `ret_20 / ret_60 / ret_120`
  * 只保留 `rv_*`、成交量比率、`log_vol / vol` 作为波动/流动性 sidecar
* 这条 `no_ret + bx20 / be10` 在多个时间窗口都表现更好：
  * latest fixed-`24m`
  * latest ratio split
  * frozen fixed-`24m`
  这三条口径下，测试段和 final OOS 的 `IC` 都已经翻正。
* 因此它现在更像 `M-PIT` 的当前月频候选版本

一句话收口：

* **“删掉直接 trailing-return 动量，保留财报主轴 + 波动/流动性 sidecar” 是当前最像 monthly PIT 新候选主线的方向。**

## 2. 这轮到底改了什么

这轮 follow-up 移除了动量的考虑：

* 从原来的 `slow_bx20_be10` 里删掉：
  * `ret_20`
  * `ret_60`
  * `ret_120`
* 保留：
  * `rv_20 / rv_60`
  * `volume_sma20_ratio / volume_sma60_ratio`
  * `log_vol / vol`
  * 所有 `PIT` 财报特征
* 不改：
  * 模型
  * 标签定义
  * 交易成本口径
  * `top_k`
  * `bx20 / be10` construction

配置约定：

* 这轮 follow-up 实际是同一个 `no_ret + bx20 / be10` 家族下的 `base / frozen fixed-24m / latest ratio` 三个派生版本。
* 由于该项目本地 `configs/local/` 默认不纳入版本控制，未来复现时应优先看各 run 目录里的 `config.used.yml`，不要把本地派生文件名当成唯一权威入口。

## 3. 经济含义上，这条线现在在学什么

删掉 `ret_*` 之后，这条线剩下的特征可以更直观地分成四组：

### 3.1 财报规模与增长

* `sales`
* `net_profit`
* `cash_flow_from_operating_activities`
* `basic_earnings_per_share`
* 各自的 `growth_*`

对应含义：

* 公司最近业务有没有变大
* 盈利和经营现金流有没有在改善
* 财报里的增长到底有没有落到利润和现金流上

### 3.2 盈利质量

* `profit_margin`
* `cfo_margin`
* `cfo_to_profit`

对应含义：

* 利润率高不高
* 现金流利润率高不高
* 利润是不是更像真金白银

### 3.3 信息新鲜度

* `days_since_report`

对应含义：

* 这份财报信息离现在有多远
* 同样的财报好消息，越新鲜通常越有参考价值

### 3.4 市场状态 sidecar

* `rv_20 / rv_60`
* `volume_sma20_ratio / volume_sma60_ratio`
* `log_vol / vol`

对应含义：

* 最近波动大不大
* 最近成交是不是相对自己平时突然放大
* 这只股票本来就热不热、流不流

这组 sidecar 的作用：

* 给财报主轴补一个风险状态和流动性状态的上下文
* 避免模型在完全不看市场状态的情况下，机械地押纯财报分数

## 4. 实验矩阵

### 4.1 参考基线

* `slow_bx20_be10 baseline`
  * run：`artifacts/runs/hk_sel_m_pit_core_hybrid_sidecar_diag_slow_bx20_be10_tr_close_exec_balanced_20260330_180023_e40db955/`

### 4.2 `no_ret` 变体

* `no_ret latest fixed24`
  * run：`artifacts/runs/hk_sel_m_pit_core_hybrid_sidecar_diag_slow_bx20_be10_no_ret_tr_close_exec_balanced_20260330_212424_f9b65169/`

* `no_ret latest ratio`
  * run：`artifacts/runs/hk_sel_m_pit_core_hybrid_sidecar_diag_slow_bx20_be10_no_ret_latest_ratio_tr_close_exec_balanced_20260330_220645_f2f6d129/`

* `no_ret frozen fixed24`
  * run：`artifacts/runs/hk_sel_m_pit_core_hybrid_sidecar_diag_slow_bx20_be10_no_ret_frozen_fixed24_tr_close_exec_balanced_20260330_220840_58168495/`

### 4.3 `no_ret` 第一轮 construction 微调

* `no_ret top15 + bx20 / be10`
  * run：`artifacts/runs/hk_sel_m_pit_core_hybrid_sidecar_diag_slow_bx20_be10_no_ret_topk15_tr_close_exec_balanced_20260330_233710_4834676a/`

* `no_ret bx20 / be12`
  * run：`artifacts/runs/hk_sel_m_pit_core_hybrid_sidecar_diag_slow_bx20_be12_no_ret_tr_close_exec_balanced_20260330_233751_1ababaf7/`

## 5. 结果

### 5.1 核心对比

| 版本 | 测试段 IC | 测试段年化 / Sharpe | Final OOS IC | Final OOS 年化 / Sharpe | Final OOS 换手 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 原版 `bx20 / be10` | `-0.67%` | `-4.0% / 0.04` | `-7.30%` | `25.3% / 0.82` | `33.6%` |
| `no_ret latest fixed24` | `+1.91%` | `-2.6% / 0.04` | `+7.79%` | `42.6% / 1.47` | `46.2%` |
| `no_ret latest ratio` | `+3.67%` | `2.4% / 0.22` | `+7.97%` | `38.2% / 1.29` | `34.6%` |
| `no_ret frozen fixed24` | `+2.21%` | `3.0% / 0.24` | `+8.92%` | `37.1% / 1.29` | `34.5%` |

### 5.2 模型方向感也一起变了

这轮最值钱的是：

* 原版 `bx20 / be10` 的 `cv_ic` 是正的，但这条线在 latest fixed-`24m` 下最终 test / OOS `IC` 都已经翻负，signal direction 也带有明显 recent-window 压力。
* `no_ret` 三条口径下，测试段 `IC` 和 final OOS `IC` 都回到了正值。
* 这说明删掉 `ret_*` 之后，排序纯度也一起改善了。

### 5.3 特征重要性更像基本面主导

`no_ret` 三条 run 的前排 feature importance 都高度一致，最前面基本都是：

* `cfo_to_profit`
* `cfo_margin`
* `growth_cash_flow_from_operating_activities`
* `profit_margin`
* `net_profit`
* `growth_net_profit`
* `basic_earnings_per_share`
* `days_since_report`

也就是说：

* `PIT` 财报特征重新回到非常明确的主导地位
* `rv_* / vol / volume_sma_ratio` 还在，但更像 sidecar
* 这比原版带 `ret_*` 的版本更贴近基本面主导的信号

### 5.4 第一轮 construction 微调怎么读

| 版本 | 测试段年化 / Sharpe | 测试段换手 | 最新测试 rolling Sharpe `12m / 24m / 36m` | Final OOS IC | Final OOS 年化 / Sharpe | Final OOS 换手 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_ret + bx20 / be10` | `-2.6% / 0.04` | `36.6%` | `-1.72 / -0.46 / -0.47` | `+7.79%` | `42.6% / 1.47` | `46.2%` |
| `no_ret + top15 + bx20 / be10` | `-4.0% / -0.01` | `39.0%` | `-1.86 / -0.62 / -0.57` | `+7.79%` | `47.8% / 1.50` | `50.2%` |
| `no_ret + bx20 / be12` | `-2.6% / 0.04` | `36.6%` | `-1.72 / -0.46 / -0.47` | `+7.79%` | `42.6% / 1.47` | `46.2%` |

这张表最值得记住的：

* `top15` 的作用更像把当前候选再往激进一点推，最近 `Final OOS` 账面更亮，但测试段更差、rolling 更差、换手也更高。
* 它因此更适合保留成 aggressive sidecar / comparator，不适合直接替换当前默认候选。
* `bx20 / be12` 在当前样本里几乎是纯 no-op：
  * `config.used.yml` 确实记录了 `buffer_entry = 12`
  * 但 `backtest_net.csv` 和 `positions_current_oos.csv` 与 `bx20 / be10` 基线逐字节一致
* 这说明在当前窗口里，把 entry buffer 从 `10` 放到 `12` 没有改变任何实际调仓决策，因此它暂时不值得继续单独推进。

## 6. 怎么读这组结果

### 6.1 这次不像单窗运气

如果只有 `latest fixed24` 一条好看，那还可能只是近期巧合。  
但现在：

* `latest fixed24` 站住了
* `latest ratio` 也站住了
* `frozen fixed24` 也站住了

所以这轮结果更像是 `ret_*` 这组直接 trailing-return 输入，确实在之前那条 `M-PIT` 慢执行线上制造了噪音或冲突

### 6.2 提高了一定的换手率作为代价

这条线也不是完全没有 trade-off：

* `latest fixed24` 版本的 final OOS 换手从 `33.6%` 升到 `46.2%`
* 但另外两条 robustness run 的换手大致仍在 `34.5%-34.6%`

更实际的理解是：

* 这轮不是“免费午餐”
* 但至少目前大部分增益并不是靠极端提换手硬换出来的

### 6.3 这轮比轻量 valuation overlay 更像真增量

和前一轮 `pb / pe / size` overlay 相比，这次 `no_ret` 的信息比更高，因为：

* 改动更单纯
* 经济含义更清楚
* `IC` 和 long-only 实现一起改善
* 而不是只在组合实现层有一段更好看的曲线

## 7. 当前定位

截至这轮探索，更合理的月频策略分工应该理解成：

* `M-PIT baseline`
  * 仍是研究锚点
  * 用来解释 frozen-vs-latest 的转弱问题
* `M-PIT + no_ret + bx20 / be10`
  * 当前最值得继续推进的 monthly PIT candidate
  * 更贴近“基本面主导 + 慢执行 + 不直接追动量”的个人投资风格
* `M-provider rebalance-only`
  * 仍是正式月频 comparator / 实现候选
  * 但不替代 `M-PIT` 研究主线

一句话说：

* **`M-PIT baseline` 负责解释**
* **`M-PIT + no_ret + bx20 / be10` 负责接棒成为当前候选**
* **`M-provider` 继续当实现 comparator**

## 8. 下一步建议

### 8.1 先别重新扩很大的模型 zoo

这轮结果出来以后，最不值得做的反而是：

* 又回头扩大量价特征组合
* 继续堆更多 valuation overlay 变体
* 直接退回季度主线

### 8.2 小范围 construction 微调已经拿到第一轮答案

这轮最值得保留的结论是：

* `top15` 值得保留，但定位应是 aggressive sidecar / comparator
* `bx20 / be12` 当前窗口没有改变任何 realized path，可以先停

所以如果还要继续做 construction follow-up，更合理的方向是：

* 先把 `no_ret + bx20 / be10` 固定为默认候选
* 只把 `top15` 留作“更集中、更高换手”的对照
* 暂时不要继续围绕 `be12` 扩小网格

### 8.3 仍然要继续看 future samples

即便这轮结果已经很强，也还不该把它写成“monthly PIT 已验证完成”。  
更准确的阶段判断是：

* 已经够资格升成 current candidate
* 还不够资格叫 mature production strategy

## 9. 一句话结论

截至 `2026-03-30`，如果只在 monthly PIT 这条线上选一个最值得继续押的方向，那么当前最合理的答案已经不是原版 `bx20 / be10`，而是：

* **`M-PIT + no_ret + bx20 / be10`**

因为它目前同时满足：

* 更符合“基本面主导、不直接追动量”的信号故事
* 在 latest 和 frozen 两组口径下都站住了
* `IC` 和 long-only 实现一起改善
* 第一轮 local construction probe 也没有把它挤下去；`top15` 只是更激进的 sidecar，`be12` 在当前窗口基本没有新信息
