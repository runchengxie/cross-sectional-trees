# HK 数据下载与整备

本页解决什么：解释 HK 研究中各类数据资产的准备顺序与落地位置。
本页不解决什么：不展开研究路线选择与参数定义。
适合谁：准备做 HK PIT 或本地资产归档的人。
读完你会得到什么：一条可执行的数据准备顺序与资产关系说明。
相关页面：`docs/playbooks/hk-selected.md`、`docs/playbooks/hk-rqdata-status.md`、`docs/rqdata/README.md`、`docs/playbooks/research-template-design.md`、`docs/cli.md`、`docs/config.md`、`docs/outputs.md`

任务摘要：先有股票池与 instrument，再落地日线与 PIT 资产，最后构建平面 fundamentals 与备份。

本页说明 HK 研究里几类数据各自落到哪里、推荐按什么顺序准备，以及 PIT 股票池、日线缓存、财务资产之间是什么关系。

如果你想先看这组 HK / RQData 资料的专题入口和分工，再回到本页，先看 `docs/rqdata/README.md`。

本页默认场景：

* `provider=rqdata`
* 市场是 `hk`
* 股票池使用港股通 PIT universe

如果你还没选好研究路线，先看 [hk-selected.md](./hk-selected.md)。
如果你想先确认“哪些 HK RQData 接口已经接了、哪些本地已经有资产、哪些今天还能下”，继续看 [hk-rqdata-status.md](./hk-rqdata-status.md)。
如果你在判断该不该新建模板，继续看 [research-template-design.md](./research-template-design.md)。

## 1. 先分清几层数据

| 数据层 | 主要命令 | 默认输出位置 | 作用 |
| --- | --- | --- | --- |
| 港股通 PIT 股票池 | `csml universe hk-connect` | `artifacts/assets/universe/` | 决定某只股票在哪些日期属于研究股票池 |
| HK 全市场 by-date 股票池 | `csml universe hk-daily-assets` | `artifacts/assets/universe/` | 用本地日线镜像派生更长历史的 HK 全市场研究股票池 |
| instrument 快照 | `csml rqdata export-hk-instruments` | `artifacts/assets/rqdata/hk/instruments/` | 保留 `listed_date`、`de_listed_date`、`round_lot` 等元数据 |
| 日线缓存 | pipeline 首次拉取时自动写入 | `artifacts/cache/hk_rqdata_daily_<symbol>.parquet` | 保留按 symbol 分开的日频行情缓存 |
| PIT 财务镜像 | `csml rqdata mirror-hk-pit-financials` | `artifacts/assets/rqdata/hk/pit_financials/<snapshot>/` | 保留按 symbol 分开的原始 PIT 财务资产 |
| 参考数据镜像 | `csml rqdata mirror-hk-ex-factors` / `mirror-hk-dividends` / `mirror-hk-shares` / `mirror-hk-exchange-rate` | `artifacts/assets/rqdata/hk/ex_factors/` 等 | 保留复权、分红、股本和汇率原料，给后续派生研究使用 |
| 港股通原始历史镜像 | `csml rqdata mirror-hk-southbound` | `artifacts/assets/rqdata/hk/southbound/<snapshot>/` | 保留按 symbol 分开的 southbound 渠道历史，给 universe 审计和资金口径回放使用 |
| 行业资产镜像 | `csml rqdata mirror-hk-instrument-industry` / `mirror-hk-industry-changes` | `artifacts/assets/rqdata/hk/instrument_industry/` 等 | 保留行业快照和行业变更区间，给行业中性和暴露回放使用 |
| 平面 fundamentals 文件 | `csml rqdata build-hk-pit-fundamentals` | `<pit_snapshot>/pipeline_fundamentals.parquet` | 给 pipeline 直接读取的财务文件 |
| 本地行业标签文件 | `csml rqdata build-hk-industry-labels` | `<industry_changes_snapshot>/industry_labels_<freq>.parquet` | 用行业变更区间本地派生可直接 join 的日/月/季标签文件 |
| 本地快照备份 | `csml backup-data` | `artifacts/snapshots/<name>/` | 把缓存、股票池和配置一起归档 |

