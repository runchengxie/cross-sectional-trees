# HK 季度 PIT Overlay Regime Shift 记录（2026-03）

本页解决什么：记录 2026-03 这轮 HK 季度 PIT overlay 研究里关于 `regime shift / concept drift` 的结论、证据和后续实验计划。  
本页不解决什么：不定义 CLI 契约，也不替代 `docs/config.md` 和 `docs/outputs.md`。  
适合谁：需要复盘这轮实验、继续接着跑研究，或准备把诊断结论转成开发任务的人。  
相关页面：`docs/research/README.md`、`docs/playbooks/hk-selected.md`、`docs/config.md`

## 阶段结论摘要

如果只看这一页，先记住 5 句：

* 这轮问题更像 `regime shift / concept drift`，不是单个模型或单次回测偶然失手。
* 主问题表现为：`final_oos` 上排序关系翻向，绝对收益偶尔还在，但横截面 rank 已经不稳。
* 换模型家族不是主解。`xgb_ranker / xgb_regressor / ridge` 在同一条 `PIT core + provider overlay` 数据路线下都出现了 `final_oos IC < 0`。
* `ridge` 仍可保留为简单 sleeve / fallback 候选，但它没有修复排序关系；`elasticnet` 在当前口径下已经退化，应排除。
* 截至 `2026-03-22`，`exp_decay + rolling` 已经把 `final_oos IC` 从负值翻回正值，应提升成新的抗漂移基线；`group cap=3` 暂不适合作为默认配置。
* 若要开始考虑实盘，当前更像是进入“小仓位 canary / shadow run”阶段，而不是任何一个配置都已足够支持单模型大仓上线。

## 快速结论表

| 项目 | 当前结论 | 对后续工作的含义 |
| --- | --- | --- |
| `xgb_ranker` dense validate | 评估段还行，`final_oos` 排序翻向 | 保留为主研究基线，但不再只看总收益 |
| `xgb_regressor` validate | 与 ranker 一样在 OOS 失真 | 漂移不是 ranker 特有问题 |
| `ridge` validate | OOS 主动收益转正，但 `IC / long_short` 仍为负 | 适合做 sleeve / fallback，不适合单独证明 alpha |
| `elasticnet` validate | 常数预测，退化 | 后续对照中排除或单独标退化 |
| construction grid | `top_k=20` 优于 `25`，buffer 只有二阶影响 | 组合构造不是当前主线 |
| 抗漂移模板 | `exp_decay + rolling` 首次把 `final_oos IC` 翻正，`group cap=3` 仅改善暴露不改善信号 | 以 `exp_decay + rolling` 作为新基线，再扫 `halflife × train_window.size` |
| 实盘适配 | `h12_w16` 最像 canary 基线；`h06_w16` 更像收益 challenger；`h12_w12` 偏保守；`h18_w12` 先留研究池 | 先做小仓位试运行和并行监控，不要直接升成唯一主模型 |
| 建模主线 | 训练窗、样本权重、行业/风格暴露更关键 | 下一版优先围绕抗漂移机制细化参数，而不是回到纯组合构造调参 |

## 背景

这轮讨论围绕 HK 季度 `PIT core + provider valuation overlay + xgb_ranker` 研究单元展开，核心基线配置在：

* [`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker.yml`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker.yml)

最关键的验证 run 是：

* `artifacts/runs/hk_sel_q_g4_fixed_pit_overlay_xgb_rank_oos_validate_20260321_162156_172122ad/`

## 核心判断

这次更像是碰到了 `feature -> future_return` 横截面映射的漂移，而不只是“市场涨跌变了”。

换句话说，市场未必没有赚钱机会，但旧训练窗里学到的排序关系，在 `2023-12-29` 到 `2025-09-29` 这段真留出集上已经不再稳定。

## 关键证据

### 1. `final_oos` 赚钱，但排序失效

在 `final_oos` 段：

* IC 均值是 `-0.1003`
* `long_short` 是 `-6.56%`
* 主动累计收益是 `-10.6%`
* 组合绝对收益仍然有 `45.2%`

