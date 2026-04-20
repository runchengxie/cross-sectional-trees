# 开发与测试

本文档的核心目标：说明开发环境搭建、测试分层策略以及相关的回归测试入口。
本文档的范围限制：不涉及对具体研究流程与量化业务概念的深入探讨。
目标读者：需要贡献代码或维护测试用例的开发者。
阅读收益：能够获取本地开发与测试的最短实践路径。
相关页面：`README.md`、`docs/cookbook.md`、`docs/config.md`

## 环境准备

推荐使用 `uv` 进行环境管理：

```bash
uv venv --seed
uv sync --extra dev
```

如需调用 RQData 相关能力：

```bash
uv sync --extra dev --extra rqdata
```

如需支持 `csml alloc-hk --format xlsx` 输出：

```bash
uv sync --extra dev --extra rqdata --extra liveops-hk
```

如需启用 DuckDB 数据查询层：

```bash
uv sync --extra dev --extra duckdb
```

如需完整的统计检验功能（例如计算 `p_value` 等）：

```bash
uv sync --extra dev --extra stats
```

## 本地运行策略

```bash
csml run --config default
```

在本地调试时，建议先配置较短的日期区间，确认整个 pipeline 能够顺利跑通后，再逐步放大测试样本的观察窗口。

补充说明：

* `default` 目前默认指向 HK starter 模板。
* 在运行 `default` 或 `hk` 模板前，请确保已经通过 `--extra rqdata` 安装了必要的数据源依赖。
* `configs/presets/hk.yml` 定义了 HK 月频 starter 路线：包含了 PIT 股票池（PIT universe）与远端（provider）基本面数据。
* `configs/presets/hk_quarterly_pit_hybrid.yml` 才是真正的 HK 季频 PIT 基本面（PIT fundamentals）入口。
* 位于 `configs/experiments/baseline/` 以及 `configs/experiments/variants/` 目录下的 HK selected 官方模板，主要是建立在季度 PIT 路线的基础之上。
* 日常开发请优先验证 `default`、`hk` 以及 HK selected 等核心路线；当前仓库原则上不再维护其他的非 HK 主线逻辑。

## 测试框架与命令

项目统一使用 `pytest` 框架。为了方便在本地收集错误、定点排查以及拆分回归测试，默认的测试入口不再强制要求计算 coverage。

```bash
scripts/dev/run_tests.sh all
```

请注意，`scripts/dev/run_tests.sh all` 仅覆盖 `pytest` 主测试集，其结果不完全等同于在 CI 环境下的完整复现。

常见测试用法概览：

```bash
# 仅执行特定的测试文件
uv run pytest tests/test_metrics.py

# 适用于日常高频执行的快速回归测试
scripts/dev/run_tests.sh fast

# fast 测试的等效别名
scripts/dev/run_tests.sh unit

# 包含较重运算的离线回归测试
scripts/dev/run_tests.sh slow

# 运行集成测试
scripts/dev/run_tests.sh integration

# 若需收集覆盖率报告，请显式执行该命令
scripts/dev/run_tests.sh coverage

# 执行 Ruff lint 与基础复杂度检查，并针对本次改动的 Python 文件执行 import 排序检查
scripts/dev/run_tests.sh lint

# 执行全仓库级别的 import 排序检查（历史遗留文件可能仍包含未清理的债务）
scripts/dev/run_tests.sh imports

# 使用 Ruff formatter 仅检查本次发生改动的 Python 文件
scripts/dev/run_tests.sh format

# 执行全仓库级别的 formatter 检查（历史遗留文件可能仍包含未清理的债务）
scripts/dev/run_tests.sh format-all

# 运行真实的 provider 集成联调测试（必须显式启用，并提前配置好对应的 token 或账号）
CSML_RUN_PROVIDER_INTEGRATION=1 uv run pytest tests/test_provider_integration.py -m integration
```

## 本地 Git Hooks 设定

如果你希望在执行 `commit` 或 `push` 前自动触发一层本地代码检查，可以安装仓库内预置的 hooks：

```bash
./scripts/dev/install_git_hooks.sh
```

安装后的默认触发行为如下：

