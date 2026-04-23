from __future__ import annotations

import argparse
from typing import Any, Sequence

from . import alloc as base_alloc
from .alloc_hk_types import HkAllocSettings


def parse_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "是"}:
        return True
    if text in {"false", "0", "no", "n", "否"}:
        return False
    return default


def nested_mapping(mapping: Any, *keys: str) -> dict[str, Any]:
    current = mapping if isinstance(mapping, dict) else {}
    for key in keys:
        next_value = current.get(key) if isinstance(current, dict) else {}
        current = next_value if isinstance(next_value, dict) else {}
    return current


def parse_float_list(values: Sequence[Any] | None) -> list[float]:
    if values is None:
        return []
    items: list[float] = []
    for entry in values:
        parts: Sequence[Any] = entry.split(",") if isinstance(entry, str) else [entry]
        for part in parts:
            text = str(part).strip()
            if not text:
                continue
            items.append(float(text))
    return items


def parse_int_list(values: Sequence[Any] | None) -> list[int]:
    if values is None:
        return []
    items: list[int] = []
    for entry in values:
        parts: Sequence[Any] = entry.split(",") if isinstance(entry, str) else [entry]
        for part in parts:
            text = str(part).strip()
            if not text:
                continue
            items.append(int(text))
    return items


def dedupe_preserve_order(values: Sequence[Any]) -> list[Any]:
    return list(dict.fromkeys(values))


def resolve_settings(args: argparse.Namespace) -> tuple[dict[str, Any], HkAllocSettings]:
    cfg = base_alloc._load_config(getattr(args, "config", None))
    hk_cfg = nested_mapping(cfg, "live", "alloc_hk")
    valuation_cfg = hk_cfg.get("valuation") if isinstance(hk_cfg.get("valuation"), dict) else {}
    fill_cfg = hk_cfg.get("secondary_fill") if isinstance(hk_cfg.get("secondary_fill"), dict) else {}

    settings = HkAllocSettings(
        cash=float(args.cash) if args.cash is not None else float(hk_cfg.get("cash", 1_000_000.0)),
        method=str(args.method or hk_cfg.get("method", "equal")).strip().lower(),
        require_stock_connect=(
            parse_bool(args.require_stock_connect, True)
            if args.require_stock_connect is not None
            else parse_bool(hk_cfg.get("require_stock_connect"), True)
        ),
        history_years=(
            int(args.history_years)
            if args.history_years is not None
            else int(valuation_cfg.get("history_years", 3))
        ),
        roll_window=(
            int(args.roll_window)
            if args.roll_window is not None
            else int(valuation_cfg.get("roll_window", 252))
        ),
        sell_quantile=(
            float(args.sell_quantile)
            if args.sell_quantile is not None
            else float(valuation_cfg.get("sell_quantile", 0.95))
        ),
        extreme_quantile=(
            float(args.extreme_quantile)
            if args.extreme_quantile is not None
            else float(valuation_cfg.get("extreme_quantile", 0.99))
        ),
        secondary_fill_enabled=(
            parse_bool(args.secondary_fill_enabled, True)
            if args.secondary_fill_enabled is not None
            else parse_bool(fill_cfg.get("enabled"), True)
        ),
        secondary_fill_avoid_high_valuation=(
            parse_bool(args.avoid_high_valuation, True)
            if args.avoid_high_valuation is not None
            else parse_bool(fill_cfg.get("avoid_high_valuation"), True)
        ),
        secondary_fill_avoid_high_valuation_strict=(
            parse_bool(args.avoid_high_valuation_strict, False)
            if args.avoid_high_valuation_strict is not None
            else parse_bool(fill_cfg.get("avoid_high_valuation_strict"), False)
        ),
        secondary_fill_max_steps=(
            int(args.max_steps)
            if args.max_steps is not None
            else int(fill_cfg.get("max_steps", 5000))
        ),
        secondary_fill_allow_over_alloc=(
            parse_bool(args.allow_over_alloc, False)
            if args.allow_over_alloc is not None
            else parse_bool(fill_cfg.get("allow_over_alloc"), False)
        ),
        secondary_fill_max_over_alloc_ratio=(
            float(args.max_over_alloc_ratio)
            if args.max_over_alloc_ratio is not None
            else float(fill_cfg.get("max_over_alloc_ratio", 0.0))
        ),
        secondary_fill_max_over_alloc_amount=(
            float(args.max_over_alloc_amount)
            if args.max_over_alloc_amount is not None
            else float(fill_cfg.get("max_over_alloc_amount", 0.0))
        ),
        secondary_fill_max_over_alloc_lots_per_ticker=(
            int(args.max_over_alloc_lots_per_ticker)
            if args.max_over_alloc_lots_per_ticker is not None
            else int(fill_cfg.get("max_over_alloc_lots_per_ticker", 1))
        ),
        secondary_fill_cash_buffer_ratio=(
            float(args.cash_buffer_ratio)
            if args.cash_buffer_ratio is not None
            else float(fill_cfg.get("cash_buffer_ratio", 0.0))
        ),
        secondary_fill_cash_buffer_amount=(
            float(args.cash_buffer_amount)
            if args.cash_buffer_amount is not None
            else float(fill_cfg.get("cash_buffer_amount", 0.0))
        ),
        secondary_fill_estimated_fee_per_order=(
            float(args.estimated_fee_per_order)
            if args.estimated_fee_per_order is not None
            else float(fill_cfg.get("estimated_fee_per_order", 0.0))
        ),
    )

    if settings.cash <= 0:
        raise SystemExit("--cash must be positive.")
    if settings.method not in {"equal", "custom"}:
        raise SystemExit("--method must be one of: equal, custom.")
    if settings.history_years <= 0:
        raise SystemExit("history_years must be > 0.")
    if settings.roll_window <= 1:
        raise SystemExit("roll_window must be > 1.")
    if not (0.0 < settings.sell_quantile < 1.0):
        raise SystemExit("sell_quantile must be in (0, 1).")
    if not (0.0 < settings.extreme_quantile < 1.0):
        raise SystemExit("extreme_quantile must be in (0, 1).")
    if settings.sell_quantile >= settings.extreme_quantile:
        raise SystemExit("sell_quantile must be less than extreme_quantile.")
    if settings.secondary_fill_max_steps <= 0:
        raise SystemExit("secondary_fill.max_steps must be > 0.")
    if settings.secondary_fill_max_over_alloc_ratio < 0:
        raise SystemExit("secondary_fill.max_over_alloc_ratio must be >= 0.")
    if settings.secondary_fill_max_over_alloc_amount < 0:
        raise SystemExit("secondary_fill.max_over_alloc_amount must be >= 0.")
    if settings.secondary_fill_max_over_alloc_lots_per_ticker < 0:
        raise SystemExit("secondary_fill.max_over_alloc_lots_per_ticker must be >= 0.")
    if settings.secondary_fill_cash_buffer_ratio < 0:
        raise SystemExit("secondary_fill.cash_buffer_ratio must be >= 0.")
    if settings.secondary_fill_cash_buffer_amount < 0:
        raise SystemExit("secondary_fill.cash_buffer_amount must be >= 0.")
    if settings.secondary_fill_estimated_fee_per_order < 0:
        raise SystemExit("secondary_fill.estimated_fee_per_order must be >= 0.")
    if (
        settings.secondary_fill_allow_over_alloc
        and settings.secondary_fill_max_over_alloc_lots_per_ticker == 0
    ):
        raise SystemExit(
            "secondary_fill.max_over_alloc_lots_per_ticker must be > 0 when allow_over_alloc=true."
        )

    return cfg, settings


