# 模型版图与当前选择

本页解决什么：从更广的算法宇宙理解当前项目为什么只维护四个模型，以及下一步什么时候值得扩模型。\
本页不解决什么：不展开具体参数、CLI 用法或单次实验结果明细。\
适合谁：想判断某类算法是否值得纳入本项目，或想解释“为什么现在是这四个模型”的读者。\
读完你会得到什么：一套按任务结构组织的模型版图、当前四模型的角色分工、以及后续扩展的优先级。\
相关页面：`docs/concepts/model-selection.md`、`docs/concepts/benchmark-protocol.md`、`docs/playbooks/hk-selected.md`、`docs/research/notes/hk-quarterly-target-design-and-direction-20260324.md`、`docs/research/notes/hk-quarterly-pit-regime-shift-202603.md`\

这个文档讨论的是“广义模型宇宙”和“当前仓库实际维护的模型集合”之间的关系。\
如果你的问题已经缩小成“现有四个模型这次该选哪个”，直接回到 [model-selection.md](model-selection.md)；本页只讨论模型边界、角色分工和扩展优先级。

先说结论：

* `docs/concepts/universe-modes.md` 讲的是股票池模式。
* 当前仓库代码真正支持的模型类型只有 `xgb_regressor`、`xgb_ranker`、`ridge`、`elasticnet`，见 `cstree.modeling`。
* 当前任务结构决定了最值得先回答的只有四个问题：线性是否够用、稀疏线性是否更优、非线性是否值得、排序目标是否更贴投资动作。
* 当前 HK quarterly PIT + overlay 主线里，最稳的基线仍然是 `xgb_ranker + h12_w16`；最值得继续追的 challenger 是 `xgb_regressor + zscore target`。
* 现阶段更高优先级的改进，是继续收口 `target`、`signal_direction` 和 anti-drift 骨架。

## 1. 先把任务说对

这个项目的核心任务是低频截面选股：

* 数据是表格型、按时间滚动、带明显时间漂移
* 主标签通常是连续型 `future_return`
* 评估关注 `IC`、`top_k`、回测、稳定性，
* 最终动作通常是按分数做横截面排序，再取前若干只股票构造组合

以当前 HK selected 入口为例，默认口径通常是：

* `label.target_col: future_return`
* `eval.top_k: 20`
* `backtest.top_k: 20`

这会直接影响模型选择。

## 2. 我们可以考虑的主流的机器学习算法

最有用的分法，按它和当前任务的关系来分：

| 类别 | 代表算法 | 在本项目里的典型角色 |
| --- | --- | --- |
| 线性回归 | 线性回归、Ridge、Lasso、ElasticNet | 做线性基线、收缩、稀疏化 |
| 线性分类 | Logistic、Softmax Regression | 只有把任务改成二分类或多分类时才自然 |
| 邻近样本 / 原型方法 | KNN、K-means clustering | 更像教学模型、聚类辅助工具或 regime 探索工具 |
| 概率生成式分类 | Naive Bayes | 假设很强，通常不贴当前高相关表格特征 |
| 间隔最大化 | SVM、SVR、RankSVM | 理论可用，工程优先级低 |
| 树模型 | 决策树、随机森林、Bagging | 可做非线性对照，但通常不是当前第一优先级 |
| Boosting / Ranking | XGBoost、LightGBM、CatBoost、GBDT Ranker | 最贴表格数据与截面排序任务 |
| 降维 / 表征学习 | PCA、Kernel PCA、Autoencoder、VAE、t-SNE、UMAP | 更像特征工程、诊断或可视化工具，不是当前主预测模型 |

PS：`K-means clustering`更适合做无监督分群或 regime 辅助分析。

## 3. 各类算法在本项目里的适配度

### 3.1 线性回归家族

