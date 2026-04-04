# HK Monthly 行业异质性处理指引（2026-04-04）

本页解决什么：给当前 HK monthly 基本面 / hybrid 研究线一套“行业异质性怎么处理”的决策框架、最小实验顺序和复盘口径。  
本页不解决什么：不替代 `current-state` 页面，也不把“行业处理”误写成已经默认接进训练主线的系统能力。  
适合谁：已经接受“财报驱动模型需要处理行业差异”，但不想直接把样本切成十几个行业小模型的人。  
读完你会得到什么：当前仓库支持的行业处理边界、推荐实验矩阵、每一步该看哪些 artifact，以及什么时候才值得进一步升级复杂度。  
相关页面：`docs/research/notes/hk-monthly-current-state-20260330.md`、`docs/research/notes/hk-monthly-time-window-design-20260330.md`、`docs/research/notes/hk-monthly-provider-factor-probes-20260330.md`、`docs/playbooks/hk-selected.md`、`docs/config.md`、`docs/outputs.md`

页面性质：`research-note`  
状态：`active deep-dive`，这是当前 monthly 研究线的行业处理设计页，不替代 [`hk-monthly-current-state-20260330.md`](./hk-monthly-current-state-20260330.md)  
最后核对时间：`2026-04-04`  
权威来源：当前仓库 `configs/`、`docs/`、pipeline 代码路径，以及现有 monthly provider / PIT probe 结论  
冲突优先级：如果与具体 run 的 `summary.json` / `config.used.yml` 冲突，以 run 产物为准；如果与后续代码能力冲突，以更新后的代码和配置契约为准

## 1. 先给结论

* 对当前 HK monthly 基本面 / hybrid 路线，不应该默认上“每个行业分别训练一个 XGB”。
* 更稳的做法是先把问题拆成三层：观察、约束、切样本。
* 当前仓库里最先该做的是：
  1. 总模型不变，只把行业标签接进 panel 做 `bucket_ic` 和暴露观察。
  2. 在组合层加最小行业约束，看收益和稳定性会不会更干净。
  3. 只有前两步都说明行业异质性仍然主导误差时，再做“金融剔除 / 金融单列”。
* 直接把月频 HK 样本切成十几个行业模型，在当前样本厚度下更像过拟合放大器，不像更专业的默认动作。

## 2. 为什么这件事在 monthly 线不能一步做满

当前 monthly 主线的可建模窗口并不厚。  
对这组 `M-PIT hybrid sidecar / overlay` 配置，修复 split 逻辑后的 anchor run 形成的是 `126` 个 model dates，对应 `50 / 52 / 24` 的 `main train / main test / final OOS`，[`hk-monthly-time-window-design-20260330.md`](./hk-monthly-time-window-design-20260330.md) 已固定了这个判断。

这意味着：

* 行业差异当然要处理，但处理方式必须节制。
* 一旦按一级甚至二级行业拆模型，很多行业的月频训练窗口会迅速变薄。
* 对树模型来说，这更容易让模型学到分叉噪声，而不是稳定的行业内排序规律。

所以当前 monthly 线更合理的问题不是：

* “要不要分行业训练？”

而是：

* “行业差异应该先在哪一层处理？”

## 3. 当前仓库已经支持什么

先把边界说死，避免以后按不存在的能力设计实验。

### 3.1 已支持

* 本地 `industry_labels_<freq>.parquet` 可直接 join 到研究 panel。
* join 后的行业列可以保留到 `dataset.parquet`、`eval_scored.parquet`。
* `eval.bucket_ic` 可以直接按行业列看分桶 IC。
* `backtest.group_col + max_names_per_group` 可以在组合层做最小分组约束。
* `backtest_industry_exposure.csv` 和 `summary.json -> backtest -> exposure` 会给出行业暴露时序和最新调仓点的显著偏离。

### 3.2 当前不支持

* 行业列不会自动加入模型 `features`。
* 当前没有“自动行业中性化”的默认主线。
* `eval.score_postprocess.method=neutralize` 只适合数值控制列，不适合直接拿字符串行业标签做去相关。
* 当前没有内建“按 join 后行业列直接过滤训练样本”的通用配置入口。

这几个边界对应的直接含义是：

* “行业观察”和“行业约束”已经能做。
* “行业 one-hot / 行业内相对值 / 行业内单独训练”还不是默认开箱能力。
* “金融剔除”如果要做成严格实验，更稳妥的入口是改 `universe.by_date_file`，而不是假装可以在 `industry` 块里顺手过滤样本。

## 4. 推荐实验顺序

当前 monthly PIT / hybrid 线建议固定成下面四步。

### 4.1 R0 baseline

用你当前正在跟踪的月频 PIT 基线，不加行业处理。

如果你只是想找最小可复用入口，当前研究里已经固定了两类基于 core sidecar 的 overlay 命名约定：

* `industry_observe`
* `industry_groupcap4`

如果你当前实际跟踪的是 `no_ret` 候选或别的 monthly 派生配置，更稳的做法是把这些 overlay 文件里的 `extends` 改到你的当前基线上，而不是再造一套平行主线。

### 4.2 R1 industry-observe

目标：

* 不改模型。
* 只把行业标签接进 panel。
* 用 `bucket_ic` 和行业暴露看“模型是不是主要在少数行业上有效”。

当前仓库里直接复用的就是 `industry_observe` 这类 overlay。

它做的事很克制：

* 读取月频行业标签 `industry_labels_m.parquet`
* 保留 `industry_name` / `first_industry_name`
* 打开 `eval.bucket_ic`
* 保存 `eval_scored.parquet`

