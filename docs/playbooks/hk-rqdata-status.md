# HK RQData 状态矩阵

本页解决什么：记录当前仓库里 HK RQData 资产的实际可用状态，以及哪些目录是主线、哪些只是 probe。  
本页不解决什么：不代替 CLI 参数文档，也不展开完整研究路线。  
适合谁：准备继续补 HK 资产、清理旧目录，或想先判断“哪些已经稳定、哪些别碰”的人。  
读完你会得到什么：当前有效资产清单、接口接入状态，以及下一步应该补哪里的结论。  
相关页面：`docs/playbooks/hk-data-assets.md`、`docs/playbooks/hk-selected.md`、`docs/rqdata/README.md`、`docs/cli.md`、`docs/outputs.md`、`docs/providers.md`

最后核对时间：`2026-03-20`（Asia/Shanghai）

重要说明：

* quota 是即时信息，不写死在这页；现场执行 `csml rqdata quota --pretty`。
* 本页以当前工作区真实目录和 manifest 为准，不以旧笔记或 probe 命名为准。
* “稳定资产”指已经能被后续研究或打包复用的 snapshot；“probe”只说明曾经做过小样本验证。

## 先看结论

当前可以当作主线资产继续维护的有：

* `instruments`
  `artifacts/assets/rqdata/hk/instruments/hk_all_instruments_20260318.parquet`
  `artifacts/assets/rqdata/hk/instruments/hk_connect_full_20260318.parquet`
* `daily`
  `artifacts/assets/rqdata/hk/daily/hk_all_2000_20260318_daily_final_latest/`
* `pit_financials`
  `artifacts/assets/rqdata/hk/pit_financials/hk_all_2000_2025_full_market_latest/`
  `artifacts/assets/rqdata/hk/pit_financials/hk_connect_full_2000_2025_full_latest/`
  `artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest/`
* `ex_factors / dividends / shares`
  全市场 alias 已切到 `2026-03-18` 的 `*_full_market_latest` snapshot；`hk_connect` 两套 snapshot 也都还在本地
* `industry_changes`
  严格全市场 `industry_changes` 已落盘，并已从本地 `daily` 网格派生 `industry_labels_d/m/q`
  它是行业切换真相层；研究里直接 join 时优先用派生出来的 `industry_labels_*`
* `southbound`
  `hk_connect` 范围 raw snapshot 已落盘：
  `artifacts/assets/rqdata/hk/southbound/hk_connect_southbound_latest/`
  它属于高价值补充层，不是默认研究入口
* `instrument_industry`
  当前稳定的是旧 `1547` symbol 口径的月频、季频快照；`3203` symbol 的 full-market 月频尝试目录已经改名成 `*_incomplete`，不要当成 latest 用
  它更像 provider 快照补充层，不是行业主线真相层
* `universe`
  `artifacts/assets/universe/hk_connect_full_by_date.csv`
  `artifacts/assets/universe/hk_connect_full_research_by_date.csv`
  `artifacts/assets/universe/hk_connect_full_research_symbols.txt`
  `artifacts/assets/universe/hk_selected_pit_research_by_date.csv`
  `artifacts/assets/universe/hk_selected_pit_research_symbols.txt`
  `artifacts/assets/universe/hk_all_full_by_date.csv`
* `bundles / backup`
  `artifacts/snapshots/bundles/hk_full_ref_20260318/`
  `artifacts/snapshots/bundles/hk_connect_ref_20260318/`
  `artifacts/snapshots/hk_runtime_20260318/`
  `artifacts/snapshots/hk_runtime_20260319_core_assets/`

当前不要当成稳定主线的：

* `financial_details`
  命令已经接入，也确认了“全市场窄字段 + 长历史”可写出有效数据；但还不适合升成全量宽表主线。
* `exchange_rate`
  命令已经接入，也有默认最小字段的真实 probe；但长时间窗目前仍更适合 staged backfill，不要把当前状态误判成“全历史已齐”。
* 旧失败 probe、空目录、老的中间 shard
  这些目录不代表“资产已完成”，清理时优先处理。

## 一张短表看口径

下面这张表只回答一个容易混淆的问题：
“当前仓库里的 HK / RQData 资产，到底哪些已经是全市场、哪些是全字段、时间拉到了哪里、能不能当主线？”