| 算法 | 擅长什么 | 为什么合适 / 不合适这个项目 |
| --- | --- | --- |
| 线性回归 | 最朴素的连续值预测 baseline | 可做教学级 baseline，但对共线性脆弱，通常被 `ridge` 替代 |
| Ridge | 稳定的线性回归、抗共线性 | 很合适，适合作为线性 sanity benchmark |
| Lasso | 稀疏化、变量选择 | 有一定价值，但大部分思路已被 `elasticnet` 覆盖 |
| ElasticNet | 同时做收缩和稀疏化 | 合适，适合作为稀疏线性 challenger，但稳定性通常不如 `ridge` |

线性家族的价值，在于它们能回答最基础的问题：这套特征在较弱归纳偏好下，是否已经有可重复的线性信号。

### 3.2 线性分类家族

| 算法 | 擅长什么 | 为什么当前不在主线 |
| --- | --- | --- |
| Logistic Regression | 预测“是否属于正类” | 当前主标签是连续型 `future_return`，不存在明确二分类标签 |
| Softmax Regression | 预测离散桶或多类别 | 当前任务不是天然多分类；强行分桶会丢失收益幅度和相对强弱信息 |

什么时候它们会变得合理：

* 任务被正式改写成“是否进入未来收益前 20%”
* 或者研究目标变成“是否正收益 / 是否超过阈值”

在那之前，回归或排序目标通常更自然。

### 3.3 邻近样本、聚类和简单概率模型

| 算法 | 擅长什么 | 为什么当前不优先 |
| --- | --- | --- |
| KNN | 低维、局部结构稳定、距离定义清晰的问题 | 金融表格特征一多，距离很容易失真；再叠加时间漂移，邻居关系不稳 |
| K-means clustering | 无监督分群、寻找相似样本簇 | 可用于 regime 探索、股票分组或特征压缩前分析，但不是直接预测器 |
| Naive Bayes | 便宜的分类 baseline | 条件独立假设太强，不贴当前高相关因子与财务特征结构 |

这类方法可以做辅助研究，但通常不该承担主线 alpha 预测任务。

### 3.4 SVM、决策树和树的袋装

| 算法 | 擅长什么 | 为什么当前不优先 |
| --- | --- | --- |
| SVM / SVR | 中小样本、边界较清晰的问题 | 对缩放、参数和样本规模更敏感；在这类滚动表格研究里，通常不比 GBDT 更自然 |
| 单棵决策树 | 规则探索、可解释的分裂 | 太不稳，容易把噪声学成规则 |
| Bagging / Random Forest | 非线性、交互、稳健性比单树更好 | 可以做非 boosting 对照，但本质仍是 pointwise 打分，通常不如 boosting / ranking 对题 |

随机森林的优先级在 `xgb_ranker`、`xgb_regressor` 和现有 anti-drift 探索之后。

### 3.5 Boosting 与排序模型

| 算法 | 擅长什么 | 为什么适合这个项目 |
| --- | --- | --- |
| XGBoost / GBDT Regressor | 表格数据、非线性、特征交互 | 很合适，是当前强非线性 benchmark |
| XGBRanker | 同日分组排序学习 | 非常合适，最贴近“横截面排序后取 top-k”的最终动作 |
| LightGBM / CatBoost Ranker | 更大的 boosting / ranking 家族 | 理论上值得考虑，但当前不是工程优先级最高的扩展 |

为什么这类模型天然更贴题：

* 当前数据是标准表格型因子 / 财务 / 量价特征
* 非线性和条件交互在这类任务里很常见
* `xgb_ranker` 能直接按 `trade_date` 分组学习同日排序，避免先回归再间接排序

当前研究页也已经给出更细的状态判断：

* 在 HK quarterly PIT + overlay 这条主线上，`xgb_ranker + h12_w16` 仍是当前最稳的主基线
* `xgb_regressor + zscore target` 是更值得继续追的 challenger
* 这说明当前最缺的是更稳的目标设计和抗漂移机制

### 3.6 降维、表征学习和可视化

