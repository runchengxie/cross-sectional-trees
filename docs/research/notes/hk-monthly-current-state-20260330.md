# HK Monthly 现行口径与实盘距离（2026-03-30）

本页解决什么：把当前 HK monthly 这条研究线最该保留的 run、结论、证据边界和下一步动作收成一页，并说明它离实盘还有多远。  
本页不解决什么：不替代单次 run 的 `summary.json` / `config.used.yml`，也不把所有 monthly follow-up 细节重写一遍。  
适合谁：已经看过几轮 monthly 对比，想知道“现在到底哪条最有前景、该继续做什么、能不能开始实盘准备”的人。  
读完你会得到什么：当前最有前景的 monthly run、它们各自好在哪里、还存在哪些问题、距离实盘的阶段判断，以及下一位 Codex 继续接手时最该看的信息。  
相关页面：`docs/research/notes/hk-monthly-time-window-design-20260330.md`、`docs/research/notes/hk-monthly-pit-frozen-vs-latest-design-20260330.md`、`docs/research/notes/hk-monthly-pit-slow-sleeve-probes-20260330.md`、`docs/research/notes/hk-monthly-pit-no-ret-follow-up-20260330.md`、`docs/research/notes/hk-monthly-benchmark-ladder-and-attribution-20260405.md`、`docs/research/notes/hk-monthly-pit-valuation-overlay-probes-20260330.md`、`docs/research/notes/hk-monthly-provider-vs-pit-20260330.md`、`docs/research/notes/hk-monthly-provider-factor-probes-20260330.md`、`docs/playbooks/hk-selected.md`、`docs/research/README.md`

页面性质：`current-state`  
最后核对时间：`2026-03-30`  
权威来源：本页列出的 run 目录下 `summary.json` / `config.used.yml` / `positions_by_rebalance_oos.csv`，以及当前 monthly 研究总笔记  
冲突优先级：如果与具体 run 的 `summary.json` / `config.used.yml` 冲突，以 run 产物为准；如果与更新样本冲突，以更晚样本为准

> 注：这轮 monthly 派生配置当时保存在作者本地 `configs/local/`，默认不纳入版本控制。未来复现或接手时，应优先使用各 run 目录里的 `config.used.yml`，不要把本地文件名当成唯一权威入口。

## 1. 先记住这些

* 现在 monthly 线最合理的分工应理解成：`M-PIT baseline` 当研究锚点，`M-PIT + no_ret + bx20 / be10` 当当前 monthly PIT candidate，`M-provider rebalance-only` 当正式月频 comparator / 实现候选，`Q-PIT` 只保留 benchmark 角色。
* `M-provider` 当前账面 OOS 最强，但 `final OOS IC` 仍为负，所以它更像实现候选，不像最干净的排序器。
* old `M-PIT baseline` 在 frozen 口径下更像真的有横截面排序证据，而当前 `no_ret + bx20 / be10` 则是在更晚窗口里把 `IC` 和 long-only 实现一起重新拉回正区间的候选版本。
* provider 那条强 OOS 曲线，当前更像 `small-cap + 短周期价格结构 + 个股选择` 的混合结果，而不是纯财报 alpha、纯 value 或纯中期 momentum。
* 这轮 `size-neutral` / `soft size control` 探针已经说明：继续救 provider 的 size 问题，边际信息开始下降，不该再当第一优先方向。
* 最新 benchmark ladder 和 attribution 已经说明：当前 monthly 策略几乎没有输给 `selected_eqw`，真正把差距拉开的主要是 `selected_capw`；因此当前更像是 **cap-weight / mega-cap 暴露问题**，不是 signal direction 被证伪。
* 最新一轮 `M-PIT + 轻量 valuation overlay` probe 已经跑完，但在 `asof_20260327 + 24m final OOS` 上没有验证出干净增量；`pe_only` 最多保留为实现 comparator。
* `M-PIT` 的 `R0-R4` 稳定性拆解也已经跑完：`2025-12-31` cutoff 下的 recut 仍然是正 `IC`，`2026-03-27` cutoff 下的 recut 已经转成负 `IC`。
* 如果目标是更贴近“季度看看、平时少动”的主观投资风格，当前更高信息比的做法不是退回季度主线，而是在 `M-PIT` 月频骨架上做 slow-sleeve construction；首轮 probe 里 `bx20 / be10` 是最平衡的慢执行模板。
* 在 `slow_bx20 / be10` 的基础上再去掉直接 trailing-return 特征后，`no_ret` 已经在 latest fixed-`24m`、latest ratio 和 frozen fixed-`24m` 三条口径下同时验证出正 `IC`，因此它现在比原版 `bx20 / be10` 更像当前 monthly PIT candidate。
* `no_ret` 第一轮 local construction probe 也已经跑完：`top15` 只把这条线推向更激进、更高换手的 sidecar；`bx20 / be12` 在当前窗口没有改变任何 realized path。
* 所以当前最值得继续做的，不是继续扩 `pb / pe / size` overlay 组合，也不是继续怀疑 split 本身，而是把 `no_ret + bx20 / be10` 作为当前候选继续推进，并保留 baseline 去解释最近新增月份为什么会把旧版 `M-PIT` 推弱。
* 这条 monthly 线已经够资格准备 `shadow / paper`，但还不够资格包装成“已能放心重仓上线的成熟实盘策略”。

