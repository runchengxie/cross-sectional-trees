## Context

仓库已经具备较完整的 HK / RQData 资产维护链路，但入口仍然分散：

- `artifacts/metadata/current_assets/hk_current.json` 记录当前 contract 指向的最新资产；当前 contract 的 `target_date` 是 `20260410`，生成时间是 `2026-04-11T14:24:21+08:00`。
- `scripts/dev/refresh_hk_current.sh` 会调用 `scripts/internal/run_hk_asset_workflow.py` 执行 `refresh + inspect`，默认覆盖 `daily`、`valuation`、`ex_factors`、`dividends`、`shares`、`industry_changes`、`southbound` 等主链资产。
- `scripts/dev/run_hk_health_checks.sh` 会批量跑 `inspect-hk-current-health`、`inspect-hk-asset-health`、`inspect-hk-pit-coverage`，并可选附带 `inspect-hk-intraday-health`，但不会默认回答 ETF daily 的完整性问题。
- `src/csml/data_tools/rqdata_assets/current_health.py` 里 `intraday` 与 `etf_daily` 目前都被视为非必需资产，且 stale severity 只有 `warning`，这更适合“当前 contract 总览”，不适合用户显式要求的“必须核实是否齐全、是否最新”。
- `asset_health.py` 和 `intraday_health.py` 已经具备历史扫描、样本抽样、按 severity 分类、与 daily 对账等能力，但它们的输出仍然偏单资产视角；用户问题需要一份横跨缓存、正式资产、current alias、历史缺口、修复动作和陈旧文件的统一审计结果。

同时，仓库协作规则明确要求对大数据优先落结构化 report，而不是在代理会话里直接展开大块 parquet；因此这次实现应优先编排和增强现有 report 能力，而不是引入另一套临时脚本。

## Goals / Non-Goals

**Goals:**

- 生成一份面向用户问题的数据资产审计结果，明确回答“现在有哪些数据”“最后刷新到哪一天”“哪些范围齐全/不齐全”“哪些问题可修复/不可修复”“哪些目录可清理”。
- 复用现有 `current_health`、`asset_health`、`intraday_health`、`hk_asset_workflow`，把现有 report 聚合成一条可重复执行的审计/修复路径。
- 把 ETF `daily` 自 `2000-01-01` 至目标日的完整性，以及股票 `5m` 数据是否刷新到目标日，提升为显式校验项，而不是仅依赖 current contract 的弱告警。
- 为历史异常提供安全修复策略，优先 patch refresh、局部 rebuild、repair queue 和 alias 切换，避免无依据地整包重下。
- 为陈旧/重复资产提供“可安全删除”的证据链和 dry-run 清理计划，避免误删 current 资产、release 产物或仍被 report 引用的快照。

**Non-Goals:**

- 不改变现有 provider 边界，也不承诺补齐 provider 本身不可提供的历史区间。
- 不把所有维护动作升级成默认自动执行的 destructive 操作；删除和大规模重建必须保持显式确认。
- 不重写现有 `inspect-*` 检查器的底层扫描模型；优先在编排层补齐缺口，只有确有必要时才收紧单个检查器规则。
- 不把研究结果目录 `artifacts/runs/` 的治理和数据资产健康混成一个统一删除器；运行结果只做引用/陈旧性标记，不在第一版里自动清理。

## Decisions

### 1. 增加一条统一的数据审计入口，聚合现有 inventory、health、repair 和 prune 结果

实现将新增一个面向维护者和代理的统一入口，负责：

- 读取 `hk_current.json` 和关键 alias，生成当前资产 inventory。
- 解析 `artifacts/assets/`、`artifacts/cache/`、`artifacts/releases/`、`artifacts/reports/` 中与当前资产相关的目录和 manifest。
- 执行或复用 ETF daily、intraday、daily_clean、valuation 等目标检查。
- 产出一份统一的 JSON report 和一份人类可读 summary。

原因：

- 用户问题是横跨多个现有命令的；继续让使用者手工拼接多个 report 成本高且容易漏项。
- 现有 `hk_asset_refresh_<date>.json` 已经承载 refresh/inspect 元数据，适合继续作为 repair 和 freshness 的上游输入。

备选方案：

- 仅更新文档，要求用户手工按 runbook 逐条执行。拒绝原因是不能形成可复用的回答路径，也无法稳定产出“可删除/不可删除”的证据链。

### 2. 审计流程采用“两层检查”模型：先元数据盘点，再定向重检查

第一层做轻量 inventory：

- current contract / alias / manifest / dataset registry / snapshot 目录扫描
- 覆盖范围、`query_end_date`、`as_of`、symbol 文件数、快照命名约定和 release 引用关系

第二层只对用户关心且高风险的数据跑重检查：

- ETF daily `2000-01-01` 到目标日
- 股票 `5m` 最新性与日线对账
- 历史缺口疑点和 repair candidate

原因：

- 仓库已有大文件和 `.parts/` 目录，全面历史复扫应保持可控。
- 轻量 inventory 足以先回答“是否值得继续重扫”“哪些资产最可疑”。

备选方案：

