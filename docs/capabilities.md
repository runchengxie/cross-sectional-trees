# 项目能力总览

用途：概览项目能力、主要入口和边界。\
范围：这里只列能力和入口；命令参数与配置细节见对应参考页。\
适合读者：想判断项目能力范围与边界的人。\
阅读后应能定位能力清单、入口和边界说明。\
相关页面：`README.md`、`docs/cookbook.md`、`docs/cli.md`、`docs/config.md`、`docs/outputs.md`

## 一句话说明

给定一份配置，`cstree run` 会完成数据读取、股票池处理、标签生成、特征构建、模型训练、评估和回测，并将结果写到 `artifacts/` 目录下。

项目的研究流水线按市场、数据源、股票池、特征、模型和组合构造分层，正在向 market-agnostic 的低频截面研究框架收敛。中国香港市场 / RQData / 本地平台资产路线是历史验证最充分的 legacy reference；A 股是当前主线迁移方向，先通过 `configs/presets/default_next.yml` 承接 default 切换前验证。

主流程之外，仓库还提供结果汇总、候选策略晋升检查、固定分数组合层比较、特征证据、benchmark 阶梯、股票池工具、标准层查询和运行结果发布打包工具。中国香港市场数据资产生产、检查和发布已经移交给 `market-data-platform`；完整参数见 `docs/cli.md`，边界说明见 `docs/concepts/shared-hk-data-platform.md`，市场生命周期和 default 切换政策见 `docs/market-lifecycle.md`。

## 用户可见入口

| 命令 | 用途 | 常见输出 |
| --- | --- | --- |
| `cstree run` | 运行主流程 | `artifacts/runs/<run>/` |
| `cstree summarize` | 聚合历史运行结果，对比各项指标 | `runs_summary.csv` |
| `cstree grid` | 在已有评分结果上做选股数量、成本、缓冲区的敏感性分析 | `grid_summary.csv` |
| `cstree tune` | 按 YAML 搜索空间批量生成实验配置、运行流水线、打分并自动汇总 | `artifacts/sweeps/<tag>/` |
| `cstree sweep-linear` | 批量运行线性模型研究路线的岭回归（`ridge`）或弹性网络（`elasticnet`）模型并自动汇总；现有预设主要服务 HK selected 路线 | `artifacts/sweeps/<tag>/` |
| `cstree promotion-gate` | 对比 baseline 与 candidate，检查候选策略是否具备升主线证据 | `artifacts/reports/*promotion_gate*` |
| `cstree cpcv` | 对 shortlisted candidate 做 CPCV 稳健性审计，输出多条样本外路径的指标分布 | `artifacts/reports/cpcv_*` |
| `cstree construction-grid` | 固定模型分数，比较 Top-K、buffer、权重和执行参数 | `artifacts/reports/*construction_grid*` |
| `cstree feature-evidence ...` | 生成特征族消融、汇总消融结果、计算特征置换重要度或单因子 IC | `artifacts/reports/*feature*` |
| `cstree benchmark-ladder` | 把策略收益和多组 benchmark 分层对比 | `artifacts/reports/*benchmark_ladder*` |
| `cstree holdings` | 读取当前持仓 | 文本 / csv / json |
| `cstree snapshot` | 运行实盘快照，或从现有的运行结果中导出快照 | 文本 / csv / json |
| `cstree alloc` | 基于持仓做等权手数分配 | 文本 / csv / json |
| `cstree alloc-hk` | 港股 frozen-active 执行前分配分析（自定义权重、估值分层、二次补仓、资金 × 选股数量场景矩阵）；不作为 A 股主线能力 | 文本 / csv / json / xlsx |
| `cstree export-targets` | 将已保存的 long-only live 持仓显式导出为交易执行引擎标准 `targets.json` 并记录来源 | `targets.json`、`targets.json.lineage.json` |
| `cstree init-config` | 导出仓库预设配置模板 | 本地 YAML 文件 |
| `marketdata backup-data` | 归档本地缓存、股票池、配置以及可选的当前冻结资产集 | `artifacts/snapshots/<name>/` |
| `marketdata data ...` | MDP 入口，实际实现由 `market-data-platform` 的 `marketdata data ...` 承载 | `artifacts/metadata/*` 或 `artifacts/standardized/*` |
| `marketdata rqdata hk-assets ...` | HK universe 已删除的旧入口，实际实现和资产归属在 `market-data-platform` | 股票池文件 |

参数细节请参阅 `docs/cli.md`。

`cstree` 是当前 CLI 名称。

仓库另外还提供一组模块级的运行结果分发工具：

