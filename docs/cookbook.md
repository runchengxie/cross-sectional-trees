# Cookbook

这个文档把常见任务串成流程。

如果你只是想知道某个命令的参数，去 `docs/cli.md`。如果你想查配置键的定义，去 `docs/config.md`。

---

## 研究流程概览

整个研究流程可以分成四个阶段：

| 阶段 | 目标 | 关键产出 |
|------|------|---------|
| 跑通最小流程 | 验证环境 + 理解主流程产出 | `summary.json`、`positions_current.csv` |
| 理解研究单元 | 决定 market/universe/fundamentals/label | 选好的配置模板 |
| 正式研究 | 基线 → 模型对比 → 调参 | 多组 run 的对比结果 |
| 产出与归档 | 快照、分配、归档 | 持仓文件、快照、备份 |

---

## 阶段一：跑通最小流程

### 1.1 准备环境

```bash
uv venv --seed
uv sync --extra dev --extra rqdata  # 如需 RQData
```

准备鉴权：

- `tushare`：`TUSHARE_TOKEN`
- `rqdata`：`RQDATA_USERNAME` + `RQDATA_PASSWORD`
- `eodhd`：`EODHD_API_TOKEN`

### 1.2 跑一次 default

```bash
csml run --config default
```

跑完后看这三个文件：

1. `summary.json` - 核心指标
2. `config.used.yml` - 实际生效的配置
3. `positions_current.csv` - 当前持仓

### 1.3 切换到 hk（如需 PIT）

```bash
csml run --config hk
```

---

## 阶段二：理解研究单元

研究单元决定了你的研究口径，包括：

- `market`：市场（cn/hk/us）
- `universe`：股票池（static/pit/auto）
- `fundamentals`：基本面数据源
- `label`：预测目标与频率
- `backtest`：回测参数

详见 `docs/config.md` 和 `docs/concepts/`。

> **关键原则**：先定研究单元，再比较模型。研究单元不变，只换模型。

---

## 阶段三：正式研究

### 3.1 月度 Provider 基线

适合快速验证和不需要 PIT 财务数据的场景：

```bash
csml run --config default
```

### 3.2 季度 PIT 财报研究

需要先准备 PIT 资产：

1. 镜像港股通 PIT 股票池：`csml universe hk-connect --config configs/presets/universe/hk_connect.yml --mode daily`
2. 拉取 PIT 财报数据：`csml rqdata mirror-hk-pit-financials ...`
3. 构建 pipeline 可读的基本面文件：`csml rqdata build-hk-pit-fundamentals ...`
4. 验证覆盖率：`csml rqdata inspect-hk-pit-coverage ...`

详见 `docs/playbooks/hk-selected.md` 和 `docs/concepts/pit-coverage.md`。

### 3.3 基线 → 模型对比

**先跑基线，再比较模型**：

```bash
# 三条基线
csml run --config configs/local/hk_sel_q_price_only_xgb_reg.yml
csml run --config configs/local/hk_sel_pit_q_core_xgb_reg.yml
csml run --config configs/local/hk_sel_pit_q_core_hybrid_xgb_reg.yml

# 汇总
csml summarize \
  --runs-dir artifacts/runs \
  --run-name-prefix hk_sel_q_baseline \
  --sort-by score
```

**再跑四模型 PK**（只有基线稳定后才做）：

```bash
csml run --config configs/local/hk_sel_q_pk_pit_core_hybrid_xgb_reg.yml
csml run --config configs/local/hk_sel_q_pk_pit_core_hybrid_xgb_rank.yml
csml run --config configs/local/hk_sel_q_pk_pit_core_hybrid_ridge.yml
csml run --config configs/local/hk_sel_q_pk_pit_core_hybrid_en.yml
```

### 3.4 线性模型搜索

```bash
csml sweep-linear --sweep-config configs/experiments/sweeps/hk_selected__linear_a.yml
```

---

## 阶段四：产出与归档

### 4.1 生成 live 快照

```bash
csml snapshot --config configs/local/hk_live.local.yml
```

### 4.2 手数分配

```bash
csml alloc --config configs/local/hk_live.local.yml --source live --top-n 20 --cash 1000000
```

### 4.3 归档研究

```bash
csml backup-data --name hk_frozen_20251231 --config configs/experiments/variants/hk_selected__xgb_regressor.yml
```

---

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

---

## 相关文档

- CLI 命令：`docs/cli.md`
- 配置键：`docs/config.md`
- 概念指南：`docs/concepts/`
- HK selected 研究：`docs/playbooks/hk-selected.md`
