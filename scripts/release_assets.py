#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shlex
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_SCRIPT = REPO_ROOT / "scripts" / "package_assets.py"


def _resolve_path(path_text: str | Path) -> Path:
    path = Path(path_text).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (Path.cwd() / path).resolve()


def _run(cmd: list[str], *, dry_run: bool, capture: bool = False) -> subprocess.CompletedProcess:
    print("+", " ".join(shlex.quote(part) for part in cmd))
    if dry_run:
        return subprocess.CompletedProcess(cmd, 0, "", "")
    return subprocess.run(cmd, check=False, capture_output=capture, text=True)


def _parse_bundle_path(output: str) -> Path | None:
    for line in output.splitlines():
        if line.startswith("Bundle created at:"):
            path_text = line.split(":", 1)[1].strip()
            if path_text:
                return Path(path_text).expanduser().resolve()
    return None


def _load_manifest(bundle_dir: Path) -> dict:
    manifest_path = bundle_dir / "manifest.yml"
    if not manifest_path.exists():
        return {}
    try:
        import yaml  # type: ignore

        return yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _manifest_value(manifest: dict, *keys: str) -> str | None:
    node: object = manifest
    for key in keys:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node if isinstance(node, str) else None


def _format_readme(bundle_dir: Path, manifest: dict) -> str:
    name = _manifest_value(manifest, "bundle", "name") or bundle_dir.name
    as_of = _manifest_value(manifest, "bundle", "as_of")
    generated_at = _manifest_value(manifest, "bundle", "generated_at") or datetime.now(
        timezone.utc
    ).astimezone().isoformat(timespec="seconds")
    source_repo = _manifest_value(manifest, "bundle", "source_repo") or str(REPO_ROOT)
    mode = _manifest_value(manifest, "bundle", "mode") or "copy"

    daily_snapshot = _manifest_value(manifest, "assets", "daily", "snapshot")
    instruments_file = _manifest_value(manifest, "assets", "instruments", "file")
    pit_snapshot = _manifest_value(manifest, "assets", "pit_financials", "snapshot")
    ex_factors_snapshot = _manifest_value(manifest, "assets", "ex_factors", "snapshot")
    dividends_snapshot = _manifest_value(manifest, "assets", "dividends", "snapshot")
    shares_snapshot = _manifest_value(manifest, "assets", "shares", "snapshot")
    universe_by_date = _manifest_value(manifest, "assets", "universe", "by_date")
    universe_symbols = _manifest_value(manifest, "assets", "universe", "symbols")
    universe_meta = _manifest_value(manifest, "assets", "universe", "meta")

    lines = [
        "# CSML HK Assets Bundle",
        "",
        "This bundle packages raw HK assets for reuse across projects.",
        "",
        f"Bundle: {name}",
        f"As of: {as_of or 'unknown'}",
        f"Generated at: {generated_at}",
        f"Source repo: {source_repo}",
        f"Mode: {mode}",
        "",
        "Contents:",
    ]

    if daily_snapshot:
        lines.append(f"- rqdata/hk/daily/{daily_snapshot}/")
    if instruments_file:
        lines.append(f"- rqdata/hk/instruments/{instruments_file}")
    if pit_snapshot:
        lines.append(f"- rqdata/hk/pit_financials/{pit_snapshot}/")
    if ex_factors_snapshot:
        lines.append(f"- rqdata/hk/ex_factors/{ex_factors_snapshot}/")
    if dividends_snapshot:
        lines.append(f"- rqdata/hk/dividends/{dividends_snapshot}/")
    if shares_snapshot:
        lines.append(f"- rqdata/hk/shares/{shares_snapshot}/")
    if universe_by_date:
        lines.append(f"- universe/{universe_by_date}")
    if universe_symbols:
        lines.append(f"- universe/{universe_symbols}")
    if universe_meta:
        lines.append(f"- universe/{universe_meta}")

    lines.extend(
        [
            "",
            "Entry points:",
            "- rqdata/hk/daily/latest",
            "- rqdata/hk/instruments/latest.parquet",
            "- universe/latest_by_date.csv",
            "- universe/latest_symbols.txt",
        ]
    )
    if pit_snapshot:
        lines.append("- rqdata/hk/pit_financials/latest")
    if ex_factors_snapshot:
        lines.append("- rqdata/hk/ex_factors/latest")
    if dividends_snapshot:
        lines.append("- rqdata/hk/dividends/latest")
    if shares_snapshot:
        lines.append("- rqdata/hk/shares/latest")
    if universe_meta:
        lines.append("- universe/latest_meta.yml")

    lines.extend(
        [
            "",
            "Notes:",
            "- Raw per-symbol parquet files live under each snapshot directory.",
            "- See manifest.yml for the exact asset mapping and metadata.",
            "",
        ]
    )
    return "\n".join(lines)


