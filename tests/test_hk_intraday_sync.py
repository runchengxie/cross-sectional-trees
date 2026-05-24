import importlib
import json
from pathlib import Path
from types import SimpleNamespace


def _load_module(module_name: str):
    return importlib.reload(importlib.import_module(module_name))


def _configure_repo_roots(module, repo_root: Path) -> None:
    module.REPO_ROOT = repo_root
    module.REPORTS_ROOT = repo_root / "artifacts" / "reports"
    module.RELEASES_ROOT = repo_root / "artifacts" / "releases"
    module.DEFAULT_INTRADAY_CACHE_DIR = repo_root / "artifacts" / "cache" / "intraday"


def _base_args() -> SimpleNamespace:
    return SimpleNamespace(
        start_date="20260402",
        end_date="20260409",
        frequency="5m",
        output=None,
        meta_output=None,
        parts_dir=None,
        symbols_file="artifacts/assets/rqdata/hk/daily/hk_all_daily_latest/symbols.txt",
        adjust_type="pre",
        fields=["open", "high", "low", "close", "volume", "total_turnover"],
        batch_size=100,
        resume=True,
        skip_inspect=False,
        daily_asset_dir="artifacts/assets/rqdata/hk/daily/hk_all_daily_latest",
        health_out=None,
        sample_limit=5,
        expected_bars_per_day=66,
        numeric_rtol=1e-6,
        numeric_atol=1e-8,
        inspect_fail_on_severity="warning",
        verify_sampled_segments=0,
        sampled_health_out=None,
        sampled_inspect_fail_on_severity="warning",
        verify_full_asset=False,
        full_health_out=None,
        full_inspect_fail_on_severity="warning",
        out_root="artifacts/assets/rqdata",
        asset_name="hk_intraday_sync_demo",
        asset_alias="artifacts/assets/rqdata/hk/intraday/hk_intraday_latest",
        package=False,
        release=False,
        preset="hk_current",
        distribution_name="hk_intraday_assets",
        package_dest=None,
        tar_dir=None,
        package_daily_snapshot="artifacts/assets/rqdata/hk/daily/hk_all_daily_latest",
        package_instruments_file="artifacts/assets/rqdata/hk/instruments/hk_all_instruments_latest.parquet",
        repo=None,
        tag=None,
        title=None,
        draft=False,
        prerelease=False,
        latest=False,
        clobber=False,
        config=None,
        username=None,
        password=None,
    )


def test_sync_hk_intraday_downloads_inspects_and_repoints_alias(tmp_path, monkeypatch):
    sync = _load_module("cstree.data_tools.rqdata_assets.intraday_sync")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _configure_repo_roots(sync, repo_root)

    download_calls: list[tuple[str, str]] = []
    inspect_calls: list[list[str]] = []
    build_calls: list[list[str]] = []

    def _fake_download(args, rqdatac):
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("intraday", encoding="utf-8")
        meta_path = output_path.with_suffix(".meta.json")
        meta_path.write_text(
            json.dumps(
                {
                    "dataset": "hk_intraday_cache",
                    "start_date": args.start_date,
                    "end_date": args.end_date,
                    "frequency": args.frequency,
                }
            ),
            encoding="utf-8",
        )
        download_calls.append((args.start_date, args.end_date))
        return {
            "output_path": output_path,
            "meta_path": meta_path,
            "parts_dir": output_path.parent / f"{output_path.stem}.parts",
            "rows": 10,
            "symbols_requested": 2,
            "symbols_downloaded": 2,
            "meta": {},
        }

    def _fake_inspect(args):
        inspect_calls.append(list(args.input))
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(
                {
                    "summary": {
                        "trade_date_max": "2026-04-09",
                        "rows_scanned": 10,
                    },
                    "quality_verdict": {
                        "overall_severity": "info",
                        "severity_counts": {"error": 0, "warning": 0, "info": 0},
                    },
                }
            ),
            encoding="utf-8",
        )
        return 0

    def _fake_build(args):
        build_calls.append(list(args.input))
        asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "intraday" / args.name
        asset_dir.mkdir(parents=True, exist_ok=True)
        (asset_dir / "data").mkdir(exist_ok=True)
        alias_path = Path(args.alias)
        alias_path.parent.mkdir(parents=True, exist_ok=True)
        if alias_path.exists() or alias_path.is_symlink():
            alias_path.unlink()
        alias_path.symlink_to(asset_dir, target_is_directory=True)
        return 0

    monkeypatch.setattr(sync, "download_hk_intraday_cache", _fake_download)
    monkeypatch.setattr(sync, "inspect_hk_intraday_health", _fake_inspect)
    monkeypatch.setattr(sync, "build_hk_intraday_asset", _fake_build)
    monkeypatch.setattr(sync.package_assets_tool, "main", lambda argv: 0)
    monkeypatch.setattr(sync.release_assets_tool, "main", lambda argv: 0)

    exit_code = sync.sync_hk_intraday(_base_args(), rqdatac=object())

    assert exit_code == 0
    assert download_calls == [("20260402", "20260409")]
    assert len(inspect_calls) == 1
    assert inspect_calls[0][0].endswith("hk_intraday_5m_20260402_20260409.parquet")
    assert len(build_calls) == 1

    alias_path = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "intraday" / "hk_intraday_latest"
    assert alias_path.is_symlink()
    assert alias_path.resolve().name == "hk_intraday_sync_demo"


