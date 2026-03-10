# 常见问题排查

本页只保留排障路径。参数定义和默认行为以 `docs/config.md`、`docs/cli.md`、`docs/providers.md` 为准。

## 先看哪里

多数问题先看这三类信息：

* 当前使用的命令和参数
* 本次 run 的 `config.used.yml`
* 本次 run 的 `summary.json`

## 1. 启动即退出：鉴权变量缺失

常见报错：

* `Please set TUSHARE_TOKEN ... first.`
* `rqdatac is required for provider='rqdata'`
* `Please set EODHD_API_TOKEN ... first.`

先检查：

1. `.env` 是否存在并已填真实值
2. `data.provider` 和凭证是否匹配
3. 当前环境是否已经重新加载

快速验证：

```bash
csml tushare verify-token
csml rqdata info
csml rqdata quota --pretty
```

相关文档：

* `docs/config.md`
* `docs/providers.md`
* `docs/cli.md`

## 2. `last_trading_day` 看起来像自然日

常见原因：

* 当前 provider 不是 `rqdata`
* 命令缺少 `market` 上下文
* 交易日历不可用

先检查：

1. 配置里的 `data.provider`
2. 命令是否提供了 `--config` 或可解析的 run 目录
3. 是否真的需要严格交易日，而不是自然日近似

建议：

* 需要强复现时，直接写绝对日期，如 `20260131`
* 需要严格交易日时，优先使用 `provider=rqdata`

相关文档：

* `docs/providers.md`
* `docs/cli.md`
* `docs/config.md`

## 3. 回测结果为空或样本很少

常见原因：

* `universe` 过滤太严
* `by_date_file` 格式不对
* `label.shift_days` 和样本尾部窗口冲突

先看：

1. `summary.json -> data.rows_model`
2. `summary.json -> data.dropped_dates`
3. `summary.json -> universe`
4. `dropped_dates.csv`（若存在）

建议：

* 先用更宽松的股票池和更短的过滤链路确认流程可跑
* 长历史回测优先使用 PIT 股票池

相关文档：

* `docs/config.md`
* `docs/outputs.md`

## 4. `summarize` 提示 `No runs matched current summarize filters.`

常见原因：

* `--exclude-flag-short-sample` 排掉了所有短样本 run
* `--exclude-flag-high-turnover`、`--exclude-flag-relative-end-date` 继续把候选 run 排空
* `--run-name-prefix`、`--since` 或 `--latest-n` 设得太严
* 历史 run 使用的是旧配置，实际门槛和你当前参考的模板不一致

先看：

1. `out/runs` 下是否真的存在 `summary.json`
2. 先去掉全部 `--exclude-flag-*` 看全量结果
3. `summary.json -> backtest.stats.periods`
4. `summary.json -> backtest.stats.avg_turnover`
5. `config.used.yml -> data.end_date`

建议：

* 先执行 `csml summarize --runs-dir out/runs --sort-by score`
* 确认哪些 `flag_*` 为 `true` 后，再逐步加回排除参数
* 若空结果来自短样本，优先重跑更长样本；只在明确知道原因时下调 `--short-sample-periods`

相关文档：

* `docs/cli.md`
* `docs/cookbook.md`
* `docs/outputs.md`

## 5. 当前持仓与预期不一致

常见原因：

* `label.shift_days=1` 时，月末信号会在下一交易日入场
* 查询时点和你心里的持仓生效日不是同一天

先看：

1. 持仓文件里的 `signal_asof`
2. `entry_date`
3. `next_entry_date`
4. `holding_window`

建议：

* 用 `csml holdings --as-of <date>` 明确查询时点
* 先确认 `shift_days` 和再平衡频率

相关文档：

* `docs/config.md`
* `docs/outputs.md`
* `docs/cli.md`

## 6. live / snapshot 命令报错

常见报错：

* `live.enabled=true requires eval.save_artifacts=true`
* `live.enabled=true but no live positions were generated`

先检查：

1. `live.enabled` 是否为 `true`
2. `eval.save_artifacts` 是否为 `true`
3. `top_k`、股票池和日期窗口是否为空
4. live 配置是否写到了独立输出目录

建议：

* 先执行 `csml run --config <live.yml>`
* 再执行 `csml holdings --source live`
* 若仍失败，再检查 `summary.json` 里的 live 路径和状态

相关文档：

* `docs/config.md`
* `docs/cli.md`
* `docs/outputs.md`

## 7. 结果每天都变，无法复现

常见原因：

* 使用了 `today`、`t-1`、`now`
* provider 回补历史数据
* 命中缓存后刷新了末端区间

建议：

1. 固定 `start_date` 和 `end_date`
2. 固定 `data.cache_tag`
3. 归档 `cache/`、`config.used.yml`、`summary.json` 和 git commit

相关文档：

* `docs/config.md`
* `docs/providers.md`

## 8. 参数校验失败

高频错误：

* `eval.save_dataset=true` 但 `eval.save_artifacts=false`
* `backtest.exit_mode=label_horizon` 与再平衡间隔不匹配
* `features.cross_sectional.method` 或 `winsorize_pct` 不合法
* `eval.bucket_ic.method` 不是 `spearman` 或 `pearson`

建议：

* 先从内置模板导出配置再改
* 每次只改一小组参数
* 复现实验时优先以 `config.used.yml` 为准

```bash
csml init-config --market hk --out config/
```

相关文档：

* `docs/config.md`
* `docs/cli.md`

## 9. HK 基本面有 warning，部分 symbol 没有 `market_cap / pe_ttm / pb`

常见原因：

* 股票池里混入了 ETF、杠杆/反向产品或其他非普通股产品
* 当前配置使用了 `fundamentals.source=provider`
* `RQData` 对这些 symbol 不提供对应的估值类字段

先看：

1. `summary.json -> fundamentals`
2. 日志里的缺失 symbol 列表
3. `universe_by_date.csv` 里对应 symbol 的类型来源

建议：

* 若只是少量 ETF / 产品代码缺失，可继续运行；这些 symbol 会被跳过
* 若缺失比例很高，先检查股票池定义，再确认是否应改用 `fundamentals.source=file`
* 做港股普通股研究时，尽量把股票池限制在普通股 universe

相关文档：

* `docs/providers.md`
* `docs/config.md`

## 10. RQData 长历史抓取报 `invalid date range`

常见原因：

* 请求起始日早于个股上市日
* 你在仓库外部写了自定义取数脚本，直接把固定长窗口传给 `rqdatac.get_price`

先看：

1. 报错 symbol 的 `listed_date`
2. 请求区间的 `start_date / end_date`
3. 当前仓库版本是否已经包含上市日裁剪逻辑

建议：

* 仓库内主流程会先按 `listed_date` 裁剪左端区间，再发请求
* 自定义脚本也应先查 `instruments(...).listed_date`
* 若个股上市日晚于整个请求区间，直接返回空表即可，不必继续请求 provider

相关文档：

* `docs/providers.md`
* `docs/dev.md`
