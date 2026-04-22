# 配置参考

本文档的核心目标：提供配置键与默认行为的速查参考。
本文档的范围限制：仅涉及配置项说明，不展开探讨具体的研究路线与概念选择。
目标读者：需要查阅配置定义与模板参考的开发者或研究员。
阅读收益：能够快速掌握配置键的权威定义，并定位常用模板的入口。
相关页面：`docs/concepts/model-selection.md`、`docs/concepts/pit-coverage.md`、`docs/concepts/universe-modes.md`、`docs/concepts/data-sources.md`、`docs/concepts/execution-costs.md`

## 常用模板速查

| 使用场景 | 推荐模板 | 关键改动说明 |
|------|---------|---------|
| 首次跑通主流程 | `default` | 无特殊改动 |
| 港股月频 Starter 模板（结合 PIT 股票池与 provider 基本面） | `hk` | 默认读取港股通研究股票池，不强制要求提供本地 PIT 基本面文件 |
| HK selected 月频本地研究推荐入口 | `configs/experiments/variants/hk_selected__tr_close_execution_balanced_local.yml` | 依赖本地 HK 资产数据。一次性贯通 `tr_close`、balanced execution 以及本地 RQData 资产链路 |
| HK selected 月频历史 benchmark 锚点 | `configs/experiments/baseline/hk_selected.yml` | 保留 `close` 结合固定 `25bps` 成本的旧口径，以便与历史结果进行横向对照 |
| 港股季频 PIT 正式研究 | `configs/presets/hk_quarterly_pit_hybrid.yml` | 依赖本地 `pipeline_fundamentals.parquet` 文件 |
| 季度 benchmark 协议配置 | `configs/experiments/baseline/hk_selected__quarterly_*.yml` 配合 `configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_*.yml` | 依赖本地 `pipeline_fundamentals.parquet` 文件 |
| 拓展的季度实验路线 | `configs/experiments/variants/hk_selected__pit_quarterly_*` | 适合在此基础上进一步派生专题研究路线 |
| 本地独立实验 | `configs/local/*.yml`（个人自建目录，默认不纳入版本控制）或任意自建实验目录 | 仅作个人本地派生使用，不作为官方基线入口 |

> 注意：在命令 `cstree run --config default` 中，`default` 为内置别名。所有的内置别名以及 `cstree init-config` 命令均会读取仓库根目录下的 `configs/` 文件夹。其默认的适用场景为源码检出（checkout）环境，或包含了 `configs/` 文件夹的导出源码目录，不适用于脱离仓库上下文的独立运行环境。

### `PIT` 在本仓库中的多重语义

为避免混淆，需注意 `PIT`（Point-in-Time）在本仓库中可能代表以下三种语义层面：

1. PIT universe（股票池）：反映按日期动态变化的股票池成员关系，通常通过 `research_universe.by_date_file` 配置项体现。
2. PIT fundamentals（基本面）：指代严格按历史披露节奏对齐的本地财务平面文件，通常通过 `fundamentals.source=file` 配合 `pipeline_fundamentals.parquet` 配置项体现。
3. 季度 PIT 研究路线：在同一研究单元内，将季度（`Q`）频率、PIT 财务特征与 benchmark 协议组合而成的一条完整的正式研究工作流。

当本文档提及 `hk.yml` 模板时，默认指代包含了部分基础设定的 HK Starter 配置，请勿将其自动等同于“完整的季度 PIT 基本面研究路线”。

---

## 配置目录结构

```text
configs/
├── presets/           # 内置预设（各市场默认配置模板）
│   ├── default.yml
│   ├── hk.yml
│   └── universe/      # 股票池专用配置
├── experiments/       # 研究实验配置集合
│   ├── baseline/      # 基线模型配置
│   ├── variants/      # 模型变体与拓展配置
│   └── sweeps/        # 批量自动实验（Sweep）配置
└── local/             # 本地覆盖与测试目录（用于个人派生，默认不纳入版本控制）
```

## 顶层配置块概览

| 模块名称 | 核心作用 | 常见配置键 |
|----|------|--------|
| `market` | 定义目标市场 | `hk` |
| `paths` | 指定产物根目录及 metadata/warehouse 默认路径 | `artifacts_root`, `metadata_db_path`, `warehouse_db_path` |
| `data` | 配置数据源、日期范围及缓存标记 | `provider`, `start_date`, `end_date`, `cache_tag` |
| `research_universe` | 定义研究股票池规则 | `mode`, `by_date_file`, `symbols` |
| `fundamentals` | 配置基本面数据行为 | `enabled`, `source`, `features` |
| `label` | 定义模型预测标签与周期 | `target_col`, `horizon_days`, `rebalance_frequency`, `shift_days` |
| `features` | 声明特征列表与处理逻辑 | `list`, `windows`, `missing` |
| `model` | 配置算法模型及超参数 | `type`, `params` |
| `eval` | 设置模型评估与收益统计参数 | `top_k`, `transaction_cost_bps`, `save_artifacts`, `save_scored_artifact` |
| `backtest` | 配置历史回测参数 | `enabled`, `rebalance_frequency`, `top_k`, `weighting` |
| `live` | 配置实盘快照与执行前分析 | `enabled`, `as_of` |
| `logging` | 控制日志输出级别与落盘路径 | `level`, `file` |

