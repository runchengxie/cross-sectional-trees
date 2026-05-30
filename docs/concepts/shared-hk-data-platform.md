# 共享 HK 数据平台边界

本页解决什么：说明 HK 数据层 sunset 后，`cross-sectional-trees` 与 `market-data-platform` 的职责边界。\
本页不解决什么：不定义新的对象存储服务，也不维护数据平台命令细节。\
适合谁：需要判断某段 HK 数据逻辑应该放在哪个仓库的人。\
相关页面：`docs/concepts/external-artifacts-root.md`、`docs/outputs.md`、`docs/rqdata/README.md`、`docs/playbooks/hk-data-assets.md`

## 当前结论

HK 数据生命周期已经不属于 `cross-sectional-trees`。HK daily、PIT、valuation、industry、intraday、current contract、dataset registry、health、asset audit、release，以及 HK tick-depth，统一由 `market-data-platform` 承担。

`cross-sectional-trees` 的职责是研究消费：

* 默认读取数据平台发布的本地文件；provider 在线读取只作为显式 opt-in 的研究侧 legacy 路线。
* 消费 universe 文件，构建 features、labels、models、backtests、live positions 和 execution targets。
* 记录 run 级别复现信息，例如 `inputs.lock.json`、`config.used.yml` 和 `summary.json`。

## 分层

| 层 | 职责 | 所属 |
| --- | --- | --- |
| 数据本体 | provider 原始镜像、派生资产、manifest、checksum、release 包 | `market-data-platform` |
| 数据管理 | 拉取、归集、清洗、对账、健康检查、registry、打包和发布 | `market-data-platform` |
| 策略研究 | 读取已发布数据，生成特征、模型、回测、持仓和研究证据 | `cross-sectional-trees` |

拆分后的核心原则是：策略项目不拥有数据权威来源，策略项目只消费数据平台发布的版本化资产。

## artifacts 数据归属

`cross-sectional-trees/artifacts` 里可以继续保留研究输出，但不应继续作为 HK 数据平台根目录使用。

应迁到 `market-data-platform/artifacts` 的历史数据包括：

* `assets/rqdata/`、`assets/style/`、`assets/universe/`
* `metadata/` 下的 current contract、dataset registry、catalog 和 universe metadata
* `cache/intraday/` 中共享的 HK 分钟线缓存
* `releases/` 中的数据资产发布包
* `reports/` 下 HK health、asset audit、current health、repair inputs 和 health logs

应留在本仓库的研究产物包括：

* `runs/`、`sweeps/`、`live_runs/`、`exports/`、`benchmarks/`、`snapshots/`
* benchmark attribution、slippage calibration、promotion gate、CPCV、feature evidence 等研究报告
* `inputs.lock.json`、`config.used.yml`、`summary.json` 等 run 级复现记录

迁移历史文件时使用平台侧命令：

```bash
marketdata migration import-cross-artifacts --artifacts-root "$DATA_PLATFORM_ROOT" --json
marketdata migration import-cross-artifacts --artifacts-root "$DATA_PLATFORM_ROOT" --apply
```

该命令只复制平台归属文件并生成迁移清单，不删除 cross 里的源文件。源文件清理应在验证平台侧清单和下游读取路径后单独执行。

## 共享数据根目录

研究侧可以通过配置读取外部数据根中的资产：

```bash
export CSTREE_ARTIFACTS_ROOT=/data/hk-data-platform
```

或者在配置中写：

```yaml
paths:
  artifacts_root: "/data/hk-data-platform"
```

如果只想读取几个具体文件，更推荐在配置中显式写入 daily asset、instrument file、PIT flat file、universe by-date file 或 standardized layer 路径，避免把研究 run 输出也写入共享数据根。

## 已 sunset 的 cross 入口

本仓库不再提供 HK 数据资产维护入口，包括旧 RQData asset CLI、HK asset workflow 旧入口、HK health shell scripts、asset package/release 模块和相关测试。旧文档页会保留简短说明，避免链接断裂，但不再承诺这些命令可用。