def test_sync_hk_intraday_preserves_existing_asset_entries_except_replaced_stem(tmp_path, monkeypatch):
    sync = _load_module("cstree.data_tools.rqdata_assets.intraday_sync")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _configure_repo_roots(sync, repo_root)

    current_asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "intraday" / "intraday_current"
    current_data_dir = current_asset_dir / "data"
    current_data_dir.mkdir(parents=True, exist_ok=True)
    (current_asset_dir / "manifest.yml").write_text("dataset: intraday\n", encoding="utf-8")
    for stem in ("hk_all_5m_20250327_20260326", "hk_all_5m_20260402_20260409"):
        (current_data_dir / f"{stem}.parquet").write_text(stem, encoding="utf-8")
        (current_data_dir / f"{stem}.meta.json").write_text("{}", encoding="utf-8")
    alias_path = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "intraday" / "hk_intraday_latest"
    alias_path.parent.mkdir(parents=True, exist_ok=True)
    alias_path.symlink_to(current_asset_dir, target_is_directory=True)

    build_calls: list[list[str]] = []

    def _fake_download(args, rqdatac):
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("new", encoding="utf-8")
        meta_path = output_path.with_suffix(".meta.json")
        meta_path.write_text("{}", encoding="utf-8")
        return {
            "output_path": output_path,
            "meta_path": meta_path,
            "parts_dir": output_path.parent / f"{output_path.stem}.parts",
            "rows": 10,
            "symbols_requested": 2,
            "symbols_downloaded": 2,
            "meta": {},
        }

    def _fake_inspect(args):
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(
                {
                    "summary": {"trade_date_max": "2026-04-09", "rows_scanned": 10},
                    "quality_verdict": {
                        "overall_severity": "info",
                        "severity_counts": {"error": 0, "warning": 0, "info": 0},
                    },
                }
            ),
            encoding="utf-8",
        )
        return 0

    def _fake_build(args):
        build_calls.append(list(args.input))
        new_asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "intraday" / args.name
        new_asset_dir.mkdir(parents=True, exist_ok=True)
        (new_asset_dir / "data").mkdir(exist_ok=True)
        alias = Path(args.alias)
        if alias.exists() or alias.is_symlink():
            alias.unlink()
        alias.symlink_to(new_asset_dir, target_is_directory=True)
        return 0

    monkeypatch.setattr(sync, "download_hk_intraday_cache", _fake_download)
    monkeypatch.setattr(sync, "inspect_hk_intraday_health", _fake_inspect)
    monkeypatch.setattr(sync, "build_hk_intraday_asset", _fake_build)
    monkeypatch.setattr(sync.package_assets_tool, "main", lambda argv: 0)
    monkeypatch.setattr(sync.release_assets_tool, "main", lambda argv: 0)

    exit_code = sync.sync_hk_intraday(_base_args(), rqdatac=object())

    assert exit_code == 0
    assert len(build_calls) == 1
    assert any(path.endswith("hk_all_5m_20250327_20260326.parquet") for path in build_calls[0])
    assert not any(
        path.endswith("artifacts/assets/rqdata/hk/intraday/hk_intraday_latest")
        for path in build_calls[0]
    )
    duplicate_stem_count = sum(path.endswith("hk_all_5m_20260402_20260409.parquet") for path in build_calls[0])
    assert duplicate_stem_count == 1