* `python -m cstree.release_tools.package_runs` 与 `python -m cstree.release_tools.release_runs`：将历史运行结果按次拆包并上传至 GitHub Releases，支持轻量、里程碑、完整（`light` / `milestone` / `full`）这三档配置。

它们主要用于公开分享、跨机器搬运以及正式版本分发，而非个人的私有备份。

## 命名空间策略

当前公开命名空间为 `cstree`：

* 示例使用 `cstree` CLI、`python -m cstree...` 模块路径、`import cstree...` 和 `CSTREE_*` 环境变量。
* `src/cstree/` 是研究侧实现所有权所在的包；数据平台能力会通过已删除的旧入口 改用 `market-data-platform`。
* `csml` CLI、`python -m csml...`、`import csml` 和 `CSML_*` 环境变量不再属于公开兼容面。

模块级入口 inventory：

| 分类 | 入口 |
| --- | --- |
| 公开 release 工具 | `python -m cstree.release_tools.package_runs`、`python -m cstree.release_tools.release_runs` |
| Playbook / 专题研究工具 | `python -m cstree.research.hk_financial_details`、`python -m cstree.research.hk_selected_provider_valuation_audit`、`marketdata rqdata refresh-hk-intraday`、`python -m cstree.research.hk_intraday_slippage_report`、`python -m cstree.research.hk_connect_cap_weight_benchmark`、`python -m cstree.research.hk_benchmark_attribution`、`python -m cstree.research.hk_monthly_run_compare` |
| 内部 / 测试面 | `src/cstree/` 内部导入、`scripts/internal/` driver、测试里的直接 `cstree` import |

## 入口分层与稳定性

当前建议按以下四个层级理解：

| 层级 | 典型入口 | 当前承诺 |
| --- | --- | --- |
| 公开主线 CLI | `cstree run`、`cstree summarize`、`cstree grid`、`cstree tune`、`cstree sweep-linear`、`cstree promotion-gate`、`cstree cpcv`、`cstree construction-grid`、`cstree feature-evidence ...`、`cstree benchmark-ladder`、`cstree holdings`、`cstree snapshot`、`cstree alloc`、`cstree export-targets`、`cstree init-config`、`marketdata backup-data` | 当前正式用户入口；文档、测试和说明文件会持续跟随更新 |
| 市场专项 frozen-active CLI | `cstree alloc-hk` | 港股执行前分配分析保留给复现、明确跟踪或报告需求；不作为 A 股主线能力扩展 |
| 兼容迁移 CLI | `marketdata data ...`、`marketdata rqdata hk-assets ...` | 标准层查询和 HK universe asset builder 的过渡入口，改用 `market-data-platform` |
| 公开但非 CLI 模块工具 | `python -m cstree.release_tools.package_runs`、`python -m cstree.release_tools.release_runs` | 已提供文档并具备复用性，但不是 `cstree` CLI 子命令 |
| 研究 / 专题模块工具 | `python -m cstree.research.hk_financial_details`、`python -m cstree.research.hk_selected_provider_valuation_audit`、`marketdata rqdata refresh-hk-intraday` | 仅在专题页面或操作手册中按场景引用；功能可用，但不作为新手的默认入口 |
| 维护与开发辅助 | `scripts/dev/run_tests.sh`、`scripts/internal/` | 测试脚本服务于日常开发与持续集成；内部目录属于维护者的私有工具 |

### 入口变更要求

| 层级 | 变更要求 |
| --- | --- |
| 公开主线 CLI | 改命令、参数、默认行为、输出字段或 provider 语义时，同步更新 `docs/cli.md`、相关配置 / 输出文档和 focused tests。破坏兼容需要另开迁移说明。 |
| 公开但非 CLI 模块工具 | 保持模块路径、参数和 release artifact contract 稳定；改动时同步 release 工具文档和打包 / 发布测试。 |
| 研究 / 专题模块工具 | 可以按研究需要小步调整，但要保留可复现实验入口；不因低频使用直接删除，删除前先做 repo-local 引用审计。 |
| 维护与开发辅助 | 可以服务维护效率而收口，但涉及 hooks、测试入口或维护者 旧入口 时，必须同步脚本文档和对应测试。 |

内部 helper 不因为被 facade、命令 registry 或 package `__all__` 导出就自动成为稳定 API。
如需对外暴露，应先补文档和测试；否则应留在 owning module 内测试，避免扩大兼容面。

## 主流程能力

### 数据与市场

