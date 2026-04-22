# HK selected 研究路线

本页解决什么：在 HK selected 路线上选择频率、数据路线和比较顺序。  
本页不解决什么：不展开参数定义、资产整备细节或专题研究流水账。  
适合谁：准备开始 HK selected 研究，或准备把现有实验收口成稳定路线的人。  
读完你会得到什么：一条按当前仓库模板和最新研究结论整理过的可执行路线图。  
相关页面：`docs/playbooks/README.md`、`docs/playbooks/hk-data-assets.md`、`docs/playbooks/research-template-design.md`、`docs/concepts/pit-coverage.md`、`docs/concepts/benchmark-protocol.md`、`docs/research/notes/hk-monthly-current-state-20260330.md`、`docs/research/notes/hk-monthly-time-window-design-20260330.md`、`docs/research/notes/hk-monthly-industry-treatment-20260404.md`、`docs/research/notes/hk-quarterly-current-state-20260329.md`、`docs/cli.md`、`docs/config.md`

页面性质：`current-state`  
最后核对时间：`2026-03-31`  
权威来源：当前 `configs/` 模板、相关研究笔记和 benchmark protocol  
冲突优先级：如果与具体 run 的 `config.used.yml` 冲突，以 run 产物为准；如果与当前 benchmark protocol 冲突，以协议页为准

本页按当前 `configs/` 模板、`docs/` 文档分工和截至 `2026-03-31` 的仓库内研究结论整理。  
历史 run 里仍然保留了旧口径；复现旧结果时，请先看 `config.used.yml`。

任务摘要：先选频率，再选数据路线；`fundamentals.source=file` 的 PIT 路线先做覆盖率体检；季度正式 benchmark 按 `price-only -> pit-core -> pit-core-hybrid` 递进；模型比较只在同一个研究单元里进行。

## 1. 先看结论

如果你只想先知道该从哪里开始，按下面这张表选入口：

| 你的目标 | 建议起点 | 原因 |
| --- | --- | --- |
| 第一次跑 HK selected，先熟悉命令和主流程 | 本地 HK assets 已就绪时，用月度 `M` + `tr_close` + balanced execution 本地 variant；否则先用 `configs/experiments/baseline/hk_selected.yml` | 当前推荐入口更贴近本地研究口径；旧 baseline 继续保留为低依赖对照和历史锚点 |
| 做正式的财报驱动研究 | 季度 `Q` + PIT 财务 | 这是当前官方 benchmark protocol 的主线 |
| 想做低频调仓，但暂时没有本地 PIT 文件 | 季度 `Q` + provider 基本面对照 | 可以先验证低频估值和慢量价，再决定是否进 PIT |
| 想探索年度 `Y` | 先把季度路线跑稳，再从季度配置派生 | 代码支持，模板和经验都更依赖季度主线 |
| 想做 `provider valuation overlay` | 先把季度 `pit-core-hybrid` 主线跑稳，再进入专题研究页 | 这条线已升级为进阶路线，不再是默认 benchmark 主线 |

先记住两条最新状态：

* 当前官方季度 PIT preset 和 benchmark 配置已经默认 `features.missing.add_indicators: false`。
* `provider_overlay` 现在是一条单独维护的进阶季度路线；主线入口仍然是 `price-only / pit-core / pit-core-hybrid`。

阅读导航：

* 路线总览看 [README.md](./README.md)
* PIT 资产准备看 [hk-data-assets.md](./hk-data-assets.md)
* 配置派生和模板边界看 [research-template-design.md](./research-template-design.md)
* PIT 体检怎么解读看 `docs/concepts/pit-coverage.md`
* benchmark 阶梯定义看 `docs/concepts/benchmark-protocol.md`
* overlay 路线现行口径先看 `docs/research/notes/hk-quarterly-current-state-20260329.md`

## 2. 主线流程

HK selected 主线研究，按下面 8 步推进最稳妥：