def _format_release_notes(bundle_dir: Path, manifest: dict) -> str:
    name = _manifest_value(manifest, "bundle", "name") or bundle_dir.name
    as_of = _manifest_value(manifest, "bundle", "as_of") or "unknown"
    generated_at = _manifest_value(manifest, "bundle", "generated_at") or "unknown"
    lines = [
        f"Bundle: {name}",
        f"As of: {as_of}",
        f"Generated at: {generated_at}",
        "",
        "Included assets:",
    ]
    daily_snapshot = _manifest_value(manifest, "assets", "daily", "snapshot")
    instruments_file = _manifest_value(manifest, "assets", "instruments", "file")
    pit_snapshot = _manifest_value(manifest, "assets", "pit_financials", "snapshot")
    ex_factors_snapshot = _manifest_value(manifest, "assets", "ex_factors", "snapshot")
    dividends_snapshot = _manifest_value(manifest, "assets", "dividends", "snapshot")
    shares_snapshot = _manifest_value(manifest, "assets", "shares", "snapshot")
    universe_by_date = _manifest_value(manifest, "assets", "universe", "by_date")
    universe_symbols = _manifest_value(manifest, "assets", "universe", "symbols")
    universe_meta = _manifest_value(manifest, "assets", "universe", "meta")

    if daily_snapshot:
        lines.append(f"- daily: {daily_snapshot}")
    if instruments_file:
        lines.append(f"- instruments: {instruments_file}")
    if pit_snapshot:
        lines.append(f"- pit_financials: {pit_snapshot}")
    if ex_factors_snapshot:
        lines.append(f"- ex_factors: {ex_factors_snapshot}")
    if dividends_snapshot:
        lines.append(f"- dividends: {dividends_snapshot}")
    if shares_snapshot:
        lines.append(f"- shares: {shares_snapshot}")
    if universe_by_date:
        lines.append(f"- universe by_date: {universe_by_date}")
    if universe_symbols:
        lines.append(f"- universe symbols: {universe_symbols}")
    if universe_meta:
        lines.append(f"- universe meta: {universe_meta}")
    return "\n".join(lines) + "\n"


def _ensure_gh() -> None:
    if shutil.which("gh") is None:
        raise SystemExit("GitHub CLI (gh) not found in PATH.")


def _default_tag(bundle_dir: Path, manifest: dict) -> str:
    name = _manifest_value(manifest, "bundle", "name") or bundle_dir.name
    as_of = _manifest_value(manifest, "bundle", "as_of")
    if as_of:
        return f"assets-{name}-{as_of}"
    return f"assets-{name}"


def _default_title(bundle_dir: Path, manifest: dict) -> str:
    name = _manifest_value(manifest, "bundle", "name") or bundle_dir.name
    as_of = _manifest_value(manifest, "bundle", "as_of")
    return f"Assets {name}{' ' + as_of if as_of else ''}"


