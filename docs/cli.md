# CLI 参考

本页解决什么：`csml` 命令入口与高频参数速查。\
本页不解决什么：不展开研究流程与配置语义。\
适合谁：需要查命令和参数的读者。\
读完你会得到什么：按场景检索命令与参数的路径。\
相关页面：`docs/cookbook.md`、`docs/capabilities.md`、`docs/config.md`、`docs/outputs.md`

## 快速决策

| 场景 | 命令 |
|------|------|
| 跑主流程 | `csml run --config <>` |
| 汇总结果 | `csml summarize --runs-dir artifacts/runs` |
| 敏感性分析 | `csml grid --config <> --top-k 10,20` |
| 模型调参 | `csml tune --tune-config <>` |
| 线性模型搜索 | `csml sweep-linear --sweep-config <>` |
| 候选升主线检查 | `csml promotion-gate --config <>` |
| 固定分数组合层比较 | `csml construction-grid --config <>` |
| 特征证据生成 / 汇总 | `csml feature-evidence <mode> --config <>` |
| Benchmark 阶梯报告 | `csml benchmark-ladder --config <>` |
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

> `csml run --config default` 里的 `default` 是内置别名，`default` 当前指向 HK starter 模板，默认 `data.provider=rqdata`。第一次跑 `default` 或 `hk` 前，先安装 `uv sync --extra dev --extra rqdata`。
>
> 这些内置别名以及 `csml init-config` 都读取仓库根目录的 `configs/`。默认使用场景是源码 checkout 或包含 `configs/` 的导出源码目录。

### 产物根目录

下面这些命令支持 `--artifacts-root`，用于把默认产物根目录从仓库内的 `artifacts/` 挪到 repo 外路径：

- `csml run`
- `csml holdings`
- `csml snapshot`
- `csml alloc`
- `csml alloc-hk`
- `csml data catalog`
- `csml data materialize`
- `csml data query`

优先级：`--artifacts-root` > `CSML_ARTIFACTS_ROOT` > `paths.artifacts_root` > 默认 `artifacts/`。

说明：

- 它只改默认派生路径，不会覆盖你已经显式写死的 `eval.output_dir`、`data.cache_dir`、`fundamentals.file`、`--db-path`、`--out-root` 这类更具体的路径。
- 如果你只是想把 metadata catalog 或 standardized 输出单独改位置，也可以继续直接传 `--db-path`、`--summary-out`、`--out-root`、`--standardized-root`。

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
csml run --config configs/presets/hk_quarterly_pit_hybrid.yml --fail-on-quality warning
csml run --config configs/presets/hk.yml --artifacts-root /data/csml-artifacts
```

说明：

* `--fail-on-quality none|info|warning|error` 会覆盖配置里的 `quality.fail_on_severity`。
* 当前主流程 preflight 只接入“HK + RQData + 本地 PIT fundamentals file”场景；命中时会先跑一遍 PIT health gate，再决定是否继续训练。

### csml grid

Top-K × 成本 × buffer × weighting 敏感性分析。

```bash
csml grid --config configs/presets/hk.yml --top-k 5,10 --cost-bps 15,25
```

### csml tune

按 YAML 搜索空间批量生成 trial config、执行 pipeline、读取 `summary.json` 打分，并把 best trial 固化回 sweep 目录。

```bash
csml tune --tune-config configs/experiments/sweeps/hk_selected__xgb_regressor_tune_smoke.yml
csml tune --tune-config configs/experiments/sweeps/hk_selected__xgb_regressor_tune_smoke.yml --dry-run
```

说明：

* `--tune-config` 里需要提供 `base_config` 和 `search_space`。
* `search_space` 每一维都要给 `name` 和 `values`；如果是标量搜索，再额外给 `path`。
* `values` 既可以是简单标量，也可以是 `{label, value}` 或 `{label, overrides}` 这种组合覆盖。
* `--sampler grid|random` 决定是全量组合还是随机抽样；`random` 下可配 `--n-trials` 和 `--seed`。
* `objective` 段现在支持 `min_cv_ic_valid_folds`；当 monthly / 小样本研究里想把 `cv_ic` 可判分性纳入筛选时，可以要求 trial 至少有若干个有效 CV folds，否则该 trial 会保留结果行，但不参与 best trial 选择。
* `objective` 还会把 `eval_ic_ir`、`walk_forward_test_ic_mean`、`backtest_sharpe`、`drawdown`、`cost_drag` 和 `turnover` 的加权分量写入 `trial_results.csv` / `best_trial.json`，方便检查最佳 trial 到底靠哪一项胜出。
* v1 更适合扫 `model.params`、`model.sample_weight_*`、`model.train_window.*` 这类训练结构；Top-K / 成本 / buffer 这类 construction 敏感性仍优先用 `csml grid`。
* 默认会在 `artifacts/sweeps/<tag>/` 下写 `jobs.csv`、`trial_results.csv`、`best_trial.json`、`best_config.yml` 和 `runs_summary.csv`；传 `--skip-summarize` 或 `--dry-run` 时会跳过自动汇总。

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
csml summarize --runs-dir artifacts/runs --comparability-class direct --sort-by dsr
```

