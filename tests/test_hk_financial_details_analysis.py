from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from csml.research.hk_financial_details import DEFAULT_MAPPING_FILE, analyze_probe, write_analysis_bundle


def _write_probe_asset(
    probe_dir: Path,
    *,
    rows: list[dict[str, object]],
    requested_symbols: list[str],
    statuses: dict[str, str] | None = None,
) -> None:
    statuses = statuses or {}
    probe_dir.mkdir(parents=True, exist_ok=True)
    data_dir = probe_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    for symbol, group in frame.groupby("symbol", dropna=False):
        group.to_parquet(data_dir / f"{symbol}.parquet", index=False)
    audit_rows: list[dict[str, object]] = []
    for symbol in requested_symbols:
        symbol_frame = frame[frame["symbol"] == symbol]
        status = statuses.get(symbol, "written" if not symbol_frame.empty else "missing_remote")
        audit_rows.append(
            {
                "symbol": symbol,
                "order_book_id": f"{symbol[:5]}.XHKG",
                "status": status,
                "attempts": 1,
                "rows": int(len(symbol_frame)),
            }
        )
    pd.DataFrame(audit_rows).to_csv(probe_dir / "audit.csv", index=False)
    manifest = {
        "name": probe_dir.name,
        "dataset": "financial_details",
        "query": {
            "fields": sorted(frame["field"].dropna().unique().tolist()),
            "fields_count": int(frame["field"].nunique(dropna=True)),
        },
        "symbol_source": {
            "count": len(requested_symbols),
        },
    }
    with (probe_dir / "manifest.yml").open("w", encoding="utf-8") as handle:
        yaml.safe_dump(manifest, handle, allow_unicode=True, sort_keys=False)


def test_analyze_probe_normalizes_known_subject_variants(tmp_path: Path):
    assert DEFAULT_MAPPING_FILE.exists()
    probe_dir = tmp_path / "probe"
    rows = [
        {
            "symbol": "00883.HK",
            "order_book_id": "00883.XHKG",
            "quarter": "2024q1",
            "info_date": "2025-04-29",
            "fiscal_year": "2024-12-31",
            "field": "operating_revenue",
            "relationship": 1,
            "amount": 111.0,
            "currency": "人民币元",
            "subject": "其中:营业收入",
            "standard": "中国会计准则",
            "if_adjusted": 1,
        },
        {
            "symbol": "01211.HK",
            "order_book_id": "01211.XHKG",
            "quarter": "2024q4",
            "info_date": "2025-03-24",
            "fiscal_year": "2024-12-31",
            "field": "operating_revenue",
            "relationship": 1,
            "amount": 222.0,
            "currency": "人民币元",
            "subject": "一,营业收入",
            "standard": "中国会计准则",
            "if_adjusted": 0,
        },
        {
            "symbol": "00939.HK",
            "order_book_id": "00939.XHKG",
            "quarter": "2024q1",
            "info_date": "2025-04-29",
            "fiscal_year": "2024-12-31",
            "field": "operating_revenue",
            "relationship": 1,
            "amount": 333.0,
            "currency": "人民币元",
            "subject": "经营收入",
            "standard": "非中国会计准则_金融公司",
            "if_adjusted": 1,
        },
    ]
    _write_probe_asset(probe_dir, rows=rows, requested_symbols=["00883.HK", "01211.HK", "00939.HK"])

    result = analyze_probe(
        probe_dir=probe_dir,
        out_dir=tmp_path / "analysis",
        dedup_mode="latest_adjusted_then_info_date",
    )

    mapping = result.subject_mapping_draft.set_index(["field", "standard", "raw_subject"])
    assert mapping.loc[("operating_revenue", "中国会计准则", "其中:营业收入"), "normalized_subject"] == "营业收入"
    assert mapping.loc[("operating_revenue", "中国会计准则", "一,营业收入"), "normalized_subject"] == "营业收入"
    assert mapping.loc[("operating_revenue", "非中国会计准则_金融公司", "经营收入"), "keep_separate"] == "yes"
    assert mapping.loc[("operating_revenue", "中国会计准则", "其中:营业收入"), "mapping_source"] == "repo_default"

    normalized = result.normalized_long
    china_subjects = normalized.loc[normalized["standard"] == "中国会计准则", "normalized_subject"].unique().tolist()
    assert china_subjects == ["营业收入"]
    assert set(result.normalization_stats["normalized_unique_subjects"].tolist()) == {2}
    assert str(DEFAULT_MAPPING_FILE) in result.mapping_files


