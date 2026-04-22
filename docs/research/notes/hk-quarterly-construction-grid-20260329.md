# HK Quarterly Construction Grid Follow-up（2026-03-29）

> 状态提示：本页属于 active deep-dive，用于记录 quarterly 线固定信号后的组合构造 follow-up。当前默认研究入口请先读 [`hk-quarterly-current-state-20260329.md`](./hk-quarterly-current-state-20260329.md)。

本页解决什么：记录 `raw-scale dedup + groupcap3` 这条结构 challenger 的前两轮 `cstree grid` 结果，并明确固定信号后下一步最值得扫的组合构造维度。
本页不解决什么：不替代主线/副线的总收口，也不重新讨论模型、`tr_close` 或纯基本面路线。  
适合谁：已经接受“当前更该看组合构造，不该继续大扫模型参数”的读者。  
读完你会得到什么：第一轮 buffer sweep、第二轮 `top_k` sweep 的实际结果，它们各自能支持到什么程度，以及为什么这些 grid 结果现在只能当 shortlist，而不能直接升级成新默认。  
相关页面：`docs/research/notes/hk-quarterly-current-state-20260329.md`、`docs/research/notes/hk-quarterly-holdings-analysis-20260329.md`、`docs/research/notes/hk-quarterly-next-step-configs-20260329.md`

页面性质：`research-note`  
最后核对时间：`2026-03-29`  
权威来源：`artifacts/runs/grid_summary.csv`、`artifacts/runs/hk_selected__quarterly_pit_core_hybrid_provider_overlay_rawscale_dedup_groupcap3_construction_grid_grid_base_20260329_205451_26a07fc9/`、以及当前 tracked sweep config  
冲突优先级：如果与具体 grid 产物冲突，以 `grid_summary.csv` 和对应 run 目录为准；如果与更新后的现行总收口冲突，以更晚的 `current-state` 页面为准

## 1. 这页是在回答什么

前面的 holdings note 已经把方向收得比较清楚：

* `raw-scale dedup + groupcap3` 是当前最像样的 structural challenger
* 它更像组合修形，不像重写信号
* 所以接下来更合理的不是继续重训模型，而是固定这条信号，直接扫 construction 参数

这一页就是当前 construction sweep 的结果记录。

## 2. 这轮 sweep 的设定

固定信号：

* [`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_exec_balanced_local_rawscale_dedup_groupcap3.yml`](../../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_exec_balanced_local_rawscale_dedup_groupcap3.yml)

固定 construction sweep 配置：

* [`configs/experiments/sweeps/hk_selected__quarterly_pit_core_hybrid_provider_overlay_rawscale_dedup_groupcap3_construction_grid.yml`](../../../configs/experiments/sweeps/hk_selected__quarterly_pit_core_hybrid_provider_overlay_rawscale_dedup_groupcap3_construction_grid.yml)

本轮最小网格：

* `top_k = 20`
* `cost_bps = 25`
* `buffer_exit = 1, 2`
* `buffer_entry = 1, 2`

这里的重点不是绝对收益有多强，而是：

* 在不改模型评分的前提下，组合层参数能不能进一步压一点换手和成本
* 哪个维度更值得继续扫

## 3. 一个前提：`cstree grid` 现在终于能正确带 execution 列了

这轮 sweep 之前，`grid` 实际上会失败，因为 `eval_scored.parquet` 没把 execution backtest 需要的 `open` 和 `adv20_amount` 一起带过去。  
修完之后，`grid_summary.csv` 里的 4 个组合都已经是 `status = ok`，所以这轮结果终于是可解释的 construction 结果，而不是工具链误报。

## 4. 第一轮结果

| 组合 | `backtest_total_return` | `backtest_sharpe` | `backtest_avg_turnover` | `backtest_avg_cost_drag` |
| --- | --- | --- | --- | --- |
| `bx1_be1` | `-0.05%` | `0.108` | `60.02%` | `0.31%` |
| `bx1_be2` | `-0.05%` | `0.108` | `60.02%` | `0.31%` |
| `bx2_be1` | `+0.01%` | `0.109` | `59.19%` | `0.30%` |
| `bx2_be2` | `+0.01%` | `0.109` | `59.19%` | `0.30%` |

这 4 行共用同一套评分，所以：

* `eval_ic_mean` 都是 `-0.0076`
* `eval_long_short` 都是 `-0.0083`
* 可变的只有 construction 层回测结果

