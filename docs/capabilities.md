# 项目能力总览

本页解决什么：概览项目能力、主要入口和边界。\
本页不解决什么：不展开命令参数与配置细节。\
适合谁：想判断项目能力范围与边界的人。\
读完你会得到什么：能力清单、入口与边界说明。\
相关页面：`README.md`、`docs/cookbook.md`、`docs/cli.md`、`docs/config.md`、`docs/outputs.md`

## 一句话说明

给定一份配置，`cstree run` 会完成数据读取、股票池处理、标签生成、特征构建、模型训练、评估和回测，并将结果写到 `artifacts/` 目录下。

主流程之外，仓库还提供结果汇总、候选策略晋升检查、固定分数组合层比较、特征证据、benchmark 阶梯、数据资产运维和发布打包工具。完整参数见 `docs/cli.md`。

## 用户可见入口

| 命令 | 用途 | 常见输出 |
| --- | --- | --- |
| `cstree run` | 运行主流程 | `artifacts/runs/<run>/` |
| `cstree summarize` | 聚合历史运行结果，对比各项指标 | `runs_summary.csv` |
| `cstree grid` | 在已有评分结果上做选股数量、成本、缓冲区的敏感性分析 | `grid_summary.csv` |
| `cstree tune` | 按 YAML 搜索空间批量生成实验配置、运行流水线、打分并自动汇总 | `artifacts/sweeps/<tag>/` |
| `cstree sweep-linear` | 批量运行港股精选路线的岭回归（`ridge`）或弹性网络（`elasticnet`）模型并自动汇总 | `artifacts/sweeps/<tag>/` |
| `cstree promotion-gate` | 对比 baseline 与 candidate，检查候选策略是否具备升主线证据 | `artifacts/reports/*promotion_gate*` |
| `cstree construction-grid` | 固定模型分数，比较 Top-K、buffer、权重和执行参数 | `artifacts/reports/*construction_grid*` |
| `cstree feature-evidence ...` | 生成特征族消融、汇总消融结果或计算特征置换重要度 | `artifacts/reports/*feature*` |
| `cstree benchmark-ladder` | 把策略收益和多组 benchmark 分层对比 | `artifacts/reports/*benchmark_ladder*` |
| `cstree holdings` | 读取当前持仓 | 文本 / csv / json |
| `cstree snapshot` | 运行实盘快照，或从现有的运行结果中导出快照 | 文本 / csv / json |
| `cstree alloc` | 基于持仓做等权手数分配 | 文本 / csv / json |
| `cstree alloc-hk` | 基于持仓做港股执行前分配分析（自定义权重、估值分层、二次补仓、资金 × 选股数量场景矩阵） | 文本 / csv / json / xlsx |
| `cstree init-config` | 导出仓库预设配置模板 | 本地 YAML 文件 |
| `cstree backup-data` | 归档本地缓存、股票池、配置以及可选的当前冻结资产集 | `artifacts/snapshots/<name>/` |
| `cstree data ...` | 元数据目录管理、标准层物化和 DuckDB 查询 | `artifacts/metadata/*` 或 `artifacts/standardized/*` |
| `cstree rqdata ...` | RQData 账号、配额、港股财报资产与合约元数据工具 | 账号信息或资产目录 |
| `cstree universe ...` | 股票池构建工具（港股通或港股全市场日线资产） | 股票池文件 |

参数细节请参阅 `docs/cli.md`。

`cstree` 是当前推荐的 CLI 名称；旧入口 `csml` 仅作为兼容 alias 保留。

仓库另外还提供两组模块级的分发工具：

* `python -m csml.release_tools.package_assets` 与 `python -m csml.release_tools.release_assets`：将港股数据资产按模块打包并上传至 GitHub Releases；默认覆盖主线的九个模块，也支持显式附加公告（`announcement`）等补充层。
* `python -m csml.release_tools.package_runs` 与 `python -m csml.release_tools.release_runs`：将历史运行结果按次拆包并上传至 GitHub Releases，支持轻量、里程碑、完整（`light` / `milestone` / `full`）这三档配置。

它们主要用于公开分享、跨机器搬运以及正式版本分发，而非个人的私有备份。

## 入口分层与稳定性

当前建议按以下四个层级理解：

