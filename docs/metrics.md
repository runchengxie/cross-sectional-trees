# 指标与结果解读

本文档的核心目标：说明各项评估指标的具体含义以及运行结果文件的正确解读方式。
本文档的范围限制：不展开探讨输出字段在代码层面的完整技术契约。
目标读者：需要分析和解释模型 run 结果的研究员或开发者。
阅读收益：掌握从 `summary.json` 及各类 CSV 文件中有效提取并解读策略表现的正确路径。
相关页面：`docs/outputs.md`、`docs/config.md`

本文档专职说明当前仓库中业已实现，并会在每次 run 结束后默认落盘的各项指标与分析文件。

若希望快速概览一次 run 的全貌，建议优先检视以下几份核心文件：

* `summary.json`
* `config.used.yml`
* `positions_current.csv` 或 `positions_current_live.csv`
* `ic_test.csv`
* `quantile_returns.csv`
* `backtest_net.csv`

默认的 run 产物落盘路径通常为：`artifacts/runs/<run_name>_<timestamp>_<hash>/`。

## 常见问题先导

当前体系内已成熟固化并常规输出的指标域主要包含：

* 预测评估侧：`ic` / `pearson_ic`、`error_metrics`、`quantile_mean`、`long_short`、`hit_rate`、`topk_positive_ratio`、`turnover_mean`
* 稳健性检验侧：`train_ic` / `cv_ic`、`final_oos`、`walk_forward`、`rolling_ic`、`permutation_test`
* 诊断与拆解侧：`bucket_ic`、`feature_importance`
* 策略回测侧：净/毛收益曲线、回撤幅度、Sharpe 比率、Sortino 比率、Calmar 比率、benchmark / active 主动偏离统计、rolling Sharpe
* 组合层诊断侧：位于 `backtest.exposure` 节点下的风格暴露、行业暴露与主动暴露摘要

现阶段暂未直接作为默认输出落地的指标（或仅能提供间接的模拟推演）：

* 资金容量：当前缺乏直接宣示“可承载资金上限规模”、“按照 ADV 计算需几日出清”或是“成交占比上限触达率”等标准的机构级容量指标。
* 归因解释（SHAP）：当前不会自动针对树模型实施 SHAP 局部解释拆解。
* 极差胜率（spread win rate）：该指标并未单独抽列为 `summary.json` 里的现成字段。用户可自行从 `quantile_returns.csv` 报表中推算每期 `Q_high - Q_low` 收益差为正的具体比例。

当前已具备配套的离线研究工具，但并未作为单次 `cstree run` 附带默认产物的分析项包括：

* `cstree feature-evidence generate-ablation` / `summarize-ablation`：该工具组合用于自动生成系统化的特征族消融（feature family ablation）配置文件，并负责汇总其相对于 baseline 在 `eval_ic_ir`、`walk_forward_test_ic_mean`、`final_oos_ic_mean`、`backtest_sharpe`、换手率（turnover）、成本拖累（cost drag）以及 active IR delta 等多维度的边际影响。
* `cstree feature-evidence permutation-importance`：基于已有的 scored artifact 预估分数资产，计算输出单一特征以及特征族（feature family）的 top-k profit proxy、permutation metric 与具体的 `permutation_importance`。
* `cstree construction-grid`：利用固定的模型预测分数作为底层输入，离线推演组合构建层不同变体下的 IC 表现、long-short 收益差、换手率、gross/net 回报、Sharpe、最大回撤、成本损耗及 active return 指标。
* `cstree benchmark-ladder`：将特定的策略收益曲线与多组基准收益阵列执行平行比对，产出包含 active total return、IR、tracking error、beta、alpha 甚至相关系数在内的 benchmark ladder 阶梯报告。

此外，需要特别厘清以下三组易混淆的概念界限：

* 沉淀于 `backtest.execution` 中的参数设定（如 `adv20_amount`、`participation` 及 `min_amount`）其实质更贴近于容量或流动性视角的压力测试代理（stress proxy）。
* 位于 `backtest.exposure` 下的数据阵列，主要致力于回答组合层面的风格与行业暴露诊断。
* 上述两者目前均尚未演进为一套绝对完整、成熟的机构级资金容量评估模型。

## 查阅顺序与导航

`summary.json` 承担了全局总览的角色。绝大多数的分析疑问皆应以此处为起点展开定位。

常见的数据存放节点：

* `data`：记录样本的横跨区间、物理行数、选用的 provider 来源、缓存命中标签及日历信息。
* `universe`：宣示股票池的构建模式、强制设定的单日最小样本存活数、因数据匮乏而遭废弃的日历数量，以及针对停牌标的的具体干预对策。
* `eval`：集中陈列预测质量、分位数收益分布、评估侧换手率、训练期对照效果以及可选的稳健性检验指标。
* `backtest`：归档 Top-K 选股下的回测配置参数、历史回测核心统计量，以及比对基准线的主动收益概况。
* `final_oos`：展示针对最终留出期的纯净测试结果。该节点内部的结构排布与 `eval/backtest` 维持高度对应。
* `walk_forward`：收录滚动窗口验证法下的检验总纲及各子窗口独立输出明细文件的指路路径。

