# HK RQData 状态矩阵

本页解决什么：记录当前仓库里 HK RQData 资产的实际可用状态，以及哪些目录是主线、哪些只是 probe。  
本页不解决什么：不代替 CLI 参数文档，也不展开完整研究路线。  
适合谁：准备继续补 HK 资产、清理旧目录，或想先判断“哪些已经稳定、哪些别碰”的人。  
读完你会得到什么：当前有效资产清单、接口接入状态，以及下一步应该补哪里的结论。  
相关页面：`docs/playbooks/hk-data-assets.md`、`docs/playbooks/hk-selected.md`、`docs/cli.md`、`docs/outputs.md`、`docs/providers.md`

最后核对时间：`2026-03-18`（Asia/Shanghai）

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
  `artifacts/assets/rqdata/hk/daily/hk_all_2000_20260312_daily_final_latest/`
* `pit_financials`
  `artifacts/assets/rqdata/hk/pit_financials/hk_all_2000_2025_full_market_latest/`
  `artifacts/assets/rqdata/hk/pit_financials/hk_connect_full_2010_2025_full_latest/`
  `artifacts/assets/rqdata/hk/pit_financials/hk_connect_full_2000_2025_full_latest/`
* `ex_factors / dividends / shares`
  全市场和 `hk_connect` 两套 snapshot 都已经在本地
* `industry_changes / instrument_industry`
  全市场 `industry_changes` 和月频、季频 `instrument_industry` 已经落盘
* `universe`
  `artifacts/assets/universe/hk_connect_full_by_date.csv`
  `artifacts/assets/universe/hk_connect_full_research_by_date.csv`
  `artifacts/assets/universe/hk_connect_full_research_symbols.txt`
  `artifacts/assets/universe/hk_all_full_by_date.csv`
* `bundles / backup`
  `artifacts/snapshots/bundles/hk_full_ref_20260318/`
  `artifacts/snapshots/bundles/hk_connect_ref_20260318/`
  `artifacts/snapshots/hk_runtime_20260318/`

当前不要当成稳定主线的：

* `financial_details`
  命令已经接入，也确认了“小样本 + 显式字段”可写出有效数据；但还不适合升成全量宽表主线。
* 旧失败 probe、空目录、老的中间 shard
  这些目录不代表“资产已完成”，清理时优先处理。

## 现在磁盘上哪些算“当前有效”

建议把下面这些当成当前有效入口：

* `artifacts/assets/rqdata/hk/daily/hk_all_daily_latest`
  当前全市场日线 alias，指向 `hk_all_2000_20260312_daily_final_latest`
* `artifacts/assets/rqdata/hk/instruments/hk_all_instruments_latest.parquet`
  当前全市场 instruments alias，指向 `hk_all_instruments_20260318.parquet`
* `artifacts/assets/rqdata/hk/instruments/hk_connect_full_latest.parquet`
  当前 `hk_connect` instruments alias，指向 `hk_connect_full_20260318.parquet`
* `artifacts/assets/universe/hk_connect_full_research_by_date.csv`
  当前 `hk_connect` 的 research-ready PIT universe，已在 `2026-03-18` 重建并对齐到 `2026-03-17`
* `artifacts/assets/universe/hk_connect_full_research_symbols.txt`
  当前 `hk_connect` 的 research-ready PIT symbol 集合，对应 `622` 个 symbol