def test_sync_hk_intraday_packages_and_releases_when_requested(tmp_path, monkeypatch):
    sync = _load_module("cstree.data_tools.rqdata_assets.intraday_sync")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _configure_repo_roots(sync, repo_root)

    package_calls: list[list[str]] = []
    release_calls: list[list[str]] = []

    def _fake_download(args, rqdatac):
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("intraday", encoding="utf-8")
        meta_path = output_path.with_suffix(".meta.json")
        meta_path.write_text("{}", encoding="utf-8")
        return {
            "output_path": output_path,
            "meta_path": meta_path,
            "parts_dir": output_path.parent / f"{output_path.stem}.parts",
            "rows": 10,
            "symbols_requested": 2,
            "symbols_downloaded": 2,
            "meta": {},
        }

    def _fake_inspect(args):
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(
                {
                    "summary": {"trade_date_max": "2026-04-09", "rows_scanned": 10},
                    "quality_verdict": {
                        "overall_severity": "info",
                        "severity_counts": {"error": 0, "warning": 0, "info": 0},
                    },
                }
            ),
            encoding="utf-8",
        )
        return 0

    def _fake_build(args):
        asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "intraday" / args.name
        asset_dir.mkdir(parents=True, exist_ok=True)
        (asset_dir / "data").mkdir(exist_ok=True)
        alias_path = Path(args.alias)
        alias_path.parent.mkdir(parents=True, exist_ok=True)
        if alias_path.exists() or alias_path.is_symlink():
            alias_path.unlink()
        alias_path.symlink_to(asset_dir, target_is_directory=True)
        return 0

    def _fake_package(argv: list[str]) -> int:
        package_calls.append(argv)
        return 0

    def _fake_release(argv: list[str]) -> int:
        release_calls.append(argv)
        return 0

    monkeypatch.setattr(sync, "download_hk_intraday_cache", _fake_download)
    monkeypatch.setattr(sync, "inspect_hk_intraday_health", _fake_inspect)
    monkeypatch.setattr(sync, "build_hk_intraday_asset", _fake_build)
    monkeypatch.setattr(sync.package_assets_tool, "main", _fake_package)
    monkeypatch.setattr(sync.release_assets_tool, "main", _fake_release)

    args = _base_args()
    args.package = True
    args.release = True
    args.repo = "owner/name"
    args.tag = "hk-intraday-20260409"

    exit_code = sync.sync_hk_intraday(args, rqdatac=object())

    assert exit_code == 0
    assert len(package_calls) == 1
    assert "--part" in package_calls[0]
    assert package_calls[0][package_calls[0].index("--part") + 1] == "intraday"
    assert "--intraday-snapshot" in package_calls[0]
    assert package_calls[0][package_calls[0].index("--intraday-snapshot") + 1].endswith(
        "artifacts/assets/rqdata/hk/intraday/hk_intraday_sync_demo"
    )

    assert len(release_calls) == 1
    assert "--skip-upload" not in release_calls[0]
    assert release_calls[0][release_calls[0].index("--repo") + 1] == "owner/name"
    assert release_calls[0][release_calls[0].index("--tag") + 1] == "hk-intraday-20260409"


