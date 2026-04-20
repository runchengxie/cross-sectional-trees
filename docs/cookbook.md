# Cookbook

本文档的核心目标：将常见任务按照通用工作流进行串联，作为实操层面的速查手册。\
本文档的范围限制：仅提供工作流速查，具体的正式研究路线入口请移步 `docs/playbooks/README.md`，底层参数细节请参阅其他相关文档。\
目标读者：已经跑通过一次基础流程，并希望按照具体任务继续推进的开发者或研究员。\
阅读收益：掌握四阶段的标准工作流以及每个阶段的下一步行动指引。\
相关页面：`docs/get-started.md`、`docs/pipeline-overview.md`、`docs/playbooks/README.md`、`docs/cli.md`、`docs/config.md`、`docs/outputs.md`

在开展 HK selected 正式研究之前，请先从 `docs/playbooks/README.md` 进入专项指引。本页更适合作为一套通用的工作流速查方案。

## 研究流程概览

| 实施阶段 | 核心目标 | 关键产出物 |
|------|------|---------|
| 跑通最小流程 | 验证本地环境并理解主流程输出 | `summary.json`、`positions_current.csv` |
| 定义研究单元 | 锁定 market、universe、fundamentals 与 label | 稳定的基线配置（Baseline） |
| 开展正式研究 | 确立基线、执行模型对比与开展调参 | 多组 run 的详细对比结果 |
| 产出与归档 | 提取快照、计算分配及执行数据归档 | 最终持仓文件、实时快照与备份快照 |

## 阶段一：跑通最小流程

请遵循 `docs/get-started.md` 中的指引跑通一次最小化流程。

若准备着手 HK 月频 Starter 路线，可执行以下命令再次运行：

```bash
csml run --config hk
```

在此处的 `hk` 别名指代了以下特性组合：

* 港股通的 `PIT universe` 设定
* 来源于 `provider` 的基本面数据
* 月频 Starter 基础路线

该模板极其适合用于环境验证与启动参考。请勿将其等同于当前 HK selected 月频本地研究的正式推荐入口。

若计划执行季频 `PIT fundamentals` 路线，请先查阅 `docs/playbooks/hk-data-assets.md` 以准备本地 `pipeline_fundamentals.parquet`，随后再运行：

```bash
csml run --config configs/presets/hk_quarterly_pit_hybrid.yml
```

## 阶段二：定义研究单元

研究单元直接决定了整体研究口径，必须优先锁定以下几类核心配置：

* `market`
* `universe`
* `fundamentals`
* `label`
* `backtest`

关键原则：优先锚定研究单元的口径，随后再横向比较不同模型的表现。

关于各项配置的定义请见 `docs/config.md`，概念与理论差异请参阅 `docs/concepts/`。

## 阶段三：正式研究

### 3.1 建立 benchmark 阶梯

首先应当把各级 benchmark 顺序跑通，确立比较基准之后再进行模型对照或参数调优：

```bash
csml run --config configs/experiments/baseline/hk_selected__quarterly_price_only.yml
csml run --config configs/experiments/baseline/hk_selected__quarterly_pit_core.yml
csml run --config configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml

csml summarize --runs-dir artifacts/runs --sort-by score
csml summarize --runs-dir artifacts/runs --comparability-class direct --sort-by dsr
```

这三条配置固定了同一个季度的研究单元。它们用于解答“alpha 收益究竟来自 price-only、core PIT 还是 hybrid 增量”这一核心问题。完整的基准分层结构请见 `docs/concepts/benchmark-protocol.md`。

### 3.2 开展模型对比

要求仅在同一个研究单元内部更换模型。官方提供的挑战者（challenger）入口如下：

* `configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_ridge.yml`
* `configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_xgb_ranker.yml`
* `configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_elasticnet.yml`

关于模型选择的建议请见 `docs/concepts/model-selection.md`，完整的 benchmark 协议请见 `docs/concepts/benchmark-protocol.md`。

### 3.3 深入 HK selected 研究

关于 HK selected 的路线选择、PIT 资产准备工作以及模板沉淀规则，均收录于 `docs/playbooks/` 目录下：

* 路线选择指引：`docs/playbooks/hk-selected.md`
* 资产准备指南：`docs/playbooks/hk-data-assets.md`
* 模板维护规范：`docs/playbooks/research-template-design.md`

倘若本地的 HK assets 已经就绪，当前首推的月频研究入口为：

```bash
csml run --config configs/experiments/variants/hk_selected__tr_close_execution_balanced_local.yml
```

该路线一次性打通了 `tr_close`、balanced execution 以及本地资产读取链路。  
`configs/experiments/baseline/hk_selected.yml` 依然作为历史 benchmark 锚点与低依赖对照项保留。请避免直接拿它充当当下的默认研究入口。

### 3.4 线性模型搜索

利用以下命令执行批量线性搜索：

```bash
csml sweep-linear --sweep-config configs/experiments/sweeps/hk_selected__linear_a.yml
```

## 阶段四：产出与归档

### 4.1 生成 live 实盘快照

能够真正触发 pipeline 运行的 `snapshot --config ...` 命令，仅接受开启了 `live.enabled=true` 的 live 配置。若目的仅仅是从已经完成的 run 中导出结果，请优先使用 `--run-dir` 或 `--skip-run` 参数。

```bash
csml snapshot --config path/to/live.yml
csml snapshot --config path/to/live.yml --skip-run
csml snapshot --run-dir artifacts/runs/<run_dir>
```

### 4.2 执行手数分配

```bash
csml alloc --config path/to/live.yml --source live --top-n 20 --cash 1000000
```

### 4.3 归档研究数据

```bash
csml backup-data --name hk_frozen_20251231 --config configs/experiments/variants/hk_selected__xgb_regressor.yml
csml backup-data --preset hk_current --name hk_current_frozen_20260410 --no-cache
```

## 常见任务速查表

| 执行任务 | 对应命令 |
|------|------|
| 运行主流程 | `csml run --config <template>` |
| 汇总运行结果 | `csml summarize --runs-dir artifacts/runs --sort-by score` |
| 敏感性分析 | `csml grid --config <template> --top-k 10,20 --cost-bps 15,25` |
| 线性模型批量搜索 | `csml sweep-linear --sweep-config <sweep.yml>` |
| 查看策略持仓 | `csml holdings --config <template> --as-of t-1` |
| 生成实盘快照 | `csml snapshot --config <live.yml>` 或 `csml snapshot --run-dir <run_dir>` |
| 计算手数分配 | `csml alloc --config <live.yml> --source live --top-n 20 --cash 1000000` |
| 归档备份数据 | `csml backup-data --name <name> --config <config>` |
| 冻结当前 HK 资产快照 | `csml backup-data --preset hk_current --name <name>` |

## 相关参考文档

* CLI 操作命令：`docs/cli.md`
* 配置参数字典：`docs/config.md`
* 专业概念指南：`docs/concepts/`
* HK selected 研究指引：`docs/playbooks/hk-selected.md`