见：

* `artifacts/runs/hk_sel_q_g4_fixed_pit_overlay_xgb_rank_oos_validate_20260321_162156_172122ad/summary.json`

这说明问题不是“市场不能赚钱”，而是“模型的横截面排序关系错了”。

### 2. 命中率不差，但分位单调性反了

同一段 `final_oos` 里：

* `hit_rate` 仍有 `56.2%`
* `topk_positive_ratio` 仍有 `59.4%`
* 但分位收益反向，最低分桶均值 `12.6%` 高于最高分桶 `6.0%`

这说明模型偶尔还能抓到赚钱股票，但全市场排序已经不再可靠。

### 3. `signal_direction` 在前后窗口切换

`validate` 的 walk-forward 结果里：

* window 2 是 `signal_direction = 1`
* window 3 变成 `signal_direction = -1`

对应文件：

* `artifacts/runs/hk_sel_q_g4_fixed_pit_overlay_xgb_rank_oos_validate_20260321_162156_172122ad/summary.json`

近邻模型 `g3` 也有类似前后翻向：

* `artifacts/runs/hk_sel_q_4way_g3_price_pit_core_xgb_rank_20260316_134927_6dcfdcbe/walk_forward_summary.csv`

所以这更像是季度 PIT 建模路线共同面对的 regime 问题，而不是单个 run 的偶然失手。

### 4. 普通正则化不是主答案

`regularized` 版本并没有救回来，反而整体转负：

* IC `-0.1121`
* `long_short = -1.81%`
* 总收益 `-12.4%`

对应文件：

* `artifacts/runs/hk_sel_q_g4_fixed_pit_overlay_xgb_rank_reg_20260321_162702_69cb5540/summary.json`

所以主矛盾不像是“树太深了，缩一下就好”，而更像是 non-stationarity。

### 5. 这次 `validate` 的 OOS 执行是干净的

`backtest_periods_oos.csv` 里退出延迟全是 `0`：

* `artifacts/runs/hk_sel_q_g4_fixed_pit_overlay_xgb_rank_oos_validate_20260321_162156_172122ad/backtest_periods_oos.csv`

因此这次结论不该归因到执行 bug。

## 建模上学到什么

### 1. 单个长窗、锚定式训练的全局模型太脆

旧样本里的关系会污染新阶段。只要市场领导权、行业轮动或风格溢价切换得足够明显，旧映射就会在新 OOS 上漂。

### 2. 不能再把总收益当主要筛选标准

强市场里模型就算排序错了，也可能因为持仓里碰到几只强票而赚钱。后续更应该盯：

* `final_oos` 的 IC
* 分位单调性
* 主动收益
* `signal_direction` 稳定性

### 3. 模型大概率学进去了风格 / 行业暴露

当市场领导权切换时，模型排名会一起漂。所以后面不只是要调模型，还要看暴露管理。

### 4. 现阶段优先修训练机制，不是继续围着单个超参转

更重要的是：

* 训练窗口
* 样本加权
* 暴露控制
* 稳定性筛选

## 当前建议的研究门槛

后续候选模型不建议再只看总收益。更合理的晋级门槛是：

* `final_oos` 为正
* quantile 单调性不反向
* `signal_direction` 在 walk-forward 里不过度频繁翻转
* 没有异常退出延迟

## 本轮执行的 5 个实验

这 5 个配置最初是为了验证“是不是 shared non-stationarity”而提出，现在已经全部执行完。这里保留它们，是为了让后续复现和扩展时能快速对应到同一批 run。

### 1. Dense validation ranker

目的：把 `final_oos + 更密 walk-forward + 行业 bucket_ic` 固化成新的标准诊断口径。

配置：

* [`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_validate_dense_wf.yml`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_validate_dense_wf.yml)

### 2. Same data, XGB regressor

目的：判断 OOS 漂移是不是 `ranker` 特别脆，还是同一信号族普遍脆。

