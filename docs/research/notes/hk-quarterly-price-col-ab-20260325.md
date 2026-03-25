# HK Quarterly PIT Price Column A/B Summary（2026-03-25）

本页解决什么：把这轮 HK quarterly PIT + overlay 研究单元里的 `close / tr_close` 六臂 A/B 结果压成一页，方便后续继续追加。
本页不解决什么：不替代主结论页，也不展开 CLI、配置字段或每次 run 的完整流水账。
适合谁：已经知道 `ranker / regressor / zscore` 主线关系，但想快速回答“价格口径默认该怎么选”的读者。
读完你会得到什么：当前 `close / tr_close` 的最小决策、可追溯 run 目录，以及后续追加同类实验时可复用的汇总表结构。
相关页面：`docs/research/notes/hk-quarterly-target-design-and-direction-20260324.md`、`docs/research/notes/hk-quarterly-pit-regime-shift-202603.md`、`docs/config.md`、`docs/providers.md`

页面性质：`research-note`
最后核对时间：`2026-03-25`
权威来源：本页列出的 6 个本地配置、对应 run 目录、`summary.json`、`config.used.yml` 和 `provider_overlay` 审计结果
冲突优先级：如果与具体 run 的 `config.used.yml` / `summary.json` 冲突，以 run 产物为准；如果与后续总收口页冲突，以后续总收口页为准

> 注：如果同一个 `run_name` 存在多个同 hash 目录，本页默认取最新的成功 run。当前 `reg_zscore_h12_w16_tr_close` 采用的是 `20260325_231418_f5c1ac48`。

## 1. 先记住 6 句

* 这里的 `close / tr_close` 是价格口径 A/B，不是“财务上应不应该考虑分红”的原则争论。
* 在本项目里切到 `tr_close`，会一起改动价格派生特征、训练标签、回测收益和 benchmark 口径。
* 这轮 6 个 run 的数据链路本身是干净的：代表性 `provider_overlay` 审计都是 `167/167` symbols cache hit、估值列覆盖率 `100%`、`valuation_age_days = 0`。
* 6 个 run 的 warning 模式完全一致，都只跳过 `02828.HK`、`03033.HK`、`03067.HK` 这 3 个符号各一次，不该解读成“分红或估值数据没下齐”。
* `tr_close` 不足以让 `ranker h12_w16` 主线直接改默认，但对 `reg_zscore h12_w16 / h18_w16` 都是净正向加成。
* 如果继续做这条副线，下一步最该接的是 `reg_zscore + tr_close` 上的动态方向规则，而不是继续扩一轮价格口径网格。

## 2. 实验矩阵

| Arm | 本地配置 | Run Dir |
| --- | --- | --- |
| Ranker h12 w16 close | `configs/local/hk_sel_q_g4_price_ab_ranker_h12_w16_close.yml` | `artifacts/runs/hk_sel_q_g4_price_ab_ranker_h12_w16_close_20260325_224250_2da24d57/` |
| Ranker h12 w16 tr_close | `configs/local/hk_sel_q_g4_price_ab_ranker_h12_w16_tr_close.yml` | `artifacts/runs/hk_sel_q_g4_price_ab_ranker_h12_w16_tr_close_20260325_225706_5f30b4fa/` |
| Reg zscore h12 w16 close | `configs/local/hk_sel_q_g4_price_ab_reg_zscore_h12_w16_close.yml` | `artifacts/runs/hk_sel_q_g4_price_ab_reg_zscore_h12_w16_close_20260325_225204_6d2290aa/` |
| Reg zscore h12 w16 tr_close | `configs/local/hk_sel_q_g4_price_ab_reg_zscore_h12_w16_tr_close.yml` | `artifacts/runs/hk_sel_q_g4_price_ab_reg_zscore_h12_w16_tr_close_20260325_231418_f5c1ac48/` |
| Reg zscore h18 w16 close | `configs/local/hk_sel_q_g4_price_ab_reg_zscore_h18_w16_close.yml` | `artifacts/runs/hk_sel_q_g4_price_ab_reg_zscore_h18_w16_close_20260325_225417_d2b91012/` |
| Reg zscore h18 w16 tr_close | `configs/local/hk_sel_q_g4_price_ab_reg_zscore_h18_w16_tr_close.yml` | `artifacts/runs/hk_sel_q_g4_price_ab_reg_zscore_h18_w16_tr_close_20260325_231843_4d216e4d/` |

## 3. 结果摘要

| Arm | Price Col | CV IC | Eval IC | 全样本 Sharpe | 全样本年化 | 全样本 MDD | Turnover | Final OOS IC | Final OOS Long-Short | Final OOS Sharpe | Final OOS 年化 | Final OOS MDD |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Ranker h12 w16 | `close` | 0.0492 | 0.0225 | -0.3938 | -0.1337 | -0.5122 | 0.5292 | 0.0825 | 0.0068 | 2.0090 | 0.4327 | -0.0825 |
| Ranker h12 w16 | `tr_close` | 0.0822 | -0.0499 | -0.4407 | -0.1225 | -0.4787 | 0.5109 | 0.0791 | 0.0065 | 2.7101 | 0.6232 | -0.0520 |
| Reg zscore h12 w16 | `close` | 0.0961 | -0.0061 | -0.1492 | -0.0350 | -0.2646 | 0.4420 | 0.0911 | 0.0146 | 2.5993 | 0.5499 | -0.0023 |
| Reg zscore h12 w16 | `tr_close` | 0.0903 | -0.0573 | 0.0257 | -0.0141 | -0.2523 | 0.4047 | 0.1131 | 0.0383 | 2.7926 | 0.6702 | -0.0187 |
| Reg zscore h18 w16 | `close` | 0.0936 | -0.0101 | -0.1341 | -0.0423 | -0.2782 | 0.4103 | 0.0953 | 0.0242 | 2.5577 | 0.5886 | -0.0096 |
| Reg zscore h18 w16 | `tr_close` | 0.1028 | -0.0558 | -0.0137 | -0.0205 | -0.2503 | 0.3967 | 0.1173 | 0.0370 | 2.9628 | 0.6574 | -0.0044 |

