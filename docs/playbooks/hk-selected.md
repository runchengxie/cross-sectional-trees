# HK selected 研究路线

本页把 HK selected 研究拆成三步：

1. 先选频率：`M` / `Q` / `Y`
2. 再选数据路线：`纯量价` / `量价 + provider 基本面` / `量价 + PIT 财务`
3. 最后在同一条路线里比较模型：`xgb_regressor` / `xgb_ranker` / `ridge` / `elasticnet`

本页只讲研究路线、模板选择和比较顺序。

先看本目录导航：

* [README.md](./README.md)

参数细节看：

* `docs/cli.md`
* `docs/config.md`

PIT 资产准备看：

* [hk-data-assets.md](./hk-data-assets.md)

模板维护和派生原则看：

* [research-template-design.md](./research-template-design.md)

## 1. 新手先看这个

如果你第一次做 HK selected，先按下面的顺序走：

1. 想先跑通四模型对比，从“月度 + provider 基本面”开始。
2. 想做低频调仓，但暂时不想准备本地 PIT 财务文件，从“季度 + provider 基本面对照”开始。
3. 想研究财报驱动信号，从“季度 + PIT 财务”开始。
4. 年度 `Y` 先当探索路线。先把季度路线跑稳，再上年度。

## 2. 先看研究矩阵

这张表只回答“你应该从哪一格开始”。它不表示每一格都有完整的内置模板。

| 频率 | 纯量价 | 量价 + provider 基本面 | 量价 + PIT 财务 |
| --- | --- | --- | --- |
| 月度 `M` | 需要本地派生。可从 `config/hk_selected__baseline.yml` 关掉 `fundamentals` 开始。 | 现成模板最完整：`config/hk_selected__baseline.yml`、`config/hk_selected__ridge_a1.yml`、`config/hk_selected__elasticnet_a0.1_l0.5.yml`、`config/hk_selected__xgb_regressor.yml`、`config/hk_selected__xgb_ranker_pairwise.yml`。 | 有现成起点：`config/hk_selected__baseline_pit_file.yml`。如果要四模型 PK，需要继续派生。 |
| 季度 `Q` | 需要本地派生。可从 `config/hk_selected__pit_quarterly_hybrid.yml` 关掉 `fundamentals` 开始。 | 有现成估值对照：`config/hk_selected__provider_quarterly_valuation.yml`。如果要再叠加量价特征，需要继续派生。 | 现成模板最多：`config/hk_selected__baseline_pit_quarterly.yml`、`config/hk_selected__pit_quarterly_financial_ml.yml`、`config/hk_selected__pit_quarterly_financial_linear.yml`、`config/hk_selected__pit_quarterly_hybrid.yml`。 |
| 年度 `Y` | 代码支持，当前没有内置模板。建议从月度或季度配置派生。 | 代码支持，当前没有内置模板。建议从季度 provider 路线派生。 | 代码支持，当前没有内置模板。建议从季度 PIT 路线派生。 |

读表时记住两点：

* 做模型比较时，只在同一格里换模型。
* 跨格比较时，你比较的是整条研究路线，不只是模型。

## 3. 月度 `M` 怎么选

月度路线适合日常基线、模型横向对比和更高样本量的研究。

| 数据路线 | 起点配置 | 需要本地 PIT 文件 | 更适合回答的问题 |
| --- | --- | --- | --- |
| 纯量价 | 从 `config/hk_selected__baseline.yml` 派生，设 `fundamentals.enabled=false` | 否 | 先看技术面和量价本身有没有稳定信号 |
| 量价 + provider 基本面 | `config/hk_selected__baseline.yml` 及其显式模型模板 | 否 | 日常基线、四模型 PK、估值与技术面的混合信号 |
| 量价 + PIT 财务 | `config/hk_selected__baseline_pit_file.yml` | 是 | 想保留月度调仓，同时把财报字段并进模型 |

月度路线当前最适合做四模型比较。原因很简单：

* 内置模板最完整
* 样本点更多
* 调参与回看结果都更直接

如果你只想先把四模型跑一遍，优先从这一块开始。

## 4. 季度 `Q` 怎么选

季度路线适合低频调仓和财报驱动研究。

这里先记住一件事：季度路线仍然读取日线行情。变化的是标签、评估和回测的 rebalance 频率。

| 数据路线 | 起点配置 | 需要本地 PIT 文件 | 更适合回答的问题 |
| --- | --- | --- | --- |
| 纯量价 | 从 `config/hk_selected__pit_quarterly_hybrid.yml` 派生，设 `fundamentals.enabled=false` | 否 | 低频调仓下，慢量价特征本身有没有方向 |
| 量价 + provider 基本面 | `config/hk_selected__provider_quarterly_valuation.yml` 是现成估值对照；如果要叠加量价特征，需要继续派生 | 否 | 低频估值字段本身有没有方向；是否值得再叠加量价 |
| 量价 + PIT 财务 | `config/hk_selected__baseline_pit_quarterly.yml`、`config/hk_selected__pit_quarterly_financial_ml.yml`、`config/hk_selected__pit_quarterly_financial_linear.yml`、`config/hk_selected__pit_quarterly_hybrid.yml` | 是 | 财报披露节奏对齐后，慢基本面、财务质量和慢量价特征有没有 alpha |

季度 PIT 这几份配置的分工是：

