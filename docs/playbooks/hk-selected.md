# HK selected 多模型研究配方

本页只讨论 HK selected 这条研究路线。

这条路线当前有两种成熟频率：

* 月度 `M`
* 季度 `Q`

代码层也支持年度 `Y`，但仓库里还没有单独维护的年度模板。当前更适合把它当成探索路线。

参数细节看 `docs/cli.md` 和 `docs/config.md`。本页只保留选路线时最容易混淆的几件事。

## 1. 前置条件

开始前先确认这几项：

1. 已安装 `RQData` 依赖：`uv sync --extra dev --extra rqdata`
2. 已准备港股通股票池文件，或知道要用哪份配置生成它
3. 已确认研究范围是 HK selected，不是更宽的港股普通股池

## 2. 先按频率选路线

| 路线 | 频率 | 常用配置 | 更适合回答的问题 |
| --- | --- | --- | --- |
| 月度研究基线 | `M` | `config/hk_selected__baseline.yml`、`config/hk_selected__ridge_a1.yml`、`config/hk_selected__xgb_regressor.yml`、`config/hk_selected__xgb_ranker_pairwise.yml` | 日常研究基准、模型横向对比、技术面和估值混合信号 |
| 季度估值对照 | `Q` | `config/hk_selected__provider_quarterly_valuation.yml` | 低频调仓加估值字段本身有没有方向 |
| 季度 PIT 财报研究 | `Q` | `config/hk_selected__baseline_pit_quarterly.yml`、`config/hk_selected__pit_quarterly_financial_ml.yml`、`config/hk_selected__pit_quarterly_financial_linear.yml`、`config/hk_selected__pit_quarterly_hybrid.yml` | 按披露节奏对齐后，慢基本面和财报特征有没有 alpha |
| 年度 PIT 财报探索 | `Y` | 以季度 PIT 配置为起点自行派生 | 只想研究非常慢的财报信号，接受样本明显变少 |

当前建议：

1. 月度路线用于日常基线和模型比较。
2. 季度路线用于财报驱动研究。
3. 年度路线先不要当默认模板。先确认你接受更少的训练窗口和回测期数。

## 3. 先固定研究基线

做模型对比时，优先只改这两类内容：

* `model`
* `eval.run_name`

尽量不要同时改：

* `universe`
* `label`
* `features`
* `eval`
* `backtest`

这样结果更容易比较。

## 4. PIT 港股通股票池和财务资产不是同一层

这里最容易混淆，单独写清楚：

1. `by_date_file` 决定的是一只股票在哪些日期属于研究股票池。
2. `mirror-hk-pit-financials --by-date-file ...` 用这份文件先解析出一组 symbol。
3. symbol 一旦被解析出来，财务镜像命令会按你给的 `start-quarter -> end-quarter` 下载这只股票的整段财务历史。
4. 下载逻辑不会把财务数据裁成“只保留在港股通期间”。
5. 真正按日期裁股票池，是 pipeline 里后面的 `universe-by-date` 过滤步骤。

这意味着：

* 有些股票后来才加入港股通。它们更早的财务历史仍然会被下载。
* 有些股票曾经在港股通，后来被移出。它们被移出后的研究日期会被股票池过滤掉。
* PIT 股票池控制的是“某天能不能进研究样本”，不是“这只股票允许保留几年财报历史”。

## 5. 月度路线怎么理解

月度路线是仓库里的默认研究基线。

常用配置：

* `config/hk_selected__baseline.yml`
* `config/hk_selected__baseline_pit_file.yml`
* `config/hk_selected__ridge_a1.yml`
* `config/hk_selected__elasticnet_a0.1_l0.5.yml`
* `config/hk_selected__xgb_regressor.yml`
* `config/hk_selected__xgb_ranker_pairwise.yml`

这条路线的特点：

* `label.rebalance_frequency=M`
* `eval.rebalance_frequency=M`
* `backtest.rebalance_frequency=M`
* 通常继续使用日线价格、成交量和成交额数据
* 更适合日常研究、模型批跑和基线比较

使用顺序建议：

1. 先从 `config/hk_selected__baseline.yml` 开始。
2. 需要本地 PIT 文件时，再切到 `config/hk_selected__baseline_pit_file.yml`。
3. 需要显式模型模板时，再切到 ridge、elasticnet、XGB 配置。

## 6. 季度路线怎么理解

季度路线要解决的是“信号更新节奏”和“调仓节奏”更接近财报披露。

这里有三个关键点：

1. 季度路线仍然使用日线行情数据。
2. 季度路线把标签、评估和回测频率一起改成 `Q`。
3. 是否只在季度调仓日抽样，要看 `eval.sample_on_rebalance_dates`。