## 关键配置详解

### `paths` 路径配置

默认情况下，系统将所有运行产物写入工作区内的 `artifacts/` 目录。若希望将数据存放与代码仓库分离管理，只需修改此处的根目录配置，而无需逐一修改各条研究链路的输入路径。

```yaml
paths:
  artifacts_root: "artifacts"
  metadata_db_path: null
  warehouse_db_path: null
```

补充说明：

* `paths.artifacts_root` 仅修改默认派生基础路径。若在配置文件中已明确指定了具体路径（如 `eval.output_dir`、`data.cache_dir`、`fundamentals.file`、`data.rqdata.daily_asset_dir` 等），这些显式路径将保持不变。
* 当 `metadata_db_path` 留空时，`cstree data catalog` 命令默认将数据写入 `<artifacts_root>/metadata/catalog.sqlite`。
* 当 `warehouse_db_path` 留空时，`cstree data query` 命令默认将数据写入 `<artifacts_root>/metadata/warehouse.duckdb`。
* 命令行参数 `--artifacts-root` 的优先级高于此处的 YAML 配置。
* 环境变量 `CSML_ARTIFACTS_ROOT`、`CSML_METADATA_DB_PATH`、`CSML_WAREHOUSE_DB_PATH` 也可用作全局的默认覆盖手段。

### 数据源配置 (`data`)

```yaml
data:
  provider: rqdata       # 当前仅支持 rqdata
  market: hk             # 当前仅支持 hk
  start_date: "20200101" # 支持具体日期或相对表达，如 "today", "t-1"
  end_date: "20241231"
  cache_tag: "experiment_a"  # 用于隔离不同实验的缓存版本
```

### 离线资产对齐 (`data.rqdata`)

若本地已备妥日线镜像与 instrument 资产快照，可配置 pipeline 直接读取本地资产目录，以避免重复调用远端数据接口：

```yaml
data:
  rqdata:
    daily_asset_dir: "artifacts/assets/rqdata/hk/daily/<snapshot>"
    instruments_file: "artifacts/assets/rqdata/hk/instruments/<snapshot>.parquet"
    ex_factors_dir: "artifacts/assets/rqdata/hk/ex_factors/<snapshot>"
```

补充说明：

* 若设定了 `data.price_col: tr_close`，并希望价格类特征、标签及回测流程统一采用总回报（Total Return）口径，强烈建议同步配置 `data.rqdata.ex_factors_dir`。
* 选用该配置时，系统会在读取日线数据后自动派生 `tr_close` 字段。原始的 `close` 字段仍将保留在数据集中，供对照参考或执行逻辑使用。
* 若通过 RQData 在线接口拉取数据，并显式配置了 `data.rqdata.adjust_type: pre/post`，系统同样支持将提供商返回的复权后价格别名映射为 `tr_close`。
* 当 `price_col=tr_close` 且已配置本地 `ex_factors_dir` 时，若发现部分股票缺少对应的复权因子数据，运行日志将抛出显式告警。同时，`summary.json -> data -> price_col_diagnostics` 中会详细记录具体的异常归类（如 `local_ex_factors`、`provider_adjusted_price`、`input_frame_missing_ex_factors` 抑或 `close_fallback_missing_ex_factors`）。

### 股票池配置 (`research_universe`)

```yaml
research_universe:
  mode: static           # 可选模式：auto / pit / static
  symbols:               # 适用于 static 模式的固定标的列表
    - 00700.HK
    - 09988.HK
  # 适用于 pit 模式的时间序列文件
  # by_date_file: artifacts/assets/universe/hk_connect_by_date.csv
```

补充说明：

* 历史配置键 `universe` 仍获向下兼容，但在新的内置模板与生成的 `config.used.yml` 中，将统一规范输出为 `research_universe`。

### 模型配置 (`model`)

```yaml
model:
  type: xgb_regressor   # 可选类型：xgb_regressor / xgb_ranker / ridge / elasticnet
  params:
    n_estimators: 100
    max_depth: 5
  sample_weight_mode: exp_decay  # 样本加权方式：none / date_equal / exp_decay
  sample_weight_params:
    halflife: 12
  train_window:
    mode: rolling                # 训练窗口模式：full / rolling
    size: 16
    unit: dates                  # 窗口单位：dates（自然交易日） / years（自然年）
```

