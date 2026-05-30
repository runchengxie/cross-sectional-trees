# HK 数据资产边界

本页解决什么：说明 HK 数据资产维护已经从 `cross-sectional-trees` sunset，以及研究侧现在如何消费数据。\
本页不解决什么：不再提供下载、检查、修复、打包或 release runbook。\
适合谁：需要跑 HK selected、PIT flat file 或本地资产直读的人。\
相关页面：`docs/playbooks/hk-selected.md`、`docs/concepts/data-sources.md`、`docs/config.md`、`docs/outputs.md`、`docs/providers.md`

## 当前状态

HK daily、PIT、valuation、industry、intraday、current contract、health、asset audit 和 release 已由 `market-data-platform` 统一承载。本仓库不再提供 `cstree rqdata ...`、HK asset workflow 旧入口 或数据资产 release 模块。

`cross-sectional-trees` 的定位是研究消费者：

* 默认读取外部数据平台生成的本地 daily asset、instrument file、PIT flat file 或 standardized layer。
* 在显式 `data.source_mode=provider_online_legacy` 的研究配置中读取 provider 在线数据。
* 消费平台或研究配置指定的股票池文件，构建特征、模型、回测和 live/export 产物。

## 研究侧配置

本地资产直读仍使用现有配置键：

* `data.rqdata.daily_asset_dir`
* `data.rqdata.instruments_file`
* `data.source_mode=platform_assets`
* `fundamentals.source=file`
* `fundamentals.file`
* `research_universe.by_date_file`

当 `fundamentals.source=provider` 或 `fundamentals.provider_overlay` 启用时，基本面缓存未命中仍会 lazy init `rqdatac` 读取服务商数据。这是研究 provider runtime，不是数据资产维护入口。

## 操作边界

需要新增、刷新、检查或发布 HK 数据资产时，先在 `market-data-platform` 完成数据生命周期操作，再把产物路径写入本仓库配置。需要在本仓库冻结当前研究环境时，使用 `marketdata backup-data` 保存配置、缓存和已解析的本地输入。

历史留在本仓库 `artifacts/` 下的数据平台文件可以复制回 MDP：

```bash
marketdata migration import-cross-artifacts --artifacts-root "$DATA_PLATFORM_ROOT" --json
marketdata migration import-cross-artifacts --artifacts-root "$DATA_PLATFORM_ROOT" --apply
```

该流程只迁移平台归属的 assets、metadata、intraday cache、release 和 HK health/audit 报告；研究 runs、sweeps、live/export、benchmark 和 slippage 报告继续留在 cross。
