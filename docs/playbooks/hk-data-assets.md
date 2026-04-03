# HK 数据下载与整备

本页解决什么：说明 HK 研究里各类离线资产怎么准备、落到哪里、彼此怎么衔接。  
本页不解决什么：不展开模型路线选择，也不代替完整 CLI 参数文档。  
适合谁：准备做 HK PIT 研究、整理本地 HK RQData 资产，或准备跨机器复用资产的人。  
读完你会得到什么：一套按优先级可执行的数据准备顺序，以及“股票池、日线、PIT、行业、备份”之间的清晰关系。  
相关页面：`docs/playbooks/hk-selected.md`、`docs/playbooks/hk-rqdata-status.md`、`docs/rqdata/README.md`、`docs/playbooks/research-template-design.md`、`docs/cli.md`、`docs/config.md`、`docs/outputs.md`、`docs/providers.md`

页面性质：`current-state`  
最后核对时间：`2026-03-25`  
权威来源：当前仓库代码、preset 配置、工作区 alias / `manifest.yml` 与本页引用的默认入口  
冲突优先级：如果与当前 preset、`manifest.yml`、`docs/playbooks/hk-rqdata-status.md` 或真实资产目录冲突，以更具体的资产状态和目录为准

本页已经按当前仓库代码、配置默认值和工作区里的 alias 重新整理。  
它的重点是“怎么准备”和“各层之间怎么配合”；如果你要看当前有哪些 snapshot 已完成、哪些只是 probe、哪些目录已经过时，请再看 [hk-rqdata-status.md](./hk-rqdata-status.md)。

## 先看结论

1. 先定研究入口，再准备资产。当前仓库里，月频 HK 预设默认读 `artifacts/assets/universe/hk_connect_full_research_by_date.csv`；季度 PIT 预设和 `hk_selected` 系列默认读 `artifacts/assets/universe/hk_selected_pit_research_by_date.csv`。
2. 日线层优先分成两套看待：可复用、可备份的 `daily snapshot`，以及日常研究会自动刷新的 `symbol cache`。前者用于归档和离线复用，后者用于平时跑研究补尾部。
3. PIT 路线的关键不只是把 raw mirror 拉下来，还要继续生成 `pipeline_fundamentals.parquet`；需要时再顺手派生一份 research-ready `universe by-date`。
4. `ex_factors`、`dividends`、`shares`、`industry_changes` 属于长期有价值的底层原料层。`southbound` 是高价值补充层。`exchange_rate` 和 `financial_details` 当前仍应按 probe / staged backfill 思路推进。
5. HK 日频估值默认仍建议走 runtime `provider_overlay`；但如果你要在 provider 访问结束前冻结 `market_cap / pe_ttm / pb` 口径，现在也支持单独镜像 `valuation` 资产。
6. 研究配置通常走 alias；打包和 Release 工具走静态 preset。两者不是一回事，不能默认“打包脚本会自动跟随 alias”。

## 当前默认入口

下面这些入口是当前仓库主链路里真正会被默认配置读到的东西：

| 场景 | 当前默认入口 | 说明 |
| --- | --- | --- |
| HK 月频研究 | `configs/presets/hk.yml` | 默认使用 `artifacts/assets/rqdata/hk/daily/hk_all_daily_clean_latest`、`artifacts/assets/rqdata/hk/instruments/hk_all_instruments_latest.parquet`、`artifacts/assets/universe/hk_connect_full_research_by_date.csv` |
| HK 季频 PIT 研究 | `configs/presets/hk_quarterly_pit_hybrid.yml` | 默认使用 `artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest/pipeline_fundamentals.parquet` 和 `artifacts/assets/universe/hk_selected_pit_research_by_date.csv` |
| 全市场离线 alias | `artifacts/assets/rqdata/hk/.../hk_all_*_latest` | 当前工作区里 `daily`、`instruments`、`ex_factors`、`dividends`、`shares`、`industry_changes` 这些 alias 已切到当前可用的 canonical snapshot；其中价格与 reference 层已前移到 `2026-03-26` |
| 行业标签 alias 所在目录 | `artifacts/assets/rqdata/hk/industry_changes/hk_all_industry_changes_latest/` | 当前目录下已经有 `industry_labels_d/m/q.parquet`，研究直接 join 时优先用这些派生文件 |

需要单独注意的一点：

* 研究默认读取的 `daily` alias 现在是 `hk_all_daily_clean_latest`；`hk_all_daily_latest` 继续保留原始日线底座，给资产巡检、patch merge 和 clean-layer 重建用。
* `src/csml/release_tools/package_assets.py` 里的 preset 是静态快照名，不是 alias 解析器。
* 当前 `hk_full` / `hk_connect` preset 里的 `daily_snapshot` 已更新到 `hk_all_2000_20260326_daily_final_latest`，但它依然是静态名字，不会自动跟着 alias 再往前走。
* `southbound` 和 `financial_details` 现在也能打成独立 part；`exchange_rate` 默认走的是一个已完成的短窗 probe snapshot，不是假装“2000-至今”的长窗都已经成功。
* 如果你要打包“当前 alias 指向的版本”，请显式传 `--daily-snapshot`、`--instruments-file`、`--pit-snapshot`、`--exchange-rate-snapshot`、`--southbound-snapshot`、`--financial-details-snapshot` 等参数，不要默认 preset 会自动前进。

