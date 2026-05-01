# 指标与结果解读

本页说明一次 run 结束后，常见评估指标分别代表什么、该先看哪些文件，以及哪些指标容易被误读。\
本页不展开字段级技术契约；字段和产物清单请看 `docs/outputs.md`。\
适合谁：需要判断模型结果、解释回测表现、排查异常 run 的研究员或开发者。\
相关页面：`docs/outputs.md`、`docs/config.md`

默认产物目录通常是：

```text
artifacts/runs/<run_name>_<timestamp>_<hash>/
```

快速看一轮结果时，先打开这些文件：

* `summary.json`
* `config.used.yml`
* `positions_current.csv` 或 `positions_current_live.csv`
* `ic_test.csv`
* `quantile_returns.csv`
* `backtest_net.csv`

## 先看哪些指标

一次 run 的默认结果大致分成五层：

| 层级 | 主要字段或文件 | 回答的问题 |
| --- | --- | --- |
| 样本质量 | `summary.json -> data / universe` | 本轮样本是否足够，是否被过滤得太狠 |
| 预测质量 | `ic`、`pearson_ic`、`quantile_mean`、`long_short` | 高分股票是否整体比低分股票更好 |
| 稳定性 | `train_ic`、`cv_ic`、`final_oos`、`walk_forward`、`rolling_ic`、`permutation_test` | 结果是否只在某段样本里好看 |
| 回测结果 | `backtest_net.csv`、`backtest.stats`、`backtest.active` | 扣除交易成本后策略是否还能赚钱 |
| 组合诊断 | `backtest.exposure`、行业和风格暴露 CSV | 组合是否偏向某些风格、行业或基准 |

当前默认产物里没有直接给出这些机构级或解释类指标：

* 资金容量上限，例如“这套策略最多能承载多少资金”或“需要几天才能完成建仓/平仓”。
* SHAP 局部解释。
* 单独的极差胜率字段。可以用 `quantile_returns.csv` 自行计算每期 `Q_high - Q_low > 0` 的比例。

仓库也提供了一些离线研究工具。它们需要单独运行，不会自动出现在每次 `cstree run` 结果里：

* `cstree feature-evidence generate-ablation` / `summarize-ablation`：生成和汇总特征族消融实验，比较相对 baseline 的增量。
* `cstree feature-evidence permutation-importance`：基于已有 scored artifact 评估单特征和特征族的置换重要度。
* `cstree feature-evidence factor-ic`：基于包含 feature 列的 parquet 输出单因子 IC、分位收益和覆盖率。
* `cstree construction-grid`：固定模型分数，只比较组合构建参数带来的变化。
* `cstree benchmark-ladder`：把策略收益曲线和多组 benchmark 逐层对比。

容易混淆的三件事：

* `backtest.execution` 里的 `adv20_amount`、`participation`、`min_amount` 是流动性和冲击成本压力测试的代理参数。
* `backtest.exposure` 用来诊断风格和行业暴露。
* 上面两类数据都不能直接等同于完整的机构级容量模型。

## 查阅顺序

`summary.json` 是总览入口。常见节点如下：

* `data`：样本区间、原始行数、provider 来源、缓存标签和交易日历。
* `universe`：股票池模式、单日最小样本数、被丢弃的日期数、停牌处理方式。
* `eval`：预测质量、分位收益、评估侧换手、训练期对照和稳定性检验。
* `backtest`：Top-K 回测配置、收益统计、交易成本和 benchmark 对比。
* `final_oos`：最终留出期结果。它和 `eval/backtest` 的结构大体一致。
* `walk_forward`：滚动前向验证汇总，以及各窗口明细文件路径。

需要看时间序列细节时，再打开这些 CSV：

* `ic_test.csv` / `ic_pearson_test.csv`
* `quantile_returns.csv`
* `turnover_eval.csv`
* `backtest_net.csv` / `backtest_gross.csv`
* `backtest_turnover.csv`
* `walk_forward_summary.csv`
* 离线协议生成的 `artifacts/reports/*.csv` 或 `*.json`

完整产物清单见 `docs/outputs.md`。

## 样本质量

样本质量字段主要在 `summary.json -> data` 和 `summary.json -> universe`。

重点看这些字段：

