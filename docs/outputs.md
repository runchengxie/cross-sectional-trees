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

如果你把产物根目录外置到 repo 之外，上面这些路径会整体跟着新根目录移动。当前支持三种入口：

* 配置：`paths.artifacts_root`
* 环境变量：`CSML_ARTIFACTS_ROOT`
* CLI：`--artifacts-root`

本页示例仍统一写成 `artifacts/...`，只是为了说明目录结构，不代表根目录必须留在仓库内。

当前默认根目录结构：

```text
artifacts/
  cache/
  assets/
    rqdata/
    universe/
  metadata/
  standardized/
  runs/
  live_runs/
  sweeps/
  snapshots/
  reports/
```

另有一类独立于 run 目录的 provider 资产镜像：

`artifacts/assets/rqdata/hk/<dataset>/<snapshot>/`

以及一类独立于 run 目录的检查 / 校准 / 健康报告：

`artifacts/reports/`

常见来源包括 `csml rqdata inspect-hk-*`、intraday slippage / health 分析，以及维护脚本串联后的健康检查输出。

当前 `dataset` 包括：

* `daily`
* `intraday`
* `pit_financials`
* `financial_details`
* `ex_factors`
* `dividends`
* `shares`
* `valuation`
* `exchange_rate`
* `announcement`
* `southbound`
* `instrument_industry`
* `industry_changes`

这类目录由 `csml rqdata mirror-hk-daily`、`csml rqdata build-hk-intraday-asset`、`csml rqdata mirror-hk-pit-financials`、`csml rqdata mirror-hk-financial-details`、`csml rqdata mirror-hk-ex-factors`、`csml rqdata mirror-hk-dividends`、`csml rqdata mirror-hk-shares`、`csml rqdata mirror-hk-valuation`、`csml rqdata mirror-hk-exchange-rate`、`csml rqdata mirror-hk-announcement`、`csml rqdata mirror-hk-southbound`、`csml rqdata mirror-hk-instrument-industry` 和 `csml rqdata mirror-hk-industry-changes` 生成。
如果你继续执行 `csml rqdata build-hk-pit-fundamentals`，默认还会在对应的 `pit_financials` 目录下生成一份平面 fundamentals 文件。
如果你继续执行 `csml rqdata build-hk-industry-labels`，默认还会在对应的 `industry_changes` 目录下生成一份本地行业标签文件。

## RQData 资产镜像目录

大多数按 symbol 镜像的目录结构：

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
* `dates.txt`：`southbound` 和 `instrument_industry` 会写，表示本次实际查询的日期列表。
* `currency_pairs.txt`：仅 `exchange_rate` 会写，表示本次实际查询并成功落盘的货币对清单。
* `trading_types.txt`：仅 `southbound` 会写，表示本次实际查询的 `sh` / `sz` 渠道列表。
* `industries.txt` / `industry_catalog.parquet`：仅 `industry_changes` 会写，表示本次枚举的行业代码和映射表。

`intraday` 例外：

```text
artifacts/assets/rqdata/hk/intraday/<snapshot>/
  manifest.yml
  inputs.txt
  fields.txt
  data/
    hk_all_5m_20250327_20260326.parquet
    hk_all_5m_20250327_20260326.meta.json
    hk_all_5m_20250327_20260326.parts/
      batch_0001.parquet
      ...
```

这类目录由本地 `5m` cache / parquet 复制打包而来，不会重新向 provider 拉数。

`exchange_rate` 例外：

```text
artifacts/assets/rqdata/hk/exchange_rate/<snapshot>/
  manifest.yml
  fields.txt
  currency_pairs.txt
  dates.txt
  data/
    exchange_rate.parquet
```

这类目录不按 symbol 拆文件，而是把整个时间窗的汇率结果写入单个 `data/exchange_rate.parquet`。

字段约定：

