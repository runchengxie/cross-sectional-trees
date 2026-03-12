# 配置参考

内置模板位于 `src/csml/config/*.yml`。导出后的配置默认放在 `config/`。

```bash
csml init-config --market default --out config/
```

相关文档：

* CLI 用法：`docs/cli.md`
* 项目能力：`docs/capabilities.md`
* 常见流程：`docs/cookbook.md`
* HK selected 配方：`docs/playbooks/README.md`
* 模板维护与派生：`docs/playbooks/research-template-design.md`
* 数据源差异：`docs/providers.md`
* 输出文件与字段：`docs/outputs.md`
* 常见报错：`docs/troubleshooting.md`

## 先选模板，再改参数

第一次改配置时，优先看这些键：

* `data.provider`：先确定数据源。
* `data.start_date` / `data.end_date`：复现实验优先用绝对日期。
* `universe.mode` + `universe.by_date_file`：长历史回测优先 PIT。
* `model.type`：先确定是线性基线还是 XGB 对照。
* `eval.top_k` / `backtest.top_k`：决定选股数量。
* `eval.transaction_cost_bps` / `backtest.transaction_cost_bps`：先把成本假设设清楚。
* `label.shift_days`：会直接影响当前持仓的解释。
* `live.enabled`：如果需要当前持仓快照，再开启 live。

## 常用模板

| 模板 | 用途 |
| --- | --- |
| `default` | HK starter 模板。适合先跑通主流程。 |
| `hk` | 港股 PIT 研究模板。适合正式研究配置。 |
| `cn/us` | 兼容模板。适合保留多市场基础切换或做对照。 |
| `config/hk_selected__xgb_regressor.yml` | 显式 XGB 回归配置。当前推荐作为 HK selected 的默认起点。 |
| `config/hk_selected__baseline.yml` | HK selected 兼容基线。当前内容和 `config/hk_selected__xgb_regressor.yml` 相同。 |
| `config/hk_selected__baseline_eval_sample.yml` | HK selected 评估抽样实验配置。适合检查样本抽样口径。 |
| `config/hk_selected__baseline_eval_sample_ffill.yml` | HK selected 评估抽样 + 退出价格回退实验配置。 |
| `config/hk_selected__baseline_pit_file.yml` | 读取本地 PIT fundamentals 文件的 HK 基线。 |
| `config/hk_selected__provider_quarterly_valuation.yml` | 不依赖本地 PIT 文件的季度估值对照。 |
| `config/hk_selected__baseline_pit_quarterly.yml` | 季度 PIT 财报基线。 |
| `config/hk_selected__pit_quarterly_financial_ml.yml` | 季度 PIT 财务 ML 基线。 |
| `config/hk_selected__pit_quarterly_financial_linear.yml` | 季度 PIT 财务线性对照。 |
| `config/hk_selected__pit_quarterly_hybrid.yml` | 季度 PIT 财报 + 慢技术面混合配置。 |
| `config/hk_connect__pit_quarterly_financial_ml.yml` | 更宽港股通股票池上的季度 PIT 财务 ML 配置。 |
| `config/hk_selected__xgb_ranker_pairwise.yml` | 显式 XGB 排序配置。 |

补充：

* `default` 现在是港股优先的 starter 模板。它用静态港股股票池，不依赖 PIT universe 文件。
* `--config default` 里的 `default` 是内置别名，不等于仓库里的 `config/default.yml`。
* 新项目优先从 `default` 或 `hk` 开始。只有确实需要多市场对照时，再切到 `cn/us`。
* `config/hk_selected.yml` 已移除。旧配置请直接改成 `config/hk_selected__xgb_regressor.yml`，或继续沿用 `config/hk_selected__baseline.yml`。
* 新文档和新实验更建议直接用 `config/hk_selected__xgb_regressor.yml`。
* `config/hk_selected__baseline.yml` 继续保留，主要用于兼容旧文档、旧脚本和旧 sweep 配置。
* `config/universe.hk_connect_full.yml` 用于生成更完整的港股通历史股票池文件。
* 当前现成模板主要覆盖月度和季度。年度 `Y` 需要从月度或季度模板本地派生。
* 当前现成季度模板主要是在比较不同信号路线，不是完整的“四模型矩阵”。如果你要做季度四模型 PK，先选一份季度基线，再本地派生四个模型版本。
* 想按研究路线选择这些模板时，先看 `docs/playbooks/README.md`。
* 想判断某个实验应该派生本地配置还是沉淀成仓库模板，继续看 `docs/playbooks/research-template-design.md`。

