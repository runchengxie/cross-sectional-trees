# 数据源指南

本页解决什么：说明当前仓库为什么只保留 HK + RQData，以及什么时候走在线接口、什么时候走本地资产。\
本页不解决什么：不展开完整配置键定义。\
适合谁：准备开始跑项目，或想确认“现在到底支持什么”的读者。\
读完你会得到什么：当前 provider 边界、最短配置和本地资产模式的使用方式。\
相关页面：`docs/config.md`、`docs/providers.md`、`docs/cli.md`

## 当前结论

当下项目以 `market-data-platform` 发布的 RQData 本地资产作为默认研究输入；在线 RQData 只保留为显式 opt-in 的研究侧 legacy 路线。

* `provider=rqdata`
* `market=hk`
* 默认 `data.source_mode=platform_assets`
* 需要在线读取时显式设置 `data.source_mode=provider_online_legacy`

## 最短配置

```yaml
market: hk

data:
  provider: rqdata
  source_mode: platform_assets
  start_date: "20200101"
  end_date: "20241231"
  rqdata:
    daily_asset_dir: artifacts/assets/rqdata/hk/daily/hk_all_daily_clean_latest
    instruments_file: artifacts/assets/rqdata/hk/instruments/hk_all_instruments_latest.parquet
```

平台资产根目录：

```bash
export DATA_PLATFORM_ROOT=/path/to/market-data-platform/artifacts
```

## 什么时候直接走在线 RQData

适合：

* 研究侧临时 probe
* 需要对照服务商即时返回
* 本地资产尚未覆盖某个探索字段

要求：

* 显式设置 `data.source_mode=provider_online_legacy`
* 安装 `--extra rqdata`
* 配置 RQData 凭证

## 什么时候切到本地资产模式

适合：

* 想冻结一版研究输入
* 试用资格有限，希望离线继续复现
* 准备做更大范围的 HK 资产研究

示例：

```yaml
data:
  provider: rqdata
  source_mode: platform_assets
  rqdata:
    daily_asset_dir: artifacts/assets/rqdata/hk/daily/hk_all_daily_clean_latest
    instruments_file: artifacts/assets/rqdata/hk/instruments/hk_all_instruments_latest.parquet
```

这时 pipeline 会直接读本地 daily / instruments 文件，并跳过在线日线 / 基础信息初始化。
但如果你显式启用了 `fundamentals.source=provider` 或 `fundamentals.provider_overlay`，在 fundamentals cache miss 时仍可能 lazy init `rqdatac`。

## 进一步阅读

* 想看 provider 细节：`docs/providers.md`
* 想看本地 HK 资产消费边界：`docs/playbooks/hk-data-assets.md`
* 想维护或冻结 HK 数据资产：使用 `market-data-platform`
* 想看配置键：`docs/config.md`