| dataset | 是否全市场 | 是否全字段 | 当前时间范围 | 是否主线 |
| --- | --- | --- | --- | --- |
| `instruments` | 是 | 不适用，固定 instrument schema | `as-of 2026-03-18` 快照 | 是 |
| `daily` | 是，`3203` 个 symbol | 否，固定 `6` 个日线字段 | `2000-01-04` 到 `2026-03-18` | 是 |
| `pit_financials` | 是 | 是，`743` 个字段 | `2000q1` 到 `2025q4`，`as-of 2026-03-10` | 是 |
| `financial_details` | 近似是，当前 raw probe 请求了 `3203` 个 symbol | 否，目前只抓 `3` 个字段 | `2000q1` 到 `2025q4`，`as-of 2026-03-19` | 否，仍是增强层 probe |
| `exchange_rate` | 不适用，按货币对而不是股票池 | 否，当前默认 `2` 个字段 | 当前稳定 probe 是 `2025-02-10` 到 `2025-02-11` | 否，补充层 |
| `ex_factors` | 是 | 不适用，按 API payload 固定 schema | `2000-01-01` 到 `2026-03-18` | 是 |
| `dividends` | 是 | 不适用，按 API payload 固定 schema | `2000-01-01` 到 `2026-03-18` | 是 |
| `shares` | 是 | 否，当前默认 `7` 个字段 | `2000-01-01` 到 `2026-03-18` | 是 |
| `industry_changes` | 是 | 否，当前 level-1 映射 `11` 个字段 | `2000-01-01` 到 `2026-03-18` | 是 |
| `southbound` | 否，只是 `hk_connect` 范围 | 否，当前 `2` 个字段 | `2014-11-17` 到 `2026-03-18` | 否，补充层 |

补充：

* “是否全字段”只对支持显式传 `fields` 的接口有意义；像 `daily`、`dividends`、`industry_changes` 这类更接近固定 schema 的 raw mirror，用“不适用”或“固定字段数”理解更准确。
* `PB`、`PE`、`market_cap` 这类估值或衍生层，不在这张 raw mirror 表里。它们不等于“把 `pit_financials` 所有字段都抓下来”，而是走 provider valuation overlay / merge 的另一条链路。
* 行业层建议按三层理解：
  `industry_changes` 是切换日真相层；
  从它本地派生的 `industry_labels_d/m/q` 是研究里直接 join 的标签层；
  `instrument_industry` 更像 provider 快照补充层，不是默认主线。
* 如果只看“已经有数据，但当前仍不是全市场 + 长历史或全字段主线”的 HK 资产族，当前主要是：
  `instrument_industry`、`financial_details`、`exchange_rate`。
  `southbound` 这条线虽然不是 `2000` 年起、也不是全市场概念，但按它自己的自然历史范围已经够完整。
  其余主线 raw 资产如 `daily`、`pit_financials`、`ex_factors`、`dividends`、`shares`、`industry_changes` 已经都有当前可用的 full-market baseline。

## 现在磁盘上哪些算“当前有效”

建议把下面这些当成当前有效入口：

* `artifacts/assets/rqdata/hk/daily/hk_all_daily_latest`
  当前全市场日线 alias，指向 `hk_all_2000_20260318_daily_final_latest`
* `artifacts/assets/rqdata/hk/instruments/hk_all_instruments_latest.parquet`
  当前全市场 instruments alias，指向 `hk_all_instruments_20260318.parquet`
* `artifacts/assets/rqdata/hk/instruments/hk_connect_full_latest.parquet`
  当前 `hk_connect` instruments alias，指向 `hk_connect_full_20260318.parquet`
* `artifacts/assets/rqdata/hk/ex_factors/hk_all_ex_factors_latest`
  当前全市场 ex-factors alias，指向 `hk_all_2000_20260318_ex_factors_full_market_latest`
* `artifacts/assets/rqdata/hk/dividends/hk_all_dividends_latest`
  当前全市场 dividends alias，指向 `hk_all_2000_20260318_dividends_full_market_latest`