## 2. 当前应该盯哪几条 run

### 2.1 月频实现候选

* `M-provider rebalance-only`
  * run：`artifacts/runs/hk_sel_m_provider_mainline_rebalance_only_tr_close_exec_balanced_20260330_002336_c12762fc/`
  * summary：`artifacts/runs/hk_sel_m_provider_mainline_rebalance_only_tr_close_exec_balanced_20260330_002336_c12762fc/summary.json`

### 2.2 月频 PIT 研究锚点与候选

* `M-PIT baseline / research anchor`
  * run：`artifacts/runs/hk_sel_m_pit_core_hybrid_sidecar_tr_close_exec_balanced_20260330_001434_eb10ec79/`
  * summary：`artifacts/runs/hk_sel_m_pit_core_hybrid_sidecar_tr_close_exec_balanced_20260330_001434_eb10ec79/summary.json`

* `M-PIT + no_ret + bx20 / be10`
  * run：`artifacts/runs/hk_sel_m_pit_core_hybrid_sidecar_diag_slow_bx20_be10_no_ret_latest_ratio_tr_close_exec_balanced_20260330_220645_f2f6d129/`
  * summary：`artifacts/runs/hk_sel_m_pit_core_hybrid_sidecar_diag_slow_bx20_be10_no_ret_latest_ratio_tr_close_exec_balanced_20260330_220645_f2f6d129/summary.json`

### 2.3 低频 benchmark

* `Q-PIT benchmark`
  * run：`artifacts/runs/hk_sel_q_pit_core_hybrid_benchmark_exec_balanced_local_20260330_001350_af21aa22/`
  * summary：`artifacts/runs/hk_sel_q_pit_core_hybrid_benchmark_exec_balanced_local_20260330_001350_af21aa22/summary.json`

## 3. 当前最合理的分工

### 3.1 `M-PIT baseline`

定位：

* 月频研究锚点
* 当前最值得继续做稳定性拆解的基线信号
* 不是因为 latest 窗口还很强，而是因为它在 frozen cutoff 下仍然最像“结构 alpha”，但在 latest 窗口上已明显转弱

原因：

* 历史 frozen reference 的 test `IC = 4.32% (p = 0.016)`、final OOS `IC = 4.88% (p = 0.093)`，说明旧窗口里它更像干净排序器
* `R1 / R2` 这两条 `2025-12-31` cutoff recut 仍然是正 `IC`，说明 split 变化本身不是把它翻坏的主因
* `R3 / R4` 这两条 `2026-03-27` cutoff recut 都已转成负 `IC`，说明当前真正该解释的是 recent regime / latest months
* 稳定 top features 仍以 `growth_sales`、`growth_cash_flow_from_operating_activities`、`cfo_to_profit`、`profit_margin`、`growth_net_profit` 为主，信号故事没有直接塌成纯量价或纯 size

一句话解释：

* 它不是当前账面最强的 latest 组合，但它仍然是最值得解释“为什么最近变弱”的那条研究主线。

### 3.2 `M-PIT + no_ret + bx20 / be10`

定位：

* 当前 monthly PIT candidate
* 更贴近“基本面主导 + 慢执行 + 不直接追动量”的执行版本

原因：

