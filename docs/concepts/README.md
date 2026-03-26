# 概念指南

本页解决什么：概念页的索引与阅读入口。
本页不解决什么：不展开任何具体概念的内容。
适合谁：需要理解概念差异或做选择的人。
读完你会得到什么：概念页的定位与跳转路径。
相关页面：`docs/config.md`、`docs/cookbook.md`、`docs/playbooks/README.md`

这里收集了项目中需要专门解释的核心概念。每个文档都是独立的，可以单独阅读。

## 概念文档

| 文档 | 解决的问题 |
|------|-----------|
| [benchmark-protocol.md](benchmark-protocol.md) | benchmark 应该怎么分层、HK selected 默认 protocol 是什么 |
| [model-landscape.md](model-landscape.md) | 更广的算法宇宙怎么理解，为什么当前只保留四个模型 |
| [model-selection.md](model-selection.md) | 四个模型（xgb_regressor、xgb_ranker、ridge、elasticnet）怎么选 |
| [pit-coverage.md](pit-coverage.md) | PIT 财务覆盖率体检怎么看 |
| [universe-modes.md](universe-modes.md) | auto/pit/static 三种股票池模式的区别 |
| [data-sources.md](data-sources.md) | 当前 HK + RQData 数据边界和本地资产模式怎么用 |

## 什么时候该看这些文档

- 想把 baseline / benchmark 阶梯定清楚 → 看 [benchmark-protocol.md](benchmark-protocol.md)
- 想理解为什么当前只维护四个模型，以及别的算法什么时候值得引入 → 看 [model-landscape.md](model-landscape.md)
- 想改配置里的模型类型 → 看 [model-selection.md](model-selection.md)
- 做季度 PIT 研究 → 先看 [pit-coverage.md](pit-coverage.md)
- 理解股票池模式的区别 → 看 [universe-modes.md](universe-modes.md)
- 确认当前数据边界与本地资产模式 → 看 [data-sources.md](data-sources.md)
