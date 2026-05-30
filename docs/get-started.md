# 快速上手

本页解决什么：用最短路径跑通一次完整流程。\
本页不解决什么：不展开配置细节与模型选择。\
适合谁：第一次进入仓库或只想验证环境的人。\
读完你会得到什么：一套可重复的最小跑通流程与产物检查清单。\
相关页面：`README.md`、`docs/cookbook.md`、`docs/cli.md`、`docs/config.md`、`docs/outputs.md`、`docs/providers.md`

## 前置条件

* Python 3.12 及以上版本
* `uv` 包管理器
* 若运行兼容默认模板，需要已由 `market-data-platform` 准备好的本地中国香港市场数据资产；若验证 A 股迁移候选入口，需要准备 `metadata/current_assets/a_share_current.json` 指向的 A 股数据资产

## 最短跑通

```bash
uv venv --seed
uv sync --extra dev
export DATA_PLATFORM_ROOT=/path/to/market-data-platform/artifacts
cstree run --config default
```

默认入口当前仍指向中国香港市场 / RQData / 本地平台资产兼容路线，只读平台资产，不需要 RQData 在线凭证。这个 default 保留用于保护老流程，不代表未来默认研发预算方向。A 股迁移候选入口是 `configs/presets/default_next.yml`，生命周期和 default 切换条件见 `docs/market-lifecycle.md`。需要临时在线读取 provider 数据时，显式设置 `data.source_mode=provider_online_legacy` 并安装 `uv sync --extra dev --extra rqdata`；详情参见 `docs/providers.md` 文件。

`cstree` 是当前 CLI 名称。

注意：`default` 是内置别名，当前会解析到仓库 `configs/` 下的 `configs/presets/default.yml`。
这些内置别名会读取仓库根目录的 `configs/` 文件夹，因此请确保在包含 `configs/` 目录的源码工作区或导出的源码目录内执行命令。

如果你只需要安装基础依赖：

```bash
uv sync --extra dev
```

## 运行后检查

建议优先查看以下三个产出物：

* `summary.json`
* `config.used.yml`
* `positions_current.csv`

## 下一步建议

* 想继续按流程做研究：`docs/cookbook.md`
* 想先建立系统心智模型：`docs/pipeline-overview.md`
* 想做当前成熟的市场专项研究路线：`docs/playbooks/README.md`
* 想验证 A 股主线迁移候选或理解 default 切换条件：`docs/market-lifecycle.md`
* 想查命令或配置定义：`docs/cli.md`、`docs/config.md`
* 想理解产物结构：`docs/outputs.md`
