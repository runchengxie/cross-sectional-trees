# Cookbook

## 推荐流程（港股示例）

1. （如果你做 HK 且需要严谨历史池）先把 PIT 股票池准备好（示例里是 hk-connect）。

   ```bash
   csxgb universe hk-connect --config config/universe.hk_connect.yml
   ```

1. 跑网格并查看结果。

   ```bash
   csxgb grid --config config/hk.yml
   ls -lh out/runs/grid_summary.csv
   ```

1. 选一组满意的参数（参考 Sharpe / 回撤 / 换手等）。

1. 复制一份配置：`config/hk.yml -> config/hk_selected.yml`，改这些键：`eval.top_k`、`backtest.top_k`、`eval.transaction_cost_bps`、`backtest.transaction_cost_bps`。

1. 跑正式单次：

   ```bash
   csxgb run --config config/hk_selected.yml
   ```

   然后你会拿到完整产物目录，包含 `summary.json`、`config.used.yml`、回测/IC/特征重要性、以及持仓 CSV 等。

1. 实盘跑一次，获得当月的持股建议

   ```bash
   csxgb snapshot --config config/hk_selected_live.yml
   # 或者你已经跑过了，只想复用最新结果
   csxgb snapshot --config config/hk_selected_live.yml --skip-run
   ```

## 覆盖默认网格参数（可选）

```bash
csxgb grid --config config/hk.yml \
  --top-k 5,10 \
  --cost-bps 25,40 \
  --output out/runs/my_grid.csv \
  --run-name-prefix hk_grid
```
