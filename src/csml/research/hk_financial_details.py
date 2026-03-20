from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_MAPPING_FILE = MODULE_DIR / "hk_financial_details_subject_mapping.csv"
REQUIRED_COLUMNS = {
    "amount",
    "currency",
    "field",
    "fiscal_year",
    "if_adjusted",
    "info_date",
    "order_book_id",
    "quarter",
    "relationship",
    "standard",
    "subject",
    "ts_code",
}
DEDUP_KEYS = [
    "ts_code",
    "order_book_id",
    "field",
    "quarter",
    "fiscal_year",
    "relationship",
    "currency",
    "standard",
    "subject",
]
SUMMARY_COLUMNS = [
    "probe_coverage.csv",
    "subject_frequency.csv",
    "subject_examples.csv",
    "subject_mapping_draft.csv",
    "duplicate_disclosure_summary.csv",
    "normalized_long.csv",
    "normalized_long.parquet",
    "normalized_subject_frequency.csv",
    "normalization_stats.csv",
    "summary.md",
    "analysis_manifest.yml",
]


@dataclass(frozen=True)
class SubjectRule:
    normalized_subject: str
    keep_separate: str
    rule_type: str
    notes: str
    mapping_source: str = "builtin"


@dataclass(frozen=True)
class AnalysisResult:
    probe_dir: Path
    out_dir: Path
    dedup_mode: str
    fields: tuple[str, ...]
    mapping_files: tuple[str, ...]
    manifest: dict[str, Any]
    raw_frame: pd.DataFrame
    deduped_frame: pd.DataFrame
    audit: pd.DataFrame
    probe_coverage: pd.DataFrame
    subject_frequency: pd.DataFrame
    subject_examples: pd.DataFrame
    subject_mapping_draft: pd.DataFrame
    duplicate_disclosure_summary: pd.DataFrame
    normalized_long: pd.DataFrame
    normalized_subject_frequency: pd.DataFrame
    normalization_stats: pd.DataFrame
    new_subjects_vs_compare: pd.DataFrame | None
    summary_text: str
    compare_probe_dir: Path | None = None


def _resolve_path(path_text: str | Path) -> Path:
    path = Path(path_text).expanduser()
    return path.resolve() if path.is_absolute() else Path.cwd().joinpath(path).resolve()


