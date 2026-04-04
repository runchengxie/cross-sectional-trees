# Benchmark Protocol

本页解决什么：把这个项目里的 benchmark / baseline 分层说清楚，并给出 HK selected 的默认协议。\
本页不解决什么：不展开参数定义、资产准备细节或具体指标解释。\
适合谁：准备做正式研究、想让对比结果可解释的人。\
读完你会得到什么：一套可直接执行的 benchmark 阶梯与对应配置入口。\
相关页面：`docs/playbooks/hk-selected.md`、`docs/concepts/model-selection.md`、`docs/metrics.md`、`docs/outputs.md`

目前该项目最多允许三层 benchmark 的设置：

1. 市场 benchmark：`backtest.benchmark_symbol` 或 `backtest.benchmark_returns_file`
2. 特征 benchmark：固定同一研究单元，跑 `price-only -> PIT-only -> hybrid`
3. 模型 benchmark：固定同一 hybrid 研究单元，只换 `ridge -> xgb_regressor -> xgb_ranker / elasticnet`

## 1. 市场 benchmark

HK 研究默认用：

* `backtest.benchmark_symbol: 02800.HK`

如果你要评估“相对港股通可投 universe 的 alpha”，更贴近的做法是自建一个
`港股通 by-date universe cap-weight benchmark`，然后通过：

* `backtest.benchmark_returns_file: artifacts/benchmarks/hk_connect_capw.csv`

接入同一条回测，而不是强行用单一 ETF 近似。
当前仓库可用 `python -m csml.research.hk_connect_cap_weight_benchmark ...` 从
`by_date universe + backtest_periods + local daily/valuation assets` 生成这类收益文件。

配置后，run 会额外输出：

* `summary.json -> backtest.benchmark`
* `summary.json -> backtest.active`
* `backtest_benchmark.csv`
* `backtest_active.csv`

如果你想同时保留“市场 ETF 代理”和“更贴近 universe 的 alpha benchmark”，现在可以继续把主 benchmark 固定在其中一条，再把其他对照放进：

* `backtest.benchmark_compare`

这层是报告层附加对比，不会改变主 benchmark 的口径。配置后还会额外输出：

* `summary.json -> backtest.report_file`
* `summary.json -> backtest.benchmark_compare`
* `backtest_report.csv`
* `backtest_benchmark_compare_summary.csv`
* `backtest_benchmark_compare_<name>.csv`

## 2. HK selected 默认 benchmark 阶梯

当前仓库把 HK selected 的 benchmark protocol 定成下面这套：

| 层级 | 角色 | 官方配置 |
| --- | --- | --- |
| 市场 benchmark | 回测市场对照 | 大多数 HK benchmark 配置默认使用 `02800.HK`；当前月频本地推荐入口改用 universe-aligned `benchmark_returns_file` |
| 报告层 compare benchmark | 同一条 run 内并排看 ETF / selected cap-weight / connect cap-weight | 当前月频本地 execution variants 默认附带 `backtest.benchmark_compare` |
| 特征 benchmark 1 | 季度纯量价 floor | `configs/experiments/baseline/hk_selected__quarterly_price_only.yml` |
| 特征 benchmark 2 | 季度 core PIT 增量 | `configs/experiments/baseline/hk_selected__quarterly_pit_core.yml` |
| 强 benchmark | 季度 core PIT + 慢量价，默认要被超越的对象 | `configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml` |
| 线性 benchmark | 同一 hybrid 单元上的 sanity check | `configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_ridge.yml` |
| Challenger | 同一 hybrid 单元上的排序模型 | `configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_xgb_ranker.yml` |
| Challenger | 同一 hybrid 单元上的稀疏线性模型 | `configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_elasticnet.yml` |

这套协议是先把问题拆开：

1. alpha 是不是先出现在纯量价里
2. 加 core PIT 后有没有稳定增量
3. 再加慢量价后有没有继续增量
4. 在同一条 hybrid 路线上，模型差异到底带来了什么

## 3. 为什么这样分层

### `ridge` 是 sanity benchmark

`ridge` 弱一些正好有用。

如果同一研究单元在 `ridge` 上的 IC 还接近 0，通常应该先怀疑：

