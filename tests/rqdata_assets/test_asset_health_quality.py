from cstree.data_tools.rqdata_assets.asset_health import _build_field_quality_checks


def _field_row(**overrides):
    row = {
        "field": "market_cap",
        "symbols_with_target_date_row": 2,
        "clean_nonmissing_on_target_date": 2,
        "unusable_on_target_date": 0,
        "provider_like_unusable_on_target_date": 0,
        "placeholder_on_target_date": 0,
        "nonfinite_on_target_date": 0,
        "zero_on_target_date": 0,
        "most_common_clean_value_on_target_date": 1.0,
        "is_constant_across_clean_values_on_target_date": False,
        "sample_provider_like_ffill_symbols": [],
        "sample_unusable_symbols": [],
        "sample_prior_clean_symbols": [],
        "sample_missing_symbols": [],
        "sample_placeholder_symbols": [],
        "sample_nonfinite_symbols": [],
        "sample_zero_symbols": [],
        "sample_clean_symbols": [],
        "sample_oldest_ffill_symbols": [],
        "ffill_age_gt_10d_symbols": 0,
        "ffill_age_gt_5d_symbols": 0,
        "ffill_age_gt_1d_symbols": 0,
        "provider_ffill_age_gt_10d_symbols": 0,
        "provider_ffill_age_gt_5d_symbols": 0,
        "provider_ffill_age_gt_1d_symbols": 0,
    }
    row.update(overrides)
    return row


def test_build_field_quality_checks_reports_all_clean_missing_error():
    checks = _build_field_quality_checks(
        field_rows=[
            _field_row(
                clean_nonmissing_on_target_date=0,
                unusable_on_target_date=2,
                sample_unusable_symbols=["00005.HK"],
                sample_missing_symbols=["00001.HK"],
            )
        ],
        dataset="daily",
        sample_limit=5,
    )

    assert checks == [
        {
            "check": "field_all_clean_missing_on_target_date",
            "field": "market_cap",
            "severity": "error",
            "affected_symbols": 2,
            "affected_pct": 100.0,
            "sample_symbols": ["00005.HK", "00001.HK"],
        }
    ]


def test_build_field_quality_checks_downgrades_provider_like_valuation_missing():
    checks = _build_field_quality_checks(
        field_rows=[
            _field_row(
                clean_nonmissing_on_target_date=0,
                unusable_on_target_date=2,
                provider_like_unusable_on_target_date=2,
                sample_provider_like_ffill_symbols=[
                    {"symbol": "00005.HK"},
                    {"symbol": "00001.HK"},
                ],
            )
        ],
        dataset="valuation",
        sample_limit=1,
    )

    assert checks == [
        {
            "check": "field_all_clean_missing_on_target_date_provider_like",
            "field": "market_cap",
            "severity": "info",
            "affected_symbols": 2,
            "affected_pct": 100.0,
            "sample_symbols": ["00005.HK"],
        }
    ]


def test_build_field_quality_checks_reports_ffill_thresholds():
    checks = _build_field_quality_checks(
        field_rows=[
            _field_row(
                clean_nonmissing_on_target_date=1,
                unusable_on_target_date=1,
                ffill_age_gt_10d_symbols=1,
                sample_oldest_ffill_symbols=[{"symbol": "00005.HK"}],
            )
        ],
        dataset="valuation",
        sample_limit=5,
    )

    assert checks == [
        {
            "check": "field_ffill_age_gt_10d",
            "field": "market_cap",
            "severity": "error",
            "affected_symbols": 1,
            "affected_pct": 100.0,
            "sample_symbols": ["00005.HK"],
        }
    ]
