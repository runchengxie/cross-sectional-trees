# 研究配方首页

本页解决什么：给正式研究流程类页面提供统一入口和阅读顺序。
本页不解决什么：不展开参数细节与概念定义。
适合谁：已经明确要做研究路线选择的人。
读完你会得到什么：HK selected 路线相关的阅读顺序与分工。
相关页面：`docs/pipeline-overview.md`、`docs/cookbook.md`、`docs/rqdata/README.md`、`docs/cli.md`、`docs/config.md`、`docs/concepts/`

`docs/playbooks/` 这一组文档只处理研究流程。

如果你现在的问题是“下一步该跑哪条路线”，先从这里开始。
如果你现在的问题是“HK / RQData 离线资产和 API 快照资料该从哪里看”，更适合从 `docs/rqdata/README.md` 进入。
如果你现在的问题是“RQData 快到期了，最后应该冻结什么”，直接看 [hk-data-assets.md](./hk-data-assets.md#rqdata-权限失效前冻结清单)。
如果你只是想按通用任务顺序推进，而不是选择正式研究路线，回到 `docs/cookbook.md` 更合适。

## 新手阅读顺序

建议按下面的顺序读：

1. 先看 [hk-selected.md](./hk-selected.md)，先选频率和数据路线。
2. 如果你选的是 PIT 财务路线，再看 [hk-data-assets.md](./hk-data-assets.md) 准备资产。
3. 如果你想先确认“哪些 HK RQData 接口已经接了、哪些本地已经有资产、哪些今天还能下”，再看 [hk-rqdata-status.md](./hk-rqdata-status.md)。
4. 如果你已经确定后面大概率不会再续 RQData，再看 [hk-data-assets.md](./hk-data-assets.md#rqdata-权限失效前冻结清单) 把 current asset 和关键研究入口冻住。
5. 如果你已经拿到了 HK 分钟线，想继续看 `5m` 落盘、quota 和滑点校准，再看 [hk-intraday-assets.md](./hk-intraday-assets.md)。
6. 如果你已经准备做正式对比，再看 `docs/concepts/benchmark-protocol.md` 确认 benchmark 阶梯。
7. 如果你要派生本地配置，或判断某个实验值不值得沉淀成仓库模板，再看 [research-template-design.md](./research-template-design.md)。

补充：

* 季度 PIT 路线现在建议先做覆盖率体检，把 `Fill Dependence` 调到可接受状态，再做基线和四模型比较。入口在 [hk-selected.md](./hk-selected.md) 和 `cstree rqdata inspect-hk-pit-coverage`。

## 每一页解决什么问题

| 页面 | 解决的问题 | 什么时候打开 |
| --- | --- | --- |
| `hk-selected.md` | 先跑哪条 HK selected 研究路线 | 想先选 `M/Q/Y`、选量价还是 PIT 财务、选四模型 PK 入口 |
| `hk-data-assets.md` | PIT 股票池、日线、财务资产怎么准备 | 需要 `pipeline_fundamentals.parquet`、要做数据归档、要补全资产 |
| `hk-rqdata-status.md` | 哪些 HK RQData API 已接入、已有资产、当前还能不能下 | 想补资产前先确认现状，或排查某条接口到底有没有打通 |
| `hk-data-assets.md` 的“RQData 权限失效前冻结清单” | RQData 权限快失效前，最后该冻结哪些资产和研究入口 | 你已经判断后面大概率离线运行，不再维护在线 refresh |
| `hk-intraday-assets.md` | HK `5m` 分钟线当前落了哪些块、quota 还够不够、已经产出哪些滑点报告 | 准备继续补分钟线，或想把现有 `5m` 数据直接拿来校准执行假设 |
| `research-template-design.md` | 什么时候派生配置，什么时候新建模板 | 想把实验沉淀成模板，或担心 `configs/` 越长越乱 |

## 常见起点

### 我第一次做 HK selected

先看：

1. [hk-selected.md](./hk-selected.md)
   如果你本地 HK assets 已就绪，而且想直接走当前月频研究主线，优先从 `configs/experiments/variants/hk_selected__tr_close_execution_balanced_local.yml` 开始；这条入口默认使用 universe-aligned cap-weight benchmark 文件。
2. 如果走 PIT 财务路线，再看 [hk-data-assets.md](./hk-data-assets.md)
3. 如果要继续补 RQData 资产，先看 [hk-rqdata-status.md](./hk-rqdata-status.md)
4. 如果已经落了 HK `5m`，再看 [hk-intraday-assets.md](./hk-intraday-assets.md)
5. 资产准备完成后，先跑 PIT 覆盖率体检，再决定基线和模型比较顺序

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
* `hk-rqdata-status.md` 负责记录 HK RQData API 的接入、资产和活体 probe 状态。
* `hk-intraday-assets.md` 负责记录 HK `5m` 分钟线、quota 和滑点校准产物。
* `research-template-design.md` 负责模板维护规则。

参数权威说明仍然在：

* `docs/cli.md`
* `docs/config.md`