配置：

* [`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_regressor_validate.yml`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_regressor_validate.yml)

### 3. Same data, ridge probe

目的：看简单线性映射是否也同样翻向。

配置：

* [`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_ridge_validate.yml`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_ridge_validate.yml)

### 4. Same data, ElasticNet probe

目的：看少量稀疏信号能不能比树模型更稳。

配置：

* [`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_elasticnet_validate.yml`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_elasticnet_validate.yml)

### 5. Small construction grid

目的：在不改信号本体的前提下，只比较 `top_k / buffer` 的组合构造稳健性。

配置：

* [`configs/experiments/sweeps/hk_selected__quarterly_pit_core_hybrid_provider_overlay_construction_grid.yml`](../../configs/experiments/sweeps/hk_selected__quarterly_pit_core_hybrid_provider_overlay_construction_grid.yml)

## 这 5 个实验的结果（2026-03-21 已执行）

这一轮结果把核心判断进一步坐实了：主问题不是 `xgb_ranker` 这个模型单点失效，而是这条 `PIT core + provider overlay` 数据路线在 `final_oos` 上发生了共同失真。

更直接地说：

* `xgb_ranker / xgb_regressor / ridge` 三个非退化模型的 `final_oos IC` 全都为负
* `elasticnet` 在当前配置下退化成常数预测
* `top_k / buffer` 这类组合构造调整只有二阶影响，解决不了主问题

### 1. Dense validation ranker：继续支持 regime shift 判断

run：

* `artifacts/runs/hk_sel_q_g4_fixed_pit_overlay_xgb_rank_validate_wf_dense_20260321_221359_d0767f2e/`

关键结果：

* 评估段 `IC = 0.0801`、`long_short = 5.25%`
* 但 `final_oos IC = -0.0926`
* `final_oos long_short = -1.97%`
* `final_oos active_total_return = -5.25%`
* `final_oos` 分位收益反向，最低分位均值高于最高分位

这说明：

* 旧训练窗里学到的排序关系到了真留出集已经失效
* 绝对收益还能为正，不足以证明排序有效

更有信息量的是 dense walk-forward：

* `2021-03-31` 到 `2023-09-29` 的 6 个窗口里，`test_ic` 都是正的
* 但 6 个 long-only 回测总收益全是负的

这说明更早一段更像“横截面 alpha 还在，但 long-only 不好赚”；而到了 `final_oos`，连横截面排序本身都开始翻。

### 2. Same data, XGB regressor：换成回归器也没救回来

run：

* `artifacts/runs/hk_sel_q_g4_fixed_pit_overlay_xgb_reg_validate_20260321_221755_46a3f5b3/`

关键结果：

* `final_oos IC = -0.0951`
* `final_oos long_short = -4.83%`
* `final_oos active_total_return = -15.36%`

这说明：

* 问题不是 `ranker` 特别脆
* 同一条信号族在 OOS 上整体都在漂

### 3. Same data, ridge probe：可以当简单 sleeve 候选，但不是更好的 alpha 证据

run：

* `artifacts/runs/hk_sel_q_g4_fixed_pit_overlay_ridge_validate_20260321_224332_7d3b0333/`

关键结果：

* `final_oos IC = -0.1159`
* `final_oos long_short = -4.49%`
* `final_oos active_total_return = +3.30%`
* `final_oos` 组合总收益高于同段 benchmark，但分位仍然反着排

这说明：

* `ridge` 没有修复排序关系
* 它更像是在组合暴露更温和的前提下，给出了更能扛波动的持仓结果

因此更合理的定位是：

* 可以保留为后续 ensemble / fallback sleeve 候选
* 不适合单独作为“这条数据路线已有稳定 alpha”的证据

补充说明：

* 这条 ridge dense walk-forward 里有一个窗口出现了延迟退出，提示后续比较模型时仍要单独检查执行完整性，不能只看总表

### 4. Same data, ElasticNet probe：当前口径下已经退化

run：

