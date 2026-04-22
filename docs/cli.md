# CLI 参考

本文档的核心目标：提供 `cstree` 命令入口与高频参数的速查参考。\
本文档的范围限制：仅涉及命令语法与参数说明，具体的研究流程与配置语义请参考相关文档。\
目标读者：需要查阅命令和参数的开发者或研究员。\
阅读收益：能够按不同使用场景快速定位对应的命令与参数路径。\
相关页面：`docs/cookbook.md`、`docs/capabilities.md`、`docs/config.md`、`docs/outputs.md`\

## 快速决策

| 使用场景 | 对应命令 |
|------|------|
| 运行主流程 | `cstree run --config <>` |
| 汇总运行结果 | `cstree summarize --runs-dir artifacts/runs` |
| 敏感性分析 | `cstree grid --config <> --top-k 10,20` |
| 模型调参 | `cstree tune --tune-config <>` |
| 线性模型搜索 | `cstree sweep-linear --sweep-config <>` |
| 候选策略升主线检查 | `cstree promotion-gate --config <>` |
| 固定分数组合层比较 | `cstree construction-grid --config <>` |
| 特征证据生成或汇总 | `cstree feature-evidence <mode> --config <>` |
| Benchmark 阶梯报告 | `cstree benchmark-ladder --config <>` |
| 查看持仓记录 | `cstree holdings --config <> --as-of t-1` |
| 生成实盘快照 | `cstree snapshot --config <live.yml>` |
| 手数分配计算 | `cstree alloc --config <> --source live --top-n 20` |
| 港股增强手数分配 | `cstree alloc-hk --config <> --source live --top-n 20 --method custom` |
| 导出配置模板 | `cstree init-config --market default` |
| 构建港股全市场股票池 | `cstree universe hk-daily-assets --config <> -- <args>` |
| 刷新数据目录（catalog） | `cstree data catalog` |
| 物化标准数据层 | `cstree data materialize --name <> ...` |
| 通过 DuckDB 查询标准层 | `cstree data query --sql <>` |

## 查看帮助信息

```bash
cstree --help
cstree <subcommand> --help
```

## 命令入口兼容

`cstree` 是当前推荐的 CLI 名称。旧入口 `csml` 仍作为兼容 alias 保留；`cstree` 通过桥接层委托到现有实现，命令语义与 `csml` 一致。新文档和脚本示例统一使用 `cstree`。

## 共享参数约定

### 配置入口

`--config` 参数支持以下输入：

- 内置别名：`default` 或 `hk`
- 本地 YAML 文件路径：例如 `configs/presets/hk.yml`

> 在命令 `cstree run --config default` 中，`default` 为内置别名，当前指向 HK starter 模板，且默认配置为 `data.provider=rqdata`。首次运行 `default` 或 `hk` 之前，请先执行 `uv sync --extra dev --extra rqdata` 安装相关依赖。
>
> 所有的内置别名以及 `cstree init-config` 命令均会读取仓库根目录下的 `configs/` 文件夹。其默认的适用场景为源码检出（checkout）环境，或包含了 `configs/` 文件夹的导出源码目录。

### 产物根目录

以下命令支持传入 `--artifacts-root` 参数，用于将默认的产物根目录从仓库内的 `artifacts/` 重新定向至仓库外的指定路径：

- `cstree run`
- `cstree holdings`
- `cstree snapshot`
- `cstree alloc`
- `cstree alloc-hk`
- `cstree data catalog`
- `cstree data materialize`
- `cstree data query`

优先级顺序：`--artifacts-root` 最高，其次为环境变量 `CSTREE_ARTIFACTS_ROOT`，再其次为兼容环境变量 `CSML_ARTIFACTS_ROOT`，再其次为配置文件中的 `paths.artifacts_root`，最后退回默认值 `artifacts/`。

说明：

- 该参数仅修改默认的派生基础路径。已经明确指定的具体路径（如 `eval.output_dir`、`data.cache_dir`、`fundamentals.file`、`--db-path`、`--out-root`）将保持不变。
- 若只需单独修改 metadata catalog 或 standardized 输出的位置，可继续直接传入 `--db-path`、`--summary-out`、`--out-root` 或 `--standardized-root` 参数。

### 日期 Token 解析

`holdings`、`snapshot`、`alloc` 和 `alloc-hk` 命令支持以下日期格式或占位符：

- 具体日期：`YYYYMMDD` 或 `YYYY-MM-DD`
- 相对日期：`today` 或 `t-1`
- 交易日标记：`last_trading_day` 或 `last_completed_trading_day`

### 输出格式控制

`holdings`、`snapshot` 和 `alloc` 命令支持 `--format text|csv|json`。

`alloc-hk` 额外支持 `--format xlsx`。要使用 Excel 格式，需提前安装依赖 `--extra liveops-hk`，并在命令中显式指定 `--out` 路径。

此外，`alloc-hk` 还支持场景矩阵参数：

- `--scenario-capital 1000000,500000`
- `--scenario-top-n 20,10`

这两个参数均支持重复传入或使用逗号分隔列表。命令执行时会按“资金规模 × TopN”的组合生成笛卡尔积。

### 透传参数机制

`cstree universe ...` 会优先解析封装层自身的参数（例如 `--config`），随后将剩余参数透传给底层执行脚本。

在传递底层脚本专属参数时，建议显式添加 `--` 作为分隔符。例如：

```bash
cstree universe hk-connect --config configs/presets/universe/hk_connect.yml -- --mode daily
```

## 主流程命令

### cstree run

运行策略主流程。

```bash
cstree run --config default
cstree run --config hk
cstree run --config configs/presets/hk_quarterly_pit_hybrid.yml --fail-on-quality warning
cstree run --config configs/presets/hk.yml --artifacts-root /data/csml-artifacts
```

说明：

- `--fail-on-quality none|info|warning|error` 会覆盖配置文件中的 `quality.fail_on_severity` 设定。
- 当前主流程的 preflight 检查仅接入了“HK + RQData + 本地 PIT fundamentals file”场景。命中该场景时，程序会首先执行 PIT 健康度门控检查（health gate），通过后方可继续训练。

