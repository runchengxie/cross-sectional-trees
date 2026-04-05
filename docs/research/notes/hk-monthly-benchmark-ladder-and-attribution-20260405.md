# HK Monthly Benchmark 梯子与强基准归因（2026-04-05）

本页解决什么：解释当前 HK monthly 线里“为什么自制 benchmark 如此强”、它强在 universe 还是强在 cap-weight，以及这些发现对策略判断意味着什么。  
本页不解决什么：不替代 `current-state` 页面，也不把这轮结论误写成“monthly 主线已经验证完成”或“行业归因已经完全干净”。  
适合谁：已经看到 `selected_capw` 压过策略和多条 comparator，想知道这到底说明了什么的人。  
读完你会得到什么：一套 benchmark ladder 的解释框架、一份基于真实报表的成分/行业/集中度结论，以及为什么当前不该把信号直接反过来买。  
相关页面：`docs/research/notes/hk-monthly-current-state-20260330.md`、`docs/research/notes/hk-monthly-provider-vs-pit-20260330.md`、`docs/research/notes/hk-monthly-industry-treatment-20260404.md`、`docs/research/README.md`、`docs/concepts/benchmark-protocol.md`

页面性质：`research-note`  
状态：`active deep-dive`，这是当前 monthly 线解释强 benchmark 的专题页，不替代 [`hk-monthly-current-state-20260330.md`](./hk-monthly-current-state-20260330.md)  
最后核对时间：`2026-04-05`  
权威来源：`artifacts/runs/hk_sel_xgb_reg_tr_close_exec_balanced_local_20260405_100857_91e4bb6b/summary.json`、`artifacts/runs/hk_sel_xgb_reg_tr_close_exec_balanced_local_20260405_100857_91e4bb6b/backtest_benchmark_compare_summary.csv`、`artifacts/reports/benchmark_attribution/hk_selected_pit_research_capw_20260405_v2/`、`artifacts/reports/benchmark_attribution/hk_selected_pit_research_eqw_20260405_v2/`  
冲突优先级：如果与具体 run 的 `summary.json` / `config.used.yml` 冲突，以 run 产物为准；如果与后续更新样本或更晚的 `current-state` 冲突，以更晚页面为准

## 1. 先说结论

这轮 benchmark ladder 和 attribution 最重要的结论只有三条：

* 当前 monthly 策略几乎没有输给 `selected_eqw`，但明显输给 `selected_capw`。
* 所以“自制 benchmark 很强”的主要来源，不是 universe 本身全面碾压策略，而是同一 research universe 里 **cap-weight / mega-cap 暴露** 很强。
* 这组证据不支持把信号直接反过来买；它更像在提醒你：当前短板主要在组合构造和大市值暴露，而不是横截面信号方向。

一句话收口：

* **当前 monthly 线更像“信号方向基本对，但没有吃满大票龙头行情”；benchmark 的强势主要来自 cap-weight 集中度，而不是神秘 alpha。**

## 2. 这轮 benchmark ladder 到底比了什么

当前 monthly 主线默认对照的 benchmark 可以分成四层：

* `hk_02800`
  * 香港宽基 ETF 代理
* `hk_03432`
  * 港股通主题 ETF comparator
* `hk_connect_full_capw`
  * 全港股通大池子 + 市值加权
* `hk_selected_pit_research_eqw` / `hk_selected_pit_research_capw`
  * 同一 research universe 下的等权 / 市值加权对照

这组设计的目的不是“多放几条 benchmark 看着热闹”，而是要把问题拆开：

* 相对 `02800` / `03432`，回答“这条主动策略至少有没有强过市场代理或港股通主题 ETF”
* 相对 `hk_connect_full_capw`，回答“这条策略有没有明显强过整个港股通池 beta”
* 相对 `hk_selected_pit_research_eqw` / `capw`，回答“这条策略到底输在 universe、输在构造，还是输在信号”

## 3. 当前 OOS 比较实际说明了什么

这轮主参考 run 是：

* `artifacts/runs/hk_sel_xgb_reg_tr_close_exec_balanced_local_20260405_100857_91e4bb6b/`

对齐结果里，最值得记的不是绝对收益，而是下面这组相对关系：

* 相对 `hk_selected_pit_research_eqw`
  * `active_total_return = -1.04%`
  * `IR = -0.03`
  * 结论：几乎打平
* 相对 `hk_selected_pit_research_capw`
  * `active_total_return = -14.86%`
  * `IR = -0.15`
  * 结论：明显落后
* 相对 `hk_connect_full_capw`
  * `active_total_return = -8.92%`
  * 结论：接近打平但略输
* 相对 `hk_02800`
  * `active_total_return = +51.29%`
  * 结论：明显跑赢香港宽基代理
* 相对 `hk_03432`
  * `active_total_return = +9.87%`
  * 但只有 `15` 个对齐期
  * 结论：可看，但证据强度明显低于前面几条

这组结果最关键的解释是：

* 策略并不是“连同 universe 的等权组合都打不过”
* 真正把差距拉开的，是 `selected_capw`

所以当前最合理的解释不是：

* “信号全反了”

而是：

* “benchmark 吃到了 research universe 里大市值龙头权重放大的红利，而策略的 `top20 equal-weight` 没吃满这段行情”

## 4. Attribution 告诉了什么

为了把 `selected_capw` 为什么强拆得更清楚，这轮补了两套 benchmark 自身的全历史归因：

* `artifacts/reports/benchmark_attribution/hk_selected_pit_research_capw_20260405_v2/`
* `artifacts/reports/benchmark_attribution/hk_selected_pit_research_eqw_20260405_v2/`

