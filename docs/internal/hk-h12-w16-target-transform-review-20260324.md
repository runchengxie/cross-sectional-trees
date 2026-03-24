# HK H12 W16 Target Transform Review 2026-03-24

本文件记录 `hk_sel_q_g4_fixed_pit_overlay` 研究单元在 `halflife=12`、`rolling train_window=16` 下的一次对照实验。

目标不是立刻换掉当前主基线，而是回答两个问题：

1. 在相同 anti-drift 骨架下，`xgb_regressor` 能否挑战当前最佳 `xgb_ranker`。
2. 对 regressor 来说，把训练标签从原始 `future_return` 改成横截面相对强弱，是否值得继续追。

## 对照配置

已跑：

* `configs/local/hk_sel_q_g4_fixed_pit_overlay_xgb_rank_antidrift_h12_w16_anchor.yml`
* `configs/local/hk_sel_q_g4_fixed_pit_overlay_xgb_reg_antidrift_h12_w16_raw.yml`
* `configs/local/hk_sel_q_g4_fixed_pit_overlay_xgb_reg_antidrift_h12_w16_rank.yml`
* `configs/local/hk_sel_q_g4_fixed_pit_overlay_xgb_reg_antidrift_h12_w16_zscore.yml`

## 已有 run

| Arm | Run Dir | Model | Train Target |
| --- | --- | --- | --- |
| Anchor | `artifacts/runs/hk_sel_q_g4_fixed_pit_overlay_xgb_rank_antidrift_h12_w16_anchor_20260324_143742_fe50c524/` | `xgb_ranker` | `none` |
| Challenger A | `artifacts/runs/hk_sel_q_g4_fixed_pit_overlay_xgb_reg_antidrift_h12_w16_raw_20260324_144036_55b02cd0/` | `xgb_regressor` | `none` |
| Challenger B | `artifacts/runs/hk_sel_q_g4_fixed_pit_overlay_xgb_reg_antidrift_h12_w16_rank_20260324_144239_a93ab9f8/` | `xgb_regressor` | `rank` |
| Challenger C | `artifacts/runs/hk_sel_q_g4_fixed_pit_overlay_xgb_reg_antidrift_h12_w16_zscore_20260324_150729_61621eef/` | `xgb_regressor` | `zscore` |

## 核心结果

| Arm | CV IC | Eval IC | Eval Top-K 正收益占比 | Final OOS IC | Final OOS Top-K 正收益占比 | Final OOS 回测总收益 | Final OOS Sharpe | 全样本回测总收益 | 全样本 Active Return |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Anchor ranker | 0.0492 | 0.0225 | 0.4769 | 0.0825 | 0.7063 | 0.8469 | 2.0090 | -0.3423 | -0.0277 |
| Regressor raw | 0.0359 | -0.0618 | 0.4346 | 0.0986 | 0.7125 | 1.2042 | 1.8277 | -0.2191 | 0.0195 |
| Regressor rank | 0.0698 | -0.0037 | 0.4538 | 0.0965 | 0.7313 | 1.0735 | 2.5099 | -0.3956 | -0.1064 |
| Regressor zscore | 0.0961 | -0.0061 | 0.4500 | 0.0911 | 0.7188 | 1.1122 | 2.5993 | -0.0988 | 0.1766 |

补充观察：

* `xgb_ranker` 仍是当前最稳的主基线。它是四条里唯一主评估 `Eval IC` 为正的模型。
* `xgb_regressor + raw target` 的近期 `Final OOS` 最亮，但主评估 `Eval IC` 和 walk-forward 平均 `test_ic` 都偏弱，更像近期局部 regime 受益。
* `xgb_regressor + rank target` 明显改善了 regressor 路线。它把 `CV IC` 从 `0.0359` 提高到 `0.0698`，也把主评估 `Eval IC` 从 `-0.0618` 拉回到接近零。
* `xgb_regressor + zscore target` 是当前最强 regressor challenger。它拿到了四条里最高的 `CV IC`，walk-forward 平均 `test_ic` 也接近 anchor，同时全样本 `Active Return` 转正且明显领先。

## Walk-forward 摘要

