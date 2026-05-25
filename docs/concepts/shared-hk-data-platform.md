# 共享 HK 数据平台边界

本页解决什么：说明什么时候把 HK 数据层从策略研究仓库里拆出来，以及拆出后
`cross-sectional-trees` 和 `rqdata-hk-depth-snapshots` 应该怎样通过数据契约互通。\
本页不解决什么：不定义新的对象存储服务，也不要求立刻迁移所有代码。\
适合谁：同时维护日线 / PIT / intraday / 十档盘口快照，并希望多个策略或数据工具复用同一套数据资产的人。\
读完你会得到什么：当前可执行的拆分顺序、目录契约和两个现有仓库的职责边界。\
相关页面：`docs/concepts/external-artifacts-root.md`、`docs/outputs.md`、`docs/rqdata/README.md`、`docs/playbooks/hk-data-assets.md`、`docs/playbooks/hk-intraday-assets.md`

## 结论

现在可以开始把 HK 数据层单独拆出来，但更稳妥的第一步不是搬代码，而是先把数据契约固定下来。

当前 `cross-sectional-trees` 已经包含一套事实上的数据平台雏形：

* `artifacts/assets/rqdata/hk/...` 保存可复用 provider 资产。
* `artifacts/metadata/current_assets/hk_current.json` 记录当前 HK 资产 alias 的 resolved path 和 manifest 摘要。
* `artifacts/metadata/dataset_registry.csv` 从 current contract 派生，给人工盘点和下游引用使用。
* `cstree rqdata inspect-hk-*`、`cstree data catalog` 和 release 工具已经承担资产检查、索引和分发职责。

因此适合采用分阶段拆分：

1. 先把 `artifacts_root` 外置成共享数据根目录。
2. 保持 `cross-sectional-trees` 只读消费 current contract 和 manifest-backed asset。
3. 让 `rqdata-hk-depth-snapshots` 继续维护十档盘口 raw / daily aggregate，并把日频聚合或成本模型派生物发布到同一个数据根目录。
4. 等两个项目都只依赖共享数据契约后，再考虑把 `cstree rqdata ...` 里的通用资产维护代码迁到独立 repo 或 package。

## 目标分层

长期目标可以按三层看：

| 层 | 职责 | 典型内容 |
| --- | --- | --- |
| 数据本体 | 保存 provider 原始镜像、派生资产、manifest、checksum 和 release 包 | daily、PIT、valuation、industry、5m intraday、tick depth raw、tick depth daily aggregate |
| 数据管理 | 拉取、归集、清洗、对账、健康检查、registry、打包和发布 | `mirror-*`、`health`、`reconcile`、`current contract`、`dataset registry` |
| 策略研究 | 读取已发布数据，生成特征、模型、回测、持仓和研究证据 | `cstree run`、`feature-evidence`、`benchmark-ladder`、`alloc-hk` |

拆分后的核心原则是：策略项目不拥有数据权威来源，策略项目只消费数据平台发布的版本化资产。

## 当前两个仓库的职责

`cross-sectional-trees` 当前应继续负责：

* 策略研究主流程、模型、回测、持仓和研究报告。
* 读取本地 HK daily / PIT / valuation / industry 等资产。
* 维护当前已公开的 `cstree rqdata ...` 入口，直到对应能力迁出并提供兼容 shim。
* 生成 `inputs.lock.json`、`config.used.yml` 和 run 级别复现记录。

`rqdata-hk-depth-snapshots` 当前应继续负责：

* RQData HK 十档盘口快照的探查、下载、resume 和 quota guard。
* raw snapshot health、daily aggregate、`reconcile-daily` 和冷归档打包。
* 将 raw snapshot 聚合成低频研究可消费的日频特征或交易成本校准输入。

两个仓库之间不要互相 import 代码，也不要把对方的工作目录当成权威数据源。互通点只应是共享数据根目录里的 manifest-backed asset。

## 共享数据根目录

当前推荐先使用共享 HK 数据根承载输入资产，并让策略项目继续保留自己的 run/cache/report 输出：

```bash
export HK_DATA_PLATFORM_ROOT=/data/hk-data-platform
```

如果你明确希望把本仓库的 run/cache/report 默认输出也放到同一个根目录，再额外设置：

```bash
export CSTREE_ARTIFACTS_ROOT=/data/hk-data-platform
```

或者在配置中写：

```yaml
paths:
  artifacts_root: "/data/hk-data-platform"
```

这会把策略运行产物也写入共享根，因此更适合数据维护仓库，不是普通研究 run 的默认选择。

这个根目录内继续沿用现有分层：

```text
/data/hk-data-platform/
  assets/
    rqdata/
      hk/
        daily/
        intraday/
        pit_financials/
        valuation/
        tick_depth/
        tick_depth_daily/
    universe/
  metadata/
    current_assets/
      hk_current.json
    dataset_registry.csv
  reports/
  standardized/
  runs/
  sweeps/
  snapshots/
```

`runs/`、`sweeps/` 和 `live_runs/` 可以继续跟随同一个根目录，也可以在策略项目里另设更细的输出路径。数据平台拆分时，最重要的是让 `assets/`、`metadata/` 和 `reports/` 可被多个项目读取。

