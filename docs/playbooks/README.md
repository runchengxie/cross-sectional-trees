# 研究配方首页

本页解决什么：给研究流程类页面提供统一入口和阅读顺序。
本页不解决什么：不展开参数细节与概念定义。
适合谁：已经明确要做研究路线选择的人。
读完你会得到什么：HK selected 路线相关的阅读顺序与分工。
相关页面：`docs/cookbook.md`、`docs/cli.md`、`docs/config.md`、`docs/concepts/`

`docs/playbooks/` 这一组文档只处理研究流程。

如果你现在的问题是“下一步该跑哪条路线”，先从这里开始。

## 新手阅读顺序

建议按下面的顺序读：

1. 先看 [hk-selected.md](./hk-selected.md)，先选频率和数据路线。
2. 如果你选的是 PIT 财务路线，再看 [hk-data-assets.md](./hk-data-assets.md) 准备资产。
3. 如果你已经准备做正式对比，再看 `docs/concepts/benchmark-protocol.md` 确认 benchmark 阶梯。
4. 如果你要派生本地配置，或判断某个实验值不值得沉淀成仓库模板，再看 [research-template-design.md](./research-template-design.md)。

补充：

* 季度 PIT 路线现在建议先做覆盖率体检，把 `Fill Dependence` 调到可接受状态，再做基线和四模型比较。入口在 [hk-selected.md](./hk-selected.md) 和 `csml rqdata inspect-hk-pit-coverage`。

## 每一页解决什么问题

| 页面 | 解决的问题 | 什么时候打开 |
| --- | --- | --- |
| `hk-selected.md` | 先跑哪条 HK selected 研究路线 | 想先选 `M/Q/Y`、选量价还是 PIT 财务、选四模型 PK 入口 |
| `hk-data-assets.md` | PIT 股票池、日线、财务资产怎么准备 | 需要 `pipeline_fundamentals.parquet`、要做数据归档、要补全资产 |
| `research-template-design.md` | 什么时候派生配置，什么时候新建模板 | 想把实验沉淀成模板，或担心 `configs/` 越长越乱 |

## 常见起点

### 我第一次做 HK selected

先看：

1. [hk-selected.md](./hk-selected.md)
2. 如果走 PIT 财务路线，再看 [hk-data-assets.md](./hk-data-assets.md)
3. 资产准备完成后，先跑 PIT 覆盖率体检，再决定基线和模型比较顺序

### 我已经知道要跑哪条路线，但不知道该不该新建模板

直接看：

* [research-template-design.md](./research-template-design.md)

### 我想做季度或年度低频财报研究

建议顺序：

1. [hk-selected.md](./hk-selected.md)
2. [hk-data-assets.md](./hk-data-assets.md)
3. 先跑 PIT 覆盖率体检
4. [research-template-design.md](./research-template-design.md)

## 这组文档怎么分工

这里的分工保持简单：

* `hk-selected.md` 负责路线选择和比较顺序。
* `hk-data-assets.md` 负责资产准备和本地归档。
* `research-template-design.md` 负责模板维护规则。

参数权威说明仍然在：

* `docs/cli.md`
* `docs/config.md`
