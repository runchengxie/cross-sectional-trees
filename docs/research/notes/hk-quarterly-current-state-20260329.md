# HK Quarterly 现行口径与研究重置（2026-03-29）

本页解决什么：把当前 HK quarterly 这条研究线真正还值得继续用的结论、配置和下一步动作收成一页，并明确哪些旧笔记已经更适合当 provenance 而不是当前决策入口。  
本页不解决什么：不替代单次 run 的 `summary.json` / `config.used.yml`，也不把历史中间实验全部重写一遍。  
适合谁：已经看过几轮 quarterly notes，开始怀疑“旧笔记太多、口径太杂”，想知道现在到底该信什么的人。  
读完你会得到什么：一套更干净的现行口径、一份“哪些信息保留、哪些降级”的清单，以及当前真正该继续推进的研究顺序。  
相关页面：`docs/playbooks/hk-selected.md`、`docs/research/notes/hk-quarterly-holdings-analysis-20260329.md`、`docs/research/notes/hk-quarterly-construction-grid-20260329.md`、`docs/research/notes/hk-quarterly-next-step-configs-20260329.md`、`docs/research/notes/hk-quarterly-oos-evidence-20260329.md`、`docs/concepts/model-landscape.md`

页面性质：`current-state`  
最后核对时间：`2026-03-29`  
权威来源：截至 `2026-03-29` 的 tracked config、已落地 balanced execution run、当前 playbook 收口、以及本页引用的历史研究笔记  
冲突优先级：如果与具体 run 的 `config.used.yml` / `summary.json` 冲突，以 run 产物为准；如果与更新后的 playbook 或 preset 冲突，以更晚的 playbook / preset 为准

## 1. 先记住这些

* 旧 notes 不该再被当成平行的“当前真相”入口；它们更适合当 provenance。
* 当前 quarterly 线真正还值得继续推进的主线，仍然是 `ranker h12_w16 + close`。
* 当前最值得继续盯的 challenger，仍然是 `reg_zscore h12_w16 + tr_close`。
* `tr_close` 不是所有路线都该默认打开的真理；它更适合当前 regressor challenger，而不是直接替掉 ranker 主线默认口径。
* balanced execution 比早期 flat cost 更合理；所以更早那些“简陋成本口径下很亮”的结果，现在只能当背景，不该直接拿来定现行主线。
* 当前 quarterly 执行口径默认按 `portfolio_value=1_000_000` 的小资金研究来理解；在这个量级下，`base_bps` 和 `min_amount` 通常比 participation 冲击更主导结果。
* 最近一段 `Final OOS` 很亮，不等于模型已经验证通过；这段样本已经被消费过。
* 当前最大的矛盾仍然是 regime shift、方向切换和前瞻证据不足，而不是“模型名字还不够多”。
* `elasticnet` 目前不值得回到 quarterly 主线，保留成低优先级稀疏线性探针就够了。
* 特征现在不该继续扩成 zoo；先做小幅去重和一小组经营利润/盈利质量特征更合理，重型资产负债表因子放后。
* 当前最像样的组合结构 probe，不是“主线直接加约束”，而是 `raw-scale dedup + groupcap3` 这条 construction challenger。
* fixed-signal construction grid 已经跑到第二轮；它能说明 construction 值得做，也能给出 shortlist，但独立 full run 没有确认 `bx = 2`、`be = 1` 或 `top_k = 25` 能优于 `raw-scale dedup + groupcap3` 本身。
* 如果要保留一条纯 PIT 基本面 sidecar，当前更像样的是 `xgb_regressor + operating_margin`，而不是纯基本面整条线整体升级。
* 如果要开新的独立路线，纯 PIT 基本面值得做，但更适合当 benchmark / challenger 线，不适合直接替掉当前 hybrid 主线。
* 这条线仍值得做，但目标应该是“低频、可复现、逐步走向 paper/shadow/canary 的 HK 研究线”，不是现在就把它包装成已经足够重仓上线的单模型。

## 2. 为什么要重置阅读入口

截至现在，`docs/research/notes/` 里保留的是几轮连续 follow-up：

* 旧 overlay 基线失效与 anti-drift 修正
* `target transform` / `signal_direction` follow-up
* `close / tr_close` A/B
* balanced execution 下的“线索 vs 证据”边界
* 下一阶段配置建议

这些页面本身没有错，但它们的角色已经变了：

* 早期页面更像中间研究日志
* 后期页面才开始纳入 balanced execution、`tr_close` 边界和“最近 OOS 不等于证据”的约束
* 如果现在继续把它们当成并列入口，很容易把不同口径下的亮点混在一起看

所以更合理的做法不是删除历史，而是：

