# HK Monthly 现行口径（文件名保留 20260330，内容核对至 2026-04-13）

本页解决什么：把当前 HK monthly 研究线真正需要保留的默认分工、升级边界和下一步动作压成一页。  
本页不解决什么：不替代单次 run 的 `summary.json` / `config.used.yml`，也不重写每轮 probe 的完整实验流水账。  
适合谁：重新接手 monthly 研究，想先知道“现在默认怎么看、什么是 challenger、哪些方向已降级”的读者。  
读完你会得到什么：当前默认口径、最需要跟踪的 challenger、已明确降级的方向，以及继续推进时最值得读的专题页。  
相关页面：`docs/research/notes/hk-monthly-time-window-design-20260330.md`、`docs/research/notes/hk-monthly-pit-frozen-vs-latest-design-20260330.md`、`docs/research/notes/hk-monthly-pit-no-ret-follow-up-20260330.md`、`docs/research/notes/hk-monthly-pit-no-ret-tuning-follow-up-20260405.md`、`docs/research/notes/hk-monthly-ranker-ab-and-next-sweep-20260413.md`、`docs/research/notes/hk-monthly-benchmark-ladder-and-attribution-20260405.md`、`docs/research/notes/hk-monthly-provider-vs-pit-20260330.md`、`docs/playbooks/hk-selected.md`、`docs/research/README.md`

页面性质：`current-state`  
最后核对时间：`2026-04-13`  
权威来源：本页引用的 monthly deep-dive 页面，以及这些页面对应 run 目录下的 `summary.json` / `config.used.yml` / `run.log`  
冲突优先级：如果与具体 run 的 `summary.json` / `config.used.yml` 冲突，以 run 产物为准；如果与更晚样本或更晚的 `current-state` 收口冲突，以更晚页面为准

> 注：为保持仓库内已有链接稳定，本页沿用旧文件名；判断以页内“最后核对时间”为准，不以文件名日期为准。

## 1. 当前默认怎么理解

| 角色 | 当前定位 | 现在怎么用 |
| --- | --- | --- |
| `M-PIT baseline` | 月频研究锚点 | 用来解释旧版 `M-PIT` 为什么在 latest 窗口转弱；不再当实现层默认答案 |
| `M-PIT + no_ret + bx20 / be10` | 当前 monthly PIT default candidate | 仍是默认 PIT 候选；先拿它承接后续新样本，不再急着换主线 |
| `trial_008 + k15_bx25_be12 + groupcap4` | 当前 guarded ranker challenger | 当前 monthly `no_ret` ranker 的主 guarded challenger；适合继续作为 shadow / paper ranker 口径跟踪 |
| `trial_008 + k15_bx20_be10 + groupcap4` | aggressive comparator | 保留作更激进的实现对照；不作为默认 |
| `trial_016 + k15_bx25_be12` | execution ceiling | OOS 实现很亮，但 walk-forward IC 仍偏弱，不能升成默认 |
| `M-provider rebalance-only` | 正式月频 comparator / shadow 候选 | 更像实现候选，不像最干净的研究主线 |
| `Q-PIT` | 低频 benchmark | 保留 benchmark 角色，不回升为 monthly 主线 |

## 2. 为什么现在是这套分工

* `R0-R4` 已经把 baseline 的问题压缩得很清楚：`2025-12-31` cutoff recut 仍为正 `IC`，`2026-03-27` cutoff recut 已转负，所以当前主要矛盾更像 recent months / latest regime，而不是 split 设计本身。
* `M-PIT + no_ret + bx20 / be10` 仍是最像“基本面主导 + 慢执行 + 不直接追 trailing-return”的 PIT 候选，而且它在 latest fixed-`24m`、latest ratio 和 frozen fixed-`24m` 三条口径下都保住了正 `IC`。
* `trial_008 + k15_bx25_be12 + groupcap4` 把 ranker 路线推进到了更合理的 guarded challenger 位置：walk-forward IC 证据比 `trial_016` 更干净，final OOS Sharpe 仍在 `2.20` 左右，turnover 约 `15.8%`，同时 top industry 名字数已被压到 `<= 4`。
* `groupcap3` 在这条线上的代价偏大：虽然 Sharpe 还能抬高，但 active IR 掉得更快，所以当前不作为首选。
* `M-provider` 账面 OOS 仍然最能打，但它的 `final OOS IC` 仍不干净，所以更适合当实现 comparator / shadow 候选，不适合回写成研究主线。
* 最新 benchmark ladder 说明当前 monthly 真正的差距更像 `selected_capw` 背后的 cap-weight / mega-cap 暴露问题，而不是 signal direction 被证伪。