### cstree grid

执行基于“Top-K × 成本 × buffer × weighting”的敏感性分析。

```bash
cstree grid --config configs/presets/hk.yml --top-k 5,10 --cost-bps 15,25
```

### cstree tune

根据 YAML 文件定义的搜索空间批量生成 trial 配置并执行 pipeline。运行完成后，读取 `summary.json` 进行打分，并将最优的 trial 固化回 sweep 目录。

```bash
cstree tune --tune-config configs/experiments/sweeps/hk_selected__xgb_regressor_tune_smoke.yml
cstree tune --tune-config configs/experiments/sweeps/hk_selected__xgb_regressor_tune_smoke.yml --dry-run
```

说明：

- `--tune-config` 对应的文件中必须提供 `base_config` 和 `search_space`。
- `search_space` 的每一个维度都需要提供 `name` 和 `values` 键。针对标量搜索维度，还需额外提供 `path`。
- `values` 支持简单标量列表，也支持类似 `{label, value}` 或 `{label, overrides}` 格式的组合覆盖配置。
- `--sampler grid|random` 决定搜索策略为全量遍历还是随机抽样。在 `random` 模式下可配置 `--n-trials` 和 `--seed`。
- `objective` 配置段目前支持 `min_cv_ic_valid_folds`。在月频或小样本研究中，若需将 `cv_ic` 可判分性作为筛选条件，可要求 trial 至少满足若干个有效 CV folds。未满足该条件的 trial 仍会保留结果记录，但将被排除在最佳 trial 评选之外。
- `objective` 还会将各维度的加权分量（包括 `eval_ic_ir`、`walk_forward_test_ic_mean`、`backtest_sharpe`、`drawdown`、`cost_drag` 和 `turnover`）写入 `trial_results.csv` 与 `best_trial.json`，便于核查最佳 trial 的获胜依据。
- 当前 v1 版本更适合搜索 `model.params`、`model.sample_weight_*` 和 `model.train_window.*` 等训练结构相关的参数。对于 Top-K、成本或 buffer 等构建层敏感性分析，请优先使用 `cstree grid`。
- 执行后，默认会在 `artifacts/sweeps/<tag>/` 目录下生成 `jobs.csv`、`trial_results.csv`、`best_trial.json`、`best_config.yml` 和 `runs_summary.csv`。使用 `--skip-summarize` 或 `--dry-run` 会跳过自动汇总步骤。

### cstree sweep-linear

批量生成基于 ridge 或 elasticnet 的模型配置并执行汇总。

```bash
cstree sweep-linear --sweep-config configs/experiments/sweeps/hk_selected__linear_a.yml
```

## 结果查看命令

### cstree summarize

聚合历史运行记录（runs）。

```bash
cstree summarize --runs-dir artifacts/runs --sort-by score
cstree summarize --runs-dir artifacts/runs --run-name-prefix hk_grid --latest-n 1
cstree summarize --runs-dir artifacts/runs --comparability-class direct --sort-by dsr
```

补充说明：

- 当 run 目录中存在 `inputs.lock.json` 时，`summarize` 会优先读取其中的 input provenance 信息。以此提供更准确的溯源数据，从而替代单纯依赖 `summary.json` 或 `config.used.yml` 获取信息的做法。
- 输出结果中将新增 `comparability_class`、`comparability_reasons` 和 `provenance_cohort_key` 字段，以区分直接可比、带有漂移风险以及 provenance 记录不足的运行结果。
- `--comparability-class direct` 参数适用于仅保留 frozen lineage 非常明确，且不存在 `latest` 或相对日期漂移信号的运行记录。
- 汇总输出将包含 cost-aware objective 的详细分量字段：`objective_component_eval_ic_ir`、`objective_component_walk_forward_test_ic_mean`、`objective_component_backtest_sharpe`、`objective_component_drawdown_penalty`、`objective_component_cost_drag_penalty`、`objective_component_turnover_penalty` 以及总分 `objective_score`。
- 借由 `--high-cost-drag-threshold` 结合 `--exclude-flag-high-cost-drag` 参数，可以直接将高成本拖累的运行结果从汇总表里剔除。

### cstree promotion-gate

基于设定的 evidence、comparability、hard rejection 以及 soft threshold 规则，自动判断候选策略（candidate）是否满足替换基线策略（baseline）的条件。

```bash
cstree promotion-gate \
  --config configs/experiments/sweeps/hk_selected__research_protocol_promotion_gate.yml \
  --baseline-run artifacts/runs/<baseline_run_dir> \
  --candidate-run artifacts/runs/<candidate_run_dir>
```

输出字段：

- `promotion_status`：包含 `promotable`（可晋升）、`reviewable`（需人工审核）、`rejected`（已拒绝）或 `non-comparable`（不可比）。
- `comparability_mismatches`
- `missing_evidence`
- `hard_failures`
- `soft_failures`
- 同时对比 baseline 和 candidate 双方的主评估指标、步进验证（walk-forward）、最终样本外（final OOS）表现、成本换手率以及 benchmark 证据。

### cstree construction-grid

读取已有的 `eval_scored.parquet` 与 `summary.json` 获取固定模型分数，并在离线状态下执行组合构建层的比较分析。本命令不会触发模型重新训练。

```bash
cstree construction-grid \
  --config configs/experiments/sweeps/hk_selected__research_protocol_construction_grid.yml
```

适用场景：

比较不同的组合配置，例如：
- `top_k`
- `cost_bps`
- `buffer_exit` / `buffer_entry`
- `weighting`
- 做多（long-only）或多空组合（long-short）
- 评分后处理逻辑（如 `neutralize`）

### cstree feature-evidence

特征证据分析工具，目前支持三种模式：

```bash
cstree feature-evidence generate-ablation \
  --config configs/experiments/sweeps/hk_selected__research_protocol_feature_evidence.yml

cstree feature-evidence summarize-ablation \
  --config configs/experiments/sweeps/hk_selected__research_protocol_feature_evidence.yml

cstree feature-evidence permutation-importance \
  --config configs/experiments/sweeps/hk_selected__research_protocol_feature_evidence.yml
```

