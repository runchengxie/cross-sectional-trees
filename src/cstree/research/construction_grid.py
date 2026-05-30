from __future__ import annotations

import argparse
import csv
import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from ..backtest import backtest_topk
from ..data_tools.symbols import canonicalize_symbol_columns
from ..execution import build_execution_model
from ..metrics import (
    daily_ic_series,
    estimate_turnover,
    quantile_returns,
    summarize_active_returns,
    summarize_ic,
)
from ..rebalance import get_rebalance_dates
from ..transform import apply_score_postprocess

FIELDNAMES = [
    "variant",
    "scored_file",
    "summary_path",
    "target_col",
    "price_col",
    "eval_signal_col",
    "backtest_signal_col",
    "top_k",
    "short_k",
    "long_only",
    "cost_bps",
    "buffer_exit",
    "buffer_entry",
    "weighting",
    "score_postprocess_method",
    "score_postprocess_columns",
    "eval_ic_mean",
    "eval_ic_ir",
    "eval_long_short",
    "eval_turnover_mean",
    "backtest_periods",
    "backtest_total_return",
    "backtest_gross_total_return",
    "backtest_ann_return",
    "backtest_ann_vol",
    "backtest_sharpe",
    "backtest_max_drawdown",
    "backtest_avg_turnover",
    "backtest_avg_cost_drag",
    "active_total_return",
    "information_ratio",
    "tracking_error",
    "beta",
    "alpha",
    "corr",
    "benchmark_name",
    "benchmark_returns_file",
    "exposure_available",
    "status",
    "error",
]


def _resolve_path(path_text: str | Path | None, *, base_dir: Path | None = None) -> Path | None:
    if path_text is None:
        return None
    candidate = Path(path_text).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    if base_dir is not None:
        by_base = (base_dir / candidate).resolve()
        if by_base.exists():
            return by_base
    return (Path.cwd() / candidate).resolve()


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Construction grid config not found: {path}")
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Failed to parse construction grid config: {path} ({exc})") from exc
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise SystemExit(f"Construction grid config must be a mapping: {path}")
    return payload


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Failed to parse summary JSON: {path} ({exc})") from exc
    return payload if isinstance(payload, dict) else {}


def _get_nested(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def _periods_per_year(stats: dict[str, Any], fallback: int) -> float:
    value = stats.get("periods_per_year")
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(fallback)
    return number if np.isfinite(number) and number > 0 else float(fallback)


def _read_returns_file(path: Path) -> pd.Series:
    if not path.exists():
        raise FileNotFoundError(f"Benchmark returns file not found: {path}")
    frame = pd.read_csv(path)
    date_col = next((col for col in ("trade_date", "date", "period_end") if col in frame.columns), None)
    ret_col = next(
        (
            col
            for col in (
                "benchmark_return",
                "return",
                "net_return",
                "strategy_return",
                "active_return",
            )
            if col in frame.columns
        ),
        None,
    )
    if date_col is None or ret_col is None:
        raise ValueError(
            "Returns file must include a date column and one return column "
            "(benchmark_return, return, net_return, or strategy_return)."
        )
    series = pd.Series(
        pd.to_numeric(frame[ret_col], errors="coerce").to_numpy(dtype=float),
        index=pd.to_datetime(frame[date_col]),
        name=ret_col,
    ).dropna()
    return series.sort_index()


def _parse_date_list(values: Any) -> list[pd.Timestamp]:
    if not isinstance(values, list):
        return []
    parsed: list[pd.Timestamp] = []
    for raw in values:
        dt = pd.to_datetime(raw, format="%Y%m%d", errors="coerce")
        if pd.isna(dt):
            dt = pd.to_datetime(raw, errors="coerce")
        if not pd.isna(dt):
            parsed.append(pd.Timestamp(dt))
    return sorted(dict.fromkeys(parsed))


def _resolve_rebalance_dates(
    summary_dates: Any,
    scored_data: pd.DataFrame,
    frequency: str,
    min_symbols_per_date: int,
) -> list[pd.Timestamp]:
    parsed = _parse_date_list(summary_dates)
    available = set(pd.to_datetime(scored_data["trade_date"].unique()))
    if parsed:
        return [date for date in parsed if date in available]

    trade_dates = sorted(available)
    dates = get_rebalance_dates(trade_dates, frequency)
    if min_symbols_per_date > 1:
        counts = scored_data.groupby("trade_date")["symbol"].nunique()
        valid_dates = set(pd.to_datetime(counts[counts >= min_symbols_per_date].index))
        dates = [date for date in dates if date in valid_dates]
    return dates


def _load_scored_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"Scored file not found: {path}")
    frame = pd.read_parquet(path)
    if frame.empty:
        raise SystemExit(f"Scored file is empty: {path}")
    frame = canonicalize_symbol_columns(frame, context="Construction grid scored data")
    if "trade_date" not in frame.columns:
        raise SystemExit("Scored data must include trade_date.")
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    return frame


