# HK Quarterly 纯基本面路线（2026-03-29）

本页解决什么：把“不用量价指标、只看 PIT 基本面”的 HK quarterly 研究路线单独收成一页，并给出第一波更合理的配置。  
本页不解决什么：不宣称这条线已经优于当前主线，也不把它包装成已验证可上线策略。  
适合谁：已经看过当前 quarterly 主线/副线，想回答“纯基本面到底值不值得单开一条线、该先用什么模型”的读者。  
读完你会得到什么：一套纯基本面路线的定位、为什么它值得做、为什么暂时不该直接回头救 `elasticnet`，以及 3 个可直接跑的 config。  
相关页面：`docs/research/notes/hk-quarterly-current-state-20260329.md`、`docs/research/notes/hk-quarterly-next-step-configs-20260329.md`、`docs/concepts/benchmark-protocol.md`、`docs/concepts/model-landscape.md`

页面性质：`research-note`  
最后核对时间：`2026-03-29`  
权威来源：截至 `2026-03-29` 的 tracked config、当前 quarterly mainline/challenger 收口、以及本页引用的纯基本面配置  
冲突优先级：如果与具体 run 的 `config.used.yml` / `summary.json` 冲突，以 run 产物为准；如果与后续 current-state 或 playbook 冲突，以更晚页面为准

## 1. 先记住 8 句

* 纯基本面路线值得做，但更适合当独立 benchmark / challenger，不适合直接替掉当前 hybrid 主线。
* 这条线当前最值得回答的问题，不是“哪个模型名字更高级”，而是“PIT 基本面本身有没有独立信号”。
* 当前第一波更合理的模型顺序是：`ridge -> small xgb_regressor -> xgb_ranker`。
* `elasticnet` 不是完全没价值，但更适合放到第二波；在纯基本面线上，它不该先于 `ridge` 和小 XGB。
* 真正限制这条线的不是面板行数太少，而是独立时间块不多、横截面相关强、regime drift 明显。
* 所以 XGB 不是不能用，但必须是小树、强约束、短窗口；不要因为“有几千行面板”就把它当大样本问题。
* 第一波纯基本面配置先保留 `close`，不同时把 `tr_close` 这个问题一起混进来；如果这条线本身站得住，再单独做 `close / tr_close` A/B。
* 特征先只用当前覆盖更密的 income / cash-flow 子集，不直接上 debt-heavy balance-sheet 比率。

## 2. 为什么这条线值得单独开

当前 quarterly 主线是 `hybrid`，也就是慢量价 + PIT 核心财务 + 估值 overlay。  
这当然是更强的研究单元，但它也会让一个问题变得不够干净：

* 如果结果好，到底是价格行为在起作用，还是基本面真的有独立贡献？

所以纯基本面路线的价值，不在于它一定更强，而在于它能回答三件更基本的问题：

1. 只靠 PIT 财务信息，横截面排序有没有信号。
2. 这条信号相对 `price-only` 是补充，还是其实只是混合路线里的次要成分。
3. 在不借助量价特征的情况下，线性模型和小型非线性模型的差距到底有多大。

这也是当前仓库 benchmark protocol 把研究顺序写成 `price-only -> PIT-only -> hybrid` 的原因，而不是一开始就只盯着混合特征。

## 3. 样本是不是太少，XGB 会不会不合适

如果只看表面行数，当前这条 HK quarterly PIT universe 并不算特别小：

* 每个 rebalance date 大致是一百多只股票
* `w16` 训练窗约等于 `16` 个季度点
* 粗看会形成几千行 panel

所以问题不是“XGB 连样本都吃不饱”，而是：

* 真正独立的时间块只有 `16` 个季度点左右
* 横截面上同日股票的相关性很强
* 旧 regime 对新 regime 的污染很明显

也就是说，这更像“时间块很少的横截面问题”，不是“自由独立样本很多的大样本机器学习问题”。

因此更合理的结论是：

* `XGB` 可以用，但要小、要克制
* `ridge` 必须保留，作为更弱、更稳的 sanity benchmark
* `elasticnet` 不是第一优先，因为当前这组纯财务特征本来就相关，稀疏化不一定带来更稳的结论

## 4. 为什么当前先不把 elasticnet 放进第一波

这里不是说 `elasticnet` 没意义，而是研究顺序要讲究。

