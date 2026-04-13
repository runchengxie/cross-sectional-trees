# HK Quarterly PIT Provider Coverage Caveat（2026-04-11）

> 状态提示：本页属于 implementation caveat，用于解释 quarterly PIT freshness warning 的成因，以及为什么仓库里新增了 `provider_dense` 变体。当前默认研究入口仍是 [`hk-quarterly-current-state-20260329.md`](./hk-quarterly-current-state-20260329.md)。

本页解决什么：说明这轮 quarterly PIT freshness warning 为什么更像 provider coverage 问题，而不是本地 build / dedup bug，并给出 `provider_dense` 变体的正确定位。  
本页不解决什么：不替代 `docs/concepts/pit-coverage.md` 的通用解读，也不把 `provider_dense` 写成新的 quarterly 默认基线。  
适合谁：需要处理 `inspect-hk-pit-coverage --include-health` 告警、或想理解 `provider_dense` 变体为什么存在的人。  
读完你会得到什么：warning 的更准确解释、受影响字段的共性、`provider_dense` 的定位，以及什么时候才值得切到这份变体。  
相关页面：`docs/research/notes/hk-quarterly-current-state-20260329.md`、`docs/concepts/pit-coverage.md`、`docs/playbooks/hk-data-assets.md`、`docs/rqdata/hk-health-checks.md`

页面性质：`research-note`  
状态：`implementation caveat`，这页只保留 quarterly PIT coverage / freshness warning 的背景和变体定位，不作为默认研究入口  
最后核对时间：`2026-04-11`  
权威来源：`configs/presets/hk_quarterly_pit_hybrid.yml`、`src/csml/data_tools/rqdata_assets/build.py`、`src/csml/data_tools/rqdata_assets/coverage.py`、本地 `artifacts/reports/hk_pit_health_20260409.json`、本地 raw PIT 资产抽样  
冲突优先级：如果与代码、health 报告或更晚的资产检查结果冲突，以更晚代码和检查结果为准；如果与具体 run 的 `summary.json` / `config.used.yml` 冲突，以 run 产物为准

## 1. 先说结论

这轮 `hk_selected__quarterly_pit_core_hybrid` 的 PIT freshness warning，主因不是本地构建代码把值算坏了，而是 provider PIT 字段覆盖不稳定。

更准确地说：

1. research universe 已先按 `--max-latest-report-age-days 365` 过滤掉一批“整只股票最新 PIT 披露极老”的 symbol-date。
2. 剩余 warning 不是因为没有最新 PIT 行，而是因为最新 PIT 行存在，但部分字段在最新行里本身就是空值。
3. health 检查是按“该字段最近一次非空值距目标日多久”报 stale，因此会把这类 provider 稀疏字段识别为 `feature_stale_gt_365d_asof_target_date`。

## 2. 为什么判断不是 build / dedup bug

抽样核对 raw PIT 资产最新 `info_date` 的原始行，现象是一致的：

* `00005.HK` 最新 raw 行在 `2026-02-25`，`basic_earnings_per_share` 有值，但 `revenue`、`operating_revenue`、`net_profit`、`cash_flow_from_operating_activities` 都是空值。
* `02359.HK` 最新 raw 行在 `2025-10-26`，只有 `basic_earnings_per_share` 有值，`revenue`、`net_profit`、`cash_flow_from_operating_activities` 为空。
* `03968.HK` 最新 raw 行在 `2025-10-29`，`operating_revenue` 有值，但 `net_profit`、`cash_flow_from_operating_activities` 为空。
* `00762.HK` 最新 raw 行在 `2025-10-22`，连 `basic_earnings_per_share` 也是空值。

这说明：

* `build-hk-pit-fundamentals` 没有把原本存在的新值错误地变成旧值。
* `keep-last` 去重不是主因；至少这些样本在最新 `info_date` 的 raw 行本体就已经缺字段。
* 问题更接近 provider 对部分金融类 / 特殊行业股票只稳定提供 EPS 或部分经营口径，而不稳定提供营收、净利润和经营现金流。

## 3. 当前最容易触发 stale warning 的字段

在 `2026-04-09` 的 PIT health 里，仍然触发 `>365d` warning 的字段主要是：

* `sales`
* `growth_sales`
* `basic_earnings_per_share`
* `growth_basic_earnings_per_share`
* `net_profit`
* `growth_net_profit`
* `cash_flow_from_operating_activities`
* `growth_cash_flow_from_operating_activities`
* `profit_margin`
* `cfo_margin`
* `cfo_to_profit`

它们的共同点是：都高度依赖 provider 在最新 PIT 行里持续提供营收 / 利润 / 现金流三类值；一旦 provider 在最新期只更新 EPS 或部分口径，staleness 就会迅速累积。

## 4. `provider_dense` 变体应该怎么理解

已新增独立变体：`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_dense.yml`

它的定位是：

* 不改动现有 `hk_selected__quarterly_pit_core_hybrid` benchmark。
* 保留同一套 quarterly selected research unit 和 price / liquidity 慢特征。
* 只把 provider 稀疏的 income-statement / growth 组合替换成相对更稳的：
  * `total_assets`
  * `total_liabilities`
  * `leverage`
  * `days_since_report`

它不是：

* 新的 quarterly 默认 baseline
* 对 build bug 的修复补丁
* 对所有 freshness warning 的“一键消失”按钮

## 5. 什么时候才值得切到这份变体

更适合切到 `provider_dense` 的场景：

* 你在做 coverage-sensitive 的 quarterly probe，希望先验证“coverage 更稳的 PIT 子集”会不会改变研究判断。
* 你要用 `--feature-age-config` 和 `--max-selected-feature-age-days` 派生 config-aware research universe。
* 你明确想把 freshness warning 从“默认 caveat”提升成“需要控制的研究变量”。

不适合切到 `provider_dense` 的场景：

* 只是想把 warning 从报告里抹掉。
* 还没有先把默认 hybrid baseline 跑清楚。
* 想把它直接当成新的 quarterly benchmark。

## 6. 配套命令现在落在哪里

`build-hk-pit-fundamentals` 现已支持 `--feature-age-config` + `--max-selected-feature-age-days`，可以按这份变体派生 config-aware research universe；对应示例已沉淀到：

* `docs/playbooks/hk-data-assets.md`
* `docs/rqdata/hk-health-checks.md`
* `docs/cli.md`

最常见的用途是：

* 剔除类似 `09988.HK` 这种“最新 PIT 行存在，但 selected feature 最近一次非空值已超过 365 天”的 symbol-date。

## 7. 一句话结论

这页最该保留的判断只有一句：当前 quarterly PIT freshness warning 更像 provider sparse 字段带来的 coverage caveat，而不是 build / dedup bug；`provider_dense` 变体是覆盖率敏感场景下的辅助入口，不是新的默认 benchmark。
