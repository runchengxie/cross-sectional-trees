# AGENTS.md

本文件给仓库维护者、外部贡献者和代码代理使用。它说明协作规则，不替代用户文档。

用户入口仍然是：

* `README.md`
* `docs/README.md`

## 先看什么

开始改动前，先确认你在改哪一层内容：

* 项目总览与快速开始：`README.md`
* 文档首页与阅读顺序：`docs/README.md`
* 最短跑通路径：`docs/get-started.md`
* 项目能力地图与公开边界：`docs/capabilities.md`
* CLI 参数：`docs/cli.md`
* 配置键与默认行为：`docs/config.md`
* 输出文件与字段：`docs/outputs.md`
* 数据源差异：`docs/providers.md`
* 排障：`docs/troubleshooting.md`
* 开发与测试：`docs/dev.md`
* 脚本入口清单：`scripts/README.md`
* 内部规划资料：`docs/internal/feature-planning.md`

## 常用命令

推荐使用 `uv`：

```bash
uv venv --seed
uv sync --extra dev
```

日常测试优先使用仓库脚本：

```bash
scripts/dev/run_tests.sh all
scripts/dev/run_tests.sh fast
scripts/dev/run_tests.sh slow
scripts/dev/run_tests.sh integration
scripts/dev/run_tests.sh coverage
scripts/dev/run_tests.sh lint
scripts/dev/run_tests.sh typecheck
scripts/dev/run_tests.sh format
```

`all` 覆盖主 `pytest` 测试集，不包含可选依赖冒烟检查和显式开启的真实 provider 联调；完整 CI 分层以 `docs/dev.md` 为准。

需要定点排查时再直接调用 `uv run python -m pytest tests/...`。

如需 RQData 相关功能：

```bash
uv sync --extra dev --extra rqdata
```

## 文档维护规则

保持入口清晰，不要把同一段说明复制到多个文件。

### 市场称谓与表述口径

文档、注释、报错信息和面向用户的说明文字应使用清晰、稳妥的市场称谓：

* 优先写“中国香港市场”“港股”“港股通”“中国大陆市场”“A 股”等表述。
* 避免把中国大陆市场与中国香港市场写成政治或地域对立关系。
* 面向用户的正文先写业务含义；命令、路径、配置键、资产键和 provider API 示例只用于说明现有接口。
* 文档润色不要顺手重命名公开接口、路径或历史产物；命名变更应单独评估兼容影响。

* `README.md` 只放项目定位、快速开始、最常用入口和文档导航。
* `docs/README.md` 是 `docs/` 的首页。
* `docs/cli.md` 维护命令和参数，不在 `README.md` 里重复展开。
* `docs/config.md` 维护配置说明，不在排障文档里复制大段配置解释。
* `docs/outputs.md` 维护产物和字段约定。
* `docs/troubleshooting.md` 只保留问题现象、原因和处理步骤。
* Markdown 相对链接只指向受版本控制的仓库文件；本地 `artifacts/` 运行产物用代码文本记录，不要写成可点击相对链接。

如果你改了下面这些内容，请同步更新对应文档：

* 新增或修改 CLI 命令：更新 `docs/cli.md`，必要时在 `README.md` 增补入口级示例。
* 修改公开能力边界、主入口分层或 artifact 根目录：更新 `README.md`、`docs/capabilities.md`，必要时同步 `docs/outputs.md`。
* 修改快速开始路径、默认 alias / preset 指向或最短示例：更新 `docs/get-started.md`，必要时同步 `README.md`。
* 新增或修改配置键、默认值、兼容规则：更新 `docs/config.md`。
* 修改输出目录、文件名、`summary.json` 结构或持仓字段：更新 `docs/outputs.md`。
* 修改 provider、symbol 规则、日期 token 行为：更新 `docs/providers.md`，必要时补 `docs/troubleshooting.md`。
* 修改开发流程、测试命令或依赖安装方式：更新 `docs/dev.md` 和 `scripts/README.md`。

## 配置与研究约定

* `config.used.yml` 是每次 run 的实际生效配置，应优先用于复现。
* 配置目录已重构为 `configs/` 结构：
  * `configs/presets/` - 内置预设（market 默认配置）
  * `configs/experiments/` - 研究实验配置
  * `configs/experiments/baseline/` - 基线配置
  * `configs/experiments/variants/` - 模型变体配置
  * `configs/experiments/sweeps/` - 批量实验配置