补充：

* 如果 run 目录里有 `inputs.lock.json`，`summarize` 会优先读取其中的 input provenance，而不是只看 `summary.json` / `config.used.yml`。
* 输出会新增 `comparability_class`、`comparability_reasons` 和 `provenance_cohort_key`，用来区分直接可比、带漂移风险和 provenance 不足的 run。
* `--comparability-class direct` 适合只保留 frozen lineage 足够明确、且没有 `latest` / 相对日期漂移信号的 run。
* 输出还会包含 cost-aware objective 的显式分量：`objective_component_eval_ic_ir`、`objective_component_walk_forward_test_ic_mean`、`objective_component_backtest_sharpe`、`objective_component_drawdown_penalty`、`objective_component_cost_drag_penalty`、`objective_component_turnover_penalty` 和 `objective_score`。
* 如果你想把高成本 run 直接从汇总里排除，可以用 `--high-cost-drag-threshold` 配合 `--exclude-flag-high-cost-drag`。

### csml promotion-gate

按固定 evidence / comparability / hard rejection / soft threshold 规则，判断 candidate 是否可以替换 baseline。

```bash
csml promotion-gate \
  --config configs/experiments/sweeps/hk_selected__research_protocol_promotion_gate.yml \
  --baseline-run artifacts/runs/<baseline_run_dir> \
  --candidate-run artifacts/runs/<candidate_run_dir>
```

输出：

* `promotion_status`: `promotable` / `reviewable` / `rejected` / `non-comparable`
* `comparability_mismatches`
* `missing_evidence`
* `hard_failures`
* `soft_failures`
* baseline / candidate 的主评估、walk-forward、final OOS、成本换手和 benchmark evidence

### csml construction-grid

从已有 `eval_scored.parquet` 和 `summary.json` 读取固定模型分数，对组合构建层做离线比较。它不会重新训练模型。

```bash
csml construction-grid \
  --config configs/experiments/sweeps/hk_selected__research_protocol_construction_grid.yml
```

适合比较：

* `top_k`
* `cost_bps`
* `buffer_exit` / `buffer_entry`
* `weighting`
* long-only / long-short
* score postprocess，例如 `neutralize`

### csml feature-evidence

特征证据工具有三个模式：

```bash
csml feature-evidence generate-ablation \
  --config configs/experiments/sweeps/hk_selected__research_protocol_feature_evidence.yml

csml feature-evidence summarize-ablation \
  --config configs/experiments/sweeps/hk_selected__research_protocol_feature_evidence.yml

csml feature-evidence permutation-importance \
  --config configs/experiments/sweeps/hk_selected__research_protocol_feature_evidence.yml
```

说明：

* `generate-ablation` 根据 `families` 写出 baseline 和 `minus_<family>` 配置，同时生成 `jobs.csv`。
* `summarize-ablation` 读取已跑完 run 的 `summary.json`，输出相对 baseline 的指标变化和 feature stability 摘要。
* `permutation-importance` 从已有 scored artifact 计算单特征 / feature family 的 profit proxy 和 permutation importance。

### csml benchmark-ladder

把同一条策略收益和多个 benchmark 收益并排比较。

```bash
csml benchmark-ladder \
  --config configs/experiments/sweeps/hk_selected__research_protocol_benchmark_ladder.yml
```

