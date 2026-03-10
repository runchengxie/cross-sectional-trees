# cross-sectional-machine-learning

使用 TuShare / RQData / EODHD 日线数据做截面因子研究与评估。项目支持 `xgb_regressor`、`xgb_ranker`、`ridge`、`elasticnet`，输出 IC、分位数组合收益、回测结果、换手估计和持仓快照。

默认产物写入 `out/runs/<run_name>_<timestamp>_<hash>/`。

## 适用范围

* 低频研究与复现实验。
* Long-only 组合评估与目标持仓快照。
* A 股、港股、美股的多市场配置切换。

当前不覆盖券商接入、自动下单、成交回执和账户级风控。

## 快速开始

推荐环境：Python 3.12+，`uv`。

```bash
uv venv --seed
uv sync
cp .env.example .env
csml run --config config/hk.yml
```

如果你准备用 `RQData`：

```bash
uv sync --extra rqdata
```

最小鉴权取决于 `data.provider`：

* `tushare`：`TUSHARE_TOKEN`
* `rqdata`：`RQDATA_USERNAME` + `RQDATA_PASSWORD`
* `eodhd`：`EODHD_API_TOKEN`

首次运行后，先看这三个文件：

* `summary.json`
* `config.used.yml`
* `positions_current.csv`

## 常用命令

```bash
# 主流程
csml run --config config/hk.yml

# 导出内置模板
csml init-config --market hk --out config/

# 跨历史 run 汇总
csml summarize --runs-dir out/runs --output out/runs/runs_summary.csv

# 查询 RQData 配额
csml rqdata quota --pretty

# 读取当前持仓
csml holdings --config config/hk.yml --as-of t-1

# 一键生成 live 快照
csml snapshot --config config/hk_live.yml
```

完整命令和参数说明见 `docs/cli.md`。

## 文档导航

文档首页：`docs/README.md`

按主题阅读：

* 上手与研究流程：`docs/README.md`、`docs/cookbook.md`
* 配置与数据源：`docs/config.md`、`docs/providers.md`
* 指标与输出：`docs/metrics.md`、`docs/outputs.md`
* 排错：`docs/troubleshooting.md`
* 开发与测试：`docs/dev.md`

## 复现建议

* 固定 `data.start_date/end_date`，避免 `today`、`t-1`、`now`。
* 保留 `cache/`、`config.used.yml`、`summary.json` 和 git commit。
* 多数据源切换时，同时记录 `data.provider` 与 provider 专属参数。

## 说明

`README` 为项目总览和最短路径。详细信息如CLI 参数、配置细节、输出字段和故障排查统一放在 `docs/` 中维护。
