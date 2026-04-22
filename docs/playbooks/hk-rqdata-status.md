# HK RQData 状态矩阵

本页解决什么：记录当前仓库里 HK / RQData 资产的真实本地状态，区分哪些已经是主线入口、哪些只是 probe、哪些其实已经失败或过时。\
本页不解决什么：不代替 CLI 参数文档，也不展开完整研究路线。\
适合谁：准备继续补 HK 资产、清理旧目录，或先判断“哪些能直接用、哪些别误用”的人。  
读完你会得到什么：当前有效入口、各接口接入状态、目录清理规则，以及下一步应该补哪里的判断。\
相关页面：`docs/playbooks/hk-data-assets.md`、`docs/playbooks/hk-selected.md`、`docs/rqdata/README.md`、`docs/cli.md`、`docs/outputs.md`、`docs/providers.md`

页面性质：`current-state` \
最后核对时间：`2026-03-26`（Asia/Shanghai）\
权威来源：当前工作区里的真实目录、alias / symlink、`manifest.yml`、`configs/presets/hk.yml`、`configs/presets/hk_quarterly_pit_hybrid.yml`\
冲突优先级：如果本页和 `config.used.yml`、当前 preset、或当前资产目录实际状态冲突，以后者为准

重要说明：

* quota 是即时信息，不写死在这页；现场执行 `cstree rqdata quota --pretty`。
* 本页只写“当前这个工作区里真实存在的状态”。旧笔记里提过的 bundle、probe、历史 snapshot，如果本地现在没有，就不算当前有效资产。
* 主线资产指已经适合被研究配置、临时脚本或后续打包复用的入口；probe只说明做过验证，不等于已经升成默认入口。
* 名字里带 `latest` 不自动等于可靠入口；要以 `manifest.yml` 的 `status` 和当前 preset / alias 指向为准。`exchange_rate` 就是反例。

## 先看结论

当前可以直接当主线入口继续维护的：

* `instruments`
  `artifacts/assets/rqdata/hk/instruments/hk_all_instruments_latest.parquet` -> `hk_all_instruments_20260318.parquet`
  `artifacts/assets/rqdata/hk/instruments/hk_connect_full_latest.parquet` -> `hk_connect_full_20260318.parquet`
* `daily`
  `artifacts/assets/rqdata/hk/daily/hk_all_daily_latest` -> `hk_all_2000_20260326_daily_final_latest`
  `2026-03-19` 到 `2026-03-26` 的尾部 patch 已本地并回 canonical snapshot；patch 目录仍保留
* `pit_financials`
  `artifacts/assets/rqdata/hk/pit_financials/hk_all_2000_2025_full_market_latest/`
  `artifacts/assets/rqdata/hk/pit_financials/hk_connect_full_2000_2025_full_latest/`
  `artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest/`
* `ex_factors / dividends / shares`
  全市场 alias 已切到 `2026-03-26` 的 `*_full_market_latest` snapshot
  另有尾部 patch：
  `artifacts/assets/rqdata/hk/ex_factors/hk_all_20260319_20260326_ex_factors_patch_20260326/`
  `artifacts/assets/rqdata/hk/dividends/hk_all_20260319_20260326_dividends_patch_20260326/`
  `artifacts/assets/rqdata/hk/shares/hk_all_20260319_20260326_shares_patch_20260326_v2/`
* `industry_changes`
  `artifacts/assets/rqdata/hk/industry_changes/hk_all_industry_changes_latest/`
  目录下已经有 `industry_labels_d/m/q.parquet`
* `southbound`
  `artifacts/assets/rqdata/hk/southbound/hk_connect_southbound_latest/`
  当前 canonical snapshot 已在 `2026-03-25` 重新做过本地 merge，覆盖到 `2026-03-24`；它是稳定补充层，不是默认研究入口
* `announcement`
  `artifacts/assets/rqdata/hk/announcement/hk_selected_2000_20260324_announcement_latest/`
  当前只有 `hk_selected` 范围的小规模原始镜像；查询窗口已前推到 `2000-01-01`，但当前最早实际 `info_date` 仍是 `2014-08-01`
* `intraday_5m`
  当前已经有 `hk_connect_research` 最近 `1` 年样本，以及全市场 `2024-05-01` 到 `2026-03-26` 的两段 `5m` parquet；细节和 quota 见 `docs/playbooks/hk-intraday-assets.md`
* `universe`
  `artifacts/assets/universe/hk_connect_full_by_date.csv`
  `artifacts/assets/universe/hk_connect_full_research_by_date.csv`
  `artifacts/assets/universe/hk_connect_full_research_symbols.txt`
  `artifacts/assets/universe/hk_selected_pit_research_by_date.csv`
  `artifacts/assets/universe/hk_selected_pit_research_symbols.txt`
  `artifacts/assets/universe/hk_all_full_by_date.csv`

