# 配置参考

本页解决什么：配置键与默认行为的速查表。
本页不解决什么：不展开研究路线与概念选择。
适合谁：需要查配置定义与模板的人。
读完你会得到什么：配置键的权威定义与常用模板入口。
相关页面：`docs/concepts/model-selection.md`、`docs/concepts/pit-coverage.md`、`docs/concepts/universe-modes.md`、`docs/concepts/data-sources.md`、`docs/concepts/execution-costs.md`

## 常用模板速查

| 场景 | 推荐模板 | 关键改动 |
|------|---------|---------|
| 第一次跑通 | `default` | 无 |
| 港股月频 starter（PIT universe + provider fundamentals） | `hk` | 默认读港股通 research universe，不要求本地 PIT fundamentals 文件 |
| HK selected 月频本地研究推荐入口 | `configs/experiments/variants/hk_selected__tr_close_execution_balanced_local.yml` | 需要本地 HK assets；把 `tr_close`、balanced execution 和本地 RQData 资产链路一次接好 |
| HK selected 月频历史 benchmark 锚点 | `configs/experiments/baseline/hk_selected.yml` | 保留 `close` + flat `25bps` 的旧口径，便于历史结果对照 |
| 港股季频 PIT 正式研究 | `configs/presets/hk_quarterly_pit_hybrid.yml` | 需要本地 `pipeline_fundamentals.parquet` |
| 季度 benchmark protocol | `configs/experiments/baseline/hk_selected__quarterly_*.yml` + `configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_*.yml` | 需要本地 `pipeline_fundamentals.parquet` |
| 更宽的季度实验路线 | `configs/experiments/variants/hk_selected__pit_quarterly_*` | 适合继续派生专题路线 |
| 本地实验 | `configs/local/*.yml`（个人自建，默认不跟踪）或自建实验目录 | 仅作个人派生，不当作官方入口 |

> **注意**：`csml run --config default` 里的 `default` 是内置别名，不等于仓库里的 `configs/presets/default.yml`。
>
> 这些内置别名和 `csml init-config` 都读取仓库根目录的 `configs/`。默认使用场景是源码 checkout 或包含 `configs/` 的导出源码目录，而不是脱离仓库上下文的孤立 wheel。

### `PIT` 在这个仓库里分别指什么

这里最容易混淆的是，`PIT` 可能同时出现在三层语义里：

* `PIT universe`：按日期变化的股票池成员关系，通常通过 `universe.by_date_file` 体现。
* `PIT fundamentals`：按披露节奏对齐的本地财务平面文件，通常通过 `fundamentals.source=file` + `pipeline_fundamentals.parquet` 体现。
* `季度 PIT 研究路线`：在同一研究单元里，把 `Q` 频率、PIT 财务字段和 benchmark protocol 组合起来的一整条正式研究路线。

文档里提到 `hk.yml` 时，默认指第一层和部分第二层之外的 HK starter，不应自动理解成“完整季度 PIT fundamentals 路线”。

---

## 配置目录结构

```
configs/
├── presets/           # 内置预设（market 默认配置）
│   ├── default.yml
│   ├── hk.yml
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
| `market` | 市场 | `hk` |
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
  provider: rqdata       # 当前仅支持 rqdata
  market: hk             # 当前仅支持 hk
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
    ex_factors_dir: "artifacts/assets/rqdata/hk/ex_factors/<snapshot>"
```

补充：

* 如果你希望 `data.price_col: tr_close`，并让价格类特征、标签、回测一起走总回报口径，推荐同时提供 `data.rqdata.ex_factors_dir`。
* `tr_close` 会在读取 daily 数据后自动派生；原始 `close` 仍会保留在数据集中，方便对照和执行参考。
* 若走 RQData 在线接口且显式设置 `data.rqdata.adjust_type: pre/post`，也可以把 provider 返回的调整后价格别名为 `tr_close`。
* 若 `price_col=tr_close` 且本地 `ex_factors_dir` 已配置，但某些 symbol 缺少对应 ex-factor 行，run 日志会给出显式告警；`summary.json -> data -> price_col_diagnostics` 也会记录是 `local_ex_factors`、`provider_adjusted_price`、`input_frame`、`input_frame_missing_ex_factors` 还是 `close_fallback_missing_ex_factors`。

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
  score_postprocess:
    method: neutralize
    columns: [log_mcap]
    strength: 0.5
    min_obs: 20
  save_artifacts: true
  save_scored_artifact: false

