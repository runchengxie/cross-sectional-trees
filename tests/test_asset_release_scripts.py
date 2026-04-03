import importlib
import subprocess
from pathlib import Path

import yaml


def _load_module(module_name: str):
    return importlib.reload(importlib.import_module(module_name))


def _symlink(target: Path, link: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(target.name)


def _prepare_demo_assets(repo_root: Path) -> None:
    daily_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "daily_demo"
    daily_dir.mkdir(parents=True, exist_ok=True)
    (daily_dir / "00005.HK.parquet").write_text("daily", encoding="utf-8")
    _symlink(daily_dir, daily_dir.parent / "hk_all_daily_latest")
    _symlink(daily_dir, daily_dir.parent / "hk_all_daily_clean_latest")

    etf_daily_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "daily" / "hk_etf_2000_20260401_daily_latest"
    etf_daily_dir.mkdir(parents=True, exist_ok=True)
    (etf_daily_dir / "02800.HK.parquet").write_text("etf-daily", encoding="utf-8")
    _symlink(etf_daily_dir, etf_daily_dir.parent / "hk_etf_daily_latest")

    valuation_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "valuation" / "valuation_demo"
    valuation_dir.mkdir(parents=True, exist_ok=True)
    (valuation_dir / "00005.HK.parquet").write_text("valuation", encoding="utf-8")
    _symlink(valuation_dir, valuation_dir.parent / "hk_all_valuation_latest")

    instruments_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "instruments"
    instruments_dir.mkdir(parents=True, exist_ok=True)
    (instruments_dir / "instruments_demo.parquet").write_text("instruments", encoding="utf-8")
    _symlink(instruments_dir / "instruments_demo.parquet", instruments_dir / "hk_all_instruments_latest.parquet")
    (instruments_dir / "hk_etf_instruments_20260401.parquet").write_text("etf-instruments", encoding="utf-8")
    _symlink(
        instruments_dir / "hk_etf_instruments_20260401.parquet",
        instruments_dir / "hk_etf_instruments_latest.parquet",
    )

    universe_dir = repo_root / "artifacts" / "assets" / "universe"
    universe_dir.mkdir(parents=True, exist_ok=True)
    (universe_dir / "by_date_demo.csv").write_text("trade_date,symbol\n20260318,00005.HK\n", encoding="utf-8")
    (universe_dir / "symbols_demo.txt").write_text("00005.HK\n", encoding="utf-8")
    (universe_dir / "meta_demo.yml").write_text("name: demo\n", encoding="utf-8")
    (universe_dir / "hk_all_full_by_date.csv").write_text("trade_date,symbol\n20260318,00005.HK\n", encoding="utf-8")
    (universe_dir / "hk_all_full_symbols.txt").write_text("00005.HK\n", encoding="utf-8")
    (universe_dir / "hk_all_full_by_date.meta.yml").write_text("name: hk_all\n", encoding="utf-8")

    pit_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "pit_financials" / "hk_all_2000_2025_full_market_latest"
    (pit_dir / "data").mkdir(parents=True, exist_ok=True)
    (pit_dir / "data" / "00005.HK.parquet").write_text("pit", encoding="utf-8")
    (pit_dir / "pipeline_fundamentals.parquet").write_text("pit-flat", encoding="utf-8")

    intraday_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "intraday" / "intraday_demo"
    (intraday_dir / "data").mkdir(parents=True, exist_ok=True)
    (intraday_dir / "data" / "hk_all_5m_demo.parquet").write_text("intraday", encoding="utf-8")
    (intraday_dir / "manifest.yml").write_text("dataset: intraday\n", encoding="utf-8")
    _symlink(intraday_dir, intraday_dir.parent / "hk_intraday_latest")

    exchange_rate_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "exchange_rate" / "exchange_rate_demo"
    (exchange_rate_dir / "data").mkdir(parents=True, exist_ok=True)
    (exchange_rate_dir / "data" / "exchange_rate.parquet").write_text("exchange-rate", encoding="utf-8")
    exchange_rate_current = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "exchange_rate" / "hk_all_2000_20260319_exchange_rate_latest"
    (exchange_rate_current / "data").mkdir(parents=True, exist_ok=True)
    (exchange_rate_current / "data" / "exchange_rate.parquet").write_text("exchange-rate-current", encoding="utf-8")

    southbound_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "southbound" / "southbound_demo"
    (southbound_dir / "data").mkdir(parents=True, exist_ok=True)
    (southbound_dir / "data" / "00005.HK.parquet").write_text("southbound", encoding="utf-8")
    _symlink(southbound_dir, southbound_dir.parent / "hk_connect_southbound_latest")

    financial_details_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "financial_details" / "financial_details_demo"
    (financial_details_dir / "data").mkdir(parents=True, exist_ok=True)
    (financial_details_dir / "data" / "00005.HK.parquet").write_text("financial-details", encoding="utf-8")
    financial_details_current = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "financial_details" / "hk_financial_details_portable_bundle_20260324"
    (financial_details_current / "data").mkdir(parents=True, exist_ok=True)
    (financial_details_current / "data" / "00005.HK.parquet").write_text("financial-details-current", encoding="utf-8")

    ex_factors_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "ex_factors" / "ex_factors_demo"
    (ex_factors_dir / "data").mkdir(parents=True, exist_ok=True)
    (ex_factors_dir / "data" / "00005.HK.parquet").write_text("ex-factors", encoding="utf-8")
    _symlink(ex_factors_dir, ex_factors_dir.parent / "hk_all_ex_factors_latest")

    dividends_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "dividends" / "dividends_demo"
    (dividends_dir / "data").mkdir(parents=True, exist_ok=True)
    (dividends_dir / "data" / "00005.HK.parquet").write_text("dividends", encoding="utf-8")
    _symlink(dividends_dir, dividends_dir.parent / "hk_all_dividends_latest")

    shares_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "shares" / "shares_demo"
    (shares_dir / "data").mkdir(parents=True, exist_ok=True)
    (shares_dir / "data" / "00005.HK.parquet").write_text("shares", encoding="utf-8")
    _symlink(shares_dir, shares_dir.parent / "hk_all_shares_latest")

    industry_dir = repo_root / "artifacts" / "assets" / "rqdata" / "hk" / "industry_changes" / "industry_demo"
    (industry_dir / "data").mkdir(parents=True, exist_ok=True)
    (industry_dir / "data" / "00005.HK.parquet").write_text("industry", encoding="utf-8")
    _symlink(industry_dir, industry_dir.parent / "hk_all_industry_changes_latest")


def _stage_demo_parts(tmp_path: Path) -> tuple[object, Path]:
    package_script = _load_module("csml.release_tools.package_assets")
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
            "--no-valuation",
            "--no-pit",
            "--no-reference",
            "--no-exchange-rate",
            "--no-southbound",
            "--no-financial-details",
            "--no-industry",
            "--part",
            "daily",
            "--part",
            "universe",
        ]
    )

    assert exit_code == 0
    return package_script, stage_root


