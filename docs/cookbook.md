# Cookbook

本页只放常见任务流程。

* 参数细节看 `docs/cli.md`
* 配置键看 `docs/config.md`
* 输出字段看 `docs/outputs.md`
* 项目能力边界看 `docs/capabilities.md`

## 1. 先记住研究顺序

开始任何一轮研究前，先把顺序定住：

1. 先固定研究单元。
2. 先验收数据，再决定要不要继续。
3. 先把 PIT 覆盖率体检跑到可接受状态，再进入基线。
4. 先跑基线，再比较模型，再调参数。

这里的研究单元通常指：

* `market`
* `universe`
* `fundamentals`
* `features`
* `label`
* `backtest`

做横向比较时，优先只改：

* `model`
* `eval.run_name`

如果你需要派生很多本地实验配置，优先放到 `config/local/`。这类文件默认只服务当前机器上的研究流程。

## 2. 首次跑通

### 2.1 准备环境

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

### 2.2 跑一次最小流程

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

补充：

* `csml run --config default` 里的 `default` 是内置别名，不等于仓库里的 `config/default.yml`。

## 3. 做 HK selected 研究

HK selected 的研究流程建议按下面的顺序走：

1. 先选频率。
2. 再确认数据路线。
3. 先过覆盖率体检，再决定要不要比较模型和调参。

如果你只是想确认主流程能跑，继续用月度 provider 基线就够了。  
如果你要研究财报驱动信号，默认从季度 `Q` 开始。年度 `Y` 先放在探索阶段。

路线入口在：

* `docs/playbooks/README.md`
* `docs/playbooks/hk-selected.md`

### 3.1 季度 PIT 研究的默认流程

季度 PIT 路线当前更适合作为正式研究起点。原因很简单：

* PIT 财务只在披露日更新。
* 日线行情仍然有用，但更适合作为慢量价特征。
* 季度频率在信息更新节奏、样本量和解释性之间更稳。

推荐流程：

1. 准备 PIT 资产，生成本地 `pipeline_fundamentals.parquet`。
2. 先做 PIT 覆盖率体检。
3. 如果覆盖率不够，先改字段集、股票池或资产准备流程。
4. 先把 `Fill Dependence` 调到黄灯或绿灯。正式比较前，优先到绿灯。
5. 先跑三条基线：`季度纯量价`、`季度 core PIT`、`季度 core PIT + 慢量价`。
6. 只有在三条基线都稳定后，再做四模型 PK 或线性模型 sweep。

这里的 `core PIT` 指高覆盖财务主项和少量稳健派生项。低覆盖字段先不要放进起步配置。

下面的命令示例默认你已经按这条流程在 `config/local/` 派生了本地配置。  
如果你还没有本地季度配置，先从仓库里的季度 PIT 模板复制一份，再按本文的步骤收窄。

体检命令：

```bash
csml rqdata inspect-hk-pit-coverage \
  --config config/local/hk_sel_pit_q_core_hybrid_xgb_reg.yml \
  --mode both
```

看输出时，先看这几项：

* `Pipeline Manifest -> dropped_all_missing_fields`
* `Complete Case -> complete_rows`
* `Complete Case -> quarter_count_meeting_min_symbols`
* `Worst Features`
* `Recent Quarters`

这几项分别回答：

* 源头 PIT 资产有没有大量全空行
* 当前特征组合能留下多少完整样本
* 每个季度能不能留下足够多的 symbol 做横截面训练
* 哪些字段最拖后腿
* 最近几个季度的研究口径是否可用

补充：

* 如果当前配置已经启用 `features.missing.method`，`Complete Case` 更接近 source-level 的严格口径。
* 这时它适合判断原始 PIT 资产有多稀，不等于“这份配置一定跑不动”。
* 真正要不要停下来，要和 `Worst Features`、`Recent Quarters`、以及你准备填补的字段一起看。
* 如果你要看“填补之后大概还能不能训练”，直接加 `--mode trainable` 或 `--mode both`。
* `trainable` / `both` 会多一段 `Fill Dependence`。重点看 `retention_ratio_after_ffill`。
* 计算方法是：`period_count_meeting_min_symbols_after_ffill / period_count_meeting_min_symbols_after_missing_fill`。
* `core PIT` 先按更严格的门槛看：`>= 0.60` 记为绿灯，`0.30-0.59` 记为黄灯，`< 0.30` 记为红灯。
* `core_hybrid` 可以稍微放宽：`>= 0.40` 记为绿灯，`0.15-0.39` 记为黄灯，`< 0.15` 记为红灯。
* 如果 `periods_after_missing_fill=0`，直接按红灯处理。先回到资产或特征集。
* 如果 `Worst Features` 里有一对字段总是一起拖后腿，比如某个原值和对应的 `growth_*` 派生项，优先成对处理，不要只删一个。

