# cstree 命名空间迁移说明

本页面向维护者，记录 `csml` 到 `cstree` 的 breaking migration、迁移映射、发布说明和 rollback 条件。用户入口仍以 `README.md`、`docs/README.md` 和 `docs/capabilities.md` 为准。

页面性质：`historical-migration-record`\
当前状态：`completed`\
最后核对时间：`2026-05-05`

本页保留为 `csml` 到 `cstree` 命名空间迁移的历史记录。当前项目公开入口已经是
`cstree`-only；本页不再表示待执行迁移计划或活跃待办清单。

## 当前状态

`1.0.0` 起采用 `cstree`-only 合约：

* 新文档、新脚本输出和测试中的用户入口使用 `cstree`。
* `src/cstree/` 是实现所有权所在的包。
* `csml` CLI、`python -m csml...`、`import csml` 和 `CSML_*` 环境变量 fallback 已移除。
* logger namespace 使用 `cstree.*`。

## 移除版本

`csml` 兼容面在 `1.0.0` breaking release 中移除。

## 迁移映射

| 旧入口 | 新入口 |
| --- | --- |
| `csml run --config <cfg>` | `cstree run --config <cfg>` |
| `csml summarize ...` | `cstree summarize ...` |
| `csml grid ...` | `cstree grid ...` |
| `csml tune ...` | `cstree tune ...` |
| `csml sweep-linear ...` | `cstree sweep-linear ...` |
| `csml holdings ...` | `cstree holdings ...` |
| `csml snapshot ...` | `cstree snapshot ...` |
| `csml alloc ...` | `cstree alloc ...` |
| `csml alloc-hk ...` | `cstree alloc-hk ...` |
| `csml data ...` | `cstree data ...` |
| `csml universe ...` | `cstree universe ...` |
| `python -m csml.release_tools.<tool>` | `python -m cstree.release_tools.<tool>` |
| `python -m csml.research.<tool>` | `python -m cstree.research.<tool>` |
| `import csml.<module>` | `import cstree.<module>` |
| `CSML_ARTIFACTS_ROOT` | `CSTREE_ARTIFACTS_ROOT` |
| `CSML_METADATA_DB_PATH` | `CSTREE_METADATA_DB_PATH` |
| `CSML_WAREHOUSE_DB_PATH` | `CSTREE_WAREHOUSE_DB_PATH` |
| `CSML_RUN_PROVIDER_INTEGRATION` | `CSTREE_RUN_PROVIDER_INTEGRATION` |
| `CSML_INTEGRATION_RQDATA_HK_SYMBOL` | `CSTREE_INTEGRATION_RQDATA_HK_SYMBOL` |

## Breaking Gate Checklist

本次移除已完成：

* 重新审计 `README.md`、`docs/`、`scripts/`、`tests/`、`src/`、`.github/` 和 `pyproject.toml` 中的 `csml` / `CSML_*` / `cstree` / `CSTREE_*` 引用。
* 更新 `pyproject.toml`，移除 `csml` console script，确认 packaging smoke test 覆盖 `cstree`。
* 删除 `import csml` 公开兼容面，不保留 shim。
* 移除 `python -m csml...` 兼容路径，并保留 `python -m cstree... --help` 覆盖。
* 移除 `CSML_*` fallback，并同步 `docs/config.md`、`docs/capabilities.md` 和相关测试。
* logger namespace 已切换到 `cstree.*`，并更新 `caplog` / logging filter 测试。
* coverage、ruff per-file ignores、monkeypatch target 和内部导入已匹配 `src/cstree/` 实现包所有权。

## 1.0.0 Release Notes

`1.0.0` breaking change:

* Removed the legacy `csml` console script. Use `cstree`.
* Removed public `python -m csml...` module execution paths. Use `python -m cstree...`.
* Removed public `import csml` compatibility. Use `import cstree`.
* Removed `CSML_*` environment variable fallbacks. Use `CSTREE_*`.

## Rollback Criteria

如果 breaking release 暴露以下影响，应发布 patch release 恢复兼容面，或恢复短期 shim 并补充迁移提示：

* 用户脚本、CI 或发布流程因 `csml` console script 删除而大面积失败。
* 下游自动化仍依赖 `python -m csml.release_tools...` 或 `python -m csml.research...`。
* `CSML_*` 删除导致无法恢复运行环境，且文档没有足够明确的迁移路径。
* logger namespace 切换破坏排障或监控过滤规则。
