# 脚本入口

`scripts/` 只保留仓库级开发辅助入口。可复用的 Python 实现应放在 `src/cstree/`，公开用户能力优先通过 `cstree` CLI 暴露。

## 常用入口

* `scripts/dev/run_tests.sh`：开发与 CI 的测试入口。
  * 常用模式：`all`、`fast`、`unit`、`slow`、`integration`、`coverage`、`lint`、`typecheck`、`imports`、`format`、`format-all`、`c901-debt`、`maintainability`。
  * `all` 覆盖主 `pytest` 测试集，不包含可选依赖冒烟检查和显式开启的真实 provider 联调。
  * `coverage` 的范围与 `all` 一致，只是额外输出覆盖率报告；它也不是完整 CI 矩阵。
* test-impact helper：按改动路径推荐 focused verification，适合在决定是否跑 `all` / `slow` 前先定位最小回归范围。

```bash
python scripts/dev/test_impact.py src/cstree/pipeline/runner.py docs/dev.md
```

* `scripts/dev/install_git_hooks.sh`：安装本地 `pre-commit` 和 `pre-push` hooks，提前检查文档契约、路径引用、测试入口和快回归。
* `scripts/internal/`：维护者私有工具，不属于公开 `cstree` 工作流。

## HK 数据资产边界

HK 数据资产下载、检查、修复、current contract 审计和 release 已从本仓库 sunset，统一交给 `market-data-platform`。本仓库不再保留 HK asset workflow wrapper、HK health shell 脚本或数据资产 release 脚本。

研究侧仍可通过配置消费外部生成的数据文件，例如 RQData provider、本地 daily asset、PIT flat file、standardized layer 或 universe 文件。

## 测试脚本速查

| 模式 | 用途 |
| --- | --- |
| `all` | 主 `pytest` 测试集，不带覆盖率 |
| `fast` / `unit` | 默认离线快回归 |
| `slow` | 较重的离线测试 |
| `integration` | 标记为 `integration` 的跨模块测试；真实 provider 联调需设置 `CSTREE_RUN_PROVIDER_INTEGRATION=1` |
| `coverage` | 主测试集加覆盖率报告 |
| `lint` | Ruff lint、基础复杂度检查、改动文件 import / 长行 ratchet |
| `typecheck` | Pyright 类型检查；当前覆盖 `pyproject.toml` 中登记的稳定模块子集 |
| `imports` | 全仓库 import 排序检查 |
| `format` | 检查本次改动的 Python 文件格式 |
| `format-all` | 检查 `src`、`tests` 和 `scripts` 下所有 Python 文件格式 |
| `c901-debt` | 校验 `C901` 文件级豁免是否已登记在维护债 inventory |
| `maintainability` | 输出 Python 文件数、长行、大函数、`C901` 豁免和重点 facade 指标 |

## 维护者脚本

当前保留的维护者脚本：

* `scripts/internal/package_repo.sh`：把仓库源码打包、校验、可选切分为 parts；不属于公开 `cstree` 工作流，但有 `tests/test_package_repo_script.py` 覆盖。
* `scripts/internal/export_repo_source.py`：把仓库文本源码导出为单个 `full_project_source.txt`，用于离线审阅或维护场景；不属于公开 `cstree` 工作流。