* `artifacts/runs/hk_sel_q_g4_fixed_pit_overlay_elasticnet_validate_20260321_224513_368e1bb5/`

关键结果：

* `pred_nunique = 1`
* `constant_prediction = true`
* `feature_importance_nonzero = 0`

这说明：

* 当前这组 `ElasticNet` 配置没有学到任何有效信号
* 后续模型族比较里应把它排除，或单独标注为退化 run

### 5. Small construction grid：只看到了二阶影响

run：

* `artifacts/runs/hk_sel_q_g4_fixed_pit_overlay_construction_grid_summary.csv`

关键结果：

* `top_k = 20` 明显优于 `25`
* `buffer_entry = 4/5` 基本没有差异
* `buffer_exit = 10` 只是在不改收益的前提下略微降低换手

这说明：

* 组合构造仍值得优化，但影响是二阶的
* 现阶段它解决不了 `final_oos` 排序翻向的问题

额外注意：

* 这次 grid 只覆盖了 `2` 个 backtest periods，适合做小确认，不适合过度外推
* grid 表里 `eval_ic_mean` 每行一样是正常现象，因为 `csml grid` 会复用同一份 scored artifact，只重算组合构造，不会每格重新训练模型

## 截至当前的更新判断

这页最初提出的“先量化漂移，再补抗漂移训练机制”仍然成立，而且优先级更清楚了：

* `xgb_ranker` 仍应保留为主研究基线，因为它仍是这条路线里最接近原始 alpha 假设的模型
* `ridge` 可以保留为简单稳定 sleeve 候选，用于后续 ensemble 或 fallback 比较
* `elasticnet` 在当前口径下应直接排除，避免把退化 run 混进模型对照
* `top_k / buffer` 调整不再是主线任务

## 下一版建模路线

从这页目前积累的证据看，下一版研究更适合按下面的顺序推进：

1. 继续把 `final_oos + dense walk_forward + 行业拆分` 作为标准诊断口径，先确认漂移画像是否稳定复现。
2. 在保留 `xgb_ranker` 主基线的同时，把 `ridge` 当作简单 sleeve / fallback 候选，而不是继续把精力放在 `ranker vs regressor` 的模型切换上。
3. 把主要开发资源投向抗漂移训练机制：`time_decay`、主训练 `rolling` 窗口、行业/风格暴露控制。
4. 等训练机制补上之后，再回头看是否需要新的 ensemble、行业内排序或更复杂的组合构造。

## 抗漂移功能落地进展（2026-03-21）

### 1. `time_decay` sample weight

当前状态：

* 已落地 `model.sample_weight_mode=exp_decay`
* 支持 `model.sample_weight_params.halflife` 或 `decay_rate`

当前语义：

* 近期训练日期权重更高
* 同一日期内仍按横截面样本数均分，避免单日样本数变化直接改变总权重

价值：

* 直接对抗旧 regime 污染新映射的问题

### 2. 主训练 `rolling` 窗口

当前状态：

* 已落地 `model.train_window`
* 支持 `mode=rolling`，`unit=dates|years`

当前语义：

* 不再只停留在评估侧 `walk_forward`
* 主训练、CV、walk-forward 训练段、`final_oos` 拟合和 `live.train_mode=full` 复训都会共用这套训练窗口逻辑

价值：

* 把“诊断出漂移”变成“训练机制适应漂移”

### 3. 行业中性化 / 行业内排序

当前状态：

* 最小版已落地：`backtest.group_col + backtest.max_names_per_group`
* 这是组合构造层的 group cap，不是分数残差化，也不是完整行业中性化

当前语义：

* 可直接利用已 join 的行业列，在回测、持仓导出、live snapshot 和 `grid` 复算里限制单组最多持仓数

价值：

* 降低模型把行业轮动误学成 alpha 的风险

仍未覆盖的范围：

* 行业内排序
* 行业中性 residualization
* 风格暴露约束

## 可直接跑的抗漂移模板

在上述 3 个功能都已经落地后，下一轮 HK overlay 研究可以先从下面这 3 个 progressive variant 开始。

