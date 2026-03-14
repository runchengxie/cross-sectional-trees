# 指标与结果解读

本页解决什么：指标与结果文件的解读方式。
本页不解决什么：不展开输出字段的完整契约。
适合谁：需要解释 run 结果的人。
读完你会得到什么：从 `summary.json` 与 CSV 解读结果的路径。
相关页面：`docs/outputs.md`、`docs/config.md`

本页只说明当前仓库已经实现、并且会写入 run 目录的指标与结果文件。

如果你只想先看一次 run 的结果，先读这几个文件：

* `summary.json`
* `config.used.yml`
* `positions_current.csv` 或 `positions_current_live.csv`
* `ic_test.csv`
* `quantile_returns.csv`
* `backtest_net.csv`

默认 run 目录是 `artifacts/runs/<run_name>_<timestamp>_<hash>/`。

## 先看哪里

`summary.json` 是总览。大多数问题都可以先在这里定位。

常见节点：

* `data`：样本区间、行数、provider、缓存和日期信息。
* `universe`：股票池模式、最小样本数、丢弃日期数、停牌处理。
* `eval`：预测质量、分位收益、换手、训练期对照、可选稳健性指标。
* `backtest`：Top-K 回测参数、回测统计、基准与主动收益。
* `final_oos`：最终留出期结果。结构和 `eval/backtest` 基本对应。
* `walk_forward`：滚动窗口验证结果和文件路径。

如果你想看时序而不是摘要，继续读 CSV：

* `ic_test.csv` / `ic_pearson_test.csv`
* `quantile_returns.csv`
* `turnover_eval.csv`
* `backtest_net.csv` / `backtest_gross.csv`
* `backtest_turnover.csv`
* `walk_forward_summary.csv`

完整产物列表见 `docs/outputs.md`。

## 数据与样本质量

这些字段主要在 `summary.json -> data` 和 `summary.json -> universe`。

重点先看：

* `symbols`：本次样本里实际出现过多少只股票。
* `rows`：原始数据总行数。
* `rows_model`：真正进入建模的数据行数。这里已经经过特征、label 和过滤步骤。
* `min_symbols_per_date`：单个交易日至少要有多少只股票才保留。
* `dropped_dates`：因为股票数不足而被丢弃的交易日数量。
* `mode`：股票池模式，常见是 `static`、`pit`、`auto`。
* `drop_suspended` / `suspended_policy`：停牌股票是否剔除，或仅标记为不可交易。

这些字段先回答两个问题：

* 样本够不够大。
* 样本有没有因为股票池、停牌或缺失值而被大幅压缩。

如果 `rows_model` 明显小于 `rows`，或者 `dropped_dates` 很多，后面的 IC、分位收益和回测都需要谨慎解读。

## 标签定义

标签定义决定“模型到底在预测什么”。相关配置主要在 `label`。

高频字段：

* `target_col`：默认是 `future_return`。
* `horizon_days`：固定持有期长度。
* `horizon_mode`：`fixed` 或 `next_rebalance`。
* `rebalance_frequency`：在 `next_rebalance` 模式下决定未来收益窗口。
* `shift_days`：信号日和入场日之间的偏移。

先确认标签定义，再解释指标。否则你看到的 IC 和回测收益，可能并不是你以为的持有期。

## 预测质量指标

这些字段主要在 `summary.json -> eval`。

### IC

默认会输出两类 IC：

* `ic`：Spearman Rank IC。看排序是否有效。
* `pearson_ic`：Pearson IC。看预测幅度和真实收益的线性关系。

直观理解：

* `ic` 可以理解成“模型给股票排的名次，和未来收益排出来的名次像不像”。
* `pearson_ic` 可以理解成“模型不只排对顺序，连强弱幅度也大致对不对”。

对应文件：

* `ic_test.csv`
* `ic_pearson_test.csv`

汇总字段常见为：

* `n`
* `mean`
* `std`
* `ir`
* `t_stat`
* `p_value`

解读建议：

* `mean` 看方向和平均强度。
* `ir` 看稳定性。
* `t_stat` / `p_value` 只能当简化参考。金融时间序列通常不满足独立同分布。

