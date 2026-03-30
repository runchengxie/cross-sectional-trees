# HK Monthly Provider vs PIT 对比笔记（2026-03-30）

本页解决什么：解释 `M-provider rebalance-only` 和 `M-PIT sidecar` 分别是什么，记录这轮月频 head-to-head 的结果，并回答 provider 那条更强 OOS 曲线更像吃到了什么风格暴露。  
本页不解决什么：不把这轮 OOS 当成最终验证，也不把风格相关性包装成严格因果归因。  
适合谁：已经看过三线框架，准备决定“月频正式主线”和“月频实现候选”该怎么分工的人。  
读完你会得到什么：两条月频线的语义区别、当前证据边界、持仓差异，以及 provider 曲线更像是不是 `size / valuation / trend` 在发力。  
相关页面：`docs/playbooks/hk-selected.md`、`docs/research/README.md`

页面性质：`research-note`  
最后核对时间：`2026-03-30`  
权威来源：两条 run 的 `summary.json` / `config.used.yml` / `positions_by_rebalance_oos.csv`、HK selected PIT universe by-date 文件、provider valuation cache、本地 daily `tr_close` cache  
冲突优先级：如果与具体 run 产物冲突，以 run 目录下的 `summary.json` / `config.used.yml` 为准；如果与更晚样本冲突，以更晚样本为准

> 注：本页涉及的月频派生配置当时保存在作者本地 `configs/local/`，默认不纳入版本控制。为避免把个人文件误当成仓库入口，下文只保留派生配置名；最终仍以各 run 目录里的 `config.used.yml` 为准。

## 1. 分析对象

这次只看两条月频线：

* `M-provider rebalance-only`
  * 派生配置名：`hk_selected__m_provider_mainline_rebalance_only_tr_close_exec_balanced`
  * run：`artifacts/runs/hk_sel_m_provider_mainline_rebalance_only_tr_close_exec_balanced_20260330_002336_c12762fc/`
* `M-PIT sidecar`
  * 派生配置名：`hk_selected__m_pit_core_hybrid_sidecar_tr_close_exec_balanced`
  * run：`artifacts/runs/hk_sel_m_pit_core_hybrid_sidecar_tr_close_exec_balanced_20260330_001434_eb10ec79/`

## 2. 先把名词讲清楚

### 2.1 `provider` 在这里是什么意思

这里的 `provider` 不是“全量基本面”。

它具体指：

* 主基本面走 `fundamentals.source=provider`
* 当前 HK provider 模式固定是 RQData `get_factor`
* 实际并到 daily panel 的字段主要是日频估值：
  * `market_cap`
  * `pe_ttm`
  * `pb`
* 再叠加月频默认量价特征：
  * `sma_*`
  * `rsi_14`
  * `macd_hist`
  * `volume_sma5_ratio`
  * `vol`

所以 `M-provider` 更准确的理解是：

* `日频估值 + 量价`
* 不是财报 PIT 主导

### 2.2 `PIT` 在这里是什么意思

这里的 `PIT` 指：

* 主基本面走 `fundamentals.source=file`
* 文件是本地 PIT 财报平面
* 研究链路按 `symbol` 做 `ffill`
* 特征主轴是财报增长 / 盈利质量 / 披露陈旧度：
  * `growth_sales`
  * `growth_net_profit`
  * `growth_cash_flow_from_operating_activities`
  * `profit_margin`
  * `cfo_to_profit`
  * `days_since_report`
* 再保留一组慢量价辅助特征

所以 `M-PIT` 更准确的理解是：

* `PIT 财报 + 慢量价`
* 财报是主轴，量价是辅助

### 2.3 `rebalance-only` 是什么意思

`rebalance-only` 指 `sample_on_rebalance_dates=true`。

这意味着：

* 模型样本不是每天一条横截面
* 而是只保留每个调仓日那一条横截面
* `purge / embargo` 也会从“日数”换算成“调仓步数”

所以这版 `M-provider rebalance-only` 的意义不是换特征，而是把评估口径和 `M-PIT` 对齐，做真正 apples-to-apples 的月频对比。

## 3. 先记住 5 句

