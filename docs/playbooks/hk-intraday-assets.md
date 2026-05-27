# HK Intraday 资产

HK intraday 下载、health、asset build、current alias 和 release 已从本仓库 sunset，并由 `market-data-platform` 承载。

本仓库仍保留研究分析入口，例如 `python -m cstree.research.hk_intraday_download` 和 `python -m cstree.research.hk_intraday_slippage_report`，用于消费已经准备好的分钟线文件和校准执行成本假设。数据资产本身的生产、检查和发布不再由 `cross-sectional-trees` 负责。