def _normalize_text(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip()


def _join_unique(values: pd.Series) -> str:
    cleaned = sorted({str(value).strip() for value in values.dropna() if str(value).strip()})
    return "|".join(cleaned)


def _load_manifest(probe_dir: Path) -> dict[str, Any]:
    manifest_path = probe_dir / "manifest.yml"
    if not manifest_path.exists():
        raise SystemExit(f"Probe manifest not found: {manifest_path}")
    with manifest_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise SystemExit(f"Probe manifest is not a mapping: {manifest_path}")
    return payload


def _load_probe_frame(probe_dir: Path, fields: tuple[str, ...]) -> pd.DataFrame:
    data_dir = probe_dir / "data"
    parquet_files = sorted(data_dir.glob("*.parquet"))
    if not parquet_files:
        raise SystemExit(f"No parquet files found under {data_dir}")
    frames: list[pd.DataFrame] = []
    for path in parquet_files:
        frame = pd.read_parquet(path)
        if frame.empty:
            continue
        frames.append(frame)
    if not frames:
        raise SystemExit(f"No non-empty parquet files found under {data_dir}")
    frame = pd.concat(frames, ignore_index=True)
    missing = sorted(REQUIRED_COLUMNS.difference(frame.columns))
    if missing:
        raise SystemExit(f"Probe data is missing required columns: {missing}")
    frame = frame.copy()
    frame["ts_code"] = _normalize_text(frame["ts_code"]).str.upper()
    frame["order_book_id"] = _normalize_text(frame["order_book_id"]).str.upper()
    frame["field"] = _normalize_text(frame["field"])
    frame["quarter"] = _normalize_text(frame["quarter"]).str.lower()
    frame["fiscal_year"] = _normalize_text(frame["fiscal_year"])
    frame["currency"] = _normalize_text(frame["currency"])
    frame["subject"] = _normalize_text(frame["subject"])
    frame["standard"] = _normalize_text(frame["standard"])
    frame["info_date"] = pd.to_datetime(frame["info_date"], errors="coerce").dt.normalize()
    frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce")
    frame["relationship"] = pd.to_numeric(frame["relationship"], errors="coerce")
    frame["if_adjusted"] = pd.to_numeric(frame["if_adjusted"], errors="coerce").astype("Int64")
    if fields:
        frame = frame[frame["field"].isin(fields)].copy()
    frame = frame.dropna(subset=["ts_code", "field", "quarter", "subject", "standard"]).copy()
    frame = frame.sort_values(
        ["field", "standard", "subject", "ts_code", "quarter", "info_date"],
        kind="mergesort",
    ).reset_index(drop=True)
    return frame


def _load_audit(probe_dir: Path) -> pd.DataFrame:
    audit_path = probe_dir / "audit.csv"
    if not audit_path.exists():
        return pd.DataFrame(columns=["ts_code", "order_book_id", "status", "rows"])
    audit = pd.read_csv(audit_path)
    audit = audit.copy()
    for column in ("ts_code", "order_book_id", "status", "min_quarter", "max_quarter"):
        if column in audit.columns:
            audit[column] = _normalize_text(audit[column])
    if "ts_code" in audit.columns:
        audit["ts_code"] = audit["ts_code"].str.upper()
    if "order_book_id" in audit.columns:
        audit["order_book_id"] = audit["order_book_id"].str.upper()
    if "rows" in audit.columns:
        audit["rows"] = pd.to_numeric(audit["rows"], errors="coerce").fillna(0).astype(int)
    return audit


def _read_mapping_frame(mapping_path: Path) -> pd.DataFrame:
    if not mapping_path.exists():
        raise SystemExit(f"Mapping file not found: {mapping_path}")
    mapping = pd.read_csv(mapping_path)
    required = {
        "field",
        "standard",
        "raw_subject",
        "normalized_subject",
        "keep_separate",
        "rule_type",
        "notes",
    }
    missing = sorted(required.difference(mapping.columns))
    if missing:
        raise SystemExit(f"Mapping file is missing required columns: {missing} ({mapping_path})")
    mapping = mapping.copy()
    for column in required:
        mapping[column] = _normalize_text(mapping[column])
    return mapping


def _merge_mapping_rules(
    rules: dict[tuple[str, str, str], SubjectRule],
    mapping: pd.DataFrame,
    *,
    mapping_source: str,
) -> None:
    for row in mapping.itertuples(index=False):
        key = (str(row.field), str(row.standard), str(row.raw_subject))
        rules[key] = SubjectRule(
            normalized_subject=str(row.normalized_subject),
            keep_separate=str(row.keep_separate),
            rule_type=str(row.rule_type),
            notes=str(row.notes),
            mapping_source=mapping_source,
        )


def _load_mapping_rules(mapping_file: Path | None) -> tuple[dict[tuple[str, str, str], SubjectRule], tuple[str, ...]]:
    rules: dict[tuple[str, str, str], SubjectRule] = {}
    mapping_files: list[str] = []
    default_mapping = _read_mapping_frame(DEFAULT_MAPPING_FILE)
    _merge_mapping_rules(rules, default_mapping, mapping_source="repo_default")
    mapping_files.append(str(DEFAULT_MAPPING_FILE))
    if mapping_file is not None:
        override_mapping = _read_mapping_frame(mapping_file)
        _merge_mapping_rules(rules, override_mapping, mapping_source="override")
        mapping_files.append(str(mapping_file))
    return rules, tuple(mapping_files)


def apply_subject_rule(
    field: str,
    standard: str,
    subject: str,
    mapping_rules: dict[tuple[str, str, str], SubjectRule] | None = None,
) -> SubjectRule:
    key = (field, standard, subject)
    if mapping_rules and key in mapping_rules:
        return mapping_rules[key]
    return SubjectRule(
        normalized_subject=subject,
        keep_separate="yes",
        rule_type="unmapped_identity",
        notes="未命中规则，先保留原 subject。",
        mapping_source="default_fallback",
    )


def _build_mapping_draft(
    frame: pd.DataFrame,
    mapping_rules: dict[tuple[str, str, str], SubjectRule],
) -> pd.DataFrame:
    records: list[dict[str, str]] = []
    unique_rows = (
        frame[["field", "standard", "subject"]]
        .drop_duplicates()
        .sort_values(["field", "standard", "subject"], kind="mergesort")
    )
    for row in unique_rows.itertuples(index=False):
        rule = apply_subject_rule(str(row.field), str(row.standard), str(row.subject), mapping_rules)
        records.append(
            {
                "field": str(row.field),
                "standard": str(row.standard),
                "raw_subject": str(row.subject),
                "normalized_subject": rule.normalized_subject,
                "keep_separate": rule.keep_separate,
                "rule_type": rule.rule_type,
                "mapping_source": rule.mapping_source,
                "notes": rule.notes,
            }
        )
    return pd.DataFrame.from_records(records)


def _deduplicate_frame(frame: pd.DataFrame, dedup_mode: str) -> pd.DataFrame:
    if dedup_mode == "none":
        return frame.copy().reset_index(drop=True)
    work = frame.copy()
    work["_info_date_sort"] = pd.to_datetime(work["info_date"], errors="coerce")
    work["_if_adjusted_sort"] = pd.to_numeric(work["if_adjusted"], errors="coerce").fillna(-1)
    if dedup_mode == "latest_info_date":
        work = work.sort_values(
            DEDUP_KEYS + ["_info_date_sort"],
            ascending=[True] * len(DEDUP_KEYS) + [False],
            kind="mergesort",
        )
    elif dedup_mode == "latest_adjusted_then_info_date":
        work = work.sort_values(
            DEDUP_KEYS + ["_if_adjusted_sort", "_info_date_sort"],
            ascending=[True] * len(DEDUP_KEYS) + [False, False],
            kind="mergesort",
        )
    else:
        raise SystemExit(f"Unsupported dedup mode: {dedup_mode}")
    deduped = work.drop_duplicates(subset=DEDUP_KEYS, keep="first").drop(
        columns=["_info_date_sort", "_if_adjusted_sort"]
    )
    return deduped.sort_values(
        ["field", "standard", "subject", "ts_code", "quarter", "info_date"],
        kind="mergesort",
    ).reset_index(drop=True)


def _build_duplicate_disclosure_summary(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(
            columns=[
                *DEDUP_KEYS,
                "disclosure_count",
                "unique_info_dates",
                "unique_amounts",
                "min_info_date",
                "max_info_date",
                "if_adjusted_values",
            ]
        )
    grouped = (
        frame.groupby(DEDUP_KEYS, dropna=False)
        .agg(
            disclosure_count=("info_date", "size"),
            unique_info_dates=("info_date", "nunique"),
            unique_amounts=("amount", "nunique"),
            min_info_date=("info_date", "min"),
            max_info_date=("info_date", "max"),
            if_adjusted_values=("if_adjusted", _join_unique),
        )
        .reset_index()
    )
    grouped = grouped[grouped["disclosure_count"] > 1].copy()
    if grouped.empty:
        return grouped
    grouped = grouped.sort_values(
        ["disclosure_count", "field", "ts_code", "quarter", "subject"],
        ascending=[False, True, True, True, True],
        kind="mergesort",
    ).reset_index(drop=True)
    return grouped


def _build_subject_frequency(frame: pd.DataFrame) -> pd.DataFrame:
    return (
        frame.groupby(["field", "standard", "subject"], dropna=False)
        .agg(rows=("ts_code", "size"), symbols=("ts_code", "nunique"))
        .reset_index()
        .sort_values(["field", "rows", "symbols", "standard", "subject"], ascending=[True, False, False, True, True])
        .reset_index(drop=True)
    )


def _build_subject_examples(frame: pd.DataFrame) -> pd.DataFrame:
    columns = ["ts_code", "field", "standard", "subject", "quarter", "info_date", "amount", "currency"]
    return frame[columns].sort_values(
        ["field", "standard", "subject", "ts_code", "quarter", "info_date"],
        kind="mergesort",
    ).reset_index(drop=True)


def _apply_mapping(
    frame: pd.DataFrame,
    mapping_draft: pd.DataFrame,
    dedup_mode: str,
) -> pd.DataFrame:
    mapping_cols = [
        "field",
        "standard",
        "raw_subject",
        "normalized_subject",
        "keep_separate",
        "rule_type",
        "mapping_source",
        "notes",
    ]
    merged = frame.merge(
        mapping_draft[mapping_cols],
        how="left",
        left_on=["field", "standard", "subject"],
        right_on=["field", "standard", "raw_subject"],
    )
    merged["mapping_applied"] = merged["subject"] != merged["normalized_subject"]
    merged["dedup_mode"] = dedup_mode
    merged = merged.drop(columns=["raw_subject", "notes"])
    columns = [
        "ts_code",
        "order_book_id",
        "quarter",
        "info_date",
        "fiscal_year",
        "field",
        "standard",
        "subject",
        "normalized_subject",
        "keep_separate",
        "rule_type",
        "mapping_source",
        "mapping_applied",
        "currency",
        "amount",
        "relationship",
        "if_adjusted",
        "dedup_mode",
    ]
    return merged[columns].sort_values(
        ["field", "standard", "normalized_subject", "ts_code", "quarter", "info_date"],
        kind="mergesort",
    ).reset_index(drop=True)


def _build_normalized_subject_frequency(normalized_long: pd.DataFrame) -> pd.DataFrame:
    return (
        normalized_long.groupby(["field", "standard", "normalized_subject"], dropna=False)
        .agg(
            rows=("ts_code", "size"),
            symbols=("ts_code", "nunique"),
            currencies=("currency", _join_unique),
        )
        .reset_index()
        .sort_values(
            ["field", "rows", "symbols", "standard", "normalized_subject"],
            ascending=[True, False, False, True, True],
        )
        .reset_index(drop=True)
    )


def _build_normalization_stats(frame: pd.DataFrame, normalized_long: pd.DataFrame) -> pd.DataFrame:
    raw_unique = frame.groupby("field", dropna=False)["subject"].nunique(dropna=True).rename("raw_unique_subjects")
    normalized_unique = (
        normalized_long.groupby("field", dropna=False)["normalized_subject"]
        .nunique(dropna=True)
        .rename("normalized_unique_subjects")
    )
    rows = normalized_long.groupby("field", dropna=False).size().rename("rows")
    symbols = normalized_long.groupby("field", dropna=False)["ts_code"].nunique().rename("symbols")
    stats = pd.concat([rows, symbols, raw_unique, normalized_unique], axis=1).reset_index()
    stats["subject_reduction"] = stats["raw_unique_subjects"] - stats["normalized_unique_subjects"]
    return stats.sort_values("field", kind="mergesort").reset_index(drop=True)


def _build_probe_coverage(
    frame: pd.DataFrame,
    audit: pd.DataFrame,
    compare_symbols: set[str],
) -> pd.DataFrame:
    written = (
        frame.groupby("ts_code", dropna=False)
        .agg(
            rows=("ts_code", "size"),
            fields_present=("field", _join_unique),
            standards_present=("standard", _join_unique),
            min_quarter=("quarter", "min"),
            max_quarter=("quarter", "max"),
        )
        .reset_index()
    )
    if audit.empty:
        coverage = written.copy()
        coverage["status"] = "written"
    else:
        base_columns = [column for column in ["ts_code", "status"] if column in audit.columns]
        coverage = audit[base_columns].drop_duplicates(subset=["ts_code"]).copy()
        coverage = coverage.merge(written, how="left", on="ts_code")
        coverage["rows"] = coverage["rows"].fillna(0).astype(int)
        for column in ("fields_present", "standards_present", "min_quarter", "max_quarter"):
            if column in coverage.columns:
                coverage[column] = coverage[column].fillna("")
    if compare_symbols:
        coverage["in_compare_probe"] = coverage["ts_code"].isin(compare_symbols)
    return coverage.sort_values("ts_code", kind="mergesort").reset_index(drop=True)


def _extract_compare_symbols(compare_audit: pd.DataFrame, compare_frame: pd.DataFrame) -> set[str]:
    if not compare_audit.empty and "ts_code" in compare_audit.columns:
        return {str(value) for value in compare_audit["ts_code"].dropna().tolist()}
    return {str(value) for value in compare_frame["ts_code"].dropna().unique().tolist()}


def _build_new_subjects_vs_compare(current_frame: pd.DataFrame, compare_frame: pd.DataFrame) -> pd.DataFrame:
    current = current_frame[["field", "standard", "subject"]].drop_duplicates()
    previous = compare_frame[["field", "standard", "subject"]].drop_duplicates()
    merged = current.merge(previous, how="left", on=["field", "standard", "subject"], indicator=True)
    new_subjects = merged[merged["_merge"] == "left_only"].drop(columns=["_merge"])
    return new_subjects.sort_values(["field", "standard", "subject"], kind="mergesort").reset_index(drop=True)


def _build_summary_text(
    *,
    probe_dir: Path,
    out_dir: Path,
    mapping_files: tuple[str, ...],
    manifest: dict[str, Any],
    audit: pd.DataFrame,
    raw_frame: pd.DataFrame,
    normalized_long: pd.DataFrame,
    duplicate_summary: pd.DataFrame,
    normalized_stats: pd.DataFrame,
    dedup_mode: str,
    compare_probe_dir: Path | None,
    new_subjects_vs_compare: pd.DataFrame | None,
) -> str:
    requested_symbols = int(len(audit)) if not audit.empty else int(raw_frame["ts_code"].nunique())
    written_symbols = int(
        (audit["status"].astype(str) == "written").sum() if not audit.empty and "status" in audit.columns else raw_frame["ts_code"].nunique()
    )
    missing_symbols = int(
        (audit["status"].astype(str) == "missing_remote").sum()
        if not audit.empty and "status" in audit.columns
        else 0
    )
    lines = [
        "# HK Financial Details Analysis",
        "",
        f"- probe_dir: `{probe_dir}`",
        f"- out_dir: `{out_dir}`",
        f"- dedup_mode: `{dedup_mode}`",
        f"- requested_symbols: {requested_symbols}",
        f"- written_symbols: {written_symbols}",
        f"- missing_remote_symbols: {missing_symbols}",
        f"- raw_rows: {len(raw_frame)}",
        f"- normalized_rows: {len(normalized_long)}",
        f"- duplicate_groups_before_dedup: {len(duplicate_summary)}",
        f"- mapping_files: {', '.join(f'`{path}`' for path in mapping_files)}",
    ]
    query = manifest.get("query")
    if isinstance(query, dict):
        fields = query.get("fields")
        if isinstance(fields, list) and fields:
            lines.append(f"- fields: {', '.join(str(field) for field in fields)}")
    if compare_probe_dir is not None:
        lines.append(f"- compare_probe_dir: `{compare_probe_dir}`")
        lines.append(f"- new_subjects_vs_compare: {0 if new_subjects_vs_compare is None else len(new_subjects_vs_compare)}")
    lines.extend(["", "## Field coverage", ""])
    for row in normalized_stats.itertuples(index=False):
        lines.append(
            f"- {row.field}: {row.rows} rows, {row.symbols} symbols, "
            f"{row.raw_unique_subjects} raw subjects -> {row.normalized_unique_subjects} normalized subjects"
        )
    if duplicate_summary.empty:
        lines.extend(["", "## Duplicate disclosures", "", "- 当前样本未发现同一 raw subject 的重复披露。"])
    else:
        lines.extend(
            [
                "",
                "## Duplicate disclosures",
                "",
                "- 原始 long 表里存在同一 `symbol + quarter + field + subject` 的重复披露；建议继续保留 `duplicate_disclosure_summary.csv` 做核对。",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def analyze_probe(
    *,
    probe_dir: Path,
    out_dir: Path,
    dedup_mode: str,
    fields: tuple[str, ...] = (),
    compare_probe_dir: Path | None = None,
    mapping_file: Path | None = None,
) -> AnalysisResult:
    manifest = _load_manifest(probe_dir)
    raw_frame = _load_probe_frame(probe_dir, fields)
    audit = _load_audit(probe_dir)
    mapping_rules, mapping_files = _load_mapping_rules(mapping_file)
    mapping_draft = _build_mapping_draft(raw_frame, mapping_rules)
    duplicate_summary = _build_duplicate_disclosure_summary(raw_frame)
    deduped_frame = _deduplicate_frame(raw_frame, dedup_mode)
    normalized_long = _apply_mapping(deduped_frame, mapping_draft, dedup_mode)
    subject_frequency = _build_subject_frequency(raw_frame)
    subject_examples = _build_subject_examples(raw_frame)
    normalized_subject_frequency = _build_normalized_subject_frequency(normalized_long)
    normalization_stats = _build_normalization_stats(raw_frame, normalized_long)

    compare_symbols: set[str] = set()
    new_subjects_vs_compare: pd.DataFrame | None = None
    if compare_probe_dir is not None:
        compare_frame = _load_probe_frame(compare_probe_dir, fields)
        compare_audit = _load_audit(compare_probe_dir)
        compare_symbols = _extract_compare_symbols(compare_audit, compare_frame)
        new_subjects_vs_compare = _build_new_subjects_vs_compare(raw_frame, compare_frame)

    probe_coverage = _build_probe_coverage(raw_frame, audit, compare_symbols)
    summary_text = _build_summary_text(
        probe_dir=probe_dir,
        out_dir=out_dir,
        mapping_files=mapping_files,
        manifest=manifest,
        audit=audit,
        raw_frame=raw_frame,
        normalized_long=normalized_long,
        duplicate_summary=duplicate_summary,
        normalized_stats=normalization_stats,
        dedup_mode=dedup_mode,
        compare_probe_dir=compare_probe_dir,
        new_subjects_vs_compare=new_subjects_vs_compare,
    )
    return AnalysisResult(
        probe_dir=probe_dir,
        out_dir=out_dir,
        dedup_mode=dedup_mode,
        fields=fields,
        mapping_files=mapping_files,
        manifest=manifest,
        raw_frame=raw_frame,
        deduped_frame=deduped_frame,
        audit=audit,
        probe_coverage=probe_coverage,
        subject_frequency=subject_frequency,
        subject_examples=subject_examples,
        subject_mapping_draft=mapping_draft,
        duplicate_disclosure_summary=duplicate_summary,
        normalized_long=normalized_long,
        normalized_subject_frequency=normalized_subject_frequency,
        normalization_stats=normalization_stats,
        new_subjects_vs_compare=new_subjects_vs_compare,
        summary_text=summary_text,
        compare_probe_dir=compare_probe_dir,
    )


def write_analysis_bundle(result: AnalysisResult) -> dict[str, Path]:
    result.out_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "probe_coverage.csv": result.out_dir / "probe_coverage.csv",
        "subject_frequency.csv": result.out_dir / "subject_frequency.csv",
        "subject_examples.csv": result.out_dir / "subject_examples.csv",
        "subject_mapping_draft.csv": result.out_dir / "subject_mapping_draft.csv",
        "duplicate_disclosure_summary.csv": result.out_dir / "duplicate_disclosure_summary.csv",
        "normalized_long.csv": result.out_dir / "normalized_long.csv",
        "normalized_long.parquet": result.out_dir / "normalized_long.parquet",
        "normalized_subject_frequency.csv": result.out_dir / "normalized_subject_frequency.csv",
        "normalization_stats.csv": result.out_dir / "normalization_stats.csv",
        "summary.md": result.out_dir / "summary.md",
        "analysis_manifest.yml": result.out_dir / "analysis_manifest.yml",
    }
    result.probe_coverage.to_csv(outputs["probe_coverage.csv"], index=False)
    result.subject_frequency.to_csv(outputs["subject_frequency.csv"], index=False)
    result.subject_examples.to_csv(outputs["subject_examples.csv"], index=False)
    result.subject_mapping_draft.to_csv(outputs["subject_mapping_draft.csv"], index=False)
    result.duplicate_disclosure_summary.to_csv(outputs["duplicate_disclosure_summary.csv"], index=False)
    result.normalized_long.to_csv(outputs["normalized_long.csv"], index=False)
    result.normalized_long.to_parquet(outputs["normalized_long.parquet"], index=False)
    result.normalized_subject_frequency.to_csv(outputs["normalized_subject_frequency.csv"], index=False)
    result.normalization_stats.to_csv(outputs["normalization_stats.csv"], index=False)
    outputs["summary.md"].write_text(result.summary_text, encoding="utf-8")
    analysis_manifest = {
        "probe_dir": str(result.probe_dir),
        "out_dir": str(result.out_dir),
        "compare_probe_dir": str(result.compare_probe_dir) if result.compare_probe_dir else None,
        "dedup_mode": result.dedup_mode,
        "fields": list(result.fields),
        "mapping_files": list(result.mapping_files),
        "rows": {
            "raw": int(len(result.raw_frame)),
            "deduped": int(len(result.deduped_frame)),
            "normalized": int(len(result.normalized_long)),
        },
        "files": {name: str(path) for name, path in outputs.items()},
    }
    if result.new_subjects_vs_compare is not None:
        compare_path = result.out_dir / "new_subjects_vs_compare.csv"
        result.new_subjects_vs_compare.to_csv(compare_path, index=False)
        outputs["new_subjects_vs_compare.csv"] = compare_path
        analysis_manifest["files"]["new_subjects_vs_compare.csv"] = str(compare_path)
    with outputs["analysis_manifest.yml"].open("w", encoding="utf-8") as handle:
        yaml.safe_dump(analysis_manifest, handle, allow_unicode=True, sort_keys=False)
    return outputs


def _default_out_dir(probe_dir: Path) -> Path:
    return probe_dir.parent / f"analysis_{probe_dir.name}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze HK financial_details probe assets and build a normalized long-form research bundle.",
    )
    parser.add_argument("--probe-dir", required=True, help="Path to a financial_details snapshot directory.")
    parser.add_argument("--out-dir", help="Output directory for analysis artifacts. Defaults to analysis_<snapshot>.")
    parser.add_argument(
        "--compare-probe-dir",
        help="Optional second probe directory used only to measure newly observed raw subjects and sample overlap.",
    )
    parser.add_argument(
        "--field",
        action="append",
        default=[],
        help="Restrict analysis to a subset of requested fields. Repeatable.",
    )
    parser.add_argument(
        "--dedup",
        choices=("none", "latest_info_date", "latest_adjusted_then_info_date"),
        default="latest_adjusted_then_info_date",
        help="Dedup policy for repeated disclosures when the source asset was pulled with --statements all.",
    )
    parser.add_argument(
        "--mapping-file",
        help=(
            "Optional CSV file with override rules layered on top of the repo default mapping. "
            "Required columns: field, standard, raw_subject, normalized_subject, keep_separate, rule_type, notes."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    probe_dir = _resolve_path(args.probe_dir)
    out_dir = _resolve_path(args.out_dir) if args.out_dir else _default_out_dir(probe_dir)
    compare_probe_dir = _resolve_path(args.compare_probe_dir) if args.compare_probe_dir else None
    mapping_file = _resolve_path(args.mapping_file) if args.mapping_file else None
    fields = tuple(str(field).strip() for field in args.field if str(field).strip())
    result = analyze_probe(
        probe_dir=probe_dir,
        out_dir=out_dir,
        dedup_mode=str(args.dedup),
        fields=fields,
        compare_probe_dir=compare_probe_dir,
        mapping_file=mapping_file,
    )
    outputs = write_analysis_bundle(result)
    written_files = ", ".join(name for name in outputs if name.endswith(".csv") or name.endswith(".md"))
    print(
        f"Wrote HK financial_details analysis to {out_dir} "
        f"({len(result.normalized_long)} normalized rows, dedup={result.dedup_mode}, files={written_files})"
    )
    return 0


__all__ = [
    "AnalysisResult",
    "SubjectRule",
    "analyze_probe",
    "apply_subject_rule",
    "build_parser",
    "main",
    "write_analysis_bundle",
]
