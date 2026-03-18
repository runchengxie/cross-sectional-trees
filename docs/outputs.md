# 输出产物与字段约定

本页解决什么：run 目录与产物字段的权威说明。
本页不解决什么：不展开指标含义与研究流程。
适合谁：要写下游消费脚本或核对输出结构的人。
读完你会得到什么：完整的目录与字段约定。
相关页面：`docs/metrics.md`、`docs/config.md`、`docs/cookbook.md`

本页说明 run 目录中的关键文件与字段约定，便于写自动化消费脚本（风控、报表、下游执行等）。

## 产物目录

默认每次运行会写到：

`artifacts/runs/<run_name>_<timestamp>_<config_hash>/`

`live` 推荐单独目录，例如 `artifacts/live_runs/...`。

当前默认根目录结构：

```text
artifacts/
  cache/
  assets/
    rqdata/
    universe/
  runs/
  live_runs/
  sweeps/
  snapshots/
```

另有一类独立于 run 目录的 provider 资产镜像：

`artifacts/assets/rqdata/hk/<dataset>/<snapshot>/`

当前 `dataset` 包括：

* `daily`
* `pit_financials`
* `financial_details`
* `ex_factors`
* `dividends`
* `shares`
* `instrument_industry`
* `industry_changes`

这类目录由 `csml rqdata mirror-hk-daily`、`csml rqdata mirror-hk-pit-financials`、`csml rqdata mirror-hk-financial-details`、`csml rqdata mirror-hk-ex-factors`、`csml rqdata mirror-hk-dividends`、`csml rqdata mirror-hk-shares`、`csml rqdata mirror-hk-instrument-industry` 和 `csml rqdata mirror-hk-industry-changes` 生成。
如果你继续执行 `csml rqdata build-hk-pit-fundamentals`，默认还会在对应的 `pit_financials` 目录下生成一份平面 fundamentals 文件。
如果你继续执行 `csml rqdata build-hk-industry-labels`，默认还会在对应的 `industry_changes` 目录下生成一份本地行业标签文件。

## RQData 资产镜像目录

目录结构：

```text
artifacts/assets/rqdata/hk/<dataset>/<snapshot>/
  manifest.yml
  audit.csv
  fields.txt
  symbols.txt
  data/
    00005.HK.parquet
    00011.HK.parquet
    ...
```

文件说明：

* `manifest.yml`：查询参数、字段列表、symbol 来源、文件统计、缺失 symbol 和 git 元数据。
* `audit.csv`：逐 symbol 下载状态，便于区分 `written`、`skipped_existing`、`missing_remote`、`failed` 和 `quota_blocked`。
* `fields.txt`：本次拉取的字段名清单。
* `symbols.txt`：本次拉取的 symbol 清单。
* `data/<symbol>.parquet`：按 symbol 分开的原始镜像文件；历史文档里常写成 `data/<ts_code>.parquet`，但文件名实际就是仓库归一后的 symbol 值。
* `dates.txt`：仅 `instrument_industry` 会写，表示本次行业快照实际查询的日期列表。
* `industries.txt` / `industry_catalog.parquet`：仅 `industry_changes` 会写，表示本次枚举的行业代码和映射表。

字段约定：

* `daily` 保留 `rqdatac.get_price` 返回的日频字段名，并额外写入 `trade_date`、legacy `ts_code`（仓库归一后的 symbol alias）和 `order_book_id`。
* `pit_financials` 保留 `rqdatac.get_pit_financials_ex` 的字段名，并额外写入 legacy `ts_code` 和 `order_book_id`。
* `financial_details` 保留 `rqdatac.hk.get_detailed_financial_items` 的字段名，并额外写入 legacy `ts_code` 和 `order_book_id`。
* `ex_factors` 保留 `rqdatac.get_ex_factor` 返回的字段名，并额外写入 legacy `ts_code`。
* `dividends` 保留 `rqdatac.get_dividend` 返回的字段名，并额外写入 legacy `ts_code` 和 `order_book_id`。
* `shares` 保留 `rqdatac.get_shares` 返回的字段名，并额外写入 legacy `ts_code` 和 `order_book_id`。
* `instrument_industry` 保留 `rqdatac.get_instrument_industry` 返回的行业列，并额外写入 legacy `ts_code`、`order_book_id`、`date`。
* `industry_changes` 保留 `start_date` / `cancel_date`，并额外写入 legacy `ts_code`、`order_book_id`、`industry_code`、`industry_name`、`industry_level`、`industry_source` 和完整行业层级列。

