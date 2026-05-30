# 外置产物根目录

本页解决什么：怎么把默认 `artifacts/` 放到 repo 外，而不改研究主链的使用方式。\
本页不解决什么：不展开对象存储、数据平台或多租户发布流程。\
适合谁：想把数据和代码仓分开存放，但当前仍以单仓研究和复现为主的人。\
读完你会得到什么：可用入口、优先级规则，以及复现时该保留哪些文件。\
相关页面：`docs/config.md`、`docs/cli.md`、`docs/outputs.md`、`docs/concepts/shared-hk-data-platform.md`

## 什么时候需要它

下面几种情况适合把默认 `artifacts/` 挪到 repo 外：

* 仓库放在源码目录，但数据和 run 产物想落到独立磁盘。
* 你希望多个 checkout 共用一套 provider 资产、metadata 或 standardized 输出。
* 你希望 `cross-sectional-trees` 和十档盘口快照工具先共享同一套 HK 数据资产，再逐步拆成独立数据平台。
* 你想重建代码仓，但保留历史 run 和数据镜像。

这一步的目标只是“把默认路径抽出来”，不是把项目升级成独立数据平台。

## 三种入口

当前支持三种方式改默认产物根目录：

1. 配置：

```yaml
paths:
  artifacts_root: "/data/cstree-artifacts"
```

2. 环境变量：

```bash
export CSTREE_ARTIFACTS_ROOT=/data/cstree-artifacts
```

3. CLI：

```bash
cstree run --config configs/presets/hk.yml --artifacts-root /data/cstree-artifacts
```

优先级固定为：

`--artifacts-root` > `CSTREE_ARTIFACTS_ROOT` > `paths.artifacts_root` > 默认 `artifacts/`

如果你要做的是“策略项目只读消费共享 HK 数据平台”，不要用这个变量把所有 run 输出也切过去；改用：

```bash
export HK_DATA_PLATFORM_ROOT=/data/hk-data-platform
```

`HK_DATA_PLATFORM_ROOT` 只会把 `artifacts/assets/...`、`artifacts/metadata/...`、`artifacts/standardized/...` 这类数据输入路径映射到共享根目录下。`artifacts/runs/...`、`artifacts/cache/...`、`artifacts/reports/...` 仍按本仓库自己的 `artifacts_root` 派生。

## 哪些命令会跟着走

下面这些命令会按新的产物根目录派生默认路径：

* `cstree run`
* `cstree holdings`
* `cstree snapshot`
* `cstree alloc`
* `cstree alloc-hk`
* `marketdata data catalog`
* `marketdata data materialize`
* `marketdata data query`

例如：

* 默认 run 目录会从 `artifacts/runs/...` 变成 `<artifacts_root>/runs/...`
* metadata catalog 默认会从 `artifacts/metadata/catalog.sqlite` 变成 `<artifacts_root>/metadata/catalog.sqlite`
* standardized 默认输出会从 `artifacts/standardized/...` 变成 `<artifacts_root>/standardized/...`

## 哪些路径不会被它覆盖

`artifacts_root` 只影响“默认派生路径”，不会覆盖你已经显式指定的更细粒度路径，例如：

* `eval.output_dir`
* `data.cache_dir`
* `fundamentals.file`
* `data.rqdata.daily_asset_dir`
* `--db-path`
* `--summary-out`
* `--out-root`
* `--standardized-root`

如果这些路径已经写死，它们仍然优先。

例外：设置了 `HK_DATA_PLATFORM_ROOT` 时，显式写成 `artifacts/assets/...`、`artifacts/metadata/...`、`artifacts/standardized/...` 的 HK 数据输入路径会被解释为共享数据平台根目录下的相同相对路径。

## 复现时保留什么

如果你要复现、审计或打包单个 run，优先保留 run 目录里的这几类文件：

* `summary.json`
* `config.used.yml`
* `inputs.lock.json`

分工分别是：

* `summary.json`：总摘要和路径索引
* `config.used.yml`：实际生效配置
* `inputs.lock.json`：运行时解析后的输入锁定，包括绝对输入路径、日期展开结果和 mutable 输入标记

`latest.json` 只应该当便利指针看待。它适合本地 live 入口快速找到最近一次 run，不适合作为长期审计、归档或发布入口。

## 推荐做法

对当前仓库，更稳妥的做法是：

* 先外置默认 `artifacts_root`
* 保持 provider 资产、metadata、standardized、runs 仍然沿用现有目录分层
* 继续用 `summary.json`、`config.used.yml`、`inputs.lock.json` 做复现

暂时不需要因为“将来可能会有数据湖”就先引入独立 registry、对象存储网关或重型 lineage 平台。

如果目标是把 HK 数据层进一步拆成多个项目共享的数据平台，请把外置 `artifacts_root` 当成第一阶段的共享数据根；具体边界见 `docs/concepts/shared-hk-data-platform.md`。
