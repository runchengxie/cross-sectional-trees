# 文档首页

这套文档按先跑通，再改配置，再看结果组织。

如果你是第一次进入仓库，先看根目录 `README.md`。`README` 负责项目总览和最短路径，这里负责详细导航。

## 推荐阅读顺序

1. `README.md`：项目定位、快速开始、常用入口。
2. `docs/cookbook.md`：先跑通通用最短流程，再按需要进入 HK 研究配方。
3. `docs/config.md`：修改配置前先看这里。
4. `docs/providers.md`：确认数据源行为和限制。
5. `docs/metrics.md`：理解 IC、回测和稳健性指标。
6. `docs/outputs.md`：看 `summary.json`、持仓文件和 run 目录结构。
7. `docs/troubleshooting.md`：排查常见错误和结果偏差。
8. `docs/dev.md`：本地开发、测试和贡献流程。

## 按主题导航

### 上手

* `README.md`
* `docs/cookbook.md`

### 命令与配置

* `docs/cli.md`
* `docs/config.md`
* `docs/providers.md`

### 结果与产物

* `docs/metrics.md`
* `docs/outputs.md`

### 排错

* `docs/troubleshooting.md`

### 开发

* `docs/dev.md`

### 内部资料

* `internal/full_function.md`：功能矩阵、边界、难点和工时估算。这不是主用户手册。

## 文档约定

* `README.md` 只放项目总览、快速开始和高频入口。
* `docs/cli.md` 是 CLI 参数的权威说明。
* `docs/config.md` 是配置键和默认行为的权威说明。
* `docs/outputs.md` 是输出文件和字段约定的权威说明。
* `docs/troubleshooting.md` 放排障，不重复解释完整配置。
* `docs/cookbook.md` 负责把常见研究流程串起来，不重复展开全部参数表。