## 资产地图

| 层级 | 主要命令 | 默认输出位置 | pipeline 是否直接读取 | 主要作用 |
| --- | --- | --- | --- | --- |
| 港股通 PIT 股票池 | `csml universe hk-connect` | `artifacts/assets/universe/` | 否，读取的是生成出的 `by_date_file` | 决定某只股票在哪些日期属于研究股票池 |
| HK 全市场 by-date 股票池 | `csml universe hk-daily-assets` | `artifacts/assets/universe/` | 否，读取的是生成出的 `by_date_file` | 从本地日线镜像派生更宽的研究股票池 |
| instrument 快照 | `csml rqdata export-hk-instruments` | `artifacts/assets/rqdata/hk/instruments/` | 是，配 `data.rqdata.instruments_file` 后直读 | 保留 `listed_date`、`de_listed_date`、`round_lot` 等元数据 |
| daily snapshot | `csml rqdata mirror-hk-daily` | `artifacts/assets/rqdata/hk/daily/<snapshot>/` | 是，配 `data.rqdata.daily_asset_dir` 后直读 | 离线归档和跨机器复用的日线底座 |
| daily query cache | pipeline 首次拉取时自动写入 | `artifacts/cache/hk_rqdata_daily_<symbol>.parquet` | 是，runtime query cache | 日常研究加速和尾部刷新 |
| PIT 财务镜像 | `csml rqdata mirror-hk-pit-financials` | `artifacts/assets/rqdata/hk/pit_financials/<snapshot>/` | 否，需继续构建 flat file | 保留按 symbol 分开的原始 PIT 财务资产 |
| 平面 fundamentals 文件 | `csml rqdata build-hk-pit-fundamentals` | `<pit_snapshot>/pipeline_fundamentals.parquet` | 是，`fundamentals.source=file` 时直读 | 给 pipeline 直接读取的 PIT 平面文件 |
| 参考数据镜像 | `mirror-hk-ex-factors` / `mirror-hk-dividends` / `mirror-hk-shares` | `artifacts/assets/rqdata/hk/ex_factors/` 等 | 否 | 保留复权、分红、股本原料 |
| 日频估值镜像 | `mirror-hk-valuation` | `artifacts/assets/rqdata/hk/valuation/<snapshot>/` | 否 | 冻结 `get_factor` 的 `market_cap / pe_ttm / pb` 等日频估值口径 |
| 汇率镜像 | `mirror-hk-exchange-rate` | `artifacts/assets/rqdata/hk/exchange_rate/<snapshot>/` | 否 | 给 `financial_details` 或跨币种派生提供汇率原料 |
| 港股通原始资格历史 | `mirror-hk-southbound` | `artifacts/assets/rqdata/hk/southbound/<snapshot>/` | 否 | 做资格审计、渠道回放和纳入日期核对 |
| 公告原始镜像 | `mirror-hk-announcement` | `artifacts/assets/rqdata/hk/announcement/<snapshot>/` | 否 | 做事件研究、披露时点回放和公告分类审计 |
| 行业真相层 | `mirror-hk-industry-changes` | `artifacts/assets/rqdata/hk/industry_changes/<snapshot>/` | 否，需继续派生 labels | 保留行业切换区间，适合回放切换日 |
| 行业快照层 | `mirror-hk-instrument-industry` | `artifacts/assets/rqdata/hk/instrument_industry/<snapshot>/` | 否 | 按指定日期拿 provider 快照，便于核对 |
| 本地行业标签文件 | `build-hk-industry-labels` | `<industry_changes_snapshot>/industry_labels_<freq>.parquet` | 是，配 `industry.file` 后直读 | 给研究直接 join 的日/月/季行业标签 |
| 本地快照备份 | `csml backup-data` | `artifacts/snapshots/<name>/` | 否 | 把缓存、股票池、配置和额外资产一起归档 |

## 推荐准备顺序

建议按下面的顺序做，而不是见到哪个接口就先拉哪个：

1. 先检查本地已有 snapshot、alias 和 `manifest.yml`，再看 `csml rqdata quota --pretty`。大资产优先复用现有目录，不要先重下。
2. 先确定研究股票池入口。
3. 导出一份 instrument 快照。
4. 决定日线层走哪条路：独立 `daily snapshot` 还是仅靠 pipeline symbol cache。
5. 如果走 PIT 路线，再镜像 `pit_financials`。
6. 继续执行 `build-hk-pit-fundamentals`，必要时同时派生 research-ready `universe by-date` 和 symbol 列表。
7. 如果你需要复权、总回报、市值或股本口径，再补 `ex_factors`、`dividends`、`shares`；如果你还要保留 provider 原始 `PE/PB/market_cap` 口径，再额外补一份 `valuation`。
8. 如果你要做行业中性、行业暴露或切换日回放，再补 `industry_changes`，然后派生 `industry_labels_<freq>`；`instrument_industry` 只在你明确需要 provider 快照时再补。
9. 如果你要保留港股通资格历史，再补 `southbound`。
10. 如果你要做跨币种 `financial_details` 处理，再补 `exchange_rate`。
11. 数据准备完毕后，用 `csml backup-data` 做本地快照；如果还要跨机器共享，再走 `package_assets` / `release_assets`。

