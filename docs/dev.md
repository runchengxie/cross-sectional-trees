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
| 维护 HK / RQData 本地资产 | HK 资产健康检查脚本、HK 资产维护 Driver |
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
uv run pytest tests/test_metrics.py

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

# 轻量校验 C901 豁免是否登记在维护债 inventory
scripts/dev/run_tests.sh c901-debt

# 输出维护债静态指标；可加 --json 或 --markdown
scripts/dev/run_tests.sh maintainability

# 全仓库 import 排序检查；历史文件可能仍有遗留问题
scripts/dev/run_tests.sh imports

# 只检查本次改动的 Python 文件格式
scripts/dev/run_tests.sh format

# 全仓库格式检查；历史文件可能仍有遗留问题
scripts/dev/run_tests.sh format-all

# 真实 provider 在线联调，需要显式开启并配置 token 或账号
CSTREE_RUN_PROVIDER_INTEGRATION=1 uv run pytest tests/test_provider_integration.py -m integration
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
| `pre-commit` | `uv run pytest tests/test_docs_contracts.py tests/test_repo_path_references.py tests/test_run_tests_script.py -q` | 提前发现文档契约、路径引用和测试入口问题 |
| `pre-push` | `scripts/dev/run_tests.sh fast` | 推送前跑快回归 |

说明：

* 本地 hook 用来提前发现问题，不能替代远端 CI。
* 特殊情况下可以用 `git commit --no-verify` 或 `git push --no-verify` 跳过。
* Ruff 已启用 formatter、import 排序和基础复杂度检查。`lint` 会拦截高风险语法错误、新增高复杂函数，并检查本次改动的 Python import 排序、未使用 import、未使用变量、lambda / closure late-binding 风险和新增 Python 长行。
* 历史 import 和 format 遗留问题可用 `imports`、`format-all` 单独盘点。
* 已知复杂度历史债务记录在 `pyproject.toml` 的 `per-file-ignores`，并在内部维护债清单里按 owner area、原因、验证命令和退出条件登记。完成拆分优化后，应逐个撤销豁免。
* 触碰 Python 文件时，不要新增超过 100 字符的代码行或新的 `C901` 文件级豁免；如果豁免仍不能撤销，要在内部维护债清单里记录原因。`lint` 会在新增 `C901` ignore 但未同步维护债清单时失败，并额外校验当前豁免是否都在维护债清单登记。
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

CI 配置在 `.github/workflows/tests.yml`。默认拆成七个 job：

1. `fast`：运行 `scripts/dev/run_tests.sh fast`。
2. `slow`：运行 `scripts/dev/run_tests.sh slow`。
3. `integration`：运行 `scripts/dev/run_tests.sh integration`。
4. `rqdata-extra-smoke`：安装 `--extra rqdata`，验证导入和 `cstree rqdata --help`。
5. `duckdb-extra-smoke`：安装 `--extra duckdb`，验证最小 DuckDB query 执行。
6. `liveops-hk-extra-smoke`：安装 `--extra liveops-hk`，验证 xlsx 文件的基本写入能力。
7. `stats-extra-smoke`：安装 `--extra stats`，验证 `scipy` 和 `summarize_ic`。

可选依赖冒烟检查（optional extra smoke）只验证额外依赖能安装、能导入、能完成最小调用。它们不替代主测试集。

本地模拟 CI 强度时，除了 `all` / `fast` / `slow` / `integration`，还要手动跑下面四组：

