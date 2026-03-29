# HK Quarterly 持仓与归因分析（2026-03-29）

本页解决什么：把当前三条最相关季度 run 的持仓稳定性、组合差异和最近 OOS 收益集中度收成一页，回答“现在更该继续调 config，还是先看持仓机制”。  
本页不解决什么：不重新评价模型显著性，也不把最近 OOS 包装成新证据。  
适合谁：已经看过 `current-state` 和 `next-step-configs`，开始怀疑“是不是再扫 config 的边际已经不高”的读者。  
读完你会得到什么：一组更像组合层解释的结论，知道 `raw-scale dedup` 到底改了什么，也知道为什么后面该把注意力从大网格调参转向持仓分析。  
相关页面：`docs/research/notes/hk-quarterly-current-state-20260329.md`、`docs/research/notes/hk-quarterly-next-step-configs-20260329.md`、`docs/research/notes/hk-quarterly-oos-evidence-20260329.md`

页面性质：`research-note`  
最后核对时间：`2026-03-29`  
权威来源：三条 tracked config 对应 run 的 `summary.json`、`positions_by_rebalance*.csv`、本地 daily 资产、industry labels 和 provider valuation as-of 文件  
冲突优先级：如果与具体 run 产物冲突，以 run 目录下的 `summary.json` / `config.used.yml` 为准；如果与更晚的前瞻样本冲突，以更晚样本为准

## 1. 分析对象

这次只看三条最相关的 run：

* 主线：`ranker h12_w16 + close + balanced execution`
* 第一 challenger：`reg_zscore h12_w16 + tr_close + balanced execution`
* 结构 challenger：`ranker h12_w16 + raw-scale dedup + balanced execution`

对应 run 目录分别是：

* `artifacts/runs/hk_sel_q_g4_fixed_pit_overlay_xgb_rank_antidrift_h12_w16_exec_balanced_local_20260328_235502_6e283435/`
* `artifacts/runs/hk_sel_q_g4_fixed_pit_overlay_xgb_reg_zscore_h12_w16_tr_close_exec_balanced_local_20260328_235640_38b3eba8/`
* `artifacts/runs/hk_sel_q_g4_fixed_pit_overlay_xgb_rank_antidrift_h12_w16_exec_balanced_local_rawscale_dedup_20260329_163648_03264be7/`

## 2. 方法边界

这次不是只看 `summary.json`。

额外做了三层组合侧还原：

1. 用 `positions_by_rebalance.csv` 和 `positions_by_rebalance_oos.csv` 看每期入选名字、持仓持续性和 run 间重合度。
2. 用本地 daily 资产的 `entry_date -> next_entry_date` `open` 复原个股 gross return，近似看最近 OOS 的个股贡献集中度。
3. 用 provider valuation as-of 和本地 daily `adv20` 代理看组合层的 `market_cap / liquidity` 变化。

所以这里的个股贡献是：

* 组合层、gross、近似 realized contribution
* 不是逐笔净收益归因
* 也不是严格 broker 级 TCA

## 3. 先记住 6 句

* 现在继续大扫 config 的边际已经明显下降，下一步更该看持仓机制。
* `raw-scale dedup` 不是 cosmetic 改动；它确实显著改了组合结构。
* 它降低换手，主要来自测试段持仓更稳定，而不是简单“只买更大市值股票”。
* `reg_zscore + tr_close` 最近 OOS 的亮点更集中，组合层集中度明显高于主线。
* 主线最近 OOS 的收益来源更分散，虽然也不是特别宽。
* 如果后面还想继续调模型，更应该先用持仓分析提出假设，再写新 config，而不是盲扫。

## 4. 持仓稳定性

测试段里，三条 run 的平均持仓数都在 `17-18` 个左右，但组合“自我稳定性”差别不小：

* 主线 `rank_w16`：测试段相邻调仓平均保留率约 `0.52`
* `reg_tr_w16`：测试段约 `0.62`
* `raw-scale dedup`：测试段约 `0.69`

同时，测试段用到的 unique symbol 数也明显收缩：

* 主线：`79`
* `reg_zscore challenger`：`71`
* `raw-scale dedup`：`59`

这说明 `raw-scale dedup` 降换手，不主要是因为某几期碰巧少动，而是因为整段测试里更少换名字、更少反复进出。

最近 OOS 里，这种优势仍在，但没有测试段那么明显：