补充：

* `manifest.yml` 的 `status` 会记录本次镜像是否完整完成。
* 这类镜像目录供下游项目复用，不属于 `artifacts/cache/` 的 query cache。
* 对 RQData 来说，原生标识是 `order_book_id`；这里的 `ts_code` 只是仓库历史兼容列，值等于本仓库归一后的 symbol。

## PIT fundamentals 平面文件

默认路径：

`artifacts/assets/rqdata/hk/pit_financials/<snapshot>/pipeline_fundamentals.parquet`

这类文件由 `csml rqdata build-hk-pit-fundamentals` 生成，也可以通过 `--out` 写到其他位置。

配套文件：

* `pipeline_fundamentals.manifest.yml`：来源资产目录、字段选择、去重策略和输出统计。
* 可选：如果构建时传了 `--symbols-out`，会额外写一个 symbol 文本文件。
* 可选：如果构建时传了 `--source-universe-by-date` + `--universe-by-date-out`，会额外写一个过滤后的 PIT universe CSV。

字段约定：

* 固定列：`trade_date`、`ts_code`（legacy symbol alias；研究主链路读入后会自动映射到 `symbol`）
* 值列：你在命令里选中的 PIT 财报字段；如果没显式传字段，默认沿用源资产 `manifest.yml` 里的字段列表
* `trade_date` 默认等于原始 PIT 行的 `info_date`
* 传 `--keep-meta` 时，会额外保留 `quarter`、`info_date`、`fiscal_year`、`standard`、`if_adjusted`、`rice_create_tm`、`order_book_id`
* 构建阶段会自动规范化旧资产里的尾随空格字段名

使用建议：

* 这类文件可直接接 `fundamentals.source=file`
* 如果你希望披露后的交易日持续使用最近一版财报值，保留 `fundamentals.ffill=true`

## HK 行业标签文件

默认路径：

`artifacts/assets/rqdata/hk/industry_changes/<snapshot>/industry_labels_<freq>.parquet`

这类文件由 `csml rqdata build-hk-industry-labels` 生成，也可以通过 `--out` 写到其他位置。

配套文件：

* `industry_labels_<freq>.manifest.yml`：来源 `industry_changes` 资产、采样频率、日期网格来源和输出统计。
* 可选：如果构建时传了 `--symbols-out`，会额外写一个 symbol 文本文件。

字段约定：

* 固定列：`trade_date`、`ts_code`（legacy symbol alias；研究主链路读入后会自动映射到 `symbol`）
* 区间元数据列：通常还会保留 `order_book_id`、`start_date`、`cancel_date`
* 行业值列：如果源资产里有，会保留 `industry_code`、`industry_name`、`industry_level`、`industry_source` 以及完整行业层级列
* `trade_date` 永远是字符串 `YYYYMMDD`
* 当某个 symbol 在该日期没有命中任何有效行业区间时，该行仍然保留，但行业列会是空值

构建规则：

* 输入真相层是 `industry_changes` 里的区间记录，按 `start_date <= trade_date < cancel_date` 命中。
* `--source-universe-by-date` 适合月频或季频，直接复用研究股票池的日期和 symbol 网格。
* `--daily-asset-dir` 适合日频，会从本地日线镜像里提取实际交易日网格。
* `--frequency D|M|Q` 会在源网格上做抽样，`M/Q` 保留每个 symbol 在当月或当季的最后一个交易日。

使用建议：

* 如果你需要精确回放切换日，优先保留 `industry_changes` 原始区间资产。
* 如果你主要是做行业中性、暴露控制或日常 join，直接消费这类 `industry_labels_<freq>` 文件会更顺手。

## `summary.json` 顶层结构

`summary.json` 顶层字段（固定键）：

