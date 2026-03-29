# HK Quarterly 下一阶段收口与配置建议（2026-03-29）

本页解决什么：把当前 HK quarterly PIT + overlay 这条线在训练窗、测试窗、特征和下一步配置上的建议收成一页，并给出可直接复用的 config 入口。
本页不解决什么：不替代具体 run 的 `config.used.yml` / `summary.json`，也不把“最近 Final OOS 很亮”包装成已经验证通过。
适合谁：已经看过最近几轮 quarterly notes，想知道“现在到底该保留什么、下一步该跑什么”的读者。
读完你会得到什么：一套更收敛的季度研究建议，以及一组按主线、challenger、窗口探针和特征探针拆好的 config。
相关页面：`docs/research/notes/hk-quarterly-target-design-and-direction-20260324.md`、`docs/research/notes/hk-quarterly-pit-regime-shift-202603.md`、`docs/research/notes/hk-quarterly-price-col-ab-20260325.md`、`docs/research/notes/hk-quarterly-oos-evidence-20260329.md`、`docs/concepts/benchmark-protocol.md`

页面性质：`research-note`
最后核对时间：`2026-03-29`
权威来源：当前 quarterly notes、已落地 balanced execution run、以及本页引用的 tracked config
冲突优先级：如果与具体 run 的 `config.used.yml` / `summary.json` 冲突，以 run 产物为准；如果与当前 playbook 或 preset 冲突，以 playbook / preset 的最新收口为准

## 1. 先记住 8 句

* 当前最像主线的仍然是 `ranker h12_w16 + close + balanced execution`。
* 当前最值得继续盯的 challenger 仍然是 `reg_zscore h12_w16 + tr_close + balanced execution`。
* 对季度策略，训练窗优先按“多少个 rebalance dates”来想，而不是先按“几年”来想。
* 目前更合理的中心点仍然是 `rolling train_window.size = 16`；`12` 和 `20` 更适合做邻域探针，不适合直接升成默认。
* 当前 `final_oos` 这段最近样本已经看过了，所以接下来不该继续围着它大扩参数网格。
* 特征上现在不该继续堆 feature zoo；先做小幅去重，比盲目扩充更值。
* 当前最值得先试的去重是两对单调变换对：`market_cap / log_mcap` 和 `vol / log_vol`。
* 如果后面真要扩特征，也更该优先补一小组杠杆 / 资产负债表风险特征，而不是继续堆技术指标。

## 2. 训练窗和测试窗怎么想

### 2.1 训练窗先看季度点数，不先看年份

放到当前 quarterly 研究里：

* `w12` 约等于 `12` 个季度点，大约 `3` 年
* `w16` 约等于 `4` 年
* `w20` 约等于 `5` 年

现有研究更支持下面这个判断：

* `w16` 是当前更均衡的中心点
* `w12` 值得保留，因为它能回答“是不是该再短一点”
* `w20` 只适合当上限探针，因为现有证据已经显示窗口一拉长，旧 regime 污染会更明显

所以这里真正该调的是 `model.train_window.size`，而不是频繁重切整个历史区间。

### 2.2 测试窗先保持可比，不再反复改边界

当前这条 quarterly dense-validation 路线，建议先继续保留：

* `eval.test_size = 0.4`
* `eval.walk_forward.n_windows = 6`
* `eval.walk_forward.test_size = 0.2`
* `eval.final_oos.size = 0.2`

原因不是“这组切法完美”，而是：

* 现在线索和证据边界已经靠它讲清楚了
* 如果现在再频繁改测试比例，很容易把“重新分桶后看起来更好”误当成策略真的更稳
* 下一轮更干净的证明，应该来自新前瞻样本，而不是继续重切已经看过的历史

按 `2026-03-29` 的数据边界，`final_oos.size = 0.2` 对季度线大致对应最近 `8` 个 OOS 信号点、`7` 个完整持有期。这个量级够用来观察最近 regime，但不该再被当成没用过的 holdout。

## 3. 特征现在该怎么动

### 3.1 先别大扩，也别大砍

当前 quarterly hybrid + overlay 这条线已经有三层信息：

* 慢量价
* PIT 核心财务
* 估值 overlay

而且最近主线和 challenger 的 `feature_importance` 分布都不算“有一大堆完全没用的死特征”。这说明现在最合理的动作不是大规模删库，也不是继续往里加一串新指标。

### 3.2 先做两组去重探针

当前 preset 在建模前会做每期横截面 `rank`。在这个前提下，下面两对列很可能已经接近重复信息：

* `market_cap` 和 `log_mcap`
* `vol` 和 `log_vol`

所以更好的第一步是先做两组小探针：

* `raw-scale dedup`：保留 `market_cap`、`vol`，删 `log_mcap`、`log_vol`
* `log-scale dedup`：保留 `log_mcap`、`log_vol`，删 `market_cap`、`vol`

这比直接去删 `ret_120`、`pb`、`cfo_to_profit` 这种真正可能带独立信息的列更稳妥。

### 3.3 真要扩，只扩一小组正交特征

如果上面的小探针跑完后还想继续扩，当前更像样的方向不是继续加技术指标，而是补一小组杠杆 / 资产负债表风险特征，例如：

* `debt_to_assets`
* `debt_to_equity`
* `net_debt_to_assets`
* `operating_margin`