## 顶层配置块

常见顶层键：

* `market`：`cn` / `hk` / `us`
* `data`：数据源、日期区间、缓存、重试
* `universe`：股票池、过滤条件、PIT 文件
* `fundamentals`：基本面数据源、列映射、缺失处理
* `label`：预测窗口、shift、截尾方式
* `features`：特征列表与窗口
* `model`：模型类型、参数、样本权重
* `eval`：切分、IC、换手、稳健性检验和可选产物
* `backtest`：调仓频率、Top-K、成本、退出规则
* `live`：当前持仓快照

## 模型切换

```yaml
model:
  type: ridge
  params:
    alpha: 1.0
  sample_weight_mode: date_equal
```

支持的模型：

* `xgb_regressor`
* `xgb_ranker`
* `ridge`
* `elasticnet`

补充：

* 未显式设置 `model.type` 时，默认使用 `xgb_regressor`。
* `xgb_ranker` 会按 `trade_date` 自动分组训练，其余模型走回归流程。

### 模型区别

| 模型 | 训练目标 | 优点 | 局限 | 适合什么场景 |
| --- | --- | --- | --- | --- |
| `xgb_regressor` | 直接拟合数值型 label | 能吃非线性和特征交互，通常是最强的通用起点 | 参数更多，训练更慢，可解释性更弱 | 你已经有一套稳定研究单元，想先拿一个强非线性基线 |
| `xgb_ranker` | 按 `trade_date` 分组做排序学习 | 和截面选股的排序目标更接近，适合做 Top-K 对照 | 训练口径更特殊，调参和结果解释都更挑数据 | 你关心同日相对排序，想比较“直接回归”与“直接排序” |
| `ridge` | 带 L2 正则的线性回归 | 训练快，稳定，参数少，系数容易看 | 只能表达线性关系，吃不到复杂交互 | 你要先做线性基线、做 sanity check、或快速比较很多研究单元 |
| `elasticnet` | 带 L1 + L2 正则的线性回归 | 比 `ridge` 更容易压缩无效特征，适合做线性搜索 | 超参数更多，稳定性通常不如 `ridge`，更容易出现退化 run | 你想在线性模型里同时做收缩和稀疏化 |

### 线性模型搜索是什么意思

`csml sweep-linear` 里的“线性模型搜索”只覆盖这两类模型：

* `ridge`：搜索 `alpha`
* `elasticnet`：搜索 `alpha` 和 `l1_ratio`

当前仓库没有单独的普通最小二乘线性回归 `model.type`。如果你看到“线性模型”这个说法，默认是指 `ridge` 和 `elasticnet` 这两条路线。

### 在这个项目里怎么选

建议按下面的顺序理解：

* 默认起点更适合用 `xgb_regressor`。仓库里的 `default`、`hk`、`config/hk_selected__xgb_regressor.yml` 都是这个方向。
* `xgb_ranker` 很重要，但它更像排序目标的专项对照，不适合直接当所有路线的统一默认值。
* `ridge` 更适合当线性基线。它跑得快，也更适合先判断这套特征和标签是不是有稳定关系。
* `elasticnet` 更适合在线性路线里做补充搜索，不一定适合作为唯一主模型。

如果你只想先选一个模型开跑，当前更稳妥的默认选项仍然是 `xgb_regressor`。如果你明确只关心同日截面排序，也可以把 `xgb_ranker` 作为第一对照。新路线探索时，最好同时保留一份 `ridge` 对照。

## `data`

高频键：

* `provider`：`tushare` / `rqdata` / `eodhd`
* `start_date` / `start_years`：两者同时存在时，`start_date` 优先生效
* `end_date`
* `price_col`
* `cache_dir`
* `cache_tag` / `cache_version`
* `cache_mode` / `daily_cache_mode`
* `cache_refresh_days`
* `cache_refresh_on_hit`
* `retry`

### 日期 token

`end_date` 支持：

* `today`
* `t-1`
* `last_trading_day`
* `last_completed_trading_day`
* `YYYYMMDD`

补充：

