#!/usr/bin/env bash

set -u -o pipefail

ARTIFACTS_ROOT="artifacts"
CONFIG="configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml"
FAIL_ON_SEVERITY="warning"
MODE="both"
NAME=""
REPORT_PATH=""
TARGET_DATE=""

usage() {
  cat <<'EOF'
Usage:
  scripts/dev/run_hk_pit_health.sh --target-date YYYYMMDD [options]

Options:
  --target-date YYYYMMDD        Target date used by PIT health. Required.
  --config PATH                 Config passed to inspect-hk-pit-coverage.
                                Default:
                                configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml
  --artifacts-root PATH         Artifacts root. Default: artifacts
  --fail-on-severity LEVEL      none|info|warning|error. Default: warning
  --mode MODE                   PIT coverage mode. Default: both
  --name NAME                   Report/log suffix. Default: derived from config filename.
  --out PATH                    Explicit JSON report path.
  -h, --help                    Show this help text.

Outputs:
  <artifacts-root>/reports/hk_pit_health_<target-date>_<name>.json
  <artifacts-root>/reports/health_logs/<timestamp>_pit_health_<name>.log
EOF
}

slugify() {
  local value="$1"
  value="${value##*/}"
  value="${value%.yml}"
  value="${value%.yaml}"
  printf '%s' "${value}" | tr -cs 'A-Za-z0-9_' '_'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-date)
      TARGET_DATE="$2"
      shift 2
      ;;
    --config)
      CONFIG="$2"
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
    --mode)
      MODE="$2"
      shift 2
      ;;
    --name)
      NAME="$2"
      shift 2
      ;;
    --out)
      REPORT_PATH="$2"
      shift 2
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

if [[ -z "${TARGET_DATE}" ]]; then
  echo "--target-date is required." >&2
  usage >&2
  exit 2
fi

if [[ -z "${NAME}" ]]; then
  NAME="$(slugify "${CONFIG}")"
fi

mkdir -p "${ARTIFACTS_ROOT}/reports" "${ARTIFACTS_ROOT}/reports/health_logs"

TS="$(date +%Y%m%d_%H%M%S)"
LOG_PATH="${ARTIFACTS_ROOT}/reports/health_logs/${TS}_pit_health_${NAME}.log"

if [[ -z "${REPORT_PATH}" ]]; then
  REPORT_PATH="${ARTIFACTS_ROOT}/reports/hk_pit_health_${TARGET_DATE}_${NAME}.json"
fi

{
  echo "# $(date -Is) :: pit_health_${NAME}"
  printf '+ '
  printf '%q ' uv run csml rqdata inspect-hk-pit-coverage \
    --config "${CONFIG}" \
    --mode "${MODE}" \
    --include-health \
    --target-date "${TARGET_DATE}" \
    --fail-on-severity "${FAIL_ON_SEVERITY}" \
    --format json \
    --out "${REPORT_PATH}"
  printf '\n'
  uv run csml rqdata inspect-hk-pit-coverage \
    --config "${CONFIG}" \
    --mode "${MODE}" \
    --include-health \
    --target-date "${TARGET_DATE}" \
    --fail-on-severity "${FAIL_ON_SEVERITY}" \
    --format json \
    --out "${REPORT_PATH}"
  rc=$?
  echo "exit_code=${rc}"
} >"${LOG_PATH}" 2>&1

echo "exit_code=${rc}"
echo "report=${REPORT_PATH}"
echo "log=${LOG_PATH}"

exit "${rc}"
