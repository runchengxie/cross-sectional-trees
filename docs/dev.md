# 开发与测试

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

如需完整统计检验（`p_value` 等）：

```bash
uv sync --extra dev --extra stats
```

## 本地运行

```bash
csml run --config config/default.yml
```

调试时建议先用较短日期区间，确认流程可跑通后再放大样本窗口。

## 测试

项目使用 `pytest`，默认参数见 `pyproject.toml`（含 `--cov=csml`）。

```bash
uv run pytest
```

常见用法：

```bash
# 只跑某个测试文件
uv run pytest tests/test_metrics.py

# 日常快回归
uv run pytest -m "not integration and not slow"

# 跑集成测试
uv run pytest -m integration

# 真实 provider 集成测试（需显式启用 + 配置对应 token/账号）
CSML_RUN_PROVIDER_INTEGRATION=1 uv run pytest tests/test_provider_integration.py -m integration
```

## 测试分层约定

建议按以下分层维护测试，避免把“离线回归”与“端到端验证”混在一起：

1. `unit`（默认日常回归）：不依赖外部账号、网络与真实行情接口。
1. `integration`：覆盖跨模块流程（可包含较慢测试或更重的 fixture）。
1. `slow`：显式标注高耗时用例，便于 CI 按需拆分执行。

常用命令：

```bash
# 离线回归（建议本地高频执行）
uv run pytest -m "not integration and not slow"

# 仅集成测试
uv run pytest -m integration
```

最近几轮和 HK + RQData 相关的高频回归，建议至少覆盖这组：

```bash
uv run pytest \
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

如果你改的是 `config/hk_selected__provider_quarterly_valuation.yml`、`config/hk_selected__baseline_pit_quarterly.yml`、`config/hk_selected__pit_quarterly_financial_ml.yml`、`config/hk_selected__pit_quarterly_financial_linear.yml`、`config/hk_selected__pit_quarterly_hybrid.yml` 或它们依赖的 pipeline 行为，建议至少理解这几组测试：

1. `tests/test_pipeline_validation.py`：配置模板烟雾检查，确认季度模板的 `label/eval/backtest.rebalance_frequency` 一致，`fundamentals.source` 没写反。
1. `tests/test_pipeline_filters.py`：provider/file 两路基本面并入、PIT 文件读取、披露日后的 `ffill`，以及慢财报派生因子是否按披露节奏生效。
1. `tests/test_fundamentals_providers.py`：HK + RQData provider 基本面抓取、标准化和缓存键行为。
1. `tests/test_rqdata_assets.py`：`mirror-hk-pit-financials` 和 `build-hk-pit-fundamentals` 这条 PIT 资产预处理链路。
1. `tests/test_universe_tools.py`：港股通 universe 构建脚本的日期 token、输出路径和流动性筛选边界。
1. `tests/test_cli.py`：PIT 资产命令和 `sweep-linear` 命令参数解析。
1. `tests/test_linear_sweep.py`：季度 PIT 线性 sweep 配置是否能被正确读取，生成的 jobs 和 base config 是否匹配。
1. `tests/test_data_providers_cache.py`：RQData 日线缓存、上市日裁剪和空区间处理，避免低频研究被脏缓存干扰。
1. `tests/test_summarize_runs.py`：`summary.json` 下游汇总字段是否完整，便于后续比较 `long_short`、`Top-K` 胜率、walk-forward 和净回测。

## 提交前检查建议

1. 至少跑一遍 `uv run pytest`。
1. 用你修改过的配置跑一次 `csml run --config ...`。
1. 检查 `README.md` 与 `docs/` 是否同步更新。

## 贡献入口

若你准备提交 PR，请同时附上：

1. 变更动机与影响范围。
1. 新增/修改的配置项说明。
1. 回归验证方式（测试命令与关键产物）。
