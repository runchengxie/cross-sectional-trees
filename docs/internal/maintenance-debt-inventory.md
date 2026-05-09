# 维护债 Inventory

本页解决什么：记录结构老化、兼容层、命令胶水、大模块、维护脚本和静态治理债务的基线与处理顺序。\
本页不解决什么：不作为用户路线图，也不直接承诺删除公开功能。\
适合谁：维护 CLI、pipeline、RQData 资产、release 流程和开发治理的人。\
读完你会得到什么：哪些候选能删、哪些只能收口、哪些应该先拆，以及每一步需要怎样验证。\
相关页面：`docs/internal/feature-planning.md`、`docs/capabilities.md`、`docs/dev.md`、`scripts/README.md`

页面性质：`internal-inventory`\
当前状态：`active-maintenance-inventory`\
最后核对时间：`2026-05-09`

## 当前状态摘要

本页同时包含四类内容：

* historical baseline：2026-04-23 / 2026-04-27 的维护债静态盘点快照。
* completed work：已经完成的首轮收口、拆分、兼容治理和验证记录。
* active backlog：仍建议继续推进的维护项。
* deferred decisions：当前不默认推进删除的兼容层、legacy 输入和维护者 wrapper。

当前优先推进的是降低未来改动风险的维护工作：继续拆大函数 / 大模块、推进静态质量
ratchet、在触碰 RQData asset 模块时收窄 public facade。兼容层删除不是本页默认任务；
只有在 breaking release 规划、外部风险确认或替代路径齐备后再单独处理。

## 使用规则

* 先判定入口分层，再判定是否可删；不在新手入口里，不等于废弃。
* 删除前必须有 repo-local usage audit、文档引用检查、替代路径和测试覆盖。
* 大模块拆分优先按职责边界拆，不按行数平均切文件。
* 静态治理走 ratchet：先约束触碰文件，再逐步减少历史豁免。
* RQData 大资产检查默认不在代理会话里重扫；需要时由维护者本地生成 report 后复核。

## 当前静态快照

生成时间：2026-05-09。统计命令：
`python scripts/dev/maintainability_metrics.py --json --limit 14`。统计范围为 `src/`、`scripts/`、
`tests/` 下排除 `__pycache__` 的 Python 文件；此快照只用于趋势判断，不代表实时仪表盘。

| 指标 | 当前值 | 说明 |
| --- | ---: | --- |
| Python 文件数 | 264 | 包括源码、脚本和测试 |
| Python 总行数 | 100,117 | 仅静态行数，用作趋势参考 |
| 超过 100 字符的行 | 1,194 | Markdown 不计入 |
| 超过 100 行的函数 | 184 | 包含测试函数 |
| 超过 250 行的函数 | 23 | 优先关注实现代码 |
| 超过 500 行的函数 | 0 | 需要单独跟踪的超大函数 |
| `C901` 文件级豁免 | 21 | 见 `pyproject.toml` |
| `rqdata public_api.__all__` | 49 | 稳定 facade 导出名数量 |

当前已经没有超过 500 行的 Python 函数。最大函数仍集中在 RQData mirror、通用
pipeline walk-forward eval、release 编排和 CLI / asset health 入口；
下一轮应继续按职责拆分，不把 import sorting、unused import 或 pyupgrade 清理混进行为保持重构。

### 2026-05-06 maintainability governance apply

`strengthen-maintainability-governance` 落地了维护治理层，而不是一次性重写核心业务：

| 范围 | 结果 | 验证 |
| --- | --- | --- |
| C901 registry | 新增结构化 registry；`mirror_financial.py` 在 lint 中暴露为既有未登记复杂度，已登记为第 35 个文件级豁免 | `python scripts/dev/check_c901_debt.py` |
| test-impact helper | 新增按改动 path 推荐 focused verification 的 helper 和覆盖测试 | `uv run pytest tests/test_dev_test_impact.py tests/test_c901_debt_check.py -q` |
| run-tests ratchet | `lint` 串接 registry 校验，保留 touched-file import / unused / `B023` / 长行 ratchet | `scripts/dev/run_tests.sh lint` |
| maintainability metrics | 新增只读维护指标脚本，避免后续大文件 / 大函数 / facade 数量靠手写片段维护 | `scripts/dev/run_tests.sh maintainability --json --limit 5` |
| CLI parser test split | 将 `tests/test_cli_rqdata.py` 的 749 行单体 parser 测试按命令族拆分；`>500` 函数从 5 降到 4 | `uv run pytest tests/test_cli_rqdata.py -q` |
| asset health postprocess extraction | 将 `inspect_hk_asset_health` 的 field coverage 汇总和 payload/render/write 后处理抽成 helper；`>500` 函数从 4 降到 3 | `uv run pytest tests/rqdata_assets/test_asset_health_quality.py tests/rqdata_assets/test_asset_health_current.py tests/rqdata_assets/test_asset_health_history.py -q` |
| PIT patch manifest extraction | 将 `patch_hk_pit_financials` 的 resume 校验和 manifest/totals 构造抽成 helper；`>500` 函数从 3 降到 2 | `uv run pytest tests/rqdata_assets/test_mirror_financial.py -q` |
| first-priority orchestration extraction | 拆 `runner.py` legacy output handoff、`train_eval_stage.py` period/walk-forward context、asset health reference/stat init、PIT patch request context；`>500` 函数从 2 降到 0 | `uv run pytest tests/test_pipeline_train_eval_contracts.py tests/test_modeling.py tests/test_split.py tests/test_pipeline_runtime.py tests/test_pipeline_filters_core.py tests/rqdata_assets/test_asset_health_quality.py tests/rqdata_assets/test_asset_health_current.py tests/rqdata_assets/test_asset_health_history.py tests/rqdata_assets/test_mirror_financial.py -q` |
| ETF daily audit | 将 `verify_etf_daily_completeness` 的 missing/stale/start-gap 检查抽成 helper，避免给 `audit_assets.py` 新增豁免 | `.venv/bin/ruff check --select C901 src/cstree/data_tools/rqdata_assets/audit_assets.py` |
| public surface / refactor contract docs | 明确入口变更要求、行为保持拆分边界、重数据验证规则和下一批抽取目标 | `uv run pytest tests/test_docs_contracts.py tests/test_repo_path_references.py tests/test_run_tests_script.py -q` |