def test_sync_hk_intraday_full_verify_is_explicit_and_scans_asset_alias(tmp_path, monkeypatch):
    sync = _load_module("cstree.data_tools.rqdata_assets.intraday_sync")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _configure_repo_roots(sync, repo_root)

    inspect_calls: list[list[str]] = []

    def _fake_download(args, rqdatac):
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("intraday", encoding="utf-8")
        meta_path = output_path.with_suffix(".meta.json")
        meta_path.write_text("{}", encoding="utf-8")
        return {
            "output_path": output_path,
            "meta_path": meta_path,
            "parts_dir": output_path.parent / f"{output_path.stem}.parts",
            "rows": 10,
            "symbols_requested": 2,
            "symbols_downloaded": 2,
            "meta": {},
        }

    def _fake_inspect(args):
        inspect_calls.append(list(args.input))
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(
                {
                    "summary": {"trade_date_max": "2026-04-09", "rows_scanned": 10},
                    "quality_verdict": {
                        "overall_severity": "info",
                        "severity_counts": {"error": 0, "warning": 0, "info": 0},
                    },
                }
            ),
            encoding="utf-8",
        )
        return 0

    def _fake_build(args):
        asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "intraday" / args.name
        asset_dir.mkdir(parents=True, exist_ok=True)
        (asset_dir / "data").mkdir(exist_ok=True)
        alias_path = Path(args.alias)
        alias_path.parent.mkdir(parents=True, exist_ok=True)
        if alias_path.exists() or alias_path.is_symlink():
            alias_path.unlink()
        alias_path.symlink_to(asset_dir, target_is_directory=True)
        return 0

    monkeypatch.setattr(sync, "download_hk_intraday_cache", _fake_download)
    monkeypatch.setattr(sync, "inspect_hk_intraday_health", _fake_inspect)
    monkeypatch.setattr(sync, "build_hk_intraday_asset", _fake_build)
    monkeypatch.setattr(sync.package_assets_tool, "main", lambda argv: 0)
    monkeypatch.setattr(sync.release_assets_tool, "main", lambda argv: 0)

    args = _base_args()
    args.verify_full_asset = True

    exit_code = sync.sync_hk_intraday(args, rqdatac=object())

    assert exit_code == 0
    assert len(inspect_calls) == 2
    assert inspect_calls[0][0].endswith("hk_intraday_5m_20260402_20260409.parquet")
    assert inspect_calls[1][0].endswith("artifacts/assets/rqdata/hk/intraday/hk_intraday_sync_demo")


def test_sync_hk_intraday_sampled_verify_selects_oldest_and_latest_segments(tmp_path, monkeypatch):
    sync = _load_module("cstree.data_tools.rqdata_assets.intraday_sync")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _configure_repo_roots(sync, repo_root)

    inspect_calls: list[list[str]] = []

    def _fake_download(args, rqdatac):
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("intraday", encoding="utf-8")
        return {
            "output_path": output_path,
            "meta_path": output_path.with_suffix(".meta.json"),
            "parts_dir": output_path.parent / f"{output_path.stem}.parts",
            "rows": 10,
            "symbols_requested": 2,
            "symbols_downloaded": 2,
            "meta": {},
        }

    def _fake_inspect(args):
        inspect_calls.append(list(args.input))
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(
                {
                    "summary": {"trade_date_max": "2026-04-09", "rows_scanned": 10},
                    "quality_verdict": {
                        "overall_severity": "info",
                        "severity_counts": {"error": 0, "warning": 0, "info": 0},
                    },
                }
            ),
            encoding="utf-8",
        )
        return 0

    def _fake_build(args):
        asset_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "intraday" / args.name
        data_dir = asset_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        for stem in (
            "hk_all_5m_20240101_20241231",
            "hk_all_5m_20250101_20251231",
            "hk_all_5m_20260101_20260409",
        ):
            (data_dir / f"{stem}.parquet").write_text(stem, encoding="utf-8")
        alias_path = Path(args.alias)
        alias_path.parent.mkdir(parents=True, exist_ok=True)
        alias_path.symlink_to(asset_dir, target_is_directory=True)
        return 0

    monkeypatch.setattr(sync, "download_hk_intraday_cache", _fake_download)
    monkeypatch.setattr(sync, "inspect_hk_intraday_health", _fake_inspect)
    monkeypatch.setattr(sync, "build_hk_intraday_asset", _fake_build)

    args = _base_args()
    args.verify_sampled_segments = 2

    assert sync.sync_hk_intraday(args, rqdatac=object()) == 0
    assert len(inspect_calls) == 2
    assert inspect_calls[1][0].endswith("hk_all_5m_20240101_20241231.parquet")
    assert inspect_calls[1][1].endswith("hk_all_5m_20260101_20260409.parquet")