以 `config/hk_selected__pit_quarterly_financial_ml.yml` 为例：

* 日线数据仍然从 `data.rqdata.frequency: 1d` 拉取。
* 股票池仍然是 `universe.mode: pit`。
* 财务文件来自本地 `pipeline_fundamentals.parquet`。
* `label.rebalance_frequency=Q`
* `eval.rebalance_frequency=Q`
* `backtest.rebalance_frequency=Q`
* `eval.sample_on_rebalance_dates=true`，表示建模样本只取季度调仓点。

这条路线不是“原生季度 bar 引擎”。它还是在日线面板上运行，只是：

* 用日线序列计算标签和回测持有窗口
* 用季度频率确定 rebalance date
* 用 PIT 财报文件按 `info_date` 并入，再向后填充到后续交易日

还要注意一件事：

* 季度 PIT 配置不会自动把镜像资产里的全部字段都喂给模型。
* 实际会进入研究的数据，取决于 `fundamentals.features` 和 `features.list`。
* 如果你手里有 full mirror，默认配置仍然只会用它引用到的那一部分字段。

季度路线内部可以继续分成三类：

| 路线 | 配置 | 是否需要先准备本地 PIT 文件 | 说明 |
| --- | --- | --- | --- |
| provider 季度估值对照 | `config/hk_selected__provider_quarterly_valuation.yml` | 否 | 先快速验证低频估值方向 |
| PIT 财报季度基线 | `config/hk_selected__baseline_pit_quarterly.yml` | 是 | 用较简单的财报字段做低频基线 |
| PIT 财务 ML / 线性 / hybrid | `config/hk_selected__pit_quarterly_financial_ml.yml`、`config/hk_selected__pit_quarterly_financial_linear.yml`、`config/hk_selected__pit_quarterly_hybrid.yml` | 是 | 用更丰富的财务主项、增长和质量特征做深入研究 |

如果你决定切到季度口径，三处频率一起改：

1. `label.rebalance_frequency=Q`
2. `eval.rebalance_frequency=Q`
3. `backtest.rebalance_frequency=Q`

只改回测频率，结果通常很难解释。

## 7. 年度路线怎么试

代码层已经支持年度频率，因为 rebalance date 是按 pandas period frequency 生成的。`Y` 可以直接工作。

但当前没有单独维护的年度模板。更稳妥的做法是从季度 PIT 配置派生一份本地配置，然后改这几项：

1. `label.rebalance_frequency=Y`
2. `eval.rebalance_frequency=Y`
3. `backtest.rebalance_frequency=Y`

建议同步收紧这几项：

* `eval.n_splits` 降低
* `eval.walk_forward.n_windows` 降低
* 尽量把起始日期拉长
* 模型先用线性或较浅的树模型

原因很简单：年度调仓的样本点会明显少很多。`2015-01-01 -> 2025-12-31` 这段区间按年看，只有大约十来个 rebalance 点。复杂模型会很容易变得不稳定。

## 8. 准备本地 PIT fundamentals 文件

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
  --name hk_connect_full_2000_2025_full_latest \
  --start-quarter 2000q1 \
  --end-quarter 2025q4 \
  --date 20260310
```

补充：

* 请求起点可以写到 `2000q1`。
* provider 实际返回的最早有效季度可能晚于请求起点。
* 当前这批 HK Connect PIT 财务资产，实际最早覆盖到的是 `2000q4`。

## 9. 建议的比较顺序

如果你做的是月度基线：

```bash
csml run --config config/hk_selected__ridge_a1.yml
csml run --config config/hk_selected__elasticnet_a0.1_l0.5.yml
csml run --config config/hk_selected__xgb_regressor.yml
csml run --config config/hk_selected__xgb_ranker_pairwise.yml
```

如果你做的是季度财报路线：

```bash
csml run --config config/hk_selected__provider_quarterly_valuation.yml
csml run --config config/hk_selected__baseline_pit_quarterly.yml
csml run --config config/hk_selected__pit_quarterly_financial_ml.yml
```

统一汇总：

```bash
csml summarize \
  --runs-dir artifacts/runs \
  --sort-by score
```

## 10. 结果怎么读

先读这几个文件：

1. `summary.json`
2. `config.used.yml`
3. `positions_current.csv`
4. `runs_summary.csv`

重点看这些指标：

* `ic_mean`
* `long_short`
* `backtest_sharpe`
* `backtest_max_drawdown`
* `backtest_avg_turnover`
* `flag_*`

如果你在比较季度 PIT run，再额外看：

* walk-forward 结果是否稳定
* `positions_current.csv` 是否集中在极少数低流动性标的
* 缺失填补和 `growth_*` 特征是否让样本覆盖明显变化