```bash
# rqdata-extra-smoke
uv sync --locked --extra dev --extra rqdata
uv run python -c "import rqdatac; print(rqdatac.__name__)"
uv run cstree rqdata --help > /dev/null

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

## HK 资产健康检查脚本

这一节面向维护 HK current 资产的人。普通代码开发通常不需要跑这些命令。

日常维护优先用轻量封装脚本：

```bash
bash scripts/dev/refresh_hk_current.sh --target-date 20260410
```

默认行为：

* 只执行刷新和检查，不会自动打包或发布 GitHub Release。
* 使用 `--refresh-mode patch`，也就是只抓尾部增量窗口，再在本地合并。
* 默认带上 `--resume`、`--gate-on-severity warning` 和 `--inspect-fail-on-severity none`。
* 检查结果达到阻断阈值时，底层 workflow 会阻止 `latest/current` 别名放行，并以非零状态退出。

常见变体：

```bash
# 检查通过后，额外打包当前资产 parts
bash scripts/dev/refresh_hk_current.sh --target-date 20260410 --with-package

# 重要时间点，把 current 状态冻结为本地备份
bash scripts/dev/refresh_hk_current.sh \
  --target-date 20260410 \
  --backup-name hk_current_frozen_20260410

# 只刷新支持 patch 模式的部分资产
bash scripts/dev/refresh_hk_current.sh \
  --target-date 20260410 \
  -- --refresh-asset daily --refresh-asset valuation
```

这个脚本是 `scripts/internal/run_hk_asset_workflow.py` 的保守封装。需要完整重拉、修复、release 发布或细分 parts 控制时，再直接调用维护者 driver。

只想把 HK 与 RQData 健康检查跑完并归档到 `artifacts/reports/` 时，用：

```bash
bash scripts/dev/run_hk_health_checks.sh --target-date 20260409
```

常见变体：

```bash
# 加跑 intraday 分钟线检查
bash scripts/dev/run_hk_health_checks.sh --target-date 20260409 --with-intraday

# 额外生成维护者视角的 workflow inspect report
bash scripts/dev/run_hk_health_checks.sh --target-date 20260409 --with-workflow-inspect
```

说明：

* 这些脚本是本地运维和调试工具，不是面向最终用户的 `cstree` CLI 功能。
* 脚本会从 `artifacts/metadata/current_assets/hk_current.json` 读取当前 `daily_clean`、`valuation`、`intraday` 路径。
* 默认生成 `current`、`daily_clean`、`valuation`、`pit` 四份 JSON 健康报告。
* stdout 和 stderr 日志会放在 `artifacts/reports/health_logs/`。
* 手动命令和报告阅读顺序见 `docs/rqdata/hk-health-checks.md`。

综合审计 current contract 时，用：

```bash
bash scripts/dev/run_hk_data_asset_audit.sh --target-date 20260410
```

它会做资产清单、数据新鲜度、修复候选和删除预演审计。默认只读、dry-run，不会刷新、修复或删除实体数据。

如果确实要联动 patch refresh，先加 `--run-refresh` 保持 dry-run；确认无误后再加 `--refresh-execute` 执行实质变更。

## HK 资产维护 Driver

这一节面向 HK 市场与 RQData 数据资产维护者。它比上一节脚本更底层，也更容易触发重 I/O 操作。

基础命令：

```bash
python scripts/internal/run_hk_asset_workflow.py --target-date 20260402
```

默认包含三阶段：

* `refresh`：刷新 `instruments / daily / daily_clean / valuation / ex_factors / dividends / shares / industry_changes / southbound` 等资产。
* `inspect`：运行健康诊断，并把报告写入 `artifacts/reports/`。
* `package`：把本次 resolved snapshot 交给 `cstree.release_tools.package_assets` 打包。

常见变体：

```bash
# 只预览执行计划
python scripts/internal/run_hk_asset_workflow.py --target-date 20260402 --dry-run

# 从中断处继续镜像拉取，跳过检查和打包
python scripts/internal/run_hk_asset_workflow.py --phase refresh --target-date 20260402 --resume

# 日常增量刷新：只抓尾部窗口，再合并为新的 snapshot
python scripts/internal/run_hk_asset_workflow.py --phase refresh --target-date 20260402 --refresh-mode patch --resume

# 使用上一轮 inspect 的 repair_candidates，重拉 warning/error 子集
python scripts/internal/run_hk_asset_workflow.py --phase repair --target-date 20260402 --repair-asset daily

