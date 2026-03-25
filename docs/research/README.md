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

| 页面 | 当前有效结论 | 是否已沉淀到主线文档 |
| --- | --- | --- |
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

* `notes/hk-h12-w16-target-transform-review-20260324.md`
* `notes/hk-quarterly-target-design-and-direction-20260324.md`
* `notes/hk-quarterly-pit-regime-shift-202603.md`
* `notes/hk-quarterly-price-col-ab-20260325.md`