* `symbols`：本轮出现过的标的数量。
* `rows`：原始数据行数。
* `rows_model`：完成特征、标签和过滤后，真正进入模型的行数。
* `min_symbols_per_date`：保留某个交易日所需的最少股票数。
* `dropped_dates`：因为样本数太少而被整体丢弃的交易日数量。
* `mode`：股票池模式，常见值有 `static`、`pit`、`auto`。
* `drop_suspended` / `suspended_policy`：停牌股票是被删除，还是保留并标记为不可交易。

这些字段回答两个问题：

* 模型看到的样本量是否足够。
* 样本是否因为股票池变化、停牌或特征缺失被大幅压缩。

如果 `rows_model` 远低于 `rows`，或 `dropped_dates` 很高，后面的 IC、分位收益和回测结果都要保守解读。

## 标签与分数

标签定义回答“模型到底在预测什么”。相关配置主要在 `label` 下。

常看字段：

* `target_col`：通常是 `future_return`。
* `horizon_days`：固定持仓期长度。
* `horizon_mode`：`fixed` 表示固定天数，`next_rebalance` 表示持有到下一次调仓。
* `rebalance_frequency`：使用 `next_rebalance` 时，未来收益对齐到哪个调仓频率。
* `shift_days`：信号日到实际入场日的间隔。
* `train_target_transform`：训练前是否对标签做横截面 `zscore`、`rank` 等变换。

看任何指标前，先确认标签口径。否则你看到的 IC 或回测收益，可能对应的持仓周期和你以为的不一样。

### 分数字段

如果启用了 `eval.save_scored_artifact=true`，`eval_scored.parquet` 通常包含三类分数：

* `pred`：模型原始输出。
* `signal_eval`：评估侧使用的方向校正分数。
* `signal_backtest`：回测侧使用的最终分数。

日常排序、分位收益、Top-K 和回测解读，优先使用 `signal_eval` 或 `signal_backtest`。直接看 `pred` 容易忽略方向翻转。

### Ranker 与 Regressor

`xgb_regressor` 或线性回归的输出更像连续预测值。它能否解释成预期收益率，取决于训练标签是否仍是原始收益率。

`xgb_ranker` 的输出是同一交易日截面内的相对排序分数。它回答的是“这些股票谁更靠前”，通常不适合解释成未来涨幅。

简单规则：

* 训练标签是原始 `future_return`，且没有做尺度变换时，模型分数才有预期收益率的参考意义。
* 训练标签做过 `zscore`、`rank` 或其他标准化后，分数更适合叫 alpha score 或排序分数。
* `quantile_mean`、`long_short` 和回测结果负责把抽象分数连接到真实未来收益。
* `label.train_target_transform != none` 时，`mae`、`rmse`、`r2` 更适合作为排障指标。

## 预测质量

预测质量指标通常在 `summary.json -> eval`。

### IC

系统默认输出两类 IC：

* `ic`：Spearman Rank IC，衡量预测排序和真实收益排序是否一致。
* `pearson_ic`：Pearson IC，衡量预测幅度和真实收益是否有线性关系。

它回答什么：

* `ic`：模型给出的排名是否接近未来真实收益排名。
* `pearson_ic`：模型分数强弱是否接近未来收益强弱。

怎么看：

* 先看 `mean`。它代表平均方向和平均强度。
* 再看 `ir`。它代表这项表现是否稳定。
* `t_stat` 和 `p_value` 只作参考。金融时间序列很难满足严格的独立同分布假设。

常见字段：

* `n`：有效交易日或截面数量。越小越容易被偶然波动影响。
* `mean`：平均值。
* `std`：时间序列标准差。越高说明表现越不稳定。
* `ir`：`mean / std`，用于粗看稳定性。
* `t_stat`：平均值相对标准误的偏离倍数。
* `p_value`：和 `t_stat` 相关的显著性参考值。

文件：

* `ic_test.csv`
* `ic_pearson_test.csv`

计算方式：

1. 按 `trade_date` 切成单日截面。
2. 每个交易日各算一次相关系数。
3. 把这些单日 IC 连成时间序列，再汇总 `mean`、`std`、`ir` 等字段。

### 训练期对照与方向校正

相关字段：

* `train_ic`
* `train_ic_raw`
* `train_pearson_ic`
* `cv_ic`
* `cv_ic_raw`
* `signal_direction`
* `signal_direction_mode`

它回答什么：