* 主线 OOS 相邻调仓平均保留率约 `0.35`
* `reg_zscore challenger` OOS 约 `0.52`
* `raw-scale dedup` OOS 约 `0.38`

所以 `raw-scale dedup` 的“稳”主要是测试段特征，不是最近 OOS 里突然变得极稳。

## 5. 这三条 run 到底有多像

主线和 `raw-scale dedup` 的平均重合度并不高：

* 测试段 `overlap_min` 约 `0.65`
* 最近 OOS 只剩约 `0.48`

主线和 `reg_zscore challenger` 也不是高度同构：

* 测试段 `overlap_min` 约 `0.70`
* 最近 OOS 约 `0.55`

所以这三条并不是“同一组名字换个参数名”；它们确实在最近阶段选出了不同的组合。

## 6. `raw-scale dedup` 真正改了什么

### 6.1 不是简单更偏 mega-cap

如果只看 full sample 的持仓中位数：

* 主线中位 `market_cap` 约 `158.7B`
* `raw-scale dedup` 约 `122.3B`

但它的中位 `adv20_amount` 反而更高：

* 主线约 `373.7M`
* `raw-scale dedup` 约 `430.1M`

再看最近 OOS 里两边互相替换掉的名字：

* `raw_only` 这一组的中位 `market_cap` 约 `66.1B`
* `base_only` 这一组约 `133.1B`
* 但 `raw_only` 的中位 `adv20_amount` 约 `632.1M`
* `base_only` 只有约 `397.0M`

这更像是：

* `raw-scale dedup` 不是单纯更偏大盘
* 它更像在去掉 `log_mcap / log_vol` 后，换成了一批“市值未必更大，但交易更顺手”的名字

### 6.2 最近 OOS 的替换在收益上是净正的

最近 OOS 里：

* 被 `raw-scale dedup` 换进来的 `raw_only` 名字，平均 realized return 约 `6.35%`
* 被主线保留、但在 dedup 里被换掉的 `base_only` 名字，平均 realized return 约 `5.13%`

这个差距不算巨大，但方向上是对的。  
也就是说，`raw-scale dedup` 不是靠纯防守来压换手，它在最近 OOS 里确实也换进了一批略更有效的名字。

## 7. 最近 OOS 的收益是不是少数名字拉出来的

是，而且三条的集中度不一样。

按最近 OOS 的 gross realized contribution 看：

* 主线前 `5` 名贡献约占总贡献的 `44.7%`
* `raw-scale dedup` 前 `5` 名约占 `57.4%`
* `reg_zscore challenger` 前 `5` 名约占 `72.3%`

这说明：

* 主线最近这段收益虽然不算特别分散，但还没有高度集中到几只股票上
* `reg_zscore + tr_close` 的最近亮点更依赖少数名字
* `raw-scale dedup` 介于两者之间

## 8. 最近 OOS 各自更像押中了什么

### 8.1 主线

主线最近 OOS 的主要贡献更偏：

* 银行
* 石油石化
* 煤炭
* 通信

更像传统高股息 / 价值 / 大盘方向里相对分散的组合贡献。

### 8.2 `reg_zscore + tr_close`

这条 challenger 最近 OOS 的亮点更集中在：

* `01810.HK`
* `01919.HK`
* `02388.HK`

行业上更偏：

* 银行
* 电子
* 医药
* 石油石化

它不是完全押单一主题，但明显更依赖头部个股。

### 8.3 `raw-scale dedup`

这条结构 challenger 最近 OOS 更偏：

* 汽车
* 非银行金融
* 电子
* 交通运输

头部贡献名字里，`09868.HK`、`01919.HK`、`01810.HK` 比较突出。

这说明它不是简单把主线做得“更慢”，而是把组合风格往另一侧挪了一步。

## 9. 对下一步研究意味着什么

### 9.1 什么不该继续做

* 不该继续在已经看过的这段 OOS 上盲扫小参数
* 不该把 `raw-scale dedup` 因为“更省换手”就直接升成新默认
* 不该把 `reg_zscore challenger` 最近这段亮点直接当成更强证据

### 9.2 什么更值得做

现在更合理的动作是：

