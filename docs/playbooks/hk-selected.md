# HK selected 研究路线

本页解决什么：在 HK selected 路线上做频率与数据路线选择，并确定比较顺序。
本页不解决什么：不展开参数定义与资产准备细节。
适合谁：已经要做 HK selected 研究的人。
读完你会得到什么：一条可执行的路线选择与比较顺序。
相关页面：`docs/playbooks/README.md`、`docs/playbooks/hk-data-assets.md`、`docs/playbooks/research-template-design.md`、`docs/concepts/pit-coverage.md`、`docs/concepts/benchmark-protocol.md`、`docs/cli.md`、`docs/config.md`

任务摘要：先选频率，再选数据路线；走 PIT 路线先做覆盖率体检，再按 benchmark protocol 跑特征阶梯，最后在同一路线内比较模型。

本页把 HK selected 研究拆成五步：

1. 先选频率：`M` / `Q` / `Y`
2. 再选数据路线：`纯量价` / `量价 + provider 基本面` / `量价 + PIT 财务`
3. 如果走 PIT 路线，先过覆盖率体检
4. 按 benchmark protocol 先跑 `price-only -> PIT-only -> hybrid`
5. 最后才在同一条路线里比较模型：`ridge` / `xgb_regressor` / `xgb_ranker` / `elasticnet`

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

1. 想先确认主流程和命令入口，从“月度 + provider 基本面”开始。
2. 想做正式的财报驱动研究，默认从“季度 + PIT 财务”开始。
3. 想做低频调仓，但暂时不想准备本地 PIT 财务文件，从“季度 + provider 基本面对照”开始。
4. 年度 `Y` 先当探索路线。先把季度路线跑稳，再上年度。

这里多记一条经验：

* 对 PIT 财务路线，先过覆盖率体检，并把 `Fill Dependence` 调到可接受状态，再谈模型比较。

## 2. 先看研究矩阵

这张表只回答“你应该从哪一格开始”。它不表示每一格都有完整的内置模板。

| 频率 | 纯量价 | 量价 + provider 基本面 | 量价 + PIT 财务 |
| --- | --- | --- | --- |
| 月度 `M` | 需要本地派生。可从 `configs/experiments/variants/hk_selected__xgb_regressor.yml` 关掉 `fundamentals` 开始。 | 现成模板最完整：`configs/experiments/variants/hk_selected__xgb_regressor.yml`、`configs/experiments/variants/hk_selected__xgb_ranker_pairwise.yml`、`configs/experiments/variants/hk_selected__ridge_a1.yml`、`configs/experiments/variants/hk_selected__elasticnet_a0.1_l0.5.yml`。 | 需要本地派生；当前没有单独维护的月度 PIT benchmark 模板。 |
| 季度 `Q` | 有官方 benchmark 起点：`configs/experiments/baseline/hk_selected__quarterly_price_only.yml`。 | 需要本地派生；当前没有单独维护的季度 provider 基本面对照模板。 | 有官方 benchmark 阶梯：`configs/experiments/baseline/hk_selected__quarterly_pit_core.yml`、`configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml`，以及同一 hybrid 单元上的 challenger 模板。 |
| 年度 `Y` | 代码支持，当前没有内置模板。建议从月度或季度配置派生。 | 代码支持，当前没有内置模板。建议从季度 provider 路线派生。 | 代码支持，当前没有内置模板。建议从季度 PIT 路线派生。 |

读表时记住两点：

* 做模型比较时，只在同一格里换模型。
* 跨格比较时，你比较的是整条研究路线，不只是模型。

## 3. 月度 `M` 怎么选

月度路线适合日常基线、模型横向对比和更高样本量的研究。

| 数据路线 | 起点配置 | 需要本地 PIT 文件 | 更适合回答的问题 |
| --- | --- | --- | --- |
| 纯量价 | 从 `configs/experiments/variants/hk_selected__xgb_regressor.yml` 派生，设 `fundamentals.enabled=false` | 否 | 先看技术面和量价本身有没有稳定信号 |
| 量价 + provider 基本面 | `configs/experiments/variants/hk_selected__xgb_regressor.yml` 及其显式模型模板 | 否 | 日常基线、四模型 PK、估值与技术面的混合信号 |
| 量价 + PIT 财务 | 需要本地派生 | 是 | 想保留月度调仓，同时把财报字段并进模型 |

月度路线当前最适合做四模型比较。原因很简单：

* 内置模板最完整
* 样本点更多
* 调参与回看结果都更直接

如果你只想先把四模型跑一遍，优先从这一块开始。

## 4. 季度 `Q` 怎么选

季度路线适合低频调仓和财报驱动研究。

这里先记住两件事：

* 季度路线仍然读取日线行情。变化的是标签、评估和回测的 rebalance 频率。
* PIT 财务只在披露日更新。季度频率更适合作为正式研究起点。

