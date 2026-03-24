from __future__ import annotations

from pathlib import Path

ARTIFACTS_ROOT = Path("artifacts")
CACHE_DIR = ARTIFACTS_ROOT / "cache"
ASSETS_DIR = ARTIFACTS_ROOT / "assets"
METADATA_DIR = ARTIFACTS_ROOT / "metadata"
STANDARDIZED_DIR = ARTIFACTS_ROOT / "standardized"
FUNDAMENTALS_DIR = ASSETS_DIR / "fundamentals"
RQDATA_ASSETS_DIR = ASSETS_DIR / "rqdata"
UNIVERSE_DIR = ASSETS_DIR / "universe"
UNIVERSE_BY_DATE_FILE = UNIVERSE_DIR / "universe_by_date.csv"
HK_CONNECT_SYMBOLS_FILE = UNIVERSE_DIR / "hk_connect_symbols.txt"
UNIVERSE_META_FILE = UNIVERSE_DIR / "universe_by_date.meta.yml"
HK_ALL_FULL_BY_DATE_FILE = UNIVERSE_DIR / "hk_all_full_by_date.csv"
HK_ALL_FULL_SYMBOLS_FILE = UNIVERSE_DIR / "hk_all_full_symbols.txt"
HK_ALL_FULL_META_FILE = UNIVERSE_DIR / "hk_all_full_by_date.meta.yml"
RUNS_DIR = ARTIFACTS_ROOT / "runs"
LIVE_RUNS_DIR = ARTIFACTS_ROOT / "live_runs"
SWEEPS_DIR = ARTIFACTS_ROOT / "sweeps"
SNAPSHOTS_DIR = ARTIFACTS_ROOT / "snapshots"

def default_path_text(path: Path) -> str:
    return path.as_posix()


def resolve_repo_path(path_text: str | Path) -> Path:
    path = Path(path_text).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (Path.cwd() / path).resolve()
