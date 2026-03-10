# Cookbook

本页分成两段：

1. 通用最短流程：第一次跑通项目时先看这里。
2. HK selected 研究配方：用 RQData + PIT universe 做港股多模型对比时再看这里。

CLI 参数细节见 `docs/cli.md`。配置键见 `docs/config.md`。输出文件和字段见 `docs/outputs.md`。

## 1) 通用最短流程

### 1.1 准备环境

推荐使用 `uv`：

```bash
uv venv --seed
uv sync --extra dev
```

如果你准备用 `RQData`：

```bash
uv sync --extra dev --extra rqdata
```

如果本地还没有配置文件，可以先导出内置模板：

```bash
csml init-config --market hk --out config/
```

同时准备好对应 provider 的鉴权变量：

* `tushare`：`TUSHARE_TOKEN`
* `rqdata`：`RQDATA_USERNAME` + `RQDATA_PASSWORD`
* `eodhd`：`EODHD_API_TOKEN`

### 1.2 跑一次最小流程

```bash
csml run --config config/hk.yml
```

第一次跑完后，先看这三个文件：

1. `summary.json`
1. `config.used.yml`
1. `positions_current.csv`

建议先用 `config.used.yml` 复盘本次 run。它保存的是实际生效配置。

### 1.3 汇总历史 run

当你已经有多次运行结果时，再用 `summarize` 做横向比较：

```bash
csml summarize \
  --runs-dir out/runs \
  --output out/runs/runs_summary.csv
```

如果筛选后输出 `No runs matched current summarize filters.`，先去掉全部 `--exclude-flag-*` 看全量结果，再检查 `flag_*` 列。

### 1.4 生成 live 快照

仓库里没有内置的 `config/hk_live.yml`。要跑 `snapshot`，请先单独准备一份 live 配置，例如 `config/hk_live.local.yml`。

常见最小改法：

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

然后再执行：

```bash
csml snapshot --config config/hk_live.local.yml
csml snapshot --config config/hk_live.local.yml --skip-run --format json
```

## 2) HK selected 多模型研究配方

这一段用于同一研究设置下的多模型对比。核心顺序是：

1. 线性基线（`ridge` / `elasticnet`）
1. 非线性对照（`xgb_regressor` / `xgb_ranker`）
1. `csml summarize` 跨 run 汇总比较

### 2.1 前置条件

这套配方默认你已经具备下面这些条件：

1. 已安装 `RQData` 依赖：`uv sync --extra dev --extra rqdata`
1. 已准备 `out/universe/universe_by_date.csv`
1. 已确认研究使用的是 HK selected 这组配置

如果你要直接读取本地 PIT fundamentals 文件，还需要先准备资产目录，再执行：

```bash
csml rqdata mirror-hk-pit-financials \
  --config config/hk_selected__baseline.yml \
  --name hk_selected_pit_2011_2025_latest \
  --fields-file config/rqdata_assets/hk_financial_fields_starter.txt \
  --start-quarter 2011q1 \
  --end-quarter 2025q4 \
  --date 20260310

csml rqdata build-hk-pit-fundamentals \
  --asset-dir data_assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest \
  --out data_assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest/pipeline_fundamentals.parquet
```

### 2.2 先固定实验基准

做模型对比时，先固定研究口径。优先只改 `model` 和 `eval.run_name`。尽量不要同时改 `universe`、`label`、`features`、`eval`、`backtest`。

仓库当前提供的 HK 相关配置：

1. `config/hk_selected__baseline.yml`
1. `config/hk_selected__baseline_pit_file.yml`
1. `config/hk_selected__provider_quarterly_valuation.yml`
1. `config/hk_selected__baseline_pit_quarterly.yml`
1. `config/hk_selected__pit_quarterly_hybrid.yml`
1. `config/hk_selected__xgb_regressor.yml`
1. `config/hk_selected__ridge_a1.yml`
1. `config/hk_selected__elasticnet_a0.1_l0.5.yml`
1. `config/hk_selected__xgb_ranker_pairwise.yml`

使用建议：

1. 线性模型批跑时，优先以 `config/hk_selected__baseline.yml` 为 base 配置。
1. 已经生成本地 PIT fundamentals 文件时，改用 `config/hk_selected__baseline_pit_file.yml`。
1. 想先做无需本地 PIT 文件的季度低频验证时，先跑 `config/hk_selected__provider_quarterly_valuation.yml`。
1. 要验证低频财报 alpha 时，优先从 `config/hk_selected__baseline_pit_quarterly.yml` 开始。
1. 要验证“财报 + 慢价格信号”的混合口径时，再跑 `config/hk_selected__pit_quarterly_hybrid.yml`。
1. 非线性对照时，显式使用 `config/hk_selected__xgb_regressor.yml` 或 `config/hk_selected__xgb_ranker_pairwise.yml`。

当前仓库内置的 `config/hk_selected__baseline.yml` 把样本窗口写成 `2015-01-01` 到 `2025-12-31`。这只是模板默认值。你要研究更新的时间区间时，先改配置，再比较结果。

### 2.2.1 季度低频两条路线怎么选