说明：

- `generate-ablation`：依据配置文件中的 `families` 列表，自动生成 baseline 以及各项 `minus_<family>` 实验配置，并同步输出 `jobs.csv` 调度列表。
- `summarize-ablation`：读取所有已完成消融实验的 `summary.json` 文件，输出相对于 baseline 的各项指标变化以及特征稳定性的分析摘要。
- `permutation-importance`：利用已有的 scored artifact 数据集，直接计算单一特征或 feature family 的 profit proxy 及排列重要性（permutation importance）。

### cstree benchmark-ladder

将同一条策略的收益与多个 benchmark 收益进行并排比较。

```bash
cstree benchmark-ladder \
  --config configs/experiments/sweeps/hk_selected__research_protocol_benchmark_ladder.yml
```

输出内容：

系统将逐一标记每个 benchmark 的角色、数据来源、可比状态，并计算主动总回报（active total return）、信息比率（IR）、跟踪误差（tracking error）、beta、alpha 以及相关性。同时也会检查对应的归因文件是否存在。

### cstree holdings

读取目标运行结果或当前策略的持仓。

```bash
cstree holdings --config configs/presets/hk.yml --as-of t-1
cstree holdings --run-dir artifacts/runs/<run_dir> --format csv
cstree holdings --config configs/presets/hk.yml --as-of t-1 --artifacts-root /data/csml-artifacts
```

### cstree snapshot

执行实盘快照生成。

前置规则：

- 若命令将触发 pipeline 运行（即执行 `cstree snapshot --config ...` 且未提供 `--skip-run` 或 `--run-dir` 参数），配置中必须显式设置 `live.enabled=true`。
- 若需从已有的 run 导出结果，请优先使用 `--run-dir` 或 `--skip-run`。这两种场景无需重新运行 pipeline。

```bash
cstree snapshot --config path/to/live.yml
cstree snapshot --config path/to/live.yml --skip-run
cstree snapshot --run-dir artifacts/runs/<run_dir>
cstree snapshot --run-dir artifacts/runs/<run_dir> --fail-on-quality warning
cstree snapshot --config path/to/live.yml --artifacts-root /data/csml-artifacts
```

补充说明：

- 若指定的 run 内存在 `summary.json` 且已记录 `quality.preflight` 信息，`snapshot` 将直接复用该记录。
- 当显式传入 `--fail-on-quality ...` 参数时，系统将依指定的阈值重新判断是否阻断流程；如果未提供此参数，将沿用 run summary 或 config 文件中的原始阈值。

### cstree alloc

手数分配工具。

```bash
cstree alloc --config path/to/live.yml --source live --top-n 20 --cash 1000000
cstree alloc --config path/to/live.yml --source live --top-n 20 --cash 1000000 --artifacts-root /data/csml-artifacts
```

### cstree alloc-hk

港股专用的增强型手数分配工具，适合将 `positions_current_live.csv` 或 `cstree holdings --format json` 输出的结果导入执行前分析层。

```bash
cstree alloc-hk --config path/to/live.yml --source live --top-n 20 --cash 1000000 --method custom
cstree alloc-hk --positions-file artifacts/runs/<run_dir>/positions_current_live.csv --as-of 2026-03-20 --roll-window 252 --no-secondary-fill
cstree alloc-hk --config path/to/live.yml --source live --top-n 20 --method custom --format xlsx --out artifacts/exports/alloc_hk.xlsx
cstree alloc-hk --config path/to/live.yml --source live --scenario-capital 1000000,500000 --scenario-top-n 20,10 --method custom --format xlsx --out artifacts/exports/alloc_hk_grid.xlsx
cstree alloc-hk --run-dir artifacts/runs/<run_dir> --fail-on-quality warning --format json
cstree alloc-hk --config path/to/live.yml --source live --top-n 20 --method custom --artifacts-root /data/csml-artifacts
```

说明：

- 在单场景分析中，`csv` 格式将继续输出逐笔标的的分配明细表。
- 在多场景分析中，`csv` 会退化为场景总览表；如需查看完整明细，请改用 `json` 或 `xlsx` 格式。
- `--fail-on-quality` 参数的优先级高于配置文件中的 `quality.fail_on_severity`。若 run summary 已经记录了 preflight 检查结论，`alloc-hk` 会直接读取复用，免去重复运行的开销。

## 数据管理命令

### cstree backup-data

归档本地数据环境。

```bash
cstree backup-data --name hk_frozen_20251231 --config configs/experiments/variants/hk_selected__xgb_regressor.yml
cstree backup-data --preset hk_current --name hk_current_frozen_20260410 --no-cache
```

说明：

- 默认行为是复制 `artifacts/cache/` 与 `artifacts/assets/universe/`，并依据传入的 `--config` 或 `--include-path` 叠加特定内容。
- 使用 `--preset hk_current` 时，工具将额外读取 `artifacts/metadata/current_assets/hk_current.json` 文件。系统会将 contract 自身及其引用的 HK 资产合并冻结到 `artifacts/snapshots/<name>/` 目录下。
- `hk_current` preset 复制的内容为 contract 解析后的 resolved snapshot 或 file，它绕过了单纯的 `latest` 别名，确保获取真实的依赖快照作为最终审计依据。
- 该工具提供的是本地私有数据冻结方案，执行时不会向 provider 重新请求数据。如需跨机器共享，推荐使用 `python -m cstree.release_tools.package_assets` 或 `release_assets` 等发行脚本。

### cstree data catalog

扫描产物根目录下的 manifest 资产，并将信息登记至 SQLite 格式的 metadata catalog 中。

```bash
cstree data catalog
cstree data catalog --db-path artifacts/metadata/catalog.sqlite
cstree data catalog --artifacts-root /data/csml-artifacts
```

默认输出路径：