另外，这轮 grid 的 `backtest_periods = 6`。  
所以它已经比“只看 1-2 个 period”的玩具 sweep 好一些，但仍然只适合做相对比较，不适合把绝对收益当成策略证据。

## 5. 该怎么读这张表

### 5.1 `buffer_entry` 当前不绑定

`be = 1` 和 `be = 2` 两组结果完全相同。  
这说明在这条固定信号下，entry 侧的 buffer 还没有真正开始影响组合。

当前更值得扫的不是继续在 `buffer_entry` 上做细网格，而是先把它固定住。

### 5.2 `buffer_exit = 2` 比 `1` 略好一点

和 `bx = 1` 相比，`bx = 2`：

* `backtest_total_return` 从 `-0.05%` 改到 `+0.01%`
* `backtest_sharpe` 从 `0.108` 到 `0.109`
* `backtest_avg_turnover` 从 `60.02%` 降到 `59.19%`
* `backtest_avg_cost_drag` 从 `0.31%` 降到 `0.30%`

改善幅度不大，但方向是一致的。  
所以如果下一轮继续扫 construction，更合理的做法是先把 `buffer_exit = 2` 固定住。

### 5.3 这轮结果支持的是“construction 优先”，不是“buffer 已经找到最优解”

这张表能支持的结论很克制：

* 现在继续做 construction sweep 是对的
* `buffer_exit` 比 `buffer_entry` 更值得继续扫
* 下一轮没必要继续做 `be = 1/2` 这种重复试验

但它还不能支持：

* `bx = 2` 已经是全局最优
* 这条 structural challenger 已经足够强，可以替掉主线

## 6. 第二轮结果：固定 `bx = 2`、`be = 1` 后比较 `top_k`

第二轮 sweep 使用：

* [`configs/experiments/sweeps/hk_selected__quarterly_pit_core_hybrid_provider_overlay_rawscale_dedup_groupcap3_topk_grid.yml`](../../../configs/experiments/sweeps/hk_selected__quarterly_pit_core_hybrid_provider_overlay_rawscale_dedup_groupcap3_topk_grid.yml)

最小网格：

* `top_k = 15 / 20 / 25`
* `cost_bps = 25`
* `buffer_exit = 2`
* `buffer_entry = 1`

结果如下：

| 组合 | `backtest_total_return` | `backtest_sharpe` | `backtest_avg_turnover` | `backtest_avg_cost_drag` |
| --- | --- | --- | --- | --- |
| `top_k = 15` | `-3.12%` | `0.054` | `65.42%` | `0.34%` |
| `top_k = 20` | `+0.01%` | `0.109` | `59.19%` | `0.30%` |
| `top_k = 25` | `+3.10%` | `0.156` | `55.90%` | `0.28%` |

这轮和第一轮一样，共用同一套评分，所以：

* `eval_ic_mean` 仍然都是 `-0.0076`
* `eval_long_short` 仍然都是 `-0.0083`
* 改善完全来自 construction 层，不来自信号本身变强

### 6.1 该怎么读这轮 `top_k` sweep

先说最直接的结论：

* 这条 fixed-signal structural challenger 下，`top_k = 25` 明显好于 `20`，`20` 又明显好于 `15`
* `top_k` 变宽后，换手和成本拖累一起下降
* 这更像“增加分散化、降低集中度”的收益，不像信号质量突然改善

也就是说，这轮结果支持的是：

* `raw-scale dedup + groupcap3` 这条结构 challenger 值得先把 `top_k = 25` 放进 shortlist
* 但它仍然只是同一份评分上的 construction shortlist，不是已经确认的新默认

但它还不能支持：

* `top_k = 25` 已经足够把这条线升级成主线
* 这条 structural challenger 的核心问题已经被 construction 解决

因为这轮 grid 的 `backtest_periods` 仍然只有 `6`，而且评估侧的 `IC / long_short` 仍然没有翻正。

## 7. 关键补充：独立 full run 没有确认 `bx2_be1` 和 `top_k25`

`cstree grid` 的作用是固定同一份评分，只比较 construction。
所以它适合做 shortlist，不适合直接决定“当前默认候选已经换成谁”。

`2026-03-29` 当晚这轮独立 full run 复验，把这件事讲清楚了：

| 方案 | 完整测试段 `total_return` | 完整测试段 `Sharpe` | Final OOS `total_return` | Final OOS `Sharpe` |
| --- | --- | --- | --- | --- |
| `raw-scale dedup + groupcap3` | `-13.38%` | `0.005` | `84.72%` | `1.894` |
| `raw-scale dedup + groupcap3 + bx2_be1` | `-14.58%` | `-0.001` | `80.64%` | `1.834` |
| `raw-scale dedup + groupcap3 + bx2_be1 + top_k25` | `-15.47%` | `-0.016` | `66.29%` | `1.589` |