| 数据路线 | 起点配置 | 需要本地 PIT 文件 | 更适合回答的问题 |
| --- | --- | --- | --- |
| 纯量价 | `configs/experiments/baseline/hk_selected__quarterly_price_only.yml` | 否 | 低频调仓下，慢量价特征本身有没有方向 |
| 量价 + provider 基本面 | 需要本地派生；可从 `configs/experiments/baseline/hk_selected.yml` 切到 `Q` 并保留 provider fundamentals | 否 | 低频估值字段本身有没有方向；是否值得再叠加量价 |
| 量价 + PIT 财务 | `configs/experiments/baseline/hk_selected__quarterly_pit_core.yml`、`configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml`，以及同一 hybrid 单元上的模型 challenger | 是 | 财报披露节奏对齐后，core PIT 和慢量价特征有没有 alpha |

### 4.1 季度 PIT 的默认研究流程

如果你的目标是研究财报驱动信号，推荐按下面的顺序走：

1. 准备 `pipeline_fundamentals.parquet`
2. 先跑 `csml rqdata inspect-hk-pit-coverage`
3. 如果 `Fill Dependence` 还是红灯，先缩窄 PIT 特征，再重跑体检
4. 先做三条 benchmark：`季度纯量价`、`季度 core PIT`、`季度 core PIT + 慢量价`
5. 确认基线稳定后，再做四模型 PK

这条流程的重点是先判断数据和信号，再判断模型。

这里的 `core PIT` 指高覆盖财务主项和少量稳健派生项。低覆盖字段先不要放进起步配置。

**重要更新（2026-03）**：最新实验表明，在季度 PIT 路线上，`add_indicators: false`（不添加缺失指示器）+ `xgb_ranker` 的组合显著优于其他配置。具体结论：

- `pit_core_hybrid` + `add_indicators: false` + `xgb_ranker`：IC 0.097，Sharpe 1.009，Score 0.959
- 同特征 + `xgb_regressor`：IC 0.072，Sharpe 2.066（但样本太短，仅 3 个 period）
- 同特征 + `add_indicators: true`（原版 hybrid）：IC 0.092，Sharpe 0.34，Score 0.249

核心发现：去掉 `*_missing` 指示器后，模型真正学到了基本面信号，而非依赖"哪些公司财报缺了"这个捷径。

如果体检结果说明 source-level 覆盖很差，先回到资产准备。  
如果源头覆盖还可以，但 selected features 的 complete-case 结果很差，先缩窄特征集。  
如果 `季度 core PIT + 慢量价` 没有明显优于 `季度纯量价`，先不要急着继续调模型。

体检命令示例：

```bash
csml rqdata inspect-hk-pit-coverage \
  --config configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml \
  --mode both
```

看 `Fill Dependence` 时，先按这套门槛判断：

* `core PIT`：`retention_ratio_after_ffill >= 0.60` 记为绿灯，`0.30-0.59` 记为黄灯，`< 0.30` 记为红灯。
* `core_hybrid`：`retention_ratio_after_ffill >= 0.40` 记为绿灯，`0.15-0.39` 记为黄灯，`< 0.15` 记为红灯。
* 如果 `periods_after_missing_fill=0`，直接按红灯处理。

`Fill Dependence` 是红灯时，先停下来改资产或特征集。  
`Fill Dependence` 是黄灯时，先看 `Worst Features`，删掉最拖后腿的一两个字段，再重跑体检。  
`Fill Dependence` 是绿灯时，再继续跑三条基线和四模型 PK。

仓库现在已经把这套 benchmark protocol 的标准入口沉淀成正式配置：

* `configs/experiments/baseline/hk_selected__quarterly_price_only.yml`
* `configs/experiments/baseline/hk_selected__quarterly_pit_core.yml`
* `configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml`
* `configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_ridge.yml`
* `configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_xgb_ranker.yml`
* `configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_elasticnet.yml`

**推荐配置**（2026-03）：

对默认 benchmark protocol，当前更稳妥的设置是：

* 保留 `features.missing.add_indicators: false`
* 先把 `configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml` 当作强 benchmark
* 再用 `configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_xgb_ranker.yml` 作为 primary challenger

如果你还想看更宽的 PIT 财报路线，仓库里另外还有这几份季度模板：

* `configs/experiments/variants/hk_selected__pit_quarterly_financial_ml.yml`
* `configs/experiments/variants/hk_selected__pit_quarterly_financial_linear.yml`
* `configs/experiments/variants/hk_selected__pit_quarterly_hybrid.yml`

这里最容易混淆的点是：

* 这三份文件是三条季度实验路线。
* 它们不是“四种模型”的一一对应模板。
* 如果你要做严格的四模型 PK，应该先选其中一条作为路线基线，再只改 `model`。

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

## 6. 四模型 PK 放在流程后段

仓库当前支持四种模型：