1. 保留主线、`reg_zscore challenger` 和 `raw-scale dedup` 这三条候选。
2. 继续做组合层解释，而不是先继续扩 model zoo。
3. 如果要写新 config，先让它回答组合层问题，例如：
   * 行业集中是不是太高
   * 头部名字贡献是不是太集中
   * `raw-scale dedup` 的低换手是不是来自更好的流动性筛选
4. 如果暂时没有新的、明确的组合层假设，就先停手，等新的前瞻样本。

### 9.3 `groupcap3` follow-up 结果

`2026-03-29` 这轮最小组合约束 probe 已经补完，两条 config 分别是：

* [`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_exec_balanced_local_groupcap3.yml`](../../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_exec_balanced_local_groupcap3.yml)
* [`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_exec_balanced_local_rawscale_dedup_groupcap3.yml`](../../../configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker_antidrift_h12_w16_exec_balanced_local_rawscale_dedup_groupcap3.yml)

这里的 `groupcap3` 不是装饰项。按 entry-date 行业标签回接后：

* 主线 `main_base` 的每期第一行业最大持仓数，平均约 `4.17`，最高 `7`
* 加了 `groupcap3` 后，平均降到约 `2.83`，最高 `3`
* `raw-scale dedup` 基线约 `3.75`
* `raw-scale dedup + groupcap3` 后约 `2.92`，最高也被压到 `3`

也就是说，这条约束确实绑住了组合，而不是名义上写在 config 里。

结果上，两条 `groupcap3` 的表现并不一样：

* 主线 `groupcap3` 把完整测试段 `total_return` 从 `-19.65%` 拉到 `-16.79%`，但最近 `Final OOS` 从 `77.65% / Sharpe 2.04` 降到 `73.02% / Sharpe 1.89`
* `raw-scale dedup + groupcap3` 则把完整测试段 `total_return` 从 `-19.10%` 拉到 `-13.38%`，同时最近 `Final OOS` 也从 `81.64% / Sharpe 1.80` 提到 `84.72% / Sharpe 1.89`

但要继续记住边界：

* 两条 `groupcap3` 的 `walk_forward` 仍然是 `0/6` 个正窗口
* 所以它们还不构成“策略已经验证通过”的新证据

当前更合理的解释是：

* `groupcap3` 本身值得保留成组合结构工具
* 如果只保留一条 construction probe，`raw-scale dedup + groupcap3` 比“主线直接加 group cap”更有继续追踪的价值
* 但这条线仍然只是结构 challenger，不足以替掉现有主线

### 9.4 `raw-scale dedup + groupcap3` 到底又多做了什么

如果把它和不带 `groupcap3` 的 `raw-scale dedup` 直接对比，结论会更清楚：

* 它不是另一条“完全不同”的策略，full sample 平均持仓重合度约 `0.93`
* 最近 OOS `7` 个 entry-date 里，只有第一期 `2024-01-02` 真正换了一只名字：`02015.HK -> 00836.HK`
* 所以它最近 OOS 的改进，不是来自大换仓，也不是来自重写头部赚钱名字

结构上它做的事情更像：

* 把最近 OOS 的第一行业最大持仓数从约 `2.86` 进一步压到 `2.71`
* 把最近 OOS 的平均行业广度从约 `10.86` 略抬到 `11.00`
* full sample 的中位 `adv20_amount` 也从约 `361.8M` 小幅抬到 `374.9M`

但它没有明显改变最近 OOS 的头部贡献结构：

* 在同一套近似 realized contribution 口径下，前 `5` 名贡献占比只小幅缓和，没有出现“集中度被重写”的变化
* 头部贡献名字基本还是 `09868.HK`、`01919.HK`、`01810.HK`、`09988.HK`、`02628.HK`

所以更贴切的理解是：

* `groupcap3` 在这条 structural challenger 上，主要做的是组合修形
* 它让行业分布更平、流动性口径略更顺手
* 但它没有把最近这段收益来源从少数核心名字改写成另一套故事

## 10. 一句话结论

当前 quarterly 线最该做的已经不是“继续调很多 config”，而是先把主线、challenger 和 `raw-scale dedup` 的组合差异看明白：  
`raw-scale dedup` 的价值主要在于更低换手和更稳定的测试段持仓，不是单纯更偏 mega-cap；`reg_zscore + tr_close` 的最近亮点则更集中、更像少数名字驱动。  
所以后面要么继续做组合结构与约束分析，要么等新样本，不要再回到盲扫网格。