| hook 名称 | 执行的命令 | 核心作用 |
| --- | --- | --- |
| `pre-commit` | `uv run pytest tests/test_docs_contracts.py tests/test_repo_path_references.py tests/test_run_tests_script.py -q` | 提前拦截并暴露文档契约、引用路径及测试入口配置方面的问题 |
| `pre-push` | `scripts/dev/run_tests.sh fast` | 确保在推送代码至远端前先完整跑通一遍离线的快回归集 |

补充说明：

* 本地 hook 的初衷在于将问题发现前置，它并不能替代远端 CI 的最终校验。
* 如遇特殊情况需要跳过本次检查，可追加使用 `git commit --no-verify` 或 `git push --no-verify` 参数。
* Ruff 引擎已经启用了 formatter 格式化、import 排序以及基础代码复杂度检查功能。`lint` 流程将在全仓库范围内拦截高风险语法错误与未登记的新增高复杂函数，并会对本次改动的 Python 文件执行严格的 import 排序检查。对于全仓库范围的历史 import 和 format 遗留债务，仍可通过 `imports` 与 `format-all` 命令单独盘点。
* 当前已知的复杂度历史债务已集中登记在 `pyproject.toml` 的 `per-file-ignores` 段落中。后续若完成了代码拆分优化，应逐个撤销相应的规则豁免。
* `tests/test_docs_contracts.py` 现已收紧校验规则，仅接受指向仓库内部受版本控制目标的 Markdown 相对链接。当在研究笔记中需要引用本地 `artifacts/...` 等运行期临时产物时，请使用纯文本代码块的形式记录，切勿将其写成可点击的相对链接。

执行逻辑说明：

* `scripts/dev/run_tests.sh integration` 专门运行打上了 `@pytest.mark.integration` 标记的跨模块流程测试集，该集默认仍以本地离线的跨模块集成验证为主。
* 尽管 `tests/test_provider_integration.py` 同样带有 `integration` 标记，但如果在环境变量中未设定 `CSML_RUN_PROVIDER_INTEGRATION=1`，该测试将自动跳过。因此，“集成测试”一词并不绝对等同于真实的 provider 在线联调。
* 针对文档引用以及公开入口的契约有效性，当前已部署了测试用例进行兜底保障。相关逻辑主要体现于 `tests/test_docs_contracts.py` 和 `tests/test_run_tests_script.py` 中。

## HK 资产健康检查脚本应用

在日常维护 current 资产时，建议优先使用轻量级的专属刷新脚本，而非手工拼凑庞大的完整工作流（workflow）：

```bash
bash scripts/dev/refresh_hk_current.sh --target-date 20260410
```

默认执行逻辑：

* 仅顺序执行 `refresh + inspect` 环节，并不会自动触发数据的打包或 GitHub Release 发布。
* 固定采用 `--refresh-mode patch` 模式，即优先针对支持的资产进行尾部窗口数据抓取，然后再于本地进行 merge 合并。
* 默认绑定 `--resume`、`--gate-on-severity warning` 及 `--inspect-fail-on-severity none` 约束条件。
* 当 inspect 诊断出的瑕疵达到或超过阻断阈值时，底层 workflow 会拦截 latest/current 别名的放行操作，并最终以非零错误状态退出执行。

常见变体指令：

```bash
# 在 inspect 顺利通过后，额外打包当前资产的 parts 碎片
bash scripts/dev/refresh_hk_current.sh --target-date 20260410 --with-package

# 针对重要时间节点，将 current 的状态冻结为一份本地独立备份
bash scripts/dev/refresh_hk_current.sh \
  --target-date 20260410 \
  --backup-name hk_current_frozen_20260410

# 仅针对部分支持 patch 模式的资产类型执行刷新
bash scripts/dev/refresh_hk_current.sh \
  --target-date 20260410 \
  -- --refresh-asset daily --refresh-asset valuation
```

此脚本仅是针对 `scripts/internal/run_hk_asset_workflow.py` 引擎的一层保守封装，其本身并未改变底层 maintainer workflow 的任何兼容默认值。若有需要执行完整的整包重拉、repair 修复、release 发布，或是实施更细粒度的 part 分片控制，请继续直接调用底层的维护者 driver。

若仅需要将本地的 HK 与 RQData 资产健康检查全部跑完，并将结果统一归档至 `artifacts/reports/` 目录下，优先推荐使用：