1. 先选频率：`M` / `Q` / `Y`
2. 再选数据路线：`纯量价` / `量价 + provider 基本面` / `量价 + PIT 财务`
3. 如果配置里用了 `fundamentals.source=file`，先准备 `pipeline_fundamentals.parquet`
4. 如果走季度 PIT 路线，先跑 `inspect-hk-pit-coverage`
5. 固定同一研究单元后，先跑特征 benchmark，再做模型比较
6. 对候选模型先跑固定分数组合层比较，不要把模型输出和仓位构建混在一起解释
7. 候选要替换主线前，先过 promotion gate：可比性、walk-forward、final OOS、成本换手和 benchmark evidence 都要齐
8. `provider_overlay`、抗漂移和更细的验证，放到主线稳定之后再展开

这里的“研究单元”至少包含这几件事：

* 频率
* 数据路线
* 股票池口径
* 是否依赖本地 PIT 文件

只要这些边界没变，你大多还在同一个研究单元里。  
同一研究单元里可以换模型、调参数、删少量字段；跨出这个单元，就已经是在比较整条研究路线。

## 3. 研究矩阵

这张表只回答“当前仓库里，你应该从哪一格开始”。  
表里写“需要本地派生”的格子，表示代码支持，但没有单独维护成官方 benchmark 模板。

| 频率 | 纯量价 | 量价 + provider 基本面 | 量价 + PIT 财务 |
| --- | --- | --- | --- |
| 月度 `M` | 需要本地派生。可从 `configs/experiments/baseline/hk_selected.yml` 或 `configs/experiments/variants/hk_selected__xgb_regressor.yml` 关闭 `fundamentals` 开始。 | 当前本地研究推荐入口是 `configs/experiments/variants/hk_selected__tr_close_execution_balanced_local.yml`。`configs/experiments/baseline/hk_selected.yml` 和四个显式模型模板继续保留，分别服务历史 benchmark 对照和模型 PK。 | 需要本地派生；当前没有单独维护的月度 PIT benchmark 模板。 |
| 季度 `Q` | 官方 benchmark 起点：`configs/experiments/baseline/hk_selected__quarterly_price_only.yml`。 | 需要本地派生；当前没有单独维护的季度 provider benchmark 模板。 | 官方 benchmark 主线：`configs/experiments/baseline/hk_selected__quarterly_pit_core.yml`、`configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml`，以及同一 hybrid 单元上的 challenger 模板。 |
| 年度 `Y` | 代码支持，当前没有内置模板。建议从月度或季度配置派生。 | 代码支持，当前没有内置模板。建议从季度 provider 路线派生。 | 代码支持，当前没有内置模板。建议从季度 PIT 路线派生。 |

读表时记住两条规则：

* 模型比较只在同一格里换模型。
* 跨格比较时，你比较的是频率、数据维度和样本口径一起变化后的整条路线。

## 4. 月度 `M` 路线

月度路线适合日常基线、模型横向比较和更快的研究反馈。

| 数据路线 | 起点配置 | 本地资产要求 | 更适合回答的问题 |
| --- | --- | --- | --- |
| 纯量价 | 从 `configs/experiments/baseline/hk_selected.yml` 或 `configs/experiments/variants/hk_selected__xgb_regressor.yml` 派生，设 `fundamentals.enabled=false` | 否 | 技术面和量价特征本身有没有稳定信号 |
| 量价 + provider 基本面 | 本地 HK assets 已就绪时，优先用 `configs/experiments/variants/hk_selected__tr_close_execution_balanced_local.yml`；需要低依赖或历史对照时，再用 `configs/experiments/baseline/hk_selected.yml` 及其显式模型模板 | 推荐入口需要本地 HK daily / instruments / ex_factors，以及本地 asof fundamentals 文件；baseline 对照不需要 | 日常本地研究、四模型 PK、估值与技术面的混合效果 |
| 量价 + PIT 财务 | 需要本地派生 | 是 | 保留月度调仓，同时把真实财报字段并入模型后会发生什么 |

月度路线当前最适合做两件事：

* 快速跑通完整流程
* 在同一路线里直接比较四种模型