* `daily` 保留 `rqdatac.get_price` 返回的日频字段名，并额外写入 `trade_date`、`symbol` 和 `order_book_id`。
* `intraday` 保留本地 `5m` parquet 当前已有的列；新产物默认至少会包含 `trade_datetime`、`symbol`、`open`、`high`、`low`、`close`、`volume`、`amount`，并尽量保留 `rq_order_book_id`。`fields.txt` 记录的是当前可直接给下游消费的值列，不包含 symbol / datetime 元数据列。
* `pit_financials` 保留 `rqdatac.get_pit_financials_ex` 的字段名，并额外写入 `symbol` 和 `order_book_id`。
* `financial_details` 保留 `rqdatac.hk.get_detailed_financial_items` 的字段名，并额外写入 `symbol` 和 `order_book_id`。
  当前实测最有用的是长表列 `field`、`amount`、`subject`、`currency`；`manifest.yml` 里的 `field_coverage` 也按这组长表记录统计。
* `ex_factors` 保留 `rqdatac.get_ex_factor` 返回的字段名，并额外写入 `symbol`。
* `dividends` 保留 `rqdatac.get_dividend` 返回的字段名，并额外写入 `symbol` 和 `order_book_id`。
* `shares` 保留 `rqdatac.get_shares` 返回的字段名，并额外写入 `symbol` 和 `order_book_id`。
* `valuation` 保留 `rqdatac.get_factor` 返回的因子列，并额外写入 `symbol`、`order_book_id` 和 `trade_date`。这类资产适合冻结 `market_cap / pe_ttm / pb` 一类日频估值口径，但它本身不是 pipeline 默认直读入口。
* `exchange_rate` 保留 `rqdatac.get_exchange_rate` 返回的字段名，固定要求至少有 `date` 和 `currency_pair`；`date` 会规范成字符串 `YYYYMMDD`。
* `announcement` 保留 `rqdatac.hk.get_announcement` 返回的字段名，并额外写入 `symbol`、`order_book_id` 和 `info_date`。
* `southbound` 固定写出 `date`、`symbol`、`order_book_id`、`trading_type`、`eligible`；其中 `trading_type` 表示 `sh` / `sz` 渠道，`eligible` 当前固定为 `1`。
* `instrument_industry` 保留 `rqdatac.get_instrument_industry` 返回的行业列，并额外写入 `symbol`、`order_book_id`、`date`。
* `industry_changes` 保留 `start_date` / `cancel_date`，并额外写入 `symbol`、`order_book_id`、`industry_code`、`industry_name`、`industry_level`、`industry_source` 和完整行业层级列。

补充：

* `manifest.yml` 的 `status` 会记录本次镜像是否完整完成。
* 这类镜像目录供下游项目复用，不属于 `artifacts/cache/` 的 query cache。
* `intraday` 的 `manifest.yml` 还会记录每个 block 的来源 cache 路径、是否存在 `.parts/`、原始 `adjust_type`、quota 字段和聚合后的日期范围。
* 对 RQData 来说，原生标识是 `order_book_id`；raw asset 新输出默认也统一写 canonical `symbol`。旧快照里的 `ts_code` 仍会在读取时自动兼容到 `symbol`。
* 本地 merge / patch 生成的新快照也遵循同一口径：输出 parquet 和 `manifest.yml -> columns` 会归一成 `symbol`，不再把 `ts_code` 继续写回新产物。

## Metadata Catalog

默认路径：

* `artifacts/metadata/catalog.sqlite`
* `artifacts/metadata/catalog_summary.csv`

这两份产物由 `csml data catalog` 生成。

如果改了 `paths.artifacts_root`、`CSML_ARTIFACTS_ROOT` 或命令行 `--artifacts-root`，默认路径会随新的产物根目录一起派生；只有显式传了 `--db-path` / `--summary-out` 时才会覆盖。

用途：

* 用 SQLite 管理 manifest-backed 资产索引
* 记录 layer、dataset、market、状态、时间范围、symbol 数和行数
* 把 `source_asset_dir`、`source_manifest`、snapshot entries 这类 lineage 关系落到表里

