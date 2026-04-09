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
* `configs/presets/hk.yml` 是 HK 月频 starter：`PIT universe` + `provider` 基本面。
* `configs/presets/hk_quarterly_pit_hybrid.yml` 才是 HK 季频 `PIT fundamentals` 入口。
* `configs/experiments/baseline/` + `configs/experiments/variants/` 下的 HK selected 官方模板，主要建立在季度 PIT 路线之上。
* 日常开发优先验证 `default`、`hk` 和 HK selected 路线；当前仓库不再维护其他非 HK 主线。

## 测试

项目使用 `pytest`。默认入口不再强制打开 coverage，便于本地只收集测试、定点排查和拆分回归。

```bash
scripts/dev/run_tests.sh all
```

`scripts/dev/run_tests.sh all` 只覆盖 `pytest` 主测试集，不等于完整复现 CI。

常见用法：

```bash
# 只跑某个测试文件
uv run pytest tests/test_metrics.py

# 日常快回归
scripts/dev/run_tests.sh fast

# `fast` 的别名
scripts/dev/run_tests.sh unit

# 较重的离线回归
scripts/dev/run_tests.sh slow

# 跑集成测试
scripts/dev/run_tests.sh integration

# 需要 coverage 时显式执行
scripts/dev/run_tests.sh coverage

# 真实 provider 集成测试（需显式启用 + 配置对应 token/账号）
CSML_RUN_PROVIDER_INTEGRATION=1 uv run pytest tests/test_provider_integration.py -m integration
```

## 本地 Git Hooks

如果你希望在 `commit` / `push` 前先跑一层本地检查，可以安装仓库内置 hooks：

```bash
./scripts/dev/install_git_hooks.sh
```

安装后默认行为：

| hook | 命令 | 作用 |
| --- | --- | --- |
| `pre-commit` | `uv run pytest tests/test_docs_contracts.py tests/test_repo_path_references.py tests/test_run_tests_script.py -q` | 提前拦住文档 / 路径 / 测试入口契约问题 |
| `pre-push` | `scripts/dev/run_tests.sh fast` | 在 push 前先跑一遍离线快回归 |

补充：

* 本地 hook 是提前发现问题，不替代 CI。
* 如需跳过一次，使用 `git commit --no-verify` 或 `git push --no-verify`。
* `tests/test_docs_contracts.py` 现在只接受指向仓库里受版本控制目标的 Markdown 相对链接；研究笔记里引用本地 `artifacts/...` 运行产物时，用代码文本记录，不要写成可点击相对链接。

说明：

* `scripts/dev/run_tests.sh integration` 跑的是 `@pytest.mark.integration` 的跨模块流程，默认仍以离线跨模块集成为主。
* `tests/test_provider_integration.py` 也带 `integration` 标记，但未设置 `CSML_RUN_PROVIDER_INTEGRATION=1` 时会自动 skip，所以“integration” 不等于真实 provider 在线联调。
* 文档引用和公开入口契约现在也有测试兜底，主要看 `tests/test_docs_contracts.py` 和 `tests/test_run_tests_script.py`。

## HK 资产维护 Driver

如果你在做 HK + RQData 资产维护，而不是日常研究 / pipeline 开发，可以直接用维护者 driver：

```bash
python scripts/internal/run_hk_asset_workflow.py --target-date 20260402
```

默认会串联三段：

* `refresh`：刷新 `instruments / daily / daily_clean / valuation / ex_factors / dividends / shares / industry_changes / southbound`
* `inspect`：把健康检查报告统一写到 `artifacts/reports/`
* `package`：把当前这次 run 解析到的 snapshot 交给 `csml.release_tools.package_assets`

常见变体：

```bash
# 先看完整命令计划，不实际执行
python scripts/internal/run_hk_asset_workflow.py --target-date 20260402 --dry-run

# 只续跑镜像，不做后续体检 / 打包
python scripts/internal/run_hk_asset_workflow.py --phase refresh --target-date 20260402 --resume

# 日常维护优先用 patch 模式：只回看尾窗，再本地 merge 成新的 refreshed snapshot
python scripts/internal/run_hk_asset_workflow.py --phase refresh --target-date 20260402 --refresh-mode patch --resume

# 读取上一轮 inspect 产出的 repair_candidates，对 warning/error 问题做子集重拉
python scripts/internal/run_hk_asset_workflow.py --phase repair --target-date 20260402 --repair-asset daily

# 在已有 package 结果上继续发 GitHub release
python scripts/internal/run_hk_asset_workflow.py --phase release --target-date 20260402 --repo owner/name --prerelease
```