输出会标记每个 benchmark 的角色、来源、可比状态、active total return、IR、tracking error、beta、alpha、相关性，以及 attribution 文件是否存在。

### csml holdings

读取当前持仓。

```bash
csml holdings --config configs/presets/hk.yml --as-of t-1
csml holdings --run-dir artifacts/runs/<run_dir> --format csv
csml holdings --config configs/presets/hk.yml --as-of t-1 --artifacts-root /data/csml-artifacts
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
csml snapshot --run-dir artifacts/runs/<run_dir> --fail-on-quality warning
csml snapshot --config path/to/live.yml --artifacts-root /data/csml-artifacts
```

补充：

* 如果 run 的 `summary.json` 里已经有 `quality.preflight`，`snapshot` 会直接复用它。
* 显式传 `--fail-on-quality ...` 时，会按该阈值重新判定是否阻断；未显式传时，优先沿用 run summary 或 config 里的阈值。

### csml alloc

手数分配。

```bash
csml alloc --config path/to/live.yml --source live --top-n 20 --cash 1000000
csml alloc --config path/to/live.yml --source live --top-n 20 --cash 1000000 --artifacts-root /data/csml-artifacts
```

### csml alloc-hk

港股增强分配，适合把 `positions_current_live.csv` 或 `csml holdings --format json` 结果往执行前分析层推进。

```bash
csml alloc-hk --config path/to/live.yml --source live --top-n 20 --cash 1000000 --method custom
csml alloc-hk --positions-file artifacts/runs/<run_dir>/positions_current_live.csv --as-of 2026-03-20 --roll-window 252 --no-secondary-fill
csml alloc-hk --config path/to/live.yml --source live --top-n 20 --method custom --format xlsx --out artifacts/exports/alloc_hk.xlsx
csml alloc-hk --config path/to/live.yml --source live --scenario-capital 1000000,500000 --scenario-top-n 20,10 --method custom --format xlsx --out artifacts/exports/alloc_hk_grid.xlsx
csml alloc-hk --run-dir artifacts/runs/<run_dir> --fail-on-quality warning --format json
csml alloc-hk --config path/to/live.yml --source live --top-n 20 --method custom --artifacts-root /data/csml-artifacts
```

说明：

- 单场景时，`csv` 仍输出逐标的分配表。
- 多场景时，`csv` 会切换为场景总览表；完整明细优先用 `json` 或 `xlsx`。
- `--fail-on-quality` 的优先级高于 `quality.fail_on_severity`；如果 run summary 已经记录了 preflight verdict，`alloc-hk` 会直接复用，不会默认重跑。


## 数据管理命令

### csml backup-data

归档本地数据。

```bash
csml backup-data --name hk_frozen_20251231 --config configs/experiments/variants/hk_selected__xgb_regressor.yml
csml backup-data --preset hk_current --name hk_current_frozen_20260410 --no-cache
```

说明：

* 默认会复制 `artifacts/cache/`、`artifacts/assets/universe/`，再叠加 `--config` / `--include-path`。
* `--preset hk_current` 会额外读取 `artifacts/metadata/current_assets/hk_current.json`，把 contract 本身和其中声明的当前 HK 资产一起冻进 `artifacts/snapshots/<name>/`。
* `hk_current` preset 复制的是 contract 解析后的 resolved snapshot/file，不是单纯把 `latest` alias 当成最终审计依据。
* 这是本地私有冻结入口，不会重新向 provider 拉数；如果要跨机器共享，优先走 `python -m csml.release_tools.package_assets` / `release_assets`。

### csml data catalog

扫描产物根目录下 manifest-backed 资产，并写入 SQLite metadata catalog。

```bash
csml data catalog
csml data catalog --db-path artifacts/metadata/catalog.sqlite
csml data catalog --artifacts-root /data/csml-artifacts
```

默认输出：

* `artifacts/metadata/catalog.sqlite`
* `artifacts/metadata/catalog_summary.csv`

如果传了 `--artifacts-root`，默认值会跟着新根目录派生；显式传 `--db-path` / `--summary-out` 时以显式参数为准。

### csml data materialize

把 raw mirror 或派生平面文件物化成 analysis-ready 标准层。

