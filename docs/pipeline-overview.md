# Pipeline Overview

本页解决什么：给出从 `config` 到 `artifacts` 的系统心智模型。
本页不解决什么：不展开每个 CLI 参数、字段定义或研究路线细节。
适合谁：已经知道项目能做什么，但还没形成完整系统地图的人。
读完你会得到什么：主流程对象、数据流和文档分工的总览。
相关页面：`docs/capabilities.md`、`docs/cli.md`、`docs/config.md`、`docs/outputs.md`、`docs/playbooks/README.md`

## 一句话地图

`config` 定义研究口径；pipeline 按这个口径读取 `data/universe/fundamentals`，构建 `label/features`，训练 `model`，再产出 `eval/backtest/live` 结果，最后把所有关键产物写到 `artifacts/`。

## 主链路

| 阶段 | 关键输入 | 主要动作 | 关键输出 |
| --- | --- | --- | --- |
| 配置解析 | `--config` / `extends` | 合并模板、解析默认值、固化研究口径 | `config.used.yml` |
| 数据与股票池 | `data`、`universe` | 拉取或读取日线、构造样本日期和成员范围 | 面板底表、股票池切片 |
| 基本面并入 | `fundamentals` | provider 读取或本地 `pipeline_fundamentals.parquet` 并入 | 带基本面的研究面板 |
| 标签与特征 | `label`、`features` | 生成未来收益标签、构造量价和财务特征 | 训练 / 评估用特征矩阵 |
| 模型训练 | `model` | 拟合 `xgb_regressor` / `xgb_ranker` / `ridge` / `elasticnet` | 预测分数、特征重要度 |
| 评估与回测 | `eval`、`backtest` | IC、Top-K、walk-forward、回测和 benchmark 对比 | `summary.json`、评估 CSV、持仓文件 |
| live 导出 | `live` | 基于最新 run 读取目标持仓、快照和分配 | `positions_current*.csv`、snapshot / alloc 输出 |

## 哪些配置块决定什么

* `data`：数据源、时间范围、缓存隔离和 provider 细节。
* `universe`：哪些股票、哪些日期能进入研究样本。
* `fundamentals`：是否并入基本面，以及来自 provider 还是本地平面文件。
* `label`：预测目标、调仓频率和位移方式。
* `features`：模型看到什么字段，以及怎么处理缺失。
* `model`：模型类型、训练窗和参数。
* `eval`：怎么评价模型分数。
* `backtest`：怎么把分数转成组合。
* `live`：怎么从研究结果导出 live 持仓、snapshot 和 alloc。

## 三个最容易混淆的边界

### 1. `universe` 和 `fundamentals` 不是一回事

* `universe.by_date_file` 决定某只股票在哪些日期能参与研究。
* `fundamentals.source=file` 决定 pipeline 是否从本地 `pipeline_fundamentals.parquet` 读取 PIT 财务字段。

### 2. `hk.yml` 不等于“完整 PIT 财务路线”

* `configs/presets/hk.yml` 是 HK 月频 starter：`PIT universe` + `provider` 基本面。
* `configs/presets/hk_quarterly_pit_hybrid.yml` 才是 HK 季频 `PIT fundamentals` 入口。

### 3. `summary.json` 和 `config.used.yml` 才是 run 的权威快照

文档、模板和 playbook 讲的是当前推荐口径；真正复现某个历史 run 时，先看该 run 目录里的：

* `config.used.yml`
* `summary.json`
* `positions_current.csv` / `positions_current_live.csv`

## 目录怎么对应这张地图

* `docs/cli.md`：命令入口和参数。
* `docs/config.md`：配置键、模板入口和默认行为。
* `docs/providers.md`：provider 差异、凭证和日期 token。
* `docs/outputs.md`：`artifacts/` 里的目录、文件和字段。
* `docs/playbooks/README.md`：正式研究路线。
* `docs/cookbook.md`：通用工作流速查。

## 下一步怎么读

* 想先跑通一次：`docs/get-started.md`
* 想做正式研究：`docs/playbooks/README.md`
* 想按对象查细节：`docs/config.md`、`docs/outputs.md`、`docs/providers.md`
