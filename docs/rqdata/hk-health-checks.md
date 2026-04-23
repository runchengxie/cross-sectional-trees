# HK 数据健康检查 Runbook

本页解决什么：把 HK / RQData 本地资产健康检查整理成可直接复制执行的命令与脚本。\
本页不解决什么：不重复展开每个 health 命令的全部参数定义。\
适合谁：准备在本地批量跑资产体检、落 report / log、再让代理复核结果的人。\
读完你会得到什么：一套从轻到重的检查顺序、可直接执行的脚本入口、以及逐条手动命令。\
相关页面：`docs/cli.md`、`docs/dev.md`、`docs/playbooks/hk-data-assets.md`、`docs/playbooks/hk-intraday-assets.md`

## 先说结论

推荐顺序：

1. 先跑 `inspect-hk-data-assets` 或 `scripts/dev/run_hk_data_asset_audit.sh`，拿统一资产清单和 dry-run 计划。
2. 如果要下钻，再跑 `inspect-hk-current-health`。
3. 再跑 `daily_clean` 和 `valuation` 的 `inspect-hk-asset-health`。
4. 再跑 `inspect-hk-pit-coverage --include-health`。
5. 只有确实需要分钟线时，再跑 `inspect-hk-intraday-health`。
6. 如果你要把多条检查聚合成一份维护者 workflow report，再额外跑 `scripts/internal/run_hk_asset_workflow.py --phase inspect`。

原因：

* `data-assets` 聚合命令默认不刷新、不修复、不删除，适合作为维护者审计入口。
* `current-health` 只看 contract、alias、manifest 和 `as_of`，最轻。
* `asset-health` 才会真的扫 snapshot 数据；`--include-history` 会更重。
* `pit-coverage --include-health` 回答的是“到目标调仓日为止，PIT 是否还能安全前推”。
* intraday 检查 I/O 最重，应单独控制。

## helper 片段

```bash
mkdir -p artifacts/reports artifacts/reports/health_logs
TS=$(date +%Y%m%d_%H%M%S)
TARGET_DATE=20260409

run_and_log() { ... }
read_current_path() { ... }
```

它做的是两件事：

* 创建 report / log 目录
* 给后面的 health 命令提供 shell 包装函数和 current asset 路径解析

所以它本身不需要当成“一条检查”去跑；更适合固化成脚本。仓库现在已经提供：

* `scripts/dev/run_hk_data_asset_audit.sh`
* `scripts/dev/run_hk_health_checks.sh`
* `scripts/dev/run_hk_pit_health.sh`

这份脚本把上面的 helper 包起来了，不需要你再手动先定义 shell 函数。

## 最推荐：直接跑脚本

先生成统一审计 report：

```bash
bash scripts/dev/run_hk_data_asset_audit.sh --target-date 20260409
```

如果要在审计里串一个 patch refresh dry-run：

```bash
bash scripts/dev/run_hk_data_asset_audit.sh --target-date 20260409 --run-refresh
```

最小用法：

```bash
bash scripts/dev/run_hk_health_checks.sh --target-date 20260409
```

如果还要加分钟线检查：

```bash
bash scripts/dev/run_hk_health_checks.sh --target-date 20260409 --with-intraday
```

如果还要顺手生成维护者 workflow inspect report：

```bash
bash scripts/dev/run_hk_health_checks.sh --target-date 20260409 --with-workflow-inspect
```

常见变体：

```bash
# 改 artifacts 根目录
bash scripts/dev/run_hk_health_checks.sh \
  --artifacts-root /data/cstree-artifacts \
  --target-date 20260409

# 改质量闸门
bash scripts/dev/run_hk_health_checks.sh \
  --target-date 20260409 \
  --fail-on-severity error

# 改 PIT 配置入口
bash scripts/dev/run_hk_health_checks.sh \
  --target-date 20260409 \
  --pit-config configs/experiments/baseline/hk_selected.yml
```

只想单独检查某个 PIT config 时：

```bash
bash scripts/dev/run_hk_pit_health.sh \
  --target-date 20260409 \
  --config configs/experiments/variants/hk_selected__quarterly_pit_core_hybrid_provider_dense.yml \
  --name provider_dense
```

单项 PIT 脚本默认会产出：

* `artifacts/reports/hk_pit_health_<date>_<name>.json`
* `artifacts/reports/health_logs/*_pit_health_<name>.log`

批量脚本默认会产出：

* `artifacts/reports/hk_data_asset_audit_<date>.json`（仅 `run_hk_data_asset_audit.sh`）
* `artifacts/reports/hk_current_health_<date>.json`
* `artifacts/reports/hk_daily_clean_health_<date>.json`
* `artifacts/reports/hk_valuation_health_<date>.json`
* `artifacts/reports/hk_pit_health_<date>.json`
* `artifacts/reports/hk_intraday_health_<date>.json`（仅 `--with-intraday`）
* `artifacts/reports/hk_asset_refresh_<date>.json`（仅 `--with-workflow-inspect`）
* `artifacts/reports/health_logs/*_<name>.log`
* `artifacts/reports/health_logs/*_hk_health_check_summary.txt`

说明：

* 脚本会优先从 `artifacts/metadata/current_assets/hk_current.json` 解析 `daily_clean`、`valuation`、`intraday` 的 resolved path。
* 如果 current contract 缺失，会回退到默认 alias 路径。
* 脚本本身不是公开 `cstree` CLI 子命令；它是本地运维辅助入口。

## 逐条手动跑

如果你想手动逐条复制执行，下面这组命令可以直接用。

### 0. 初始化目录和常量

