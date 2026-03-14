# HK 数据下载与整备

本页解决什么：解释 HK 研究中各类数据资产的准备顺序与落地位置。
本页不解决什么：不展开研究路线选择与参数定义。
适合谁：准备做 HK PIT 或本地资产归档的人。
读完你会得到什么：一条可执行的数据准备顺序与资产关系说明。
相关页面：`docs/playbooks/hk-selected.md`、`docs/playbooks/research-template-design.md`、`docs/cli.md`、`docs/config.md`、`docs/outputs.md`

任务摘要：先有股票池与 instrument，再落地日线与 PIT 资产，最后构建平面 fundamentals 与备份。

本页说明 HK 研究里几类数据各自落到哪里、推荐按什么顺序准备，以及 PIT 股票池、日线缓存、财务资产之间是什么关系。

本页默认场景：

* `provider=rqdata`
* 市场是 `hk`
* 股票池使用港股通 PIT universe

如果你还没选好研究路线，先看 [hk-selected.md](./hk-selected.md)。
如果你在判断该不该新建模板，继续看 [research-template-design.md](./research-template-design.md)。

## 1. 先分清几层数据

| 数据层 | 主要命令 | 默认输出位置 | 作用 |
| --- | --- | --- | --- |
| 港股通 PIT 股票池 | `csml universe hk-connect` | `artifacts/assets/universe/` | 决定某只股票在哪些日期属于研究股票池 |
| HK 全市场 by-date 股票池 | `csml universe hk-daily-assets` | `artifacts/assets/universe/` | 用本地日线镜像派生更长历史的 HK 全市场研究股票池 |
| instrument 快照 | `csml rqdata export-hk-instruments` | `artifacts/assets/rqdata/hk/instruments/` | 保留 `listed_date`、`de_listed_date`、`round_lot` 等元数据 |
| 日线缓存 | pipeline 首次拉取时自动写入 | `artifacts/cache/hk_rqdata_daily_<ts_code>.parquet` | 保留按 symbol 分开的日频行情缓存 |
| PIT 财务镜像 | `csml rqdata mirror-hk-pit-financials` | `artifacts/assets/rqdata/hk/pit_financials/<snapshot>/` | 保留按 symbol 分开的原始 PIT 财务资产 |
| 平面 fundamentals 文件 | `csml rqdata build-hk-pit-fundamentals` | `<pit_snapshot>/pipeline_fundamentals.parquet` | 给 pipeline 直接读取的财务文件 |
| 本地快照备份 | `csml backup-data` | `artifacts/snapshots/<name>/` | 把缓存、股票池和配置一起归档 |

## 2. 推荐准备顺序

建议按下面的顺序做：

1. 先生成港股通 PIT 股票池文件。
2. 再导出一份 HK instrument 快照。
3. 如果你要跑研究或做持仓回溯，再让 pipeline 把日线缓存落到 `artifacts/cache/`。
4. 如果你要做 PIT 财报研究，再镜像 `pit_financials`。
5. 用 `build-hk-pit-fundamentals` 生成研究用平面文件。
6. 数据准备完成后，用 `csml backup-data` 做一份本地快照。

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
* 目录里会写 `manifest.yml`、`audit.csv`、`fields.txt`、`symbols.txt` 和 `data/<ts_code>.parquet`
* 当前实现按 symbol 单独请求，更适合 quota 中断后续跑
* RQData 当前会把早于 `2000-01-04` 的 HK 日线请求自动裁到 `2000-01-04`

如果你只是要给 pipeline 日常研究提速，日线缓存仍然按下面的方式落地：

1. pipeline 按 symbol 调 `fetch_daily`
2. 命中 `data.cache_mode=symbol`
3. 自动把结果写到 `artifacts/cache/hk_rqdata_daily_<ts_code>.parquet`

这个缓存逻辑已经比较成熟，特点是：

* 默认一个 symbol 一个缓存文件
* 已有缓存时，会按 `data.cache_refresh_days` 只刷新尾部区间
* 适合长期维护一套稳定的 HK 日线缓存

如果你已经有本地日线镜像，而且想完全离线跑 pipeline，可以再多配两项：

* `data.rqdata.daily_asset_dir`：指向 daily snapshot 目录
* `data.rqdata.instruments_file`：指向 HK instrument 快照文件

这样 `provider=rqdata` 也可以直接吃本地资产，不需要运行时再初始化 provider。

如果你的目标是“把 2000 年以来的 HK 全市场研究口径补齐”，常见顺序是：

1. 先跑 `mirror-hk-daily`
2. 再跑 `csml universe hk-daily-assets`
3. 再把 `universe.by_date_file` 切到 `artifacts/assets/universe/hk_all_full_by_date.csv`
4. 配上 `data.rqdata.daily_asset_dir` 和 `data.rqdata.instruments_file`

如果你的目标是“把港股通 symbol archive 的日线缓存尽量补齐”，当前做法是：

1. 先准备好更宽的港股通 `by_date_file`
2. 优先跑 `mirror-hk-daily` 做独立归档
3. 需要 pipeline query cache 时，再用一份覆盖这组 symbol 的配置跑 pipeline
4. 固定 `data.start_date/end_date`
5. 保持 `data.cache_mode=symbol`

首次运行会最慢。后续同口径重跑时，主要是命中缓存和刷新尾部。

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
* PIT 财务镜像目录会写 `manifest.yml`、`audit.csv`、`fields.txt`、`symbols.txt` 和 `data/<ts_code>.parquet`。
* 如果 hit quota，中断后可以继续 `--resume`。
* 当前这套 HK PIT 财务镜像实测最早返回到 `2000q4`，不是连续从 `2000q1` 开始。

## 6. 平面 fundamentals 文件怎么生成

镜像目录准备好后，再执行：

```bash
csml rqdata build-hk-pit-fundamentals \
  --asset-dir artifacts/assets/rqdata/hk/pit_financials/hk_connect_full_2000_2025_full_latest \
  --out artifacts/assets/rqdata/hk/pit_financials/hk_connect_full_2000_2025_full_latest/pipeline_fundamentals.parquet
```

这一步会做几件事：

* 按 `info_date` 生成 `trade_date`
* 去掉 `trade_date + ts_code` 重复行
* 输出给 pipeline 直接读取的平面 fundamentals 文件

如果你同时传：

* `--source-universe-by-date`
* `--universe-by-date-out`

还可以顺手派生一份“只保留确实有 PIT 财报的 symbol”的研究股票池文件。

## 7. 配额和恢复建议

日常运维时，先做这几件事：

1. 先看 `csml rqdata quota --pretty`
2. 大范围财务镜像固定 `--name` 并配 `--resume`
3. 新增更长历史窗口时，考虑配新的 `data.cache_tag`
4. 先做小范围探针，再启动全量下载

对不同数据层，建议不同：

* 日线缓存：通常走 symbol cache，后续增量刷新成本较低
* PIT 财务镜像：优先小 `batch-size`，让 quota 中断后更容易续跑

## 8. 备份怎么做

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

## 9. 常见误解

### 误解 1：PIT 股票池会把历史财报自动裁成成员期

不会。股票池控制的是研究日期过滤，财务镜像控制的是本地保留的财报历史。

### 误解 2：季度 PIT 路线就不再依赖日线

不会。季度路线仍然读取日线行情，只是标签、评估和回测频率改成 `Q`。

### 误解 3：有 full mirror 就会自动把全部字段喂给模型

不会。真正进入 pipeline 的字段仍然由配置里的 `fundamentals.features` 和 `features.list` 决定。
