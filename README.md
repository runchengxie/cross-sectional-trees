# cross-sectional-machine-learning

使用 RQData 日线数据做港股截面因子研究、评估和持仓快照。当前正式支持的数据输入与研究主链边界是 `market=hk + data.provider=rqdata + 可选本地 HK 资产直读`。

## 这项目是干嘛的

低频研究与复现实验的工作流，覆盖研究、评估、回测与持仓快照输出。

## 我能不能跑起来

Python 3.12+，推荐 `uv`。如果你需要 RQData 能力，安装时加 `--extra rqdata`；如果你要把 `csml alloc-hk` 导出成 Excel，再额外加 `--extra liveops-hk`。

```bash
uv venv --seed
uv sync --extra dev --extra rqdata
cp .env.example .env
```

鉴权与 provider 选择见 `docs/providers.md`。

常见命令和依赖关系：

| 任务 | 典型命令 | 需要的 extra | 额外凭证 |
| --- | --- | --- | --- |
| 跑默认 HK starter | `csml run --config default` | `rqdata` | RQData 账号 |
| 跑 HK 季频 PIT fundamentals | `csml run --config configs/presets/hk_quarterly_pit_hybrid.yml` | `rqdata` | RQData 账号 |
| DuckDB 查询标准层 | `csml data query --sql "..."` | `duckdb` | 无 |
| 导出 HK Excel 分配表 | `csml alloc-hk --format xlsx --out ...` | `liveops-hk` | 如果走 live/provider 路径，仍需要对应数据源凭证 |
| 计算带 `p_value` 的统计检验 | Python / `csml` 下游分析调用 `summarize_ic` | `stats` | 无 |

`default` / `hk` 这些内置别名，以及 `csml init-config`，都读取仓库根目录的 `configs/`。也就是说，日常使用应在包含 `configs/` 的源码 checkout 或导出源码目录里运行。

## 最短命令是什么

`csml run --config default`

`default` 当前指向 HK starter 模板，默认 `data.provider=rqdata`。第一次跑 `default` 或 `hk` 前，先安装 `uv sync --extra dev --extra rqdata`。

## 这仓库还有哪些入口

* 研究汇总与敏感性分析：`csml summarize` / `csml grid` / `csml sweep-linear`
* live 结果查看与分配：`csml holdings` / `csml snapshot` / `csml alloc` / `csml alloc-hk`（含 HK 执行前场景矩阵）
* 数据与运维工具：`csml rqdata ...` / `csml universe ...`
* 数据分层与查询：`csml data catalog` / `csml data materialize` / `csml data query`

完整能力地图见 `docs/capabilities.md`。

## 入口分层

当前建议按下面四层理解：

| 层级 | 典型入口 | 当前定位 |
| --- | --- | --- |
| 公开主线 CLI | `csml run` / `csml summarize` / `csml grid` / `csml sweep-linear` / `csml holdings` / `csml snapshot` / `csml alloc` / `csml alloc-hk` / `csml data ...` / `csml rqdata ...` / `csml universe ...` | 当前正式对外说明、持续维护的用户入口 |
| 公开但非 CLI 模块工具 | `python -m csml.release_tools.package_assets` / `release_assets` / `package_runs` / `release_runs` | 已在文档中说明的打包 / 分发工具，但它们不是 `csml` 子命令 |
| 研究 / 专题模块工具 | `python -m csml.research.hk_financial_details` / `hk_selected_provider_valuation_audit` / `hk_intraday_download` / `hk_asset_patch_merge` | 只在对应 playbook 或专题页里按场景使用；可复用，但不属于新手默认主线 |
| 维护与开发辅助 | `scripts/dev/run_tests.sh`、`scripts/internal/` | 前者服务开发与 CI；后者是维护者私有工具，不属于公开研究工作流 |

如果你拿不准某个入口算不算“正式支持”，优先看 `README.md`、`docs/capabilities.md`、`docs/cli.md` 和对应 playbook 是否把它当作主线入口写出来。

## 跑完先看什么

优先看 `summary.json`、`config.used.yml` 和 `positions_current.csv`。最短跑通步骤和产物检查清单放在 `docs/get-started.md`。

## 后续按什么路径读文档

从 [docs/README.md](docs/README.md) 进入。新手直接看 `docs/get-started.md`，先建立系统地图看 `docs/pipeline-overview.md`，正式研究路线从 `docs/playbooks/README.md` 进入，通用工作流速查看 `docs/cookbook.md`，按对象查细节看 `docs/cli.md` / `docs/config.md` / `docs/outputs.md`。
