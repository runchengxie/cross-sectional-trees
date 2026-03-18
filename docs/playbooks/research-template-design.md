# 研究模板设计原则

本页解决什么：判断本地派生与仓库模板沉淀的边界。
本页不解决什么：不展开具体模型与参数选择。
适合谁：维护 `configs/` 模板或准备沉淀研究路线的人。
读完你会得到什么：清晰的模板沉淀判断标准与行动建议。
相关页面：`docs/playbooks/hk-selected.md`、`docs/playbooks/hk-data-assets.md`、`docs/config.md`

任务摘要：先判断是否仍在同一研究矩阵单元，再决定派生本地配置或新建模板。

本页解决两个问题：

1. 什么时候只派生一份本地配置。
2. 什么时候值得把一个实验沉淀成仓库模板。

这页主要给两类人看：

* 想在现有路线里继续做实验的人
* 想维护 `configs/` 模板的人

如果你还没选好研究路线，先看 [hk-selected.md](./hk-selected.md)。
如果你还没准备好 PIT 财务资产，先看 [hk-data-assets.md](./hk-data-assets.md)。

## 1. 先做这一步判断

先判断你现在改的是“实验细节”还是“研究路线边界”。

| 场景 | 建议动作 | 是否新建仓库模板 |
| --- | --- | --- |
| 只改日期、缓存标签、输出目录、`live` 参数、`run_name` | 派生本地配置 | 否 |
| 只改模型参数，或在同一路线里做四模型 PK | 派生本地配置 | 否 |
| 只在同一路线里试几组特征列 | 先派生本地配置 | 通常否 |
| 想长期维护一条新的频率路线 | 新建仓库模板 | 是 |
| 想长期维护一条新的数据路线 | 新建仓库模板 | 是 |
| 新路线会引入新的本地资产依赖 | 新建仓库模板，并补文档 | 是 |
| 这个配置会被多人反复当作基线使用 | 考虑新建仓库模板 | 视情况而定 |

最简单的判断方法是：

* 如果你还在同一个研究矩阵单元里，优先派生本地配置。
* 如果你已经跨到了新的研究矩阵单元，才考虑新建仓库模板。
* 如果 PIT 体检还没有到绿灯，先继续派生和收窄本地配置，不要急着沉淀模板。

## 2. 什么叫“同一个研究矩阵单元”

在 HK selected 里，一个研究矩阵单元通常由这几件事共同决定：

* 频率：`M` / `Q` / `Y`
* 数据路线：纯量价、量价 + provider 基本面、量价 + PIT 财务
* 股票池口径
* 是否依赖本地 PIT 财务文件

只要这些边界没变，你大多还在同一个单元里。

这时更适合：

* 复制一份本地 YAML
* 改 `model`
* 改参数
* 改少量特征列
* 改 `eval.run_name`

## 3. 什么时候只派生本地配置

下面这些情况，优先不要往仓库里继续加模板：

* 你只是在同一路线里做四模型 PK
* 你只是在同一路线里做参数搜索
* 你只是在同一路线里做小范围特征试验
* 你只是为了某次回测临时改日期、缓存、输出目录
* 你还不确定这条配置会不会长期保留

推荐做法：

1. 从现有基线复制到 `configs/local/` 或你自己的实验目录。
2. 只改本次实验真的需要改的字段。
3. 用稳定的 `run_name` 前缀，方便后续 `summarize`。

例如：

* 季度 `Q` + PIT 财务 + 慢量价 的标准 benchmark protocol

更合适的做法是：

* 直接使用仓库里的三条官方 benchmark 配置和同一 hybrid 单元上的 challenger
* 只有在你要试更细的参数、exit policy 或 universe 时，才继续派生到 `configs/local/`
* 不要把一次性的实验快照继续沉淀成新的仓库模板

## 4. 什么时候新建仓库模板

新建模板要解决“新的稳定问题”，而不是记录“一次实验”。

下面这些情况更适合新建模板：