原因也很直接：

* 内置模板最完整
* 样本点更多
* 结果回看和参数调整更高频

当前把月度入口分成两个角色更清楚：

* `configs/experiments/variants/hk_selected__tr_close_execution_balanced_local.yml`：当前本地研究推荐入口，适合直接进入更合理的价格和执行近似口径；主 benchmark 默认改用 `hk_selected_pit_research` 的 cap-weight 文件，避免 local daily snapshot 缺 `02800.HK` 时 benchmark / active 摘要中断；同一条 run 还会默认附带 `3432 + 02800 + hk_selected equal-weight + hk_selected cap-weight + hk_connect_full cap-weight` 的报告层对比。
* `configs/experiments/baseline/hk_selected.yml`：历史 benchmark 锚点，也是低依赖的回退入口。

如果你现在的目标只是“先把四种模型都跑一遍看看差距”，月度 `M` + provider 基本面仍然是最顺手的入口；但那更接近模型 PK 入口，不再是默认研究口径入口。

如果你已经确认要做“财报驱动 + 月频”的 PIT / hybrid 研究，而且开始担心行业异质性，不要直接把样本切成很多行业模型；先看 `docs/research/notes/hk-monthly-industry-treatment-20260404.md` 里的“观察 -> 约束 -> 金融剔除/单列 -> 最后才拆模型”顺序。

### 4.1 Monthly Time-Split Policy

这节只定义当前 monthly 主线的正式时间口径。  
完整推导、资产边界核对和 probe 历史，继续看 `docs/research/notes/hk-monthly-time-window-design-20260330.md` 与 `docs/research/notes/hk-monthly-current-state-20260330.md`。

先分清楚三件事：

* monthly 研究边界优先由 `research_universe.by_date_file` 决定，不是 raw daily 或 PIT 文件的最早日期。
* 在当前港股通 PIT monthly 研究池里，可用 rebalance dates 是 `2015-01-30 -> 2026-03-27`，共 `135` 个。
* 在 `label.horizon_mode=next_rebalance + shift_days=1` 下，最新完整可标注的 monthly 点是 `2026-01-30`，不是 `2026-03-27`。

当前现行 monthly 主线口径写成：

* `data.end_date=20260327`
* `eval.test_size=0.5`
* `eval.final_oos.size=24`

按当前这套口径解读 latest monthly PIT mainline 时，应优先认下面这组窗口：

* `50` 个 `main train` dates
* `52` 个 `main test` dates
* `24` 个 `final OOS` dates

它对应的是当前 latest fixed-window monthly 研究入口，而不是所有历史 run 的统一事实。  
如果某次具体 run 的 `summary.json` / `config.used.yml` 与这里冲突，以 run 产物为准。

这三段各自回答的问题不同：

* `main train`：主训练段，用来拟合模型。
* `main test`：主比较段，用来比较模型、特征 recipe 和构造变体；它是 in-sample 里的尾段，不是最终 holdout。
* `final_oos`：最后 `24` 个 monthly dates 的保留 holdout；pipeline 会先用全部剩余 in-sample 重训 final model，再评估这段 holdout。
* `walk_forward`：稳定性检查，不替代 `main test`，也不替代 `final_oos`。

当前默认判断也一并固定下来：

* `2015` 起的完整 monthly 样本池仍是默认主线。
* `30m final OOS` 更适合当 stress sidecar。
* `2016-12-05` / `2017+` modern-only 窗口更适合当 robustness sidecar，不适合直接替换默认主线。
* 对月频来说，约 `2` 年 `final_oos` 够做候选筛选，不够当“长期稳健性已充分验证”的最终证据。

如果你要把某个 monthly challenger 升成新主线，建议额外跑：