若需追踪细致的时间序列变动轨迹，请进一步查阅各配套的 CSV 报表：

* `ic_test.csv` / `ic_pearson_test.csv`
* `quantile_returns.csv`
* `turnover_eval.csv`
* `backtest_net.csv` / `backtest_gross.csv`
* `backtest_turnover.csv`
* `walk_forward_summary.csv`
* 离线协议生成的专题报告：如通过 `cstree promotion-gate`、`cstree construction-grid`、`cstree feature-evidence` 或 `cstree benchmark-ladder` 等工具写出的位于 `artifacts/reports/*.csv` 或 `*.json` 目录下的研究文件。

全量产物清单请参阅 `docs/outputs.md`。

## 数据基座与样本质量研判

此类校验字段集中留存于 `summary.json -> data` 与 `summary.json -> universe` 节点之下。

建议优先查证：

* `symbols`：统计在此次划定的样本时空中，实际现身过的标的总数。
* `rows`：未经任何筛选的原始数据初始行数。
* `rows_model`：历经特征对齐、标签贴合以及各项过滤清洗工序后，真正获准放行进入建模核心区的有效样本行数。
* `min_symbols_per_date`：维持单日截面存续所必需达到的标的底线数量。
* `dropped_dates`：因当日幸存标的数量跌破阈值而遭到整体整日废弃的日历总数。
* `mode`：阐明股票池的运管模式，通常见于 `static`、`pit` 以及 `auto`。
* `drop_suspended` / `suspended_policy`：揭示对待停牌标的的态度，是实施彻底的物理剔除，还是仅打上不可交易的业务标签。

上述字段旨在优先响应以下两项根本疑虑：

* 提供给模型咀嚼的样本规模是否足够庞大。
* 样本群体是否因为严苛的股票池更迭、大面积停牌或特征大范围空缺而遭遇了严重缩水。

若察觉到 `rows_model` 呈现出显著劣于 `rows` 的断崖式下跌，或者 `dropped_dates` 的数值畸高，后续对诸如 IC、分位收益乃至最终回测净值的解读，务必秉持更为审慎和保留的态度。

## 模型标签定义解读

标签的定义从根本上回答了“模型当前究竟在尝试预测什么”。相关的指令配置绝大多数均盘踞在 `label` 命名空间下。

高频查阅字段：

* `target_col`：常规默认值为 `future_return`，即远期收益率。
* `horizon_days`：用以锚定固定持仓期的观测跨度。
* `horizon_mode`：标识观测窗形态，可为 `fixed`（固定天数）或 `next_rebalance`（对齐至下一次调仓动作）。
* `rebalance_frequency`：当选用 `next_rebalance` 模式时，由该参数具体裁定未来收益的结算视窗。
* `shift_days`：调和信号生成日与实际持仓入场日之间的时滞天数差。
* `train_target_transform`：裁决在交由模型训练前，是否预先对原生标签列施加诸如横截面 `zscore` 或是 `rank` 排序等变形映射手术。

在试图诠释任何评估指标前，请务必率先确认标签的真实定义范畴。若越过此步，你所面对的 IC 读数或回测收益，极有可能是基于一套完全偏离你直觉假设的持仓周期计算而出的产物。

### 明确分数的物理意义

当在配置中启用了 `eval.save_scored_artifact=true`，系统产出的 `eval_scored.parquet` 宽表内通常会沉淀下三列派生分数：

* `pred`：模型输出的原始预测值。
* `signal_eval`：将原始分数与评估侧判定的方向因子（如 `-1` 翻转）相乘后得出的校正分数。
* `signal_backtest`：将原始分数与回测侧方向因子相乘后得出的最终指导分数。

在绝大多数场景下，针对模型输出的排序核对、分位收益追踪、Top-K 精选摘取以及回测交割结论，均应以 `signal_eval` 或 `signal_backtest` 作为判定准绳，请尽量避免直接使用未经方向校正的原始 `pred` 值。

### Ranker 与 Regressor 输出语义的本质分歧

纵然外在表现皆为分数，但不同算法家族的模型，其输出语义存在着深层次的差异：

* 针对 `xgb_regressor` 或传统的线性回归模型，其输出在形态上更趋近于连续的绝对预测值。但它究竟在多大程度上能够拟合真实世界的预期收益率，很大程度上取决于其所吞吐的训练标签是否曾经历过 `train_target_transform` 的改造。
* 针对 `xgb_ranker` 的输出，应当将其解读为特定同日横截面内部的相对排序分数。它主要用于回答横截面内标的的相对优劣顺序。

此处最易滋生误解的盲区在于：

* 只有当训练模型使用的标签本身即为纯粹的 `future_return` 原始收益率，并且中途未经过任何改变尺度的换算操作时，模型的最终输出才可视为预期收益率的代理。
* 一旦训练标签经历了 `zscore`、`rank` 或其他的横截面标准化处理，此时更为严谨的称谓应当是 alpha score（超额得分）或者纯粹的排序分数。