* `artifacts/assets/rqdata/hk/shares/hk_all_shares_latest`
  当前全市场 shares alias，指向 `hk_all_2000_20260318_shares_full_market_latest`
* `artifacts/assets/rqdata/hk/industry_changes/hk_all_industry_changes_latest`
  当前全市场 industry_changes alias，指向 `hk_all_2000_20260318_industry_changes_full_market_latest`，目录下已经有 `industry_labels_d/m/q.parquet`
* `artifacts/assets/rqdata/hk/southbound/hk_connect_southbound_latest`
  当前 `hk_connect` 范围 southbound raw snapshot，覆盖 `2014-11-17` 到 `2026-03-18`
* `artifacts/assets/universe/hk_connect_full_research_by_date.csv`
  当前 `hk_connect` 的 research-ready PIT universe，已在 `2026-03-18` 重建并对齐到 `2026-03-17`
* `artifacts/assets/universe/hk_connect_full_research_symbols.txt`
  当前 `hk_connect` 的 research-ready PIT symbol 集合，对应 `904` 个 symbol
* `artifacts/assets/universe/hk_selected_pit_research_by_date.csv`
  当前 `hk_selected` 这条实验线的 research-ready PIT universe，已在 `2026-03-18` 从本地 PIT flat file 重新派生
* `artifacts/assets/universe/hk_selected_pit_research_symbols.txt`
  当前 `hk_selected` 的 research-ready PIT symbol 集合，对应 `222` 个 symbol
* `artifacts/assets/rqdata/hk/financial_details/hk_financial_details_hk_all3203_superset_2000_2025_20260319/`
  当前保留的 `financial_details` 全市场窄字段 raw probe；请求 `3203` 个 symbol、`3` 个字段、`2000q1-2025q4`
* `artifacts/assets/rqdata/hk/financial_details/analysis_hk_all3203_superset_2000_2025_local_override_v10/`
  当前 `financial_details` 的标准化分析基线，只用于研究侧审阅和 subject 归并，不属于 pipeline 主线输入
* `artifacts/assets/rqdata/hk/exchange_rate/hk_exchange_rate_probe_20250210_20250211_minimal/`
  当前保留的 `exchange_rate` minimal probe；默认字段是 `currency_pair` 和 `middle_referrence_rate`

如果你要写配置、文档示例或临时脚本，优先引用这些 alias，避免再次把日期写死到多个地方。

## 接口状态矩阵

## 基础信息

| API | 仓库接入 | 当前本地状态 | 建议 |
| --- | --- | --- | --- |
| `all_instruments` | 已接，`csml rqdata export-hk-instruments` | 稳定 | 继续维护，属于主数据入口。 |
| `instruments` | 无单独 mirror 命令 | 间接覆盖 | 缺细节时按需调，不必单独做离线体系。 |
| `get_ex_factor` | 已接，`mirror-hk-ex-factors` | 稳定，full/connect 都在 | 继续保留，属于复权原料层。 |
| `get_dividend` | 已接，`mirror-hk-dividends` | 稳定，full/connect 都在 | 继续保留，属于股息原料层。 |
| `get_shares` | 已接，`mirror-hk-shares` | 稳定，full/connect 都在 | 继续保留，属于股本原料层。 |
| `get_exchange_rate` | 已接，`mirror-hk-exchange-rate` | 已有默认最小字段 probe；长窗 staged backfill 仍待补 | 如果目标是给 `financial_details` 做币种归一，优先复用默认两列。 |
| `get_industry` | 无单独 mirror 命令 | 无独立稳定资产 | 优先级低于 `industry_changes`。 |
| `get_industry_change` | 已接，`mirror-hk-industry-changes` | 稳定 | 行业切换真相层，优先保留。 |
| `get_instrument_industry` | 已接，`mirror-hk-instrument-industry` | 稳定但仍是旧 research-universe 口径 | 便捷快照层；当前保留的月频/季频 latest 还是 `1547` symbol 版本。 |
| `get_industry_mapping` | 间接覆盖 | 已写到 `industry_changes` 目录 | 作为字典表看待，不必单独升级。 |
| `get_turnover_rate` | 未接入离线 mirror | 无稳定资产 | 当前优先级低。 |
| `hk.get_southbound_eligible_secs` | 已接，`mirror-hk-southbound` | `hk_connect` 范围 raw snapshot 已稳定落盘；full-market raw snapshot 仍无 | 默认研究仍可直接用现有 universe；需要渠道审计或资格回放时优先复用这份 raw mirror。 |