当前有用，但不要写成默认主线入口的：

* `valuation`
  `artifacts/assets/rqdata/hk/valuation/hk_all_2000_20260326_valuation_full_market_latest/`
  当前全市场 `get_factor` 日频估值镜像已经落盘；`2026-03-25` 到 `2026-03-26` 的尾部 patch 已本地并回 canonical snapshot，另保留 patch 目录：
  `artifacts/assets/rqdata/hk/valuation/hk_all_20260325_20260326_valuation_patch_20260326/`
  适合长期归档 `market_cap / pe_ttm / pb` provider 口径，但仍不是默认 pipeline 入口
* `instrument_industry`
  当前 `m/q latest` 还是基于 `1547` symbol 旧口径快照；`3203` symbol 的全市场月频尝试目录已经改名成 `*_incomplete`，而且 `manifest.yml` 里是全量 `missing_remote`
* `financial_details`
  `hk_financial_details_hk_all3203_superset_2000_2025_20260319/` 这份 raw probe 可用，`analysis_hk_all3203_superset_2000_2025_local_override_v10/` 这份分析基线也可复用，但它仍然是增强层，不是主线 fundamentals
* `pit_financials` 的 `starter` 增量 probe
  `hk_all_probe_2025q4_2026q1_starter_20260319/`
  `hk_all_probe_2025q4_2026q1_starter_20260324/`
  `hk_connect_probe_2025q4_2026q1_starter_20260319/`
  `hk_connect_probe_2025q4_2026q1_starter_20260324/`
  这几份都适合做更晚 as-of 的窄增量验证；`20260324` 这批已经补出了 `pipeline_fundamentals.parquet` 和对应 research universe，但仍不是对 full snapshot 的替代
* `exchange_rate`
  短窗 probe 已经成功，但 `hk_all_2000_20260319_exchange_rate_*_latest` 这批长窗 `latest` 当前全部 `status: failed`
* `bundles / backup`
  当前 `artifacts/snapshots/` 里已经有 `hk_trial_snapshot_20260324/`
  它是本地 trial snapshot，不是 release bundle，也不应自动当成默认共享资产
  旧笔记里提过的 `hk_runtime_*`、`hk_full_ref_*`、`hk_connect_ref_*` 仍不在这个工作区里，不能当作本地现成资产
* 旧失败 probe、空目录、老的 patch / archive
  它们只说明做过尝试，不说明已经完成

## 一张短表看口径

这张表只回答一个容易混淆的问题：  
“当前仓库里的 HK / RQData 资产，到底哪些已经是主线、哪些只是 probe、时间和字段大概到了哪里？”

| dataset | 当前覆盖 | 字段口径 | 时间范围 / as-of | 当前本地状态 | 是否主线 |
| --- | --- | --- | --- | --- | --- |
| `instruments` | 全市场 snapshot `3212` symbols；另有 `hk_connect` snapshot | 固定 instrument schema | `as-of 2026-03-18` | 稳定 | 是 |
| `daily` | 按全市场 instrument 集请求 `3212` symbols，最终 `3203` symbols 有值 | 固定 `6` 个日线字段 | `2000-01-04` 到 `2026-03-26` | 稳定 | 是 |
| `pit_financials` | 全市场 full snapshot；另有 `hk_connect` / `hk_selected` 平面文件 | `743` 个字段 | `2000q1` 到 `2025q4`，`date=20260310` | 稳定 | 是 |
| `financial_details` | 请求 `3203` symbols 的全市场窄字段 probe | `3` 个字段 | `2000q1` 到 `2025q4`，`date=20260319` | raw probe + analysis | 否 |
| `exchange_rate` | `11` 个 HKD 货币对 | 短窗已验证默认 `8` 字段；另有 minimal `2` 字段 | 成功 probe 到 `2025-02-16`；`2000-2026` 长窗 `latest` 全失败 | 仅短窗 probe | 否 |
| `ex_factors` | 全市场 `3203` symbol 集请求，最终 `2668` symbols 有值；尾部 patch 已并回 canonical snapshot | API payload 固定 schema | `2000-01-01` 到 `2026-03-26` | 稳定 | 是 |
| `dividends` | 全市场 `3203` symbol 集请求，最终 `2271` symbols 有值；尾部 patch 已并回 canonical snapshot | API payload 固定 schema | `2000-01-01` 到 `2026-03-26` | 稳定 | 是 |
| `shares` | 按全市场 instrument 集请求 `3212` symbols，最终 `3203` symbols 有值；尾部 patch 已并回 canonical snapshot | 默认 `7` 个字段 | `2000-01-01` 到 `2026-03-26` | 稳定 | 是 |
| `valuation` | 按全市场日线 symbol 集请求 `3212` symbols，最终 `3204` symbols 有值；尾部 patch 已并回 canonical snapshot | 默认 `3` 个字段：`hk_total_market_val / pe_ratio_ttm / pb_ratio_ttm` | query `2000-01-01` 到 `2026-03-26`；provider 实际最早日调整到 `2000-01-03` | 稳定补充层 | 否 |
| `industry_changes` | 全市场 `3203` symbol 基线 | level-1 映射 `11` 字段 + `industry_labels_d/m/q` | `2000-01-01` 到 `2026-03-18` | 稳定 | 是 |
| `instrument_industry` | `m/q latest` 只基于 `1547` symbol 旧口径；`3203` symbol 全市场月频尝试为空 | `6` 个字段 | `2000-01-01` 到 `2026-03-18` | 旧口径快照 + incomplete 尝试 | 否 |
| `southbound` | 只覆盖 `hk_connect`；`by_date` 联合集 `967` symbols | `2` 个字段 | canonical snapshot 现为 `2014-11-17` 到 `2026-03-24`；`2026-03-25` 又重新合并了一次 base raw + tail patch | 稳定补充层 | 否 |
| `announcement` | `hk_selected` `222` symbols probe | API payload 固定 schema | query `2000-01-01` 到 `2026-03-24`；当前最早实际 `info_date=2014-08-01` | 小范围补充层 | 否 |
| `intraday_5m` | `hk_connect_research` `1` 年样本 + 全市场 `2` 段年度块 | 固定 `6` 个 `5m` 字段 | 当前 provider 实际可用范围 `2024-05-01` 到 `2026-03-26` | 稳定补充层 | 否 |