基于上述原理：

* `quantile_mean` 与 `long_short` 的核心价值之一，正是建立起模型抽象分数与现实未来收益表现之间的映射桥梁。
* 当配置了 `label.train_target_transform != none` 时，`error_metrics` 组内反馈的各类绝对误差指标，其属性更宜作为内部排障使用的辅助诊断值。

## 预测质量核心指标

此类指标通常驻扎于 `summary.json -> eval` 目录下。

### 核心 IC 指标

系统默认会双线并行输出两类截然不同的 IC 读数：

* `ic`：即 Spearman Rank IC。用于侦测模型对标的相对位次的排序能力。
* `pearson_ic`：即 Pearson IC。用于审视模型给出的预测幅度与标的真实收益之间是否具有线性关系。

直观释义：

* `ic` 用以解答“模型给出的预测排名，与未来真实收益的排位是否相似”。
* `pearson_ic` 用以解答“模型不仅排名正确，其预测强度的相对大小是否吻合了现实收益的幅度差异”。

依赖的源文件档案：

* `ic_test.csv`
* `ic_pearson_test.csv`

统计核算机制：

1. 按照 `trade_date` 交易日切片执行分组，在每个独立的单日横截面内部发起一次相关系数运算。
2. 将这些按日期排列的单期 IC 串联，形成一条连贯的 IC 时间序列。
3. `summary.json` 中罗列的 `mean`、`std`、`ir`、`t_stat`、`p_value` 等汇总数据，皆是对这条时序数据实施的二次汇总计算。

由此可知，呈现在这里的 `ic` 或 `pearson_ic`，其根本使命在于证明信号体系是否具备在多个交易日中持续稳定地进行标的排序的能力。

汇总统计维度的常见字段：

* `n`
* `mean`
* `std`
* `ir`
* `t_stat`
* `p_value`

这套统计字段不仅用于 `ic`，同样高频活跃于 `pearson_ic`、`train_ic`、`train_ic_raw`、`train_pearson_ic`、`cv_ic`、`cv_ic_raw` 乃至 `bucket_ic` 等多项统计场景中：

* `n`：参与统计的有效交易日天数或横截面数量。此值越小，统计结论就越容易受到偶然波动的干扰。
* `mean`：该项指标在整段考察期内的平均值。
* `std`：该指标在时间序列上的波动标准差。该值越大，说明模型表现好坏参差，稳定性较弱。
* `ir`：即 `mean / std`。它直观地表征了 IC 预测能力的稳定性。
* `t_stat`：用来衡量平均值相对于标准误的偏离倍数，可粗略窥探其偏离零轴的明显程度。
* `p_value`：与 `t_stat` 相关的概率测算值。数值越小，越说明其具有统计显著性；但鉴于金融时间序列的复杂性，仅建议将其作为参考。

解读建议：

* 观察 `mean` 把握预测的整体方向与平均效力。
* 观察 `ir` 确认其表现的稳定性。
* 对待 `t_stat` 与 `p_value`，仅作简化参考视之，金融时间序列往往并不遵循严格的独立同分布假设。

速读心法：

* `mean` 越高，表明模型平均而言越擅长正确排序。
* `ir` 越高，证实这项预测表现稳健且经常奏效。
* 一旦察觉 `std` 较大，通常说明信号很可能仅在特定的行情区间有效，泛化能力存疑。

### 训练期对照与自动方向校正

这组字段用于判断信号的最终方向及其底层的可靠程度：

* `train_ic`
* `train_ic_raw`
* `train_pearson_ic`
* `cv_ic`
* `cv_ic_raw`
* `signal_direction`
* `signal_direction_mode`

`signal_direction_mode` 支持 `fixed`、`train_ic` 以及 `cv_ic` 三种模式。当系统侦测到模型在训练段内学习到稳定的负相关特征时，可以自动执行方向翻转操作。

字段速记要诀：

* `train_ic`：训练周期内、且已经历过方向翻转校正的 Rank IC。用于确认在训练集里排序逻辑是否成立。
* `train_ic_raw`：训练周期内、尚未接受过方向翻转的原始 Rank IC。它作为决定是否需将最终信号乘上 `-1` 的核心依据。
* `train_pearson_ic`：训练周期内、历经方向校正的 Pearson IC。用以探查在训练段内，预测幅度的线性映射关系是否达标。
* `cv_ic`：交叉验证后的 IC 汇总成绩。偏向于解答“在更换了时间窗口后，信号是否依旧有效”。
* `cv_ic_raw`：交叉验证环节中、尚未历经翻转的原始 IC。多用于初步探明信号的方向。
* `signal_direction`：最终施加在预测分数上的方向因子，通常为 `1` 或 `-1`。为 `-1` 时意味着原始高分应作为空头对象反向运用。
* `signal_direction_mode`：揭露上述方向因子的确立途径，是由配置模板硬性指定，还是依据 `train_ic` 或 `cv_ic` 的表现自动推演。

直观释义：

* 这一流程的目的在于确定高分预测到底对应多头还是空头信号。

### 模型误差度量