def _prepare_signal_column(
    data: pd.DataFrame,
    signal_col: str,
    variant: dict[str, Any],
) -> tuple[pd.DataFrame, str, str, str]:
    postprocess = variant.get("score_postprocess") or {}
    if not isinstance(postprocess, dict):
        raise ValueError("score_postprocess must be a mapping.")
    method = str(postprocess.get("method", "none")).strip().lower()
    columns = [str(col) for col in postprocess.get("columns", [])]
    if method == "none":
        return data, signal_col, method, ",".join(columns)
    out = data.copy()
    derived_col = f"__construction_score_{variant.get('name', 'variant')}"
    out[derived_col] = apply_score_postprocess(
        out,
        signal_col,
        method=method,
        columns=columns,
        strength=float(postprocess.get("strength", 1.0)),
        min_obs=postprocess.get("min_obs"),
    )
    return out, derived_col, method, ",".join(columns)


def _build_base_context(config: dict[str, Any], config_dir: Path) -> dict[str, Any]:
    cfg = config.get("construction_grid", config)
    if not isinstance(cfg, dict):
        raise SystemExit("construction_grid must be a mapping.")

    summary_path = _resolve_path(cfg.get("summary_file") or cfg.get("summary_path"), base_dir=config_dir)
    summary = _load_json(summary_path)
    run_dir = _resolve_path(_get_nested(summary, "run", "output_dir"), base_dir=config_dir)
    if run_dir is None and summary_path is not None:
        run_dir = summary_path.parent

    scored_file = _first_non_empty(
        cfg.get("scored_file"),
        _get_nested(summary, "eval", "scored_file"),
    )
    scored_path = _resolve_path(scored_file, base_dir=run_dir or config_dir)
    if scored_path is None:
        raise SystemExit("Construction grid requires scored_file or summary.eval.scored_file.")
    scored_data = _load_scored_data(scored_path)

    target_col = str(
        _first_non_empty(
            cfg.get("target_col"),
            _get_nested(summary, "label", "target_col"),
            "future_return",
        )
    )
    price_col = str(
        _first_non_empty(
            cfg.get("price_col"),
            _get_nested(summary, "data", "price_col"),
            "close",
        )
    )
    eval_signal_col = str(
        _first_non_empty(
            cfg.get("eval_signal_col"),
            _get_nested(summary, "eval", "scored_signal_col"),
            "signal_eval",
            "pred",
        )
    )
    if eval_signal_col not in scored_data.columns and "pred" in scored_data.columns:
        eval_signal_col = "pred"
    backtest_signal_col = str(
        _first_non_empty(
            cfg.get("backtest_signal_col"),
            _get_nested(summary, "eval", "scored_signal_backtest_col"),
            eval_signal_col,
        )
    )
    if backtest_signal_col not in scored_data.columns:
        backtest_signal_col = eval_signal_col

    missing_cols = [
        col
        for col in ("trade_date", "symbol", target_col, price_col, eval_signal_col, backtest_signal_col)
        if col not in scored_data.columns
    ]
    if missing_cols:
        raise SystemExit("Missing required columns in scored data: " + ", ".join(missing_cols))

    min_symbols_per_date = int(
        _first_non_empty(cfg.get("min_symbols_per_date"), _get_nested(summary, "data", "min_symbols_per_date"), 1)
    )
    eval_frequency = str(
        _first_non_empty(
            cfg.get("eval_rebalance_frequency"),
            cfg.get("rebalance_frequency"),
            _get_nested(summary, "eval", "rebalance_frequency"),
            "W",
        )
    )
    backtest_frequency = str(
        _first_non_empty(
            cfg.get("backtest_rebalance_frequency"),
            cfg.get("rebalance_frequency"),
            _get_nested(summary, "backtest", "rebalance_frequency"),
            eval_frequency,
        )
    )
    eval_rebalance_dates = _resolve_rebalance_dates(
        _get_nested(summary, "eval", "rebalance_dates"),
        scored_data,
        eval_frequency,
        min_symbols_per_date,
    )
    backtest_rebalance_dates = _resolve_rebalance_dates(
        _get_nested(summary, "backtest", "rebalance_dates"),
        scored_data,
        backtest_frequency,
        min_symbols_per_date,
    )

    variants = cfg.get("variants")
    if not isinstance(variants, list) or not variants:
        raise SystemExit("construction_grid.variants must be a non-empty list.")
    for idx, variant in enumerate(variants, start=1):
        if not isinstance(variant, dict):
            raise SystemExit(f"construction_grid.variants[{idx}] must be a mapping.")

    return {
        "cfg": cfg,
        "summary": summary,
        "summary_path": summary_path,
        "scored_file": scored_path,
        "scored_data": scored_data,
        "target_col": target_col,
        "price_col": price_col,
        "eval_signal_col": eval_signal_col,
        "backtest_signal_col": backtest_signal_col,
        "eval_rebalance_dates": eval_rebalance_dates,
        "backtest_rebalance_dates": backtest_rebalance_dates,
        "variants": variants,
    }