- `artifacts/metadata/catalog.sqlite`
- `artifacts/metadata/catalog_summary.csv`

如果传入了 `--artifacts-root`，默认输出路径将随之变更；如果显式传入了 `--db-path` 或 `--summary-out` 参数，则以显式参数指定的路径为准。

### cstree data materialize

将原始镜像（raw mirror）或派生的平面文件物化为可供分析查询的标准数据层（analysis-ready standardized layer）。

```bash
cstree data materialize --name hk_daily_panel --preset rqdata-daily --asset-dir artifacts/assets/rqdata/hk/daily/hk_all_daily_latest --frequency M
cstree data materialize --name hk_pit_panel --preset pit-fundamentals --file artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest/pipeline_fundamentals.parquet
cstree data materialize --name hk_daily_panel --preset rqdata-daily --asset-dir /data/csml-artifacts/assets/rqdata/hk/daily/hk_all_daily_latest --artifacts-root /data/csml-artifacts
```

说明：

- `rqdata-daily`、`pit-fundamentals`、`industry-labels` 等预设配置，现已默认以标准的 `symbol` 列读取数据。
- 历史文件中若依然使用 `ts_code`、`stock_ticker` 或 `order_book_id` 命名列，物化过程将自动兼容并将其归一化为 `symbol`。如有特殊情况，也可以继续传入 `--symbol-col ts_code` 指定具体列名。

默认输出根目录：

- `artifacts/standardized/<market>/<dataset>/<name>/`

当提供 `--artifacts-root` 参数时，默认输出根目录将同步变更；显式传入 `--out-root` 时以显式参数为准。

### cstree data query

借助 DuckDB 引擎查询已物化的标准数据层。首次使用前请先安装 DuckDB 依赖：

```bash
uv sync --extra dev --extra duckdb
```

示例操作：

```bash
cstree data query --sql "select symbol, trade_date, close from standardized.hk_daily_panel limit 5"
cstree data query --sql-file queries/top_names.sql --format csv --out artifacts/metadata/top_names.csv
cstree data query --sql "select count(*) from standardized.hk_daily_panel" --artifacts-root /data/csml-artifacts
```

## 配置模板命令

### cstree init-config

导出仓库内置的 preset 模板文件。

```bash
cstree init-config --market default --out configs/
cstree init-config --market hk --out ./custom_hk.yml --force
```

`init-config` 工具从仓库根目录下的 `configs/presets/` 读取模板内容，因此推荐在源码检出环境或具备完整 `configs/` 结构的项目目录中使用。

## RQData 命令

### cstree rqdata info

打印并验证当前 RQData 的登录认证信息。

### cstree rqdata quota

查询当前账号的 RQData 额度使用状况。

### cstree rqdata list-hk-financial-fields

列出港股相关的财务报表可用字段。

```bash
cstree rqdata list-hk-financial-fields --contains profit
```

### cstree rqdata export-hk-instruments

导出港股市场的 instrument 元数据信息。

```bash
cstree rqdata export-hk-instruments --out artifacts/assets/rqdata/hk/instruments/hk_all_instruments_latest.parquet
cstree rqdata export-hk-instruments --instrument-type ETF --out artifacts/assets/rqdata/hk/instruments/hk_etf_instruments_latest.parquet
```

补充说明：

- `--instrument-type` 的默认值为 `CS`（Common Stock），代表当前口径仅包含普通股票。
- 如需单独导出 ETF 股票池，请显式传入参数 `--instrument-type ETF`。

### cstree rqdata mirror-hk-daily

拉取港股日线行情数据镜像。

```bash
cstree rqdata mirror-hk-daily --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv --start-date 20000101 --end-date 20260311 --batch-size 50 --name hk_connect_full_2000_20260311_daily_latest
```

补充说明：

- `--batch-size` 参数默认值为 `20`，用于控制每次 `rqdatac.get_price` 请求中合并的 `order_book_id` 数量。
- 遇网络波动导致批量请求失败时，命令会自动降级为单 symbol 请求重试，确保大部分正常产物顺利落盘。

### cstree rqdata mirror-hk-pit-financials

拉取基于 PIT（Point-in-Time）模式的财报数据。

```bash
cstree rqdata mirror-hk-pit-financials --name hk_selected_pit_2011_2025_latest --fields-file configs/field_profiles/hk_financial_fields_starter.txt --start-quarter 2011q1 --end-quarter 2025q4 --date 20260310
```

### cstree rqdata mirror-hk-financial-details

拉取港股财务报表的细项数据明细。

```bash
cstree rqdata mirror-hk-financial-details --symbol 00005.HK --field revenue --start-quarter 2024q1 --end-quarter 2025q4
```

### cstree rqdata mirror-hk-exchange-rate

获取港币对其他货币的历史汇率数据。

```bash
cstree rqdata mirror-hk-exchange-rate --start-date 20250210 --end-date 20250211 --name hk_exchange_rate_probe_20250210_20250211_minimal
```

### cstree rqdata mirror-hk-ex-factors

拉取港股的历史复权因子。

```bash
cstree rqdata mirror-hk-ex-factors --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv --start-date 20100101 --end-date 20260317 --name hk_connect_ex_factors_latest
```

### cstree rqdata mirror-hk-dividends

拉取港股历史分红记录。

```bash
cstree rqdata mirror-hk-dividends --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv --start-date 20100101 --end-date 20260317 --name hk_connect_dividends_latest
```

### cstree rqdata mirror-hk-shares

拉取港股公司的历史股本变动数据。

```bash
cstree rqdata mirror-hk-shares --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv --start-date 20100101 --end-date 20260317 --name hk_connect_shares_latest
```

### cstree rqdata mirror-hk-valuation

拉取港股日频估值因子的原始镜像数据。默认拉取的因子包括：`hk_total_market_val`、`pe_ratio_ttm` 以及 `pb_ratio_ttm`。

```bash
cstree rqdata mirror-hk-valuation --symbols-file artifacts/assets/rqdata/hk/daily/hk_all_daily_latest/symbols.txt --start-date 20000101 --end-date 20260324 --name hk_all_2000_20260324_valuation_full_market_latest --resume
```