def _build_tar(bundle_dir: Path, tar_path: Path, *, dry_run: bool) -> None:
    if dry_run:
        return
    if tar_path.exists():
        tar_path.unlink()
    tar_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(bundle_dir, arcname=bundle_dir.name, recursive=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Package HK assets and upload to a GitHub Release.",
    )
    parser.add_argument("--bundle", help="Existing bundle directory to upload.")
    parser.add_argument("--tar-out", help="Output tar.gz path.")
    parser.add_argument("--tag", help="Release tag (default derived from bundle).")
    parser.add_argument("--title", help="Release title (default derived from bundle).")
    parser.add_argument("--notes-file", help="Release notes file.")
    parser.add_argument("--draft", action="store_true", help="Create as draft.")
    parser.add_argument("--prerelease", action="store_true", help="Mark as prerelease.")
    parser.add_argument("--latest", action="store_true", help="Mark as latest.")
    parser.add_argument("--clobber", action="store_true", help="Overwrite asset if exists.")
    parser.add_argument("--repo", help="Target repo in owner/name format.")
    parser.add_argument("--skip-package", action="store_true", help="Skip packaging step.")
    parser.add_argument("--skip-upload", action="store_true", help="Skip release upload step.")
    parser.add_argument("--no-readme", action="store_true", help="Do not write bundle README.")
    parser.add_argument("--dry-run", action="store_true")
    args, package_args = parser.parse_known_args(argv)

    if args.bundle and package_args:
        print("Warning: package args ignored because --bundle is set.", file=sys.stderr)

    bundle_dir: Path
    if args.bundle:
        bundle_dir = _resolve_path(args.bundle)
        if not bundle_dir.exists():
            raise SystemExit(f"Bundle not found: {bundle_dir}")
    else:
        if args.skip_package:
            raise SystemExit("No bundle provided and --skip-package was set.")
        if "--dry-run" in package_args:
            raise SystemExit("package_assets --dry-run does not create a bundle.")
        package_cmd = [sys.executable, str(PACKAGE_SCRIPT), *package_args]
        result = _run(package_cmd, dry_run=args.dry_run, capture=True)
        if result.returncode != 0:
            sys.stderr.write(result.stderr or "")
            raise SystemExit(result.returncode)
        sys.stdout.write(result.stdout or "")
        if args.dry_run:
            print("Dry run complete.")
            return 0
        bundle_dir = _parse_bundle_path(result.stdout or "")
        if bundle_dir is None:
            raise SystemExit("Could not detect bundle path from package_assets output.")

    manifest = _load_manifest(bundle_dir)
    if not args.no_readme:
        readme_path = bundle_dir / "README.md"
        if not args.dry_run:
            readme_path.write_text(_format_readme(bundle_dir, manifest), encoding="utf-8")

    tar_path = _resolve_path(args.tar_out) if args.tar_out else bundle_dir.with_suffix(".tar.gz")
    _build_tar(bundle_dir, tar_path, dry_run=args.dry_run)

    if args.skip_upload:
        print(f"Bundle: {bundle_dir}")
        print(f"Tarball: {tar_path}")
        return 0

    _ensure_gh()
    tag = args.tag or _default_tag(bundle_dir, manifest)
    title = args.title or _default_title(bundle_dir, manifest)
    notes_file = args.notes_file
    if not notes_file:
        notes_path = tar_path.with_suffix(".release_notes.txt")
        if not args.dry_run:
            notes_path.write_text(_format_release_notes(bundle_dir, manifest), encoding="utf-8")
        notes_file = str(notes_path)

    repo_args: list[str] = ["--repo", args.repo] if args.repo else []

    view_cmd = ["gh", "release", "view", tag, *repo_args]
    view_result = _run(view_cmd, dry_run=args.dry_run, capture=True)
    if view_result.returncode == 0:
        upload_cmd = ["gh", "release", "upload", tag, str(tar_path), *repo_args]
        if args.clobber:
            upload_cmd.append("--clobber")
        _run(upload_cmd, dry_run=args.dry_run)
        return 0

    create_cmd = [
        "gh",
        "release",
        "create",
        tag,
        str(tar_path),
        "--title",
        title,
        "--notes-file",
        notes_file,
        *repo_args,
    ]
    if args.draft:
        create_cmd.append("--draft")
    if args.prerelease:
        create_cmd.append("--prerelease")
    if args.latest:
        create_cmd.append("--latest")
    _run(create_cmd, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
