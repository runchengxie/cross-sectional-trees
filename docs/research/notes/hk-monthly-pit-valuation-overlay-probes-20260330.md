# HK Monthly PIT Valuation Overlay Probes (2026-03-30)

> 状态提示：本页保留为 historical provenance，用于追溯 monthly 线里 `valuation overlay` 为什么被降级。当前默认研究入口请先读 [`hk-monthly-current-state-20260330.md`](./hk-monthly-current-state-20260330.md)。

页面性质：`research-note`  
状态：`historical provenance`，这页只保留这批 `M-PIT + provider valuation overlay` probe 的证据链，不再作为 monthly 线默认阅读入口  
最后核对时间：`2026-03-30`  
权威来源：6 条 run 的 `summary.json` / `config.used.yml` / `positions_by_rebalance_oos.csv`，以及对应的 `provider_valuation_audit.csv`  
冲突优先级：如果和具体 run 产物冲突，以 run 目录下的 `summary.json` / `config.used.yml` 为准；如果和更晚样本冲突，以更晚样本为准

> 注：这批 monthly 派生配置保存在作者本地 `configs/local/`，默认不纳入版本控制。这里记录的是实验结论，不把本地文件名当成唯一权威入口。

## 1. 这页回答什么

这页只回答一个问题：

* 在修复 `provider_overlay` 链路、修复 monthly split、并统一到 `asof_20260327 + test_size=0.5 + final_oos=24` 之后，`M-PIT` 加一层很克制的 provider 估值，是否真的带来了干净增量？

这页不回答：

* provider 那条线为什么强
* monthly 时间设计本身该怎么切
* quarterly 线是否值得继续

这些问题分别见：

* [`hk-monthly-provider-vs-pit-20260330.md`](./hk-monthly-provider-vs-pit-20260330.md)
* [`hk-monthly-provider-factor-probes-20260330.md`](./hk-monthly-provider-factor-probes-20260330.md)
* [`hk-monthly-time-window-design-20260330.md`](./hk-monthly-time-window-design-20260330.md)

## 2. 这批 probe 的共同口径

这 6 条 run 统一采用：

* `data.end_date=20260327`
* `eval.test_size=0.5`
* `eval.final_oos.size=24`
* monthly split 修复后的 `50 / 52 / 24` main train / main test / final OOS
* `label.horizon_mode=next_rebalance + shift_days=1`

因此这批 run 的 final OOS 区间都是：

* `2024-02-29 -> 2026-01-30`

本页只比较下面 6 条：

* `diag`
  * `artifacts/runs/hk_sel_m_pit_core_hybrid_sidecar_diag_tr_close_exec_balanced_20260330_155212_d2b52da6/`
* `pb_only`
  * `artifacts/runs/hk_sel_m_pit_core_hybrid_overlay_pb_only_tr_close_exec_balanced_20260330_155404_b56250f6/`
* `pe_only`
  * `artifacts/runs/hk_sel_m_pit_core_hybrid_overlay_pe_only_tr_close_exec_balanced_20260330_160111_6285b775/`
* `pb_pe`
  * `artifacts/runs/hk_sel_m_pit_core_hybrid_overlay_pb_pe_tr_close_exec_balanced_20260330_160225_49b00d0a/`
* `size_placebo`
  * `artifacts/runs/hk_sel_m_pit_core_hybrid_overlay_size_placebo_tr_close_exec_balanced_20260330_160400_5354ccd8/`
* `pb_pe_size`
  * `artifacts/runs/hk_sel_m_pit_core_hybrid_overlay_pb_pe_size_tr_close_exec_balanced_20260330_160507_2db1b34c/`

## 3. 先看最重要的结论

* 这批结果不支持“轻量 valuation overlay 已经给 `M-PIT` 带来干净增量”。
* `pb_only` 明显最差，当前可以先降级。
* `pe_only` 的组合实现最好，但 `final OOS IC` 仍为负，所以更像实现 comparator，不像研究升级。
* `pb_pe` 和 `pb_pe_size` 的主要优点只是换手略低，不是排序证据更强。
* `size_placebo` 没有把结果救回来，所以这轮证据也不支持“只要把 size 混回来就会更强”。

一句话概括：

* 这轮 `overlay` 更像“组合层微调”，不像“研究主线获得新 alpha”。

## 4. 结果快照

