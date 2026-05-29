# 开发与测试

本页说明本地开发环境、测试入口、Git hooks、CI 分层，以及 HK 资产维护脚本。\
本页不解释具体研究流程和量化指标；研究路径请看 `docs/cookbook.md` 和 `docs/playbooks/README.md`。\
适合谁：需要改代码、跑回归测试、维护脚本或排查 CI 的开发者。\
相关页面：`README.md`、`docs/cookbook.md`、`docs/config.md`、`scripts/README.md`

## 先按角色选路径

| 你现在要做什么 | 先看哪里 |
| --- | --- |
| 本地改代码并跑回归 | 环境准备、测试框架与命令、修改模块与对应测试 |
| 改 CLI、pipeline、配置解析 | 测试框架与命令、季度 provider 与 PIT 路线测试重点 |
| 维护 HK / RQData 本地资产 | 进入 `market-data-platform/docs/hk-assets.md` 和 `marketdata rqdata ...` |
| 排查 GitHub Actions | GitHub Actions CI 架构 |
| 提交前自检 | 本地 Git Hooks、提交前检查建议 |

日常开发通常不需要先读 HK 资产维护章节。那部分面向数据资产维护者，涉及刷新、检查、修复、打包和 release。

## 环境准备

推荐使用 `uv`：

```bash
uv venv --seed
uv sync --extra dev
```

按需安装额外依赖：

```bash
# RQData 相关能力
uv sync --extra dev --extra rqdata

# cstree alloc-hk --format xlsx
uv sync --extra dev --extra rqdata --extra liveops-hk

# DuckDB 查询层
uv sync --extra dev --extra duckdb

# 完整统计检验，例如 p_value
uv sync --extra dev --extra stats
```

`uv sync` 会把当前环境同步到本次命令声明的 extras 集合。给已有 RQData 环境追加 Excel 导出能力时，不要只运行 `uv sync --extra liveops-hk`；日常 HK 运维建议一次性使用 `uv sync --extra dev --extra rqdata --extra liveops-hk`。

## 本地跑一次

```bash
cstree run --config default
```

本地调试建议先缩短日期区间。确认 pipeline 能跑通后，再扩大样本窗口。

补充说明：

* `default` 目前指向 HK starter 模板。
* 运行 `default` 或 `hk` 前，需要先安装 `--extra rqdata`。
* `configs/presets/hk.yml` 是 HK 月频 starter 路线，包含 PIT 股票池和远端 provider 基本面。
* `configs/presets/hk_quarterly_pit_hybrid.yml` 是 HK 季频 PIT 基本面入口。
* `configs/experiments/baseline/` 和 `configs/experiments/variants/` 下的 HK selected 官方模板，主要基于季度 PIT 路线。
* 日常开发优先验证 `default`、`hk` 和 HK selected 这些核心路线。

## 测试框架与命令

项目使用 `pytest`。仓库脚本 `scripts/dev/run_tests.sh` 是日常测试入口。

```bash
scripts/dev/run_tests.sh all
```

`all` 覆盖主 `pytest` 测试集，不完全等同于在 CI 环境下的完整复现。CI 还会单独跑可选依赖冒烟检查（optional extra smoke）。

常用命令：

```bash
# 只跑某个测试文件
uv run python -m pytest tests/test_metrics.py

# 高频快回归
scripts/dev/run_tests.sh fast

# fast 的别名
scripts/dev/run_tests.sh unit

# 较重的离线回归
scripts/dev/run_tests.sh slow

# 跨模块集成测试
scripts/dev/run_tests.sh integration

# 覆盖率报告
scripts/dev/run_tests.sh coverage

# Ruff lint、基础复杂度检查、改动 Python 文件的 import / 长行 ratchet
scripts/dev/run_tests.sh lint

# Pyright 类型检查；当前只覆盖 pyproject.toml 中登记的稳定模块子集
scripts/dev/run_tests.sh typecheck

# 轻量校验 C901 豁免是否登记在维护债 inventory
scripts/dev/run_tests.sh c901-debt

# 校验共享数据运维能力没有回流到研究仓库
scripts/dev/run_tests.sh data-ops-boundary

# 输出维护债静态指标；可加 --json 或 --markdown
scripts/dev/run_tests.sh maintainability

# 全仓库 import 排序检查；历史文件可能仍有遗留问题
scripts/dev/run_tests.sh imports

# 只检查本次改动的 Python 文件格式
scripts/dev/run_tests.sh format

# 全仓库格式检查；历史文件可能仍有遗留问题
scripts/dev/run_tests.sh format-all

# 真实 provider 在线联调，需要显式开启并配置 token 或账号
CSTREE_RUN_PROVIDER_INTEGRATION=1 uv run python -m pytest tests/test_provider_integration.py -m integration
```

