from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from market_data_platform.data_providers import normalize_market
from market_data_platform.symbols import (
    PROVIDER_SYMBOL_PRIORITY,
    canonicalize_symbol_columns,
    ensure_symbol_columns,
    normalize_symbol_for_market,
    normalize_symbol_standard_name,
)


def _prepare_panel_join_frame(
    frame: pd.DataFrame,
    column_map: dict[str, Any] | None = None,
    *,
    item_label: str,
    symbol_priority: tuple[str, ...] | list[str] = PROVIDER_SYMBOL_PRIORITY,
) -> pd.DataFrame:
    join_df = frame.copy()
    column_map = column_map or {}
    if column_map:
        rename_map = {
            source: normalize_symbol_standard_name(standard)
            for standard, source in column_map.items()
            if (
                source in join_df.columns
                and normalize_symbol_standard_name(standard) != source
                and normalize_symbol_standard_name(standard) not in join_df.columns
            )
        }
        if rename_map:
            join_df = join_df.rename(columns=rename_map)
    if "trade_date" not in join_df.columns and "date" in join_df.columns:
        join_df = join_df.rename(columns={"date": "trade_date"})
    join_df = canonicalize_symbol_columns(
        join_df,
        context=f"{item_label} data",
        priority=symbol_priority,
    )
    if "trade_date" not in join_df.columns or "symbol" not in join_df.columns:
        sys.exit(f"{item_label} data must include trade_date and symbol columns.")
    join_df["trade_date"] = pd.to_datetime(join_df["trade_date"], errors="coerce")
    join_df = join_df[join_df["trade_date"].notna()].copy()
    join_df["trade_date"] = join_df["trade_date"].dt.normalize()
    if "valuation_trade_date" in join_df.columns:
        valuation_trade_date = pd.to_datetime(
            join_df["valuation_trade_date"], errors="coerce"
        )
        join_df["valuation_trade_date"] = valuation_trade_date.dt.normalize()
    for date_col in ("start_date", "cancel_date"):
        if date_col in join_df.columns:
            parsed = pd.to_datetime(join_df[date_col], errors="coerce")
            join_df[date_col] = parsed.dt.normalize()
    join_df["symbol"] = join_df["symbol"].astype(str).str.strip()
    join_df = join_df.drop_duplicates(subset=["trade_date", "symbol"]).copy()
    return join_df.sort_values(["symbol", "trade_date"]).reset_index(drop=True)


def _select_panel_join_columns(
    frame: pd.DataFrame,
    *,
    keep_columns: list[str] | None,
    item_label: str,
) -> pd.DataFrame:
    if not keep_columns:
        return frame
    missing = [column for column in keep_columns if column not in frame.columns]
    if missing:
        sys.exit(f"{item_label} columns not found in join data: {missing}")
    selected = ["trade_date", "symbol"] + keep_columns
    return frame.loc[:, list(dict.fromkeys(selected))].copy()


def _atomic_write(path: Path, write_fn) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        write_fn(tmp)
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()


def save_series(series: pd.Series, path: Path, value_name: Optional[str] = None) -> None:
    if series is None or series.empty:
        return
    name = value_name or series.name or "value"
    out = series.rename(name).reset_index()

    def _write(tmp_path: Path) -> None:
        out.to_csv(tmp_path, index=False)

    _atomic_write(path, _write)


def save_frame(frame: pd.DataFrame, path: Path) -> None:
    if frame is None or frame.empty:
        return

    def _write(tmp_path: Path) -> None:
        frame.to_csv(tmp_path, index=False)

    _atomic_write(path, _write)


def save_parquet(frame: pd.DataFrame, path: Path) -> None:
    if frame is None or frame.empty:
        return

    def _write(tmp_path: Path) -> None:
        frame.to_parquet(tmp_path)

    _atomic_write(path, _write)


def _ensure_symbol_alias(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return frame
    if not any(col in frame.columns for col in ("symbol", "ts_code", "stock_ticker", "order_book_id")):
        return frame
    return canonicalize_symbol_columns(frame, context="Pipeline output")


def save_json(payload: dict, path: Path) -> None:
    def _write(tmp_path: Path) -> None:
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, indent=2, default=str)

    _atomic_write(path, _write)


def _coerce_yyyymmdd(values: pd.Series) -> pd.Series:
    text = values.astype(str).str.strip()
    compact = text.str.replace("-", "", regex=False)
    parsed = pd.to_datetime(compact, format="%Y%m%d", errors="coerce")
    formatted = parsed.dt.strftime("%Y%m%d")
    return formatted.where(parsed.notna(), text)


