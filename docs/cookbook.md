# Cookbook

本页解决什么：把常见任务按通用工作流串起来，作为速查页使用。
本页不解决什么：不替代 `docs/playbooks/README.md` 的正式研究路线入口，也不展开参数细节。
适合谁：已经跑通一次流程、想按任务推进的人。
读完你会得到什么：四阶段工作流和每阶段的下一步指引。
相关页面：`docs/get-started.md`、`docs/pipeline-overview.md`、`docs/playbooks/README.md`、`docs/cli.md`、`docs/config.md`、`docs/outputs.md`

如果你要做 HK selected 正式研究，先从 `docs/playbooks/README.md` 进入；本页更适合作为通用工作流速查。

## 研究流程概览

| 阶段 | 目标 | 关键产出 |
|------|------|---------|
| 跑通最小流程 | 验证环境 + 理解主流程产出 | `summary.json`、`positions_current.csv` |
| 定义研究单元 | 锁定 market/universe/fundamentals/label | 稳定的基线配置 |
| 正式研究 | 基线 → 模型对比 → 调参 | 多组 run 的对比结果 |
| 产出与归档 | 快照、分配、归档 | 持仓文件、快照、备份 |

## 阶段一：跑通最小流程

按 `docs/get-started.md` 跑通一次最小流程。

如果你准备做 HK 月频 starter 路线，可以再跑一次：

```bash
csml run --config hk
```

这里的 `hk` 指的是：

* 港股通 `PIT universe`
* `provider` 基本面
* 月频 starter 路线

它适合环境验证和 starter 路线，不等于当前 HK selected 月频本地研究的推荐入口。

如果你准备做季频 `PIT fundamentals` 路线，先看 `docs/playbooks/hk-data-assets.md` 准备本地 `pipeline_fundamentals.parquet`，再跑：

```bash
csml run --config configs/presets/hk_quarterly_pit_hybrid.yml
```

## 阶段二：定义研究单元

研究单元决定了研究口径，至少要锁定这几类配置：

* `market`
* `universe`
* `fundamentals`
* `label`
* `backtest`

关键原则：先定研究单元，再比较模型。

配置定义见 `docs/config.md`，概念差异见 `docs/concepts/`。

## 阶段三：正式研究

### 3.1 先有 benchmark 阶梯

先把 benchmark 顺序跑通，再对照模型或调参：

```bash
csml run --config configs/experiments/baseline/hk_selected__quarterly_price_only.yml
csml run --config configs/experiments/baseline/hk_selected__quarterly_pit_core.yml
csml run --config configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml

csml summarize --runs-dir artifacts/runs --sort-by score
csml summarize --runs-dir artifacts/runs --comparability-class direct --sort-by dsr
```

这三条配置固定了同一季度研究单元，用来回答“alpha 到底来自 price-only、core PIT，还是 hybrid 增量”。完整分层见 `docs/concepts/benchmark-protocol.md`。

### 3.2 模型对比

只在同一研究单元里换模型。官方 challenger 入口见：

* `configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_ridge.yml`
* `configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_xgb_ranker.yml`
* `configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_elasticnet.yml`

模型选择建议见 `docs/concepts/model-selection.md`，完整 benchmark protocol 见 `docs/concepts/benchmark-protocol.md`。

### 3.3 HK selected 研究

HK selected 的路线选择、PIT 资产准备和模板沉淀规则在 `docs/playbooks/`：

* 路线选择：`docs/playbooks/hk-selected.md`
* 资产准备：`docs/playbooks/hk-data-assets.md`
* 模板维护：`docs/playbooks/research-template-design.md`

如果你本地 HK assets 已经就绪，当前更推荐的月频研究入口是：

```bash
csml run --config configs/experiments/variants/hk_selected__tr_close_execution_balanced_local.yml
```

这条线把 `tr_close`、balanced execution 和本地资产链路一次接好。  
`configs/experiments/baseline/hk_selected.yml` 仍然保留为历史 benchmark 锚点和低依赖对照，不建议直接拿它充当当前默认研究入口。

### 3.4 线性模型搜索

```bash
csml sweep-linear --sweep-config configs/experiments/sweeps/hk_selected__linear_a.yml
```

## 阶段四：产出与归档

### 4.1 生成 live 快照

真正触发 pipeline 的 `snapshot --config ...` 只接受 `live.enabled=true` 的 live 配置；如果你只是想从已有 run 导出结果，优先用 `--run-dir` 或 `--skip-run`。

```bash
csml snapshot --config path/to/live.yml
csml snapshot --config path/to/live.yml --skip-run
csml snapshot --run-dir artifacts/runs/<run_dir>
```

### 4.2 手数分配

```bash
csml alloc --config path/to/live.yml --source live --top-n 20 --cash 1000000
```

### 4.3 归档研究

```bash
csml backup-data --name hk_frozen_20251231 --config configs/experiments/variants/hk_selected__xgb_regressor.yml
csml backup-data --preset hk_current --name hk_current_frozen_20260410 --no-cache
```

## 常见任务速查

| 任务 | 命令 |
|------|------|
| 跑主流程 | `csml run --config <template>` |
| 汇总结果 | `csml summarize --runs-dir artifacts/runs --sort-by score` |
| 敏感性分析 | `csml grid --config <template> --top-k 10,20 --cost-bps 15,25` |
| 线性模型搜索 | `csml sweep-linear --sweep-config <sweep.yml>` |
| 查看持仓 | `csml holdings --config <template> --as-of t-1` |
| 生成快照 | `csml snapshot --config <live.yml>` 或 `csml snapshot --run-dir <run_dir>` |
| 手数分配 | `csml alloc --config <live.yml> --source live --top-n 20 --cash 1000000` |
| 归档数据 | `csml backup-data --name <name> --config <config>` |
| 冻结当前 HK 资产 | `csml backup-data --preset hk_current --name <name>` |

## 相关文档

* CLI 命令：`docs/cli.md`
* 配置键：`docs/config.md`
* 概念指南：`docs/concepts/`
* HK selected 研究：`docs/playbooks/hk-selected.md`
