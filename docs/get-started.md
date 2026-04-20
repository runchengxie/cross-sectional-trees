# 快速上手

本页解决什么：用最短路径跑通一次完整流程。\
本页不解决什么：不展开配置细节与模型选择。\
适合谁：第一次进入仓库或只想验证环境的人。\
读完你会得到什么：一套可重复的最小跑通流程与产物检查清单。\
相关页面：`README.md`、`docs/cookbook.md`、`docs/cli.md`、`docs/config.md`、`docs/outputs.md`、`docs/providers.md`

## 前置条件

* Python 3.12 及以上版本
* `uv` 包管理器

## 最短跑通

```bash
uv venv --seed
uv sync --extra dev --extra rqdata
cp .env.example .env
csml run --config default
```

请按 `data.provider` 配置好鉴权变量，详情参见 `docs/providers.md` 文件。

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
* 想做港股精选研究：`docs/playbooks/README.md`
* 想查命令或配置定义：`docs/cli.md`、`docs/config.md`
* 想理解产物结构：`docs/outputs.md`
