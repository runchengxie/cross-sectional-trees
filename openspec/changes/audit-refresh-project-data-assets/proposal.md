## Why

当前仓库已经积累了多层本地数据资产与缓存，但缺少一套统一、可重复的盘点与修复工作流，来回答“现在有哪些数据已经落盘”“哪些数据已经刷新到最新”“哪些历史段存在缺口或损坏”“哪些旧资产已经可以清理”。用户当前明确需要核对 ETF 自 `2000-01-01` 至今的 daily 完整性、股票 `5m` 数据的最新性，并对现有健康检查算法、历史数据问题和陈旧文件做一次系统盘查，因此需要把这类一次性维护工作沉淀成可执行、可复核的变更。

## What Changes

- 增加一套面向 `artifacts/cache/`、`artifacts/assets/`、`artifacts/metadata/` 的数据资产盘点流程，输出当前已下载/缓存数据、有效时间范围、最新日期、symbol 覆盖和关键 manifest/current contract 信息。
- 增加面向用户问题的定向刷新与核验能力，重点覆盖 ETF `daily` 自 `2000-01-01` 至今的完整性、股票 `5m` 数据是否已刷新到最新交易日，以及无法补齐时的 provider 边界说明。
- 增加基于现有 `inspect-hk-current-health`、`inspect-hk-asset-health`、`inspect-hk-intraday-health`、`inspect-hk-pit-coverage` 的统一健康检查汇总，补充问题分类、历史缺口识别、可修复与不可修复的判定，以及安全修复路径。
- 增加对历史数据异常的安全修复工作流，优先使用现有 refresh / patch / rebuild / alias 切换入口修复 manifest、时间覆盖、分块残缺、current contract 漂移等问题，并把修复结果落成 report。
- 增加陈旧资产与重复缓存识别规则，区分“可安全删除”“建议归档”“仍被 current alias 或下游引用”的目录与文件，避免手工误删。
- 补充对应的文档与维护者脚本说明，明确何时应运行轻量检查、何时应运行重 I/O 历史检查，以及哪些清理动作必须人工确认。

## Capabilities

### New Capabilities
- `data-asset-inventory`: 盘点本地缓存、正式资产和 current contract，输出覆盖范围、最新日期、关键元数据和待核验对象清单。
- `market-data-refresh-verification`: 针对 ETF `daily` 与股票 `5m` 资产执行定向刷新、最新性验证与缺口说明。
- `data-health-repair`: 聚合现有健康检查结果，识别历史数据异常并提供可执行的安全修复路径与修复产物。
- `stale-data-pruning`: 识别可删除的陈旧或重复数据资产，产出带依据的清理建议和受控删除流程。

### Modified Capabilities
None.

## Impact

- 受影响目录主要包括 `artifacts/cache/`、`artifacts/assets/`、`artifacts/metadata/`、`artifacts/reports/`、`scripts/dev/`、`scripts/internal/`、`docs/rqdata/` 和 `docs/playbooks/`。
- 受影响入口主要包括 `csml rqdata inspect-*`、`csml rqdata sync-*`、`csml rqdata build-*`、`scripts/dev/refresh_hk_current.sh` 与 HK 资产维护脚本。
- 该变更不会引入公开 API breaking change，但会新增更严格的数据盘点、修复和清理约束，并可能产生新的 report / manifest / alias 切换输出。
