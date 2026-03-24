# 数据缓存元数据

此目录包含由数据流水线生成的运行时缓存。

## 目录结构

- `hk_rqdata_daily_<symbol>.parquet`
  当配置 `data.cache_mode=symbol` 时，按 市场/数据源/标的代码（market/provider/symbol）作为键值生成的日线价格缓存。
- `hk_rqdata_basic*.parquet`
  缓存的基础信息/标的（basic/instrument）数据表。
- `fundamentals/hk/hk_rqdata_fundamentals_<symbol>_<start>_<end>_<digest>.parquet`
  缓存的数据源基本面数据或估值叠加（valuation overlay）结果。哈希摘要（digest）取决于请求的接口（endpoint）、字段（fields）、参数（params）以及列映射关系（column mapping）。
- 其他数据源或不同的 `cache_tag` 值可能会在同级目录下生成带有不同前缀的文件。

## 日线缓存表结构 

日线缓存文件存储了由 `fetch_daily` 返回的标准化数据框（DataFrame）。常见的港股（HK）列包括：

| 字段 | 类型 | 描述 |
|-------|------|-------------|
| `trade_date` | 字符串 (`YYYYMMDD`) | 交易日期 |
| `ts_code` | 字符串 | 标准标的代码 |
| `symbol` | 字符串 | 标准化代码别名 |
| `stock_ticker` | 字符串 | 适配数据源的代码别名 |
| `close` | 浮点数 | 请求时获取的收盘价 |
| `vol` | 浮点数 | 标准化为 `vol` 字段的成交量 |
| `amount` | 浮点数 | 标准化为 `amount` 字段的成交额 |

根据配置的不同，文件可能仅包含所请求的日线字段（例如 `close/vol/amount`），或者包含更完整的量价数据集合（OHLCV：开盘、最高、最低、收盘、成交量）。

## 注意事项

- 这是运行时缓存，可以随时删除并重新生成。
- 本地日线数据资产与运行时缓存并不互斥；读取本地数据依然可以生成缓存并写入 `artifacts/cache/` 目录。
- 数据的覆盖范围、日期区间以及文件数量取决于近期的工作负载（workloads），因此本 README 刻意不将这些信息与特定版本绑定（version-pinned）。
- 常用的检查命令：

```bash
find artifacts/cache -maxdepth 1 -name 'hk_rqdata_daily_*.parquet' | wc -l
find artifacts/cache/fundamentals/hk -name '*.parquet' | wc -l
ls artifacts/cache | sed -n '1,40p'
```