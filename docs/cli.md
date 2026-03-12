# CLI 参考

本页汇总 `csml` 的命令入口和高频参数。

阅读建议：

* 想按任务串起来执行时，先看 `docs/cookbook.md`
* 想看 HK selected 研究路线时，先看 `docs/playbooks/hk-selected.md`
* 想查配置键时，继续看 `docs/config.md`
* 想查输出文件时，继续看 `docs/outputs.md`

## 查看帮助

```bash
csml --help
csml <subcommand> --help
```

## 共享约定

### 配置入口

多数命令的 `--config` 支持两种写法：

* 内置别名：`default/cn/hk/us`
* 本地 YAML 路径：如 `config/hk.yml`

### run 定位

`holdings`、`snapshot`、`alloc` 这类命令常见三种定位方式：

* `--config`：按配置查最近一次对应 run
* `--run-dir`：直接指定 run 目录，优先级高于 `--config`
* `--positions-file`：`alloc` 可直接读取持仓 CSV

### `--as-of` 日期 token

`holdings`、`snapshot`、`alloc` 支持：

* `YYYYMMDD`
* `YYYY-MM-DD`
* `today`
* `t-1`
* `last_trading_day`
* `last_completed_trading_day`

`last_trading_day` 和 `last_completed_trading_day` 只有在能识别到 `provider=rqdata` 且有 `market` 上下文时，才会严格按交易日解析。否则会回退到自然日并输出 warning。

做自动化任务或复现实验时，优先使用绝对日期。

### 输出格式

`holdings`、`snapshot`、`alloc` 支持：

* `--format text|csv|json`
* `--out <path>`

不传 `--out` 时默认输出到 stdout。

### 脚本透传

`csml tushare verify-token`、`csml universe index-components`、`csml universe hk-connect` 会把部分参数原样转发到底层脚本。遇到边角参数时，以 `--help` 和脚本帮助输出为准。

## 1) `csml run`

用途：运行主流程，完成训练、评估、回测和产物落盘。

关键参数：

* `--config <path_or_alias>`：配置路径或内置别名。

典型输出：

* `artifacts/runs/<run_name>_<timestamp>_<hash>/summary.json`
* `artifacts/runs/<run_name>_<timestamp>_<hash>/config.used.yml`

示例：

```bash
csml run --config config/hk.yml
csml run --config hk
```

## 2) `csml grid`

用途：在同一份 `eval_scored.parquet` 上做 `Top-K × 成本 × buffer × weighting` 敏感性分析，不会为每个组合重训模型。

关键参数：

* `--config <path_or_alias>`：基础配置。
* `--top-k <values>`：可重复传，支持逗号分隔。
* `--cost-bps <values>`：可重复传，支持逗号分隔。
* `--buffer-exit <values>`：可重复传，支持逗号分隔。
* `--buffer-entry <values>`：可重复传，支持逗号分隔。
* `--weighting <values>`：可重复传，支持 `equal,signal`。
* `--output <csv_path>`：输出 CSV，默认 `artifacts/runs/grid_summary.csv`。
* `--run-name-prefix <prefix>`
* `--log-level <level>`

示例：

```bash
csml grid --config config/hk.yml --top-k 5,10 --cost-bps 15,25

csml grid \
  --config config/hk_selected__baseline.yml \
  --top-k 10,20 \
  --cost-bps 15,25,40 \
  --buffer-exit 8,10 \
  --buffer-entry 4,5 \
  --weighting equal,signal
```

## 3) `csml sweep-linear`

用途：批量生成 `ridge` / `elasticnet` 配置，执行 `run`，再自动 `summarize`。

关键参数：

* `--sweep-config <path>`：sweep YAML。CLI 参数会覆盖该文件。
* `--config <path_or_alias>`：基础配置，默认 `config/hk_selected__baseline.yml`。
* `--run-name-prefix <prefix>`
* `--sweeps-dir <dir>`
* `--tag <name>`
* `--runs-dir <dir>`：覆盖生成配置里的 `eval.output_dir`
* `--ridge-alpha <values>`
* `--elasticnet-alpha <values>`
* `--elasticnet-l1-ratio <values>`
* `--skip-ridge`
* `--skip-elasticnet`
* `--dry-run`
* `--continue-on-error`
* `--skip-summarize`
* `--summary-output <csv_path>`
* `--log-level <level>`