补充：

* `hk_connect_full_research_by_date.csv` 和 `hk_selected_pit_research_by_date.csv` 这两类 research universe，推荐从本地 `pipeline_fundamentals.parquet` 过滤派生，不要手工维护。
* 当前仓库里的默认研究入口已经收口到这两组 research universe；`hk_connect_full_by_date.csv` 和 `hk_all_full_by_date.csv` 更偏原始或宽覆盖层。

## 先厘清一个最容易混淆的关系

`universe.by_date_file` 和本地数据资产控制的是两件不同的事：

1. `universe.by_date_file` 控制的是某只股票在哪些日期能进入研究样本。
2. daily / PIT / southbound / industry 这类镜像资产控制的是本地保留了这只股票多长的历史。

对港股通 PIT universe 来说，这一点尤其关键：

* 股票池文件只负责成员日期。
* 某只股票一旦进入本次镜像的 symbol 集合，下载逻辑通常会按你请求的整个历史区间拉数据。
* 下载逻辑不会把数据自动裁成“只保留它在港股通期间的片段”。

这意味着：

* 某只股票后来才加入港股通，它更早的日线和财务历史仍然可以保留在本地。
* 某只股票后来被移出港股通，它被移出后的研究日期会被 `by_date_file` 过滤掉。
* 股票池决定的是“能不能参与某天的研究”，不是“本地能不能保留这只股票更早的历史”。

## 日线层怎么准备

### 1. 先选落地方式：独立 snapshot 还是 pipeline cache

日线层当前有两条路径：

| 方式 | 写到哪里 | 适合什么 | 不适合什么 |
| --- | --- | --- | --- |
| `csml rqdata mirror-hk-daily` | `artifacts/assets/rqdata/hk/daily/<snapshot>/` | 可备份、可复用、可跨机器共享、支持 `--resume` 的离线归档 | 只想在本机平时跑研究、顺手补尾部 |
| pipeline symbol cache | `artifacts/cache/hk_rqdata_daily_<symbol>.parquet` | 日常研究提速、尾部刷新、按需补最近几天 | 想拿到一份结构完整的离线资产目录 |

如果你的目标是“建立一份可以长期复用的 HK 日线底座”，优先用 `mirror-hk-daily`。

示例：

```bash
csml rqdata mirror-hk-daily \
  --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv \
  --start-date 20000101 \
  --end-date 20260318 \
  --name hk_connect_full_2000_20260318_daily_latest \
  --resume
```

这条命令的要点：

* 默认字段是 `open/high/low/close/volume/total_turnover`。
* HK 日线默认 `skip_suspended=true`。
* 输出目录会写 `manifest.yml`、`audit.csv`、`fields.txt`、`symbols.txt` 和 `data/<symbol>.parquet`。
* 当前实现按 symbol 请求和落盘，`--resume` 实际上是“要求输入参数一致，然后跳过已有 symbol 文件”。
* provider 层面对 HK 历史起点的实际可用范围会把早于 `2000-01-04` 的请求裁到 `2000-01-04`。

如果你只是要给 pipeline 平时跑研究提速，symbol cache 的逻辑更简单：

1. pipeline 按 symbol 调 `fetch_daily`
2. `data.cache_mode=symbol` 命中 symbol cache 逻辑
3. 结果写到 `artifacts/cache/hk_rqdata_daily_<symbol>.parquet`

这套缓存逻辑的特点：

* 默认一个 symbol 一个缓存文件。
* 本地已有缓存时，会按 `data.cache_refresh_days` 只刷新尾部区间。
* 适合长期维护一套“会自己补最后几天”的研究缓存。
* 即使你已经配置了本地 `daily_asset_dir` + `instruments_file`，pipeline 仍会先看 symbol cache；cache miss 时，本地 asset 读出的结果也会回写到 `artifacts/cache/`。所以 `daily snapshot` 和 runtime `symbol cache` 是叠加关系，不是严格二选一。

### 2. 离线运行 pipeline 需要哪两个配置

如果你已经有本地日线镜像，并希望 `provider=rqdata` 时完全直读本地资产，需要同时提供：

* `data.rqdata.daily_asset_dir`
* `data.rqdata.instruments_file`

两者齐全时，pipeline 会直接读本地资产并跳过 `rqdatac.init`。  
只配一个通常不够，因为日线和 instrument 元数据是一套一起生效的离线路径。

### 3. 从 daily snapshot 反推全市场 universe

如果你的目标是“先有一套宽覆盖的 full-market daily，再从它派生研究股票池”，入口是：

