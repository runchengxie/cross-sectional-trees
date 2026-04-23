# 维护债 Inventory

本页解决什么：记录结构老化、兼容层、命令胶水、大模块、维护脚本和静态治理债务的基线与处理顺序。\
本页不解决什么：不作为用户路线图，也不直接承诺删除公开功能。\
适合谁：维护 CLI、pipeline、RQData 资产、release 流程和开发治理的人。\
读完你会得到什么：哪些候选能删、哪些只能收口、哪些应该先拆，以及每一步需要怎样验证。\
相关页面：`docs/internal/feature-planning.md`、`docs/capabilities.md`、`docs/dev.md`、`scripts/README.md`

页面性质：`internal-inventory`\
最后核对时间：`2026-04-23`

## 使用规则

* 先判定入口分层，再判定是否可删；不在新手入口里，不等于废弃。
* 删除前必须有 repo-local usage audit、文档引用检查、替代路径和测试覆盖。
* 大模块拆分优先按职责边界拆，不按行数平均切文件。
* 静态治理走 ratchet：先约束触碰文件，再逐步减少历史豁免。
* RQData 大资产检查默认不在代理会话里重扫；需要时由维护者本地生成 report 后复核。

## 当前基线

生成时间：2026-04-23。统计范围为 `src/`、`scripts/`、`tests/` 下排除 `__pycache__` 的 Python 文件。

| 指标 | 当前值 | 说明 |
| --- | ---: | --- |
| Python 文件数 | 240 | 包括源码、脚本和测试 |
| Python 总行数 | 87,527 | 仅静态行数，用作趋势参考 |
| 超过 100 字符的行 | 1,223 | Markdown 不计入 |
| 超过 100 行的函数 | 169 | 包含测试函数 |
| 超过 250 行的函数 | 31 | 优先关注实现代码 |
| `C901` 文件级豁免 | 34 | 见 `pyproject.toml` |

### 本轮前后对比

本轮完成后重新统计同一范围：

| 指标 | 初始基线 | 本轮后 | 变化 |
| --- | ---: | ---: | ---: |
| Python 文件数 | 240 | 245 | +5 |
| Python 总行数 | 87,527 | 87,895 | +368 |
| 超过 100 字符的行 | 1,223 | 1,182 | -41 |
| 超过 100 行的函数 | 169 | 166 | -3 |
| 超过 250 行的函数 | 31 | 29 | -2 |
| `C901` 文件级豁免 | 34 | 34 | 0 |

行数增加主要来自把大函数抽成新 helper / rendering / path 模块，以及新增回归覆盖；
长行和超大函数数量下降。`C901` 豁免没有新增，也暂时没有移除，因为首轮拆分后的
5 个原始大文件仍有真实复杂函数命中。

### 最大实现文件

| 行数 | 文件 | 类别 | 初步处理 |
| ---: | --- | --- | --- |
| 2,328 | `src/cstree/release_tools/hk_asset_workflow.py` | release orchestration | 按 stage planning、command construction、report collection 拆 |
| 2,304 | `src/cstree/data_tools/rqdata_assets/asset_health.py` | RQData health inspection | 先拆 report rendering 或 scan aggregation |
| 1,689 | `src/cstree/data_tools/rqdata_assets/coverage.py` | RQData PIT coverage | 先拆 text rendering 或 trainable grid |
| 1,312 | `src/cstree/data_tools/rqdata_assets/audit_assets.py` | RQData asset audit | 后续纳入第二批 |
| 1,280 | `src/cstree/research/summarize_runs.py` | research summary | 暂不作为首批删除或拆分目标 |
| 1,232 | `src/cstree/data_tools/rqdata_assets/build.py` | RQData asset build | 先拆 PIT universe filtering 或 path resolution |
| 1,199 | `src/cstree/pipeline/eval.py` | pipeline evaluation | 先拆 period evaluation 或 walk-forward helpers |
| 1,164 | `src/cstree/data_providers.py` | provider boundary | 先保持稳定，避免同时改 provider 行为 |

### 首轮大模块拆分记录

2026-04-23 已完成第一轮行为保持拆分，优先抽纯渲染、路径解析和公开复用 helper：