### cstree rqdata mirror-hk-announcement

拉取港股上市公司的公告原始记录。

```bash
cstree rqdata mirror-hk-announcement --symbols-file artifacts/assets/universe/hk_selected_pit_research_symbols.txt --start-date 20000101 --end-date 20260324 --name hk_selected_2000_20260324_announcement_latest
```

### cstree rqdata mirror-hk-southbound

获取港股通成分股的历史变更记录。

```bash
cstree rqdata mirror-hk-southbound --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv --start-date 20141117 --end-date 20260318 --trading-type both --rebalance-frequency D --name hk_connect_southbound_latest
```

### cstree rqdata mirror-hk-instrument-industry

拉取港股在不同快照日期下的行业分类数据。

```bash
cstree rqdata mirror-hk-instrument-industry --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv --start-date 20100101 --end-date 20260318 --level 0 --rebalance-frequency M --name hk_connect_instrument_industry_latest
```

### cstree rqdata mirror-hk-industry-changes

拉取港股行业类别的成分纳入与剔除区间，并按 symbol 进行存储。

```bash
cstree rqdata mirror-hk-industry-changes --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv --start-date 20100101 --end-date 20260318 --level 1 --mapping-date 20260318 --name hk_connect_industry_changes_latest
```

### cstree rqdata build-hk-pit-fundamentals

整合基本面数据，构建能够被 pipeline 顺利读取的分析文件。

```bash
cstree rqdata build-hk-pit-fundamentals --asset-dir artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest --out artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest/pipeline_fundamentals.parquet
cstree rqdata build-hk-pit-fundamentals --asset-dir artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest --out artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest/pipeline_fundamentals.parquet --source-universe-by-date artifacts/assets/universe/hk_connect_full_by_date.csv --universe-by-date-out artifacts/assets/universe/hk_selected_pit_research_by_date.csv --max-latest-report-age-days 365
cstree rqdata build-hk-pit-fundamentals --asset-dir artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest --out artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest/pipeline_fundamentals.parquet --source-universe-by-date artifacts/assets/universe/hk_connect_full_by_date.csv --universe-by-date-out artifacts/assets/universe/hk_selected_pit_research_by_date.csv --max-latest-report-age-days 365 --feature-age-config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_dense.yml --max-selected-feature-age-days 365
```

说明：

- 配合 `--source-universe-by-date` 和 `--universe-by-date-out` 参数执行时，会自动派生一份适合研究环境读取的 PIT 股票池文件（universe）。
- `--max-latest-report-age-days` 参数仅约束派生的股票池：系统将遍历每一个交易日（`trade_date`），并检查每只股票的最新 PIT 披露时间。若间隔天数超出设定阈值，则将对应的 `symbol-date` 从池中剔除。这主要用于处理“股票存在平面 PIT 数据，但披露记录陈旧，不再适合放入研究池”的问题。
- 借助 `--feature-age-config` 及 `--max-selected-feature-age-days` 参数，命令可进一步读取配置中要求的 PIT 特定特征，执行“数据新鲜度”二次筛查。如果目标特征完全缺失，或最新的非空记录天数超出设定上限，该记录同样会被清理。这有效应对了“最新财报行已存在，但关键字段长期处于空值”的场景。

### cstree rqdata build-hk-industry-labels

利用本地的 `industry_changes` 资产，派生日频、月频或季频的行业标签数据集。

```bash
cstree rqdata build-hk-industry-labels --asset-dir artifacts/assets/rqdata/hk/industry_changes/hk_all_industry_changes_latest --daily-asset-dir artifacts/assets/rqdata/hk/daily/hk_all_daily_latest --frequency M
cstree rqdata build-hk-industry-labels --asset-dir artifacts/assets/rqdata/hk/industry_changes/hk_all_industry_changes_latest --daily-asset-dir artifacts/assets/rqdata/hk/daily/hk_all_daily_latest --frequency D
```

说明：

- 使用 `--daily-asset-dir` 时，将基于本地日线镜像的实际 `trade_date + symbol` 网格派生面向全市场的 `D/M/Q` 标签。
- 使用 `--source-universe-by-date` 时，将沿用指定的股票池网格派生标签，适用于对齐特定的研究资产池。
- `--frequency D|M|Q` 控制对源网格的采样频率。`D` 保留全量日期，而 `M/Q` 将截取每只股票在当月或当季末最后一个交易日的数据。
- 最终产物默认输出至 `<asset-dir>/industry_labels_<freq>.parquet`，并配套生成同名 manifest 文件。

### cstree rqdata inspect-hk-pit-coverage

审查 PIT 数据的覆盖质量。

```bash
cstree rqdata inspect-hk-pit-coverage --config configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml --mode both
cstree rqdata inspect-hk-pit-coverage --config configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml --mode both --include-health --target-date 20260331
```

相关细节可参阅 `docs/concepts/pit-coverage.md`。

说明：

- 默认仅输出基于训练集的覆盖率及可用性诊断。如果添加了 `--include-health` 参数，报告中将补充一段 `Health` 内容，用以解答“截至 `target_date` 日期，这份 `pipeline_fundamentals.parquet` 是否安全，能否顺延至后续调仓日”。
- 若不提供 `--target-date` 参数，系统优先采用 `--by-date-file` 或配置文件中 `research_universe.by_date_file` 提供的数据范围上限；若两处皆未声明，则回退为 parquet 文件扫描所得的最大日期。
- `Health` 环节将排查是否存在断档风险。诊断范围包括全量覆盖情况统计、各字段新鲜度统计（`age_days_*`）、最近 30/90/180 天落盘频率以及完全无数据的 symbol 列举。
- 鉴于财报披露的固有滞后特征，PIT 新鲜度检查采用分段告警策略：陈旧超过 `180` 天标记为 `info`，超过 `365` 天才升级为 `warning`。从而避免将正常的周期延迟与失效的陈旧数据混为一谈。
- 引入的 `--symbols-file` 和 `--by-date-file` 过滤器仅作用于 `Health` 环节，不干涉历史覆盖率或可训练数据的统计口径。
- 使用 `--fail-on-severity none|info|warning|error` 参数可将体检报告提升为严格的质量拦截器，遇到相应级别的质量问题即刻触发非零退出。只要显式附带该参数，无论是否补充了 `--include-health`，命令内部都会自动激活 `Health` 诊断环节。

