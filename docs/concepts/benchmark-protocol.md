# Benchmark Protocol

本页解决什么：把这个项目里的 benchmark / baseline 分层说清楚，并给出 HK selected 的默认协议。
本页不解决什么：不展开参数定义、资产准备细节或具体指标解释。
适合谁：准备做正式研究、想让对比结果可解释的人。
读完你会得到什么：一套可直接执行的 benchmark 阶梯与对应配置入口。
相关页面：`docs/playbooks/hk-selected.md`、`docs/concepts/model-selection.md`、`docs/metrics.md`、`docs/outputs.md`

这个项目不是“没有 benchmark”，而是已经有 benchmark 能力，但过去更像散落在配置、输出和 playbook 里的隐含约定。

更准确地说，这里至少有三层 benchmark：

1. 市场 benchmark：`backtest.benchmark_symbol`
2. 特征 benchmark：固定同一研究单元，跑 `price-only -> PIT-only -> hybrid`
3. 模型 benchmark：固定同一 hybrid 研究单元，只换 `ridge -> xgb_regressor -> xgb_ranker / elasticnet`

## 1. 市场 benchmark

HK 研究默认用：

* `backtest.benchmark_symbol: 02800.HK`

配置后，run 会额外输出：

* `summary.json -> backtest.benchmark`
* `summary.json -> backtest.active`
* `backtest_benchmark.csv`
* `backtest_active.csv`

所以这个项目的“市场 benchmark”并不是额外要补的能力，代码已经支持。

## 2. HK selected 默认 benchmark 阶梯

当前仓库把 HK selected 的 benchmark protocol 定成下面这套：

| 层级 | 角色 | 官方配置 |
| --- | --- | --- |
| 市场 benchmark | 回测市场对照 | 所有 HK benchmark 配置默认使用 `02800.HK` |
| 特征 benchmark 1 | 季度纯量价 floor | `configs/experiments/baseline/hk_selected__quarterly_price_only.yml` |
| 特征 benchmark 2 | 季度 core PIT 增量 | `configs/experiments/baseline/hk_selected__quarterly_pit_core.yml` |
| 强 benchmark | 季度 core PIT + 慢量价，默认要被超越的对象 | `configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml` |
| 线性 benchmark | 同一 hybrid 单元上的 sanity check | `configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_ridge.yml` |
| Challenger | 同一 hybrid 单元上的排序模型 | `configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_xgb_ranker.yml` |
| Challenger | 同一 hybrid 单元上的稀疏线性模型 | `configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_elasticnet.yml` |

这套协议的重点不是“谁赢了”，而是先把问题拆开：

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

这两个都适合做专项挑战，但不适合一开始就定义基线：

* `xgb_ranker` 更偏排序目标
* `elasticnet` 更偏线性收缩/稀疏化

它们应该回答“同一研究单元里，换目标函数或线性归纳偏好后会不会更好”，而不是替代 benchmark protocol 本身。

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

## 5. 推荐执行顺序

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

## 6. 跑完先看什么

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

## 7. 和当前季度 PIT 最佳实践的关系

这套 benchmark protocol 和当前仓库的季度 PIT 最佳实践并不冲突。

当前 `configs/presets/hk_quarterly_pit_hybrid.yml` 默认已经使用：

* `features.missing.add_indicators: false`

所以官方 hybrid benchmark 与 challenger 配置，默认就是更稳妥的 `nomiss` 口径。

如果你后面要做更细的实验，比如：

* 更严格的 `xgb_ranker` 参数组
* 不同 `ffill` / exit policy
* 不同 universe

那就从这套 benchmark 配置继续派生到 `configs/local/`，不要回到“没有统一 benchmark”的状态。