| 原文件 | 新边界 | 当前状态 | `C901` 处理 |
| --- | --- | --- | --- |
| `src/cstree/data_tools/rqdata_assets/asset_health.py` | `asset_health_rendering.py` | 主文件约 2,102 行；渲染模块 225 行 | 原文件仍有 6 个 C901 命中，豁免保留 |
| `src/cstree/data_tools/rqdata_assets/coverage.py` | `coverage_rendering.py` | 主文件约 1,416 行；渲染模块 313 行 | 原文件仍有 3 个 C901 命中，豁免保留 |
| `src/cstree/data_tools/rqdata_assets/build.py` | `build_paths.py` | 主文件约 1,215 行；路径模块 29 行 | 原文件仍有 4 个 C901 命中，豁免保留 |
| `src/cstree/pipeline/eval.py` | `eval_benchmark.py` | 主文件约 1,098 行；benchmark 模块 117 行 | 原文件仍有 2 个 C901 命中，豁免保留 |
| `src/cstree/release_tools/hk_asset_workflow.py` | `hk_asset_workflow_paths.py` | 主文件约 2,244 行；path/model 模块 186 行 | 原文件仍有 4 个 C901 命中，豁免保留 |

校验命令：`.venv/bin/ruff check --isolated --select C901 ...`。本轮没有新增复杂度豁免；
`command_registry.py` 和 `cli/liveops.py` 不需要 `C901` 文件级豁免。下一轮应优先拆仍命中的
entrypoint 函数，而不是再抽常量。

### 最大函数

| 行数 | 函数 | 文件 | 初步处理 |
| ---: | --- | --- | --- |
| 762 | `inspect_hk_asset_health` | `src/cstree/data_tools/rqdata_assets/asset_health.py` | 拆扫描、汇总、渲染 |
| 599 | `run_train_eval_stage` | `src/cstree/pipeline/train_eval_stage.py` | 第二批，先不和 eval 同时改 |
| 536 | `run` | `src/cstree/pipeline/runner.py` | 先移除 legacy re-export 依赖，再拆 orchestration |
| 523 | `_evaluate_period` | `src/cstree/pipeline/eval.py` | 拆 period context、scoring、report payload |
| 426 | `backtest_topk` | `src/cstree/backtest.py` | 第二批，需回测回归覆盖 |
| 413 | `resolve_runtime_settings` | `src/cstree/pipeline/config.py` | 和 config compatibility 一起小步处理 |
| 408 | `build_run_summary_sections` | `src/cstree/pipeline/output_summary_sections.py` | 后续拆 summary section builders |

## 首批候选

| 候选 | 类别 | repo-local usage | 文档/公开面 | 风险 | 建议动作 | 验证 |
| --- | --- | --- | --- | --- | --- | --- |
| `src/cstree/pipeline/data.py` | compatibility shim | `pipeline/runner.py` 仍从它导入 | 无公开文档入口 | 低 | 先把 repo 内部导入改到 canonical 模块；保留 shim 或删除需单独决定 | `tests/test_pipeline_runtime.py`、`tests/test_pipeline_e2e.py` 或相关 pipeline 快测 |
| `src/cstree/compat.py` | dependency compatibility | `pipeline/data.py`、`panel_loader.py`、`feature_dataset.py` 使用 `ensure_numpy_nan_alias` | 无公开文档入口 | 中 | 保留到确认 `pandas_ta` / NumPy 组合不再需要；避免散落更多调用 | `tests/test_pipeline_filters_core.py`、`tests/test_transform.py` |
| legacy `universe` config key | config compatibility | `config_utils.py` 规范到 `research_universe` | `docs/config.md` 明示仍兼容 | 中 | 先保持兼容；集中测试 canonical、legacy、conflict 三类行为 | `tests/test_config_utils.py` |
| `ts_code` / `stock_ticker` aliases | symbol compatibility | `data_tools/symbols.py`、RQData asset tools、liveops readers 多处接受 | `docs/providers.md`、`docs/outputs.md` 明示历史输入兼容 | 中 | 只在边界层接受，输出继续收敛到 `symbol`；暂不删除 | `tests/test_symbol_alias.py`、`tests/test_data_providers_cache.py` |
| `scripts/internal/run_hk_asset_workflow.py` | maintainer driver | `scripts/dev/refresh_hk_current.sh`、`scripts/dev/run_hk_health_checks.sh`、测试引用 | `scripts/README.md`、`docs/dev.md`、RQData health docs 引用 | 中 | 保留为 driver；如要删，先提供 `python -m cstree.release_tools.hk_asset_workflow` 替代文档 | `tests/test_refresh_hk_current_script.py`、`tests/test_run_release_scripts.py` |
| `scripts/internal/package_repo.sh` | maintainer helper | `tests/test_package_repo_script.py` 覆盖 | 未列入公开 CLI | 低 | 保留并标注为 private helper；不进入首批删除 | `tests/test_package_repo_script.py` |
| `scripts/internal/export_repo_source.py` | maintainer helper | 生成 `full_project_source.txt`；当前无直接测试引用 | 仅维护者辅助 | 低 | 标注为 private helper；后续按使用频率决定是否保留 | 文档路径检查 |