* 这条特征路线本身没信号
* PIT 覆盖率还不够
* 研究单元还没固定好

### `xgb_regressor` 是强 benchmark

它适合当“默认要被超越的对象”，因为：

* 非线性能力更强
* 现有仓库经验更多
* 作为统一强基线，更适合比较特征增量

### `xgb_ranker` / `elasticnet` 是 challenger

这两个都适合做专项挑战，观察是否能超越我们定义的基线：

* `xgb_ranker` 更偏排序目标
* `elasticnet` 更偏线性收缩/稀疏化

它们应该回答“同一研究单元里，换目标函数或线性归纳偏好后会不会更好”。

## 4. 跑 benchmark 时什么必须固定

做特征 benchmark 时，至少固定这些块：

* `universe`
* `label`
* `eval`
* `backtest`
* `market` / `data`

做模型 benchmark 时，在上面基础上再固定：

* `fundamentals`
* `features`

只改：

* `model`
* `eval.run_name`

如果这些块一起变了，你比较的就不是 benchmark，而是整条研究路线。

## 5. 同一研究单元里的特征研究 protocol

这套 protocol 只用于下面这种场景：

* `universe`、`label`、`eval`、`backtest`、`market/data` 已经固定
* 你还在同一个研究矩阵单元里
* 这次要回答的是“当前特征空间够不够用”或“该加哪一组特征”

它的作用是统一研究口径，避免后续配置一会儿靠直觉加列、一会儿随手删列，最后没人能解释为什么结果变化。

### 5.1 先按特征簇组织，而不是按单列组织

默认先把当前候选特征拆成几个可解释的 family，再决定删哪组、加哪组。

HK selected 当前常见 family 可以按下面理解：

* 动量：`ret_*`、`sma_*`、`sma_*_diff`、`rsi_*`、`macd_hist`
* 波动 / 流动性：`rv_*`、`volume_sma*_ratio`、`log_vol`、`vol`
* 成长：`growth_sales`、`growth_basic_earnings_per_share`、`growth_net_profit`、`growth_cash_flow_from_operating_activities`
* 质量 / 盈利：`profit_margin`、`operating_margin`、`cfo_margin`、`cfo_to_profit`
* 估值 / 规模：`market_cap`、`log_mcap`、`pe_ttm`、`pb`
* 新鲜度 / 时效性：`days_since_report`、`valuation_age_days`
* 行业 / 状态：当前更适合先做 diagnostics、`bucket_ic` 或组合约束；要升成训练特征时，单独记录假设

如果当前研究线刻意不包含某一类，例如 monthly `no_ret` 候选不再直接使用 trailing-return 动量，这种“留白”本身就是研究假设，后续不要无意间再补回去。

### 5.2 默认顺序一：先做 feature family ablation

默认先做 family 级消融，而不是直接盯单个 feature importance 排名。

推荐顺序：

1. 固定第 4 节里的研究块，只改 `features`
2. 先跑 `baseline`
3. 再按 family 做 `minus_<family>` 对照
4. 比较 `summary.json`、`feature_importance.csv`、回测表现和换手

最少建议覆盖：

* `minus_vol_liq`
* `minus_growth`
* `minus_quality`
* `minus_valuation_size`
* `minus_freshness`

如果某条线本来就没有某个 family，就不要为了凑表而硬加一个空组。

### 5.3 默认顺序二：对单调变换对先做 raw/log dedup

如果当前配置在建模前已经做每期横截面 `rank` 或 `zscore`，默认优先检查这类单调变换对：

* `market_cap` / `log_mcap`
* `vol` / `log_vol`

推荐做法：

* `raw-scale dedup`：保留 raw 列，删 log 列
* `log-scale dedup`：保留 log 列，删 raw 列

先回答“这两列是不是本质重复”，再决定是否继续动 `pb`、`cfo_to_profit`、`ret_120` 这类更可能带独立信息的列。

### 5.4 默认顺序三：新增稀疏 PIT 因子前先做 coverage probe

对资产负债表风险、杠杆、营运资本这类 PIT 因子的推荐处理顺序：

