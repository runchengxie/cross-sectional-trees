# 项目能力总览

本页解决什么：概览项目能力、主要入口和边界。
本页不解决什么：不展开命令参数与配置细节。
适合谁：想判断项目能力范围与边界的人。
读完你会得到什么：能力清单、入口与边界说明。
相关页面：`README.md`、`docs/cookbook.md`、`docs/cli.md`、`docs/config.md`、`docs/outputs.md`

## 一句话说明

给一份配置，`csml` 会完成数据读取、股票池处理、标签生成、特征构建、模型训练、评估、回测，并把结果写到 `artifacts/`。

## 用户可见入口

| 命令 | 用途 | 常见输出 |
| --- | --- | --- |
| `csml run` | 跑主流程 | `artifacts/runs/<run>/` |
| `csml summarize` | 聚合历史 run，对比指标 | `runs_summary.csv` |
| `csml grid` | 在已有评分结果上做 Top-K / 成本 / buffer 敏感性分析 | `grid_summary.csv` |
| `csml sweep-linear` | 批量跑 HK selected 路线的 `ridge` / `elasticnet` 并自动汇总 | `artifacts/sweeps/<tag>/` |
| `csml holdings` | 读取当前持仓 | text / csv / json |
| `csml snapshot` | 跑 live 快照，或从现有 run 导出快照 | text / csv / json |
| `csml alloc` | 基于持仓做等权手数分配 | text / csv / json |
| `csml init-config` | 导出内置配置模板 | 本地 YAML |
| `csml backup-data` | 归档本地缓存、股票池和配置 | `artifacts/snapshots/<name>/` |
| `csml migrate-artifacts` | 一次性把旧布局迁到 `artifacts/` | 新目录结构 |
| `csml rqdata ...` | RQData 账号、配额、港股财报资产与 instrument 元数据工具 | 账号信息或资产目录 |
| `csml universe ...` | 股票池构建工具（`hk-connect` / `hk-daily-assets` / `index-components`） | 股票池文件 |
| `csml tushare verify-token` | 验证 TuShare token | 验证结果 |

参数细节见 `docs/cli.md`。

仓库另外还提供两组脚本级分发工具：

* `scripts/package_assets.py` / `scripts/release_assets.py`：把 HK 数据资产按 part 打包并上传到 GitHub Releases
* `scripts/package_runs.py` / `scripts/release_runs.py`：把历史 run 结果按 run 拆包并上传到 GitHub Releases，支持 `light / milestone / full` 三档 profile

它们不是 `csml` CLI 子命令，主要用于私有备份、跨机器搬运和 Release 分发。

## 主流程能力

### 数据与市场

* 支持 `tushare`、`rqdata`、`eodhd`。
* 支持 `cn`、`hk`、`us` 三个市场口径。
* 当前工作流以 `hk` 为主。
* `default` / `hk` 内置模板默认走 HK + RQData starter 路线。
* `cn/us` 主要保留基础兼容、对照实验和已有配置切换能力。
* 支持缓存、重试、相对日期和绝对日期。

provider 差异见 `docs/providers.md`。

### 股票池

* 支持 `auto`、`pit`、`static` 三种股票池模式。
* 支持按日期股票池文件。
* 支持停牌处理、最小样本数控制和流动性过滤。
* 提供港股通、HK 全市场日线资产和指数成分股票池构建工具。

### 基本面

* 支持 `fundamentals.source=provider` 和 `fundamentals.source=file`。
* 支持 HK + RQData provider 基本面。
* 支持把 RQData 港股 PIT 财报镜像成独立资产目录，再转成 pipeline 可读的 fundamentals 文件。
* 支持 `ffill`、列映射、缺失填补和缺失标记。

### 建模与评估

* 模型：`xgb_regressor`、`xgb_ranker`、`ridge`、`elasticnet`
* 评估：IC、分位数收益、换手、训练期对照、rolling、bucket IC
* 稳健性：permutation test、walk-forward、final OOS
* 研究编排：`summarize`、`grid`、`sweep-linear`

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
  runs/
  live_runs/
  sweeps/
  snapshots/
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
* `migrate-artifacts` 只服务旧目录升级。新仓库通常不需要执行。