```bash
csml universe hk-daily-assets \
  --config configs/presets/universe/hk_all_assets.yml \
  -- --end-date 20260318
```

这个工具当前的发现逻辑是：

* 先找最新的 `hk_all_*_daily_final_latest`
* 找不到时再回退旧命名 `hk_all_*_daily_full_latest`

如果你本地同时保留了多版日线镜像，最好显式传 `--daily-asset-dir`，不要把版本选择交给自动发现。

常见顺序是：

1. 先镜像一份 full-market daily。
2. 再跑 `csml universe hk-daily-assets` 派生 `hk_all_full_by_date.csv`。
3. 需要完全离线时，把配置里的 `universe.by_date_file` 指到 `artifacts/assets/universe/hk_all_full_by_date.csv`。
4. 同时补好 `data.rqdata.daily_asset_dir` 和 `data.rqdata.instruments_file`。

### 4. 为什么不推荐为了复权再单独重跑一套日线

当前更推荐的底层分层是：

* 一套未复权 daily
* 一套 `ex_factors`
* 一套 `dividends`
* 需要市值、自由流通或港股流通口径时，再补 `shares`

原因很简单：

* 未复权 daily 是更稳定的底层原料。
* 有了 `ex_factors` 和 `dividends`，前复权、总回报和股息相关派生都可以本地重建。
* `shares` 决定市值和流通口径，长期价值通常高于直接囤一套派生价格。

还要单独记住一件事：

* `mirror-hk-daily --resume` 当前不会在旧 parquet 上追加新的交易日。
* 它的行为是“参数匹配后跳过已有 symbol 文件”，不是“沿着旧文件继续 append 最新日期”。
* 所以“补最近几天”更适合走 pipeline symbol cache；“生成一份更新到更晚日期的完整离线目录”才适合新建 snapshot。

## PIT、参考资产与汇率层

### 1. instrument 快照先准备

instrument 是 HK 离线体系里最轻、但几乎处处会用到的元数据层。建议尽早准备：

```bash
csml rqdata export-hk-instruments \
  --out artifacts/assets/rqdata/hk/instruments/hk_all_instruments_latest.parquet
```

它主要保留：

* `listed_date`
* `de_listed_date`
* `round_lot`
* 其他 instrument 元数据

### 2. PIT raw mirror：先把原始财务资产冻住

PIT 财务镜像的典型命令：

```bash
csml rqdata mirror-hk-pit-financials \
  --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv \
  --field-profile full \
  --start-quarter 2000q1 \
  --end-quarter 2025q4 \
  --date 20260310 \
  --batch-size 5 \
  --name hk_connect_full_2000_2025_full_latest \
  --resume
```

这条链路的要点：

* `--by-date-file` 会先解析 symbol 集合，再按 symbol 拉整个 quarter 区间。
* 目录内部同样会写 `manifest.yml`、`audit.csv`、`fields.txt`、`symbols.txt` 和 `data/<symbol>.parquet`。
* 做大范围镜像时，最好固定 `--name`、`--date`、`--start-quarter`、`--end-quarter`，并始终带 `--resume`。
* HK PIT 历史覆盖最终能追到多早，取决于 provider 实际返回；不要把“请求从 `2000q1` 开始”直接理解成“每个 symbol 都一定从 `2000q1` 连续可得”。

### 3. `build-hk-pit-fundamentals`：把 raw PIT 变成 pipeline 能直接读的文件

只拉 raw mirror 不够。研究主链路真正直接消费的是平面 fundamentals 文件。

```bash
csml rqdata build-hk-pit-fundamentals \
  --asset-dir artifacts/assets/rqdata/hk/pit_financials/hk_connect_full_2000_2025_full_latest \
  --out artifacts/assets/rqdata/hk/pit_financials/hk_connect_full_2000_2025_full_latest/pipeline_fundamentals.parquet \
  --source-universe-by-date artifacts/assets/universe/hk_connect_full_by_date.csv \
  --universe-by-date-out artifacts/assets/universe/hk_connect_full_research_by_date.csv \
  --symbols-out artifacts/assets/universe/hk_connect_full_research_symbols.txt
```

这一步会做的事情：

* 把 `trade_date` 映射为原始 PIT 行的 `info_date`
* 对 `trade_date + symbol` 做去重，默认策略是 `keep-last`
* 生成 pipeline 直接可读的 `pipeline_fundamentals.parquet`
* 如果同时提供 `--source-universe-by-date` 和 `--universe-by-date-out`，再顺手派生一份“只保留本地确实有 PIT flat data 的 symbol”研究股票池

构建时还有几个常用参数：

* `--duplicate-policy error`
  如果你不想自动保留最后一行，而是希望发现重复后直接报错
* `--keep-meta`
  如果你还想保留 `quarter`、`info_date`、`fiscal_year`、`rice_create_tm` 等 PIT 元数据列
* `--field-profile`、`--field`、`--fields-file`
  如果你要在 flat file 里只保留一部分值列
  `2026-03-25` 之后，`--field-profile full` 已经会正确覆盖 asset manifest 里的 starter 选择，适合把 `hk_all` 这种 full snapshot 重建成真正的 `743` 字段 flat file