`error_metrics` 阵列囊括了以下指标：

* `n`
* `mae`
* `rmse`
* `r2`

这组参数属于第二梯队的观察指标，其主要作用在于排查模型严重退化、输出常数预测以及标签存在严重异常等情况。

直观释义：

* `n`：被卷入误差统计的样本总量。如果样本量较少，请避免过度解读这批数值。
* `mae`：评估模型平均每次预测的绝对偏离误差。
* `rmse`：对巨大的错判极为敏感，适合用于识别模型的严重失真预测。
* `r2`：衡量模型解释了多大比例的现实方差波动。它在截面选股任务中往往数值不高，但若低至底线以下，便值得排查。

补充认知边界：

* 对于类似 `xgb_ranker` 这样专注于排序任务的模型而言，这组数值的主要使命在于报警，用以侦测模型是否退化为常数发生器，或是底层标签体系出了大纰漏。
* 倘若你在配置中设定了 `label.train_target_transform != none`，这意味着模型的训练目标与最终评估用的真实标签已经不在同一个量纲体系内，此时强行解读 `mae`、`rmse` 或 `r2` 的绝对大小意义不大。
* 在截面选股任务中，由于其本质在于相对排序，因此不能单纯因为 `r2` 得分不高就全盘否定模型的价值。

### 分位数收益分布检测

引入分位数收益的核心目的在于验证：高分股票群体是否在整体表现上系统性地优于低分群体。

依赖的源文件档案：

* `quantile_returns.csv`

对应的摘要字段：

* `quantile_mean`
* `long_short`

解读方略建议：

* 审视 `quantile_mean`，确认由低到高的各个分位阵营，其平均收益是否保持了单调递增的趋势。
* 审视 `long_short`，探究最高分位群体与最低分位群体之间的收益差值跨度。

背后的统计核算机制：

1. 在每个 `trade_date` 截面内，依据预测分数将标的进行排序。
2. 将当日标的等分为 `n_quantiles` 组。
3. 针对每个分位组分别测算未来收益的均值，生成时序层面的 `quantile_returns.csv` 报表。
4. `summary.json -> eval.quantile_mean` 是该时序报表在时间轴上的均值汇总。
5. `long_short` 为 `quantile_mean` 中最高分位均值与最低分位均值之差。

直观释义：

* `quantile_mean`：反映将股票依据模型分数分组后，各组的平均未来收益表现，用于检验“高分群体的表现是否整体更优”。
* `long_short`：最高分位与最低分位的平均收益差值。用于检验“最看多梯队与最看空梯队之间拉开了多大的收益差距”。
* 如果模型有效，高分阵营应当在整体走势上明显优于低分阵营。

补充认知边界：

* 倘若在某一个交易日内，符合条件的股票总数少于设定的 `n_quantiles` 份数，该日历日将不会被纳入分位统计。
* 针对截面模型，我们对其 `quantile_mean` 展现出的单调递增属性的关注，通常优先于某一独立分位点上的绝对数值。
* 如果分数自身的量纲与绝对收益率不匹配，直接使用 `long_short` 与未来的真实收益表现进行对照，往往比直接分析预测原始分 `pred` 更有价值。
* 若需要单独查看极差胜率（spread win rate），当前仓库并未提供现成的汇总字段，但可以通过 `quantile_returns.csv` 明细表自行计算每期最高分位减最低分位差值为正的概率。

### 换手率监控与减震缓冲区

评估侧的换手率相关字段包括：

* `turnover_mean`
* `turnover_count`
* `buffer_exit`
* `buffer_entry`

依赖的源文件档案：

* `turnover_eval.csv`

`buffer_exit` 与 `buffer_entry` 的设立旨在削弱因策略频繁调仓而引发的无谓抖动。当标的排名仅发生微弱波动时，缓冲区机制能够有效拦截不必要的无效换手。

字段速记要诀：

* `turnover_mean`：在每一次评估触发换仓时，平均有多大比例的原有持仓被替换。
* `turnover_count`：实际被纳入换手统计的有效调仓回合数。当此数值偏低时，`turnover_mean` 的参考价值将有所下降。
* `buffer_exit`：允许既有持仓即使“排名略微跌出 Top-K 门槛”也能暂时保留。该数值设定越宽泛，标的越不容易因为名次的小幅滑坡而被替换。
* `buffer_entry`：要求新入选标的不仅名次要达标，还必须比 Top-K 门槛具有更显著的优势方可入选。此数值越高，组合纳入新标的的频率就越低。

直观释义：

* `turnover_mean` 越高，意味着组合换手的频次越快。
* 缓冲区的价值在于减少那些“刚买入不久便因微小排名变动而卖出”的高频震荡调仓动作。

### 靶向命中率与 Top-K 正向收益占比

这两项参数提供了关于预测准确率的直观统计：

* `hit_rate`
* `topk_positive_ratio`

它们分别解答了以下疑问：

* 模型判定的大方向是否经常正确。
* 选出的 Top-K 标的池中，未来收益为正的比例是否可观。

直观释义：