1. 保留旧 notes 作为 provenance
2. 新增一页现行总收口
3. 以后先读本页，再按需要回到旧页面追溯证据链

## 3. 旧笔记里什么还值得保留

下面这些结论，今天仍然值得保留：

### 3.1 真实问题是漂移，不是单纯模型输赢

旧 quarterly overlay 基线失效，主要矛盾更像 `regime shift / concept drift`。  
这一点没有过时，反而是当前所有结论的起点。

### 3.2 `h12_w16` 仍是当前最像样的 anti-drift 中心点

窗口再拉长会重新吃到旧 regime 污染；窗口太短又更容易不稳。  
所以 `rolling train_window.size = 16` 仍然是当前更合理的中心点。

### 3.3 `reg_zscore` 是正式 challenger，不是偶然亮点

相对化 target 这条路已经不只是一次局部实验，而是值得正式保留的副线。

### 3.4 `tr_close` 该按路线使用，不该一刀切

它对 ranker 主线证据不足，对 `reg_zscore` challenger 是净正向加成。  
这条判断现在仍然成立。

### 3.5 最近 OOS 很亮，不等于证据

这条边界在 balanced execution run 之后更应该被钉住，而不是淡化。

## 4. 旧笔记里什么该降级

下面这些内容，今天更适合降级成“背景”：

### 4.1 只在 flat `transaction_cost_bps` 下显得很亮的局部结果

这些结果不是完全没用，但在 balanced execution 已经落地之后，它们不该继续承担“现行主线证据”的角色。

### 4.2 只看最近 `Final OOS`、不看完整测试段和前面 walk-forward 的结论

现在已经明确知道：

* balanced execution 下的两条候选完整测试段仍然为负
* 前 `6` 个 walk-forward 测试窗都是负收益

所以任何只强调最近 OOS 亮点、却弱化这两件事的表述，都应该降级。

### 4.3 把 `tr_close` 当成整个 quarterly overlay 单元默认真理的冲动

分红影响当然重要，但当前证据并不支持把 ranker 主线直接切到 `tr_close`。

### 4.4 围着已经看过的 OOS 再做一轮大网格

这类动作继续做下去，边际信息会越来越差，后验筛选风险却会越来越高。

## 5. 当前真正有效的现行口径

截至 `2026-03-29`，当前更该当成“现行研究口径”的是：

### 5.1 主线

* `ranker h12_w16 + close + balanced execution`

当前定位：

* 仍然是更像主线的候选
* 不是因为它已经被完全验证，而是因为它在现有证据里仍然最稳

### 5.2 第一优先 challenger

* `reg_zscore h12_w16 + tr_close + balanced execution`

当前定位：

* 仍然是最值得跟踪的 challenger
* 但还没有强到可以替掉主线

### 5.3 训练窗与测试边界

* 训练窗继续以 rebalance dates 思考
* `w16` 继续当中心点
* `w12 / w20` 只当邻域探针
* 当前最近 `8` 个 OOS 信号点已经被用来判断候选，不再是假装没看过的 holdout

### 5.4 特征动作

* 先不大扩 feature zoo
* `market_cap / log_mcap`、`vol / log_vol` 的去重探针已经补过；`raw-scale dedup` 值得保留成低优先级结构 challenger，`log-scale dedup` 可以降级
* 如果只保留一条组合结构 follow-up，当前更值得追的是 `raw-scale dedup + groupcap3`，而不是“主线直接加 group cap”
* 如果还要加，优先补 `operating_profit / growth_operating_profit / operating_margin` 这一小组经营利润特征，再看更重的资产负债表因子

### 5.5 执行口径

* 当前 quarterly 本地研究默认沿用 `balanced execution + portfolio_value=1_000_000`。
* 在 `top_k=20` 的设定下，这更接近“小资金、低 participation”的研究口径，而不是容量边界测试。
* 所以接下来的默认回测，优先继续沿用这套 `1M` 资金假设；只有在显式做容量 / 交易冲击敏感性测试时，才单独改 `portfolio_value` 或更激进地改 execution 参数。
* 如果要先做贴近你这类资金规模的微调，优先看 `min_amount` 和直接费率，不要先把 `impact_bps` 当成主要矛盾。
* 更细的 execution 解释和 `1m` 口径说明，统一参考 `docs/playbooks/hk-intraday-assets.md`，本页不重复展开公式。

## 6. 当前不建议做什么

* 不回头把 `elasticnet` 当成 quarterly 主线修复方案
* 不因为 `tr_close` 在 challenger 上有效，就重刷整个 quarterly 研究线
* 不继续围着已消费的最近 OOS 大扫窗口、价格口径和模型组合
* 不在统计证据还不硬的时候，把这条线包装成“已可重仓上线的唯一主信号”

## 7. 当前最该继续推进的顺序