| 路线 | 配置 | 是否需要先准备本地 PIT 文件 | 更适合回答的问题 |
| --- | --- | --- | --- |
| provider 季度估值对照 | `config/hk_selected__provider_quarterly_valuation.yml` | 否 | 先确认低频调仓 + 估值字段本身有没有方向 |
| PIT 财报季度基线 | `config/hk_selected__baseline_pit_quarterly.yml` | 是 | 认真验证财报披露节奏对齐后，慢基本面有没有 alpha |

补充：

1. 这里说的“准备本地 PIT 文件”，指的是运行仓库内置命令把 RQData PIT 资产整理成 `pipeline_fundamentals.parquet`，不是手工清洗表格。
1. provider 季度估值对照适合先排查“是不是频率更低就会好一些”。这一步更省事，但不替代完整财报研究。
1. PIT 财报季度基线适合认真研究财报 alpha。当前 pipeline 已内置 `profit_margin`、`asset_turnover`、`roa`、`leverage`、`cfo_to_assets`、`accrual_ratio`、`receivables_to_revenue`、`inventory_to_revenue` 这类慢因子派生。
1. 如果纯 PIT 基线已有方向，再跑 `config/hk_selected__pit_quarterly_hybrid.yml`，判断慢价格和流动性特征是否真的带来增益。

### 2.2.2 什么时候切到季度 PIT 口径

满足下面这些条件时，优先考虑季度 PIT 口径：

1. 你关心的是财报驱动的慢因子，不是短周期技术信号。
1. 你希望标签窗口和财报更新节奏更接近。
1. 你更在意 `long_short`、`Top-K` 胜率、walk-forward 和净回测的一致性。

这条路线的核心是先把频率对齐：

1. `label.rebalance_frequency=Q`
1. `eval.rebalance_frequency=Q`
1. `backtest.rebalance_frequency=Q`

如果只改回测频率，不改标签和评估频率，结果通常很难解释。

### 2.3 先过可信性门槛

建议先做这四个检查，再看夏普：

1. 样本长度：`backtest_periods >= 24`
1. 交易可实现性：`backtest_avg_turnover <= 0.7`
1. 数据稳定性：`data.end_date` 优先固定绝对日期
1. 模型退化：优先剔除 `flag_constant_prediction=true` 或 `flag_zero_feature_importance=true`

先看全量汇总：

```bash
csml summarize \
  --runs-dir out/runs \
  --sort-by score
```

确认这批 run 基本满足门槛后，再加排除参数：

```bash
csml summarize \
  --runs-dir out/runs \
  --exclude-flag-short-sample \
  --exclude-flag-high-turnover \
  --exclude-flag-relative-end-date \
  --sort-by score
```

如果输出 `No runs matched current summarize filters.`，常见原因有：

1. `backtest_periods < 24`
1. `backtest_avg_turnover > 0.7`
1. 历史 run 的 `config.used.yml` 和当前模板不是同一版

这时先去掉 `--exclude-flag-*` 看全量结果，再决定是重跑、更换样本窗口，还是下调阈值。

### 2.4 先跑线性基线

`ridge` 和 `elasticnet` 适合做稳定基线。它们参数少，复现成本低。

先跑两条默认基线：

```bash
csml run --config config/hk_selected__ridge_a1.yml
csml run --config config/hk_selected__elasticnet_a0.1_l0.5.yml
```

需要扩展网格时，优先扫描：

1. `ridge.alpha`: `0.01, 0.1, 1, 10, 100`
1. `elasticnet.alpha`: `0.01, 0.1, 1`
1. `elasticnet.l1_ratio`: `0.1, 0.5, 0.9`

要一次性批跑并自动导出对比表，可以直接用：

```bash
csml sweep-linear --sweep-config config/sweeps/hk_selected__linear_a.yml
```

临时覆盖少量参数时，再叠加 CLI 参数：

```bash
csml sweep-linear \
  --sweep-config config/sweeps/hk_selected__linear_a.yml \
  --tag hk_linear_a_debug \
  --dry-run
```

命令会在 `out/sweeps/<tag>/` 下生成：

1. `configs/`：本次 sweep 的临时配置文件
1. `jobs.csv`：参数组合清单
1. `run_results.csv`：每个组合执行状态
1. `runs_summary.csv`：自动执行 `csml summarize` 的聚合结果

如果线性基线已经有可用候选，但长期卡在 `flag_short_sample=true`，先不要继续扩大 `alpha` 网格。先改 `eval` 设计，再跑一轮小 sweep：

```bash
csml sweep-linear --sweep-config config/sweeps/hk_selected__eval_sample.yml
csml sweep-linear --sweep-config config/sweeps/hk_selected__eval_sample_ffill.yml
```

这两组配置当前只保留 3 个候选模型：

1. `ridge alpha = 30`
1. `ridge alpha = 100`
1. `elasticnet alpha = 0.01, l1_ratio = 0.05`

区别是：

1. `hk_selected__eval_sample.yml` 把主测试窗口改成 `test_size=0.7`，并把 walk-forward 调成更小的多窗口切法。
1. `hk_selected__eval_sample_ffill.yml` 在同样的样本切法下，把 `backtest.exit_price_policy` 从 `delay` 改成 `ffill`。

