# 研究笔记

本页解决什么：研究笔记目录索引，以及“哪些结论已经沉淀到主线”的状态说明。
本页不解决什么：不承载 CLI、配置或输出契约说明。
适合谁：需要阅读研究笔记或论文摘要的人。
读完你会得到什么：研究笔记入口、当前结论状态和时点型页面写法。
相关页面：`docs/README.md`、`docs/playbooks/README.md`、`docs/config.md`

这个目录放论文精读和研究型笔记，不承载 CLI、配置或输出契约说明。

## 当前内容分组

当前目录已经按两类页面拆成两个子目录：

* `docs/research/papers/`：外部论文精读和背景材料
* `docs/research/notes/`：仓库内研究记录、阶段性结论和 follow-up 总结

### 论文精读

| 页面 | 定位 | 是否已沉淀到主线文档 |
| --- | --- | --- |
| `papers/fundamental-analysis-via-machine-learning-digest.md` | 外部论文背景材料，回答“财报细项 + 非线性模型”为什么值得研究 | 否，属于背景阅读 |
| `papers/predicting-future-earnings-changes-using-machine-learning.md` | 外部论文背景材料，回答“未来盈利变化方向预测 + 细粒度财务数据”这条路线为什么值得关注 | 否，属于背景阅读 |

### 研究笔记与结论沉淀

如果你现在要重新进入 HK quarterly 研究，不建议直接从旧的 follow-up 页面往回翻。  
当前更合理的阅读顺序是：

1. `notes/hk-quarterly-current-state-20260329.md`
2. `notes/hk-quarterly-holdings-analysis-20260329.md`
3. `notes/hk-quarterly-construction-grid-20260329.md`
4. `notes/hk-quarterly-next-step-configs-20260329.md`
5. `notes/hk-quarterly-oos-evidence-20260329.md`
6. 如果你要单开“不用量价指标”的独立路线，再看 `notes/hk-quarterly-pure-fundamentals-20260329.md`
7. 只有当你要追溯结论出处时，再回去看更早的专题页

| 页面 | 当前有效结论 | 是否已沉淀到主线文档 |
| --- | --- | --- |
| `notes/hk-quarterly-current-state-20260329.md` | 当前 quarterly 线的现行口径、哪些旧结论仍保留、哪些已降级成 provenance、以及现在该从哪两条路线继续往前推 | 是，当前应作为 quarterly notes 的总入口 |
| `notes/hk-quarterly-holdings-analysis-20260329.md` | `raw-scale dedup` 的价值主要在于更低换手和更稳定的测试段持仓，`reg_zscore + tr_close` 的最近 OOS 亮点则更集中、更像少数名字驱动 | 否，当前作为组合层解释页保留 |
| `notes/hk-quarterly-construction-grid-20260329.md` | 第一轮 fixed-signal construction sweep 已经表明 `buffer_exit` 比 `buffer_entry` 更值得继续扫；下一步更像是固定 `bx = 2` 后比较 `top_k`，而不是继续扩特征 | 否，当前作为组合构造 follow-up 页保留 |
| `notes/hk-quarterly-next-step-configs-20260329.md` | 当前 quarterly 下一阶段更适合收口到少数几个窗口和特征探针，并统一到 balanced execution 口径下继续比较 | 否，当前作为下一阶段执行建议页保留 |
| `notes/hk-quarterly-oos-evidence-20260329.md` | 最近 `Final OOS` 很亮不等于模型已验证；当前两条 balanced execution 候选更适合当下一轮前瞻验证对象，而不是已确认赢家 | 否，当前作为“线索 vs 证据”边界说明页保留 |
| `notes/hk-quarterly-pure-fundamentals-20260329.md` | 纯 PIT 基本面值得作为独立 benchmark / challenger 线，但第一波应先跑 `ridge -> small xgb_regressor -> xgb_ranker`，而不是直接回头救 `elasticnet` | 否，当前作为独立纯基本面路线说明页保留 |
| `notes/hk-quarterly-pit-regime-shift-202603.md` | 旧 quarterly overlay 基线失效，`ranker h12_w16` 抗漂移版本仍是当前更稳的基线 | 是，已反映到 `docs/playbooks/hk-selected.md` 和相关配置口径 |
| `notes/hk-h12-w16-target-transform-review-20260324.md` | `zscore target` 是当前更值得跟踪的 regressor challenger，但还不能替代 ranker 主基线 | 部分沉淀，摘要已被后续总结页吸收 |
| `notes/hk-quarterly-target-design-and-direction-20260324.md` | 相对化 label 已升级成正式研究副线，但方向切换问题仍需单独验证 | 是，当前是这组 follow-up 的汇总结论页 |
| `notes/hk-quarterly-price-col-ab-20260325.md` | `tr_close` 不足以让 ranker 主线改默认，但对 `reg_zscore` challenger 是正向加成 | 部分沉淀，当前作为价格口径 A/B 的独立汇总页保留 |

## 时点型页面头部模板

带时间语义的研究页，建议统一在开头写清楚下面四项：

* 页面性质：`research-note` / `current-state` / `paper-digest`
* 最后核对时间
* 权威来源：实验 run、当前配置、外部论文或资产目录
* 冲突优先级：和哪一页或哪个产物冲突时，以谁为准

复现具体历史 run 时，优先级始终高于研究笔记的是：

* `config.used.yml`
* `summary.json`
* 当前仍在使用的 preset / playbook

## 当前文件

论文精读：

* `papers/fundamental-analysis-via-machine-learning-digest.md`
* `papers/predicting-future-earnings-changes-using-machine-learning.md`

研究笔记：

* `notes/hk-quarterly-current-state-20260329.md`
* `notes/hk-quarterly-holdings-analysis-20260329.md`
* `notes/hk-quarterly-construction-grid-20260329.md`
* `notes/hk-h12-w16-target-transform-review-20260324.md`
* `notes/hk-quarterly-target-design-and-direction-20260324.md`
* `notes/hk-quarterly-pit-regime-shift-202603.md`
* `notes/hk-quarterly-price-col-ab-20260325.md`
* `notes/hk-quarterly-oos-evidence-20260329.md`
* `notes/hk-quarterly-next-step-configs-20260329.md`
* `notes/hk-quarterly-pure-fundamentals-20260329.md`