1. 冻结主线、结构 challenger 和纯基本面 sidecar 的规格，不再继续大扩模型网格。
2. 先看 [`hk-quarterly-holdings-analysis-20260329.md`](./hk-quarterly-holdings-analysis-20260329.md)，把 `raw-scale dedup + groupcap3` 到底是在修组合结构还是改信号故事看清楚。
3. 再看 [`hk-quarterly-construction-grid-20260329.md`](./hk-quarterly-construction-grid-20260329.md)，接受“固定信号后继续做组合构造”的顺序。
4. 固定 `raw-scale dedup + groupcap3` 信号；当前两轮 grid 已经说明 construction 值得做，但独立 full run 没有确认 `bx = 2`、`be = 1`、`top_k = 25` 能升级默认，所以这轮先不要再继续围着 construction 小参数打转。
5. 并行维护纯 PIT 基本面 sidecar 线，但只把它当 benchmark / challenger；当前更像样的是 `xgb_regressor + operating_margin`，不是把纯基本面整体升成主线。
6. 如果还要做特征扩充，先补一小组经营利润特征；资产负债表重型因子放到更后面。
7. 等新的前瞻样本，再决定谁配得上升级。

如果按 `2026-03-29` 这轮已完成的探针继续往下走，下一步更值得做的是：

1. 先读 [`hk-quarterly-holdings-analysis-20260329.md`](./hk-quarterly-holdings-analysis-20260329.md)，把结构 challenger 的组合故事看清楚。
2. 再读 [`hk-quarterly-construction-grid-20260329.md`](./hk-quarterly-construction-grid-20260329.md)，接受“固定信号后继续做组合构造”的研究顺序。
3. 然后沿着 `raw-scale dedup + groupcap3` 这条结构 challenger，把 `construction-grid` 理解成 shortlist 证据，而不是升级证据；现阶段先冻结它，不再继续扫 `bx2_be1/top_k25` 这类小参数。
4. 纯基本面 sidecar 继续保留，而且当前更值得保留的是 `xgb_regressor + operating_margin`。
5. 这轮如果不再新增研究问题，就先停手，等下一段没看过的新季度样本。

## 8. 现在旧 notes 应该怎么读

建议按下面的角色理解它们：

| 页面 | 现在更像什么 | 还值不值得看 |
| --- | --- | --- |
| `hk-quarterly-pit-regime-shift-202603.md` | 这条线为什么要 anti-drift 的历史起点 | 值得，作为 provenance |
| `hk-h12-w16-target-transform-review-20260324.md` | `zscore target` 从哪里冒出来的中间实验页 | 值得，但不该当当前入口 |
| `hk-quarterly-target-design-and-direction-20260324.md` | `ranker` vs `reg_zscore` 主副线关系的第一次总结 | 值得，作为副线由来说明 |
| `hk-quarterly-price-col-ab-20260325.md` | `close / tr_close` 路线边界的专题页 | 值得，但只按路线使用 |
| `hk-quarterly-oos-evidence-20260329.md` | “线索 vs 证据”边界页 | 仍然直接相关 |
| `hk-quarterly-construction-grid-20260329.md` | fixed-signal construction sweep 的最新结果页 | 仍然直接相关 |
| `hk-quarterly-next-step-configs-20260329.md` | 当前最可执行的 config 清单 | 仍然直接相关 |

一句话说：

* `construction-grid`、`oos-evidence` 和 `next-step-configs` 仍然是当前直接相关页
* 其余页面主要保留 provenance 价值

## 9. 当前推荐阅读顺序

如果你今天才重新进入 quarterly 研究，建议按下面顺序读：

1. 本页：先把现行口径和边界看对。
2. [`hk-quarterly-holdings-analysis-20260329.md`](./hk-quarterly-holdings-analysis-20260329.md)：看现在为什么更该先做组合层解释，而不是继续盲扫 config。
3. [`hk-quarterly-construction-grid-20260329.md`](./hk-quarterly-construction-grid-20260329.md)：看清当前为什么优先做组合构造，而不是继续加新因子。
4. [`hk-quarterly-next-step-configs-20260329.md`](./hk-quarterly-next-step-configs-20260329.md)：看下一步具体跑什么。
5. [`hk-quarterly-oos-evidence-20260329.md`](./hk-quarterly-oos-evidence-20260329.md)：看为什么最近 OOS 亮点不能直接当证据。
6. 需要追溯时，再回去翻更早的专题页。

## 10. 一句话结论

当前更合理的做法不是“继续把旧 notes 当并列真相”，也不是“把历史全删掉”；而是把旧页面降级成 provenance，把主线、challenger、balanced execution、`tr_close` 边界和证据标准统一收口到这一页，再从这里重新出发。