```bash
csml data materialize --name hk_daily_panel --preset rqdata-daily --asset-dir artifacts/assets/rqdata/hk/daily/hk_all_daily_latest --frequency M
csml data materialize --name hk_pit_panel --preset pit-fundamentals --file artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest/pipeline_fundamentals.parquet
csml data materialize --name hk_daily_panel --preset rqdata-daily --asset-dir /data/csml-artifacts/assets/rqdata/hk/daily/hk_all_daily_latest --artifacts-root /data/csml-artifacts
```

说明：

* `rqdata-daily`、`pit-fundamentals`、`industry-labels` 这些 preset 现在默认按 canonical `symbol` 读取输入列。
* 历史文件如果还保留 `ts_code` / `stock_ticker` / `order_book_id`，会自动兼容并归一到 `symbol`；需要显式指定时也可以继续传 `--symbol-col ts_code`。

默认输出根目录：

* `artifacts/standardized/<market>/<dataset>/<name>/`

如果传了 `--artifacts-root`，默认输出根目录会跟着新根目录派生；显式传 `--out-root` 时以显式参数为准。

### csml data query

刷新 DuckDB 视图后直接查询标准层。首次使用前先安装：

```bash
uv sync --extra dev --extra duckdb
```

示例：

```bash
csml data query --sql "select symbol, trade_date, close from standardized.hk_daily_panel limit 5"
csml data query --sql-file queries/top_names.sql --format csv --out artifacts/metadata/top_names.csv
csml data query --sql "select count(*) from standardized.hk_daily_panel" --artifacts-root /data/csml-artifacts
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
csml rqdata build-hk-pit-fundamentals --asset-dir artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest --out artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest/pipeline_fundamentals.parquet --source-universe-by-date artifacts/assets/universe/hk_connect_full_by_date.csv --universe-by-date-out artifacts/assets/universe/hk_selected_pit_research_by_date.csv --max-latest-report-age-days 365
csml rqdata build-hk-pit-fundamentals --asset-dir artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest --out artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest/pipeline_fundamentals.parquet --source-universe-by-date artifacts/assets/universe/hk_connect_full_by_date.csv --universe-by-date-out artifacts/assets/universe/hk_selected_pit_research_by_date.csv --max-latest-report-age-days 365 --feature-age-config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_dense.yml --max-selected-feature-age-days 365
```

说明：

* `--source-universe-by-date` + `--universe-by-date-out` 会顺手派生一份 research-ready PIT universe。
* `--max-latest-report-age-days` 只作用在这份派生 universe 上：它会按每个 `trade_date` 回看该 symbol 当时最近一条 PIT 披露，超过阈值的 symbol-date 会被剔除。
* 这适合处理 “symbol 仍然有 PIT flat data，但最新披露已经过旧，不应该继续留在研究股票池里” 的场景。
* `--feature-age-config` + `--max-selected-feature-age-days` 会再按 config 的 PIT-backed selected features 做 as-of 检查：任一 selected feature 缺少 as-of 非空值，或最近非空值超过阈值，都会剔除对应 symbol-date。
* 这适合处理 “最新 PIT 行存在，但 config 需要的字段在最新行里长期为空” 的 provider coverage 场景。

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
* `--target-date` 不传时，会优先取 `--by-date-file` 或 `config research_universe.by_date_file` 里的最大日期；再没有时，回退到 `pipeline_fundamentals.parquet` 的最大 `trade_date`。
* `Health` 会统计 `symbols_with_all_selected_features_asof_target_date`、各字段 `age_days_*`、`rows_last_30d/90d/180d`、以及 `symbol_without_any_pit_row_before_target_date` 这类断档告警。
* PIT freshness 默认分两档：`>180d` 记为 `info`，`>365d` 才记为 `warning`。这样 7-8 个月的披露滞后仍然可见，但不会和明显失效的超老 PIT 行混在同一层告警里。
* `--symbols-file` 和 `--by-date-file` 只影响 `Health` section，不改变原有覆盖率 / trainable 计算口径。
* `--fail-on-severity none|info|warning|error` 可以把 health 检查升级成质量闸门；命中对应级别的问题时命令会非零退出。显式传这个参数时，即使没写 `--include-health`，也会自动启用 `Health` section。

### csml rqdata inspect-hk-asset-health

检查本地 HK 资产快照的最新日期覆盖率，以及目标交易日上字段是否为空、是否只能依赖前值补齐。