* 这两条月频线不是“同一篮子股票换个打分器”，而是两条几乎完全不同的组合。
* `M-PIT` 仍然更像横截面研究主线，因为测试段和 final OOS 的 IC 都是正的。
* `M-provider rebalance-only` 更像实现候选，因为它的 long-only OOS 曲线明显更强。
* provider 那条强 OOS 曲线，更像吃到了 `small-cap + 短周期价格结构`，不是纯粹吃到了 PIT 财报信息。
* 这段样本里 classic value 是正的，但 provider 相对 PIT 并没有明显更 cheap，所以“value 主导”这个说法不成立。

## 4. 这轮结果快照

`M-provider rebalance-only`：

* test `IC = 2.12% (p = 0.190)`
* final OOS `IC = -2.00% (p = 0.281)`
* final OOS long-only backtest `ann = 62.7%`, `sharpe = 1.73`
* walk-forward mean `ann = 11.2%`, `sharpe = 0.552`

`M-PIT sidecar`：

* test `IC = 4.32% (p = 0.016)`
* final OOS `IC = 4.88% (p = 0.093)`
* final OOS long-only backtest `ann = 24.3%`, `sharpe = 0.78`
* walk-forward mean `ann = 11.2%`, `sharpe = 0.509`

所以这轮最合理的分工还是：

* `M-PIT`：研究主线
* `M-provider rebalance-only`：正式月频 comparator / 实现候选

## 5. 持仓到底有多像

不太像。

在两条线共有的 `24` 个 OOS 月度调仓点上：

* 平均重合名字数只有 `1.92 / 20`
* 平均 Jaccard 只有 `0.077`
* 单期最低 `0`
* 单期最高也只有 `5`

这已经不是“轻微偏好差异”，而是两条基本在买不同的组合。

更具体地看，高频出现的差异名字：

`provider-only` 更常见：

* `09688.HK`
* `06060.HK`
* `01877.HK`
* `06185.HK`
* `00819.HK`

`PIT-only` 更常见：

* `01818.HK`
* `00005.HK`
* `00939.HK`
* `02359.HK`
* `02888.HK`

这也解释了为什么两条线的 OOS 曲线会差这么多：它们不是在同一组股票上做不同排序，而是组合结构本身就已经分叉。

## 6. 风格暴露怎么看

这里用的是一组统一 proxy，不直接照抄模型内部列名：

* `small_score`：越大表示越偏小盘
* `cheap_pb_score`：越大表示越偏低 `pb`
* `cheap_pe_score`：越大表示越偏低 `pe_ttm`
* `trend60_score`：越大表示 `60d` 动量越强
* `trend120_score`：越大表示 `120d` 动量越强
* `sma20_score`：越大表示价格相对 `20d` 均线更强

这些分数都按每个 rebalance date 做了截面 rank，中位附近大致是 `0`。

OOS 平均暴露：

`M-provider`：

* `small_score = 0.146`
* `cheap_pb_score = -0.098`
* `cheap_pe_score = 0.006`
* `trend60_score = 0.044`
* `trend120_score = 0.019`
* `sma20_score = -0.011`

`M-PIT`：

* `small_score = -0.057`
* `cheap_pb_score = -0.068`
* `cheap_pe_score = -0.005`
* `trend60_score = -0.009`
* `trend120_score = 0.045`
* `sma20_score = -0.009`

`provider - PIT` 的平均暴露差：

* `small_score = +0.203`
* `cheap_pb_score = -0.030`
* `cheap_pe_score = +0.010`
* `trend60_score = +0.053`
* `trend120_score = -0.026`
* `sma20_score = -0.002`

解释：

* provider 明显更偏小盘
* provider 略偏强一点的 `60d` 趋势
* 但 provider 并不比 PIT 更便宜，至少按 `pb` 看反而略贵
* PIT 更像“不是小盘，也不是追短趋势，更靠财报排序本身”

## 7. provider 那条强 OOS 曲线，到底是不是风格在发力

结论可以压成一句：

* `是，但更像 small-cap + 短周期价格结构，不太像 classic value，也不太像中期 momentum。`

这里做了两层检查。

### 7.1 先看样本里哪些风格本身在赚钱

用同一 universe、同一调仓点、同一 `entry_date -> next_entry_date` 窗口，做 top-bottom quintile spread：

* `small_spread = +1.57%`
* `cheap_pb_spread = +1.69%`
* `cheap_pe_spread = +1.78%`
* `trend60_spread = -1.79%`
* `trend120_spread = -1.63%`
* `sma20_spread = +1.92%`