def test_analyze_probe_override_mapping_file_takes_precedence(tmp_path: Path):
    probe_dir = tmp_path / "probe"
    rows = [
        {
            "symbol": "00883.HK",
            "order_book_id": "00883.XHKG",
            "quarter": "2024q1",
            "info_date": "2025-04-29",
            "fiscal_year": "2024-12-31",
            "field": "operating_revenue",
            "relationship": 1,
            "amount": 111.0,
            "currency": "人民币元",
            "subject": "其中:营业收入",
            "standard": "中国会计准则",
            "if_adjusted": 1,
        },
    ]
    _write_probe_asset(probe_dir, rows=rows, requested_symbols=["00883.HK"])
    mapping_file = tmp_path / "mapping_override.csv"
    mapping_file.write_text(
        "\n".join(
            [
                "field,standard,raw_subject,normalized_subject,keep_separate,rule_type,notes",
                "operating_revenue,中国会计准则,其中:营业收入,营业收入_覆写,no,manual_override,测试覆盖默认映射",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = analyze_probe(
        probe_dir=probe_dir,
        out_dir=tmp_path / "analysis",
        dedup_mode="latest_adjusted_then_info_date",
        mapping_file=mapping_file,
    )

    mapping = result.subject_mapping_draft.set_index(["field", "standard", "raw_subject"])
    assert mapping.loc[("operating_revenue", "中国会计准则", "其中:营业收入"), "normalized_subject"] == "营业收入_覆写"
    assert mapping.loc[("operating_revenue", "中国会计准则", "其中:营业收入"), "mapping_source"] == "override"
    assert result.normalized_long.loc[0, "normalized_subject"] == "营业收入_覆写"
    assert result.mapping_files == (str(DEFAULT_MAPPING_FILE), str(mapping_file))


def test_analyze_probe_dedups_latest_adjusted_then_info_date(tmp_path: Path):
    probe_dir = tmp_path / "probe_all"
    rows = [
        {
            "symbol": "02318.HK",
            "order_book_id": "02318.XHKG",
            "quarter": "2024q1",
            "info_date": "2024-04-23",
            "fiscal_year": "2024-12-31",
            "field": "other_operating_expense_items",
            "relationship": -1,
            "amount": -62000000.0,
            "currency": "人民币元",
            "subject": "提取保费准备金",
            "standard": "非中国会计准则_保险公司",
            "if_adjusted": 0,
        },
        {
            "symbol": "02318.HK",
            "order_book_id": "02318.XHKG",
            "quarter": "2024q1",
            "info_date": "2025-04-25",
            "fiscal_year": "2024-12-31",
            "field": "other_operating_expense_items",
            "relationship": -1,
            "amount": -62000000.0,
            "currency": "人民币元",
            "subject": "提取保费准备金",
            "standard": "非中国会计准则_保险公司",
            "if_adjusted": 1,
        },
        {
            "symbol": "02318.HK",
            "order_book_id": "02318.XHKG",
            "quarter": "2024q1",
            "info_date": "2025-04-25",
            "fiscal_year": "2024-12-31",
            "field": "other_operating_expense_items",
            "relationship": -1,
            "amount": -27994000000.0,
            "currency": "人民币元",
            "subject": "银行业务利息支出",
            "standard": "非中国会计准则_保险公司",
            "if_adjusted": 1,
        },
    ]
    _write_probe_asset(probe_dir, rows=rows, requested_symbols=["02318.HK"])

    result = analyze_probe(
        probe_dir=probe_dir,
        out_dir=tmp_path / "analysis",
        dedup_mode="latest_adjusted_then_info_date",
    )

    assert len(result.duplicate_disclosure_summary) == 1
    duplicate = result.duplicate_disclosure_summary.iloc[0]
    assert duplicate["disclosure_count"] == 2
    assert duplicate["unique_amounts"] == 1
    assert str(duplicate["if_adjusted_values"]) == "0|1"

    normalized = result.normalized_long
    kept = normalized[normalized["subject"] == "提取保费准备金"].reset_index(drop=True)
    assert len(kept) == 1
    assert str(kept.loc[0, "info_date"].date()) == "2025-04-25"
    assert int(kept.loc[0, "if_adjusted"]) == 1


def test_write_analysis_bundle_writes_compare_outputs(tmp_path: Path):
    compare_dir = tmp_path / "compare_probe"
    compare_rows = [
        {
            "symbol": "00883.HK",
            "order_book_id": "00883.XHKG",
            "quarter": "2024q1",
            "info_date": "2025-04-29",
            "fiscal_year": "2024-12-31",
            "field": "operating_revenue",
            "relationship": 1,
            "amount": 111.0,
            "currency": "人民币元",
            "subject": "其中:营业收入",
            "standard": "中国会计准则",
            "if_adjusted": 1,
        },
    ]
    _write_probe_asset(compare_dir, rows=compare_rows, requested_symbols=["00883.HK", "00939.HK"])

    probe_dir = tmp_path / "probe"
    current_rows = compare_rows + [
        {
            "symbol": "00011.HK",
            "order_book_id": "00011.XHKG",
            "quarter": "2024q2",
            "info_date": "2025-07-30",
            "fiscal_year": "2024-12-31",
            "field": "other_operating_expense_items",
            "relationship": -1,
            "amount": 2975000000.0,
            "currency": "港元",
            "subject": "业务及行政支出",
            "standard": "非中国会计准则_金融公司",
            "if_adjusted": 1,
        },
    ]
    _write_probe_asset(
        probe_dir,
        rows=current_rows,
        requested_symbols=["00883.HK", "00011.HK", "00175.HK"],
        statuses={"00175.HK": "missing_remote"},
    )

    result = analyze_probe(
        probe_dir=probe_dir,
        out_dir=tmp_path / "analysis",
        dedup_mode="latest_adjusted_then_info_date",
        compare_probe_dir=compare_dir,
    )
    outputs = write_analysis_bundle(result)

    assert (tmp_path / "analysis" / "summary.md").exists()
    assert (tmp_path / "analysis" / "normalized_long.parquet").exists()
    assert (tmp_path / "analysis" / "new_subjects_vs_compare.csv").exists()
    assert set(outputs) >= {"summary.md", "normalized_long.parquet", "new_subjects_vs_compare.csv"}

    new_subjects = pd.read_csv(tmp_path / "analysis" / "new_subjects_vs_compare.csv")
    assert len(new_subjects) == 1
    assert new_subjects.loc[0, "subject"] == "业务及行政支出"

    coverage = pd.read_csv(tmp_path / "analysis" / "probe_coverage.csv")
    assert "in_compare_probe" in coverage.columns
    assert bool(coverage.loc[coverage["symbol"] == "00883.HK", "in_compare_probe"].iloc[0]) is True
    assert bool(coverage.loc[coverage["symbol"] == "00011.HK", "in_compare_probe"].iloc[0]) is False