这张表最该怎么读：

* `ranker h12_w16` 切到 `tr_close` 后，最近 OOS Sharpe 变高，但全样本 `Eval IC` 和全样本 backtest 都更弱，所以证据不足以把 ranker 主线默认切到 `tr_close`。
* `reg_zscore h12_w16` 切到 `tr_close` 后，最近 OOS IC、Long-Short、Sharpe 同时抬升，而且全样本 Sharpe 从负值抬到接近零上方，turnover 也下降。
* `reg_zscore h18_w16` 切到 `tr_close` 后，也是一致改善，并拿到这 6 个 arm 里最高的 Final OOS Sharpe。

## 4. `close -> tr_close` 配对变化

| Arm | `CV IC` 变化 | `Eval IC` 变化 | 全样本 Sharpe 变化 | Turnover 变化 | Final OOS IC 变化 | Final OOS Long-Short 变化 | Final OOS Sharpe 变化 | 当前判断 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Ranker h12 w16 | +0.0330 | -0.0723 | -0.0469 | -0.0184 | -0.0034 | -0.0003 | +0.7011 | 近期 OOS 变亮，但主链路变脏，不升默认 |
| Reg zscore h12 w16 | -0.0057 | -0.0512 | +0.1749 | -0.0373 | +0.0221 | +0.0236 | +0.1933 | 净改善，保留 `tr_close` 支线 |
| Reg zscore h18 w16 | +0.0093 | -0.0457 | +0.1204 | -0.0136 | +0.0221 | +0.0127 | +0.4051 | 净改善，保留 `tr_close` 支线 |

这里有一个容易误读的点：

* `tr_close` 并不是“只让标签更合理一点”。
* 它改的是整条价格链路，所以某个 arm 即使 `Final OOS Sharpe` 变高，也不自动等于“更适合升成默认口径”。
* 对 ranker 主线，目前更像是“recent OOS 更好看，但整条研究线没有更稳”；对 regressor challenger，则更像“同一支线里整体更顺”。

## 5. 数据检查

代表性审计报告：

* `close` 代表 run：`artifacts/reports/hk_sel_q_g4_price_ab_ranker_h12_w16_close_20260325_224250_2da24d57_provider_valuation_audit.csv`
* `tr_close` 代表 run：`artifacts/reports/hk_sel_q_g4_price_ab_ranker_h12_w16_tr_close_20260325_225706_5f30b4fa_provider_valuation_audit.csv`

当前可保留的检查结论：

* 两个代表 run 的 `provider_overlay` 审计都是 `167/167` cache hit。
* 估值列覆盖率都是 `100%`，`valuation_age_days` 全部是 `0`。
* 6 个 run 的 `run.log` 都只出现 3 条 overlay warning，对应 `02828.HK`、`03033.HK`、`03067.HK`。
* 这更像少量非普通股产品被 provider overlay 降级跳过，不像“分红资产没下载齐”或“估值回源失败导致结果飘”。

## 6. 当前结论

当前更稳妥的执行口径是：

1. `ranker h12_w16` 继续维持现有主线，不因为这轮 A/B 直接把默认价格口径改成 `tr_close`。
2. `reg_zscore h12_w16` 如果继续推进，优先保留 `tr_close` 分支。
3. `reg_zscore h18_w16` 作为次 challenger，也优先保留 `tr_close` 分支。
4. 下一步最值得做的是 `signal_direction` 的离线规则回放，优先接在 `reg_zscore_h12_w16_tr_close`，`h18_w16_tr_close` 作为次 challenger。

## 7. 下一阶段执行顺序

如果把这页只压成一个可执行顺序，当前更合理的是：

1. `ranker h12_w16` 继续走执行主线，不因为这轮价格口径 A/B 而换默认。
2. `reg_zscore_h12_w16_tr_close` 作为第一优先 challenger，先做脚本层的离线方向回放。
3. `reg_zscore_h18_w16_tr_close` 作为第二优先 challenger，只有当第一优先规则成立后再跟进复验。
4. 方向规则先用最简单、最可解释的版本，不先改主 pipeline，也不先做更复杂的 regime 分类器。

这页对应的“先别做什么”也需要保留下来：

* 不继续扩 `close / tr_close` 网格。
* 不把 `ranker` 主线直接切到 `tr_close`。
* 不把 `raw target` 重新升回主研究方向。

## 8. 追加约定

如果后续还要把类似实验继续记在这页，建议保持下面这个顺序：

1. 先在“实验矩阵”里补配置名和 run 目录。
2. 在“结果摘要”里补新行，不删旧行。
3. 如果是成对 A/B，再更新“`close -> tr_close` 配对变化”。
4. 只有当主结论发生变化时，再回写到总收口页。
