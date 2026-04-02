# CLI 参考

本页解决什么：`csml` 命令入口与高频参数速查。
本页不解决什么：不展开研究流程与配置语义。
适合谁：需要查命令和参数的读者。
读完你会得到什么：按场景检索命令与参数的路径。
相关页面：`docs/cookbook.md`、`docs/capabilities.md`、`docs/config.md`、`docs/outputs.md`

## 快速决策

| 场景 | 命令 |
|------|------|
| 跑主流程 | `csml run --config <>` |
| 汇总结果 | `csml summarize --runs-dir artifacts/runs` |
| 敏感性分析 | `csml grid --config <> --top-k 10,20` |
| 线性模型搜索 | `csml sweep-linear --sweep-config <>` |
| 查看持仓 | `csml holdings --config <> --as-of t-1` |
| 生成快照 | `csml snapshot --config <live.yml>` |
| 手数分配 | `csml alloc --config <> --source live --top-n 20` |
| 港股增强分配 | `csml alloc-hk --config <> --source live --top-n 20 --method custom` |
| 导出模板 | `csml init-config --market default` |
| 构建 HK 全市场股票池 | `csml universe hk-daily-assets --config <> -- <args>` |
| 刷新数据 catalog | `csml data catalog` |
| 物化标准层 | `csml data materialize --name <> ...` |
| DuckDB 查询标准层 | `csml data query --sql <>` |

## 查看帮助

```bash
csml --help
csml <subcommand> --help
```

## 共享约定

### 配置入口

`--config` 支持：

- 内置别名：`default` / `hk`
- 本地 YAML 路径：`configs/presets/hk.yml`

> `csml run --config default` 里的 `default` 是内置别名，不等于 `configs/presets/default.yml`。
>
> `default` 当前指向 HK starter 模板，默认 `data.provider=rqdata`。第一次跑 `default` 或 `hk` 前，先安装 `uv sync --extra dev --extra rqdata`。
>
> 这些内置别名以及 `csml init-config` 都读取仓库根目录的 `configs/`。默认使用场景是源码 checkout 或包含 `configs/` 的导出源码目录。

### 日期 token

`holdings`、`snapshot`、`alloc`、`alloc-hk` 支持：

- `YYYYMMDD` / `YYYY-MM-DD`
- `today` / `t-1`
- `last_trading_day` / `last_completed_trading_day`

### 输出格式

`holdings`、`snapshot`、`alloc` 支持：`--format text|csv|json`

`alloc-hk` 额外支持：`--format xlsx`。该格式需要安装 `--extra liveops-hk`，并且必须显式传 `--out`。

`alloc-hk` 还支持场景矩阵参数：

- `--scenario-capital 1000000,500000`
- `--scenario-top-n 20,10`

两者都支持重复传入和逗号分隔；命令会按 `资金 × TopN` 做笛卡尔积。

### 透传参数

`csml universe ...` 会先解析 wrapper 自己的参数（例如 `--config`），再把其余参数透传给底层脚本。

需要传底层脚本参数时，建议显式加一个 `--` 分隔，例如：

```bash
csml universe hk-connect --config configs/presets/universe/hk_connect.yml -- --mode daily
```

## 主流程命令

### csml run

运行主流程。

```bash
csml run --config default
csml run --config hk
```

### csml grid

Top-K × 成本 × buffer × weighting 敏感性分析。

```bash
csml grid --config configs/presets/hk.yml --top-k 5,10 --cost-bps 15,25
```

### csml sweep-linear

批量生成 ridge / elasticnet 配置并汇总。

```bash
csml sweep-linear --sweep-config configs/experiments/sweeps/hk_selected__linear_a.yml
```

## 结果查看命令

### csml summarize

聚合历史 run。

```bash
csml summarize --runs-dir artifacts/runs --sort-by score
csml summarize --runs-dir artifacts/runs --run-name-prefix hk_grid --latest-n 1
```

### csml holdings

读取当前持仓。

```bash
csml holdings --config configs/presets/hk.yml --as-of t-1
csml holdings --run-dir artifacts/runs/<run_dir> --format csv
```

### csml snapshot

跑 live 快照。

规则先写清楚：

* 如果命令会触发 pipeline 运行，也就是 `csml snapshot --config ...` 且没有传 `--skip-run` / `--run-dir`，那么配置里必须显式写 `live.enabled=true`。
* 如果你只是想从已有 run 导出结果，优先用 `--run-dir` 或 `--skip-run`；这两种场景不要求重新跑 pipeline。

