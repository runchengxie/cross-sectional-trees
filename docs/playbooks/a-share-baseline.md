# A 股 baseline 迁移 playbook

用途：给 A 股主线迁移提供最小可执行阅读顺序和验收边界。\
范围：只描述 `cross-sectional-trees` 研究侧如何消费 A 股平台资产；不替代 `market-data-platform` 的 TuShare 数据运维文档，也不替代执行引擎券商接入手册。\
适合读者：准备验证 A 股 price-only / daily_clean baseline，或准备评估 default 是否可以从港股兼容入口切到 A 股的人。\
相关页面：`docs/market-lifecycle.md`、`docs/config.md`、`docs/providers.md`、`docs/cookbook.md`、顶层 contracts 文档

页面性质：`active-migration` \
最后核对时间：`2026-05-30` \
权威来源：`configs/presets/default_next.yml`、`configs/presets/a_share.yml`、顶层 contracts 文档 \
冲突优先级：如果本页和具体 run 的 `config.used.yml` 冲突，以 run 产物为准；如果本页和 `docs/market-lifecycle.md` 冲突，以生命周期政策页为准。

## 当前结论

A 股当前是主线迁移方向，但不是已经与历史 HK/RQData 路线等价成熟的完整研究栈。当前建议先把 A 股作为 price-only / daily_clean baseline 跑稳，再补 PIT universe、PIT fundamentals、行业历史和执行 dry-run 证据。

推荐入口：

```bash
cstree run --config default_next
```

`default_next` 是 `configs/presets/default_next.yml` 的 CLI alias，继承 `configs/presets/a_share.yml`。它存在的意义是给 default 真正切换前提供稳定候选入口；不要在验收条件未满足前直接把 `default` 改到 A 股。

## 最小前置条件

数据平台根目录需要能解析到 A 股 current contract：

```text
metadata/current_assets/a_share_current.json
```

当前 baseline 依赖的主要资产和字段边界：

- `daily_clean`：复权价格、成交量、成交额、估值 overlay、涨跌停/ST/停牌/上市天数等标记。
- `instruments`：证券基础信息。
- 静态股票池或人工维护 by-date 股票池。
- 研究侧交易规则过滤：T+1、涨跌停、ST、停牌、上市天数、板块粗分类等先作为研究过滤或标记处理。

这些能力不足以证明已经具备完整 PIT 研究能力：

- 不能用当前指数成分回填历史 PIT universe。
- 不能用最新财报快照冒充 PIT fundamentals。
- 不能用当前行业标签回填历史行业。
- `targets.json` 能导出和解析，不等于任一券商后端已经具备中国大陆市场真实报单能力。

## 推荐验证顺序

1. 确认数据平台已经发布 `a_share_current.json`，并且 `daily_clean` 质量门禁通过。
2. 跑 `cstree run --config default_next`，生成 `summary.json`、`config.used.yml` 和持仓文件。
3. 检查 `config.used.yml` 中：
   - `market: a_share`
   - `data.provider: tushare`
   - `data.source_mode: platform_assets`
   - `research_universe.mode: static`
   - `execution.market: a_share`
4. 建立 A 股 benchmark ladder，不要直接沿用港股 benchmark 语义。
5. 先固定 price-only / daily_clean baseline，再替换或扩展股票池。
6. 只有在 PIT universe、PIT fundamentals、行业历史和执行 dry-run 证据都补齐后，才讨论把 `default` 从港股兼容入口切到 A 股。

## 与港股 playbook 的关系

`hk-selected.md` 现在是 legacy research lane。它仍有价值：

- 作为历史方法论和 benchmark protocol 参考。
- 作为跨市场 sanity check。
- 作为复现历史 HK run 的入口。

但新增 A 股研究不应从 HK selected 配置复制市场假设。可以复用研究框架和评估方法，不能复用港股通、RQData、港股 benchmark、港股交易日历或 `alloc-hk` 的市场专项假设。

## default 晋升前 checklist

`default_next` 晋升为 `default` 前，至少需要满足：

- [ ] A 股 `daily_clean` 和 `instruments` current contract 稳定发布。
- [ ] `default_next` 可以稳定生成 `summary.json`、`config.used.yml` 和持仓文件。
- [ ] A 股 benchmark ladder 已建立并能解释主要收益来源。
- [ ] PIT universe 已具备 point-in-time 成分来源，或明确记录仍处于 static/by-date 人工池阶段。
- [ ] PIT fundamentals 已处理披露日、报告期、公告延迟和字段映射。
- [ ] 行业历史变更资产可用，或文档明确当前行业标签只用于当前截面说明。
- [ ] 研究侧交易规则过滤与执行侧 dry-run 证据一致。
- [ ] `cstree export-targets` 输出的 A 股 `targets.json` 已被 `quant-execution-engine` 解析并完成基础 dry-run。
- [ ] README、`docs/config.md`、`docs/providers.md`、`docs/market-lifecycle.md` 和 `configs/catalog.csv` 已同步新的 default 语义。

## 常见误区

- 不要把 `a_share.yml` 的可运行性解释成 A 股完整主线成熟。
- 不要把静态股票池 baseline 写成 PIT universe 研究。
- 不要把 daily_basic 估值 overlay 写成完整 PIT fundamentals。
- 不要把执行目标文件能打开理解成真实券商路径已验证。
- 不要把 HK selected 的 benchmark、港股通约束或 `alloc-hk` 默认带入 A 股。