第一波纯基本面路线真正想回答的是：

1. 纯基本面有没有独立信号。
2. 线性基线和小型非线性模型差多少。
3. 排序损失相对回归损失有没有额外收益。

在这三个问题还没回答前，先上 `elasticnet`，边际信息通常不如下面两件事：

* `ridge` 有没有最基本的可解释信号
* 小 XGB 相对 `ridge` 的提升到底是真提升，还是噪音

所以当前更合理的顺序是：

1. `ridge`
2. `xgb_regressor`
3. `xgb_ranker`
4. 如果这三条里已经看到一点稳定性，再补 `elasticnet`

## 5. 特征口径为什么先这么保守

第一波纯基本面配置现在只保留了更密的 PIT 子集：

* `sales`
* `growth_sales`
* `operating_profit`
* `growth_operating_profit`
* `basic_earnings_per_share`
* `growth_basic_earnings_per_share`
* `net_profit`
* `growth_net_profit`
* `cash_flow_from_operating_activities`
* `growth_cash_flow_from_operating_activities`
* `profit_margin`
* `cfo_margin`
* `cfo_to_profit`
* `days_since_report`

这样做有两个原因：

* 这组字段当前在本地 `pipeline_fundamentals.parquet` 里的覆盖更稳
* 它能把研究问题保持干净，不把“低覆盖 balance-sheet 字段导致样本塌缩”混进第一波判断里

所以这条线当前不是“纯财务大全”，而是“纯财务里更稳、覆盖更好的核心子集”。

## 6. 为什么先保留 close，不同时做 tr_close

纯基本面路线当然可以考虑 `tr_close`，而且从经济意义上说也有道理。  
但当前第一波不默认切到 `tr_close`，原因不是分红不重要，而是要避免同时混入两个研究问题：

1. 纯 PIT 基本面本身有没有信号。
2. 纯 PIT 基本面在 total-return 口径下会不会更好。

如果一开始两个问题一起改，解释会变脏。  
所以当前第一波先保留 `close`；如果这条线本身能站住，再补一轮 `close / tr_close` A/B 会更干净。

## 7. 这次新增的 3 个 config

### 7.1 Shared Base

* [`configs/experiments/variants/hk_selected__quarterly_pit_financial_exec_balanced_local_base.yml`](../../../configs/experiments/variants/hk_selected__quarterly_pit_financial_exec_balanced_local_base.yml)

作用：

* 复用当前 quarterly 主线的本地 daily / instruments / ex_factors 和 balanced execution
* 保留当前 dense validation、walk-forward 和 final OOS 口径
* 去掉 price/volume 特征和 provider valuation overlay，只保留纯 PIT 财务特征

### 7.2 Ridge Benchmark

* [`configs/experiments/variants/hk_selected__quarterly_pit_financial_ridge_exec_balanced_local.yml`](../../../configs/experiments/variants/hk_selected__quarterly_pit_financial_ridge_exec_balanced_local.yml)

定位：

* 第一优先 benchmark
* 用来回答“纯基本面线在更弱、更稳的线性模型下有没有最基本的信号”

### 7.3 Small XGB Regressor

* [`configs/experiments/variants/hk_selected__quarterly_pit_financial_xgb_regressor_exec_balanced_local.yml`](../../../configs/experiments/variants/hk_selected__quarterly_pit_financial_xgb_regressor_exec_balanced_local.yml)

定位：

* 第一优先 non-linear probe
* 用来回答“在同一组纯财务特征上，小型非线性回归模型相对 ridge 到底多了多少东西”

### 7.4 Small XGB Ranker

* [`configs/experiments/variants/hk_selected__quarterly_pit_financial_xgb_ranker_exec_balanced_local.yml`](../../../configs/experiments/variants/hk_selected__quarterly_pit_financial_xgb_ranker_exec_balanced_local.yml)

定位：

* 第一波 ranking challenger
* 用来回答“在纯基本面线上，排序损失是不是比回归损失更自然”

## 8. 建议怎么跑

更合理的顺序是：

1. 先跑 `ridge`
2. 再跑 `xgb_regressor`
3. 最后跑 `xgb_ranker`

理由很简单：

