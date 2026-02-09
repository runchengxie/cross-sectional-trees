from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Mapping, Optional

import yaml


@dataclass(frozen=True)
class ResolvedConfig:
    data: dict
    label: str
    path: Path | None
    source: str


def _load_yaml_text(text: str) -> dict:
    cfg = yaml.safe_load(text) or {}
    if not isinstance(cfg, dict):
        raise SystemExit("Config root must be a mapping.")
    return cfg


def load_yaml_path(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return _load_yaml_text(handle.read())


def load_yaml_package(package: str, filename: str) -> dict:
    return _load_yaml_text(read_package_text(package, filename))


def read_package_text(package: str, filename: str) -> str:
    try:
        return resources.files(package).joinpath(filename).read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SystemExit(f"Packaged config not found: {package}/{filename}") from exc


def _package_has_file(package: str, filename: str) -> bool:
    try:
        return resources.files(package).joinpath(filename).is_file()
    except Exception:
        return False


def _resolve_alias(ref: str, aliases: Optional[Mapping[str, str]]) -> Optional[str]:
    if not aliases:
        return None
    key = ref.strip()
    candidates = [
        key,
        key.lower(),
        Path(key).name,
        Path(key).name.lower(),
    ]
    for candidate in candidates:
        if candidate in aliases:
            return aliases[candidate]
    return None


def resolve_config(
    ref: str | Path | None,
    *,
    package: str,
    default_name: str,
    aliases: Optional[Mapping[str, str]] = None,
) -> ResolvedConfig:
    if ref is None or str(ref).strip() == "":
        data = load_yaml_package(package, default_name)
        label = Path(default_name).stem
        source = f"package:{package}/{default_name}"
        return ResolvedConfig(data=data, label=label, path=None, source=source)

    ref_text = str(ref).strip()
    path = Path(ref_text)
    if path.exists():
        data = load_yaml_path(path)
        return ResolvedConfig(data=data, label=path.stem, path=path, source=str(path))

    alias = _resolve_alias(ref_text, aliases)
    if alias is None:
        candidate = Path(ref_text).name
        if candidate and _package_has_file(package, candidate):
            alias = candidate

    if alias:
        data = load_yaml_package(package, alias)
        label = Path(alias).stem
        source = f"package:{package}/{alias}"
        return ResolvedConfig(data=data, label=label, path=None, source=source)

    raise SystemExit(f"Config file not found: {ref_text}")


PIPELINE_ALIASES: Mapping[str, str] = {
    "default": "default.yml",
    "default.yml": "default.yml",
    "default.yaml": "default.yml",
    "cn": "cn.yml",
    "cn.yml": "cn.yml",
    "cn.yaml": "cn.yml",
    "hk": "hk.yml",
    "hk.yml": "hk.yml",
    "hk.yaml": "hk.yml",
    "us": "us.yml",
    "us.yml": "us.yml",
    "us.yaml": "us.yml",
}


def resolve_pipeline_config(ref: str | Path | None) -> ResolvedConfig:
    return resolve_config(
        ref,
        package="csml.config",
        default_name="default.yml",
        aliases=PIPELINE_ALIASES,
    )


def resolve_pipeline_filename(ref: str) -> str:
    alias = _resolve_alias(ref, PIPELINE_ALIASES)
    if alias:
        return alias
    candidate = Path(ref).name
    if _package_has_file("csml.config", candidate):
        return candidate
    raise SystemExit(f"Unknown built-in config name: {ref}")
