# 数据源行为差异与限制

本页解决什么：当前项目的数据边界、RQData 行为、离线资产入口与相关限制。  
本页不解决什么：不展开完整研究流程与所有配置键。  
适合谁：需要确认 provider 行为、日期 token、symbol 规则和本地资产模式的人。  
读完你会得到什么：项目当前支持边界、RQData 使用方式、常见限制与缓存注意事项。  
相关页面：`docs/config.md`、`docs/cli.md`、`docs/concepts/data-sources.md`、`docs/playbooks/hk-data-assets.md`

## 当前边界

本项目当前正式验证最充分的 provider / market 组合是：

* `data.provider=rqdata`
* 默认 `data.source_mode=platform_assets`，只读 `market-data-platform` 发布的本地资产
* `market=hk`
* 在线 `rqdatac` 访问
* 本地 HK 资产直读（daily + instruments）

以上是当前稳定支持面的完整边界。主流程正在向 market-agnostic 的配置边界收敛，但旧的多市场 / 多 provider 归档配置不再作为活跃入口维护。
`configs/presets/a_share.yml` 仅作为兼容和实验入口保留，不属于当前正式主线。

## 鉴权与初始化

需要的环境变量：

```bash
export RQDATA_USERNAME=your_username
export RQDATA_PASSWORD=your_password
```

也可以通过 `data.rqdata.init.username/password` 显式传入。优先级是：

1. `data.rqdata.init`
2. 环境变量 `RQDATA_USERNAME` / `RQDATA_PASSWORD`
3. 用户名别名 `RQDATA_USER`

如果配置了本地 HK 资产，pipeline 默认会跳过在线日线/基础信息初始化，直接读本地文件。
研究侧临时在线读取需要显式设置 `data.source_mode=provider_online_legacy`。如果你同时启用了 `fundamentals.source=provider` 或 `fundamentals.provider_overlay`，运行时在遇到 fundamentals cache miss 时仍会按同一套 `data.rqdata.init` / 环境变量口径补做 `rqdatac.init`。

## 日期 token

* `today` / `t-1` 永远按自然日解析。
* `last_trading_day` / `last_completed_trading_day` 只有在 `rqdatac` 交易日历可用时才按交易日严格解析。
* 本地资产模式或 `rqdatac` 不可用时，会退回自然日并给 warning。

需要强复现时，优先写死绝对日期，如 `20260131`。

## 基本面 provider 模式

`fundamentals.source=provider` 现在只支持 HK + RQData，并固定走 `endpoint=get_factor`。

常见配置：

```yaml
fundamentals:
  enabled: true
  source: provider
  endpoint: get_factor
  fields:
    - hk_total_market_val
    - pe_ratio_ttm
    - pb_ratio_ttm
  column_map:
    trade_date: trade_date
    symbol: symbol
    market_cap: hk_total_market_val
    pe_ttm: pe_ratio_ttm
    pb: pb_ratio_ttm
```

如果未显式指定 `fields`，默认请求：

* `hk_total_market_val`
* `pe_ratio_ttm`
* `pb_ratio_ttm`

如果 provider 原始返回列还是 `ts_code`，配置里应写 `column_map.symbol: ts_code`；主研究链路的标准列名统一为 `symbol`。

## `fundamentals.provider_overlay`

这条链路仍然保留，而且是当前 HK 季频研究主线上真正活跃的能力。

适用场景：

* 主基本面来自 `fundamentals.source=file`
* 文件是稀疏 PIT 财务平面
* 需要把日频估值字段按 `trade_date + symbol` 叠加回 daily panel

当前约束：

* 只支持 `source=provider`
* 只支持 `provider=rqdata`
* 不做额外 `ffill`
* join 主键固定为 `trade_date + symbol`

## Symbol 与市场规则

当前项目内部统一使用 HK symbol：

* Canonical 格式：`00001.HK`
* RQData 调接口时会转换成：`00001.XHKG`

仓库内部的标准列名是 `symbol`。旧输入里的 `ts_code` / `stock_ticker` / `order_book_id` 仍然只作为历史资产读取兼容；新的配置、产物和研究代码应继续以 `symbol` 为主。`order_book_id` 可以保留在 RQData 边界层或 provider 元数据里，不应作为主研究链路列名。
新增读取路径如果需要接受旧别名，应把兼容逻辑限制在输入边界，并继续输出标准 `symbol`。

## 本地 HK 资产直读

如果你已经准备好本地镜像，可以让 pipeline 完全跳过在线日线/基础信息读取：

```yaml
data:
  provider: rqdata
  rqdata:
    daily_asset_dir: artifacts/assets/rqdata/hk/daily/hk_all_daily_clean_latest
    instruments_file: artifacts/assets/rqdata/hk/instruments/hk_all_instruments_latest.parquet
    ex_factors_dir: artifacts/assets/rqdata/hk/ex_factors/hk_all_ex_factors_latest
```

说明：

* 研究默认建议优先指向 `hk_all_daily_clean_latest`；保留 `hk_all_daily_latest` 主要是为了原始资产巡检、patch merge 和 clean-layer 重建。
* `daily_asset_dir` 与 `instruments_file` 同时存在时，`rqdatac.init` 会被跳过
* 这条“跳过”只针对本地 daily / instruments 读取；如果后续还要在线拉 fundamentals / provider overlay，cache miss 时仍会 lazy init `rqdatac`
* 如果提供 `ex_factors_dir`，pipeline 可以自动派生 `tr_close`
* `backtest.benchmark_symbol` 只额外拉价格，不再参与 fundamentals / industry / load_basic 这类非价格加载
* `backtest.benchmark_returns_file` 走本地收益序列对齐，不会触发额外 provider 拉数

详细流程见 `docs/playbooks/hk-data-assets.md`。

## 缓存与结果变化

关键配置：

```yaml
data:
  cache_mode: symbol
  cache_refresh_days: 10
  cache_refresh_on_hit: false
  cache_tag: null
```

需要注意：

1. `symbol` 模式会按单票缓存，并按 `cache_refresh_days` 刷新尾部区间。
2. 相对日期、缓存刷新、provider 回补都会导致同配置重跑结果变化。
3. 并行维护 `frozen` 与 `rolling` 研究时，优先用不同的 `cache_tag` 隔离缓存。
4. provider 基本面默认落到 `data.cache_dir/fundamentals/hk/`，与日线缓存分开。