## 2. 推荐准备顺序

建议按下面的顺序做：

0. 先确认本地有没有已经可复用的 snapshot；大资产优先打包或备份，不要急着重下。
1. 先生成港股通 PIT 股票池文件。
2. 再导出一份 HK instrument 快照。
3. 如果你要跑研究或做持仓回溯，再让 pipeline 把日线缓存落到 `artifacts/cache/`。
4. 如果你要做 PIT 财报研究，再镜像 `pit_financials`。
5. 如果你要保留复权、分红和股本原料，再镜像 `ex_factors`、`dividends` 和 `shares`。
6. 如果你准备把 `financial_details` 的原币值统一到单一货币，再补 `exchange_rate`。
7. 如果你要保留港股通原始渠道历史，再镜像 `southbound`。
8. 如果你要做行业中性、行业暴露或行业归属回放，再镜像 `instrument_industry` 和 `industry_changes`。
9. 用 `build-hk-pit-fundamentals` 生成研究用平面文件。
10. 如果你要直接 join 行业标签，再用 `build-hk-industry-labels` 从 `industry_changes` 派生本地标签文件。
11. 数据准备完成后，用 `csml backup-data` 做一份本地快照。

补充：

* 默认 HK 月频研究配置现在读取 `artifacts/assets/universe/hk_connect_full_research_by_date.csv`
* `hk_selected` / 季频 PIT 模板现在读取 `artifacts/assets/universe/hk_selected_pit_research_by_date.csv`
* 这两份 `research universe` 都建议用 `build-hk-pit-fundamentals` 和本地 flat file 一起派生，不要再手工维护

## 3. 股票池与下载历史的关系和处理

这里要单独记住：

1. `universe.by_date_file` 控制的是某只股票在哪些日期进入研究样本。
2. 日线缓存和财务镜像控制的是本地保留了这只股票多少历史数据。

对港股通 PIT universe 来说：

* 股票池文件只决定成员日期。
* 某只股票一旦被纳入 symbol 集合，下载逻辑通常会按你请求的整个历史区间拉数。
* 下载逻辑不会把数据裁成“只保留在港股通期间”。

这意味着：

* 某只股票后来才加入港股通，它更早的日线和财务历史仍然可以保留在本地。
* 某只股票后来被移出港股通，它被移出后的研究日期会被股票池过滤掉。
* 股票池决定的是“能不能参与某天的研究”，不是“能不能保留更早历史”。

## 4. 日线缓存怎么落地

现在有两条路：

1. 用 `csml rqdata mirror-hk-daily` 生成独立资产目录
2. 让 pipeline 首次运行时自动把 query cache 写到 `artifacts/cache/`

如果你要做可备份、可复用、可 `--resume` 的大范围归档，优先用第一条。

独立资产命令示例：

```bash
csml rqdata mirror-hk-daily \
  --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv \
  --start-date 20000101 \
  --end-date 20260311 \
  --name hk_connect_full_2000_20260311_daily_latest \
  --resume
```

这条命令的特点：

* 默认字段集是 `open/high/low/close/volume/total_turnover`
* 输出到 `artifacts/assets/rqdata/hk/daily/<snapshot>/`
* 目录里会写 `manifest.yml`、`audit.csv`、`fields.txt`、`symbols.txt` 和 `data/<symbol>.parquet`
* 当前实现按 symbol 单独请求，更适合 quota 中断后续跑
* RQData 当前会把早于 `2000-01-04` 的 HK 日线请求自动裁到 `2000-01-04`

如果你只是要给 pipeline 日常研究提速，日线缓存仍然按下面的方式落地：

1. pipeline 按 symbol 调 `fetch_daily`
2. 命中 `data.cache_mode=symbol`
3. 自动把结果写到 `artifacts/cache/hk_rqdata_daily_<symbol>.parquet`