### 1. `exp_decay` only

适合回答的问题：

* 只提高近期样本权重，是否已经足够改善 `final_oos`

配置：

* [`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_exp_decay_validate.yml`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_exp_decay_validate.yml)

关键设置：

* `model.sample_weight_mode=exp_decay`
* `model.sample_weight_params.halflife=12`

### 2. `exp_decay + rolling`

适合回答的问题：

* 在近期加权之外，再限制主训练只看最近 `16` 个季度训练日期，能否进一步减少旧 regime 污染

配置：

* [`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_exp_decay_rolling_validate.yml`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_exp_decay_rolling_validate.yml)

关键设置：

* `model.sample_weight_mode=exp_decay`
* `model.train_window.mode=rolling`
* `model.train_window.size=16`
* `model.train_window.unit=dates`

### 3. `exp_decay + rolling + group cap`

适合回答的问题：

* 若训练侧已经做了抗漂移处理，再在组合层限制单行业最多 `3` 只，能否减少行业轮动带来的误伤

配置：

* [`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_exp_decay_rolling_groupcap_validate.yml`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_exp_decay_rolling_groupcap_validate.yml)

关键设置：

* `model.sample_weight_mode=exp_decay`
* `model.train_window.mode=rolling`
* `backtest.group_col=first_industry_name`
* `backtest.max_names_per_group=3`

推荐运行顺序：

1. 先跑 `exp_decay` only，看单独样本加权是否已经带来改善。
2. 再跑 `exp_decay + rolling`，判断主训练窗口收缩的增量价值。
3. 最后跑 `exp_decay + rolling + group cap`，把组合层暴露控制作为第三层增量。

## 这 3 个抗漂移模板的结果（2026-03-22 已执行）

这一轮结果第一次给出了“训练机制已经开始修复 `final_oos` 排序关系”的正面证据，但边界也需要说清楚：

* `exp_decay` 单独版仍然没有解决 `final_oos` 失真，只是把负 IC 拉得没那么差。
* `exp_decay + rolling` 是第一版把 `final_oos IC` 从负翻正、并同时把主动收益翻正的配置，应提升成新的抗漂移基线。
* `group cap=3` 没有改善信号本身，只是在组合层进一步压暴露；当前这档约束会牺牲收益，不适合默认开启。

### 1. `exp_decay` only：方向改善，但还不够

run：

* `artifacts/runs/hk_sel_q_g4_fixed_pit_overlay_xgb_rank_expdecay_validate_20260322_152544_ca332382/`

关键结果：

* `final_oos IC = -0.0597`
* `final_oos long_short = -2.11%`
* `final_oos active_total_return = -9.50%`

这说明：

* 只靠近期样本加权，还不足以把旧 regime 污染清掉
* 它比 dense baseline 略好，但还不能叫“开始稳定有效”

### 2. `exp_decay + rolling`：当前最重要的正面信号

run：

* `artifacts/runs/hk_sel_q_g4_fixed_pit_overlay_xgb_rank_expdecay_roll16_validate_20260322_155439_19eeecf9/`

关键结果：

* `final_oos IC = +0.0825`
* `final_oos long_short = +0.68%`
* `final_oos top20_positive_ratio = 70.6%`
* `final_oos active_total_return = +13.7%`
* `final_oos beta = 0.44`
* `final_oos alpha = 24.9%`

这说明：

* 主问题确实更像“旧样本污染当前 regime”
* 相比单独 `exp_decay`，主训练 `rolling` 窗口是更关键的增量
* 这版更适合作为新的抗漂移基线

但仍要保留两点克制：

* `final_oos` 只有 `8` 个日期，统计把握还不硬
* quantile 还不是完全单调，`Q4` 仍略高于 `Q5`

因此更准确的表述是：

* 这版已经“开始重新出现可用 alpha signal”
* 但还不是“已经确认稳定有效因子”

### 3. `exp_decay + rolling + group cap`：约束有效，但不该先默认开启