backtest:
  enabled: true
  rebalance_frequency: "M"   # M / Q / Y
  top_k: 20
  weighting: equal           # equal / signal
  execution:
    entry_policy:
      price_col: open
    exit_policy:
      price: delay           # strict / ffill / delay
      fallback: ffill        # ffill / none
      price_col: close
    cost_model:
      name: side_bps         # bps / side_bps / none
      buy_bps: 10
      sell_bps: 10
      short_entry_bps: 15
      short_exit_bps: 10
      short_borrow_bps_per_day: 0.5
    slippage_model:
      name: participation    # none / bps / participation
      amount_col: adv20_amount
      base_bps: 2
      impact_bps: 20
      portfolio_value: 1000000
      power: 0.5
    constraints:
      min_price: 5
      min_amount: 1000000
      amount_col: adv20_amount
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
| `provider` | 数据源 | `rqdata` |
| `start_date` | 开始日期 | `20200101` / `today` |
| `end_date` | 结束日期 | `20241231` / `t-1` / `last_trading_day` |
| `cache_tag` | 缓存版本标签 | 任意字符串 |
| `price_col` | 标签、回测、基准和价格类特征使用的价格列 | `close` / `tr_close` |

说明：

* `data.price_col` 现在不仅控制标签和回测，也控制 `sma`、`rsi`、`macd`、`ret_*`、`rv_*` 这类价格衍生特征。
* 想做 `close` vs `tr_close` 的 A/B，对照时只需要切这一项即可。

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
| `winsorize_pct` | 按 `trade_date` 对原始标签做去极值 | `0.01`, `null` |
| `train_target_transform` | 训练时对标签做横截面变换 | `none` / `zscore` / `rank` |

说明：

* `train_target_transform` 只影响训练、CV、walk-forward 和 `live.train_mode=full` 的拟合标签。
* 评估、`IC`、`Top-K`、`long_short` 和回测仍然使用 `label.target_col` 的原标签列。
* 对 `xgb_regressor` 来说，这个开关适合做“绝对收益回归 vs 相对强弱回归”的对照；对 `xgb_ranker` 来说，单调变换通常影响更小。

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
| `score_postprocess.method` | 预测分数后处理 | `none` / `neutralize` |
| `score_postprocess.columns` | 后处理依赖列 | `["log_mcap"]` |
| `score_postprocess.strength` | 中和强度 | `0.5`, `1.0` |
| `save_artifacts` | 保存产物 | `true` / `false` |
| `save_scored_artifact` | 单独保存 `eval_scored.parquet` | 默认 `false` |
| `purge_days` | 泄漏防护天数 | 默认 `horizon_days + shift_days` |

说明：

* `eval.score_postprocess` 发生在模型打分之后、`IC`/分位统计/回测之前，不会改训练样本，也不等于特征中性化。
* 当前 `method=neutralize` 会按 `trade_date` 对预测分数做截面线性去相关；`columns` 支持一个或多个控制列。
* `strength=1.0` 表示全量去掉该截面的线性暴露，`0.5` 表示只去掉一半；它适合做 “soft size control” 一类 probe。
* `min_obs` 至少要满足 `len(columns) + 1`；不满足时，该日期会回退为原始分数，不强行中和。

### `eval.walk_forward`

| 键 | 说明 | 常见值 |
|---|------|--------|
| `enabled` | 开启 walk-forward | `true` / `false` |
| `n_windows` | 目标窗口数 | `2`, `4`, `6` |
| `test_size` | 每个测试窗长度；为空时继承 `eval.test_size` | `0.2`, `0.3`, `null` |
| `step_size` | 窗口步长；为空时默认等于 `test_size` | `0.1`, `0.2`, `null` |
| `anchor_end` | 是否从样本尾部向前锚定窗口 | `true` / `false` |

说明：

* `eval.walk_forward.test_size: null` 不表示“小窗默认值”，而是直接继承 `eval.test_size`。
* 当 `anchor_end=true` 且 `step_size=null` 时，步长默认等于测试窗长度；如果 `test_size` 本身很大，例如 `0.6`，请求 `4` 个窗口时往往只能放下最后 `1` 个窗口。
* 现在 run 日志会在“请求窗口数”大于“实际可放下窗口数”时给出显式告警，避免把 `walk_forward.n_windows` 当成最终产出数量。

### `backtest`

| 键 | 说明 | 常见值 |
|---|------|--------|
| `enabled` | 开启回测 | `true` / `false` |
| `weighting` | 权重方式 | `equal` / `signal` |
| `exit_price_policy` | 退出价格策略 | `strict` / `ffill` / `delay` |
| `rebalance_frequency` | 再平衡频率 | `M` / `Q` / `Y` |
| `group_col` | 组合层分组列（例如行业列） | `first_industry_name` |
| `max_names_per_group` | 单组最多持仓数 | `2`, `3`, `5` |
| `execution` | 执行 realism 扩展：入场价、退出价列、费用模型、滑点、流动性约束 | 见下文 |

