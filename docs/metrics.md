# 指标与结果解读

本页解决什么：指标与结果文件的解读方式。\
本页不解决什么：不展开输出字段的完整契约。\
适合谁：需要解释 run 结果的人。\
读完你会得到什么：从 `summary.json` 与 CSV 解读结果的路径。\
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

## 先回答一个常见问题

当前已经成熟输出落地的指标，主要包括：

* 评估侧：`ic` / `pearson_ic`、`error_metrics`、`quantile_mean`、`long_short`、`hit_rate`、`topk_positive_ratio`、`turnover_mean`
* 稳健性：`train_ic` / `cv_ic`、`final_oos`、`walk_forward`、`rolling_ic`、`permutation_test`
* 诊断拆解：`bucket_ic`、`feature_importance`
* 回测侧：净/毛收益、回撤、Sharpe、Sortino、Calmar、benchmark / active、rolling Sharpe
* 组合层诊断：`backtest.exposure` 下的风格暴露、行业暴露和主动暴露摘要

目前还没有直接落地的指标（或者只做到间接模拟）：

* 容量：当前没有直接输出“可承载资金规模”“按 ADV 需要几天出清”“成交占比上限触发率”这类标准容量指标。
* 单因子边际贡献：当前没有自动输出 `drop-column`、系统化 ablation、feature permutation importance、SHAP 这类“去掉某个因子后损失多少”的结论。
* spread win rate：当前没有单独汇总成 `summary.json` 字段，但可以从 `quantile_returns.csv` 自己派生每期 `Q_high - Q_low` 为正的比例。

另外要特别区分三件事：

* `backtest.execution` 里的 `adv20_amount`、`participation`、`min_amount` 更接近容量 / 流动性 stress proxy
* `backtest.exposure` 更接近组合暴露诊断
* 两者尚未达到完整的机构级容量评估

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
* `train_target_transform`：训练时是否先把标签做横截面 `zscore` / `rank` 变换。

先确认标签定义，再解释指标。否则你看到的 IC 和回测收益，可能并不是你以为的持有期。

### 先确认你在读什么指标

如果启用了 `eval.save_scored_artifact=true`，`eval_scored.parquet` 里通常会保留三列分数：

* `pred`：模型原始输出。
* `signal_eval`：乘上评估侧方向因子后的分数。
* `signal_backtest`：乘上回测侧方向因子后的分数。

大多数排序、分位收益、Top-K 和回测结论，应该优先按 `signal_eval` / `signal_backtest` 来理解，而不是只看裸 `pred`。

### Ranker 和 Regressor 的输出含义不同

同样是分数，不同模型家族的语义并不完全一样：

* `xgb_regressor` / 线性回归类输出，更接近连续预测值。但它到底像不像预期收益率，还取决于训练标签是否做过 `train_target_transform`。
* `xgb_ranker` 输出更应该读成同日相对排序分数。它天然更偏向回答谁该排前面。

最容易误读的是这句：

* 只有当训练标签本身就是原始 `future_return`，且没有再做会改变尺度的变换时，模型输出才比较接近预期收益率。
* 如果训练标签做了 `zscore`、`rank` 或别的横截面标准化，那输出更稳妥的叫法是alpha score或排序分数。

也因此：

* `quantile_mean` / `long_short` 的价值之一，就是把模型分数重新接回未来收益表现。
* `error_metrics` 在 `train_target_transform != none` 时，更适合当诊断值。

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

计算机制是统一的：

1. 先按 `trade_date` 分组，在每个交易日横截面里计算一次相关系数。
2. 把这些按日期排好的单期 IC 串起来，形成一条 IC 时序。
3. `summary.json` 里的 `mean`、`std`、`ir`、`t_stat`、`p_value`，都是对这条 IC 时序再做汇总。

所以这里的 `ic` / `pearson_ic` 回答的是“这个信号能不能在很多个交易日里持续把股票排对”。

汇总字段常见为：

* `n`
* `mean`
* `std`
* `ir`
* `t_stat`
* `p_value`

