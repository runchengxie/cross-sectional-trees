# CLI 参考

本页解决什么：`csml` 命令入口与高频参数速查。
本页不解决什么：不展开研究流程与配置语义。
适合谁：需要查命令和参数的读者。
读完你会得到什么：按场景检索命令与参数的路径。
相关页面：`docs/cookbook.md`、`docs/config.md`、`docs/outputs.md`

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

---

## 查看帮助

```bash
csml --help
csml <subcommand> --help
```

---

## 共享约定

### 配置入口

`--config` 支持：

- 内置别名：`default` / `cn` / `hk` / `us`
- 本地 YAML 路径：`configs/presets/hk.yml`

> `csml run --config default` 里的 `default` 是内置别名，不等于 `configs/presets/default.yml`。

### 日期 token

`holdings`、`snapshot`、`alloc` 支持：

- `YYYYMMDD` / `YYYY-MM-DD`
- `today` / `t-1`
- `last_trading_day` / `last_completed_trading_day`

### 输出格式

`holdings`、`snapshot`、`alloc` 支持：`--format text|csv|json`

---

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

---

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
csml snapshot --config configs/local/hk_live.local.yml
```

### csml alloc

手数分配。

```bash
csml alloc --config configs/local/hk_live.local.yml --source live --top-n 20 --cash 1000000
```

---

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

---

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
csml rqdata export-hk-instruments --out artifacts/assets/rqdata/hk/instruments/hk_instruments_latest.parquet
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

### csml rqdata build-hk-pit-fundamentals

构建 pipeline 可读的基本面文件。

```bash
csml rqdata build-hk-pit-fundamentals --asset-dir artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest --out artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest/pipeline_fundamentals.parquet
```

### csml rqdata inspect-hk-pit-coverage

检查 PIT 覆盖率。

```bash
csml rqdata inspect-hk-pit-coverage --config configs/local/hk_sel_pit_q_core_hybrid_xgb_reg.yml --mode both
```

详见 `docs/concepts/pit-coverage.md`。

---

## 股票池命令

### csml universe hk-connect

构建港股通 PIT universe。

```bash
csml universe hk-connect --config configs/presets/universe/hk_connect.yml --mode daily
```

### csml universe index-components

拉取指数成分。

```bash
csml universe index-components --index-code 000300.SH --month 202501
```

### csml init-config

导出内置模板。

```bash
csml init-config --market default --out configs/
```

---

## 相关文档

- 配置键：`docs/config.md`
- 输出文件：`docs/outputs.md`
- Cookbook：`docs/cookbook.md`
- 概念指南：`docs/concepts/`