补充：

* 全市场在这页里指当前本地 symbol source 或 snapshot 口径，不等于每个 symbol 都一定从 remote 拿到了有效数据。
* `PB`、`PE`、`market_cap` 这类估值层，现在既可以走 runtime provider overlay / merge，也可以保留成离线 `valuation` raw mirror；当前本地两条链路都存在。
* 行业层建议按三层理解：
  `industry_changes` 是切换日真相层；
  `industry_labels_d/m/q` 是研究直接 join 的标签层；
  `instrument_industry` 是 provider 快照补充层。
* `2026-03-27` 已按当前 `hk_all_daily_latest` 重新构建 `industry_labels_d/m/q`；三份文件现在都对齐到 `2026-03-26` 这版 daily grid。
* `hk_connect_full_by_date.csv`、`hk_connect_full_research_by_date.csv`、`hk_selected_pit_research_by_date.csv` 都是按 rebalance date 落盘的成员明细，不是“每个交易日一整张全量成员表”。

## 当前有效入口

### 配置默认会读的入口

* `configs/presets/hk.yml`
  默认读：
  `artifacts/assets/rqdata/hk/daily/hk_all_daily_latest`
  `artifacts/assets/rqdata/hk/instruments/hk_all_instruments_latest.parquet`
  `artifacts/assets/universe/hk_connect_full_research_by_date.csv`
* `configs/presets/hk_quarterly_pit_hybrid.yml`
  默认读：
  `artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest/pipeline_fundamentals.parquet`
  `artifacts/assets/universe/hk_selected_pit_research_by_date.csv`
* `hk_selected` 相关实验配置
  当前基本都收口到 `hk_selected_pit_research_by_date.csv` 这一组 research universe

### 当前建议直接引用的 alias / snapshot

* `artifacts/assets/rqdata/hk/daily/hk_all_daily_latest`
  当前 alias，指向 `hk_all_2000_20260326_daily_final_latest`
* `artifacts/assets/rqdata/hk/daily/hk_all_20260319_20260326_daily_patch_20260326/`
  当前全市场日线尾部 patch；`2725` symbols、`16,345` 行，已本地并回 canonical snapshot；patch 目录保留作审计
* `artifacts/assets/rqdata/hk/instruments/hk_all_instruments_latest.parquet`
  当前 alias，指向 `hk_all_instruments_20260318.parquet`
* `artifacts/assets/rqdata/hk/instruments/hk_connect_full_latest.parquet`
  当前 alias，指向 `hk_connect_full_20260318.parquet`
* `artifacts/assets/rqdata/hk/pit_financials/hk_all_2000_2025_full_market_latest/pipeline_fundamentals.parquet`
  当前更完整的全市场 PIT 平面文件；`2026-03-25` 已重建为 `743` 个 value columns、`98,436` 行、`3,135` symbols
* `artifacts/assets/rqdata/hk/pit_financials/hk_connect_full_2000_2025_full_latest/pipeline_fundamentals.parquet`
  当前 `hk_connect` 宽 PIT 平面文件