### cstree rqdata inspect-hk-asset-health

全面体检本地港股资产快照，重点考察最新日期的覆盖度。主要排查指标包括：目标交易日字段是否缺失，以及是否过度依赖前序值的顺延填充。

```bash
cstree rqdata inspect-hk-asset-health --asset-dir artifacts/assets/rqdata/hk/valuation/hk_all_2000_20260331_valuation_full_market_latest
cstree rqdata inspect-hk-asset-health --asset-dir artifacts/assets/rqdata/hk/valuation/hk_all_2000_20260331_valuation_full_market_latest --field pe_ratio_ttm --field pb_ratio_ttm --target-date 20260331 --format json --out artifacts/reports/hk_valuation_health_20260331.json
cstree rqdata inspect-hk-asset-health --asset-dir artifacts/assets/rqdata/hk/valuation/hk_all_2000_20260331_valuation_full_market_latest --by-date-file artifacts/assets/universe/hk_selected_pit_research_by_date.csv --target-date 20260331
cstree rqdata inspect-hk-asset-health --asset-dir artifacts/assets/rqdata/hk/daily/hk_all_daily_latest --target-date 20260401 --include-history --history-sample-limit 10 --format json --out artifacts/reports/hk_daily_health_20260401_full_history.json
cstree rqdata inspect-hk-asset-health --asset-dir artifacts/assets/rqdata/hk/valuation/hk_all_2000_20260401_valuation_full_market_refetched_latest --daily-asset-dir artifacts/assets/rqdata/hk/daily/hk_all_2000_20260401_daily_clean_latest --target-date 20260401 --include-history --format json --out artifacts/reports/hk_valuation_health_20260401_with_daily_ref.json
```

说明：

- 日期解析优先提取 `audit.csv` 中的最新日期设定目标日。若无此文件，依次降级使用 `manifest.yml` 声明的查询日期或 parquet 解析后的最大交易日。
- `--by-date-file` 支持按照目标日期筛选研究池成分，将焦点对准当日真正需进入策略检验的标的。而 `--symbols-file` 专用于观察自定义的特定标的列表。
- 诊断结果中的 `missing_but_prior_nonnull` 指代目标日当天源数据为空但历史时段存在可用数值的情形。与之相配合，`unusable_but_prior_clean` 与 `ffill_age_days_*` 会量化追溯非空数据时的回退步长，以衡量占位符及失效常量的影响。
- 命令中集成了诸多精细的退化检查特征（如 `placeholder_on_target_date`、`nonfinite_on_target_date`、`zero_on_target_date` 等），旨在甄别常规非空判断无法揭露的脏数据、横截面常数化及同日逻辑去重异常等情况。多数数据集遵循 `symbol + date` 模式去重。针对 `dividends`、`southbound`、`industry_changes` 或 `financial_details` 这类复杂资产，程序内置了更贴切的复合主键去重逻辑。
- 对针对 `daily` 类型的量价资产，系统会增加特定的逻辑校验，比如识别 `high/low/open/close` 边界的非自洽冲突以及负成交量、负成交额异常。
- `sample_stale_symbols` 清单重点曝光覆盖不到目标日落后标的，帮助排查是因为原始数据池缺失，还是单纯的更新滞后。
- 诊断记录包含对 `audit.csv` 失败日志的挖掘，辅助操作者区分这是由于权限、流量限额问题造成的阻断，还是远端数据源本身的缺失。
- 加入 `--include-history` 开关后，系统会启动历史扫描回溯功能。例如，深挖日线价量矛盾、零负价差、以及长周期常数值固化等隐藏问题。可通过 `--history-sample-limit` 灵活配置采样展示的数量规模。
- 当分析 `valuation` 类资产并绑定了 `--daily-asset-dir` 时，系统将引用本地日线收盘价展开辅助验证：若发现收盘价未发生活动，系统即会智能静默连续的估值停滞警告，由此过滤掉因长期停牌或无交易引发的平价固化噪音。
- `json` 格式报告的尾部总揽中带有高度集成的 `quality_verdict` 评分体系；结合 `--fail-on-severity none|info|warning|error` 参数控制运行退出状态。

### cstree rqdata inspect-hk-current-health

执行一项轻量化的健康校验，旨在核对 `hk_current` contract 与当前的别名引用是否在宏观尺度上达成对齐，跳过庞大的 parquet 文件扫描。

```bash
cstree rqdata inspect-hk-current-health
cstree rqdata inspect-hk-current-health --asset daily_clean --asset valuation --asset universe_meta --target-date 20260409 --format json --out artifacts/reports/hk_current_health_20260409.json
```

说明：

- 程序首先尝试读取 `artifacts/metadata/current_assets/hk_current.json`。若该 contract 文档不存在，系统会将视线转向 `artifacts/` 目录下的默认别名，并随即把 `current_contract_missing` 作为诊断瑕疵计入考核结果。
- 本工具致力于提供快速反馈。评估内容涵盖别名连接是否有效、manifest 元信息的完整性、核心更新截面 `as_of` 以及 `last_rebalance_date` 是否已明显落后于目标日期。
- 相较于深度检查，它极为适合作为海量数据校验前的第一道哨卡，特别是能够化解本地受限设备或代理运行环节下因处理庞大资产而引发的卡顿。
- 一旦质量瑕疵突破了 `--fail-on-severity` 设立的底线，程序同样会以非零状态报错终止。

### cstree rqdata inspect-hk-data-assets

全方位汇集梳理 HK current 资产库。检查范围覆盖 ETF 的全日线连续度、intraday 数据新鲜度、各个已有的 health report 日志、自动维护候选项以及稳健的旧资源清理计划。默认执行只读检查，不做刷新、修复和清理。

