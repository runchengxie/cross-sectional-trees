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


@dataclass(frozen=True)
class LoadedConfigRef:
    data: dict
    path: Path | None
    source: str


def _iter_search_candidates(
    ref: str,
    *,
    current_path: Path | None,
    search_paths: list[str] | None,
) -> list[Path]:
    path = Path(ref).expanduser()
    candidates: list[Path] = []

    if path.is_absolute():
        candidates.append(path)
        return candidates

    if current_path is not None:
        candidates.append((current_path.parent / path).resolve())

    candidates.append((Path.cwd() / path).resolve())

    for search_dir in search_paths or []:
        search_root = Path(search_dir)
        candidates.append((search_root / path).resolve())
        if path.name and path.name != str(path):
            candidates.append((search_root / path.name).resolve())

    deduped: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        deduped.append(candidate)
    return deduped


def _resolve_extends(
    data: dict,
    *,
    package: str,
    search_paths: list[str] | None = None,
    current_path: Path | None = None,
    _stack: set[str] | None = None,
) -> dict:
    """Recursively resolve extends directive."""
    if _stack is None:
        _stack = set()

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

        base_config = _load_config_by_ref(
            extends_ref,
            package=package,
            search_paths=search_paths,
            current_path=current_path,
        )
        if base_config is None:
            raise SystemExit(f"Config file not found for extends: {extends_ref}")
        if base_config.source in _stack:
            raise SystemExit(f"Circular extends detected: {extends_ref}")

        _stack.add(base_config.source)
        try:
            base_data = _resolve_extends(
                base_config.data,
                package=package,
                search_paths=search_paths,
                current_path=base_config.path,
                _stack=_stack,
            )
        finally:
            _stack.remove(base_config.source)
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
    current_path: Path | None = None,
) -> LoadedConfigRef | None:
    """Load a single config by reference (path, alias, or package file)."""
    for candidate_path in _iter_search_candidates(
        ref,
        current_path=current_path,
        search_paths=search_paths,
    ):
        if candidate_path.exists():
            resolved_path = candidate_path.resolve()
            return LoadedConfigRef(
                data=load_yaml_path(resolved_path),
                path=resolved_path,
                source=str(resolved_path),
            )

    candidate = Path(ref).name
    if package is not None and _package_has_file(package, candidate):
        return LoadedConfigRef(
            data=load_yaml_package(package, candidate),
            path=None,
            source=f"package:{package}/{candidate}",
        )

    return None


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
    search_paths = list(search_paths or [])

    if ref is None or str(ref).strip() == "":
        if package is None:
            default_ref = _load_config_by_ref(
                default_name,
                package=package,
                search_paths=search_paths,
            )
            if default_ref is None:
                raise SystemExit(f"Default config not found: {default_name}")
            base_data = default_ref.data
            resolved_path = default_ref.path
        else:
            base_data = load_yaml_package(package, default_name)
            resolved_path = None
        base_data = _resolve_extends(
            base_data,
            package=package,
            search_paths=search_paths,
            current_path=resolved_path,
        )
        label = Path(default_name).stem
        source = (
            default_ref.source
            if package is None
            else f"package:{package}/{default_name}"
        )
        return ResolvedConfig(data=base_data, label=label, path=resolved_path, source=source)

    ref_text = str(ref).strip()
    explicit = _load_config_by_ref(
        ref_text,
        package=package,
        search_paths=search_paths,
    )
    if explicit is not None:
        data = _resolve_extends(
            explicit.data,
            package=package,
            search_paths=search_paths,
            current_path=explicit.path,
        )
        label = Path(ref_text).stem if explicit.path is None else explicit.path.stem
        return ResolvedConfig(data=data, label=label, path=explicit.path, source=explicit.source)

    alias = _resolve_alias(ref_text, aliases)
    if alias is None and package is not None:
        candidate = Path(ref_text).name
        if candidate and _package_has_file(package, candidate):
            alias = candidate

    if alias:
        if package is None:
            # Load from filesystem search_paths
            alias_ref = _load_config_by_ref(
                alias,
                package=package,
                search_paths=search_paths,
            )
            if alias_ref is None:
                raise SystemExit(f"Config file not found: {alias}")
            base_data = alias_ref.data
            resolved_path = alias_ref.path
        else:
            base_data = load_yaml_package(package, alias)
            resolved_path = None
        base_data = _resolve_extends(
            base_data,
            package=package,
            search_paths=search_paths,
            current_path=resolved_path,
        )
        label = Path(alias).stem
        source = f"{alias}" if package is None else f"package:{package}/{alias}"
        return ResolvedConfig(data=base_data, label=label, path=resolved_path, source=source)

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
        str(project_root),
        str(configs_dir),
        str(configs_dir / "presets"),
        str(configs_dir / "experiments"),
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
        str(project_root),
        str(configs_dir),
        str(configs_dir / "presets"),
        str(configs_dir / "experiments"),
    ]

    alias = _resolve_alias(ref, PIPELINE_ALIASES)
    if alias:
        return alias
    path = Path(ref)
    for candidate in _iter_search_candidates(ref, current_path=None, search_paths=search_paths):
        if candidate.exists():
            return path.name
    raise SystemExit(f"Unknown config name: {ref}")
