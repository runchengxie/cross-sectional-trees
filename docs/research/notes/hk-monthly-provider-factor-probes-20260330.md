# HK Monthly Provider Factor Probes（2026-03-30）

本页解决什么：把 `M-provider rebalance-only` 这条月频实现候选的字段拆解、`size-neutral` probe 和 `soft size control` probe 单独收成一页，避免主对比页继续膨胀成实验流水账。  
本页不解决什么：不重新解释 `provider` 和 `PIT` 的基本语义，也不替代 monthly 现行口径总入口。  
适合谁：已经知道 `M-provider` 和 `M-PIT` 的区别，准备继续追问“provider 那条强 OOS 到底主要来自哪里”的读者。  
读完你会得到什么：provider 线的最小字段消融结论、size 相关 probe 的边界，以及为什么这条线现在更适合当实现 comparator 而不是研究主线。  
相关页面：`docs/research/notes/hk-monthly-current-state-20260330.md`、`docs/research/notes/hk-monthly-provider-vs-pit-20260330.md`、`docs/research/README.md`

页面性质：`research-note`  
最后核对时间：`2026-03-30`  
权威来源：本页列出的各 run 目录下 `summary.json` / `config.used.yml` / `positions_by_rebalance_oos.csv`，以及相关本地 style 标签文件  
冲突优先级：如果与具体 run 产物冲突，以 run 目录下的 `summary.json` / `config.used.yml` 为准；如果与更晚样本冲突，以更晚样本为准

> 注：本页涉及的月频派生配置当时保存在作者本地 `configs/local/`，默认不纳入版本控制。为避免把个人文件误当成仓库入口，下文只保留派生配置名；最终仍以各 run 目录里的 `config.used.yml` 为准。

## 1. 分析对象

这页只看 `M-provider rebalance-only` 这条线的 follow-up probes。

基线 run：

* baseline：`artifacts/runs/hk_sel_m_provider_mainline_rebalance_only_tr_close_exec_balanced_20260330_002336_c12762fc/`

后续 probes：

* no-size：`artifacts/runs/hk_sel_m_provider_mainline_rebalance_only_no_size_tr_close_exec_balanced_20260330_092944_d135d140/`
* tech-only：`artifacts/runs/hk_sel_m_provider_mainline_rebalance_only_tech_only_tr_close_exec_balanced_20260330_093056_d17aff35/`
* valuation-only：`artifacts/runs/hk_sel_m_provider_mainline_rebalance_only_valuation_only_tr_close_exec_balanced_20260330_093153_68415c81/`
* size-bucket hard-cap：`artifacts/runs/hk_sel_m_provider_mainline_rebalance_only_size_bucket_q4_cap5_tr_close_exec_balanced_20260330_094935_f8c9e35b/`
* soft-half：`artifacts/runs/hk_sel_m_provider_mainline_rebalance_only_soft_size_half_tr_close_exec_balanced_20260330_102756_e546303e/`
* soft-full：`artifacts/runs/hk_sel_m_provider_mainline_rebalance_only_soft_size_full_tr_close_exec_balanced_20260330_103558_6107d181/`

## 2. 第一批 provider 拆解配置

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

## 3. 第一批 provider 拆解结果

先看最短结论：

* baseline 的强 final OOS 不是单一模块单独就能复现
* 去掉 size 之后，provider 这条线掉得最明显
* tech-only 和 valuation-only 都还能跑出能看的 long-only 曲线
* 但这两条单模块线都没有表现出足够干净的横截面排序证据

### 3.1 baseline vs no-size

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

### 3.2 tech-only vs valuation-only

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

### 3.3 walk-forward 怎么看

四窗均值：

* baseline：`ann = 11.2%`, `sharpe = 0.552`
* no-size：`ann = -0.1%`, `sharpe = 0.114`
* tech-only：`ann = 17.8%`, `sharpe = 0.603`
* valuation-only：`ann = 13.4%`, `sharpe = 0.677`

这里要注意两件事：

* tech-only 的 final OOS 比 baseline 弱很多，但 walk-forward 均值不差，说明它更像“有实现价值，但不是干净排序器”
* valuation-only 的 walk-forward 也不差，而且换手更低，所以它更像 provider 组合里的稳定底座，而不是最近这段强 OOS 的唯一来源

### 3.4 这批拆解之后该怎么定性

这一轮最值得保留的结论是：