这个缓存逻辑已经比较成熟，特点是：

* 默认一个 symbol 一个缓存文件
* 已有缓存时，会按 `data.cache_refresh_days` 只刷新尾部区间
* 适合长期维护一套稳定的 HK 日线缓存

如果你已经有本地日线镜像，而且想完全离线跑 pipeline，可以再多配两项：

* `data.rqdata.daily_asset_dir`：指向 daily snapshot 目录
* `data.rqdata.instruments_file`：指向 HK instrument 快照文件

这样 `provider=rqdata` 也可以直接吃本地资产，不需要运行时再初始化 provider。

补充：

* `csml universe hk-daily-assets` 默认会优先发现最新的 `hk_all_*_daily_final_latest`，找不到时再回退旧命名 `hk_all_*_daily_full_latest`。
* 如果你的磁盘上同时保留了多版日线镜像，最好显式传 `--daily-asset-dir`，不要把“默认发现哪一版”交给猜测。

如果你的目标是“把 2000 年以来的 HK 全市场研究口径补齐”，常见顺序是：

1. 先跑 `mirror-hk-daily`
2. 再跑 `csml universe hk-daily-assets`
3. 再把 `universe.by_date_file` 切到 `artifacts/assets/universe/hk_all_full_by_date.csv`
4. 配上 `data.rqdata.daily_asset_dir` 和 `data.rqdata.instruments_file`

如果你的目标是把港股通 symbol archive 的日线缓存尽量补齐，当前做法是：

1. 先准备好更宽的港股通 `by_date_file`
2. 优先跑 `mirror-hk-daily` 做独立归档
3. 需要 pipeline query cache 时，再用一份覆盖这组 symbol 的配置跑 pipeline
4. 固定 `data.start_date/end_date`
5. 保持 `data.cache_mode=symbol`

首次运行会最慢。后续同口径重跑时，主要是命中缓存和刷新尾部。

### 为什么不需要为了复权重跑一套日线

更推荐的分层是：

* 保留一套 `未复权` 日线
* 单独保留 `ex_factors`
* 单独保留 `dividends`
* 需要市值、自由流通或港股流通口径时，再补 `shares`

原因：

* 未复权日线是更稳定的原料层，不会把企业行为直接揉进价格序列。
* `ex_factors` 和 `dividends` 保留后，前复权、总回报、股息相关派生都可以在本地重建。
* `shares` 是市值和流通口径的上游原料，长期价值通常高于直接囤一批派生因子。

这也意味着：

* 如果你的目标只是以后可复权、可查错、可切换口径，不需要单独再镜像一套前复权日线。
* 只有当你明确要生成一份更新到更晚日期的完整 `daily snapshot` 时，才值得新建一版日线资产目录。
* 当前 `mirror-hk-daily` 的 `--resume` 主要用于跳过已存在 symbol，不会在旧 parquet 上追加新的交易日；因此“补最新几天”更适合走 pipeline symbol cache，“重做完整离线归档”才适合新建 snapshot。

## 5. PIT 财务资产怎么落地

PIT 财务资产有独立命令，推荐流程比日线更清晰：

1. 先准备 symbol 集合，通常来自 `--by-date-file`
2. 固定 quarter 区间
3. 固定 `--date`
4. 固定 `--name`
5. 大范围下载时始终带 `--resume`

常用命令：

```bash
csml rqdata mirror-hk-pit-financials \
  --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv \
  --field-profile full \
  --name hk_connect_full_2000_2025_full_latest \
  --start-quarter 2000q1 \
  --end-quarter 2025q4 \
  --date 20260310 \
  --batch-size 5 \
  --resume
```

补充：

* `--by-date-file` 先解析 symbol 集合，再按 symbol 全区间拉财务历史。
* PIT 财务镜像目录会写 `manifest.yml`、`audit.csv`、`fields.txt`、`symbols.txt` 和 `data/<symbol>.parquet`。
* 如果 hit quota，中断后可以继续 `--resume`。
* 当前这套 HK PIT 财务镜像实测最早返回到 `2000q4`，不是连续从 `2000q1` 开始。