| 层级 | 典型入口 | 当前承诺 |
| --- | --- | --- |
| 公开主线 CLI | `cstree run`、`cstree summarize`、`cstree grid`、`cstree tune`、`cstree sweep-linear`、`cstree promotion-gate`、`cstree construction-grid`、`cstree feature-evidence ...`、`cstree benchmark-ladder`、`cstree holdings`、`cstree snapshot`、`cstree alloc`、`cstree alloc-hk`、`cstree init-config`、`cstree backup-data`、`cstree data ...`、`cstree rqdata ...`、`cstree universe ...` | 当前正式用户入口；文档、测试和说明文件会持续跟随更新 |
| 公开但非 CLI 模块工具 | `python -m csml.release_tools.package_assets`、`python -m csml.release_tools.release_assets`、`python -m csml.release_tools.package_runs`、`python -m csml.release_tools.release_runs` | 已提供文档并具备复用性，但不是 `cstree` CLI 子命令 |
| 研究 / 专题模块工具 | `python -m csml.research.hk_financial_details`、`python -m csml.research.hk_selected_provider_valuation_audit`、`python -m csml.research.hk_intraday_download`、`python -m csml.research.hk_asset_patch_merge` | 仅在专题页面或操作手册中按场景引用；功能可用，但不作为新手的默认入口 |
| 维护与开发辅助 | `scripts/dev/run_tests.sh`、`scripts/internal/` | 测试脚本服务于日常开发与持续集成；内部目录属于维护者的私有工具 |

## 主流程能力

### 数据与市场

* 仅支持 `rqdata` 数据源。
* 仅支持港股（`hk`）市场口径。
* 当前的核心工作流即为港股加 RQData 的入门路线。
* 支持数据缓存、失败重试、相对日期与绝对日期标识。

关于数据服务商的差异说明，请参阅 `docs/providers.md`。

### 股票池

* 支持自动（`auto`）、特定时间点（`pit`）以及静态（`static`）三种股票池模式。
* 支持读取按日期配置的股票池文件。
* 支持停牌处理、最小样本数控制和流动性过滤机制。
* 提供港股通和港股全市场日线资产的股票池构建工具。

### 基本面

* 支持通过服务商在线获取（`fundamentals.source=provider`）以及从本地文件读取（`fundamentals.source=file`）基本面数据。
* 支持港股加 RQData 组合的服务商基本面抓取。
* 支持将 RQData 港股特定时间点（`pit`）财报镜像固化为独立的资产目录，然后再转换为流水线可读的基本面文件。
* 支持数据向前填充（`ffill`）、列名映射、缺失值填补与缺失情况标记。

### 建模与评估

* 模型：支持 XGBoost 回归器（`xgb_regressor`）、XGBoost 排序器（`xgb_ranker`）、岭回归（`ridge`）以及弹性网络（`elasticnet`）。
* 评估：提供信息系数（IC）、分位数收益、换手率、训练期表现对照、滚动评估（rolling）以及分桶信息系数（bucket IC）。
* 稳健性：内置特征置换检验（permutation test）、滚动前向验证（walk-forward）以及最终留出期检验（final OOS）。
* 研究编排：支持结果汇总（`summarize`）、参数网格分析（`grid`）、超参搜索（`tune`）以及线性模型搜索（`sweep-linear`）。
* 研究证据：支持候选策略晋升检查（`promotion-gate`）、固定分数组合层比较（`construction-grid`）、特征证据生成与汇总（`feature-evidence`）以及 benchmark 阶梯报告（`benchmark-ladder`）。

具体的评估指标说明请参阅 `docs/metrics.md`。

### 回测与持仓

* 支持基于排名前 K 名（Top-K）的逻辑进行回测。
* 支持配置交易成本、换手缓冲区、持仓权重分配、业绩基准对比以及头寸退出规则。
* 支持生成历史调仓记录文件、当前最新持仓文件以及当期与上期的调仓差异文件。
* 支持生成实盘环境下的目标持仓快照。

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
* 完整的账户级别行业中性化、风格中性化、总风险敞口和现金管理的动态闭环。

在使用时还需要特别注意：

* 持仓查看命令与快照命令输出的均为目标理论持仓，并不代表真实成交后的实际持仓状态。
* 相对交易日标记（例如最近一个交易日）只有在识别到所配置的服务商支持且交易日历可正常访问时，才会严格按照交易日历进行时间解析。
* 服务商后端的数据回补、本地数据缓存的周期性刷新以及相对日期参数的使用，都可能导致即便使用同一份配置文件重新运行，也会得到不同的结果。