维护债指标需要看趋势时，用下面的只读入口生成快照；它只扫描 `src/`、`scripts/`
和 `tests/` 下的 Python 文件，不访问 `artifacts/`：

```bash
scripts/dev/run_tests.sh maintainability --markdown
scripts/dev/run_tests.sh maintainability --json --limit 20
```

## 本地 Git Hooks

如果希望在 `commit` 或 `push` 前自动跑一层检查，可以安装仓库 hooks：

```bash
./scripts/dev/install_git_hooks.sh
```

安装后的默认行为：

| hook | 命令 | 作用 |
| --- | --- | --- |
| `pre-commit` | `uv run python -m pytest tests/test_docs_contracts.py tests/test_repo_path_references.py tests/test_run_tests_script.py -q` | 提前发现文档契约、路径引用和测试入口问题 |
| `pre-push` | `scripts/dev/run_tests.sh fast` | 推送前跑快回归 |

说明：

* 本地 hook 用来提前发现问题，不能替代远端 CI。
* 特殊情况下可以用 `git commit --no-verify` 或 `git push --no-verify` 跳过。
* Ruff 已启用 formatter、import 排序和基础复杂度检查。`lint` 会拦截高风险语法错误、新增高复杂函数，并检查本次改动的 Python import 排序、未使用 import、未使用变量、lambda / closure late-binding 风险和新增 Python 长行。
* Pyright 已接入 `typecheck` 和 CI。当前只检查 `pyproject.toml` 中 `[tool.pyright].include` 列出的稳定模块子集；扩大覆盖范围时，应先修复对应模块的类型问题，再把路径加入 include。
* 历史 import 和 format 遗留问题可用 `imports`、`format-all` 单独盘点。
* 已知复杂度历史债务记录在 `pyproject.toml` 的 `per-file-ignores`，并在内部维护债清单里按 owner area、原因、验证命令和退出条件登记。完成拆分优化后，应逐个撤销豁免。
* 触碰 Python 文件时，不要新增超过 100 字符的代码行或新的 `C901` 文件级豁免；如果豁免仍不能撤销，要在内部维护债清单里记录原因。`lint` 会在新增 `C901` ignore 但未同步维护债清单时失败，并额外校验当前豁免是否都在维护债清单登记。
* 触碰数据下载、健康检查、current contract、registry、universe asset builder 或 release 相关路径时，先看 `docs/internal/data-ops-boundary-inventory.md`。`lint` 会运行 `scripts/dev/data_ops_boundary.py --check`，防止共享数据运维实现回流到本仓库。
* 全仓库严格规则可用诊断命令盘点，不默认作为 gate：`.venv/bin/ruff check src tests --select E,F,W,I,B,UP,SIM,RUF --ignore E501 --statistics`。
* 全仓库 import sorting、unused import、pyupgrade 或 `SIM/RUF` 批量清理应作为单独机械改动处理，不和行为保持 refactor 或功能改动混做。
* `tests/test_docs_contracts.py` 只接受指向仓库内受版本控制文件的 Markdown 相对链接。引用本地 `artifacts/...` 运行产物时，用代码文本记录，不要写成可点击相对链接。

## 测试分层

建议按三层维护测试：

1. `unit` / `fast`：日常快回归，保持离线，不依赖外部账号、网络或真实行情接口。
2. `integration`：跨模块流程测试，可包含耗时更长或依赖更重的 fixture。
3. `slow`：计算较重的离线闭环测试，例如反复拉起 pipeline 的 `tests/test_pipeline_filters_*.py`。

