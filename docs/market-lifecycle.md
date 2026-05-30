# 市场生命周期与默认入口政策

本页解决什么：明确 A 股主线化、港股冻结维护、策略归档和未来 sunset 的项目口径。
本页不解决什么：不替代 `docs/config.md` 的完整配置说明，也不替代 `market-data-platform` 的数据资产运维手册。
适合谁：需要判断默认入口、配置生命周期、港股研究路线和 A 股迁移优先级的人。
相关页面：`README.md`、`docs/config.md`、`docs/providers.md`、`docs/concepts/shared-hk-data-platform.md`

## 决策摘要

未来研究主线以 A 股为核心。中国香港市场数据资产保留为冻结维护和可复现归档状态；港股策略研究从默认主线降级为 legacy research lane。除非存在明确资金、模拟盘、人工跟踪或跨市场验证需求，不再新增港股策略功能、港股 sweep 或港股数据维护入口。

当前不要直接删除港股。更安全的目标状态是：

| 层级 | 当前政策 |
| --- | --- |
| A 股研究 | 当前主线迁移方向，使用 `configs/presets/default_next.yml` 作为 default 切换前的候选入口 |
| 港股数据资产 | 由 `market-data-platform` 生产、检查、发布；本仓库只读消费；后续以冻结维护和可复现归档为主 |
| 港股策略研究 | 降级为 legacy / archived research lane，保留复现、对照和少量明确跟踪需求 |
| 港股 liveops / `alloc-hk` | 若无资金、模拟盘或人工跟踪需求，视为 frozen-active；保留兼容入口但不扩展默认主线 |
| `default` alias | 短期仍指向历史兼容的港股 starter，避免破坏老流程；A 股验收后再切换 |

## 配置生命周期字段

`configs/catalog.csv` 使用 `lifecycle` 字段标记配置状态：

| lifecycle | 含义 | 维护口径 |
| --- | --- | --- |
| `active_migration` | A 股主线迁移中使用的候选入口 | 可以迭代，但必须同步测试和迁移说明 |
| `legacy_reference` | 港股或共享历史参考模板 | 保持可运行和可解释，避免新增研究功能 |
| `legacy_research` | 港股历史研究路线 | 保留复现价值和必要 bugfix，不再作为默认研究预算入口 |
| `archived_provenance` | 历史 sweep / 参数搜索 / 证据包入口 | 只用于 provenance；新增 sweep 不应落在这里 |
| `shared_active` | 市场无关、仍服务主线的共享模板 | 正常维护 |
| `shared_reference` | 共享参考或兼容项 | 小心维护，不默认扩展 |

生命周期字段只描述项目政策，不改变配置解析行为。真正的默认行为仍由 CLI alias 和 `configs/presets/default.yml` 决定。

## 当前推荐入口

| 使用目的 | 推荐入口 | 说明 |
| --- | --- | --- |
| 老流程兼容 / 复现历史港股 starter | `default` 或 `configs/presets/default.yml` | 当前仍解析到中国香港市场 / RQData / 本地平台资产路线 |
| 明确运行港股 legacy reference | `configs/presets/hk.yml` | 港股历史成熟路线，后续以可复现和少量跟踪为主 |
| A 股 default 迁移候选 | `configs/presets/default_next.yml` | 继承 `configs/presets/a_share.yml`，用于 default 切换前验证 |
| A 股基础 baseline | `configs/presets/a_share.yml` | 当前偏 price-only / daily_clean / 静态股票池，不能视为已与港股路线等价 |

## A 股 default 晋升条件

只有至少满足下列验收后，才应把 `cstree run --config default` 从港股兼容入口切换到 A 股：

1. A 股 price-only baseline 可稳定读取 `metadata/current_assets/a_share_current.json` 指向的数据资产，并产出 `summary.json`、`config.used.yml` 和持仓文件。
2. PIT universe 有明确来源，例如 CSI300/500/800 或全 A 动态成分；不能用当前成分回填历史。
3. PIT fundamentals 明确披露日、报告期、公告延迟和字段映射；不能用最新财报快照伪装历史可得数据。
4. 行业 overlay 的历史变更边界清楚；只有当前行业标签时，不应回填历史回测。
5. 研究侧显式处理或标记 A 股交易规则：T+1、ST、停牌、涨跌停、新股上市天数和不同板块规则。
6. `cstree export-targets` 输出的 A 股 `targets.json` 已通过 `quant-execution-engine` 基础 dry-run；这仍不代表任何券商实盘能力已经放行。
7. README、`docs/config.md`、`docs/providers.md`、`docs/capabilities.md` 和 `configs/catalog.csv` 已同步说明默认入口变化。

## 港股 sunset 条件

港股策略或入口可以进一步 sunset 前，至少应确认：

1. 连续一段时间没有港股资金、模拟盘或人工跟踪需求。
2. 最后稳定数据快照、current contract、registry 和 manifest 已归档。
3. 关键港股 run 的 `summary.json`、`config.used.yml`、`inputs.lock.json` 或等价输入锁定文件可复现。
4. 下游不再依赖 `alloc-hk`、HK current contract 或 HK release preset 作为活跃入口。
5. 文档已将港股定位为 historical provenance / legacy market。
6. CI 只保留最小 smoke test，不再维护大面积港股研究矩阵。

## 改动原则

- 不把中国香港市场数据生产逻辑重新放回本仓库。
- 不为了“主线化”直接删除港股配置、历史研究记录或可复现证据。
- 不把 `configs/presets/a_share.yml` 当前能力夸大为完整 PIT / 执行 / 券商等价能力。
- 新增港股研究功能、港股 sweep 或港股数据入口前，必须先说明资金、模拟盘、人工跟踪或跨市场验证需求。