补充：

* 若仍写 `config/hk_selected.yml` 且文件不存在，会自动回退到 `config/hk_selected__baseline.yml` 并给 warning。
* 输出目录默认在 `artifacts/sweeps/<tag>/`。

示例：

```bash
csml sweep-linear --sweep-config config/sweeps/hk_selected__linear_a.yml

csml sweep-linear \
  --sweep-config config/sweeps/hk_selected__linear_a.yml \
  --tag hk_linear_a_debug \
  --dry-run
```

## 4) `csml summarize`

用途：聚合历史 run 的 `summary.json` 和 `config.used.yml`，输出对比表。

关键参数：

* `--runs-dir <dir>`：扫描目录，可重复传，默认 `artifacts/runs`
* `--output <csv_path>`：默认 `<first-runs-dir>/runs_summary.csv`
* `--run-name-prefix <prefix>`：可重复传，支持逗号分隔
* `--since <datetime>`：支持 `YYYYMMDD`、`YYYY-MM-DD`、`YYYYMMDD_HHMMSS`、`YYYY-MM-DDTHH:MM:SS`，也支持 `today`、`now`、`yesterday`、`t-1`
* `--latest-n <int>`
* `--short-sample-periods <int>`
* `--high-turnover-threshold <float>`
* `--score-drawdown-weight <float>`
* `--score-cost-weight <float>`
* `--exclude-flag-short-sample`
* `--exclude-flag-high-turnover`
* `--exclude-flag-negative-long-short`
* `--exclude-flag-relative-end-date`
* `--sort-by <timestamp|score|dsr>`
* `--log-level <level>`

`--sort-by score` 使用：

```text
score = backtest_sharpe
      - score_drawdown_weight * abs(backtest_max_drawdown)
      - score_cost_weight * backtest_avg_cost_drag
```

补充：

* 若 run 被识别成 `constant prediction` 或 `zero feature importance`，`score` 和 `dsr` 会留空，避免退化模型排到前面。

示例：

```bash
csml summarize --runs-dir artifacts/runs --output artifacts/runs/runs_summary.csv

csml summarize --runs-dir artifacts/runs --run-name-prefix hk_grid --latest-n 1

csml summarize \
  --runs-dir artifacts/runs \
  --exclude-flag-short-sample \
  --exclude-flag-high-turnover \
  --exclude-flag-relative-end-date \
  --sort-by score
```

## 5) `csml holdings`

用途：输出最近一次 run 的当前持仓。

关键参数：

* `--config <path_or_alias>`
* `--run-dir <dir>`
* `--top-k <int>`
* `--as-of <date_or_token>`
* `--source <auto|backtest|live>`，默认 `auto`
* `--format <text|csv|json>`
* `--out <path>`

补充：

* 持仓文件中的标的列兼容 `ts_code` 和 `stock_ticker`，推荐使用 `stock_ticker`。

示例：

```bash
csml holdings --config config/hk.yml --as-of t-1
csml holdings --run-dir artifacts/runs/<run_dir> --format csv --out artifacts/exports/positions/latest.csv
```

## 6) `csml snapshot`

用途：封装 `run + holdings`，适合 live 快照、定时任务和脚本调用。

关键参数：

* `--config <path_or_alias>`
* `--run-dir <dir>`
* `--as-of <date_or_token>`
* `--skip-run`
* `--top-k <int>`
* `--format <text|csv|json>`
* `--out <path>`

补充：

* 默认会先执行一次 `run`，再读取 live 持仓。
* `--config` 和 `--run-dir` 至少要提供一个。
* live 配置要求 `live.enabled=true` 且 `eval.save_artifacts=true`。
* 仓库里没有内置的 `config/hk_live.yml`。通常做法是从 `csml init-config --market hk` 导出的模板另存一份 live 配置。

示例：