* `configs/local/` - 本地覆盖配置目录；约定上用于个人文件，默认不纳入版本控制
* 支持 `extends` 机制减少配置复制，参考 `configs/catalog.csv` 索引表。
* 研究对比时，优先保持 `research_universe`、`label`、`features`、`eval`、`backtest` 不变，只替换模型相关参数。
* 港股线性模型批跑优先使用 `configs/experiments/baseline/hk_selected.yml` 作为基线配置。
* 港股默认研究模板使用港股通 PIT universe；这只是仓库内置研究口径，不等于 provider 的港股覆盖边界。
* 输出目录默认是 `artifacts/runs/<run_name>_<timestamp>_<hash>/`。
* 看结果时，先读 `summary.json`、`config.used.yml` 和持仓文件。
* 线性模型汇总时，优先排除或单独标记 `flag_constant_prediction=true`、`flag_zero_feature_importance=true` 的退化 run。
* 并行维护 `frozen` 与 `rolling` 数据窗口时，优先用不同的 `data.cache_tag` 隔离缓存。

## 数据目录约定

* 原始数据缓存：`artifacts/cache/` - 运行时缓存，可删除重建
* Provider 资产与 universe：`artifacts/assets/` - 可复用的原始 / 派生资产镜像
* 元数据：`artifacts/metadata/` - universe membership、symbol 映射、catalog 等
* 标准层：`artifacts/standardized/` - analysis-ready 查询层
* 研究结果：`artifacts/runs/` - 实验运行输出
* Live 运行结果：`artifacts/live_runs/`
* 批跑汇总：`artifacts/sweeps/`
* 数据 / 结果快照：`artifacts/snapshots/`
* 检查 / 健康 / 校准报告：`artifacts/reports/`
* 详见 `artifacts/metadata/dataset_registry.csv` 数据集索引。

## 大数据检查约定

* 对 `artifacts/assets/`、`artifacts/cache/` 下的大型 parquet / `.parts/` 目录，默认不要让代理直接做整块读取后再在会话里展开结果。
* 中国香港市场数据资产健康检查、PIT coverage、current contract 审计和 asset release 已迁到 `market-data-platform`；本仓库只读取其产出的报告或数据文件。
* 对 intraday 数据，优先把正式资产目录或同名 `.parts/` 目录传给检查命令，不要默认直扫合并后的超大 parquet。
* 需要保留检查痕迹时，优先使用 `--format json --out artifacts/reports/<name>.json`，并额外把 stdout / stderr 重定向到日志文件，避免只在交互上下文里看结果。
* 如果检查预计会扫描大量数据或运行很久，优先由用户本地执行命令并把 `artifacts/reports/*.json` 与对应 log 提供给代理复核；不要默认在代理会话里直接重跑整套重 I/O 检查。

## 资源与长任务约定

* 中国香港市场 PIT、full-market assets、monthly live snapshot、sweep / tune、XGBoost ranker 训练都按重任务处理；开始前先确认输入规模、输出目录、是否已有可复用 run，以及机器内存是否足够。
* 在 8GiB 级别内存环境里，不要默认在代理会话中直接跑全量 PIT 宽表 + 完整 research pipeline。优先先做窄列投影、样本 / 日期 smoke、或让用户在本地 shell 中运行完整命令。
* 重任务输出必须落到 `run.log`、`summary.json`、`artifacts/reports/*.json` 这类文件；不要依赖交互上下文保存唯一日志。
* 如果 Codex / shell 会话中断、WSL 重启或命令无 traceback 消失，先取证再决定是否重跑：
  * 查目标 run 目录是否有 `summary.json`、`positions_current*.csv`、`run.log`。
  * 查 `tail -100 <run>/run.log`，确认最后停在哪个阶段。
  * 查 `free -h`、`dmesg -T | tail` 或 cgroup memory 事件，判断是否可能 OOM / 被外层杀进程。
  * 查 `ps` 确认是否仍有残留训练进程。
* 崩溃后不要用“原命令再跑一次”作为第一反应；先降低峰值内存或缩小任务面，例如关闭不必要 artifact、减少宽列读取、复用已生成的小型报告、或拆分 asset 构建与持仓生成。

## 编辑与验证

* 搜索优先用 `rg`。
* 优先做小范围改动，避免顺手重写无关文件。
* 不要提交 `artifacts/`、旧 `out/`、缓存文件或临时实验产物，除非任务明确要求。
* 文档改动至少检查交叉引用和路径是否仍然有效。
* 文档、脚本说明或测试入口改动，优先跑：`uv run python -m pytest tests/test_docs_contracts.py tests/test_repo_path_references.py tests/test_run_tests_script.py -q`。
* 如需在本地提前拦住文档 / 路径 / 快回归问题，可安装仓库内置 git hooks：`./scripts/dev/install_git_hooks.sh`。
* 代码改动后，运行与改动范围匹配的测试。
* 中国香港市场 RQData research provider 相关改动，至少考虑回归：`tests/test_summarize_runs.py`、`tests/` 下的 `test_pipeline_filters_*.py`、`tests/test_pipeline_validation.py`、`tests/test_cli_research.py`；provider/cache/universe 平台行为回归在 `market-data-platform` 对应测试中执行。

## 说明

如果某条协作规则和用户任务冲突，以用户的明确要求为准。若规则需要长期变化，请同时更新本文件。