### 3.2 什么时候先停下来，不要继续调参

出现下面这些情况时，先不要急着换模型或细调参数：

* 在 strict 口径下，`quarter_count_meeting_min_symbols=0`，而且 `Worst Features` 也说明核心原始字段覆盖很差
* `Worst Features` 里低覆盖字段正好是当前核心特征
* `Pipeline Manifest` 里的 `dropped_all_missing_fields` 很高
* `Fill Dependence` 已经是红灯
* `季度纯量价`、`季度 core PIT`、`季度 core PIT + 慢量价` 三条基线还没有跑清楚

这时更应该先做：

* 重建或补全 PIT 资产
* 缩窄 PIT 字段集
* 把最拖后腿的一两个字段先拿掉
* 把体检命令跑到你真正准备比较的那份配置上

如果 `Fill Dependence` 是黄灯，下一步先做这几件事：

* 看 `Worst Features` 里是不是有一两个字段特别拖后腿
* 如果是原值 + `growth_*` 成对出现，优先一起处理
* 先删掉最拖后腿的一两个字段，再重跑体检
* 对 `core_hybrid` 额外确认 `季度纯量价` 基线已经跑清楚

### 3.3 三条基线比四模型 PK 更重要

这一步的目标是先回答“信号有没有增量信息”，再回答“哪个模型更好”。

推荐顺序：

1. `季度纯量价`
2. `季度 core PIT`
3. `季度 core PIT + 慢量价`
4. 四模型 PK

如果你已经在 `config/local/` 派生了本文建议的三条基线，直接按这个顺序跑：

```bash
csml run --config config/local/hk_sel_q_price_only_xgb_reg.yml
csml run --config config/local/hk_sel_pit_q_core_xgb_reg.yml
csml run --config config/local/hk_sel_pit_q_core_hybrid_xgb_reg.yml

csml summarize \
  --runs-dir artifacts/runs \
  --run-name-prefix hk_sel_q_baseline \
  --sort-by score
```

如果 `季度 core PIT + 慢量价` 没有明显优于 `季度纯量价`，先回头看 PIT 资产和特征口径。  
如果线性模型已经接近树模型，也先不要急着加复杂模型。

### 3.4 第四步再做四模型 PK

如果你已经跑完三条基线，第四步再做四模型 PK。

推荐继续沿用 `季度 core PIT + 慢量价` 那条线，只在同一研究单元里换模型。  
下面这组命令同样假设你已经在 `config/local/` 派生了四份 PK 配置：

```bash
csml run --config config/local/hk_sel_q_pk_pit_core_hybrid_xgb_reg.yml
csml run --config config/local/hk_sel_q_pk_pit_core_hybrid_xgb_rank.yml
csml run --config config/local/hk_sel_q_pk_pit_core_hybrid_ridge.yml
csml run --config config/local/hk_sel_q_pk_pit_core_hybrid_en.yml
```

汇总时直接用统一前缀：

```bash
csml summarize \
  --runs-dir artifacts/runs \
  --run-name-prefix hk_sel_q_pk_pit_core_hybrid \
  --sort-by score
```

## 4. 在同一研究单元里比较多次 run

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

如果你是在做模型 PK，再补两条检查：

* 先确认这些 run 的 `config.used.yml` 里 `universe`、`fundamentals`、`features`、`label`、`backtest` 没有漂移。
* 先确认退化 run 没混进来，例如 `flag_constant_prediction=true` 或 `flag_zero_feature_importance=true`。

## 5. 生成 live 快照

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

## 6. 从持仓到资金分配

如果你已经有当前持仓，想继续做等权手数分配：

```bash
csml alloc --config config/hk_live.local.yml --source live --top-n 20 --cash 1000000
```

如果你已经有现成的持仓 CSV：

```bash
csml alloc \
  --positions-file artifacts/runs/<run_dir>/positions_by_rebalance_live.csv \
  --top-n 10 \
  --cash 1000000
```

`alloc` 会直接用到 RQData 价格和 `round_lot`。如果你要长期复用这条流程，先看 `docs/cli.md` 和 `docs/providers.md` 里的相关说明。

## 7. 做本地快照和目录整理

需要归档一轮研究时：

```bash
csml backup-data \
  --name hk_frozen_20251231 \
  --config config/hk_selected__xgb_regressor.yml
```

如果你是从旧版本目录升级过来，本地还保留旧布局：

```bash
csml migrate-artifacts --dry-run
csml migrate-artifacts
```

## 8. 常见场景入口

### HK selected 多模型研究

这条路线单独放到：

* `docs/playbooks/README.md`

补充：

* `docs/playbooks/README.md` 会告诉你先看研究路线、资产准备还是模板设计原则。

### 查 provider 差异

先看：

* `docs/providers.md`

### 想看 run 里到底写出了什么

先看：

* `docs/outputs.md`