* `artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest/pipeline_fundamentals.parquet`
  当前季度 PIT preset 默认入口
* `artifacts/assets/rqdata/hk/ex_factors/hk_all_ex_factors_latest`
  当前 alias，指向 `hk_all_2000_20260326_ex_factors_full_market_latest`
* `artifacts/assets/rqdata/hk/ex_factors/hk_all_20260319_20260326_ex_factors_patch_20260326/`
  当前全市场 ex-factor 尾部 patch；`10` symbols、`11` 行，已本地并回 canonical snapshot
* `artifacts/assets/rqdata/hk/dividends/hk_all_dividends_latest`
  当前 alias，指向 `hk_all_2000_20260326_dividends_full_market_latest`
* `artifacts/assets/rqdata/hk/dividends/hk_all_20260319_20260326_dividends_patch_20260326/`
  当前全市场 dividends 尾部 patch；`181` symbols、`186` 行，已本地并回 canonical snapshot
* `artifacts/assets/rqdata/hk/shares/hk_all_shares_latest`
  当前 alias，指向 `hk_all_2000_20260326_shares_full_market_latest`
* `artifacts/assets/rqdata/hk/shares/hk_all_20260319_20260326_shares_patch_20260326_v2/`
  当前全市场 shares 尾部 patch；`2724` symbols、`62,787` 行，已本地并回 canonical snapshot
* `artifacts/assets/rqdata/hk/valuation/hk_all_valuation_latest`
  当前 valuation alias，指向 `hk_all_2000_20260326_valuation_full_market_latest`
* `artifacts/assets/rqdata/hk/valuation/hk_all_2000_20260326_valuation_full_market_latest`
  当前全市场 valuation raw mirror；`3204` symbols、`10,984,164` 行
* `artifacts/assets/rqdata/hk/valuation/hk_all_20260325_20260326_valuation_patch_20260326/`
  当前全市场 valuation 尾部 patch；`2725` symbols、`5,448` 行，已本地并回 canonical snapshot
* `artifacts/assets/rqdata/hk/industry_changes/hk_all_industry_changes_latest`
  当前 alias，指向 `hk_all_2000_20260318_industry_changes_full_market_latest`
* `artifacts/assets/rqdata/hk/industry_changes/hk_all_industry_changes_latest/industry_labels_m.parquet`
  当前研究最适合直接 join 的月频行业标签；`2026-03-27` 已重建，当前最大 `trade_date=2026-03-26`
* `artifacts/assets/rqdata/hk/industry_changes/hk_all_industry_changes_latest/industry_labels_d.parquet`
  日频标签；`2026-03-27` 已重建，当前最大 `trade_date=2026-03-26`
* `artifacts/assets/rqdata/hk/industry_changes/hk_all_industry_changes_latest/industry_labels_q.parquet`
  季频标签；`2026-03-27` 已重建，当前最大 `trade_date=2026-03-26`
* `artifacts/assets/rqdata/hk/southbound/hk_connect_southbound_latest`
  当前 `hk_connect` 范围的 southbound canonical snapshot；`2026-03-25` 的 manifest 已明确记录 base raw snapshot 与 `2026-03-19` 到 `2026-03-24` tail patch 的本地合并结果
  `2026-03-25` 到 `2026-03-26` 这段当天尝试过再次 patch，但当前命令返回 `No trading dates resolved for southbound mirroring.`，所以本地稳定入口仍停在 `2026-03-24`
* `artifacts/assets/rqdata/hk/announcement/hk_selected_2000_20260324_announcement_latest`
  当前已落盘的 `announcement` raw snapshot；范围是 `hk_selected`，查询窗口从 `2000-01-01` 开始，但当前实际返回的最早公告日期仍是 `2014-08-01`

### 当前有效的 universe 入口

* `artifacts/assets/universe/hk_connect_full_by_date.csv`
  `2014-11-28` 到 `2026-03-17`
  `137` 个 rebalance date
  历史并集 `967` symbols
* `artifacts/assets/universe/hk_connect_full_research_by_date.csv`
  `2014-11-28` 到 `2026-03-17`
  `137` 个 rebalance date
  历史并集 `904` symbols
* `artifacts/assets/universe/hk_selected_pit_research_by_date.csv`
  `2014-11-28` 到 `2026-03-17`
  `137` 个 rebalance date
  历史并集 `222` symbols
* `artifacts/assets/universe/hk_all_full_by_date.csv`
  `2000-02-29` 到 `2026-03-26`
  `314` 个 rebalance date
  历史并集 `3195` symbols

### 当前保留但不是默认入口的有效目录

* `artifacts/assets/rqdata/hk/financial_details/hk_financial_details_hk_all3203_superset_2000_2025_20260319/`
  全市场窄字段 raw probe