* 如果 `ridge` 完全站不住，纯基本面这条线本身就要更谨慎
* 如果 `ridge` 有点东西，而小 XGB 继续提升，说明非线性值得保留
* 如果 `xgb_ranker` 再进一步改善，才说明“纯基本面 + 排序损失”有独立研究价值

如果这三条都不行，就别急着往里塞 `elasticnet` 或更重的 balance-sheet 特征。

## 9. `2026-03-29` 第一波结果

第一波三条纯基本面 run 已经补完：

* `ridge`
* `small xgb_regressor`
* `small xgb_ranker`

对应 run 目录分别是：

* `artifacts/runs/hk_sel_q_pit_financial_ridge_exec_balanced_local_20260329_195743_36ec78b4/`
* `artifacts/runs/hk_sel_q_pit_financial_xgb_reg_exec_balanced_local_20260329_195854_18165ac1/`
* `artifacts/runs/hk_sel_q_pit_financial_xgb_rank_exec_balanced_local_20260329_200011_2c72809c/`

先看完整测试段：

* `ridge`：`total_return -21.17%`，`Sharpe -0.16`
* `xgb_regressor`：`total_return -16.61%`，`Sharpe -0.09`
* `xgb_ranker`：`total_return -12.00%`，`Sharpe -0.04`

再看最近 `Final OOS`：

* `ridge`：`total_return 87.28%`，`Sharpe 1.25`
* `xgb_regressor`：`total_return 71.38%`，`Sharpe 1.32`
* `xgb_ranker`：`total_return 44.63%`，`Sharpe 0.83`

这说明三件事：

1. 纯基本面路线不是完全没有东西；至少它不是一跑就退化成常数预测。
2. 但三条的完整测试段仍然都为负，`walk_forward` 也都是 `0/6` 个正窗口，所以它还远远不到“已验证策略”。
3. “最近 OOS 最亮”和“完整测试段最稳”并不一致。最近亮点更偏 `ridge / xgb_regressor`，而完整测试段相对最不差的是 `xgb_ranker`。

还有一个很关键的小信号：

* `ridge` 的主评估 `signal_direction = -1`
* `xgb_ranker` 也是 `-1`
* 只有 `xgb_regressor` 是 `+1`

这说明当前这组纯 PIT 财务特征，在现有标签和训练窗定义下，方向本身还不够稳。  
所以纯基本面路线当前更适合被理解成“干净 benchmark / challenger 线”，而不是已经可以独立站住的主线。

## 10. 现在最小还值得补的一步

如果纯基本面线还要继续往前走，当前最小、最有先验支撑的 follow-up 不是继续扩很多 balance-sheet 因子，而是只补一个：

* `operating_margin`

原因很简单：

* 第一波纯基本面 `xgb_regressor` 里，`operating_profit / growth_operating_profit` 已经是最靠前的重要特征
* `operating_margin` 和这组经营利润信号逻辑相近，但比 debt-heavy 资产负债表比率更不容易把样本覆盖压塌

对应配置是：

* [`configs/experiments/variants/hk_selected__quarterly_pit_financial_xgb_regressor_exec_balanced_local_operating_margin.yml`](../../../configs/experiments/variants/hk_selected__quarterly_pit_financial_xgb_regressor_exec_balanced_local_operating_margin.yml)

所以这条 sidecar 线更合理的下一步是：

1. 不再扩成 factor zoo
2. 只先看 `operating_margin` 在纯 PIT `xgb_regressor` 上有没有额外增量
3. 如果连这一步都没有明显帮助，再考虑暂停纯基本面扩特征，而不是继续往里塞更重的 balance-sheet 因子

如果按第一波结果继续排优先级，我会这样看：

* `ridge` 保留成 sanity benchmark
* `xgb_regressor` 保留成“最近 regime 更亮”的非线性 probe
* `xgb_ranker` 保留成“完整测试段相对更稳”的 ranking challenger

但这三条都还不足以把 `hybrid` 主线替掉。

## 10. 当前最合理的定位

截至 `2026-03-29`，纯基本面路线更适合被理解成：

* 一条新的独立 benchmark / challenger 线
* 用来回答 PIT 基本面本身有没有稳定信号
* 不用于直接替换当前 `hybrid` 主线

一句话收口：

* 纯基本面路线值得开，但第一波应该是“少特征、弱线性 benchmark、小 XGB probe”的克制版本，而不是马上回到 `elasticnet` 或重开新的模型动物园。