* provider 这条强 OOS，确实和 size 有明显关系
* 去掉 size 之后，provider 不能维持原来的实现强度
* tech 模块更像收益推动器，但证据不干净、换手偏高
* valuation 模块更像稳定器，单独拿出来不够强，但也不是没用

## 4. 方法边界

这里的 provider probe 有几个边界要记住：

* 它们适合回答“provider 曲线更像靠什么在跑”
* 不适合直接替代 `provider vs PIT` 的主线比较
* 它们主要看的是：
  * `summary.json`
  * `positions_by_rebalance_oos.csv`
  * 统一外部 valuation / size proxy
* 不等于一套严格风险模型归因

## 5. size-neutral provider 探针

### 5.1 这次具体做了什么

这次没有改框架代码，也没有上严格回归中性化，而是先做一个近似 probe：

* 派生配置：`hk_selected__m_provider_mainline_rebalance_only_size_bucket_q4_cap5_tr_close_exec_balanced`
* 对应 run：`artifacts/runs/hk_sel_m_provider_mainline_rebalance_only_size_bucket_q4_cap5_tr_close_exec_balanced_20260330_094935_f8c9e35b/`
* 本地 join 标签：`artifacts/assets/style/hk_selected_size_bucket_q4_mcap_m_20260330.parquet`

做法：

* 用当前 `hk_selected` PIT universe 的月频网格
* 从本地 valuation snapshot 取 `hk_total_market_val`
* 每个 rebalance date 内按市值切四档：
  * `Q1_small`
  * `Q2_mid_small`
  * `Q3_mid_large`
  * `Q4_large`
* 回测层加：
  * `backtest.group_col = size_bucket_q4`
  * `backtest.max_names_per_group = 5`

所以这条线的语义不是“完全 size-neutral”，而是：

* 不允许 top-20 组合在某一个 size bucket 里无限堆名字
* 先看 provider 曲线在被强行削弱小盘集中度以后，还能剩下多少

### 5.2 结果怎么变了

和原始 baseline 对比：

baseline：

* test `IC = 2.12%`
* test backtest `ann = 13.6%`, `sharpe = 0.653`
* final OOS `IC = -2.00%`
* final OOS backtest `ann = 62.7%`, `sharpe = 1.73`
* walk-forward mean `ann = 11.2%`, `sharpe = 0.552`

size-bucket cap probe：

* test `IC = 2.13%`
* test backtest `ann = 15.1%`, `sharpe = 0.650`
* final OOS `IC = -2.05%`
* final OOS backtest `ann = 54.9%`, `sharpe = 1.54`
* walk-forward mean `ann = 6.9%`, `sharpe = 0.375`

这组数字最值得看的不是 test 段，而是：

* final OOS 曲线明显变弱
* walk-forward 均值掉得更明显
* `IC` 并没有因为加了 size cap 就变干净

所以这条 probe 给出的结论很直接：

* provider 的强 OOS，不只是“碰巧带一点小盘暴露”
* 把小盘集中度压掉以后，它的实现层优势会明显收缩
* 但压掉以后，排序证据也没有因此变得更漂亮

### 5.3 这个 cap 到底有没有真的生效

有，而且是明确生效了。

OOS 持仓层面：

* baseline 平均每期持仓约 `12.8`
* probe 平均每期持仓约 `10.8`
* probe 在所有 OOS 月份都满足“单一 size bucket 不超过 5 只”

平均 bucket 分布：

baseline：

* `Q1_small = 6.17`
* `Q2_mid_small = 3.58`
* `Q3_mid_large = 0.71`
* `Q4_large = 2.33`
* 平均 `small share = 49.5%`
* 平均 `size_rank_pct = 0.366`

probe：

* `Q1_small = 4.50`
* `Q2_mid_small = 3.21`
* `Q3_mid_large = 0.88`
* `Q4_large = 2.25`
* 平均 `small share = 44.4%`
* 平均 `size_rank_pct = 0.404`

解释：

* 这个 cap 确实把组合往更大的 size bucket 拉了一点
* 但它没有把组合变成 `5 / 5 / 5 / 5` 的完全均衡篮子
* 原因也很清楚：这是上限约束，不是配额约束；当前 provider 排序在中大盘桶里并没有足够强的候选去把空位自然补满

### 5.4 这条 probe 说明了什么

这一轮之后，关于 provider 可以更明确地说：

* 它的强 OOS 确实部分依赖小盘集中度
* 但简单加一个硬 group cap，不会把它自动洗成更干净的结构 alpha
* 这条线仍然更像“实现候选”，不是更强研究主线