这也是为什么当前 research universe 不建议手工维护：  
更稳妥的方式是直接从本地 flat fundamentals 反推，保证“股票池”和“本地财报可用性”始终一致。

### 4. `ex_factors`、`dividends`、`shares`：长期价值很高的参考原料

如果你的目标是保留总回报、复权、市值和股本相关的长期底层原料，PIT 之后最值得补的是这三类：

```bash
csml rqdata mirror-hk-ex-factors \
  --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv \
  --start-date 20100101 \
  --end-date 20260318 \
  --name hk_connect_full_2010_20260318_ex_factors_latest \
  --resume

csml rqdata mirror-hk-dividends \
  --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv \
  --start-date 20100101 \
  --end-date 20260318 \
  --name hk_connect_full_2010_20260318_dividends_latest \
  --resume

csml rqdata mirror-hk-shares \
  --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv \
  --start-date 20100101 \
  --end-date 20260318 \
  --name hk_connect_full_2010_20260318_shares_latest \
 --resume
```

这些资产的定位：

* 它们不会被 pipeline 自动直读。
* 它们更像原料层，给后续复权、总回报、市值、流通股本等派生使用。
* `mirror-hk-shares` 默认会拉一组常用股本字段；需要额外列时再补 `--field` 或 `--fields-file`。

如果你的目标不是“以后自己从价格和股本近似重建”，而是要把 provider 的日频估值口径原样冻住，再单独补一份：

```bash
csml rqdata mirror-hk-valuation \
  --symbols-file artifacts/assets/rqdata/hk/daily/hk_all_daily_latest/symbols.txt \
  --start-date 20000101 \
  --end-date 20260326 \
  --name hk_all_2000_20260326_valuation_full_market_latest \
  --resume
```

这条线的定位要分清：

* 它保存的是 `rqdatac.get_factor` 的 provider 口径，不是你本地从 `close * shares` 反推的近似值。
* 默认字段就是 `hk_total_market_val`、`pe_ratio_ttm`、`pb_ratio_ttm`；需要更多估值列时再补 `--field`。
* 它不是 pipeline 默认读取入口；研究主线仍然优先走 `fundamentals.provider_overlay`。
* 它更适合“访问权限快结束，想把以后难以稳定还原的日频估值先冻住”这种场景。

按当前工作区的磁盘体量看：

* `daily` 全市场 snapshot 约 `318M`
* `pit_financials` 全市场宽表 snapshot 约 `1.5G`
* `pipeline_fundamentals.parquet` 全字段 flat file 约 `23M`
* `ex_factors` 约 `23M`
* `dividends` 约 `20M`
* `shares` 约 `31M`
* `valuation` 全市场日频估值镜像约 `196M`
* `industry_changes` 约 `57M`

所以真正的大头是 `daily` 和 `pit_financials`。  
`ex_factors/dividends/shares/industry_changes` 这组原料层并不重，`valuation` 也只是中等体量；长期保留通常是划算的。

### 5. `exchange_rate`：当前仍按 probe 和 staged backfill 处理

如果你准备把 `financial_details` 的原币值统一到单一货币，再补汇率层：

```bash
csml rqdata mirror-hk-exchange-rate \
  --start-date 20250210 \
  --end-date 20250211 \
  --name hk_exchange_rate_probe_20250210_20250211_minimal
```

这条线当前的结论要写得更明确一些：

* 默认字段只有 `currency_pair` 和 `middle_referrence_rate`。
* 如果你需要买卖参考价或结算汇率，再补 `--field` 或 `--fields-file`。
* 按当前工作区 manifest 看，短窗口 probe 已经能稳定完成，例如 `2025-02-10` 到 `2025-02-16`。
* 但 `2025` 全年和 `2000-01-01` 到 `2026-03-19` 这类长窗口尝试目前仍是 `failed / timed out`。

因此更合理的策略是：

1. 先做最小字段短窗口 probe
2. 再按阶段分批回填更长历史
3. 不要把“命令已经接入”误读成“全历史汇率已经稳定可一把拉完”

### 6. `financial_details`：仍然当增强层 probe 用

`financial_details` 当前更适合做窄字段、显式白名单的 probe，不建议直接升成全市场全字段宽表主线。

示例：

```bash
csml rqdata mirror-hk-financial-details \
  --start-quarter 2024q1 \
  --end-quarter 2025q4 \
  --date 20260319 \
  --field operating_revenue \
  --field net_profit \
  --symbol 00386.HK \
  --symbol 00939.HK \
  --symbol 01211.HK \
  --name hk_financial_details_probe_core_2024_2025_latest
```

建议：

* 优先显式传 `--symbol` 和 `--field`
* 不要把 `--field-profile full` 当成默认选择
* 它当前更像“验证原始细项结构、积累 subject 归并规则”的增强层，而不是研究主链路的基础资产

如果你已经拉了一版 probe，后续研究入口是：

