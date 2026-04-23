# 脚本入口

`scripts/` 只保留少量仓库级辅助入口。可复用的 Python 实现应放在 `src/cstree/`，公开用户能力优先通过 `cstree` CLI 暴露。

## 常用入口

* `scripts/dev/run_tests.sh`：开发与 CI 的测试入口。
* `scripts/dev/refresh_hk_current.sh`：本地日常刷新 HK current 资产；默认使用尾部增量刷新（patch refresh）和健康检查门控（inspect gate）。
* `scripts/dev/run_hk_data_asset_audit.sh`：生成 HK current 资产审计报告，覆盖资产清单、新鲜度、修复候选和删除预演（prune dry-run）。
* `scripts/dev/run_hk_health_checks.sh`：批量运行 HK / RQData 资产健康检查，并统一保存 report / log。
* `scripts/dev/run_hk_pit_health.sh`：针对某个 HK PIT config 单独运行 coverage + health，并统一保存 report / log。
* `scripts/internal/`：维护者私有工具，不属于公开 `cstree` 工作流。

## 维护者脚本

当前 `scripts/internal/` 里和 HK 资产维护相关的常用入口：

* `scripts/internal/run_hk_asset_workflow.py`：串联 `refresh / inspect / package / release` 的维护者 driver。它主要负责编排，底层仍复用现有 `cstree rqdata ...` 与 `cstree.release_tools.*`。

术语说明：

* patch refresh：只拉最近尾部窗口的数据。
* patch merge：把尾部补丁合并回新的资产快照。
* inspect gate：健康检查达到指定严重级别时，阻止 latest/current alias 放行。
* repair candidates：健康检查报告里列出的待修复 symbol/date 子集。
