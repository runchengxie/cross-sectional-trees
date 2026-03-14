# 数据源指南

本页解决什么：选择数据 provider 的决策与权衡。
本页不解决什么：不展开配置键的权威定义。
适合谁：需要在 provider 之间做选择的人。
读完你会得到什么：provider 选择建议与使用边界。
相关页面：`docs/config.md`、`docs/providers.md`、`docs/cli.md`

这个文档帮你选择和配置数据 provider。

## 支持的 provider

| Provider | 支持的市场 | 特点 |
|----------|-----------|------|
| `tushare` | A 股 | 免费额度有限，适合 A 股研究 |
| `rqdata` | 港股、A 股、美股 | 收费，覆盖全，历史数据好 |
| `eodhd` | 港股、A 股、美股 | 收费，API 稳定 |

---

## 快速决策

| 你的情况 | 推荐 provider |
|---------|-------------|
| 做港股研究 | `rqdata` |
| 做 A 股研究 | `tushare` 或 `rqdata` |
| 做美股研究 | `rqdata` 或 `eodhd` |
| 想先跑通看看 | `rqdata`（需要账号）或 `tushare`（免费额度） |

---

## 配置示例

### TuShare（A股）

```yaml
data:
  provider: tushare
  start_date: "20200101"
  end_date: "20241231"
```

环境变量：

```bash
export TUSHARE_TOKEN=your_token_here
```

### RQData（港股）

```yaml
data:
  provider: rqdata
  market: hk
  start_date: "20200101"
  end_date: "20241231"
```

环境变量：

```bash
export RQDATA_USERNAME=your_username
export RQDATA_PASSWORD=your_password
```

### EODHD

```yaml
data:
  provider: eodhd
  market: hk
  start_date: "20200101"
  end_date: "20241231"
```

环境变量：

```bash
export EODHD_API_TOKEN=your_token_here
```

---

## provider 差异

| 差异点 | TuShare | RQData | EODHD |
|--------|---------|--------|-------|
| 港股通支持 | 有限 | 完整 | 完整 |
| PIT 财报 | 不支持 | 支持 | 不支持 |
| 历史数据质量 | 一般 | 好 | 好 |
| 交易日历 | 不严格 | 严格 | 严格 |
| 免费额度 | 有 | 无 | 有 |

详见 `docs/providers.md`。

---

## 本地资产模式

如果你已经有本地数据，可以不走 provider，直接读本地文件：

```yaml
data:
  provider: rqdata
  rqdata:
    daily_asset_dir: artifacts/assets/rqdata/hk/daily/hk_connect_full_2000_20260311_daily_latest
    instruments_file: artifacts/assets/rqdata/hk/instruments/hk_instruments_latest.parquet
```

这样即使没有网络，也能跑研究。

详见 `docs/config.md` 的「本地 HK 资产直读」部分。

---

## 相关文档

- 配置参数：`docs/config.md`
- provider 差异详情：`docs/providers.md`
- CLI 命令：`docs/cli.md`
