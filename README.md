# cross-sectional-trees

本项目使用 RQData 日线数据进行港股截面树模型研究、benchmark 对照、模型评估、回测、持仓快照和研究证据管理。当前正式支持的数据输入与研究主线边界为 `market=hk` 结合 `data.provider=rqdata`、`data.source_mode=platform_assets`，默认只读 `market-data-platform` 发布的本地资产。

本地港股资产直读主要覆盖日线和合约信息。若确实需要研究侧临时在线读取 provider 数据，配置必须显式设置 `data.source_mode=provider_online_legacy`；启用 `fundamentals.source=provider` 或 `fundamentals.provider_overlay` 时，基本面缓存未命中仍可能延迟加载 `rqdatac`。

## 项目定位

本项目提供一套适用于低频因子研究与实验复现的工作流，核心能力涵盖模型研究、指标评估、历史回测、候选策略治理、特征证据、benchmark 对照、持仓快照输出以及显式的交易执行目标交接。

HK 数据资产维护能力已从本仓库 sunset。日线、PIT、估值、行业、intraday、current contract、release 和十档盘口快照的下载、检查、清洗、发布入口由 `market-data-platform` 承载；本仓库只消费它产出的本地资产、标准层或服务商在线数据。若要理解拆分边界，先看 `docs/concepts/shared-hk-data-platform.md`。

## 环境准备与安装

运行环境要求 Python 3.12 及以上版本，推荐使用 `uv` 进行依赖管理。
需要使用 RQData 相关功能时，请在安装时添加 `--extra rqdata` 参数。若需将 `cstree alloc-hk` 的分配结果导出为 Excel 格式，请额外添加 `--extra liveops-hk` 参数。

```bash
uv venv --seed
uv sync --extra dev --extra rqdata --extra liveops-hk
cp .env.example .env
```

如果只做研究回测、暂不导出 `alloc-hk` Excel 分配表，可以省略 `--extra liveops-hk`。

数据鉴权配置与服务商的详细说明，请参考 `docs/providers.md` 文件。

常见命令及其依赖关系如下：

| 任务 | 典型命令 | 所需附加依赖 | 额外凭证 |
| --- | --- | --- | --- |
| 运行默认港股入门模板 | `cstree run --config default` | 无 | 已准备 `market-data-platform` 本地资产 |
| 运行港股季频特定时间点基本面路线 | `cstree run --config configs/presets/hk_quarterly_pit_hybrid.yml` | 无 | 已准备 PIT / daily 等本地资产 |
| 使用 DuckDB 查询标准层数据 | `marketdata data query --sql "..."` | `duckdb` | 已安装并配置 `market-data-platform` |
| 导出港股 Excel 分配表 | `cstree alloc-hk --format xlsx --out ...` | `liveops-hk` | 若走实时或服务商路径，需对应数据源凭证 |
| 导出执行引擎目标持仓 | `cstree export-targets --run-dir ... --out ...` | 无 | 无；仅消费已保存 live 持仓 |
| 计算包含 P 值的统计检验 | Python 下游分析调用 `summarize_ic` | `stats` | 无 |

CLI 入口使用 `cstree`。

`default` 和 `hk` 等内置别名，以及 `cstree init-config` 命令，均会默认读取仓库根目录下的 `configs/` 文件夹。日常使用时，请确保在包含 `configs/` 目录的源码工作区或导出的源码目录内执行相关命令。

## 快速开始

最短的跑通命令如下：

```bash
cstree run --config default
```

内置别名 `default` 当前指向港股入门模板，默认配置为 `data.provider=rqdata` 且 `data.source_mode=platform_assets`。首次运行 `default` 或 `hk` 前，请先在 `market-data-platform` 准备本地资产，并设置 `DATA_PLATFORM_ROOT` 或 `HK_DATA_PLATFORM_ROOT`。只有显式走在线 provider legacy 路线时才需要安装 `--extra rqdata`；若同时需要港股 Excel 分配表，请使用 `uv sync --extra dev --extra liveops-hk`。

## 核心入口清单

除主流程外，系统还提供以下功能入口：

* 主流程：`cstree run`
* 研究汇总与参数调优：`cstree summarize`、`cstree grid`、`cstree tune`、`cstree sweep-linear`
* 研究治理与证据工具：`cstree promotion-gate`、`cstree cpcv`、`cstree construction-grid`、`cstree feature-evidence`、`cstree benchmark-ladder`
* 实盘结果与执行交接：`cstree holdings`、`cstree snapshot`、`cstree alloc`、`cstree alloc-hk`（包含港股执行前场景矩阵分析）、`cstree export-targets`（导出执行引擎标准 targets 文件）
* 配置模板：`cstree init-config`
* 数据平台操作：标准层查询、HK universe 构建和本地数据备份统一使用 `marketdata data ...`、`marketdata rqdata hk-assets ...` 和 `marketdata backup-data`，本仓库不再提供对应 `cstree` 子命令。

完整的能力地图请参考 `docs/capabilities.md` 文件。

## 入口分层

为了便于理解和维护，当前仓库的能力入口分为以下四个层级：

| 层级 | 典型入口 | 当前定位 |
| --- | --- | --- |
| 公开主线命令行 | `cstree run`、研究汇总、研究治理、持仓分配、股票池和标准层命令 | 当前正式对外发布、包含完整文档说明并持续维护的用户级命令入口。 |
| 公开附属模块工具 | 运行结果打包与分发相关模块 | 已经在文档中公开的运行结果打包与分发工具。它们属于独立可复用模块，不作为 `cstree` 的直接子命令调用。 |
| 研究与专题模块工具 | 针对特定专题的模块 | 针对特定操作手册或专题场景使用的工具。具备复用价值，排除在新手默认主线之外。 |
| 维护与开发辅助 | 测试与内部脚本 | 前者服务于日常开发与持续集成；后者属于仓库维护者的私有工具，不计入公开的研究工作流。 |

如果你在使用中无法确定某个入口是否属于正式支持的范畴，请优先查阅 `README.md`、`docs/capabilities.md`、`docs/cli.md` 以及对应的操作手册页面。只要在上述文档中作为主线被提及，即代表正式受支持。

## 运行后产物检查

任务运行结束后，建议优先检查以下三个文件：

1. `summary.json`
2. `config.used.yml`
3. `positions_current.csv`

关于最短跑通步骤以及详细的产物检查清单，请查阅 `docs/get-started.md` 文件。

## 文档阅读指南

推荐以 `docs/README.md` 作为全局文档的起点。根据不同使用阶段，建议的阅读路径如下：

* 初次接触：直接阅读 `docs/get-started.md` 完成首次跑通。
* 建立系统认知：阅读 `docs/pipeline-overview.md` 了解架构与数据流向。
* 开展正式研究：从 `docs/playbooks/README.md` 切入具体的业务路线。
* 拆分共享数据层：阅读 `docs/concepts/shared-hk-data-platform.md`，再看 `docs/concepts/external-artifacts-root.md`。
* 日常工作速查：查阅 `docs/cookbook.md` 获取常见任务指南。
* 查询具体细节：根据开发或排障需求，分别查阅 `docs/cli.md`（命令）、`docs/config.md`（配置）或 `docs/outputs.md`（产物字段）。
