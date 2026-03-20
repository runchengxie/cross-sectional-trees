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
| 导出模板 | `csml init-config --market default` |
| 构建 HK 全市场股票池 | `csml universe hk-daily-assets --config <> -- <args>` |
| 刷新数据 catalog | `csml data catalog` |
| 物化标准层 | `csml data materialize --name <> ...` |
| DuckDB 查询标准层 | `csml data query --sql <>` |
| 验证 TuShare token | `csml tushare verify-token` |

## 查看帮助

```bash
csml --help
csml <subcommand> --help
```

## 共享约定

### 配置入口

`--config` 支持：

- 内置别名：`default` / `cn` / `hk` / `us`
- 本地 YAML 路径：`configs/presets/hk.yml`

> `csml run --config default` 里的 `default` 是内置别名，不等于 `configs/presets/default.yml`。
>
> `default` 当前指向 HK starter 模板，默认 `data.provider=rqdata`。第一次跑 `default` 或 `hk` 前，先安装 `uv sync --extra dev --extra rqdata`。

### 日期 token

`holdings`、`snapshot`、`alloc` 支持：

- `YYYYMMDD` / `YYYY-MM-DD`
- `today` / `t-1`
- `last_trading_day` / `last_completed_trading_day`

### 输出格式

`holdings`、`snapshot`、`alloc` 支持：`--format text|csv|json`

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

```bash
csml snapshot --config path/to/live.yml
```

### csml alloc

手数分配。

```bash
csml alloc --config path/to/live.yml --source live --top-n 20 --cash 1000000
```


## 数据管理命令

### csml backup-data

归档本地数据。

```bash
csml backup-data --name hk_frozen_20251231 --config configs/experiments/variants/hk_selected__xgb_regressor.yml
```

### csml migrate-artifacts

旧目录迁移。

```bash
csml migrate-artifacts --dry-run
csml migrate-artifacts
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

导出内置模板。

```bash
csml init-config --market default --out configs/
csml init-config --market hk --out ./custom_hk.yml --force
```

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
```

### csml rqdata mirror-hk-daily

拉取港股日线数据。

```bash
csml rqdata mirror-hk-daily --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv --start-date 20000101 --end-date 20260311 --name hk_connect_full_2000_20260311_daily_latest
```

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

* `--daily-asset-dir` 适合派生严格全市场档案上的 `D/M/Q` 标签，会用本地日线镜像里的实际 `trade_date + ts_code` 网格来落标签。
* `--source-universe-by-date` 适合对齐研究股票池；月频或季频文件会直接沿用该 universe 里的日期和 symbol 网格。
* `--frequency D|M|Q` 控制在源网格上怎么采样：`D` 保留全部日期，`M/Q` 保留每个 symbol 在当月或当季的最后一个交易日。
* 默认输出到 `<asset-dir>/industry_labels_<freq>.parquet`，并同时写 `<asset-dir>/industry_labels_<freq>.manifest.yml`。

### csml rqdata inspect-hk-pit-coverage

检查 PIT 覆盖率。

```bash
csml rqdata inspect-hk-pit-coverage --config configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml --mode both
```

详见 `docs/concepts/pit-coverage.md`。

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

### csml universe index-components

拉取指数成分。

```bash
csml universe index-components -- --index-code 000300.SH --month 202501
```

## TuShare 命令

### csml tushare verify-token

验证本地 `TUSHARE_TOKEN` / `TUSHARE_TOKEN_2` 是否可用。

```bash
csml tushare verify-token
```

## 相关文档

- 配置键：`docs/config.md`
- 输出文件：`docs/outputs.md`
- Cookbook：`docs/cookbook.md`
- 概念指南：`docs/concepts/`
