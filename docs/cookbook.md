# Cookbook

本页只放常见任务流程。

* 参数细节看 `docs/cli.md`
* 配置键看 `docs/config.md`
* 输出字段看 `docs/outputs.md`
* 项目能力边界看 `docs/capabilities.md`

## 1. 首次跑通

### 1.1 准备环境

推荐使用 `uv`：

```bash
uv venv --seed
uv sync --extra dev
```

如需 `RQData`：

```bash
uv sync --extra dev --extra rqdata
```

如需导出内置模板：

```bash
csml init-config --market default --out config/
```

同时准备对应 provider 的鉴权变量：

* `tushare`：`TUSHARE_TOKEN`
* `rqdata`：`RQDATA_USERNAME` + `RQDATA_PASSWORD`
* `eodhd`：`EODHD_API_TOKEN`

### 1.2 跑一次最小流程

```bash
csml run --config default
```

第一次跑完后，先看：

1. `summary.json`
2. `config.used.yml`
3. `positions_current.csv`

如果你已经要做 PIT 港股研究，再切到：

```bash
csml run --config hk
```

## 2. 横向比较多次 run

```bash
csml summarize \
  --runs-dir artifacts/runs \
  --output artifacts/runs/runs_summary.csv
```

如果你需要先看全量结果：

```bash
csml summarize \
  --runs-dir artifacts/runs \
  --sort-by score
```

如果你需要先排掉短样本、高换手和相对日期 run：

```bash
csml summarize \
  --runs-dir artifacts/runs \
  --exclude-flag-short-sample \
  --exclude-flag-high-turnover \
  --exclude-flag-relative-end-date \
  --sort-by score
```

如果输出 `No runs matched current summarize filters.`，先去掉全部 `--exclude-flag-*` 看全量结果。

## 3. 生成 live 快照

仓库里没有内置的 `config/hk_live.yml`。通常做法是单独准备一份 live 配置，例如 `config/hk_live.local.yml`。

常见最小改法：

```yaml
data:
  end_date: "t-1"

eval:
  output_dir: "artifacts/live_runs"
  save_artifacts: true

backtest:
  enabled: false

live:
  enabled: true
  as_of: "t-1"
  train_mode: "full"
```

然后执行：

```bash
csml snapshot --config config/hk_live.local.yml
csml snapshot --config config/hk_live.local.yml --skip-run --format json
```

## 4. 做本地快照和目录整理

需要归档一轮研究时：

```bash
csml backup-data \
  --name hk_frozen_20251231 \
  --config config/hk_selected__baseline.yml
```

如果你是从旧版本目录升级过来，本地还保留旧布局：

```bash
csml migrate-artifacts --dry-run
csml migrate-artifacts
```

## 5. 常见场景入口

### HK selected 多模型研究

这条路线单独放到：

* `docs/playbooks/hk-selected.md`

### 查 provider 差异

先看：

* `docs/providers.md`

### 想看 run 里到底写出了什么

先看：

* `docs/outputs.md`