## 3. 当前最值得记住的边界

* 现在不该再把 `pb / pe / size` overlay 组合当 monthly 第一优先方向；这条线已经给出“证据不够干净”的结论。
* 现在也不该继续把 provider 的 `size-neutral` / `hard-cap` / `soft size control` 当主战场；这些 probe 的边际信息已经明显下降。
* `trial_016` 不再是 ranker 默认候选，它更适合当 execution ceiling；signal-side 更应该盯 `trial_008`。
* ranker 线当前最好的状态不是“无 guardrail 的最好曲线”，而是“加了最小 `groupcap4` 之后还能保住大部分实现增量”。
* 当前这条线已经够资格做 `shadow / paper`，但还不够资格被包装成“已能放心重仓上线的成熟单策略”。

## 4. 下一步只做这 3 件事

1. 固定 `M-PIT + no_ret + bx20 / be10` 为当前 PIT default candidate，用后续新样本判断它能否继续守住正 `IC` 和可接受的实现质量。
2. 固定 `trial_008 + k15_bx25_be12 + groupcap4` 为 ranker 主 guarded challenger；`trial_008 + k15_bx20_be10 + groupcap4` 保留为 aggressiveness 对照，不再继续扩 construction 小网格。
3. 把 baseline 的工作严格收窄为“解释 latest 转弱”，继续沿着 `R0-R4` 看逐月 `IC`、行业分布和 size bucket 变化，而不是重新打开大网格。

## 5. 当前不再优先做什么

* 不继续优先救 provider 的 size 倾斜。
* 不继续扩 monthly valuation overlay 组合。
* 不把 `Q-PIT` 重新拔高成 monthly 替代主线。
* 不围着 construction 小参数重新扫一轮大网格。

## 6. 当前阶段判断

* `shadow / paper`：已经够资格开始。
* 很小资金 canary：要等新的样本确认，但 guardrail probe 已经完成，不再是当前 blocker。
* 更成熟的实盘主策略：还需要更长 OOS 和更干净的实现解释。

## 7. 推荐阅读顺序

1. 本页：先把当前默认分工看对。
2. [`hk-monthly-time-window-design-20260330.md`](./hk-monthly-time-window-design-20260330.md)：确认当前 monthly time-split policy。
3. [`hk-monthly-pit-frozen-vs-latest-design-20260330.md`](./hk-monthly-pit-frozen-vs-latest-design-20260330.md)：理解 `R0-R4` 为什么把问题指向 recent regime，而不是 split。
4. [`hk-monthly-pit-no-ret-tuning-follow-up-20260405.md`](./hk-monthly-pit-no-ret-tuning-follow-up-20260405.md)：看当前 default candidate 是怎么收敛出来的。
5. [`hk-monthly-ranker-ab-and-next-sweep-20260413.md`](./hk-monthly-ranker-ab-and-next-sweep-20260413.md)：看 ranker challenger、`trial_008` 和 construction follow-up 的现状。
6. [`hk-monthly-benchmark-ladder-and-attribution-20260405.md`](./hk-monthly-benchmark-ladder-and-attribution-20260405.md)：看当前差距为什么更像 cap-weight / mega-cap 暴露问题。

## 8. 一句话结论

当前 HK monthly 最合理的现行口径是：`M-PIT baseline` 保留为研究锚点，`M-PIT + no_ret + bx20 / be10` 保持默认 PIT candidate，`trial_008 + k15_bx25_be12 + groupcap4` 升为 ranker 主 guarded challenger，`M-provider rebalance-only` 保留为实现 comparator / shadow 候选；接下来优先等新样本和继续前瞻跟踪，而不是重开大网格。