但这一步的前提是先确认本地 PIT 原料字段覆盖和缺失处理都够稳定。它不是当前第一优先级。

### 3.4 当前不建议做的特征动作

* 不把月频 baseline 那套 `RSI / MACD / SMA diff` 直接搬到季度主线
* 不因为 `tr_close` 在 challenger 上有效，就顺手把所有特征路线都重刷一轮
* 不重新打开 `features.missing.add_indicators`
* 不把 `valuation_age_days` 当成当前的重点研究列
* 暂时不把 `southbound` 直接升成研究特征；它当前更像高价值资产层 / 审计层，不是现成的标准化 feature merge 入口

## 4. 其他更值得调整的思路

按当前优先级，更值得继续推进的是：

1. 保留 `ranker h12_w16 + close + balanced execution` 作为主线候选。
2. 保留 `reg_zscore h12_w16 + tr_close + balanced execution` 作为第一优先 challenger。
3. 在 challenger 上继续做离线 `signal_direction` 规则回放，而不是继续大扩 `close / tr_close` 网格。
4. 如果后面要再往“更真实执行”推进，优先补更像样的 HK 直接费率 schedule；不要先跳到更重的 intraday 数据工程。

这里还有一个操作层提醒：

* 这组 local balanced execution 配置是为了研究近似更合理、同时尽量离线复现
* 它们仍然是 daily 级 execution approximation，不是 `5m` 逐 bar 成交仿真
* 如果本地 daily 资产不包含 `02800.HK`，benchmark/active 摘要可能不会完整生成；这时先看绝对收益、Sharpe、turnover 和 cost drag 更稳妥

## 5. 这次新增的 config

### 5.1 主线和 challenger

* [`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_exec_balanced_local.yml`](../../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_exec_balanced_local.yml)
  当前推荐的季度主线入口：`ranker + h12_w16 + close + balanced execution + local assets`
* [`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_regressor_zscore_h12_w16_tr_close_exec_balanced_local.yml`](../../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_regressor_zscore_h12_w16_tr_close_exec_balanced_local.yml)
  当前推荐的第一优先 challenger：`reg_zscore + h12_w16 + tr_close + balanced execution + local assets`

### 5.2 训练窗探针

* [`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w12_exec_balanced_local.yml`](../../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w12_exec_balanced_local.yml)
  用来回答“窗口是不是该比 `w16` 更短”
* [`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w20_exec_balanced_local.yml`](../../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w20_exec_balanced_local.yml)
  用来回答“窗口再拉长会不会重新吃到旧 regime 污染”

### 5.3 特征去重探针

* [`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_exec_balanced_local_rawscale_dedup.yml`](../../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_exec_balanced_local_rawscale_dedup.yml)
  保留 `market_cap` / `vol`，删 `log_mcap` / `log_vol`
* [`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_exec_balanced_local_logscale_dedup.yml`](../../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_exec_balanced_local_logscale_dedup.yml)
  保留 `log_mcap` / `log_vol`，删 `market_cap` / `vol`

### 5.4 数据加工 / 算法小探针

* [`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_exec_balanced_local_leverage.yml`](../../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_exec_balanced_local_leverage.yml)
  主线加一小组杠杆 / 资产负债表风险特征：`operating_margin`、`debt_to_assets`、`debt_to_equity`、`net_debt_to_assets`
* [`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_regressor_zscore_h12_w16_tr_close_exec_balanced_local_leverage.yml`](../../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_regressor_zscore_h12_w16_tr_close_exec_balanced_local_leverage.yml)
  challenger 加同一组杠杆 / 资产负债表风险特征，用来判断这组正交财务风险信息是不是更适合 `reg_zscore`
* [`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_regressor_zscore_h12_w16_tr_close_exec_balanced_local_fixed_pos.yml`](../../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_regressor_zscore_h12_w16_tr_close_exec_balanced_local_fixed_pos.yml)
  challenger 固定做多方向，用来判断最近这条副线是不是只是被 `cv_ic` 自动翻向掩盖了问题
* [`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_regressor_zscore_h12_w16_tr_close_exec_balanced_local_fixed_neg.yml`](../../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_regressor_zscore_h12_w16_tr_close_exec_balanced_local_fixed_neg.yml)
  challenger 固定做空方向，用来对照阶段性方向切换到底有多强

## 6. 建议怎么跑

如果只跑一轮最小复验，顺序建议是：

1. 先跑主线 config，确认 `ranker h12_w16 + balanced execution` 在当前本地资产下仍然站得住。
2. 再跑 challenger config，确认 `reg_zscore h12_w16 + tr_close + balanced execution` 是否继续保留最近 regime 优势。
3. 然后优先补 challenger 的两条固定方向探针：
   * `fixed_pos`
   * `fixed_neg`
4. 再补两条杠杆 / 资产负债表风险特征探针：
   * mainline leverage
   * challenger leverage
5. 最后再补更轻的结构探针：
   * `w12 / w20`
   * `raw-scale / log-scale dedup`

如果这些小探针都没有明显改善，就先别继续扩更多特征和窗口。

一句话收口：

* 当前更合理的动作不是“再大扩一轮搜索空间”
* 而是把主线、challenger、窗口上限和特征去重都收成少数几个点，在同一套 balanced execution 口径下继续比较
