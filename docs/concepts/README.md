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
| [model-selection.md](model-selection.md) | 四个模型（xgb_regressor、xgb_ranker、ridge、elasticnet）怎么选 |
| [pit-coverage.md](pit-coverage.md) | PIT 财务覆盖率体检怎么看 |
| [universe-modes.md](universe-modes.md) | auto/pit/static 三种股票池模式的区别 |
| [data-sources.md](data-sources.md) | 数据 provider（tushare/rqdata/eodhd）怎么选 |

---

## 什么时候该看这些文档

- 想改配置里的模型类型 → 看 [model-selection.md](model-selection.md)
- 做季度 PIT 研究 → 先看 [pit-coverage.md](pit-coverage.md)
- 理解股票池模式的区别 → 看 [universe-modes.md](universe-modes.md)
- 选择数据 provider → 看 [data-sources.md](data-sources.md)
