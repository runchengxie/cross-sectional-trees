# Scripts

`scripts/` 现在只保留少量仓库级辅助入口，尽量不承载可复用 Python 实现。

## Canonical Entrypoints

* `scripts/dev/run_tests.sh`：开发与 CI 的测试入口
* `scripts/dev/refresh_hk_current.sh`：本地日常刷新 HK current 资产；默认走尾窗 patch refresh + inspect gate
* `scripts/dev/run_hk_data_asset_audit.sh`：本地生成 HK current 资产统一审计 report，覆盖清单、新鲜度、repair 候选和 prune dry-run
* `scripts/dev/run_hk_health_checks.sh`：本地批量跑 HK / RQData 资产健康检查并统一落 report / log
* `scripts/dev/run_hk_pit_health.sh`：本地单独跑某个 HK PIT config 的 coverage + health，并统一落 report / log
* `scripts/internal/`：维护者私有工具，不属于公开 `cstree` 工作流

当前 `scripts/internal/` 里和 HK 资产维护相关的常用入口：

* `scripts/internal/run_hk_asset_workflow.py`：串联 `refresh / inspect / package / release` 的维护者 driver；底层仍复用现有 `cstree rqdata ...` 与 `csml.release_tools.*`