```bash
bash scripts/dev/run_hk_health_checks.sh --target-date 20260409
```

常见变体指令：

```bash
# 同步增加针对 intraday 分钟级别数据的检查
bash scripts/dev/run_hk_health_checks.sh --target-date 20260409 --with-intraday

# 额外促成一份维护者视角的 workflow inspect report
bash scripts/dev/run_hk_health_checks.sh --target-date 20260409 --with-workflow-inspect
```

执行逻辑说明：

* 这些指令并非开放给最终用户的 `csml` CLI 功能，而是专供本地运维与调试使用的辅助脚本。
* 脚本会优先从 `artifacts/metadata/current_assets/hk_current.json` 契约文件中解析出当下正使用的 `daily_clean`、`valuation` 和 `intraday` 具体路径。
* 默认将同时产出 `current`、`daily_clean`、`valuation`、`pit` 四份独立的 JSON 健康报告，并将产生的 stdout 与 stderr 日志流分别留存于 `artifacts/reports/health_logs/` 中。
* 关于逐条执行的手动命令详情，以及阅读这些 report 的标准顺序，请参阅 `docs/rqdata/hk-health-checks.md` 指南。

若需要严格按照 current contract 契约，执行一次综合性的“资产清单梳理 + 数据新鲜度查验 + repair 候选甄别 + prune 删除动作试运行（dry-run）”统一审计，请优先执行：

```bash
bash scripts/dev/run_hk_data_asset_audit.sh --target-date 20260410
```

执行逻辑说明：

* 该工具实质为 `csml rqdata inspect-hk-data-assets` 命令的本地化封装。其默认处于只读和 dry-run 状态，绝不主动引发任何 refresh、repair 或 delete 实体操作。
* 默认产出结果位于 `artifacts/reports/hk_data_asset_audit_<date>.json`，极为适合在启动大规模重数据清洗之前，先交由系统维护者或代理程序进行前置复核。
* 倘若确实需要联动开启 patch refresh 流程，请先附加上 `--run-refresh` 参数以保持在 dry-run 状态；在人工或系统确认无误后，再显式追回 `--refresh-execute` 参数以推动实质性变更。

## HK 资产维护 Driver 详解

对于专注于 HK 市场与 RQData 接口底层的资产数据维护人员（而非从事日常因子研究或 pipeline 流程开发的人员），可直接调用这套深度的维护者 driver 脚本：

```bash
python scripts/internal/run_hk_asset_workflow.py --target-date 20260402
```

该命令默认会自动串联并执行以下三大核心阶段：

* `refresh` 阶段：依次刷新 `instruments / daily / daily_clean / valuation / ex_factors / dividends / shares / industry_changes / southbound` 等各类基础资产。
* `inspect` 阶段：执行全方位健康诊断，并将诊断报告统一投递写入 `artifacts/reports/` 目录。
* `package` 阶段：将本次 run 解析锚定后的 snapshot 移交送入 `csml.release_tools.package_assets` 组件实施打包处理。

常见变体指令：

```bash
# 仅预览完整的命令执行计划，不触发任何实际数据操作
python scripts/internal/run_hk_asset_workflow.py --target-date 20260402 --dry-run

# 仅接续由于中断未完成的镜像拉取任务，略过后续的体检与打包动作
python scripts/internal/run_hk_asset_workflow.py --phase refresh --target-date 20260402 --resume

# 日常高频维护建议启用 patch 模式：仅向后抓取最近的尾部增量窗口，然后在本地完成 merge 操作拼合成全新的 refreshed snapshot
python scripts/internal/run_hk_asset_workflow.py --phase refresh --target-date 20260402 --refresh-mode patch --resume

# 摄取上轮 inspect 遗留的 repair_candidates 清单，专门针对 warning 或 error 级别的瑕疵发动子集重拉修复
python scripts/internal/run_hk_asset_workflow.py --phase repair --target-date 20260402 --repair-asset daily

# 强制解除 workflow 的阻断门控（gate），回退到“仅记录 inspect 报告，但不拦截卡死后续发布步骤”的模式
python scripts/internal/run_hk_asset_workflow.py --target-date 20260402 --gate-on-severity none

# 依托现有的 package 资产包，直接追加执行 GitHub release 发布推送流程
python scripts/internal/run_hk_asset_workflow.py --phase release --target-date 20260402 --repo owner/name --prerelease
```