详情请参阅 `docs/concepts/model-selection.md`。

### 评估与回测配置 (`eval` & `backtest`)

```yaml
eval:
  top_k: 20
  transaction_cost_bps: 15
  score_postprocess:
    method: neutralize
    columns: [log_mcap]
    strength: 0.5
    min_obs: 20
  save_artifacts: true
  save_scored_artifact: false

backtest:
  enabled: true
  rebalance_frequency: "M"   # 调仓频率：M（月频） / Q（季频） / Y（年频）
  top_k: 20
  weighting: equal           # 资金分配权重：equal（等权） / signal（基于信号加权）
  execution:
    entry_policy:
      price_col: open
    exit_policy:
      price: delay           # 退场缺价策略：strict / ffill / delay
      fallback: ffill        # 退场降级策略：ffill / none
      price_col: close
    cost_model:
      name: side_bps         # 成本计算模型：bps / side_bps / none
      buy_bps: 10
      sell_bps: 10
      short_entry_bps: 15
      short_exit_bps: 10
      short_borrow_bps_per_day: 0.5
    slippage_model:
      name: participation    # 滑点模型：none / bps / participation
      amount_col: adv20_amount
      base_bps: 2
      impact_bps: 20
      portfolio_value: 1000000
      power: 0.5
    constraints:
      min_price: 5
      min_amount: 1000000
      amount_col: adv20_amount
```

### 港股增强分配配置 (`live.alloc_hk`)

`cstree alloc-hk` 工具将优先读取当前持仓快照，随后在港股执行前分析层（liveops）开展资金与手数分配运算。命令行传入的参数优先级始终高于此处的 YAML 配置。

```yaml
live:
  alloc_hk:
    cash: 1000000
    method: custom                  # 分配逻辑：equal / custom
    require_stock_connect: true
    scenarios:
      capitals: [1000000, 500000]   # 可选。不配置时默认只运行单一资金场景
      top_ns: [20, 10]              # 可选。不配置时默认沿用 CLI 提供的 --top-n 参数
    valuation:
      history_years: 3
      roll_window: 252
      sell_quantile: 0.95
      extreme_quantile: 0.99
    secondary_fill:
      enabled: true
      avoid_high_valuation: true
      avoid_high_valuation_strict: false
      max_steps: 5000
      allow_over_alloc: false
      max_over_alloc_ratio: 0.0
      max_over_alloc_amount: 0.0
      max_over_alloc_lots_per_ticker: 1
      cash_buffer_ratio: 0.0
      cash_buffer_amount: 0.0
      estimated_fee_per_order: 0.0
```

补充说明：

* 若 `live.alloc_hk.scenarios.capitals` 与 `top_ns` 矩阵同时存在，程序会自动按“资金规模 × TopN”生成组合情景矩阵。
* 在命令行中显式提供 `--scenario-capital` 或 `--scenario-top-n` 参数时，将无条件覆盖上述配置。

### 质量闸门配置 (`quality`)

系统目前在主流程及 liveops 环节支持接入可选的质量闸门。当前版本重点针对“HK + RQData + `fundamentals.source=file`”构成的本地 PIT 场景进行约束。运行 `cstree run` 前会触发 `inspect-hk-pit-coverage` 健康度检测，其结论将同步沉淀至 `summary.json -> quality.preflight`。

```yaml
quality:
  fail_on_severity: warning   # 阻断阈值：none / info / warning / error
  save_report: true           # 是否将 preflight JSON 质检报告落盘至 <run_dir>/quality/
  pit_coverage_mode: strict   # 覆盖率评估口径：strict / trainable / both
  target_date: null           # 可选。默认沿用 by_date_file 的最新记录或 PIT 文件的最大 trade_date
  health_sample_limit: 5
```

补充说明：

* `fail_on_severity` 作为核心开关：设定为 `none` 时仅作日志留存，不阻断流程；设定为其他阈值时，一旦命中相应严重等级的错误，`cstree run`、`cstree snapshot` 或 `cstree alloc-hk` 将触发 fail-fast 机制立即报错退出。
* 当配置了 `save_report=true`，系统会将详细的质检报告保存在 `<run_dir>/quality/`。对于实盘或后置节点（liveops）来说，工具会优先复用 `summary.json` 中已有的检测结论，规避繁重的重复计算。
* 若在命令行尾缀 `--fail-on-quality ...` 参数，同样会覆盖此处的默认行为。

### 日志输出配置 (`logging`)