* `xgb_regressor`
* `xgb_ranker`
* `ridge`
* `elasticnet`

推荐做法很固定：

1. 先把数据路线和特征口径定住。
2. 先跑完 `季度纯量价`、`季度 core PIT`、`季度 core PIT + 慢量价` 这三条基线。
3. 再选定研究矩阵里的一个单元；对标准季度 PIT protocol，直接用官方 hybrid benchmark。
4. 标准四模型 PK 直接使用官方 hybrid benchmark 和三个 challenger 模板；只有更细的实验再复制到 `configs/local/`。
5. 保持下面这些块尽量不变：
   `universe`、`fundamentals`、`features`、`label`、`eval`、`backtest`
6. 只改两类内容：
   `model`
   `eval.run_name`
7. 跑四份配置，再统一 `summarize`。

**重要更新（2026-03）**：最新实验表明，季度 PIT 路线的最佳实践是：

1. **一定要设置 `features.missing.add_indicators: false`**，去掉 `*_missing` 指示器
2. **优先使用 `xgb_ranker`**，在基本面路线上表现显著优于 `xgb_regressor`

模型 benchmark 现在有现成模板：

* `xgb_regressor`：`configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml`
* `xgb_ranker`：`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_xgb_ranker.yml`
* `ridge`：`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_ridge.yml`
* `elasticnet`：`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_elasticnet.yml`

如果你现在要做“季度 + 量价 + PIT 财务”的四模型 PK，更稳妥的起点是：

* 先跑完 `季度纯量价`、`季度 core PIT`、`季度 core PIT + 慢量价`
* 用 `configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml` 固定研究单元
* 再只切到同一单元上的 `ridge`、`xgb_ranker`、`elasticnet`
* 只改 `model` 和 `eval.run_name`

这一步更适合放在下面这些条件都满足之后：

* PIT 覆盖率体检已经跑过
* `季度 core PIT` 已经能稳定训练
* `季度 core PIT + 慢量价` 已经证明比更简单的基线更有信息量

模型分组可以直接这样记：

* 线性模型：`ridge`、`elasticnet`
* 非线性模型：`xgb_regressor`、`xgb_ranker`

示例：

```bash
# 三条 benchmark
csml run --config configs/experiments/baseline/hk_selected__quarterly_price_only.yml
csml run --config configs/experiments/baseline/hk_selected__quarterly_pit_core.yml
csml run --config configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml

# 同一 hybrid 单元上的 challenger
csml run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_ridge.yml
csml run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_xgb_ranker.yml
csml run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_elasticnet.yml

csml summarize \
  --runs-dir artifacts/runs \
  --run-name-prefix hk_sel_q_benchmark_ \
  --sort-by score
```

如果你要继续细化线性模型，再单独用 `csml sweep-linear` 跑 `ridge` 和 `elasticnet`。前提仍然是先把研究单元固定住。

## 7. 什么时候需要准备 PIT 财务文件

只有在你走“量价 + PIT 财务”这条路线时，才需要本地 PIT fundamentals 文件。

判断方法很简单：

* `fundamentals.source=provider`：不需要本地 PIT 文件
* `fundamentals.enabled=false`：不需要本地 PIT 文件
* `fundamentals.source=file`：需要本地 PIT 文件

最短准备流程：

```bash
csml rqdata mirror-hk-pit-financials \
  --config configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml \
  --name hk_selected_pit_2011_2025_latest \
  --fields-file configs/field_profiles/hk_financial_fields_starter.txt \
  --start-quarter 2011q1 \
  --end-quarter 2025q4 \
  --date 20260312

csml rqdata build-hk-pit-fundamentals \
  --asset-dir artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest \
  --out artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest/pipeline_fundamentals.parquet

csml rqdata inspect-hk-pit-coverage \
  --config configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml \
  --mode both
```

如果你要做“PIT 财务 + provider valuation”叠加实验，先不要把日频估值写回稀疏 PIT 文件后直接解释结果。更稳妥的做法是让 pipeline 走双路 merge：主 `fundamentals.file` 保留 PIT 财报，provider valuation 用 `fundamentals.provider_overlay` 直接并到 daily panel。对应的 `G4_fixed` 本地配置已经按这个口径改好；例如你可以先在 `configs/local/<your_g4_fixed_config>.yml` 派生一份，然后直接跑：

```bash
csml run --config configs/local/<your_g4_fixed_config>.yml

uv run python -m csml.research.hk_selected_provider_valuation_audit \
  --run-dir artifacts/runs/<run_dir>
```

这样至少能先把 daily overlay 路径上的覆盖率看清楚，再决定要不要继续解释 G4 类实验；如果 `valuation_age_days` 不是接近 0 或缺失，而是重新出现长尾陈旧值，就说明链路又被改坏了。

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
* 体检输出里的 `Complete Case` 和 `Recent Quarters` 是否还支持当前研究口径
