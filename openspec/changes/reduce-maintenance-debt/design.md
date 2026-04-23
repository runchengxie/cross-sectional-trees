## Context

仓库当前公开主线已经收口到 `cstree` 命名空间、HK 市场和 RQData provider。`docs/capabilities.md` 明确把能力分成公开 CLI、公开但非 CLI 的 release 工具、专题研究模块、维护与开发辅助脚本；因此本次不能把“不在新手入口里”简单等同于“不需要”。

本次静态盘点得到的主要证据：

- `pyproject.toml` 里有 34 个 `C901` 复杂度豁免，并且注释说明这些是正在逐步拆分的大型 orchestration 模块。
- `src/scripts/tests` 下排除 `__pycache__` 后共有 240 个 Python 文件、约 87,527 行；超过 100 字符的行有 1,223 行。
- 最大的实现文件集中在 release、RQData 资产、pipeline 和 research：`hk_asset_workflow.py` 2,328 行、`asset_health.py` 2,304 行、`coverage.py` 1,689 行、`audit_assets.py` 1,312 行、`build.py` 1,232 行、`pipeline/eval.py` 1,199 行。
- 大函数风险也集中：`inspect_hk_asset_health` 762 行、`run_train_eval_stage` 599 行、`pipeline.runner.run` 536 行、`_evaluate_period` 523 行、`backtest_topk` 426 行、`register_liveops_commands` 357 行。
- RQData 资产命令层已有 `RQDataAssetCommandSpec`，但仍有多层薄包装：`command_registry.py` 427 行、24 个 command specs、23 个 `_add_*_args` 包装函数；`args.py + args_mirror.py + command_registry.py + public_api.py + __init__.py` 合计约 2,387 行。
- `pipeline/data.py` 是 legacy re-export shim，但当前 `pipeline/runner.py` 仍从它导入；`compat.py` 的 `ensure_numpy_nan_alias` 仍被 `pipeline/data.py`、`panel_loader.py`、`feature_dataset.py` 使用。
- `config_utils.py` 仍支持 legacy `universe`，`data_tools/symbols.py` 和 RQData 资产工具仍接受 `ts_code` / `stock_ticker` / `order_book_id`，文档也声明这些是历史输入兼容。

结论：当前问题不是大面积废功能，而是兼容层、命令胶水、巨型 orchestration 模块和静态治理的维护边界需要收紧。

## Goals / Non-Goals

**Goals:**

- 为老旧兼容层建立“审计 -> 收口 -> 弃用 -> 删除”的流程，每一步都有 repo 内调用检查、文档检查和测试覆盖。
- 在不改变用户可见行为的前提下，拆分首批高风险大模块和大函数，降低 review 难度。
- 简化 RQData asset command 注册路径，让命令定义、默认值、参数构造和 runner 绑定更靠近同一个声明式 spec。
- 将 liveops CLI 从长函数堆参数的模式迁移到更小的 command builder 或声明式定义。
- 逐步收紧 lint 和复杂度治理，优先约束新增/触碰代码，再逐步减少历史豁免。
- 明确哪些 maintainer-only scripts 仍保留，哪些应删除、迁移或只作为模块入口文档化。

**Non-Goals:**

- 不一次性删除 `release_tools/`、`research/` 或 `scripts/internal/` 整体。
- 不在本变更中扩大市场/provider 支持面。
- 不把 RQData 在线重 I/O 健康检查作为默认验证步骤。
- 不要求一次性消除所有长行、所有大函数或所有 `C901` 豁免。
- 不改变 artifact 目录结构、公开 CLI 名称或现有 HK/RQData 主线行为，除非后续单独列出 breaking migration。

## Decisions

1. 分阶段处理兼容层，而不是直接删除。

   Rationale: `pipeline/data.py` 和 `compat.py` 当前仍在主流程导入链里；legacy symbol 和 legacy universe 也在文档中明示为历史输入兼容。直接删除会制造行为回归。第一步应先把内部调用迁到 canonical 模块和 `research_universe` / `symbol`，再用测试证明旧入口只剩边界兼容。

   Alternative considered: 立即删除 shim。拒绝原因是现有导入和文档契约还没有退场。

2. 大模块按行为边界拆分，不做“按行数平均切文件”。

   Rationale: `hk_asset_workflow.py`、`asset_health.py`、`coverage.py`、`build.py`、`pipeline/eval.py` 的问题是 orchestration、扫描、渲染、I/O、CLI adapter 混在一起。拆分目标应是让单个文件拥有清晰职责，而不是只把行数转移到新文件。

   Alternative considered: 先全仓格式化和机械拆文件。拒绝原因是会产生大 diff，难以确认行为等价。