说明：

* 若同时启用 `universe.by_date_file`，选股样本仍按 PIT universe 过滤。
* 回测的 entry/exit 定价与 `tradable` 检查会使用未经过 `universe_by_date` 过滤的日线价格面板，避免已持仓股票在持有期内因 universe 变化而“消失”。
* `backtest.group_col + max_names_per_group` 是组合构造阶段的最小版暴露约束，不会改变模型打分，也不等于完整行业中性化。
* `backtest.execution` 会在 `transaction_cost_bps`、`exit_price_policy` 和 `data.price_col` 之上做更细的 execution 建模；不配时仍沿用原有默认行为。
* `execution.entry_policy.price_col` / `execution.exit_policy.price_col` 只影响回测与持仓构造，不会改变标签、基准或价格类特征的 `data.price_col` 口径。
* 成本、滑点、`tr_close` 与现金分红账本的关系，单独见 `docs/concepts/execution-costs.md`。

### `backtest.execution`

常见子键：

| 键 | 说明 | 常见值 |
|---|------|--------|
| `entry_policy.price_col` | 入场成交价列 | `open` / `close` / `tr_close` |
| `exit_policy.price` | 退出缺价处理 | `strict` / `ffill` / `delay` |
| `exit_policy.price_col` | 退出成交价列 | `close` / `open` / `tr_close` |
| `cost_model.name` | 费用模型 | `bps` / `side_bps` / `none` |
| `slippage_model.name` | 滑点模型 | `none` / `bps` / `participation` |
| `constraints.min_price` | 最低允许买入价格 | 任意非负数 |
| `constraints.min_amount` | 最低允许买入成交额 | 任意非负数 |

补充：

* `cost_model.name=bps` 时，仍可继续只用 `backtest.transaction_cost_bps`。
* `cost_model.name=side_bps` 适合分开配置 long/short、开仓/平仓 bps；`short_borrow_bps_per_day` 用于短端持有期借券成本近似。
* `slippage_model.name=bps` 表示固定单边滑点；`participation` 会按 `trade_weight * portfolio_value / amount_col` 估计冲击成本。
* `constraints.min_amount` 和 `slippage_model.amount_col` 读取的是仓库标准化后的列名；常见 provider 原始字段如 `total_turnover` 会先映射成 `amount`。
* 若想避免 `open` 入场直接读取同日总成交额带来的轻微 look-ahead，可把 `amount_col` 设成派生流动性代理列，例如 `adv20_amount` 或 `medadv20_amount`；它们分别表示按 symbol 计算、排除当日后的过去 `20` 个交易日平均/中位成交额。
* `summary.json -> backtest -> execution_source` 会记录这次 run 是沿用 `default_flat_cost`，还是显式启用了 `backtest.execution` 的 `explicit_execution_config`。
* 当前仓库里已经给出四条可直接复用的月频 HK execution variants：
  [hk_selected__execution_stress_local.yml](../configs/experiments/variants/hk_selected__execution_stress_local.yml)、
  [hk_selected__execution_balanced_local.yml](../configs/experiments/variants/hk_selected__execution_balanced_local.yml)、
  [hk_selected__execution_connect_conservative_local.yml](../configs/experiments/variants/hk_selected__execution_connect_conservative_local.yml)、
  [hk_selected__tr_close_execution_balanced_local.yml](../configs/experiments/variants/hk_selected__tr_close_execution_balanced_local.yml)。

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
      symbol: symbol
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
- provider / overlay 配置里的 canonical 标的键统一写 `symbol`；若原始列名还是 `ts_code`，请在 `column_map` 里写成 `symbol: ts_code`。
- `fundamentals.symbol_param` 的 canonical 默认值也是 `symbol`。
- 研究主链路内部以 `symbol` 为 canonical 标的列；旧配置里的 `column_map.ts_code` 仍然兼容。
- 主 `fundamentals.file` 仍按原逻辑做按 `symbol` 的 `ffill`，适合 PIT 财报。
- `provider_overlay` 按 `trade_date + symbol` 精确并到 daily panel，不做额外 `ffill`。
- 如果你同时配置了本地 daily / instruments 资产，pipeline 仍可在 overlay cache miss 时 lazy init `rqdatac` 去补拉估值。
- 当 `provider_overlay.required=true` 且本轮 run 一条 overlay 数据都没载入时，pipeline 会直接失败，不再静默降级成“空 overlay”。
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