* 高分最终应该代表多头，还是应该反向使用。
* 换一个时间窗口后，信号是否仍然有效。

怎么看：

* `train_ic`：训练期、方向校正后的 Rank IC。
* `train_ic_raw`：训练期、方向校正前的 Rank IC。系统常用它判断是否需要乘 `-1`。
* `train_pearson_ic`：训练期、方向校正后的 Pearson IC。
* `cv_ic`：交叉验证后的 IC 汇总，更关注跨窗口稳定性。
* `cv_ic_raw`：交叉验证中方向校正前的 IC。
* `signal_direction`：最终方向因子，通常为 `1` 或 `-1`。
* `signal_direction_mode`：方向来自固定配置、`train_ic`，还是 `cv_ic`。

### 误差指标

`error_metrics` 包含：

* `n`
* `mae`
* `rmse`
* `r2`

它回答什么：

* 模型是否严重退化。
* 输出是否接近常数。
* 标签是否有明显异常。

怎么看：

* `n`：参与误差统计的样本量。
* `mae`：平均绝对误差。
* `rmse`：对大误差更敏感，适合发现严重失真。
* `r2`：模型解释了多少方差。截面选股里它经常不高。

常见误解：

* 对 `xgb_ranker` 这类排序模型，`mae`、`rmse`、`r2` 主要用于排障。
* 训练标签做过 `zscore` 或 `rank` 后，误差指标的绝对大小通常没有直接业务含义。
* 截面选股更关心排序，不能因为 `r2` 不高就直接否定模型。

### 分位数收益

相关字段和文件：

* `summary.json -> eval.quantile_mean`
* `summary.json -> eval.long_short`
* `quantile_returns.csv`

它回答什么：

* 按模型分数从低到高分组后，高分组未来收益是否更好。
* 最高分组和最低分组之间的收益差有多大。

怎么看：

* `quantile_mean`：各分位组的平均未来收益。重点看从低分到高分是否大体递增。
* `long_short`：最高分位均值减最低分位均值。

计算方式：

1. 每个 `trade_date` 内按预测分数排序。
2. 把股票分成 `n_quantiles` 组。
3. 分别计算每组未来收益均值。
4. 汇总到 `quantile_returns.csv`。
5. `summary.json -> eval.quantile_mean` 是时间轴上的平均结果。

注意：

* 某天股票数少于 `n_quantiles` 时，该天不会进入分位统计。
* 对截面模型，分位收益的单调性通常比单个分位点的绝对值更重要。
* 极差胜率可以从 `quantile_returns.csv` 里自行计算。

### 换手率与缓冲区

相关字段和文件：

* `turnover_mean`
* `turnover_count`
* `buffer_exit`
* `buffer_entry`
* `turnover_eval.csv`

它回答什么：

* 每次调仓平均替换了多少持仓。
* 缓冲区是否减少了因为小幅排名变化带来的无效换手。

怎么看：

* `turnover_mean`：平均换手比例，越高代表组合换得越快。
* `turnover_count`：参与统计的调仓次数。太低时，`turnover_mean` 参考价值下降。
* `buffer_exit`：已有持仓跌出 Top-K 一点点时，允许继续保留。
* `buffer_entry`：新股票进入组合前，需要超过门槛多少。

### 命中率与 Top-K 正收益占比

相关字段：

* `hit_rate`
* `topk_positive_ratio`

它回答什么：

* 预测方向是否经常正确。
* 实际买入的 Top-K 股票里，有多少最终收益为正。

怎么看：

* `hit_rate`：预测值和真实收益符号一致的比例。
* `topk_positive_ratio`：每个调仓日 Top-K 股票未来收益为正的比例，再对时间求平均。

注意：

* 这两个指标提供“方向感”，不能替代 Rank IC、分位收益和回测结果。
* 单边行情里，排序不错的模型也可能因为绝对涨跌方向判断不准，导致 `hit_rate` 不好看。

### 可选切面

启用对应配置后，系统还会输出：

* `bucket_ic` / `bucket_ic_file`
* `rolling_ic`
* `permutation_test`

常见文件：

* `bucket_ic.csv`
* `ic_rolling_6m.csv`
* `ic_rolling_12m.csv`
* `permutation_test.csv`

它们分别回答：