这组汇总字段不仅包括`ic`，也常用于 `pearson_ic`、`train_ic`、`train_ic_raw`、`train_pearson_ic`、`cv_ic`、`cv_ic_raw` 和 `bucket_ic`：

* `n`：参与统计的有效交易日数或有效截面数。越小，结论越容易偶然波动。
* `mean`：这个指标在整个评估区间里的平均水平。
* `std`：这个指标在时间上的波动大小。越大，说明好坏时段差得越多。
* `ir`：这里就是 `mean / std`。代表是IC 的稳定度。
* `t_stat`：平均值相对标准误有多大，可粗看偏离 0 是否明显。
* `p_value`：和 `t_stat` 对应的概率值。越小，越不像纯随机噪声；但在金融时间序列里只能当弱参考。

解读建议：

* `mean` 看方向和平均强度。
* `ir` 看稳定性。
* `t_stat` / `p_value` 只能当简化参考。金融时间序列通常不满足独立同分布。

简短理解：

* `mean` 越高，说明平均来说越能排对。
* `ir` 越高，说明预测是比较稳定地灵。
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

字段速记：

* `train_ic`：训练期、方向校正后的 Rank IC。看训练段里排序有没有用。
* `train_ic_raw`：训练期、未翻转方向前的原始 Rank IC。它主要用来判断要不要把信号乘以 `-1`。
* `train_pearson_ic`：训练期、方向校正后的 Pearson IC。看训练段里幅度关系是否也对。
* `cv_ic`：交叉验证后的 IC 汇总，偏向回答“换几个时间窗以后，这个信号还灵不灵”。
* `cv_ic_raw`：交叉验证里未翻转方向前的原始 IC。主要用于初步的方向判断。
* `signal_direction`：最终作用在预测分数上的方向因子，常见是 `1` 或 `-1`。`-1` 表示原始高分其实该反着用。
* `signal_direction_mode`：方向因子是固定给的，还是由 `train_ic` / `cv_ic` 自动推出来的。

直观理解：

* 这一步是在判断“高分到底该买，还是其实应该反着用”。

### 误差指标

`error_metrics` 包含：

* `n`
* `mae`
* `rmse`
* `r2`

这组指标为第二梯队，相比之前的指标出现频率更低，主要适合排查退化模型、常数预测和标签异常。

直观理解：

* `n`：参与误差统计的样本数。样本太少时，不要过度解读这组值。
* `mae`：平均每次大概错多少。
* `rmse`：对大错更敏感，适合抓明显失真。
* `r2`：模型解释了多少波动。它在截面选股里不一定高，但过低时值得排查。

补充边界：

* 对 `xgb_ranker` 这类排序任务，这组值主要用于发现退化、常数预测或标签异常。
* 当 `label.train_target_transform != none` 时，模型训练目标和评估标签不在同一量纲，`mae` / `rmse` / `r2` 的绝对大小更不宜过度解释。
* 如果有人只因为 `r2` 不高就否定截面模型，通常是在拿回归直觉硬套排序任务。

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

计算机制：

1. 每个 `trade_date` 里，先按分数把股票排序。
2. 再把当日股票切成 `n_quantiles` 个分位组。
3. 对每个分位组计算未来收益均值，得到一条按日期展开的 `quantile_returns.csv`。
4. `summary.json -> eval.quantile_mean` 是这张时序表在时间维度上的均值。
5. `long_short` 就是 `quantile_mean` 里最高分位减最低分位。

直观理解：

* `quantile_mean`：把股票按模型分数分组后，每一组的平均未来收益。它回答“高分组是不是整体更好”。
* `long_short`：最高分位平均收益减去最低分位平均收益。它回答“最好和最差这两头到底拉开了多少”。
* 如果模型真有用，通常高分组应该整体好于低分组。
* `long_short` 可以粗看“最看好的那组”和“最不看好的那组”差了多少。

补充边界：