```bash
cstree construction-grid \
  --config configs/experiments/sweeps/hk_selected__research_protocol_construction_grid.yml

cstree feature-evidence summarize-ablation \
  --config configs/experiments/sweeps/hk_selected__research_protocol_feature_evidence.yml

cstree benchmark-ladder \
  --config configs/experiments/sweeps/hk_selected__research_protocol_benchmark_ladder.yml

cstree promotion-gate \
  --config configs/experiments/sweeps/hk_selected__research_protocol_promotion_gate.yml \
  --baseline-run artifacts/runs/<baseline_run_dir> \
  --candidate-run artifacts/runs/<candidate_run_dir>
```

这些命令的目标不是再造一个模型，而是把 RF 项目里更硬的研究协议迁移过来：固定 OOS / final holdout、成本换手前置、分数到仓位独立比较、利润导向特征证据和 benchmark ladder。

为避免混淆，再单独记一条：

* `configs/experiments/baseline/hk_selected.yml` 仍保留历史月频 baseline 口径，用于低依赖对照和旧 run 复现；它不是当前这套 monthly time-split policy 的权威来源。

最直接的起跑方式是：

```bash
# 当前推荐的 HK selected 月频本地研究入口
cstree run --config configs/experiments/variants/hk_selected__tr_close_execution_balanced_local.yml

# walk-forward 稳定性诊断 sidecar
cstree run --config configs/experiments/variants/hk_selected__tr_close_execution_balanced_wf_diag_local.yml

# 历史 benchmark 锚点 / 低依赖对照
cstree run --config configs/experiments/baseline/hk_selected.yml
```

## 5. 季度 `Q` 路线

季度路线适合低频调仓和正式的财报驱动研究。

这里先固定两个判断：

* 季度路线仍然读取日线行情；变化的是 `label`、`eval` 和 `backtest` 的 rebalance 频率。
* 当前官方 HK selected benchmark protocol 的主线，是季度 `price-only -> pit-core -> pit-core-hybrid`。

| 数据路线 | 起点配置 | 是否需要本地 PIT 文件 | 更适合回答的问题 |
| --- | --- | --- | --- |
| 纯量价 | `configs/experiments/baseline/hk_selected__quarterly_price_only.yml` | 否 | 低频调仓下，慢量价特征本身有没有方向 |
| 量价 + provider 基本面 | 需要本地派生；可从 `configs/experiments/baseline/hk_selected.yml` 切到 `Q`，再对齐低频相关配置 | 否 | 低频估值字段本身有没有信息量；和慢量价放在一起是否值得继续 |
| 量价 + PIT 财务 | `configs/experiments/baseline/hk_selected__quarterly_pit_core.yml`、`configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml`，以及同一 hybrid 单元上的 challenger 模板 | 是 | 财报披露节奏对齐后，core PIT 和慢量价能不能提供可解释的 alpha |

### 5.1 季度 PIT 的官方流程

如果你的目标是正式做财报驱动研究，推荐按下面顺序走：

1. 准备 `pipeline_fundamentals.parquet`
2. 运行 `cstree rqdata inspect-hk-pit-coverage`
3. 先看 `Fill Dependence`、`Worst Features`、`Complete Case`
4. 覆盖率达标后，按顺序跑三条基线：
   `quarterly_price_only -> quarterly_pit_core -> quarterly_pit_core_hybrid`
5. 固定 `pit-core-hybrid` 研究单元后，再比较模型

这条流程的目标很明确：

* 先确认数据能不能支撑研究
* 再确认 PIT 特征有没有增量
* 最后才回答“哪种模型更合适”

这里的 `core PIT`，指的是覆盖率较高的财务主项和少量稳健派生项。  
低覆盖字段、更宽的字段池和专题路线，放到主线稳定之后再加。

### 5.2 季度 PIT 的当前模板状态

截至 `2026-03-28`，这里有 3 条需要明确写清楚：

* 当前官方季度 preset `configs/presets/hk_quarterly_pit_hybrid.yml` 已经默认 `features.missing.add_indicators: false`。
* 当前三条官方季度 benchmark 配置都建立在这个 preset 之上。
* 仓库里仍能看到带 `*_missing` 列的历史 run；那是旧口径或旧本地配置，不是当前默认模板。

所以，读季度 PIT 结果时请先区分两件事：

