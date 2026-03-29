# 常见问题排查

本页解决什么：按症状组织的排障路径。  
本页不解决什么：不替代参数与默认行为的权威说明。  
适合谁：运行中遇到错误或结果异常的人。  
读完你会得到什么：按症状定位原因与处理步骤。  
相关页面：`docs/config.md`、`docs/cli.md`、`docs/providers.md`、`docs/outputs.md`

本页只保留排障路径。参数定义和默认行为以 `docs/config.md`、`docs/cli.md`、`docs/providers.md` 为准。

## 先看哪里

多数问题先看这三类信息：

* 当前使用的命令和参数
* 本次 run 的 `config.used.yml`
* 本次 run 的 `summary.json`

## 1. 启动即退出：RQData 鉴权或依赖缺失

常见报错：

* `rqdatac is required for provider='rqdata'`
* `rqdatac.init failed: ...`
* `Unsupported data.provider '...'`
* `Unsupported market '...'`

先检查：

1. `.env` 是否存在并已填真实的 `RQDATA_USERNAME` / `RQDATA_PASSWORD`
2. 当前配置是否仍然写着旧的 provider 或旧市场
3. 是否已经安装 `uv sync --extra dev --extra rqdata`

快速验证：

```bash
csml rqdata info
csml rqdata quota --pretty
```

## 2. `last_trading_day` 看起来像自然日

常见原因：

* 当前环境没有可用的 `rqdatac` 交易日历
* 命令缺少 `--config` 或无法从 run 目录推断市场
* 你实际上在本地资产模式下运行

建议：

* 需要强复现时，直接写绝对日期，如 `20260131`
* 需要严格交易日时，优先确认 `csml rqdata info` 正常

## 3. 回测结果为空或样本很少

常见原因：

* `universe` 过滤太严
* `by_date_file` 格式不对
* `label.shift_days` 与样本尾部窗口冲突

先看：

1. `summary.json -> data.rows_model`
2. `summary.json -> data.dropped_dates`
3. `summary.json -> universe`
4. `dropped_dates.csv`（若存在）

建议：

* 先用更宽松的股票池和更短的过滤链路确认流程可跑
* 长历史回测优先使用 PIT 股票池

## 4. `summarize` 提示 `No runs matched current summarize filters.`

常见原因：

* `--exclude-flag-short-sample` 排掉了所有短样本 run
* 其他 `--exclude-flag-*` 继续把候选 run 排空
* `--run-name-prefix`、`--since` 或 `--latest-n` 设得太严

建议：

* 先去掉全部 `--exclude-flag-*` 看全量结果
* 再根据 `summary.json` 里的 `flag_*` 逐步加回过滤条件

## 5. `Not enough dates for a meaningful split.`

常见原因：

* 新加的特征组覆盖率太差，`dropna(subset=required_cols)` 把大部分历史都筛掉了
* 季度 PIT 路线里，某几个低覆盖字段把可训练季度点压缩到最近很短一段
* `final_oos` 再切走最后一小段后，in-sample 日期数已经不够 split

先看：

1. `run.log` 里有没有 `Feature availability collapse` 告警
2. `Applied feature missing fill ... remaining_nans=...` 后面的数量是不是仍然很大
3. 报错信息里的 `model_dates_before_final_oos` 和 `Recent model dates`

建议：

* 如果是季度 PIT 配置，先跑：

```bash
csml rqdata inspect-hk-pit-coverage --config <your-config> --mode both
```

* 优先删掉最拖后腿的特征，而不是先改 `test_size`
* 对 coverage 很差的资产负债表字段，先做 lite probe，再考虑完整 debt ratio 版本