当前主要覆盖：

* `artifacts/assets/**/manifest.yml`
* `artifacts/assets/**/*.manifest.yml`
* `artifacts/standardized/**/manifest.yml`
* `artifacts/snapshots/**/manifest.yml`

说明：

* `catalog.sqlite` 是控制面，不存行情本体。
* `catalog_summary.csv` 是给人看和临时筛选的平面导出，不替代 SQLite。

## Standardized Layer

默认路径：

`artifacts/standardized/<market>/<dataset>/<name>/`

这类目录由 `csml data materialize` 生成，目标是把 raw / derived 输入转成更适合横截面查询和聚合的分析层。

如果改了 `paths.artifacts_root`、`CSML_ARTIFACTS_ROOT` 或命令行 `--artifacts-root`，默认输出根目录会随新的产物根目录一起派生；只有显式传了 `--out-root` 时才会覆盖。

目录结构：

```text
artifacts/standardized/<market>/<dataset>/<name>/
  manifest.yml
  data/
    trade_year=2026/
      part-00000.parquet
      ...
```

文件说明：

* `manifest.yml`：标准层数据集名、频率、分区方式、列类型、质量统计和 lineage。
* `data/trade_year=.../*.parquet`：按 `trade_year` 分区的 analysis-ready Parquet 文件。

字段约定：

* 标准列：`trade_date`、`trade_date_key`、`symbol`、`_source_file`
* `trade_date` 会规范成可直接查询/聚合的时间列
* `trade_date_key` 保留 `YYYYMMDD` 字符串键，便于和现有研究链路对照
* 如果输入本来就有 `trade_date` / `symbol` / `_source_file` 这类同名列，标准层会保留原始列并自动改名到 `source_*`

质量字段：

* `quality.rows_missing_date_dropped`
* `quality.rows_missing_symbol_dropped`
* `quality.duplicate_rows_dropped`

使用建议：

* 原始 replay、审计和复现继续看 `artifacts/assets/`。
* 横截面覆盖分析、聚合、筛选和 SQL 查询优先读 `artifacts/standardized/`。
* `csml data materialize` 的常用 preset 已默认把 `symbol` 当输入标准列；历史 `ts_code` / `stock_ticker` / `order_book_id` 文件仍会自动归一到 `symbol`。

## PIT fundamentals 平面文件

默认路径：

`artifacts/assets/rqdata/hk/pit_financials/<snapshot>/pipeline_fundamentals.parquet`

这类文件由 `csml rqdata build-hk-pit-fundamentals` 生成，也可以通过 `--out` 写到其他位置。

配套文件：

* `pipeline_fundamentals.manifest.yml`：来源资产目录、字段选择、去重策略和输出统计。
* 可选：如果构建时传了 `--symbols-out`，会额外写一个 symbol 文本文件。
* 可选：如果构建时传了 `--source-universe-by-date` + `--universe-by-date-out`，会额外写一个过滤后的 PIT universe CSV。

字段约定：

* 固定列：`trade_date`、`symbol`
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

* 固定列：`trade_date`、`symbol`
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
| `backtest` | 回测参数、绩效统计、基准/主动收益、风格/行业暴露与滚动 Sharpe（含延迟退出 lag 统计） |
| `final_oos` | 最终留出期（启用时）对应评估与回测摘要 |
| `positions` | 回测持仓文件路径与窗口字段声明 |
| `live` | live 模式状态、as_of 与 live 持仓文件路径 |
| `quality` | 主流程 preflight 质量闸门摘要与报告路径 |
| `fundamentals` | 基本面数据源与字段配置摘要 |
| `industry` | 本地行业标签 join 配置摘要 |
| `walk_forward` | 滚动窗口验证参数与结果 |

说明：

1. 这些键固定存在，但部分值会是 `null`/空对象（例如未启用 `final_oos`、未启用 `live`）。
1. 消费脚本建议优先读 `summary.json` 里保存的文件路径，不要硬编码文件名。
1. `summary.json -> walk_forward.n_windows` 表示请求窗口数；`summary.json -> walk_forward.actual_windows` 表示按当前 `test_size / step_size / anchor_end` 真实放得下的窗口数，可能更小。

