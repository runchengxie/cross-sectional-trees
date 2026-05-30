# 系统流程总览

本页说明 `cstree run` 主流程如何从配置走到产物，并补充主流程之外的公开能力。\
本页不展开每个 CLI 参数、字段定义或具体研究路线。\
适合谁：已经知道项目大概能做什么，但还没形成完整系统地图的人。\
读完你会得到什么：主流程对象、数据流、外围工具分工和下一步阅读路径。\
相关页面：`docs/capabilities.md`、`docs/cli.md`、`docs/config.md`、`docs/outputs.md`、`docs/playbooks/README.md`

## 一句话地图

`config` 定义研究口径。`cstree run` 按这个口径读取 `data/universe/fundamentals`，构建 `label/features`，训练 `model`，产出 `eval/backtest/live` 结果，最后把关键产物写到 `artifacts/`。

这页讲的是主流程。项目还包含结果汇总、候选晋升检查、构造层网格、特征证据、benchmark 阶梯、股票池工具、数据标准层和运行结果发布打包工具；这些能力见本页后面的“主流程之外”。当前最成熟的数据路线是中国香港市场 / RQData / 本地平台资产，相关资产生产、检查和发布已经由 `market-data-platform` 承载。

## 主流程

| 阶段 | 关键输入 | 主要动作 | 关键输出 |
| --- | --- | --- | --- |
| 配置解析 | `--config` / `extends` | 合并模板、解析默认值、固化研究口径 | `config.used.yml` |
| 数据与股票池 | `data`、`universe` | 拉取或读取日线，构造样本日期和成员范围 | 面板底表、股票池切片 |
| 基本面并入 | `fundamentals` | 读取 provider 数据或本地 `pipeline_fundamentals.parquet` | 带基本面的研究面板 |
| 标签与特征 | `label`、`features` | 生成未来收益标签，构造量价和财务特征 | 训练 / 评估用特征矩阵 |
| 模型训练 | `model` | 拟合 `xgb_regressor` / `xgb_ranker` / `ridge` / `elasticnet` | 预测分数、特征重要度 |
| 评估与回测 | `eval`、`backtest` | 计算 IC、分位收益、Top-K、walk-forward、回测和 benchmark 对比 | `summary.json`、评估 CSV、持仓文件 |
| live 导出 | `live` | 从最新 run 读取目标持仓、快照、分配结果和显式执行目标交接文件 | `positions_current*.csv`、snapshot / alloc 输出、标准 `targets.json` |

## 配置块分工

* `data`：数据源、时间范围、缓存隔离和 provider 细节。
* `universe`：哪些股票、哪些日期能进入研究样本。
* `fundamentals`：是否并入基本面，以及来自 provider 还是本地平面文件。
* `label`：预测目标、调仓频率和位移方式。
* `features`：模型看到哪些字段，以及怎么处理缺失。
* `model`：模型类型、训练窗和参数。
* `eval`：怎么评价模型分数。
* `backtest`：怎么把分数转成组合。
* `live`：怎么从研究结果导出 live 持仓、snapshot 和 alloc。

## 容易混淆的边界

### 1. `research_universe` 和 `fundamentals`

* `research_universe.by_date_file` 决定某只股票在哪些日期能参与研究。
* `fundamentals.source=file` 决定 pipeline 是否从本地 `pipeline_fundamentals.parquet` 读取 PIT 财务字段。

股票池控制“谁能进样本”，基本面文件控制“有哪些财务字段可用”。两者需要对齐，但不是同一个开关。

### 2. `hk.yml` 和完整 PIT 财务路线

* `configs/presets/hk.yml` 是当前成熟路线的月频 starter：`PIT universe` + `provider` 基本面。
* `configs/presets/hk_quarterly_pit_hybrid.yml` 是当前成熟路线的季频 `PIT fundamentals` 入口。

要跑季度 PIT 财务路线时，应从后者或 HK selected playbook 指向的实验配置开始。其他市场路线应复用同样的配置块边界，而不是把 HK 专项假设扩散到通用主流程。

### 3. run 产物才是历史复现依据

文档、模板和 playbook 说明当前推荐口径。复现某个历史 run 时，先看该 run 目录里的：

* `config.used.yml`
* `summary.json`
* `positions_current.csv` / `positions_current_live.csv`

### 4. 本地资产直读和在线 provider

本地平台资产直读可以跳过在线日线和基础信息读取。当前已验证的是中国香港市场资产直读；若同一配置启用了 `fundamentals.source=provider` 或 `fundamentals.provider_overlay`，基本面缓存未命中时仍可能 lazy init `rqdatac`。

## 主流程之外

| 能力组 | 入口 | 什么时候用 |
| --- | --- | --- |
| 结果汇总 | `cstree summarize` | 汇总多次 run，比较 IC、回测和稳定性指标 |
| 参数与构造搜索 | `cstree grid`、`cstree tune`、`cstree sweep-linear` | 比较 Top-K / 成本 / buffer、超参搜索、线性模型批跑 |
| 研究治理 | `cstree promotion-gate` | 判断 candidate 是否具备升主线证据 |
| 固定分数组合层比较 | `cstree construction-grid` | 固定模型分数，只比较组合构造参数 |
| 特征证据 | `cstree feature-evidence ...` | 生成消融配置、汇总消融结果、计算特征置换重要度和单因子 IC |
| Benchmark 阶梯 | `cstree benchmark-ladder` | 把策略收益和多组 benchmark 分层对比 |
| 持仓与分配 | `cstree holdings`、`cstree snapshot`、`cstree alloc`、`cstree alloc-hk` | 查看当前持仓、导出快照、做资金和手数分配 |
| 执行目标交接 | `cstree export-targets` | 将已经保存并通过质量门禁的 long-only live 持仓显式导出为执行引擎 `targets.json`；不会触发下单 |
| 数据标准层 | `marketdata data catalog/materialize/query` | 管理 metadata、物化 standardized layer、用 DuckDB 查询 |
| 股票池MDP 入口 | `marketdata rqdata hk-assets ...` | 改用 `market-data-platform` 的 HK universe asset builder |
| 运行结果发布打包 | `python -m cstree.release_tools.*` | 跨机器共享运行结果 |

命令参数以 `docs/cli.md` 为准。能力边界和稳定性分层见 `docs/capabilities.md`。

## 目录怎么对应这张地图

* `docs/capabilities.md`：项目能力、入口层级和边界。
* `docs/cli.md`：命令入口和参数。
* `docs/config.md`：配置键、模板入口和默认行为。
* `docs/providers.md`：provider 差异、凭证和日期 token。
* `docs/outputs.md`：`artifacts/` 里的目录、文件和字段。
* `docs/playbooks/README.md`：正式研究路线。
* `docs/cookbook.md`：通用工作流速查。
* `docs/research/README.md`：研究笔记入口和状态说明。

## 下一步怎么读

* 想先跑通一次：`docs/get-started.md`
* 想确认项目能力边界：`docs/capabilities.md`
* 想查命令参数：`docs/cli.md`
* 想做正式研究：`docs/playbooks/README.md`
* 想按对象查细节：`docs/config.md`、`docs/outputs.md`、`docs/providers.md`