执行逻辑说明：

* 该入口属于专职的数据维护者脚本，切勿与公开的 `csml` 业务主 CLI 相混淆。
* 其自身主要承担轻量级的编排中枢功能；关于底层实质的数据抓取、健康检查、打包及 release 推送逻辑，依然分别落脚于现有的各自独立命令集中。
* 在 `refresh` 顺利完成之后，它默认会自动将通用别名 `latest` 重定向回指新资产；如果你仅仅是想派生一份 dated snapshot 留存，并不打算影响当前主线使用的 alias，请加上 `--no-repoint-latest` 选项。
* 设定 `--refresh-mode full` 将延续原汁原味的整包完全重拉语义；若转为 `--refresh-mode patch`，则针对 `daily`、`valuation`、`ex_factors`、`dividends` 及 `shares` 这几类高频资产，系统会先请求拉取近期数据的 patch 包，继而唤起本地的 patch merge 算法融合出崭新的 canonical snapshot。
* patch 模式的默认回溯长度为：`daily` 回看最近 20 个日历日，其余支持增量更新的 dated assets 统筹回看 40 个日历日。可通过设定 `--daily-patch-lookback-days` 与 `--dated-patch-lookback-days` 来调节各自的窗口尺度。
* 在每一次非 dry-run 的实质执行中，系统将额外编撰出一份结构化的 workflow report，默认归档至 `artifacts/reports/hk_asset_refresh_<target_date>.json`。如需变更存储位置可传入 `--workflow-report` 参数指明路径。
* 同一轮非 dry-run 的 workflow 执行还会同步刷新 `artifacts/metadata/current_assets/hk_current.json` 契约，将当前最新生成的 HK 资产 alias、对应的 resolved snapshot 文件实体、manifest 摘要数据乃至 `as_of` 时点等关键线索，悉数固化进这份轻量级的 current contract 之中。这不仅利于后续交付给 `package_assets --preset hk_current` 运用，也保障了 run 侧数据输入的绝对锁定复用。
* 程序的出厂设定包含 `--gate-on-severity warning` 这一安全底线。当此轮作业涵盖了 `inspect` 检查且其汇总严重级别触及设定的告警阈值时，由 refresh 或是 repair 触发的 `latest` alias 重新指派动作将遭到坚决阻断，随后的 `package` 或 `release` 也会被当即跳过，workflow 全局最终以非零的失败状态收场。
* 若仅单跑 `inspect` 实施常规体检而并不带有后续的推进 phase 时，并不会触发上述的 workflow 刚性门控限制；此时它的本质仍旧只是为了生成和记录 report。
* `repair` 阶段专司读取先存的 workflow report 中蕴含的 `inspect.assets.<asset>.repair_candidates` 指导项，生成经按 `symbol/date` 精简收缩后的问题子集执行点对点重拉并执行 patch merge 缝合；默认操作范畴仅囊括 `warning` 和 `error` 等级的故障，如需将其向下放宽辐射至 `info` 级通报，请配上 `--repair-min-severity` 选项。
* 默认情况下，`repair` 还会恪尽职守地对业已完成修补的资产触发一轮 `post_repair` 级别的自动回归复检（inspect）。其后的流程是否放行 alias 重新指派、package 打包或 release，将铁面无私地仅以这轮复检的体检结果为准绳。若执意退回旧版无复检的流转行为，请显式携带 `--no-repair-rerun-inspect`。
* repair 运行全程还会并行输出两份简明 JSON 纪要日志：其一为 `artifacts/reports/hk_asset_repair_queue_<target_date>.json`，专用于真实记录本轮投入修补的 `symbol/date/window` 实际干预队列；另一为 `artifacts/reports/hk_asset_remaining_repair_candidates_<target_date>.json`，它忠实记录了经历复检之后依然根深蒂固未能拔除的顽固候选项。
* 倘若你仅仅期望跟进处理上一轮 repair 后悬而未决的顽固候选项，请启用 `--repair-only-unresolved` 选项；系统将优先锁定读取源头 source report 中的 `repair.remaining_candidates` 残留集，当其不存在时再行退回搜刮 `inspect.assets.<asset>.post_repair_repair_candidates`。
* `repair` 逻辑被构想定义成“第二动补救工序”。合理的排障次序应当是：先跑通一轮完整的含有 `inspect` 的 workflow 逼迫出详细确凿的 report 伤单，接着再单独召唤 `--phase repair` 命令展开按图索骥的手术刀式修洞。