```bash
csml snapshot --config path/to/live.yml
csml snapshot --config path/to/live.yml --skip-run
csml snapshot --run-dir artifacts/runs/<run_dir>
```

### csml alloc

手数分配。

```bash
csml alloc --config path/to/live.yml --source live --top-n 20 --cash 1000000
```

### csml alloc-hk

港股增强分配，适合把 `positions_current_live.csv` 或 `csml holdings --format json` 结果往执行前分析层推进。

```bash
csml alloc-hk --config path/to/live.yml --source live --top-n 20 --cash 1000000 --method custom
csml alloc-hk --positions-file artifacts/runs/<run_dir>/positions_current_live.csv --as-of 2026-03-20 --roll-window 252 --no-secondary-fill
csml alloc-hk --config path/to/live.yml --source live --top-n 20 --method custom --format xlsx --out artifacts/exports/alloc_hk.xlsx
csml alloc-hk --config path/to/live.yml --source live --scenario-capital 1000000,500000 --scenario-top-n 20,10 --method custom --format xlsx --out artifacts/exports/alloc_hk_grid.xlsx
```

说明：

- 单场景时，`csv` 仍输出逐标的分配表。
- 多场景时，`csv` 会切换为场景总览表；完整明细优先用 `json` 或 `xlsx`。


## 数据管理命令

### csml backup-data

归档本地数据。

```bash
csml backup-data --name hk_frozen_20251231 --config configs/experiments/variants/hk_selected__xgb_regressor.yml
```

### csml data catalog

扫描 `artifacts/` 下 manifest-backed 资产，并写入 SQLite metadata catalog。

```bash
csml data catalog
csml data catalog --db-path artifacts/metadata/catalog.sqlite
```

默认输出：

* `artifacts/metadata/catalog.sqlite`
* `artifacts/metadata/catalog_summary.csv`

### csml data materialize

把 raw mirror 或派生平面文件物化成 analysis-ready 标准层。

```bash
csml data materialize --name hk_daily_panel --preset rqdata-daily --asset-dir artifacts/assets/rqdata/hk/daily/hk_all_daily_latest --frequency M
csml data materialize --name hk_pit_panel --preset pit-fundamentals --file artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest/pipeline_fundamentals.parquet
```

说明：

* `rqdata-daily`、`pit-fundamentals`、`industry-labels` 这些 preset 现在默认按 canonical `symbol` 读取输入列。
* 历史文件如果还保留 `ts_code` / `stock_ticker` / `order_book_id`，会自动兼容并归一到 `symbol`；需要显式指定时也可以继续传 `--symbol-col ts_code`。

默认输出根目录：

* `artifacts/standardized/<market>/<dataset>/<name>/`

### csml data query

刷新 DuckDB 视图后直接查询标准层。首次使用前先安装：

```bash
uv sync --extra dev --extra duckdb
```

示例：

```bash
csml data query --sql "select symbol, trade_date, close from standardized.hk_daily_panel limit 5"
csml data query --sql-file queries/top_names.sql --format csv --out artifacts/metadata/top_names.csv
```

## 配置模板命令

### csml init-config

导出仓库 preset 模板。

```bash
csml init-config --market default --out configs/
csml init-config --market hk --out ./custom_hk.yml --force
```

`init-config` 读取仓库根目录的 `configs/presets/`，所以默认使用场景也是源码 checkout 或包含 `configs/` 的导出源码目录。

## RQData 命令

### csml rqdata info

显示 RQData 登录信息。

### csml rqdata quota

查询 RQData 配额。

### csml rqdata list-hk-financial-fields

列出港股财报字段。

```bash
csml rqdata list-hk-financial-fields --contains profit
```

### csml rqdata export-hk-instruments

导出港股 instrument 元数据。

```bash
csml rqdata export-hk-instruments --out artifacts/assets/rqdata/hk/instruments/hk_all_instruments_latest.parquet
csml rqdata export-hk-instruments --instrument-type ETF --out artifacts/assets/rqdata/hk/instruments/hk_etf_instruments_latest.parquet
```

补充：

* `--instrument-type` 默认是 `CS`，也就是当前股票口径。
* 需要单独导出 ETF universe 时，可显式传 `--instrument-type ETF`。

### csml rqdata mirror-hk-daily

拉取港股日线数据。

```bash
csml rqdata mirror-hk-daily --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv --start-date 20000101 --end-date 20260311 --batch-size 50 --name hk_connect_full_2000_20260311_daily_latest
```

补充：

* `--batch-size` 默认是 `20`，表示每次 `rqdatac.get_price` 请求里包含多少个 `order_book_id`。
* 批量请求失败时，命令会自动拆回单 symbol 重试，便于继续完成大多数产物。