```bash
csml snapshot --config config/hk_live.local.yml
csml snapshot --config config/hk_live.local.yml --skip-run --format json
```

## 7) `csml alloc`

用途：按最新持仓做 Top-N 等权分配，输出每只股票的买入手数或股数。

关键参数：

* `--config <path_or_alias>`
* `--run-dir <dir>`
* `--positions-file <csv>`
* `--top-k <int>`
* `--as-of <date_or_token>`
* `--source <auto|backtest|live>`，默认 `auto`
* `--side <long|short|all>`，默认 `long`
* `--top-n <int>`，默认 `20`
* `--cash <float>`，默认 `1000000`
* `--buffer-bps <float>`
* `--price-field <name>`，默认 `close`
* `--price-lookback-days <int>`，默认 `20`
* `--username <name>`
* `--password <password>`
* `--format <text|csv|json>`
* `--out <path>`

补充：

* 价格和 `round_lot` 依赖 RQData。
* `--positions-file` 中标的列兼容 `ts_code` 和 `stock_ticker`。

示例：

```bash
csml alloc --config config/hk_live.local.yml --source live --top-n 20 --cash 1000000

csml alloc --run-dir artifacts/runs/<run_dir> --source live --top-n 10 --format json --out artifacts/exports/alloc/top10.json

csml alloc --positions-file artifacts/runs/<run_dir>/positions_by_rebalance_live.csv --top-n 5
```

## 8) `csml backup-data`

用途：把当前本地缓存、PIT universe 和指定配置文件做一次私有快照，写到 `artifacts/snapshots/<name>/`。

关键参数：

* `--out-root <dir>`：快照根目录，默认 `artifacts/snapshots`
* `--name <snapshot_name>`：快照目录名；不传时自动用时间戳
* `--config <path>`：附带归档的配置文件，可重复传
* `--include-path <path>`：额外归档的文件或目录，可重复传
* `--no-cache`：不包含 `artifacts/cache/`
* `--no-universe`：不包含 `artifacts/assets/universe/`
* `--skip-missing`：缺失路径时跳过，不中断

补充：

* 这个命令只复制本地文件，不会联网或重新下载 provider 数据。
* 默认包含 `artifacts/cache/` 和 `artifacts/assets/universe/`。
* 快照目录里会生成 `manifest.yml`，记录来源路径、文件数、字节数和当前 git 信息（若仓库可识别）。
* 这份快照默认按私有备份设计。若仓库是公开仓库，不要把 `artifacts/cache/` 或其他 provider 原始数据直接上传到 GitHub Releases。
* 公开 release 更适合上传 `manifest.yml`、研究配置、`config.used.yml`、汇总 CSV 和说明文件。完整快照保留在本地磁盘、NAS 或对象存储。

示例：

```bash
csml backup-data \
  --name hk_frozen_20251231 \
  --config config/hk_selected__baseline.yml

csml backup-data \
  --name hk_eval_bundle \
  --config config/hk_selected__baseline_eval_sample.yml \
  --config config/hk_selected__baseline_eval_sample_ffill.yml \
  --include-path config/sweeps/hk_selected__eval_sample.yml \
  --include-path config/sweeps/hk_selected__eval_sample_ffill.yml

csml backup-data \
  --name hk_eval_bundle_public \
  --no-cache \
  --config config/hk_selected__baseline_eval_sample.yml \
  --config config/hk_selected__baseline_eval_sample_ffill.yml \
  --include-path artifacts/runs/hk_evalb_ridge_a30_grid_summary.csv
```

## 9) `csml migrate-artifacts`

用途：把旧布局的 `cache/`、`out/`、`data_assets/`、`data_mirror/` 迁移到 `artifacts/`。

关键参数：

* `--copy`：复制到新布局，保留旧目录
* `--force`：目标文件冲突时覆盖
* `--dry-run`：只显示将要迁移的路径，不执行修改

补充：

* 默认执行移动，不会重新下载 provider 数据。
* 会处理这些目录：`cache/`、`out/fundamentals/`、`data_assets/rqdata/`、`out/universe/`、`out/runs/`、`out/live_runs/`、`out/sweeps/`、`data_mirror/`。

