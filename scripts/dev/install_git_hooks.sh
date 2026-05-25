#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

for hook in .githooks/pre-commit .githooks/pre-push; do
  if [[ ! -f "$hook" ]]; then
    echo "Missing hook file: $hook" >&2
    exit 1
  fi
done

chmod +x .githooks/pre-commit .githooks/pre-push
git config --local core.hooksPath .githooks

cat <<'EOF'
Configured local git hooks via .githooks

pre-commit:
  uv run python -m pytest tests/test_docs_contracts.py tests/test_repo_path_references.py tests/test_run_tests_script.py -q

pre-push:
  ./scripts/dev/run_tests.sh fast

Skip once with:
  git commit --no-verify
  git push --no-verify
EOF
