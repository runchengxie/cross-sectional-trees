# HK 数据健康检查 Runbook

本页解决什么：把 HK / RQData 本地资产健康检查整理成可直接复制执行的命令与脚本。  
本页不解决什么：不重复展开每个 health 命令的全部参数定义。  
适合谁：准备在本地批量跑资产体检、落 report / log、再让代理复核结果的人。  
读完你会得到什么：一套从轻到重的检查顺序、可直接执行的脚本入口、以及逐条手动命令。  
相关页面：`docs/cli.md`、`docs/dev.md`、`docs/playbooks/hk-data-assets.md`、`docs/playbooks/hk-intraday-assets.md`

## 先说结论

推荐顺序：

1. 先跑 `inspect-hk-current-health`
2. 再跑 `daily_clean` 和 `valuation` 的 `inspect-hk-asset-health`
3. 再跑 `inspect-hk-pit-coverage --include-health`
4. 只有确实需要分钟线时，再跑 `inspect-hk-intraday-health`
5. 如果你要把多条检查聚合成一份维护者 workflow report，再额外跑 `scripts/internal/run_hk_asset_workflow.py --phase inspect`

原因：

* `current-health` 只看 contract、alias、manifest 和 `as_of`，最轻。
* `asset-health` 才会真的扫 snapshot 数据；`--include-history` 会更重。
* `pit-coverage --include-health` 回答的是“到目标调仓日为止，PIT 是否还能安全前推”。
* intraday 检查 I/O 最重，应单独控制。

## helper 片段要不要单独跑

你之前那段：

```bash
mkdir -p artifacts/reports artifacts/reports/health_logs
TS=$(date +%Y%m%d_%H%M%S)
TARGET_DATE=20260409

run_and_log() { ... }
read_current_path() { ... }
```

不是单独的健康检查命令。

它做的是两件事：

* 创建 report / log 目录
* 给后面的 health 命令提供 shell 包装函数和 current asset 路径解析

所以它本身不需要当成“一条检查”去跑；更适合固化成脚本。仓库现在已经提供：

* `scripts/dev/run_hk_health_checks.sh`

这份脚本把上面的 helper 包起来了，不需要你再手动先定义 shell 函数。

## 最推荐：直接跑脚本

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
  --artifacts-root /data/csml-artifacts \
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

脚本默认会产出：

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
* 脚本本身不是公开 `csml` CLI 子命令；它是本地运维辅助入口。

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

from csml.current_assets import default_hk_current_contract_path, hk_current_candidate_paths

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
uv run csml rqdata inspect-hk-current-health \
  --target-date "$TARGET_DATE" \
  --fail-on-severity "$FAIL_ON_SEVERITY" \
  --format json \
  --out "artifacts/reports/hk_current_health_${TARGET_DATE}.json" \
  >"artifacts/reports/health_logs/${TS}_current_health.log" 2>&1
```

### 3. 跑 daily_clean health

```bash
uv run csml rqdata inspect-hk-asset-health \
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
uv run csml rqdata inspect-hk-asset-health \
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
uv run csml rqdata inspect-hk-pit-coverage \
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
uv run csml rqdata inspect-hk-intraday-health \
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

1. `hk_current_health_<date>.json`
2. `hk_daily_clean_health_<date>.json`
3. `hk_valuation_health_<date>.json`
4. `hk_pit_health_<date>.json`
5. `hk_intraday_health_<date>.json`
6. `*_hk_health_check_summary.txt`
7. 各条 `*.log`

如果你要让代理复核，优先把 JSON report 和 summary 发过来，不要先把大 parquet 发过来。

## 什么时候值得升级成正式命令

值得，但建议分两步看：

1. 现在这一步先用 `scripts/dev/run_hk_health_checks.sh` 固化本地 runbook。
2. 如果后面这套检查已经稳定成团队日常入口，再考虑升成公开 `csml rqdata inspect-hk-health-bundle` 之类的聚合子命令。

当前先不直接升成公开 CLI 的原因：

* 仓库已经有单项 health 命令，缺的是“安全地组织执行”的外壳。
* 这套顺序和默认配置仍然偏 HK + RQData 本地运维口径。
* 先用脚本迭代，成本更低，也不容易过早承诺 CLI 稳定性。
