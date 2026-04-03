# 文档首页

本页解决什么：提供唯一文档入口、问题索引和阅读路径。\
本页不解决什么：不展开具体命令、配置或概念细节。\
适合谁：不知道先看哪一页的读者。\
读完你会得到什么：问题到页面的映射、阅读路径和页面分工边界。\
相关页面：`README.md`、`docs/get-started.md`、`docs/pipeline-overview.md`、`docs/capabilities.md`、`docs/cookbook.md`、`docs/playbooks/README.md`、`docs/rqdata/README.md`、`docs/cli.md`、`docs/config.md`、`docs/outputs.md`

## 先按问题找页面

| 我现在的问题 | 先看哪一页 |
| --- | --- |
| 我第一次进入仓库，想先跑起来 | `docs/get-started.md` |
| 我想先知道系统从 config 到 artifacts 是怎么流的 | `docs/pipeline-overview.md` |
| 我想做 HK selected 正式研究 | `docs/playbooks/README.md` |
| 我只想按通用任务顺序推进 | `docs/cookbook.md` |
| 我想查命令和参数 | `docs/cli.md` |
| 我想查 metadata catalog、标准层物化或 DuckDB 查询 | `docs/cli.md` |
| 我想查配置键、模板入口和默认行为 | `docs/config.md` |
| 我想把 `artifacts/` 挪到 repo 外，或者统一改产物根目录 | `docs/concepts/external-artifacts-root.md` |
| 我想理解成本、滑点、`tr_close` 和现金分红假设 | `docs/concepts/execution-costs.md` |
| 我想查输出目录、文件和字段 | `docs/outputs.md` |
| 我想查 provider 差异、凭证和日期 token | `docs/providers.md` |
| 我想看 HK `5m` 分钟线现状、quota 和滑点校准文件 | `docs/playbooks/hk-intraday-assets.md` |
| 我想理解为什么当前只保留四个模型，以及别的算法何时值得引入 | `docs/concepts/model-landscape.md` |
| 我想查 HK / RQData 专题资料 | `docs/rqdata/README.md` |
| 我想看研究笔记和当前结论沉淀状态 | `docs/research/README.md` |

## 四条阅读路径

1. 我想先跑起来：`docs/get-started.md`
2. 我想先建立系统心智模型：`docs/pipeline-overview.md` → `docs/capabilities.md` → `docs/config.md` → `docs/outputs.md`
3. 我想做正式研究：`docs/playbooks/README.md` → `docs/concepts/benchmark-protocol.md` → `docs/cookbook.md`
4. 我想查某个细节：`docs/cli.md`、`docs/config.md`、`docs/outputs.md`、`docs/providers.md`、`docs/metrics.md`、`docs/troubleshooting.md`、`docs/rqdata/README.md`、`docs/playbooks/hk-intraday-assets.md`、`docs/concepts/`
5. 我想把数据目录放到 repo 外但不改主流程：`docs/concepts/external-artifacts-root.md` → `docs/config.md` → `docs/outputs.md`

## 页面分工

入口：`README.md`、本页 \
任务路径：`docs/get-started.md`、`docs/playbooks/` \
系统总览：`docs/pipeline-overview.md`、`docs/capabilities.md` \
通用工作流速查：`docs/cookbook.md` \
参考手册：`docs/cli.md`、`docs/config.md`、`docs/outputs.md`、`docs/providers.md`、`docs/metrics.md`、`docs/troubleshooting.md` \
专题资料：`docs/rqdata/` \
概念解释：`docs/concepts/`（包括 `docs/concepts/execution-costs.md`、`docs/concepts/external-artifacts-root.md`） \
开发与内部：`docs/dev.md`、`docs/internal/` \
研究笔记与论文精读：`docs/research/`