| 顶层键 | 说明 |
| --- | --- |
| `run` | 本次运行元数据（名称、时间戳、配置来源、模型类型、输出目录） |
| `data` | 市场、数据源、日期区间、样本规模 |
| `dataset` | `dataset.parquet` 的 schema/行数/索引信息 |
| `universe` | 股票池模式、PIT 文件与停牌处理策略 |
| `label` | 标签窗口、`shift_days`、标签模式 |
| `split` | 训练/测试日期与 purge/embargo 信息 |
| `eval` | IC、分位数、换手、错误指标、方向判定、滚动指标 |
| `backtest` | 回测参数、绩效统计、基准/主动收益与滚动 Sharpe（含延迟退出 lag 统计） |
| `final_oos` | 最终留出期（启用时）对应评估与回测摘要 |
| `positions` | 回测持仓文件路径与窗口字段声明 |
| `live` | live 模式状态、as_of 与 live 持仓文件路径 |
| `fundamentals` | 基本面数据源与字段配置摘要 |
| `industry` | 本地行业标签 join 配置摘要 |
| `walk_forward` | 滚动窗口验证参数与结果 |

说明：

1. 这些键固定存在，但部分值会是 `null`/空对象（例如未启用 `final_oos`、未启用 `live`）。
1. 消费脚本建议优先读 `summary.json` 里保存的文件路径，不要硬编码文件名。

`summary.json -> fundamentals` 当前会额外记录一层 `provider_overlay` 摘要：

```json
{
  "enabled": true,
  "source": "file",
  "provider": "rqdata",
  "file": "artifacts/assets/.../pipeline_fundamentals.parquet",
  "cache_dir": null,
  "features": ["revenue", "net_profit"],
  "log_market_cap": true,
  "market_cap_col": "market_cap",
  "provider_overlay": {
    "enabled": true,
    "source": "provider",
    "provider": "rqdata",
    "cache_dir": "artifacts/cache/fundamentals/hk",
    "features": ["market_cap", "pe_ttm", "pb"]
  }
}
```

说明：

1. `provider_overlay` 只表示运行时是否启用了第二路 provider 估值 merge，不等于这些列在每个 `trade_date` 都有值。
1. 审 provider 估值链路时，优先看 `config.used.yml` 与这里的 `fundamentals.provider_overlay`，再决定是按 file 还是按 overlay 口径复现。

`summary.json -> industry` 会记录本地行业标签 join 的配置与解析结果：

```json
{
  "enabled": true,
  "source": "file",
  "file": "artifacts/assets/.../industry_labels_m.parquet",
  "keep_columns": ["industry_name", "first_industry_name"],
  "resolved_columns": ["industry_name", "first_industry_name"],
  "ffill": false,
  "ffill_limit": null
}
```

说明：

1. `industry` 只表示本次运行是否把本地行业标签接进了 panel，不等于系统已经自动做了行业中性化。
1. `resolved_columns` 是本次真正保留到 panel / artifact 的行业列集合。

## 稳定性契约（给下游脚本）

稳定 contract（版本演进时尽量保持不变）：

1. `summary.json` 顶层固定键集合（`run/data/dataset/universe/label/split/eval/backtest/final_oos/positions/live/fundamentals/industry/walk_forward`）。
1. 研究主链路内部 canonical 标的列是 `symbol`；run artifacts / CLI 输出会继续双写 `symbol`、`ts_code`、`stock_ticker`。
1. 持仓主键列语义：`trade_date`、`entry_date`、`symbol`、`ts_code`、`stock_ticker`、`weight`、`signal`、`rank`、`side`。
1. `weight` 的解释取决于 `backtest.weighting`：`equal` 时等权，`signal` 时为信号 softmax 后的目标权重。
1. `summary.json` 内记录的文件路径优先级高于固定文件名推断。

best-effort（可能为空、缺失或未产出文件）：

1. `final_oos` / `live` / `walk_forward` 子结构（取决于对应功能是否启用）。
1. `dataset.parquet`、`eval_scored.parquet`、`backtest_*.csv` 等产物（取决于配置与数据可用性）。
1. 任何依赖外部数据源补数/修订得到的统计值（同配置在不同日期可能变化）。

## run 目录文件索引（按生成条件）