如果你的目标是把总回报、市值或股息相关原料也一并冻住，推荐在 PIT 之后顺手补三类轻量资产：

```bash
csml rqdata mirror-hk-ex-factors \
  --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv \
  --start-date 20100101 \
  --end-date 20260317 \
  --name hk_connect_ex_factors_latest \
  --resume

csml rqdata mirror-hk-dividends \
  --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv \
  --start-date 20100101 \
  --end-date 20260317 \
  --name hk_connect_dividends_latest \
  --resume

csml rqdata mirror-hk-shares \
  --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv \
  --start-date 20100101 \
  --end-date 20260317 \
  --name hk_connect_shares_latest \
  --resume
```

补充：

* 这三类参考数据主要用于离线归档和后续派生，不会被 pipeline 自动直读。
* `mirror-hk-shares` 默认会拉一组常用股本字段；如需额外列，再补 `--field` / `--fields-file`。
* 这三类命令会优先复用 `artifacts/assets/rqdata/hk/instruments/` 下最近的 HK instruments 快照来解析 `unique_id`，所以先准备 instrument 快照更稳。
* 如果你在试用期内赶时间，优先级仍然低于 instrument、日线和 PIT core。

如果你要把 `financial_details` 的原币值统一到单一货币，可以再补一份轻量汇率镜像：

```bash
csml rqdata mirror-hk-exchange-rate \
  --start-date 20250210 \
  --end-date 20250211 \
  --name hk_exchange_rate_probe_20250210_20250211_minimal
```

补充：

* `mirror-hk-exchange-rate` 默认只保留 `currency_pair` 和 `middle_referrence_rate`；如需结算汇率或买卖参考价，再补 `--field` / `--fields-file`。
* 当前这个接口长时间窗明显慢于 `shares/dividends`，更适合先做 probe，再按阶段补长历史。
* 如果你的目标只是给 `financial_details` 做币种归一，这组默认最小字段通常已经够用。

如果你想把港股通原始历史单独冻住，而不是只保留派生后的 `universe by-date` 文件，可以再补一份 `southbound`：

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

补充：

* `southbound` 资产按 symbol 落盘，每行保留 `date`、`trading_type` 和 `eligible=1`。
* 这层更适合做 universe 审计、渠道差异回放和“某只股票何时可被南向买入”的原始核对。
* 如果你当前只关心研究股票池，现有 `csml universe hk-connect` 已经够用；`southbound` raw mirror 属于高价值但非必需的补充层。

`mirror-hk-financial-details` 目前建议只当 probe 用：

```bash
csml rqdata mirror-hk-financial-details \
  --start-quarter 2024q1 \
  --end-quarter 2025q4 \
  --date 20260318 \
  --field operating_revenue \
  --field net_profit \
  --symbol 00386.HK \
  --symbol 00939.HK \
  --symbol 01211.HK \
  --name hk_financial_details_probe_core_2024_2025_latest
```

补充：

* 目前更稳的做法是显式传 `--symbol` 和 `--field`，不要直接上 `--field-profile full`。
* 这个接口当前更适合验证原始细项结构，不适合在试用额度里直接做全市场宽表镜像。
* 如果你已经拉了一版 probe，想继续看 `subject` 频次、重复披露和保守标准化长表，可以直接跑研究侧脚本：

```bash
uv run python scripts/analyze_hk_financial_details.py \
  --probe-dir artifacts/assets/rqdata/hk/financial_details/hk_financial_details_probe_connect60_superset_2024_2025_20260319 \
  --compare-probe-dir artifacts/assets/rqdata/hk/financial_details/hk_financial_details_probe_connect30_core_2024_2025_20260319 \
  --dedup latest_adjusted_then_info_date \
  --mapping-file configs/local/hk_financial_details_subject_mapping.csv
```