* 研究配置已经显式保留 `market` 和 `data.provider` 边界，目标是让主流程按市场适配数据、股票池和执行日历。
* 当前正式验证最充分的 legacy reference 是 `market=hk` 加 `data.provider=rqdata`；它不再代表未来默认研发预算方向。
* `configs/presets/default_next.yml` 是 A 股 default 迁移候选；`configs/presets/a_share.yml` 是中国大陆市场 / A 股方向的基础 baseline，但不应被理解为已达到 HK/RQData 历史路线同等成熟度。
* 本地资产直读归在 RQData provider 的离线资产模式下，配置仍使用 `data.provider=rqdata`。
* 支持数据缓存、失败重试、相对日期与绝对日期标识。
* 数据资产生产、检查和发布已由 `market-data-platform` 承担。本仓库只读取 provider、本地资产、标准层和 `market-data-platform` 产物，不再提供 `cstree rqdata ...` 维护入口。

关于数据服务商的差异说明，请参阅 `docs/providers.md`。

### 股票池

* 支持自动（`auto`）、特定时间点（`pit`）以及静态（`static`）三种股票池模式。
* 支持读取按日期配置的股票池文件。
* 支持停牌处理、最小样本数控制和流动性过滤机制。
* HK universe asset builder 已由 `market-data-platform` 承担；本仓库只保留已删除的旧入口 和研究侧读取逻辑。

### 基本面

* 支持通过服务商在线获取（`fundamentals.source=provider`）以及从本地文件读取（`fundamentals.source=file`）基本面数据。
* 当前已验证中国香港市场加 RQData 组合的服务商基本面抓取。
* 支持读取由外部数据平台生成的 PIT 平面基本面文件。
* 支持数据向前填充（`ffill`）、列名映射、缺失值填补与缺失情况标记。

### 建模与评估

* 模型：支持 XGBoost 回归器（`xgb_regressor`）、XGBoost 排序器（`xgb_ranker`）、岭回归（`ridge`）以及弹性网络（`elasticnet`）。
* 评估：提供信息系数（IC）、分位数收益、换手率、训练期表现对照、滚动评估（rolling）以及分桶信息系数（bucket IC）。
* 稳健性：内置特征置换检验（permutation test）、滚动前向验证（walk-forward）、最终留出期检验（final OOS）以及候选升主线前的 CPCV sidecar。
* 研究编排：支持结果汇总（`summarize`）、参数网格分析（`grid`）、超参搜索（`tune`）以及线性模型搜索（`sweep-linear`）。
* 研究证据：支持候选策略晋升检查（`promotion-gate`）、CPCV 稳健性审计（`cpcv`）、固定分数组合层比较（`construction-grid`）、特征证据生成与汇总、单因子 IC（`feature-evidence`）以及 benchmark 阶梯报告（`benchmark-ladder`）。

具体的评估指标说明请参阅 `docs/metrics.md`。

### 回测与持仓

* 支持基于排名前 K 名（Top-K）的逻辑进行回测。
* 支持配置交易成本、换手缓冲区、持仓权重分配、业绩基准对比以及头寸退出规则。
* 支持生成历史调仓记录文件、当前最新持仓文件以及当期与上期的调仓差异文件。
* 支持生成实盘环境下的目标持仓快照。
* 支持将已确认的 long-only live 持仓导出为 `quant-execution-engine` 可消费的标准 `targets.json`，同时保留独立来源记录伴随文件；此导出不触发下单。

输出的详细字段约定请参阅 `docs/outputs.md`。

## 产物与目录

在日常研究中，最常查看的内容包括：

* `artifacts/runs/<run>/summary.json`
* `artifacts/runs/<run>/config.used.yml`
* `artifacts/runs/<run>/positions_current.csv`
* `artifacts/runs/runs_summary.csv`

默认的产物根目录结构如下：

```text
artifacts/
  cache/
  assets/
  metadata/
  standardized/
  runs/
  live_runs/
  sweeps/
  snapshots/
  reports/
```

完整的目录结构与字段定义请参阅 `docs/outputs.md`。

## 当前边界

当前系统不覆盖以下功能：

* 真实券商账户或订单管理系统（OMS）接入。
* 自动交易下单、成交回执处理和撤单控制。
* 盘口价格冲击、涨跌停等极其微观的交易结构仿真。
* 直接在低频回测中扫描十档盘口 raw snapshot；这类数据应先在数据层聚合成日频特征或交易成本模型资产。
* 完整的账户级别行业中性化、风格中性化、总风险敞口和现金管理的动态闭环。

在使用时还需要特别注意：

* 持仓查看命令与快照命令输出的均为目标理论持仓，并不代表真实成交后的实际持仓状态。
* 相对交易日标记（例如最近一个交易日）只有在识别到所配置的服务商支持且交易日历可正常访问时，才会严格按照交易日历进行时间解析。
* 服务商后端的数据回补、本地数据缓存的周期性刷新以及相对日期参数的使用，都可能导致即便使用同一份配置文件重新运行，也会得到不同的结果。
