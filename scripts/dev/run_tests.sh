#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/dev/run_tests.sh [all|fast|unit|slow|integration|coverage] [pytest args...]

Modes:
  all          Run the main pytest suite without coverage.
               Does not include optional-extra smoke jobs or opt-in real provider tests.
  fast, unit   Run the default fast offline regression suite.
  slow         Run heavier offline regression tests.
  integration  Run the marked cross-module integration suite.
               Real provider integration still requires CSML_RUN_PROVIDER_INTEGRATION=1.
  coverage     Run the main pytest suite with coverage.
               Scope matches 'all'; it is not the full CI matrix.
EOF
}

mode="${1:-all}"
if [[ $# -gt 0 ]]; then
  shift
fi

case "$mode" in
  all)
    exec uv run pytest "$@"
    ;;
  fast | unit)
    exec uv run pytest --no-cov -m "not integration and not slow" "$@"
    ;;
  slow)
    exec uv run pytest --no-cov -m "slow and not integration" "$@"
    ;;
  integration)
    exec uv run pytest --no-cov -m "integration" "$@"
    ;;
  coverage)
    exec uv run pytest --cov=csml --cov-report=term-missing "$@"
    ;;
  -h | --help | help)
    usage
    ;;
  *)
    echo "Unknown mode: $mode" >&2
    usage >&2
    exit 2
    ;;
esac