## 行情

| API | 仓库接入 | 当前本地状态 | 建议 |
| --- | --- | --- | --- |
| `get_price` | 已接，`mirror-hk-daily` | 稳定 | 主线资产；当前 full-market `daily_final_latest` 是默认日线底座。 |

补充：

* 当前全市场日线 snapshot 覆盖 `3203` 个 symbol，日期范围是 `2000-01-04` 到 `2026-03-18`。
* `hk_connect` 的独立日线 snapshot 也保留了，但属于兼容资产，不再是默认入口。
* `hk_connect_full_by_date.csv` 已在 `2026-03-18` 刷新到最近完整交易日 `2026-03-17`。
* `hk_connect_full_research_by_date.csv` 已在 `2026-03-18` 重新派生，当前覆盖 `904` 个带本地 PIT flat fundamentals 的 symbol。
* `hk_selected_pit_research_by_date.csv` 也已在 `2026-03-18` 重新派生，当前覆盖 `222` 个 symbol，给 `hk_selected` 系列配置使用。

## 财务

| API | 仓库接入 | 当前本地状态 | 建议 |
| --- | --- | --- | --- |
| `get_pit_financials_ex` | 已接，`mirror-hk-pit-financials` | 稳定 | 主线资产；full-market `743` 字段 snapshot 已完成。 |
| `hk.get_detailed_financial_items` | 已接，`mirror-hk-financial-details` | 全市场窄字段 probe 可用，但仍非主线资产 | 继续显式 `field` 白名单增强，不要直接升成全字段计划。 |

补充：

* `hk_all_2000_2025_full_market_latest` 是当前更完整的全市场 PIT snapshot。
* 旧的 `hk_all_2000_2025_full_latest` 空快照已经清理，不应再被配置、脚本或文档引用。
* `hk_connect_full_2000_2025_full_latest/pipeline_fundamentals.parquet` 已在 `2026-03-18` 用本地宽 PIT 镜像重建，当前是 `904` 个 symbol、`743` 个 value 字段，不再是早先那份窄版 flat file。
* `hk_selected_pit_2011_2025_latest/pipeline_fundamentals.parquet` 也已在 `2026-03-18` 重建，并同步派生出 `hk_selected_pit_research_*` 入口文件。
* `financial_details` 当前最完整的 raw probe 是 `hk_financial_details_hk_all3203_superset_2000_2025_20260319/`：请求 `3203` 个 symbol、`2000q1-2025q4`、`3` 个字段，实际写出 `345` 个 parquet。
* 对这份 raw probe 的标准化分析基线是 `analysis_hk_all3203_superset_2000_2025_local_override_v10/`；它说明“窄字段增强层”是可做的，但不等于已经适合升成全字段主线。
* 之前那类把 `financial_details` 当成“`743` 字段宽表”去拉的试法，会在多只股票上触发 server error，不应再作为默认方案。
* `exchange_rate` 命令已经接入，当前有 `hk_exchange_rate_probe_20250210_20250211_minimal/` 这份真实 probe；默认只保留 `currency_pair` 和 `middle_referrence_rate`。
* 这条接口当前最大问题不是配额，而是长时间窗明显慢于 `shares/dividends`；现阶段更适合先做最小字段 probe，再按阶段回填更长历史。
* `hk_all_probe_2025q4_2026q1_starter_20260319/` 也已经落盘，和 `hk_connect` 版本一样是 `date=2026-03-19` 的 `17` 列 starter 增量，并已生成 `pipeline_fundamentals.parquet` 与 `artifacts/assets/universe/hk_all_probe_2025q4_2026q1_starter_20260319_research_*`。
* `hk_connect_probe_2025q4_2026q1_starter_20260319/` 是当前更晚 as-of 的窄 PIT 增量快照，`date=2026-03-19`，starter 字段集共 `17` 列；目录下已生成 `pipeline_fundamentals.parquet`，并派生 `artifacts/assets/universe/hk_connect_probe_2025q4_2026q1_starter_20260319_research_*`。