1. 先加 coverage-safe 的小探针，例如 `operating_margin`
2. 再加 debt / structure block，例如 `debt`、`debt_to_assets`、`debt_to_equity`、`net_debt_to_assets`
3. 每一步都检查可用样本有没有明显塌缩

至少检查这些信号：

* `run.log` 里是否出现 `Feature availability collapse`
* 过滤后模型日期是否明显变少
* 是否出现 `flag_zero_feature_importance=true`
* 是否出现 `flag_constant_prediction=true`

如果新特征把历史压缩到很短窗口，就先回退到 coverage-safe 版本。

### 5.5 默认顺序四：不要默认打开 missing indicators

`features.missing.add_indicators` 目前应视为专项假设，不是默认增强项。

只有在下面两种情况才建议打开：

* 你明确在研究“缺失本身是否携带信息”
* 你要验证 report staleness / sparse PIT 覆盖是否应该显式入模

否则默认保持关闭，并先用：

* `cross_sectional_median`
* `days_since_report`
* `valuation_age_days`

这些更容易解释的方式处理时效和覆盖问题。

### 5.6 跑完先看什么

做完这套特征实验后，优先检查：

* `config.used.yml`
* `summary.json`
* `feature_importance.csv`
* `run.log`

重点字段：

* `feature_importance_nonzero`
* `flag_zero_feature_importance`
* `flag_constant_prediction`
* OOS `IC`
* long-only / long-short 表现
* turnover / cost drag

如果新增特征后只得到“指标略升，但样本覆盖更差、重要度更集中、换手更高”，默认不升主线。

### 5.7 什么时候可以不按这套顺序来

下面这些场景可以跳过部分步骤，但要在配置名或研究笔记里写清楚：

* `price-only` / `PIT-only` floor benchmark
* 明确的 placebo / diagnostic sidecar
* 目标只是验证数据路线，不是验证特征增量
* 明确只回答单一问题，例如“只看 `operating_margin` 有没有增量”

简单说：

* 主线 / benchmark 配置，默认按这套顺序走
* probe / sidecar 配置，可以只做和当前问题直接相关的那一步

## 6. 推荐执行顺序

```bash
# 特征 benchmark
csml run --config configs/experiments/baseline/hk_selected__quarterly_price_only.yml
csml run --config configs/experiments/baseline/hk_selected__quarterly_pit_core.yml
csml run --config configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml

# 模型 benchmark / challenger
csml run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_ridge.yml
csml run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_xgb_ranker.yml
csml run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_elasticnet.yml

csml summarize \
  --runs-dir artifacts/runs \
  --run-name-prefix hk_sel_q_benchmark_ \
  --sort-by score
```

如果你只想先看最小闭环，先跑：

1. `hk_selected__quarterly_price_only.yml`
2. `hk_selected__quarterly_pit_core.yml`
3. `hk_selected__quarterly_pit_core_hybrid.yml`

先确认特征增量，再谈 challenger。

## 7. 跑完先看什么

先看：

* `summary.json`
* `config.used.yml`
* `backtest_active.csv`
* `runs_summary.csv`

重点看：

* `eval.ic_mean`
* `eval.long_short`
* `backtest.sharpe`
* `summary.json -> backtest.active.information_ratio`
* `summary.json -> backtest.active.tracking_error`
* `runs_summary.csv -> backtest_information_ratio`
* `runs_summary.csv -> backtest_tracking_error`
* `flag_constant_prediction`
* `flag_zero_feature_importance`

如果 `ridge` 和 `xgb_regressor` 都打不动 `price-only -> PIT-only -> hybrid` 的增量顺序，就先别急着继续换模型。

## 8. 和当前季度 PIT 最佳实践的关系

这套 benchmark protocol 和当前仓库的季度 PIT 最佳实践并不冲突。

当前 `configs/presets/hk_quarterly_pit_hybrid.yml` 默认已经使用：

* `features.missing.add_indicators: false`

所以官方 hybrid benchmark 与 challenger 配置，默认就是更稳妥的 `nomiss` 口径。

如果你后面要做更细的实验，比如：

* 更严格的 `xgb_ranker` 参数组
* 不同 `ffill` / exit policy
* 不同 universe

那就从这套 benchmark 配置继续派生到 `configs/local/`。