```bash
uv run python -m csml.research.hk_financial_details \
  --probe-dir artifacts/assets/rqdata/hk/financial_details/hk_financial_details_probe_connect60_superset_2024_2025_20260319 \
  --compare-probe-dir artifacts/assets/rqdata/hk/financial_details/hk_financial_details_probe_connect30_core_2024_2025_20260319 \
  --dedup latest_adjusted_then_info_date \
  --mapping-file configs/local/hk_financial_details_subject_mapping.csv
```

这个模块不是正式 CLI，它的职责是把 raw long table 整理成研究分析包。默认会在 probe 同级目录下生成：

* `probe_coverage.csv`
* `subject_frequency.csv`
* `subject_mapping_draft.csv`
* `duplicate_disclosure_summary.csv`
* `normalized_long.parquet`
* `summary.md`

补充：

* 仓库默认映射表在 `configs/field_profiles/hk_financial_details_subject_mapping.csv`
* `--mapping-file` 是叠加覆盖层，适合把人工审核过的新规则放进 `configs/local/`
* 未知 `subject` 默认保持原样，不会被强行归一化

## 行业层与 southbound 怎么准备

### 1. `southbound` 是审计层，不是默认研究入口

如果你只关心研究股票池，`csml universe hk-connect` 通常已经够用。  
如果你还要追溯“某只股票何时具备南向资格”，再补 `southbound` raw mirror：

```bash
csml rqdata mirror-hk-southbound \
  --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv \
  --start-date 20141117 \
  --end-date 20260318 \
  --trading-type both \
  --rebalance-frequency D \
  --name hk_connect_southbound_latest \
  --resume
```

它的特点：

* 按 symbol 落盘
* 每行保留 `date`、`trading_type` 和 `eligible`
* 更适合资格审计、渠道差异回放和纳入日期核对

### 2. 行业层要分三层看

HK 行业资产更清楚的分法是：

| 层 | 主要命令 | 作用 | 是否建议长期保留 |
| --- | --- | --- | --- |
| `industry_changes` | `mirror-hk-industry-changes` | 行业切换真相层，按区间保留变更历史 | 是 |
| `instrument_industry` | `mirror-hk-instrument-industry` | 某些快照日期上的 provider 行业快照 | 按需 |
| `industry_labels_<freq>` | `build-hk-industry-labels` | 本地研究直接 join 的标签文件 | 是 |

如果你只保留一层，优先保留 `industry_changes`。  
如果你只是要在研究里 join 行业列，再从它派生 `industry_labels_<freq>`。

#### `industry_changes`

```bash
csml rqdata mirror-hk-industry-changes \
  --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv \
  --start-date 20100101 \
  --end-date 20260318 \
  --level 1 \
  --mapping-date 20260318 \
  --name hk_connect_industry_changes_latest \
  --resume
```

它会：

* 先通过 `get_industry_mapping` 枚举行业代码
* 再把每个 symbol 的行业区间写到 `data/<symbol>.parquet`
* 额外写 `industries.txt` 和 `industry_catalog.parquet`

#### `instrument_industry`

```bash
csml rqdata mirror-hk-instrument-industry \
  --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv \
  --start-date 20100101 \
  --end-date 20260318 \
  --level 0 \
  --rebalance-frequency M \
  --name hk_connect_instrument_industry_latest \
  --resume
```

它会：

* 按 `by_date_file` 或日期区间解析快照日期
* 把这些日期写到 `dates.txt`
* 更偏 provider 快照补充层，不等于切换日真相层

#### `build-hk-industry-labels`

如果你已经有 `industry_changes`，后续的日频、月频、季频行业标签都可以本地派生：

```bash
csml rqdata build-hk-industry-labels \
  --asset-dir artifacts/assets/rqdata/hk/industry_changes/hk_all_industry_changes_latest \
  --daily-asset-dir artifacts/assets/rqdata/hk/daily/hk_all_daily_latest \
  --frequency M

csml rqdata build-hk-industry-labels \
  --asset-dir artifacts/assets/rqdata/hk/industry_changes/hk_all_industry_changes_latest \
  --source-universe-by-date artifacts/assets/universe/hk_all_full_by_date.csv \
  --frequency M
```

这里最重要的规则是：

* 必须二选一：`--source-universe-by-date` 或 `--daily-asset-dir`
* 不能两者同时给，也不能两者都不给

这一步的逻辑：

* 读取 `industry_changes` 里的 `start_date` / `cancel_date`
* 在所选日期网格上按 `start_date <= trade_date < cancel_date` 命中行业标签
* `D` 保留全部日期，`M/Q` 保留每个 symbol 在该月或该季的最后一个交易日

注意：

* `M/Q` 是对本地日期网格做抽样，不是 provider 的“月度行业接口”。
* 如果你需要精确回放切换日，保留 `industry_changes` 本体。
* 如果你只是做行业中性、暴露控制或日常 merge，直接用 `industry_labels_<freq>` 更顺手。
* `industry_labels_<freq>` 是派生文件，不会随着 `hk_all_daily_latest` alias 自动重建；如果 daily snapshot 前进了，而你又需要对齐新日期，记得重新跑 `build-hk-industry-labels`。

