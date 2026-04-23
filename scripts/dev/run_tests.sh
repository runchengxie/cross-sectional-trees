#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/dev/run_tests.sh [all|fast|unit|slow|integration|coverage|lint|imports|format|format-all] [args...]

Modes:
  all          Run the main pytest suite without coverage.
               Does not include optional-extra smoke jobs or opt-in real provider tests.
  fast, unit   Run the default fast offline regression suite.
  slow         Run heavier offline regression tests.
  integration  Run the marked cross-module integration suite.
               Real provider integration prefers CSTREE_RUN_PROVIDER_INTEGRATION=1;
               legacy CSML_RUN_PROVIDER_INTEGRATION=1 still works.
  coverage     Run the main pytest suite with coverage.
               Scope matches 'all'; it is not the full CI matrix.
  lint         Run Ruff lint and basic complexity checks, plus import-order on changed files.
  imports      Run Ruff import-order checks across src, tests, and scripts.
  format       Check Ruff formatting on changed Python files.
  format-all   Check Ruff formatting across src, tests, and scripts.
EOF
}

run_ruff() {
  if [[ -x .venv/bin/ruff ]]; then
    .venv/bin/ruff "$@"
    return
  fi
  uv run --no-project --with ruff ruff "$@"
}

changed_python_files() {
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    printf '%s\n' src tests scripts
    return
  fi
  {
    git diff --name-only --diff-filter=ACMRT HEAD -- '*.py'
    git ls-files --others --exclude-standard -- '*.py'
  } | sort -u
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
  lint)
    run_ruff check src tests scripts "$@"
    mapfile -t changed_python < <(changed_python_files)
    if [[ ${#changed_python[@]} -gt 0 ]]; then
      run_ruff check --select I "${changed_python[@]}" "$@"
    fi
    ;;
  imports)
    run_ruff check --select I src tests scripts "$@"
    ;;
  format)
    mapfile -t changed_python < <(changed_python_files)
    if [[ ${#changed_python[@]} -eq 0 ]]; then
      echo "No changed Python files to format-check."
      exit 0
    fi
    run_ruff format --check "${changed_python[@]}" "$@"
    ;;
  format-all)
    run_ruff format --check src tests scripts "$@"
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
