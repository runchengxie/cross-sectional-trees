# PIT 覆盖率指南

本页解决什么：理解 PIT 财务覆盖率体检的意义与解读方法。
本页不解决什么：不替代命令参数与配置定义。
适合谁：做季度 PIT 财报研究或需要判断样本覆盖的人。
读完你会得到什么：覆盖率体检的解读框架与行动建议。
相关页面：`docs/cli.md`、`docs/playbooks/hk-selected.md`、`docs/playbooks/hk-data-assets.md`

这个文档帮你理解 PIT 财务数据的覆盖率体检。

## 什么是 PIT 覆盖率

PIT（Point-In-Time）财务数据的覆盖率，指的是在某个季度里，有多少股票同时满足：

1. 有完整的财报数据
2. 有对应的行情数据
3. 满足最小样本数门槛

覆盖率直接影响模型能否训练，以及训练结果的可靠性。

## 快速决策

| 你的情况 | 建议 |
|---------|------|
| 第一次做季度 PIT 研究 | 先跑覆盖率体检，确认 `Fill Dependence` 在黄灯以上 |
| 覆盖率是红灯 | 先改字段集或股票池，不要急着调模型 |
| 覆盖率是黄灯 | 优先解决最拖后腿的一两个字段，再进入基线比较 |

## 怎么看覆盖率体检结果

运行命令：

```bash
csml rqdata inspect-hk-pit-coverage \
  --config configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml \
  --mode both
```

如果你已经在本地派生过配置，也可以把 `--config` 换成你自己的 `configs/local/*.yml`。

如果你还想同时回答“这份 `pipeline_fundamentals.parquet` 到某个调仓日有没有陈旧、有没有断档”，可以在同一个命令上加：

```bash
csml rqdata inspect-hk-pit-coverage \
  --config configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml \
  --mode both \
  --include-health \
  --target-date 20260331
```

这里的 `Health` section 和 `Coverage` section 不同：

* `Coverage` 看的是特征覆盖率和 trainability
* `Health` 看的是 target-date 视角下的 freshness / staleness / 断档

### 关键指标

| 指标 | 含义 | 看什么 |
|------|------|--------|
| `dropped_all_missing_fields` | 源头 PIT 资产有多少全空行 | 太高说明资产本身有问题 |
| `complete_rows` | 当前特征组合能留下多少完整样本 | 决定了训练数据量 |
| `quarter_count_meeting_min_symbols` | 每个季度有多少 symbol 能做横截面 | 决定了能不能训练 |
| `Worst Features` | 最拖后腿的字段 | 优先处理这些 |
| `retention_ratio_after_ffill` | 横截面填补后还能剩多少 | `Fill Dependence` 的核心指标 |

### Fill Dependence 判断标准

| 数值区间 | 标记 | 含义 |
|---------|------|------|
| `>= 0.60` | 🟢 绿灯 | 核心 PIT 路线可以继续 |
| `0.30 - 0.59` | 🟡 黄灯 | 核心 PIT 路线可以继续，但要关注 |
| `< 0.30` | 🔴 红灯 | 先停下来，改字段集或股票池 |

对于 hybrid 路线（财报 + 慢量价），门槛可以稍微放宽：

| 数值区间 | 标记 |
|---------|------|
| `>= 0.40` | 🟢 绿灯 |
| `0.15 - 0.39` | 🟡 黄灯 |
| `< 0.15` | 🔴 红灯 |

## 常见问题

### 1. 原始 PIT 资产覆盖率低

先看 `Worst Features`：

- 如果是最基础的财务字段（如 `revenue`、`net_profit`）覆盖率低，可能是 provider 本身的问题
- 如果是派生的 `growth_*` 字段低，可能是原值字段本身的覆盖率就低

**处理方式**：
1. 缩窄字段集，只用高覆盖的字段
2. 检查股票池是否混入了 PIT 不覆盖的股票

### 2. 填补后样本还是不够

如果 `periods_after_missing_fill=0`，说明即使做了横截面填补，仍然没有足够的季度样本。

**处理方式**：
1. 放宽 `universe.min_symbols_per_date`
2. 减少 PIT 特征数量
3. 回到资产准备阶段，补全缺失的财报数据

### 3. 原值和 growth_* 成对拖后腿

如果 `Worst Features` 里某个原值和对应的 `growth_*` 派生项同时出现，优先成对处理，不要只删一个。

## 推荐的季度 PIT 研究流程

1. **第一步**：先做覆盖率体检
2. **第二步**：如果是红灯，先改字段集；如果是黄灯，先解决最拖后腿的字段
3. **第三步**：跑三条基线：
   - `季度纯量价`
   - `季度 core PIT`
   - `季度 core PIT + 慢量价`
4. **第四步**：只有三条基线都稳定后，才做四模型 PK

详见 `docs/cookbook.md` 的「HK selected 研究」部分。

## 相关文档

- 覆盖率体检命令：`docs/cli.md`
- 季度 PIT 研究流程：`docs/cookbook.md`
- HK selected 研究：`docs/playbooks/hk-selected.md`
- PIT 资产准备：`docs/playbooks/hk-data-assets.md`
