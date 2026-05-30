# HK Intraday 资产

HK intraday 下载、health、asset build、current alias 和 release 已从本仓库 sunset，并由 `market-data-platform` 承载。

`marketdata rqdata refresh-hk-intraday` 仅保留为已删除的旧入口，并转到 `market-data-platform` 的实现；新流程应使用 `marketdata rqdata refresh-hk-intraday` 或平台侧模块。本仓库保留 `python -m cstree.research.hk_intraday_slippage_report` 等研究分析入口，用于消费已经准备好的分钟线文件和校准执行成本假设。数据资产本身的生产、检查和发布不再由 `cross-sectional-trees` 负责。
