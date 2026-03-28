# HK Quarterly OOS 亮眼结果与证据边界（2026-03-29）

本页解决什么：把这轮 HK quarterly PIT + balanced execution 下两条候选 run 的结论压成一页，明确哪些只能算研究线索，哪些才够资格叫证据。
本页不解决什么：不替代配置说明、输出字段说明，也不替代单次 run 的原始 `summary.json`。
适合谁：已经看到 `Final OOS` 很亮，但不确定这是不是已经足够支持模型选择的人。
读完你会得到什么：一套更严格的判定口径，以及这两条 run 当前到底该怎么定位。
相关页面：`docs/research/notes/hk-quarterly-target-design-and-direction-20260324.md`、`docs/research/notes/hk-quarterly-price-col-ab-20260325.md`、`docs/concepts/model-landscape.md`、`docs/concepts/benchmark-protocol.md`

页面性质：`research-note`
最后核对时间：`2026-03-29`
权威来源：本页列出的 2 个本地配置、对应 run 目录、`summary.json`、`config.used.yml`
冲突优先级：如果与具体 run 的 `config.used.yml` / `summary.json` 冲突，以 run 产物为准；如果与后续更新的总收口页冲突，以后续总收口页为准

## 1. 先记住 6 句

* 这两条 run 的 `Final OOS` 都是正的，而且不弱。
* 但它们的完整测试段都是负收益，不能因为最后一段亮眼就把它们当成“已验证模型”。
* 这次的 `Final OOS` 只是测试段最后 `8` 个调仓点，不是独立于模型选择之外的新样本。
* 两条 run 在 `2021-03-31` 到 `2023-09-29` 的 `6` 个 walk-forward 测试窗里，回测收益全部为负。
* 所以当前更准确的说法是“找到了最近一个 regime 下表现很亮的候选”，而不是“找到了已经稳健成立的模型”。
* 如果接下来继续围着这段 `Final OOS` 调参，那么这段样本就已经被消费掉了，后面再拿它当证据会变成后验筛选。

## 2. 这次看的是哪两条 run

| 路线 | Run Name | Run Dir |
| --- | --- | --- |
| 主线候选 | `hk_sel_q_g4_fixed_pit_overlay_xgb_rank_antidrift_h12_w16_exec_balanced_local` | `artifacts/runs/hk_sel_q_g4_fixed_pit_overlay_xgb_rank_antidrift_h12_w16_exec_balanced_local_20260328_235502_6e283435/` |
| Challenger | `hk_sel_q_g4_fixed_pit_overlay_xgb_reg_zscore_h12_w16_tr_close_exec_balanced_local` | `artifacts/runs/hk_sel_q_g4_fixed_pit_overlay_xgb_reg_zscore_h12_w16_tr_close_exec_balanced_local_20260328_235640_38b3eba8/` |

这两条 run 用的是同一类执行假设：

* 本地 daily / instruments / fundamentals / ex_factors 资产
* `balanced execution`
* quarterly PIT + overlay 骨架

所以它们的比较口径是干净的；问题不在“成本假设不一致”，而在“整段测试期是否够稳”。

## 3. 结果怎么读才不容易骗到自己

### 3.1 先看完整测试段，而不是只看最后一段

| 路线 | 完整测试段 `total_return` | 完整测试段 `Sharpe` | Final OOS `total_return` | Final OOS `Sharpe` |
| --- | ---: | ---: | ---: | ---: |
| `ranker h12_w16 + close + balanced execution` | `-19.65%` | `-0.06` | `77.65%` | `2.04` |
| `reg_zscore h12_w16 + tr_close + balanced execution` | `-35.27%` | `-0.47` | `100.78%` | `1.81` |

这张表最该记住的不是“最后一段真亮”，而是：

* 亮点集中在测试段最后一截
* 把整个测试段放在一起看，这两条都没有证明自己“整体为正”

### 3.2 再看 walk-forward 的前面几窗有没有一贯性

当前两条 run 的 `walk_forward.results` 都是 `6` 个测试窗，`test_size=0.2`、`step_size=1`。

| 路线 | `2021-03-31` 到 `2023-09-29` 的 6 个 WF 测试窗 | 当前判断 |
| --- | --- | --- |
| `ranker h12_w16 + close + balanced execution` | `6/6` 窗回测收益为负 | 不是“偶尔坏一次”，而是前一段 regime 持续不顺 |
| `reg_zscore h12_w16 + tr_close + balanced execution` | `6/6` 窗回测收益为负 | 同样不是稳定线，只是最近一段明显改善 |

也就是说，这次不是“全段稳健，最后一段更亮”。
更像是“前一段普遍不行，最后一段突然变好”。

## 4. 这算不算数据挖掘

算，至少已经进入“有数据挖掘风险”的区域。

更准确地说，要分两层：

### 4.1 还不算彻底失真时

如果我们只是说：

* 这两条是下一轮最值得跟踪的候选
* 当前 `Final OOS` 说明最近 regime 下它们可能有信号

那还只是“研究线索”，不是错误结论。

### 4.2 会变成后验筛选时

如果我们进一步说：

* 因为这段 `Final OOS` 很好，所以这条模型已经验证通过
* 因为这段 `Final OOS` 很好，所以继续围着它调参数，再拿同一段结果证明它好

那就已经是典型的后验筛选。

原因很简单：

* 这段 `Final OOS` 已经参与了模型选择
* 被用来选过模型的样本，就不再是干净证据

## 5. 现在什么叫线索，什么叫证据

### 5.1 当前这两条最多只能算线索

当前可以成立的说法是：

* `ranker h12_w16 + close + balanced execution` 仍然是更像主线的候选，因为它在同口径下完整测试段没那么差，而且 Final OOS Sharpe 更高。
* `reg_zscore h12_w16 + tr_close + balanced execution` 仍然是值得跟踪的 challenger，因为它在最近 regime 下收益更强，且 turnover 与成本拖累更低。
* 这两条都说明“最近一段市场环境里，确实可能存在可用信号”。

这些都属于研究线索。

### 5.2 当前还不够叫证据

至少缺下面几件事之一：

* 完整测试段在成本后也能站住，不能整段还是负收益。
* 多个 walk-forward 窗口里不是长期一边倒地为负。
* 一个没有参与过模型选择的新时间段。
* 或者 paper / shadow / canary 的前瞻验证。

所以当前还不能说：

* “这条模型已经验证通过”
* “这条模型可以替代主基线”
* “这段 `Final OOS` 足以证明它稳定可复现”

## 6. 当前最稳妥的决策

如果只压成最小决策，当前更合理的是：

1. 保留最多 `1-2` 条候选，不再根据这段 `Final OOS` 继续大范围扩网格。
2. 把当前这段 `Final OOS` 视为“已使用证据”，不再把它当成干净 holdout。
3. `ranker h12_w16 + close + balanced execution` 继续作为主线候选。
4. `reg_zscore h12_w16 + tr_close + balanced execution` 继续作为第一优先 challenger。
5. 真正要决定谁更合适，下一步必须靠新的时间段或前瞻 paper / shadow，而不是继续复读当前这段 OOS。

## 7. 一句话结论

这两条 run 当前都不是“已经证明自己”的模型；它们只是“在最近一个 regime 里表现很亮、值得冻结后继续前瞻验证的候选”。
