# RQData 资料页

本页解决什么：给 HK / RQData 离线资产、仓库状态和 API 快照提供一个专题入口。  
本页不解决什么：不代替 CLI 参数文档，也不代替官方在线文档。  
适合谁：准备补 HK 离线资产、核对当前本地状态，或需要离线查 API 语义的人。  
读完你会得到什么：这组文档的阅读顺序，以及它们各自的分工边界。  
相关页面：`docs/playbooks/README.md`、`docs/providers.md`、`docs/cli.md`

当前这个专题只围绕 HK + RQData 主线组织。

这里实际有三类页面：

* 流程 / 状态页：`hk-data-assets.md`、`hk-rqdata-status.md`、`hk-intraday-assets.md`
* 运维 runbook：`hk-health-checks.md`
* reference snapshot：`hk-stock-data-reference.md`

## 建议阅读顺序

1. 先看 [`docs/playbooks/hk-data-assets.md`](../playbooks/hk-data-assets.md)，确认哪些资产值得优先离线保存、应该按什么顺序补。
2. 再看 [`docs/playbooks/hk-rqdata-status.md`](../playbooks/hk-rqdata-status.md)，确认当前工作区里哪些 snapshot / alias 已经可复用，哪些还只是 probe。
3. 如果你想把本地 HK 资产健康检查跑成一组 report / log，再看 `docs/rqdata/hk-health-checks.md`。
4. 如果你在补 HK 分钟线、看 `5m` quota 成本，或要复用现有滑点校准结果，再看 [`docs/playbooks/hk-intraday-assets.md`](../playbooks/hk-intraday-assets.md)。
5. 需要离线查 vendor API 语义时，再看 [`hk-stock-data-reference.md`](./hk-stock-data-reference.md)。

## 分工边界

* `hk-data-assets.md`
  负责“该保留什么、按什么顺序准备、不同资产层之间是什么关系”。
* `hk-rqdata-status.md`
  负责“当前这个仓库磁盘上到底有什么、哪些目录能当主线入口、哪些别误用”。
* `hk-intraday-assets.md`
  负责“当前 `5m` 分钟线到底落了哪些块、provider 边界在哪里、quota 够不够继续下、已经产出了哪些滑点校准文件”。
* `hk-health-checks.md`
  负责“本地应该先跑哪些 health 命令、如何落 report / log、何时用轻检查替代重扫描”。
* `hk-stock-data-reference.md`
  负责保留米筐港股 API 文档快照，便于离线检索字段和接口语义。

## 使用规则

* 如果 `hk-stock-data-reference.md` 和仓库代码 / manifest / playbook 发生冲突，优先以仓库当前实现和本地资产 manifest 为准。
* 如果你新增、重刷或清理了 HK / RQData 资产，优先更新 `hk-rqdata-status.md`，不要把当前磁盘状态复制到多个页面。
* 参数和命令权威说明仍然在 `docs/cli.md`；provider 行为差异仍然在 `docs/providers.md`。
