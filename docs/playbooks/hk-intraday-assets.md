# HK Intraday 资产与滑点校准快照

本页解决什么：记录截至上次核对时工作区里已经落盘的 HK `5m` 资产、provider 边界、quota 成本和滑点校准产物。\
本页不解决什么：不代替 `docs/cli.md` 的命令参数说明，也不直接给出生产级 broker TCA 参数。\
适合谁：准备继续补 HK 分钟线、复用现有 `5m` parquet、或想知道“这批数据现在能拿来做什么”的读者。\
读完你会得到什么：已核对的 intraday 入口、provider 边界、经验滑点报告位置，以及继续下载前要先核对哪些东西。\
相关页面：`docs/playbooks/hk-rqdata-status.md`、`docs/concepts/execution-costs.md`、`docs/rqdata/README.md`、`python -m cstree.research.hk_intraday_download`、`python -m cstree.research.hk_intraday_slippage_report`

页面性质：`operational-snapshot`\
资产与报告核对时间：`2026-04-03`（Asia/Shanghai）\
文档职责核对时间：`2026-04-22`（Asia/Shanghai）\
权威来源：`artifacts/cache/intraday/*.meta.json`、`artifacts/assets/rqdata/hk/intraday/*/manifest.yml`、`artifacts/reports/*slippage*`、工作区脚本和现场 quota

状态边界：

* 本页保留 intraday 资产和滑点校准的上次操作快照，不负责每天更新 quota。
* 当前 `hk_intraday_latest` 指向、可用块数和健康状态，优先看 [hk-rqdata-status.md](./hk-rqdata-status.md) 以及最新 `artifacts/reports/hk_data_asset_audit_*.json`。
* 继续下载或发布前，先跑 `cstree rqdata quota --pretty` 和 `cstree rqdata inspect-hk-data-assets --intraday-mode metadata`；需要深度核对时再用 `inspect-hk-intraday-health`。

## 先说结论

截至 `2026-04-03`，本地已经核对到三组可复用的 HK `5m` 数据：

* `hk_connect_research` 最近 `1` 年样本，可用来先校准港股通研究池。
* 全市场 `2025-03-27` 到 `2026-03-26` 的 `5m` 全年块。
* 全市场 `2024-05-01` 到 `2025-03-26` 的 `5m` 年度块。

这组快照说明：

* 全市场 `5m` 已经足够支持经验滑点校准，不需要再回到“先下数据再说”的状态。
* provider 当前 HK 分钟线最早只能拿到 `2024-05-01`，所以“完整过去两年全市场 `5m`”在这个 provider 上并不存在。
* 试用 quota `1GB/day` 当时足够做全市场 `5m` 的年度块，但不适合继续做更重的 `1m` 全市场历史。

## 正式资产层

从 `2026-04-03` 开始，仓库也支持把本地 intraday cache 提升成正式资产层：

```bash
cstree rqdata build-hk-intraday-asset --input artifacts/cache/intraday --name hk_intraday_latest --alias artifacts/assets/rqdata/hk/intraday/hk_intraday_latest
cstree rqdata sync-hk-intraday --symbols-file artifacts/assets/rqdata/hk/daily/hk_all_daily_latest/symbols.txt --start-date 20260402 --end-date 20260409 --resume
```

这层和 `daily` 的区别是：

* 正式入口在 `artifacts/assets/rqdata/hk/intraday/<snapshot>/`
* 命令会把 parquet、同名 `.meta.json` 和 `.parts/` 一起复制到 `data/`
* 之后即使你清掉 `artifacts/cache/intraday/`，正式资产仍然可直接被健康检查和滑点报告脚本复用
* 如果你想把 `download -> inspect -> alias` 也收口成一条命令，现在优先用 `cstree rqdata sync-hk-intraday`；它默认只检查新增 patch，按需可加 `--verify-sampled-segments 3` 等距抽查正式资产的历史分段
* `--verify-full-asset` 是显式重动作，适合低频放后台或离线环境跑；`--package` / `--release` 也只在明确要出 tarball / GitHub Release 时再开

