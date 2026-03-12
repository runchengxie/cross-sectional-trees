# HK selected 多模型研究配方

本页只讨论 HK selected 这条研究路线。

适用场景：

* 你想在同一套研究口径下比较 `ridge`、`elasticnet`、`xgb_regressor`、`xgb_ranker`
* 你想决定是否切到季度 PIT 财报路线
* 你想把港股通默认研究模板跑成一组可比较的 run

参数细节看 `docs/cli.md` 和 `docs/config.md`。本页只保留决策顺序和推荐流程。

## 1. 前置条件

这条路线默认你已经具备下面这些条件：

1. 已安装 `RQData` 依赖：`uv sync --extra dev --extra rqdata`
2. 已准备港股通股票池文件，或知道要用哪份配置生成它
3. 已确认研究范围是 HK selected，不是更宽的港股普通股池

## 2. 先固定研究基线

做模型对比时，优先只改这两类内容：

* `model`
* `eval.run_name`

尽量不要同时改：

* `universe`
* `label`
* `features`
* `eval`
* `backtest`

这样做的目的很简单：结果才有可比性。

## 3. 常用配置怎么选

| 配置 | 用途 |
| --- | --- |
| `config/hk_selected__baseline.yml` | HK selected 通用基线。适合线性模型批跑和日常研究基准。 |
| `config/hk_selected__baseline_pit_file.yml` | 读取本地 PIT fundamentals 文件的 HK 基线。 |
| `config/hk_selected__provider_quarterly_valuation.yml` | 不依赖本地 PIT 文件的季度估值对照。 |
| `config/hk_selected__baseline_pit_quarterly.yml` | 季度 PIT 财报基线。 |
| `config/hk_selected__pit_quarterly_financial_ml.yml` | 季度 PIT 财务 ML 基线。 |
| `config/hk_selected__pit_quarterly_financial_linear.yml` | 季度 PIT 财务线性对照。 |
| `config/hk_selected__pit_quarterly_hybrid.yml` | 季度 PIT 财报 + 慢技术面混合配置。 |
| `config/hk_connect__pit_quarterly_financial_ml.yml` | 更宽港股通股票池上的季度 PIT 财务 ML 配置。 |
| `config/hk_selected__xgb_regressor.yml` | 显式 XGB 回归配置。 |
| `config/hk_selected__xgb_ranker_pairwise.yml` | 显式 XGB 排序配置。 |
| `config/hk_selected__ridge_a1.yml` | 线性 ridge 基线。 |
| `config/hk_selected__elasticnet_a0.1_l0.5.yml` | 线性 elasticnet 基线。 |

使用顺序建议：

1. 先从 `config/hk_selected__baseline.yml` 开始。
2. 需要本地 PIT 文件时，再切到 `config/hk_selected__baseline_pit_file.yml`。
3. 想先验证季度低频估值方向时，先跑 `config/hk_selected__provider_quarterly_valuation.yml`。
4. 想认真研究财报 alpha 时，再切到季度 PIT 路线。

## 4. 季度低频三条路线怎么选

| 路线 | 配置 | 是否需要先准备本地 PIT 文件 | 更适合回答的问题 |
| --- | --- | --- | --- |
| provider 季度估值对照 | `config/hk_selected__provider_quarterly_valuation.yml` | 否 | 低频调仓加估值字段本身有没有方向 |
| PIT 财报季度基线 | `config/hk_selected__baseline_pit_quarterly.yml` | 是 | 按披露节奏对齐后，慢基本面有没有 alpha |
| PIT 财务 ML / 线性对照 | `config/hk_selected__pit_quarterly_financial_ml.yml` / `config/hk_selected__pit_quarterly_financial_linear.yml` | 是 | 高覆盖财务主项、增长和质量比率是否比简单基线更强 |

补充：

* 这里说的“准备本地 PIT 文件”，指的是用仓库内置命令生成 `pipeline_fundamentals.parquet`。
* provider 季度估值对照适合先做小范围验证。它更省事，但不替代完整财报研究。
* 如果你关心的是财报驱动的慢因子，季度 PIT 路线更合适。

## 5. 什么时候切到季度 PIT

满足下面这些条件时，优先考虑季度 PIT 口径：

1. 你关心的是财报驱动的慢因子，不是短周期技术信号。
2. 你希望标签窗口和财报更新节奏更接近。
3. 你更在意 `long_short`、Top-K 胜率、walk-forward 和净回测的一致性。

切换时，三处频率一起改：

1. `label.rebalance_frequency=Q`
2. `eval.rebalance_frequency=Q`
3. `backtest.rebalance_frequency=Q`

只改回测频率，结果通常很难解释。

## 6. 准备本地 PIT fundamentals 文件

如果你要走本地 PIT 文件路线，先执行：

```bash
csml rqdata mirror-hk-pit-financials \
  --config config/hk_selected__baseline.yml \
  --name hk_selected_pit_2011_2025_latest \
  --fields-file config/rqdata_assets/hk_financial_fields_starter.txt \
  --start-quarter 2011q1 \
  --end-quarter 2025q4 \
  --date 20260310

csml rqdata build-hk-pit-fundamentals \
  --asset-dir artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest \
  --out artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest/pipeline_fundamentals.parquet
```

如果你要准备更宽股票池的财报资产，先生成股票池文件，再镜像财报：

```bash
csml universe hk-connect --config config/universe.hk_connect_full.yml

csml rqdata mirror-hk-pit-financials \
  --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv \
  --field-profile full \
  --name hk_connect_full_2010_2025_full_latest \
  --start-quarter 2010q1 \
  --end-quarter 2025q4 \
  --date 20260310
```

## 7. 建议的比较顺序

### 第一步：先跑线性基线

```bash
csml run --config config/hk_selected__ridge_a1.yml
csml run --config config/hk_selected__elasticnet_a0.1_l0.5.yml
```

需要批跑时，再用：

```bash
csml sweep-linear --sweep-config config/sweeps/hk_selected__linear_a.yml
```

### 第二步：再跑非线性对照

```bash
csml run --config config/hk_selected__xgb_regressor.yml
csml run --config config/hk_selected__xgb_ranker_pairwise.yml
```

### 第三步：统一汇总

```bash
csml summarize \
  --runs-dir artifacts/runs \
  --sort-by score
```

## 8. 先过可信性门槛，再看收益

建议至少先检查这四项：

1. `backtest_periods >= 24`
2. `backtest_avg_turnover <= 0.7`
3. `data.end_date` 是否为绝对日期
4. 是否出现 `flag_constant_prediction=true` 或 `flag_zero_feature_importance=true`

可以先看全量结果：

```bash
csml summarize \
  --runs-dir artifacts/runs \
  --sort-by score
```

确认这批 run 基本可比后，再加排除参数：

```bash
csml summarize \
  --runs-dir artifacts/runs \
  --exclude-flag-short-sample \
  --exclude-flag-high-turnover \
  --exclude-flag-relative-end-date \
  --sort-by score
```

## 9. 结果怎么读

先读这几个文件：

1. `summary.json`
2. `config.used.yml`
3. `positions_current.csv`
4. `runs_summary.csv`

再重点看这些指标：

* `ic_mean`
* `long_short`
* `backtest_sharpe`
* `backtest_max_drawdown`
* `backtest_avg_turnover`
* `flag_*`

如果你在比较多条季度 PIT run，再额外看：

* walk-forward 结果是否稳定
* `positions_current.csv` 是否集中在极少数低流动性标的
* 缺失填补和 `growth_*` 特征是否让样本覆盖明显变化