* 它只删掉了 `ret_20 / ret_60 / ret_120`，保留了 `PIT` 财报主轴和 `rv_* / volume_sma_ratio / log_vol / vol` 这组波动/流动性 sidecar
* latest fixed-`24m` 下，`final OOS IC = 7.79%`，long-only `ann = 42.6%`, `sharpe = 1.47`
* latest ratio 下，`test IC = 3.67%`、`final OOS IC = 7.97%`，long-only `ann = 38.2%`, `sharpe = 1.29`
* frozen fixed-`24m` 下，`test IC = 2.21%`、`final OOS IC = 8.92%`，long-only `ann = 37.1%`, `sharpe = 1.29`
* feature importance 也重新回到非常明确的 `PIT` 财报主导，量价块更像 sidecar，不再像直接 trailing-return 动量在牵引模型
* 第一轮 construction follow-up 已经说明：`top15` 虽然能把 latest OOS 账面再往上推一点，但测试段更差、rolling 更差、换手更高；`bx20 / be12` 则在当前窗口基本是 no-op，所以它们都还不足以替换当前默认候选

一句话解释：

* 它现在是这条 monthly PIT 线上最像“既更符合你的投资直觉、又有跨口径 robustness”的当前候选版本。

### 3.3 `M-provider rebalance-only`

定位：

* 正式月频 comparator
* 当前最像实盘实现候选的月频组合

原因：

* test `IC = 2.12% (p = 0.190)`
* final OOS `IC = -2.00% (p = 0.281)`
* final OOS long-only `ann = 62.7%`, `sharpe = 1.73`
* walk-forward mean `ann = 11.2%`, `sharpe = 0.552`
* OOS 回撤浅，账面曲线明显强于 `M-PIT`

一句话解释：

* 它更像“最近这段样本里很能打的组合实现”，但不够像“已经证明自己是干净排序器”的主研究线。

### 3.4 `Q-PIT`

定位：

* 正式低频 benchmark
* 不升主线

原因：

* test `IC = -5.46% (p = 0.210)`
* final OOS `IC = -11.19% (p = 0.066)`
* final OOS long-only `ann = 21.2%`, `sharpe = 0.80`
* final OOS 只有 `8` 个季度点

一句话解释：

* 它仍有 benchmark 价值，但样本和稳定性都不支持把它升成当前最值得押注的方向。

## 4. 这些 run 各自好在哪里

### 4.1 `M-PIT` 的优点

* 横截面排序证据更干净。
* test 和 final OOS 的 `IC` 都是正的，这一点比 `provider` 更像真正的研究主线。
* 财报字段主导 feature importance，说明这条线不是被快频量价完全偷走了信号故事。
* 最近 `12m` rolling OOS `IC` 仍为正，说明它不是只靠早期窗口托住均值。

### 4.2 `M-PIT + no_ret + bx20 / be10` 的优点

* 它把“基本面主导、不直接追 trailing-return 动量”的信号故事重新讲顺了。
* latest fixed-`24m`、latest ratio 和 frozen fixed-`24m` 三条口径下，测试段和 final OOS 的 `IC` 都回到了正区间。
* feature importance 前排重新回到 `cfo_to_profit`、`cfo_margin`、现金流增长、利润率、净利润这些 `PIT` 财报字段，量价块更像 sidecar。
* 它比 old baseline 更像“当前可以继续观察、继续微调实现边界”的 monthly PIT candidate。

### 4.3 `M-provider` 的优点

* final OOS long-only 曲线最强，且回撤很浅。
* 作为 `20` 只等权、带显式 execution cost 的月频组合，它已经有“可以拿来做 shadow portfolio”的吸引力。
* walk-forward 均值不差，说明它不只是 final OOS 一段完全孤立的奇迹。

### 4.4 `Q-PIT` 的优点

* 作为低频财报 benchmark，语义最清楚。
* 它能提醒 monthly 线不要误把“实现漂亮”当成“财报研究已经被验证”。

## 5. 当前最重要的问题

### 5.1 final OOS 还不够长

当前这批 monthly 核心参考口径的 final OOS 大致都还只有约 `2` 年：

* frozen reference / provider 这类旧窗口大致是 `25` 个 OOS 月度截面，约 `2023-11-30 -> 2025-11-27`
* latest fixed-`24m` 这批 `M-PIT` sidecar / `no_ret` 候选则是 `24` 个 OOS 月度截面，约 `2024-02-29 -> 2026-01-30`

这对月频来说已经够做第一轮候选筛选，但还不够长到把“结构 alpha”和“一段顺风 regime”彻底分开。

更实际的理解是：

* `2` 年 OOS：够做候选筛选
* `3-5` 年 OOS：更像成熟证据

### 5.2 `provider` 的研究证据还不干净

它现在最核心的问题不是“赚不赚钱”，而是：