### csml rqdata mirror-hk-pit-financials

拉取 PIT 财报数据。

```bash
csml rqdata mirror-hk-pit-financials --name hk_selected_pit_2011_2025_latest --fields-file configs/field_profiles/hk_financial_fields_starter.txt --start-quarter 2011q1 --end-quarter 2025q4 --date 20260310
```

### csml rqdata mirror-hk-financial-details

拉取港股财报细项数据。

```bash
csml rqdata mirror-hk-financial-details --symbol 00005.HK --field revenue --start-quarter 2024q1 --end-quarter 2025q4
```

### csml rqdata mirror-hk-exchange-rate

拉取港币对外汇率历史。

```bash
csml rqdata mirror-hk-exchange-rate --start-date 20250210 --end-date 20250211 --name hk_exchange_rate_probe_20250210_20250211_minimal
```

### csml rqdata mirror-hk-ex-factors

拉取港股复权因子历史。

```bash
csml rqdata mirror-hk-ex-factors --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv --start-date 20100101 --end-date 20260317 --name hk_connect_ex_factors_latest
```

### csml rqdata mirror-hk-dividends

拉取港股分红历史。

```bash
csml rqdata mirror-hk-dividends --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv --start-date 20100101 --end-date 20260317 --name hk_connect_dividends_latest
```

### csml rqdata mirror-hk-shares

拉取港股股本历史。

```bash
csml rqdata mirror-hk-shares --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv --start-date 20100101 --end-date 20260317 --name hk_connect_shares_latest
```

### csml rqdata mirror-hk-valuation

拉取港股日频估值因子原始镜像，默认包含 `hk_total_market_val`、`pe_ratio_ttm`、`pb_ratio_ttm`。

```bash
csml rqdata mirror-hk-valuation --symbols-file artifacts/assets/rqdata/hk/daily/hk_all_daily_latest/symbols.txt --start-date 20000101 --end-date 20260324 --name hk_all_2000_20260324_valuation_full_market_latest --resume
```

### csml rqdata mirror-hk-announcement

拉取港股公司公告原始记录。

```bash
csml rqdata mirror-hk-announcement --symbols-file artifacts/assets/universe/hk_selected_pit_research_symbols.txt --start-date 20000101 --end-date 20260324 --name hk_selected_2000_20260324_announcement_latest
```

### csml rqdata mirror-hk-southbound

拉取港股通成分历史。

```bash
csml rqdata mirror-hk-southbound --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv --start-date 20141117 --end-date 20260318 --trading-type both --rebalance-frequency D --name hk_connect_southbound_latest
```

### csml rqdata mirror-hk-instrument-industry

拉取港股股票在若干快照日期上的行业分类。

```bash
csml rqdata mirror-hk-instrument-industry --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv --start-date 20100101 --end-date 20260318 --level 0 --rebalance-frequency M --name hk_connect_instrument_industry_latest
```

### csml rqdata mirror-hk-industry-changes

拉取港股行业纳入剔除区间，并按 symbol 落盘。

```bash
csml rqdata mirror-hk-industry-changes --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv --start-date 20100101 --end-date 20260318 --level 1 --mapping-date 20260318 --name hk_connect_industry_changes_latest
```

### csml rqdata build-hk-pit-fundamentals

构建 pipeline 可读的基本面文件。

```bash
csml rqdata build-hk-pit-fundamentals --asset-dir artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest --out artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest/pipeline_fundamentals.parquet
```

### csml rqdata build-hk-industry-labels

用本地 `industry_changes` 资产派生日频、月频或季频行业标签文件。

```bash
csml rqdata build-hk-industry-labels --asset-dir artifacts/assets/rqdata/hk/industry_changes/hk_all_industry_changes_latest --daily-asset-dir artifacts/assets/rqdata/hk/daily/hk_all_daily_latest --frequency M
csml rqdata build-hk-industry-labels --asset-dir artifacts/assets/rqdata/hk/industry_changes/hk_all_industry_changes_latest --daily-asset-dir artifacts/assets/rqdata/hk/daily/hk_all_daily_latest --frequency D
```

说明：

* `--daily-asset-dir` 适合派生严格全市场档案上的 `D/M/Q` 标签，会用本地日线镜像里的实际 `trade_date + symbol` 网格来落标签。
* `--source-universe-by-date` 适合对齐研究股票池；月频或季频文件会直接沿用该 universe 里的日期和 symbol 网格。
* `--frequency D|M|Q` 控制在源网格上怎么采样：`D` 保留全部日期，`M/Q` 保留每个 symbol 在当月或当季的最后一个交易日。
* 默认输出到 `<asset-dir>/industry_labels_<freq>.parquet`，并同时写 `<asset-dir>/industry_labels_<freq>.manifest.yml`。