run：

* `artifacts/runs/hk_sel_q_g4_fixed_pit_overlay_xgb_rank_expdecay_roll16_groupcap3_validate_20260322_160246_4563fd25/`

关键结果：

* `final_oos IC` 与 `long_short` 和 rolling 版相同
* 但 `final_oos total_return` 从 `84.7%` 降到 `73.7%`
* `final_oos active_total_return` 从 `+13.7%` 降到 `+6.9%`
* `final_oos sharpe` 从 `2.01` 降到 `1.62`

这说明：

* 当前这档 group cap 没有改善模型分数本身
* 它更像是组合暴露控制工具，而不是抗漂移主解
* 在没有进一步验证前，不适合直接替代无约束版成为默认基线

## 更新后的抗漂移基线判断

截至 `2026-03-22`，更合理的默认口径已经变成：

* 把 [`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_validate.yml`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_validate.yml) 视为新的抗漂移基线
* 它对应当前最佳已验证组合：`halflife=12` + `rolling train_window.size=16`
* 暂不默认启用 `group cap=3`

这条判断的含义不是“问题已经解决”，而是：

* 下一轮研究不必再回到无 rolling 的旧基线
* 更值得在这条新基线上继续扫参数，判断改善是否可重复

## 实盘适配判断（2026-03-22）

这一步更适合回答“哪些配置已经开始接近可实盘”，而不是“谁回测收益最高”。

更准确地说，截至这轮结果：

* 还没有任何一个配置足够支持“单模型、唯一主信号、直接大仓上线”。
* 但已经可以区分出谁适合先进入 `paper -> shadow -> 小仓位 canary` 阶段。

### 1. `h12_w16`：最适合先做小仓位 canary

run：

* `artifacts/runs/hk_sel_q_g4_fixed_pit_overlay_xgb_rank_antidrift_h12_w16_validate_20260322_170636_f2222aec/`

判断依据：

* `eval_ic = 0.0225`
* `eval_long_short = 1.34%`
* `final_oos IC = 0.0825`
* `final_oos long_short = 0.68%`
* `final_oos beta = 0.44`
* `walk_forward` 6 窗 `test_ic` 全正，`signal_direction` 全为 `-1.0`
* `final_oos` 全部 `exit_delay_steps = 0`

这说明：

* 它不是收益最高的一档，但研究段、walk-forward 和 `final_oos` 的口径最一致
* 当前最像“可以先拿去做低权重实盘试运行”的默认版本

为什么当前说它“价值最好”，而不只是“回测最好”：

* `h06_w16` 的收益弹性更强，但 `eval_long_short` 仍为负，且最后一窗 `signal_direction` 翻到 `1.0`，更像高弹性 challenger，不像默认主模型
* `h12_w12` 的回撤控制更漂亮，但 `cv_ic` 接近 `0`，`walk_forward` 里也有两窗翻负，更像偏防守备选
* `h18_w12` 的 realized result 不差，但 `walk_forward` 已经是 `3` 正 `3` 负，方向切换也更明显
* `h12_w16` 不是单项冠军，但在“`final_oos` 翻正、方向稳定、beta 较低、无延迟退出、研究段不过度失真”这几项里同时过线

换句话说，`h12_w16` 现在最有价值，不是因为它某个指标绝对最高，而是因为：

* 它是当前最适合拿去验证“这条抗漂移建模路线是否能开始承接 live canary”的参数组
* 它在“稳定性”和“收益弹性”之间给出了最均衡的折中
* 它最适合当后续比较新实验时的默认参照组

### 2. `h06_w16`：适合并行 challenger，不适合直接升成唯一主模型

run：

* `artifacts/runs/hk_sel_q_g4_fixed_pit_overlay_xgb_rank_antidrift_h06_w16_validate_20260322_165143_a27be519/`

判断依据：

* `final_oos long_short = 4.33%`
* `final_oos active_total_return = 30.9%`
* `final_oos sharpe = 2.43`

但同时：

