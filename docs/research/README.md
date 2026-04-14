# 研究笔记

本页解决什么：给 `docs/research/notes/` 提供默认入口、阅读顺序和页面角色说明。 \
本页不解决什么：不承载 CLI、配置键或输出契约。 \
适合谁：需要重新接手研究笔记、判断哪些页还在生效、哪些页只保留追溯价值的人。 \
读完你会得到什么：一套更短的阅读顺序、当前有效页面的角色分工，以及最小头部模板。\
相关页面：`docs/README.md`、`docs/playbooks/README.md`、`docs/config.md`

> 注：部分 `current-state` 文件名保留了旧日期以避免破坏仓库内已有链接；阅读时以页内“最后核对时间”为准。

## 现在怎么读这些 notes

建议把 `notes/` 里的页面按下面四类理解：

* `current-state`：现行口径和默认入口，重新接手时先读。
* `active deep-dive`：当前仍有直接信息价值的专题分析、probe 汇总或解释层。
* `implementation caveat`：数据覆盖、freshness、build / health 这类实现边界说明；只在相关问题出现时再读。
* `historical provenance`：保留追溯路径，不再作为默认入口。

## 快速入口

如果你只是要重新接手，不必先读下面所有表格，先按这组入口走。

### 月度调仓港股通选股策略

默认入口：
`notes/hk-monthly-current-state-20260330.md`

优先补读：
`notes/hk-monthly-time-window-design-20260330.md`
`notes/hk-monthly-pit-frozen-vs-latest-design-20260330.md`
`notes/hk-monthly-pit-no-ret-tuning-follow-up-20260405.md`
`notes/hk-monthly-ranker-ab-and-next-sweep-20260413.md`
`notes/hk-monthly-benchmark-ladder-and-attribution-20260405.md`

按需再读：
`notes/hk-monthly-pit-slow-sleeve-probes-20260330.md`
`notes/hk-monthly-pit-no-ret-follow-up-20260330.md`
`notes/hk-monthly-provider-vs-pit-20260330.md`
`notes/hk-monthly-industry-treatment-20260404.md`
`notes/hk-monthly-slowfund-five-line-wrap-up-20260413.md`

追溯降级路线时再读：
`notes/hk-monthly-pit-valuation-overlay-probes-20260330.md`
`notes/hk-monthly-provider-factor-probes-20260330.md`

### 季度调仓港股通选股策略

默认入口：
`notes/hk-quarterly-current-state-20260329.md`

优先补读：
`notes/hk-quarterly-benchmark-and-interpretation-20260405.md`
`notes/hk-quarterly-holdings-analysis-20260329.md`
`notes/hk-quarterly-construction-grid-20260329.md`
`notes/hk-quarterly-oos-evidence-20260329.md`

按需再读：
`notes/hk-quarterly-next-step-configs-20260329.md`
`notes/hk-quarterly-pure-fundamentals-20260329.md`

只在 freshness / health / `provider_dense` 相关问题出现时再读：
`notes/hk-quarterly-pit-provider-coverage-20260411.md`

追溯旧结论时再读：
`notes/hk-quarterly-pit-regime-shift-202603.md`
`notes/hk-h12-w16-target-transform-review-20260324.md`
`notes/hk-quarterly-target-design-and-direction-20260324.md`
`notes/hk-quarterly-price-col-ab-20260325.md`

## 状态快照

### Current State

| 页面 | 当前一句话 |
| --- | --- |
| `notes/hk-monthly-current-state-20260330.md` | 当前 monthly 默认分工是：`M-PIT baseline` 留作研究锚点，`M-PIT + no_ret + bx20 / be10` 继续当默认 PIT candidate，`trial_008 + k15_bx25_be12` 升为 ranker 主 challenger，`M-provider rebalance-only` 保留实现 comparator / shadow 候选。 |
| `notes/hk-quarterly-current-state-20260329.md` | 当前 quarterly 默认分工是：`ranker h12_w16 + close + balanced execution` 保持主线，`reg_zscore h12_w16 + tr_close` 保持第一 challenger，`raw-scale dedup + groupcap3` 继续当结构 probe，`provider_dense` 只保留为 coverage-sensitive 变体。 |

### Active Deep-Dive