* `bucket_ic`：信号在哪些子样本桶里更有效，例如行业、市值或流动性分组。
* `rolling_ic`：信号是否只在某段历史窗口有效。
* `permutation_test`：真实模型是否明显强于“打乱标签后的噪音模型”。

注意：

* `permutation_test` 是整体标签打乱后的噪音基线。
* 它和某个具体 feature 的 permutation importance 不是同一件事。
* 单特征边际贡献通常需要消融、drop-column、SHAP 或特征置换重要度来评估。

## 回测指标

回测指标通常在 `summary.json -> backtest`。

### 净收益与毛收益

相关文件：

* `backtest_net.csv`
* `backtest_gross.csv`

优先看净收益。毛收益适合观察未扣成本前的信号表现；净收益反映交易成本和滑点之后还能留下多少。

### 核心统计

`summary.json -> backtest.stats` 常见字段：

* `periods`
* `total_return`
* `ann_return`
* `ann_vol`
* `sharpe`
* `max_drawdown`
* `avg_holding`
* `periods_per_year`
* `avg_turnover`
* `avg_cost_drag`

它回答什么：

* 策略最终赚了多少。
* 收益曲线波动和回撤有多大。
* 换手和成本是否吞掉了收益。

怎么看：

* `periods`：参与统计的回测周期数。
* `total_return`：整个回测区间累计收益。
* `ann_return`：年化收益。
* `ann_vol`：年化波动。
* `sharpe`：单位风险对应的收益。
* `max_drawdown`：最大回撤。
* `avg_holding`：平均持有时间，通常近似为交易日数。
* `periods_per_year`：年化换算用的周期数。
* `avg_turnover`：每次调仓平均换手。
* `avg_cost_drag`：每期平均被成本拖累多少收益，单位通常是基点。

### 风险指标

额外风险字段：

* `sortino`
* `calmar`
* `drawdown_duration`
* `recovery_time`
* `drawdown_duration_days`
* `recovery_time_days`
* `skew`
* `kurtosis`
* `var_95`
* `cvar_95`

它们补充说明：

* 下行风险是否过大。
* 最大回撤持续了多久。
* 收益是否过度依赖少数极端行情。

怎么看：

* `sortino`：比 `sharpe` 更关注亏损波动。
* `calmar`：收益相对最大回撤是否划算。
* `drawdown_duration` / `drawdown_duration_days`：从前高跌到低点的周期数或自然日数。
* `recovery_time` / `recovery_time_days`：从低点回到前高的周期数或自然日数。
* `skew`：收益分布偏度。明显为负时，要警惕突发大亏。
* `kurtosis`：收益分布峰度。越高说明极端波动更常见。
* `var_95`：历史最差 5% 情况下的单期收益下限。
* `cvar_95`：落入最差 5% 后的平均损失，通常比 `var_95` 更保守。

### Benchmark 与主动收益

配置 `benchmark_symbol` 或 `benchmark_returns_file` 后，系统会输出：

* `summary.json -> backtest.benchmark`
* `summary.json -> backtest.active`
* `backtest_benchmark.csv`
* `backtest_active.csv`

主动收益常看字段：

* `tracking_error`
* `information_ratio`
* `beta`
* `alpha`
* `corr`
* `active_total_return`

它回答什么：

* 策略和基准走势差多远。
* 偏离基准后有没有换来稳定超额收益。
* 收益有多少来自市场 beta，有多少更像策略自身贡献。

怎么看：

* `tracking_error`：策略收益和基准收益的偏离波动。
* `information_ratio`：主动收益相对主动风险是否划算。
* `beta`：策略和基准的系统性联动。
* `alpha`：剥离 beta 后的独立超额收益。
* `corr`：策略收益和基准收益的相关性。
* `active_total_return`：复利后相对基准的累计超额收益。

### 风格与行业暴露

如果回测有持仓，且 panel 里有可解析的暴露因子，系统会输出：

* `summary.json -> backtest.exposure`
* `backtest_style_exposure.csv`
* `backtest_industry_exposure.csv`
* `backtest_active_exposure_summary.csv`

风格暴露使用 best-effort 诊断。系统会尽量解析：

* `size`
* `value`
* `quality`
* `momentum`
* `low_vol`
* `beta`

它回答什么：

* 组合是否偏向大市值、价值、质量、动量、低波或 beta。
* 行业权重是否明显偏离全市场等权或市值加权基准。