* `config/hk_selected__baseline_pit_quarterly.yml`：简单 PIT 财报基线，模型是 `xgb_regressor`
* `config/hk_selected__pit_quarterly_financial_ml.yml`：更丰富的财务主项、增长和质量特征，模型是 `xgb_regressor`
* `config/hk_selected__pit_quarterly_financial_linear.yml`：和上一份尽量保持同一套财务特征，但模型换成 `ridge`
* `config/hk_selected__pit_quarterly_hybrid.yml`：PIT 财务 + 慢量价特征，模型是 `xgb_regressor`

这里最容易混淆的点是：

* 这四份文件是四条季度实验路线。
* 它们不是“四种模型”的一一对应模板。
* 如果你要做严格的四模型 PK，应该先选其中一条作为基线，再只改 `model`。

## 5. 年度 `Y` 怎么选

代码层已经支持年度频率，但当前没有单独维护的年度模板。

更稳妥的做法是：

1. 先从季度路线选一份最接近你的配置。
2. 把 `label.rebalance_frequency`、`eval.rebalance_frequency`、`backtest.rebalance_frequency` 一起改成 `Y`。
3. 同步把 `eval.n_splits` 和 `eval.walk_forward.n_windows` 调低。
4. 起步时优先用线性模型或较浅的树模型。

年度路线更适合这类问题：

* 你只关心很慢的财报信号
* 你接受更少的训练窗口
* 你愿意先做探索，再决定要不要长期维护这条路线

## 6. 四模型 PK 的标准做法

仓库当前支持四种模型：

* `xgb_regressor`
* `xgb_ranker`
* `ridge`
* `elasticnet`

推荐做法很固定：

1. 先选定研究矩阵里的一个单元。
2. 复制一份基线配置到本地，例如放到 `config/local/`。
3. 保持下面这些块尽量不变：
   `universe`、`fundamentals`、`features`、`label`、`backtest`
4. 只改两类内容：
   `model`
   `eval.run_name`
5. 跑四份配置，再统一 `summarize`。

模型块可以直接参考现成模板：

* `xgb_regressor`：`config/hk_selected__xgb_regressor.yml`
* `xgb_ranker`：`config/hk_selected__xgb_ranker_pairwise.yml`
* `ridge`：`config/hk_selected__ridge_a1.yml`
* `elasticnet`：`config/hk_selected__elasticnet_a0.1_l0.5.yml`

如果你现在要做“季度 + 量价 + PIT 财务”的四模型 PK，最直接的起点是：

* 以 `config/hk_selected__pit_quarterly_hybrid.yml` 为基线
* 派生四份本地配置
* 只改 `model` 和 `eval.run_name`

示例：

```bash
csml run --config config/local/hk_sel_pit_q_hybrid_xgb_reg.yml
csml run --config config/local/hk_sel_pit_q_hybrid_xgb_rank.yml
csml run --config config/local/hk_sel_pit_q_hybrid_ridge.yml
csml run --config config/local/hk_sel_pit_q_hybrid_en.yml

csml summarize \
  --runs-dir artifacts/runs \
  --run-name-prefix hk_sel_pit_q_hybrid \
  --sort-by score
```

如果你要做线性模型搜索，再单独用 `csml sweep-linear`。前提仍然是先把研究单元固定住。

## 7. 什么时候需要准备 PIT 财务文件

只有在你走“量价 + PIT 财务”这条路线时，才需要本地 PIT fundamentals 文件。

判断方法很简单：

* `fundamentals.source=provider`：不需要本地 PIT 文件
* `fundamentals.enabled=false`：不需要本地 PIT 文件
* `fundamentals.source=file`：需要本地 PIT 文件

最短准备流程：

```bash
csml rqdata mirror-hk-pit-financials \
  --config config/hk_selected__baseline.yml \
  --name hk_selected_pit_2011_2025_latest \
  --fields-file config/rqdata_assets/hk_financial_fields_starter.txt \
  --start-quarter 2011q1 \
  --end-quarter 2025q4 \
  --date 20260312

csml rqdata build-hk-pit-fundamentals \
  --asset-dir artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest \
  --out artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest/pipeline_fundamentals.parquet
```

更完整的资产准备顺序看：

* [hk-data-assets.md](./hk-data-assets.md)

## 8. 常见误解

### 误解 1：研究矩阵里的每一格都有完整内置模板

当前不是这样。仓库已经覆盖了常用单元，但不是九宫格全部现成。

### 误解 2：季度或年度路线不再依赖日线行情

不会。季度和年度路线仍然读取日线价格、成交量和成交额，只是 rebalance 频率变了。

### 误解 3：PIT 股票池会把财务历史自动裁成成员期

不会。股票池控制的是某个日期能不能进入研究样本。财务镜像控制的是本地保留了多少历史。

### 误解 4：比较模型时，可以直接拿不同路线的模板互相比

这样很难解释。更稳妥的做法是在同一条路线里换模型。

## 9. 结果先看什么

先读这几个文件：

1. `summary.json`
2. `config.used.yml`
3. `positions_current.csv`
4. `runs_summary.csv`

重点看：

* `ic_mean`
* `long_short`
* `backtest_sharpe`
* `backtest_max_drawdown`
* `backtest_avg_turnover`
* `flag_*`

如果你在比较季度或年度低频 run，再额外看：

* walk-forward 是否稳定
* `positions_current.csv` 是否集中在极少数低流动性标的
* 样本覆盖是否因为缺失填补、`growth_*` 特征或更慢的 rebalance 频率发生明显变化