示例：

```bash
csml migrate-artifacts --dry-run

csml migrate-artifacts

csml migrate-artifacts --copy
```

## 10) `csml rqdata info`

用途：初始化并显示 RQData 登录信息。

关键参数：

* `--config <path_or_alias>`
* `--username <name>`
* `--password <password>`

## 11) `csml rqdata quota`

用途：查询 RQData 配额。

关键参数：

* `--config <path_or_alias>`
* `--username <name>`
* `--password <password>`
* `--pretty`

## 12) `csml rqdata list-hk-financial-fields`

用途：列出港股财报镜像接口支持的字段名，便于准备 `--fields-file`。

关键参数：

* `--contains <token>`，按字段名子串过滤，可重复传
* `--limit <n>`
* `--out <path>`

补充：

* 该命令不拉取远端数据。
* 字段列表来自本地安装的 `rqdatac` / `rqdatac-hk` 元数据。

示例：

```bash
csml rqdata list-hk-financial-fields --contains profit --out artifacts/exports/hk_profit_fields.txt
```

## 13) `csml rqdata mirror-hk-pit-financials`

用途：按港股 symbol 集合拉取 PIT 三大表财报数据，输出项目无关的 `parquet + manifest` 资产目录。

关键参数：

* `--config <path_or_alias>`：用于 `rqdata.init`。当没有显式传 `--symbol/--symbols-file/--by-date-file` 时，也会拿配置里的 universe 解析 symbol。
* `--username <name>`
* `--password <password>`
* `--start-quarter <YYYYqN>`
* `--end-quarter <YYYYqN>`
* `--date <YYYYMMDD>`
* `--statements <latest|all>`
* `--field-profile <starter|full>`
* `--field <name>` 或 `--fields-file <path>`
* `--symbol <code>` / `--symbols-file <path>` / `--by-date-file <path>`
* `--batch-size <n>`
* `--out-root <path>`
* `--name <snapshot_name>`
* `--resume`
* `--skip-existing`
* `--max-attempts <n>`
* `--backoff-seconds <seconds>`
* `--max-backoff-seconds <seconds>`

补充：

* 默认输出到 `artifacts/assets/rqdata/hk/pit_financials/<snapshot>/`。
* 目录里会写 `manifest.yml`、`audit.csv`、`fields.txt`、`symbols.txt` 和 `data/<ts_code>.parquet`。
* 仓库内置了一份 starter 字段文件：`config/rqdata_assets/hk_financial_fields_starter.txt`。
* `--field-profile starter` 等价于仓库内置的 starter 字段集。
* `--field-profile full` 会读取本地安装的 `rqdatac` 元数据，把港股财务接口当前支持的全部字段都拉进来。
* 为了复现，建议显式传 `--date`，例如 `20260310`。
* 大范围下载时，优先固定 `--name` 并配合 `--resume` 使用。命令会跳过已存在的 symbol 文件，并把结果、失败和 quota 中断都写进 `audit.csv` 与 `manifest.yml`。
* 请求失败会按指数退避重试；如果识别到 quota 用尽，会保留当前进度并提前停止。

示例：

```bash
csml rqdata mirror-hk-pit-financials \
  --config config/hk_selected__baseline.yml \
  --name hk_selected_pit_2011_2025_latest \
  --fields-file config/rqdata_assets/hk_financial_fields_starter.txt \
  --start-quarter 2011q1 \
  --end-quarter 2025q4 \
  --date 20260310
```

更完整的 HK selected 研究流程见 `docs/playbooks/hk-selected.md`。

## 14) `csml rqdata mirror-hk-financial-details`

用途：拉取港股原始财报细分项目，输出项目无关的 `parquet + manifest` 资产目录。

关键参数：

* 参数结构与 `mirror-hk-pit-financials` 相同，也支持 `--resume`、`--skip-existing` 和重试参数
* 数据来源是 `rqdatac.hk.get_detailed_financial_items`

补充：