* `hit_rate`：揭示了预测方向与真实收益方向一致的概率，类似于评价“总共蒙对了多少次方向”。
* `topk_positive_ratio`：在每个调仓日，统计跻身 Top-K 榜单的标的之中未来收益大于零的占比，并将这些单日比例汇总求取平均值。它代表了“实际买入名单中最终实现正收益的标的份额”。

背后的统计核算机制：

* `hit_rate`：将预测值与真实收益按行比对，若双方符号一致则记为命中。
* `topk_positive_ratio`：针对每个交易日提取分数靠前的 `K` 只标的，统计其中未来收益大于 0 的占比，再将这些单日占比求取平均。

补充认知边界：

* 这两项指标偏向于展示“方向感”。若需深入透析模型排序质量，仍应重点参考前面列举的硬核排序指标。
* 对于截面 `ranker` 或截面 `regressor`，核心的衡量标尺依然是 `RankIC`、分位数单调性以及 `long_short` 的跨度表现。
* 在面临全市场同涨或同跌的单边行情时，即使排序逻辑优秀但未能准确预测绝对涨跌符号的模型，其 `hit_rate` 成绩也可能表现不佳。
* 如果未来需要单独评估极差（spread）胜率，更为合理的统计口径是考察每期 `top-bottom spread` 数值为正向的概率占比。

### 进阶的可选切面拆解

当通过配置主动启用时，系统还将输出以下高阶分析报告：

* `bucket_ic` / `bucket_ic_file`：依据行业、市值、流动性等特征实施分桶后，各组独立计算的 IC 表现。
* `rolling_ic`：呈现滚动视窗下的 IC 均值与滚动 IC IR 表现。
* `permutation_test`：基于置换检验法输出的验证结论。

常见的落盘文件档案：

* `bucket_ic.csv`
* `ic_rolling_6m.csv`
* `ic_rolling_12m.csv`
* `permutation_test.csv`

字段速记要诀：

* `bucket_ic`：将样本大群拆解成分桶后，各自计算出的内部 IC 表现汇总。用于探查“信号是否仅在某些特定群体上生效”。
* `bucket_ic_file`：指引至对应分桶 IC 明细底稿 CSV 报表的路径。
* `rolling_ic`：呈现滚动窗口期内的 IC 表现轨迹，通常重点关注最新窗口期的 `ic_mean` 与 `ic_ir` 读数。
* `permutation_test`：通过打乱训练标签并重复模拟评估构建出的噪音基准线。如果真实模型结果仅略高于该噪音线，则需警惕模型可能存在过拟合。

直观释义：

* 借助 `bucket_ic` 审视信号是否局限于特定子样本群。
* 借助 `rolling_ic` 审视信号是否仅在特定历史时段有效。
* 借助 `permutation_test` 审视当前表现是否主要由训练噪音构成。

补充认知边界：

* `bucket_ic` 专门负责解答“信号在哪些子样本桶中更有效”。
* `permutation_test` 本质上是一套基于打乱训练标签的噪音基线检验。
* 若期望评估“剔除该因子后，整体模型的预测能力会下降多少”，目前仓库尚未将 drop-column（剔除重训）、permutation importance（特征置换评估）或 SHAP 等高阶归因方法作为默认产出。

## 回测阶段考量指标

此类指标通常位于 `summary.json -> backtest` 节点下。

### 净收益首当其冲

依赖的源文件档案：

* `backtest_net.csv`
* `backtest_gross.csv`

在日常评估策略表现时，务必优先查看净收益。毛收益的参考价值仅限于观察未扣除交易成本之前的信号纯净表现。

直观释义：

* 毛收益类似于未考虑磨损的理论选股能力。
* 净收益则代表扣除各类交易成本与滑点后，实际能够获取的回报。

### 核心回测统计基本盘

位于 `summary.json -> backtest.stats` 节点下的常驻字段包括：

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

这组核心数据主要解答以下问题：

* 策略最终的盈亏状况。
* 收益曲线的波动与最大回撤幅度。
* 收益是否受到换手率和交易成本的严重侵蚀。

速读心法：

* `periods`：整个回测周期内实际参与统计的计息周期数。
* `total_return`：整个回测区间的累计收益率。
* `ann_return`：折算为年化口径的预期收益率。
* `ann_vol`：收益曲线的年化波动率。
* `sharpe`：衡量单位风险所带来的超额收益补偿。
* `max_drawdown`：历史回测期间出现的最大回撤幅度。
* `avg_holding`：单笔持仓的平均持有时间，通常近似表示平均持有交易日天数。
* `periods_per_year`：一个自然年中包含的回测周期数，用于将微观周期收益换算为年化口径。
* `avg_turnover`：回测过程中每次调仓的平均换手比例。
* `avg_cost_drag`：交易成本平均在每期拉低了多少收益（基点）。

### 风险监控与尾部压力审视

回测体系额外提供了一组契合交易视角的风险探查指标：

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

它们分别用于补充评估：

* 下行风险抵御能力及回撤区间的运作效率。
* 处于最大回撤区间的具体时长。
* 收益分布是否存在过度依赖极端行情的风险。