| 文件 | 生成条件 | 主要用途 |
| --- | --- | --- |
| `summary.json` | 默认 | 机器可读总摘要，包含路径指针与关键指标 |
| `config.used.yml` | 默认 | 实际生效配置（复现优先读这个） |
| `dropped_dates.csv` | 存在被 `min_symbols_per_date` 丢弃的日期时 | 排查样本不足与过滤影响 |
| `eval_scored.parquet` | `eval.save_artifacts=true` 且评估阶段成功 | `grid/summarize` 与二次分析复用 |
| `dataset.parquet` | `eval.save_artifacts=true` 且 `eval.save_dataset=true` | 冻结建模输入样本 |
| `ic_test.csv` / `ic_pearson_test.csv` | 默认 | 测试期 IC 时序 |
| `ic_train.csv` / `ic_pearson_train.csv` | `eval.report_train_ic=true` | 训练期对照 |
| `quantile_returns.csv` | 默认 | 分位数组合收益 |
| `turnover_eval.csv` | 默认 | 评估侧换手序列 |
| `backtest_net.csv` / `backtest_gross.csv` | `backtest.enabled=true` 且回测成功 | 净/毛收益序列 |
| `backtest_turnover.csv` / `backtest_periods.csv` | `backtest.enabled=true` 且回测成功 | 回测换手与周期收益 |
| `backtest_benchmark.csv` / `backtest_active.csv` | 配置了 `backtest.benchmark_symbol` 且数据可用 | 基准与主动收益 |
| `positions_by_rebalance*.csv` / `positions_current*.csv` | 生成了持仓结果时 | 下游持仓消费/执行衔接 |
| `rebalance_diff*.csv` | 对应 `positions_current*.csv` 存在至少两期时 | 最新一期调仓差异 |
| `latest.json` | `live.enabled=true` 且 live 成功输出时 | 指向最新 live run 目录 |
| `feature_importance.csv` | 模型支持且成功训练时 | 解释性分析 |
| `walk_forward_*.csv` | `eval.walk_forward.enabled=true` | 滚动窗口稳健性分析 |
| `permutation_test.csv` | `eval.permutation_test.enabled=true` | 抗伪发现检验 |

说明：

1. `*` 代表普通/`_live`/`_oos` 变体（是否存在取决于功能开关）。
1. 所有下游脚本应优先使用 `summary.json` 中记录的文件路径，不要只按文件名猜测。

## 持仓文件

### `positions_by_rebalance.csv` / `positions_by_rebalance_live.csv`

每个调仓期的目标持仓明细，核心列：

| 列名 | 说明 |
| --- | --- |
| `rebalance_date` | 信号计算日（`YYYYMMDD`） |
| `signal_asof` | 同 `rebalance_date`，用于快照展示 |
| `entry_date` | 实际入场日（考虑 `shift_days`） |
| `next_entry_date` | 下一次入场日（最后一期为空） |
| `holding_window` | `entry_date -> next_entry_date`（最后一期为 `entry_date`） |
| `symbol` | 标的代码（内部 canonical 列名） |
| `ts_code` | 标的代码旧别名（兼容列，值与 `symbol` 一致） |
| `stock_ticker` | 标的代码外部通用别名（兼容列，值与 `symbol` 一致） |
| `weight` | 目标权重；`backtest.weighting=equal` 时等权，`signal` 时为信号 softmax 权重 |
| `signal` | 该标的预测信号值 |
| `rank` | 当期截面排序名次 |
| `side` | `long` 或 `short` |

### `positions_current.csv` / `positions_current_live.csv`

只保留最新 `entry_date` 的那一组持仓，列结构与 `positions_by_rebalance` 一致。

兼容说明：

1. 项目研究主链路内部已经改为以 `symbol` 作为主字段。
1. 对外消费仍可继续使用 `ts_code` 或 `stock_ticker`；它们的值与 `symbol` 一致。

### `positions_by_rebalance_oos.csv` / `positions_current_oos.csv`

仅在启用 `eval.final_oos` 且成功评估时输出，字段与主文件一致。

## 调仓差异文件

`rebalance_diff.csv`（以及 `_live` / `_oos` 版本）展示最新一期 vs 上一期的变化：

