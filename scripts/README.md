# Scripts

`scripts/` 现在按职责分组，便于区分公开工作流、研究辅助脚本和维护者私有工具。

## Canonical Entrypoints

* `scripts/dev/run_tests.sh`：开发与 CI 的测试入口
* `scripts/release/`：资产和 run 结果的打包与 GitHub Release 分发脚本
* `scripts/research/`：HK 研究辅助脚本
* `scripts/internal/`：维护者私有工具，不属于公开 `csml` 工作流

根目录旧路径目前仍保留兼容 wrapper；新文档和新引用应优先使用分组后的 canonical 路径。