补充：

* 这个脚本不是正式 CLI，只负责把 `financial_details` 的原始长表整理成研究用分析包。
* 默认会在 probe 同级目录下写 `analysis_<snapshot>/`，产出 `probe_coverage.csv`、`subject_frequency.csv`、`subject_mapping_draft.csv`、`duplicate_disclosure_summary.csv`、`normalized_long.parquet` 和 `summary.md`。
* repo 默认映射表在 `src/csml/research/hk_financial_details_subject_mapping.csv`；`--mapping-file` 是叠加覆盖层，适合把人工确认过的新规则放进 `configs/local/` 或研究目录里。
* 默认映射只会合并已经验证过的少量版式变体；未知 `subject` 默认保留原样，不会强行标准化。

如果你已经确定后面要做行业中性或行业暴露控制，推荐再补两类行业资产：

```bash
csml rqdata mirror-hk-instrument-industry \
  --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv \
  --start-date 20100101 \
  --end-date 20260318 \
  --level 0 \
  --rebalance-frequency M \
  --name hk_connect_instrument_industry_latest \
  --resume

csml rqdata mirror-hk-industry-changes \
  --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv \
  --start-date 20100101 \
  --end-date 20260318 \
  --level 1 \
  --mapping-date 20260318 \
  --name hk_connect_industry_changes_latest \
  --resume
```

补充：

* `mirror-hk-instrument-industry` 会按 `by_date_file` 或日期区间解析快照日期，并把这些日期写到 `dates.txt`。
* `mirror-hk-industry-changes` 会先用 `get_industry_mapping` 枚举行业代码，再把每个 symbol 的行业区间写到 `data/<symbol>.parquet`。
* 这两类资产当前也不会被 pipeline 自动直读，更适合离线研究、行业中性和归因检查。
* 如果你更关心“切换日真相层”，优先保留 `industry_changes`；`instrument_industry` 的月频、季频更像便捷快照层。

## 6. 平面 fundamentals 文件怎么生成

镜像目录准备好后，再执行：

```bash
csml rqdata build-hk-pit-fundamentals \
  --asset-dir artifacts/assets/rqdata/hk/pit_financials/hk_connect_full_2000_2025_full_latest \
  --out artifacts/assets/rqdata/hk/pit_financials/hk_connect_full_2000_2025_full_latest/pipeline_fundamentals.parquet
```

这一步会做几件事：

* 按 `info_date` 生成 `trade_date`
* 去掉 `trade_date + symbol` 重复行（旧资产中的 `ts_code` 会自动兼容）
* 输出给 pipeline 直接读取的平面 fundamentals 文件

如果你同时传：

* `--source-universe-by-date`
* `--universe-by-date-out`

还可以顺手派生一份“只保留确实有 PIT 财报的 symbol”的研究股票池文件。

## 7. 本地行业标签文件怎么生成

如果你已经有 `industry_changes` 资产，后续的日频、月频、季频行业标签都可以本地派生，不需要再向 provider 重复请求快照：

```bash
csml rqdata build-hk-industry-labels \
  --asset-dir artifacts/assets/rqdata/hk/industry_changes/hk_all_industry_changes_latest \
  --daily-asset-dir artifacts/assets/rqdata/hk/daily/hk_all_daily_latest \
  --frequency M
```

如果你要严格对齐研究 universe，而不是“最宽全市场档案”，再改用 `source_universe_by_date`：

```bash
csml rqdata build-hk-industry-labels \
  --asset-dir artifacts/assets/rqdata/hk/industry_changes/hk_all_industry_changes_latest \
  --source-universe-by-date artifacts/assets/universe/hk_all_full_by_date.csv \
  --frequency M
```

如果你要日频标签，用本地日线镜像提供真实交易日网格：