直观释义：

* 相比 `sharpe`，`sortino` 更聚焦于惩罚出现亏损时的恶性波动。
* `calmar` 致力于评估收益相较于承受的最大回撤是否具有吸引力。
* `drawdown_duration`：记录从前高点跌落至最深谷底所经历的回测周期数。
* `recovery_time`：记录从最深谷底回升至前高点所消耗的回测周期数。
* `drawdown_duration_days`：将跌落回撤旅程换算为自然日长度。
* `recovery_time_days`：将从谷底复苏至前高的过程换算为自然日长度。
* `skew`：探测收益分布的偏度。显著为负的数值预示着策略更易遭遇突发的大幅亏损。
* `kurtosis`：量度收益分布的峰度。数值越高，发生极端震荡的概率越超出常态分布预期。
* `var_95`：基于历史分布推演，处于最差 5% 情况下的单期收益预期下限。
* `cvar_95`：在跌入最差 5% 分布区间后的条件期望收益。它通常比 `var_95` 揭示出更为悲观的极端风险预期。

### 参照基准与主动剥离收益

当在配置中指定了 `benchmark_symbol` 或 `benchmark_returns_file`，系统将记录下：

* `summary.json -> backtest.benchmark`
* `summary.json -> backtest.active`

相伴产出的文件通常包括：

* `backtest_benchmark.csv`
* `backtest_active.csv`

主动收益侧重点关切的字段：

* `tracking_error`
* `information_ratio`
* `beta`
* `alpha`
* `corr`
* `active_total_return`

直观释义：

* `tracking_error`：度量策略收益轨迹与基准参照物之间的偏离程度。
* `information_ratio`：评估这种偏离是否成功换取了长期稳定的超额回报。
* `beta`：考察策略走势与基准大盘的系统性关联度。
* `alpha`：在剥离掉由 beta 贡献的被动收益后，策略自身获取的独立超额收益水平。
* `corr`：策略净值走势与基准收益曲线的相关系数。数值越高，说明走势与基准越为一致。
* `active_total_return`：复利结算后，策略相对基准累计获取的超额净胜收益。

### 风格侧写与行业偏离度暴露

若回测进程产出了具体持仓，且 panel 内包含可供解析的暴露因子列，系统将自动补充以下产出：

* `summary.json -> backtest.exposure`
* `backtest_style_exposure.csv`
* `backtest_industry_exposure.csv`
* `backtest_active_exposure_summary.csv`

请注意，这部分目前已作为实质性的常态落地产物。

关于风格暴露，目前采用尽力而为（best-effort）的组合诊断机制，系统默认尝试解析以下六大风格维度：

* `size`
* `value`
* `quality`
* `momentum`
* `low_vol`
* `beta`

核算逻辑概览：

1. 针对每一个调仓日（`rebalance_date`），结合当期实盘持仓与同日的横截面 panel。
2. 利用现有因子列或历史价格推演出各风格的特征值。
3. 测算组合内多头（`portfolio_long`）、空头（`portfolio_short`）及净头寸（`portfolio_net`）各自承担的风格暴露量。
4. 随后引入全市场等权重模型及（在条件允许获取时）市值加权基准模型作为参照，计算主动暴露的净值。

行业暴露则是依据行业标签对资金权重进行聚合，最终输出：

* 组合最终成型的净权重配比
* 全市场等权重配置下的理论权重
* 依据市值加权配置推演的基准权重
* 相对前两者的真实主动偏离差值

`backtest_active_exposure_summary.csv` 是一张便于快速阅览的宽表视图，按调仓期合并归拢：

* 当前时点最显著的风格主动暴露项
* 当前偏离度最明显的行业主动偏差阵营

在审阅这部分数据时，请注意：

* 这些输出仅用于说明“组合当前的风格或行业倾斜方向”。
* 系统目前尚不具备自动向组合施加硬性风格约束的能力，也未集成完整的 Barra 风险预测模型。
* 若显示 `style_factors[*].available=false`，代表本次 run 的数据集中缺乏对应可解析的特征列。
* 若配置开启了 `final_oos`，则在 `summary.json -> final_oos -> backtest -> exposure` 路径下也会呈现类似的结构输出。

### 滚动截面下的回测统计动态

当通过配置启用时，系统将额外生成：

* `summary.json -> backtest.rolling_sharpe`
* `backtest_rolling_sharpe_6m.csv`
* `backtest_rolling_sharpe_12m.csv`

这组数据专门用于审视某套策略是否仅在某一段特定的顺风行情中有效。`rolling_sharpe` 的运算本质即为通过设定的滚动抽样窗口，反复计算并更新特定区间内的 `mean`、`std` 及 `sharpe` 指标。

## 最终留出期的纯净检验

若在配置中启用了 `eval.final_oos`，`summary.json -> final_oos` 将会输出一套完全独立、未受污染的纯净测试结果。

这部分包含的统计内容通常有：

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

这部分数据样本自始至终被严密隔离，绝对禁止参与任何训练拟合或参数优化过程。它被视为项目正式交付前的最后一关独立验收基准。