* 如果某个交易日股票数少于 `n_quantiles`，那一天不会进入分位统计。
* 对截面模型来说，`quantile_mean` 的**单调性**通常比某一个分位点的绝对数值更重要。
* 如果分数本身不是收益率口径，`long_short` 往往比 `pred` 更值得直接拿来和未来收益对照。
* 如果你想看 “spread win rate”，当前仓库没有单独汇总字段，但可以从 `quantile_returns.csv` 自己计算每期最高分位减最低分位是否为正。

### 换手与缓冲区

评估侧换手相关字段：

* `turnover_mean`
* `turnover_count`
* `buffer_exit`
* `buffer_entry`

对应文件：

* `turnover_eval.csv`

`buffer_exit` 和 `buffer_entry` 用来降低调仓抖动。排名轻微波动时，缓冲区可以减少不必要的换手。

字段速记：

* `turnover_mean`：每次评估调仓时，平均有多大比例的持仓被换掉。
* `turnover_count`：实际参与换手统计的调仓次数。次数太少时，`turnover_mean` 参考性会变弱。
* `buffer_exit`：已有持仓允许“掉出 Top-K 一点点”仍先保留。数值越大，越不容易因为小波动被卖掉。
* `buffer_entry`：新股票必须比 Top-K 再更靠前一些才允许挤进来。数值越大，越不容易频繁换新票。

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

* `hit_rate`：预测值和真实收益同号的比例。它更像“方向对了多少次”。
* `topk_positive_ratio`：每个调仓日里，Top-K 名单中未来收益为正的比例，再对这些日期求平均。它更像“真正买进名单里，赚钱的票占多少”。

计算机制：

* `hit_rate`：把预测值和真实收益逐行对齐后，只看符号是否一致。
* `topk_positive_ratio`：对每个交易日先取分数最高的 `K` 只股票，再看其中未来收益大于 0 的占比，最后对日期求平均。

补充边界：

* 这两项都更偏“方向感”，想要了解排序质量还是看前面的指标。
* 对截面 `ranker` / 截面 `regressor`，主指标通常还是 `RankIC`、分位单调性和 `long_short`。
* 在全市场一起涨跌的阶段，一个排序正确但没有把绝对涨跌符号猜准的模型，`hit_rate` 也可能并不亮眼。
* 如果未来要单独看spread 胜率，更自然的口径通常是每期 `top-bottom spread` 为正的比例。

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

字段速记：

* `bucket_ic`：把样本拆成几个桶后，各桶分别算出来的 IC 汇总。它适合查“信号是不是只在某类股票上有效”。
* `bucket_ic_file`：对应分桶 IC 明细 CSV 的路径。
* `rolling_ic`：滚动窗口里的 IC 表现，常看最新窗口的 `ic_mean` 和 `ic_ir`。
* `permutation_test`：把训练标签打乱后重复评估得到的噪声基线。如果真实结果只比它好一点，就要警惕过拟合。

直观理解：

* `bucket_ic` 看信号是不是只在某个角落有效。
* `rolling_ic` 看信号是不是只在某几年有效。
* `permutation_test` 看你看到的效果，是否只是训练噪声。

补充边界：

* `bucket_ic` 回答的是“信号在哪些 bucket 上有效”。
* `permutation_test` 是打乱训练标签后的噪声基线检验。
* 如果你想回答“去掉这个因子后整体模型伤了多少”，当前仓库还没有把 drop-column / permutation importance / SHAP 做成 run 默认输出。

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

