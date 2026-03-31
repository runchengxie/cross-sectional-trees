标题：HK Monthly `M-PIT` Frozen vs Latest 稳定性拆解与首轮结果  
日期：`2026-03-30`  
状态：`active deep-dive`，这页同时回答“该怎么拆解 `M-PIT` 从 frozen 到 latest 的变化”以及“`R0-R4` 首轮实跑到底说明了什么”，不替代 [`hk-monthly-current-state-20260330.md`](./hk-monthly-current-state-20260330.md)

## 一句话结论

`R0-R4` 首轮实跑已经把方向压得很清楚：

* `2025-12-31` cutoff 下，无论用 old ratio split 还是 fixed `24m` final OOS，`M-PIT` 都仍然是正 `IC`
* 一旦窗口推进到 `asof_20260327`，无论用 old ratio split 还是 fixed `24m` final OOS，`M-PIT` 都转成负 `IC`
* 所以这轮 monthly 的主要矛盾不是 split 口径本身，而更像最近新增月份对应的 regime / sample-window 变化

## 这页回答什么

核心问题只有一个：

* 为什么旧 frozen snapshot 里，`M-PIT` 还像“正 IC 的研究主线”；但更新到 `asof_20260327 + 24m final OOS` 后，基线已经转弱？

这不是一个适合继续靠加特征回答的问题。  
先把原因拆清，后面的 overlay、construction、modern-only probe 才有意义。

## 先说两个边界

### 1. 旧 frozen run 不是“坏切分”

当前仓库里记录下来的旧 frozen anchor 是：

* run: `artifacts/runs/hk_sel_m_pit_core_hybrid_sidecar_tr_close_exec_balanced_20260330_001434_eb10ec79`

它本身已经是：

* `rebalance_gap_days = 21.0`
* `purge_steps = 2`
* `embargo_steps = 1`
* `train/test/final_oos = 38 / 61 / 25`

所以这轮 `frozen vs latest` 设计，不是在追“旧 frozen 是不是也吃了后来那种 `20/22` 月级 purge bug”。  
那类坏切分主要出现在后面那批本地 overlay probe 的早期坏 run，不是这条 frozen anchor 本身。

### 2. 旧 frozen snapshot 没有被独立冻成单独资产包

当前仓库只有一份最新的：

* `artifacts/assets/universe/hk_selected_pit_research_by_date.csv`
* `artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest/pipeline_fundamentals.parquet`

并没有单独保留“截至 `2025-12-31` 的 frozen universe 文件”。

这意味着：

* 用当前资产把 `end_date` 切回 `20251231`，可以做很有价值的 `recut`
* 但它不是 bitwise reproduction
* 它会同时带进 universe/PIT/provider 历史刷新后的状态

这不是缺点，而正是这轮实验要利用的信息：

* `recorded frozen` vs `frozen recut with current assets`

可以直接告诉我们，旧结论里有多少是“当时的资产状态”在起作用。

## 当前两个锚点

### 历史 frozen reference

历史 reference 就用仓库里已经存在的这条：

* `hk_sel_m_pit_core_hybrid_sidecar_tr_close_exec_balanced_20260330_001434_eb10ec79`

关键口径：

* `data.end_date = 20251231`
* `eval.test_size = 0.6`
* `eval.final_oos.size = 0.2`
* `final OOS = 2023-11-30 -> 2025-11-27`
* `final OOS IC = +4.88%`
* `ann = 24.3%`
* `sharpe = 0.78`

### 最新 latest anchor

当前最新锚点就用这条：

* `hk_sel_m_pit_core_hybrid_sidecar_diag_tr_close_exec_balanced_20260330_155212_d2b52da6`

关键口径：

* `data.end_date = 20260327`
* `eval.test_size = 0.5`
* `eval.final_oos.size = 24`
* `final OOS = 2024-02-29 -> 2026-01-30`
* `final OOS IC = -7.30%`
* `ann = 26.0%`
* `sharpe = 0.84`

## 最小而有信息量的实验矩阵

我建议先做 `1` 个历史 reference + `3` 个新 recut。