def resolve_scenarios(
    args: argparse.Namespace,
    *,
    cfg: dict[str, Any],
    settings: HkAllocSettings,
) -> tuple[tuple[float, ...], tuple[int, ...]]:
    scenarios_cfg = nested_mapping(cfg, "live", "alloc_hk", "scenarios")
    raw_capitals: Sequence[Any] | None = args.scenario_capital
    raw_top_ns: Sequence[Any] | None = args.scenario_top_n

    if raw_capitals is None:
        cfg_capitals = scenarios_cfg.get("capitals")
        if isinstance(cfg_capitals, (list, tuple)):
            raw_capitals = list(cfg_capitals)
    if raw_top_ns is None:
        cfg_top_ns = scenarios_cfg.get("top_ns")
        if isinstance(cfg_top_ns, (list, tuple)):
            raw_top_ns = list(cfg_top_ns)

    capitals = parse_float_list(raw_capitals) if raw_capitals is not None else [settings.cash]
    top_ns = parse_int_list(raw_top_ns) if raw_top_ns is not None else [args.top_n]

    if not capitals:
        capitals = [settings.cash]
    if not top_ns:
        top_ns = [args.top_n]

    capitals = dedupe_preserve_order(capitals)
    top_ns = dedupe_preserve_order(top_ns)

    for idx, capital in enumerate(capitals):
        if capital <= 0:
            raise SystemExit(f"scenario capital at index {idx} must be > 0.")
    for idx, top_n in enumerate(top_ns):
        if top_n <= 0:
            raise SystemExit(f"scenario top_n at index {idx} must be > 0.")

    return tuple(float(value) for value in capitals), tuple(int(value) for value in top_ns)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute HK pre-trade lot sizing and valuation diagnostics from latest holdings.",
    )
    parser.add_argument("--config", help="Pipeline config path or built-in name (default: default).")
    parser.add_argument("--run-dir", help="Explicit run directory to read (overrides --config).")
    parser.add_argument(
        "--artifacts-root",
        help=(
            "Optional artifacts root override used when resolving the default runs directory. "
            "When omitted, alloc-hk uses CSTREE_ARTIFACTS_ROOT, "
            "paths.artifacts_root, or artifacts/."
        ),
    )
    parser.add_argument("--positions-file", help="Explicit positions CSV path (overrides --config/--run-dir).")
    parser.add_argument("--top-k", type=int, help="Optional Top-K filter when selecting the latest run.")
    parser.add_argument(
        "--as-of",
        default="t-1",
        help=(
            "As-of date (YYYYMMDD, YYYY-MM-DD, today, t-1, last_trading_day, "
            "last_completed_trading_day). Default: t-1."
        ),
    )
    parser.add_argument(
        "--source",
        default="auto",
        choices=["auto", "backtest", "live"],
        help="Positions source (auto/backtest/live). Default: auto.",
    )
    parser.add_argument(
        "--side",
        default="long",
        choices=["long", "short", "all"],
        help="Select side for allocation (long/short/all). Default: long.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="Number of names to allocate from sorted holdings. Default: 20.",
    )
    parser.add_argument(
        "--scenario-capital",
        action="append",
        default=None,
        help="Scenario capital list (repeatable, supports comma-separated values).",
    )
    parser.add_argument(
        "--scenario-top-n",
        action="append",
        default=None,
        help="Scenario Top-N list (repeatable, supports comma-separated values).",
    )
    parser.add_argument("--cash", type=float, help="Total portfolio cash for sizing. Overrides live.alloc_hk.cash.")
    parser.add_argument(
        "--method",
        choices=["equal", "custom"],
        help="Sizing method. custom uses holdings weight. Overrides live.alloc_hk.method.",
    )
    parser.add_argument(
        "--require-stock-connect",
        dest="require_stock_connect",
        action="store_true",
        default=None,
        help="Require stock_connect eligibility for tradable names.",
    )
    parser.add_argument(
        "--allow-non-stock-connect",
        dest="require_stock_connect",
        action="store_false",
        help="Allow non-stock-connect names to remain tradable.",
    )
    parser.add_argument("--history-years", type=int, help="Lookback years for valuation history.")
    parser.add_argument("--roll-window", type=int, help="Rolling window used for valuation thresholds.")
    parser.add_argument("--sell-quantile", type=float, help="Quantile used for HIGH valuation threshold.")
    parser.add_argument("--extreme-quantile", type=float, help="Quantile used for EXTREME valuation threshold.")
    parser.add_argument(
        "--secondary-fill",
        dest="secondary_fill_enabled",
        action="store_true",
        default=None,
        help="Enable secondary fill after base lot sizing.",
    )
    parser.add_argument(
        "--no-secondary-fill",
        dest="secondary_fill_enabled",
        action="store_false",
        help="Disable secondary fill after base lot sizing.",
    )
    parser.add_argument(
        "--avoid-high-valuation",
        dest="avoid_high_valuation",
        action="store_true",
        default=None,
        help="Prefer LOW/NEUTRAL names first during secondary fill.",
    )
    parser.add_argument(
        "--allow-high-valuation",
        dest="avoid_high_valuation",
        action="store_false",
        help="Do not prefer LOW/NEUTRAL names during secondary fill.",
    )
    parser.add_argument(
        "--avoid-high-valuation-strict",
        dest="avoid_high_valuation_strict",
        action="store_true",
        default=None,
        help="Hard-block HIGH/EXTREME names during secondary fill.",
    )
    parser.add_argument(
        "--allow-over-alloc",
        dest="allow_over_alloc",
        action="store_true",
        default=None,
        help="Allow bounded over-allocation during secondary fill.",
    )
    parser.add_argument("--max-steps", type=int, help="Maximum secondary fill steps.")
    parser.add_argument("--max-over-alloc-ratio", type=float, help="Over-allocation cap as a ratio of cash.")
    parser.add_argument("--max-over-alloc-amount", type=float, help="Over-allocation cap as an absolute amount.")
    parser.add_argument(
        "--max-over-alloc-lots-per-ticker",
        type=int,
        help="Per-ticker cap for over-allocation lots.",
    )
    parser.add_argument("--cash-buffer-ratio", type=float, help="Cash buffer ratio reserved before fill.")
    parser.add_argument("--cash-buffer-amount", type=float, help="Cash buffer amount reserved before fill.")
    parser.add_argument(
        "--estimated-fee-per-order",
        type=float,
        help="Estimated fee added to each secondary fill step.",
    )
    parser.add_argument("--username", help="Override RQData username.")
    parser.add_argument("--password", help="Override RQData password.")
    parser.add_argument(
        "--fail-on-quality",
        choices=["none", "info", "warning", "error"],
        default=None,
        help=(
            "Optional quality gate threshold. When omitted, alloc-hk reuses the threshold stored "
            "in the resolved run summary or from the config."
        ),
    )
    parser.add_argument(
        "--format",
        default="text",
        choices=["text", "csv", "json", "xlsx"],
        help="Output format (text/csv/json/xlsx). Default: text.",
    )
    parser.add_argument("--out", help="Optional output path (default: stdout; required for xlsx).")
    args = parser.parse_args(argv)

    if args.top_n <= 0:
        raise SystemExit("--top-n must be a positive integer.")
    return args