def _init_row(
    *,
    variant: dict[str, Any],
    context: dict[str, Any],
    signal_col: str,
    score_postprocess_method: str,
    score_postprocess_columns: str,
) -> dict[str, Any]:
    cfg = context["cfg"]
    summary = context["summary"]
    top_k = int(_first_non_empty(variant.get("top_k"), cfg.get("top_k"), _get_nested(summary, "backtest", "top_k"), 10))
    long_only = _coerce_bool(
        _first_non_empty(variant.get("long_only"), cfg.get("long_only"), _get_nested(summary, "backtest", "long_only")),
        default=True,
    )
    short_k_raw = _first_non_empty(variant.get("short_k"), cfg.get("short_k"), _get_nested(summary, "backtest", "short_k"))
    short_k = int(short_k_raw) if short_k_raw is not None else None
    cost_bps = float(
        _first_non_empty(
            variant.get("cost_bps"),
            variant.get("transaction_cost_bps"),
            cfg.get("cost_bps"),
            cfg.get("transaction_cost_bps"),
            _get_nested(summary, "backtest", "transaction_cost_bps"),
            0.0,
        )
    )
    benchmark_name = _first_non_empty(variant.get("benchmark_name"), cfg.get("benchmark_name"))
    benchmark_returns_file = _first_non_empty(
        variant.get("benchmark_returns_file"),
        cfg.get("benchmark_returns_file"),
    )
    return {
        "variant": str(variant.get("name") or f"k{top_k}_bps{cost_bps:g}"),
        "scored_file": str(context["scored_file"]),
        "summary_path": str(context["summary_path"]) if context["summary_path"] else None,
        "target_col": context["target_col"],
        "price_col": context["price_col"],
        "eval_signal_col": signal_col,
        "backtest_signal_col": signal_col,
        "top_k": top_k,
        "short_k": short_k,
        "long_only": long_only,
        "cost_bps": cost_bps,
        "buffer_exit": int(_first_non_empty(variant.get("buffer_exit"), cfg.get("buffer_exit"), 0)),
        "buffer_entry": int(_first_non_empty(variant.get("buffer_entry"), cfg.get("buffer_entry"), 0)),
        "weighting": str(_first_non_empty(variant.get("weighting"), cfg.get("weighting"), "equal")).lower(),
        "score_postprocess_method": score_postprocess_method,
        "score_postprocess_columns": score_postprocess_columns,
        "benchmark_name": str(benchmark_name) if benchmark_name is not None else None,
        "benchmark_returns_file": (
            str(benchmark_returns_file) if benchmark_returns_file is not None else None
        ),
        "exposure_available": False,
        "status": "ok",
        "error": None,
    }