* `periods`：回测里实际统计了多少个收益周期。
* `total_return`：整个回测区间从头拿到尾的累计收益。
* `ann_return`：年化大概能赚多少。
* `ann_vol`：收益波动有多大。
* `sharpe`：单位风险换来了多少收益。
* `max_drawdown`：历史上最痛的一次回撤有多深。
* `avg_holding`：平均一笔持仓会拿多久，通常可近似理解为平均持有交易日数。
* `periods_per_year`：一年大约会经历多少个回测收益周期，用于把周期收益换成年化口径。
* `avg_turnover`：回测里每次调仓平均换掉多少仓位。
* `avg_cost_drag`：交易成本平均会把每期收益拖低多少。

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
* `drawdown_duration`：从前高点跌到最深谷底，经历了多少个回测周期。
* `recovery_time`：从最深谷底回到前高点，又花了多少个回测周期。
* `drawdown_duration_days`：同一段回撤，换成自然日大概持续多久。
* `recovery_time_days`：从谷底恢复到前高点，用自然日看大概花多久。
* `skew`：收益分布偏向哪一边。明显为负时，通常说明更容易出现突然的大亏。
* `kurtosis`：收益分布尾巴有多厚。越高，通常说明极端波动更多。
* `var_95`：按历史分布看，最差 5% 左右单期收益大概会跌到哪里。
* `cvar_95`：落入最差 5% 以后，平均还会有多差。它通常比 `var_95` 更悲观。

### 基准与主动收益

当配置了 `benchmark_symbol` 或 `benchmark_returns_file` 时，还会写：

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
* `corr`：策略收益和基准收益的相关性。越高，说明走势越像基准。
* `active_total_return`：把收益复利算完后，策略相对基准最终多赚了多少。

### 风格与行业暴露

当回测成功产出持仓，且 panel 里存在可解析的暴露列时，还会写：

* `summary.json -> backtest.exposure`
* `backtest_style_exposure.csv`
* `backtest_industry_exposure.csv`
* `backtest_active_exposure_summary.csv`

这部分当前已经落地，不只是研究备忘。

风格暴露目前是 best-effort 组合诊断，默认尝试解析六类风格：

* `size`
* `value`
* `quality`
* `momentum`
* `low_vol`
* `beta`

计算机制可以粗看成：

1. 对每个 `rebalance_date`，取当期持仓和同日 panel。
2. 用可用列或价格历史派生出风格值。
3. 计算组合 `portfolio_long` / `portfolio_short` / `portfolio_net` 的暴露。
4. 再和全市场等权、可得时的市值权重基准做比较，得到主动暴露。

行业暴露则是按行业标签聚合权重，输出：

* 组合净权重
* 全市场等权权重
* 可得时的市值权重
* 相对等权 / 市值权重的主动偏离

`backtest_active_exposure_summary.csv` 是更方便扫读的一层宽表，按每个调仓期汇总：

* 当前最主要的风格主动暴露
* 最显著的行业主动偏离

解读时要注意：

* 这层输出回答的是“组合到底在偏什么”。
* 目前尚未具备自动约束组合，以及完整 Barra 风险模型。
* `style_factors[*].available=false` 表示这次 run 缺少可解析列。
* 如果启用了 `final_oos`，同样结构也会出现在 `summary.json -> final_oos -> backtest -> exposure`。

### 滚动回测统计

按配置启用时，还会写：

* `summary.json -> backtest.rolling_sharpe`
* `backtest_rolling_sharpe_6m.csv`
* `backtest_rolling_sharpe_12m.csv`

这部分适合看策略是否只在某一段行情有效。`rolling_sharpe` 本质上是“拿一个滚动窗口，反复重算那段时间的 `mean`、`std` 和 `sharpe`”。

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

这是一段真正不参与训练和调参的保留样本。你可以把它当成最后一次单独验收。

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
* `walk_forward_summary.csv` 相当于每个窗口单独给一份 mini summary。
* `walk_forward_feature_stability.csv` 里的 `top_k_hit_rate` / `nonzero_hit_rate`，适合看某个特征是不是只偶尔冒头，还是很多窗口都在稳定出现。

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
* `feature_importance_source`：重要性数值是按什么口径算出来的，不同模型之间不能直接横比绝对值大小。
* `feature_importance_nonzero`：重要性不为 0 的特征个数。太少时，通常说明模型基本没用上多少信息。
* 它适合排错和做筛选线索，不适合直接拿来证明因子有效。
* `zero_feature_importance`：所有特征重要性都为 0，通常说明模型已经退化成“特征几乎没起作用”。
* `constant_prediction`：模型对不同股票几乎给出同一个分数，通常说明这次 run 已经退化。