```yaml
logging:
  level: INFO
  # 当未显式声明 file 且 eval.save_artifacts=true 时，
  # 系统自动将运行日志写入 artifacts/runs/<run_dir>/run.log
  # file: artifacts/reports/my_run.log
```

## 高频核心键快速索引

### 数据集基础 (`data`)

| 键名 | 作用说明 | 常见配置值 |
|---|------|--------|
| `provider` | 数据供应商 | `rqdata` |
| `start_date` | 数据截取起点 | `20200101` 或 `today` |
| `end_date` | 数据截取终点 | `20241231`、`t-1` 或 `last_trading_day` |
| `cache_tag` | 缓存沙箱标签 | 任意字符串命名 |
| `price_col` | 统一作用于标签、回测、基准及价格衍生特征的价格标尺 | `close` 或 `tr_close` |

说明：

* `data.price_col` 的影响范围已全面拓宽。除了作用于最终收益结算与回测，它同时也约束了 `sma`、`rsi`、`macd`、`ret_*`、`rv_*` 等时序价格衍生特征的底层输入。
* 若需实施基于 `close` 与 `tr_close` 的 A/B 对比测试，仅需切换此单项配置即可实现全局同步联动。

### 研究股票池 (`universe`)

| 键名 | 作用说明 | 常见配置值 |
|---|------|--------|
| `mode` | 池子构建模式 | `static` / `pit` / `auto` |
| `by_date_file` | 指向包含 PIT 动态变更的参照文件 | CSV 格式的绝对或相对路径 |
| `min_symbols_per_date` | 横截面最低样本容量保护 | `5` |

详情请参阅 `docs/concepts/universe-modes.md`。

### 模型标签与目标 (`label`)

| 键名 | 作用说明 | 常见配置值 |
|---|------|--------|
| `horizon_days` | 模型预测的前瞻周期（交易日） | `5`、`20`、`60` |
| `rebalance_frequency` | 策略换仓频率 | `M`（月）、`Q`（季）、`Y`（年） |
| `shift_days` | 规避未来函数的信号滞后天数 | `1`、`0` |
| `winsorize_pct` | 针对截面原始标签的去极值比例 | `0.01` 或 `null` |
| `train_target_transform` | 针对模型拟合标签实施的横截面映射转换 | `none` / `zscore` / `rank` |

说明：

* `train_target_transform` 仅修饰输入至训练、交叉验证（CV）、walk-forward 前向验证及全量重训模式（`live.train_mode=full`）的标签列。
* 评估体系中的 `IC` 测试、分位追踪、Top-K 选股以及所有回测流程，均严格绑定于 `label.target_col` 所锚定的原始未映射收益率。
* 对待 `xgb_regressor` 模型，该转换开关非常适合用于评估“绝对收益回归与相对强弱回归”的效果差异；而对于本身具备排序属性的 `xgb_ranker` 模型，单调变换所带来的影响通常微乎其微。

### 算法与调优 (`model`)

| 键名 | 作用说明 | 常见配置值 |
|---|------|--------|
| `type` | 指定算法模型底座 | `xgb_regressor` / `xgb_ranker` / `ridge` / `elasticnet` |
| `sample_weight_mode` | 样本加权策略 | `none` / `date_equal` / `exp_decay` |
| `sample_weight_params.halflife` | 采用 `exp_decay` 时的衰减半衰期（以训练所含截面步数为尺度） | `8`、`12`、`16` |
| `sample_weight_params.decay_rate` | 指定恒定的指数衰减率（作为 `halflife` 的替代品） | `0.95`、`0.98` |
| `train_window.mode` | 主体训练数据的窗口策略 | `full`（全历史） / `rolling`（滚动窗口） |
| `train_window.size` | 滚动窗口的具体尺度 | `12`、`16`、`20` |
| `train_window.unit` | 滚动窗口的计量单位 | `dates`（自然截面数） / `years`（自然年） |

说明：

* 启用 `sample_weight_mode=exp_decay` 后，距离预测基准点越近的历史样本将获得更高的拟合权重。同时，处于同一日期的横截面样本群仍会先行依据群体规模实施一次平均降权处理，以防样本数量的突变扭曲整体梯度。
* 配置 `sample_weight_params` 时，必须保证至少声明了 `halflife` 或 `decay_rate` 二者之一。
* `model.train_window` 约束的是主训练集、CV 折叠、walk-forward 的训练侧、终局样本外推拟合以及实盘全量再训练过程的数据输入量。它并非评估环节 `walk_forward` 的代名词。
* 当 `train_window.unit=dates` 时，提取的是时序轴上最近的 `N` 个交易截面；若配置为 `years`，则是立足于终点时刻向回溯 `N` 个自然年。

