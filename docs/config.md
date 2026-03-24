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
| 本地实验 | `configs/local/*.yml`（个人自建，默认不跟踪）或自建实验目录 | 仅作个人派生，不当作官方入口 |

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
└── local/             # 本地覆盖目录（个人派生，默认不纳入版本控制）
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
| `eval` | 评估 | `top_k`, `transaction_cost_bps`, `save_artifacts`, `save_scored_artifact` |
| `backtest` | 回测 | `enabled`, `rebalance_frequency`, `top_k`, `weighting` |
| `live` | 快照 | `enabled`, `as_of` |
| `logging` | 日志输出 | `level`, `file` |

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
  sample_weight_mode: exp_decay  # none / date_equal / exp_decay
  sample_weight_params:
    halflife: 12
  train_window:
    mode: rolling                # full / rolling
    size: 16
    unit: dates                  # dates / years
```

详见 `docs/concepts/model-selection.md`。

### 评估与回测

```yaml
eval:
  top_k: 20
  transaction_cost_bps: 15
  save_artifacts: true
  save_scored_artifact: false

backtest:
  enabled: true
  rebalance_frequency: "M"   # M / Q / Y
  top_k: 20
  weighting: equal           # equal / signal
```

### `live.alloc_hk`

`csml alloc-hk` 会先读当前持仓，再在港股 liveops 层做执行前 sizing。CLI 参数优先级高于配置。

```yaml
live:
  alloc_hk:
    cash: 1000000
    method: custom                  # equal / custom
    require_stock_connect: true
    scenarios:
      capitals: [1000000, 500000]   # 可选；不配时默认只跑单场景
      top_ns: [20, 10]              # 可选；不配时默认沿用 CLI --top-n
    valuation:
      history_years: 3
      roll_window: 252
      sell_quantile: 0.95
      extreme_quantile: 0.99
    secondary_fill:
      enabled: true
      avoid_high_valuation: true
      avoid_high_valuation_strict: false
      max_steps: 5000
      allow_over_alloc: false
      max_over_alloc_ratio: 0.0
      max_over_alloc_amount: 0.0
      max_over_alloc_lots_per_ticker: 1
      cash_buffer_ratio: 0.0
      cash_buffer_amount: 0.0
      estimated_fee_per_order: 0.0
```

补充：

* `live.alloc_hk.scenarios.capitals` 和 `top_ns` 同时存在时，会按 `资金 × TopN` 生成场景矩阵。
* CLI 传 `--scenario-capital` / `--scenario-top-n` 时，会覆盖对应配置项。

### 日志

```yaml
logging:
  level: INFO
  # 不显式配置 file 时，若 eval.save_artifacts=true，
  # 默认写到 artifacts/runs/<run_dir>/run.log
  # file: artifacts/reports/my_run.log
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

### `model`

| 键 | 说明 | 常见值 |
|---|------|--------|
| `type` | 模型类型 | `xgb_regressor` / `xgb_ranker` / `ridge` / `elasticnet` |
| `sample_weight_mode` | 训练样本加权 | `none` / `date_equal` / `exp_decay` |
| `sample_weight_params.halflife` | `exp_decay` 半衰期（按训练日期步数） | `8`, `12`, `16` |
| `sample_weight_params.decay_rate` | `exp_decay` 的固定衰减率（可替代 `halflife`） | `0.95`, `0.98` |
| `train_window.mode` | 主训练窗口模式 | `full` / `rolling` |
| `train_window.size` | rolling 窗口大小 | `12`, `16`, `20` |
| `train_window.unit` | rolling 窗口单位 | `dates` / `years` |

说明：

* `sample_weight_mode=exp_decay` 时，近期训练日期权重更高；同一日期内仍会先按截面样本数做均分。
* `sample_weight_params` 目前至少需要提供 `halflife` 或 `decay_rate` 之一。
* `model.train_window` 作用在主训练、CV、walk-forward 训练段、`final_oos` 拟合和 `live.train_mode=full` 的再训练，不是评估侧 `walk_forward` 的别名。
* `train_window.unit=dates` 表示最近 `N` 个训练日期；`years` 表示相对训练终点回看最近 `N` 年。

### `eval`

| 键 | 说明 | 常见值 |
|---|------|--------|
| `top_k` | 选股数量 | `10`, `20`, `30` |
| `transaction_cost_bps` | 交易成本(bps) | `15`, `25` |
| `save_artifacts` | 保存产物 | `true` / `false` |
| `save_scored_artifact` | 单独保存 `eval_scored.parquet` | 默认 `false` |
| `purge_days` | 泄漏防护天数 | 默认 `horizon_days + shift_days` |

### `backtest`

| 键 | 说明 | 常见值 |
|---|------|--------|
| `enabled` | 开启回测 | `true` / `false` |
| `weighting` | 权重方式 | `equal` / `signal` |
| `exit_price_policy` | 退出价格策略 | `strict` / `ffill` / `delay` |
| `rebalance_frequency` | 再平衡频率 | `M` / `Q` / `Y` |
| `group_col` | 组合层分组列（例如行业列） | `first_industry_name` |
| `max_names_per_group` | 单组最多持仓数 | `2`, `3`, `5` |

说明：

