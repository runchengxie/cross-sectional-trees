# 功能矩阵、范围与工时评估（内部资料）

给一份配置，`cstree` 会跑完整研究流水线：拉数、构池、打标签、做特征、训练、评估、回测、落盘产物、输出持仓快照。

这是一份内部规划和范围说明文档。首次使用仓库时，请先看根目录 `README.md` 和 `docs/README.md`。

## 文档定位

本文件用于回答四个问题：

1. 这个项目当前已经落地了哪些能力层。
2. 哪些属于研究主链路，哪些属于数据资产工具和运维辅助。
3. 这些能力的关键工程难点分布在哪一层。
4. 以人天口径看，开发/维护预算应怎么估。

说明：

* 本文按研究主链路 + 数据资产工具 + 运维辅助 + 边界/工时分组。
* 参数字典与默认值仍以 `docs/config.md` 为准。
* CLI 全量参数仍以 `docs/cli.md` 和 `cstree <cmd> --help` 为准。
* 输出字段 Schema 仍以 `docs/outputs.md` 为准。
* 本文口径是当前仓库已落地能力 + 明确不覆盖的边界 + 粗粒度工时判断。

## 一、当前能力矩阵（按层分组）

### 1) 用户可见 CLI 能力

| 能力层 | 命令 | 能力 | 关键输出/副作用 | 备注 |
| --- | --- | --- | --- | --- |
| 研究主入口 | `cstree run` | 训练/评估/回测/持仓主流程 | `artifacts/runs/...` 全套产物 | 研究主入口 |
| 研究编排 | `cstree grid`、`cstree sweep-linear`、`cstree summarize` | 敏感性分析、线性模型 sweep、历史 run 汇总 | `grid_summary.csv`、`artifacts/sweeps/...`、`runs_summary.csv` | 研究对比与批处理入口 |
| 结果消费 | `cstree holdings`、`cstree snapshot`、`cstree alloc` | 读取持仓、导出快照、做等权手数分配 | text/csv/json 持仓或分配表 | `alloc` 依赖 RQData 价格和 round lot |
| 配置模板 | `cstree init-config` | 导出内置 YAML 模板 | 本地 YAML | 支持 `--force` 覆盖 |
| RQData 账号/字段探针 | `cstree rqdata info`、`cstree rqdata quota`、`cstree rqdata list-hk-financial-fields` | 检查账号初始化、配额与 HK 财报字段元数据 | 账号/配额/字段清单 | 运维排障和下载前探测 |
| RQData HK 原始资产镜像 | `cstree rqdata export-hk-instruments`、`mirror-hk-daily`、`mirror-hk-pit-financials`、`mirror-hk-financial-details`、`mirror-hk-ex-factors`、`mirror-hk-dividends`、`mirror-hk-shares`、`mirror-hk-exchange-rate`、`mirror-hk-announcement`、`mirror-hk-southbound`、`mirror-hk-instrument-industry`、`mirror-hk-industry-changes` | 把 HK instrument、行情、PIT 财报、参考数据、announcement、southbound、行业资产冻结为可复用目录 | `artifacts/assets/rqdata/hk/<dataset>/<snapshot>/` | 属于正式 CLI，不是边角脚本 |
| RQData HK 派生构建 | `cstree rqdata build-hk-pit-fundamentals`、`build-hk-industry-labels`、`inspect-hk-pit-coverage` | 构建 pipeline 可读 fundamentals、行业标签文件，并检查 PIT 覆盖率 | `pipeline_fundamentals.parquet`、`industry_labels_<freq>.parquet`、coverage 报告 | 连接 raw mirror 与研究主链路 |
| Universe 工具 | `cstree universe hk-connect`、`hk-daily-assets` | 构建港股通 PIT universe、HK 全市场 by-date universe | `artifacts/assets/universe/...` | `hk-daily-assets` 依赖本地日线镜像 |
| 运维辅助 | `cstree backup-data` | 归档本地缓存/股票池/配置 | `artifacts/snapshots/<name>/` | 研究运维与排障入口 |

补充：

* 本页按能力层汇总，不重复 `docs/cli.md` 的逐命令参数展开。
* HK / RQData 资产准备顺序与关系，优先看 `docs/playbooks/hk-data-assets.md`。

### 2) 研究主链路模块矩阵（`cstree run` 内部能力）