直观释义：

* 假若策略在 in-sample 内的测试表现优异，但在 `final_oos` 数据集上却表现糟糕，最需要优先警惕并排查的原因便是模型过拟合。

## 滚动步进前向验证（Walk-Forward）与特征话语权（Feature Importance）

### 步进前向验证（Walk-Forward）

在启用 `eval.walk_forward` 的前提下，系统将生成如下档案：

* `walk_forward_summary.csv`
* `walk_forward_feature_importance.csv`
* `walk_forward_feature_stability.csv`

审视这部分数据，核心目的在于洞悉以下两点：

* 在切换至不同的截取时间窗口时，IC 表现和回测收益能否保持稳定。
* 那些被识别出的核心重要特征，是否能在多个相互隔离的观测窗口中反复且稳定地出现。

直观释义：

* 倘若模型仅在单一的观测窗口内表现突出，切换窗口后便效果平平，该信号的稳定性很可能不佳。
* `walk_forward_summary.csv` 相当于为每个独立的观测窗口提供了一份迷你版的 summary 成绩单。
* `walk_forward_feature_stability.csv` 内部的 `top_k_hit_rate` 与 `nonzero_hit_rate` 数据，非常适合用于判断某项特征是偶尔生效还是能够在多个验证窗口中持久稳定地发挥作用。

### 特征重要度（Feature Importance）

在默认的常规模式下，只要训练顺利完成且挂载的模型支持该能力，系统便会输出：

* `feature_importance.csv`

关于重要度数值的计算口径来源，会记录在 `summary.json -> eval.feature_importance_source` 字段中：

* 对于 XGBoost 家族模型，通常直接提取自其原生的 `feature_importances_` 接口。
* 对于纯粹的线性模型，通常是提取其绝对值系数 `coef_abs`。

此外还附带以下辅助标识：

* `feature_importance_nonzero`
* `zero_feature_importance`
* `constant_prediction`

这几个辅助字段在快速排查、识别已然退化失效的 run 方面极为有效。在对线性模型进行宏观汇总时，通常应将存在这几项问题的 run 排除在外，或予以显著的警示标记。

直观释义：

* `feature_importance` 揭示了模型在进行拟合计算时主要依赖了哪些输入特征。
* `feature_importance_source`：提示重要度数值的计算口径；因此，在不同算法模型之间横向比较其绝对值大小是不可取的。
* `feature_importance_nonzero`：统计重要性不为零的特征数量。若数量极少，暗示模型在拟合时未能有效利用大部分信息。
* 此指标更适合作为排障线索和特征筛选参考，不宜直接将其作为证明某项因子必然有效的唯一证据。
* `zero_feature_importance`：当所有特征重要性均为零时，通常表明模型已退化，特征输入几乎未发挥任何作用。
* `constant_prediction`：当模型对形态各异的股票重复输出雷同的评分结果时，通常意味着该轮 run 已发生退化。

补充认知边界：

* 对于树模型，`feature_importance` 通常表征了其在训练中被拆分利用的相对频次或增益程度；对于线性模型，当前使用的是 `coef_abs`，即仅提取了不包含方向的纯绝对值系数。
* 若要评估单一因子的独立预测能力，应参考单因子自身计算出的 `IC`、`quantile_mean` 或 `long_short` 成绩单，或将该因子单独提取出来进行单因子建模验证。
* 至于评估特定特征“对整体联合模型的边际贡献”属于另一个维度的命题，通常需要借助 ablation（消融实验）、drop-column（剔除重训）、SHAP 或 feature permutation importance（特征置换重要度）等进阶工具进行分析；目前这些方法并非默认的常规输出配置。

## 容易引发歧义与认知错位的重点领域

### 预测分数并不等价于预期收益率

最容易引发误会的一点是，误将模型输出的预测分数与未来真实的收益率画上等号。

请注意以下规则：

* `future_return` 才是真正的评估标签目标。
* `pred` / `signal_eval` / `signal_backtest` 仅是模型内部运算得出的打分依据。
* 只有当模型直接使用未加修饰的原始收益标签进行训练，且过程中未经历任何量纲变换时，其输出的预测分数才勉强具备预期收益率的参考意义。

因此，倘若训练标签经过了 `zscore`、`rank` 或其他形式的标准化处理：

* 产出的分数应被视为一种 `alpha score` 排序得分。
* 能够将该抽象分数转化为对“未来真实收益表现”评估的桥梁，是 `IC`、`quantile_mean`、`long_short` 以及回测分析结果。

### Ranker 与 Regressor 的评估标尺可通用，但业务语境存在差异

尽管许多经典的评估指标在两种模型上均有输出，但解读时需区分其本质差异：

* 对于 `regressor`，分数形态更贴近于连续的预测拟合值。
* 对于 `ranker`，分数本质上是在进行截面内的相对排序选拔。

由此：