简短理解：

* `mean` 越高，说明平均来说越能排对。
* `ir` 越高，说明不是偶尔灵，而是比较稳定地灵。
* `std` 很大时，通常说明信号只在部分时间段有效。

### 训练期对照与方向校正

这些字段用于判断信号方向和稳定性：

* `train_ic`
* `train_ic_raw`
* `train_pearson_ic`
* `cv_ic`
* `cv_ic_raw`
* `signal_direction`
* `signal_direction_mode`

`signal_direction_mode` 支持 `fixed`、`train_ic`、`cv_ic`。当模型学到的是稳定负相关信号时，系统可以自动翻转方向。

直观理解：

* 这一步是在判断“高分到底该买，还是其实应该反着用”。

### 误差指标

`error_metrics` 包含：

* `mae`
* `rmse`
* `r2`

这组指标不是截面选股里最核心的 KPI，但很适合排查退化模型、常数预测和 label 异常。

直观理解：

* `mae`：平均每次大概错多少。
* `rmse`：对大错更敏感，适合抓明显失真。
* `r2`：模型解释了多少波动。它在截面选股里不一定高，但过低时值得排查。

### 分位收益

分位收益用于回答“高分股票是否真的系统性更好”。

对应文件：

* `quantile_returns.csv`

对应摘要字段：

* `quantile_mean`
* `long_short`

解读建议：

* `quantile_mean` 看各分位平均收益是否单调。
* `long_short` 看最高分位和最低分位之间的收益跨度。

直观理解：

* 如果模型真有用，通常高分组应该整体好于低分组。
* `long_short` 可以粗看“最看好的那组”和“最不看好的那组”差了多少。

### 换手与缓冲区

评估侧换手相关字段：

* `turnover_mean`
* `turnover_count`
* `buffer_exit`
* `buffer_entry`

对应文件：

* `turnover_eval.csv`

`buffer_exit` 和 `buffer_entry` 用来降低调仓抖动。排名轻微波动时，缓冲区可以减少不必要的换手。

直观理解：

* `turnover_mean` 越高，说明组合换得越勤。
* 缓冲区的作用就是少做“今天刚买、下次又卖”的小幅抖动调仓。

### 命中率与 Top-K 正收益占比

这两个字段更直观：

* `hit_rate`
* `topk_positive_ratio`

它们适合回答两个问题：

* 方向判断是否经常做对。
* 选出来的 Top-K 标的里，未来收益为正的比例高不高。

直观理解：

* `hit_rate` 更像“方向对了多少次”。
* `topk_positive_ratio` 更像“真正买进名单里，赚钱的票占多少”。

### 可选拆解

按配置启用时，还会写这些结果：

* `bucket_ic` / `bucket_ic_file`：按行业、市值、流动性等分桶后分别计算 IC。
* `rolling_ic`：滚动 IC 均值与滚动 IC IR。
* `permutation_test`：置换检验结果。

常见文件：

* `bucket_ic.csv`
* `ic_rolling_6m.csv`
* `ic_rolling_12m.csv`
* `permutation_test.csv`

直观理解：

* `bucket_ic` 看信号是不是只在某个角落有效。
* `rolling_ic` 看信号是不是只在某几年有效。
* `permutation_test` 看你看到的效果，是否只是训练噪声。

## 回测指标

这些字段主要在 `summary.json -> backtest`。

### 先看净收益

对应文件：

* `backtest_net.csv`
* `backtest_gross.csv`

日常判断策略时，先看净收益。毛收益只用于看成本前的信号质量。

直观理解：

* 毛收益像“纸面选股能力”。
* 净收益像“把成本算进去以后，真正还能剩多少”。

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

这组字段先回答三个问题：

* 赚没赚钱。
* 波动和回撤大不大。
* 收益是不是被换手和成本吃掉了。

简短理解：

* `ann_return`：年化大概能赚多少。
* `ann_vol`：收益波动有多大。
* `sharpe`：单位风险换来了多少收益。
* `max_drawdown`：历史上最痛的一次回撤有多深。
* `avg_turnover` / `avg_cost_drag`：组合是不是靠高频换手硬撑。