def _evaluate_variant(context: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    cfg = context["cfg"]
    data, signal_col, method, columns = _prepare_signal_column(
        context["scored_data"],
        context["backtest_signal_col"],
        variant,
    )
    row = _init_row(
        variant=variant,
        context=context,
        signal_col=signal_col,
        score_postprocess_method=method,
        score_postprocess_columns=columns,
    )
    if row["top_k"] <= 0:
        row["status"] = "failed"
        row["error"] = "top_k must be positive."
        return row
    if row["short_k"] is not None and int(row["short_k"]) < 0:
        row["status"] = "failed"
        row["error"] = "short_k must be >= 0."
        return row
    if row["weighting"] not in {"equal", "signal"}:
        row["status"] = "failed"
        row["error"] = "weighting must be one of: equal, signal."
        return row

    try:
        target_col = context["target_col"]
        price_col = context["price_col"]
        eval_slice = data[data["trade_date"].isin(context["eval_rebalance_dates"])].copy()
        ic_stats = summarize_ic(daily_ic_series(eval_slice, target_col, signal_col))
        row["eval_ic_mean"] = ic_stats.get("mean")
        row["eval_ic_ir"] = ic_stats.get("ir")

        n_quantiles = int(_first_non_empty(variant.get("n_quantiles"), cfg.get("n_quantiles"), 5))
        quantile_ts = quantile_returns(eval_slice, signal_col, target_col, n_quantiles)
        quantile_mean = quantile_ts.mean() if not quantile_ts.empty else pd.Series(dtype=float)
        row["eval_long_short"] = (
            float(quantile_mean.iloc[-1] - quantile_mean.iloc[0])
            if not quantile_mean.empty
            else None
        )

        if context["eval_rebalance_dates"]:
            turnover = estimate_turnover(
                eval_slice,
                signal_col,
                int(row["top_k"]),
                context["eval_rebalance_dates"],
                buffer_exit=int(row["buffer_exit"]),
                buffer_entry=int(row["buffer_entry"]),
            )
            row["eval_turnover_mean"] = float(turnover.mean()) if not turnover.empty else None

        summary = context["summary"]
        backtest_cfg = cfg.get("backtest") if isinstance(cfg.get("backtest"), dict) else {}
        execution_cfg = _first_non_empty(variant.get("execution"), cfg.get("execution"))
        exit_price_policy = str(
            _first_non_empty(
                variant.get("exit_price_policy"),
                cfg.get("exit_price_policy"),
                _get_nested(summary, "backtest", "exit_price_policy"),
                "strict",
            )
        ).lower()
        exit_fallback_policy = str(
            _first_non_empty(
                variant.get("exit_fallback_policy"),
                cfg.get("exit_fallback_policy"),
                _get_nested(summary, "backtest", "exit_fallback_policy"),
                "ffill",
            )
        ).lower()
        execution_model = build_execution_model(
            execution_cfg,
            default_cost_bps=float(row["cost_bps"]),
            default_exit_price_policy=exit_price_policy,
            default_exit_fallback_policy=exit_fallback_policy,
            default_price_col=price_col,
        )
        label_horizon = _first_non_empty(
            variant.get("exit_horizon_days"),
            cfg.get("exit_horizon_days"),
            _get_nested(summary, "backtest", "exit_horizon_days"),
            _get_nested(summary, "label", "horizon_days"),
        )
        if label_horizon is not None:
            label_horizon = int(label_horizon)
        tradable_col = _first_non_empty(
            variant.get("tradable_col"),
            cfg.get("tradable_col"),
            _get_nested(summary, "backtest", "tradable_col"),
            "is_tradable",
        )
        tradable_col = str(tradable_col) if tradable_col is not None else None
        if tradable_col and tradable_col not in data.columns:
            tradable_col = None
        group_col = _first_non_empty(
            variant.get("group_col"),
            cfg.get("group_col"),
            _get_nested(summary, "backtest", "group_col"),
        )
        group_col = str(group_col) if group_col is not None else None
        if group_col and group_col not in data.columns:
            group_col = None
        row["exposure_available"] = bool(group_col)
        max_names_per_group = _first_non_empty(
            variant.get("max_names_per_group"),
            cfg.get("max_names_per_group"),
            _get_nested(summary, "backtest", "max_names_per_group"),
        )
        if max_names_per_group is not None:
            max_names_per_group = int(max_names_per_group)

        trading_days = int(
            _first_non_empty(
                variant.get("trading_days_per_year"),
                cfg.get("trading_days_per_year"),
                _get_nested(summary, "backtest", "trading_days_per_year"),
                252,
            )
        )
        bt_result = backtest_topk(
            data,
            pred_col=signal_col,
            price_col=price_col,
            rebalance_dates=context["backtest_rebalance_dates"],
            top_k=int(row["top_k"]),
            shift_days=int(_first_non_empty(variant.get("shift_days"), cfg.get("shift_days"), _get_nested(summary, "label", "shift_days"), 0)),
            cost_bps=float(row["cost_bps"]),
            trading_days_per_year=trading_days,
            exit_mode=str(_first_non_empty(variant.get("exit_mode"), cfg.get("exit_mode"), "rebalance")).lower(),
            exit_horizon_days=label_horizon,
            long_only=bool(row["long_only"]),
            short_k=row["short_k"],
            weighting=str(row["weighting"]),
            buffer_exit=int(row["buffer_exit"]),
            buffer_entry=int(row["buffer_entry"]),
            tradable_col=tradable_col,
            group_col=group_col,
            max_names_per_group=max_names_per_group,
            exit_price_policy=exit_price_policy,
            exit_fallback_policy=exit_fallback_policy,
            execution=execution_model,
            pricing_data=data,
        )
        if bt_result is None:
            row["status"] = "no_backtest"
            return row
        bt_stats, net_series, gross_series, _, _ = bt_result
        row["backtest_periods"] = bt_stats.get("periods")
        row["backtest_total_return"] = bt_stats.get("total_return")
        row["backtest_gross_total_return"] = float((1.0 + gross_series).prod() - 1.0)
        row["backtest_ann_return"] = bt_stats.get("ann_return")
        row["backtest_ann_vol"] = bt_stats.get("ann_vol")
        row["backtest_sharpe"] = bt_stats.get("sharpe")
        row["backtest_max_drawdown"] = bt_stats.get("max_drawdown")
        row["backtest_avg_turnover"] = bt_stats.get("avg_turnover")
        row["backtest_avg_cost_drag"] = bt_stats.get("avg_cost_drag")

        benchmark_path = _resolve_path(
            row.get("benchmark_returns_file") or None,
            base_dir=Path(str(context["scored_file"])).parent,
        )
        if benchmark_path:
            benchmark = _read_returns_file(benchmark_path)
            active_stats, _ = summarize_active_returns(
                net_series,
                benchmark,
                periods_per_year=_periods_per_year(bt_stats, trading_days),
            )
            row["active_total_return"] = active_stats.get("active_total_return")
            row["information_ratio"] = active_stats.get("information_ratio")
            row["tracking_error"] = active_stats.get("tracking_error")
            row["beta"] = active_stats.get("beta")
            row["alpha"] = active_stats.get("alpha")
            row["corr"] = active_stats.get("corr")
    except Exception as exc:
        row["status"] = "failed"
        row["error"] = str(exc)
    return row


def build_construction_grid(config: dict[str, Any], *, config_dir: Path) -> list[dict[str, Any]]:
    context = _build_base_context(config, config_dir)
    rows = [_evaluate_variant(context, variant) for variant in context["variants"]]
    return rows


def write_reports(
    rows: list[dict[str, Any]],
    *,
    output_csv: Path | None,
    output_json: Path | None,
) -> None:
    if output_csv:
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        with output_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)
    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(rows, ensure_ascii=True, indent=2, default=str), encoding="utf-8")


def add_construction_grid_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--config", required=True, help="Construction grid YAML config.")
    parser.add_argument("--output", default=None, help="Output CSV path.")
    parser.add_argument("--output-json", default=None, help="Output JSON path.")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Logging level",
    )
    return parser


def run(args: argparse.Namespace) -> list[dict[str, Any]]:
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(levelname)s: %(message)s",
    )
    config_path = _resolve_path(args.config)
    assert config_path is not None
    config = _load_yaml(config_path)
    rows = build_construction_grid(config, config_dir=config_path.parent)
    cfg = config.get("construction_grid", config)
    output_csv = _resolve_path(args.output or cfg.get("output_csv") or cfg.get("output"), base_dir=config_path.parent)
    output_json = _resolve_path(args.output_json or cfg.get("output_json"), base_dir=config_path.parent)
    if output_csv is None and output_json is None:
        print(json.dumps(rows, ensure_ascii=True, indent=2, default=str))
    else:
        write_reports(rows, output_csv=output_csv, output_json=output_json)
        if output_csv:
            logging.info("Construction grid CSV written to %s", output_csv)
        if output_json:
            logging.info("Construction grid JSON written to %s", output_json)
    return rows