```bash
csml rqdata build-hk-industry-labels \
  --asset-dir artifacts/assets/rqdata/hk/industry_changes/hk_all_industry_changes_latest \
  --daily-asset-dir artifacts/assets/rqdata/hk/daily/hk_all_daily_latest \
  --frequency D
```

这一步会做几件事：

* 读取 `industry_changes` 里的 `start_date` / `cancel_date` 区间。
* 选一个本地日期网格来源：`source_universe_by_date` 或 `daily_asset_dir`。
* 按 `start_date <= trade_date < cancel_date` 给每个 `trade_date + symbol` 命中行业标签。
* 写出 `industry_labels_<freq>.parquet` 和配套 manifest。

使用建议：

* 你如果要精确回放切换日，`industry_changes` 仍然是主资产，不要只保留快照文件。
* 你如果只是做行业中性、暴露控制或日常 merge，优先直接用 `industry_labels_<freq>`。
* 如果你的目标是“严格全市场档案”，`M/Q` 也优先从 `daily` 资产取网格；`hk_all_full_by_date.csv` 会回到研究 universe 口径。
* `M/Q` 只是对本地日期网格抽样，不是 provider 原生“月度接口”。

如果你要直接把这份文件接进研究配置，可以加：

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

* 这样会把行业列直接并到 panel，并保留到 `dataset.parquet`；若启用 `eval.save_scored_artifact=true`，也会写到 `eval_scored.parquet`。
* 这一步只是提供 join 输入；自动行业中性化、行业约束或行业 dummy 仍然要在后续研究逻辑里显式处理。
* 如果你的研究单元是月度或季度，尽量用同频文件；只有明确要传播最近一次标签时，才考虑 `ffill=true`。

## 8. 配额和恢复建议

日常运维时，先做这几件事：

1. 先看 `csml rqdata quota --pretty`
2. 大范围财务镜像固定 `--name` 并配 `--resume`
3. 新增更长历史窗口时，考虑配新的 `data.cache_tag`
4. 先做小范围探针，再启动全量下载

对不同数据层，建议不同：

* 日线缓存：通常走 symbol cache，后续增量刷新成本较低
* PIT 财务镜像：优先小 `batch-size`，让 quota 中断后更容易续跑

### 试用期内推荐的最小动作

如果你还在试用期，先记住一个原则：

* 最值得保留的是会被横截面研究反复扫的原料层。
* 不太值得优先保留的是派生接口、便捷接口，或者只有特定事件策略才会用的数据。

按当前仓库实盘情况看，本地资产体量的大头已经是：

* `daily`：约 `319M`
* `pit_financials`：约 `1.5G`

而 `ex_factors`、`dividends`、`shares`、行业几类加起来只是一百多兆量级，所以把这些参考原料保留下来并不过度工程化；真正容易过度工程化的，是把低价值接口也升级成一级命令和长期维护对象。

### 两档最小命令

#### 保守档：不重刷 full-market daily，只补当前研究最需要的增量

适合你想继续研究、但不急着重建一整套离线底座的场景。

1. 先刷新港股通 PIT universe：

```bash
csml universe hk-connect --config configs/presets/universe/hk_connect.yml -- --mode daily
```

2. 再做一份更晚 as-of date 的窄 PIT 增量，只补当前研究 universe：

```bash
csml rqdata mirror-hk-pit-financials \
  --by-date-file artifacts/assets/universe/hk_connect_full_by_date.csv \
  --fields-file configs/field_profiles/hk_financial_fields_starter.txt \
  --start-quarter 2025q4 \
  --end-quarter 2026q1 \
  --date 20260318 \
  --batch-size 5 \
  --name hk_connect_probe_2025q4_2026q1_starter_20260318 \
  --resume
```

3. 需要把这份窄 PIT 直接接入研究时，再生成平面 fundamentals：

```bash
csml rqdata build-hk-pit-fundamentals \
  --asset-dir artifacts/assets/rqdata/hk/pit_financials/hk_connect_probe_2025q4_2026q1_starter_20260318 \
  --out artifacts/assets/rqdata/hk/pit_financials/hk_connect_probe_2025q4_2026q1_starter_20260318/pipeline_fundamentals.parquet
```

