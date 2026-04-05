# HK Monthly PIT No-Ret Tuning Follow-Up（2026-04-05）

本页解决什么：记录 `M-PIT + no_ret + bx20 / be10` 这条 monthly candidate 在第一轮结构调参和第二轮 XGB 小邻域调参里的有效增量、当前证据边界，以及为什么 `cv_ic` 还不足以让我们直接升默认。  
本页不解决什么：不替代 `hk-monthly-current-state-20260330.md` 作为 monthly 总入口，也不把这轮结果误写成“已经找到最终主线”。  
适合谁：已经接受 `no_ret + bx20 / be10` 是当前 monthly PIT candidate，但希望知道“调参到底有没有真增量、增量来自哪里、现在最该继续做什么”的人。  
读完你会得到什么：round 1 和 round 2 分别改出了什么、哪些结果值得保留、`cv_ic = NaN` 目前怎么读，以及下一步最值钱的确认型研究方向。  
相关页面：`docs/research/notes/hk-monthly-current-state-20260330.md`、`docs/research/notes/hk-monthly-pit-no-ret-follow-up-20260330.md`、`docs/research/notes/hk-monthly-time-window-design-20260330.md`、`docs/research/notes/hk-monthly-benchmark-ladder-and-attribution-20260405.md`、`docs/config.md`

页面性质：`research-note`  
状态：`active deep-dive`（当前 monthly 默认入口仍是 `hk-monthly-current-state-20260330.md`）  
最后核对时间：`2026-04-05`  
权威来源：本页列出的 `artifacts/sweeps/.../best_trial.json`、各 run 目录下 `summary.json` / `run.log` / `config.used.yml`  
冲突优先级：如果与具体 run 的 `summary.json` / `config.used.yml` 冲突，以 run 产物为准；如果与更晚样本冲突，以更晚样本为准

## 1. 先说结论

这轮调参值得单独落盘，原因有三条：

* round 1 已经证明：对这条 monthly candidate，先调训练结构是对的。`exp_decay(h=6) + rolling 48 dates` 比共享默认训练结构更值得保留。
* round 2 已经证明：在固定 `h6 + w48` 之后，XGB 小邻域调参还能再拿到一段真实增量，尤其是测试段 backtest 和换手改善明显。
* 但 round 2 的最强 balanced challenger 还不能直接升默认，因为它的 `cv_ic` 五折全 `NaN`，这意味着“方向判定 / 小折稳定性”这一层还缺证据。

一句话收口：

* **这轮调参已经找到了更强的 monthly challenger，但更像“应先做确认型 follow-up”，还不是“可以直接官宣新主线”。**

## 2. 这轮到底调了什么

### 2.1 固定不动的部分

这轮调参都基于同一条 monthly 主线：

* `M-PIT + no_ret + bx20 / be10`
* `data.end_date = 20260327`
* `eval.test_size = 0.5`
* `eval.final_oos.size = 24`
* 不改 feature recipe
* 不改 construction

也就是说：

* 这轮的目标不是“把整条 monthly 线重新设计一遍”
* 而是回答“在当前最像主线候选的 `no_ret` family 上，结构参数和 XGB 小邻域有没有稳定增量”

### 2.2 round 1 调的是训练结构

第一轮 sweep：

* `sample_weight_mode`
  * `date_equal`
  * `exp_decay(halflife = 6 / 12 / 18 / 24)`
* `train_window`
  * `full`
  * `rolling 48 / 60 / 72 dates`

round 1 的 winner：

* run：`artifacts/runs/hk_sel_m_tune_hk_m_pit_no_ret_r1_trial_006_20260405_211826_7f91fc0f/`
* 结构：`exp_decay(h=6) + rolling 48 dates`

### 2.3 round 2 调的是 XGB 小邻域

第二轮 sweep 固定 `h6 + w48`，只动：

* `learning_rate`
* `max_depth`
* `min_child_weight`
* `subsample`
* `colsample_bytree`
* `reg_alpha`
* `reg_lambda`

round 2 的 balanced winner：

* run：`artifacts/runs/hk_sel_m_tune_hk_m_pit_no_ret_r2_trial_009_20260405_214136_91057180/`
* 参数：
  * `learning_rate = 0.03`
  * `max_depth = 3`
  * `min_child_weight = 1`
  * `subsample = 1.0`
  * `colsample_bytree = 1.0`
  * `reg_alpha = 0.3`
  * `reg_lambda = 3.0`

round 2 的实现型 comparator：

* run：`artifacts/runs/hk_sel_m_tune_hk_m_pit_no_ret_r2_trial_042_20260405_215615_4a372718/`

## 3. 结果怎么读

### 3.1 round 1 给了什么

round 1 winner 的关键信号：

* `eval IC IR = 0.244`
* `cv_ic mean = 0.00003`
* `final OOS IC = 7.84%`
* 全样本 backtest `Sharpe = 0.18`
* `final OOS Sharpe = 1.34`
* `final OOS turnover = 31.3%`

这组结果说明：

* 这条 monthly candidate 的第一阶段增量，主要来自训练结构，不是来自树参数微调
* `exp_decay(h=6)` 和 `rolling 48` 是值得保留的结构 challenger

### 3.2 round 2 给了什么

和 round 1 winner 相比，round 2 balanced winner 的主要变化是：