* `eval_long_short = -2.35%`
* `walk_forward` 最后一窗出现 `signal_direction = 1.0`
* `walk_forward` 有 `5` 窗 `test_ic > 0`、`1` 窗 `test_ic < 0`

这说明：

* 它的收益弹性最强
* 但稳定性略逊于 `h12_w16`
* 更适合当并行对照的 challenger，先做 shadow 或小权重副模型

### 3. `h12_w12`：保守备选

run：

* `artifacts/runs/hk_sel_q_g4_fixed_pit_overlay_xgb_rank_antidrift_h12_w12_validate_20260322_170200_e015c069/`

判断依据：

* `final_oos max_drawdown = -1.75%`
* `final_oos beta = 0.42`
* `final_oos active_total_return = 15.4%`
* `final_oos` 全部 `exit_delay_steps = 0`

但同时：

* `cv_ic` 接近 `0`
* `walk_forward` 有 `4` 窗 `test_ic > 0`、`2` 窗 `test_ic < 0`
* `signal_direction` 在窗口中有切换

这说明：

* 它更像偏防守型的备选
* 若上线优先目标是控制回撤而不是抢收益，可以保留在候选池
* 但优先级仍低于 `h12_w16`

### 4. `h18_w12`：先留在研究池

run：

* `artifacts/runs/hk_sel_q_g4_fixed_pit_overlay_xgb_rank_antidrift_h18_w12_validate_20260322_171514_ad93ea3c/`

判断依据：

* `final_oos` 表现并不差：`IC = 0.0463`、`long_short = 1.98%`、`sharpe = 2.76`
* 但 `walk_forward` 有 `3` 窗 `test_ic > 0`、`3` 窗 `test_ic < 0`
* 后半段 `signal_direction` 切换更明显

这说明：

* 它的 realized result 不差
* 但稳定性证据还不够支持优先拿去 live

### 当前更实用的结论

若必须现在给出一个实盘顺序：

1. `h12_w16`：默认 canary 基线
2. `h06_w16`：并行 challenger
3. `h12_w12`：偏保守备选
4. `h18_w12`：继续留在研究池

这条排序的前提是：

* 目标是“先开始可控地试运行”，不是“证明已经可以大仓正式上线”
* `final_oos` 仍只有 `8` 个日期，所以所有 live 判断都应带监控和降级预案

## `h12_w16` canary 监控清单

如果下一步要把 `h12_w16` 放进 `paper -> shadow -> 小仓位 canary`，至少应该固定看下面这些指标：

### 1. 排序是否还在工作

每个 rebalance date 都记录：

* 当期横截面 `IC`
* `top_k` 正收益占比
* `Q5-Q1` 或近似的 top-bottom spread

触发关注的信号：

* 连续 `2` 期 `IC < 0`
* 连续 `2` 期 `top_k_positive_ratio < 50%`
* 连续 `2` 期 `long_short <= 0`

### 2. 是否重新长得像高 beta 暴露

至少每月更新一次：

* 滚动 `beta`
* 滚动主动收益
* 滚动信息比率

触发关注的信号：

* `beta` 明显抬升并持续接近或高于 `1`
* 主动收益重新转负，但组合绝对收益仍然为正

后一种情况尤其要警惕，因为它通常意味着“市场在涨，但排序关系又开始漂了”。

### 3. 方向是否出现新的 sign flip

每次重训后都检查：

* `cv_ic` 的符号
* `walk_forward` 最近几窗 `signal_direction`
* live 打分是否仍沿用 `-1.0` 方向

触发关注的信号：

* 新一轮 `walk_forward` 再次出现 `signal_direction` 来回切换
* `cv_ic` 和最近 `walk_forward test_ic` 的方向重新互相冲突

### 4. 执行完整性是否退化

每次 run 都检查：

* `backtest_periods.csv`
* `backtest_periods_oos.csv`
* 持仓文件中的缺失退出或超长持有

触发关注的信号：

* `exit_delay_steps > 0`
* `delayed_exit_ratio` 明显上升
* 平均持有天数明显偏离季度节奏