* `last_trading_day` 和 `last_completed_trading_day` 是否严格按交易日解析，取决于 provider 和命令上下文。
* 做自动化任务或复现实验时，优先使用绝对日期。
* provider 差异见 `docs/providers.md`，命令侧行为见 `docs/cli.md`。

### 缓存

`cache_mode` / `daily_cache_mode` 支持：

* `symbol`：按单票缓存
* `range` / `window`：按时间区间缓存

常见建议：

* 需要隔离实验版本时，设置 `data.cache_tag`
* 想减少“同配置结果漂移”时，固定绝对日期并保留缓存目录
* HK 这类日频研究，几百只股票跑 10-15 年通常仍是几十 MB 级别，优先继续用 Parquet 缓存，不必先上数据库

### TuShare 覆盖项

按需可配：

* `daily_endpoint` / `basic_endpoint`
* `daily_fields` / `basic_fields`
* `daily_params` / `basic_params`
* `daily_symbol_param` / `daily_start_param` / `daily_end_param`

## `universe`

高频关注点：

* `mode`：`auto` / `pit` / `static`
* `by_date_file`
* `require_by_date`
* `min_symbols_per_date`
* `suspended_policy`

建议：

* 长历史回测优先 `pit + by_date_file`
* 静态 `symbols/symbols_file` 适合当期研究，不适合严谨历史回测

## `label`

高频键：

* `target_col`
* `horizon_days`
* `horizon_mode`
* `rebalance_frequency`
* `shift_days`
* `winsorize`

补充：

* `rebalance_frequency` 常见值是 `M`、`Q`、`Y`。
* `shift_days` 会影响信号日和入场日的对应关系。
* 如果你看到“当月持仓”和预期不一致，先回看 `shift_days`。

## `eval`

高频键：

* `top_k`
* `transaction_cost_bps`
* `purge_days`
* `embargo_days`
* `signal_direction_mode`
* `min_abs_ic_to_flip`
* `sample_on_rebalance_dates`
* `report_train_ic`
* `save_artifacts`
* `save_dataset`
* `permutation_test`
* `walk_forward`
* `final_oos`
* `rolling`
* `bucket_ic`

### 泄漏防护

默认行为：

* `eval.purge_days` 未配置时，会自动取 `label.horizon_days_effective + label.shift_days`
* `eval.embargo_days` 未配置时默认 `0`

建议：

* 显式覆盖时，通常保持 `purge_days >= shift_days + horizon_days_effective`
* `sample_on_rebalance_dates=true` 时，系统会把 `purge/embargo` 从天数换算为重平衡步数

### 可选评估能力

* `permutation_test`：做置换检验
* `walk_forward`：做滚动窗口验证
* `final_oos`：保留最终留出期
* `rolling`：输出滚动 IC / Sharpe
* `bucket_ic`：输出分桶 IC

## `backtest`

高频键：

* `enabled`
* `rebalance_frequency`
* `top_k`
* `transaction_cost_bps`
* `long_only`
* `short_k`
* `benchmark_symbol`
* `exit_mode`
* `exit_price_policy`
* `exit_fallback_policy`
* `weighting`
* `buffer_exit`
* `buffer_entry`
* `tradable_col`
* `execution`

### 退出价格

`exit_price_policy`：

* `strict`：到期日没有价格或不可交易时，本期不计算退出
* `ffill`：用到期日前最近可用价格退出
* `delay`：向后找最近可用价格退出

`exit_fallback_policy`：

* `ffill`：`delay` 向后找不到价格时，回退到到期日前最近可用价格
* `none`：不回退

### 组合权重

`weighting`：

* `equal`：入选持仓等权
* `signal`：对入选持仓按信号做 softmax 权重，保留方向但让强信号权重更高

建议：

* 先用 `equal` 做基线，便于解释和横向比较。
* 当 `Pearson IC`、尾部组合或回测明显优于 `Spearman IC` 时，再单独测试 `signal`。

补充：

* `rebalance_frequency` 常见值是 `M`、`Q`、`Y`。

### 新旧键优先级

* 旧键：`backtest.exit_price_policy` / `backtest.exit_fallback_policy`
* 新键：`backtest.execution.exit_policy.price` / `backtest.execution.exit_policy.fallback`
* 两者同时存在时，新键最终生效