def _stage_demo_valuation_part(tmp_path: Path) -> tuple[object, Path]:
    package_script = _load_module("csml.release_tools.package_assets")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _prepare_demo_assets(repo_root)

    package_script.REPO_ROOT = repo_root
    package_script.ASSETS_ROOT = repo_root / "artifacts" / "assets"

    stage_root = tmp_path / "stage_valuation"
    exit_code = package_script.main(
        [
            "--dest",
            str(stage_root),
            "--name",
            "demo_assets_valuation",
            "--as-of",
            "20260318",
            "--daily-snapshot",
            "daily_demo",
            "--valuation-snapshot",
            "valuation_demo",
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
            "--no-exchange-rate",
            "--no-southbound",
            "--no-financial-details",
            "--no-industry",
            "--part",
            "valuation",
        ]
    )

    assert exit_code == 0
    return package_script, stage_root


def _stage_demo_supplemental_parts(tmp_path: Path) -> tuple[object, Path]:
    package_script = _load_module("csml.release_tools.package_assets")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _prepare_demo_assets(repo_root)

    package_script.REPO_ROOT = repo_root
    package_script.ASSETS_ROOT = repo_root / "artifacts" / "assets"

    stage_root = tmp_path / "stage_supplemental"
    exit_code = package_script.main(
        [
            "--dest",
            str(stage_root),
            "--name",
            "demo_assets_extra",
            "--as-of",
            "20260319",
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
            "--exchange-rate-snapshot",
            "exchange_rate_demo",
            "--southbound-snapshot",
            "southbound_demo",
            "--financial-details-snapshot",
            "financial_details_demo",
            "--no-valuation",
            "--no-pit",
            "--no-reference",
            "--no-industry",
            "--part",
            "exchange_rate",
            "--part",
            "southbound",
            "--part",
            "financial_details",
        ]
    )

    assert exit_code == 0
    return package_script, stage_root