| 组别 | 配置 / run | cutoff | split | 作用 |
| --- | --- | --- | --- | --- |
| `R0` | 已有历史 reference | `2025-12-31` | `0.6 + 0.2比例式 final OOS` | 当时结论的记录值 |
| `R1` | `hk_selected__m_pit_core_hybrid_sidecar_diag_frozen_ratio_tr_close_exec_balanced.yml` | `2025-12-31` | `0.6 + 0.2比例式 final OOS` | 看 current assets 下，旧 cut + 旧 split 还站不站得住 |
| `R2` | `hk_selected__m_pit_core_hybrid_sidecar_diag_frozen_fixed24_tr_close_exec_balanced.yml` | `2025-12-31` | `0.5 + 24m final OOS` | 在同一 cutoff 下隔离 split 影响 |
| `R3` | `hk_selected__m_pit_core_hybrid_sidecar_diag_latest_ratio_tr_close_exec_balanced.yml` | `2026-03-27` | `0.6 + 0.2比例式 final OOS` | 在最新 cutoff 下反查 old split 敏感度 |
| `R4` | 已有 latest anchor | `2026-03-27` | `0.5 + 24m final OOS` | 当前主锚点 |

## `R0-R4` 首轮实跑结果

### 结果表

| 组别 | run | cutoff / split | final OOS | `IC` | 年化 / Sharpe |
| --- | --- | --- | --- | ---: | ---: |
| `R0` | `hk_sel_m_pit_core_hybrid_sidecar_tr_close_exec_balanced_20260330_001434_eb10ec79` | `20251231` / `0.6 + 0.2 ratio` | `2023-11-30 -> 2025-11-27` | `+4.88%` | `24.3% / 0.78` |
| `R1` | `hk_sel_m_pit_core_hybrid_sidecar_diag_frozen_ratio_tr_close_exec_balanced_20260330_163548_17a6965f` | `20251231` / `0.6 + 0.2 ratio` | `2023-10-31 -> 2025-10-31` | `+6.74%` | `25.4% / 0.92` |
| `R2` | `hk_sel_m_pit_core_hybrid_sidecar_diag_frozen_fixed24_tr_close_exec_balanced_20260330_163624_48065e04` | `20251231` / `0.5 + 24m fixed` | `2023-11-30 -> 2025-10-31` | `+6.14%` | `30.2% / 1.07` |
| `R3` | `hk_sel_m_pit_core_hybrid_sidecar_diag_latest_ratio_tr_close_exec_balanced_20260330_163712_c6b44b72` | `20260327` / `0.6 + 0.2 ratio` | `2024-01-31 -> 2026-01-30` | `-6.94%` | `35.1% / 1.05` |
| `R4` | `hk_sel_m_pit_core_hybrid_sidecar_diag_tr_close_exec_balanced_20260330_155212_d2b52da6` | `20260327` / `0.5 + 24m fixed` | `2024-02-29 -> 2026-01-30` | `-7.30%` | `26.0% / 0.84` |

### 这张表最该怎么读

#### 1. split 不是主因

`R1` 和 `R2` 都仍然是正 `IC`，`R3` 和 `R4` 都已经转成负 `IC`。  
这说明：

* 在 frozen cutoff 下，old ratio split 和 fixed `24m` split 都站得住
* 在 latest cutoff 下，old ratio split 和 fixed `24m` split 都站不住
* 所以不能把这次 monthly 转弱主要怪给 split 设计

#### 2. 主要压力更像最近新增月份 / recent regime

这组里最有信息量的比较是：

* `R2` vs `R4`

因为它们共用：

* current assets
* fixed `24m` final OOS
* 同一套模型 / 特征 / execution

唯一显著变化基本就是：

* cutoff 从 `2025-12-31` 推到 `2026-03-27`

而这一步足以让 `final OOS IC` 从 `+6.14%` 翻到 `-7.30%`。  
所以当前最该解释的，不是 split，而是：

* 最近新增月份到底改写了什么
* 这是不是一段新的 regime / 行业主导结构 / 风格切换

#### 3. asset refresh 不是把旧结论打坏的主因

`R0` vs `R1` 的方向不是“旧 frozen reference 很强，但 current-assets recut 已经坏掉”，反而是：

* `R0 = +4.88%`
* `R1 = +6.74%`

这说明：

* universe / PIT / 本地 daily 资产刷新当然会改数值
* 但它不是把 `M-PIT` 从正 `IC` 翻成负 `IC` 的主导解释

#### 4. 最新窗口的问题更像“排序纯度下降”，不只是“组合赚不赚钱”

即便 `R3 / R4` 的 long-only 回测年化和 Sharpe 还不算难看，`final OOS IC` 还是已经翻负。  
这更像：

* 实现层还有收益
* 但横截面排序逻辑本身在 latest 窗口里已经变脏

这也是为什么这轮不该继续靠加 `pb / pe / size` overlay 去救表观收益。

## 每一组比较到底在回答什么

### `R0` vs `R1`

回答：

* 如果时间 cutoff 和 split 都尽量贴近旧 frozen，但换成当前资产再跑，旧结论还剩多少？

这一步主要吸收：

* universe `by_date_file` 刷新
* PIT flat 文件刷新
* 本地 daily / ex_factors / execution 资产刷新
* 代码路径变化