接进研究配置的方式：

```yaml
industry:
  enabled: true
  source: file
  file: artifacts/assets/rqdata/hk/industry_changes/hk_all_industry_changes_latest/industry_labels_m.parquet
  keep_columns:
    - industry_name
    - first_industry_name
  ffill: false
  required: true

eval:
  bucket_ic:
    enabled: true
    schemes:
      - industry_name
```

说明：

* 这样会把行业列并到 panel，并保留到 `dataset.parquet`
* 如果启用 `eval.save_scored_artifact=true`，这些列也会进入 `eval_scored.parquet`
* 这条链路不会自动做行业中性化，它只负责把标签 join 进来

## 配额、恢复与试用期策略

### 1. 大范围下载前先做这几件事

1. 先看 `csml rqdata quota --pretty`
2. 固定绝对日期，不要在大镜像里混用 `today/t-1`
3. 固定 `--name`，大任务始终配 `--resume`
4. 先做小范围 probe，再决定是否扩大到全量
5. 引入更长历史窗口时，考虑新建 `data.cache_tag`

如果你同时维护 `frozen` 和 `rolling` 两套研究，也建议给两套数据使用不同的 `cache_tag`，避免缓存混用。

### 2. 试用期内先抓什么

如果你还在试用期，优先级建议是：

1. 只在你明确需要一份更晚 full-market 离线底座时，才重刷 `daily`
2. 如果只是继续研究，优先补更晚 as-of 的窄 PIT 增量
3. 接着补 `ex_factors`、`dividends`、`shares`
4. 如果你已经进入 `financial_details` 路线，再补最小字段的 `exchange_rate`
5. `southbound`、`announcement` 这类补充层排在更后面

原因：

* `daily` 和 `pit_financials` 是最占体量的大头
* `ex_factors/dividends/shares/industry_changes` 体积不大，但长期复用价值高
* `exchange_rate` 当前长窗仍不稳定，更适合 staged backfill
* `financial_details` 仍然是增强层，不是先手主线

### 3. 两种常见作业模式

#### 保守档：先服务当前研究，不重刷 full-market daily

适合“我现在就要继续研究，但不急着重建离线底座”的场景。

建议顺序：

1. 刷新港股通 PIT universe
2. 补一份最近几个 quarter 的窄 PIT 增量
3. 立刻构建对应的 `pipeline_fundamentals.parquet`
4. 如果担心企业行为和股本原料过旧，再补 `ex_factors/dividends/shares`

当前工作区里更贴近这一路线的增量命名是：

* `hk_all_probe_2025q4_2026q1_starter_20260324`
* `hk_connect_probe_2025q4_2026q1_starter_20260324`

`20260319` 那一批仍在本地，但当前更晚的 `20260324` starter 已经补出了 `pipeline_fundamentals.parquet` 和对应的 research universe，继续做增量 as-of 验证时应优先看这批。

这类增量更适合：

* 快速接入最新 as-of 数据
* 不大改现有 daily 底座
* 先满足研究推进，再考虑大规模重刷

#### 归档档：补一份完整离线底座

适合“我明确要保留一份新的 full-market baseline，并计划离线复用”的场景。

建议顺序：

1. quota 确认足够
2. 新建一版 full-market daily snapshot
3. 从该 snapshot 派生 `hk_all_full_by_date.csv`
4. 立刻用 `csml backup-data` 固化为本地快照

如果你只是想补最近几天的 freshness gap，而不是重新生成一整版日线目录，这一档通常不是最优选择。

## 备份、打包与跨机器共享

### 1. 本地私有备份优先用 `csml backup-data`

示例：

```bash
csml backup-data \
  --name hk_frozen_20260323 \
  --config configs/experiments/variants/hk_selected__xgb_regressor.yml
```

这个命令默认会把下面几类内容一起复制到 `artifacts/snapshots/<name>/`：

* `artifacts/cache/`
* `artifacts/assets/universe/`
* 你显式传入的配置文件

如果要额外把某些资产目录也带进去，再补 `--include-path`。  
生成的 `manifest.yml` 会记录拷贝条目和 git 元数据，便于之后追溯。

### 2. 跨机器共享：`package_assets` / `release_assets`

如果你的目标是把 HK 资产拆成可搬运的 part，入口是：

```bash
uv run python -m csml.release_tools.package_assets \
  --preset hk_full \
  --daily-snapshot hk_all_2000_20260326_daily_final_latest \
  --dest ~/csml_asset_parts/hk_full_20260327 \
  --mode copy \
  --overwrite
```

这条链路的特点：