| 模块 | 已实现能力 | 关键参数入口 | 典型风险点 |
| --- | --- | --- | --- |
| Universe | `auto/pit/static` 股票池，按日期过滤、停牌/上市天数/成交额过滤 | `research_universe.*` | 过滤顺序改变结果；PIT 数据缺失 |
| Data | `rqdata`，HK symbol 规则，缓存与重试；支持直接读取本地 daily/instruments 资产 | `market`、`data.*` | 在线/离线双路径结果漂移 |
| Fundamentals | `provider/file` 两路并入，列映射、`ffill`、缺失策略；支持 `provider_overlay` 叠加 provider 日频估值 | `fundamentals.*` | provider 能力不对齐；PIT 与日频估值 merge 口径不一致 |
| Industry | 支持从本地 `industry_labels_<freq>.parquet` join 行业标签 | `industry.*` | 行业标签频率与研究频率错配 |
| Label | `fixed/next_rebalance`，shift 与截尾 | `label.*` | 时序泄漏、标签口径偏差 |
| Features | 技术特征生成 + 横截面 `none/zscore/rank` + 缺失标记 | `features.*` | 窗口与样本可用性冲突 |
| Model | `xgb_regressor/xgb_ranker/ridge/elasticnet` | `model.*` | 模型与样本权重设定不当 |
| Eval | train/test + CV IC，direction flip，置换检验，walk-forward，final OOS，rolling/bucket 指标 | `eval.*` | 仅看单指标导致过拟合 |
| Backtest/Execution | Top-K、多空、成本模型、buffer、exit policy、tradable 约束 | `backtest.*` | 回测语义与真实交易偏差 |
| Live | 产出 live 持仓文件与 `latest.json` 指针 | `live.*` | 依赖 `eval.save_artifacts=true` |
| Reproducibility | 冻结配置、哈希 run 目录、核心产物落盘、`cache_tag` 隔离 | `eval.output_dir`、`data.cache_tag` 等 | 缓存、相对日期、数据回补导致重跑差异 |

### 3) 独立于 run 目录的资产与辅助产物

| 类别 | 典型文件/目录 | 触发方式 | 用途 |
| --- | --- | --- | --- |
| run 核心产物 | `summary.json`、`config.used.yml`、`backtest_*.csv`、持仓文件（`eval_scored.parquet` 为可选） | `cstree run` / `snapshot` | 研究结果复现、汇总和下游消费 |
| provider 原始镜像 | `artifacts/assets/rqdata/hk/<dataset>/<snapshot>/` | `cstree rqdata mirror-hk-*` | 冻结可复用原始资产，供下游项目或本仓库继续派生 |
| 平面 fundamentals | `<pit_snapshot>/pipeline_fundamentals.parquet` | `cstree rqdata build-hk-pit-fundamentals` | 给 pipeline 直接读取的 file fundamentals |
| 本地行业标签 | `<industry_changes_snapshot>/industry_labels_<freq>.parquet` | `cstree rqdata build-hk-industry-labels` | 给研究主链路或分析脚本直接 join 行业列 |
| universe 文件 | `artifacts/assets/universe/*.csv`、`*.txt` | `cstree universe ...` | 研究样本边界、离线审计和资产下载入口 |
| 本地数据快照 | `artifacts/snapshots/<name>/` | `cstree backup-data` | 归档缓存、股票池、配置和额外资产路径 |
| 兼容迁移副作用 | `cache/`、`out/`、`data_assets/` 迁到 `artifacts/` | 手动迁移旧目录 | 旧仓库升级；不是日常研究产物 |

### 4) 明确边界（当前不覆盖）

* 券商/OMS 账户对接与自动下单执行。
* 成交回执、撤单重试、盘中执行控制。
* 涨跌停、盘口冲击、复杂成交模型等微观结构仿真。
* 账户级风控约束（行业/风格/敞口/现金管理）的一体化执行闭环。
* 自动行业中性化或行业约束执行；当前 `industry` 链路只负责把本地标签 join 进 panel。

补充边界：

* `holdings/snapshot` 输出的是目标持仓，不等同真实成交持仓。
* 交易日历 token 在部分场景可能退化为自然日逻辑（无交易日历时会给告警）。
* 数据供应商回补/修订会导致同配置不同时间结果变化。
* 旧目录迁移只是历史兼容问题；新仓库通常不需要处理。

## 二、难点分层（工程 + 研究）