`summary.json -> data` 现在会额外记录：

* `price_col`：这次 run 训练标签、价格特征、回测和 benchmark 采用的主价格列。
* `price_col_diagnostics`：当前主要用于 `tr_close` 口径审计，会记录 `tr_close_source_counts`，以及缺失/回退 symbol 的数量和样本。

如果 `price_col=tr_close`，`price_col_diagnostics.tr_close_source_counts` 常见值包括：

* `local_ex_factors`
* `provider_adjusted_price`
* `input_frame`
* `input_frame_missing_ex_factors`
* `close_fallback_missing_ex_factors`

`summary.json -> backtest -> execution` 会记录回测侧实际生效的 execution 建模摘要，例如：

```json
{
  "entry_policy": {"price_col": "open"},
  "exit_policy": {
    "price_policy": "delay",
    "fallback_policy": "ffill",
    "price_col": "close"
  },
  "cost_model": {
    "name": "side_bps",
    "long_entry_bps": 10.0,
    "long_exit_bps": 10.0,
    "short_entry_bps": 15.0,
    "short_exit_bps": 10.0,
    "short_borrow_bps_per_day": 0.5
  },
  "slippage_model": {
    "name": "participation",
    "amount_col": "amount",
    "base_bps": 2.0,
    "impact_bps": 20.0,
    "portfolio_value": 1000000.0,
    "power": 0.5
  },
  "constraints": {
    "min_price": 5.0,
    "min_amount": 1000000.0,
    "amount_col": "amount"
  }
}
```

说明：

1. 这里记录的是“实际生效值”，优先级高于你对默认行为的记忆。
1. `summary.json -> backtest -> execution_source` 会标记这次 run 是沿用 `default_flat_cost`，还是显式启用了 `backtest.execution` 的 `explicit_execution_config`。
1. `backtest.stats.avg_cost_drag` 现在表示总 execution drag；若需要拆分，查看同层 `avg_fee_drag` 与 `avg_slippage_drag`。

`summary.json -> backtest -> exposure` 当前会记录一层 best-effort 暴露摘要：

```json
{
  "style_file": "artifacts/runs/<run_dir>/backtest_style_exposure.csv",
  "industry_file": "artifacts/runs/<run_dir>/backtest_industry_exposure.csv",
  "active_summary_file": "artifacts/runs/<run_dir>/backtest_active_exposure_summary.csv",
  "latest_rebalance_date": "20250425",
  "latest_entry_date": "20250428",
  "style_factors": {
    "size": {"available": true, "source": "columns", "columns": ["log_mcap"]},
    "value": {"available": true, "source": "columns", "columns": ["pb", "pe_ttm"]},
    "quality": {"available": false, "source": null, "columns": []},
    "momentum": {"available": true, "source": "columns", "columns": ["ret_20"]},
    "low_vol": {"available": true, "source": "columns", "columns": ["rv_20"]},
    "beta": {"available": true, "source": "columns", "columns": ["beta"]}
  },
  "latest_style": {
    "size": {
      "portfolio_net": 0.42,
      "active_net_vs_equal": 0.42,
      "source": "columns",
      "source_columns": ["log_mcap"],
      "weight_coverage": 1.0
    }
  },
  "industry_column": "industry_name",
  "latest_industry": {
    "reference": "active_net_vs_cap_weight",
    "top_absolute_active": [
      {"industry": "银行", "portfolio_net_weight": 0.5, "active_net_vs_cap_weight": 0.18}
    ]
  }
}
```

说明：

1. 这层是“组合暴露摘要”，不是完整 Barra 风险模型，也不会自动改变回测权重。
1. `style_factors[*].available=false` 表示当前 run 的 panel 里缺少可解析列；这是 best-effort 缺失，不是报错。
1. `active_summary_file` 是一行一个调仓期的宽表，方便直接看每期风格主动暴露与最显著行业偏离。
1. 若启用了 `final_oos`，同样结构会出现在 `summary.json -> final_oos -> backtest -> exposure`。

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

