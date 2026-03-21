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
* 下一步优先级不是继续围着 `top_k` 或单个超参打转，而是补 `time_decay`、主训练 `rolling` 窗口和暴露控制。

## 快速结论表

| 项目 | 当前结论 | 对后续工作的含义 |
| --- | --- | --- |
| `xgb_ranker` dense validate | 评估段还行，`final_oos` 排序翻向 | 保留为主研究基线，但不再只看总收益 |
| `xgb_regressor` validate | 与 ranker 一样在 OOS 失真 | 漂移不是 ranker 特有问题 |
| `ridge` validate | OOS 主动收益转正，但 `IC / long_short` 仍为负 | 适合做 sleeve / fallback，不适合单独证明 alpha |
| `elasticnet` validate | 常数预测，退化 | 后续对照中排除或单独标退化 |
| construction grid | `top_k=20` 优于 `25`，buffer 只有二阶影响 | 组合构造不是当前主线 |
| 建模主线 | 训练窗、样本权重、行业/风格暴露更关键 | 下一版优先开发抗漂移机制 |

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

## 需要开发的 3 个功能卡片

### 1. `time_decay` sample weight

现状：

* `sample_weight_mode` 目前只支持 `none` 和 `date_equal`

目标：

* 新增 `time_decay / exp_decay` 一类模式，让近期样本权重大、远期样本权重小

价值：

* 直接对抗旧 regime 污染新映射的问题

### 2. 主训练 `rolling` 窗口

现状：

* 现在暴露出来的是评估侧 `walk_forward`，不是最终训练只用最近 `N` 年样本的主训练开关

目标：

* 给主训练流程增加 rolling 窗口配置

价值：

* 把“诊断出漂移”变成“训练机制适应漂移”

### 3. 行业中性化 / 行业内排序

现状：

* 现在可以 join 行业标签，但不会自动 neutralize 或加行业约束

目标：

* 在打分或组合构造阶段加入行业内排序、行业上限或中性化逻辑

价值：

* 降低模型把行业轮动误学成 alpha 的风险

## 推荐运行顺序

这轮 5 个实验已经全部跑完。若后续复现或继续扩展，建议顺序仍然是：

1. 先跑 dense validation ranker，确认新的标准诊断口径。
2. 再跑 `xgb_regressor / ridge / elasticnet` 三个同数据模型对照。
3. 最后用 construction grid 验证组合构造是否还能带来稳健性增益。

## 运行命令

```bash
uv run csml run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_validate_dense_wf.yml
uv run csml run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_regressor_validate.yml
uv run csml run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_ridge_validate.yml
uv run csml run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_elasticnet_validate.yml
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
