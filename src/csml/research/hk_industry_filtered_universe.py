#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from csml.repo_paths import find_repo_root, resolve_repo_path as resolve_repo_relative_path


REPO_ROOT = find_repo_root(__file__)
DEFAULT_FINANCIAL_BUCKETS = ("银行", "非银行金融", "综合金融")


def resolve_repo_path(path_text: str | Path) -> Path:
    return resolve_repo_relative_path(path_text, repo_root=REPO_ROOT)


def _parse_trade_dates(series: pd.Series) -> pd.Series:
    raw = series.astype(str).str.strip()
    if raw.replace({"": pd.NA}).dropna().str.fullmatch(r"\d{8}").all():
        return pd.to_datetime(raw, format="%Y%m%d", errors="coerce")
    return pd.to_datetime(series, errors="coerce")


def _load_by_date_frame(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {"trade_date", "symbol"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise SystemExit(f"{path} is missing required columns: {', '.join(missing)}")
    work = frame.copy()
    work["trade_date"] = _parse_trade_dates(work["trade_date"])
    work["symbol"] = work["symbol"].astype(str).str.strip()
    work = work.dropna(subset=["trade_date"])
    work = work.loc[work["symbol"] != ""].copy()
    return work


def _load_latest_industry_labels(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path, columns=["trade_date", "symbol", "first_industry_name"])
    work = frame.copy()
    work["trade_date"] = pd.to_datetime(work["trade_date"], errors="coerce")
    work["symbol"] = work["symbol"].astype(str).str.strip()
    work["first_industry_name"] = work["first_industry_name"].astype("string").str.strip()
    work = work.dropna(subset=["trade_date", "symbol", "first_industry_name"])
    work = work.loc[work["symbol"] != ""].copy()
    work = work.sort_values(["symbol", "trade_date"])
    return work.drop_duplicates(subset=["symbol"], keep="last").reset_index(drop=True)


def _build_filtered_universe(
    *,
    base: pd.DataFrame,
    labels: pd.DataFrame,
    target_buckets: set[str],
    selection_mode: str,
    missing_policy: str,
) -> tuple[pd.DataFrame, dict[str, object]]:
    merged = base.merge(labels[["symbol", "first_industry_name"]], on="symbol", how="left")
    industry = merged["first_industry_name"]
    target_mask = industry.isin(target_buckets)
    classified_mask = industry.notna()

    if selection_mode == "exclude":
        keep_mask = ~target_mask
        if missing_policy == "drop":
            keep_mask &= classified_mask
    elif selection_mode == "only":
        keep_mask = target_mask
    else:
        raise SystemExit(f"Unsupported selection mode: {selection_mode}")

    filtered = merged.loc[keep_mask, base.columns].copy()
    filtered["trade_date"] = pd.to_datetime(filtered["trade_date"]).dt.strftime("%Y%m%d")

    summary = {
        "input_rows": int(len(base)),
        "output_rows": int(len(filtered)),
        "input_symbols": int(base["symbol"].nunique()),
        "output_symbols": int(filtered["symbol"].nunique()),
        "input_dates": int(base["trade_date"].nunique()),
        "output_dates": int(pd.to_datetime(filtered["trade_date"], format="%Y%m%d").nunique()),
        "selection_mode": selection_mode,
        "missing_policy": missing_policy,
        "target_first_industries": sorted(target_buckets),
        "classified_symbols": int(labels["symbol"].nunique()),
        "selected_target_symbols": int(
            labels.loc[labels["first_industry_name"].isin(target_buckets), "symbol"].nunique()
        ),
        "selected_target_rows_in_input": int(target_mask.sum()),
        "unclassified_rows_in_input": int((~classified_mask).sum()),
    }
    return filtered, summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build an industry-filtered HK universe-by-date CSV by assigning each symbol "
            "its latest non-null first-industry label and then excluding or keeping "
            "selected buckets."
        )
    )
    parser.add_argument("--by-date-file", required=True, help="Input universe-by-date CSV.")
    parser.add_argument(
        "--industry-labels",
        required=True,
        help="Monthly industry label parquet with symbol/trade_date/first_industry_name.",
    )
    parser.add_argument("--out", required=True, help="Output filtered universe-by-date CSV.")
    parser.add_argument(
        "--summary-out",
        default=None,
        help="Optional JSON summary path. Defaults to <out>.summary.json when omitted.",
    )
    parser.add_argument(
        "--selection-mode",
        choices=("exclude", "only"),
        default="exclude",
        help="Whether to exclude the listed buckets or keep only them.",
    )
    parser.add_argument(
        "--missing-policy",
        choices=("keep", "drop"),
        default="keep",
        help=(
            "How to handle symbols that cannot be classified from latest non-null labels. "
            "Ignored when --selection-mode=only."
        ),
    )
    parser.add_argument(
        "--first-industry",
        action="append",
        default=list(DEFAULT_FINANCIAL_BUCKETS),
        help=(
            "Repeat to add target first-industry names. Defaults to 银行 / 非银行金融 / 综合金融. "
            "Passing this flag appends to the default list."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    by_date_path = resolve_repo_path(args.by_date_file)
    industry_path = resolve_repo_path(args.industry_labels)
    out_path = resolve_repo_path(args.out)
    summary_path = (
        resolve_repo_path(args.summary_out)
        if args.summary_out
        else out_path.with_suffix(f"{out_path.suffix}.summary.json")
    )

    base = _load_by_date_frame(by_date_path)
    labels = _load_latest_industry_labels(industry_path)
    target_buckets = {str(item).strip() for item in args.first_industry if str(item).strip()}
    if not target_buckets:
        raise SystemExit("No target first-industry buckets resolved.")

    filtered, summary = _build_filtered_universe(
        base=base,
        labels=labels,
        target_buckets=target_buckets,
        selection_mode=args.selection_mode,
        missing_policy=args.missing_policy,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    filtered.to_csv(out_path, index=False)

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "by_date_file": str(by_date_path),
                "industry_labels": str(industry_path),
                "out": str(out_path),
                "summary": summary,
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )

    print(
        f"Wrote {out_path} with {summary['output_rows']} rows, "
        f"{summary['output_symbols']} symbols, {summary['output_dates']} dates."
    )
    print(
        f"Selection mode={summary['selection_mode']}, missing_policy={summary['missing_policy']}, "
        f"target buckets={', '.join(summary['target_first_industries'])}."
    )
    print(f"Summary written to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