常规运行顺序：

```bash
scripts/dev/run_tests.sh fast
scripts/dev/run_tests.sh slow
scripts/dev/run_tests.sh integration
```

`scripts/dev/run_tests.sh integration` 运行带有 `@pytest.mark.integration` 的跨模块测试。`tests/test_provider_integration.py` 虽然也带有 `integration` 标记，但只有设置 `CSTREE_RUN_PROVIDER_INTEGRATION=1` 时才会真正访问 provider。

### 测试矩阵维度剖析

上面的测试分层用于本地快速定位问题，不代表完整 CI。

## GitHub Actions CI

CI 配置在 `.github/workflows/tests.yml`。默认拆成八个 job：

1. `fast`：运行 `scripts/dev/run_tests.sh fast`。
2. `slow`：运行 `scripts/dev/run_tests.sh slow`。
3. `integration`：运行 `scripts/dev/run_tests.sh integration`。
4. `typecheck`：运行 `scripts/dev/run_tests.sh typecheck`。
5. `rqdata-extra-smoke`：安装 `--extra rqdata`，验证 `rqdatac` 与 research 侧 RQData runtime 可导入。
6. `duckdb-extra-smoke`：安装 `--extra duckdb`，验证最小 DuckDB query 执行。
7. `liveops-hk-extra-smoke`：安装 `--extra liveops-hk`，验证 xlsx 文件的基本写入能力。
8. `stats-extra-smoke`：安装 `--extra stats`，验证 `scipy` 和 `summarize_ic`。

可选依赖冒烟检查（optional extra smoke）只验证额外依赖能安装、能导入、能完成最小调用。它们不替代主测试集。

本地模拟 CI 强度时，除了 `all` / `fast` / `slow` / `integration` / `typecheck`，还要手动跑下面四组：

```bash
# rqdata-extra-smoke
uv sync --locked --extra dev --extra rqdata
uv run python -c "import rqdatac; print(rqdatac.__name__)"
uv run python -c "from cstree import rqdata_runtime; print(rqdata_runtime.__name__)"
uv run cstree --help > /dev/null

# duckdb-extra-smoke
uv sync --locked --extra dev --extra duckdb
uv run python -c "import duckdb; print(duckdb.__version__)"
uv run cstree data query --sql "select 1 as value" > /dev/null

# liveops-hk-extra-smoke
uv sync --locked --extra dev --extra liveops-hk
uv run python -c "import openpyxl; print(openpyxl.__version__)"
uv run python -c "from pathlib import Path; import pandas as pd; from cstree.liveops.alloc_hk import write_xlsx_report; out = Path('/tmp/alloc_hk_smoke.xlsx'); write_xlsx_report(out, pd.DataFrame([{'symbol': '0001.HK'}]), pd.DataFrame([{'as_of': '2026-03-20'}]), pd.DataFrame([{'symbol': '0001.HK'}])); assert out.exists() and out.stat().st_size > 0"

# stats-extra-smoke
uv sync --locked --extra dev --extra stats
uv run python -c "import scipy; print(scipy.__version__)"
uv run python -c "import pandas as pd; from cstree.metrics import summarize_ic; series = pd.Series([0.1, -0.1, 0.2]); stats = summarize_ic(series); assert 'p_value' in stats and stats['p_value'] == stats['p_value']"
```

## HK 数据资产维护边界

HK 数据资产下载、检查、修复、current contract 审计和 release 已从本仓库 sunset。相关能力由 `market-data-platform` 统一承载；本仓库只保留研究侧 provider runtime、本地资产消费，以及 `cstree data ...` / `cstree universe ...` 兼容入口。

旧 RQData asset CLI、HK current refresh shell wrappers、HK health shell wrappers、HK asset workflow driver、asset package 模块和 asset release 模块不再属于本仓库。需要准备或校验 HK daily、PIT、valuation、industry、intraday、current contract 或 release 资产时，先在 `market-data-platform` 执行数据平台命令，再把生成的文件路径写入本仓库配置。

## HK + RQData 高频回归