### csml rqdata inspect-hk-pit-coverage

检查 PIT 覆盖率。

```bash
csml rqdata inspect-hk-pit-coverage --config configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml --mode both
csml rqdata inspect-hk-pit-coverage --config configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml --mode both --include-health --target-date 20260331
```

详见 `docs/concepts/pit-coverage.md`。

说明：

* 默认输出还是覆盖率 / trainability 体检；加上 `--include-health` 后，会额外输出 `Health` section，回答“到某个 `target_date` 为止，这份 `pipeline_fundamentals.parquet` 能不能安全前推到调仓日”。
* `--target-date` 不传时，会优先取 `--by-date-file` 或 `config universe.by_date_file` 里的最大日期；再没有时，回退到 `pipeline_fundamentals.parquet` 的最大 `trade_date`。
* `Health` 会统计 `symbols_with_all_selected_features_asof_target_date`、各字段 `age_days_*`、`rows_last_30d/90d/180d`、以及 `symbol_without_any_pit_row_before_target_date` 这类断档告警。
* `--symbols-file` 和 `--by-date-file` 只影响 `Health` section，不改变原有覆盖率 / trainable 计算口径。
* `--fail-on-severity none|info|warning|error` 可以把 health 检查升级成质量闸门；命中对应级别的问题时命令会非零退出。显式传这个参数时，即使没写 `--include-health`，也会自动启用 `Health` section。

### csml rqdata inspect-hk-asset-health

检查本地 HK 资产快照的最新日期覆盖率，以及目标交易日上字段是否为空、是否只能依赖前值补齐。

```bash
csml rqdata inspect-hk-asset-health --asset-dir artifacts/assets/rqdata/hk/valuation/hk_all_2000_20260331_valuation_full_market_latest
csml rqdata inspect-hk-asset-health --asset-dir artifacts/assets/rqdata/hk/valuation/hk_all_2000_20260331_valuation_full_market_latest --field pe_ratio_ttm --field pb_ratio_ttm --target-date 20260331 --format json --out artifacts/reports/hk_valuation_health_20260331.json
csml rqdata inspect-hk-asset-health --asset-dir artifacts/assets/rqdata/hk/valuation/hk_all_2000_20260331_valuation_full_market_latest --by-date-file artifacts/assets/universe/hk_selected_pit_research_by_date.csv --target-date 20260331
csml rqdata inspect-hk-asset-health --asset-dir artifacts/assets/rqdata/hk/daily/hk_all_daily_latest --target-date 20260401 --include-history --history-sample-limit 10 --format json --out artifacts/reports/hk_daily_health_20260401_full_history.json
```

说明：

* 默认优先用 `audit.csv` 的最新日期作为目标日；没有 `audit.csv` 时回退到 `manifest.yml` 里的查询日期，再回退到 parquet 扫描得到的最大日期。
* `--by-date-file` 会按目标日过滤研究 universe，只检查这一天实际会进入策略判断的 symbol；`--symbols-file` 则适合传入自定义观察名单。
* `missing_but_prior_nonnull` 表示目标日原始值为空、但更早日期有值；`unusable_but_prior_clean` 和 `ffill_age_days_*` 会进一步统计占位符 / `inf` / 非法值在回退后离目标日有多远。
* `placeholder_on_target_date`、`nonfinite_on_target_date`、`zero_on_target_date`、`is_constant_across_clean_values_on_target_date` 和 `symbol_duplicate_dates_in_asset_file` 用来补齐仅看 non-null 时抓不到的脏值、退化值、横截面常数和同一 `symbol-date` 重复行问题。
* 对 `daily` 资产，命令还会额外检查 `high/low/open/close` 的价格逻辑关系，以及负成交量 / 负成交额。
* `sample_stale_symbols` 会列出没有覆盖到目标日的样本 symbol，适合快速判断是原始数据没补齐，还是个别 symbol 落后。
* `sample_missing_asset_file_details` 和 `audit_issue_groups` 会把 `audit.csv` 里的失败原因带出来，便于区分权限问题、quota 问题和单纯没有远端数据。
* 加上 `--include-history` 后，命令会额外扫描每个 parquet 的全历史，输出 `history` section；当前覆盖 `daily` 资产的价格边界异常、非正价格、负成交量、负成交额，以及 `valuation` 资产的连续 stale run，`--history-sample-limit` 控制样本行数量。
* JSON 输出会额外给出统一的 `quality_verdict`；需要阻断时可用 `--fail-on-severity none|info|warning|error`。

