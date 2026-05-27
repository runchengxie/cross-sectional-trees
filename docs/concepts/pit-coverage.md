# PIT 覆盖率

PIT 覆盖率检查用于判断本地 `pipeline_fundamentals.parquet` 在指定研究股票池和调仓日期上是否足够可用。

`cross-sectional-trees` 不再内置 PIT 覆盖率检查命令。HK PIT coverage、health 和质量门禁已经迁到 `market-data-platform`。研究侧若使用 `fundamentals.source=file`，应先在数据平台完成 PIT flat file 生成和覆盖率检查，再运行本仓库的研究流程。

`cstree run` 仍会把已保存的质量摘要用于 liveops 后置门禁；新的 preflight 计算不再在本仓库执行。