说明这段 OOS 里：

* 小盘是赚钱的
* value 也是赚钱的
* 中期 momentum 反而是负的
* 更短周期的价格结构（这里用 `sma20_gap` 代理）是正的

### 7.2 再看 `provider - PIT` 的收益差和这些 spread 的相关性

同一批共有 OOS 月份上，`provider` 的计划持有期平均收益比 `PIT` 高约 `+1.13%`。  
把这个 `provider_minus_pit` 跟上面的风格 spread 做相关：

* 对 `small_spread` 相关约 `+0.326`
* 对 `cheap_pb_spread` 相关约 `+0.279`
* 对 `cheap_pe_spread` 相关约 `-0.024`
* 对 `trend60_spread` 相关约 `-0.174`
* 对 `trend120_spread` 相关约 `-0.190`
* 对 `sma20_spread` 相关约 `+0.393`

这组数字最值得看的不是绝对大小，而是方向：

* `small` 正相关
* `sma20` 正相关
* `60d / 120d momentum` 反而不是正相关

再结合上一节的平均持仓暴露，可以得到比较稳的解释：

* provider 曲线强，确实带有风格成分
* 主要嫌疑是：
  * 更偏小盘
  * 更偏短周期技术结构
* 不是：
  * 纯 value
  * 纯中期 momentum

### 7.3 为什么不能直接说“provider 就只是风格 beta”

还不能这么说，原因有两点：

* 这里的相关性分析是研究级 proxy，不是严格风险模型回归
* provider 和 PIT 的组合重合度极低，说明除了风格倾斜，它们还在做不同的个股选择

所以更准确的话应该是：

* provider 的强 OOS，不是纯 alpha 黑箱
* 也不是可以被一句“只是 value/trend”打发掉
* 当前更像 `small-cap + 短结构 + 个股选择` 的混合结果

## 8. 第一批 provider 拆解配置

为了先回答“provider 的强 OOS 到底主要来自哪里”，本地先固定一批最小拆解，不直接上大而全 hybrid。

当前这批配置包括：

* baseline：`hk_selected__m_provider_mainline_rebalance_only_tr_close_exec_balanced`
* no-size：`hk_selected__m_provider_mainline_rebalance_only_no_size_tr_close_exec_balanced`
* tech-only：`hk_selected__m_provider_mainline_rebalance_only_tech_only_tr_close_exec_balanced`
* valuation-only：`hk_selected__m_provider_mainline_rebalance_only_valuation_only_tr_close_exec_balanced`

每条在回答什么：

* baseline：保留当前 `provider rebalance-only` 全量口径，作为对照组
* no-size：保留 `pe_ttm + pb + tech`，去掉 `market_cap / log_mcap`，先看 provider 曲线是否主要靠 size 暴露
* tech-only：只保留 `sma / rsi / macd / volume` 这组量价，回答 provider 更像技术策略还是估值策略
* valuation-only：只保留 `market_cap / pe_ttm / pb / log_mcap`，看日频 asof 估值块单独能不能站住

为什么这一批先不直接加 `size-neutral`：

* `size-neutral` 更像组合约束 / 排序中和探针，不只是删字段
* 它值得做，但不适合和字段消融一起上
* 先跑完这批，再决定 `size-neutral` 是走组合层约束还是排序层处理，会更干净

## 9. 第一批 provider 拆解结果

对应 run：

* baseline：`artifacts/runs/hk_sel_m_provider_mainline_rebalance_only_tr_close_exec_balanced_20260330_002336_c12762fc/`
* no-size：`artifacts/runs/hk_sel_m_provider_mainline_rebalance_only_no_size_tr_close_exec_balanced_20260330_092944_d135d140/`
* tech-only：`artifacts/runs/hk_sel_m_provider_mainline_rebalance_only_tech_only_tr_close_exec_balanced_20260330_093056_d17aff35/`
* valuation-only：`artifacts/runs/hk_sel_m_provider_mainline_rebalance_only_valuation_only_tr_close_exec_balanced_20260330_093153_68415c81/`

先看最短结论：

* baseline 的强 final OOS 不是单一模块单独就能复现
* 去掉 size 之后，provider 这条线掉得最明显
* tech-only 和 valuation-only 都还能跑出能看的 long-only 曲线
* 但这两条单模块线都没有表现出足够干净的横截面排序证据

### 9.1 baseline vs no-size