```bash
cstree rqdata inspect-hk-data-assets --target-date 20260410 --format json --out artifacts/reports/hk_data_asset_audit_20260410.json
cstree rqdata inspect-hk-data-assets --target-date 20260410 --intraday-mode metadata --fail-on-severity warning
cstree rqdata inspect-hk-data-assets --target-date 20260410 --run-refresh --refresh-mode patch --refresh-dry-run --format json --out artifacts/reports/hk_data_asset_audit_20260410_refresh_dry_run.json
```

说明：

- 程序首选读取 `artifacts/metadata/current_assets/hk_current.json` 作为依赖参照物；一旦缺失，将退回到 `artifacts/` 主节点中进行线索追溯，并将证据保留在生成的 `inventory` 文档中。
- 生成的 `inventory.records[]` 矩阵会汇总所有 current 引用、报表、release 快照以及各自的分类归属。资产池的状态标签会被划分为：`current`、`retained`、`unreferenced` 或是存在冲突的 `metadata-inconsistent`。
- `freshness.etf_daily` 扫描器将专门盯防 ETF 数据列：确保其覆盖从创设初段（如 2000 年代）直至当前的 `--target-date` 窗口，同时精确切割出提供商空隙（`provider-boundary`）和本地遗漏（`local-gap`）两类问题。
- `freshness.intraday` 默认使用清单合同校验其最大日期。需要高频扫描时可开启 `--intraday-mode scan`；更重度的体检可启用 `--intraday-mode health` 挂载执行 `inspect-hk-intraday-health` 逻辑。
- `health` 聚合面板会归档同一目标日下包括 current / daily / valuation / PIT / intraday 等在内的工作流日志。日志未能如期生成的现象会被定义为警告，而非被程序静默过滤。
- `repair.candidates[]` 提供的是系统建议。仅在参数中成对提供 `--execute-repair` 及其对应的 `--approved-repair-action` 指令后，系统才会落实建议自动修复错误。
- 规划阶段产生的 `prune.candidates[]` 均为虚拟试运行指令。必须附带 `--delete-prune-candidates` 参数且明确出具 `--approved-prune-path` 认可意见后，废弃数据的真实删除操作才会落地。

### cstree rqdata sync-hk-intraday

贯穿执行港股 `5m` 分钟线的一站式维护通道：首先将 intraday 数据下载并暂存到缓存层，紧接调用深度数据检查；放行后自动将缓存提升为正式 intraday 快照资产，并刷新 `hk_intraday_latest` 别名；如有更进一步的归档需求，须显式引入 `--package` 或 `--release` 开关完成 tarball 压缩和 GitHub 发行。

```bash
cstree rqdata sync-hk-intraday --symbols-file artifacts/assets/rqdata/hk/daily/hk_all_daily_latest/symbols.txt --start-date 20260402 --end-date 20260409 --resume
cstree rqdata sync-hk-intraday --symbols-file artifacts/assets/rqdata/hk/daily/hk_all_daily_latest/symbols.txt --start-date 20260402 --end-date 20260409 --output artifacts/cache/intraday/hk_all_5m_20260402_20260409.parquet --inspect-fail-on-severity error
cstree rqdata sync-hk-intraday --symbols-file artifacts/assets/rqdata/hk/daily/hk_all_daily_latest/symbols.txt --start-date 20260402 --end-date 20260409 --verify-full-asset --full-inspect-fail-on-severity none
cstree rqdata sync-hk-intraday --symbols-file artifacts/assets/rqdata/hk/daily/hk_all_daily_latest/symbols.txt --start-date 20260402 --end-date 20260409 --output artifacts/cache/intraday/hk_all_5m_20260402_20260409.parquet --package
```

说明：

- 默认执行顺序为：`download -> inspect（仅限新的 patch） -> build asset + alias`。其中 inspect 的默认拦截级别为 `warning`，触发该级别警告后流程将终止，且后续更新 `hk_intraday_latest` 的操作会被取消。
- `--resume` 能够自动衔接先前因网络或其他长任务截断的下载，直接基于 `<output_stem>.parts/` 里的现有碎片继续未竟的工作。
- 提供 `--skip-inspect` 将赋予直接跃升资产层的权利，建议仅在使用者充分认识隐患的前提下开启。常规场合下仍倡导保留严防死守的质检护栏。
- 工具通常只着眼于对本次切片内容发起检验，更新别名后忽略沉重的存量数据扫描。如有全面摸底需要，务必手动启用 `--verify-full-asset` 参数。因该计算资源消耗巨大，建议分拆作为后台任务运营。
- 当注入 `--package` 时，系统将依附这批新快照产生专属的 intraday release 节点与对应的 tar 包；若改用 `--release` 将同步下达指令由 `gh release` 分发上网。考虑到整体数据体系的一致性约束，上述指令要求对应的 `daily` 行情基座和 `instruments` 数据同处合规可用期。

### cstree rqdata inspect-hk-intraday-health

核查本地留存的港股 `5m` 分钟线 parquet 文件，挖掘隐藏的时序重复、漏 bar 断片、各交易日 session 计数畸变、负价与负量异类特征，并引入日线对比账本确认聚合无误。

```bash
cstree rqdata inspect-hk-intraday-health --input artifacts/cache/intraday/hk_all_5m_20260327_20260401.parquet
cstree rqdata inspect-hk-intraday-health --input artifacts/cache/intraday/hk_all_5m_20260327_20260401.parquet --daily-asset-dir artifacts/assets/rqdata/hk/daily/hk_all_daily_latest --format json --out artifacts/reports/hk_intraday_health_20260401.json
cstree rqdata inspect-hk-intraday-health --input artifacts/assets/rqdata/hk/intraday/hk_intraday_latest --daily-asset-dir artifacts/assets/rqdata/hk/daily/hk_all_daily_latest
```

说明：

