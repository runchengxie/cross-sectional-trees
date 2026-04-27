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
               Real provider integration uses CSTREE_RUN_PROVIDER_INTEGRATION=1.
  coverage     Run the main pytest suite with coverage.
               Scope matches 'all'; it is not the full CI matrix.
  lint         Run Ruff lint and basic complexity checks, plus changed-file ratchets.
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

check_added_python_long_lines() {
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    return 0
  fi

  local added_lines
  local untracked_lines
  added_lines="$(
    git diff --unified=0 -- '*.py' | awk '
      /^\+\+\+ b\// {
        file = substr($0, 7)
        next
      }
      /^@@ / {
        if (match($0, /\+([0-9]+)/, parts)) {
          line_no = parts[1] - 1
        } else {
          line_no = 0
        }
        next
      }
      /^\+/ && $0 !~ /^\+\+\+/ {
        line_no += 1
        text = substr($0, 2)
        if (length(text) > 100) {
          printf "%s:%d:%d:%s\n", file, line_no, length(text), text
        }
        next
      }
      /^-/ {
        next
      }
      {
        if (line_no > 0) {
          line_no += 1
        }
      }
    '
  )"
  untracked_lines="$(
    while IFS= read -r file; do
      [[ -f "$file" ]] || continue
      awk 'length($0) > 100 {printf "%s:%d:%d:%s\n", FILENAME, FNR, length($0), $0}' "$file"
    done < <(git ls-files --others --exclude-standard -- '*.py')
  )"

  if [[ -n "$added_lines" || -n "$untracked_lines" ]]; then
    echo "Python lines added in this worktree must be <= 100 characters:" >&2
    [[ -z "$added_lines" ]] || printf '%s\n' "$added_lines" >&2
    [[ -z "$untracked_lines" ]] || printf '%s\n' "$untracked_lines" >&2
    return 1
  fi
}

check_added_c901_ignores() {
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    return 0
  fi

  local added_ignores
  added_ignores="$(
    git diff --unified=0 -- pyproject.toml | awk '
      /^\+/ && $0 !~ /^\+\+\+/ && $0 ~ /C901/ {
        print substr($0, 2)
      }
    '
  )"
  if [[ -z "$added_ignores" ]]; then
    return 0
  fi

  if git diff --name-only -- docs/internal/maintenance-debt-inventory.md | grep -q .; then
    return 0
  fi

  echo "New C901 ignores must be documented in docs/internal/maintenance-debt-inventory.md:" >&2
  printf '%s\n' "$added_ignores" >&2
  return 1
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
    exec uv run pytest --cov=cstree --cov-report=term-missing "$@"
    ;;
  lint)
    run_ruff check src tests scripts "$@"
    mapfile -t changed_python < <(changed_python_files)
    if [[ ${#changed_python[@]} -gt 0 ]]; then
      run_ruff check --select I,F401,F841,B023 "${changed_python[@]}" "$@"
    fi
    check_added_python_long_lines
    check_added_c901_ignores
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
