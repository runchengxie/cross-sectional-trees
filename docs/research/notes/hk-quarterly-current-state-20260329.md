# HK Quarterly 现行口径（文件名保留 20260329，内容核对至 2026-04-11）

本页解决什么：把当前 HK quarterly 研究线真正还在生效的默认主线、候选路线、结构探针和数据边界压成一页。
本页不解决什么：不替代单次 run 的 `summary.json` / `config.used.yml`，也不重写每篇 historical note 的完整证据链。  
适合谁：重新进入 quarterly 研究，想先知道“现在默认看哪条、哪些页仍相关、哪些内容已经降级”的读者。  
读完你会得到什么：当前默认口径、主要候选路线、当前不再优先的方向，以及下一步最值得继续推进的少数动作。
相关页面：`docs/playbooks/hk-selected.md`、`docs/research/notes/hk-quarterly-benchmark-and-interpretation-20260405.md`、`docs/research/notes/hk-quarterly-holdings-analysis-20260329.md`、`docs/research/notes/hk-quarterly-construction-grid-20260329.md`、`docs/research/notes/hk-quarterly-oos-evidence-20260329.md`、`docs/research/notes/hk-quarterly-pure-fundamentals-20260329.md`、`docs/research/notes/hk-quarterly-pit-provider-coverage-20260411.md`

页面性质：`current-state`  
最后核对时间：`2026-04-11`  
权威来源：当前 quarterly notes、相关 balanced execution run、`docs/playbooks/hk-selected.md` 的现行收口，以及 provider coverage / health note  
冲突优先级：如果与具体 run 的 `config.used.yml` / `summary.json` 冲突，以 run 产物为准；如果与更晚的 playbook、preset 或 `current-state` 收口冲突，以更晚页面为准

> 注：为保持仓库内已有链接稳定，本页沿用旧文件名；判断以页内“最后核对时间”为准，不以文件名日期为准。

## 1. 术语速查

| 本页写法 | 含义 |
| --- | --- |
| 主线 | 当前默认研究锚点 |
| 候选路线（challenger） | 有局部亮点，仍需继续验证的路线 |
| 结构探针（structural probe） | 主要检查组合构造或持仓稳定性，不直接证明信号更强 |
| 辅助路线（sidecar） | 独立回答一个问题，暂不替换主线 |
| 数据边界（caveat） | 数据覆盖、新鲜度或构建口径带来的使用限制 |

## 2. 当前默认怎么理解

| 角色 | 当前定位 | 现在怎么用 |
| --- | --- | --- |
| `ranker h12_w16 + close + balanced execution` | 默认主线 | 仍是 quarterly 默认锚点；它在现有证据里最稳 |
| `reg_zscore h12_w16 + tr_close + balanced execution` | 第一候选路线（challenger） | 保留为最值得跟踪的候选；最近 OOS 亮点不能直接覆盖前段弱证据 |
| `raw-scale dedup + groupcap3` | 结构候选 / 结构探针 | 主要回答组合修形和持仓稳定性问题，不直接等同于“信号更强” |
| `xgb_regressor + operating_margin` | 纯 PIT 基本面辅助路线（sidecar） | 作为 benchmark / challenger 线保留，不直接替掉当前 hybrid 主线 |
| `provider_dense` variant | 数据边界配套变体 | 仅用于 coverage-sensitive probe 和 health gate，不是新的 quarterly 默认配置 |

## 3. 为什么现在是这套分工

* quarterly 的主问题仍然是 `regime shift / concept drift`，不是“模型名字还不够多”；这一点没有被后续 follow-up 推翻。
* `tr_close` 依然是路线相关结论，不能一刀切设为默认值：它对 ranker 主线证据不足，对 `reg_zscore` challenger 才是净正向加成。
* 固定分数组合网格已经说明 construction 值得做，也给出了 shortlist，但还没有给出足够干净的证据去替掉主线默认。
* 纯 PIT 基本面路线值得保留。它回答的是“基本面本身有没有独立信息量”，不承担替换当前 hybrid 主线的结论。
* `2026-04-11` 的 provider coverage note 已经把 freshness warning 的性质说清楚：它更像 provider sparse 字段导致的 coverage caveat，不是 build / dedup bug；因此 `provider_dense` 只应作为覆盖率敏感场景的变体，不应回写成新默认。

## 4. 当前最值得记住的边界

* 最近 `Final OOS` 很亮，不等于模型已经验证通过；这段样本已经被消费过。
* `balanced execution` 是当前默认解释口径；更早那些 flat cost 下的亮点现在只保留背景价值。
* `raw-scale dedup + groupcap3` 更像结构探针，不构成直接替换主线的理由。
* provider coverage warning 现在不该再被默认解读成“资产刷新失败”或“build 代码有 bug”。

## 5. 当前不再优先做什么

* 不回头把 `elasticnet` 当 quarterly 主线修复方案。
* `tr_close` 在 challenger 上有效，不足以触发整个 quarterly 研究线重刷。
* 不继续围着已消费的最近 OOS 大扫价格口径、窗口和模型组合。
* 不把 `provider_dense` 变体误写成新的 benchmark baseline。

## 6. 下一步只做这 3 件事

1. 冻结当前主线和 challenger 规格，把新的判断尽量留给后续前瞻样本，避免继续扩模型 zoo。
2. 把 `raw-scale dedup + groupcap3` 继续当结构 challenger 使用，只在很小范围内看组合构造，不把 shortlist 直接升成默认。
3. 在覆盖率敏感的 quarterly probe 里显式区分“默认 hybrid baseline”和“provider_dense coverage variant”，避免再把数据 caveat 和模型结论混在一起。

## 7. 推荐阅读顺序

1. 本页：先把默认主线、候选路线和数据边界看对。
2. [`hk-quarterly-benchmark-and-interpretation-20260405.md`](./hk-quarterly-benchmark-and-interpretation-20260405.md)：理解主线、候选路线、结构探针和纯基本面辅助路线分别在回答什么。
3. [`hk-quarterly-holdings-analysis-20260329.md`](./hk-quarterly-holdings-analysis-20260329.md)：看结构候选到底是在修组合还是改信号故事。
4. [`hk-quarterly-construction-grid-20260329.md`](./hk-quarterly-construction-grid-20260329.md)：看为什么 construction 结果现在更适合当 shortlist，不足以作为升级证据。
5. [`hk-quarterly-oos-evidence-20260329.md`](./hk-quarterly-oos-evidence-20260329.md)：看为什么最近 OOS 亮点不能直接当证据。
6. [`hk-quarterly-pit-provider-coverage-20260411.md`](./hk-quarterly-pit-provider-coverage-20260411.md)：只在你需要处理 freshness / coverage warning、或想理解 `provider_dense` 变体时再读。

## 8. 一句话结论

当前 HK quarterly 最合理的现行口径仍然是：`ranker h12_w16 + close + balanced execution` 保持默认主线，`reg_zscore h12_w16 + tr_close + balanced execution` 保持第一候选路线，`raw-scale dedup + groupcap3` 保持结构探针，纯 PIT 基本面线继续做独立辅助路线；`provider_dense` 只作为 coverage-sensitive 变体保留，不升级成新的默认 baseline。