* final OOS `IC` 仍为负
* `no-size`、`hard-cap`、`soft size control` 都说明它明显依赖港股通池内的相对小盘暴露
* 更软或更硬的 size 处理中和，都没有把它洗成更强的横截面排序器

所以现在对 `provider` 更准确的描述是：

* 它是实现候选
* 不是最干净的研究主线

### 5.3 old `M-PIT baseline` 的实现层还不够顺

它现在的问题不是有没有信号，而是：

* old baseline 的 final OOS long-only 年化和 Sharpe 明显弱于 `provider`
* 回撤更深
* 还没把“排序证据”稳定转成“更好看的实盘实现”

但这条问题描述已经不该直接套到 `no_ret + bx20 / be10` 上，因为后者当前已经在 multiple windows 下把 `IC` 和 long-only 实现一起拉回正区间。

### 5.4 换手和成本仍然值得认真对待

当前这批月频参考线的换手大致分成两档：

* `M-provider` 更高，大约在月度平均换手 `55%-65%`
* `M-PIT + no_ret + bx20 / be10` 这条当前候选更低，大致在 `35%-46%`
* 每期平均成本拖累仍大多在 `0.3%-0.4%` 这一档

对你这种 `1,000,000` 资金量级来说，这通常不是流动性致命问题，因为：

* 当前研究 universe 已经要求 `min_turnover = 10,000,000`
* `top_k = 20` 等权下，单票仓位大概只在组合的 `5%`

但这仍然不是装饰项：

* 对中等强度策略，成本完全可能吃掉很大一块边际收益

### 5.5 最新 monthly sidecar 已经更新到新窗口

这轮 monthly sidecar probe 已经不是旧的 `2025-12-31` frozen snapshot。

当前最新这批对照 run 已经统一到了：

* `raw snapshot as of 2026-03-27`
* `eval.test_size = 0.5`
* `eval.final_oos.size = 24`
* `latest fully labeled monthly point = 2026-01-30`

所以现在真正该解释的问题，已经不是“为什么还没把数据往后拉”，而是：

* 为什么更新到更晚样本之后，`M-PIT` 基线自己转弱了
* 这种转弱到底来自新月份、split 口径还是 universe / PIT 资产刷新

`R0-R4` 首轮实跑已经把这个问题压缩了一大半：

* `R1 / R2`：`2025-12-31` cutoff 下，无论是 old ratio split 还是 fixed `24m final OOS`，`M-PIT` 都仍然是正 `IC`
* `R3 / R4`：`2026-03-27` cutoff 下，无论是 old ratio split 还是 fixed `24m final OOS`，`M-PIT` 都已经转成负 `IC`
* 所以这轮 monthly 转弱的主要矛盾更像 recent months / latest regime，而不是 split 设计本身

## 6. 距离实盘还有多远

### 6.1 现在可以做什么

当前已经可以：

* 把 `M-provider` 作为 shadow / paper 组合候选
* 把 `M-PIT baseline` 作为研究锚点继续维护
* 把 `M-PIT + no_ret + bx20 / be10` 作为当前 monthly PIT candidate 持续跟踪
* 在不扩大资金的前提下，开始准备一套月度实盘观察流程

### 6.2 现在还不该做什么

当前还不该：

* 把任一单条 monthly run 当成“已验证完成、可放心重仓”的唯一主信号
* 仅凭 `provider` 最近这段漂亮 OOS，就直接把 `M-PIT` 降级
* 把继续延长 OOS 误解成“不停用更老数据训练”

### 6.3 更实际的阶段判断

如果按你现在这条月频线的成熟度打阶段：

* 研究阶段：已经走过最混沌的探索期
* shadow / paper：已经够资格开始
* 很小资金 canary：再做一轮关键优化，并再积累一小段新样本后可以考虑
* 更成熟的实盘主策略：还需要更长 OOS 和更干净的实现解释

## 7. 当前最值得继续做的事

### 7.1 第一优先

* 把 `M-PIT + no_ret + bx20 / be10` 固定为当前 monthly PIT candidate

优先考虑：

* 保持 `top_k = 20`
* 保持 `buffer_exit = 20`
* 保持 `buffer_entry = 10`
* 暂时不再把 `ret_*` 加回去

原因：

* 这轮 `no_ret` follow-up 已经在 latest fixed-`24m`、latest ratio 和 frozen fixed-`24m` 三条口径下同时站住
* 改善的不只是 long-only 曲线，`IC` 也一起翻正
* 这条线当前更像“值得继续收窄验证”的 candidate，不像“还在大范围摸索的想法”