| 指标 | round 1 winner | round 2 winner |
| --- | ---: | ---: |
| `eval IC IR` | `0.244` | `0.249` |
| 全样本 backtest `Sharpe` | `0.182` | `0.498` |
| 全样本 backtest `max_drawdown` | `-53.7%` | `-37.4%` |
| 全样本 backtest `avg_turnover` | `39.8%` | `21.1%` |
| `final OOS IC` | `7.84%` | `7.39%` |
| `final OOS ann` | `34.3%` | `36.6%` |
| `final OOS Sharpe` | `1.34` | `1.47` |
| `final OOS turnover` | `31.3%` | `23.5%` |

怎么读这张表：

* round 2 的增量不是幻觉
* 它最突出的改善不是把 `final OOS IC` 再大幅拉高，而是把实现层做得更顺了：
  * 全样本回测更稳
  * 回撤更浅
  * 换手更低
  * `final OOS Sharpe` 也更高

### 3.3 为什么不直接升默认

round 2 winner 的问题不在收益账面，而在验证边界：

* `summary.json` 里 `cv_ic.scores = [NaN, NaN, NaN, NaN, NaN]`
* `run.log` 里也明确写了 `CV IC (raw): mean=nan, std=nan`
* 当前 `signal_direction_mode = cv_ic`

这意味着：

* 这条 run 在“大考”里表现更好
* 但在“把训练段再切成 5 个小折做模拟考”时，方向判定这一步没拿到可用成绩

所以它更适合当前定位成：

* **provisional balanced challenger**

而不是：

* **已经确认的新默认主线**

## 4. `cv_ic = NaN` 当前怎么读

### 4.1 它不等于“模型无效”

`cv_ic = NaN` 更准确的意思是：

* 这一步交叉验证没有产出可判分的有效 IC

不是：

* 这个指标算出来很差

更白话一点：

* 不是“考了 20 分”
* 而是“这门考试这次没出成绩”

### 4.2 它也不等于“monthly CV 天生不行”

目前证据反而说明：

* round 1 的 `20 / 20` 个 trial，`cv_ic` 全都能正常算出来
* round 2 的 `48` 个 trial 里，只有 `11` 个出现 `cv_ic = NaN`

所以：

* 这不是 monthly 线天然就无法计算 `cv_ic`
* 更像是 round 2 某些参数组合把 CV 小折里的预测压得太“平”了

### 4.3 当前最强的参数线索

目前最值得记住的事实：

* round 2 里 `cv_ic = NaN` 的 `11` 个 trial，**全部**带有 `reg_alpha = 0.3`
* 但 `reg_alpha = 0.3` 的 `15` 个 trial 里，也有 `4` 个能正常算出有限 `cv_ic`

这说明：

* 目前最像的问题不是“monthly 设计错了”
* 更像是 `L1` 正则偏强，再叠加某些 `subsample / colsample / min_child_weight / reg_lambda` 组合后，让模型在 CV 小折里过于僵硬

也就是说：

* `reg_alpha = 0.3` 是当前最强嫌疑
* 但它更像触发条件之一，不像唯一根因

## 5. 当前更合理的分工

截至这轮调参，monthly 这条线更合理的角色划分应理解成：

* `M-PIT + no_ret + bx20 / be10`
  * 仍是 current candidate family
* round 1 winner（`h6 + w48`）
  * 结构 challenger
  * 说明训练结构值得保留
* round 2 `trial_009`
  * 当前最强 balanced challenger
  * 但仍需确认 `cv_ic NaN` 的解释
* round 2 `trial_042`
  * implementation comparator
  * 可以保留为更激进的实现参考

最不该做的事是：

* 直接宣布 round 2 已经找到新 monthly 默认

## 6. 下一步最值钱的研究方向

下一步不该继续大扫，更适合做一个很小的确认矩阵。

### 6.1 第一优先：围着 `trial_009` 做确认型 sweep

目标不是继续刷更高 Sharpe，而是回答：

* 能不能在保住 round 2 增量的同时，把 `cv_ic` 恢复成可判分

更合理的优先顺序：

* 先固定 `h6 + w48`
* 再围绕 `trial_009` 缩小邻域，只看：
  * `reg_alpha`
  * `reg_lambda`
  * `min_child_weight`
  * `subsample`
  * `colsample_bytree`

当前最值得先做的动作：

* 优先把 `reg_alpha` 从 `0.3` 往下收

### 6.2 第二优先：把 `trial_042` 保留成实现 comparator

这条线的价值不是替代主线，而是回答：

* 如果更看重 latest `final OOS` 账面实现，这个 family 大概能推到哪里

### 6.3 第三优先：做一次 `cv_ic NaN` 的定性 debug

最值钱的不是继续猜，而是直接把每个 CV fold 的这些信息打出来：

* 有效日期数
* 每日可用样本数
* 预测分数的离散度
* 每日唯一预测值个数

如果这一步确认：

* 小折里预测接近常数

那后续 monthly 调参就应明确加一条研究约束：

* **先排除会破坏 CV 判向的参数区域，再在剩余区域里优化收益实现。**

## 7. 当前状态一句话

截至 `2026-04-05`：

* **这轮调参已经把 `no_ret + bx20 / be10` 推出了一个更强的 monthly challenger；但在 `cv_ic NaN` 解释清楚之前，它更适合继续当候选，而不是直接取代当前主线入口。**
