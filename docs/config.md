# 配置参考

内置模板位于 `src/csml/config/*.yml`。导出后的配置默认放在 `config/`。

```bash
csml init-config --market hk --out config/
```

相关文档：

* CLI 用法：`docs/cli.md`
* 数据源差异：`docs/providers.md`
* 输出文件与字段：`docs/outputs.md`
* 常见报错：`docs/troubleshooting.md`

## 开始前先决定这几件事

第一次改配置时，优先看这些键：

* `data.provider`：先确定数据源。
* `data.start_date` / `data.end_date`：复现实验优先用绝对日期。
* `universe.mode` + `universe.by_date_file`：长历史回测优先 PIT。
* `model.type`：先确定是线性基线还是 XGB 对照。
* `eval.top_k` / `backtest.top_k`：决定选股数量。
* `eval.transaction_cost_bps` / `backtest.transaction_cost_bps`：先把成本假设设清楚。
* `label.shift_days`：会直接影响当前持仓的解释。
* `live.enabled`：如果需要当前持仓快照，再开启 live。

## HK 配置角色分工

HK 相关配置建议按职责使用：

* `config/hk_selected__baseline.yml`：通用基线配置。适合 `sweep-linear` 和线性模型批跑。
* `config/hk_selected__xgb_regressor.yml`：显式 XGB 回归实验配置。
* `config/hk_selected__xgb_ranker_pairwise.yml`：显式 XGB 排序实验配置。

实践建议：

* 线性模型批跑时，优先用 `config/hk_selected__baseline.yml` 作为基础配置。
* 非线性对照时，显式指定对应的 XGB 配置文件。
* HK selected 基线现在默认覆盖 `2015-01-01` 到 `2025-12-31`，配合 PIT universe 做 10y+ 回测。
* 旧的 `config/hk_selected.yml` 已弃用。若 `sweep-linear` 遇到该路径且文件不存在，会自动回退到 `config/hk_selected__baseline.yml` 并给 warning。

## 顶层配置块

常见顶层键：

* `market`：`cn` / `hk` / `us`
* `data`：数据源、日期区间、缓存、重试
* `universe`：股票池、过滤条件、PIT 文件
* `fundamentals`：基本面数据源、列映射、缺失处理
* `label`：预测窗口、shift、截尾方式
* `features`：特征列表与窗口
* `model`：模型类型、参数、样本权重
* `eval`：切分、IC、换手、稳健性检验和可选产物
* `backtest`：调仓频率、Top-K、成本、退出规则
* `live`：当前持仓快照

## 模型切换

```yaml
model:
  type: ridge
  params:
    alpha: 1.0
  sample_weight_mode: date_equal
```

支持的模型：

* `xgb_regressor`
* `xgb_ranker`
* `ridge`
* `elasticnet`

补充：

* 未显式设置 `model.type` 时，默认使用 `xgb_regressor`。
* `xgb_ranker` 会按 `trade_date` 自动分组训练，其余模型走回归流程。

## `data`

高频键：

* `provider`：`tushare` / `rqdata` / `eodhd`
* `start_date` / `start_years`：两者同时存在时，`start_date` 优先生效
* `end_date`
* `price_col`
* `cache_dir`
* `cache_tag` / `cache_version`
* `cache_mode` / `daily_cache_mode`
* `cache_refresh_days`
* `cache_refresh_on_hit`
* `retry`

### 日期 token

`end_date` 支持：

* `today`
* `t-1`
* `last_trading_day`
* `last_completed_trading_day`
* `YYYYMMDD`

补充：

* `last_trading_day` 和 `last_completed_trading_day` 是否严格按交易日解析，取决于 provider 和命令上下文。
* 做自动化任务或复现实验时，优先使用绝对日期。
* provider 差异见 `docs/providers.md`，命令侧行为见 `docs/cli.md`。

### 缓存

`cache_mode` / `daily_cache_mode` 支持：

* `symbol`：按单票缓存
* `range` / `window`：按时间区间缓存

常见建议：

* 需要隔离实验版本时，设置 `data.cache_tag`
* 想减少“同配置结果漂移”时，固定绝对日期并保留缓存目录
* HK 这类日频研究，几百只股票跑 10-15 年通常仍是几十 MB 级别，优先继续用 Parquet 缓存，不必先上数据库

### TuShare 覆盖项

按需可配：

* `daily_endpoint` / `basic_endpoint`
* `daily_fields` / `basic_fields`
* `daily_params` / `basic_params`
* `daily_symbol_param` / `daily_start_param` / `daily_end_param`

## `universe`

高频关注点：