如果你只是想临时保留一下本地状态，`artifacts/snapshots/` 仍然适合做冻结备份；如果你要给下游长期复用，优先用这里的正式资产层。

## 已核对落盘的 intraday 入口

### 港股通 research 样本

* `artifacts/cache/intraday/hk_connect_research_5m_20250317_20260317.parquet`
  `541` symbols，`8,601,600` 行，约 `132 MB`
* `artifacts/cache/intraday/hk_connect_research_5m_20250317_20260317.meta.json`
  这次全年样本实际耗 quota `113,894,195` bytes

适合用途：

* 先在研究池上估一个 `open -> VWAP/close` 的经验滑点量级
* 先做 execution 参数灵敏度分析
* 不想先碰全市场微盘噪音时，先拿它做过滤后的 calibration

### 全市场 `5m` 年度块

* `artifacts/cache/intraday/hk_all_5m_20250327_20260326.parquet`
  `2785` symbols，`43,169,526` 行，约 `326 MB`
* `artifacts/cache/intraday/hk_all_5m_20250327_20260326.meta.json`
  实际耗 quota `311,744,293` bytes
* `artifacts/cache/intraday/hk_all_5m_20240501_20250326.parquet`
  `2698` symbols，`38,466,138` 行，约 `251 MB`
* `artifacts/cache/intraday/hk_all_5m_20240501_20250326.meta.json`
  实际耗 quota `247,094,080` bytes

两段合起来的可用范围是：

* `2024-05-01` 到 `2026-03-26`
* 并集 `2827` symbols

注意：

* 两段的 symbol 数不同是正常现象，不代表坏数据；这是不同年份实际有分钟线返回的 symbol 集不同。
* `2024-03-27` 到 `2024-04-30` 这一段 provider 当前拿不到，不能按“还没下载”处理。

## provider 边界

这次实际验证到的边界是：

* HK 分钟线最早允许的开始日期是 `2024-05-01`
* 如果请求更早日期，provider 会直接报 `start_date earlier than earliest date allowed 20240501`

所以今后如果你看到目录名里想做“过去 2 年全市场 `5m`”，要先记住这个前提：

* 现在最多只能做到 `2024-05-01` 起的全市场分钟线
* 不要把 `2024-03-27` 到 `2024-04-30` 当成待补 patch

## checkpoint / resume 规则

公开入口 `python -m cstree.research.hk_intraday_download` 现在已经支持真正的断点续传：

* 下载时每个 batch 先落到 `*.parts/batch_XXXX.parquet`
* 每个 batch 同时写入 `*.parts/batch_XXXX.meta.json`，记录 symbol 列表、日期、字段、频率和复权口径的签名
* `--resume` 只会跳过签名完全匹配的 batch part；如果换了 `symbols-file`、字段或 `adjust-type`，旧 part 会被重新下载，避免误复用
* 最后再把 part 文件流式合并成单个 parquet
* 现在也支持 `--adjust-type none|pre|post|pre_volume|post_volume`；后续如果要补更严肃的盘中执行样本，优先考虑单独下载 `--adjust-type none`
* `--symbols-file` 默认按 canonical `symbol` 读入；旧文件里的 `ts_code` / `stock_ticker` / `order_book_id` 仍会自动兼容。最终落盘 parquet 会统一把 `symbol` 规范成 canonical 的五位 `.HK` 代码；`rq_order_book_id` 只作为 provider 元数据列保留

上次核对时已经保留的 checkpoint 目录：

* `artifacts/cache/intraday/hk_all_5m_20250327_20260326.parts/`
* `artifacts/cache/intraday/hk_all_5m_20240501_20250326.parts/`

这两点很重要：

* 如果实例中途挂掉，现在可以从 part 目录继续，不需要整段重下。
* `python -m cstree.research.hk_intraday_slippage_report` 和 `cstree rqdata inspect-hk-intraday-health` 现在都会优先使用同名 `.parts/` 目录，避免整块读取巨大的最终 parquet，降低全市场大文件导致内存爆掉的风险。