baseline：

* test `IC = 2.12% (p = 0.190)`
* final OOS `IC = -2.00% (p = 0.281)`
* final OOS `ann = 62.7%`, `sharpe = 1.73`

no-size：

* test `IC = 0.72% (p = 0.619)`
* final OOS `IC = 0.24% (p = 0.891)`
* final OOS `ann = 26.2%`, `sharpe = 0.89`

这组对比最重要的信息不是“去掉 size 以后收益仍然为正”，而是：

* test 段已经明显变差，成本后年化转负
* final OOS 曲线也被腰斩
* OOS 平均换手从 `66.3%` 升到 `78.8%`

所以当前最稳的判断是：

* baseline 那条更强的实现曲线，size 暴露确实是重要组成部分
* provider 的强 OOS 不能解释成“就算没有 size 也差不多”

### 9.2 tech-only vs valuation-only

tech-only：

* test `IC = -1.29% (p = 0.318)`
* final OOS `IC = -0.24% (p = 0.913)`
* final OOS `ann = 31.6%`, `sharpe = 1.10`
* final OOS `avg_turnover = 84.1%`

valuation-only：

* test `IC = 0.64% (p = 0.660)`
* final OOS `IC = -1.06% (p = 0.601)`
* final OOS `ann = 24.5%`, `sharpe = 0.74`
* final OOS `avg_turnover = 39.7%`

解释：

* tech-only 的 long-only 曲线比 valuation-only 更强，但排序证据更脏，换手也显著更高
* valuation-only 的 long-only 曲线稍弱，但更低换手、更像一个温和的估值底座
* 这说明 provider 线不是纯粹靠某一个 valuation 字段吃饭，也不是 tech 模块单独就能解释全部优势

### 9.3 walk-forward 怎么看

四窗均值：

* baseline：`ann = 11.2%`, `sharpe = 0.552`
* no-size：`ann = -0.1%`, `sharpe = 0.114`
* tech-only：`ann = 17.8%`, `sharpe = 0.603`
* valuation-only：`ann = 13.4%`, `sharpe = 0.677`

这里要注意两件事：

* tech-only 的 final OOS 比 baseline 弱很多，但 walk-forward 均值不差，说明它更像“有实现价值，但不是干净排序器”
* valuation-only 的 walk-forward 也不差，而且换手更低，所以它更像 provider 组合里的稳定底座，而不是最近这段强 OOS 的唯一来源

### 9.4 这批拆解之后该怎么定性

这一轮最值得保留的结论是：

* provider 这条强 OOS，确实和 size 有明显关系
* 去掉 size 之后，provider 不能维持原来的实现强度
* tech 模块更像收益推动器，但证据不干净、换手偏高
* valuation 模块更像稳定器，单独拿出来不够强，但也不是没用

所以如果下一步只做一件事，优先级最高的仍然是：

* 做 `size-neutral provider` 探针，而不是直接跳去大而全 `provider + PIT` hybrid

## 10. 这对下一步意味着什么

### 10.1 现在怎么用这两条线

最合理的记账方式：

* `M-PIT` 继续当研究主线，因为它的 IC 证据更像横截面排序
* `M-provider rebalance-only` 当月频正式 comparator / 实现候选，因为 long-only 曲线更强

### 10.2 如果你想继续追问 provider 曲线

更值得写的 follow-up，不是继续加更多 provider 特征，而是：

1. 做一个 `size-neutral` 或 `log_mcap` 受限版本，看 provider 曲线还能剩多少。
2. 做一个去掉最强技术列的 probe，例如压掉 `macd_hist / sma_*_diff`。
3. 对 `provider-only` 高频名字做行业和流动性归类，看是不是某几类股票在主导。

如果这些约束一加，provider 曲线明显塌，而 PIT 相对稳定，那就能更明确地把 provider 的 OOS 亮点解释成风格驱动而不是更稳的结构 alpha。

## 11. 方法边界

这里的持仓与风格分析有几个边界要记住：

* 风格 proxy 用的是统一外部口径：
  * provider valuation cache
  * 本地 daily `tr_close`
* 不是精确复刻模型内部所有特征
* spread return 用的是 `entry_date -> next_entry_date` 的计划持有期 gross return
* 不是 backtest 的净收益归因
* 所以它适合回答“方向像什么”，不适合回答“精确贡献是多少”