| 层级 | 难点主题 | 为什么难 | 典型失败模式 | 降险措施 |
| --- | --- | --- | --- | --- |
| L1 数据接入层 | 多 provider、多市场、符号标准化 | 同名字段语义不一致，符号体系不同 | 某市场可跑、跨市场失真 | 统一 symbol 规范 + provider 适配测试 |
| L1 数据接入层 | API 配额、失败重试、token 轮换 | 第三方服务不稳定且有频率限制 | 间歇失败、批量任务中断 | 重试/退避/轮换 + 配额监控 |
| L2 研究正确性层 | PIT universe 与过滤顺序 | 顺序不同会改变样本分布 | 能跑通但结果漂移 | 固化顺序、日志化样本数变化 |
| L2 研究正确性层 | 标签/切分/评估泄漏防控 | 泄漏点跨多个模块 | 指标异常高，实盘失效 | purge/embargo（含默认推导与告警）+ 时间切分单测 |
| L2 研究正确性层 | `file` 基本面、`provider_overlay`、行业标签 join 的口径一致性 | 稀疏 PIT、日频估值和行业标签属于不同更新频率 | merge 成功但含义错位，结果不可解释 | 显式 schema、`trade_date + symbol` 主键约定、结果摘要落盘 |
| L2 研究正确性层 | 稳健性验证组合 | 单一指标不能代表可交易性 | 过拟合模型上线 | CV + walk-forward + permutation 联检 |
| L3 回测语义层 | 成本、buffer、退出策略、可交易性 | 每个细节都影响收益与换手 | 回测结果过于乐观 | 参数显式化 + 默认值审计 |
| L3 回测语义层 | `label_horizon` 与调仓频率协同 | 退出与再平衡可能冲突 | 逻辑跳过或行为不一致 | 冲突检测与报错策略 |
| L4 可复现运维层 | 数据资产谱系、版本与 freshness 一致性 | raw mirror、flat fundamentals、industry labels、universe-by-date 之间形成派生链 | 同名 snapshot 可跑但上下游口径不一致 | `manifest.yml`、命名约定、资产目录审计、`config.used.yml` 固化引用 |
| L4 可复现运维层 | 在线 provider + 离线本地资产双路径并存 | 同一配置族可能既走 API，又走本地 daily/instruments 资产 | 同模板不同运行方式结果漂移，复现困难 | 在配置中显式声明资产路径，分离 `cache_tag`，记录数据来源摘要 |
| L4 可复现运维层 | 研究工具链与资产工具链编排 | `grid/sweep/summarize` 与 `mirror/build/backup` 都是长链路 | 半途失败、汇总不完整、资产和 run 错配 | `continue-on-error`、状态落盘、快照归档、分层 playbook |

判断标准：

* L1-L2 偏“能不能做对”。
* L3 偏“回测是否接近可执行现实”。
* L4 偏“是否可长期维护、复现和审计”。

## 三、工时重估（按人天）

口径说明：

* 1 人天 = 8 小时。
* 估算针对单人开发，具备 Python + 量化研究工程经验。
* 默认数据权限/配额已就绪，不含 OMS/自动交易系统改造。
* 本页工时是当前范围的粗粒度规划估算。
* 当前范围已包含研究主链路、HK 资产镜像/派生工具和基础运维辅助。

### 1) 自下而上拆分（当前范围）

| 工作包 | 主要内容 | 估算（人天） |
| --- | --- | --- |
| 基础工程骨架 | CLI、配置解析、日志、目录约定 | 4-8 |
| 数据与 provider | 多源适配、字段标准化、缓存、重试 | 8-14 |
| Universe 与研究样本 | PIT 处理、指数成分、港股通构建、全市场 by-date 口径 | 6-12 |
| 标签与特征 | 标签口径、技术特征、横截面变换、缺失处理 | 8-14 |
| 建模与评估 | 多模型、CV/IC、稳健性检验 | 8-16 |
| 回测与持仓消费 | 成本、退出、buffer、持仓与 live 产物 | 8-16 |
| 研究编排工具 | `grid/sweep-linear/summarize` | 6-12 |
| 数据资产镜像与派生工具 | `mirror-hk-*`、`build-hk-pit-fundamentals`、`build-hk-industry-labels`、覆盖率检查 | 8-16 |
| 运维/备份/兼容辅助 | `backup-data`、token/quota/info 工具 | 3-6 |
| 测试与回归 | 单测、集成测试、修复迭代 | 9-18 |
| 文档与示例 | README + docs + playbooks | 4-8 |
| 小计 |  | 72-140 |
| 风险缓冲 | API 波动、数据修订、需求返工、资产链路返工（20%-30%） | 16-42 |
| 合计 | 当前项目范围总量级 | 88-182 人天 |

### 2) 三档预算（更便于立项）

| 档位 | 范围定义 | 重估（人天） |
| --- | --- | --- |
| 基础可用版 | 单市场、单 provider、主流程可跑、核心产物齐全，少量资产准备工具可用 | 30-50 |
| 可复现研究版 | 多市场/多 provider、PIT、稳健评估、本地资产对齐、较完整测试与文档 | 60-100 |
| 准生产运维版 | 在研究版上补资产镜像/派生、备份/审计、失败恢复、稳定批处理 | 100-160 |

扩展说明（不在当前项目边界内）：

* 若要补齐券商接入 + 下单 + 回执 + 执行风控闭环，通常还需额外 60-120 人天，取决于券商/OMS 复杂度。

### 3) 工时倍率因子（为什么会比预期更长）

* 每新增 1 个市场：总工时通常增加 15%-25%。
* 每新增 1 个 provider：总工时通常增加 20%-35%。
* 若要求强可复现（固定数据快照、严格审计）：增加 20%-40%。
* 若要求长期维护离线资产快照、`latest` 命名和派生链路：增加 15%-30%。
* 若要求准实盘稳定性（定时任务、失败恢复、告警闭环）：增加 25%-50%。

## 结论

* 当前项目是研究主链路 + HK 数据资产工具 + 运维辅助的组合体。
* 最主要的工程成本在数据一致性、泄漏防控、回测语义、资产谱系和双路径复现。
* 以人天口径，项目级预算通常应按 60 人天以上（可复现研究目标）准备；若要长期稳定维护资产与批处理，应按 100 人天以上准备。
