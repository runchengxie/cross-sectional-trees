# HK 数据资产边界

本页解决什么：说明 HK 数据资产维护已经从 `cross-sectional-trees` sunset，以及研究侧现在如何消费数据。\
本页不解决什么：不再提供下载、检查、修复、打包或 release runbook。\
适合谁：需要跑 HK selected、PIT flat file 或本地资产直读的人。\
相关页面：`docs/playbooks/hk-selected.md`、`docs/concepts/data-sources.md`、`docs/config.md`、`docs/outputs.md`、`docs/providers.md`

## 当前状态

HK daily、PIT、valuation、industry、intraday、current contract、health、asset audit 和 release 已由 `market-data-platform` 统一承载。本仓库不再提供 `cstree rqdata ...`、HK asset workflow wrapper 或数据资产 release 模块。

`cross-sectional-trees` 的定位是研究消费者：

* 读取 provider 在线数据。
* 读取外部数据平台生成的本地 daily asset、instrument file、PIT flat file 或 standardized layer。
* 构建研究股票池、特征、模型、回测和 live/export 产物。

## 研究侧配置

本地资产直读仍使用现有配置键：

* `data.rqdata.daily_asset_dir`
* `data.rqdata.instruments_file`
* `fundamentals.source=file`
* `fundamentals.file`
* `universe.by_date_file`

当 `fundamentals.source=provider` 或 `fundamentals.provider_overlay` 启用时，基本面缓存未命中仍会 lazy init `rqdatac` 读取服务商数据。这是研究 provider runtime，不是数据资产维护入口。

## 操作边界

需要新增、刷新、检查或发布 HK 数据资产时，先在 `market-data-platform` 完成数据生命周期操作，再把产物路径写入本仓库配置。需要在本仓库冻结当前研究环境时，使用 `cstree backup-data` 保存配置、缓存和已解析的本地输入。