### 核心评估环节 (`eval`)

| 键名 | 作用说明 | 常见配置值 |
|---|------|--------|
| `top_k` | 买入头寸上限数量 | `10`、`20`、`30` |
| `transaction_cost_bps` | 常规换手损耗假设（基点） | `15`、`25` |
| `score_postprocess.method` | 策略打分结果的后置优化逻辑 | `none` 或 `neutralize`（横截面中性化） |
| `score_postprocess.columns` | 执行中性化时所依赖的因子或标签列 | `["log_mcap"]` |
| `score_postprocess.strength` | 中性化的剔除力度调整 | `0.5`、`1.0` |
| `save_artifacts` | 开启持久化写入，保留报告与模型字典 | `true` 或 `false` |
| `save_scored_artifact` | 开启后，将保留含打分列的 `eval_scored.parquet` 全量大表 | 默认为 `false` |
| `purge_days` | 样本外重叠的断档天数防护 | 默认取 `horizon_days + shift_days` |

说明：

* `eval.score_postprocess` 的介入时点严格排布于模型预测输出之后，但在后续的 `IC` 计算、分位收益追踪与投资组合构建之前。该操作不会污染训练时的特征输入，也不等同于前置的特征层面中性化（Feature Neutralization）。
* 目前配置的 `method=neutralize` 将逐日执行针对目标控制列的正交去线性相关运算；支持在 `columns` 数组下挂载单个或多个解释变量列。
* 参数 `strength=1.0` 象征着将所选因子的横截面线性暴露彻底抹平；而配置为 `0.5` 则仅作半数扣减，适用于执行类似于 “soft size control” 的探针分析。
* 统计截面的有效观测容量（`min_obs`）须确保超越 `len(columns) + 1` 的下限门槛。若样本数量不足，算法将主动放弃正交化操作，复用原始模型得分。

### 步进样本外验证 (`eval.walk_forward`)

| 键名 | 作用说明 | 常见配置值 |
|---|------|--------|
| `enabled` | 激活 walk-forward 验证流程 | `true` 或 `false` |
| `n_windows` | 计划切分的目标外延窗数量 | `2`、`4`、`6` |
| `test_size` | 独立测试窗的比重或跨度。空置时继承主干 `eval.test_size` | `0.2`、`0.3` 或 `null` |
| `step_size` | 窗口滑动的步长。空置时默认与测试窗跨度保持一致 | `0.1`、`0.2` 或 `null` |
| `anchor_end` | 是否自最尾端逆向推演窗体排布 | `true` 或 `false` |

说明：

* 将 `eval.walk_forward.test_size` 赋为 `null` 并非唤醒内置的默认值，而是直接继承顶层的 `eval.test_size` 设定。
* 当选择 `anchor_end=true` 且 `step_size=null` 时，系统将测试窗的跨度复制为步移距离。若 `test_size` 自身占比较大（如 `0.6`），在试图获取 `4` 个观测窗时，历史全集可能仅有空间承载最后 `1` 个验证窗。
* 当请求的窗口数量超过了历史数据的承载极限，执行引擎将在控制台抛出超载警告，提醒用户 `walk_forward.n_windows` 仅作为预期上限，而非保底产出的绝对指标。

### 策略回测配置 (`backtest`)

| 键名 | 作用说明 | 常见配置值 |
|---|------|--------|
| `enabled` | 激活基于持仓重组的历史收益回测计算 | `true` 或 `false` |
| `weighting` | 定义入选名单的资金占比派发方式 | `equal`（等额等权）或 `signal`（按信号加权） |
| `exit_price_policy` | 遭遇标的停牌或退市缺价时的仓位估值与结算原则 | `strict`（抛弃）、`ffill`（顺延）或 `delay`（滞后结算） |
| `rebalance_frequency` | 执行账户调换的周期 | `M`（月）、`Q`（季）、`Y`（年） |
| `group_col` | 面向组合优化层的分组参考列（多为行业代码） | `first_industry_name` |
| `max_names_per_group` | 限制单一分组内的最大持仓数量 | `2`、`3`、`5` |
| `benchmark_symbol` | 指定单一股票或 ETF 代码作为基准曲线代理 | `02800.HK` |
| `benchmark_returns_file` | 外部提供的基准收益序列文件 | `artifacts/benchmarks/hk_connect_capw.csv` |
| `benchmark_compare` | 报告层附加对比基准列表，不替代主基准 | 详见下方示例 |
| `execution` | 执行层细节扩展：开平仓价格参照、滑点刻画及流动性约束 | 详见下文扩展章节 |

说明：