* 若同时启用 `universe.by_date_file`，选股样本仍按 PIT universe 过滤。
* 回测的 entry/exit 定价与 `tradable` 检查会使用未经过 `universe_by_date` 过滤的日线价格面板，避免已持仓股票在持有期内因 universe 变化而“消失”。
* `backtest.group_col + max_names_per_group` 是组合构造阶段的最小版暴露约束，不会改变模型打分，也不等于完整行业中性化。

### `logging`

| 键 | 说明 | 常见值 |
|---|------|--------|
| `level` | 日志级别 | `INFO` / `WARNING` / `DEBUG` |
| `file` | 日志文件路径 | 任意文件路径 |

说明：

* 若未设置 `logging.file` 且 `eval.save_artifacts=true`，pipeline 会默认把日志写到本次 run 目录下的 `run.log`。
* 若显式设置 `logging.file`，则按该路径写日志，不再额外生成默认的 `<run_dir>/run.log`。

### `fundamentals`

| 键 | 说明 | 常见值 |
|---|------|--------|
| `enabled` | 开启基本面 | `true` / `false` |
| `source` | 数据来源 | `provider` / `file` |
| `ffill` | 财报沿用 | `true` / `false` |
| `provider_overlay.enabled` | 在 `source=file` 基础上叠加 provider 日频估值 | `true` / `false` |

### `features.missing`

| 键 | 说明 | 常见值 |
|---|------|--------|
| `method` | 填补方法 | `none` / `zero` / `cross_sectional_median` |
| `add_indicators` | 添加缺失标记 | `true` / `false` |

### `fundamentals.provider_overlay`

当主基本面走 `fundamentals.source=file` 且文件是稀疏 PIT 财报时，可以把 provider 的日频估值单独作为第二路输入并到 daily panel，而不是先写回 PIT 文件再 `ffill`。

```yaml
fundamentals:
  enabled: true
  source: file
  file: artifacts/assets/.../pipeline_fundamentals.parquet
  ffill: true
  provider_overlay:
    enabled: true
    source: provider
    provider: rqdata
    endpoint: get_factor
    fields:
      - hk_total_market_val
      - pe_ratio_ttm
      - pb_ratio_ttm
    column_map:
      trade_date: trade_date
      symbol: ts_code
      market_cap: hk_total_market_val
      pe_ttm: pe_ratio_ttm
      pb: pb_ratio_ttm
    features:
      - market_cap
      - pe_ttm
      - pb
    auto_add_features: true
    required: true
```

约定：

- `provider_overlay` 目前只支持 `source=provider`。
- 研究主链路内部以 `symbol` 为 canonical 标的列；旧配置里的 `column_map.ts_code` 仍然兼容。
- 主 `fundamentals.file` 仍按原逻辑做按 `symbol` 的 `ffill`，适合 PIT 财报。
- `provider_overlay` 按 `trade_date + symbol` 精确并到 daily panel，不做额外 `ffill`。
- 如果 overlay 数据里没有 `valuation_trade_date`，pipeline 会把 provider 行本身的 `trade_date` 记为 `valuation_trade_date`，并在需要时计算 `valuation_age_days`。
- `log_market_cap` 仍由顶层 `fundamentals.log_market_cap` 控制；只要 panel 里出现了 `market_cap`，就可以派生 `log_mcap`。

### `industry`

当你已经有本地 `industry_labels_<freq>.parquet` 时，可以直接把行业标签并到研究 panel，作为行业中性、暴露分析或 `bucket_ic` 的现成 join 输入。

```yaml
industry:
  enabled: true
  source: file
  file: artifacts/assets/rqdata/hk/industry_changes/hk_all_industry_changes_latest/industry_labels_m.parquet
  keep_columns:
    - industry_code
    - industry_name
    - first_industry_code
    - first_industry_name
  ffill: false
  required: true
```

约定：

- `industry` 目前只支持 `source=file`。
- join 主键固定是 `trade_date + symbol`；旧文件里的 `ts_code` / `stock_ticker` / `order_book_id` 会自动兼容。
- 如果 `keep_columns` 为空，默认保留文件里的全部非主键列。
- 这些行业列不会自动加入模型 `features`，但会保留在 `dataset.parquet`；若 `eval.save_scored_artifact=true`，也会保留到 `eval_scored.parquet`，并可直接被 `eval.bucket_ic.schemes` 引用。
- 这条链路只负责把行业标签接进 panel；自动行业中性化或行业约束还需要你在后续研究逻辑里显式实现。
- 如果你用的是 `industry_labels_m/q.parquet`，更稳妥的做法是让文件频率和你的研究单元一致；只有在你明确知道自己要传播最近一次标签时，才打开 `ffill=true`。

## 路径迁移（旧仓库升级）

| 旧路径 | 新路径 |
|--------|--------|
| `config/hk.yml` | `configs/presets/hk.yml` |
| `config/default.yml` | `configs/presets/default.yml` |
| `config/hk_selected__xgb_regressor.yml` | `configs/experiments/variants/hk_selected__xgb_regressor.yml` |

如果本地还有旧目录，需要手动把数据迁到新布局。仓库不再提供自动迁移命令。

详见 `docs/troubleshooting.md`。

## 相关文档

- CLI 命令：`docs/cli.md`
- 输出文件：`docs/outputs.md`
- Provider 差异：`docs/providers.md`
- 概念指南：`docs/concepts/`