| 页面 | 当前角色 |
| --- | --- |
| `notes/hk-monthly-time-window-design-20260330.md` | monthly 正式 time-split policy 与资产边界说明。 |
| `notes/hk-monthly-pit-frozen-vs-latest-design-20260330.md` | monthly `R0-R4` 稳定性拆解；用于回答 baseline 为什么在 latest 窗口转弱。 |
| `notes/hk-monthly-pit-slow-sleeve-probes-20260330.md` | monthly 慢执行模板的第一轮 probe 汇总。 |
| `notes/hk-monthly-pit-no-ret-follow-up-20260330.md` | `no_ret` 为什么能成为 monthly PIT 候选的第一轮证据页。 |
| `notes/hk-monthly-pit-no-ret-tuning-follow-up-20260405.md` | `no_ret + bx20 / be10` 的结构调参和局部模型调参收口页。 |
| `notes/hk-monthly-ranker-ab-and-next-sweep-20260413.md` | monthly ranker A/B、dated-asset 复现约束、`trial_008` / `trial_016` challenger 与 construction follow-up。 |
| `notes/hk-monthly-provider-vs-pit-20260330.md` | monthly 里 `provider vs PIT` 的语义差异和当前分工。 |
| `notes/hk-monthly-benchmark-ladder-and-attribution-20260405.md` | 解释 monthly 当前差距为什么更像 cap-weight / mega-cap 暴露问题。 |
| `notes/hk-monthly-industry-treatment-20260404.md` | monthly 行业异质性的处理顺序和当前代码边界。 |
| `notes/hk-monthly-slowfund-five-line-wrap-up-20260413.md` | monthly 慢财务五线对比的收口页；说明 `main / comp / accrual / fin / nonfin` 各自该扮演什么角色。 |
| `notes/hk-quarterly-benchmark-and-interpretation-20260405.md` | quarterly 主线、challenger、结构 probe 和纯基本面 sidecar 的解释层。 |
| `notes/hk-quarterly-holdings-analysis-20260329.md` | quarterly 持仓稳定性、集中度和组合差异分析。 |
| `notes/hk-quarterly-construction-grid-20260329.md` | quarterly fixed-signal construction shortlist；当前仍更适合当 shortlist，不是升级证据。 |
| `notes/hk-quarterly-next-step-configs-20260329.md` | quarterly 下一阶段配置建议。 |
| `notes/hk-quarterly-oos-evidence-20260329.md` | quarterly 最近 OOS 亮点与“已得到证据”的边界说明。 |
| `notes/hk-quarterly-pure-fundamentals-20260329.md` | quarterly 纯 PIT 基本面 sidecar 路线。 |

### Implementation Caveat

| 页面 | 当前角色 |
| --- | --- |
| `notes/hk-quarterly-pit-provider-coverage-20260411.md` | quarterly PIT freshness / coverage warning 的解释页；说明 `provider_dense` 为什么存在以及何时才该使用。 |

### Historical Provenance

| 页面 | 当前角色 |
| --- | --- |
| `notes/hk-quarterly-pit-regime-shift-202603.md` | quarterly 线为什么走向 anti-drift 的历史起点。 |
| `notes/hk-h12-w16-target-transform-review-20260324.md` | `h12_w16` 下 `target transform` 的中间对照过程。 |
| `notes/hk-quarterly-target-design-and-direction-20260324.md` | `ranker` 与 `reg_zscore` 主副线关系的阶段性总结。 |
| `notes/hk-quarterly-price-col-ab-20260325.md` | `close / tr_close` 专题 A/B 的原始结论页。 |
| `notes/hk-monthly-pit-valuation-overlay-probes-20260330.md` | monthly valuation overlay 为什么被降级的证据链。 |
| `notes/hk-monthly-provider-factor-probes-20260330.md` | provider 线里 size 相关 probes 为什么被降级的证据链。 |

## 时点型页面的最小头部模板

带时间语义的研究页，建议至少写清下面几项：

* 页面性质：`research-note` / `current-state` / `paper-digest`
* 最后核对时间
* 权威来源：实验 run、当前配置、外部论文或资产目录
* 冲突优先级：和哪一页或哪个产物冲突时，以谁为准

如果页面不是 `current-state`，建议再加一行状态提示：

* 说明自己属于 `active deep-dive`、`implementation caveat` 还是 `historical provenance`
* 明确自己不该作为默认入口
* 直接指向对应的 `current-state` 页面

复现具体历史 run 时，优先级始终高于研究笔记的是：

* `config.used.yml`
* `summary.json`
* 当前仍在使用的 preset / playbook

## 当前文件

研究笔记：

* `notes/hk-monthly-current-state-20260330.md`
* `notes/hk-monthly-time-window-design-20260330.md`
* `notes/hk-monthly-pit-frozen-vs-latest-design-20260330.md`
* `notes/hk-monthly-pit-slow-sleeve-probes-20260330.md`
* `notes/hk-monthly-pit-no-ret-follow-up-20260330.md`
* `notes/hk-monthly-pit-no-ret-tuning-follow-up-20260405.md`
* `notes/hk-monthly-ranker-ab-and-next-sweep-20260413.md`
* `notes/hk-monthly-provider-vs-pit-20260330.md`
* `notes/hk-monthly-benchmark-ladder-and-attribution-20260405.md`
* `notes/hk-monthly-industry-treatment-20260404.md`
* `notes/hk-monthly-slowfund-five-line-wrap-up-20260413.md`
* `notes/hk-monthly-pit-valuation-overlay-probes-20260330.md`
* `notes/hk-monthly-provider-factor-probes-20260330.md`
* `notes/hk-quarterly-current-state-20260329.md`
* `notes/hk-quarterly-benchmark-and-interpretation-20260405.md`
* `notes/hk-quarterly-holdings-analysis-20260329.md`
* `notes/hk-quarterly-construction-grid-20260329.md`
* `notes/hk-quarterly-next-step-configs-20260329.md`
* `notes/hk-quarterly-oos-evidence-20260329.md`
* `notes/hk-quarterly-pure-fundamentals-20260329.md`
* `notes/hk-quarterly-pit-provider-coverage-20260411.md`
* `notes/hk-quarterly-pit-regime-shift-202603.md`
* `notes/hk-h12-w16-target-transform-review-20260324.md`
* `notes/hk-quarterly-target-design-and-direction-20260324.md`
* `notes/hk-quarterly-price-col-ab-20260325.md`

论文摘要：

* `papers/fundamental-analysis-via-machine-learning-digest.md`
* `papers/predicting-future-earnings-changes-using-machine-learning.md`