## 因子与公告

| API | 仓库接入 | 当前本地状态 | 建议 |
| --- | --- | --- | --- |
| `get_factor` | runtime overlay 支持 | 无离线 mirror | 保持 runtime 用法，不必单独囤。 |
| `get_all_factor_names` | 未接入 | 无 | 需要字段浏览时再补。 |
| `hk.get_announcement` | 未接入 | 无 | 当前不是主线。 |

## 目录清理规则

现在磁盘里的 HK 目录建议按下面的规则理解：

* `*_latest` 或带完整日期区间的 full/connect snapshot
  这些才是主线资产目录。
* `probe_*`
  默认都先当实验目录看；只有明确写入有效数据、且你决定长期保留时，才值得继续留。
* `daily/_archive_20260314/`
  这是历史中间产物收纳目录，不是默认入口。里面的 shard、失败重试目录都不应再被新文档引用。

## 现在推荐的默认组合

如果你只是想让框架继续稳定跑，不想再被旧目录绕进去，默认用下面这一组：

* `daily`
  `artifacts/assets/rqdata/hk/daily/hk_all_daily_latest`
* `instruments`
  `artifacts/assets/rqdata/hk/instruments/hk_all_instruments_latest.parquet`
* `pit_financials`
  `artifacts/assets/rqdata/hk/pit_financials/hk_all_2000_2025_full_market_latest/`
* `reference`
  `artifacts/assets/rqdata/hk/ex_factors/hk_all_ex_factors_latest`
  `artifacts/assets/rqdata/hk/dividends/hk_all_dividends_latest`
  `artifacts/assets/rqdata/hk/shares/hk_all_shares_latest`
* `industry`
  `artifacts/assets/rqdata/hk/industry_changes/hk_all_industry_changes_latest/industry_labels_m.parquet`
* `universe`
  `artifacts/assets/universe/hk_all_full_by_date.csv`
  或 `artifacts/assets/universe/hk_connect_full_by_date.csv`

当前配置入口已经收口到两组 research universe：

* `configs/presets/hk.yml`
  默认使用 `artifacts/assets/universe/hk_connect_full_research_by_date.csv`
* `configs/presets/hk_quarterly_pit_hybrid.yml`
  以及 `hk_selected` 系列实验配置，默认使用 `artifacts/assets/universe/hk_selected_pit_research_by_date.csv`

## 下一步建议

推荐顺序：

1. 先别为了复权口径重刷 `daily`；当前更合理的主线仍然是 `未复权日线 + ex_factors + dividends + shares`。
2. 如果只是继续研究，不急着重建 full-market 离线底座，优先补更晚 as-of date 的窄 `PIT` 增量，而不是重刷 `daily` 或 `pit_financials` 大资产。
3. 优先把配置、文档和脚本统一到 alias 路径，减少日期写死。
4. 只补轻量增量或小样本 probe，例如 `financial_details` 的少量 field/sample。
5. 新资产下载前，先看 `manifest.yml` 和 `quota`，不要把旧失败 probe 误认成当前缺口。

补充判断：

* 当前最值钱的仍然是会被横截面研究反复扫的原料层：`daily`、`pit_financials`、`ex_factors`、`dividends`、`shares`、行业变更。
* 当前不值得升级成主线缓存对象的，主要是 `get_factor`、`get_all_factor_names`、`get_turnover_rate`，以及只有事件驱动才明显受益的 `hk.get_announcement`。
* 如果你还想用试用额度换“以后可能会后悔没下”的东西，优先级上通常是 `southbound` 原始历史高于 `announcement`。

## 最小检查命令

```bash
csml rqdata quota --pretty
ls artifacts/assets/rqdata/hk/instruments
ls artifacts/assets/rqdata/hk/daily
sed -n '1,80p' artifacts/assets/rqdata/hk/daily/hk_all_daily_latest/manifest.yml
sed -n '1,80p' artifacts/assets/rqdata/hk/pit_financials/hk_all_2000_2025_full_market_latest/manifest.yml
```

如果你发现这页和磁盘目录再次不一致，优先更新这页，不要再往别的文档里复制一份临时状态。
