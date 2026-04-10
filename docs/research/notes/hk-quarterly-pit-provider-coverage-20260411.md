# HK Quarterly PIT Provider Coverage Note 2026-04-11

权威来源：

* `configs/presets/hk_quarterly_pit_hybrid.yml`
* `src/csml/data_tools/rqdata_assets/build.py`
* `src/csml/data_tools/rqdata_assets/coverage.py`
* 本地 `artifacts/reports/hk_pit_health_20260409.json`
* 本地 `artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest/data/*.parquet`

## 结论

这轮 `hk_selected__quarterly_pit_core_hybrid` 的 PIT freshness warning，主因不是本地构建代码把值算坏了，而是 provider PIT 字段覆盖不稳定。

更准确地说：

1. research universe 已经先按 `--max-latest-report-age-days 365` 过滤掉了一批“整只股票 PIT 披露极老”的 symbol-date。
2. 剩余 warning 不是因为没有最新 PIT 行，而是因为最新 PIT 行存在，但某些字段在最新行里本身就是空值。
3. health 检查是按“该字段最近一次非空值距目标日多久”报 stale，因此会把这类 provider 稀疏字段识别为 `feature_stale_gt_365d_asof_target_date`。

## 为什么判断不是 build / dedup bug

抽样核对了 raw PIT 资产最新 `info_date` 的原始行，现象一致：

* `00005.HK` 最新 raw 行在 `2026-02-25`，`basic_earnings_per_share` 有值，但 `revenue`、`operating_revenue`、`net_profit`、`cash_flow_from_operating_activities` 都是空值。
* `02359.HK` 最新 raw 行在 `2025-10-26`，只有 `basic_earnings_per_share` 有值，`revenue`、`net_profit`、`cash_flow_from_operating_activities` 为空。
* `03968.HK` 最新 raw 行在 `2025-10-29`，`operating_revenue` 有值，但 `net_profit`、`cash_flow_from_operating_activities` 为空。
* `00762.HK` 最新 raw 行在 `2025-10-22`，连 `basic_earnings_per_share` 也是空值。

这说明：

* `build-hk-pit-fundamentals` 没有把原本存在的新值错误地变成旧值。
* `keep-last` 去重也不是主因；至少这些样本在最新 `info_date` 的 raw 行本体就已经缺字段。
* 问题更接近 provider 对部分金融类 / 特殊行业股票只稳定提供 EPS 或部分经营口径，而不稳定提供营收、净利润、经营现金流。

## 当前最明显受影响的字段

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

这组字段的共同点是：高度依赖 provider 在最新 PIT 行里持续提供营收 / 利润 / 现金流三类值；一旦 provider 在最新期只更新 EPS 或部分口径，staleness 会迅速累积。

## 候选字段密度观察

基于当前 `hk_selected_pit_research_by_date.csv` 在 `2026-04-09` 的 symbol 集合做了字段密度扫描，结论是：

* 当前这组 `sales / net_profit / cfo / growth_* / margin` 确实属于 provider 稀疏段。
* 相对更稳的是：
  * `days_since_report`
  * `total_assets`
  * `total_liabilities`
  * `leverage`
* 但即使是这些更稳的 balance-sheet 字段，也不是完全零 warning；只能说比当前这组明显更稳。

## 建议

不要再把这类 warning 直接归因为“本地 PIT 刷新没做完”或“build 代码有 bug”。

后续可选路线：

1. 保持当前 benchmark config 不动，把这份问题当作 provider coverage caveat 记录下来。
2. 新增一份 provider-dense PIT variant，用更稳的 balance-sheet / freshness 字段替代当前稀疏的 income-statement / growth 组合。
3. 如果必须维持当前特征集，则接受 health 报告里这类 provider-sparse warning，不要再把它当作资产刷新失败。

当前更推荐第 2 条，而不是直接覆盖已有 benchmark baseline。

## 当前落地

已新增独立 variant：`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_dense.yml`

定位：

* 不改动现有 `hk_selected__quarterly_pit_core_hybrid` benchmark。
* 保留同一套 quarterly selected research unit 和 price/liquidity 慢特征。
* 仅把 provider 稀疏的 PIT 收入 / 利润 / 现金流 / growth 组合替换为更稳的：
  * `total_assets`
  * `total_liabilities`
  * `leverage`
  * `days_since_report`

配套处理：

* `build-hk-pit-fundamentals` 支持 `--feature-age-config` + `--max-selected-feature-age-days`，可以按这份 variant 的 PIT-backed selected features 派生 config-aware research universe。
* 这类过滤只作用于 `--universe-by-date-out`，不改 raw PIT mirror，也不改 `pipeline_fundamentals.parquet` 本体。
* 典型用途是剔除类似 `09988.HK` 这种“最新 PIT 行存在，但 selected balance-sheet 字段最近一次非空值超过 365 天”的 symbol-date。

示例：

```bash
csml rqdata build-hk-pit-fundamentals \
  --asset-dir artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest \
  --out artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest/pipeline_fundamentals.parquet \
  --source-universe-by-date artifacts/assets/universe/hk_connect_full_by_date.csv \
  --universe-by-date-out artifacts/assets/universe/hk_selected_pit_research_by_date.csv \
  --max-latest-report-age-days 365 \
  --feature-age-config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_dense.yml \
  --max-selected-feature-age-days 365 \
  --force
```