### 风险和尾部

回测还会给出一组更偏交易语境的风险指标：

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

它们分别补充：

* 下行风险和回撤效率。
* 最大回撤持续多久。
* 收益分布是否过度依赖少数极端时期。

直观理解：

* `sortino` 比 `sharpe` 更关注亏钱时的波动。
* `calmar` 看收益相对最大回撤是否划算。
* `drawdown_duration` / `recovery_time` 看难受会持续多久。
* `var_95` / `cvar_95` 看尾部最差情况大概有多差。

### 基准与主动收益

当配置了 `benchmark_symbol` 时，还会写：

* `summary.json -> backtest.benchmark`
* `summary.json -> backtest.active`

对应文件可能包括：

* `backtest_benchmark.csv`
* `backtest_active.csv`

主动收益侧常见字段：

* `tracking_error`
* `information_ratio`
* `beta`
* `alpha`
* `corr`
* `active_total_return`

直观理解：

* `tracking_error`：你和基准偏离得有多大。
* `information_ratio`：这种偏离有没有换来稳定超额。
* `beta`：你到底有多像基准。
* `alpha`：扣掉 beta 以后，还剩多少独立超额。

### 滚动回测统计

按配置启用时，还会写：

* `summary.json -> backtest.rolling_sharpe`
* `backtest_rolling_sharpe_6m.csv`
* `backtest_rolling_sharpe_12m.csv`

这部分适合看策略是否只在某一段行情有效。

## 最终留出期

如果开启 `eval.final_oos`，`summary.json -> final_oos` 会再给一套独立结果。

这部分通常包含：

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

这是一段真正不参与训练和调参的保留样本。你可以把它当成“最后一次单独验收”。

直观理解：

* 如果 in-sample 很好、`final_oos` 很差，通常要优先怀疑过拟合。

## Walk-Forward 与特征重要性

### Walk-Forward

如果启用了 `eval.walk_forward`，常见文件有：

* `walk_forward_summary.csv`
* `walk_forward_feature_importance.csv`
* `walk_forward_feature_stability.csv`

这部分主要看两件事：

* 不同窗口的 IC 和回测是否稳定。
* 重要特征是否在多个窗口里反复出现。

直观理解：

* 如果只有一个窗口特别好，其余窗口一般，信号大概率不稳。

### 特征重要性

默认训练成功且模型支持时，会输出：

* `feature_importance.csv`

重要性来源会写在 `summary.json -> eval.feature_importance_source`：

* XGBoost 模型通常来自 `feature_importances_`
* 线性模型通常来自绝对值系数 `coef_abs`

同时还会给：

* `feature_importance_nonzero`
* `zero_feature_importance`
* `constant_prediction`

这几个字段适合快速识别退化 run。做线性模型汇总时，通常应排除或单独标记这些 run。

直观理解：

* `feature_importance` 适合看模型主要在用什么。
* 它适合排错和做筛选线索，不适合直接拿来证明因子有效。
* `constant_prediction` 和 `zero_feature_importance` 往往说明这次 run 已经退化。

## 建议阅读顺序

如果你在做一次常规研究，建议按这个顺序读：

1. `summary.json -> data / universe`
2. `summary.json -> eval.ic / eval.pearson_ic / eval.quantile_mean / eval.long_short`
3. `summary.json -> backtest.stats`
4. `summary.json -> backtest.active` 或 `backtest.benchmark`
5. `summary.json -> final_oos`
6. `walk_forward_summary.csv`
7. `feature_importance.csv`

如果你只想先判断这次 run 值不值得继续看，最短路径是：

1. 样本有没有被压缩得太厉害。
2. `eval.ic.mean` 和 `eval.ic.ir` 是否稳定。
3. `quantile_mean` 是否有基本单调性。
4. `backtest.stats` 的净收益、回撤和成本拖累是否还能接受。
5. `final_oos` 和 `walk_forward` 是否延续了同样的结论。
