# HK Monthly 现行口径与实盘距离（2026-03-30）

本页解决什么：把当前 HK monthly 这条研究线最该保留的 run、结论、证据边界和下一步动作收成一页，并说明它离实盘还有多远。  
本页不解决什么：不替代单次 run 的 `summary.json` / `config.used.yml`，也不把所有 monthly follow-up 细节重写一遍。  
适合谁：已经看过几轮 monthly 对比，想知道“现在到底哪条最有前景、该继续做什么、能不能开始实盘准备”的人。  
读完你会得到什么：当前最有前景的 monthly run、它们各自好在哪里、还存在哪些问题、距离实盘的阶段判断，以及下一位 Codex 继续接手时最该看的信息。  
相关页面：`docs/research/notes/hk-monthly-provider-vs-pit-20260330.md`、`docs/research/notes/hk-monthly-provider-factor-probes-20260330.md`、`docs/playbooks/hk-selected.md`、`docs/research/README.md`

页面性质：`current-state`  
最后核对时间：`2026-03-30`  
权威来源：本页列出的 run 目录下 `summary.json` / `config.used.yml` / `positions_by_rebalance_oos.csv`，以及当前 monthly 研究总笔记  
冲突优先级：如果与具体 run 的 `summary.json` / `config.used.yml` 冲突，以 run 产物为准；如果与更新样本冲突，以更晚样本为准

> 注：这轮 monthly 派生配置当时保存在作者本地 `configs/local/`，默认不纳入版本控制。未来复现或接手时，应优先使用各 run 目录里的 `config.used.yml`，不要把本地文件名当成唯一权威入口。

## 1. 先记住这些

* 现在 monthly 线最合理的分工仍然是：`M-PIT` 当研究主线，`M-provider rebalance-only` 当正式月频 comparator / 实现候选，`Q-PIT` 只保留 benchmark 角色。
* `M-provider` 当前账面 OOS 最强，但 `final OOS IC` 仍为负，所以它更像实现候选，不像最干净的排序器。
* `M-PIT` 当前 long-only 账面不如 `provider` 亮，但测试段和 final OOS 的 `IC` 都为正，更像真的有横截面排序证据。
* provider 那条强 OOS 曲线，当前更像 `small-cap + 短周期价格结构 + 个股选择` 的混合结果，而不是纯财报 alpha、纯 value 或纯中期 momentum。
* 这轮 `size-neutral` / `soft size control` 探针已经说明：继续救 provider 的 size 问题，边际信息开始下降，不该再当第一优先方向。
* 当前最值得继续做的不是更激进的 size 处理，而是 `M-PIT + 少量 provider valuation overlay`。
* 这条 monthly 线已经够资格准备 `shadow / paper`，但还不够资格包装成“已能放心重仓上线的成熟实盘策略”。

## 2. 当前应该盯哪几条 run

### 2.1 月频实现候选

* `M-provider rebalance-only`
  * run：`artifacts/runs/hk_sel_m_provider_mainline_rebalance_only_tr_close_exec_balanced_20260330_002336_c12762fc/`
  * summary：`artifacts/runs/hk_sel_m_provider_mainline_rebalance_only_tr_close_exec_balanced_20260330_002336_c12762fc/summary.json`

### 2.2 月频研究主线

* `M-PIT sidecar`
  * run：`artifacts/runs/hk_sel_m_pit_core_hybrid_sidecar_tr_close_exec_balanced_20260330_001434_eb10ec79/`
  * summary：`artifacts/runs/hk_sel_m_pit_core_hybrid_sidecar_tr_close_exec_balanced_20260330_001434_eb10ec79/summary.json`

### 2.3 低频 benchmark

* `Q-PIT benchmark`
  * run：`artifacts/runs/hk_sel_q_pit_core_hybrid_benchmark_exec_balanced_local_20260330_001350_af21aa22/`
  * summary：`artifacts/runs/hk_sel_q_pit_core_hybrid_benchmark_exec_balanced_local_20260330_001350_af21aa22/summary.json`

## 3. 当前最合理的分工

### 3.1 `M-PIT`

定位：

* 月频研究主线
* 当前最像“结构 alpha”而不是风格顺风

原因：

* test `IC = 4.32% (p = 0.016)`
* final OOS `IC = 4.88% (p = 0.093)`
* final OOS long-only `ann = 24.3%`, `sharpe = 0.78`
* walk-forward mean `ann = 11.2%`, `sharpe = 0.509`
* 稳定 top features 以 `growth_sales`、`growth_cash_flow_from_operating_activities`、`cfo_to_profit`、`profit_margin`、`growth_net_profit` 为主

一句话解释：

* 它不是最炸裂的 OOS 组合，但它更像“排序逻辑本身在工作”。

### 3.2 `M-provider rebalance-only`

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

### 3.3 `Q-PIT`

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

### 4.2 `M-provider` 的优点

* final OOS long-only 曲线最强，且回撤很浅。
* 作为 `20` 只等权、带显式 execution cost 的月频组合，它已经有“可以拿来做 shadow portfolio”的吸引力。
* walk-forward 均值不差，说明它不只是 final OOS 一段完全孤立的奇迹。

### 4.3 `Q-PIT` 的优点

* 作为低频财报 benchmark，语义最清楚。
* 它能提醒 monthly 线不要误把“实现漂亮”当成“财报研究已经被验证”。

## 5. 当前最重要的问题

### 5.1 final OOS 还不够长

当前两条月频线的 final OOS 都是：

* `25` 个 OOS 月度截面
* 大致从 `2023-11-30` 到 `2025-11-27`

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

### 5.3 `M-PIT` 的实现层还不够顺

它现在的问题不是有没有信号，而是：