### 5. 行业暴露是否重新集中

即使当前没有默认启用 `group cap`，也建议持续观察：

* 前 `20` 持仓的行业分布
* 单行业持仓数
* 行业贡献是否过度集中在一两个板块

触发关注的信号：

* 单一行业持仓数持续偏高
* 组合收益越来越依赖单一主题板块

如果这些现象重新出现，就说明当前改善可能更多来自阶段性主题暴露，而不是更稳的横截面 alpha。

## 下一轮建议配置：`halflife × train_window.size`

下一轮最值得扫的是：

* `halflife = 6 / 12 / 18`
* `train_window.size = 12 / 16 / 20`

推荐配置入口：

* 抗漂移基线：[`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_validate.yml`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_validate.yml)

3 × 3 搜索矩阵：

| halflife | rolling=12 | rolling=16 | rolling=20 |
| --- | --- | --- | --- |
| `6` | [`hl06_w12`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h06_w12_validate.yml) | [`hl06_w16`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h06_w16_validate.yml) | [`hl06_w20`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h06_w20_validate.yml) |
| `12` | [`hl12_w12`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w12_validate.yml) | 基线：[`antidrift`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_validate.yml) / [`hl12_w16`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_validate.yml) | [`hl12_w20`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w20_validate.yml) |
| `18` | [`hl18_w12`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h18_w12_validate.yml) | [`hl18_w16`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h18_w16_validate.yml) | [`hl18_w20`](../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h18_w20_validate.yml) |

建议优先顺序：

1. 先以新基线 `halflife=12 / rolling=16` 作为中心点重复确认。
2. 再沿 `rolling size` 方向先看 `12 / 20` 两端，判断窗口长度敏感性。
3. 最后再沿 `halflife` 方向比较 `6 / 18`，判断近期加权到底要多陡。

## 推荐运行顺序

这轮 5 个实验已经全部跑完。若后续复现或继续扩展，建议顺序仍然是：

1. 先跑 dense validation ranker，确认新的标准诊断口径。
2. 再跑 `xgb_regressor / ridge / elasticnet` 三个同数据模型对照。
3. 最后用 construction grid 验证组合构造是否还能带来稳健性增益。
4. 若继续沿抗漂移主线推进，则从新的 `antidrift` 基线出发，扫 `halflife × train_window.size`，暂不默认启用 `group cap=3`。

## 运行命令

```bash
uv run csml run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_validate_dense_wf.yml
uv run csml run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_regressor_validate.yml
uv run csml run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_ridge_validate.yml
uv run csml run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_elasticnet_validate.yml
uv run csml run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_exp_decay_validate.yml
uv run csml run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_exp_decay_rolling_validate.yml
uv run csml run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_exp_decay_rolling_groupcap_validate.yml
uv run csml run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_validate.yml
uv run csml run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h06_w12_validate.yml
uv run csml run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h06_w16_validate.yml
uv run csml run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h06_w20_validate.yml
uv run csml run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w12_validate.yml
uv run csml run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_validate.yml
uv run csml run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w20_validate.yml
uv run csml run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h18_w12_validate.yml
uv run csml run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h18_w16_validate.yml
uv run csml run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h18_w20_validate.yml
uv run csml grid \
  --config configs/experiments/sweeps/hk_selected__quarterly_pit_core_hybrid_provider_overlay_construction_grid.yml \
  --run-name-prefix hk_sel_q_g4_fixed_pit_overlay_construction \
  --top-k 20,25 \
  --cost-bps 25 \
  --buffer-exit 8,10 \
  --buffer-entry 4,5 \
  --output artifacts/runs/hk_sel_q_g4_fixed_pit_overlay_construction_grid_summary.csv
```

## 备注

这份记录是研究笔记，不是稳定 API 或输出契约。若后续把其中某些诊断逻辑正式产品化，应同步更新：

* `docs/config.md`
* `docs/outputs.md`
* `docs/playbooks/hk-selected.md`
