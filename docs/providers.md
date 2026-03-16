# 数据源行为差异与限制

- 本页解决什么：provider 行为差异、限制与缓存策略。
- 本页不解决什么：不展开完整研究流程与配置键定义。
- 适合谁：需要选择或切换 provider 的读者。
- 读完你会得到什么：provider 差异对照、关键注意事项与离线入口。
- 相关页面：`docs/config.md`、`docs/cli.md`、`docs/concepts/data-sources.md`、`docs/playbooks/hk-data-assets.md`

本项目支持 `tushare`、`rqdata`、`eodhd`。同一份配置在不同 provider 下，结果可能不同（字段覆盖、交易日历、历史回补、停牌口径都不同）。

## 快速对照

| 项 | TuShare | RQData | EODHD |
| --- | --- | --- | --- |
| `data.provider` | `tushare` | `rqdata` | `eodhd` |
| 必需鉴权 | `TUSHARE_TOKEN` | `RQDATA_USERNAME` + `RQDATA_PASSWORD` | `EODHD_API_TOKEN` |
| 可选别名 | `TUSHARE_TOKEN_2` | `RQDATA_USER`（用户名别名） | `EODHD_API_KEY` |
| 日线接口 | TuShare endpoint（可配） | `rqdatac.get_price` | EODHD HTTP API |
| 基础信息（name/list_date） | TuShare basic endpoint | `rqdatac.instruments` / `all_instruments` | `exchange-symbol-list` |
| `last_trading_day` | 回退自然日 | 依赖 rqdatac 交易日历 | 回退自然日 |
| `fundamentals.source=provider` | 支持（需 endpoint） | 仅 `market=hk` 且 `endpoint=get_factor` | 不支持 |
| 本地资产直读 | 不支持 | 支持（daily + instruments） | 不支持 |

说明：

1. `last_trading_day / last_completed_trading_day` 只有在 `provider=rqdata` 且 `rqdatac` 交易日历可用时按交易日解析；本地资产模式或未安装 `rqdatac` 时会回退自然日并给 warning。
1. `today/t-1` 永远走自然日。

## 鉴权与初始化

- TuShare：仅支持环境变量 `TUSHARE_TOKEN`（可选 `TUSHARE_TOKEN_2` 用于轮换）；`data.retry.rotate_tokens=true` 时会在失败时切换 token。
- RQData：需要安装 `rqdatac`（HK 资产相关命令还需要 `rqdatac-hk`）。优先用 `data.rqdata.init` 传入 `username/password`，或用环境变量 `RQDATA_USERNAME`/`RQDATA_PASSWORD`（`RQDATA_USER` 为用户名别名）。配置了本地资产时会跳过 `rqdatac.init`。
- EODHD：token 可放在 `data.eodhd.api_token` 或环境变量 `EODHD_API_TOKEN`/`EODHD_API_KEY`；基础信息接口对非 HK 市场要求设置 `data.eodhd.exchange`，且可选 `data.eodhd.base_url`、`data.eodhd.timeout`。

## 交易日历与日期 token

- `today/t-1` 永远按自然日解析。
- `last_trading_day` 与 `last_completed_trading_day` 只有在 `provider=rqdata` 且 `rqdatac` 可用时严格走交易日；否则回退自然日并给 warning。
- pipeline 的 `data.end_date`、`live.as_of`，以及 `csml holdings/snapshot/alloc --as-of` 都遵循同一规则。

## 基本面 provider 模式

- `fundamentals.source=provider` 时默认跟随 `data.provider`，也可用 `fundamentals.provider` 覆盖。
- TuShare：需要配置 `fundamentals.endpoint`（或 `data.fundamentals_endpoint`），支持 cn/hk/us。
- RQData：仅 `market=hk` 且 `endpoint=get_factor`；若未显式指定 `fundamentals.fields`，默认请求 `hk_total_market_val`、`pe_ratio_ttm`、`pb_ratio_ttm`。如需标准列名可通过 `fundamentals.column_map` 映射为 `market_cap`/`pe_ttm`/`pb`。
- EODHD：不支持 provider 基本面，请改用 `fundamentals.source=file`。

