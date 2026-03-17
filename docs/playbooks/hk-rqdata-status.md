# HK RQData 状态矩阵

本页解决什么：记录 HK RQData 相关接口在本仓库里的接入状态、本地已有资产和最近一次活体 probe 结果。  
本页不解决什么：不展开研究路线选择，也不代替 CLI 参数文档。  
适合谁：准备继续补 HK 资产，或想先确认“哪些已经有了、哪些现在能下、哪些还没接”的人。  
读完你会得到什么：一张按 API 分组的状态矩阵，以及下一步该补什么的明确结论。  
相关页面：`docs/playbooks/hk-data-assets.md`、`docs/cli.md`、`docs/outputs.md`、`docs/providers.md`

最后核对时间：`2026-03-18`（Asia/Shanghai）  
核对环境：当前仓库工作区 + 当前这台机器上的 RQData 试用账号  
当日 quota 快照：`TRIAL`，`remaining_days=9`，`bytes_used=3.21 MB / 1.00 GB`

## 先看结论

当前已经有的稳定资产：

* `artifacts/assets/rqdata/hk/instruments/hk_all_instruments_20260312.parquet`
* `artifacts/assets/rqdata/hk/instruments/hk_connect_full_20260312.parquet`
* `artifacts/assets/rqdata/hk/daily/hk_all_2000_20260312_daily_final_latest/`
* `artifacts/assets/rqdata/hk/pit_financials/hk_all_2000_2025_full_latest/`
* `artifacts/assets/rqdata/hk/pit_financials/hk_connect_full_2000_2025_full_latest/`
* `artifacts/assets/rqdata/hk/pit_financials/hk_connect_full_2010_2025_full_latest/`
* `artifacts/assets/universe/hk_connect_full_by_date.csv`
* `artifacts/assets/universe/hk_all_full_by_date.csv`

当前已经打通、可以继续扩成批量下载的命令：

* `csml rqdata export-hk-instruments`
* `csml rqdata mirror-hk-daily`
* `csml rqdata mirror-hk-pit-financials`
* `csml rqdata mirror-hk-ex-factors`
* `csml rqdata mirror-hk-dividends`
* `csml rqdata mirror-hk-shares`

当前最值得继续补全量的仍然是：

* `get_ex_factor`
* `get_dividend`
* `get_shares`

当前不建议当作“已打通”的：

* `hk.get_detailed_financial_items`
  现有 probe 目录存在，但 `revenue / 00005.HK / 2024q1-2025q4` 这组查询连续两次都是 `missing_remote`，还没有形成可复用资产。

当前还没接成离线资产命令的：

* `get_exchange_rate`
* `get_industry`
* `get_industry_change`
* `get_instrument_industry`
* `get_industry_mapping`
* `get_turnover_rate`
* `get_all_factor_names`
* `hk.get_announcement`

## 一个重要约定

HK 这条链路里，三个 ID 不能混：

* `ts_code`：仓库内部常用，形如 `00005.HK`
* `order_book_id`：RQData 常规 HK 标识，形如 `00005.XHKG`
* `unique_id`：部分 HK 接口真实更稳的标识，形如 `00005_01.XHKG`

本仓库现在的处理方式是：

* 研究和资产文件名仍然以 `ts_code` 为主。
* instrument 快照保存 `ts_code + order_book_id + unique_id`。
* `mirror-hk-ex-factors` / `mirror-hk-dividends` / `mirror-hk-shares` 会优先读本地 instrument 快照，把 `ts_code` 解析到 `unique_id`。

经验结论：

* 直接拿 `.HK` 去打部分底层 HK API，可能返回 `None` 或触发 `unknown order_book_id`。
* CLI 命令比临时脚本更稳，因为命令已经做了 symbol 归一化和 `unique_id` 解析。

## 状态定义

* `稳定资产`：不是单 symbol probe，能直接给后续研究复用。
* `probe 资产`：小样本验证用目录，只说明接口/命令打通过，不等于已经完成全量归档。
* `未接入`：仓库里还没有对应的批量资产命令。
* `未验证`：这轮没有做活体 probe，不代表接口一定不可用。

## 基础信息

| API | 仓库接入 | 本地资产状态 | 2026-03-18 probe | 备注 |
| --- | --- | --- | --- | --- |
| `all_instruments` | 已接，`csml rqdata export-hk-instruments` | 已有稳定资产 | `ok`，`3453` 行，约 `0.55s` | 现在是 HK symbol 映射主数据源。 |
| `instruments` | 无单独镜像命令 | 间接覆盖，大部分常用字段已在 instrument 快照里 | `ok`，单 symbol 约 `0.39s` | 需要补少量明细字段时可直接调用。 |
| `get_ex_factor` | 已接，`mirror-hk-ex-factors` | 只有 probe 资产，暂无全量 snapshot | CLI probe `ok`，`4` 行 | 2026-03-17 旧 probe 曾超时；2026-03-18 复测已打通。 |
| `get_exchange_rate` | 未接入 | 无 | 未验证 | 只有做跨币种标准化时才值得补。 |
| `get_shares` | 已接，`mirror-hk-shares` | 只有 probe 资产，暂无全量 snapshot | raw probe `ok`，CLI probe `ok` | 这条已经可扩成全量下载。 |
| `get_industry` | 未接入 | 无 | 未验证 | 次优先级。 |
| `get_industry_change` | 未接入 | 无 | 未验证 | 如果做行业归属回放再补。 |
| `get_instrument_industry` | 未接入 | 无 | 未验证 | 同上。 |
| `get_industry_mapping` | 未接入 | 无 | 未验证 | 更像字典表。 |
| `get_turnover_rate` | 未接入 | 无 | 未验证 | 当前日线里已有 `total_turnover`，先不急。 |
| `get_dividend` | 已接，`mirror-hk-dividends` | 只有 probe 资产，暂无全量 snapshot | CLI probe `ok`，`4` 行 | 2026-03-17 旧 probe 超时；2026-03-18 复测已打通。 |
| `hk.get_southbound_eligible_secs` | 无原始镜像命令，但 `csml universe hk-connect` 已使用 | 已有稳定 universe 资产 | raw probe `ok`，`613` 个 symbol，约 `0.64s` | 当前研究层面已经够用，暂不急着再做 raw mirror。 |