```bash
csml rqdata inspect-hk-asset-health --asset-dir artifacts/assets/rqdata/hk/valuation/hk_all_2000_20260331_valuation_full_market_latest
csml rqdata inspect-hk-asset-health --asset-dir artifacts/assets/rqdata/hk/valuation/hk_all_2000_20260331_valuation_full_market_latest --field pe_ratio_ttm --field pb_ratio_ttm --target-date 20260331 --format json --out artifacts/reports/hk_valuation_health_20260331.json
csml rqdata inspect-hk-asset-health --asset-dir artifacts/assets/rqdata/hk/valuation/hk_all_2000_20260331_valuation_full_market_latest --by-date-file artifacts/assets/universe/hk_selected_pit_research_by_date.csv --target-date 20260331
csml rqdata inspect-hk-asset-health --asset-dir artifacts/assets/rqdata/hk/daily/hk_all_daily_latest --target-date 20260401 --include-history --history-sample-limit 10 --format json --out artifacts/reports/hk_daily_health_20260401_full_history.json
csml rqdata inspect-hk-asset-health --asset-dir artifacts/assets/rqdata/hk/valuation/hk_all_2000_20260401_valuation_full_market_refetched_latest --daily-asset-dir artifacts/assets/rqdata/hk/daily/hk_all_2000_20260401_daily_clean_latest --target-date 20260401 --include-history --format json --out artifacts/reports/hk_valuation_health_20260401_with_daily_ref.json
```

说明：

* 默认优先用 `audit.csv` 的最新日期作为目标日；没有 `audit.csv` 时回退到 `manifest.yml` 里的查询日期，再回退到 parquet 扫描得到的最大日期。
* `--by-date-file` 会按目标日过滤研究 universe，只检查这一天实际会进入策略判断的 symbol；`--symbols-file` 则适合传入自定义观察名单。
* `missing_but_prior_nonnull` 表示目标日原始值为空、但更早日期有值；`unusable_but_prior_clean` 和 `ffill_age_days_*` 会进一步统计占位符 / `inf` / 非法值在回退后离目标日有多远。
* `placeholder_on_target_date`、`nonfinite_on_target_date`、`zero_on_target_date`、`is_constant_across_clean_values_on_target_date` 和 `symbol_duplicate_dates_in_asset_file` 用来补齐仅看 non-null 时抓不到的脏值、退化值、横截面常数和同一逻辑记录重复问题。大多数数据集默认按 `symbol + date` 去重；`dividends`、`southbound`、`industry_changes`、`shares` / `ex_factors`、`financial_details` 会自动改用各自更合理的事件 / 披露键。
* 对 `daily` 资产，命令还会额外检查 `high/low/open/close` 的价格逻辑关系，以及负成交量 / 负成交额。
* `sample_stale_symbols` 会列出没有覆盖到目标日的样本 symbol，适合快速判断是原始数据没补齐，还是个别 symbol 落后。
* `sample_missing_asset_file_details` 和 `audit_issue_groups` 会把 `audit.csv` 里的失败原因带出来，便于区分权限问题、quota 问题和单纯没有远端数据。
* 加上 `--include-history` 后，命令会额外扫描每个 parquet 的全历史，输出 `history` section；当前覆盖 `daily` 资产的价格边界异常、非正价格、负成交量、负成交额，以及 `valuation` 资产的连续 stale run，`--history-sample-limit` 控制样本行数量。
* 对 `valuation` 资产，如果同时传 `--daily-asset-dir`，历史 stale-run 检查会用本地 `daily close` 做去噪：只有在对应 run 期间 `close` 发生变化的常数段才继续报出来，长期停牌 / 无交易导致的平价常数段会被抑制。
* JSON 输出会额外给出统一的 `quality_verdict`；需要阻断时可用 `--fail-on-severity none|info|warning|error`。

### csml rqdata inspect-hk-current-health

轻量检查 `hk_current` contract 和当前 alias 是否整体对齐，不扫描大 parquet。

```bash
csml rqdata inspect-hk-current-health
csml rqdata inspect-hk-current-health --asset daily_clean --asset valuation --asset universe_meta --target-date 20260409 --format json --out artifacts/reports/hk_current_health_20260409.json
```