- `--input` 接收包含单独文件、存放片段的 `.parts/` 工作夹、整包缓存乃至正式的数据资产在内的混杂格式支持。如果同名 `.parts/` 存在，应用内部将启动自动展开解构机制。
- 根据港股交易日准则，全天完整的 `5m` 记录理论数值锁定在 `66` 根柱线。基于此，逻辑检测模块会自动标识不足柱线、溢出排程或显著非标定的情形。
- 一旦挂接 `--daily-asset-dir` 账本对比源，分析模块将分钟内的 `open/high/low/close/volume/amount` 进行高频重构合并，同标准的本地日线基准做穿透式对账，直接把问题定位到 intraday 本身漏缺还是源端层级不一致。
- 对账过程中，`close`、`volume` 和 `amount` 字段依然采用严格数值比较。对于 `open`、`high` 和 `low` 字段，工具会自动过滤由于轻微 tick 或集合竞价口径差异导致的噪音（前提是前述三个字段已对齐）。这样保留下来的警告信息均具有较高的人工排查价值。
- 最终生成的 JSON 评估文档末段同样含有 `quality_verdict` 分级定音；通过配置 `--fail-on-severity` 可达成强制拦截效果。

### cstree rqdata build-hk-intraday-asset

执行资产转换组装，将松散在港股 `5m` 缓存区的单独 parquet 及 `.parts` 子层聚合成能够长期留用的正是 `intraday` 产物层，全过程依赖磁盘迁移操作且免除非必要的外部重试拉取。

```bash
cstree rqdata build-hk-intraday-asset --input artifacts/cache/intraday/hk_all_5m_20250327_20260326.parquet --name hk_all_5m_20250327_20260326_latest
cstree rqdata build-hk-intraday-asset --input artifacts/cache/intraday --name hk_intraday_latest --alias artifacts/assets/rqdata/hk/intraday/hk_intraday_latest
```

说明：

- 打包目录将规范化地落点至 `artifacts/assets/rqdata/hk/intraday/<snapshot>/`。其中内嵌的 `data/` 子干将无损保留其源 parquet 内容及对应的附属元信息与分片块。
- 该动作彻底剥离源文件羁绊。即便将旧缓存空间施以深度清空，构建落位的正是资产夹依然具备充分的自持力供各类下游工具消费。
- 附带的 `manifest.yml` 索引将涵盖数据的横跨日期谱系、结构字段定义、源节点指纹追踪及落位分片的行列尺度与额度特征。
- 随后 `inspect-hk-intraday-health` 与底层计算如 `python -m cstree.research.hk_intraday_slippage_report` 都可以无缝地用其充当合法 `--input` 数据源。

### cstree rqdata build-hk-daily-clean-layer

通过保守的策略手段提炼港股 `daily` 的核心整洁资产层，期间严格保障源数据档案的完好。清理动作聚焦在几点公约化法则上：界限失常修正、负值量的剥离屏蔽以及极少部分滞留式挂空期零价的截断归零。

```bash
cstree rqdata build-hk-daily-clean-layer --asset-dir artifacts/assets/rqdata/hk/daily/hk_all_daily_latest --out-dir artifacts/assets/rqdata/hk/daily/hk_all_daily_clean_20260402 --alias artifacts/assets/rqdata/hk/daily/hk_all_daily_clean_latest
cstree rqdata build-hk-daily-clean-layer --asset-dir artifacts/assets/rqdata/hk/daily/hk_all_daily_latest --out-dir artifacts/assets/rqdata/hk/daily/hk_all_daily_clean_20260402 --symbols-file artifacts/assets/rqdata/hk/daily/hk_all_daily_latest/symbols.txt --zero-price-min-run 10 --overwrite
cstree rqdata build-hk-daily-clean-layer --asset-dir artifacts/assets/rqdata/hk/daily/hk_etf_daily_latest --out-dir artifacts/assets/rqdata/hk/daily/hk_etf_daily_clean_20260402 --instruments-file artifacts/assets/rqdata/hk/instruments/hk_etf_instruments_latest.parquet --etf-short-zero-max-run 2 --overwrite
```

说明：

- 程序拒绝污染既有 `asset-dir` 环境；针对被清洗标的一经捕获仅重组并在设定 `out-dir` 内完成全新镜像写入。状态良好的文件将受惠于零拷贝逻辑直接延续至新域内。
- `price_bounds_fix` 逻辑约束异常维的上下限溢出：它仅向自身当日的最高至最低区间妥协修正，绝对维护 `open` 和 `close` 不受侵犯。
- 对冗长常数域的修整建立在稳健的前提下：默认寻找 `5` 个以上完全零化（即 `open=high=low=close=0`）的空窗死区段位，通过把其对应的价、量、金额齐齐置空，杜绝死数据持续灌溉下游模型。
- 若涉及 ETF 类属且支持获取全信息，净化器启用次级处理通道。一般的经典产品容忍较短时间段落的修正；反之如涉及加减杠杆、crypto 题材或是非常态商品标的，系统将卸载强制清扫工作流，仅作观测并单独陈列至 `cleaning_report.json` 作备忘考察。
- 当下的规则倾向更为克制保守，遭遇量化项负数异常一律优先置空隐去而非粗暴改归零值。
- 后台同时会沉淀出对应的行动纪要 `cleaning_report.json` 和 `cleaning_actions.csv` 附文，让具体施加给哪些品种做了何种修正统统具备可溯原的证迹。

## 股票池生成命令

### cstree universe hk-connect

生成港股通相关的 PIT 数据池。

```bash
cstree universe hk-connect --config configs/presets/universe/hk_connect.yml -- --mode daily
```

### cstree universe hk-daily-assets

通过本地历史行情数据，生成适用于全港股市场的可分析股票资产池。

```bash
cstree universe hk-daily-assets --config configs/presets/universe/hk_all_assets.yml -- --end-date 20251231
```

## 参阅文档索引

- 配置参数对照表：`docs/config.md`
- 输出结果导读指南：`docs/outputs.md`
- 操作实战集锦：`docs/cookbook.md`
- 专业分析概念手册：`docs/concepts/`
