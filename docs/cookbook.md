# Cookbook

本页解决什么：把常见研究任务按顺序串起来。
本页不解决什么：不展开参数细节或替代 playbooks 的场景路线。
适合谁：已经跑通一次流程、想按任务推进的人。
读完你会得到什么：四阶段流程和每阶段的下一步指引。
相关页面：`docs/get-started.md`、`docs/playbooks/README.md`、`docs/cli.md`、`docs/config.md`、`docs/outputs.md`

## 研究流程概览

| 阶段 | 目标 | 关键产出 |
|------|------|---------|
| 跑通最小流程 | 验证环境 + 理解主流程产出 | `summary.json`、`positions_current.csv` |
| 定义研究单元 | 锁定 market/universe/fundamentals/label | 稳定的基线配置 |
| 正式研究 | 基线 → 模型对比 → 调参 | 多组 run 的对比结果 |
| 产出与归档 | 快照、分配、归档 | 持仓文件、快照、备份 |

## 阶段一：跑通最小流程

按 `docs/get-started.md` 跑通一次最小流程。

如果你准备做 PIT 港股研究，跑完最小流程后再跑一次：

```bash
csml run --config hk
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

### 3.4 线性模型搜索

```bash
csml sweep-linear --sweep-config configs/experiments/sweeps/hk_selected__linear_a.yml
```

## 阶段四：产出与归档

### 4.1 生成 live 快照

```bash
csml snapshot --config path/to/live.yml
```

### 4.2 手数分配

```bash
csml alloc --config path/to/live.yml --source live --top-n 20 --cash 1000000
```

### 4.3 归档研究

```bash
csml backup-data --name hk_frozen_20251231 --config configs/experiments/variants/hk_selected__xgb_regressor.yml
```

## 常见任务速查

| 任务 | 命令 |
|------|------|
| 跑主流程 | `csml run --config <template>` |
| 汇总结果 | `csml summarize --runs-dir artifacts/runs --sort-by score` |
| 敏感性分析 | `csml grid --config <template> --top-k 10,20 --cost-bps 15,25` |
| 线性模型搜索 | `csml sweep-linear --sweep-config <sweep.yml>` |
| 查看持仓 | `csml holdings --config <template> --as-of t-1` |
| 生成快照 | `csml snapshot --config <live.yml>` |
| 手数分配 | `csml alloc --config <live.yml> --source live --top-n 20 --cash 1000000` |
| 归档数据 | `csml backup-data --name <name> --config <config>` |

## 相关文档

* CLI 命令：`docs/cli.md`
* 配置键：`docs/config.md`
* 概念指南：`docs/concepts/`
* HK selected 研究：`docs/playbooks/hk-selected.md`