| Arm | Walk-forward 平均 Test IC | Walk-forward 平均 Long-Short | Walk-forward 平均 Top-K 正收益占比 | Walk-forward 平均回测总收益 |
| --- | ---: | ---: | ---: | ---: |
| Anchor ranker | 0.0611 | 0.0205 | 0.4458 | -0.1401 |
| Regressor raw | -0.0100 | -0.0006 | 0.4083 | -0.2180 |
| Regressor rank | 0.0199 | 0.0189 | 0.4222 | -0.1222 |
| Regressor zscore | 0.0560 | 0.0309 | 0.4222 | -0.1359 |

这里最重要的结论不是谁最近涨得多，而是谁在滚动窗口里更稳：

* `anchor` 仍然最好。
* `zscore target` 已经超过 `rank target`，成为最值得继续追的 regressor 版本。
* `rank target` 仍然明显好于 `raw target`。
* `raw target` 当前不适合作为优先 challenger。

## 置换检验补充

按 `eval.cv_ic.mean` 相对 100 次 permutation 的经验分位看：

* Anchor ranker：经验 `p ≈ 0.19`
* Regressor raw：经验 `p ≈ 0.15`
* Regressor rank：经验 `p ≈ 0.19`
* Regressor zscore：经验 `p ≈ 0.06`

`zscore target` 还谈不上显著，但已经是四条里最接近“脱离随机波动”的版本。

## 风险提示

四条 run 仍然显示明显的方向漂移迹象：

* 主评估 `signal_direction` 都是 `+1`
* 但 walk-forward 窗口里，`anchor`、`raw`、`zscore` 的 6 个窗口全是 `-1`
* `rank target` 也是 6 个窗口里有 5 个是 `-1`

这说明 anti-drift 还没有解决方向不稳问题。当前 `Final OOS` 只有 8 个调仓日，不能单凭这段结果替换主基线。

## 当前判断

优先级建议：

1. 保留 `xgb_ranker h12_w16` 作为主基线。
2. 把 `xgb_regressor + zscore target` 升级为下一轮正式 challenger。
3. `xgb_regressor + rank target` 作为次优 challenger 保留。
4. `xgb_regressor + raw target` 暂时降级，不继续优先扩展。

当前四路的实用排序建议：

1. 如果优先看“主评估口径是否最稳”，仍然是 `anchor ranker` 第一。
2. 如果优先看“下一轮最值得扩展的 challenger”，是 `regressor + zscore target` 第一。
3. 如果要给 regressor 路线保留两条 target 方案，顺序是 `zscore > rank > raw`。

## 推荐 follow-up grid

下一轮不建议同时扩太多变量。最小但信息量高的一组是：

* 锚点：`configs/local/hk_sel_q_g4_fixed_pit_overlay_followup_anchor_rank_h12_w16.yml`
* Challenger：`configs/local/hk_sel_q_g4_fixed_pit_overlay_followup_reg_zscore_h06_w16.yml`
* Challenger：`configs/local/hk_sel_q_g4_fixed_pit_overlay_followup_reg_zscore_h12_w12.yml`
* Challenger：`configs/local/hk_sel_q_g4_fixed_pit_overlay_followup_reg_zscore_h12_w16.yml`
* Challenger：`configs/local/hk_sel_q_g4_fixed_pit_overlay_followup_reg_zscore_h12_w20.yml`
* Challenger：`configs/local/hk_sel_q_g4_fixed_pit_overlay_followup_reg_zscore_h18_w16.yml`

这组是围绕 `h12_w16` 中心点做一个十字形小扫：

* `halflife` 只看 `6 / 12 / 18`
* `train_window` 只看 `12 / 16 / 20`
* 每次只动一个旋钮，避免解释混乱
* `ranker` 只保留当前最佳点做锚，不重复扩 ranker 全网格

建议比较顺序：

1. 先看 `zscore` 是否在 `eval.ic`、walk-forward 平均 `test_ic`、全样本 `active_total_return` 三项同时维持领先。
2. 再看最优 `zscore` 点是否真正超过 `anchor ranker`。
3. 如果 `zscore` 小扫里出现更优点，再决定是否补 ranker 的对称复扫。