```bash
mkdir -p artifacts/reports artifacts/reports/health_logs
TS=$(date +%Y%m%d_%H%M%S)
TARGET_DATE=20260409
FAIL_ON_SEVERITY=warning
HISTORY_SAMPLE_LIMIT=10
PIT_CONFIG=configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml
```

### 1. 解析 current asset 路径

```bash
read_current_path() {
  uv run python - "artifacts" "$1" <<'PY'
import json
import sys
from pathlib import Path

from cstree.current_assets import default_hk_current_contract_path, hk_current_candidate_paths

artifacts_root = Path(sys.argv[1]).expanduser().resolve()
asset_key = sys.argv[2]
contract_path = default_hk_current_contract_path(artifacts_root)

if contract_path.exists():
    payload = json.loads(contract_path.read_text(encoding="utf-8"))
    entry = payload.get("assets", {}).get(asset_key, {})
    resolved = str(entry.get("resolved_path") or "").strip()
    if resolved:
        print(resolved)
        raise SystemExit(0)

candidate = hk_current_candidate_paths(artifacts_root).get(asset_key)
if candidate is None:
    raise SystemExit(f"Unknown hk_current asset key: {asset_key}")
print(str(candidate))
PY
}

DAILY_CLEAN_DIR="$(read_current_path daily_clean)"
VALUATION_DIR="$(read_current_path valuation)"
INTRADAY_DIR="$(read_current_path intraday)"
```

### 2. 跑 current health

```bash
uv run cstree rqdata inspect-hk-current-health \
  --target-date "$TARGET_DATE" \
  --fail-on-severity "$FAIL_ON_SEVERITY" \
  --format json \
  --out "artifacts/reports/hk_current_health_${TARGET_DATE}.json" \
  >"artifacts/reports/health_logs/${TS}_current_health.log" 2>&1
```

### 3. 跑 daily_clean health

```bash
uv run cstree rqdata inspect-hk-asset-health \
  --asset-dir "$DAILY_CLEAN_DIR" \
  --target-date "$TARGET_DATE" \
  --include-history \
  --history-sample-limit "$HISTORY_SAMPLE_LIMIT" \
  --fail-on-severity "$FAIL_ON_SEVERITY" \
  --format json \
  --out "artifacts/reports/hk_daily_clean_health_${TARGET_DATE}.json" \
  >"artifacts/reports/health_logs/${TS}_daily_clean_health.log" 2>&1
```

### 4. 跑 valuation health

```bash
uv run cstree rqdata inspect-hk-asset-health \
  --asset-dir "$VALUATION_DIR" \
  --daily-asset-dir "$DAILY_CLEAN_DIR" \
  --target-date "$TARGET_DATE" \
  --include-history \
  --history-sample-limit "$HISTORY_SAMPLE_LIMIT" \
  --fail-on-severity "$FAIL_ON_SEVERITY" \
  --format json \
  --out "artifacts/reports/hk_valuation_health_${TARGET_DATE}.json" \
  >"artifacts/reports/health_logs/${TS}_valuation_health.log" 2>&1
```

### 5. 跑 PIT health

```bash
uv run cstree rqdata inspect-hk-pit-coverage \
  --config "$PIT_CONFIG" \
  --mode both \
  --include-health \
  --target-date "$TARGET_DATE" \
  --fail-on-severity "$FAIL_ON_SEVERITY" \
  --format json \
  --out "artifacts/reports/hk_pit_health_${TARGET_DATE}.json" \
  >"artifacts/reports/health_logs/${TS}_pit_health.log" 2>&1
```

### 6. 需要时再跑 intraday health

```bash
uv run cstree rqdata inspect-hk-intraday-health \
  --input "$INTRADAY_DIR" \
  --daily-asset-dir "$DAILY_CLEAN_DIR" \
  --fail-on-severity "$FAIL_ON_SEVERITY" \
  --format json \
  --out "artifacts/reports/hk_intraday_health_${TARGET_DATE}.json" \
  >"artifacts/reports/health_logs/${TS}_intraday_health.log" 2>&1
```

### 7. 需要聚合 workflow inspect 时再跑

```bash
python scripts/internal/run_hk_asset_workflow.py \
  --phase inspect \
  --target-date "$TARGET_DATE" \
  --workflow-report "artifacts/reports/hk_asset_refresh_${TARGET_DATE}.json" \
  >"artifacts/reports/health_logs/${TS}_workflow_inspect.log" 2>&1
```

## 看哪些文件最值钱

优先级建议：

1. `hk_data_asset_audit_<date>.json`
2. `hk_current_health_<date>.json`
3. `hk_daily_clean_health_<date>.json`
4. `hk_valuation_health_<date>.json`
5. `hk_pit_health_<date>.json`
6. `hk_intraday_health_<date>.json`
7. `*_hk_health_check_summary.txt`
8. 各条 `*.log`

如果你要让代理复核，优先把 JSON report 和 summary 发过来，不要先把大 parquet 发过来。

## 聚合命令和单项命令怎么分工

`cstree rqdata inspect-hk-data-assets` 已经是公开 CLI 入口，适合先回答“当前资产是否新鲜、缺口在哪里、哪些路径可考虑清理”。它默认只读和 dry-run。

保留单项命令的原因：

* 聚合命令偏审计和决策，不替代 `inspect-hk-asset-health` 的字段级深扫。
* intraday 扫描 I/O 重，默认仍由 `--intraday-mode` 显式控制。
* refresh、repair 和 delete 都需要显式参数解锁，避免审计命令被误用成破坏性维护入口。