### csml rqdata inspect-hk-intraday-health

检查本地 HK `5m` parquet 是否有重复时间戳、缺 bar、session bar count 异常、负成交量 / 成交额，以及和本地 `daily` 快照是否能对账。

```bash
csml rqdata inspect-hk-intraday-health --input artifacts/cache/intraday/hk_all_5m_20260327_20260401.parquet
csml rqdata inspect-hk-intraday-health --input artifacts/cache/intraday/hk_all_5m_20260327_20260401.parquet --daily-asset-dir artifacts/assets/rqdata/hk/daily/hk_all_daily_latest --format json --out artifacts/reports/hk_intraday_health_20260401.json
```

说明：

* `--input` 可以重复传多个 parquet；如果同名 `.parts/` 目录存在，命令会自动展开分片文件。
* HK `5m` 的默认 full-session bar 数是 `66`，命令会同时检查缺 bar、off-schedule bar 和 `bar_count != 66` 的 symbol-day。
* 传入 `--daily-asset-dir` 后，会把 intraday 聚合后的 `open/high/low/close/volume/amount` 和本地 daily parquet 对账，方便定位是 intraday 本身漏 bar，还是 daily / intraday 之间有不一致。
* JSON 输出会额外给出统一的 `quality_verdict`；需要阻断时可用 `--fail-on-severity none|info|warning|error`。

### csml rqdata build-hk-daily-clean-layer

在不改动原始日线镜像的前提下，构建一层保守的 HK `daily` clean snapshot。当前只处理规则明确的问题：`high/low` 边界不自洽、负成交量 / 负成交额，以及连续零价段。

```bash
csml rqdata build-hk-daily-clean-layer --asset-dir artifacts/assets/rqdata/hk/daily/hk_all_daily_latest --out-dir artifacts/assets/rqdata/hk/daily/hk_all_daily_clean_20260402 --alias artifacts/assets/rqdata/hk/daily/hk_all_daily_clean_latest
csml rqdata build-hk-daily-clean-layer --asset-dir artifacts/assets/rqdata/hk/daily/hk_all_daily_latest --out-dir artifacts/assets/rqdata/hk/daily/hk_all_daily_clean_20260402 --symbols-file artifacts/assets/rqdata/hk/daily/hk_all_daily_latest/symbols.txt --zero-price-min-run 10 --overwrite
csml rqdata build-hk-daily-clean-layer --asset-dir artifacts/assets/rqdata/hk/daily/hk_etf_daily_latest --out-dir artifacts/assets/rqdata/hk/daily/hk_etf_daily_clean_20260402 --instruments-file artifacts/assets/rqdata/hk/instruments/hk_etf_instruments_latest.parquet --etf-short-zero-max-run 2 --overwrite
```

说明：

* 原始 `asset-dir` 不会被改写；命令会在 `out-dir` 里写一个新的快照，未改动的 symbol 直接复用源文件，改动过的 symbol 才会重写 parquet。
* `price_bounds_fix` 只会把异常行的 `high` / `low` 收敛到该行 `OHLC` 的最大 / 最小值，不会改动 `open` / `close`。
* 连续零价段默认要求至少 `5` 根连续日线都满足 `open=high=low=close=0`；命令会把这段的 `OHLCV` 和 `total_turnover` 置空，避免把明显坏段继续喂给下游。
* ETF 快照如果能拿到 instruments metadata，会启用 second-pass：vanilla ETF 的短零价段默认允许再清到 `2` 连，杠杆 / 反向 / crypto / commodity 这类特殊产品不会被自动清洗，只会在 `cleaning_report.json` 里单独报出来。
* 负 `volume` / `total_turnover` 当前按保守策略置空，不会强行改成 `0`。
* 输出目录会额外写 `cleaning_report.json` 和 `cleaning_actions.csv`，方便追踪到底修了哪些 symbol、哪类规则各修了多少行。

## 股票池命令

### csml universe hk-connect

构建港股通 PIT universe。

```bash
csml universe hk-connect --config configs/presets/universe/hk_connect.yml -- --mode daily
```

### csml universe hk-daily-assets

用本地日线镜像构建 HK 全市场股票池。

```bash
csml universe hk-daily-assets --config configs/presets/universe/hk_all_assets.yml -- --end-date 20251231
```

## 相关文档

- 配置键：`docs/config.md`
- 输出文件：`docs/outputs.md`
- Cookbook：`docs/cookbook.md`
- 概念指南：`docs/concepts/`
