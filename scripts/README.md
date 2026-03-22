# Scripts

`scripts/` 现在只保留少量仓库级辅助入口，尽量不承载可复用 Python 实现。

## Canonical Entrypoints

* `scripts/dev/run_tests.sh`：开发与 CI 的测试入口
* `scripts/internal/`：维护者私有工具，不属于公开 `csml` 工作流