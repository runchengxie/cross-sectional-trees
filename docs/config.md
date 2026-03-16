# 配置参考

本页解决什么：配置键与默认行为的速查表。
本页不解决什么：不展开研究路线与概念选择。
适合谁：需要查配置定义与模板的人。
读完你会得到什么：配置键的权威定义与常用模板入口。
相关页面：`docs/concepts/model-selection.md`、`docs/concepts/pit-coverage.md`、`docs/concepts/universe-modes.md`、`docs/concepts/data-sources.md`

## 常用模板速查

| 场景 | 推荐模板 | 关键改动 |
|------|---------|---------|
| 第一次跑通 | `default` | 无 |
| 港股 PIT 正式研究 | `hk` | 可能需要 PIT 资产 |
| 季度 benchmark protocol | `configs/experiments/baseline/hk_selected__quarterly_*.yml` + `configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_*.yml` | 需要本地 `pipeline_fundamentals.parquet` |
| 更宽的季度实验路线 | `configs/experiments/variants/hk_selected__pit_quarterly_*` | 适合继续派生专题路线 |
| 本地实验 | `configs/local/*.yml` 或自建实验目录 | 仅作个人派生，不当作官方入口 |

> **注意**：`csml run --config default` 里的 `default` 是内置别名，不等于仓库里的 `configs/presets/default.yml`。

---

## 配置目录结构

```
configs/
├── presets/           # 内置预设（market 默认配置）
│   ├── default.yml
│   ├── hk.yml
│   ├── cn.yml
│   ├── us.yml
│   └── universe/      # 股票池配置
├── experiments/       # 研究实验配置
│   ├── baseline/      # 基线配置
│   ├── variants/      # 模型变体配置
│   └── sweeps/        # 批量实验配置
└── local/             # 本地覆盖/历史实验快照目录（避免新增官方模板）
```

## 顶层配置块

| 块 | 作用 | 常见键 |
|----|------|--------|
| `market` | 市场 | `cn` / `hk` / `us` |
| `data` | 数据源、日期、缓存 | `provider`, `start_date`, `end_date`, `cache_tag` |
| `universe` | 股票池 | `mode`, `by_date_file`, `symbols` |
| `fundamentals` | 基本面 | `enabled`, `source`, `features` |
| `label` | 标签 | `target_col`, `horizon_days`, `rebalance_frequency`, `shift_days` |
| `features` | 特征 | `list`, `windows`, `missing` |
| `model` | 模型 | `type`, `params` |
| `eval` | 评估 | `top_k`, `transaction_cost_bps`, `save_artifacts` |
| `backtest` | 回测 | `enabled`, `rebalance_frequency`, `top_k`, `weighting` |
| `live` | 快照 | `enabled`, `as_of` |

## 关键配置速查

### 数据源

```yaml
data:
  provider: rqdata        # tushare / rqdata / eodhd
  market: hk             # cn / hk / us
  start_date: "20200101" # 或 "today", "t-1"
  end_date: "20241231"
  cache_tag: "experiment_a"  # 隔离实验版本
```

### `data.rqdata`（离线资产对齐）

如果你已经准备好本地日线镜像与 instrument 快照，可以让 pipeline 直接读资产目录，避免重复从 provider 拉取：

```yaml
data:
  rqdata:
    daily_asset_dir: "artifacts/assets/rqdata/hk/daily/<snapshot>"
    instruments_file: "artifacts/assets/rqdata/hk/instruments/<snapshot>.parquet"
```

### 股票池

```yaml
universe:
  mode: static           # auto / pit / static
  symbols:               # static 模式用
    - 00700.HK
    - 09988.HK
  # pit 模式用
  # by_date_file: artifacts/assets/universe/hk_connect_by_date.csv
```

### 模型

```yaml
model:
  type: xgb_regressor   # xgb_regressor / xgb_ranker / ridge / elasticnet
  params:
    n_estimators: 100
    max_depth: 5
```

详见 `docs/concepts/model-selection.md`。

### 评估与回测

```yaml
eval:
  top_k: 20
  transaction_cost_bps: 15
  save_artifacts: true

backtest:
  enabled: true
  rebalance_frequency: "M"   # M / Q / Y
  top_k: 20
  weighting: equal           # equal / signal
```

## 高频键快速参考

### `data`

| 键 | 说明 | 常见值 |
|---|------|--------|
| `provider` | 数据源 | `tushare` / `rqdata` / `eodhd` |
| `start_date` | 开始日期 | `20200101` / `today` |
| `end_date` | 结束日期 | `20241231` / `t-1` / `last_trading_day` |
| `cache_tag` | 缓存版本标签 | 任意字符串 |

### `universe`

| 键 | 说明 | 常见值 |
|---|------|--------|
| `mode` | 股票池模式 | `static` / `pit` / `auto` |
| `by_date_file` | PIT 股票池文件 | CSV 路径 |
| `min_symbols_per_date` | 最小样本数 | `5` |

详见 `docs/concepts/universe-modes.md`。

### `label`

| 键 | 说明 | 常见值 |
|---|------|--------|
| `horizon_days` | 预测天数 | `5`, `20`, `60` |
| `rebalance_frequency` | 再平衡频率 | `M` / `Q` / `Y` |
| `shift_days` | 信号位移 | `1`, `0` |

### `eval`

| 键 | 说明 | 常见值 |
|---|------|--------|
| `top_k` | 选股数量 | `10`, `20`, `30` |
| `transaction_cost_bps` | 交易成本(bps) | `15`, `25` |
| `save_artifacts` | 保存产物 | `true` / `false` |
| `purge_days` | 泄漏防护天数 | 默认 `horizon_days + shift_days` |

### `backtest`

| 键 | 说明 | 常见值 |
|---|------|--------|
| `enabled` | 开启回测 | `true` / `false` |
| `weighting` | 权重方式 | `equal` / `signal` |
| `exit_price_policy` | 退出价格策略 | `strict` / `ffill` / `delay` |
| `rebalance_frequency` | 再平衡频率 | `M` / `Q` / `Y` |

### `fundamentals`

| 键 | 说明 | 常见值 |
|---|------|--------|
| `enabled` | 开启基本面 | `true` / `false` |
| `source` | 数据来源 | `provider` / `file` |
| `ffill` | 财报沿用 | `true` / `false` |

### `features.missing`

| 键 | 说明 | 常见值 |
|---|------|--------|
| `method` | 填补方法 | `none` / `zero` / `cross_sectional_median` |
| `add_indicators` | 添加缺失标记 | `true` / `false` |

## 路径迁移（旧仓库升级）

| 旧路径 | 新路径 |
|--------|--------|
| `config/hk.yml` | `configs/presets/hk.yml` |
| `config/default.yml` | `configs/presets/default.yml` |
| `config/hk_selected__xgb_regressor.yml` | `configs/experiments/variants/hk_selected__xgb_regressor.yml` |

如果本地还有旧目录，执行：

```bash
csml migrate-artifacts
```

详见 `docs/troubleshooting.md`。

## 相关文档

- CLI 命令：`docs/cli.md`
- 输出文件：`docs/outputs.md`
- Provider 差异：`docs/providers.md`
- 概念指南：`docs/concepts/`