说明：

* 这是维护者脚本，不是公开 `csml` 主 CLI。
* 它只做薄编排；底层数据抓取、健康检查、打包、release 逻辑仍然分别落在现有命令里。
* `refresh` 成功后默认会回指通用 `latest` alias；如果你只想产出 dated snapshot，不想动 alias，传 `--no-repoint-latest`。
* `--refresh-mode full` 保留原来的整包重拉语义；`--refresh-mode patch` 会对 `daily / valuation / ex_factors / dividends / shares` 先拉尾窗 patch，再调用本地 patch merge 生成新的 canonical snapshot。
* patch 模式默认 `daily` 回看 20 个日历日、其他支持的 dated assets 回看 40 个日历日；可用 `--daily-patch-lookback-days` 和 `--dated-patch-lookback-days` 调整。
* 每次非 dry-run 执行还会额外写一份结构化 workflow report，默认落到 `artifacts/reports/hk_asset_refresh_<target_date>.json`；需要自定义位置时可传 `--workflow-report`。
* `repair` 会读取已有 workflow report 里的 `inspect.assets.<asset>.repair_candidates`，生成按 `symbol/date` 收缩后的子集重拉和 patch merge；默认只包含 `warning`/`error`，可用 `--repair-min-severity` 放宽到 `info`。
* `repair` 设计成第二次执行的修补流程；如果要基于本轮 inspect 结果修洞，先跑一轮带 `inspect` 的 workflow 产出 report，再单独跑 `--phase repair`。

### 测试矩阵

把最容易混淆的事实放在一张表里：

| 入口 / mode | 默认会跑什么 | 明确不跑什么 | 额外依赖 / 凭证 | 和 CI 的关系 |
| --- | --- | --- | --- | --- |
| `scripts/dev/run_tests.sh all` | 主 `pytest` 测试集 | 四个 optional extra smoke、显式启用前的真实 provider 联调 | `uv sync --extra dev` | 只覆盖主测试集，`all != 完整 CI` |
| `scripts/dev/run_tests.sh fast` / `unit` | `not integration and not slow` 的离线快回归 | `slow`、`integration`、extra smoke、真实 provider 联调 | `uv sync --extra dev` | 对应 CI 的 `fast` job |
| `scripts/dev/run_tests.sh slow` | `@pytest.mark.slow` 的较重离线回归 | `fast`、`integration`、extra smoke、真实 provider 联调 | `uv sync --extra dev` | 对应 CI 的 `slow` job |
| `scripts/dev/run_tests.sh integration` | `@pytest.mark.integration` 的跨模块流程 | 四个 optional extra smoke；未显式开启时真实 provider 联调会 skip | `uv sync --extra dev` | 对应 CI 的 `integration` job，但默认仍以离线流程为主 |
| `scripts/dev/run_tests.sh coverage` | 和 `all` 同一范围，但显式开启 coverage | 四个 optional extra smoke、显式启用前的真实 provider 联调 | `uv sync --extra dev` | 方便本地看覆盖率，不代表完整 CI |
| `CSML_RUN_PROVIDER_INTEGRATION=1 uv run pytest tests/test_provider_integration.py -m integration` | 真实 HK + RQData provider 联调 | 其他主测试集与 extra smoke | `--extra rqdata` + 真实账号 / token | 不在默认 CI，也不在 `run_tests.sh all` 里 |
| `rqdata-extra-smoke` / `duckdb-extra-smoke` / `liveops-hk-extra-smoke` / `stats-extra-smoke` | optional extra 的安装、导入和最小正向调用 | 主 `pytest` 测试集 | 各自对应的 extra | 只在 CI 单独执行；本地要显式补跑 |

## 测试分层约定

建议按以下分层维护测试，避免把“离线回归”与“端到端验证”混在一起：