### 2026-05-07 second-priority orchestration extraction

本轮继续处理上一轮列出的下一批目标，仍按行为保持拆分，不改变 CLI、artifact schema 或
provider 语义：

| 范围 | 结果 | 验证 |
| --- | --- | --- |
| southbound mirror context | 将 `mirror_hk_southbound` 的 symbols/date/trading type/output/request key 准备收口到 `_SouthboundMirrorContext`；同时修复 touched lint 暴露的 retry lambda 捕获 | `uv run pytest tests/rqdata_assets/test_mirror_industry.py -q` |
| generic mirror workflow context | 为 dated mirror 和 quarter mirror 分别新增 typed context helper，拆出参数、目录、request group、symbol map 和 retry active-field binding | `uv run pytest tests/rqdata_assets/test_mirror_daily.py tests/rqdata_assets/test_mirror_financial.py -q` |
| backtest setup context | 将 `backtest_topk` 的执行模型解析和 pricing table 准备抽为 helper，主函数只保留 rebalance loop 和 long/short accounting | `uv run pytest tests/test_backtest.py tests/test_execution_calendar.py -q` |
| asset health symbol scan state | 将 symbol parquet 读取、duplicate-date state updater、history state updater 抽出主检查循环；`inspect_hk_asset_health` 从 418 行降到 356 行 | `uv run pytest tests/rqdata_assets/test_asset_health_quality.py tests/rqdata_assets/test_asset_health_current.py tests/rqdata_assets/test_asset_health_history.py -q` |
| C901 removal pilot | 将 `train_eval_stage.py` 的 walk-forward evaluation 抽成 helper，isolated C901 清零并撤销该文件的 `C901` per-file ignore | `uv run pytest tests/test_pipeline_train_eval_contracts.py tests/test_modeling.py tests/test_split.py tests/test_pipeline_runtime.py tests/test_pipeline_filters_core.py -q` |
| thin C901 removal batch | 清理 `split.py`、`alloc_core.py`、`package_assets.py`、`release_assets.py` 的单命中 C901；当前文件级豁免从 34 降到 30 | `uv run pytest tests/test_split.py tests/test_asset_release_scripts.py tests/test_alloc.py tests/test_cli_liveops.py -q` |
| priority-line-2 pain-point extraction | 继续拆 `mirror_hk_southbound` resume/checkpoint/batch frame、`mirror_workflow` fetch policy/field fallback、`backtest_topk` rebalance/leg accounting、`asset_health` target-date field stats；`backtest.py` 撤销 C901，文件级豁免降到 29，长行降到 1,204 | `.venv/bin/python -m pytest tests/test_backtest.py tests/test_execution_calendar.py tests/rqdata_assets/test_mirror_industry.py tests/rqdata_assets/test_mirror_daily.py tests/rqdata_assets/test_mirror_financial.py tests/rqdata_assets/test_asset_health_current.py tests/rqdata_assets/test_asset_health_history.py tests/rqdata_assets/test_asset_health_quality.py -q` |
| priority-line-2 continuation | 继续拆 `mirror_workflow` writer/finalize、`mirror_hk_southbound` symbol writer/finalize、`asset_health` field resolver / quality checks、`pipeline/eval.py` walk-forward backtest；撤销 `asset_health.py` 和 `pipeline/eval.py` 的 C901，文件级豁免降到 27 | `.venv/bin/python -m pytest tests/rqdata_assets/test_mirror_industry.py tests/rqdata_assets/test_mirror_daily.py tests/rqdata_assets/test_mirror_financial.py tests/rqdata_assets/test_asset_health_current.py tests/rqdata_assets/test_asset_health_history.py tests/rqdata_assets/test_asset_health_quality.py tests/test_metrics.py tests/test_pipeline_e2e.py tests/test_pipeline_train_eval_contracts.py -q` |
| pipeline runner legacy removal | 删除未被 repo-local 调用的 `runner.py` private `_run_legacy` 路径和专用 locals handoff；当前 pipeline 只保留 `prepare_research_context()` + `run()` 主路径，`>250` 函数从 31 降到 30 | `python -m compileall -q src/cstree/pipeline/runner.py`; `scripts/dev/run_tests.sh lint`; `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_pipeline_runtime.py tests/test_pipeline_filters_core.py tests/test_pipeline_train_eval_contracts.py -q` |
| output context dataclass boundary | 将输出持久化入口的 flat dict handoff 收口为 `OutputContext` dataclass；保持 Mapping 兼容，先锁住 source 顺序和 override 语义 | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_output_context.py tests/test_pipeline_runtime.py tests/test_pipeline_filters_core.py tests/test_pipeline_train_eval_contracts.py -q`; `scripts/dev/run_tests.sh lint` |

### 2026-05-09 pipeline orchestration extraction

本轮按 summary section、artifact writer、runtime settings、panel loader、period eval
和通用 mirror workflow 子职责继续拆编排层，保持 `summary.json` schema、artifact 路径、
文件名、配置键、默认值、provider 语义和错误语义不变。`>250` 行函数从 30 降到 23；
`pipeline/output_summary_sections.py`、`pipeline/output_artifacts.py`、
`pipeline/config.py::resolve_runtime_settings`、`pipeline/panel_loader.py::_load_research_panel`、
`pipeline/eval.py::_evaluate_period`、`rqdata_assets/mirror_workflow.py::_mirror_dated_dataset`
和 `_mirror_dataset` 不再出现在最大函数列表中。`output_artifacts.py`、`config.py`、
`panel_loader.py`、`mirror_workflow.py`、`mirror_daily.py` 和 `mirror_financial.py`
isolated C901 已清零，并撤销对应 per-file ignore。

| 范围 | 结果 | 验证 |
| --- | --- | --- |
| summary section builders | 将 run/data/dataset/universe/label/split/eval/backtest/final_oos/positions/live/quality/fundamentals/industry/walk_forward 拆为私有 builder | `python -m py_compile src/cstree/pipeline/output_summary_sections.py`; `.venv/bin/ruff check src/cstree/pipeline/output_summary_sections.py`; `.venv/bin/python scripts/dev/maintainability_metrics.py --json --limit 10` |
| artifact writer groups | 将 dataset/scored、feature importance、eval series、OOS eval、backtest、OOS backtest、positions、auxiliary outputs 拆为私有 writer helper；撤销 `output_artifacts.py` 的 `C901` per-file ignore | `python -m py_compile src/cstree/pipeline/output_artifacts.py`; `.venv/bin/ruff check --isolated --select C901 src/cstree/pipeline/output_artifacts.py`; `scripts/dev/run_tests.sh c901-debt`; `.venv/bin/python scripts/dev/maintainability_metrics.py --json --limit 14` |
| runtime settings helpers | 将 fundamentals、industry、features、model/sample-weight/train-window、backtest/execution、live 配置归一化拆为私有 helper；撤销 `config.py` 的 `C901` per-file ignore | `python -m py_compile src/cstree/pipeline/config.py`; `.venv/bin/ruff check --select C901 src/cstree/pipeline/config.py`; `uv run pytest tests/test_config_utils.py tests/test_pipeline_validation.py -q` |
| panel loader helpers | 将 price symbol resolve、provider/file fetch、daily panel prepare、benchmark split、filter load/apply、tradeability apply 和 label horizon state 拆出 `_load_research_panel` | `python -m py_compile src/cstree/pipeline/panel_loader.py`; `.venv/bin/ruff check --select C901 src/cstree/pipeline/panel_loader.py` |
| period eval helpers | 将 permutation test、label/rebalance gap warning、positions、execution sim 和 backtest attachment 从 `_evaluate_period` 拆出 | `python -m py_compile src/cstree/pipeline/eval.py`; `.venv/bin/ruff check --select C901 src/cstree/pipeline/eval.py` |
| mirror workflow batch handlers | 将通用 dated / quarter mirror 的 quota batch summary、split-after-error summary、pending quota marking 和 batch processor 抽为 helper；撤销 `mirror_workflow.py` 的 `C901` per-file ignore | `python -m py_compile src/cstree/data_tools/rqdata_assets/mirror_workflow.py`; `.venv/bin/ruff check --isolated --select C901 --config lint.mccabe.max-complexity=18 src/cstree/data_tools/rqdata_assets/mirror_workflow.py` |
| daily mirror workflow | 将 daily mirror 的 context、fetch payload、prepared batch writer、batch error handler、pending resume scan 和 finalize 拆为 helper；撤销 `mirror_daily.py` 的 `C901` per-file ignore | `python -m py_compile src/cstree/data_tools/rqdata_assets/mirror_daily.py`; `.venv/bin/ruff check --isolated --select C901 --config lint.mccabe.max-complexity=18 src/cstree/data_tools/rqdata_assets/mirror_daily.py` |
| PIT patch batch handlers | 将 PIT patch 的 quota/fetch error batch summary、batch processor、pending resume scan 和 unfinished audit marking 拆为 helper；撤销 `mirror_financial.py` 的 `C901` per-file ignore | `python -m py_compile src/cstree/data_tools/rqdata_assets/mirror_financial.py`; `.venv/bin/ruff check --isolated --select C901 --config lint.mccabe.max-complexity=18 src/cstree/data_tools/rqdata_assets/mirror_financial.py` |

剩余 deferred decisions：

* `mirror_financial.py` 的 PIT patch mirror 仍是较大入口；manifest builder、request
  context、batch error handling 和 audit marking 已抽出并撤销 C901，后续只按复用价值继续拆。
* 当前不推进 breaking 删除：public CLI、release module tools、legacy config key、
  symbol aliases、compatibility shim 和维护者 wrapper 均保持兼容。
* 全仓库 `I/F401/F841/B/UP/SIM/RUF` 清理继续作为单独机械改动，不和业务 refactor 混做。

## Active Backlog

| 优先级 | 事项 | 当前建议 |
| --- | --- | --- |
| P1 | 继续拆大函数 / 大模块 | 当前先巩固 `>500` 清零结果；下一步优先 `intraday_health.py` scanner/summary、`package_assets.py` part specs、`pipeline/eval.py` walk-forward window |
| P2 | 静态质量 ratchet | 优先单独处理 import sorting；`F401`、`UP` 等继续走 touched-file gate，不和行为重构混做 |
| P3 | `public_api.py` facade 收口 | 随 RQData asset 模块改动逐步判断 private helper 应留在模块内测试还是提升为稳定 public API |
| P4 | compatibility shim 删除 | `cstree.pipeline.data` 等只在 breaking release 或外部风险确认后处理 |
| P4 | legacy config / symbol aliases | `universe`、`ts_code` / `stock_ticker` / `order_book_id` 继续边界层兼容，内部和新输出收敛到 canonical 字段 |
| P4 | 维护者 wrapper / private helper | `run_hk_asset_workflow.py`、`package_repo.sh`、`export_repo_source.py` 先保留；删除前必须提供替代路径和引用更新 |

## C901 Debt Registry

本表是 `pyproject.toml` 里当前 21 个文件级 `C901` 豁免的审计口径。owner area
表示责任域，不表示个人 owner。新增、删除或保留豁免时，必须同步更新本表；本地
轻量校验可运行：

```bash
scripts/dev/run_tests.sh c901-debt
```

| File / module | Owner area | Reason | Validation command | Exit condition |
| --- | --- | --- | --- | --- |
| `src/cstree/commands/linear_sweep.py` | CLI / sweep | CLI 参数、配置生成和 sweep 汇总仍在同一入口 | `uv run pytest tests/test_linear_sweep.py tests/test_cli_research.py -q` | 拆出 job planning 和 summary writer 后撤销 |
| `src/cstree/commands/run_grid.py` | CLI / research | grid 参数解析、读取评分和结果渲染混合 | `uv run pytest tests/test_cli_research.py tests/test_construction_grid.py -q` | 拆出 input loading、scenario builder、writer 后撤销 |
| `src/cstree/commands/tune.py` | CLI / sweep | tune 搜索空间、job dispatch 和汇总逻辑混合 | `uv run pytest tests/test_tune.py tests/test_cli_research.py -q` | 拆出 search-space expansion 和 run summary 后撤销 |
| `src/cstree/data_providers.py` | provider boundary | provider 兼容、缓存、symbol/date 边界和错误处理集中 | `uv run pytest tests/test_data_providers_cache.py tests/test_fundamentals_providers.py -q` | 拆出 cache key、symbol normalization、provider adapter 后撤销 |
| `src/cstree/data_tools/build_hk_connect_universe.py` | universe assets | 港股通 universe 读取、过滤、输出和日期处理集中 | `uv run pytest tests/test_universe_tools.py -q` | 拆出 input resolve、liquidity filter、writer 后撤销 |
| `src/cstree/data_tools/rqdata_assets/args.py` | RQData CLI | 非 mirror 命令参数仍较集中，兼容默认值多 | `uv run pytest tests/test_cli_rqdata.py tests/rqdata_assets/test_request_groups.py -q` | 参数组和默认值进入 command spec 后撤销 |
| `src/cstree/data_tools/rqdata_assets/build.py` | RQData asset build | PIT / daily 构建路径、过滤和写入仍集中 | `uv run pytest tests/rqdata_assets/test_build.py -q` | 拆出 PIT universe filtering 和 path resolution 后撤销 |
| `src/cstree/data_tools/rqdata_assets/clean_daily.py` | RQData daily | 日线清洗规则、异常处理和输出集中 | `uv run pytest tests/rqdata_assets/test_clean_daily.py -q` | 拆出 price bounds、suspension rules、writer 后撤销 |
| `src/cstree/data_tools/rqdata_assets/coverage.py` | RQData coverage | PIT coverage 聚合、trainable grid 和渲染仍有复杂分支 | `uv run pytest tests/rqdata_assets/test_coverage.py -q` | 拆出 coverage aggregation 和 trainable grid 后撤销 |
| `src/cstree/data_tools/rqdata_assets/intraday_asset.py` | RQData intraday | 分钟资产选择、分片读取、输出规则集中 | `uv run pytest tests/test_hk_intraday_download.py tests/test_hk_intraday_tools.py -q` | 拆出 asset resolver 和 parts writer 后撤销 |
| `src/cstree/data_tools/rqdata_assets/intraday_health.py` | RQData intraday | 分钟健康检查扫描、聚合和报告集中 | `uv run pytest tests/test_hk_intraday_tools.py tests/rqdata_assets/ -q` | 拆出 scanner、summary、rendering 后撤销 |
| `src/cstree/data_tools/rqdata_assets/mirror_industry_changes.py` | RQData mirror | 行业变更 mirror 的日期、重试和输出集中 | `uv run pytest tests/rqdata_assets/ -q` | 拆出 dated fetch 和 writer 后撤销 |
| `src/cstree/data_tools/rqdata_assets/mirror_industry_southbound.py` | RQData mirror | request context、resume state、checkpoint manifest、fetch batch、symbol writer 和 finalize 已抽出，resume validation / pending collection 仍在入口 | `uv run pytest tests/rqdata_assets/ -q` | 继续拆出 resume validation 和 pending collection 后撤销 |
| `src/cstree/data_tools/rqdata_assets/mirror_instrument_industry.py` | RQData mirror | instrument industry mirror 的历史兼容和输出集中 | `uv run pytest tests/rqdata_assets/ -q` | 拆出 normalization 和 dated writer 后撤销 |
| `src/cstree/liveops/alloc_hk_allocation.py` | liveops HK | 港股执行分析含估值分层、二次补仓和 xlsx 输出 | `uv run pytest tests/test_alloc_hk.py tests/test_cli_liveops.py -q` | 拆出 scenario builder、allocation engine、xlsx writer 后撤销 |
| `src/cstree/liveops/holdings.py` | liveops | 持仓读取、格式兼容和输出渲染集中 | `uv run pytest tests/test_holdings_live.py tests/test_cli_liveops.py -q` | 拆出 reader、normalizer、renderer 后撤销 |
| `src/cstree/pipeline/config_eval.py` | pipeline config | eval / backtest 配置兼容分支集中 | `uv run pytest tests/test_config_utils.py tests/test_metrics.py -q` | 拆出 eval config contract 后撤销 |
| `src/cstree/pipeline/feature_engineering.py` | pipeline features | 特征构造、缺失处理和派生列规则集中 | `uv run pytest tests/test_transform.py tests/test_pipeline_filters_core.py -q` | 拆出 feature block builder 和 imputation rules 后撤销 |
| `src/cstree/pipeline/preflight.py` | pipeline validation | 运行前检查、provider 可用性和配置提示集中 | `uv run pytest tests/test_pipeline_validation.py tests/test_cli_core.py -q` | 拆出 config checks、provider checks、message builder 后撤销 |
| `src/cstree/portfolio.py` | portfolio | 组合构造、权重和输出字段规则集中 | `uv run pytest tests/test_backtest.py tests/test_pipeline_e2e.py -q` | 拆出 weighting、turnover accounting、position rows 后撤销 |
| `src/cstree/release_tools/hk_asset_workflow.py` | release workflow | refresh/inspect/package/release 编排和 report 收集集中 | `uv run pytest tests/test_hk_asset_workflow.py tests/test_run_release_scripts.py -q` | 拆出 stage planning、command construction、report collection 后撤销 |

## Orchestration Refactor Contract

拆大编排函数时，默认只做行为保持拆分。除非另开 breaking change，不改变公开 CLI、
配置兼容、provider 语义、artifact 路径、artifact schema、`summary.json` 字段和错误语义。

可接受的抽取边界：

* input normalization：CLI/config 参数归一化、legacy key 迁移、默认值解析。
* domain decision logic：过滤、切分、权重、severity、gate、promotion 等业务判断。
* data loading：provider/file/local asset 读取、日期窗口、cache key、parts 解析。
* artifact writing：CSV/JSON/parquet/xlsx 写入、manifest、report 路径规划。
* report rendering：stdout、markdown、summary section、health report 展示。
* validation：preflight、schema/contract 检查、错误提示构造。
* command construction：release / asset workflow 里的命令计划和 dry-run 计划。

每次拆分都要先锁住或同步补 characterization tests；如果对应文件仍保留 `C901` 豁免，
本页的 registry 必须记录下一步出口。跨模块传递状态时，优先用 dataclass、typed request
或窄函数签名，避免继续传无边界 mutable dict。

### Next Orchestration Extraction Targets

| 目标文件 | 下一步边界 | 首选 characterization tests |
| --- | --- | --- |
| `src/cstree/data_tools/rqdata_assets/mirror_industry_southbound.py` | resume validation、pending collection、batch error handlers | `uv run pytest tests/rqdata_assets/ -q` |
| `src/cstree/pipeline/eval.py` | walk-forward window fit/score/report helpers | `uv run pytest tests/test_pipeline_train_eval_contracts.py tests/test_pipeline_e2e.py -q` |
| `src/cstree/data_tools/rqdata_assets/intraday_health.py` | scanner、summary、rendering | `uv run pytest tests/test_hk_intraday_tools.py tests/rqdata_assets/ -q` |

### Heavy Data Verification Rule

HK PIT、full-market assets、monthly live snapshot、sweep / tune、XGBoost ranker 训练和
RQData 大资产检查默认不在代理会话里整包重扫。常规实现优先使用小 fixture、synthetic
case 或维护者已经生成的小型 JSON/text report。需要复核重任务时，先读
`summary.json`、`config.used.yml`、`artifacts/reports/*.json`、`run.log` 这类小产物；
不要默认展开大型 parquet 或 `.parts/` 目录。

## 历史基线

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

### 2026-04-27 apply 基线

`improve-pipeline-maintainability` 开始 implementation 前，按同一统计口径重新核对：

| 指标 | 当前值 | 相对上轮后 |
| --- | ---: | ---: |
| Python 文件数 | 245 | 0 |
| Python 总行数 | 88,133 | +238 |
| 超过 100 字符的行 | 1,180 | -2 |
| 超过 100 行的函数 | 166 | 0 |
| 超过 250 行的函数 | 29 | 0 |
| `C901` 文件级豁免 | 34 | 0 |

本 change 的目标验证矩阵：

| 改动范围 | 首选验证 |
| --- | --- |
| train/eval contracts | `uv run pytest tests/test_pipeline_train_eval_contracts.py -q` |
| model registry / split CV | `uv run pytest tests/test_modeling.py tests/test_split.py -q` |
| pipeline runner compatibility | `uv run pytest tests/test_pipeline_runtime.py tests/test_pipeline_filters_core.py -q` |
| period evaluation / backtest | `uv run pytest tests/test_metrics.py tests/test_backtest.py tests/test_backtest_reporting.py tests/test_pipeline_e2e.py -q` |
| RQData asset health | `uv run pytest tests/rqdata_assets/ -q` |
| release workflow helpers | `uv run pytest tests/test_hk_asset_workflow.py tests/test_run_release_scripts.py -q` |
| static quality ratchet | `scripts/dev/run_tests.sh lint` and `uv run pytest tests/test_run_tests_script.py -q` |

### 2026-04-27 apply 收尾统计

`improve-pipeline-maintainability` 完成 contract / registry / eval / ratchet / large-module
首轮拆分后，按同一统计口径重新核对：

| 指标 | apply 基线 | 当前值 | 变化 |
| --- | ---: | ---: | ---: |
| Python 文件数 | 245 | 249 | +4 |
| Python 总行数 | 88,133 | 89,020 | +887 |
| 超过 100 字符的行 | 1,180 | 1,176 | -4 |
| 超过 100 行的函数 | 166 | 169 | +3 |
| 超过 250 行的函数 | 29 | 29 | 0 |
| `C901` 文件级豁免 | 34 | 34 | 0 |

行数增加来自新增 stage contract、model registry 测试、asset health daily rule helper 和
workflow report helper。`>250` 超大函数没有新增，`C901` 豁免没有新增；`>100` 函数数量
仍需下一轮继续用职责拆分下降。

本轮 large-module 抽取记录：

| 原文件 | 新边界 | before | after | 说明 |
| --- | --- | ---: | ---: | --- |
| `src/cstree/data_tools/rqdata_assets/asset_health.py` | `asset_health_daily_rules.py` | 2,102 行 | 2,055 行；新模块 133 行 | 抽出 daily target-day 价格 / 成交规则检查；`inspect_hk_asset_health` 约 762 行降到 710 行 |
| `src/cstree/release_tools/hk_asset_workflow.py` | `hk_asset_workflow_report.py` | 2,244 行 | 2,131 行；新模块 169 行 | 抽出 workflow report 初始化、写入、gate trigger / skipped step 记录 |

验证：`uv run pytest tests/rqdata_assets/ tests/test_hk_asset_workflow.py tests/test_run_release_scripts.py -q`
和 `scripts/dev/run_tests.sh lint` 均通过。

### 2026-04-27 maintainability apply 基线

`improve-codebase-maintainability` 开始 implementation 前，按 tracked `src/`、`scripts/`、
`tests/` Python 文件重新核对。这个 change 的范围是维护债治理，不承诺一次性删除公开功能；
每项任务都需要保留行为、同步验证，并按任务完成情况更新本页。

| 指标 | 当前值 | 说明 |
| --- | ---: | --- |
| Python 文件数 | 249 | `src/` 153，`tests/` 94，`scripts/` 2 |
| Python 总行数 | 89,020 | `src/` 58,517，`tests/` 30,006，`scripts/` 497 |
| 超过 100 字符的行 | 1,176 | 其中 `src/` 819 |
| 超过 100 行的函数 | 169 | 其中 `src/` 97 |
| 超过 250 行的函数 | 29 | 其中 `src/` 28 |
| 超过 500 行的函数 | 4 | 其中 `src/` 3 |
| `C901` 文件级豁免 | 34 | 见 `pyproject.toml` |

本 change 的首要约束：

* 行为保持优先；拆分大函数和收窄 facade 时不改变 CLI、配置、provider、artifact schema。
* 兼容 shim 先审计和标注退出路径，除非明确批准，不做立即 breaking 删除。
* Ruff / PEP 8 治理继续走 ratchet，不做一次性全仓库机械修复。
* RQData 大资产检查不在代理会话里重扫大 parquet；使用现有小 fixture 和结构化测试。

本 change apply 记录：

| 范围 | before | after | 验证 |
| --- | ---: | ---: | --- |
| `pipeline/train_eval_stage.py` `_run_train_eval_stage_impl` | 599 行，98 参数 | 550 行，1 个 `TrainEvalRequest` 参数；新增 request-from-kwargs 和 fit/train-score helper | `uv run pytest tests/test_pipeline_train_eval_contracts.py tests/test_modeling.py tests/test_split.py -q` |
| `pipeline/runner.py` `run` | 530 行 | 509 行；新增 service hook resolution 和 benchmark compare frame attachment helpers | `uv run pytest tests/test_pipeline_runtime.py tests/test_pipeline_filters_core.py -q` |
| `rqdata_assets/asset_health.py` `inspect_hk_asset_health` | 710 行 | 581 行；新增 field quality check builder 和 synthetic tests | `uv run pytest tests/rqdata_assets/test_asset_health_quality.py tests/rqdata_assets/test_asset_health_current.py tests/rqdata_assets/test_asset_health_history.py -q` |
| `rqdata_assets` package facade | `public_api.__all__` 49 个名字 | repo-local audit 未发现 private facade imports；新增测试确认 package/public API 不导出下划线 helper | `uv run pytest tests/test_cli_rqdata.py tests/rqdata_assets/test_request_groups.py -q` |

本 change 收尾统计（包含本次工作树新增测试文件）：

| 指标 | apply 基线 | 收尾值 | 变化 |
| --- | ---: | ---: | ---: |
| Python 文件数 | 249 | 251 | +2 |
| Python 总行数 | 89,020 | 89,473 | +453 |
| `src/` 行数 | 58,517 | 58,782 | +265 |
| `tests/` 行数 | 30,006 | 30,194 | +188 |
| 超过 100 字符的行 | 1,176 | 1,175 | -1 |
| 超过 100 行的函数 | 169 | 172 | +3 |
| 超过 250 行的函数 | 29 | 29 | 0 |
| 超过 500 行的函数 | 4 | 4 | 0 |

行数增加主要来自兼容 shim 测试、asset health synthetic quality tests、runner facade tests，
以及把 train/eval flat kwargs 转换逻辑显式化。超大函数数量没有增加；`inspect_hk_asset_health`
和 `run` 明显缩短，`_run_train_eval_stage_impl` 的参数面从 98 个字段收口为单个 request。
下一轮应优先继续拆 `asset_health` 的 symbol scan / target-date stats update、`runner` 的 setup/dataset load，
以及 `train_eval_stage` 的 period / walk-forward context 构造。

### 最大实现文件

| 行数 | 文件 | 类别 | 初步处理 |
| ---: | --- | --- | --- |
| 2,568 | `src/cstree/data_tools/rqdata_assets/asset_health.py` | RQData health inspection | 主函数已缩短；继续拆 symbol scan / target-date stats update |
| 2,157 | `src/cstree/release_tools/hk_asset_workflow.py` | release orchestration | 按 stage planning、command construction、report collection 拆 |
| 1,698 | `src/cstree/data_tools/rqdata_assets/audit_assets.py` | RQData asset audit | 后续纳入第二批 |
| 1,546 | `src/cstree/data_tools/rqdata_assets/mirror_financial.py` | RQData financial mirror | PIT patch 已撤 C901；后续只按复用价值继续拆 |
| 1,535 | `src/cstree/data_tools/rqdata_assets/mirror_workflow.py` | RQData generic mirror | C901 已撤销；后续只按复用价值继续拆 |
| 1,416 | `src/cstree/data_tools/rqdata_assets/coverage.py` | RQData PIT coverage | 先拆 trainable grid 或 coverage aggregation |
| 1,387 | `src/cstree/pipeline/eval.py` | pipeline evaluation | 继续拆 walk-forward window helpers |
| 1,280 | `src/cstree/research/summarize_runs.py` | research summary | 暂不作为首批删除或拆分目标 |
| 1,215 | `src/cstree/data_tools/rqdata_assets/build.py` | RQData asset build | 先拆 PIT universe filtering 或 path resolution |
| 1,164 | `src/cstree/data_providers.py` | provider boundary | 先保持稳定，避免同时改 provider 行为 |
| 1,158 | `src/cstree/release_tools/package_assets.py` | asset packaging | 第二批，先拆 part spec construction |
| 1,147 | `src/cstree/data_tools/rqdata_assets/intraday_health.py` | RQData intraday | 后续拆 scanner、summary、rendering |
| 1,121 | `src/cstree/data_tools/data_warehouse.py` | data materialization | 第二批，先补边界测试再拆 |
| 1,091 | `src/cstree/exposure.py` | exposure analysis | 第二批，按 reporting / analysis 边界拆 |

### 首轮大模块拆分记录

2026-04-23 已完成第一轮行为保持拆分，优先抽纯渲染、路径解析和公开复用 helper：

| 原文件 | 新边界 | 当前状态 | `C901` 处理 |
| --- | --- | --- | --- |
| `src/cstree/data_tools/rqdata_assets/asset_health.py` | `asset_health_rendering.py` / postprocess helpers | 主文件继续按 health scanner / resolver / checks 拆分 | 后续已撤销 C901 豁免 |
| `src/cstree/data_tools/rqdata_assets/coverage.py` | `coverage_rendering.py` | 主文件约 1,416 行；渲染模块 313 行 | 原文件仍有 3 个 C901 命中，豁免保留 |
| `src/cstree/data_tools/rqdata_assets/build.py` | `build_paths.py` | 主文件约 1,215 行；路径模块 29 行 | 原文件仍有 4 个 C901 命中，豁免保留 |
| `src/cstree/pipeline/eval.py` | `eval_benchmark.py` | 主文件继续按 period / walk-forward / benchmark 拆分 | 后续已撤销 C901 豁免 |
| `src/cstree/release_tools/hk_asset_workflow.py` | `hk_asset_workflow_paths.py` | 主文件约 2,244 行；path/model 模块 186 行 | 原文件仍有 4 个 C901 命中，豁免保留 |

校验命令：`.venv/bin/ruff check --isolated --select C901 ...`。本轮没有新增复杂度豁免；
`command_registry.py` 和 `cli/liveops.py` 不需要 `C901` 文件级豁免。下一轮应优先拆仍命中的
entrypoint 函数，而不是再抽常量。

### 最大函数

| 行数 | 函数 | 文件 | 初步处理 |
| ---: | --- | --- | --- |
| 410 | `inspect_hk_intraday_health` | `src/cstree/data_tools/rqdata_assets/intraday_health.py` | 后续拆 scanner、summary、rendering |
| 357 | `_build_part_specs` | `src/cstree/release_tools/package_assets.py` | 后续拆 part planning 和 manifest rows |
| 349 | `mirror_hk_instrument_industry` | `src/cstree/data_tools/rqdata_assets/mirror_instrument_industry.py` | 后续拆 normalization 和 dated writer |
| 349 | `_run_train_eval_stage_impl` | `src/cstree/pipeline/train_eval_stage.py` | 已抽 period/walk-forward evaluation 并撤销 C901 豁免；后续继续拆 fit/eval runner |
| 347 | `mirror_hk_industry_changes` | `src/cstree/data_tools/rqdata_assets/mirror_industry_changes.py` | 后续拆 dated fetch 和 writer |
| 342 | `main` | `src/cstree/commands/run_grid.py` | 后续拆 input loading、scenario builder、writer |
| 324 | `mirror_hk_southbound` | `src/cstree/data_tools/rqdata_assets/mirror_industry_southbound.py` | 已抽 request/resume/checkpoint/fetch batch/writer/finalize；后续拆 resume validation / pending collection |
| 312 | `run` | `src/cstree/commands/linear_sweep.py` | 后续拆 sweep planning、job dispatch、summary writer |
| 312 | `build_hk_daily_clean_layer` | `src/cstree/data_tools/rqdata_assets/clean_daily.py` | 后续拆 price bounds、suspension rules、writer |
| 311 | `prepare_research_context` | `src/cstree/pipeline/runner.py` | 后续拆 stage context assembly |
| 304 | `inspect_hk_pit_coverage` | `src/cstree/data_tools/rqdata_assets/coverage.py` | 后续拆 coverage aggregation 和 trainable grid |
| 303 | `run` | `src/cstree/commands/tune.py` | 后续拆 search-space expansion 和 run summary |
| 302 | `main` | `src/cstree/data_tools/build_hk_connect_universe.py` | 后续拆 input resolve、liquidity filter、writer |
| 302 | `inspect_hk_asset_health` | `src/cstree/data_tools/rqdata_assets/asset_health.py` | 继续拆 health scanner / resolver / checks |
| 293 | `_evaluate_walk_forward_window` | `src/cstree/pipeline/eval.py` | 后续拆 window fit/score/report helpers |
| 291 | `compute_backtest_exposure_analysis` | `src/cstree/exposure.py` | 后续按 analysis/reporting 边界拆 |
| 286 | `main` | `src/cstree/release_tools/hk_asset_workflow.py` | 后续拆 stage planning、command construction、report collection |
| 284 | `backtest_topk` | `src/cstree/backtest.py` | 后续拆 rebalance loop 和 period accounting |
| 272 | `patch_hk_pit_financials` | `src/cstree/data_tools/rqdata_assets/mirror_financial.py` | 已撤销 C901；后续继续拆 base merge / manifest handoff |
| 269 | `_build_pit_health_section` | `src/cstree/data_tools/rqdata_assets/coverage.py` | 后续拆 health section rendering |

## 首批候选

| 候选 | 类别 | repo-local usage | 文档/公开面 | 风险 | 建议动作 | 验证 |
| --- | --- | --- | --- | --- | --- | --- |
| `src/cstree/pipeline/data.py` | compatibility shim | 当前 repo-local search 未发现内部导入 | 无公开文档入口 | 低 | 已加 `DeprecationWarning`；若确认无外部用户，再单独删除 | compatibility shim test、pipeline 快测 |
| `src/cstree/compat.py` | dependency compatibility | `pipeline/data.py`、`panel_loader.py`、`feature_dataset.py` 使用 `ensure_numpy_nan_alias` | 无公开文档入口 | 中 | 保留到确认 `pandas_ta` / NumPy 组合不再需要；避免散落更多调用 | `tests/test_pipeline_filters_core.py`、`tests/test_transform.py` |
| legacy `universe` config key | config compatibility | `config_utils.py` 规范到 `research_universe` | `docs/config.md` 明示仍兼容 | 中 | 先保持兼容；集中测试 canonical、legacy、conflict 三类行为 | `tests/test_config_utils.py` |
| `ts_code` / `stock_ticker` aliases | symbol compatibility | `data_tools/symbols.py`、RQData asset tools、liveops readers 多处接受 | `docs/providers.md`、`docs/outputs.md` 明示历史输入兼容 | 中 | 只在边界层接受，输出继续收敛到 `symbol`；暂不删除 | `tests/test_symbol_alias.py`、`tests/test_data_providers_cache.py` |
| `scripts/internal/run_hk_asset_workflow.py` | maintainer driver | `scripts/dev/refresh_hk_current.sh`、`scripts/dev/run_hk_health_checks.sh`、测试引用 | `scripts/README.md`、`docs/dev.md`、RQData health docs 引用 | 中 | 保留为 driver；如要删，先提供 `python -m cstree.release_tools.hk_asset_workflow` 替代文档 | `tests/test_refresh_hk_current_script.py`、`tests/test_run_release_scripts.py` |
| `scripts/internal/package_repo.sh` | maintainer helper | `tests/test_package_repo_script.py` 覆盖 | 未列入公开 CLI | 低 | 保留并标注为 private helper；不进入首批删除 | `tests/test_package_repo_script.py` |
| `scripts/internal/export_repo_source.py` | maintainer helper | 生成 `full_project_source.txt`；当前无直接测试引用 | 仅维护者辅助 | 低 | 标注为 private helper；后续按使用频率决定是否保留 | 文档路径检查 |

2026-04-27 audit：`run_hk_asset_workflow.py` 仍被 `scripts/dev/refresh_hk_current.sh`
和 `scripts/dev/run_hk_health_checks.sh` 调用，并被 `docs/dev.md`、RQData health 文档、
`tests/test_refresh_hk_current_script.py` 覆盖到引用路径。`package_repo.sh` 仍有
`tests/test_package_repo_script.py` 覆盖。`export_repo_source.py` 未发现自动化调用，继续作为
低优先级 private helper 保留；如要删除，应先确认维护者是否仍需要离线源码导出。

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
| `src/cstree/data_tools/rqdata_assets/public_api.py` | 490 | 测试和程序化使用 facade | `__all__` 导出 49 个稳定名字；模块内部仍导入大量 private helpers |
| `src/cstree/data_tools/rqdata_assets/__init__.py` | 37 | package facade | 动态转抄 `public_api`，边界不够显式 |

首批目标是让新增或修改命令时主要看一个 command spec 声明；共享 argument builder 只在确实减少重复时保留。后续再判断 `public_api.py` 和 package facade 的 private helper 导出边界。

2026-04-27 audit：repo-local search 未发现通过 `rqdata_assets` facade 或 `public_api`
导入 private helper；`public_api.__all__` 当前导出 49 个稳定名字、0 个下划线 helper。
本轮先补测试锁住这个边界，不触碰 `public_api.py` 内部大量私有 imports，避免把 facade
治理和历史 unused-import 清理混成一个大 diff。

## Static Quality Ratchet

当前 `pyproject.toml` 只启用 `E9`、`F821`、`F822`、`F823`、`C90`，并设置 `line-length = 100`。后续阶段按下面顺序推进：

1. 对触碰文件不新增长行、未使用导入或新的 `C901` 豁免。
2. 每拆一个大模块，尝试移除或减少对应 `C901` 豁免。
3. 使用 `scripts/dev/run_tests.sh maintainability` 记录大文件、大函数、长行和复杂度豁免趋势。
4. `scripts/dev/run_tests.sh lint` 已对改动 Python 文件追加 import 排序、unused import、
   unused variable、`B023` 和新增长行检查。
5. `scripts/dev/run_tests.sh c901-debt` 用于轻量校验当前 `C901` 豁免是否都登记在本页。
6. 再评估是否把更多 Ruff 规则纳入 `scripts/dev/run_tests.sh lint`。

2026-04-27 diagnostic-only 盘点：

命令：`.venv/bin/ruff check src tests scripts --select E,F,W,I,B,UP,SIM,RUF --ignore E501 --statistics`

| 规则 | 数量 | 处理建议 |
| --- | ---: | --- |
| `F401` unused import | 202 | 先继续在 touched files gate 拦截；全仓库修复需单独机械清理 |
| `UP045` Optional 写法 | 101 | 适合作为后续 pyupgrade 批次，但不和行为 refactor 混做 |
| `RUF046` unnecessary cast to int | 86 | 多为历史 defensive cast；先诊断，不立刻 gate |
| `I001` import 排序 | 75 | touched files 已 gate；全仓库 import sort 可单独做 |
| `E402` module import not at top | 31 | 多数需要确认是否为延迟 import，暂不自动修 |
| `RUF043` pytest raises pattern | 23 | 测试清理批次处理 |

本轮结论：下一步最稳妥的全局候选仍是 `I` import sorting，但需要先单独跑
`scripts/dev/run_tests.sh imports` 盘点并控制 diff；`F401` 和 `UP` 继续保持 touched-file
ratchet，避免和行为保持 refactor 混在一起。全仓库 import sorting、unused import、
pyupgrade 或 `SIM/RUF` 批量清理应作为单独机械改动处理。

## 建议验证矩阵

| 改动范围 | 首选验证 |
| --- | --- |
| OpenSpec / 维护债文档 | `uv run pytest tests/test_docs_contracts.py tests/test_repo_path_references.py -q` |
| config compatibility | `uv run pytest tests/test_config_utils.py -q` |
| symbol compatibility | `uv run pytest tests/test_symbol_alias.py tests/test_data_providers_cache.py -q` |
| train/eval contracts | `uv run pytest tests/test_pipeline_train_eval_contracts.py tests/test_modeling.py tests/test_split.py -q` |
| pipeline import / runner | `uv run pytest tests/test_pipeline_runtime.py tests/test_pipeline_filters_core.py -q` |
| RQData command registry | `uv run pytest tests/test_cli_rqdata.py tests/rqdata_assets/test_request_groups.py -q` |
| RQData asset health / coverage / build | `uv run pytest tests/rqdata_assets/ -q` |
| liveops CLI | `uv run pytest tests/test_cli_liveops.py tests/test_alloc.py tests/test_alloc_hk.py -q` |
| release workflow helpers | `uv run pytest tests/test_hk_asset_workflow.py tests/test_run_release_scripts.py -q` |
| focused test impact helper | `uv run pytest tests/test_dev_test_impact.py -q` |
| static quality ratchet | `scripts/dev/run_tests.sh lint` and `uv run pytest tests/test_run_tests_script.py -q` |

## Deferred Decisions

这些事项当前不默认推进删除；只有在外部兼容风险确认、breaking release 规划或替代路径文档齐备后再处理。

* legacy `universe` 和 legacy symbol aliases 暂不设置移除窗口；当前只在边界层保留兼容。
* `cstree.pipeline.data` 暂时保留为短期外部导入兼容 shim；repo 内部已改用 canonical 模块。
  2026-04-27 已加 `DeprecationWarning` 和 targeted compatibility shim test。删除前需要再次确认
  外部包使用风险，或明确接受 breaking import 变更。
* `scripts/internal/run_hk_asset_workflow.py` 暂时保留为维护者 driver / 兼容 wrapper；两个 dev 脚本仍引用它。
* `public_api.py` 已先收窄 package facade；下一轮继续判断哪些 private helper 应改成模块内测试或真实 public API。

## 刷新触发条件

发生以下变化时，应更新本页：

* 新增或移除 `C901` 文件级豁免。
* 新增、删除或改变 compatibility shim 的退出路径。
* 修改 `public_api.py` 或 package facade 的导出边界。
* 删除 legacy config key、symbol alias 或 provider 边界兼容规则。
* 完成一轮大函数 / 大模块拆分后，重新生成最大函数、最大文件和静态治理基线。
* 修改维护者 wrapper、private helper 脚本或其替代入口。