* 默认输出到 `artifacts/assets/rqdata/hk/financial_details/<snapshot>/`。
* 同样会写 `audit.csv`，便于区分 `written`、`missing_remote`、`failed` 和 `quota_blocked`。
* 这类数据通常比 PIT 宽表更大。第一次建议先用 `--statements latest`，并限制字段范围。

示例：

```bash
csml rqdata mirror-hk-financial-details \
  --symbol 00005.HK \
  --field revenue \
  --start-quarter 2024q1 \
  --end-quarter 2025q4 \
  --date 20260310
```

## 15) `csml rqdata build-hk-pit-fundamentals`

用途：把 `mirror-hk-pit-financials` 生成的资产目录整理成 pipeline 可直接读取的 `fundamentals.source=file` 文件。

关键参数：

* `--asset-dir <path>`：`mirror-hk-pit-financials` 的输出目录
* `--field-profile <starter|full>`：可选。和镜像命令共用字段 profile
* `--field <name>` 或 `--fields-file <path>`：可选。默认沿用资产目录 `manifest.yml` 里的字段列表
* `--out <path>`：可选。默认写到 `<asset-dir>/pipeline_fundamentals.parquet`
* `--source-universe-by-date <path>` + `--universe-by-date-out <path>`：可选。按已写入财报的 symbol 过滤一份研究用 PIT universe
* `--symbols-out <path>`：可选。额外写一份 symbol 列表，便于直接接到研究配置
* `--keep-meta`
* `--duplicate-policy <keep-last|error>`
* `--force`

补充：

* 输出文件至少包含 `trade_date`、`ts_code` 和选中的财报字段。
* 默认把 `trade_date` 写成财报披露日，也就是 `info_date`。
* 如果镜像资产用了 `--field-profile full`，这里可以改用 `--field-profile starter`、`--fields-file` 或少量 `--field`，先生成一份更窄的研究文件。
* 后续在 pipeline 里通常配合 `fundamentals.ffill=true` 使用，这样披露后的交易日会延续最近一版财报值。
* 命令会额外写一份 sidecar manifest：`<out>.manifest.yml`。
* 构建时会自动规范化旧资产里的脏列名，比如尾随空格字段；不需要手工修 parquet。

示例：

```bash
csml rqdata build-hk-pit-fundamentals \
  --asset-dir artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest \
  --source-universe-by-date artifacts/assets/universe/hk_connect_full_by_date.csv \
  --universe-by-date-out artifacts/assets/universe/hk_connect_full_research_by_date.csv \
  --symbols-out artifacts/assets/universe/hk_connect_full_research_symbols.txt \
  --out artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest/pipeline_fundamentals.parquet
```

## 16) `csml tushare verify-token`

用途：验证 TuShare token 是否可用。

补充：

* 推荐直接执行 `csml tushare verify-token`。
* 额外参数会转发到底层脚本。

## 17) `csml universe index-components`

用途：拉取指数成分并输出 symbols 文件，必要时生成 PIT 文件。

关键参数：

* 额外参数会转发到底层脚本 `fetch_index_components.py`
* 使用 `--by-date-out` 时，输出 CSV 包含 `trade_date`、`ts_code`、`stock_ticker`

示例：

```bash
csml universe index-components --index-code 000300.SH --month 202501
```

## 18) `csml universe hk-connect`

用途：构建港股通 PIT universe。

关键参数：

* `--config <path_or_alias>`
* 其余参数转发到底层脚本 `build_hk_connect_universe.py`

补充：

* by-date CSV 会同时包含 `ts_code` 和 `stock_ticker`。
* `top_quantile=0` 表示保留全部港股通候选。这个口径适合做全量资产镜像。
* 仓库提供了 `config/universe.hk_connect_full.yml`，用于生成更完整的历史港股通股票池文件。
* 场景化用法见 `docs/playbooks/hk-selected.md`。

示例：

```bash
csml universe hk-connect --config config/universe.hk_connect.yml --mode daily
```

## 19) `csml init-config`

用途：导出内置配置模板。

关键参数：

* `--market <default|cn|hk|us>`，默认 `default`
* `--out <path_or_dir>`
* `--force`

示例：

```bash
csml init-config --market hk --out config/
```