* 两者都可以使用 `RankIC`、分位收益阶梯、Top-K 选股以及实盘回测指标来进行评估。
* 但对于 `ranker` 模型，不应过度关注诸如 `mae`、`rmse` 或 `r2` 这类专为连续回归设计的误差度量指标。
* 对于 `regressor` 模型，若训练标签已做过相对化处理，同样不应将预测分数强行解释为绝对的百分比预期收益率。

### 预测分值、特征重要度与单因子有效性是完全不同的概念

这三个概念常常被混为一谈，但它们各自衡量了不同的维度：

* 模型分值：决定了当前标的在选股队列中的相对排序位置。
* `feature_importance`：反映了模型在训练拟合时主要依赖了哪些输入特征。
* 单因子有效性：评估如果将某项特定因子单独提取出来，其自身是否具备独立的预测能力。

理清脉络后可知：

* `feature_importance` 较高，并不意味着该单项因子自身必然能够稳定产生 alpha 超额收益。
* 反之，某个单因子表现出众，也不代表将其放入包含众多特征的多因子模型中后，它仍能维持同样显著的边际贡献。

### 单兵预测能力、边际提携贡献、噪音探底检验也是三个独立维度

当前仓库武器库中已提供的工具包括：

* 位于单模型评估基座层面的 `IC` / `quantile_mean` / `long_short` 阵列。
* 通过打乱标签次序重组生成的噪音探测基准，如 `permutation_test`。

目前尚未作为默认产出配置落地的工具包括：

* feature permutation importance（特征扰动重要度评估）
* drop-column / ablation（剔除单特征重训测试）
* SHAP（基于博弈论的局部归因解释）

因此，请注意区分：

* 默认提供的 `permutation_test` 是一套基于打乱训练整体标签重组而确立的噪音干扰基线检验。
* 切勿将其误认为是在评估某项具体 feature 的 permutation importance，两者目标完全不同。

### 命中率 `hit_rate` 仅是辅助指标，不应替代核心的排序评价标准

在截面选股场景中，更核心的问题在于：

* 高分股票群体是否在总体收益走势上系统性地优于低分群体。
* 这种收益差异的阶层关系是否稳固。

因此，通常排在更优先查验序列的核心标尺应为：

* `RankIC`
* `quantile_mean` 展现出的单调递增阶梯特性
* `long_short` 计算出的上下端极差收益
* 历史回测结果中的净收益与剥离 beta 后的主动收益余量

而 `hit_rate` 与 `topk_positive_ratio` 这对指标的作用定位主要在于：

* 从侧面补充提供整体的涨跌方向感参考。
* 赋予一个更为通俗易懂的“胜率”观测视角。

它们是极佳的辅助参考，但不应单独替代上述提及的核心排序与收益指标。

### `bucket_ic` 分层探测、偏离暴露分析与资金容量极限压测各自独立

这三项分析工具分别致力于解决不同维度的命题：

* `bucket_ic`：探明在哪些具体的特征子样本群体（如特定行业或市值区间）中，模型信号的预测能力更强。
* `backtest.exposure`：审查在完成一系列组合调仓后，实际的投资组合在风格或行业上存在怎样的偏离与暴露。
* execution 模块 / `adv20_amount` / `participation` 参数：推演在施加了实际的交易流动性约束与市场冲击成本后，策略回测表现是否会遭遇显著滑坡。

由此可以厘清：

* 某一阵营中的 `bucket_ic` 表现抢眼，不代表最终构建的投资组合就一定会在该领域积累高强度的风险暴露头寸。
* 同样，即便投资组合呈现出向某一特定行业明显倾斜的态势，也绝不意味着该模型仅在这个特定行业内具备有效性。
* 若 execution 层的压力测试结果出现显著衰退，通常是在警示流动性枯竭或触及了资金容量上限的风险，而非由于风格偏离所导致的问题。

请务必注意：

* 目前本仓库内虽然布置了一定数量的、用于从侧面探测评估资金容量的代理参数（proxy），但至今仍未构筑并发布一套完备、正式的资金容量核算指标体系。

## 建议的阅读顺序指南

在开展一次常规流水线式的策略研究验收时，建议遵循下述检阅次序以提升效率：

1. `summary.json -> data / universe`
2. `summary.json -> eval.ic / eval.pearson_ic / eval.quantile_mean / eval.long_short`
3. `summary.json -> backtest.stats`
4. `summary.json -> backtest.active` 或者 `backtest.benchmark`
5. `summary.json -> final_oos`
6. `walk_forward_summary.csv`
7. `feature_importance.csv`

若仅为快速概览以决定某次 run 是否具备进一步分析的价值，建议执行以下最短路径核验：

1. 查验基础样本集是否存在被过度剔除或压缩的情况。
2. 观察 `eval.ic.mean` 及其配套的 `eval.ic.ir` 表现是否扎实稳定。
3. 审视 `quantile_mean` 是否维持了基本的单调递增特征。
4. 确认 `backtest.stats` 中的净收益结余、最大回撤深度以及换手成本拖累是否处于可接受的容忍范围内。
5. 最终对比 `final_oos` 以及 `walk_forward` 交出的独立盲测结果，看其结论是否与前面在训练集/验证集上得出的评估基调保持一致。