## 行情

| API | 仓库接入 | 本地资产状态 | 2026-03-18 probe | 备注 |
| --- | --- | --- | --- | --- |
| `get_price` | 已接，`mirror-hk-daily` | 已有稳定资产 | raw probe `ok`，`7` 行；CLI probe `ok` | 日线这条已经成熟。pipeline 的 symbol cache 也能继续用。 |

## 财务

| API | 仓库接入 | 本地资产状态 | 2026-03-18 probe | 备注 |
| --- | --- | --- | --- | --- |
| `get_pit_financials_ex` | 已接，`mirror-hk-pit-financials` | 已有稳定资产 | raw probe `ok`，`8` 行；CLI probe `ok` | 直接传 `00005.HK` 的临时脚本可能拿不到值，CLI 路线正常。 |
| `hk.get_detailed_financial_items` | 已接，`mirror-hk-financial-details` | 只有 probe 目录，暂无可复用资产 | CLI probe `completed` 但 `0` 行 | 当前按 `revenue / 00005.HK / 2024q1-2025q4` 连续两次都是 `missing_remote`。先别当成已打通。 |

## 因子

| API | 仓库接入 | 本地资产状态 | 2026-03-18 probe | 备注 |
| --- | --- | --- | --- | --- |
| `get_factor` | 仅 runtime overlay 支持，不走离线 mirror | 无离线资产 | 未单独 probe | 当前仅在 `fundamentals.source=provider` 且 `endpoint=get_factor` 时使用。默认口径是 `hk_total_market_val`、`pe_ratio_ttm`、`pb_ratio_ttm`。 |
| `get_all_factor_names` | 未接入 | 无 | 未验证 | 只有要扩 factor 字段浏览器时再补。 |

## 公告

| API | 仓库接入 | 本地资产状态 | 2026-03-18 probe | 备注 |
| --- | --- | --- | --- | --- |
| `hk.get_announcement` | 未接入 | 无 | 未验证 | 当前不是主线，先不升成资产命令。 |

## 当前目录里哪些不要误判

下面这些目录存在，但不能当成“已完成资产”：

* `artifacts/assets/rqdata/hk/ex_factors/probe_00005_2025_ex_factors`
* `artifacts/assets/rqdata/hk/dividends/probe_00005_2025_dividends`
* `artifacts/assets/rqdata/hk/ex_factors/probe_00005_2025_ex_factors_debug`
* `artifacts/assets/rqdata/hk/ex_factors/probe_00005_2025_ex_factors_retry`
* `artifacts/assets/rqdata/hk/daily/probe_00005_202501_daily_recheck`

原因：

* 这些目录里有一部分是 `2026-03-17` 的失败 probe。
* 有的只写了 `fields.txt / symbols.txt`。
* 有的虽然写了 `manifest.yml`，但 `status=completed_with_failures`，`symbols_written=0`。

当前能算“probe 成功”的小样本目录主要是：

* `artifacts/assets/rqdata/hk/ex_factors/probe_00005_2025_ex_factors_v3/`
* `artifacts/assets/rqdata/hk/dividends/probe_00005_2025_dividends_v3/`
* `artifacts/assets/rqdata/hk/shares/probe_00005_2025_shares_v2/`
* `artifacts/assets/rqdata/hk/daily/probe_00005_202501_daily_v2/`
* `artifacts/assets/rqdata/hk/pit_financials/probe_00005_2024_2025_pit_v2/`

## 下一步建议

推荐按这个顺序继续：

1. 不动 `daily`、`pit_financials`、`instruments` 这三条主线，它们已经是稳定资产。
2. 把 `ex_factors`、`dividends`、`shares` 从单 symbol probe 扩成 `hk_connect_full_by_date.csv` 范围的正式 snapshot。
3. `financial_details` 先不要全量跑。先再找 1 到 3 个确定有值的 field/sample 验证出“哪种查询能稳定出行”。
4. `exchange_rate`、行业、公告、`factor_names` 保持未接入，等研究真正需要再升格。

## 如何刷新这页

最小检查顺序：

1. `csml rqdata quota --pretty`
2. `csml rqdata export-hk-instruments --out ...`
3. `csml rqdata mirror-hk-daily --symbol 00005.HK ...`
4. `csml rqdata mirror-hk-pit-financials --symbol 00005.HK --field revenue ...`
5. `csml rqdata mirror-hk-ex-factors --symbol 00005.HK ...`
6. `csml rqdata mirror-hk-dividends --symbol 00005.HK ...`
7. `csml rqdata mirror-hk-shares --symbol 00005.HK ...`

如果这些 probe 有变化，再更新本页的“最后核对时间”和矩阵结论。