### 测试矩阵维度剖析

| 执行入口 / 模式 | 默认覆盖范畴 | 明确排除的范畴 | 额外前置依赖或凭证 | 对应 CI 流水线的关系映射 |
| --- | --- | --- | --- | --- |
| `scripts/dev/run_tests.sh all` | 执行主流 `pytest` 常规测试全集 | 隔离全部四项 optional extra smoke，以及未显式启用的真实 provider 联调 | 依赖 `uv sync --extra dev` | 仅覆盖主测试集，不代表完整 CI |
| `scripts/dev/run_tests.sh fast` 或 `unit` | 涵盖带有 `not integration and not slow` 标识的离线轻量快回归用例 | 剔除 `slow`、`integration`、全部 extra smoke 以及真实 provider 联调 | 依赖 `uv sync --extra dev` | 对应 CI 环节下的 `fast` job |
| `scripts/dev/run_tests.sh slow` | 锁定带有 `@pytest.mark.slow` 标签的离线回归集 | 剔除 `fast`、`integration`、全部 extra smoke 以及真实 provider 联调 | 依赖 `uv sync --extra dev` | 对应 CI 环节下的 `slow` job |
| `scripts/dev/run_tests.sh integration` | 锁定带有 `@pytest.mark.integration` 的跨模块流程测试集 | 隔离四项 optional extra smoke；在缺乏显式开启时，涉及真实 provider 的测试会被跳过 | 依赖 `uv sync --extra dev` | 对应 CI 下的 `integration` job，默认以本地离线为主 |
| `scripts/dev/run_tests.sh coverage` | 测试覆盖范围同 `all`，但注入了代码覆盖率统计 | 隔离全部四项 optional extra smoke，以及未显式启用的真实 provider 联调 | 依赖 `uv sync --extra dev` | 方便本地查看覆盖率，不代表通过完整 CI |
| `CSML_RUN_PROVIDER_INTEGRATION=1 uv run pytest tests/test_provider_integration.py -m integration` | 验证真实 HK + RQData provider 的数据提取 | 排斥其他所有常规测试集用例与 extra smoke | 需挂载 `--extra rqdata`，且配置真实授权账号与 token | 不包含在默认 CI 流水线与 `run_tests.sh all` 中 |
| `rqdata-extra-smoke` / `duckdb-extra-smoke` / `liveops-hk-extra-smoke` / `stats-extra-smoke` | 验证 optional extra 的安装、导入及基础调用 | 屏蔽主 `pytest` 测试集 | 要求分别预装各自指代的额外依赖包 | 此四大分支专享于 CI 独立执行；本地需显式运行对应的补充验证 |

## 测试分层设计约定

建议遵循以下分层约束来维护测试体系，避免将离线回归与端到端验证混杂：

1. `unit`（日常回归）：应保持离线执行，杜绝依赖外部账户授权、网络连通性及真实的外部行情接口。
2. `integration`：用于校验跨模块间的协作流程（允许容纳执行耗时较长或依赖较重 fixture 的测试场景）。
3. `slow`：属于离线闭环测试，由于计算负担较重而单独分离。目前主要包含 `tests/test_pipeline_filters_*.py` 等用例，这些用例会反复拉起 pipeline 运转，因此被单独切分以便于本地或 CI 环境中独立执行。

推荐的常规运行命令：

```bash
# 执行日常快回归（鼓励在本地高频执行）
scripts/dev/run_tests.sh fast

# 执行计算量较重的纯离线回归
scripts/dev/run_tests.sh slow

# 专注于模块集成验证
scripts/dev/run_tests.sh integration
```

## GitHub Actions CI 架构解读

目前本仓库已启用基于 GitHub Actions 的流程编排，配置文件位于 `.github/workflows/tests.yml`。

在默认配置下，CI 流水线被逻辑切分为七个独立的 job：