def _annotate_positions_window(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return frame
    out = frame.copy()
    if "rebalance_date" in out.columns:
        rebalance_compact = _coerce_yyyymmdd(out["rebalance_date"])
        out["rebalance_date"] = rebalance_compact
        out["signal_asof"] = rebalance_compact
    if "entry_date" in out.columns:
        entry_compact = _coerce_yyyymmdd(out["entry_date"])
        out["entry_date"] = entry_compact
        entry_dt = pd.to_datetime(entry_compact, format="%Y%m%d", errors="coerce")
        unique_entries = sorted(entry_dt.dropna().unique())
        next_map = {
            unique_entries[idx]: unique_entries[idx + 1]
            for idx in range(len(unique_entries) - 1)
        }
        next_entry = pd.to_datetime(entry_dt.map(next_map), errors="coerce")
        next_entry_str = next_entry.dt.strftime("%Y%m%d").where(next_entry.notna(), "")
        out["next_entry_date"] = next_entry_str
        holding_window = out["entry_date"].astype(str) + " -> " + out["next_entry_date"]
        holding_window = holding_window.where(out["next_entry_date"].astype(str) != "", out["entry_date"])
        out["holding_window"] = holding_window
    return _ensure_symbol_alias(out)


def _build_rebalance_diff(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty or "entry_date" not in frame.columns:
        return pd.DataFrame()
    frame = canonicalize_symbol_columns(frame, context="Rebalance diff")
    entry_compact = _coerce_yyyymmdd(frame["entry_date"])
    entry_dt = pd.to_datetime(entry_compact, format="%Y%m%d", errors="coerce")
    unique_entries = sorted(entry_dt.dropna().unique())
    if len(unique_entries) < 2:
        return pd.DataFrame()
    latest_entry = unique_entries[-1]
    prev_entry = unique_entries[-2]
    current = frame[entry_dt == latest_entry].copy()
    previous = frame[entry_dt == prev_entry].copy()

    for df in (current, previous):
        if "side" not in df.columns:
            df["side"] = "long"
        if "weight" not in df.columns:
            df["weight"] = np.nan
        if "signal" not in df.columns:
            df["signal"] = np.nan
        if "rank" not in df.columns:
            df["rank"] = np.nan

    current = current[["symbol", "side", "weight", "signal", "rank"]].rename(
        columns={
            "weight": "weight",
            "signal": "signal",
            "rank": "rank",
        }
    )
    previous = previous[["symbol", "side", "weight", "signal", "rank"]].rename(
        columns={
            "weight": "weight_prev",
            "signal": "signal_prev",
            "rank": "rank_prev",
        }
    )

    merged = current.merge(
        previous, on=["symbol", "side"], how="outer", indicator=True
    )
    merged["weight"] = merged["weight"].fillna(0.0)
    merged["weight_prev"] = merged["weight_prev"].fillna(0.0)
    merged["weight_delta"] = merged["weight"] - merged["weight_prev"]
    merged["change"] = merged["_merge"].astype(str).map(
        {"left_only": "added", "right_only": "removed", "both": "changed"}
    )
    merged.loc[
        (merged["_merge"] == "both") & (merged["weight_delta"].abs() < 1e-12),
        "change",
    ] = "unchanged"
    merged = merged[merged["change"] != "unchanged"].copy()
    merged["entry_date"] = latest_entry.strftime("%Y%m%d")
    merged["entry_date_prev"] = prev_entry.strftime("%Y%m%d")
    merged.drop(columns=["_merge"], inplace=True)
    merged.sort_values(["change", "side", "symbol"], inplace=True)
    return _ensure_symbol_alias(merged)


def normalize_symbol_list(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value.strip()]
    return [str(item).strip() for item in value if str(item).strip()]


def load_symbols_file(path: Path) -> list[str]:
    if not path.exists():
        sys.exit(f"Symbols file not found: {path}")
    symbols = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            symbols.append(text)
    return symbols


def coerce_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return False
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "t"}
    return False


def normalize_universe_symbol(symbol: str, market: str) -> str:
    return normalize_symbol_for_market(symbol, market=normalize_market(market))


def normalize_date_like_series(series: pd.Series) -> pd.Series:
    if series.empty:
        return pd.to_datetime(series, errors="coerce")
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(series, errors="coerce").dt.normalize()

    text = series.astype(str).str.strip().str.replace(r"\.0+$", "", regex=True)
    digits_mask = text.str.fullmatch(r"\d{8}")
    parsed = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")

    if digits_mask.any():
        parsed.loc[digits_mask] = pd.to_datetime(
            text.loc[digits_mask],
            format="%Y%m%d",
            errors="coerce",
        )
    if (~digits_mask).any():
        parsed.loc[~digits_mask] = pd.to_datetime(text.loc[~digits_mask], errors="coerce")

    return parsed.dt.normalize()


def load_universe_by_date(path: Path, market: str) -> pd.DataFrame:
    if not path.exists():
        sys.exit(f"Universe-by-date file not found: {path}")
    df = pd.read_csv(path)
    if df.empty:
        sys.exit(f"Universe-by-date file is empty: {path}")
    columns = {col.lower(): col for col in df.columns}
    date_col = columns.get("trade_date") or columns.get("date") or columns.get("rebalance_date")
    symbol_col = (
        columns.get("symbol")
        or columns.get("ts_code")
        or columns.get("stock_ticker")
        or columns.get("order_book_id")
    )
    if not date_col or not symbol_col:
        sys.exit("Universe-by-date file must include date + symbol columns.")

    df = df.rename(columns={date_col: "trade_date", symbol_col: "symbol"})
    selected_col = (
        columns.get("selected")
        or columns.get("selected_bool")
        or columns.get("selected_flag")
        or columns.get("is_selected")
    )
    if selected_col and selected_col in df.columns:
        df = df[df[selected_col].map(coerce_bool)].copy()

    df["trade_date"] = normalize_date_like_series(df["trade_date"])
    df = df[df["trade_date"].notna()].copy()
    df["trade_date"] = df["trade_date"].dt.normalize()
    df = ensure_symbol_columns(df, context="Universe-by-date file")
    df["symbol"] = df["symbol"].astype(str).str.strip()
    df["symbol"] = df["symbol"].apply(lambda s: normalize_universe_symbol(s, market))
    df = df[df["symbol"] != ""].copy()
    df = df.drop_duplicates(subset=["trade_date", "symbol"])
    return df[["trade_date", "symbol"]].copy()


def apply_universe_by_date(data: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
    if universe.empty:
        return data
    rebalance_dates = np.array(sorted(universe["trade_date"].unique()))
    if rebalance_dates.size == 0:
        return data
    trade_dates = np.array(sorted(data["trade_date"].unique()))
    if trade_dates.size == 0:
        return data
    idx = np.searchsorted(rebalance_dates, trade_dates, side="right") - 1
    valid_mask = idx >= 0
    if not np.any(valid_mask):
        return data.iloc[0:0].copy()
    date_map = pd.DataFrame(
        {
            "trade_date": trade_dates[valid_mask],
            "rebalance_date": rebalance_dates[idx[valid_mask]],
        }
    )
    universe_map = universe.rename(columns={"trade_date": "rebalance_date"})
    data = data.merge(date_map, on="trade_date", how="inner")
    data = data.merge(
        universe_map[["rebalance_date", "symbol"]],
        on=["rebalance_date", "symbol"],
        how="inner",
    )
    return data.drop(columns=["rebalance_date"])


def parse_feature_windows(features: list[str], prefix: str, suffix: str = "") -> list[int]:
    windows = set()
    for feat in features:
        if not feat.startswith(prefix):
            continue
        if suffix and not feat.endswith(suffix):
            continue
        end = len(feat) - len(suffix) if suffix else len(feat)
        value = feat[len(prefix):end]
        if value.isdigit():
            windows.add(int(value))
    return sorted(windows)


def _parse_window_config(raw: Any) -> set[int]:
    windows: set[int] = set()
    if isinstance(raw, (list, tuple, set)):
        values = raw
    elif raw is None:
        values = []
    else:
        values = [raw]
    for item in values:
        try:
            win = int(item)
        except (TypeError, ValueError):
            continue
        if win > 0:
            windows.add(win)
    return windows


def _summarize_walk_forward_feature_stability(
    importance_frame: pd.DataFrame,
    top_k: int,
) -> pd.DataFrame:
    if importance_frame is None or importance_frame.empty:
        return pd.DataFrame()

    data = importance_frame.copy()
    data["importance"] = pd.to_numeric(data["importance"], errors="coerce")
    data = data[np.isfinite(data["importance"])].copy()
    if data.empty:
        return pd.DataFrame()

    windows_total = int(data["window"].nunique())
    features_total = int(data["feature"].nunique())
    top_k_effective = max(1, min(int(top_k), features_total))
    data["rank"] = data.groupby("window")["importance"].rank(method="average", ascending=False)
    data["is_top_k"] = data["rank"] <= top_k_effective
    data["is_nonzero"] = data["importance"] > 0

    summary = (
        data.groupby("feature", as_index=False)
        .agg(
            windows_seen=("window", "nunique"),
            importance_mean=("importance", "mean"),
            importance_std=("importance", "std"),
            rank_mean=("rank", "mean"),
            rank_std=("rank", "std"),
            top_k_hits=("is_top_k", "sum"),
            nonzero_hits=("is_nonzero", "sum"),
        )
        .sort_values(["top_k_hits", "importance_mean"], ascending=[False, False])
        .reset_index(drop=True)
    )
    summary["windows_total"] = windows_total
    summary["windows_missing"] = windows_total - summary["windows_seen"]
    summary["top_k"] = top_k_effective
    summary["top_k_hit_rate"] = summary["top_k_hits"] / windows_total
    summary["nonzero_hit_rate"] = summary["nonzero_hits"] / windows_total
    summary["importance_std"] = summary["importance_std"].fillna(0.0)
    summary["rank_std"] = summary["rank_std"].fillna(0.0)
    return summary
