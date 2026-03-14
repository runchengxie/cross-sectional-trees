# AGENTS.md

本文件给仓库维护者、外部贡献者和代码代理使用。它说明协作规则，不替代用户文档。

用户入口仍然是：

* `README.md`
* `docs/README.md`

## 先看什么

开始改动前，先确认你在改哪一层内容：

* 项目总览与快速开始：`README.md`
* 文档首页与阅读顺序：`docs/README.md`
* CLI 参数：`docs/cli.md`
* 配置键与默认行为：`docs/config.md`
* 输出文件与字段：`docs/outputs.md`
* 数据源差异：`docs/providers.md`
* 排障：`docs/troubleshooting.md`
* 开发与测试：`docs/dev.md`
* 内部规划资料：`docs/internal/full_function.md`

## 常用命令

推荐使用 `uv`：

```bash
uv venv --seed
uv sync --extra dev
uv run pytest
```

如需 RQData 相关功能：

```bash
uv sync --extra dev --extra rqdata
```

## 文档维护规则

保持入口清晰，不要把同一段说明复制到多个文件。

* `README.md` 只放项目定位、快速开始、最常用入口和文档导航。
* `docs/README.md` 是 `docs/` 的首页。
* `docs/cli.md` 维护命令和参数，不在 `README.md` 里重复展开。
* `docs/config.md` 维护配置说明，不在排障文档里复制大段配置解释。
* `docs/outputs.md` 维护产物和字段约定。
* `docs/troubleshooting.md` 只保留问题现象、原因和处理步骤。

如果你改了下面这些内容，请同步更新对应文档：

* 新增或修改 CLI 命令：更新 `docs/cli.md`，必要时在 `README.md` 增补入口级示例。
* 新增或修改配置键、默认值、兼容规则：更新 `docs/config.md`。
* 修改输出目录、文件名、`summary.json` 结构或持仓字段：更新 `docs/outputs.md`。
* 修改 provider、symbol 规则、日期 token 行为：更新 `docs/providers.md`，必要时补 `docs/troubleshooting.md`。
* 修改开发流程、测试命令或依赖安装方式：更新 `docs/dev.md`。

## 配置与研究约定

* `config.used.yml` 是每次 run 的实际生效配置，应优先用于复现。
* 配置目录已重构为 `configs/` 结构：
  * `configs/presets/` - 内置预设（market 默认配置）
  * `configs/experiments/` - 研究实验配置
  * `configs/experiments/baseline/` - 基线配置
  * `configs/experiments/variants/` - 模型变体配置
  * `configs/experiments/sweeps/` - 批量实验配置
  * `configs/local/` - 本地覆盖配置（gitignored）
* 支持 `extends` 机制减少配置复制，参考 `configs/catalog.csv` 索引表。
* 研究对比时，优先保持 `universe`、`label`、`features`、`eval`、`backtest` 不变，只替换模型相关参数。
* HK 线性模型批跑优先使用 `configs/experiments/baseline/hk_selected.yml` 作为基线配置。
* HK 默认研究模板使用港股通 PIT universe；这只是仓库内置研究口径，不等于 provider 的港股覆盖边界。
* 输出目录默认是 `artifacts/runs/<run_name>_<timestamp>_<hash>/`。
* 看结果时，先读 `summary.json`、`config.used.yml` 和持仓文件。
* 线性模型汇总时，优先排除或单独标记 `flag_constant_prediction=true`、`flag_zero_feature_importance=true` 的退化 run。
* 并行维护 `frozen` 与 `rolling` 数据窗口时，优先用不同的 `data.cache_tag` 隔离缓存。

## 数据目录约定

* 原始数据缓存：`artifacts/cache/` - 运行时缓存，可删除重建
* 元数据：`artifacts/metadata/` - universe membership、symbol 映射等
* 研究结果：`artifacts/runs/` - 实验运行输出
* 详见 `artifacts/metadata/dataset_registry.csv` 数据集索引。

## 编辑与验证

* 搜索优先用 `rg`。
* 优先做小范围改动，避免顺手重写无关文件。
* 不要提交 `artifacts/`、旧 `out/`、缓存文件或临时实验产物，除非任务明确要求。
* 文档改动至少检查交叉引用和路径是否仍然有效。
* 代码改动后，运行与改动范围匹配的测试。
* HK + RQData 相关改动，至少考虑回归：`tests/test_summarize_runs.py`、`tests/test_pipeline_filters.py`、`tests/test_fundamentals_providers.py`、`tests/test_data_providers_cache.py`。

## 说明

如果某条协作规则和用户任务冲突，以用户的明确要求为准。若规则需要长期变化，请同时更新本文件。