`summary.json -> run` 现在还会记录训练机制相关元数据：

```json
{
  "log_file": "artifacts/runs/<run_dir>/run.log",
  "model_type": "xgb_ranker",
  "sample_weight_mode": "exp_decay",
  "sample_weight_params": {"halflife": 12},
  "train_window": {"mode": "rolling", "size": 16, "unit": "dates"}
}
```

说明：

1. `log_file` 是本次 run 实际使用的日志路径；未显式配置 `logging.file` 时，默认会落在 `<run_dir>/run.log`。
1. `sample_weight_mode` / `sample_weight_params` 反映模型拟合时是否启用了近期样本加权。
1. `train_window` 反映主训练、CV、walk-forward 训练段、`final_oos` 拟合与 `live.train_mode=full` 复训所使用的训练窗口配置。

`summary.json -> quality -> preflight` 会记录主流程前置质量检查的结果；当前支持的是 HK 本地 PIT fundamentals 文件对应的 PIT health gate。例如：

```json
{
  "enabled": true,
  "fail_on_severity": "warning",
  "gate_triggered": false,
  "message": "2 quality issue(s) detected; none met fail_on_severity=warning.",
  "overall_verdict": {
    "color": "yellow",
    "overall_severity": "warning",
    "issue_count": 2,
    "severity_counts": {"error": 0, "warning": 2, "info": 0},
    "fail_on_severity": "warning",
    "gate_triggered": false,
    "gate_status": "pass"
  },
  "checks": [
    {
      "name": "hk_pit_coverage_health",
      "report_file": "artifacts/runs/<run_dir>/quality/hk_pit_coverage_preflight.json"
    }
  ]
}
```

说明：

1. `overall_verdict` 是给 `snapshot` / `alloc-hk` 复用的统一 verdict；liveops 可在不重跑 inspection 的情况下，按新的 `--fail-on-quality` 阈值重新判定。
1. `checks[*].report_file` 是详细 JSON 报告；需要回看具体红灯项时，优先读它。

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

`summary.json -> split` 现在会额外区分原始 train 日期数和训练窗口裁剪后的实际 train 日期数：

```json
{
  "train_dates": 16,
  "train_dates_raw": 28,
  "test_dates": 8,
  "train_window": {"mode": "rolling", "size": 16, "unit": "dates", "applied": true}
}
```

说明：

1. `train_dates_raw` 是 purge/embargo 之后、但还没应用 `model.train_window` 时的训练日期数。
1. `train_dates` 是最终实际用于本轮主训练的日期数。

## 稳定性契约（给下游脚本）

稳定 contract（版本演进时尽量保持不变）：

1. `summary.json` 顶层固定键集合（`run/data/dataset/universe/label/split/eval/backtest/final_oos/positions/live/quality/fundamentals/industry/walk_forward`）。
1. 研究主链路内部 canonical 标的列是 `symbol`；新生成的 run artifacts / CLI 输出默认只写 `symbol`。
1. `csml build-hk-connect-universe` 和 `csml build-hk-daily-asset-universe` 新生成的 universe CSV 也默认只写 `symbol`，不再主动补 `ts_code` / `stock_ticker`。
1. 旧输入文件里的 `ts_code`、`stock_ticker`、`order_book_id` 仍会在读取时自动映射到 `symbol`。
1. 持仓主键列语义：`trade_date`、`entry_date`、`symbol`、`weight`、`signal`、`rank`、`side`。
1. `weight` 的解释取决于 `backtest.weighting`：`equal` 时等权，`signal` 时为信号 softmax 后的目标权重。
1. 若配置了 `backtest.group_col + max_names_per_group`，持仓文件会体现该分组上限约束；这属于组合层约束，不会改变 `eval` 里的 IC / quantile 指标。
1. `summary.json` 内记录的文件路径优先级高于固定文件名推断。

