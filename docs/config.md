# 配置参考

内置模板位于 `src/csxgb/config/*.yml`，导出后的配置默认放在 `config/`。`--config` 支持内置别名（`default/cn/hk/us`）或文件路径。

模板导出示例：

```bash
csxgb init-config --market hk --out config/
```

## 关键参数

* `universe`：股票池、过滤条件、最小截面规模（支持 `by_date_file` 动态池；可用 `mode/require_by_date/suspended_policy` 明确 PIT 与停牌处理）
* `market`：`cn` / `hk` / `us`
* `data`：`provider`、`rqdata` / `eodhd` 或 `daily_endpoint` / `basic_endpoint` / `column_map`（字段映射为 `trade_date/ts_code/close/vol/amount`）、`cache_tag`、`retry`
* `fundamentals`：Level 0 基本面数据合并（`features`/`column_map`/`ffill`/`log_market_cap`/`required`）
* `label`：预测窗口、shift、winsorize（支持 `horizon_mode=next_rebalance`）
* `features`：特征清单与窗口
* `model`：XGBoost 参数，`sample_weight_mode`（`none`/`date_equal`）
* `eval`：切分、分位数、换手成本、embargo/purge、`signal_direction_mode`、`min_abs_ic_to_flip`、`sample_on_rebalance_dates`，以及可选的 `report_train_ic`、`save_artifacts`、`permutation_test` 与 `walk_forward`
* `backtest`：再平衡频率、Top-K、成本、`long_only/short_k`、基准、`exit_mode`、`exit_price_policy` 与 `buffer_exit/buffer_entry`
* `live`：可选“当下持仓快照”，用于在固定回测之外输出当前组合

## 基本面数据

* 默认 `fundamentals.enabled=true`（CN/Default 走 TuShare `daily_basic`，HK/US 默认走本地文件）；如无数据可先设为 `false`。
* `fundamentals.source=provider` 走数据源接口（目前仅支持 TuShare）；`source=file` 则读取本地 CSV/Parquet。缺文件会警告并跳过（可用 `fundamentals.required=true` 强制报错）。
* 使用 `fundamentals.column_map` 映射字段，再通过 `ffill` 做按股票时间向前填充。

## Live 模式

`live` 用于在同一套配置下生成“当前持仓快照”。建议搭配单独的 live 配置文件与输出目录，避免和回测产物混在一起。

```yaml
data:
  end_date: "t-1"   # 支持 today / t-1 / YYYYMMDD / last_trading_day

eval:
  output_dir: "out/live_runs"
  save_artifacts: true

backtest:
  enabled: false

live:
  enabled: true
  as_of: "t-1"
  train_mode: "full"   # full=用全部可用标签训练; train=复用回测训练集模型
```

说明：
* `last_trading_day` / `last_completed_trading_day` 需要交易日历支持（`provider=rqdata`），否则会退回到自然日并给出警告。
* Live 产物固定写入 `positions_by_rebalance_live.csv` 与 `positions_current_live.csv`（live-only 不再生成普通文件）；持仓文件会包含 `signal_asof/next_entry_date/holding_window` 辅助字段。
* `csxgb holdings --source live` 会优先读取 summary 中的 live 文件路径。
* 一键快照：`csxgb snapshot --config config/hk_live.yml`（内部先 run 再输出 holdings），可用 `--skip-run` / `--run-dir` 只读已有结果。