## 已核对产出的滑点校准结果

### 报告文件

单段报告：

* `artifacts/reports/hk_all_5m_20240501_20250326_slippage_daily.parquet`
* `artifacts/reports/hk_all_5m_20240501_20250326_slippage_summary.json`
* `artifacts/reports/hk_all_5m_20240501_20250326_slippage_liquidity.csv`
* `artifacts/reports/hk_all_5m_20250327_20260326_slippage_daily.parquet`
* `artifacts/reports/hk_all_5m_20250327_20260326_slippage_summary.json`
* `artifacts/reports/hk_all_5m_20250327_20260326_slippage_liquidity.csv`

合并后的总口径：

* `artifacts/reports/hk_all_5m_20240501_20260326_slippage_daily.parquet`
* `artifacts/reports/hk_all_5m_20240501_20260326_slippage_summary.json`
* `artifacts/reports/hk_all_5m_20240501_20260326_slippage_liquidity.csv`
* `artifacts/reports/hk_execution_calibration_candidates_20260326.csv`

### `VWAP` 口径说明

这批报告里的 `buy_open_to_vwap_bps` 现在不是简单的 `amount / volume`。

原因是：

* 当前已落盘的 HK `5m` parquet 来自 provider 默认 `adjust_type=pre` 的价格序列。
* 长窗历史上，直接用原始 `amount / volume` 去对比复权后的 `open`，会把 `VWAP` 估偏。

所以当前脚本改成了：

* `vwap_method=bar_price_volume_proxy`
* 用每根 bar 的 `OHLC` 均价按 bar `volume` 加权，近似整天的 session price center

这更适合当前这批缓存做经验校准，但仍然只是 proxy，不是 tick 级真实 VWAP。

### 合并总口径的高层读法

`2024-05-01` 到 `2026-03-26` 的全市场 raw summary：

* `1,245,688` 个 symbol-day
* `2827` 个 symbols
* `468` 个 trade dates
* `abs_open_to_vwap_bps` 中位数约 `147.66 bps`
* `abs_open_to_close_bps` 中位数约 `117.99 bps`

但这组数不能直接拿去当你的策略滑点参数，因为它混了大量极端不活跃的小票。看 liquidity bucket 更有意义：

* bucket 1 的 `session_amount` 中位数是 `0`，这批几乎就是“不应交易”的样本
* bucket 3 到 5 的 `abs_open_to_vwap_bps` 中位数大约在 `143` 到 `153 bps`
* bucket 5 的 `session_amount` 中位数约 `69.15M`

所以更合理的读法是：

* 这份报告首先用来做“不可交易样本识别”和“按流动性分层的经验校准”
* 不要把全市场 raw 中位数直接灌进 `slippage_bps`
* 真正用于 `hk_selected` 或港股通组合时，应先按 `adv20_amount`、研究池、价格门槛等条件过滤

### `hk_selected` / 港股通研究池的候选参数

`artifacts/reports/hk_execution_calibration_candidates_20260326.csv` 已经把全市场 `5m` 报告缩到了两个更贴近研究的口径：

* `hk_selected`：按 research symbol 集过滤，再加 `open >= 5`
* `hk_connect_research`：按港股通 research symbol 集过滤，再加 `open >= 5`

更实用的几档读法：

* `hk_selected + min_amount >= 10M`
  `buy_open_to_vwap_bps` 中位数约 `3.90 bps`，`p75` 约 `140.00 bps`
* `hk_connect_research + min_amount >= 20M`
  `buy_open_to_vwap_bps` 中位数约 `1.75 bps`，`p75` 约 `146.91 bps`
* 两条线在 `50M` 档都落到 `buy_open_to_vwap_bps` 中位数约 `4` 到 `5 bps`，但 `p90` 仍在 `339` 到 `370 bps`

