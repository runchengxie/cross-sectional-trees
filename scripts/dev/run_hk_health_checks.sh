#!/usr/bin/env bash

set -u -o pipefail

ARTIFACTS_ROOT="artifacts"
TARGET_DATE=""
FAIL_ON_SEVERITY="warning"
HISTORY_SAMPLE_LIMIT="10"
PIT_CONFIG="configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml"
WITH_INTRADAY="0"
WITH_WORKFLOW_INSPECT="0"

usage() {
  cat <<'EOF'
Usage:
  scripts/dev/run_hk_health_checks.sh [options]

Options:
  --target-date YYYYMMDD        Target date used by the health checks.
                                Default: hk_current contract.target_date,
                                else latest asset as_of, else today.
  --artifacts-root PATH         Artifacts root. Default: artifacts
  --fail-on-severity LEVEL      none|info|warning|error. Default: warning
  --history-sample-limit N      Sample row count for asset history checks.
                                Default: 10
  --pit-config PATH             Config passed to inspect-hk-pit-coverage.
                                Default:
                                configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml
  --with-intraday               Also run intraday health.
  --with-workflow-inspect       Also run the maintainer workflow inspect phase.
  -h, --help                    Show this help text.

Outputs:
  <artifacts-root>/reports/*.json
  <artifacts-root>/reports/health_logs/*.log
  <artifacts-root>/reports/health_logs/*_hk_health_check_summary.txt
EOF
}

read_current_path() {
  local asset_key="$1"
  uv run python - "$ARTIFACTS_ROOT" "$asset_key" <<'PY'
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

resolve_default_target_date() {
  uv run python - "$ARTIFACTS_ROOT" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

from cstree.current_assets import default_hk_current_contract_path

artifacts_root = Path(sys.argv[1]).expanduser().resolve()
contract_path = default_hk_current_contract_path(artifacts_root)

if contract_path.exists():
    payload = json.loads(contract_path.read_text(encoding="utf-8"))
    contract = payload.get("contract", {})
    target_date = str(contract.get("target_date") or "").strip()
    if target_date:
        print(target_date)
        raise SystemExit(0)

    assets = payload.get("assets", {})
    as_of_values = [
        str(entry.get("as_of") or "").strip()
        for entry in assets.values()
        if isinstance(entry, dict) and str(entry.get("as_of") or "").strip()
    ]
    if as_of_values:
        print(max(as_of_values))
        raise SystemExit(0)

print(datetime.now().strftime("%Y%m%d"))
PY
}

run_and_log() {
  local name="$1"
  shift
  local log_path="${LOG_DIR}/${TS}_${name}.log"
  {
    echo "# $(date -Is) :: ${name}"
    printf '+ '
    printf '%q ' "$@"
    printf '\n'
    "$@"
    local rc=$?
    echo "exit_code=${rc}"
    return "${rc}"
  } >"${log_path}" 2>&1
}

record_result() {
  local name="$1"
  local rc="$2"
  local report_path="$3"
  local log_path="${LOG_DIR}/${TS}_${name}.log"
  {
    echo "[${name}] exit_code=${rc}"
    echo "report=${report_path}"
    echo "log=${log_path}"
    echo
  } >>"${SUMMARY_PATH}"
}

run_step() {
  local name="$1"
  local report_path="$2"
  shift 2

  if run_and_log "$name" "$@"; then
    local rc=0
  else
    local rc=$?
    OVERALL_RC=1
  fi

  record_result "$name" "$rc" "$report_path"
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
    --fail-on-severity)
      FAIL_ON_SEVERITY="$2"
      shift 2
      ;;
    --history-sample-limit)
      HISTORY_SAMPLE_LIMIT="$2"
      shift 2
      ;;
    --pit-config)
      PIT_CONFIG="$2"
      shift 2
      ;;
    --with-intraday)
      WITH_INTRADAY="1"
      shift
      ;;
    --with-workflow-inspect)
      WITH_WORKFLOW_INSPECT="1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

mkdir -p "${ARTIFACTS_ROOT}/reports" "${ARTIFACTS_ROOT}/reports/health_logs"

TS="$(date +%Y%m%d_%H%M%S)"
LOG_DIR="${ARTIFACTS_ROOT}/reports/health_logs"
SUMMARY_PATH="${LOG_DIR}/${TS}_hk_health_check_summary.txt"
OVERALL_RC=0

if [[ -z "${TARGET_DATE}" ]]; then
  TARGET_DATE="$(resolve_default_target_date)"
fi

DAILY_CLEAN_DIR="$(read_current_path daily_clean)"
VALUATION_DIR="$(read_current_path valuation)"

{
  echo "# HK health checks"
  echo "timestamp=${TS}"
  echo "target_date=${TARGET_DATE}"
  echo "artifacts_root=${ARTIFACTS_ROOT}"
  echo "fail_on_severity=${FAIL_ON_SEVERITY}"
  echo "pit_config=${PIT_CONFIG}"
  echo "daily_clean_dir=${DAILY_CLEAN_DIR}"
  echo "valuation_dir=${VALUATION_DIR}"
  echo
} >"${SUMMARY_PATH}"

run_step \
  current_health \
  "${ARTIFACTS_ROOT}/reports/hk_current_health_${TARGET_DATE}.json" \
  uv run cstree rqdata inspect-hk-current-health \
  --artifacts-root "${ARTIFACTS_ROOT}" \
  --target-date "${TARGET_DATE}" \
  --fail-on-severity "${FAIL_ON_SEVERITY}" \
  --format json \
  --out "${ARTIFACTS_ROOT}/reports/hk_current_health_${TARGET_DATE}.json"

run_step \
  daily_clean_health \
  "${ARTIFACTS_ROOT}/reports/hk_daily_clean_health_${TARGET_DATE}.json" \
  uv run cstree rqdata inspect-hk-asset-health \
  --asset-dir "${DAILY_CLEAN_DIR}" \
  --target-date "${TARGET_DATE}" \
  --include-history \
  --history-sample-limit "${HISTORY_SAMPLE_LIMIT}" \
  --fail-on-severity "${FAIL_ON_SEVERITY}" \
  --format json \
  --out "${ARTIFACTS_ROOT}/reports/hk_daily_clean_health_${TARGET_DATE}.json"

run_step \
  valuation_health \
  "${ARTIFACTS_ROOT}/reports/hk_valuation_health_${TARGET_DATE}.json" \
  uv run cstree rqdata inspect-hk-asset-health \
  --asset-dir "${VALUATION_DIR}" \
  --daily-asset-dir "${DAILY_CLEAN_DIR}" \
  --target-date "${TARGET_DATE}" \
  --include-history \
  --history-sample-limit "${HISTORY_SAMPLE_LIMIT}" \
  --fail-on-severity "${FAIL_ON_SEVERITY}" \
  --format json \
  --out "${ARTIFACTS_ROOT}/reports/hk_valuation_health_${TARGET_DATE}.json"

run_step \
  pit_health \
  "${ARTIFACTS_ROOT}/reports/hk_pit_health_${TARGET_DATE}.json" \
  uv run cstree rqdata inspect-hk-pit-coverage \
  --config "${PIT_CONFIG}" \
  --mode both \
  --include-health \
  --target-date "${TARGET_DATE}" \
  --fail-on-severity "${FAIL_ON_SEVERITY}" \
  --format json \
  --out "${ARTIFACTS_ROOT}/reports/hk_pit_health_${TARGET_DATE}.json"

if [[ "${WITH_INTRADAY}" == "1" ]]; then
  INTRADAY_DIR="$(read_current_path intraday)"
  {
    echo "intraday_dir=${INTRADAY_DIR}"
    echo
  } >>"${SUMMARY_PATH}"

  run_step \
    intraday_health \
    "${ARTIFACTS_ROOT}/reports/hk_intraday_health_${TARGET_DATE}.json" \
    uv run cstree rqdata inspect-hk-intraday-health \
    --input "${INTRADAY_DIR}" \
    --daily-asset-dir "${DAILY_CLEAN_DIR}" \
    --fail-on-severity "${FAIL_ON_SEVERITY}" \
    --format json \
    --out "${ARTIFACTS_ROOT}/reports/hk_intraday_health_${TARGET_DATE}.json"
fi

if [[ "${WITH_WORKFLOW_INSPECT}" == "1" ]]; then
  run_step \
    workflow_inspect \
    "${ARTIFACTS_ROOT}/reports/hk_asset_refresh_${TARGET_DATE}.json" \
    python scripts/internal/run_hk_asset_workflow.py \
    --phase inspect \
    --target-date "${TARGET_DATE}" \
    --workflow-report "${ARTIFACTS_ROOT}/reports/hk_asset_refresh_${TARGET_DATE}.json"
fi

cat "${SUMMARY_PATH}"
exit "${OVERALL_RC}"