计算概要：

1. 每个 `rebalance_date` 取当期持仓和同日横截面 panel。
2. 用现有因子列或历史价格估算风格值。
3. 分别计算 `portfolio_long`、`portfolio_short`、`portfolio_net` 的风格暴露。
4. 和全市场等权、市值加权基准对比，得到主动暴露。

注意：

* 这些输出只说明组合倾斜方向。
* 系统当前不会自动施加硬性风格约束。
* 仓库没有内置完整 Barra 风险预测模型。
* `style_factors[*].available=false` 表示本轮数据缺少对应特征列。
* 启用 `final_oos` 后，类似结构也会出现在 `summary.json -> final_oos -> backtest -> exposure`。

### 滚动 Sharpe

启用后会输出：

* `summary.json -> backtest.rolling_sharpe`
* `backtest_rolling_sharpe_6m.csv`
* `backtest_rolling_sharpe_12m.csv`

它回答什么：

* 策略是否只在某一段顺风行情里表现好。

怎么看：

* 滚动窗口内反复计算 `mean`、`std` 和 `sharpe`。
* 如果只在少数窗口里高，稳定性需要打折。

## 最终留出期

启用 `eval.final_oos` 后，`summary.json -> final_oos` 会输出一套独立结果。

常见内容：

* `ic`
* `pearson_ic`
* `error_metrics`
* `hit_rate`
* `topk_positive_ratio`
* `bucket_ic`
* `rolling_ic`
* `quantile_mean`
* `long_short`
* `turnover_mean`
* `backtest`
* `positions`

`final_oos` 样本不参与训练、拟合或参数选择。它适合当作交付前的最后一层独立验证。

如果 in-sample 结果很好，但 `final_oos` 很差，优先排查过拟合。

## Walk-Forward 与特征重要度

### Walk-Forward

启用 `eval.walk_forward` 后会输出：

* `walk_forward_summary.csv`
* `walk_forward_feature_importance.csv`
* `walk_forward_feature_stability.csv`

它回答什么：

* 换一段训练/测试窗口后，IC 和回测收益是否还稳定。
* 核心特征是否在多个窗口里反复出现。

怎么看：

* `walk_forward_summary.csv` 可以理解为每个窗口的一份小型成绩单。
* `walk_forward_feature_stability.csv` 的 `top_k_hit_rate` 和 `nonzero_hit_rate` 可用于判断特征是偶然出现，还是持续有用。

### CPCV

运行 `cstree cpcv` 后会输出：

* `cpcv_splits.csv`
* `cpcv_path_returns.csv`
* `cpcv_path_metrics.csv`
* `cpcv_summary.json`

它回答什么：

* 候选配置是否只在某一条历史样本外路径上好看。
* 换成多条组合式样本外路径后，Sharpe、IC、long-short、回撤、换手和成本的分布是否仍可接受。

怎么看：

* `cpcv_summary.json` 里的 `sharpe_median`、`sharpe_p25`、`sharpe_min` 和 `positive_sharpe_ratio` 是晋升前最直接的稳健性指标。
* `ic_median` 与 `long_short_median` 用来确认信号层方向是否仍然成立。
* `max_drawdown_p10`、`turnover_median` 和 `cost_drag_median` 用来检查路径分布里的风险与交易成本。
* CPCV 是 shortlisted candidate 的最终审计 sidecar，不替代 walk-forward，也不替代 final OOS。

### Feature Importance

默认情况下，只要模型训练成功且支持重要度输出，系统会写出：

* `feature_importance.csv`

重要度来源记录在：

* `summary.json -> eval.feature_importance_source`

常见来源：

* XGBoost 模型：来自模型原生 `feature_importances_`。
* 线性模型：来自绝对值系数 `coef_abs`。

辅助字段：

* `feature_importance_nonzero`
* `zero_feature_importance`
* `constant_prediction`

怎么看：

* `feature_importance`：模型训练时主要用了哪些输入特征。
* `feature_importance_source`：重要度计算口径，不同模型之间不要直接比绝对值。
* `feature_importance_nonzero`：非零重要度特征数量。很少时要排查模型是否没有利用信息。
* `zero_feature_importance`：所有特征重要度都是零，通常表示 run 已退化。
* `constant_prediction`：不同股票得到几乎相同分数，通常也是退化信号。