这里的口径不是策略 OOS 对齐窗口，而是 benchmark 自身的完整历史：

* `87` 个周期
* `selected_capw` 总收益 `125.5%`
* `selected_eqw` 总收益 `102.9%`

也就是说，在同一个 research universe 里，**只把等权换成市值加权，就多出了约 `22.6` 个点的累计收益**。

### 4.1 集中度差异

`selected_capw`：

* 平均 `top1 weight = 13.30%`
* 平均 `top5 weight = 34.65%`
* `effective_n ≈ 24.0`

`selected_eqw`：

* 平均 `top1 weight = 1.25%`
* 平均 `top5 weight = 6.24%`
* `effective_n ≈ 80.8`

这已经足够说明：

* `selected_capw` 不是“同一池子更平滑的版本”
* 它其实是一个明显更集中、明显更偏头部大票的组合

### 4.2 头部成分贡献

`selected_capw` 的头部贡献高度集中：

* 第一大贡献股是 `00700.HK`
  * 贡献占比约 `20.6%`
* 前五大贡献股合计约 `40.7%`
* 前几名主要是：
  * `00700.HK`
  * `00005.HK`
  * `01398.HK`
  * `00939.HK`
  * `01288.HK`

而 `selected_eqw` 的头部集中度就低很多：

* 第一大贡献股是 `00981.HK`
  * 贡献占比约 `5.29%`
* 前五大贡献股合计约 `20.8%`

这组对照基本已经把问题钉住：

* 自制 cap-weight benchmark 的强势，很大一部分来自少数头部大票被持续放大

### 4.3 行业贡献

在当前行业标签资产下，`selected_capw` 已知行业里贡献最大的板块是：

* `银行`
  * 贡献占比约 `31.1%`
* 前三大行业合计约 `58.1%`

这和你从成分上看到的大票金融/龙头行情是吻合的。

不过行业结论要加 caveat：

* 当前行业资产里有不少历史前缀是空值
* 所以行业归因能看，但**不如成分集中度结论那么硬**

## 5. 为什么这不支持“把信号反过来买”

如果一个策略真的更像“方向反了”，更常见的证据应该是：

* `IC` 长期为负
* `Q1 > Q5`
* `long-short` 为负
* 与等权 benchmark 也明显拉不开，甚至系统性更差

但当前 monthly 线不是这个样子：

* 测试期 `IC` 是正的
* 高分组收益优于低分组
* 相对 `selected_eqw` 几乎打平，而不是大幅落后

所以当前更合理的理解是：

* 模型方向并没有被这组证据推翻
* 真正值得优先解释的是：
  * 为什么 `selected_capw` 如此强
  * 为什么 `top20 equal-weight` 没吃满这段大票行情

这条边界很重要，因为它直接决定下一步动作：

* 不是先做 reverse-signal
* 而是先做组合构造、size 暴露和 benchmark 解释层的工作

## 6. `Unknown` 为什么这么多

当前行业归因里 `Unknown` 比例不低，不是因为行业资产没有更新到最近，而是因为：

* `industry_labels_m.parquet` 覆盖到 `2026-04-02`
* 但很多大票在相当长一段历史里，`first_industry_name` 本身就是空值

例如：

* `00700.HK`
  * 共 `263` 条月度行业记录
  * 其中 `210` 条为空
  * 空值一直持续到 `2021-11-30`
* `00388.HK`
  * 也有长期前缀空值
* `03690.HK`
  * 上市后到 `2021-11-30` 之间也有前缀空值

这意味着：

* 当前 `Unknown` 不是“随机少数漏标”
* 而是行业标签资产里存在系统性的历史前缀缺口

所以现在更稳的说法应该是：

* 成分集中度结论：可信度高
* 行业归因结论：可参考，但要明确受 `Unknown` 污染

## 7. 这页对 monthly 主线意味着什么

这轮 benchmark ladder / attribution 更像在帮你把 monthly 线的矛盾重新排队：

### 7.1 它强化了什么

* `M-PIT + no_ret + bx20 / be10` 仍然值得作为当前 monthly PIT candidate 继续推进
* `provider` 仍然是实现 comparator，而不是自然升级成研究主线
* “为什么 benchmark 很强”已经不再是抽象疑问，而是有了具体解释框架

### 7.2 它降低了什么优先级

* 直接做 reverse-signal
* 继续把“benchmark 很强”误读成“模型方向错了”
* 在没解释集中度之前，继续盲目扩 feature zoo

### 7.3 它真正把什么抬成了下一步

* 用 benchmark ladder 解释 `selected_capw` vs `selected_eqw`
* 用成分集中度解释为什么 strategy 会输给 `selected_capw`
* 再决定后面该做：
  * 组合构造调整
  * size 暴露控制
  * 行业最小约束

## 8. 这页现在应该怎么用

如果你今天重新进入 monthly 研究，这页最合理的角色不是替代 `current-state`，而是：

* 先读 `hk-monthly-current-state-20260330.md`
* 再读本页，把“为什么 benchmark 很强”这件事看清楚
* 然后再回到：
  * `hk-monthly-provider-vs-pit-20260330.md`
  * `hk-monthly-industry-treatment-20260404.md`

因为这页真正补上的，是 monthly 线过去比较缺的一层：

* **benchmark 解释层**

## 9. 一句话结论

当前 monthly 线真正值得记住的，不是“自制 benchmark 强得离谱”，而是：

* **它强，主要强在同一 research universe 里的 cap-weight / mega-cap 集中度；策略当前更像输在构造和大票暴露，而不是输在信号方向。**