* 当前官方模板怎么定义
* 某个历史 run 当时实际用了什么口径

最稳妥的核对方式仍然是先读该 run 的 `config.used.yml`。

### 5.3 覆盖率体检怎么过关

体检命令：

```bash
cstree rqdata inspect-hk-pit-coverage \
  --config configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml \
  --mode both
```

看 `Fill Dependence` 时，按下面这套门槛判断：

* `core PIT`：`retention_ratio_after_ffill >= 0.60` 为绿灯，`0.30-0.59` 为黄灯，`< 0.30` 为红灯
* `core_hybrid`：`retention_ratio_after_ffill >= 0.40` 为绿灯，`0.15-0.39` 为黄灯，`< 0.15` 为红灯
* `periods_after_missing_fill=0`：直接按红灯处理

对应动作：

* 红灯：停止跑模型，先改字段集、股票池或 PIT 资产
* 黄灯：先看 `Worst Features`，优先删掉最拖后腿的一两个字段，再重跑体检
* 绿灯：可以继续跑三条基线和模型 challenger

### 5.4 季度 PIT 的官方 benchmark 与 challenger

当前官方季度 benchmark protocol 的入口已经收口到下面这些配置：

* `configs/experiments/baseline/hk_selected__quarterly_price_only.yml`
* `configs/experiments/baseline/hk_selected__quarterly_pit_core.yml`
* `configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml`
* `configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_ridge.yml`
* `configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_xgb_ranker.yml`
* `configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_elasticnet.yml`

当前协议里的角色分工是：

* `xgb_regressor`：强 benchmark，也是默认要被超越的对象
* `xgb_ranker`：primary challenger，回答“换成排序目标后会不会更好”
* `ridge`：线性 sanity benchmark
* `elasticnet`：稀疏线性 challenger

这套分工和“某次局部实验里哪种模型分数更高”是两回事。  
如果你在旧笔记或历史 run 里看到 `xgb_ranker` 某次赢了 `xgb_regressor`，请把它理解成特定研究单元下的一次结果，不要自动外推成全局默认。

## 6. 年度 `Y` 路线

代码层已经支持年度频率，但当前没有单独维护的年度模板。

更稳妥的做法是：

1. 先从季度路线选一份最接近你的配置
2. 把 `label.rebalance_frequency`、`eval.rebalance_frequency`、`backtest.rebalance_frequency` 一起改成 `Y`
3. 同步下调 `eval.n_splits` 和 `eval.walk_forward.n_windows`
4. 起步时优先使用线性模型或较浅的树模型

年度路线更适合这类问题：

* 你只关心很慢的财报信号
* 你接受更少的训练窗口
* 你准备先做探索，再决定是否长期维护这条线

## 7. 四模型比较怎么做

四模型比较放在流程后段，结论会更稳定，也更容易解释。

推荐顺序：

1. 先固定研究单元
2. 先跑完特征 benchmark
3. 再只换 `model` 和 `eval.run_name`
4. 用同一批 run 统一 `summarize`

对标准季度 PIT 主线，最直接的执行方式就是：

```bash
# 特征 benchmark
cstree run --config configs/experiments/baseline/hk_selected__quarterly_price_only.yml
cstree run --config configs/experiments/baseline/hk_selected__quarterly_pit_core.yml
cstree run --config configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml

# 同一 hybrid 单元上的模型 challenger
cstree run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_ridge.yml
cstree run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_xgb_ranker.yml
cstree run --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_elasticnet.yml

cstree summarize \
  --runs-dir artifacts/runs \
  --run-name-prefix hk_sel_q_benchmark_ \
  --sort-by score
```

这里最重要的控制变量是：

* `universe`
* `fundamentals`
* `features`
* `label`
* `eval`
* `backtest`

如果这些块一起变了，你比较的就不再是模型，而是整条研究路线。  
如果你还要继续细化线性模型，再单独用 `cstree sweep-linear` 做后续搜索。

## 8. 什么时候必须准备 PIT 财务文件

判断规则很简单：