4. 如果你担心企业行为和股本原料还不够新，再轻量补三类参考资产：

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

说明：

* 这一档默认不重刷 `hk_all_*_daily_*`。
* 最新几天的价格缺口更适合让 pipeline 的 symbol cache 在研究时按需补齐。
* 重点是把“高价值、低体量”的财务增量和企业行为原料尽量冻住。

#### 归档档：补一份更新到更晚日期的完整离线底座

适合你明确要保留一份新的 full-market daily snapshot，准备之后离线复用。

1. 先确认 quota，再新建一版 full-market daily snapshot：

```bash
csml rqdata quota --pretty

csml rqdata mirror-hk-daily \
  --symbols-file artifacts/assets/rqdata/hk/daily/hk_all_daily_latest/symbols.txt \
  --start-date 20000104 \
  --end-date 20260317 \
  --name hk_all_2000_20260317_daily_final_latest
```

2. 再从这份本地日线镜像派生新的全市场 universe：

```bash
csml universe hk-daily-assets \
  -- \
  --daily-asset-dir artifacts/assets/rqdata/hk/daily/hk_all_2000_20260317_daily_final_latest \
  --start-date 20000104 \
  --end-date 20260317
```

3. 下载完成后，做一份本地快照，避免试用期过后目录散落：

```bash
csml backup-data \
  --name hk_runtime_20260318_refresh \
  --include-path artifacts/assets/rqdata/hk/daily/hk_all_2000_20260317_daily_final_latest \
  --include-path artifacts/assets/rqdata/hk/pit_financials/hk_all_2000_2025_full_market_latest \
  --include-path artifacts/assets/rqdata/hk/ex_factors/hk_all_ex_factors_latest \
  --include-path artifacts/assets/rqdata/hk/dividends/hk_all_dividends_latest \
  --include-path artifacts/assets/rqdata/hk/shares/hk_all_shares_latest \
  --include-path artifacts/assets/rqdata/hk/industry_changes/hk_all_industry_changes_latest
```

说明：

* 这一档的目标是“生成一份新的完整离线底座”，不是为了复权额外保存一套价格口径。
* `mirror-hk-daily` 当前不会在旧 parquet 上 append 新交易日，所以这里直接新建 snapshot 更清楚。
* 如果 quota 紧张，优先保守档；只有你明确需要一份新的 full-market 离线日线目录时，再走归档档。

### 剩余试用期的优先级

按“还剩几天试用 + 每天带宽/额度有限”的场景，建议顺序是：

1. 第一优先是补 `daily` 的 freshness gap，但只在你明确需要新 full-market snapshot 时执行。
2. 第二优先是做一份更晚 as-of date 的窄 `PIT` 增量，不要重跑全市场全字段；先盯 `2025q4` 到 `2026q1`。
3. 第三优先是保留 `ex_factors`、`dividends`、`shares` 的最新快照；这几类便宜但长期很值。
4. 如果你已经开始用 `financial_details`，第四优先是补一份最小字段的 `exchange_rate`。
5. 如果还想用试用额度换“以后可能会后悔没下”的东西，再考虑 `southbound` 原始历史和 `announcement`。

原因：

* `southbound` 更接近 universe 审计和资金口径原料。
* `exchange_rate` 对 `financial_details` 的跨币种归一很直接，但当前更适合小窗 probe 或 staged backfill，不适合盲目单次拉全历史。
* `announcement` 更偏事件驱动，不是当前这条 HK 横截面研究主线的必需层。
* `get_factor`、`get_turnover_rate`、`get_all_factor_names` 这类接口暂时不值得升级成主线缓存对象。

## 9. 备份怎么做

本地私有备份优先用：

```bash
csml backup-data \
  --name hk_frozen_20260312 \
  --config configs/experiments/variants/hk_selected__xgb_regressor.yml
```