这张表的含义很直接：

* 第一轮和第二轮 grid 给出的 `bx2_be1`、`top_k25` 更像是 construction shortlist
* 但一旦拉回完整 `cstree run` 口径，它们都没有把 `raw-scale dedup + groupcap3` 本身做强
* 所以现在不能把 `bx = 2`、`be = 1`、`top_k = 25` 升成新的 construction 默认

更准确地说：

* `buffer_exit = 2` 有过“轻微正向 hint”，但没有通过端到端复验
* `top_k = 25` 在 grid 上更像样，但也没有通过独立 full run 复验
* 当前真正站得住的，仍然是 `raw-scale dedup + groupcap3`

## 8. 这页现在真正支持的结论

到这一步，这页能支持的结论应当收得更克制：

1. `construction` 仍然是对的研究方向，因为 grid 明确说明同一份信号下，组合层参数会改结果。
2. 但 grid 只能提供 shortlist，不足以直接升级默认配置。
3. 当前最该保留的结构 challenger 仍然是 `raw-scale dedup + groupcap3`。
4. `bx2_be1` 和 `top_k25` 暂时都应降级成“做过、但未被 full run 确认”的 follow-up。

## 9. 下一步该怎么用这页
如果今天还要继续用这页做决策，更合理的读法是：

1. 接受“grid 负责 shortlist，full run 才负责晋级”这条边界。
2. 当前冻结的结构 challenger 仍然是 `raw-scale dedup + groupcap3`。
3. `bx2_be1` 和 `top_k25` 先保留为历史 follow-up，不继续当现行候选往前推进。
4. 如果后面还要重新开 construction 线，优先从 weighting 或更强 group cap 这种真正新维度开始，而不是继续围着 `bx2_be1/top_k25` 打转。

为避免每次都手敲同一组 construction 参数，这里保留相关 tracked 入口：

* [`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_exec_balanced_local_rawscale_dedup_groupcap3_bx2_be1.yml`](../../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_exec_balanced_local_rawscale_dedup_groupcap3_bx2_be1.yml)
  `buffer` follow-up 的独立 full run 入口；已跑过，但暂未确认优于 `raw-scale dedup + groupcap3`
* [`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_exec_balanced_local_rawscale_dedup_groupcap3_bx2_be1_topk15.yml`](../../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_exec_balanced_local_rawscale_dedup_groupcap3_bx2_be1_topk15.yml)
  `top_k = 15` 的集中版
* [`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_exec_balanced_local_rawscale_dedup_groupcap3_bx2_be1_topk25.yml`](../../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_exec_balanced_local_rawscale_dedup_groupcap3_bx2_be1_topk25.yml)
  `top_k = 25` 的宽版；grid 上较好，但独立 full run 未确认
* [`configs/experiments/sweeps/hk_selected__quarterly_pit_core_hybrid_provider_overlay_rawscale_dedup_groupcap3_topk_grid.yml`](../../../configs/experiments/sweeps/hk_selected__quarterly_pit_core_hybrid_provider_overlay_rawscale_dedup_groupcap3_topk_grid.yml)
  固定 `bx = 2`、`be = 1` 后只扫 `top_k`

对应最小命令：

```bash
uv run cstree grid \
  --config configs/experiments/sweeps/hk_selected__quarterly_pit_core_hybrid_provider_overlay_rawscale_dedup_groupcap3_topk_grid.yml \
  --top-k 15,20,25 \
  --cost-bps 25
```

如果后面还想继续做 construction 而不是回头改模型，再考虑：

* weighting 方案
* 更强的 group/sector cap
* 更高的流动性门槛

而不是立刻回去扩 feature zoo。

## 10. 当前结论

一句话收口：

* 第一轮 construction grid 已经验证：这条路是通的，`buffer_exit` 略有帮助，`buffer_entry` 当前不重要
* 第二轮 `top_k` grid 进一步表明：在这条 fixed-signal challenger 上，`top_k = 25` 值得进 shortlist
* 但独立 full run 没有确认 `bx2_be1` 或 `top_k25` 能优于 `raw-scale dedup + groupcap3`
* 所以当前最合理的结构 challenger，仍然是 `raw-scale dedup + groupcap3`；grid 结果只保留为 construction shortlist 证据