| 列名 | 说明 |
| --- | --- |
| `entry_date` / `entry_date_prev` | 当前与上一期入场日 |
| `symbol` / `side` | 标的与方向 |
| `ts_code` | 标的代码旧别名（兼容列，等价于 `symbol`） |
| `stock_ticker` | 标的代码外部别名（等价于 `symbol`） |
| `weight` / `weight_prev` | 当前与上一期权重（缺失补 0） |
| `signal` / `signal_prev` | 当前与上一期信号 |
| `rank` / `rank_prev` | 当前与上一期 rank |
| `weight_delta` | `weight - weight_prev` |
| `change` | `added` / `removed` / `changed` |

## 数据集文件

### `dataset.parquet`（可选）

仅在同时满足以下条件时输出：

1. `eval.save_artifacts=true`
1. `eval.save_dataset=true`

格式约定：

1. Parquet 以 `(trade_date, symbol)` 为 MultiIndex。
1. 列顺序为：`price_col` + `features` + `extra_cols` + `label` + `is_tradable`（若存在）。
1. 若启用了本地 `industry.file` join，行业列会进入 `extra_cols` 并保留在 `dataset.parquet`。
1. 对应 schema 会写入 `summary.json -> dataset.schema`。

## 研究工具输出契约

下面三类文件不在单个 run 目录内，但属于研究流程中的核心对比产物。

### `csml summarize`：`runs_summary.csv`

默认位置：

`<first-runs-dir>/runs_summary.csv`（可用 `--output` 覆盖）。

来源：

1. 递归扫描 `--runs-dir` 下的 `summary.json`。
1. 对应读取同目录 `config.used.yml`。
1. 生成 `flag_*`、`score`、`dsr` 列用于筛选/排序。

列契约（当前稳定列顺序）：

```text
source_runs_dir,run_dir,run_name,run_timestamp,config_hash,summary_path,config_path,market,data_provider,data_start_date,data_end_date,data_end_date_config,data_rows,data_rows_model,data_rows_model_in_sample,data_rows_model_oos,data_dropped_dates,universe_mode,label_horizon_days,label_shift_days,eval_top_k,backtest_top_k,transaction_cost_bps,eval_rebalance_frequency,backtest_rebalance_frequency,backtest_exit_price_policy,backtest_exit_fallback_policy,backtest_weighting,eval_buffer_exit,eval_buffer_entry,backtest_buffer_exit,backtest_buffer_entry,eval_ic_mean,eval_ic_ir,eval_long_short,eval_turnover_mean,eval_pred_nunique,feature_importance_nonzero,backtest_periods,backtest_periods_per_year,backtest_total_return,backtest_ann_return,backtest_ann_vol,backtest_sharpe,backtest_skew,backtest_kurtosis_excess,backtest_max_drawdown,backtest_avg_turnover,backtest_avg_cost_drag,backtest_tracking_error,backtest_information_ratio,backtest_beta,backtest_alpha,backtest_corr,dsr,dsr_sr0,dsr_n_trials,dsr_var_trials,flag_short_sample,flag_negative_long_short,flag_high_turnover,flag_relative_end_date,flag_constant_prediction,flag_zero_feature_importance,score,status,error
```

`score` 计算规则：

```text
score = backtest_sharpe
      - score_drawdown_weight * abs(backtest_max_drawdown)
      - score_cost_weight * backtest_avg_cost_drag
```

默认权重（可由 CLI 覆盖）：

1. `score_drawdown_weight = 0.5`
1. `score_cost_weight = 10.0`

补充：

1. 若 `backtest_sharpe` 缺失，则 `score` 为空。
1. 若 `backtest_max_drawdown` 或 `backtest_avg_cost_drag` 缺失，会按 0 处理惩罚项。
1. `backtest_tracking_error`、`backtest_information_ratio`、`backtest_beta`、`backtest_alpha`、`backtest_corr` 来自 `summary.json -> backtest.active`。
1. 若命中 `flag_constant_prediction=true` 或 `flag_zero_feature_importance=true`，会把 `score` 和 `dsr` 留空，避免退化模型排到前面。
1. `dsr` 为 Deflated Sharpe Ratio（0-1），在 summarize 阶段按可比策略分组计算；`dsr_sr0` 为组内多重比较修正后的 Sharpe 阈值（原频率）。
1. `dsr_n_trials` 使用分组内尝试次数（attempts count）；`dsr_var_trials` 为分组内原频率 Sharpe 的样本方差（`ddof=1`）。