## 入口分层标记

| 分层 | 代表入口 | 处理原则 |
| --- | --- | --- |
| 公开主线 CLI | `cstree run`、`cstree rqdata ...`、`cstree universe ...`、`cstree alloc-hk` | 不做 breaking 改动，除非另开迁移说明 |
| 公开但非 CLI 模块工具 | `python -m cstree.release_tools.package_assets`、`python -m cstree.release_tools.release_runs` | 不是新手入口，但仍是公开分发工具 |
| 专题研究模块 | `python -m cstree.research.hk_financial_details` 等 | 不因低频使用直接删除；先看 playbook 和研究笔记引用 |
| 维护与开发辅助 | `scripts/dev/run_tests.sh`、`scripts/internal/` | 可收口，但要保留维护者替代路径 |

## RQData 命令层基线

| 文件 | 行数 | 当前职责 | 问题 |
| --- | ---: | --- | --- |
| `src/cstree/data_tools/rqdata_assets/command_registry.py` | 约 350 | command spec、默认值、runner 注册 | 第一阶段已去掉 `_add_*_args` 薄包装，默认值集中到 argument builder |
| `src/cstree/data_tools/rqdata_assets/args.py` | 915 | 非 mirror 命令参数 | 参数构造和默认值分散 |
| `src/cstree/data_tools/rqdata_assets/args_mirror.py` | 493 | mirror 命令参数 | 多个 mirror 命令重复转发相同默认值 |
| `src/cstree/data_tools/rqdata_assets/public_api.py` | 511 | 测试和程序化使用 facade | 导出 67 个名字，包含大量 private helpers |
| `src/cstree/data_tools/rqdata_assets/__init__.py` | 41 | package facade | 动态转抄 `public_api`，边界不够显式 |

首批目标是让新增或修改命令时主要看一个 command spec 声明；共享 argument builder 只在确实减少重复时保留。后续再判断 `public_api.py` 和 package facade 的 private helper 导出边界。

## Static Quality Ratchet

当前 `pyproject.toml` 只启用 `E9`、`F821`、`F822`、`F823`、`C90`，并设置 `line-length = 100`。后续阶段按下面顺序推进：

1. 对触碰文件不新增长行、未使用导入或新的 `C901` 豁免。
2. 每拆一个大模块，尝试移除或减少对应 `C901` 豁免。
3. 使用 `docs/dev.md` 中的本地统计片段记录大文件、大函数、长行和复杂度豁免趋势。
4. `scripts/dev/run_tests.sh lint` 已对改动 Python 文件追加 import 排序和新增长行检查。
5. 再评估是否把更多 Ruff 规则纳入 `scripts/dev/run_tests.sh lint`。

## 建议验证矩阵

| 改动范围 | 首选验证 |
| --- | --- |
| config compatibility | `uv run pytest tests/test_config_utils.py -q` |
| symbol compatibility | `uv run pytest tests/test_symbol_alias.py tests/test_data_providers_cache.py -q` |
| pipeline import / runner | `uv run pytest tests/test_pipeline_runtime.py tests/test_pipeline_filters_core.py -q` |
| RQData command registry | `uv run pytest tests/test_cli_rqdata.py tests/rqdata_assets/test_request_groups.py -q` |
| RQData asset health / coverage / build | `uv run pytest tests/rqdata_assets/ -q` |
| liveops CLI | `uv run pytest tests/test_cli_liveops.py tests/test_alloc.py tests/test_alloc_hk.py -q` |
| release workflow helpers | `uv run pytest tests/test_hk_asset_workflow.py tests/test_run_release_scripts.py -q` |
| docs/path changes | `uv run pytest tests/test_docs_contracts.py tests/test_repo_path_references.py -q` |

## 剩余决策

* legacy `universe` 和 legacy symbol aliases 暂不设置移除窗口；当前只在边界层保留兼容。
* `cstree.pipeline.data` 暂时保留为短期外部导入兼容 shim；repo 内部已改用 canonical 模块。
* `scripts/internal/run_hk_asset_workflow.py` 暂时保留为维护者 driver / 兼容 wrapper；两个 dev 脚本仍引用它。
* `public_api.py` 已先收窄 package facade；下一轮继续判断哪些 private helper 应改成模块内测试或真实 public API。
