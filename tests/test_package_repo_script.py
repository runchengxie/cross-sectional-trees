import hashlib
import os
import subprocess
import tarfile
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _prepare_demo_repo(tmp_path: Path) -> tuple[Path, bytes]:
    repo_root = tmp_path / "repo"
    script_dir = repo_root / "scripts" / "internal"
    script_dir.mkdir(parents=True, exist_ok=True)

    source_script = _repo_root() / "scripts" / "internal" / "package_repo.sh"
    target_script = script_dir / "package_repo.sh"
    target_script.write_text(source_script.read_text(encoding="utf-8"), encoding="utf-8")
    target_script.chmod(0o755)

    (repo_root / "README.md").write_text("# demo repo\n", encoding="utf-8")
    (repo_root / "src").mkdir()
    payload = os.urandom(4096)
    (repo_root / "src" / "payload.bin").write_bytes(payload)
    return repo_root, payload


def test_package_repo_script_has_valid_bash_syntax():
    repo_root = _repo_root()
    result = subprocess.run(
        ["bash", "-n", "scripts/internal/package_repo.sh"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_package_repo_script_can_split_archive_and_reassemble(tmp_path: Path):
    repo_root, payload = _prepare_demo_repo(tmp_path)
    out_dir = tmp_path / "out"

    result = subprocess.run(
        [
            "bash",
            "scripts/internal/package_repo.sh",
            "--name",
            "demo",
            "--out-dir",
            str(out_dir),
            "--split-size",
            "1k",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Created split parts:" in result.stdout

    parts = sorted(
        path
        for path in out_dir.glob("demo_*.tar.gz.part-*")
        if path.is_file() and not path.name.endswith(".sha256")
    )
    assert len(parts) >= 2

    archive_name = parts[0].name.split(".part-", 1)[0]
    archive_checksum = out_dir / f"{archive_name}.sha256"
    parts_manifest = out_dir / f"{archive_name}.parts.txt"

    assert not (out_dir / archive_name).exists()
    assert archive_checksum.exists()
    assert parts_manifest.exists()

    checksum_hash, checksum_target = archive_checksum.read_text(encoding="utf-8").strip().split(maxsplit=1)
    assert checksum_target == archive_name

    manifest_text = parts_manifest.read_text(encoding="utf-8")
    assert f"cat {archive_name}.part-* > {archive_name}" in manifest_text

    restored_archive = out_dir / archive_name
    with restored_archive.open("wb") as handle:
        for part in parts:
            part_checksum = out_dir / f"{part.name}.sha256"
            assert part_checksum.exists()
            handle.write(part.read_bytes())

    restored_hash = hashlib.sha256(restored_archive.read_bytes()).hexdigest()
    assert restored_hash == checksum_hash

    with tarfile.open(restored_archive, "r:gz") as tar:
        names = tar.getnames()
        assert any(name.endswith("README.md") for name in names)
        payload_name = next(name for name in names if name.endswith("src/payload.bin"))
        extracted = tar.extractfile(payload_name)
        assert extracted is not None
        assert extracted.read() == payload


def test_package_repo_script_defaults_work_dir_to_out_dir(tmp_path: Path):
    repo_root, _ = _prepare_demo_repo(tmp_path)
    out_dir = tmp_path / "out"
    env = os.environ.copy()
    env["TMPDIR"] = str(tmp_path / "missing-tmpdir")

    result = subprocess.run(
        [
            "bash",
            "scripts/internal/package_repo.sh",
            "--name",
            "demo",
            "--out-dir",
            str(out_dir),
            "--split-size",
            "1k",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert any(
        path.is_file() and not path.name.endswith(".sha256")
        for path in out_dir.glob("demo_*.tar.gz.part-*")
    )


def test_package_repo_script_supports_explicit_work_dir(tmp_path: Path):
    repo_root, _ = _prepare_demo_repo(tmp_path)
    out_dir = tmp_path / "out"
    work_dir = tmp_path / "work"

    result = subprocess.run(
        [
            "bash",
            "scripts/internal/package_repo.sh",
            "--name",
            "demo",
            "--out-dir",
            str(out_dir),
            "--work-dir",
            str(work_dir),
            "--split-size",
            "1k",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert work_dir.exists()
    assert not any(work_dir.iterdir())