* `fundamentals.source=provider`：不需要本地 PIT 文件
* `fundamentals.enabled=false`：不需要本地 PIT 文件
* `fundamentals.source=file`：需要本地 PIT 文件

最短准备流程：

```bash
cstree rqdata mirror-hk-pit-financials \
  --config configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml \
  --name hk_selected_pit_2011_2025_latest \
  --fields-file configs/field_profiles/hk_financial_fields_starter.txt \
  --start-quarter 2011q1 \
  --end-quarter 2025q4 \
  --date 20260312

cstree rqdata build-hk-pit-fundamentals \
  --asset-dir artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest \
  --out artifacts/assets/rqdata/hk/pit_financials/hk_selected_pit_2011_2025_latest/pipeline_fundamentals.parquet \
  --source-universe-by-date artifacts/assets/universe/hk_connect_full_by_date.csv \
  --universe-by-date-out artifacts/assets/universe/hk_selected_pit_research_by_date.csv \
  --max-latest-report-age-days 365

cstree rqdata inspect-hk-pit-coverage \
  --config configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml \
  --mode both
```

更完整的资产准备顺序，看 [hk-data-assets.md](./hk-data-assets.md)。

## 9. 进阶路线：`provider valuation overlay`

`provider valuation overlay` 现在是一条单独维护的季度进阶路线。

它的定义是：

* 主基本面继续走 `fundamentals.source=file` 的稀疏 PIT 财报
* 日频估值通过 `fundamentals.provider_overlay` 按 `trade_date + symbol` 直接并到 daily panel

这条线的主入口是：

* `configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_overlay_xgb_ranker.yml`

当前使用方式有 3 条原则：

* 先把官方 `quarterly_pit_core_hybrid` 主线跑稳，再进入 overlay
* 日频估值直接走 `provider_overlay`；不要把它写回稀疏 PIT 文件后再解释结果
* 现行专题结论和研究边界先看 `docs/research/notes/hk-quarterly-current-state-20260329.md`

截至 `2026-03-28`，这条线的状态是：

* 旧 overlay 基线已经在 `final_oos` 暴露出 regime shift
* 当前仓库里有单独维护的抗漂移验证配置
* 这条线适合当专题研究和 canary 准备路线，不适合重新写回 HK selected 主线 benchmark

如果你要审计 overlay 合并链路，可以在 run 完成后执行：

```bash
uv run python -m csml.research.hk_selected_provider_valuation_audit \
  --run-dir artifacts/runs/<run_dir>
```

## 10. 几个容易混淆的点

先把下面这些点记住，很多阅读和复现问题都会少很多：

* 仓库只把核心研究单元维护成官方模板；研究矩阵里其余格子需要本地派生
* 季度和年度路线仍然读取日线行情；低频设定改的是标签、评估和回测的 rebalance 频率
* `research_universe.by_date_file` 控制的是某只股票在哪些日期能进入研究样本；本地日线和 PIT 资产控制的是你保留了多长历史
* 模型比较必须固定在同一个研究单元里；跨格比较属于路线比较
* 历史 run 和当前模板不是同一个概念；读旧结果时先看 `config.used.yml`

## 11. 结果先看什么

跑完之后，优先按这个顺序读产出：

1. `summary.json`
2. `config.used.yml`
3. `runs_summary.csv`
4. `positions_current.csv`

重点看这些指标：

* `ic_mean`
* `long_short`
* `backtest_sharpe`
* `backtest_max_drawdown`
* `backtest_avg_turnover`
* `flag_*`

如果你在看季度或年度低频 run，再额外叠加下面几项：

* `walk_forward` 的方向是否稳定
* `positions_current.csv` 是否过度集中到低流动性个股
* `inspect-hk-pit-coverage` 里的 `Complete Case`、`Fill Dependence` 和 `Recent Quarters` 是否还支持当前字段组合

如果最终结论和你的预期差很多，先不要急着换模型。  
先回到 `config.used.yml`、覆盖率体检和研究单元边界，确认你比较的到底是不是同一件事。