def _stage_demo_etf_parts(tmp_path: Path) -> tuple[object, Path]:
    package_script = _load_module("csml.release_tools.package_assets")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _prepare_demo_assets(repo_root)

    package_script.REPO_ROOT = repo_root
    package_script.ASSETS_ROOT = repo_root / "artifacts" / "assets"

    stage_root = tmp_path / "stage_etf"
    exit_code = package_script.main(
        [
            "--preset",
            "hk_etf",
            "--dest",
            str(stage_root),
            "--name",
            "demo_etf_assets",
            "--as-of",
            "20260401",
        ]
    )

    assert exit_code == 0
    return package_script, stage_root


def _stage_demo_current_parts(tmp_path: Path) -> tuple[object, Path]:
    package_script = _load_module("csml.release_tools.package_assets")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _prepare_demo_assets(repo_root)

    package_script.REPO_ROOT = repo_root
    package_script.ASSETS_ROOT = repo_root / "artifacts" / "assets"

    stage_root = tmp_path / "stage_current"
    exit_code = package_script.main(
        [
            "--preset",
            "hk_current",
            "--dest",
            str(stage_root),
            "--name",
            "demo_current_assets",
            "--as-of",
            "20260403",
            "--part",
            "intraday",
            "--part",
            "etf",
            "--part",
            "valuation",
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
    release_script = _load_module("csml.release_tools.release_assets")

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


def test_package_assets_can_stage_valuation_part(tmp_path):
    _, stage_root = _stage_demo_valuation_part(tmp_path)

    assert (
        stage_root
        / "valuation"
        / "rqdata"
        / "hk"
        / "valuation"
        / "valuation_demo"
        / "00005.HK.parquet"
    ).exists()
    assert (stage_root / "valuation" / "rqdata" / "hk" / "valuation" / "latest").is_symlink()

    root_manifest = yaml.safe_load((stage_root / "manifest.yml").read_text(encoding="utf-8"))
    assert sorted(root_manifest["parts"].keys()) == ["valuation"]


def test_release_assets_builds_tarballs_for_valuation_part(tmp_path):
    _, stage_root = _stage_demo_valuation_part(tmp_path)
    release_script = _load_module("csml.release_tools.release_assets")

    tar_dir = tmp_path / "tarballs_valuation"
    exit_code = release_script.main(
        [
            "--staged-root",
            str(stage_root),
            "--tar-dir",
            str(tar_dir),
            "--part",
            "valuation",
            "--skip-upload",
        ]
    )

    assert exit_code == 0
    assert (tar_dir / "assets-demo_assets_valuation-20260318-valuation.tar.gz").exists()


def test_package_assets_stages_supplemental_parts_and_manifests(tmp_path):
    _, stage_root = _stage_demo_supplemental_parts(tmp_path)

    assert (
        stage_root
        / "exchange_rate"
        / "rqdata"
        / "hk"
        / "exchange_rate"
        / "exchange_rate_demo"
        / "data"
        / "exchange_rate.parquet"
    ).exists()
    assert (
        stage_root
        / "southbound"
        / "rqdata"
        / "hk"
        / "southbound"
        / "southbound_demo"
        / "data"
        / "00005.HK.parquet"
    ).exists()
    assert (
        stage_root
        / "financial_details"
        / "rqdata"
        / "hk"
        / "financial_details"
        / "financial_details_demo"
        / "data"
        / "00005.HK.parquet"
    ).exists()

    assert (stage_root / "exchange_rate" / "rqdata" / "hk" / "exchange_rate" / "latest").is_symlink()
    assert (stage_root / "southbound" / "rqdata" / "hk" / "southbound" / "latest").is_symlink()
    assert (stage_root / "financial_details" / "rqdata" / "hk" / "financial_details" / "latest").is_symlink()

    root_manifest = yaml.safe_load((stage_root / "manifest.yml").read_text(encoding="utf-8"))
    assert sorted(root_manifest["parts"].keys()) == ["exchange_rate", "financial_details", "southbound"]


def test_release_assets_builds_tarballs_for_supplemental_parts(tmp_path):
    _, stage_root = _stage_demo_supplemental_parts(tmp_path)
    release_script = _load_module("csml.release_tools.release_assets")

    tar_dir = tmp_path / "tarballs_extra"
    exit_code = release_script.main(
        [
            "--staged-root",
            str(stage_root),
            "--tar-dir",
            str(tar_dir),
            "--part",
            "exchange_rate",
            "--part",
            "southbound",
            "--part",
            "financial_details",
            "--skip-upload",
        ]
    )

    assert exit_code == 0
    assert (tar_dir / "assets-demo_assets_extra-20260319-exchange_rate.tar.gz").exists()
    assert (tar_dir / "assets-demo_assets_extra-20260319-southbound.tar.gz").exists()
    assert (tar_dir / "assets-demo_assets_extra-20260319-financial_details.tar.gz").exists()


def test_package_assets_etf_preset_stages_daily_and_instruments_without_universe(tmp_path):
    _, stage_root = _stage_demo_etf_parts(tmp_path)

    assert (
        stage_root
        / "daily"
        / "rqdata"
        / "hk"
        / "daily"
        / "hk_etf_2000_20260401_daily_latest"
        / "02800.HK.parquet"
    ).exists()
    assert (
        stage_root
        / "instruments"
        / "rqdata"
        / "hk"
        / "instruments"
        / "hk_etf_instruments_20260401.parquet"
    ).exists()
    assert not (stage_root / "universe").exists()
    assert (stage_root / "daily" / "rqdata" / "hk" / "daily" / "latest").is_symlink()
    assert (stage_root / "instruments" / "rqdata" / "hk" / "instruments" / "latest.parquet").is_symlink()

    root_manifest = yaml.safe_load((stage_root / "manifest.yml").read_text(encoding="utf-8"))
    assert sorted(root_manifest["parts"].keys()) == ["daily", "instruments"]


def test_package_assets_current_preset_stages_intraday_etf_and_valuation_parts(tmp_path):
    _, stage_root = _stage_demo_current_parts(tmp_path)

    assert (
        stage_root
        / "intraday"
        / "rqdata"
        / "hk"
        / "intraday"
        / "intraday_demo"
        / "data"
        / "hk_all_5m_demo.parquet"
    ).exists()
    assert (
        stage_root
        / "etf"
        / "rqdata"
        / "hk"
        / "daily"
        / "hk_etf_2000_20260401_daily_latest"
        / "02800.HK.parquet"
    ).exists()
    assert (
        stage_root
        / "etf"
        / "rqdata"
        / "hk"
        / "instruments"
        / "hk_etf_instruments_20260401.parquet"
    ).exists()
    assert (
        stage_root
        / "valuation"
        / "rqdata"
        / "hk"
        / "valuation"
        / "valuation_demo"
        / "00005.HK.parquet"
    ).exists()

    assert (stage_root / "intraday" / "rqdata" / "hk" / "intraday" / "hk_intraday_latest").is_symlink()
    assert (stage_root / "etf" / "rqdata" / "hk" / "daily" / "hk_etf_daily_latest").is_symlink()
    assert (
        stage_root
        / "etf"
        / "rqdata"
        / "hk"
        / "instruments"
        / "hk_etf_instruments_latest.parquet"
    ).is_symlink()

    root_manifest = yaml.safe_load((stage_root / "manifest.yml").read_text(encoding="utf-8"))
    assert sorted(root_manifest["parts"].keys()) == ["etf", "intraday", "valuation"]


def test_release_assets_builds_tarballs_for_intraday_and_etf_parts(tmp_path):
    _, stage_root = _stage_demo_current_parts(tmp_path)
    release_script = _load_module("csml.release_tools.release_assets")

    tar_dir = tmp_path / "tarballs_current"
    exit_code = release_script.main(
        [
            "--staged-root",
            str(stage_root),
            "--tar-dir",
            str(tar_dir),
            "--part",
            "intraday",
            "--part",
            "etf",
            "--skip-upload",
        ]
    )

    assert exit_code == 0
    assert (tar_dir / "assets-demo_current_assets-20260403-intraday.tar.gz").exists()
    assert (tar_dir / "assets-demo_current_assets-20260403-etf.tar.gz").exists()


def test_release_assets_creates_single_release_with_multiple_assets(tmp_path, monkeypatch):
    _, stage_root = _stage_demo_parts(tmp_path)
    release_script = _load_module("csml.release_tools.release_assets")

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
    release_script = _load_module("csml.release_tools.release_assets")

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
    assert package_cmd[1:3] == ["-m", "csml.release_tools.package_assets"]
    assert "--part" in package_cmd
    assert package_cmd[package_cmd.index("--part") + 1] == "daily"