* 即便启用了 `research_universe.by_date_file` 过滤引擎，构建名单依然将严格受限于该 PIT 时点有效池的成分羁绊之中。
* 回测环节执行进离场交割计算和甄别市场交易资质（`tradable` 鉴别）时，系统会调取未经 `universe_by_date` 剔除的原生行情源，以此防范已成功建仓的股票因稍后惨遭基准池剔除而“消失”。
* `backtest.group_col` 与 `max_names_per_group` 配合使用可视为组合构建期的暴露额度封顶。这不会改变算法产出的评分次序，也不等同于完整的行业中性化机制。
* 启用 `backtest.execution` 会在 `transaction_cost_bps`、`exit_price_policy` 和 `data.price_col` 的基础上架设更为精细的交割模拟网；若未配置此项，原有的默认行为仍将生效。
* `execution.entry_policy.price_col` 及 `execution.exit_policy.price_col` 仅影响回测与持仓结算，不会篡改作为机器学习标签、主基准或价格衍生特征的全局标尺 `data.price_col`。
* 核心参照锚标 `backtest.benchmark_symbol` 与 `backtest.benchmark_returns_file` 存在天然互斥，两者选其一配置即可。前者适用于使用现成 ETF 指代，后者则适合自行定制。
* `backtest.benchmark_returns_file` 支持 `csv` 及 `parquet` 格式；时间轴坐标列可命名为 `trade_date`、`date`、`exit_date` 及 `rebalance_date`；回报比率列接受 `benchmark_return`、`return` 或 `net_return`。
* `backtest.benchmark_compare` 属纯粹报表层的多维补充。它不会干预系统沉淀到 `summary.json -> backtest.benchmark` / `backtest.active` 的主干统计数字，也不会影响前置的训练或调仓决议。
* `backtest.benchmark_compare` 的各配置项支持三种表达形式：直接填入收益文件的路径字符串；使用包含 `{name, returns_file}` 的字典项；或针对单一代码采用 `{name, symbol}` 格式。若省略 `name` 属性，系统会就地提取文件名或标的代码作为替代。
* 启用 `backtest.benchmark_compare` 后，运行结果会随附生成 `backtest_benchmark_compare_summary*.csv` 及 `backtest_benchmark_compare_<name>*.csv` 对照明细，并将关联线索汇集于 `summary.json -> backtest.benchmark_compare` 中。
* 核心回测流程当前将附赠一份名为 `backtest_report*.csv` 的汇总报表，包含策略净值轨迹、相对基准的超额收益线、按自然年测算的滑动 1Y/3Y/5Y CAGR 以及滚动最大回撤统计。
* 有关流转费用、滑点、复权修饰后的净价 `tr_close` 乃至真实现金分派的综合账本机制，请参阅专题文档：`docs/concepts/execution-costs.md`。

配置样例典范：

```yaml
backtest:
  benchmark_returns_file: artifacts/benchmarks/hk_selected_pit_research_m_capw_open_close_20181101_20260202.csv
  benchmark_compare:
    - name: hk_3432
      symbol: 3432.HK
    - name: hk_02800
      returns_file: artifacts/benchmarks/hk_02800_open_close_20181101_20260202.csv
    - name: hk_connect_full_capw
      returns_file: artifacts/benchmarks/hk_connect_full_research_m_capw_open_close_20181101_20260202.csv
```

### 进阶执行层 (`backtest.execution`)

常见内嵌参数：

| 子键名称 | 功能说明 | 常见配置值 |
|---|------|--------|
| `entry_policy.price_col` | 建仓入场时的划价坐标列 | `open` / `close` / `tr_close` |
| `exit_policy.price` | 退出缺价处理逻辑 | `strict` / `ffill` / `delay` |
| `exit_policy.price_col` | 清仓退出时的划价坐标列 | `close` / `open` / `tr_close` |
| `cost_model.name` | 调仓交易的成本扣除模型 | `bps` / `side_bps` / `none` |
| `slippage_model.name` | 滑点成本模型 | `none` / `bps` / `participation` |
| `constraints.min_price` | 买入标的的价格下限保护 | 任意非负数 |
| `constraints.min_amount` | 买入标的日成交额下限保护 | 任意非负实数 |

补充说明：