* `artifacts/assets/rqdata/hk/financial_details/analysis_hk_all3203_superset_2000_2025_local_override_v10/`
  当前 `financial_details` 分析基线；目录下有 `normalized_long.parquet`、`analysis_manifest.yml`、`summary.md`
* `artifacts/assets/rqdata/hk/pit_financials/hk_all_probe_2025q4_2026q1_starter_20260319/`
  更晚 as-of 的全市场 starter PIT 增量
* `artifacts/assets/rqdata/hk/pit_financials/hk_all_probe_2025q4_2026q1_starter_20260324/`
  更新到 `date=20260324` 的全市场 starter 增量；目录下已经有 `pipeline_fundamentals.parquet`
* `artifacts/assets/rqdata/hk/pit_financials/hk_connect_probe_2025q4_2026q1_starter_20260319/`
  更晚 as-of 的 `hk_connect` starter PIT 增量
* `artifacts/assets/rqdata/hk/pit_financials/hk_connect_probe_2025q4_2026q1_starter_20260324/`
  更新到 `date=20260324` 的 `hk_connect` starter 增量；目录下已经有 `pipeline_fundamentals.parquet`
* `artifacts/assets/rqdata/hk/financial_details/hk_financial_details_portable_bundle_20260324/`
  `financial_details` 的试验性便携打包目录；说明这条线还在推进，但不改变“仍非主线 fundamentals”的判断
* `artifacts/assets/rqdata/hk/valuation/hk_all_valuation_latest`
  当前全市场日频估值镜像 alias；适合长期归档 provider 口径，但研究主线仍优先 runtime `provider_overlay`
* `artifacts/assets/universe/hk_all_probe_2025q4_2026q1_starter_20260319_research_by_date.csv`
  对应上面全市场 starter 增量派生出的 research universe
* `artifacts/assets/universe/hk_all_probe_2025q4_2026q1_starter_20260324_research_by_date.csv`
  对应 `20260324` 全市场 starter 增量派生出的 research universe
* `artifacts/assets/universe/hk_connect_probe_2025q4_2026q1_starter_20260319_research_by_date.csv`
  对应上面 `hk_connect` starter 增量派生出的 research universe
* `artifacts/assets/universe/hk_connect_probe_2025q4_2026q1_starter_20260324_research_by_date.csv`
  对应 `20260324` `hk_connect` starter 增量派生出的 research universe

### 当前运行时 cache 补充

* `artifacts/cache/`
  当前不是只有一层日线 symbol cache。
* `artifacts/cache/intraday/`
  当前已经有 `hk_connect_research` `5m` 样本，以及全市场 `hk_all_5m_20240501_20250326`、`hk_all_5m_20250327_20260326` 两段分钟线 cache；两段都保留了 `.parts/` checkpoint，可直接断点续跑或分批做滑点聚合
* `artifacts/cache/hk_rqdata_daily_<symbol>.parquet`
  当前本地有 `328` 个 HK 日线 cache 文件；这层会在 provider / local asset 读取后继续回写。
  当前没看到 `hk_rqdata_daily_<symbol>_<start>_<end>.parquet` 这类 `range/window` 命名，说明现有日线 runtime cache 仍全部落在 `symbol` 模式。
* `artifacts/cache/hk_rqdata_basic_*.parquet`
  当前本地有 `2` 个 basic cache 文件，而且都是带 digest 的 symbol-subset cache；当前没有未加哈希的 `hk_rqdata_basic.parquet`。
* `artifacts/cache/fundamentals/hk/`
  当前顶层有 `1194` 个 fundamentals cache 文件；其中默认 namespace `hk_rqdata_*` 有 `972` 个，`hk_selected_tr_close` 这个 `cache_tag` namespace 另有 `222` 个。
* `artifacts/cache/fundamentals/hk/provider_valuation_merge/`
  当前还有 `222` 个 merge-stage parquet；把这层也算上时，`artifacts/cache/fundamentals/hk/` 下总共有 `1416` 个 parquet。它们都是 runtime valuation overlay / merge cache，不是离线 raw mirror 资产。

### 当前不要引用成默认入口的路径

* `artifacts/assets/rqdata/hk/exchange_rate/hk_all_2000_20260319_exchange_rate_latest/`
* `artifacts/assets/rqdata/hk/exchange_rate/hk_all_2000_20260319_exchange_rate_chunked_latest/`
* `artifacts/assets/rqdata/hk/exchange_rate/hk_all_2000_20260319_exchange_rate_minimal_latest/`
* `artifacts/assets/rqdata/hk/exchange_rate/hk_all_2000_20260319_exchange_rate_tty_latest/`