* 默认会把资产拆成 `daily / instruments / pit / reference / exchange_rate / southbound / financial_details / industry / universe` 这些 part
* 新增了 `hk_etf` preset，默认只打 `daily + instruments` 两个 part，不再强依赖 universe / PIT / reference 那些 ETF 当前没有主线快照的层
* `announcement` 也支持单独打包，但默认不进包；只有显式传 `--part announcement --announcement-snapshot <snapshot-or-path>` 才会生成
* 每个 part 都有自己的 `manifest.yml`
* part 内部会生成 `latest` 软链接，方便下游配置直接引用
* 只想打核心层时，可以显式传 `--part daily --part instruments --part pit --part universe`
* 当前 preset 不会默认绑定 `announcement_snapshot`，因为仓库里现成的公告镜像还是 `hk_selected` 小范围补充层，不应自动混进 `hk_full` / `hk_connect` 主链分发
* 如果你不想带增强层，可以补 `--no-exchange-rate`、`--no-southbound`、`--no-financial-details`

单独打 `announcement` 的例子：

```bash
uv run python -m csml.release_tools.package_assets \
  --name hk_connect_refresh \
  --as-of 20260326 \
  --part announcement \
  --announcement-snapshot artifacts/assets/rqdata/hk/announcement/hk_selected_2000_20260324_announcement_latest \
  --dest artifacts/releases/assets/hk_connect_refresh_20260326_announcement_stage \
  --mode copy \
  --overwrite
```

ETF `daily` 资产的正式打包例子：

```bash
uv run python -m csml.release_tools.package_assets \
  --preset hk_etf \
  --dest ~/csml_asset_parts/hk_etf_20260401 \
  --mode copy \
  --overwrite
```

如果要直接打成 GitHub Release 的 tarball：

```bash
uv run python -m csml.release_tools.release_assets \
  --preset hk_etf \
  --tag hk_etf_assets_20260401 \
  --mode copy \
  --overwrite \
  --skip-upload
```

如果你要直接打成 GitHub Release 资产，再用：

```bash
uv run python -m csml.release_tools.release_assets \
  --tag hk_assets_20260327 \
  --preset hk_full \
  --daily-snapshot hk_all_2000_20260326_daily_final_latest \
  --mode copy \
  --overwrite \
  --skip-upload
```

为什么上面示例显式传了 `--daily-snapshot`：

* 因为 `package_assets` / `release_assets` 走的是静态 preset
* 它们不会自动跟随 `hk_all_daily_latest` 这类 alias
* 如果你要分发当前工作区真正正在使用的 snapshot，最好把关键快照名写死在命令里
* `exchange_rate` 尤其要显式确认，因为当前稳定可用的是短窗 probe，不是长窗 `latest`
* `announcement` 也建议显式传 `--announcement-snapshot`，不要假设 preset 会自动带上它

### 3. 历史 run 和数据资产是两条不同流程

不要把“资产打包”与“历史 run 归档”混成一条线。

* 数据资产：`python -m csml.release_tools.package_assets` / `python -m csml.release_tools.release_assets`
* 历史 run：`python -m csml.release_tools.package_runs` / `python -m csml.release_tools.release_runs`

归档历史 run 的常见入口：

```bash
uv run python -m csml.release_tools.release_runs \
  --name hk_selected_history \
  --runs-dir artifacts/runs \
  --run-name-prefix hk_selected \
  --profile light \
  --latest-n 20 \
  --skip-upload
```

一般建议：

* `--profile light` 作为默认归档档位
* 关键里程碑 run 用 `--profile milestone`
* 只有在你确实要整目录打包时再用 `--profile full`

### 4. 下游机器怎么引用这些 part

解压后常见的配置方式如下：

```yaml
data:
  rqdata:
    daily_asset_dir: "/path/to/extract/daily/rqdata/hk/daily/latest"
    instruments_file: "/path/to/extract/instruments/rqdata/hk/instruments/latest.parquet"
universe:
  by_date_file: "/path/to/extract/universe/universe/latest_by_date.csv"
fundamentals:
  source: file
  file: "/path/to/extract/pit/rqdata/hk/pit_financials/latest/pipeline_fundamentals.parquet"
```

如果你只想共享部分资产，优先用 `--part`。  
如果你只是想切换具体 snapshot，则显式覆写 `--daily-snapshot`、`--instruments-file`、`--pit-snapshot` 等参数。

公开仓库或公开 Release 还要额外注意：

* 不要默认公开原始 provider 数据
* 优先只公开 `manifest.yml`、配置、说明文件和汇总结果
* 先确认你的分发方式是否触及 provider 合规边界

## 常见误解

### 误解 1：PIT 股票池会把历史财报自动裁成成员期

不会。股票池控制的是研究日期过滤；财务镜像控制的是本地保留多少财报历史。

### 误解 2：季度 PIT 路线就不再依赖日线

不会。季度路线仍然需要底层 daily 行情；变化的是 rebalance、标签和评估频率。

### 误解 3：只要有 full mirror，模型就会自动吃到所有字段

不会。真正进入 pipeline 的字段仍由配置里的 `fundamentals.features` 和 `features.list` 决定。

### 误解 4：`industry_changes` 和 `instrument_industry` 可以互相替代

不能。`industry_changes` 是区间真相层；`instrument_industry` 是若干快照日期上的 provider 快照。

### 误解 5：alias 路径和 `package_assets` preset 会自动同步

不会。alias 是研究入口习惯用的稳定路径；打包 preset 是脚本里的静态默认值。打包前必须核对或显式覆写。