## Symbol 与市场规则

内部统一格式：`00001.HK`（5 位补零 + `.HK`）。

RQData：内部 `00001.HK` 会转换为 `00001.XHKG` 调接口；非 HK 市场直接使用原值。

EODHD：HK symbol 最终为 `<code>.HK`，`data.eodhd.hk_symbol_mode` 支持 `strip_one`/`strip_all`/`pad4`/`pad5`，默认不裁剪；非 HK 若 symbol 未带交易所后缀，可用 `data.eodhd.exchange` 自动拼接。

## HK 资产与离线入口

- 日线与 instruments 离线：用 `csml rqdata mirror-hk-daily` + `csml rqdata export-hk-instruments` 生成资产，并在配置里设置 `data.rqdata.daily_asset_dir` 与 `data.rqdata.instruments_file`（daily 目录需要包含 `data/` 子目录）。两者齐全时 pipeline 会直接读本地资产并跳过 `rqdatac.init`。
- 财务镜像与平面 fundamentals：用 `csml rqdata mirror-hk-pit-financials` / `mirror-hk-financial-details`，再用 `build-hk-pit-fundamentals` 生成供 pipeline 读取的平面文件。
- 镜像资产默认写到 `artifacts/assets/rqdata/`，与 `artifacts/cache/` 的查询缓存是两套目录。
- 默认研究口径是港股通 PIT universe；若需要更广覆盖，优先用 `configs/presets/universe/hk_all_assets.yml` 或 `csml universe hk-daily-assets` 先生成更宽的 universe，再做镜像。
- 详细流程见 `docs/playbooks/hk-data-assets.md`，命令清单见 `docs/cli.md`，输出路径见 `docs/outputs.md`。

## 缓存与同配置结果变化

### 关键配置

- `data.cache_mode` / `data.daily_cache_mode`：`symbol` 或 `range/window`
- `data.cache_refresh_days`
- `data.cache_refresh_on_hit`
- `data.cache_tag` / `data.cache_version`
- `fundamentals.cache_dir`
- `fundamentals.cache_tag` / `fundamentals.cache_version`

### 行为差异

1. `symbol` 模式（默认）：单票一个缓存文件，会按 `cache_refresh_days` 增量刷新末端区间。
1. `range/window` 模式：按请求时间窗口缓存，不做末端刷新合并。
1. 启用 `cache_refresh_on_hit` 时，即使命中缓存也会按 `cache_refresh_days` 刷新末端区间。
1. 不同 `cache_tag` 会形成独立命名空间，适合隔离实验版本。
1. provider 基本面默认落到 `data.cache_dir/fundamentals/<market>/`，避免和日线缓存混在一起。

### 结果变化常见来源

1. provider 回补历史数据。
1. 命中缓存后触发末端刷新（`cache_refresh_days > 0`）。
1. 使用相对日期（`today/t-1`）导致样本窗口每日漂移。
1. 改动了 universe 或长历史窗口后，最好配一个新的 `cache_tag`，避免把旧研究缓存和新研究混用。
1. 同时维护 `frozen` 和 `rolling` 两套研究时，建议给两套数据使用不同的 `cache_tag`。
1. 港股 ETF、杠杆/反向产品等可能缺失 `market_cap / pe_ttm / pb`，pipeline 会跳过并给 warning。

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

1. `max_attempts` 默认 1（不重试），需要显式加大。
1. `rotate_tokens` 仅对 TuShare 有效（需要 `TUSHARE_TOKEN_2` 才会轮换）。
1. 高频批量请求前建议先做小窗口验证，确认权限和配额。

## 复现建议

1. 固定 `data.start_date/end_date` 为绝对日期。
1. 固定 `data.provider` 与 provider 专属参数（如 `data.rqdata.init` / `data.eodhd.exchange`）。
1. 保留 `artifacts/cache/`、`config.used.yml`、`summary.json`。
1. 使用 `data.cache_tag` 隔离关键实验版本。
1. 10-15 年、几百只股票、日频 + 少量基本面通常还不需要数据库；先把 Parquet 缓存和 PIT universe 管好。