涉及 HK + RQData research provider、PIT flat file 消费或 universe 逻辑时，建议至少覆盖：

```bash
scripts/dev/run_tests.sh all tests/test_pipeline_validation.py tests/test_summarize_runs.py tests/test_pipeline_filters_*.py tests/test_fundamentals_providers.py tests/test_universe_tools.py tests/test_cli_core.py tests/test_cli_research.py tests/test_cli_liveops.py tests/test_linear_sweep.py tests/test_data_providers_cache.py -q
```

### 季度 provider 与 PIT 路线测试重点

如果修改季度 PIT 配置或底层 pipeline 逻辑，重点关注：`tests/test_pipeline_validation.py`、`tests/test_pipeline_filters_*.py`、`tests/test_fundamentals_providers.py`、`tests/test_universe_tools.py`、`tests/test_cli_research.py`、`tests/test_linear_sweep.py`、`tests/test_data_providers_cache.py` 和 `tests/test_summarize_runs.py`。

## 修改模块与对应测试指南

不确定最小验证范围时，先用 test-impact helper 按改动路径生成建议命令，再决定是否补跑
`all`、`slow` 或 integration：

```bash
python scripts/dev/test_impact.py src/cstree/pipeline/runner.py docs/dev.md
python scripts/dev/test_impact.py --json src/cstree/release_tools/package_runs.py
```

| 修改范围 | 提交前至少运行 | 建议补充 |
| --- | --- | --- |
| CLI 命令行、参数解析、wrapper 转发 | `tests/test_cli_core.py`、`tests/test_cli_research.py`、`tests/test_cli_liveops.py` | `scripts/dev/run_tests.sh fast` |
| 文档、README.md、docs/、workflow 说明 | `tests/test_docs_contracts.py`、`tests/test_repo_path_references.py`、`tests/test_run_tests_script.py`、`tests/test_data_ops_boundary.py` | `scripts/dev/run_tests.sh fast` |
| `scripts/dev/run_tests.sh`、CI 测试入口 | `tests/test_run_tests_script.py`、`tests/test_docs_contracts.py` | `fast` / `slow` / `integration`，或相关 smoke 测试 |
| release_tools 打包或 Release 预演 | `tests/test_run_release_scripts.py` | 运行结果打包 / 发布脚本的最小 smoke 测试 |
| `cstree data query`、metadata catalog、standardized layer | `tests/test_data_warehouse.py`、`tests/test_cli_core.py`；平台本体看 market-data-platform 的 `tests/test_data_warehouse.py` | `cstree data query --sql "select 1 as value"` |
| 数据运维边界、platform wrapper、HK universe wrapper | `tests/test_data_ops_boundary.py`、`tests/test_data_warehouse.py`、`tests/test_universe_tools.py`、`tests/test_hk_intraday_download.py` | `scripts/dev/run_tests.sh data-ops-boundary` |
| alloc-hk、liveops-hk、xlsx 输出 | `tests/test_alloc_hk.py`、`tests/test_cli_liveops.py` | 安装 `uv sync --extra dev --extra liveops-hk` 后跑 xlsx 最小 smoke |
| HK + RQData provider、PIT fundamentals、universe | `tests/test_pipeline_validation.py`、`tests/test_pipeline_filters_*.py`、`tests/test_fundamentals_providers.py`、`tests/test_universe_tools.py`、`tests/test_data_providers_cache.py` | `tests/test_summarize_runs.py`、`tests/test_linear_sweep.py` |
| intraday 研究、provider overlay audit、financial details | `tests/test_hk_intraday_download.py`、`tests/test_audit_provider_valuation.py`、`tests/test_hk_financial_details_analysis.py` | 按对应 playbook 跑最小 smoke |

## 提交前检查建议

1. 至少运行一次 `scripts/dev/run_tests.sh all`。
2. 如果改了配置或 pipeline，运行一次对应的 `cstree run --config ...`。
3. 检查 `README.md` 与 `docs/` 是否需要同步更新。

## 贡献入口

提交 PR 时，请说明：

1. 变更动机与影响范围。
2. 新增或修改的配置项。
3. 回归验证方式，包括测试命令和关键产物。