说明：

* 默认读取 `artifacts/metadata/current_assets/hk_current.json`；如果 contract 缺失，会回退到 `artifacts/` 下的默认 alias 路径继续检查，并把 `current_contract_missing` 记成质量问题。
* 它优先回答“current 是否整体对齐”，例如 alias 是否存在、manifest 状态是否健康、`as_of` 是否落后于目标日、`universe_meta` 的 `last_rebalance_date` 是否落后。
* 这条命令适合作为大范围 parquet 扫描前的第一道轻检查，尤其适合笔记本环境或 agent 上下文容易被大文件拖垮的场景。
* 命中 `--fail-on-severity` 时，命令会和其他 health 检查一样以非零退出。

### csml rqdata inspect-hk-data-assets

聚合检查 HK current 资产清单、ETF daily 起止覆盖、intraday 新鲜度、已有 health report、repair 候选项和保守 prune 计划。默认不刷新、不修复、不删除。

```bash
csml rqdata inspect-hk-data-assets --target-date 20260410 --format json --out artifacts/reports/hk_data_asset_audit_20260410.json
csml rqdata inspect-hk-data-assets --target-date 20260410 --intraday-mode metadata --fail-on-severity warning
csml rqdata inspect-hk-data-assets --target-date 20260410 --run-refresh --refresh-mode patch --refresh-dry-run --format json --out artifacts/reports/hk_data_asset_audit_20260410_refresh_dry_run.json
```

说明：

* 默认读取 `artifacts/metadata/current_assets/hk_current.json`；如果 contract 缺失，会回退到 `artifacts/` 下的默认 alias，并把证据写进 `inventory`。
* `inventory.records[]` 会把 current 引用、report / release 引用、manifest 状态和路径分类合并成统一清单；分类包括 `current`、`retained`、`unreferenced`、`metadata-inconsistent`。
* `freshness.etf_daily` 默认扫描 ETF daily parquet，检查是否从 2000-01-01 附近的首个交易日覆盖到 `--target-date`，并区分 `provider-boundary` 和 `local-gap`。
* `freshness.intraday` 默认用 manifest / contract 元数据判断最新日期；`--intraday-mode scan` 会扫描 intraday parquet，`--intraday-mode health` 会复用 `inspect-hk-intraday-health`，这两种模式都可能明显更重。
* `health` 会聚合 `artifacts/reports/` 下同一目标日的 current / daily / valuation / PIT / intraday / workflow report；预期 report 缺失会记为 warning，而不是静默忽略。
* `repair.candidates[]` 只生成候选和建议命令。只有同时传 `--execute-repair` 和对应的 `--approved-repair-action`，才会执行允许的自动修复动作。
* `prune.candidates[]` 是删除计划。默认只 dry-run；只有同时传 `--delete-prune-candidates` 和逐条 `--approved-prune-path`，才会删除候选路径。

### csml rqdata sync-hk-intraday

串起 HK `5m` 的常用维护路径：先下载本地 intraday cache，再跑健康检查，通过后把这批 cache 提升成正式 `intraday` 资产并更新 `hk_intraday_latest`；只有显式加 `--package` / `--release` 时，才继续做 tarball / GitHub Release。

```bash
csml rqdata sync-hk-intraday --symbols-file artifacts/assets/rqdata/hk/daily/hk_all_daily_latest/symbols.txt --start-date 20260402 --end-date 20260409 --resume
csml rqdata sync-hk-intraday --symbols-file artifacts/assets/rqdata/hk/daily/hk_all_daily_latest/symbols.txt --start-date 20260402 --end-date 20260409 --output artifacts/cache/intraday/hk_all_5m_20260402_20260409.parquet --inspect-fail-on-severity error
csml rqdata sync-hk-intraday --symbols-file artifacts/assets/rqdata/hk/daily/hk_all_daily_latest/symbols.txt --start-date 20260402 --end-date 20260409 --verify-full-asset --full-inspect-fail-on-severity none
csml rqdata sync-hk-intraday --symbols-file artifacts/assets/rqdata/hk/daily/hk_all_daily_latest/symbols.txt --start-date 20260402 --end-date 20260409 --output artifacts/cache/intraday/hk_all_5m_20260402_20260409.parquet --package
```

说明：