best-effort（可能为空、缺失或未产出文件）：

1. `final_oos` / `live` / `walk_forward` 子结构（取决于对应功能是否启用）。
1. `dataset.parquet`、`eval_scored.parquet`、`backtest_*.csv` 等产物（取决于配置与数据可用性）。
1. 任何依赖外部数据源补数/修订得到的统计值（同配置在不同日期可能变化）。

## 复现入口

如果你要复现、审计或把单个 run 交给下游系统，优先看同目录下这四类文件：

1. `summary.json`：机器可读总摘要，包含关键指标和各类输出文件路径。
1. `config.used.yml`：本次 run 实际生效配置；复现实验时优先读它，不要回退到原始模板猜测。
1. `inputs.lock.json`：运行时解析后的输入锁定，包括实际产物根目录、绝对输入路径、推断到的 source manifest，以及相对日期 / `latest` 这类 mutable 输入标记。
1. `latest.json`：仅在 live 输出场景写入，是一个 mutable 便利指针，不是长期审计入口；做发布、复现或归档时应落到具体 run 目录。

## run 目录文件索引（按生成条件）

| 文件 | 生成条件 | 主要用途 |
| --- | --- | --- |
| `summary.json` | 默认 | 机器可读总摘要，包含路径指针与关键指标 |
| `config.used.yml` | 默认 | 实际生效配置（复现优先读这个） |
| `inputs.lock.json` | 默认 | 运行时解析后的输入锁定；优先用于审输入路径、日期展开结果和 mutable 输入标记 |
| `run.log` | `eval.save_artifacts=true` 且未显式配置 `logging.file` | 本次 run 的默认本地日志 |
| `quality/hk_pit_coverage_preflight.json` | `quality.fail_on_severity!=none` 或 `quality.save_report=true` 且当前 config 命中受支持 preflight | 主流程前置质量报告，供 liveops / 审计复用 |
| `dropped_dates.csv` | 存在被 `min_symbols_per_date` 丢弃的日期时 | 排查样本不足与过滤影响 |
| `eval_scored.parquet` | `eval.save_artifacts=true` 且 `eval.save_scored_artifact=true` 且评估阶段成功 | `grid` 与二次分析复用 |
| `dataset.parquet` | `eval.save_artifacts=true` 且 `eval.save_dataset=true` | 冻结建模输入样本 |
| `ic_test.csv` / `ic_pearson_test.csv` | 默认 | 测试期 IC 时序 |
| `ic_train.csv` / `ic_pearson_train.csv` | `eval.report_train_ic=true` | 训练期对照 |
| `quantile_returns.csv` | 默认 | 分位数组合收益 |
| `turnover_eval.csv` | 默认 | 评估侧换手序列 |
| `backtest_net.csv` / `backtest_gross.csv` | `backtest.enabled=true` 且回测成功 | 净/毛收益序列 |
| `backtest_turnover.csv` / `backtest_periods.csv` | `backtest.enabled=true` 且回测成功 | 回测换手与周期收益 |
| `backtest_benchmark.csv` / `backtest_active.csv` | 配置了 `backtest.benchmark_symbol` 或 `backtest.benchmark_returns_file`，且数据可用 | 基准与主动收益 |
| `backtest_style_exposure.csv` / `backtest_industry_exposure.csv` | 生成了回测持仓且 panel 中存在可解析暴露列 | 风格与行业暴露时序 |
| `backtest_active_exposure_summary.csv` | 生成了回测暴露结果时 | 一行一个调仓期的主动暴露汇总宽表 |
| `positions_by_rebalance*.csv` / `positions_current*.csv` | 生成了持仓结果时 | 下游持仓消费/执行衔接 |
| `rebalance_diff*.csv` | 对应 `positions_current*.csv` 存在至少两期时 | 最新一期调仓差异 |
| `latest.json` | `live.enabled=true` 且 live 成功输出时 | 指向最新 live run 目录的 mutable 便利指针 |
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
| `weight` | 目标权重；`backtest.weighting=equal` 时等权，`signal` 时为信号 softmax 权重 |
| `signal` | 该标的预测信号值 |
| `rank` | 当期截面排序名次 |
| `side` | `long` 或 `short` |