* 你把月度研究改成季度或年度，并且准备长期维护
* 你把 `fundamentals.source=provider` 改成 `source=file`，研究口径已经明显变化
* 你把“估值对照”改成“PIT 财报主项”或“PIT 财报 + 慢量价”
* 你把股票池范围从 `hk_selected` 扩成了另一个长期维护的 universe
* 这条配置会成为团队内反复复用的起点

更直接一点：

* 新模板对应新的研究问题
* 新模板对应新的资产准备前置
* 新模板对应新的默认阅读路径

如果还没有到这一步，先派生。

## 5. 什么时候要加“显式模型模板”

不是每一条路线都需要同时维护四个显式模型模板。

显式模型模板更适合这些情况：

* 这条路线已经是仓库里的长期主基线
* 新手经常直接拿它做四模型对比
* 这条路线的特征、频率和资产依赖都已经比较稳定

月度 `M` + provider 基本面 这条路线符合这些条件，所以仓库里已经维护了：

* `configs/experiments/variants/hk_selected__ridge_a1.yml`
* `configs/experiments/variants/hk_selected__elasticnet_a0.1_l0.5.yml`
* `configs/experiments/variants/hk_selected__xgb_regressor.yml`
* `configs/experiments/variants/hk_selected__xgb_ranker_pairwise.yml`

季度路线现在已经有一套官方 benchmark protocol，所以更适合：

* 保留稳定的 feature benchmark 和 hybrid challenger 入口
* 更细的实验继续在本地派生

这样 `configs/` 不会很快变成一串难以分辨的实验快照，同时也不会让正式 benchmark 只存在于 `configs/local/`。

## 6. 命名和放置建议

### 仓库内长期维护模板

继续放在 `configs/`，并保持名字能看出三件事：

* 股票池或市场范围
* 数据路线
* 频率或研究重点

例如：

* `configs/experiments/baseline/hk_selected.yml`
* `configs/experiments/baseline/hk_selected__quarterly_price_only.yml`
* `configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml`

### 本地派生配置

建议放在你自己的本地目录，例如：

* `configs/local/`
* `configs/experiments/`

这类文件更适合描述实验目的，而不是沉淀成仓库默认入口。
如果一个配置需要被团队复用或在文档里当作正式入口，应该收回到 `configs/experiments/`。

例如：

* `configs/local/<my_quarterly_pit_core_hybrid_xgb_ranker>.yml`
* `configs/local/<my_quarterly_pit_core_hybrid_xgb_ranker_ffill>.yml`
* `configs/local/<my_quarterly_pit_core_hybrid_xgb_ranker_strict>.yml`

## 7. 新建模板时必须同步什么

如果你决定新建一个仓库模板，至少同步这几处：

1. `docs/config.md`
2. 如果它影响研究路线选择，更新 [hk-selected.md](./hk-selected.md)
3. 如果它引入新的资产准备前置，更新 [hk-data-assets.md](./hk-data-assets.md)
4. 如果它改变了新手入口，更新 `README.md`、`docs/README.md` 或 `docs/cookbook.md`

代码层也要同步验证：

* 配置模板 smoke check
* 和这条路线直接相关的 pipeline / provider / asset tests

如果只是本地派生配置，这些动作通常都不需要。

## 8. 一个简单的决策顺序

当你在犹豫“派生还是新建”时，可以直接按这个顺序问：

1. 这次改动是否跨了新的频率或新的数据路线？
2. 这次改动是否引入了新的资产准备前置？
3. 这份配置是否会成为多人重复使用的稳定基线？
4. 如果不进仓库，新手是否仍然能顺着现有入口完成同类任务？

如果前 3 个问题都偏向“否”，通常先派生本地配置。

## 9. 给新手的一个最短原则

如果你刚接触这个项目，可以直接记住下面这句：

* 先用仓库模板选路线，再用本地配置做实验。

仓库模板负责：

* 定义稳定路线
* 定义阅读入口
* 定义常用基线

本地配置负责：

* 跑你的具体实验
* 做模型比较
* 试参数和少量特征变化