* `artifacts/assets/rqdata/hk/financial_details/hk_financial_details_probe_core_2024_2025_latest/`
  当前保留的 `financial_details` 有效 probe，只用于验证接口行为和资产结构

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
| `get_exchange_rate` | 未接入离线 mirror | 无稳定资产 | 有跨币种需求再补。 |
| `get_industry` | 无单独 mirror 命令 | 无独立稳定资产 | 优先级低于 `industry_changes`。 |
| `get_industry_change` | 已接，`mirror-hk-industry-changes` | 稳定 | 行业切换真相层，优先保留。 |
| `get_instrument_industry` | 已接，`mirror-hk-instrument-industry` | 稳定 | 便捷快照层，月频/季频都有。 |
| `get_industry_mapping` | 间接覆盖 | 已写到 `industry_changes` 目录 | 作为字典表看待，不必单独升级。 |
| `get_turnover_rate` | 未接入离线 mirror | 无稳定资产 | 当前优先级低。 |
| `hk.get_southbound_eligible_secs` | 无 raw mirror，但 `csml universe hk-connect` 已使用 | 稳定 universe 已存在 | 研究层面已够用，暂不急着做原始镜像。 |

## 行情

| API | 仓库接入 | 当前本地状态 | 建议 |
| --- | --- | --- | --- |
| `get_price` | 已接，`mirror-hk-daily` | 稳定 | 主线资产；当前 full-market `daily_final_latest` 是默认日线底座。 |

补充：

* 当前全市场日线 snapshot 覆盖 `3203` 个 symbol，日期范围是 `2000-01-04` 到 `2026-03-11`。
* `hk_connect` 的独立日线 snapshot 也保留了，但属于兼容资产，不再是默认入口。
* `hk_connect_full_by_date.csv` 已在 `2026-03-18` 刷新到最近完整交易日 `2026-03-17`。
* `hk_connect_full_research_by_date.csv` 也已在 `2026-03-18` 重新派生，当前覆盖 `622` 个带 PIT fundamentals 的 symbol。

## 财务

| API | 仓库接入 | 当前本地状态 | 建议 |
| --- | --- | --- | --- |
| `get_pit_financials_ex` | 已接，`mirror-hk-pit-financials` | 稳定 | 主线资产；full-market `743` 字段 snapshot 已完成。 |
| `hk.get_detailed_financial_items` | 已接，`mirror-hk-financial-details` | 小样本 probe 可用，暂无稳定全量资产 | 继续显式 `symbol + field` 小样本试，不要直接升成全量计划。 |

补充：

* `hk_all_2000_2025_full_market_latest` 是当前更完整的全市场 PIT snapshot。
* 旧的 `hk_all_2000_2025_full_latest` 空快照已经清理，不应再被配置、脚本或文档引用。
* `financial_details` 当前确认可用的 probe 是 `hk_financial_details_probe_core_2024_2025_latest/`，样本为 `00386.HK`、`00939.HK`、`01211.HK`，字段为 `operating_revenue`、`net_profit`。
* 之前那类 `743` 字段宽表 probe 会在多只股票上触发 server error，不应再作为默认试法。

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
* `industry`
  `artifacts/assets/rqdata/hk/industry_changes/hk_all_2000_20260318_industry_changes_latest/industry_labels_m.parquet`
* `universe`
  `artifacts/assets/universe/hk_all_full_by_date.csv`
  或 `artifacts/assets/universe/hk_connect_full_by_date.csv`

## 下一步建议

推荐顺序：

1. 先别重刷 `daily` 和 `pit_financials`，它们已经有稳定大资产。
2. 优先把配置、文档和脚本统一到 alias 路径，减少日期写死。
3. 只补轻量增量或小样本 probe，例如 `financial_details` 的少量 field/sample。
4. 新资产下载前，先看 `manifest.yml` 和 `quota`，不要把旧失败 probe 误认成“当前缺口”。

## 最小检查命令

```bash
csml rqdata quota --pretty
ls artifacts/assets/rqdata/hk/instruments
ls artifacts/assets/rqdata/hk/daily
sed -n '1,80p' artifacts/assets/rqdata/hk/daily/hk_all_2000_20260312_daily_final_latest/manifest.yml
sed -n '1,80p' artifacts/assets/rqdata/hk/pit_financials/hk_all_2000_2025_full_market_latest/manifest.yml
```

如果你发现这页和磁盘目录再次不一致，优先更新这页，不要再往别的文档里复制一份“临时状态”。
