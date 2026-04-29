# 文档首页

用途：提供唯一文档入口、问题索引和阅读路径。\
范围：这里只做导航；具体命令、配置和概念细节放在对应页面。\
适合读者：不知道先看哪一页的人。\
相关页面分工：问题索引、阅读路径和页面边界见下文。\
相关页面：`README.md`、`docs/get-started.md`、`docs/pipeline-overview.md`、`docs/capabilities.md`、`docs/cookbook.md`、`docs/playbooks/README.md`、`docs/rqdata/README.md`、`docs/cli.md`、`docs/config.md`、`docs/outputs.md`、`docs/dev.md`、`scripts/README.md`

## 先按问题找页面

| 我现在的问题 | 先看哪一页 |
| --- | --- |
| 我第一次进入仓库，想先跑起来 | `docs/get-started.md` |
| 我想先知道系统从配置到产出物是怎么流转的 | `docs/pipeline-overview.md` |
| 我想做港股精选正式研究 | `docs/playbooks/README.md` |
| 我只想按通用任务顺序推进 | `docs/cookbook.md` |
| 我想查命令和参数 | `docs/cli.md` |
| 我想查元数据目录、标准层物化或 DuckDB 查询 | `docs/cli.md` |
| 我想查配置键、模板入口和默认行为 | `docs/config.md` |
| 我想把 `artifacts/` 挪到仓库外，或者统一改产物根目录 | `docs/concepts/external-artifacts-root.md` |
| 我想理解成本、滑点、平仓逻辑和现金分红假设 | `docs/concepts/execution-costs.md` |
| 我想查输出目录、文件和字段 | `docs/outputs.md` |
| 我想查服务商差异、凭证和日期标识符 | `docs/providers.md` |
| 我想查开发测试命令和仓库脚本入口 | `docs/dev.md`、`scripts/README.md` |
| 我想批量跑港股或 RQData 本地资产健康检查，并把结果保存成报告或日志 | `docs/rqdata/hk-health-checks.md` |
| 我想看港股五分钟线快照、配额量级和滑点校准文件 | `docs/playbooks/hk-intraday-assets.md` |
| 我想理解为什么当前只保留四个模型，以及别的算法何时值得引入 | `docs/concepts/model-landscape.md` |
| 我想查港股或 RQData 专题资料 | `docs/rqdata/README.md` |
| 我想看研究笔记和当前结论状态 | `docs/research/README.md` |

## 五条阅读路径

1. 我想先跑起来：`docs/get-started.md`
2. 我想先建立系统心智模型：`docs/pipeline-overview.md` → `docs/capabilities.md` → `docs/config.md` → `docs/outputs.md`
3. 我想做正式研究：`docs/playbooks/README.md` → `docs/concepts/benchmark-protocol.md` → `docs/cookbook.md`
4. 我想查某个细节：`docs/cli.md`、`docs/config.md`、`docs/outputs.md`、`docs/providers.md`、`docs/metrics.md`、`docs/troubleshooting.md`、`docs/rqdata/README.md`、`docs/playbooks/hk-intraday-assets.md`、`docs/concepts/`
5. 我想把数据目录放到仓库外但不改主流程：`docs/concepts/external-artifacts-root.md` → `docs/config.md` → `docs/outputs.md`

## 页面分工

入口：`README.md`、本页\
任务路径：`docs/get-started.md`、`docs/playbooks/`\
系统总览：`docs/pipeline-overview.md`、`docs/capabilities.md`\
通用工作流速查：`docs/cookbook.md`\
参考手册：`docs/cli.md`、`docs/config.md`、`docs/outputs.md`、`docs/providers.md`、`docs/metrics.md`、`docs/troubleshooting.md`\
专题资料：`docs/rqdata/`\
概念解释：`docs/concepts/`（包括 `docs/concepts/execution-costs.md`、`docs/concepts/external-artifacts-root.md`）\
开发与内部：`docs/dev.md`、`scripts/README.md`、`docs/internal/`\
研究笔记：`docs/research/`

## 常用术语

| 术语 | 本仓库推荐写法 |
| --- | --- |
| artifact | 产物；路径名或配置键里保留 `artifacts/` |
| run | 运行；目录语境可写 `run 目录` |
| provider | 数据服务商；配置键仍写 `provider` |
| benchmark ladder | 基准阶梯（benchmark ladder） |
| health gate | 健康检查门控 |
| final OOS | 最终样本外（final OOS） |
| CPCV | 组合式清除交叉验证（CPCV） |
| PIT universe | 特定时间点股票池（PIT universe） |