## Current Contract

共享数据层的第一份稳定契约是：

```text
<artifacts_root>/metadata/current_assets/hk_current.json
```

它应该描述当前 HK 资产的可用入口，包括：

* alias path 和 resolved path
* manifest path
* as-of date
* dataset、status、query date range 和 totals 摘要

策略项目应优先读取 current contract 或其中的 resolved asset，而不是扫描任意 `latest` alias。

十档盘口相关正式资产在 current contract 中使用下面这些 asset key：

| Asset key | 建议路径 | 用途 |
| --- | --- | --- |
| `tick_depth_raw` | `assets/rqdata/hk/tick_depth/<snapshot>/` | 原始十档盘口快照交付目录，主要用于审计和重聚合 |
| `tick_depth_daily` | `assets/rqdata/hk/tick_depth_daily/<snapshot>/` | 日频盘口聚合特征，供研究或成本模型读取 |
| `execution_cost_model` | `assets/rqdata/hk/execution_cost/<snapshot>/` | 由盘口、分钟线和日线校准出的交易成本参数 |

当前 `cross-sectional-trees` 尚未把这些 key 纳入主 pipeline，因此这些 key 只用于共享数据契约、健康检查和 registry 展示，不直接改变回测行为。

## 对账方向

正确的对账方向是：

* 十档盘口 raw / aggregate 对账时，可以读取共享数据根目录中的日线资产作为 reference。
* `cross-sectional-trees` 不应该成为日线数据的权威来源；它只是当前维护这套日线资产工具的仓库。
* 如果对账使用研究清洗口径，应明确标记为 `cross-clean`，数值口径差异只作为研究覆盖检查，不作为 raw 下载验收门禁。

示例：

```bash
rqdata-hk-depth reconcile-daily \
  --tick-input /data/hk-data-platform/assets/rqdata/hk/tick_depth/core_20250401_20260506 \
  --daily-asset-dir /data/hk-data-platform/assets/rqdata/hk/daily/hk_all_daily_clean_latest \
  --out /data/hk-data-platform/reports/tick_daily_reconcile_cross_clean.json \
  --reference-policy cross-clean
```

用于下载验收时，优先使用同报价口径的 raw daily reference，并标记为 `raw-daily`。

## 策略使用盘口数据的方式

`cross-sectional-trees` 不应在普通低频回测中直接扫描 raw tick depth parquet。更合适的消费方式是由数据层先生成轻量派生物：

* 按 symbol / trade_date 聚合的 spread、depth、imbalance、VWAP 质量和 coverage 标记。
* 按成交额分位、时段、流动性分桶校准的滑点或冲击成本参数。
* 带 as-of 和样本窗口的 `execution_cost_model` asset。

策略回测读取这些派生表后，再把成本参数接入 `backtest` 或 `execution` 配置。这样可以避免研究 pipeline 被超大 raw snapshot I/O 绑死，也更符合低频策略的复现要求。

## Symbol 约定

两个仓库都需要保留 provider 原生标识和研究 canonical 标识：

| 字段 | 约定 |
| --- | --- |
| `order_book_id` | RQData 原生标识，例如 `00005.XHKG` |
| `symbol` | 研究 canonical 标识，例如 `00005.HK` |

数据平台交付给 `cross-sectional-trees` 的日频或成本模型派生物，应至少提供 `symbol`。如果原始数据来自 RQData，也应保留 `order_book_id` 便于追溯和对账。

## Git 边界

推荐继续使用多个 Git repo：

* `cross-sectional-trees.git`：策略研究与回测。
* `rqdata-hk-depth-snapshots.git`：十档盘口快照工具；未来可以并入数据平台 repo。
* `hk-data-platform.git`：后续独立出来的数据管理代码、schema、manifest 模板、数据检查和发布工具。

大数据本体不进 Git。Git 只追踪：

* 代码
* schema / manifest 模板
* 配置和 universe 生成规则
* 健康检查 policy
* 小样本测试数据
* 文档和迁移记录

parquet、tarball、cache、run 输出和报告仍放在共享 `artifacts_root`、NAS、对象存储或 release asset 中。

## 拆分顺序

建议按下面顺序推进：

1. 外置共享 `artifacts_root`，让两个项目都能读写同一套数据根。
2. 把日线、PIT、估值、行业、分钟线和十档盘口的正式资产都收口到 manifest-backed 目录。
3. 使用 `hk_current.json` 和 `dataset_registry.csv` 登记 `tick_depth_daily` 和未来的 `execution_cost_model`。
4. 在 `rqdata-hk-depth-snapshots` 中用共享 daily asset 做 `reconcile-daily`，报告写入共享 `reports/`。
5. 在 `cross-sectional-trees` 中先只消费 `execution_cost_model` 这种轻量派生物，而不是 raw snapshot。
6. 等 CLI 和测试覆盖稳定后，再把通用 `cstree rqdata ...` 数据维护代码迁到独立数据平台 package，并在 `cstree` 保留兼容入口或清晰迁移说明。

这个顺序能避免一次性把策略、数据下载、历史资产和测试全部拆开，降低中途两个项目都不可用的风险。
