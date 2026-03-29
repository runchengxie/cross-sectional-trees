# HK Quarterly Construction Grid Follow-up（2026-03-29）

本页解决什么：记录 `raw-scale dedup + groupcap3` 这条结构 challenger 的第一轮 `csml grid` 结果，并明确固定信号后下一步最值得扫的组合构造维度。  
本页不解决什么：不替代主线/副线的总收口，也不重新讨论模型、`tr_close` 或纯基本面路线。  
适合谁：已经接受“当前更该看组合构造，不该继续大扫模型参数”的读者。  
读完你会得到什么：第一轮 buffer sweep 的实际结果、它能支持到什么程度，以及下一轮 construction sweep 最合理该怎么扫。  
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

这一页就是第一轮 construction sweep 的结果记录。

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

## 3. 一个前提：`csml grid` 现在终于能正确带 execution 列了

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

## 6. 下一步最值得扫什么

如果只做一轮最小 follow-up，我会这样排：

1. 固定当前信号：`raw-scale dedup + groupcap3`
2. 固定 `buffer_exit = 2`
3. 暂时把 `buffer_entry` 固定在 `1`
4. 直接扫 `top_k = 15 / 20 / 25`

原因很简单：

* `buffer_entry` 已经证明自己现在不绑定
* `buffer_exit` 已经有一个轻微但一致的方向
* 当前更可能带来可解释差异的维度，已经不是 `be`，而是组合宽度

为避免每次都手敲同一组 buffer 参数，这里已经补了两类 tracked 入口：

* [`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_exec_balanced_local_rawscale_dedup_groupcap3_bx2_be1.yml`](../../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_exec_balanced_local_rawscale_dedup_groupcap3_bx2_be1.yml)
  把当前最像样的结构 challenger 固定到 `buffer_exit = 2`、`buffer_entry = 1`
* [`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_exec_balanced_local_rawscale_dedup_groupcap3_bx2_be1_topk15.yml`](../../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_exec_balanced_local_rawscale_dedup_groupcap3_bx2_be1_topk15.yml)
  `top_k = 15` 的集中版
* [`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_exec_balanced_local_rawscale_dedup_groupcap3_bx2_be1_topk25.yml`](../../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_exec_balanced_local_rawscale_dedup_groupcap3_bx2_be1_topk25.yml)
  `top_k = 25` 的宽版
* [`configs/experiments/sweeps/hk_selected__quarterly_pit_core_hybrid_provider_overlay_rawscale_dedup_groupcap3_topk_grid.yml`](../../../configs/experiments/sweeps/hk_selected__quarterly_pit_core_hybrid_provider_overlay_rawscale_dedup_groupcap3_topk_grid.yml)
  固定 `bx = 2`、`be = 1` 后只扫 `top_k`

对应最小命令：

```bash
uv run csml grid \
  --config configs/experiments/sweeps/hk_selected__quarterly_pit_core_hybrid_provider_overlay_rawscale_dedup_groupcap3_topk_grid.yml \
  --top-k 15,20,25 \
  --cost-bps 25
```

如果 `top_k` 也扫完还没有清楚差异，再考虑：

* weighting 方案
* 更强的 group/sector cap
* 更高的流动性门槛

而不是立刻回去扩 feature zoo。

## 7. 当前结论

一句话收口：

* 第一轮 construction grid 已经验证：这条路是通的，`buffer_exit` 略有帮助，`buffer_entry` 当前不重要
* 所以下一个最有价值的研究方向，不是新因子，而是固定信号后继续做 `top_k` construction sweep
