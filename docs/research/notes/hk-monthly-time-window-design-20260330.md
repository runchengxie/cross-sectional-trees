# HK Monthly Time Window Design (2026-03-30)

页面性质：`research-note`  
状态：`active deep-dive`，这页解释 monthly 时间边界和切分设计，不替代 [`hk-monthly-current-state-20260330.md`](./hk-monthly-current-state-20260330.md)  
最后核对时间：`2026-03-30`  
权威来源：本地资产 manifest、`hk_selected_pit_research_by_date.csv`、当前月频 PIT anchor run、[`runtime.py`](../../../src/csml/pipeline/runtime.py) 的切分逻辑  
冲突优先级：如果和具体 run 的 `config.used.yml` / `summary.json` 冲突，以 run 产物为准；如果和未来新 snapshot 的资产边界冲突，以新 asset manifest 为准

## 结论先写在前面

* 当前本地 monthly 研究资产里，真正控制月频研究边界的是 `hk_selected_pit_research_by_date.csv`，不是更早的 raw daily 或 PIT 资产。
* 当前这条港股通 PIT monthly 研究池可用的研究月点是 `2015-01-30 -> 2026-03-27`，一共 `135` 个月度 rebalance dates。
* 因为当前配置同时使用了 `label.horizon_mode=next_rebalance` 和 `shift_days=1`，最新一个月点 `2026-03-27` 还不能形成已实现标签；`2026-02-27` 也仍然需要 `2026-03-27` 之后再有一个交易日的价格才能完成标签。因此当前这组 config 的最新**完整可标注**月点仍是 `2026-01-30`。对应完整 labeled monthly 点是 `2015-01-30 -> 2026-01-30`，共 `133` 个。
* 对当前这组 `M-PIT hybrid sidecar / overlay` 配置，真实可建模窗口应以具体 run 的 `summary.json` 为准；修复 split 逻辑后的 anchor diag run `hk_sel_m_pit_core_hybrid_sidecar_diag_tr_close_exec_balanced_20260330_155212_d2b52da6` 形成了 `126` 个 model dates，并落在 `50 / 52 / 24` 的 main train / main test / final OOS 切分。
* 默认切分现在建议直接写成 `data.end_date=20260327`、`eval.test_size=0.5`、`eval.final_oos.size=24`；在 split 修复后，这对应的 monthly mainline 切分已经回到 `50 / 52 / 24`，不再是之前那种 `purge/embargo` 被误放大成 `22/20` 个月点的坏状态。
* `2016-12-05` 之后确实更接近今天的沪深港互联互通生态，但如果直接把默认研究窗口砍到现代阶段，月频 train dates 会明显变薄，更适合当 sidecar robustness probe，不适合替换默认主线。

## 先分清三层时间边界

| 层级 | 当前本地边界 | 含义 | 备注 |
| --- | --- | --- | --- |
| raw daily 资产 | `2000-01-04 -> 2026-03-27` | 本地日线缓存的物理边界 | 来自 `hk_all_2000_20260327_daily_final_latest/manifest.yml` |
| PIT fundamentals 文件 | `2011-04-21 -> 2026-03-10` | `pipeline_fundamentals.parquet` 里的 `trade_date` 边界 | 这是财务披露可见日期，不是月度 rebalance 日期 |
| selected PIT monthly research universe | `2015-01-30 -> 2026-03-27` | 当前 monthly 研究池实际允许进入样本的 rebalance dates | 来自 `hk_selected_pit_research_by_date.csv`，共 `135` 个月点 |

这三层不能混成一句“数据到什么时候”。

对 monthly 研究最重要的是第三层，也就是 `universe.by_date_file`。  
raw daily 和 PIT 资产即使更早，如果 `by_date_file` 没有那些日期，策略也不会把它们当成同一研究窗口里的月频样本。

## 什么叫“完整月度数据”

当前 monthly 线使用的是：

* `label.horizon_mode=next_rebalance`
* `rebalance_frequency=M`
* `sample_on_rebalance_dates=true`

这意味着某个 rebalance date 要想形成已实现标签，必须知道**下一个** rebalance date。  
而当前配置里还有 `shift_days=1`，所以实际还需要“下一个 rebalance date 之后的下一个交易日”的价格。

因此：

* `2026-03-27` 是当前研究池里的最新 snapshot date
* 但它还不是当前可以评估的最后一个 labeled monthly point
* 在 `shift_days=1` 下，`2026-02-27` 也还不够，因为它需要 `2026-03-27` 之后再有一个交易日的价格
* 所以当前这组 config 的最新完整 labeled monthly point 是 `2026-01-30`

按当前 `by_date_file` 计算：

* 研究月点：`2015-01-30 -> 2026-03-27`，`135` 个
* 若只考虑 `next_rebalance`：完整 labeled 月点可到 `2026-02-27`，`134` 个
* 对当前实际 config（`next_rebalance + shift_days=1`）：完整 labeled 月点只到 `2026-01-30`，`133` 个

所以今天如果做新 snapshot，正确写法应该是：

* `raw snapshot as of 2026-03-27`
* `latest fully labeled monthly point under current config = 2026-01-30`

不应该写成“截至 `2026-03-31` 的 monthly OOS”。

## 为什么模型可用月点会比 134 更少

当前这组月频 PIT hybrid 配置不是只吃一个低频因子，它还要经过：

* `ret_120`
* `rv_60`
* volume 均线
* PIT 披露衍生列
* 横截面缺失过滤

所以 earliest labeled date 不等于 earliest model date。

结合当前 anchor diag run `hk_sel_m_pit_core_hybrid_sidecar_diag_tr_close_exec_balanced_20260330_155212_d2b52da6` 的实际 split 结果，当前这组配置至少可以确认：