补充：

1. 若启用了 `backtest.group_col + max_names_per_group`，这里展示的是应用分组上限约束后的最终持仓，不等于单纯的全市场前 `K` 名。

### `positions_current.csv` / `positions_current_live.csv`

只保留最新 `entry_date` 的那一组持仓，列结构与 `positions_by_rebalance` 一致。

兼容说明：

1. 项目研究主链路内部已经改为以 `symbol` 作为主字段。
1. 旧持仓文件如果仍是 `ts_code` / `stock_ticker` / `order_book_id`，CLI 读取时会自动兼容并规范到 `symbol`。
1. `csml holdings` / `csml alloc` 的导出 payload 也只保留 canonical `symbol`，不会把这些 legacy alias 列原样透传回输出。

### `positions_by_rebalance_oos.csv` / `positions_current_oos.csv`

仅在启用 `eval.final_oos` 且成功评估时输出，字段与主文件一致。

## 调仓差异文件

`rebalance_diff.csv`（以及 `_live` / `_oos` 版本）展示最新一期 vs 上一期的变化：

| 列名 | 说明 |
| --- | --- |
| `entry_date` / `entry_date_prev` | 当前与上一期入场日 |
| `symbol` / `side` | 标的与方向 |
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
1. 当你把 `data.price_col` 切到 `tr_close` 时，另一条价格列（通常是原始 `close`）会保留在 `extra_cols`，方便做口径对照。
1. 若 `backtest.execution` 需要额外价格/流动性列（例如 `open`、`amount`），这些列也会保留在 `extra_cols`，供 `eval_scored.parquet` 复用。
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

1. 先执行一次 base pipeline（会强制打开 `eval.save_scored_artifact=true` 产出 `eval_scored.parquet`）。
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

### `csml alloc-hk`

默认不写 run 目录内文件，除非显式传 `--out`。它消费的输入契约仍然是持仓文件 / holdings JSON 的稳定字段：

* `symbol`
* `weight`、`signal`、`rank`、`side`

单场景 `--format=xlsx` 时，`--out` 必填，且当前会写一个 3 sheet 工作簿：

* `分配`
* `汇总`
* `卖出信号`

多场景 `--format=xlsx` 时，会写一个场景工作簿：

* `场景总览`
* `<scenario_id>_分配`
* `<scenario_id>_汇总`
* `<scenario_id>_卖出`

该格式需要安装 `--extra liveops-hk`。

单场景 `--format=json` 时，顶层 payload 当前固定包含：

* `as_of`、`entry_date`、`pricing_date`
* `source`、`side`、`market`
* `requested_top_n`、`selected_n`
* `cash`、`allocation_method`、`require_stock_connect`
* `pricing_source`、`pricing_source_detail`
* `estimated_value`、`cash_left`、`total_gap_to_target`
* `summary`
* `allocations`
* `sell_signals`

多场景 `--format=json` 时，顶层 payload 会切换成场景矩阵结构，常用键包括：

* `mode=scenario_grid`
* `as_of`、`entry_date`
* `source`、`side`、`market`
* `scenario_capitals`
* `scenario_top_ns`
* `scenario_overview`
* `scenarios`

其中 `scenarios[]` 里的每个元素，仍然沿用单场景 payload 的字段约定，并额外包含：

* `scenario_id`
* `scenario_capital`
* `scenario_top_n`

多场景 `--format=csv` 时，当前输出 `scenario_overview` 的平面表，而不是逐标的 `allocations` 明细。

`allocations` 行级常用字段：

