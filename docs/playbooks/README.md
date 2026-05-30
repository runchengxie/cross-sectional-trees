# 研究配方首页

本页解决什么：给正式研究流程类页面提供统一入口和阅读顺序。\
本页不解决什么：不展开参数细节与概念定义。\
适合谁：已经明确要做研究路线选择的人。\
读完你会得到什么：A 股 baseline 迁移入口、港股 legacy research lane 的阅读顺序与分工。\
相关页面：`docs/market-lifecycle.md`、`docs/pipeline-overview.md`、`docs/cookbook.md`、`docs/cli.md`、`docs/config.md`、`docs/concepts/`

`docs/playbooks/` 这一组文档只处理研究流程。

如果你现在的问题是“A 股主线迁移从哪里开始”，先看 `docs/playbooks/a-share-baseline.md`。\
如果你现在的问题是“如何复现或对照 HK selected 历史路线”，再看 `docs/playbooks/hk-selected.md`。\
如果你现在的问题是“HK / RQData 数据资产该在哪里维护”，答案是 `market-data-platform`；本仓库只消费它的产物。\
只想按通用任务顺序推进时，回到 `docs/cookbook.md` 更合适。

## 新手阅读顺序

建议按下面的顺序读：

1. 如果目标是 A 股主线迁移验证，先看 `docs/playbooks/a-share-baseline.md`，用 `cstree run --config default_next` 跑 price-only / daily_clean baseline。
2. 如果目标是复现、对照或继续跟踪港股 legacy research，再看 `docs/playbooks/hk-selected.md`，先选频率和数据路线。
3. 如果港股路线选的是 PIT 财务路线，先确认 `market-data-platform` 已经产出可用的 PIT flat file，再看 `docs/playbooks/hk-data-assets.md` 配置研究侧消费路径。
4. 如果你已经拿到了 HK 分钟线，想继续看滑点校准，再看 `docs/playbooks/hk-intraday-assets.md`。
5. 如果你已经准备做正式对比，再看 `docs/concepts/benchmark-protocol.md` 确认 benchmark 阶梯；A 股 benchmark 不能直接沿用港股 benchmark 语义。
6. 如果你要派生本地配置，或判断某个实验值不值得沉淀成仓库模板，再看 `docs/playbooks/research-template-design.md`。

补充：

* 港股季度 PIT 路线现在建议先在 `market-data-platform` 做覆盖率体检，把 `Fill Dependence` 调到可接受状态，再做基线和四模型比较。
* A 股 default 晋升条件、港股冻结维护和 sunset 条件，以 `docs/market-lifecycle.md` 为准。

## 每一页解决什么问题

| 页面 | 解决的问题 | 什么时候打开 |
| --- | --- | --- |
| `a-share-baseline.md` | A 股 default 迁移候选怎么跑、哪些能力尚未等价落地 | 想验证 `default_next`、`a_share.yml`、daily_clean baseline 或 default 晋升条件 |
| `hk-selected.md` | 港股 legacy research lane 里先跑哪条 HK selected 研究路线 | 想复现或对照 `M/Q/Y`、量价、PIT 财务、四模型 PK 入口 |
| `hk-data-assets.md` | 研究侧如何消费外部 HK 数据资产 | 已有 `pipeline_fundamentals.parquet`、daily asset 或 standardized layer |
| `hk-rqdata-status.md` | 旧 HK RQData 状态页 sunset 说明 | 遇到旧链接时确认边界 |
| `hk-intraday-assets.md` | HK `5m` 数据资产 sunset 边界和滑点研究入口 | 已有分钟线文件，想拿来校准执行假设 |
| `research-template-design.md` | 什么时候派生配置，什么时候新建模板 | 想把实验沉淀成模板，或担心 `configs/` 越长越乱 |

## 常见起点

### 我想验证 A 股迁移候选

先看：

1. `docs/playbooks/a-share-baseline.md`
2. 确认数据平台已发布 `metadata/current_assets/a_share_current.json`
3. 跑 `cstree run --config default_next`
4. 对照 `docs/market-lifecycle.md` 的 A 股 default 晋升条件补证据

### 我第一次复现或对照 HK selected

先看：

1. `docs/playbooks/hk-selected.md`
   如果本地 HK assets 已就绪，而且有复现、对照或明确跟踪需求，可从 `configs/experiments/variants/hk_selected__tr_close_execution_balanced_local.yml` 开始；这条入口默认使用 universe-aligned cap-weight benchmark 文件。
2. 如果走 PIT 财务路线，先在 `market-data-platform` 准备 flat file，再看 `docs/playbooks/hk-data-assets.md`
3. 如果已经落了 HK `5m`，再看 `docs/playbooks/hk-intraday-assets.md`
4. 数据准备完成后，先确认 PIT 覆盖率体检已在数据平台通过，再决定基线和模型比较顺序

### 我已经知道要跑哪条路线，但不知道该不该新建模板

直接看：

* `docs/playbooks/research-template-design.md`

### 我想做季度或年度低频财报研究

如果是 A 股，请先回到 `docs/playbooks/a-share-baseline.md` 的 checklist，确认 PIT universe、PIT fundamentals 和行业历史是否具备。

如果是港股 legacy research，建议顺序：

1. `docs/playbooks/hk-selected.md`
2. `docs/playbooks/hk-data-assets.md`
3. 先在数据平台跑 PIT 覆盖率体检
4. `docs/playbooks/research-template-design.md`

## 这组文档怎么分工

这里的分工保持简单：

* `a-share-baseline.md` 负责 A 股迁移候选、baseline 验证和 default 晋升 checklist。
* `hk-selected.md` 负责港股 legacy research lane 的路线选择和比较顺序。
* `hk-data-assets.md` 负责研究侧港股数据消费边界。
* `hk-rqdata-status.md` 保留旧状态页 sunset 说明。
* `hk-intraday-assets.md` 负责 HK `5m` 数据资产 sunset 边界和滑点研究入口。
* `research-template-design.md` 负责模板维护规则。

参数权威说明仍然在：

* `docs/cli.md`
* `docs/config.md`