* latest model date 到了 `2026-01-30`
* 当前 run 一共形成了 `126` 个 model dates
* 其中 `24` 个进入 final OOS，`52` 个进入 main test，`50` 个留在 main train

这说明仅凭原始资产边界去推测 effective model window 不够可靠。  
这里更稳妥的做法是：把实际 run 产物当主依据，而不是先验估算。

## 要不要直接从 2016 以后开始

如果问题是“哪一段更像今天这套互联互通生态”，答案偏向：

* 制度起点：`2014-11-17`，沪港通下的港股通
* 更接近今天完整互联互通阶段：`2016-12-05` 之后，深港通开通

但这不等于默认 monthly 主线应该直接从 `2016-12` 或 `2017` 截断。

原因有两个：

* 当前 `hk_selected_pit_research_by_date.csv` 自己就只从 `2015-01-30` 开始，往前也只能多补很少几个月点，边际价值有限。
* 如果把默认可建模窗口近似收缩到 `2017-06-30 -> 2026-02-27`，只剩大约 `105` 个 model dates；再保留 `24` 个月 final OOS，主 train/test 切完后大约只有 `38` 个 train dates，默认主线会偏薄。

所以更合理的处理是：

* 默认主线保留 `2015` 起的完整月频样本池
* 把“`2016-12-05` / `2017` 以后更可比”写成解释和 sidecar probe
* 不把 modern-only 窗口直接升格成默认主线

## 当前 frozen 口径和建议新口径

### 旧 frozen snapshot

截至 `2025-12-31` 的 frozen monthly anchor，实际大致是：

* effective model dates：`126`
* `eval.test_size=0.6`
* `eval.final_oos.size=0.2`
* 最终得到：`38` 个 train dates、`61` 个 test dates、`25` 个 final OOS dates

这个切法的问题不是“错”，而是：

* main test 段偏长
* train 段偏薄
* final OOS 用比例切，随着 snapshot 更新会平移，不够直观

### 建议的新默认口径

对当前这批 monthly overlay probe，更平衡的默认切法是：

* `data.start_date: 20150101`
* `data.end_date: 20260327`
* `eval.test_size: 0.5`
* `eval.final_oos.size: 24`

按当前修复后的 split 逻辑和最新 `asof_20260327` 研究池，默认口径的实际切分已经是：

| 口径 | train dates | test dates | final OOS dates | final OOS 区间 |
| --- | ---: | ---: | ---: | --- |
| 建议默认 | `50` | `52` | `24` | `2024-02-29 -> 2026-01-30` |
| 更严格 stress sidecar | `46` | `48` | `30` | `2023-08-31 -> 2026-01-30` |

我更推荐把 `24m final OOS` 当默认，把 `30m final OOS` 当 stress sidecar。  
原因：

* `24` 个月点已经覆盖了最近完整两年，多于此前 frozen run 的 `25` 个比例式 OOS 所代表的“最近两年左右”直觉，但定义更明确。
* `0.5` 主 split 比当前 `0.6` 更平衡，不会把 in-sample 的 train 压得过薄。
* `30m` 虽然也可跑，但它更适合作为“更严格 recent-regime 压力测试”，不是第一默认口径。

## Walk-Forward 怎么看

这批 monthly config 里的 walk-forward 目前是：

* `n_windows=4`
* `test_size=0.2`
* `step_size=0.1`
* `anchor_end=true`

这个部分我建议先不改。

理由：

* 它的职责是看稳定性，不是替代 main test 或 final OOS。
* 在当前 `24m final OOS` 新口径下，in-sample 还有 `105` 个月点，`walk_forward.test_size=0.2` 仍然会形成大约 `21` 个测试月点的窗口，量级上是合理的。
* 先把主 split 和 final OOS 设计固定，再比较 overlay 结果，更容易解释。

## 对这批 local configs 的实际建议

对下面这批 monthly probe，本次统一采用同一套时间设计：

* `hk_selected__m_pit_core_hybrid_sidecar_diag_tr_close_exec_balanced.yml`
* `hk_selected__m_pit_core_hybrid_overlay_pb_only_tr_close_exec_balanced.yml`
* `hk_selected__m_pit_core_hybrid_overlay_pe_only_tr_close_exec_balanced.yml`
* `hk_selected__m_pit_core_hybrid_overlay_pb_pe_tr_close_exec_balanced.yml`
* `hk_selected__m_pit_core_hybrid_overlay_size_placebo_tr_close_exec_balanced.yml`
* `hk_selected__m_pit_core_hybrid_overlay_pb_pe_size_tr_close_exec_balanced.yml`

统一更新为：

* `data.end_date=20260327`
* `eval.test_size=0.5`
* `eval.final_oos.size=24`
* 其余模型、特征、execution、walk-forward 口径不动

这样做的好处是：

* 先把这批 overlay 实验的时间边界统一下来
* 保留与旧 frozen snapshot 的可解释对照
* 不把“是否从 2017 才开始更合理”这个问题，和“overlay 有没有增量”这个问题混在同一轮实验里

## 什么时候再看 modern-only sidecar

如果这批 overlay 跑完后，`pb / pe_ttm` 的方向站得住，下一轮更值得加的是一个单独 sidecar：

* 默认主线：`2015` 起样本池 + `24m final OOS`
* 现代阶段 sidecar：`2016-12-05` 或 `2017` 以后 + 同样的 `24m final OOS`

这样可以回答一个更干净的问题：

* overlay 的增量，是跨整个港股通阶段都成立
* 还是主要成立在更接近今天制度结构的 modern regime

这一步值得做，但不该先于“先把默认时间设计定住并把 overlay bug 修好”。
