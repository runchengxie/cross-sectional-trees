# HK Monthly 慢财务五线对比收口（2026-04-13）

> 状态提示：本页属于 active deep-dive，用于收口本轮 monthly `no_ret` ranker guarded challenger 上的慢财务因子与金融 / 非金融切样本实验。当前 monthly 默认入口仍是 [hk-monthly-current-state-20260330.md](./hk-monthly-current-state-20260330.md)。

本页解决什么：把这轮 `positive_cfo_ratio`、`accrual_ratio`、`financial-only`、`nonfinancial-only` 五线对比压成一页，回答“下一步该保留哪条主线、哪些只该当诊断项”。

本页不解决什么：不替代单次 run 的 `summary.json` / `config.used.yml`，也不把 `financial-only` 或 `nonfinancial-only` 直接升级成新的默认主线。

适合谁：已经看过 [hk-monthly-ranker-ab-and-next-sweep-20260413.md](./hk-monthly-ranker-ab-and-next-sweep-20260413.md)，并想知道这一轮慢财务与行业切样本实验到底该怎么落地收口的人。

读完你会得到什么：五条线各自的角色定位、最关键的解释边界，以及下一步为什么该优先做“轻度金融暴露约束”，而不是继续做硬切样本。

相关页面：[hk-monthly-current-state-20260330.md](./hk-monthly-current-state-20260330.md)、[hk-monthly-ranker-ab-and-next-sweep-20260413.md](./hk-monthly-ranker-ab-and-next-sweep-20260413.md)、[hk-monthly-industry-treatment-20260404.md](./hk-monthly-industry-treatment-20260404.md)、[hk-monthly-benchmark-ladder-and-attribution-20260405.md](./hk-monthly-benchmark-ladder-and-attribution-20260405.md)、[../README.md](../README.md)

页面性质：`research-note`

状态：`active deep-dive`

最后核对时间：`2026-04-13`

权威来源：本页列出的 run 目录下 `summary.json` / `config.used.yml`，以及 `artifacts/reports/hk_monthly_positive_cfo_vs_all_industry_slices_20260413/` 下的 `window_metrics.csv` / `attribution_summary.csv`

冲突优先级：如果与具体 run 的 `summary.json` / `config.used.yml` 冲突，以 run 产物为准；如果与后续更晚样本或更晚 compare 冲突，以更晚结果为准

## 1. 先说结论

这轮五线对比最重要的结论不是“找到了新主线”，而是把每条线的角色分清了：

* `positive_cfo_ratio_3y + k15_bx25_be12 + groupcap4` 继续当主 guarded challenger。
* `positive_cfo_ratio_2y + k15_bx20_be10 + groupcap4` 保留为 aggressive comparator。
* `positive_cfo_ratio_3y + accrual_ratio + k15_bx25_be12 + groupcap4` 保留为 signal-side watchlist。
* `nonfinancial-only` 只保留为 diagnostic only。
* `financial-only` 只保留为 diagnostic / implementation sleeve，不升成主线。

一句话收口：

* 当前 monthly 最近这段 realized edge 确实有相当一部分来自金融，但它还不是一个足够干净、能直接升成默认主线的 cross-sectional signal 故事。

## 2. 这次到底比了哪五条线

统一比较口径：

* monthly `no_ret` ranker family
* dated asset 固定在 `2026-04-02 / 2026-04-01` 这一轮研究资产口径
* 对比报告目录：`artifacts/reports/hk_monthly_positive_cfo_vs_all_industry_slices_20260413/`

五条线分别是：

| label | 角色 | 配置 / 来源 |
| --- | --- | --- |
| `main` | guarded challenger | `positive_cfo_ratio_3y + k15_bx25_be12 + groupcap4` |
| `comp` | aggressive comparator | `positive_cfo_ratio_2y + k15_bx20_be10 + groupcap4` |
| `accrual` | slowfund watchlist | `positive_cfo_ratio_3y + accrual_ratio + k15_bx25_be12 + groupcap4` |
| `nonfin` | 非金融诊断项 | `configs/local/hk_selected__m_pit_no_ret_ranker_trial008_gc4_k15_bx25_be12_nonfinancial_fixed20260402.yml` |
| `fin` | 金融诊断项 | `configs/local/hk_selected__m_pit_no_ret_ranker_trial008_gc4_k15_bx25_be12_financial_only_fixed20260402.yml` |

## 3. 24m / full 怎么读

长窗里最值得看的不是单独一个 `Sharpe`，而是 `Sharpe`、`active IR`、`active total return` 和 `IC mean` 放在一起读。