这些目录名字看起来像“当前 alias”，但 `manifest.yml` 都是 `status: failed`，不能当作稳定入口。  
另外 `hk_exchange_rate_probe_202501/`、`hk_exchange_rate_probe_2025_fullyear/` 和 `hk_exchange_rate_probe_2025_fullyear_minimal/` 这几类更长窗 probe 当前也都是 `status: failed`。  
当前真正成功的 `exchange_rate` 资产是短窗 probe：

* `hk_exchange_rate_probe_20250210_20250211_minimal/`
  `2` 字段，`2` 天，`11` 个货币对
* `hk_exchange_rate_probe_20250210_20250211/`
  默认 `8` 字段，`2` 天，`11` 个货币对
* `hk_exchange_rate_probe_20250210_20250212/`
  默认 `8` 字段，`3` 天，`11` 个货币对
* `hk_exchange_rate_probe_20250210_20250216/`
  默认 `8` 字段，`6` 天，`11` 个货币对

如果你要写配置、文档示例或临时脚本，优先引用上面这些 alias、有效 snapshot 和当前 preset 默认路径，避免再次把日期写死到多个地方。

## 接口状态矩阵

### 基础信息

| API | 仓库接入 | 当前本地状态 | 建议 |
| --- | --- | --- | --- |
| `all_instruments` | 已接，`cstree rqdata export-hk-instruments` | 稳定 | 继续维护，属于主数据入口。 |
| `instruments` | 无单独 mirror 命令 | 间接覆盖 | 只在缺细节时按需调，不必单独做离线体系。 |
| `get_ex_factor` | 已接，`mirror-hk-ex-factors` | 稳定，full / connect 都在 | 继续保留，属于复权原料层。 |
| `get_dividend` | 已接，`mirror-hk-dividends` | 稳定，full / connect 都在 | 继续保留，属于股息原料层。 |
| `get_shares` | 已接，`mirror-hk-shares` | 稳定，full / connect 都在 | 继续保留，属于股本原料层。 |
| `get_exchange_rate` | 已接，`mirror-hk-exchange-rate` | 短窗 probe 成功；长窗 `latest` 当前全部失败 | 继续用 staged backfill 思路，不要把当前状态写成“全历史已齐”。 |
| `get_industry` | 无单独 mirror 命令 | 无独立稳定资产 | 优先级低于 `industry_changes`。 |
| `get_industry_change` | 已接，`mirror-hk-industry-changes` | 稳定 | 行业切换真相层，优先保留。 |
| `get_instrument_industry` | 已接，`mirror-hk-instrument-industry` | `m/q latest` 有效，但还是旧口径；全市场月频尝试为空 | 便捷快照层；不要把 `_incomplete` 目录当 latest。 |
| `get_industry_mapping` | 间接覆盖 | 已写到 `industry_changes` 目录 | 作为字典表看待，不必单独升级。 |
| `get_turnover_rate` | 未接入离线 mirror | 无稳定资产 | 当前优先级低。 |
| `hk.get_southbound_eligible_secs` | 已接，`mirror-hk-southbound` | `hk_connect` 范围 raw snapshot 已稳定落盘；full-market raw snapshot 仍无 | 默认研究仍可直接用现有 universe；需要资格审计或纳入回放时优先复用。 |

### 行情

| API | 仓库接入 | 当前本地状态 | 建议 |
| --- | --- | --- | --- |
| `get_price` | 已接，`mirror-hk-daily` | 稳定 | 主线资产；当前 full-market `daily_final_latest` 是默认日线底座。 |

补充：

* 当前全市场日线 snapshot 的 query 范围是 `3212` symbols，最终 `3203` symbols 有值。
* 日期范围是 `2000-01-04` 到 `2026-03-26`。
* `hk_connect` 的独立日线 snapshot 也还在本地，但已经不是默认入口。
* `hk_connect_full_by_date.csv` 已在 `2026-03-18` 生成到最近完整 rebalance date `2026-03-17`。
* `hk_connect_full_research_by_date.csv` 按当前文件现算覆盖 `329` 个 symbol。
* `hk_selected_pit_research_by_date.csv` 按当前文件现算覆盖 `218` 个 symbol，给 `hk_selected` 系列配置使用。

### 财务

| API | 仓库接入 | 当前本地状态 | 建议 |
| --- | --- | --- | --- |
| `get_pit_financials_ex` | 已接，`mirror-hk-pit-financials` | 稳定 | 主线资产；full-market `743` 字段 snapshot 已完成。 |
| `hk.get_detailed_financial_items` | 已接，`mirror-hk-financial-details` | 全市场窄字段 probe 可用，但仍非主线资产 | 继续显式 `field` 白名单增强，不要直接升成全字段计划。 |

补充：

