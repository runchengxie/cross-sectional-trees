# cross-sectional-xgboost

使用 TuShare / RQData / EODHD 日线数据与 XGBoost 回归进行截面因子挖掘和评估（支持 A/HK/US 多市场配置切换）。流程包含特征工程、时间序列切分、IC 评估、分位数组合收益、换手率估计与特征重要性输出。

项目是基于一个散户的视角，因此：

* 低频策略
* 无做空
* 不涉及过大的股票池，避免带来巨大的滑点和交易成本

## 功能概览

* 拉取 TuShare / RQData / EODHD 日线数据（按 `data.provider` 选择数据源）并缓存到 `cache/`（Parquet）
* 计算 SMA、RSI、MACD、成交量等技术指标
* 训练 XGBoost 回归模型并评估截面 IC
* 输出分位数组合收益、长短组合收益、换手率估计

## 环境与依赖

* Python >= 3.12
* 依赖见 `pyproject.toml`
* 可选：`uv` + `direnv`（仓库内已提供 `.envrc.example`）

## 安装方式

使用 `uv`（推荐）：

```bash
uv venv --seed
uv sync
```

使用 `venv + pip`：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## 配置 TuShare Token（仅当 data.provider=tushare）

主程序与工具脚本优先读取 `TUSHARE_TOKEN`，其次 `TUSHARE_TOKEN_2`，仅在兼容旧配置时才读取 `TUSHARE_API_KEY`。
如果你已从 `.env.example` 复制到 `.env`，请确保补充 `TUSHARE_TOKEN`（可选 `TUSHARE_TOKEN_2` 作为备用）。
注意：当前实现不会自动轮换 Token，`TUSHARE_TOKEN_2` 仅作为备用读取。

示例 `.env`：

```bash
TUSHARE_TOKEN="replace-with-your-tushare-pro-token"
TUSHARE_TOKEN_2="replace-with-your-second-tushare-pro-token"
# Legacy alias (avoid using unless required by old setups)
# TUSHARE_API_KEY="replace-with-your-tushare-pro-token"
EODHD_API_TOKEN="replace-with-your-eodhd-token"
RQDATA_USERNAME="your-user"
RQDATA_PASSWORD="your-pass"
```

若使用 `direnv`：

```bash
cp .envrc.example .envrc
direnv allow
```

## 配置 RQData（仅当 data.provider=rqdata）

需要安装 `rqdatac`。项目仅用到日线行情接口，不要求 `rqdatac_hk`（除非你要用港股通成分股等扩展功能）。

如需传入初始化参数，可在配置中设置 `data.rqdata.init`，例如：

```yaml
data:
  provider: rqdata
  rqdata:
    init:
      username: "your-user"
      password: "your-pass"
```

也可使用环境变量 `RQDATA_USERNAME`（或 `RQDATA_USER`）/ `RQDATA_PASSWORD`（配置文件优先级更高）。

## 配置 EODHD（仅当 data.provider=eodhd）

使用环境变量 `EODHD_API_TOKEN`（或配置 `data.eodhd.api_token`）。可选字段：

* `data.eodhd.exchange`：交易所代码（如 `HK`）。
* `data.eodhd.hk_symbol_mode`：港股代码转换模式（`keep` / `strip_one` / `strip_all` / `pad4` / `pad5`）。
* `data.eodhd.period` / `data.eodhd.order` / `data.eodhd.fmt`：用于日线接口的参数透传。

## 运行

```bash
python main.py --config config/config.yml
python main.py --config config/config.cn.yml
python main.py --config config/config.hk.yml
python main.py --config config/config.us.yml
```

输出包含：

* CV IC 与 Daily IC
* 分位数收益与长短组合收益
* Top-K 换手率估计与成本拖累
* 简易 long-only 回测（按再平衡周期持有到下一次）
* 特征重要性排序

## 工具脚本

* `project_tools/verify_tushare_tokens.py`：验证 TuShare Token 是否可用
* `project_tools/combine_code.py`：打包项目源码为单文件文本（用于归档/审查）
* `project_tools/fetch_index_components.py`：拉取指数成分并导出为 `symbols_file` 列表
* `project_tools/build_hk_connect_universe.py`：基于港股通 PIT + 成交额筛选生成 `universe_by_date.csv`

## 自定义参数

在 `config/config.yml` 或各市场配置中调整：

* `universe`：股票池、过滤条件、最小截面规模（支持 `by_date_file` 动态池）
* `market`：`cn` / `hk` / `us`
* `data`：`provider`、`rqdata` / `eodhd` 或 `daily_endpoint` / `basic_endpoint` / `column_map`（字段映射为 `trade_date/ts_code/close/vol/amount`）
* `label`：预测窗口、shift、winsorize
* `features`：特征清单与窗口
* `model`：XGBoost 参数
* `eval`：切分、分位数、换手成本、embargo，以及可选的 `report_train_ic` 与 `permutation_test`
* `backtest`：再平衡频率、Top-K、成本与基准

示例（生成指数成分列表）：

```bash
python project_tools/fetch_index_components.py \
  --index-code 000300.SH \
  --month 202501 \
  --out hs300_symbols.txt
```

示例（港股通 PIT + 流动性池）：

默认配置（建议先用默认跑一遍）：

```bash
python project_tools/build_hk_connect_universe.py
```

覆盖单个参数：

```bash
python project_tools/build_hk_connect_universe.py --top-quantile 0.9
```

明确日期区间（回测）： 

```bash
python project_tools/build_hk_connect_universe.py \
  --start-date 20200101 \
  --end-date 20251231
```

日常更新（默认 T-1）： 

```bash
python project_tools/build_hk_connect_universe.py --mode daily
```

然后在配置中设置：

```yaml
universe:
  by_date_file: "universe_by_date.csv"
```

说明：

* `drop_suspended` 通过成交量/成交额为 0 的数据近似过滤停牌。
* `drop_st` 基于 `stock_basic` 的名称匹配，仅适用于 A 股，属于粗过滤。
* 日线缓存文件名统一为 `{market}_{provider}_daily_{symbol}_{START}_{END}.parquet`。
* 港股通股票池默认配置在 `config/universe.hk_connect.yml`，CLI 参数可覆盖。
* `mode=backtest` 要求固定 `end_date`；`mode=daily` 默认使用最近一个已完成交易日 (T-1)，并在输出文件名后追加日期。
* `top_quantile` 的语义是“保留分位数以上的标的”，例如 `0.8` 会保留流动性最高的 20%。
* 默认会在 CSV 旁输出 `*.meta.yml`，记录最终生效参数与每期股票池数量。