1. `fast`：运行 `scripts/dev/run_tests.sh fast`。
2. `slow`：运行 `scripts/dev/run_tests.sh slow`。
3. `integration`：运行 `scripts/dev/run_tests.sh integration`。
4. `rqdata-extra-smoke`：安装 `--extra rqdata` 附加组件，验证该 optional extra 体系能否被正确导入，并测试 `csml rqdata --help`。
5. `duckdb-extra-smoke`：安装 `--extra duckdb` 附加组件，验证可选包状态及最小 DuckDB query 执行。
6. `liveops-hk-extra-smoke`：安装 `--extra liveops-hk` 附加组件，验证对 `openpyxl` 的支持，确认 xlsx 文件的基本写入能力。
7. `stats-extra-smoke`：安装 `--extra stats` 附加组件，检验 `scipy` 包导入及 `summarize_ic` 计算引擎的基础调用。

这种松耦合的设计使得常规离线回归、较重离线处理、跨模块流程验证以及 optional extra 组件的烟雾检查都能保持独立。当某段执行失败时，开发者可以更便捷地在本地独立复现问题。

若需在本地完整模拟 CI 的测试强度，除了运行 `all` / `fast` / `slow` / `integration`，还需手动执行上述四部分 optional extra smoke 验证：

```bash
# 对应的 rqdata-extra-smoke 执行策略
uv sync --locked --extra dev --extra rqdata
uv run python -c "import rqdatac; print(rqdatac.__name__)"
uv run csml rqdata --help > /dev/null

# 对应的 duckdb-extra-smoke 执行策略
uv sync --locked --extra dev --extra duckdb
uv run python -c "import duckdb; print(duckdb.__version__)"
uv run csml data query --sql "select 1 as value" > /dev/null

# 对应的 liveops-hk-extra-smoke 执行策略
uv sync --locked --extra dev --extra liveops-hk
uv run python -c "import openpyxl; print(openpyxl.__version__)"
uv run python -c "from pathlib import Path; import pandas as pd; from csml.liveops.alloc_hk import write_xlsx_report; out = Path('/tmp/alloc_hk_smoke.xlsx'); write_xlsx_report(out, pd.DataFrame([{'symbol': '0001.HK'}]), pd.DataFrame([{'as_of': '2026-03-20'}]), pd.DataFrame([{'symbol': '0001.HK'}])); assert out.exists() and out.stat().st_size > 0"

# 对应的 stats-extra-smoke 执行策略
uv sync --locked --extra dev --extra stats
uv run python -c "import scipy; print(scipy.__version__)"
uv run python -c "import pandas as pd; from csml.metrics import summarize_ic; series = pd.Series([0.1, -0.1, 0.2]); stats = summarize_ic(series); assert 'p_value' in stats and stats['p_value'] == stats['p_value']"
```

近期针对涉及 HK + RQData 重构的高频回归测试时，建议至少覆盖下列测试集：

```bash
scripts/dev/run_tests.sh all \
  tests/test_pipeline_validation.py \
  tests/test_summarize_runs.py \
  tests/test_pipeline_filters_*.py \
  tests/test_fundamentals_providers.py \
  tests/rqdata_assets/ \
  tests/test_universe_tools.py \
  tests/test_cli_core.py \
  tests/test_cli_rqdata.py \
  tests/test_cli_research.py \
  tests/test_cli_liveops.py \
  tests/test_linear_sweep.py \
  tests/test_data_providers_cache.py \
  -q
```

### 季度 provider 与 PIT 路线测试重点

如果你修改了诸如 `configs/experiments/baseline/hk_selected__quarterly_price_only.yml`、`configs/experiments/baseline/hk_selected__quarterly_pit_core.yml`、`configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml`、`configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_*.yml`，或更深层的 `configs/experiments/variants/hk_selected__pit_quarterly_financial_ml.yml`、`configs/experiments/variants/hk_selected__pit_quarterly_financial_linear.yml`、`configs/experiments/variants/hk_selected__pit_quarterly_hybrid.yml` 及其底层 pipeline 逻辑，建议至少了解以下几组测试：