- 每次默认全量跑所有 `include-history` 和 intraday 对账。拒绝原因是 I/O 过重，且与仓库对大数据检查的约定冲突。

### 3. 把 ETF daily 与 intraday freshness 从“可选观察项”提升为显式审计规则

实现上不一定马上修改 `CURRENT_HEALTH_POLICY` 的全局默认语义，但统一审计入口必须单独定义更严格的目标：

- 对 ETF daily：验证当前 alias、时间范围、最新日期、symbol 覆盖、缺失文件、历史缺口，并区分“provider 缺失”“本地缺失”“manifest 漂移”。
- 对 intraday：验证 `hk_intraday_latest` 是否覆盖目标交易日，必要时复用 `.parts/` 和 daily reconciliation，输出最新 trade date、symbol-day 缺口和可修复范围。

原因：

- 现在 `current_health` 里的 `etf_daily` / `intraday` 只是 optional warning，无法满足“是否齐全、是否已刷新到最新”的判断标准。

备选方案：

- 保持现状，仅在最终 summary 里手工强调。拒绝原因是规则无法沉淀，下一次仍会重复人工解释。

### 4. 修复优先复用现有 workflow 和 repair queue，不新造独立修复器

修复路径按优先级分三档：

- 轻修复：alias 漂移、manifest/current contract 不一致、可直接 repoint 的已存在快照
- 中修复：基于 patch refresh 或 targeted refresh 的尾窗补齐
- 重修复：只对明确损坏或缺失的资产做局部 rebuild / rerun inspect

统一审计报告应直接消费或生成：

- `hk_asset_refresh_<target_date>.json`
- `hk_asset_repair_queue_<target_date>.json`
- `hk_asset_remaining_repair_candidates_<target_date>.json`

原因：

- 仓库已有按 severity 分类 repair candidates 的设计，继续复用可以降低实现风险。
- 把修复动作锚定到现有 workflow，可以天然继承 gate、rerun inspect 和 report 落盘能力。

备选方案：

- 新写一个与 `hk_asset_workflow.py` 平行的修复脚本。拒绝原因是逻辑重复且容易与现有 refresh/inspect 规则漂移。

### 5. 清理采用“引用可达性 + 类型白名单 + dry-run”的保守策略

统一审计入口需要把快照分为至少四类：

- current 引用中，禁止自动删除
- release / package / report 仍引用中，默认不删
- 仅作为 patch / repair 中间产物，且已有稳定正式快照替代，可建议删除
- 明显陈旧且不再被 alias、current contract、release、report 引用，可标记为候选删除

输出应先生成清理计划文件，而不是直接删除；真正删除必须显式开启并限定到已批准类型。

原因：

- `artifacts/releases/`、`artifacts/reports/repair_inputs/`、`__patch` 目录和旧 snapshot 的生命周期不同，不能按“名字旧”直接删除。

备选方案：

- 直接按日期阈值删旧目录。拒绝原因是会误删仍被 current alias 或 report 依赖的资产。

## Risks / Trade-offs

- [重检查仍然可能耗时较长] → 把 inventory 与 deep checks 分阶段执行，并允许仅对 ETF / intraday / 指定资产启用历史扫描。
- [provider 边界可能被误判为本地坏数据] → 报告里单独标记“provider-unavailable”与“local-missing”，例如 HK `5m` 的最早可用日边界。
- [alias 切换可能掩盖未真正修复的数据问题] → 任何 repoint 前必须重新跑 inspect，并把切换前后 resolved path 写入 report。
- [清理策略过于保守，短期内不会明显降体积] → 第一版先确保不误删；真正 aggressive cleanup 作为后续优化。
- [现有 sample-based 报告可能不足以解释大范围缺口] → 对 summary 保留抽样，对 repair/prune 决策额外保留聚合统计和必要的明细文件路径。

## Migration Plan

1. 增加统一审计入口与 report schema，先能稳定产出 inventory、freshness、ETF/intraday 结论和 prune candidates。
2. 接入现有 refresh / inspect / repair workflow，把缺口判定与修复动作串起来。
3. 为 ETF daily、intraday 和历史问题增加更明确的 severity 规则与 summary 文案。
4. 补文档与维护脚本说明，明确轻量盘点、重检查、修复和清理的推荐顺序。

回滚策略：

- 如果统一入口不稳定，可回退到保留现有 `refresh_hk_current.sh` 与 `run_hk_health_checks.sh` 的老路径；新增 report 不会破坏既有资产格式。
- 清理动作保持显式确认，因此不会要求数据层回滚；最多只需停用新的 prune plan 生成逻辑。

## Open Questions

- 统一入口最终应暴露为公开 `csml rqdata ...` 子命令，还是先落在 `scripts/dev/` / `scripts/internal/` 供维护者使用？
- ETF 完整性判定的权威 universe 应以 `etf_instruments` 为准，还是允许用户传入自定义 ETF symbol 集？
- intraday “刷新到最新” 是否以 current contract `target_date` 为目标，还是应自动解析最近交易日并允许 market holiday 容忍窗口？
- 第一版是否只生成 prune plan，不真正执行删除；如果需要执行，哪些目录类型可以安全纳入显式删除开关？