| 方法 | 擅长什么 | 在本项目里的更合理定位 |
| --- | --- | --- |
| PCA | 线性降维、去共线性 | 可作为线性分支的辅助特征工程，不是主预测模型 |
| Kernel PCA | 非线性降维 | 可能更灵活，但计算、解释和稳定性成本更高 |
| Autoencoder | 非线性表征压缩 | 只有在特征规模、样本量和基础设施都明显升级时才值得认真引入 |
| VAE | 带生成假设的表征学习 | 研究性更强，当前项目阶段过重 |
| t-SNE / UMAP | 可视化、结构探索、regime 观察 | 更适合做研究诊断图，不适合直接塞进稳定生产训练管线 |

尤其是 `t-SNE / UMAP`，它们最自然的用途是：

* 看特征空间是否有明显分群
* 看某段时期是否发生了分布漂移
* 辅助理解 regime shift

## 4. 为什么当前就保留这四个模型

当前仓库保留的四个模型分别回答四个不同的问题：

| 模型 | 当前角色 | 它主要回答什么 |
| --- | --- | --- |
| `ridge` | 线性 sanity benchmark | 如果只允许线性关系，这套特征有没有基本信号 |
| `elasticnet` | 稀疏线性 challenger | 在线性模型里加入稀疏化，会不会更好 |
| `xgb_regressor` | 强非线性 benchmark | 非线性和特征交互，是否显著提升效果 |
| `xgb_ranker` | 任务最贴题的排序主线 | 既然最终动作是排序选股，直接学同日排序会不会更稳 |

这套组合的优点是：

* 覆盖了线性、稀疏线性、非线性、直接排序四个关键问题
* 每个模型的角色都清楚，不会把 benchmark 和 challenger 混成一团
* 研究比较的解释成本低，适合在同一研究单元里做稳定对照

更重要的是，它和当前研究结论并不冲突：

* `xgb_ranker h12_w16` 仍是当前主基线
* `xgb_regressor + zscore target` 已经证明值得继续追
* `ridge` 仍然是必要的 sanity check
* `elasticnet` 虽然更容易退化，但仍保留了“稀疏线性是否有价值”的问题意识

所以，这四个模型是当前研究骨架的最小完整集。

## 5. 哪些方向值得继续推进，什么时候推进

| 方向 | 为什么值得做 | 什么时候推进最合适 |
| --- | --- | --- |
| `target` 设计 | 当前研究已支持 `zscore > rank > raw` 的 regressor 路线排序 | 现在就该持续推进，它已经是正式副线 |
| `signal_direction` 与 anti-drift | 研究里已观察到明显阶段性方向切换和 regime shift | 现在就该推进，优先级高于扩模型动物园 |
| 增加一个额外的 GBDT challenger | 可验证“是 XGBoost 特有，还是 boosting / ranking 家族普遍有效” | 只有当当前 protocol 已稳定、维护成本可接受时再做，首选可考虑 LightGBM |
| 增加随机森林对照 | 可帮助拆分“树模型本身”与“boosting / ranking objective”带来的效果 | 当你已经想做树模型家族内部精细对照时再做 |
| 分类分支 | 如果决策问题改成门槛式入选，Logistic 一类会变得自然 | 只有当标签和决策本身正式改写成分类问题时 |
| PCA / 降维支线 | 当特征数膨胀、线性分支共线性上升时，可帮助降噪 | 只在线性分支真的被特征规模拖垮时推进 |
| Autoencoder / VAE | 可能提供更强表征能力 | 只有当样本量、特征复杂度、研究基础设施都明显上台阶时 |

当前更合理的优先级可以直接写成：

1. 继续收口 `target`、方向规则和 anti-drift。
2. 在当前 protocol 稳住后，再考虑新增一个 boosting challenger。
3. 更远的分类分支、复杂降维或深度表征学习，放到后面。

## 6. 一句话收口

这个项目当前选择 `ridge + elasticnet + xgb_regressor + xgb_ranker`，是因为这四个模型刚好覆盖了当前最重要的四个研究问题；在 `target`、方向和抗漂移问题还没收口之前，继续往模型动物园里加名字，通常不如先把研究骨架做稳。
