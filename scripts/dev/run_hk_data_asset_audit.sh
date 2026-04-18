#!/usr/bin/env bash
set -euo pipefail

TARGET_DATE=""
ARTIFACTS_ROOT="artifacts"
INTRADAY_MODE="metadata"
FAIL_ON_SEVERITY="none"
RUN_REFRESH="0"
REFRESH_DRY_RUN="1"
OUT=""
EXTRA_ARGS=()

usage() {
  cat <<'EOF'
Usage:
  scripts/dev/run_hk_data_asset_audit.sh [options] [-- audit args...]

Runs the unified HK data asset audit. The default mode is non-destructive:
it writes inventory, ETF daily freshness, intraday freshness, health summary,
repair candidates, and a dry-run prune plan without deleting or repairing data.

Options:
  --target-date YYYYMMDD       Target date. Default: hk_current target_date.
  --artifacts-root PATH        Artifacts root. Default: artifacts.
  --intraday-mode MODE         metadata|scan|health. Default: metadata.
  --fail-on-severity LEVEL     none|info|warning|error. Default: none.
  --run-refresh                Run workflow refresh+inspect before final verdict.
  --refresh-execute            If --run-refresh is set, execute it instead of dry-run.
  --out PATH                   Output JSON path. Default: artifacts/reports/hk_data_asset_audit_<target>.json.
  -h, --help                   Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-date)
      TARGET_DATE="$2"
      shift 2
      ;;
    --artifacts-root)
      ARTIFACTS_ROOT="$2"
      shift 2
      ;;
    --intraday-mode)
      INTRADAY_MODE="$2"
      shift 2
      ;;
    --fail-on-severity)
      FAIL_ON_SEVERITY="$2"
      shift 2
      ;;
    --run-refresh)
      RUN_REFRESH="1"
      shift
      ;;
    --refresh-execute)
      REFRESH_DRY_RUN="0"
      shift
      ;;
    --out)
      OUT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      EXTRA_ARGS+=("$@")
      break
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ -z "$TARGET_DATE" ]]; then
  TARGET_DATE="$(uv run python - "$ARTIFACTS_ROOT" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).expanduser().resolve()
contract = root / "metadata" / "current_assets" / "hk_current.json"
if contract.exists():
    payload = json.loads(contract.read_text(encoding="utf-8"))
    target = str(payload.get("contract", {}).get("target_date") or "").strip()
    if target:
        print(target)
        raise SystemExit(0)
print("")
PY
)"
fi

if [[ -z "$TARGET_DATE" ]]; then
  TARGET_DATE="$(date +%Y%m%d)"
fi

mkdir -p "$ARTIFACTS_ROOT/reports"
if [[ -z "$OUT" ]]; then
  OUT="$ARTIFACTS_ROOT/reports/hk_data_asset_audit_${TARGET_DATE}.json"
fi

CMD=(
  uv run csml rqdata inspect-hk-data-assets
  --artifacts-root "$ARTIFACTS_ROOT"
  --target-date "$TARGET_DATE"
  --intraday-mode "$INTRADAY_MODE"
  --fail-on-severity "$FAIL_ON_SEVERITY"
  --format json
  --out "$OUT"
)

if [[ "$RUN_REFRESH" == "1" ]]; then
  CMD+=(--run-refresh)
  if [[ "$REFRESH_DRY_RUN" == "1" ]]; then
    CMD+=(--refresh-dry-run)
  fi
fi

CMD+=("${EXTRA_ARGS[@]}")

printf '+ '
printf '%q ' "${CMD[@]}"
printf '\n'
"${CMD[@]}"
echo "Wrote $OUT"