所以当前更适合先落成三档执行候选。仓库里现在已经有两条校准入口，加上一条滞后 ADV 压力基线：

* `balanced`
  对应 [hk_selected__execution_balanced_local.yml](../../configs/experiments/variants/hk_selected__execution_balanced_local.yml)

```yaml
backtest:
  execution:
    slippage_model:
      name: participation
      amount_col: adv20_amount
      base_bps: 4
      impact_bps: 50
      portfolio_value: 1000000
      power: 0.5
      max_participation: 0.05
    constraints:
      min_price: 5
      min_amount: 10000000
      amount_col: adv20_amount
```

* `connect_conservative`
  对应 [hk_selected__execution_connect_conservative_local.yml](../../configs/experiments/variants/hk_selected__execution_connect_conservative_local.yml)

```yaml
backtest:
  execution:
    slippage_model:
      name: participation
      amount_col: adv20_amount
      base_bps: 4
      impact_bps: 50
      portfolio_value: 1000000
      power: 0.5
      max_participation: 0.05
    constraints:
      min_price: 5
      min_amount: 20000000
      amount_col: adv20_amount
```

* `stress baseline`
  对应 [hk_selected__execution_stress_local.yml](../../configs/experiments/variants/hk_selected__execution_stress_local.yml)

```yaml
backtest:
  execution:
    slippage_model:
      name: participation
      amount_col: adv20_amount
      base_bps: 2
      impact_bps: 20
      portfolio_value: 1000000
      power: 0.5
      max_participation: 0.1
    constraints:
      min_price: 5
      min_amount: 1000000
      amount_col: adv20_amount
```

解释：

* 这里的 `base_bps` 对齐的是研究池过滤后的 `open -> VWAP proxy` 中位数量级。
* `impact_bps` 使用这批分钟线结果作为“压力带”，据此设定更保守的 participation 曲线，不直接拟合 `p75/p90`。
* `stress baseline` 保留得更宽松一些，适合先替代 flat `25bps`；如果你要直接上校准后的研究线，优先从 `balanced` 或 `connect_conservative` 开始。
* 在当前 `portfolio_value=1m`、`top_k=20` 的设定下，单笔 trade participation 通常很低，真正决定结果的大多还是 `base_bps` 和 `min_amount`；如果你要做容量分析，先改 `portfolio_value`，再谈 `impact_bps`。

## quota 快照

`2026-03-26` 现场核对到的 quota：

* 在两段全市场 `5m` 下载完成后：`bytes_remaining: 66.64 MB`
* 在当天顺手补完 `daily / valuation / ex_factors / dividends / shares` patch 后：`bytes_remaining: 59.51 MB`

基于这次真实下载结果，可以更实际地估：

* 全市场 `5m` 一整年大约是 `247 MB` 到 `312 MB` quota 量级
* 港股通 research `5m` 一整年大约 `114 MB`
* 当天这些轻量 tail patch 合计只额外消耗了约 `7.48 MB`
* 当时剩余 quota 不适合再开新的大段分钟线下载

但这不影响继续做两类事情：

* 本地读现有 parquet 做 calibration / aggregation /回测参数校准
* 做日线、估值、复权、分红、股本这类更轻的 patch

## 建议的使用顺序

1. 先用 `artifacts/reports/hk_all_5m_20240501_20260326_slippage_liquidity.csv` 看不同流动性桶的经验滑点量级。
2. 再把 `hk_selected` 或港股通研究池按 `adv20_amount` / 价格 / 最低成交额过滤，抽出更贴近策略的样本。
3. 在 execution 配置里优先使用 `adv20_amount` 或 `medadv20_amount`，不要退回 `open + same-day amount`。
4. 现阶段如果要补正式研究参数，优先从 `balanced` 或 `connect_conservative` 开始；不要直接用全市场 raw 中位数。
5. 如果后面要更细的盘中执行研究，再决定是否值得补 `1m`；不要在 `1GB/day` 试用 quota 下先把自己拖进更重的数据维护。