### 7.2 第二优先

* 围绕 `no_ret` 继续做 very local 的 construction 微调，但要更收窄

已经知道：

* `top_k = 15` 可以保留为 aggressive comparator
* `bx20 / be12` 在当前窗口没有新信息，先停

如果还要继续，只建议：

* 围绕 `top15` 再做最多一条 very local 派生
* 或者直接把研究预算让回 future samples

原因：

* 当前更有信息比的是确认这条候选的实现边界
* 但这轮已经说明，不是每个小 buffer 变体都会带来可解释的新结果
* 所以不该重新回到小网格横扫

### 7.3 第三优先

* 补 benchmark ladder 的解释层，把“为什么自制 benchmark 强”这件事固定下来

更具体地说：

* 保留 `selected_eqw / selected_capw / connect_full_capw / 02800 / 03432` 这组 benchmark 梯子
* 把“策略几乎打平 `selected_eqw`，但明显输给 `selected_capw`”当成当前 monthly 线的重要解释边界
* 把 `selected_capw` 的头部集中度、mega-cap 暴露和银行/龙头贡献当成 monthly 解释层的一部分，而不是留在 run 目录里靠人工拼

原因：

* 这直接关系到你后面该继续怀疑 signal direction，还是该优先看组合构造和 size 暴露
* 当前证据更支持后者，不支持直接把信号反过来买

### 7.4 第四优先

* 保留 baseline 的 latest 漂移拆解，把它当成解释性工作而不是当前候选

更具体地说：

* 以已经跑完的 `R0-R4` 为边界条件
* 固定 old `M-PIT` baseline 配置
* 去看 latest 这几个月的逐月 `IC`、行业分布、size bucket、持仓重合度和个股集中变化

原因：

* `R0-R4` 已经说明 split 不是第一嫌疑人
* 现在 baseline 的主要价值是解释“旧版为什么被 recent months 推弱”
* 这件事仍有研究价值，但不该再盖过当前 candidate 的推进优先级

### 7.5 第五优先

* 如果只关心实现，保留 `pe_only` 做 comparator，再做换手优化

优先考虑：

* `buffer_entry / buffer_exit`
* `top_k`

原因：

* 这轮 overlay 里只有 `pe_only` 在实现层还有继续观察价值
* 但它不该被包装成“研究主线升级”

### 7.6 第六优先

* 补一个 `30m final OOS` 的 stress sidecar

这里要特别注意：

* 当前并不存在一个应该写成“截至 `2026-03-31`”的完整 monthly OOS
* 更合理的说法是：
  * 旧 run：`2025-12-31` frozen snapshot
  * 新 run：`asof_20260327` latest snapshot
* `30m` sidecar 的意义是做更严格 recent-regime 压力测试，不是制造一个新的默认口径

## 8. 不建议继续优先做什么

* 不把 `size-neutral provider` 当成下一阶段主战场
* 不继续围着 provider 做更硬或更软的 size 微调
* 不继续把 `pb / pe / size` overlay 组合当 monthly 第一优先
* 不把 `Q-PIT` 从 benchmark 重新拔高成 monthly 研究主线替代品
* 不直接做“大而全 provider + PIT + tech + valuation” 黑箱混合版

## 9. 给下一位 Codex 的接手提示

### 9.1 先看哪些文件

先看：

1. 本页
2. `docs/research/notes/hk-monthly-time-window-design-20260330.md`
3. `docs/research/notes/hk-monthly-pit-frozen-vs-latest-design-20260330.md`
4. `docs/research/notes/hk-monthly-pit-slow-sleeve-probes-20260330.md`
5. `docs/research/notes/hk-monthly-pit-no-ret-follow-up-20260330.md`
6. `docs/research/notes/hk-monthly-benchmark-ladder-and-attribution-20260405.md`
7. `docs/research/notes/hk-monthly-pit-valuation-overlay-probes-20260330.md`
8. `docs/research/notes/hk-monthly-provider-vs-pit-20260330.md`
9. `docs/research/notes/hk-monthly-provider-factor-probes-20260330.md`
10. 各核心 run 目录下的 `summary.json`
11. 各核心 run 目录下的 `config.used.yml`

### 9.2 当前最该信什么

* `config.used.yml` 比本地 `configs/local/` 更权威
* `summary.json` 比口头复述更权威
* 当前 monthly 分工应理解为：
  * `M-PIT baseline`：研究锚点
  * `M-PIT + no_ret + bx20 / be10`：当前 monthly PIT candidate
  * `M-PIT + no_ret + top15 + bx20 / be10`：激进 sidecar / comparator
  * `M-provider`：实现 comparator / 候选
  * `Q-PIT`：低频 benchmark