1. `unit`（默认日常回归）：不依赖外部账号、网络与真实行情接口。
1. `integration`：覆盖跨模块流程（可包含较慢测试或更重的 fixture）。
1. `slow`：离线但更重的回归。当前主要覆盖 `tests/` 下这组 `test_pipeline_filters_*.py` 用例，它们会反复拉起 pipeline，便于本地和 CI 拆分执行。

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

CI 默认拆成七段：

1. `fast`：`scripts/dev/run_tests.sh fast`
1. `slow`：`scripts/dev/run_tests.sh slow`
1. `integration`：`scripts/dev/run_tests.sh integration`
1. `rqdata-extra-smoke`：安装 `--extra rqdata`，验证 optional extra 和 `csml rqdata --help`
1. `duckdb-extra-smoke`：安装 `--extra duckdb`，验证 optional extra 和最小 DuckDB 查询
1. `liveops-hk-extra-smoke`：安装 `--extra liveops-hk`，验证 `openpyxl` 和最小 xlsx 写出
1. `stats-extra-smoke`：安装 `--extra stats`，验证 `scipy` 和 `summarize_ic` 的最小调用

这样可以把默认离线回归、较重离线回归、端到端流程，以及 optional extra 的安装/导入烟雾检查分开看。排查失败时，先在本地复现对应那一段。

如果你要本地尽量贴近 CI，除了 `all` / `fast` / `slow` / `integration`，还需要单独跑这四段 optional extra smoke：

```bash
# rqdata-extra-smoke
uv sync --locked --extra dev --extra rqdata
uv run python -c "import rqdatac; print(rqdatac.__name__)"
uv run csml rqdata --help > /dev/null

# duckdb-extra-smoke
uv sync --locked --extra dev --extra duckdb
uv run python -c "import duckdb; print(duckdb.__version__)"
uv run csml data query --sql "select 1 as value" > /dev/null

# liveops-hk-extra-smoke
uv sync --locked --extra dev --extra liveops-hk
uv run python -c "import openpyxl; print(openpyxl.__version__)"
uv run python -c "from pathlib import Path; import pandas as pd; from csml.liveops.alloc_hk import write_xlsx_report; out = Path('/tmp/alloc_hk_smoke.xlsx'); write_xlsx_report(out, pd.DataFrame([{'symbol': '0001.HK'}]), pd.DataFrame([{'as_of': '2026-03-20'}]), pd.DataFrame([{'symbol': '0001.HK'}])); assert out.exists() and out.stat().st_size > 0"

# stats-extra-smoke
uv sync --locked --extra dev --extra stats
uv run python -c "import scipy; print(scipy.__version__)"
uv run python -c "import pandas as pd; from csml.metrics import summarize_ic; series = pd.Series([0.1, -0.1, 0.2]); stats = summarize_ic(series); assert 'p_value' in stats and stats['p_value'] == stats['p_value']"
```

最近几轮和 HK + RQData 相关的高频回归，建议至少覆盖这组：

```bash
scripts/dev/run_tests.sh all \
  tests/test_pipeline_validation.py \
  tests/test_summarize_runs.py \
  tests/test_pipeline_filters_*.py \
  tests/test_fundamentals_providers.py \
  tests/rqdata_assets/ \
  tests/test_universe_tools.py \
  tests/test_cli_core.py \
  tests/test_cli_rqdata.py \
  tests/test_cli_research.py \
  tests/test_cli_liveops.py \
  tests/test_linear_sweep.py \
  tests/test_data_providers_cache.py \
  -q
```

### 季度 provider / PIT 路线要看哪些测试

如果你改的是 `configs/experiments/baseline/hk_selected__quarterly_price_only.yml`、`configs/experiments/baseline/hk_selected__quarterly_pit_core.yml`、`configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml`、`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_*.yml`，或者 `configs/experiments/variants/hk_selected__pit_quarterly_financial_ml.yml`、`configs/experiments/variants/hk_selected__pit_quarterly_financial_linear.yml`、`configs/experiments/variants/hk_selected__pit_quarterly_hybrid.yml` 及其依赖的 pipeline 行为，建议至少理解这几组测试：