补充：

1. `eval_pred_nunique` 记录评估打分列 `pred` 的唯一值数量；`<=1` 会触发 `flag_constant_prediction=true`。
1. `feature_importance_nonzero` 记录 `feature_importance.csv` 中非零重要度个数；对线性模型它等价于“非零系数个数”。

### `csml grid`：`grid_summary.csv`

默认位置：

`artifacts/runs/grid_summary.csv`（可用 `--output` 覆盖）。

来源：

1. 先执行一次 base pipeline（产出 `eval_scored.parquet`）。
1. 在同一份 scored 数据上循环 `top_k × cost_bps × buffer_exit × buffer_entry × weighting`。
1. 每行对应一个参数组合，不会为每个格点重训模型。

列契约（当前稳定列顺序）：

```text
run_name,top_k,cost_bps,buffer_exit,buffer_entry,weighting,summary_path,output_dir,label_horizon_days,eval_ic_mean,eval_ic_ir,eval_long_short,eval_turnover_mean,backtest_periods,backtest_total_return,backtest_ann_return,backtest_ann_vol,backtest_sharpe,backtest_max_drawdown,backtest_avg_turnover,backtest_avg_cost_drag,status,error
```

### `csml sweep-linear`：`artifacts/sweeps/<tag>/`

目录结构：

```text
artifacts/sweeps/<tag>/
  configs/
    ridge_*.yml
    elasticnet_*.yml
  jobs.csv
  run_results.csv
  runs_summary.csv   # 默认会自动 summarize，除非 --skip-summarize
```

其中：

1. `jobs.csv` 列契约：`order,model,alpha,l1_ratio,run_name,config_path`
1. `run_results.csv` 列契约：`order,run_name,config_path,status,error`
1. `runs_summary.csv` 列契约与 `csml summarize` 章节一致。

### `csml backup-data`：`artifacts/snapshots/<name>/`

目录结构：

```text
artifacts/snapshots/<name>/
  manifest.yml
  artifacts/cache/...
  artifacts/assets/universe/...
  config/...
```

其中：

1. `manifest.yml` 记录快照名、生成时间、来源路径、复制后的目标路径、`kind/file_count/total_bytes` 汇总，以及当前 git 提交信息（若可识别）。
1. 默认会把 `artifacts/cache/` 和 `artifacts/assets/universe/` 一起复制；额外路径由 `--config` 和 `--include-path` 决定。
1. 这是本地私有快照工具，不会重新向 provider 拉数。
1. 若需要公开分享，请另做一份不含 `artifacts/cache/` 的安全包。推荐只保留 `manifest.yml`、配置文件、`config.used.yml`、汇总 CSV 和简短说明。

### 一次性旧目录迁移

当前仓库默认只使用 `artifacts/` 布局。

如果你是从旧版本目录升级过来，本地还保留旧目录，可执行：

```bash
csml migrate-artifacts
```

默认会把这些目录搬到新布局：

* `cache/` -> `artifacts/cache/`
* `out/fundamentals/` -> `artifacts/assets/fundamentals/`
* `data_assets/rqdata/` -> `artifacts/assets/rqdata/`
* `out/universe/` -> `artifacts/assets/universe/`
* `out/runs/` -> `artifacts/runs/`
* `out/live_runs/` -> `artifacts/live_runs/`
* `out/sweeps/` -> `artifacts/sweeps/`
* `data_mirror/` -> `artifacts/snapshots/`

新仓库或新克隆目录通常不需要这一步。

## 其他常用文件

1. `config.used.yml`：本次运行实际生效配置（复现实验首选）。
1. `eval_scored.parquet`：评估样本打分明细（启用 artifact 时）。
1. `ic_*.csv`、`quantile_returns.csv`、`backtest_*.csv`：指标时序数据。
1. `feature_importance.csv`：模型特征重要性。
1. `walk_forward_feature_importance.csv`：walk-forward 每个窗口的特征重要性明细。
1. `walk_forward_feature_stability.csv`：跨窗口稳定性统计（命中率/均值/方差等）。