1. `tests/test_pipeline_validation.py`：配置模板的安全验证墙，主要校验季度模板中 `label/eval/backtest.rebalance_frequency` 的调仓频率是否一致，以及 `fundamentals.source` 的指定是否存在错误。
2. `tests/` 下的 `test_pipeline_filters_*.py` 测试组：覆盖 provider/file 两路基本面合并、PIT 文件读取、披露日后的 ffill，以及慢财报派生因子是否按披露节奏生效。
3. `tests/test_fundamentals_providers.py`：验证 HK + RQData provider 基本面抓取、数据标准化和缓存键行为。
4. `tests/rqdata_assets/`：全面验证 `mirror-hk-pit-financials` 及 `build-hk-pit-fundamentals` 等操作，包括覆盖率（coverage）检查与质量健康度（health）筛查等预处理流程。
5. `tests/test_universe_tools.py`：验证港股通 universe 构建脚本的日期 token、输出路径和流动性筛选边界。
6. `tests/test_cli_rqdata.py` 和 `tests/test_cli_research.py`：测试 PIT 资产命令和 sweep-linear 命令的参数解析。
7. `tests/test_linear_sweep.py`：验证季度 PIT 线性 sweep 配置能否正确读取，以及生成的 jobs 和 base config 是否匹配。
8. `tests/test_data_providers_cache.py`：测试 RQData 日线缓存、上市日裁剪和空区间处理，确保低频研究不被异常缓存干扰。
9. `tests/test_summarize_runs.py`：验证 summary.json 的下游汇总字段是否完整，特别是 backtest.active 的 benchmark 指标能否正确进入 runs_summary.csv。

## 修改模块与对应测试指南

下表说明在修改特定模块时，提交前最少应该先运行哪几组测试。

| 你所修改的模块边界 | 提交前至少应运行的测试 | 建议补充运行的测试 |
| --- | --- | --- |
| CLI 命令行、参数解析、wrapper 转发逻辑 | `tests/test_cli_core.py`、`tests/test_cli_rqdata.py`、`tests/test_cli_research.py`、`tests/test_cli_liveops.py` | `scripts/dev/run_tests.sh fast` |
| 文档更新、README.md、docs/ 目录及 workflow 说明修改 | `tests/test_docs_contracts.py`、`tests/test_repo_path_references.py`、`tests/test_run_tests_script.py` | `scripts/dev/run_tests.sh fast` |
| `scripts/dev/run_tests.sh` 脚本及 CI 测试入口逻辑 | `tests/test_run_tests_script.py`、`tests/test_docs_contracts.py` | 完整运行 `fast` / `slow` / `integration`，或针对性的 smoke 测试 |
| release_tools 打包工具或 Release 预演逻辑 | `tests/test_asset_release_scripts.py`、`tests/test_run_release_scripts.py` | 针对相关脚本的最小打包 smoke 测试 |
| csml data query、metadata catalog 或 standardized layer | `tests/test_data_warehouse.py`、`tests/test_cli_core.py` | 本地手动运行一次 `csml data query --sql "select 1 as value"` |
| alloc-hk、liveops-hk 调度逻辑及 xlsx 输出功能 | `tests/test_alloc_hk.py`、`tests/test_cli_liveops.py` | 安装 `uv sync --extra dev --extra liveops-hk` 并补充 xlsx 输出的最小 smoke 测试 |
| HK + RQData provider、PIT fundamentals 或 universe 规则构建 | `tests/test_pipeline_validation.py`、`tests/test_pipeline_filters_*.py`、`tests/test_fundamentals_providers.py`、`tests/rqdata_assets/`、`tests/test_universe_tools.py` 与 `tests/test_data_providers_cache.py` | `tests/test_summarize_runs.py`、`tests/test_linear_sweep.py` |
| intraday 数据、patch merge 逻辑、provider overlay audit 或 financial details 分析 | `tests/test_hk_intraday_download.py`、`tests/test_hk_intraday_tools.py`、`tests/test_hk_asset_patch_merge.py`、`tests/test_audit_provider_valuation.py`、`tests/test_hk_financial_details_analysis.py` | 在本地按照对应 playbook 中的指令进行 smoke 测试验证 |

## 提交前检查建议

1. 至少运行一次 `scripts/dev/run_tests.sh all`。
2. 使用修改后的配置运行一次 `csml run --config ...`。
3. 检查 `README.md` 与 `docs/` 目录下的文档是否同步更新。

## 贡献入口

如需提交 PR，请同时附上：

1. 变更动机与影响范围。
2. 新增或修改的配置项说明。
3. 回归验证方式（测试命令与关键产物）。