1. `tests/test_pipeline_validation.py`：配置模板烟雾检查，确认季度模板的 `label/eval/backtest.rebalance_frequency` 一致，`fundamentals.source` 没写反。
1. `tests/` 下这组 `test_pipeline_filters_*.py`：provider/file 两路基本面并入、PIT 文件读取、披露日后的 `ffill`，以及慢财报派生因子是否按披露节奏生效。
1. `tests/test_fundamentals_providers.py`：HK + RQData provider 基本面抓取、标准化和缓存键行为。
1. `tests/rqdata_assets/`：`mirror-hk-pit-financials`、`build-hk-pit-fundamentals`、coverage / health 检查等 PIT 资产预处理链路。
1. `tests/test_universe_tools.py`：港股通 universe 构建脚本的日期 token、输出路径和流动性筛选边界。
1. `tests/test_cli_rqdata.py`、`tests/test_cli_research.py`：PIT 资产命令和 `sweep-linear` 命令参数解析。
1. `tests/test_linear_sweep.py`：季度 PIT 线性 sweep 配置是否能被正确读取，生成的 jobs 和 base config 是否匹配。
1. `tests/test_data_providers_cache.py`：RQData 日线缓存、上市日裁剪和空区间处理，避免低频研究被脏缓存干扰。
1. `tests/test_summarize_runs.py`：`summary.json` 下游汇总字段是否完整，尤其是 `backtest.active` 的 benchmark 指标能否进入 `runs_summary.csv`。

## 改哪里跑哪些测试

下面这张表不是“全量回归清单”，而是提交前最少该先跑哪几组：

| 你改的范围 | 最少先跑 | 通常再补 |
| --- | --- | --- |
| CLI / 参数解析 / wrapper 转发 | `tests/test_cli_core.py`、`tests/test_cli_rqdata.py`、`tests/test_cli_research.py`、`tests/test_cli_liveops.py` | `scripts/dev/run_tests.sh fast` |
| 文档 / `README.md` / `docs/` / workflow 说明 | `tests/test_docs_contracts.py`、`tests/test_repo_path_references.py`、`tests/test_run_tests_script.py` | `scripts/dev/run_tests.sh fast` |
| `scripts/dev/run_tests.sh` / CI 测试入口 | `tests/test_run_tests_script.py`、`tests/test_docs_contracts.py` | 对应复现一遍 `fast` / `slow` / `integration` 或相关 smoke |
| `release_tools` 打包 / Release staging | `tests/test_asset_release_scripts.py`、`tests/test_run_release_scripts.py` | 对应脚本最小打包烟雾检查 |
| `csml data query` / metadata catalog / standardized layer | `tests/test_data_warehouse.py`、`tests/test_cli_core.py` | 本地补一个 `csml data query --sql "select 1 as value"` |
| `alloc-hk` / `liveops-hk` / xlsx 输出 | `tests/test_alloc_hk.py`、`tests/test_cli_liveops.py` | `uv sync --extra dev --extra liveops-hk` 后补最小 xlsx smoke |
| HK + RQData provider / PIT fundamentals / universe | `tests/test_pipeline_validation.py`、`tests/` 下的 `test_pipeline_filters_*.py`、`tests/test_fundamentals_providers.py`、`tests/rqdata_assets/`、`tests/test_universe_tools.py`、`tests/test_data_providers_cache.py` | `tests/test_summarize_runs.py`、`tests/test_linear_sweep.py` |
| intraday / patch merge / provider overlay audit / financial details 分析 | `tests/test_hk_intraday_download.py`、`tests/test_hk_intraday_tools.py`、`tests/test_hk_asset_patch_merge.py`、`tests/test_audit_provider_valuation.py`、`tests/test_hk_financial_details_analysis.py` | 对应 playbook 里的最小命令烟雾检查 |

## 提交前检查建议

1. 至少跑一遍 `scripts/dev/run_tests.sh all`。
1. 用你修改过的配置跑一次 `csml run --config ...`。
1. 检查 `README.md` 与 `docs/` 是否同步更新。

## 贡献入口

若你准备提交 PR，请同时附上：

1. 变更动机与影响范围。
1. 新增/修改的配置项说明。
1. 回归验证方式（测试命令与关键产物）。