* 在 `cost_model.name=bps` 情景下，用户依然可以继续使用 `backtest.transaction_cost_bps` 简化配置。
* `cost_model.name=side_bps` 适合分别设定做多/做空以及建仓/清仓的损耗成本；配置项 `short_borrow_bps_per_day` 用于估测融券借贷下的日均利息开支。
* `slippage_model.name=bps` 对应单边固定滑点额度；而 `participation` 模式将依据实际盘面占比推算滑点影响，计算逻辑为 `trade_weight * portfolio_value / amount_col`。
* `constraints.min_amount` 与配套模块 `slippage_model.amount_col` 须使用系统归一化后的标准列名。例如原始字段如 `total_turnover`，必须写成被转换后的 `amount` 字段名。
* 若希望避免使用 `open` 入场价直接关联当日总成交额所带入的极微弱“未来数据（look-ahead）”成分，可将 `amount_col` 替换为某种历史平滑的流动性指标列（例如 `adv20_amount` 或 `medadv20_amount`，它们排除了交易当日的数据并分别计算了过去 20 个交易日的平均/中位数成交金额）。
* `summary.json -> backtest -> execution_source` 会详细记录本轮回测是恪守了简单的 `default_flat_cost` 模式，还是启用了高规级的 `explicit_execution_config` 执行流程。
* 仓库已内置了多套历经考验的港股月频执行层交割样例，详情参见：
  [hk_selected__execution_stress_local.yml](../configs/experiments/variants/hk_selected__execution_stress_local.yml)、
  [hk_selected__execution_balanced_local.yml](../configs/experiments/variants/hk_selected__execution_balanced_local.yml)、
  [hk_selected__execution_connect_conservative_local.yml](../configs/experiments/variants/hk_selected__execution_connect_conservative_local.yml)、
  [hk_selected__tr_close_execution_balanced_local.yml](../configs/experiments/variants/hk_selected__tr_close_execution_balanced_local.yml)。

### 基本面配置 (`fundamentals`)

| 键名 | 作用说明 | 常见配置值 |
|---|------|--------|
| `enabled` | 财务基本面数据开关 | `true` 或 `false` |
| `source` | 数据供应模式 | `provider`（远端抓取） / `file`（本地导入） |
| `ffill` | 财报空窗期的自动前向填充 | `true` 或 `false` |
| `provider_overlay.enabled` | 叠加加载日频估值补充数据的开关 | `true` 或 `false` |

说明：

* 在特征列表 `features.list` 内声明的 PIT 财报二次派生列，不仅涵盖诸如 `growth_*`、`delta_*` 或 `profit_margin` 之类的单期切片运算，也支持 `sales_cagr_3y`、`eps_cagr_3y` 等复合年化增长指标，以及 `cfo_margin_avg_3y`、`profit_margin_std_3y`、`positive_cfo_ratio_2y` 乃至带有条件约束的 `positive_cfo_ratio_3y_min2` 这类表征长周期稳定性的深度扩展特征。这些计算会首先在严格对齐发布日期的财报事件序列上完成预演，待到并入最终的日线宽表（daily panel）时，才会执行最终的 `ffill` 操作。

### 缺失值干预规程 (`features.missing`)

| 键名 | 作用说明 | 常见配置值 |
|---|------|--------|
| `method` | 缺失值填补策略 | `none`（留空） / `zero`（填零） / `cross_sectional_median`（使用截面中位数填补） |
| `add_indicators` | 是否增加缺失标记指示列 | `true` 或 `false` |

### 高频估值数据补充挂载策略 (`fundamentals.provider_overlay`)

当主干财务数据依赖 `fundamentals.source=file` 读取本地 PIT 文件时，通常面临文件更新滞后或离散留档的困境。此时可以开启 `provider_overlay`，单线向数据供应商拉取每日滚动的估值序列，并直接将其拼接融入最终的日线大表（daily panel）中，进而规避将高频估值反向回填入 PIT 底层库再执行费时的前向填充（ffill）操作。

```yaml
fundamentals:
  enabled: true
  source: file
  file: artifacts/assets/.../pipeline_fundamentals.parquet
  ffill: true
  provider_overlay:
    enabled: true
    source: provider
    provider: rqdata
    endpoint: get_factor
    fields:
      - hk_total_market_val
      - pe_ratio_ttm
      - pb_ratio_ttm
    column_map:
      trade_date: trade_date
      symbol: symbol
      market_cap: hk_total_market_val
      pe_ttm: pe_ratio_ttm
      pb: pb_ratio_ttm
    features:
      - market_cap
      - pe_ttm
      - pb
    auto_add_features: true
    required: true
```

统约共识：