* `hk_all_2000_2025_full_market_latest` 是当前更完整的全市场 PIT snapshot；目录下已经有 `pipeline_fundamentals.parquet`。
  `2026-03-25` 这次重建后，`pipeline_fundamentals.parquet` 已经恢复成真正的全字段 flat file：`743` 个 value columns、`745` 列总宽度、`98,436` 行、`3,135` 个 symbol、压缩后约 `23 MB`。
* `hk_connect_full_2000_2025_full_latest/pipeline_fundamentals.parquet` 也是当前有效入口。
* `hk_selected_pit_2011_2025_latest/pipeline_fundamentals.parquet` 仍然是季度 PIT preset 默认入口。
* `hk_selected_pit_2011_2025_latest/manifest.yml` 里仍保留了历史 `data_assets/`、`config/...` 路径痕迹；当前应以实际目录 `artifacts/assets/...` 和 preset 文件里的路径为准。
* `hk_all_probe_2025q4_2026q1_starter_20260319/` 已生成 `pipeline_fundamentals.parquet`；raw mirror 请求 `3203` symbols、实际 `856` symbols 写出，平面文件当前覆盖 `310` 个 symbol。
* `hk_all_probe_2025q4_2026q1_starter_20260324/` 现在也已生成 `pipeline_fundamentals.parquet`；raw mirror 请求 `3190` symbols、实际 `1065` symbols 写出，平面文件当前覆盖 `520` 个 symbol。
* `hk_connect_probe_2025q4_2026q1_starter_20260319/` 也已生成 `pipeline_fundamentals.parquet`；raw mirror 请求 `967` symbols、实际 `189` symbols 写出，平面文件当前覆盖 `131` 个 symbol。
* `hk_connect_probe_2025q4_2026q1_starter_20260324/` 现在也已生成 `pipeline_fundamentals.parquet`；raw mirror 请求 `967` symbols、实际 `293` symbols 写出，平面文件当前覆盖 `232` 个 symbol。
* `hk_all_probe_2025q4_2026q1_starter_20260324_research_by_date.csv` 已存在，当前覆盖 `314` 个 rebalance date、`520` 个 symbol。
* `hk_connect_probe_2025q4_2026q1_starter_20260324_research_by_date.csv` 也已存在，当前覆盖 `137` 个 rebalance date、`232` 个 symbol。
* `financial_details` 当前最完整的 raw probe 是 `hk_financial_details_hk_all3203_superset_2000_2025_20260319/`：请求 `3203` 个 symbol、`3` 个字段、`2000q1-2025q4`，实际写出 `345` 个 parquet。
* 对这份 raw probe 的标准化分析基线是 `analysis_hk_all3203_superset_2000_2025_local_override_v10/`；它说明“窄字段增强层”已经有可复用分析入口，但不等于已经适合升成主线宽表。
* `2026-03-24` 又新增了一批 `financial_details` smoke / probe 目录和 `portable_bundle`；它们说明探索还在继续，但不改变“主线仍不是 financial_details 宽表”的判断。
* 把 `financial_details` 当成“直接补齐成 `743` 字段宽表”的路线，当前仍不成立。

### 因子与公告

| API | 仓库接入 | 当前本地状态 | 建议 |
| --- | --- | --- | --- |
| `get_factor` | runtime overlay + `mirror-hk-valuation` | 全市场 `3` 字段 valuation snapshot 已落盘 | 平时研究仍优先 runtime overlay；如果要防 provider 权限失效，这份离线镜像值得保留。 |
| `get_all_factor_names` | 未接入 | 无 | 需要字段浏览时再补。 |
| `hk.get_announcement` | 已接，`mirror-hk-announcement` | `hk_selected` 范围小规模 raw snapshot 已落盘 | 继续按 `hk_selected` / `hk_connect` 小范围保留，不要直接升成全市场主线。 |

## 目录清理规则

现在磁盘里的 HK 目录建议按下面的规则理解：

* `hk_all_*_latest`、`hk_all_*_full_market_latest`、`hk_connect_*_latest`
  先看它是不是 symlink，再看目标目录里的 `manifest.yml`
  对大多数数据集这类路径是主线入口，但 `exchange_rate` 是反例
* `probe_*`
  默认都先当实验目录看；只有明确写出了有效数据、而且你决定长期保留时，才值得继续留
* `*_incomplete`
  直接当失败或未完成尝试看，不要继续当 latest 引用
* `*_patch_*`
  当作修补中间产物看，不是新的主入口
* `daily/_archive_20260314/`
  这是历史中间产物归档，不是默认入口
* `artifacts/snapshots/`
  当前已经有 `hk_trial_snapshot_20260324/`，但它是本地试验快照，不等于发布级 bundle

## 现在推荐的默认组合

