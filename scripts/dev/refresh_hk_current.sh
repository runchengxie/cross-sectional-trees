#!/usr/bin/env bash
set -euo pipefail

TARGET_DATE="$(date +%Y%m%d)"
CONFIG=""
GATE_ON_SEVERITY="warning"
INSPECT_FAIL_ON_SEVERITY="none"
DAILY_PATCH_LOOKBACK_DAYS="20"
DATED_PATCH_LOOKBACK_DAYS="40"
WITH_PACKAGE="0"
BACKUP_NAME=""
RESUME="1"
DRY_RUN="0"
NO_REPOINT_LATEST="0"
EXTRA_WORKFLOW_ARGS=()

usage() {
  cat <<'EOF'
Usage:
  scripts/dev/refresh_hk_current.sh [options] [-- workflow args...]

Daily HK current refresh wrapper. It runs the maintainer workflow with a
tail-window patch refresh (--refresh-mode patch) and an inspect gate. By default
it does not package or backup; opt into those when you are freezing or sharing a
current state.

Options:
  --target-date YYYYMMDD          Target date. Default: today.
  --config PATH_OR_ALIAS          Config forwarded to the workflow.
  --gate-on-severity LEVEL        none|info|warning|error. Default: warning.
  --inspect-fail-on-severity L    none|info|warning|error. Default: none.
  --daily-patch-lookback-days N   Daily tail overlap. Default: 20.
  --dated-patch-lookback-days N   Valuation/ex_factors/dividends/shares
                                  tail overlap. Default: 40.
  --with-package                  Also run the package phase after inspect.
  --backup-name NAME              After a successful non-dry run, freeze the
                                  resolved hk_current contract with
                                  csml backup-data --preset hk_current.
  --no-resume                     Do not pass --resume to patch mirror steps.
  --dry-run                       Forward --dry-run to the workflow; skips
                                  backup execution.
  --no-repoint-latest             Forward --no-repoint-latest to the workflow.
  -h, --help                      Show this help text.

Examples:
  scripts/dev/refresh_hk_current.sh --target-date 20260410

  scripts/dev/refresh_hk_current.sh \
    --target-date 20260410 \
    --backup-name hk_current_frozen_20260410

  scripts/dev/refresh_hk_current.sh \
    --target-date 20260410 \
    --with-package \
    -- --refresh-asset daily --refresh-asset valuation
EOF
}

print_command() {
  printf '+ '
  printf '%q ' "$@"
  printf '\n'
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
    --gate-on-severity)
      GATE_ON_SEVERITY="$2"
      shift 2
      ;;
    --inspect-fail-on-severity)
      INSPECT_FAIL_ON_SEVERITY="$2"
      shift 2
      ;;
    --daily-patch-lookback-days)
      DAILY_PATCH_LOOKBACK_DAYS="$2"
      shift 2
      ;;
    --dated-patch-lookback-days)
      DATED_PATCH_LOOKBACK_DAYS="$2"
      shift 2
      ;;
    --with-package)
      WITH_PACKAGE="1"
      shift
      ;;
    --backup-name)
      BACKUP_NAME="$2"
      shift 2
      ;;
    --no-resume)
      RESUME="0"
      shift
      ;;
    --dry-run)
      DRY_RUN="1"
      shift
      ;;
    --no-repoint-latest)
      NO_REPOINT_LATEST="1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      EXTRA_WORKFLOW_ARGS+=("$@")
      break
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

WORKFLOW_CMD=(
  python scripts/internal/run_hk_asset_workflow.py
  --phase refresh
  --phase inspect
  --target-date "${TARGET_DATE}"
  --refresh-mode patch
  --gate-on-severity "${GATE_ON_SEVERITY}"
  --inspect-fail-on-severity "${INSPECT_FAIL_ON_SEVERITY}"
  --daily-patch-lookback-days "${DAILY_PATCH_LOOKBACK_DAYS}"
  --dated-patch-lookback-days "${DATED_PATCH_LOOKBACK_DAYS}"
)

if [[ "${WITH_PACKAGE}" == "1" ]]; then
  WORKFLOW_CMD+=(--phase package)
fi

if [[ "${RESUME}" == "1" ]]; then
  WORKFLOW_CMD+=(--resume)
fi

if [[ -n "${CONFIG}" ]]; then
  WORKFLOW_CMD+=(--config "${CONFIG}")
fi

if [[ "${DRY_RUN}" == "1" ]]; then
  WORKFLOW_CMD+=(--dry-run)
fi

if [[ "${NO_REPOINT_LATEST}" == "1" ]]; then
  WORKFLOW_CMD+=(--no-repoint-latest)
fi

if [[ "${#EXTRA_WORKFLOW_ARGS[@]}" -gt 0 ]]; then
  WORKFLOW_CMD+=("${EXTRA_WORKFLOW_ARGS[@]}")
fi

print_command "${WORKFLOW_CMD[@]}"
"${WORKFLOW_CMD[@]}"

if [[ -n "${BACKUP_NAME}" ]]; then
  BACKUP_CMD=(uv run csml backup-data --preset hk_current --name "${BACKUP_NAME}" --no-cache)
  if [[ "${DRY_RUN}" == "1" ]]; then
    echo "[dry-run] skip backup:"
    print_command "${BACKUP_CMD[@]}"
  else
    print_command "${BACKUP_CMD[@]}"
    "${BACKUP_CMD[@]}"
  fi
fi
