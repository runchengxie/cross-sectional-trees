# 文档首页

这套文档按四层组织：

1. 入口：`README.md` 和本页。
2. 参考：命令、配置、输出、provider、指标、排障、开发。
3. 配方：把常见研究流程串起来。
4. 内部资料：规划、范围和预算，不作为主用户手册。

如果你是第一次进入仓库，先看根目录 `README.md`。

当前文档路线默认按港股优先组织：

* 先用 `default` 跑通。
* 需要正式 PIT 港股研究时，再切到 `hk` 或 `config/hk.yml`。
* `cn/us` 仍保留，但主要用于兼容已有配置和多市场对照。

## 推荐阅读顺序

1. `README.md`：项目定位、快速开始、常用入口。
2. `docs/capabilities.md`：项目能做什么、不能做什么、主要输出是什么。
3. `docs/cookbook.md`：常见任务的最短流程和配方入口。
4. `docs/config.md`：改配置前先看这里。
5. `docs/outputs.md`：看 run 目录、`summary.json` 和持仓文件。
6. `docs/troubleshooting.md`：排查常见错误和结果偏差。

## 按任务找文档

### 先跑通一次

* `README.md`
* `docs/cookbook.md`
* 默认从 `default` 开始。

### 想知道项目能做什么

* `docs/capabilities.md`
* `docs/outputs.md`

### 想查命令参数

* `docs/cli.md`

### 想改配置

* `docs/config.md`
* `docs/providers.md`

### 想看结果

* `docs/metrics.md`
* `docs/outputs.md`

### 想做特定研究流程

* `docs/cookbook.md`
* `docs/playbooks/README.md`

补充：

* 如果你在做季度 PIT 财报研究，先读 `docs/cookbook.md` 里的 HK selected 流程，再去 `docs/playbooks/hk-selected.md` 看路线细节。
* 这条流程现在会先做 PIT 覆盖率体检，把 `Fill Dependence` 调到可接受状态，再做基线和模型比较。

### 想做 HK selected 研究

* `docs/playbooks/README.md`

补充：

* `docs/playbooks/README.md` 会先告诉你该读哪一页。
* 如果你要跑季度或年度 PIT 财报路线，最后会落到 `docs/playbooks/hk-data-assets.md` 准备本地 `pipeline_fundamentals.parquet`。

### 想排错

* `docs/troubleshooting.md`

### 想开发和测试

* `docs/dev.md`

### 想看内部规划或研究笔记

* `docs/internal/feature-planning.md`
* `docs/research/README.md`

## 文档分工

* `README.md`：项目总览和最短路径。
* `docs/capabilities.md`：能力边界、主要入口和产物概览。
* `docs/cli.md`：CLI 参数的权威说明。
* `docs/config.md`：配置键、模板和默认行为的权威说明。
* `docs/outputs.md`：输出文件和字段约定。
* `docs/cookbook.md`：常见任务流程。
* `docs/playbooks/`：场景化研究配方。
* `docs/troubleshooting.md`：常见问题和一次性迁移命令。
* `docs/internal/`：内部规划资料。
* `docs/research/`：研究笔记和论文精读。
