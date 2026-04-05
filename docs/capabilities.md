# 项目能力总览

本页解决什么：概览项目能力、主要入口和边界。\
本页不解决什么：不展开命令参数与配置细节。\
适合谁：想判断项目能力范围与边界的人。\
读完你会得到什么：能力清单、入口与边界说明。\
相关页面：`README.md`、`docs/cookbook.md`、`docs/cli.md`、`docs/config.md`、`docs/outputs.md`

## 一句话说明

给一份配置，`csml` 会完成数据读取、股票池处理、标签生成、特征构建、模型训练、评估、回测，并把结果写到 `artifacts/`。

## 用户可见入口

| 命令 | 用途 | 常见输出 |
| --- | --- | --- |
| `csml run` | 跑主流程 | `artifacts/runs/<run>/` |
| `csml summarize` | 聚合历史 run，对比指标 | `runs_summary.csv` |
| `csml grid` | 在已有评分结果上做 Top-K / 成本 / buffer 敏感性分析 | `grid_summary.csv` |
| `csml tune` | 按 YAML 搜索空间批量生成 trial config、跑 pipeline、打分并自动汇总 | `artifacts/sweeps/<tag>/` |
| `csml sweep-linear` | 批量跑 HK selected 路线的 `ridge` / `elasticnet` 并自动汇总 | `artifacts/sweeps/<tag>/` |
| `csml holdings` | 读取当前持仓 | text / csv / json |
| `csml snapshot` | 跑 live 快照，或从现有 run 导出快照 | text / csv / json |
| `csml alloc` | 基于持仓做等权手数分配 | text / csv / json |
| `csml alloc-hk` | 基于持仓做港股执行前分配分析（custom 权重、估值分层、二次补仓、资金 × TopN 场景矩阵） | text / csv / json / xlsx |
| `csml init-config` | 导出仓库 preset 配置模板 | 本地 YAML |
| `csml backup-data` | 归档本地缓存、股票池和配置 | `artifacts/snapshots/<name>/` |
| `csml data ...` | metadata catalog、标准层物化和 DuckDB 查询 | `artifacts/metadata/*` / `artifacts/standardized/*` |
| `csml rqdata ...` | RQData 账号、配额、港股财报资产与 instrument 元数据工具 | 账号信息或资产目录 |
| `csml universe ...` | 股票池构建工具（`hk-connect` / `hk-daily-assets`） | 股票池文件 |

参数细节见 `docs/cli.md`。

仓库另外还提供两组模块级分发工具：

* `python -m csml.release_tools.package_assets` / `python -m csml.release_tools.release_assets`：把 HK 数据资产按 part 打包并上传到 GitHub Releases；默认覆盖主线 9 个 part，也支持显式附加 `announcement` 这类补充层
* `python -m csml.release_tools.package_runs` / `python -m csml.release_tools.release_runs`：把历史 run 结果按 run 拆包并上传到 GitHub Releases，支持 `light / milestone / full` 三档 profile

它们不是主要用于私有备份、跨机器搬运和 Release 分发。

## 入口分层与稳定性

当前建议按下面四层理解：

| 层级 | 典型入口 | 当前承诺 |
| --- | --- | --- |
| 公开主线 CLI | `csml run`、`csml summarize`、`csml grid`、`csml tune`、`csml sweep-linear`、`csml holdings`、`csml snapshot`、`csml alloc`、`csml alloc-hk`、`csml init-config`、`csml backup-data`、`csml data ...`、`csml rqdata ...`、`csml universe ...` | 当前正式用户入口；文档、测试和 README 会持续跟随 |
| 公开但非 CLI 模块工具 | `python -m csml.release_tools.package_assets`、`python -m csml.release_tools.release_assets`、`python -m csml.release_tools.package_runs`、`python -m csml.release_tools.release_runs` | 已文档化、可复用，但不是 `csml` CLI 子命令 |
| 研究 / 专题模块工具 | `python -m csml.research.hk_financial_details`、`python -m csml.research.hk_selected_provider_valuation_audit`、`python -m csml.research.hk_intraday_download`、`python -m csml.research.hk_asset_patch_merge` | 只在专题页或 playbook 里按场景引用；可用，但不当作默认新手入口 |
| 维护与开发辅助 | `scripts/dev/run_tests.sh`、`scripts/internal/` | `run_tests.sh` 服务开发与 CI；`scripts/internal/` 属于维护者私有工具 |

## 主流程能力

### 数据与市场

* 只支持 `rqdata`。
* 只支持 `hk` 市场口径。
* 当前工作流就是 HK + RQData starter 路线。
* 支持缓存、重试、相对日期和绝对日期。

provider 差异见 `docs/providers.md`。

### 股票池

* 支持 `auto`、`pit`、`static` 三种股票池模式。
* 支持按日期股票池文件。
* 支持停牌处理、最小样本数控制和流动性过滤。
* 提供港股通和 HK 全市场日线资产股票池构建工具。

### 基本面

* 支持 `fundamentals.source=provider` 和 `fundamentals.source=file`。
* 支持 HK + RQData provider 基本面。
* 支持把 RQData 港股 PIT 财报镜像成独立资产目录，再转成 pipeline 可读的 fundamentals 文件。
* 支持 `ffill`、列映射、缺失填补和缺失标记。

### 建模与评估

* 模型：`xgb_regressor`、`xgb_ranker`、`ridge`、`elasticnet`
* 评估：IC、分位数收益、换手、训练期对照、rolling、bucket IC
* 稳健性：permutation test、walk-forward、final OOS
* 研究编排：`summarize`、`grid`、`tune`、`sweep-linear`

指标说明见 `docs/metrics.md`。

### 回测与持仓

* 支持 Top-K 回测。
* 支持成本、buffer、weighting、benchmark 和退出规则。
* 支持历史调仓文件、当前持仓文件和调仓差异文件。
* 支持 live 目标持仓快照。

输出字段见 `docs/outputs.md`。

## 产物与目录

日常最常看的内容：

* `artifacts/runs/<run>/summary.json`
* `artifacts/runs/<run>/config.used.yml`
* `artifacts/runs/<run>/positions_current.csv`
* `artifacts/runs/runs_summary.csv`

默认根目录结构：

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

完整目录和字段见 `docs/outputs.md`。

## 当前边界

当前不覆盖：

* 券商 / OMS 接入。
* 自动下单、成交回执和撤单控制。
* 盘口冲击、涨跌停等微观结构仿真。
* 账户级行业、风格、敞口和现金管理闭环。

使用时还要注意：

* `holdings` 和 `snapshot` 输出的是目标持仓，不是成交后持仓。
* `last_trading_day` 只有在识别到 `provider=rqdata` 且交易日历可用时才会严格按交易日解析。
* provider 回补、缓存刷新和相对日期都会影响同配置重跑结果。