| line | Sharpe | active IR | active total return | IC mean | avg turnover |
| --- | ---: | ---: | ---: | ---: | ---: |
| `main` | `2.32` | `0.48` | `11.2%` | `6.05%` | `16.4%` |
| `comp` | `2.42` | `0.42` | `10.2%` | `5.81%` | `17.6%` |
| `accrual` | `2.19` | `0.45` | `10.3%` | `7.15%` | `16.5%` |
| `nonfin` | `1.48` | `-1.36` | `-17.3%` | `2.94%` | `13.4%` |
| `fin` | `2.03` | `0.95` | `25.2%` | `-8.00%` | `9.58%` |

这张表已经说明了大部分故事：

* `main` 最平衡。
* `comp` 更激进，长窗 `Sharpe` 略高，但主动收益不如 `main`。
* `accrual` 的 `IC mean` 最好，但没有把这个优势稳定转成更强的主动收益。
* `nonfin` 主动收益明显变差。
* `fin` 主动收益最亮，但 `IC mean` 反而最差。

## 4. 每条线各自说明了什么

### 4.1 `main`

`positive_cfo_ratio_3y` 仍是目前最合理的 guarded mainline。  
它不是最激进、也不是单项指标最亮，但它是这五条线里最接近“信号和实现都不过分偏”的点。

### 4.2 `comp`

`positive_cfo_ratio_2y` 没有抢走主线位置。  
它更像 aggressiveness 提升版：实现可以更亮一点，但信号解释没有明显更干净，所以保留 comparator 身份更合理。

### 4.3 `accrual`

`accrual_ratio` 是这轮唯一仍值得继续盯的慢财务 sidecar。  
它在 `IC mean` 上有稳定增量，但 active 指标没有同步压过 `main`，所以更像 signal-side watchlist，而不是立刻升主线。

### 4.4 `nonfin`

`nonfinancial-only` 说明“金融污染”不是当前 monthly 问题的唯一解释。  
把金融整个切掉，并没有把这条线洗得更强，反而把最近这段 realized edge 一起切掉了。

所以这条线的价值主要是：

* 证明不该直接把“金融剔除”误当成默认答案。

### 4.5 `fin`

`financial-only` 的价值也主要是诊断，不是升级主线。  
它在主动收益上最亮，但长期 `IC mean` 为负，而且本身持仓更集中，`avg_names_per_rebalance` 只有约 `8.8`。这更像：

* 金融板块这段时间提供了很强的 realized return engine
* 但它还不是一个足够可信的横截面排序主叙事

## 5. 五线一起看，真正回答了什么

五线一起看，当前更合理的解释是：

* 最近这段 monthly realized edge 里，金融不是纯污染源。
* 但金融贡献出来的东西，更像集中度较高、实现层较亮的收益来源，不像足够干净的主信号。
* 因此现在不该走两个极端：
  * 不该把 `financial-only` 升成默认主线
  * 也不该把 `nonfinancial-only` 升成默认主线

更合理的研究动作是留在全市场主线里，继续做“适度约束”，而不是“硬切样本”。

## 6. 为什么下一步更像“轻度金融暴露约束”

这里说的“轻度金融暴露约束”，意思不是：

* 直接删掉金融
* 或者只做金融

而是：

* 继续保留全市场 universe
* 允许金融股参与排序和入选
* 但不让组合的 realized edge 过度依赖金融集中暴露

它要回答的问题是：

* 如果把金融的集中度稍微压一下，`main` 这条线还能不能保住大部分主动收益？
* 如果能保住，说明金融更多是在抬集中度和 realized path，不一定是唯一 alpha 来源。
* 如果一压就塌，说明这段 realized edge 确实高度依赖金融。

## 7. 当前仓库里，这个“轻约束”最接近什么

当前仓库直接支持的最小约束旋钮仍然是：

```yaml
backtest:
  group_col: first_industry_name
  max_names_per_group: <N>
```

也就是：

* 保留全市场
* 打分不变
* 只在组合层限制单一行业的持仓名字数

这是一种“轻约束”，因为它：

* 不改训练样本
* 不改模型打分
* 不做硬切金融 / 非金融 universe

但要注意两点：

* 当前仓库的内建能力是统一 `groupcap`，不是“只对金融单独设更紧 cap”的分组特例。
* 所以如果你要做更精细的“金融 tighter、其它行业 looser”，还需要再补一个小研究层扩展。

## 8. 当前最合理的下一步

优先级我会这样排：

1. 保留 `main` / `comp` / `accrual` 三条主比较线，不再继续扩慢财务 feature zoo。
2. 在全市场主线里继续测轻约束，而不是继续做 `financial-only` / `nonfinancial-only` 硬切样本。
3. 如果轻约束也说明结果高度依赖金融，再决定是否值得补一个“金融 tighter cap”的小研究工具。

一句话收口：

* 这轮五线结果已经足够说明，下一步该做的是“全市场主线里的金融暴露控制实验”，不是继续在 `financial-only` 和 `nonfinancial-only` 之间摇摆。
