# 维护债清单

本页只记录当前仓库仍保留的维护债。历史 HK RQData asset 维护代码、workflow wrapper、asset release 工具和相关测试已经 sunset，并迁出 `cross-sectional-trees` 的职责边界。

## 当前原则

* `cross-sectional-trees` 聚焦研究、回测、live/export 和运行结果发布。
* HK 数据下载、检查、清洗、PIT、current contract 和 asset release 由 `market-data-platform` 承担。
* 新增 C901 豁免时，需要在本页登记原因和退出条件。
* `scripts/dev/run_tests.sh maintainability` 执行当前 ratchet budget：长行、大函数和 C901 豁免不得超过现有基线。清债后只下调预算，不上调。

## C901 Registry

| File / module | Owner area | Reason | Validation command | Exit condition |
| --- | --- | --- | --- | --- |
| `src/cstree/commands/linear_sweep.py` | research commands | CLI orchestration still combines config expansion, job planning, and summary handling | `uv run pytest tests/test_linear_sweep.py -q` | Split planning and execution helpers |
| `src/cstree/commands/run_grid.py` | research commands | Grid command still owns parsing, run discovery, and report rendering | `uv run pytest tests/test_run_grid.py -q` | Extract report rendering and grid evaluation helpers |
| `src/cstree/commands/tune.py` | research commands | Tune command still combines search-space parsing, job writing, and execution orchestration | `uv run pytest tests/test_tune.py -q` | Extract search-space and job writer helpers |
| `src/cstree/liveops/alloc_hk_allocation.py` | liveops | HK allocation combines lot sizing, scenario matrix, and cash constraints | `uv run pytest tests/test_alloc_hk.py -q` | Split scenario planner and allocation engine |
| `src/cstree/liveops/holdings.py` | liveops | Holdings command still handles multiple input formats and renderers | `uv run pytest tests/test_holdings_live.py tests/test_holdings_errors.py -q` | Extract parser and renderer helpers |
| `src/cstree/pipeline/config_eval.py` | pipeline config | Evaluation config normalization still handles many legacy/default cases | `uv run pytest tests/test_pipeline_validation.py -q` | Split validation by config block |
| `src/cstree/pipeline/feature_engineering.py` | pipeline features | Feature construction still contains multiple feature-family branches | `uv run pytest tests/test_pipeline_filters_feature_formulas.py -q` | Extract feature-family builders |
| `src/cstree/pipeline/preflight.py` | pipeline preflight | Preflight checks still combine config, data, and environment validation | `uv run pytest tests/test_pipeline_validation.py -q` | Split check groups into small validators |
| `src/cstree/portfolio.py` | portfolio | Portfolio construction still combines ranking, buffering, weighting, and exits | `uv run pytest tests/test_backtest.py tests/test_pipeline_filters_backtest.py -q` | Extract weighting and exit helpers |