| run | 新增特征 | Final OOS IC | OOS ann | OOS sharpe | OOS avg turnover |
| --- | --- | ---: | ---: | ---: | ---: |
| `diag` | 无 | `-7.30%` | `25.98%` | `0.84` | `44.39%` |
| `pb_only` | `pb` | `-9.26%` | `18.60%` | `0.67` | `44.25%` |
| `pe_only` | `pe_ttm` | `-8.10%` | `28.90%` | `0.94` | `44.43%` |
| `pb_pe` | `pb + pe_ttm` | `-8.49%` | `21.30%` | `0.73` | `40.90%` |
| `size_placebo` | `log_mcap` | `-7.03%` | `16.63%` | `0.64` | `43.41%` |
| `pb_pe_size` | `pb + pe_ttm + log_mcap` | `-8.15%` | `22.36%` | `0.77` | `40.30%` |

如何读这张表：

* 如果看研究证据，关键列是 `Final OOS IC`。这列 6 条都没有过线。
* 如果看组合实现，`pe_only` 是这批里最好的一条，但它并没有把研究证据洗正。
* 如果看交易成本，`pb_pe` / `pb_pe_size` 确实更低换手，但收益和排序都没有同步变强。

## 5. 这次不是数据链路坏了

这点很重要。

这批 overlay run 对应的 valuation audit 显示：

* `163/163` symbols cache hits
* `Coverage(any valuation col) = 100%`
* `valuation_age_days max = 0`

也就是说：

* `provider_overlay` 已经真的接上了
* 这轮结果应视为真实研究结果
* 不是前一版那种“rqdatac 没初始化，所以其实没加上 overlay”的假阴性

所以这里更合理的解释不是“链路有问题”，而是：

* 在这版更晚样本和更明确的 `24m final OOS` 下，`M-PIT` 本身就比旧 frozen snapshot 更弱
* 轻量 valuation overlay 并没有把这个问题解决掉

## 6. 该怎么理解这批 probe

### 6.1 `pb_only`

结论：

* 当前可直接降级

原因：

* `Final OOS IC` 最差
* 组合实现也没有补偿

### 6.2 `pe_only`

结论：

* 可以保留成实现 comparator
* 但不应该升格成研究主线升级

原因：

* 它给了这批里最高的 OOS 年化和 Sharpe
* 但 `Final OOS IC` 仍然为负

### 6.3 `pb_pe`

结论：

* 如果你要研究“估值层能否顺便降换手”，它还值得保留
* 如果你要研究“有没有干净增量 alpha”，它没有回答出来

### 6.4 `size_placebo`

结论：

* 当前不支持“加回 size 就能救曲线”

### 6.5 `pb_pe_size`

结论：

* 它比 `pb_pe` 略顺一点，但仍没有超过 `diag`
* 所以也不支持“估值 + size 混回去就会形成更强主线”

## 7. 对当前 monthly 主线意味着什么

这批 probe 跑完后，monthly 主线判断应该收得更保守：

* `M-PIT` 仍然是研究主线，但需要先解释为什么更新窗口后基线自己转弱了
* `M-provider rebalance-only` 仍然是实现 comparator / 候选
* `M-PIT + valuation overlay` 当前最多只保留 `pe_only` 这个实现 comparator，不升格成默认下一主线

所以这页最重要的阶段判断是：

* overlay 方向没有被“否定到不值得再提”
* 但它已经不该继续占据 monthly 研究的第一优先级

## 8. 接下来最有价值的研究方向

如果只选一个方向，我会押：

* 做 `M-PIT` 基线的 `frozen vs latest` 稳定性拆解，而不是继续叠更多 overlay 组合
* 具体实验矩阵和配置命名，见 [`hk-monthly-pit-frozen-vs-latest-design-20260330.md`](./hk-monthly-pit-frozen-vs-latest-design-20260330.md)

更具体地说，优先回答：

* 为什么旧的 frozen snapshot 还像“有正 IC 的研究主线”，但这版 `asof_20260327 + 24m final OOS` 已经转弱？
* 差异主要来自：
  * 新增最近几个月样本
  * split 口径变化
  * universe by-date 更新
  * 还是 PIT / execution 资产刷新

这件事的信息比，比继续扩 `pb / pe / size` 组合更高。  
因为在基线本身解释不清的时候，继续叠特征只会把故事越讲越脏。

## 9. 更实际的下一步顺序

1. 固定 `M-PIT diag`，做 `2025-12-31 frozen` vs `asof_20260327 latest` 的稳定性拆解。
2. 如果只关心实现，保留 `pe_only` 做 comparator，再去看 `buffer_entry / buffer_exit / top_k`。
3. 等上面两件事清楚了，再补一个 `30m final OOS` stress sidecar。

## 10. 一句话结论

截至 `2026-03-30`，这批 `M-PIT + provider valuation overlay` probe 的最合理收口是：

* 没有出现可以升级成 monthly 研究主线的新赢家
* `pe_only` 可以保留为实现 comparator
* 下一阶段的第一优先，不是更多 overlay，而是解释 `M-PIT` 基线在新窗口上为什么转弱
