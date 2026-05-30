# cross-sectional-trees

低频截面研究仓库。

它读取 `market-data-platform` 已发布的本地数据资产，完成因子研究、模型训练、评估、回测和持仓快照，并在需要时导出 `quant-execution-engine` 可消费的标准 `targets.json`。本仓库不负责市场数据生产，也不负责真实券商下单。

## 这个项目做什么

日常可以把它理解成研究流水线：

```text
平台数据资产 -> 研究配置 -> 模型与回测 -> 持仓快照 -> 执行目标文件
```

最常用的能力是：

- 运行低频截面模型研究和 benchmark 对照。
- 汇总多次实验结果，检查策略候选是否有足够证据进入下一步。
- 生成当前目标持仓、分配分析和执行引擎标准 `targets.json`。
- 保存可复现的 `summary.json`、`config.used.yml` 和持仓文件。

中国香港市场 / RQData / 本地平台资产路线是历史验证最充分的 legacy reference；A 股是当前主线迁移方向。项目结构正在向 market-agnostic 的研究框架收敛；新增市场时，应尽量复用 `market`、`data`、`research_universe`、`features`、`model`、`eval`、`backtest` 和 `live` 这些通用配置边界。生命周期口径见 [docs/market-lifecycle.md](docs/market-lifecycle.md)。

中国香港市场数据资产的下载、清洗、健康检查、current contract 和发布已经迁到 `market-data-platform`。本仓库默认只读平台资产。

## 快速开始

前置条件：

- Python 3.12+
- `uv`
- 若运行兼容默认模板，需要已由 `market-data-platform` 准备好的本地中国香港市场数据资产；若验证 A 股迁移候选入口，需要准备 `metadata/current_assets/a_share_current.json` 指向的 A 股数据资产

```bash
uv venv --seed
uv sync --extra dev
export DATA_PLATFORM_ROOT=/path/to/market-data-platform/artifacts
cstree run --config default
```

`default` 当前仍指向中国香港市场兼容 starter，默认使用 `data.provider=rqdata` 和 `data.source_mode=platform_assets`，用于保护历史流程不被突然破坏。A 股主线迁移候选入口是 `configs/presets/default_next.yml`；它继承 `configs/presets/a_share.yml`，在 PIT universe、PIT fundamentals、交易规则和执行 dry-run 证据通过验收后，才应考虑切换 `default`。

运行后先看：

```text
artifacts/runs/<run>/summary.json
artifacts/runs/<run>/config.used.yml
artifacts/runs/<run>/positions_current.csv
```

更完整的首次跑通步骤见 [docs/get-started.md](docs/get-started.md)。

## 常用入口

```bash
cstree run --config default
cstree summarize
cstree holdings --help
cstree alloc-hk --help
cstree export-targets --help
```

这些命令分别覆盖主研究流程、结果汇总、持仓查看、市场专项分配分析和执行目标导出。完整 CLI 说明见 [docs/cli.md](docs/cli.md)。

## 入口分层

新手日常只需要先关注公开主线命令；完整能力边界见 [docs/capabilities.md](docs/capabilities.md)，参数细节见 [docs/cli.md](docs/cli.md)。

- 研究主线：`cstree run`、`cstree summarize`、`cstree grid`、`cstree tune`、`cstree sweep-linear`
- 持仓与执行交接：`cstree holdings`、`cstree snapshot`、`cstree alloc`、`cstree alloc-hk`、`cstree export-targets`
- 配置模板：`cstree init-config`
- 数据平台相关入口：`marketdata backup-data`、`marketdata data ...`、`marketdata rqdata hk-assets ...`

## 数据边界

- `market-data-platform`：生产、检查和发布共享市场数据资产。
- `cross-sectional-trees`：只读消费平台资产，做研究、回测和目标持仓导出。
- `quant-execution-engine`：读取标准 `targets.json`，负责 dry-run、风控、执行和审计。

想理解拆分背景和路径约定，先读 [docs/concepts/shared-hk-data-platform.md](docs/concepts/shared-hk-data-platform.md)。

## 文档导航

- 第一次跑起来：[docs/get-started.md](docs/get-started.md)
- 市场生命周期与 default 切换政策：[docs/market-lifecycle.md](docs/market-lifecycle.md)
- 建立整体认知：[docs/pipeline-overview.md](docs/pipeline-overview.md)
- 查看能力边界：[docs/capabilities.md](docs/capabilities.md)
- 按任务找做法：[docs/cookbook.md](docs/cookbook.md)
- 查配置：[docs/config.md](docs/config.md)
- 查输出字段：[docs/outputs.md](docs/outputs.md)
- 查服务商和凭证：[docs/providers.md](docs/providers.md)
- 查开发和测试：[docs/dev.md](docs/dev.md)

如果不知道先读哪一页，从 [docs/README.md](docs/README.md) 开始。