- 目前 `provider_overlay` 仅支持 `source=provider` 这一单轨输入模式。
- 在规范对齐目标的基准主键时，要求统一标定为 `symbol`。若旧有外部数据源依然沿用如 `ts_code` 之类的命名，请务必在 `column_map` 映射字典中配置诸如 `symbol: ts_code` 的规则转换。
- 处于宏观配置层的 `fundamentals.symbol_param` 其默认规范值同样为 `symbol`。
- 系统核心运算链路内部仅认领 `symbol` 作为唯一主键标识；过往配置中的 `column_map.ts_code` 设定仍旧予以向下兼容。
- 主干配置 `fundamentals.file` 继续维持按 `symbol` 实施前向填充（ffill）的既有逻辑，完全贴合 PIT 财报特质。
- 而 `provider_overlay` 数据会严格凭借 `trade_date + symbol` 的二维坐标网格合并至日线层版面上，决不会触发跨日期的自动 `ffill` 顺延。
- 即使本地已经装载了全套日线与仪表面板的缓存数据，负责总调度的程序仍能在遭遇 `overlay` 缓存缺失（cache miss）时，自发启动懒加载（lazy init）机制并连线 `rqdatac` 补拉估值。
- 注意严苛规则：若 `provider_overlay.required=true` 且在该轮实验中未能成功拉取哪怕一条 `overlay` 记录，pipeline 将直接抛出致命错误并中止执行，绝不允许静默降级以避免后续逻辑受到污染。
- 倘若抓取回来的 `overlay` 数据集中没有找到 `valuation_trade_date` 字段，pipeline 将自动剥离原行自带的 `trade_date` 充当其定位值，并支持在需要时演算生成对应的新鲜度表征属性（`valuation_age_days`）。
- 衍生指标 `log_market_cap` 依旧交由顶层参数 `fundamentals.log_market_cap` 把控，只要特征版面上加载了 `market_cap`，系统即可自动演算并派生出相应的 `log_mcap` 字段。

### 行业标签融入配置 (`industry`)

若本地已留存了 `industry_labels_<freq>.parquet` 系列文件，您可径直将行业分类标签导入研究的主面板中。这将为后续实施的行业中性化、特定风险暴露度分析或精细的 `bucket_ic` 对比提供现成的、可直接连接（join）的结构化输入条件。

```yaml
industry:
  enabled: true
  source: file
  file: artifacts/assets/rqdata/hk/industry_changes/hk_all_industry_changes_latest/industry_labels_m.parquet
  keep_columns:
    - industry_code
    - industry_name
    - first_industry_code
    - first_industry_name
  ffill: false
  required: true
```

统约共识：

- 在当前的阶段版本里，`industry` 模块排他性地仅支持 `source=file` 作为唯一的受信任引入渠道。
- 连接操作的核心主键锁死在 `trade_date + symbol` 二维坐标网格上。为了顾及历史遗留问题，源自旧式档案内依旧沿用的如 `ts_code`、`stock_ticker` 或 `order_book_id` 等别名将受到自动化识别并予以兼容处理。
- 倘若 `keep_columns` 配置列表为空，系统将默认采用全盘收录策略，将源文件中除主键外所有的附加列一并合并。
- 必须明确：引入的类别标签列决不会自动侵占并跻身主导运算决策的核心 `features` 阵营内；不过它们必定会栖身并保底存储于沉淀收口的 `dataset.parquet` 库表中。更进一步论，当总开关 `eval.save_scored_artifact=true` 被激活后，这些行业属性也会顺带被转录至带有综合量化打分记录的大表 `eval_scored.parquet` 之内，从而为 `eval.bucket_ic.schemes` 提供名正言顺的调遣与评测用材。
- 这条特定的接入链路职能边界清晰：它纯粹专职地负责将孤立的行业标识标签平顺接引入主研究面板版图；若期望后续能够进一步完成行业本色抽离中性化运作作业，抑或是实现基于行业归类的强限制壁垒隔离管控，则完全仰赖您在后续的具体模型构建与探究开发环节中亲自动手编写代码以实施并落实相关的逻辑闭环。
- 选用诸如 `industry_labels_m/q.parquet` 这种带有频段标记的文件格式时，更稳妥的做法是保持文件频率与研究单元相一致。仅在明确需要顺延最近一次标签数据时，才开启 `ffill=true`。

## 路径迁移（针对旧版仓库的升级指导）

| 旧式存放路径 | 新版升级后存放路径 |
|--------|--------|
| `config/hk.yml` | `configs/presets/hk.yml` |
| `config/default.yml` | `configs/presets/default.yml` |
| `config/hk_selected__xgb_regressor.yml` | `configs/experiments/variants/hk_selected__xgb_regressor.yml` |

若本地环境中仍遗留有沿袭旧版规制划定的目录痕迹，当前版本已终止提供自动搬迁工具。请自行手动将数据挪移至全新的目录体系架构内。

更为详实的细节脉络拆解，请移步查阅：`docs/troubleshooting.md`。

## 相关关联文档参考索引

- CLI 操作命令行：`docs/cli.md`
- 输出结果文档：`docs/outputs.md`
- 远端提供商区别对照：`docs/providers.md`
- 概念理论体系指南：`docs/concepts/`
