# RQData 资料页

本页解决什么：说明 `cross-sectional-trees` 中 RQData 相关资料的当前边界。\
本页不解决什么：不再组织 HK 数据资产运维 runbook。\
适合谁：需要区分 research provider runtime 和数据平台职责的人。\
相关页面：`docs/playbooks/hk-data-assets.md`、`docs/providers.md`、`docs/cli.md`、`docs/concepts/shared-hk-data-platform.md`

## 当前边界

本仓库仍支持 HK + RQData 研究数据源，例如日线 provider、基本面 provider、缓存和本地资产消费配置。

本仓库不再维护 HK RQData 数据资产生命周期。下载、检查、清洗、PIT coverage、current contract、dataset registry、health report 和 release 统一由 `market-data-platform` 负责。

## 页面分工

* `docs/playbooks/hk-data-assets.md`：研究侧如何消费外部 HK 数据资产。
* `docs/playbooks/hk-rqdata-status.md`：旧状态页 sunset 说明。
* `docs/playbooks/hk-intraday-assets.md`：intraday asset sunset 边界和滑点研究入口。
* `docs/rqdata/hk-health-checks.md`：旧 health runbook sunset 说明。
* `docs/rqdata/hk-stock-data-reference.md`：保留 vendor API 文档快照，便于离线检索字段和接口语义。