* final OOS long-only 年化和 Sharpe 明显弱于 `provider`
* 回撤更深
* 还没把“排序证据”稳定转成“更好看的实盘实现”

### 5.4 换手和成本仍然值得认真对待

这两条月频线当前大致都在：

* 月度平均换手 `55%-65%`
* 每期平均成本拖累约 `0.37%-0.39%`

对你这种 `1,000,000` 资金量级来说，这通常不是流动性致命问题，因为：

* 当前研究 universe 已经要求 `min_turnover = 10,000,000`
* `top_k = 20` 等权下，单票仓位大概只在组合的 `5%`

但这仍然不是装饰项：

* 对中等强度策略，成本完全可能吃掉很大一块边际收益

### 5.5 现在这批 run 不是“自动更新”的

当前两条 monthly run 为什么只到 `2025-11`，不是因为 PIT 数据断了，而是因为：

* `config.used.yml` 里 `data.end_date` 固定成了 `20251231`
* 当前这批 run 用到的日线缓存样本最大日期也是 `2025-12-31`

但另外两层其实已经更新得更靠后：

* PIT fundamentals 最大日期已到 `2026-03-10`
* universe by-date 最大日期已到 `2026-03-26`

所以当前真正卡住继续扩 OOS 的，是：

* 价格缓存
* run 配置里的 `end_date`

## 6. 距离实盘还有多远

### 6.1 现在可以做什么

当前已经可以：

* 把 `M-provider` 作为 shadow / paper 组合候选
* 把 `M-PIT` 作为研究主线继续维护
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

* 做 `M-PIT + 少量 provider valuation overlay`

更具体地说：

* 保留 `M-PIT` 的财报主轴
* 只加非常克制的一层 provider 估值，例如 `pb / pe_ttm`
* 不要一上来把整套 provider 量价块一起混进去

原因：

* `M-PIT` 已经证明自己更像研究主线
* provider 这边继续调 size 强度，边际信息已经不高
* 现在最值钱的问题变成：`provider` 的低频估值层，能不能给 `M-PIT` 带来干净增量

### 7.2 第二优先

* 对胜出的月频线做换手优化

优先考虑：

* `buffer_entry / buffer_exit`
* `top_k`

原因：

* 这一步应该放在主信号相对明确之后
* 不然很容易分不清，是信号更好了，还是只是交易更少了

### 7.3 第三优先

* 做一个截至 `2026-03-31` 的 monthly 新 snapshot

这里要特别注意：

* 当前 split 是按比例切的，不是固定日期切的
* 所以把 `end_date` 往后推重跑，会轻微挪动 train / test / final OOS 边界
* 更干净的做法是把今天这批 run 当成冻结快照保留，再额外做一批截至 `2026-03-31` 的新 snapshot

## 8. 不建议继续优先做什么

* 不把 `size-neutral provider` 当成下一阶段主战场
* 不继续围着 provider 做更硬或更软的 size 微调
* 不把 `Q-PIT` 从 benchmark 重新拔高成 monthly 研究主线替代品
* 不直接做“大而全 provider + PIT + tech + valuation” 黑箱混合版

## 9. 给下一位 Codex 的接手提示

### 9.1 先看哪些文件

先看：

1. 本页
2. `docs/research/notes/hk-monthly-provider-vs-pit-20260330.md`
3. `docs/research/notes/hk-monthly-provider-factor-probes-20260330.md`
4. 各核心 run 目录下的 `summary.json`
5. 各核心 run 目录下的 `config.used.yml`

### 9.2 当前最该信什么

* `config.used.yml` 比本地 `configs/local/` 更权威
* `summary.json` 比口头复述更权威
* 当前 monthly 分工应理解为：
  * `M-PIT`：研究主线
  * `M-provider`：实现 comparator / 候选
  * `Q-PIT`：低频 benchmark

### 9.3 当前最重要的 open questions

* `M-PIT` 加一层轻量 provider 估值 overlay 后，能不能在不污染信号故事的前提下改善 long-only 实现
* 如果把 monthly 数据扩到 `2026-03-31`，这两条线的新 snapshot 还是否维持当前排序
* `M-PIT` 在做了更保守的 turnover 优化之后，能不能缩小和 `provider` 的实现差距

### 9.4 继续往后扩样本时要记住什么

* 不要把“新 end_date 重跑”误写成“旧 OOS 自然延长”
* 更合理的说法是：
  * 旧 run：截至 `2025-12-31` 的冻结 snapshot
  * 新 run：截至 `2026-03-31` 的扩展 snapshot
* 这样未来回看时，才能分清哪些结论是当时就有的，哪些是后来新样本带来的

## 10. 当前推荐阅读顺序

如果你今天重新进入 monthly 研究，建议按下面顺序读：

1. 本页：先把主线、候选、实盘距离和下一步看对。
2. [`hk-monthly-provider-vs-pit-20260330.md`](./hk-monthly-provider-vs-pit-20260330.md)：再看 provider 和 PIT 到底差在哪里。
3. [`hk-monthly-provider-factor-probes-20260330.md`](./hk-monthly-provider-factor-probes-20260330.md)：如果你要继续追 provider 线为什么强、为什么又不够干净，再看这一页。
4. 核心 run 目录下的 `summary.json` / `config.used.yml`：最后再下手复现或继续派生配置。

## 11. 一句话结论

截至 `2026-03-30`，HK monthly 最合理的现行口径仍然是：

* `M-PIT` 作为研究主线继续推进
* `M-provider rebalance-only` 作为正式月频 comparator / 实现候选保留
* 下一步优先做 `M-PIT + 少量 provider valuation overlay`
* 同时准备一批截至 `2026-03-31` 的新 snapshot，并把当前 run 当成冻结历史快照保存
