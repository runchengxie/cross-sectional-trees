# RQData 资料页

本页解决什么：给 HK / RQData 离线资产、仓库状态和 API 快照提供一个专题入口。
本页不解决什么：不代替 CLI 参数文档，也不代替官方在线文档。
适合谁：准备补 HK 离线资产、核对当前本地状态，或需要离线查 API 语义的人。
读完你会得到什么：这组四页文档的阅读顺序，以及它们各自的分工边界。
相关页面：`docs/playbooks/README.md`、`docs/providers.md`、`docs/cli.md`

这组资料适合单独收口成一个专题入口，但不建议把研究流程类页面整体移出 `docs/playbooks/`。

这里实际上有两类页面：

* 流程 / 状态页：`hk-data-assets.md`、`hk-rqdata-status.md`
* reference snapshot：`hk-stock-data-reference.md`、`a-share-data-reference.md`

原因很简单：

* `hk-data-assets.md` 和 `hk-rqdata-status.md` 仍然属于研究 / 运维 playbook。
* `hk-stock-data-reference.md` 和 `a-share-data-reference.md` 更像外部 API 的离线 reference snapshot。
* 把它们强行塞进同一层目录，会让流程文档和参考手册的边界变糊。

更合理的做法是保留原有分工，同时在这里给一个统一入口，而不是把所有和 RQData 有关的内容都塞进一个目录。

## 建议阅读顺序

1. 先看 [`docs/playbooks/hk-data-assets.md`](../playbooks/hk-data-assets.md)，确认哪些资产值得优先离线保存、应该按什么顺序补。
2. 再看 [`docs/playbooks/hk-rqdata-status.md`](../playbooks/hk-rqdata-status.md)，确认当前工作区里哪些 snapshot / alias 已经可复用，哪些还只是 probe。
3. 需要离线查 vendor API 语义时，再看 [`hk-stock-data-reference.md`](./hk-stock-data-reference.md)；如果要对照 A 股接口，再看 [`a-share-data-reference.md`](./a-share-data-reference.md)。

## 分工边界

* `hk-data-assets.md`
  负责“该保留什么、按什么顺序准备、不同资产层之间是什么关系”。
* `hk-rqdata-status.md`
  负责“当前这个仓库磁盘上到底有什么、哪些目录能当主线入口、哪些别误用”；也负责那张最短的 `dataset -> 是否全市场 / 是否全字段 / 时间范围 / 是否主线` 对照表。
* `hk-stock-data-reference.md`
  负责保留米筐港股 Python API 文档快照，便于试用资格到期后离线检索字段和接口语义。
* `a-share-data-reference.md`
  负责保留米筐 A 股 API 文档快照，作为对照参考。

## 使用规则

* 如果 `hk-stock-data-reference.md`、`a-share-data-reference.md` 和仓库代码 / manifest / playbook 发生冲突，优先以仓库当前实现和本地资产 manifest 为准。
* 如果你新增、重刷或清理了 HK / RQData 资产，优先更新 `hk-rqdata-status.md`，不要把当前磁盘状态复制到多个页面。
* 参数和命令权威说明仍然在 `docs/cli.md`；provider 行为差异仍然在 `docs/providers.md`。
