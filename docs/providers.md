# 数据源行为差异与限制

本页解决什么：provider 行为差异、限制与缓存策略。
本页不解决什么：不展开完整研究流程与配置键定义。
适合谁：需要选择或切换 provider 的读者。
读完你会得到什么：provider 差异对照与注意事项。
相关页面：`docs/config.md`、`docs/cli.md`、`docs/concepts/data-sources.md`

本项目支持 `tushare`、`rqdata`、`eodhd`。同一份配置在不同 provider 下，结果可能不同（字段覆盖、交易日历、历史回补、停牌口径都不同）。

## 快速对照

| 项 | TuShare | RQData | EODHD |
| --- | --- | --- | --- |
| `data.provider` | `tushare` | `rqdata` | `eodhd` |
| 必需鉴权 | `TUSHARE_TOKEN` | `RQDATA_USERNAME` + `RQDATA_PASSWORD` | `EODHD_API_TOKEN` |
| 额外附加变量 | `TUSHARE_TOKEN_2` | `RQDATA_USER`（用户名别名） | `EODHD_API_KEY` |
| 日线接口 | TuShare endpoint（可配） | `rqdatac.get_price` | EODHD HTTP API |
| 基础信息（name/list_date） | TuShare basic endpoint | `rqdatac.instruments/all_instruments` | `exchange-symbol-list` |
| `last_trading_day` 严格交易日 | 否（回退自然日） | 是（可用交易日历时） | 否（回退自然日） |
| 基本面 `fundamentals.source=provider` | 支持 | HK 支持（pipeline 当前走 `get_factor`） | 不支持 |

说明：`last_trading_day / last_completed_trading_day` 只有在 `provider=rqdata` 且交易日历可用时才严格按交易日解析，否则会给 warning 并回退自然日。

补充：`rqdata` 的基本面 provider 模式当前只覆盖 `market=hk`。pipeline 默认走 `rqdatac.get_factor`。其他市场仍建议使用 `fundamentals.source=file`。

补充：当前主文档和默认模板按港股优先组织。`cn/us` provider 入口继续保留，但更适合兼容已有配置或做对照实验。

补充：如果你要下载更完整的港股财报资产，使用 `csml rqdata mirror-hk-pit-financials` 或 `csml rqdata mirror-hk-financial-details`。这两条命令会把数据写到 `artifacts/assets/rqdata/`，不走 pipeline 的 provider 基本面缓存。

补充：如果你也想把 HK 日线落成独立资产目录，使用 `csml rqdata mirror-hk-daily`。这条命令同样写到 `artifacts/assets/rqdata/`，和 `artifacts/cache/` 里的 query cache 是两套东西。

补充：如果你已经准备好了 HK 日线 snapshot 和 instrument 快照，现在也可以在 pipeline 配 `data.rqdata.daily_asset_dir` + `data.rqdata.instruments_file`，直接离线读取本地资产，不再初始化 `rqdatac`。

补充：如果你依赖 `round_lot`、`listed_date`、`de_listed_date` 这类 instrument 元数据，使用 `csml rqdata export-hk-instruments` 先做一份本地快照。`alloc` 这类下游命令会直接用到 `round_lot`。

补充：财报镜像目录除了 `manifest.yml`，现在还会写 `audit.csv`。做大范围下载时，优先固定 `--name` 并配合 `--resume` 使用，这样网络抖动重试、已有文件跳过和 quota 中断都能保留进度。

补充：如果你已经有 `pit_financials` 资产目录，可以继续执行 `csml rqdata build-hk-pit-fundamentals`。这条命令会生成一个平面 fundamentals 文件，默认把 `trade_date` 写成 `info_date`，可直接接到 `fundamentals.source=file`。如果你同时传 `--source-universe-by-date` 和 `--universe-by-date-out`，还可以顺手派生一份只保留“确实有 PIT 财报”的研究 universe。

补充：旧的 HK PIT 资产里如果出现过字段名尾随空格，`build-hk-pit-fundamentals` 现在会在构建时自动规范化；不需要手工重写原始 parquet。

