import importlib.util
import subprocess
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_SCRIPT_PATH = REPO_ROOT / "scripts" / "package_assets.py"
RELEASE_SCRIPT_PATH = REPO_ROOT / "scripts" / "release_assets.py"


def _load_script(module_name: str, script_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _prepare_demo_assets(repo_root: Path) -> None:
    daily_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "daily_demo"
    daily_dir.mkdir(parents=True, exist_ok=True)
    (daily_dir / "00005.HK.parquet").write_text("daily", encoding="utf-8")

    instruments_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "instruments"
    instruments_dir.mkdir(parents=True, exist_ok=True)
    (instruments_dir / "instruments_demo.parquet").write_text("instruments", encoding="utf-8")

    universe_dir = repo_root / "artifacts" / "assets" / "universe"
    universe_dir.mkdir(parents=True, exist_ok=True)
    (universe_dir / "by_date_demo.csv").write_text("trade_date,ts_code\n20260318,00005.HK\n", encoding="utf-8")
    (universe_dir / "symbols_demo.txt").write_text("00005.HK\n", encoding="utf-8")
    (universe_dir / "meta_demo.yml").write_text("name: demo\n", encoding="utf-8")


def _stage_demo_parts(tmp_path: Path) -> tuple[object, Path]:
    package_script = _load_script("package_assets_script", PACKAGE_SCRIPT_PATH)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _prepare_demo_assets(repo_root)

    package_script.REPO_ROOT = repo_root
    package_script.ASSETS_ROOT = repo_root / "artifacts" / "assets"

    stage_root = tmp_path / "stage"
    exit_code = package_script.main(
        [
            "--dest",
            str(stage_root),
            "--name",
            "demo_assets",
            "--as-of",
            "20260318",
            "--daily-snapshot",
            "daily_demo",
            "--instruments-file",
            "instruments_demo.parquet",
            "--universe-by-date",
            "by_date_demo.csv",
            "--universe-symbols",
            "symbols_demo.txt",
            "--universe-meta",
            "meta_demo.yml",
            "--no-pit",
            "--no-reference",
            "--no-industry",
            "--part",
            "daily",
            "--part",
            "universe",
        ]
    )

    assert exit_code == 0
    return package_script, stage_root


def test_package_assets_stages_selected_parts_and_manifests(tmp_path):
    _, stage_root = _stage_demo_parts(tmp_path)

    assert (stage_root / "daily" / "rqdata" / "hk" / "daily" / "daily_demo" / "00005.HK.parquet").exists()
    assert (stage_root / "universe" / "universe" / "by_date_demo.csv").exists()
    assert not (stage_root / "instruments").exists()

    daily_latest = stage_root / "daily" / "rqdata" / "hk" / "daily" / "latest"
    universe_latest = stage_root / "universe" / "universe" / "latest_by_date.csv"
    assert daily_latest.is_symlink()
    assert universe_latest.is_symlink()

    root_manifest = yaml.safe_load((stage_root / "manifest.yml").read_text(encoding="utf-8"))
    assert root_manifest["distribution"]["name"] == "demo_assets"
    assert sorted(root_manifest["parts"].keys()) == ["daily", "universe"]

    daily_manifest = yaml.safe_load((stage_root / "daily" / "manifest.yml").read_text(encoding="utf-8"))
    assert daily_manifest["part"]["name"] == "daily"
    assert daily_manifest["part"]["summary"]["snapshot"] == "daily_demo"


def test_release_assets_builds_multiple_tarballs_for_selected_parts(tmp_path):
    _, stage_root = _stage_demo_parts(tmp_path)
    release_script = _load_script("release_assets_script", RELEASE_SCRIPT_PATH)

    tar_dir = tmp_path / "tarballs"
    exit_code = release_script.main(
        [
            "--staged-root",
            str(stage_root),
            "--tar-dir",
            str(tar_dir),
            "--part",
            "daily",
            "--part",
            "universe",
            "--skip-upload",
        ]
    )

    assert exit_code == 0
    assert (tar_dir / "assets-demo_assets-20260318-daily.tar.gz").exists()
    assert (tar_dir / "assets-demo_assets-20260318-universe.tar.gz").exists()
    assert (stage_root / "README.md").exists()


def test_release_assets_creates_single_release_with_multiple_assets(tmp_path, monkeypatch):
    _, stage_root = _stage_demo_parts(tmp_path)
    release_script = _load_script("release_assets_script_for_create", RELEASE_SCRIPT_PATH)

    calls: list[list[str]] = []

    def _fake_run(cmd: list[str], *, dry_run: bool, capture: bool = False):
        calls.append(cmd)
        if cmd[:3] == ["gh", "release", "view"]:
            return subprocess.CompletedProcess(cmd, 1, "", "")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(release_script, "_run", _fake_run)
    monkeypatch.setattr(release_script, "_ensure_gh", lambda: None)

    tar_dir = tmp_path / "tarballs"
    exit_code = release_script.main(
        [
            "--staged-root",
            str(stage_root),
            "--tar-dir",
            str(tar_dir),
            "--part",
            "daily",
            "--part",
            "universe",
        ]
    )

    assert exit_code == 0
    create_cmd = next(cmd for cmd in calls if cmd[:3] == ["gh", "release", "create"])
    assert any(item.endswith("assets-demo_assets-20260318-daily.tar.gz") for item in create_cmd)
    assert any(item.endswith("assets-demo_assets-20260318-universe.tar.gz") for item in create_cmd)


def test_release_assets_forwards_selected_parts_to_package_step(tmp_path, monkeypatch):
    _, stage_root = _stage_demo_parts(tmp_path)
    release_script = _load_script("release_assets_script_for_package", RELEASE_SCRIPT_PATH)

    calls: list[list[str]] = []

    def _fake_run(cmd: list[str], *, dry_run: bool, capture: bool = False):
        calls.append(cmd)
        if cmd[0].endswith("python") or cmd[0].endswith("python3") or cmd[0] == "python":
            return subprocess.CompletedProcess(
                cmd,
                0,
                f"Staged asset parts at: {stage_root}\nPart daily: {stage_root / 'daily'}\n",
                "",
            )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(release_script, "_run", _fake_run)

    tar_dir = tmp_path / "tarballs"
    exit_code = release_script.main(
        [
            "--tar-dir",
            str(tar_dir),
            "--part",
            "daily",
            "--skip-upload",
            "--preset",
            "hk_full",
        ]
    )

    assert exit_code == 0
    package_cmd = calls[0]
    assert "--part" in package_cmd
    assert package_cmd[package_cmd.index("--part") + 1] == "daily"