这个命令默认会把下面几类内容一起复制：

* `artifacts/cache/`
* `artifacts/assets/universe/`
* 你显式传入的配置文件

如果你要做 GitHub Release：

* 私有仓库可以考虑上传完整快照
* 公开仓库更适合上传 `manifest.yml`、配置、说明文件和汇总 CSV
* 原始 provider 缓存和原始数据是否适合公开，要先看你的使用边界和合规要求

如果你想自动打包并上传到 GitHub Release（私有仓库场景），可以用：

```bash
python3 scripts/release_assets.py \
  --tag hk_assets_20260312 \
  --preset hk_full \
  --mode copy \
  --overwrite
```

这个脚本会调用 `package_assets.py` 生成 bundle、写 `README.md`、打包成 tar.gz，
并用 `gh release create/upload` 上传到 GitHub Release。只想打包不上传时加 `--skip-upload`。

## 10. 跨机器打包与共享资产

如果你需要把离线资产带到另一台机器或共享给他人，建议用仓库内置的打包脚本，把常用资产聚合成一个可搬运的 bundle。

脚本入口：`scripts/package_assets.py`

推荐用法（全市场口径，打包成独立目录）：

```bash
python3 scripts/package_assets.py \
  --preset hk_full \
  --dest /home/richard/code/csml_assets/hk_full_20260312 \
  --mode copy \
  --overwrite
```

说明：

* `--preset hk_full`：全市场口径，默认包含日线、instrument、PIT、`ex_factors`、`dividends`、`shares`、`industry_changes` 与 universe 资产。
* `--mode copy`：生成独立可搬运目录；本机调试时也可以用 `--mode symlink`。
* bundle 内会写 `manifest.yml`，并为关键入口生成 `latest` 软链接，方便配置引用。

如果你只想保留旧的“瘦 bundle”，可以显式关掉 reference / industry：

```bash
python3 scripts/package_assets.py \
  --preset hk_full \
  --no-reference \
  --no-industry \
  --dest /home/richard/code/csml_assets/hk_full_core_20260312 \
  --mode copy \
  --overwrite
```

补充：

* `hk_full` 现在默认会生成 `rqdata/hk/ex_factors/latest`、`rqdata/hk/dividends/latest`、`rqdata/hk/shares/latest` 和 `rqdata/hk/industry_changes/latest`。
* `hk_connect` 预设仍然默认保留核心资产；如果你也想把 reference snapshot 打进去，可以继续手动传 `--ex-factors-snapshot`、`--dividends-snapshot`、`--shares-snapshot`。

在其他项目里使用有两种常见方式：

* 直接把 bundle 目录复制到目标项目的 `artifacts/assets/`。
* 不复制，直接在配置里指向 bundle 的 `latest` 路径。

示例（直接指向 bundle）：

```yaml
data:
  rqdata:
    daily_asset_dir: "/path/to/bundle/rqdata/hk/daily/latest"
    instruments_file: "/path/to/bundle/rqdata/hk/instruments/latest.parquet"
universe:
  by_date_file: "/path/to/bundle/universe/latest_by_date.csv"
fundamentals:
  source: file
  file: "/path/to/bundle/rqdata/hk/pit_financials/latest/pipeline_fundamentals.parquet"
```

如果你只想共享部分资产，可以用 `--no-pit` 或用 `--daily-snapshot`、`--instruments-file` 等参数覆盖默认快照。

## 10. 常见误解

### 误解 1：PIT 股票池会把历史财报自动裁成成员期

不会。股票池控制的是研究日期过滤，财务镜像控制的是本地保留的财报历史。

### 误解 2：季度 PIT 路线就不再依赖日线

不会。季度路线仍然读取日线行情，只是标签、评估和回测频率改成 `Q`。

### 误解 3：有 full mirror 就会自动把全部字段喂给模型

不会。真正进入 pipeline 的字段仍然由配置里的 `fundamentals.features` 和 `features.list` 决定。