这一步的意义不是“改善收益”，而是回答：

* alpha 到底是不是明显集中在一两个行业
* 当前 PIT / hybrid 排序器有没有把行业差异误当成公司内生质量

### 4.3 R2 industry-groupcap

目标：

* 继续保留总模型。
* 不动训练集、不动特征。
* 只在组合层压一下一级行业集中度。

当前仓库里直接复用的是 `industry_groupcap4` 这类 overlay。

这份 overlay 只在 `R1` 基础上再加两行：

```yaml
backtest:
  group_col: first_industry_name
  max_names_per_group: 4
```

当前推荐先用 `4`，而不是一上来就 `2` 或 `3`。  
原因很简单：月频 `top_k=20` 时，过紧的 cap 会让组合先被约束打瘦，再去讨论信号好坏，信息含量反而变差。

### 4.4 R3 nonfinancial-only

目标：

* 这一步才真正触到“金融单列 / 剔除”。
* 不是把行业拆成很多模型，而是先切掉最大的报表结构断点。

当前仓库没有内建“按 join 后行业列过滤训练样本”的配置项，因此这一步更稳的做法是：

* 从当前 monthly `universe.by_date_file` 出发
* 结合 `industry_labels_m.parquet`
* 生成一份新的 `nonfinancial by-date` universe 文件
* 再跑同一条基线

这一步现在更适合写成研究动作，而不是仓库里默认就给一个会因为缺文件而跑不通的 tracked config。

### 4.5 R4 financial-only

这一步只建议当诊断项，不建议先升成主线。

它更像在回答：

* 金融板块单独拉出来后，样本是不是过薄
* financial-only 的 IC / OOS 到底是稳定还是跳点

如果它本身就很薄、很跳，那更说明第一阶段该优先保留“非金融主线 + 金融单独对待”的思路，而不是继续朝多行业多模型方向走。

## 5. 每一步该看什么 artifact

### 5.1 先看 `summary.json`

优先看：

* `summary.json -> industry`
* `summary.json -> eval`
* `summary.json -> final_oos`
* `summary.json -> backtest -> exposure`

这里先回答四件事：

* 行业标签到底有没有成功接进 panel
* `IC`、`p_value` 和 long-only 指标有没有明显变化
* 组合层加了行业 cap 之后，收益和换手是变干净还是直接变瘦
* 最新一个调仓点的行业主动暴露有没有明显收敛

### 5.2 再看 `bucket_ic.csv`

这一步主要回答：

* 行业内效果是不是明显不均衡
* 是否只有一两个行业有正 IC，其它行业接近零甚至为负

如果 `bucket_ic` 显示信号主要集中在个别行业，而 `R2` 的行业 cap 对收益损伤不大，那就说明：

* 当前更像“总模型 + 最小行业约束”已经足够

如果 `bucket_ic` 很偏，而 `R2` 一加 cap 就明显伤到主要收益来源，那再去做 `R3` 会更有意义。

### 5.3 再看 `backtest_industry_exposure.csv`

这一步回答：

* 行业约束有没有真正生效
* active weight 是不是从“押大行业偏离”收敛到“行业内选优”

这里要特别记住一条：

* 行业暴露收敛，不等于模型本身已经完成行业中性化。

它只是说明：

* 当前组合层约束，至少没有让持仓无限堆向某一个行业。

## 6. 怎么判这些实验

### 6.1 如果 `R1` 显示行业集中很强

这不代表你应该立刻分行业训练。  
它只说明你的直觉是对的：模型里确实有行业异质性问题。

下一步先看 `R2`。

### 6.2 如果 `R2` 压住行业暴露，但 `IC / OOS` 没明显变差

当前更合理的结论是：

* 先保留总模型
* 再保留最小行业约束
* 暂时不升级成细行业分模

这通常是当前仓库和当前样本厚度下，信息比最高的停点。

### 6.3 如果 `R2` 一加约束就明显伤到结果

先别急着说“行业处理没用”。  
更合理的解释通常是：

* 当前 alpha 的一部分确实和行业结构缠在一起
* 你需要先分辨这是“金融报表污染”还是“全市场行业轮动”

这时更值得继续的是 `R3 nonfinancial-only`，而不是直接去做十几个行业模型。

### 6.4 如果 `R3 nonfinancial-only` 明显更稳

这时才值得把“金融单列 / 金融剔除”升级成下一层 baseline。

这一步成立时，说明你抓到的是最大的结构断点，而不是只是在月频小样本里追求精细幻觉。

## 7. 什么时候才值得再升级复杂度

只有下面两件事同时成立，才值得继续往更细的行业处理走：

* `R1` / `R2` 已经清楚说明行业异质性是主要问题
* `R3` 之后问题仍然明显存在

这时下一层才轮到：

* 行业内相对值特征
* 行业编码入模
* 金融 / 非金融双模型
* 最后才是更细行业分模

对当前 HK monthly 线，不建议把这些动作直接跳成默认第一步。

## 8. 这页真正想固定下来的方法论

把这套 monthly 基本面 / hybrid 研究线里的行业处理，按下面这句话记住就够了：

* 先观察，再约束，再切样本，最后才拆模型。

更具体一点就是：

1. 先确认问题是不是行业集中。
2. 再确认组合层最小约束能不能把问题压住。
3. 压不住，再看最大结构断点，也就是金融 vs 非金融。
4. 只有前三步都不够，才值得往行业相对化特征或细行业模型继续推进。

这比“先把样本切成很多行业模型再看结果”更适合当前仓库，也更适合当前月频样本条件。
