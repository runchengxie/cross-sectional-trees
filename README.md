# cross-sectional-machine-learning

使用 TuShare / RQData / EODHD 日线数据做截面因子研究、评估和持仓快照。

项目当前支持：

* `xgb_regressor`
* `xgb_ranker`
* `ridge`
* `elasticnet`

模型差异、适用场景和选择建议见 `docs/config.md`。

默认产物写入 `artifacts/`，其中常见目录包括：

```text
artifacts/
  cache/
  assets/
  runs/
  live_runs/
  sweeps/
  snapshots/
```

## 适用范围

* 低频研究与复现实验。
* Long-only 组合评估与目标持仓快照。
* 港股优先的研究与持仓工作流。
* A 股和美股模板继续保留，用于兼容已有配置和多市场对照。
* 历史 run 汇总、线性模型 sweep、Top-K / 成本敏感性分析。

当前不覆盖：

* 券商接入与自动下单。
* 成交回执、撤单重试和盘中执行控制。
* 账户级风控闭环。

## 快速开始

推荐环境：Python 3.12+，`uv`。

```bash
uv venv --seed
uv sync --extra dev --extra rqdata
cp .env.example .env
csml run --config default
```

如果你只想安装基础开发依赖，不跑港股默认模板：

```bash
uv sync --extra dev
```

最小鉴权取决于 `data.provider`：

* `tushare`：`TUSHARE_TOKEN`
* `rqdata`：`RQDATA_USERNAME` + `RQDATA_PASSWORD`
* `eodhd`：`EODHD_API_TOKEN`

补充：

* `default` 是 HK starter 模板。它用静态港股股票池，适合先确认主流程能跑通。
* `csml run --config default` 里的 `default` 是内置别名，不等于仓库里的 `configs/presets/default.yml`。
* `hk` 或 `configs/presets/hk.yml` 更适合正式 PIT 港股研究。
* `cn/us` 继续保留，但当前文档不把它们作为主阅读路线。
* 如果你要跑季度或年度 PIT 财报路线，先准备本地 `pipeline_fundamentals.parquet`。入口见 `docs/playbooks/README.md`。

第一次跑完后，先看这三个文件：

* `summary.json`
* `config.used.yml`
* `positions_current.csv`

## 常用入口

```bash
# 主流程
csml run --config default

# PIT 港股研究模板
csml run --config hk

# 导出内置模板
csml init-config --market default --out configs/

# 跨历史 run 汇总
csml summarize --runs-dir artifacts/runs --output artifacts/runs/runs_summary.csv

# 读取当前持仓
csml holdings --config hk --as-of t-1

# 一键生成 live 快照
csml snapshot --config configs/local/hk_live.local.yml

# 从持仓生成等权手数分配
csml alloc --config configs/local/hk_live.local.yml --source live --top-n 20 --cash 1000000

# 查询命令帮助
csml --help
csml <subcommand> --help
```

如果你是在旧版本目录上继续使用这个仓库，再看 `docs/troubleshooting.md` 里的 `csml migrate-artifacts`。新仓库通常不需要这一步。

## 文档导航

先看 [docs/README.md](docs/README.md)。

按任务阅读：

* 想先知道项目能做什么：`docs/capabilities.md`
* 想跑通常见流程：`docs/cookbook.md`
* 想做 HK selected 研究矩阵：`docs/playbooks/README.md`
* 想查命令参数：`docs/cli.md`
* 想改配置：`docs/config.md`
* 想看指标与输出：`docs/metrics.md`、`docs/outputs.md`
* 想查 provider 行为：`docs/providers.md`
* 想排错：`docs/troubleshooting.md`
* 想做开发和测试：`docs/dev.md`

## 复现建议

* 固定 `data.start_date` / `data.end_date`，避免 `today`、`t-1`、`now`。
* 保留 `artifacts/cache/`、`config.used.yml`、`summary.json` 和 git commit。
* 多数据源切换时，同时记录 `data.provider` 与 provider 专属参数。
* 需要本地快照时，使用 `csml backup-data`。

## 说明

`README.md` 只保留项目总览和最短路径。详细说明统一放在 `docs/` 中维护。