## 6. soft size control probe

这轮补的是“分数层”的软 size 控制，而不是组合层的硬 bucket cap。

本地配置：

* `hk_selected__m_provider_mainline_rebalance_only_soft_size_half_tr_close_exec_balanced`
* `hk_selected__m_provider_mainline_rebalance_only_soft_size_full_tr_close_exec_balanced`

做法：

* 在模型打分之后，按 `trade_date` 对最终 score 和 `log_mcap` 做截面线性去相关
* `half` 版本只去掉 `50%` 的 `log_mcap` 线性暴露
* `full` 版本去掉 `100%` 的 `log_mcap` 线性暴露
* 不改训练样本、不改 provider 特征集，只改最终排序信号

对应 run：

* `soft-half`：`artifacts/runs/hk_sel_m_provider_mainline_rebalance_only_soft_size_half_tr_close_exec_balanced_20260330_102756_e546303e/`
* `soft-full`：`artifacts/runs/hk_sel_m_provider_mainline_rebalance_only_soft_size_full_tr_close_exec_balanced_20260330_103558_6107d181/`

### 6.1 head-to-head 结果

和已有两条 provider probe 放在一起看：

* baseline：`test IC = 2.12%`，`final OOS IC = -2.00%`，`final OOS ann = 62.7%`，`sharpe = 1.73`
* hard-cap：`test IC = 2.13%`，`final OOS IC = -2.05%`，`final OOS ann = 54.9%`，`sharpe = 1.54`
* soft-half：`test IC = 2.34%`，`final OOS IC = -1.94%`，`final OOS ann = 46.9%`，`sharpe = 1.52`
* soft-full：`test IC = 2.54%`，`final OOS IC = -1.82%`，`final OOS ann = 27.8%`，`sharpe = 0.98`

测试段解读：

* soft 控制没有把 provider 的测试段打死，反而 `IC / long-short` 有小幅改善
* `soft-full` 的测试段最强，`test ann = 16.5%`、`sharpe = 0.69`
* 但这些改善主要停留在测试段，没转化成更干净的最终 OOS 排序证据

最终 OOS 解读：

* 两条 soft 版本的 `final OOS IC` 仍然是负的，`p-value` 也不显著
* `soft-half` 仍保住了不错的 long-only 账面，`ann = 46.9%`、`sharpe = 1.52`
* `soft-full` 的 long-only 曲线被明显削弱，`ann` 从 baseline 的 `62.7%` 掉到 `27.8%`
* 所以“把 size 暴露处理得更软”并没有把 provider 变成更干净的横截面排序器；继续加大 neutralization 只是在持续削弱实现曲线

### 6.2 size 结构到底改了多少

看 OOS 持仓结构，soft 控制是生效的，而且比硬 cap 更明显：

* baseline：`Q1_small` 平均占比约 `49.5%`，`Q4_large` 约 `17.9%`，平均 `size_rank_pct ≈ 0.359`
* hard-cap：`Q1_small` 约 `44.4%`，`Q4_large` 约 `19.4%`，平均 `size_rank_pct ≈ 0.385`
* soft-half：`Q1_small` 约 `41.1%`，`Q4_large` 约 `29.7%`，平均 `size_rank_pct ≈ 0.451`
* soft-full：`Q1_small` 约 `29.3%`，`Q4_large` 约 `47.2%`，平均 `size_rank_pct ≈ 0.578`

这说明：

* soft neutralization 比硬 cap 更有效地把组合往大盘端推
* 但 size 结构变干净以后，provider 的 OOS 排序证据并没有同步转正
* 所以 baseline 那条强 OOS 曲线，不只是“需要一点 size”，而是相当程度上和这类 size 倾斜绑定在一起

### 6.3 这轮 probe 之后怎么定

这轮之后，对 provider 更准确的定性是：

* `provider` 作为实现候选仍然成立，但它的强 OOS 账面明显依赖 size 倾斜
* soft size control 能改善风格暴露，却没有把它洗成更强的结构 alpha
* `M-PIT` 继续保留研究主线地位，这一点没有改变

因此，provider 线上下一步最值得做的已经不再是“继续调 size-neutral 强度”，而是：

1. 如果要继续用 provider，接受它更像实现 comparator，而不是主研究线。
2. 真正值得继续试的是 `PIT + 少量 provider overlay`，例如只加 `pb / pe_ttm` 这类低频估值层，而不是整套 provider 量价块。
