from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
import yaml


def _load_config(path: str | None) -> dict:
    if not path:
        return {}
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise SystemExit(f"Config file not found: {cfg_path}")
    with cfg_path.open("r", encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle) or {}
    if not isinstance(cfg, dict):
        raise SystemExit("Config root must be a mapping.")
    return cfg


def _init_rqdatac(args) -> object:
    try:
        import rqdatac
    except ImportError as exc:
        raise SystemExit(
            "rqdatac is not installed. Install with: pip install '.[rqdata]'"
        ) from exc

    load_dotenv()
    init_kwargs: dict = {}
    cfg = _load_config(args.config) if getattr(args, "config", None) else {}
    rq_cfg = cfg.get("data", {}).get("rqdata", {}) if isinstance(cfg, dict) else {}
    if isinstance(rq_cfg, dict) and isinstance(rq_cfg.get("init"), dict):
        init_kwargs.update(rq_cfg.get("init"))

    if getattr(args, "username", None):
        init_kwargs["username"] = args.username
    if getattr(args, "password", None):
        init_kwargs["password"] = args.password

    env_username = os.getenv("RQDATA_USERNAME") or os.getenv("RQDATA_USER")
    env_password = os.getenv("RQDATA_PASSWORD")
    if env_username and "username" not in init_kwargs:
        init_kwargs["username"] = env_username
    if env_password and "password" not in init_kwargs:
        init_kwargs["password"] = env_password

    try:
        rqdatac.init(**init_kwargs)
    except Exception as exc:
        raise SystemExit(f"rqdatac.init failed: {exc}") from exc
    return rqdatac


def _handle_run(args) -> int:
    import main as pipeline

    pipeline.main(["--config", args.config])
    return 0


def _handle_rqdata_info(args) -> int:
    rqdatac = _init_rqdatac(args)
    info = rqdatac.info()
    print(info)
    return 0


def _handle_rqdata_quota(args) -> int:
    rqdatac = _init_rqdatac(args)
    quota = rqdatac.user.get_quota()
    payload = quota
    if hasattr(quota, "to_dict"):
        try:
            payload = quota.to_dict(orient="records")
        except TypeError:
            payload = quota.to_dict()
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


def _handle_universe_hk_connect(args) -> int:
    from project_tools import build_hk_connect_universe

    build_hk_connect_universe.main(args.args)
    return 0


def _handle_universe_index_components(args) -> int:
    from project_tools import fetch_index_components

    fetch_index_components.main(args.args)
    return 0


def _handle_tushare_verify(args) -> int:
    from project_tools import verify_tushare_tokens

    verify_tushare_tokens.main(args.args)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="csxgb", description="Cross-sectional XGBoost CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run the main training/eval/backtest pipeline")
    run.add_argument("--config", default="config/config.yml", help="Path to YAML config")
    run.set_defaults(func=_handle_run)

    rqdata = subparsers.add_parser("rqdata", help="RQData utilities")
    rq_sub = rqdata.add_subparsers(dest="rq_command", required=True)

    rq_info = rq_sub.add_parser("info", help="Show rqdatac login/info")
    rq_info.add_argument("--config", help="Optional config path to load rqdata.init")
    rq_info.add_argument("--username", help="Override RQData username")
    rq_info.add_argument("--password", help="Override RQData password")
    rq_info.set_defaults(func=_handle_rqdata_info)

    rq_quota = rq_sub.add_parser("quota", help="Show rqdatac quota usage")
    rq_quota.add_argument("--config", help="Optional config path to load rqdata.init")
    rq_quota.add_argument("--username", help="Override RQData username")
    rq_quota.add_argument("--password", help="Override RQData password")
    rq_quota.set_defaults(func=_handle_rqdata_quota)

    universe = subparsers.add_parser("universe", help="Universe construction helpers")
    uni_sub = universe.add_subparsers(dest="uni_command", required=True)

    hk = uni_sub.add_parser("hk-connect", help="Build HK Connect universe")
    hk.add_argument("args", nargs=argparse.REMAINDER)
    hk.set_defaults(func=_handle_universe_hk_connect)

    index_components = uni_sub.add_parser(
        "index-components", help="Fetch index constituents (TuShare)"
    )
    index_components.add_argument("args", nargs=argparse.REMAINDER)
    index_components.set_defaults(func=_handle_universe_index_components)

    tushare = subparsers.add_parser("tushare", help="TuShare utilities")
    tu_sub = tushare.add_subparsers(dest="tushare_command", required=True)

    verify = tu_sub.add_parser("verify-token", help="Verify TuShare token(s)")
    verify.add_argument("args", nargs=argparse.REMAINDER)
    verify.set_defaults(func=_handle_tushare_verify)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 1
    return int(func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
