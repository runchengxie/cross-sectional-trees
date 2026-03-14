from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Mapping, Optional

import yaml


EXTENDS_KEY = "extends"


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge two dictionaries. Override takes precedence."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _resolve_extends(
    data: dict,
    *,
    package: str,
    search_paths: list[str] | None = None,
    _visited: set[str] | None = None,
) -> dict:
    """Recursively resolve extends directive."""
    if _visited is None:
        _visited = set()

    if EXTENDS_KEY not in data:
        return data

    extends_list = data[EXTENDS_KEY]
    if isinstance(extends_list, str):
        extends_list = [extends_list]
    elif not isinstance(extends_list, list):
        raise SystemExit(f"'{EXTENDS_KEY}' must be a string or list of strings")

    if not extends_list:
        del data[EXTENDS_KEY]
        return data

    base_configs: list[dict] = []
    for extends_ref in extends_list:
        extends_ref = str(extends_ref).strip()
        if not extends_ref:
            continue

        visited_key = f"{package}:{extends_ref}"
        if visited_key in _visited:
            raise SystemExit(f"Circular extends detected: {extends_ref}")
        _visited.add(visited_key)

        base_data = _load_config_by_ref(
            extends_ref,
            package=package,
            search_paths=search_paths,
        )
        base_configs.append(base_data)

    del data[EXTENDS_KEY]

    merged = {}
    for base in base_configs:
        merged = _deep_merge(merged, base)

    merged = _deep_merge(merged, data)
    return merged


def _load_config_by_ref(
    ref: str,
    *,
    package: str,
    search_paths: list[str] | None = None,
) -> dict:
    """Load a single config by reference (path, alias, or package file)."""
    path = Path(ref)

    if path.exists():
        return load_yaml_path(path)

    if search_paths:
        for search_dir in search_paths:
            search_path = Path(search_dir) / path.name
            if search_path.exists():
                return load_yaml_path(search_path)

    candidate = path.name
    if _package_has_file(package, candidate):
        return load_yaml_package(package, candidate)

    raise SystemExit(f"Config file not found for extends: {ref}")


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
    package: str | None,
    default_name: str,
    aliases: Optional[Mapping[str, str]] = None,
    search_paths: list[str] | None = None,
) -> ResolvedConfig:
    """Resolve pipeline config with extends support."""
    if ref is None or str(ref).strip() == "":
        if package is None:
            # Load from filesystem
            base_data = None
            for search_dir in search_paths:
                search_path = Path(search_dir) / default_name
                if search_path.exists():
                    base_data = load_yaml_path(search_path)
                    break
            if base_data is None:
                raise SystemExit(f"Default config not found: {default_name}")
        else:
            base_data = load_yaml_package(package, default_name)
        base_data = _resolve_extends(base_data, package=package, search_paths=search_paths)
        label = Path(default_name).stem
        source = f"{default_name}" if package is None else f"package:{package}/{default_name}"
        return ResolvedConfig(data=base_data, label=label, path=None, source=source)

    ref_text = str(ref).strip()
    path = Path(ref_text)
    if path.exists():
        data = load_yaml_path(path)
        data = _resolve_extends(data, package=package, search_paths=search_paths)
        return ResolvedConfig(data=data, label=path.stem, path=path, source=str(path))

    alias = _resolve_alias(ref_text, aliases)
    if alias is None:
        candidate = Path(ref_text).name
        if candidate and _package_has_file(package, candidate):
            alias = candidate

    if alias:
        if package is None:
            # Load from filesystem search_paths
            base_data = None
            for search_dir in search_paths:
                search_path = Path(search_dir) / alias
                if search_path.exists():
                    base_data = load_yaml_path(search_path)
                    break
            if base_data is None:
                raise SystemExit(f"Config file not found: {alias}")
        else:
            base_data = load_yaml_package(package, alias)
        base_data = _resolve_extends(base_data, package=package, search_paths=search_paths)
        label = Path(alias).stem
        source = f"{alias}" if package is None else f"package:{package}/{alias}"
        return ResolvedConfig(data=base_data, label=label, path=None, source=source)

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
    """Resolve pipeline config from project configs/ directory."""
    # Use project root configs/ instead of packaged csml.config
    project_root = Path(__file__).parent.parent.parent
    configs_dir = project_root / "configs"
    search_paths = [
        str(configs_dir / "presets"),
        str(configs_dir / "experiments"),
        str(configs_dir),
    ]
    return resolve_config(
        ref,
        package=None,  # Disable package loading, use filesystem only
        default_name="default.yml",
        aliases=PIPELINE_ALIASES,
        search_paths=search_paths,
    )


def resolve_pipeline_filename(ref: str) -> str:
    """Resolve pipeline config filename from project configs/ directory."""
    project_root = Path(__file__).parent.parent.parent
    configs_dir = project_root / "configs"
    search_paths = [
        str(configs_dir / "presets"),
        str(configs_dir / "experiments"),
        str(configs_dir),
    ]

    alias = _resolve_alias(ref, PIPELINE_ALIASES)
    if alias:
        return alias
    candidate = Path(ref).name
    for search_dir in search_paths:
        search_path = Path(search_dir) / candidate
        if search_path.exists():
            return candidate
    raise SystemExit(f"Unknown config name: {ref}")