* 默认会依次执行 `download -> inspect(new patch only) -> build asset + alias`；其中 inspect 默认 gate 是 `warning`，命中后会停止，不会推进 `hk_intraday_latest`。
* `--resume` 会继续复用 `<output_stem>.parts/` 里已经存在的 batch parquet，适合 WSL / 长任务中断后续跑。
* `--skip-inspect` 允许你在确认风险的情况下直接推进正式资产层；否则建议保留默认检查。
* 整包 `hk_intraday_latest` 回扫默认不会执行；只有显式加 `--verify-full-asset` 才会在 alias 更新后扫描整包。这一步 I/O 很重，更适合单独后台跑。
* `--package` 会基于新 intraday snapshot 打一个仅含 `intraday` part 的 release stage 和 tarball；`--release` 会在此基础上继续调用 `gh release` 上传。
* `--package` / `--release` 仍复用 `package_assets` 的仓库级约束，所以它会要求当前 `daily` 和 `instruments` 基础快照可用。

### csml rqdata inspect-hk-intraday-health

检查本地 HK `5m` parquet 是否有重复时间戳、缺 bar、session bar count 异常、负成交量 / 成交额，以及和本地 `daily` 快照是否能对账。

```bash
csml rqdata inspect-hk-intraday-health --input artifacts/cache/intraday/hk_all_5m_20260327_20260401.parquet
csml rqdata inspect-hk-intraday-health --input artifacts/cache/intraday/hk_all_5m_20260327_20260401.parquet --daily-asset-dir artifacts/assets/rqdata/hk/daily/hk_all_daily_latest --format json --out artifacts/reports/hk_intraday_health_20260401.json
csml rqdata inspect-hk-intraday-health --input artifacts/assets/rqdata/hk/intraday/hk_intraday_latest --daily-asset-dir artifacts/assets/rqdata/hk/daily/hk_all_daily_latest
```

说明：

* `--input` 可以重复传多个 parquet、`.parts/` 目录、缓存目录，或正式的 `intraday` 资产目录；如果同名 `.parts/` 目录存在，命令会自动展开分片文件。
* HK `5m` 的默认 full-session bar 数是 `66`，命令会同时检查缺 bar、off-schedule bar 和 `bar_count != 66` 的 symbol-day。
* 传入 `--daily-asset-dir` 后，会把 intraday 聚合后的 `open/high/low/close/volume/amount` 和本地 daily parquet 对账，方便定位是 intraday 本身漏 bar，还是 daily / intraday 之间有不一致。
* 对账时，`close/volume/amount` 仍按严格数值比较；`open/high/low` 则会自动抑制一部分“close/volume/amount 已经对上、但只差轻微 tick / 集合竞价口径”的噪音 mismatch，真正留下来的 warning 会更偏向值得人工看的偏差。
* JSON 输出会额外给出统一的 `quality_verdict`；需要阻断时可用 `--fail-on-severity none|info|warning|error`。

### csml rqdata build-hk-intraday-asset

把本地 HK `5m` cache / parquet / `.parts` 目录打包成正式 `intraday` 资产层，方便下游长期复用；命令只复制本地文件，不会重新向 provider 拉数。

```bash
csml rqdata build-hk-intraday-asset --input artifacts/cache/intraday/hk_all_5m_20250327_20260326.parquet --name hk_all_5m_20250327_20260326_latest
csml rqdata build-hk-intraday-asset --input artifacts/cache/intraday --name hk_intraday_latest --alias artifacts/assets/rqdata/hk/intraday/hk_intraday_latest
```

说明：

* 输出目录固定落在 `artifacts/assets/rqdata/hk/intraday/<snapshot>/`，其中 `data/` 会保留原始 parquet、同名 `.meta.json`，以及同名 `.parts/` 分片目录。
* 默认是独立复制，不依赖源 `artifacts/cache/intraday/` 继续存在；因此清 cache 后，这层正式资产仍可直接给下游用。
* `manifest.yml` 会记录整体日期范围、字段、输入来源和每个 parquet block 的行数 / 字节数 / adjust_type / quota 元数据。
* 之后 `inspect-hk-intraday-health` 和 `python -m csml.research.hk_intraday_slippage_report` 都可以直接把这个资产目录当 `--input` 读取。

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