### 2.4.1 季度 PIT 财报路线怎么起步

建议按这个顺序跑：

1. 先跑季度 provider 估值对照，确认低频口径本身有没有方向。
1. 再跑季度 PIT 基线，确认财报文件和季度口径都工作正常。
1. 再跑季度 PIT 线性 sweep，看慢因子有没有稳定方向。
1. 最后再跑财报 + 慢技术面的混合配置，判断是否值得加复杂度。

建议命令：

```bash
csml run --config config/hk_selected__provider_quarterly_valuation.yml
csml run --config config/hk_selected__baseline_pit_quarterly.yml
csml sweep-linear --sweep-config config/sweeps/hk_selected__pit_quarterly_linear.yml
csml run --config config/hk_selected__pit_quarterly_hybrid.yml
```

这四步分别回答四个问题：

1. 低频估值字段本身有没有方向。
1. PIT 财报 + 季度调仓本身有没有可解释的信号。
1. 线性模型下，慢因子方向是否稳定。
1. 加入慢技术面后，结果是否明显改善。

看结果时，建议先读：

1. `summary.json -> eval.long_short`
1. `summary.json -> eval.topk_positive_ratio`
1. `summary.json -> walk_forward`
1. `summary.json -> backtest.stats`

如果季度 PIT 路线的 `IC` 仍然不高，但 `long_short`、`Top-K` 胜率和净回测开始同步改善，这条线就值得继续扩展。

### 2.5 再跑非线性对照组

```bash
csml run --config config/hk_selected__xgb_regressor.yml
csml run --config config/hk_selected__xgb_ranker_pairwise.yml
```

`xgb_ranker` 和回归模型不是同一个学习问题。项目会按 `trade_date` 分组训练 ranker。

### 2.6 汇总所有 run

```bash
csml summarize \
  --runs-dir out/runs \
  --run-name-prefix hk_sel_ \
  --output out/runs/hk_sel_models_summary.csv
```

汇总表会聚合每个 run 的 `summary.json` 和 `config.used.yml`，并生成 `flag_*`、`score`、`dsr` 字段。退化模型的 `score` 和 `dsr` 会留空。

### 2.7 结果怎么读

建议按这个顺序看：

1. 先看稳定性：`eval.ic`、`eval.pearson_ic`、walk-forward 指标
1. 再看可交易性：`eval.turnover_mean`、成本拖累、`backtest.stats`
1. 最后再决定是否值得上更复杂的模型

常见情形：

1. 线性和 XGB 差不多，甚至更好：优先选线性，把精力放在特征和交易假设。
1. XGB 指标更高但不稳定：优先怀疑过拟合，重点看 walk-forward 和 permutation test。
1. 收益提升但换手飙升：先调 `buffer_exit` / `buffer_entry` 或降低模型复杂度。
1. `long_short` 经常翻向：先回看标签和特征对齐。

### 2.8 可选：`csml grid` 做 Top-K / 成本 / buffer 形状分析

`csml grid` 会先基于给定配置跑一次 base pipeline，读取 `eval_scored.parquet`，然后在同一份 scored 数据上循环 `Top-K × cost_bps × buffer_exit × buffer_entry × weighting`。它不会为每个网格点重训模型。

示例：

```bash
csml grid \
  --config config/hk_selected__ridge_a1.yml \
  --top-k 5,10,20 \
  --cost-bps 10,25,40 \
  --buffer-exit 8,10 \
  --buffer-entry 4,5 \
  --weighting equal,signal
```

### 2.9 最小可执行清单

```bash
csml run --config config/hk_selected__ridge_a1.yml
csml run --config config/hk_selected__elasticnet_a0.1_l0.5.yml
csml run --config config/hk_selected__xgb_regressor.yml
csml run --config config/hk_selected__xgb_ranker_pairwise.yml
csml summarize --runs-dir out/runs --run-name-prefix hk_sel_ --output out/runs/hk_sel_models_summary.csv
```

## 3) 私有快照与分享

`csml backup-data` 只做本地快照。它会把当前 `cache/`、`out/universe/`、指定配置文件和额外路径复制到 `data_mirror/<name>/`。这个命令不会联网，也不会自动生成压缩包。

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
```

建议：

1. `frozen` 快照固定研究口径和窗口，只用于可比回测。
1. `rolling` 快照随最新已完成交易日更新，用于近端验证。
1. 两套数据尽量用不同的 `data.cache_tag`。
1. 如果仓库是公开仓库，不要把 `cache/` 或 provider 原始数据直接上传到公开 release。

如果你想把源码和快照目录另存成压缩包，可以分别处理：

```bash
./scripts/package_zip.sh --name csml-source-snapshot --out-dir release/
tar -czf release/csml-data-snapshot-hk_frozen_20251231.tar.gz data_mirror/hk_frozen_20251231
```

恢复时，先解压快照目录，再查看 `manifest.yml`。按需把里面的 `cache/`、`out/universe/`、`config/` 拷回工作区。当前仓库没有单独的“私有 release 自动恢复”命令。