### 与停牌处理的关系

* `universe.suspended_policy=mark`：保留样本并标记 `is_tradable`
* `universe.suspended_policy=filter`：前置过滤停牌样本

## `fundamentals`

高频键：

* `enabled`
* `source`
* `features`
* `column_map`
* `ffill`
* `log_market_cap`
* `required`
* `cache_dir`

补充：

* 想做纯量价路线时，最直接的做法是把 `fundamentals.enabled=false`。
* `source=provider` 支持 TuShare，也支持 `market=hk` + `provider=rqdata`
* `source=file` 读取本地 CSV 或 Parquet
* `provider=rqdata` 时，默认走 `rqdatac.get_factor`
* 未显式设置 `fundamentals.cache_dir` 时，provider 基本面默认缓存到 `data.cache_dir/fundamentals/<market>/`
* HK 常用映射可直接写成：`market_cap -> hk_total_market_val`、`pe_ttm -> pe_ratio_ttm`、`pb -> pb_ratio_ttm`
* 缺文件时默认 warning 并跳过，可用 `required=true` 改成报错
* 如果文件来自 `csml rqdata build-hk-pit-fundamentals`，默认 `trade_date=info_date`。常见接法是保留 `fundamentals.ffill=true`，让披露后的交易日沿用最近一版财报值
* 如果 `features.list` 里写了 `delta_<field>`，pipeline 会先在财报披露日上计算相邻报告的变化量，再沿用 `fundamentals.ffill`
* 如果 `features.list` 里写了 `growth_<field>`，pipeline 会在财报披露日上计算对称增长率：`(当前值 - 上期值) / ((|当前值| + |上期值|) / 2)`，再沿用 `fundamentals.ffill`
* 如果 `features.list` 里写了 `days_since_report`，pipeline 会按最新披露日计算财报新鲜度

季度 PIT 研究时，建议再注意三件事：

* 标签、评估和回测的 `rebalance_frequency` 一起改成 `Q`。这样口径一致，结果更容易解释。
* 优先使用 `source=file` + PIT fundamentals 文件。季度财报研究更依赖披露时点，直接读本地 PIT 文件更稳妥。
* 先用覆盖率高的主项和增长，再决定要不要加更稀疏的资产负债结构比率。常见起点包括 `sales`、`operating_profit`、`net_profit`、`basic_earnings_per_share`、`cash_flow_from_operating_activities`、`growth_*`、`profit_margin`、`cfo_margin`、`cfo_to_profit` 和 `days_since_report`。如果你镜像了覆盖更完整的 PIT 字段，再扩展到 `debt_to_equity`、`cash_to_assets`、`working_capital_to_assets` 这类结构比率。

## `features.missing`

`features.missing` 用于对模型特征做缺失填补。这个块常用于季度财报研究。

高频键：

* `method`
* `features`
* `add_indicators`
* `indicator_suffix`

当前支持的 `method`：

* `none`
* `zero`
* `cross_sectional_median`

建议：

* 财务特征优先用 `cross_sectional_median`。它会按 `trade_date` 做横截面中位数填补。
* 如果你同时打开 `add_indicators=true`，模型会额外拿到 `<feature>_missing` 这类缺失标记。
* 这个块建议只覆盖目标财报列，不要默认套到全部价格特征。

## `live`

`live` 用于在同一套配置下生成当前持仓快照。建议单独使用 live 配置文件和独立输出目录。

```yaml
data:
  end_date: "t-1"

eval:
  output_dir: "artifacts/live_runs"
  save_artifacts: true

backtest:
  enabled: false

live:
  enabled: true
  as_of: "t-1"
  train_mode: "full"
```

开启 live 时，通常还需要：

* `eval.save_artifacts=true`
* 单独的 `eval.output_dir`
* 明确的 `live.as_of`

命令入口见 `docs/cli.md`，输出文件见 `docs/outputs.md`。

## 可选输出

### `dataset.parquet`

设置 `eval.save_dataset=true` 且 `eval.save_artifacts=true` 后，会额外输出 `dataset.parquet`。

### `backtest.execution`

如需显式配置执行成本和退出规则，可使用：

```yaml
backtest:
  execution:
    cost_model:
      name: bps
      bps: 15
      round_trip: true
    exit_policy:
      price: delay
      fallback: ffill
```