* `symbol`
* `name`、`side`、`rank`、`signal`、`weight`
* `order_book_id`
* `price`、`price_source`、`pricing_date`
* `round_lot`、`stock_connect`、`tradable`
* `target_value`
* `lots_base`、`lots_extra`、`lots`、`shares`
* `est_value`、`gap_to_target`、`gap_ratio`
* `pct_1y`、`z_1y`、`valuation`
* `overpriced_low`、`overpriced_high`、`overpriced_range`

`sell_signals` 行级常用字段：

* `symbol`
* `name`、`side`、`rank`、`signal`、`weight`
* `close_pre`
* `sell_trigger`、`extreme_trigger`
* `last_sell_signal_date`
* `pct_1y`、`z_1y`、`valuation`

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
1. 若需要公开分享，请另做一份不含 `artifacts/cache/` 的安全包。推荐只保留 `manifest.yml`、配置文件、`config.used.yml`、`inputs.lock.json`、汇总 CSV 和简短说明。

### 历史 run Release staging：`python -m csml.release_tools.package_runs`

如果你要把历史研究结果拆成可上传 GitHub Release 的独立包，建议用模块级打包流程，而不是直接复制整个 `artifacts/runs/`。

默认 staging 结构：

```text
<staged_root>/
  manifest.yml
  runs_summary.csv
  <run_dir>/
    manifest.yml
    summary.json
    config.used.yml
    inputs.lock.json
    positions_current.csv
    positions_by_rebalance.csv
    rebalance_diff.csv
    ic_*.csv
    quantile_returns*.csv
    backtest_*.csv
    feature_importance.csv
    walk_forward_*.csv
```

其中：

1. 根目录 `manifest.yml` 记录这次打包选中了哪些 run、来源目录、文件数和字节数汇总；如果当前目录可识别为 git 仓库，还会写入 `commit/branch/is_dirty`。
1. 默认 profile 是 `--profile light`：只打包轻量 run 结果，也就是 `summary.json`、`config.used.yml`、`inputs.lock.json`、持仓、关键评估/回测 CSV、`feature_importance.csv`、`walk_forward_*.csv` 等。
1. `--profile milestone` 会在 light 的基础上再带上 `eval_scored.parquet` 和 `dataset.parquet`。
1. `--profile full` 会直接归档整个 run 目录。
1. `--include-scored`、`--include-dataset`、`--include-full-run-dir` 仍然可用，但现在是对当前 profile 的显式追加覆盖。
1. root manifest 和每个 run 的 `manifest.yml` 都会写 `reproducibility.asset_references`：优先记录资产 `manifest.yml` 或 `*.manifest.yml` 的路径与 sha256；如果引用的是没有 manifest 的资产文件，则退化记录该文件本身的路径与 sha256。
1. `runs_summary.csv` 是对 staging root 再做一次 `summarize` 得到的索引表，方便先看再决定下载哪几个 run。

对应的上传入口是 `python -m csml.release_tools.release_runs`：

1. 它会把每个 `<run_dir>/` 分别打成一个 tar.gz。
1. 然后在同一个 GitHub Release tag 下上传多份 run asset。
1. 这条链路和 `python -m csml.release_tools.release_assets` 分开；前者是研究结果备份，后者是数据资产备份。

### 旧目录升级说明

当前仓库默认只使用 `artifacts/` 布局。

如果你是从旧版本目录升级过来，本地还保留旧目录，需要手动把这些目录搬到新布局：

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
1. `run.log`：默认本地运行日志；若配置了 `logging.file`，则以 `summary.json -> run.log_file` 为准。
1. `eval_scored.parquet`：评估样本打分明细（需 `eval.save_scored_artifact=true`）。
1. `ic_*.csv`、`quantile_returns.csv`、`backtest_*.csv`：指标时序数据。
1. `feature_importance.csv`：模型特征重要性。
1. `walk_forward_feature_importance.csv`：walk-forward 每个窗口的特征重要性明细。
1. `walk_forward_feature_stability.csv`：跨窗口稳定性统计（命中率/均值/方差等）。
