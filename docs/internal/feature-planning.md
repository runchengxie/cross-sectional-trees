# 内部功能规划

本页解决什么：给维护者记录功能规划入口和协作边界。\
本页不解决什么：不替代用户文档，也不承诺路线图发布时间。\
适合谁：维护项目能力地图、CLI 分层、资产流程和文档分工的人。\
读完你会得到什么：内部规划资料应该放在哪里、公开文档应该同步哪些内容。\
相关页面：`README.md`、`docs/README.md`、`docs/capabilities.md`、`docs/pipeline-overview.md`、`docs/cli.md`

页面性质：`internal-index`\
最后核对时间：`2026-04-22`

## 使用规则

* 面向用户的事实放在 `README.md`、`docs/README.md`、`docs/capabilities.md` 和对应专题页。
* 新增公开 CLI 或调整能力边界时，先更新 `docs/cli.md`，再同步 `docs/capabilities.md`。
* 新增数据资产流程时，先判断它属于流程页、状态页还是操作快照，避免把会过期的状态复制到多个页面。
* 研究想法可以先放研究笔记；成为正式路径后，再提升到 playbook、concept 或 capabilities。