补充：字段名可以先用 `csml rqdata list-hk-financial-fields` 导出，再整理成 `--fields-file`。如果你只是想快速准备一份更完整的财务归档，也可以直接用 `--field-profile full`。

补充：`RQData market=hk` 的行情覆盖范围大于仓库里的默认 `hk-connect` 研究股票池。仓库当前提供的是港股通 PIT universe 模板；如果你想研究更广的港股普通股池，需要单独准备 `universe.by_date_file` 或新的 universe builder。

补充：如果你的目标是“港股通历史股票池 + 更完整的 PIT 财务归档”，优先用 `configs/presets/universe/hk_connect_full.yml` 生成 `artifacts/assets/universe/hk_connect_full_by_date.csv`，再执行财报镜像命令。这个模板把 `top_quantile` 设成 `0`，表示保留全部港股通候选。

补充：如果你想把 HK 的股票池、日线缓存、PIT 财务镜像、平面 fundamentals 和本地备份放到同一套流程里看，直接读 `docs/playbooks/hk-data-assets.md`。

补充：港股 ETF、杠杆/反向产品或其他非普通股产品，常见情况是能取到日线，但拿不到 `market_cap / pe_ttm / pb` 这类 provider 基本面字段。pipeline 会跳过这些 symbol，并给 warning。

补充：`csml holdings/snapshot/alloc --as-of last_trading_day` 在能识别到 `provider=rqdata` + `market` 上下文时同样按交易日解析；缺少上下文时回退自然日（会输出 warning）。

## Symbol 规则（重点是 HK）

内部统一格式：

* HK：`00001.HK`（5 位补零 + `.HK`）
* CN/US：按输入与 provider 映射规则处理

provider 侧转换：

1. RQData（HK）：内部 `00001.HK` 会转换为 `00001.XHKG` 调接口。
1. EODHD（HK）：`data.eodhd.hk_symbol_mode` 支持 `strip_one`（常见默认：`00001.HK -> 0001.HK`）、`strip_all`、`pad4`、`pad5`。

## 缓存与同配置结果变化

关键配置：

* `data.cache_mode` / `data.daily_cache_mode`：`symbol` 或 `range/window`
* `data.cache_refresh_days`
* `data.cache_refresh_on_hit`
* `data.cache_tag`（或 `cache_version`）
* `fundamentals.cache_dir`

行为差异：

1. `symbol` 模式（默认）：单票一个缓存文件，会按 `cache_refresh_days` 增量刷新末端区间。
1. `range/window` 模式：按请求时间窗口缓存，不做末端刷新合并。
1. 不同 `cache_tag` 会形成独立命名空间，适合隔离实验版本。
1. provider 基本面默认落到 `data.cache_dir/fundamentals/<market>/`，避免和日线缓存混在一起。

结果变化常见来源：

1. provider 回补历史数据。
1. 命中缓存后触发末端刷新（`cache_refresh_days > 0`）。
1. 使用相对日期（`today/t-1`）导致样本窗口每日漂移。
1. 改动了 universe 或长历史窗口后，最好配一个新的 `cache_tag`，避免把旧研究缓存和新研究混用。
1. 同时维护 `frozen` 和 `rolling` 两套研究时，建议给两套数据使用不同的 `cache_tag`。

## 速率限制与重试

可用 `data.retry` 控制失败重试：

```yaml
data:
  retry:
    max_attempts: 3
    backoff_seconds: 0.5
    max_backoff_seconds: 5.0
    rotate_tokens: true
```

说明：

1. `rotate_tokens` 仅对 TuShare 有效（在 `TUSHARE_TOKEN` 与 `TUSHARE_TOKEN_2` 间轮换）。
1. 高频批量请求前建议先做小窗口验证，确认权限和配额。

## 复现建议

1. 固定 `data.start_date/end_date` 为绝对日期。
1. 固定 `data.provider` 与 provider 专属参数。
1. 保留 `artifacts/cache/`、`config.used.yml`、`summary.json`。
1. 使用 `data.cache_tag` 隔离关键实验版本。
1. 10-15 年、几百只股票、日频 + 少量基本面通常还不需要数据库；先把 Parquet 缓存和 PIT universe 管好。