3. RQData 命令层继续沿用 `RQDataAssetCommandSpec`，但扩展 spec 能力。

   Rationale: 仓库已经有 command spec 形态，继续推进比重写 CLI 更稳。应把默认值 provider、argument builder、runner、client requirement、help text 放进一个可读的声明结构，减少 `args.py`、`args_mirror.py`、`command_registry.py`、`public_api.py`、`__init__.py` 之间的跳转。

   Alternative considered: 保留当前薄包装，只拆实现文件。拒绝原因是命令层本身已经成为维护成本来源。

4. 静态治理采用 ratchet 模式。

   Rationale: 当前历史长行和复杂度豁免较多，直接打开一整套 Ruff 规则会产生大量无关 churn。更稳的方式是对 touched files 强制更严格、对豁免清单逐步减少，并把每轮删除的豁免和测试绑定。

   Alternative considered: 一次性启用 Ruff 全规则。拒绝原因是成本高且会掩盖真正的行为变更。

5. 删除候选必须先证明“不是公开/维护者入口”。

   Rationale: `scripts/internal/run_hk_asset_workflow.py` 虽然只是 bootstrap，但 `scripts/README.md` 明确列为 HK 资产维护 driver；release 和 research 模块也在 capability 文档里有入口分层。删除动作需要使用频率、替代入口和文档迁移说明，而不能只依赖静态观感。

   Alternative considered: 按“一次性脚本”标签批量删除。拒绝原因是会破坏维护者工作流。

## Risks / Trade-offs

- Public behavior drift -> 对每个拆分阶段运行对应 CLI/parser、pipeline、RQData asset、release helper 的回归测试，并在文档中记录是否有 public contract 变化。
- Refactor diff 过大 -> 每次只处理一个边界，例如先拆 `asset_health` 的 report rendering，再拆 scan aggregation。
- Compatibility 永远不退场 -> 给每个兼容入口建立 owner、usage audit、deprecation condition 和 removal condition。
- Spec 过于宽泛导致 apply 阶段难落地 -> tasks 按阶段拆成可独立提交的小项，每项包含目标文件、测试和文档检查。
- RQData 重 I/O 验证成本过高 -> 默认使用离线单元测试和已有 fake fixtures；真实 provider 或大资产扫描只在用户明确要求或维护者本地执行后复核 report。

## Migration Plan

1. 生成维护债 inventory，记录每个候选的类别、现有调用、文档引用、测试覆盖和建议动作。
2. 先处理低风险内部导入：把 `pipeline/runner.py` 从 `pipeline/data.py` re-export 切到真实模块导入，并确认 tests 覆盖。
3. 对 legacy config/symbol compatibility 添加集中 deprecation notes 或边界注释，避免兼容逻辑继续散在主流程。
4. 以 RQData asset command registry 为第一批结构化重构，把 wrapper 减到必要数量并保持 CLI help/parse tests 通过。
5. 逐个拆分大模块，每次只动一个职责边界，并移除对应 `C901` 豁免或减少大函数规模。
6. 审核 `scripts/internal/`，保留仍在文档和维护流程中使用的 driver；无使用证据的脚本才进入删除或 relocation。
7. 每批完成后更新相关 docs，并运行 `scripts/dev/run_tests.sh fast` 或更窄的目标测试；RQData 相关改动至少考虑 `tests/test_cli_rqdata.py`、`tests/rqdata_assets/`、`tests/test_hk_asset_workflow.py`、`tests/test_data_providers_cache.py`。

Rollback is standard git revert per phase because each phase should be small and behavior-preserving. For compatibility removals, rollback also requires restoring docs that announced the removal.

## Open Questions

- 外部是否仍有人直接导入 `cstree.pipeline.data`、`cstree.compat` 或 `cstree.data_tools.rqdata_assets.public_api` 的 private names？
- `universe` legacy config key 和 `ts_code` / `stock_ticker` 输入别名是否需要给出明确版本窗口，还是只先收口为边界兼容？
- `scripts/internal/run_hk_asset_workflow.py` 是否仍是维护者的常用入口，还是可以改为 `python -m cstree.release_tools.hk_asset_workflow` 并删除脚本？
- RQData asset command spec 是否应该覆盖所有 argparse 参数，还是保留少量共享 argument builder 作为中间层？