* `mode`：`auto` / `pit` / `static`
* `by_date_file`
* `require_by_date`
* `min_symbols_per_date`
* `suspended_policy`

建议：

* 长历史回测优先 `pit + by_date_file`
* 静态 `symbols/symbols_file` 适合当期研究，不适合严谨历史回测

## `label`

高频键：

* `target_col`
* `horizon_days`
* `horizon_mode`
* `rebalance_frequency`
* `shift_days`
* `winsorize`

补充：

* `shift_days` 会影响信号日和入场日的对应关系。
* 如果你看到“当月持仓”和预期不一致，先回看 `shift_days`。

## `eval`

高频键：

* `top_k`
* `transaction_cost_bps`
* `purge_days`
* `embargo_days`
* `signal_direction_mode`
* `min_abs_ic_to_flip`
* `sample_on_rebalance_dates`
* `report_train_ic`
* `save_artifacts`
* `save_dataset`
* `permutation_test`
* `walk_forward`
* `final_oos`
* `rolling`
* `bucket_ic`

### 泄漏防护

默认行为：

* `eval.purge_days` 未配置时，会自动取 `label.horizon_days_effective + label.shift_days`
* `eval.embargo_days` 未配置时默认 `0`

建议：

* 显式覆盖时，通常保持 `purge_days >= shift_days + horizon_days_effective`
* `sample_on_rebalance_dates=true` 时，系统会把 `purge/embargo` 从天数换算为重平衡步数

### 可选评估能力

* `permutation_test`：做置换检验
* `walk_forward`：做滚动窗口验证
* `final_oos`：保留最终留出期
* `rolling`：输出滚动 IC / Sharpe
* `bucket_ic`：输出分桶 IC

## `backtest`

高频键：

* `enabled`
* `rebalance_frequency`
* `top_k`
* `transaction_cost_bps`
* `long_only`
* `short_k`
* `benchmark_symbol`
* `exit_mode`
* `exit_price_policy`
* `exit_fallback_policy`
* `buffer_exit`
* `buffer_entry`
* `tradable_col`
* `execution`

### 退出价格

`exit_price_policy`：

* `strict`：到期日没有价格或不可交易时，本期不计算退出
* `ffill`：用到期日前最近可用价格退出
* `delay`：向后找最近可用价格退出

`exit_fallback_policy`：

* `ffill`：`delay` 向后找不到价格时，回退到到期日前最近可用价格
* `none`：不回退

### 新旧键优先级

* 旧键：`backtest.exit_price_policy` / `backtest.exit_fallback_policy`
* 新键：`backtest.execution.exit_policy.price` / `backtest.execution.exit_policy.fallback`
* 两者同时存在时，新键最终生效

### 与停牌处理的关系

* `universe.suspended_policy=mark`：保留样本并标记 `is_tradable`
* `universe.suspended_policy=filter`：前置过滤停牌样本

## `fundamentals`

高频键：

* `enabled`
* `source`
* `features`
* `column_map`
* `ffill`
* `log_market_cap`
* `required`
* `cache_dir`

补充：

* `source=provider` 支持 TuShare，也支持 `market=hk` + `provider=rqdata`
* `source=file` 读取本地 CSV 或 Parquet
* `provider=rqdata` 时，默认走 `rqdatac.get_factor`
* 未显式设置 `fundamentals.cache_dir` 时，provider 基本面默认缓存到 `data.cache_dir/fundamentals/<market>/`
* HK 常用映射可直接写成：`market_cap -> hk_total_market_val`、`pe_ttm -> pe_ratio_ttm`、`pb -> pb_ratio_ttm`
* 缺文件时默认 warning 并跳过，可用 `required=true` 改成报错

## `live`

`live` 用于在同一套配置下生成当前持仓快照。建议单独使用 live 配置文件和独立输出目录。

```yaml
data:
  end_date: "t-1"

eval:
  output_dir: "out/live_runs"
  save_artifacts: true

backtest:
  enabled: false

live:
  enabled: true
  as_of: "t-1"
  train_mode: "full"
```

开启 live 时，通常还需要：

* `eval.save_artifacts=true`
* 单独的 `eval.output_dir`
* 明确的 `live.as_of`

命令入口见 `docs/cli.md`，输出文件见 `docs/outputs.md`。

## 可选输出

### `dataset.parquet`

设置 `eval.save_dataset=true` 且 `eval.save_artifacts=true` 后，会额外输出 `dataset.parquet`。

### `backtest.execution`

如需显式配置执行成本和退出规则，可使用：

```yaml
backtest:
  execution:
    cost_model:
      name: bps
      bps: 15
      round_trip: true
    exit_policy:
      price: delay
      fallback: ffill
```