### 9.3 当前最重要的 open questions

* 为什么旧 frozen snapshot 里的 `M-PIT` 更像正 IC 研究主线，而 old baseline 更新到 `asof_20260327 + 24m final OOS` 后明显转弱
* `no_ret + bx20 / be10` 这条候选在后续新样本里，能不能持续守住正 `IC` 和可接受的实现质量
* 这种差异主要来自新增月份、split 口径变化，还是 old baseline 里的 `ret_*` 直接 trailing-return 输入
* 当前 strategy 和 `selected_eqw` 几乎打平，但输给 `selected_capw` 的差距，后续更该通过哪些组合构造或 size 暴露控制来解释
* 如果只把 `pe_only` 当实现 comparator，它在做了更保守的 turnover 优化后，能不能改善 long-only 实现而不误导研究主线判断

### 9.4 继续往后扩样本时要记住什么

* 不要把“新 raw cutoff 重跑”误写成“旧 OOS 自然延长”
* 现在这条线更合理的说法是：
  * 旧 run：截至 `2025-12-31` 的冻结 snapshot
  * 新 run：`asof_20260327` 的 latest snapshot
* 这样未来回看时，才能分清哪些结论是当时就有的，哪些是后来新样本带来的

## 10. 当前推荐阅读顺序

如果你今天重新进入 monthly 研究，建议按下面顺序读：

1. 本页：先把主线、候选、实盘距离和下一步看对。
2. [`hk-monthly-time-window-design-20260330.md`](./hk-monthly-time-window-design-20260330.md)：先把当前 `asof` 边界和 `24m final OOS` 设计看清。
3. [`hk-monthly-pit-frozen-vs-latest-design-20260330.md`](./hk-monthly-pit-frozen-vs-latest-design-20260330.md)：先看 `R0-R4` 已经跑出了什么，以及为什么当前主要矛盾更像 recent months / latest regime。
4. [`hk-monthly-pit-slow-sleeve-probes-20260330.md`](./hk-monthly-pit-slow-sleeve-probes-20260330.md)：如果你想把 `M-PIT` 做得更像“季度看看、平时少动”的慢执行模板，先看这页。
5. [`hk-monthly-pit-no-ret-follow-up-20260330.md`](./hk-monthly-pit-no-ret-follow-up-20260330.md)：再看为什么当前最值得继续押的是“删掉直接 trailing-return 动量”的候选版本。
6. `docs/research/notes/hk-monthly-benchmark-ladder-and-attribution-20260405.md`：再看为什么当前自制 benchmark 很强，以及为什么这更像 cap-weight / mega-cap 暴露问题，而不是 signal direction 反了。
7. [`hk-monthly-pit-valuation-overlay-probes-20260330.md`](./hk-monthly-pit-valuation-overlay-probes-20260330.md)：然后再看为什么这轮轻量估值 overlay 没有过线。
8. [`hk-monthly-provider-vs-pit-20260330.md`](./hk-monthly-provider-vs-pit-20260330.md)：再回头看 provider 和 PIT 到底差在哪里。
9. [`hk-monthly-provider-factor-probes-20260330.md`](./hk-monthly-provider-factor-probes-20260330.md)：如果你要继续追 provider 线为什么强、为什么又不够干净，再看这一页。
10. 核心 run 目录下的 `summary.json` / `config.used.yml`：最后再下手复现或继续派生配置。

## 11. 一句话结论

截至 `2026-03-30`，HK monthly 最合理的现行口径仍然是：

* `M-PIT baseline` 继续作为研究锚点保留
* `M-PIT + no_ret + bx20 / be10` 升成当前 monthly PIT candidate
* `M-provider rebalance-only` 作为正式月频 comparator / 实现候选保留
* 最新 benchmark ladder 和 attribution 已经说明：当前主要差距更像 `selected_capw` 里的 cap-weight / mega-cap 暴露，而不是 signal direction 被证明反了
* 最新 `M-PIT + 轻量 valuation overlay` probe 没有验证出干净增量，`pe_only` 最多只保留为实现 comparator
* `R0-R4` 已经说明 old baseline 这轮转弱的主要矛盾更像 recent months / latest regime，而不是 split 设计
* 下一步优先围绕 `no_ret` 做小范围确认，而不是继续扩 overlay 组合