注意：

* 重要度高的特征，不一定单独拿出来也能赚钱。
* 单因子有效性要看该因子的 IC、分位收益、long-short，或单独建模验证。
* 联合模型里的边际贡献需要消融、drop-column、SHAP 或特征置换重要度等方法评估。

### 单因子 IC

`cstree feature-evidence factor-ic` 用来把单个 feature 当作原始排序信号，逐列计算单因子证据。

它输出：

* `ic_mean` / `ic_ir`：单因子 Spearman Rank IC 的均值和稳定性。
* `pearson_ic_mean` / `pearson_ic_ir`：单因子 Pearson IC 的均值和稳定性。
* `q1_return` / `qN_return` / `long_short`：按因子原始方向分组后的低分组、高分组和高减低收益。
* `coverage`：feature 与目标都非空的样本占目标非空样本比例。
* `positive_ic_ratio`：日度 Rank IC 大于 0 的比例。

常用输入是 run 目录里的 `dataset.parquet`，因为它保留 feature 列。`eval_scored.parquet` 不一定包含全部 feature 列，除非相关列被额外保留下来。

## 常见误读

### 模型分数不等于未来涨幅

`future_return` 才是评估标签。`pred`、`signal_eval`、`signal_backtest` 是模型分数。

只有在训练标签是原始收益率，且没有做尺度变换时，分数才有预期收益率的参考意义。做过 `zscore`、`rank` 或其他标准化后，分数更适合理解成排序分。

把排序分转成真实收益判断，要看 `IC`、`quantile_mean`、`long_short` 和回测。

### Ranker 和 Regressor 可以共用指标，但语义不同

两类模型都可以看 Rank IC、分位收益、Top-K 和回测。

区别在于：

* `regressor` 分数更像连续预测值。
* `ranker` 分数更像同日截面内的排序。
* `ranker` 不宜过度关注 `mae`、`rmse`、`r2`。
* `regressor` 如果训练标签做过相对化处理，也不宜把分数解释成绝对百分比收益。

### 模型分数、特征重要度、单因子有效性是三件事

* 模型分数：决定当前标的在选股队列中的位置。
* `feature_importance`：说明模型训练时主要依赖哪些特征。
* 单因子有效性：评估某个因子单独使用时是否有预测能力。

重要度高，只能说明联合模型里用到了它。它单独是否有效，还要单独验证。

### 默认 permutation test 不是特征置换重要度

默认 `permutation_test` 打乱的是训练标签，用来构造噪音基线。

特征置换重要度评估的是“扰动某个 feature 后，模型表现下降多少”。两者目标不同。

### `hit_rate` 是辅助指标

截面选股更关心：

* 高分股票是否整体优于低分股票。
* 收益差是否稳定。
* 扣成本后是否还有净收益。

因此，优先看：

* `RankIC`
* `quantile_mean` 单调性
* `long_short`
* 净回测收益
* 主动收益

`hit_rate` 和 `topk_positive_ratio` 适合作为补充胜率视角。

### 分桶 IC、暴露分析和容量压力测试各看一件事

* `bucket_ic`：信号在哪些子样本里更有效。
* `backtest.exposure`：组合实际偏向哪些风格或行业。
* execution 参数：流动性和交易冲击下，收益是否明显衰退。

某个行业的 `bucket_ic` 好，不能直接推出组合会重仓该行业。组合行业偏离明显，也不能直接推出信号只在该行业有效。

execution 压力测试变差时，优先看流动性和容量风险。

## 推荐阅读顺序

常规研究验收按这个顺序看：

1. `summary.json -> data / universe`
2. `summary.json -> eval.ic / eval.pearson_ic / eval.quantile_mean / eval.long_short`
3. `summary.json -> backtest.stats`
4. `summary.json -> backtest.active` 或 `backtest.benchmark`
5. `summary.json -> final_oos`
6. `walk_forward_summary.csv`
7. `feature_importance.csv`

只想快速判断某次 run 是否值得继续分析时，看这五点：

1. 样本是否被过度过滤。
2. `eval.ic.mean` 和 `eval.ic.ir` 是否稳定。
3. `quantile_mean` 是否大体单调。
4. 净收益、最大回撤和成本拖累是否可接受。
5. `final_oos` 与 `walk_forward` 是否支持前面的结论。