# 关闭严重级别门控，只记录 inspect 报告
python scripts/internal/run_hk_asset_workflow.py --target-date 20260402 --gate-on-severity none

# 基于现有 package 追加 GitHub release 发布
python scripts/internal/run_hk_asset_workflow.py --phase release --target-date 20260402 --repo owner/name --prerelease
```

关键概念：

* 维护者 driver 不是公开业务 CLI。
* 它主要负责编排；真实抓取、检查、打包和发布逻辑仍落在各自独立命令里。
* `refresh` 成功后，默认会把 `latest` alias 指向新资产。只想保留 dated snapshot 时，加 `--no-repoint-latest`。
* `--refresh-mode full` 表示整包重拉。
* `--refresh-mode patch` 表示增量补丁刷新（patch refresh）：先拉近期数据补丁，再用补丁合并（patch merge）生成新的 canonical snapshot。
* patch 默认回溯：`daily` 20 个日历日，其他支持增量的 dated assets 40 个日历日。可用 `--daily-patch-lookback-days` 和 `--dated-patch-lookback-days` 调整。
* 非 dry-run 执行会写结构化 workflow report，默认路径是 `artifacts/reports/hk_asset_refresh_<target_date>.json`。
* 非 dry-run workflow 还会刷新 `artifacts/metadata/current_assets/hk_current.json`，记录当前 alias、resolved snapshot、manifest 摘要和 `as_of`。
* 默认 `--gate-on-severity warning`。如果 inspect 达到阈值，`latest` alias 重新指派、package 和 release 会被拦截。
* 单独跑 `inspect` 时，通常只生成报告，不触发后续门控推进。
* `repair` 会读取 workflow report 中的 `inspect.assets.<asset>.repair_candidates`，按 `symbol/date` 精简后重拉问题子集，并执行 patch merge。
* `repair` 默认处理 `warning` 和 `error`。需要包含 `info` 时，用 `--repair-min-severity`。
* `repair` 默认会跑 `post_repair` 复检。后续是否放行 alias、package 或 release，以复检结果为准。
* `repair` 会额外写两份简明 JSON：`artifacts/reports/hk_asset_repair_queue_<target_date>.json` 和 `artifacts/reports/hk_asset_remaining_repair_candidates_<target_date>.json`。
* 只处理上一轮 repair 后仍未解决的候选项时，用 `--repair-only-unresolved`。

推荐排障顺序：

1. 先跑一轮包含 `inspect` 的 workflow，拿到完整 report。
2. 再单独跑 `--phase repair`，按报告里的候选项修复。
3. 等 `post_repair` 复检通过后，再考虑 alias、package 或 release。

## HK + RQData 高频回归

涉及 HK + RQData 重构时，建议至少覆盖：

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

### 季度 provider 与 PIT 路线测试重点

如果修改这些配置或底层 pipeline 逻辑，需要重点关注下列测试：

* `configs/experiments/baseline/hk_selected__quarterly_price_only.yml`
* `configs/experiments/baseline/hk_selected__quarterly_pit_core.yml`
* `configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml`
* `configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_*.yml`
* `configs/experiments/variants/hk_selected__pit_quarterly_financial_ml.yml`
* `configs/experiments/variants/hk_selected__pit_quarterly_financial_linear.yml`
* `configs/experiments/variants/hk_selected__pit_quarterly_hybrid.yml`

测试说明：

1. `tests/test_pipeline_validation.py`：校验季度模板中 `label/eval/backtest.rebalance_frequency` 是否一致，以及 `fundamentals.source` 是否设置正确。
2. `tests/` 下的 `test_pipeline_filters_*.py`：覆盖 provider/file 基本面合并、PIT 文件读取、披露日后 `ffill`、慢财报派生因子。
3. `tests/test_fundamentals_providers.py`：验证 HK + RQData provider 基本面抓取、标准化和缓存键。
4. `tests/rqdata_assets/`：验证 `mirror-hk-pit-financials`、`build-hk-pit-fundamentals`、覆盖率和健康检查预处理。
5. `tests/test_universe_tools.py`：验证港股通 universe 的日期 token、输出路径和流动性筛选边界。
6. `tests/test_cli_rqdata.py` 和 `tests/test_cli_research.py`：验证 PIT 资产命令和 `sweep-linear` 参数解析。
7. `tests/test_linear_sweep.py`：验证季度 PIT 线性 sweep 配置读取，以及生成 jobs 和 base config。
8. `tests/test_data_providers_cache.py`：验证 RQData 日线缓存、上市日裁剪和空区间处理。
9. `tests/test_summarize_runs.py`：验证 `summary.json` 下游汇总字段，尤其是 `backtest.active` benchmark 指标能否进入 `runs_summary.csv`。

## 修改模块与对应测试指南

不确定最小验证范围时，先用 test-impact helper 按改动路径生成建议命令，再决定是否补跑
`all`、`slow` 或 integration：

```bash
python scripts/dev/test_impact.py src/cstree/pipeline/runner.py docs/dev.md
python scripts/dev/test_impact.py --json src/cstree/data_tools/rqdata_assets/asset_health.py
```

| 修改范围 | 提交前至少运行 | 建议补充 |
| --- | --- | --- |
| CLI 命令行、参数解析、wrapper 转发 | `tests/test_cli_core.py`、`tests/test_cli_rqdata.py`、`tests/test_cli_research.py`、`tests/test_cli_liveops.py` | `scripts/dev/run_tests.sh fast` |
| 文档、README.md、docs/、workflow 说明 | `tests/test_docs_contracts.py`、`tests/test_repo_path_references.py`、`tests/test_run_tests_script.py` | `scripts/dev/run_tests.sh fast` |
| `scripts/dev/run_tests.sh`、CI 测试入口 | `tests/test_run_tests_script.py`、`tests/test_docs_contracts.py` | `fast` / `slow` / `integration`，或相关 smoke 测试 |
| release_tools 打包或 Release 预演 | `tests/test_asset_release_scripts.py`、`tests/test_run_release_scripts.py` | 相关脚本的最小打包 smoke 测试 |
| `cstree data query`、metadata catalog、standardized layer | `tests/test_data_warehouse.py`、`tests/test_cli_core.py` | `cstree data query --sql "select 1 as value"` |
| alloc-hk、liveops-hk、xlsx 输出 | `tests/test_alloc_hk.py`、`tests/test_cli_liveops.py` | 安装 `uv sync --extra dev --extra liveops-hk` 后跑 xlsx 最小 smoke |
| HK + RQData provider、PIT fundamentals、universe | `tests/test_pipeline_validation.py`、`tests/test_pipeline_filters_*.py`、`tests/test_fundamentals_providers.py`、`tests/rqdata_assets/`、`tests/test_universe_tools.py`、`tests/test_data_providers_cache.py` | `tests/test_summarize_runs.py`、`tests/test_linear_sweep.py` |
| intraday、patch merge、provider overlay audit、financial details | `tests/test_hk_intraday_download.py`、`tests/test_hk_intraday_tools.py`、`tests/test_hk_asset_patch_merge.py`、`tests/test_audit_provider_valuation.py`、`tests/test_hk_financial_details_analysis.py` | 按对应 playbook 跑最小 smoke |

## 提交前检查建议

1. 至少运行一次 `scripts/dev/run_tests.sh all`。
2. 如果改了配置或 pipeline，运行一次对应的 `cstree run --config ...`。
3. 检查 `README.md` 与 `docs/` 是否需要同步更新。

## 贡献入口

提交 PR 时，请说明：

1. 变更动机与影响范围。
2. 新增或修改的配置项。
3. 回归验证方式，包括测试命令和关键产物。