补充边界：

* `feature_importance` 对于树模型，它通常表示训练时被使用的相对重要程度；对线性模型，这里当前用的是 `coef_abs`，也就是绝对值系数，不带方向。
* 单因子预测力应该看单因子自己的 `IC` / `quantile_mean` / `long_short`，或者单因子单独跑模型。
* “对整体模型的边际贡献”则是另一个问题，通常要靠 ablation、drop-column、SHAP 或 feature permutation importance；这些当前还不是默认输出。

## 几个最容易混淆的点

### 分数不一定等于收益率

文档里最容易被跳读的一点，就是模型分数和未来收益率不是天然同一个东西。

可以这样记：

* `future_return` 是评估标签。
* `pred` / `signal_eval` / `signal_backtest` 是模型输出分数。
* 只有在原始收益标签直接入模、且没有再做尺度变换时，这个分数才比较像预期收益率。

所以如果训练标签做过 `zscore`、`rank` 或其他标准化：

* 分数更应该叫 `alpha score`
* 真正把它翻译回“未来收益表现”的桥梁，是 `IC`、`quantile_mean`、`long_short` 和回测

### Ranker 和 Regressor 的结论可以共用，但语义不同

很多评估指标两种模型都会产出，但读法不该完全一样：

* 对 `regressor`，分数更像连续预测值。
* 对 `ranker`，分数更像“谁该排前面”的排序分。

因此：

* 两者都可以看 `RankIC`、分位收益、Top-K 和回测。
* 但对 `ranker`，不要太执着于 `mae` / `rmse` / `r2`。
* 对 `regressor`，如果训练标签已经相对化，分数也不该硬解释成百分比收益。

### 模型分数、feature importance、单因子有效性不是一回事

这三件事经常被混成一句话，但其实分别回答不同问题：

* 模型分数：这只股票当前该排多前面。
* `feature_importance`：模型训练时主要在利用哪些输入。
* 单因子有效性：某个因子单独拿出来，自己有没有预测力。

所以：

* `feature_importance` 高，不等于单因子自己一定有稳定 alpha。
* 某个因子单独很有效，也不等于它在多因子模型里还有同样大的边际贡献。

### 单因子预测力、边际贡献、噪声检验也是三件事

当前仓库里已经有的是：

* 单模型层面的 `IC` / `quantile_mean` / `long_short`
* `permutation_test` 这种标签打乱后的噪声基线

当前还没有默认落地的是：

* feature permutation importance
* drop-column / ablation
* SHAP

所以不要把：

* `permutation_test`

误读成：

* “这个 feature 的 permutation importance”

两者名字像，但完全不是一回事。

### `hit_rate` 是辅助指标，不该盖过排序指标

在截面选股里，更核心的问题通常是：

* 高分股有没有系统性强于低分股
* 这个强弱关系是否稳定

所以通常优先级更高的是：

* `RankIC`
* `quantile_mean` 的单调性
* `long_short`
* 回测净收益和主动收益

`hit_rate` 和 `topk_positive_ratio` 更像是：

* 补充方向感
* 给人更直观的“命中率”视角

它们很有用，但不宜单独替代排序类指标。

### `bucket_ic`、暴露分析、容量 stress 也不是一回事

这三者分别回答：

* `bucket_ic`：信号在哪些子样本里更有效。
* `backtest.exposure`：组合最后实际偏到了哪些风格 / 行业。
* execution / `adv20_amount` / `participation`：如果放进交易约束和冲击假设，回测会不会明显恶化。

因此：

* `bucket_ic` 强，不代表组合就一定有对应暴露。
* 组合有明显行业偏离，也不代表模型只是在那个行业里有效。
* execution stress 明显恶化，通常是在提醒流动性 / 容量问题，不是风格暴露问题。

最后一句最重要：

* 当前仓库已经有不少**容量相关 proxy**，但还没有形成一套正式的**容量指标板**。

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