如果目标是“继续稳定研究，不想再被旧目录绕进去”，默认按下面两组入口理解：

### 月频 HK preset

* `daily`
  `artifacts/assets/rqdata/hk/daily/hk_all_daily_latest`
* `instruments`
  `artifacts/assets/rqdata/hk/instruments/hk_all_instruments_latest.parquet`
* `universe`
  `artifacts/assets/universe/hk_connect_full_research_by_date.csv`
* `fundamentals`
  默认仍是 runtime provider valuation overlay，不是本地 raw PIT 文件

### 季度 PIT preset / hk_selected

* `daily`
  行情仍来自本地日线或 runtime 日线，不是单独的季度行情资产
* `pit fundamentals`
  `artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest/pipeline_fundamentals.parquet`
* `universe`
  `artifacts/assets/universe/hk_selected_pit_research_by_date.csv`

### 全市场 raw baseline

如果你是在补底层资产，而不是直接跑 preset，优先用下面这组：

* `daily`
  `artifacts/assets/rqdata/hk/daily/hk_all_daily_latest`
* `pit_financials`
  `artifacts/assets/rqdata/hk/pit_financials/hk_all_2000_2025_full_market_latest/`
* `reference`
  `artifacts/assets/rqdata/hk/ex_factors/hk_all_ex_factors_latest`
  `artifacts/assets/rqdata/hk/dividends/hk_all_dividends_latest`
  `artifacts/assets/rqdata/hk/shares/hk_all_shares_latest`
* `valuation`
  `artifacts/assets/rqdata/hk/valuation/hk_all_valuation_latest`
  这是 provider 口径的 `market_cap / pe_ttm / pb` 离线冻存，不是默认 pipeline 入口
* `industry`
  `artifacts/assets/rqdata/hk/industry_changes/hk_all_industry_changes_latest/industry_labels_m.parquet`
  当前已对齐到 `hk_all_daily_latest` 的最近日期 `2026-03-26`
* `full-market universe`
  `artifacts/assets/universe/hk_all_full_by_date.csv`

## 下一步建议

推荐顺序：

1. 保持当前主线仍然是 `未复权日线 + ex_factors + dividends + shares`，不要为了复权口径重刷 `daily`。
2. 如果只是继续研究，优先复用 `hk_all_2000_2025_full_market_latest` 和现成 research universe，不要先去追新的大重刷。
3. 如果要补更晚 as-of date，优先把 `20260319` / `20260324` 这些 `starter` PIT probe 当成增量验证，不要把它们误当 full snapshot 替代品。
4. `financial_details` 继续走少量 field / sample 的白名单增强路线；`analysis_hk_all3203_superset_2000_2025_local_override_v10/` 可以作为当前审阅基线。
5. `exchange_rate` 如果还要推进，先用短窗或分段窗口 staged backfill，不要直接把 `2000-2026` 长窗 `latest` 写进脚本。
6. 配置、文档和临时脚本优先引用 alias 或当前 preset 默认路径，减少日期写死。
7. 如果你需要真正可复用的备份目录，现在应该显式新建命名清晰的 snapshot，而不是默认把 `hk_trial_snapshot_20260324/` 当成发布级 bundle。
8. 新资产下载前，先看 `manifest.yml` 和 `quota`，不要把旧失败目录误认成当前缺口。

补充判断：

* 当前最有价值的仍然是研究会反复扫的底层原料：`daily`、`pit_financials`、`ex_factors`、`dividends`、`shares`、`industry_changes`。
* 当前不值得升级成“更宽、更杂”主线缓存对象的，主要是 `exchange_rate` 长窗镜像、`financial_details` 宽表化、`instrument_industry` 全市场月频、`get_turnover_rate`、大而全 `get_factor` factor zoo，以及全市场化的 `hk.get_announcement`。
* 如果你还想优先补“以后可能会后悔没下”的东西，当前优先级通常是把 `southbound` 和行业相关资产保持干净，其次才是继续追更宽的补充层接口。

## 最小检查命令

```bash
cstree rqdata quota --pretty
ls -l artifacts/assets/rqdata/hk/daily
readlink -f artifacts/assets/rqdata/hk/daily/hk_all_daily_latest
sed -n '1,80p' artifacts/assets/rqdata/hk/daily/hk_all_daily_latest/manifest.yml
sed -n '1,80p' artifacts/assets/rqdata/hk/pit_financials/hk_all_2000_2025_full_market_latest/manifest.yml
sed -n '1,80p' artifacts/assets/rqdata/hk/exchange_rate/hk_all_2000_20260319_exchange_rate_minimal_latest/manifest.yml
ls -la artifacts/snapshots
```

如果你发现这页和磁盘目录再次不一致，优先更新这页，不要再往别的文档里复制一份临时状态。
