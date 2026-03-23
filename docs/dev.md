# 开发与测试

本页解决什么：开发环境、测试分层与回归入口。
本页不解决什么：不展开研究流程与业务概念。
适合谁：贡献代码或维护测试的人。
读完你会得到什么：本地开发与测试的最短路径。
相关页面：`README.md`、`docs/cookbook.md`、`docs/config.md`

## 环境准备

推荐使用 `uv`：

```bash
uv venv --seed
uv sync --extra dev
```

如需 RQData 相关能力：

```bash
uv sync --extra dev --extra rqdata
```

如需 `csml alloc-hk --format xlsx`：

```bash
uv sync --extra dev --extra rqdata --extra liveops-hk
```

如需 DuckDB 查询层：

```bash
uv sync --extra dev --extra duckdb
```

如需完整统计检验（`p_value` 等）：

```bash
uv sync --extra dev --extra stats
```

## 本地运行

```bash
csml run --config default
```

调试时建议先用较短日期区间，确认流程可跑通后再放大样本窗口。

补充：

* `default` 现在是 HK starter 模板。
* 跑 `default` 或 `hk` 模板前，先安装 `--extra rqdata`。
* 如果你要复现仓库里的 PIT 港股研究路线，优先用 `configs/presets/hk.yml`，以及 `configs/experiments/baseline/` + `configs/experiments/variants/` 下的 HK selected 官方模板。
* `cn/us` 相关改动主要属于兼容维护。日常开发优先验证 `default`、`hk` 和 HK selected 路线。

## 测试

项目使用 `pytest`。默认入口不再强制打开 coverage，便于本地只收集测试、定点排查和拆分回归。

```bash
scripts/dev/run_tests.sh all
```

常见用法：

```bash
# 只跑某个测试文件
uv run pytest tests/test_metrics.py

# 日常快回归
scripts/dev/run_tests.sh fast

# 较重的离线回归
scripts/dev/run_tests.sh slow

# 跑集成测试
scripts/dev/run_tests.sh integration

# 需要 coverage 时显式执行
scripts/dev/run_tests.sh coverage

# 真实 provider 集成测试（需显式启用 + 配置对应 token/账号）
CSML_RUN_PROVIDER_INTEGRATION=1 uv run pytest tests/test_provider_integration.py -m integration
```

说明：

* `scripts/dev/run_tests.sh integration` 跑的是 `@pytest.mark.integration` 的跨模块流程。
* `tests/test_provider_integration.py` 也带 `integration` 标记，但未设置 `CSML_RUN_PROVIDER_INTEGRATION=1` 时会自动 skip，所以默认 CI 的 `integration` job 仍以离线集成为主。
* 文档引用和公开入口契约现在也有测试兜底，主要看 `tests/test_docs_contracts.py` 和 `tests/test_run_tests_script.py`。

## 测试分层约定

建议按以下分层维护测试，避免把“离线回归”与“端到端验证”混在一起：

1. `unit`（默认日常回归）：不依赖外部账号、网络与真实行情接口。
1. `integration`：覆盖跨模块流程（可包含较慢测试或更重的 fixture）。
1. `slow`：离线但更重的回归。当前主要覆盖 `tests/test_pipeline_filters.py` 这类会反复拉起 pipeline 的用例，便于本地和 CI 拆分执行。

常用命令：

```bash
# 离线回归（建议本地高频执行）
scripts/dev/run_tests.sh fast

# 较重的离线回归
scripts/dev/run_tests.sh slow

# 仅集成测试
scripts/dev/run_tests.sh integration
```

## CI

仓库现在提供 GitHub Actions workflow：`.github/workflows/tests.yml`。

CI 默认拆成五段：

1. `fast`：`scripts/dev/run_tests.sh fast`
1. `slow`：`scripts/dev/run_tests.sh slow`
1. `integration`：`scripts/dev/run_tests.sh integration`
1. `rqdata-extra-smoke`：安装 `--extra rqdata`，验证 optional extra 和 `csml rqdata --help`
1. `duckdb-extra-smoke`：安装 `--extra duckdb`，验证 optional extra 和 `csml data query --help`

这样可以把默认离线回归、较重离线回归、端到端流程，以及 optional extra 的安装/导入烟雾检查分开看。排查失败时，先在本地复现对应那一段。

最近几轮和 HK + RQData 相关的高频回归，建议至少覆盖这组：

```bash
scripts/dev/run_tests.sh all \
  tests/test_pipeline_validation.py \
  tests/test_summarize_runs.py \
  tests/test_pipeline_filters.py \
  tests/test_fundamentals_providers.py \
  tests/test_rqdata_assets.py \
  tests/test_universe_tools.py \
  tests/test_cli.py \
  tests/test_linear_sweep.py \
  tests/test_data_providers_cache.py \
  -q
```

### 季度 provider / PIT 路线要看哪些测试

如果你改的是 `configs/experiments/baseline/hk_selected__quarterly_price_only.yml`、`configs/experiments/baseline/hk_selected__quarterly_pit_core.yml`、`configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml`、`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_*.yml`，或者 `configs/experiments/variants/hk_selected__pit_quarterly_financial_ml.yml`、`configs/experiments/variants/hk_selected__pit_quarterly_financial_linear.yml`、`configs/experiments/variants/hk_selected__pit_quarterly_hybrid.yml` 及其依赖的 pipeline 行为，建议至少理解这几组测试：

1. `tests/test_pipeline_validation.py`：配置模板烟雾检查，确认季度模板的 `label/eval/backtest.rebalance_frequency` 一致，`fundamentals.source` 没写反。
1. `tests/test_pipeline_filters.py`：provider/file 两路基本面并入、PIT 文件读取、披露日后的 `ffill`，以及慢财报派生因子是否按披露节奏生效。
1. `tests/test_fundamentals_providers.py`：HK + RQData provider 基本面抓取、标准化和缓存键行为。
1. `tests/test_rqdata_assets.py`：`mirror-hk-pit-financials` 和 `build-hk-pit-fundamentals` 这条 PIT 资产预处理链路。
1. `tests/test_universe_tools.py`：港股通 universe 构建脚本的日期 token、输出路径和流动性筛选边界。
1. `tests/test_cli.py`：PIT 资产命令和 `sweep-linear` 命令参数解析。
1. `tests/test_linear_sweep.py`：季度 PIT 线性 sweep 配置是否能被正确读取，生成的 jobs 和 base config 是否匹配。
1. `tests/test_data_providers_cache.py`：RQData 日线缓存、上市日裁剪和空区间处理，避免低频研究被脏缓存干扰。
1. `tests/test_summarize_runs.py`：`summary.json` 下游汇总字段是否完整，尤其是 `backtest.active` 的 benchmark 指标能否进入 `runs_summary.csv`。

## 提交前检查建议

1. 至少跑一遍 `scripts/dev/run_tests.sh all`。
1. 用你修改过的配置跑一次 `csml run --config ...`。
1. 检查 `README.md` 与 `docs/` 是否同步更新。

## 贡献入口

若你准备提交 PR，请同时附上：

1. 变更动机与影响范围。
1. 新增/修改的配置项说明。
1. 回归验证方式（测试命令与关键产物）。