如果这里就已经显著转弱，那就别急着怪最近三个月新样本。

### `R1` vs `R2`

回答：

* 在同一个 `2025-12-31` cutoff 下，把 old ratio split 换成新 `24m final OOS`，结论怎么变？

这一步是纯 split 设计问题。  
它告诉我们：

* 旧结论有没有显著依赖 `0.6 + 0.2` 这种比例式切法

### `R2` vs `R4`

回答：

* 在同样的 `0.5 + 24m final OOS` 口径下，只把 cutoff 从 `2025-12-31` 推到 `2026-03-27`，基线发生了什么？

这一步最接近“新增最近几个月样本”的问题。

### `R3` vs `R4`

回答：

* 在最新 cutoff 下，old ratio split 和 new fixed-24 split 的差别有多大？

这一步的价值是防止我们把“recent regime 变弱”误判成“只是切法变了”。

## 推荐运行顺序

先跑：

1. `R1` frozen ratio recut
2. `R2` frozen fixed-24 recut
3. `R3` latest ratio recut

然后把它们分别和已有的 `R0 / R4` 对照。

这样安排的原因：

* `R4` 已经有了，不用重跑
* `R1 -> R2` 先把 `2025-12-31` 这一侧拆清，信息比最高
* `R3` 只在你需要判断“最新窗口是不是对 split 特别敏感”时再补

## 本次新增配置

这次已经补了 `3` 个本地 `diag` 配置：

* `hk_selected__m_pit_core_hybrid_sidecar_diag_frozen_ratio_tr_close_exec_balanced.yml`
* `hk_selected__m_pit_core_hybrid_sidecar_diag_frozen_fixed24_tr_close_exec_balanced.yml`
* `hk_selected__m_pit_core_hybrid_sidecar_diag_latest_ratio_tr_close_exec_balanced.yml`

共同原则：

* 模型、特征、execution、bucket diagnostics 不变
* 只改 `data.end_date`、`eval.test_size`、`eval.final_oos.size`
* 统一保留 `diag` 版的 size bucket diagnostics，避免只剩收益图

## 每次 run 至少要记哪些字段

建议每条 run 都至少摘这几类指标：

* `data.symbols`
* `data.rows_model`
* `split.train_dates / test_dates / purge_steps / embargo_steps`
* `final_oos.start / end / dates`
* `final_oos.ic.mean`
* `final_oos.backtest.stats.ann_return / sharpe / max_drawdown`
* `final_oos.backtest.stats.avg_turnover / avg_cost_drag`
* `final_oos.bucket_ic`
* 最终持仓的 `size_bucket_q4 / size_rank_pct`

## 如果只压一句当前判断

首轮 `R0-R4` 已经足够把 monthly 下一步优先级收口成：

1. 不再把 split 当第一嫌疑人
2. 不继续扩 `pb / pe / size` overlay 组合
3. 直接去拆 latest 这几个月的逐月 `IC`、行业结构、size 暴露和持仓漂移

## 我会怎么读结果

如果结果呈现下面这些模式，对应解释会很直接：

### 模式 A

* `R0` 强
* `R1` 已明显转弱

解释：

* 旧 frozen 结论已经对 asset refresh 很敏感

### 模式 B

* `R1` 还行
* `R2` 明显转弱

解释：

* split 口径是重要因素

### 模式 C

* `R2` 还行
* `R4` 明显转弱

解释：

* 最近新增的几个月样本或最新 regime 才是主要压力源

### 模式 D

* `R3` 和 `R4` 差异很大

解释：

* 最新窗口对 split 很敏感，不能轻易把单一切法当最终口径

## 本次首轮实跑实际落点

这轮首轮结果最接近：

* 强模式 C
* 明显不是模式 B
* 也不支持“模式 A 才是主因”

更直白一点说：

* split 不是主要矛盾
* recent months / latest regime 更像主要矛盾
* asset refresh 会改数值，但不是把方向翻掉的核心原因

## 这轮之后再做什么

现在 `R0-R4` 已经跑过一轮，下面这些动作才值得继续排优先级：

* latest 窗口的逐月 `IC` / 持仓 / 行业 / size 漂移拆解
* `pe_only` comparator 的 construction 优化
* `30m final OOS` stress sidecar
* `2017+` modern-only sidecar

否则你很容易把“基线为什么变弱”这个问题，错扔给 overlay、换手或 size 解释。

## 一句话收口

`M-PIT` 下一步最值钱的工作，不是继续加因子，而是先用 `R0-R4` 这套最小矩阵，把“old frozen 为什么看起来更强、latest 为什么变弱”拆清楚。
