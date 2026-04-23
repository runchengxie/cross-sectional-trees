#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_repo_src() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    src_root = repo_root / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))


def main() -> int:
    _bootstrap_repo_src()
    from cstree.release_tools.hk_asset_workflow import main as workflow_main

    return int(workflow_main() or 0)


if __name__ == "__main__":
    raise SystemExit(main())
