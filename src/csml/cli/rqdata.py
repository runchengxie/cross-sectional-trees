from __future__ import annotations

import json

from .common import augment_quota_payload, format_quota_pretty, init_rqdatac


def handle_rqdata_info(args) -> int:
    rqdatac = init_rqdatac(args)
    info = rqdatac.info()
    print(info)
    return 0


def handle_rqdata_quota(args) -> int:
    rqdatac = init_rqdatac(args)
    quota = rqdatac.user.get_quota()
    payload = quota
    if hasattr(quota, "to_dict"):
        try:
            payload = quota.to_dict(orient="records")
        except TypeError:
            payload = quota.to_dict()
    payload = augment_quota_payload(payload)
    if getattr(args, "pretty", False):
        print(format_quota_pretty(payload))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


def _run_rqdata_asset_command(args, method_name: str) -> int:
    from ..data_tools import rqdata_assets

    rqdatac = init_rqdatac(args)
    return int(getattr(rqdata_assets, method_name)(args, rqdatac) or 0)


def handle_rqdata_list_hk_financial_fields(args) -> int:
    from ..data_tools import rqdata_assets

    return int(rqdata_assets.list_hk_financial_fields(args) or 0)


def handle_rqdata_build_hk_pit_fundamentals(args) -> int:
    from ..data_tools import rqdata_assets

    return int(rqdata_assets.build_hk_pit_fundamentals_file(args) or 0)


def handle_rqdata_build_hk_industry_labels(args) -> int:
    from ..data_tools import rqdata_assets

    return int(rqdata_assets.build_hk_industry_labels_file(args) or 0)


def handle_rqdata_inspect_hk_pit_coverage(args) -> int:
    from ..data_tools import rqdata_assets

    return int(rqdata_assets.inspect_hk_pit_coverage(args) or 0)


def handle_rqdata_inspect_hk_asset_health(args) -> int:
    from ..data_tools import rqdata_assets

    return int(rqdata_assets.inspect_hk_asset_health(args) or 0)


def handle_rqdata_export_hk_instruments(args) -> int:
    return _run_rqdata_asset_command(args, "export_hk_instruments")


def handle_rqdata_mirror_hk_daily(args) -> int:
    return _run_rqdata_asset_command(args, "mirror_hk_daily")


def handle_rqdata_mirror_hk_valuation(args) -> int:
    return _run_rqdata_asset_command(args, "mirror_hk_valuation")


def handle_rqdata_mirror_hk_pit_financials(args) -> int:
    return _run_rqdata_asset_command(args, "mirror_hk_pit_financials")


def handle_rqdata_mirror_hk_financial_details(args) -> int:
    return _run_rqdata_asset_command(args, "mirror_hk_financial_details")


def handle_rqdata_mirror_hk_ex_factors(args) -> int:
    return _run_rqdata_asset_command(args, "mirror_hk_ex_factors")


def handle_rqdata_mirror_hk_dividends(args) -> int:
    return _run_rqdata_asset_command(args, "mirror_hk_dividends")


def handle_rqdata_mirror_hk_shares(args) -> int:
    return _run_rqdata_asset_command(args, "mirror_hk_shares")


def handle_rqdata_mirror_hk_exchange_rate(args) -> int:
    return _run_rqdata_asset_command(args, "mirror_hk_exchange_rate")


def handle_rqdata_mirror_hk_announcement(args) -> int:
    return _run_rqdata_asset_command(args, "mirror_hk_announcement")


def handle_rqdata_mirror_hk_southbound(args) -> int:
    return _run_rqdata_asset_command(args, "mirror_hk_southbound")


def handle_rqdata_mirror_hk_instrument_industry(args) -> int:
    return _run_rqdata_asset_command(args, "mirror_hk_instrument_industry")


def handle_rqdata_mirror_hk_industry_changes(args) -> int:
    return _run_rqdata_asset_command(args, "mirror_hk_industry_changes")


def register_rqdata_command(subparsers) -> None:
    from ..data_tools import rqdata_assets

    rqdata = subparsers.add_parser("rqdata", help="RQData utilities")
    rq_sub = rqdata.add_subparsers(dest="rq_command", required=True)

    rq_info = rq_sub.add_parser("info", help="Show rqdatac login/info")
    rq_info.add_argument("--config", help="Optional config path to load rqdata.init")
    rq_info.add_argument("--username", help="Override RQData username")
    rq_info.add_argument("--password", help="Override RQData password")
    rq_info.set_defaults(func=handle_rqdata_info)

    rq_quota = rq_sub.add_parser("quota", help="Show rqdatac quota usage")
    rq_quota.add_argument("--config", help="Optional config path to load rqdata.init")
    rq_quota.add_argument("--username", help="Override RQData username")
    rq_quota.add_argument("--password", help="Override RQData password")
    rq_quota.add_argument(
        "--pretty",
        action="store_true",
        help="Show human-friendly output with percent and progress bar",
    )
    rq_quota.set_defaults(func=handle_rqdata_quota)

    rq_list_fields = rq_sub.add_parser(
        "list-hk-financial-fields",
        help="List supported HK financial field names for PIT/details APIs",
    )
    rqdata_assets.add_list_hk_financial_fields_args(rq_list_fields)
    rq_list_fields.set_defaults(func=handle_rqdata_list_hk_financial_fields)

    rq_export_instruments = rq_sub.add_parser(
        "export-hk-instruments",
        help="Export HK instrument metadata such as order_book_id, listed_date, and round_lot",
    )
    rqdata_assets.add_hk_instruments_export_args(rq_export_instruments)
    rq_export_instruments.set_defaults(func=handle_rqdata_export_hk_instruments)

    rq_daily = rq_sub.add_parser(
        "mirror-hk-daily",
        help="Mirror HK daily OHLCV + turnover data into parquet + manifest assets",
    )
    rqdata_assets.add_hk_daily_mirror_args(rq_daily)
    rq_daily.set_defaults(func=handle_rqdata_mirror_hk_daily)

    rq_valuation = rq_sub.add_parser(
        "mirror-hk-valuation",
        help="Mirror HK daily valuation factors into parquet + manifest assets",
    )
    rqdata_assets.add_hk_valuation_mirror_args(rq_valuation)
    rq_valuation.set_defaults(func=handle_rqdata_mirror_hk_valuation)

    rq_pit = rq_sub.add_parser(
        "mirror-hk-pit-financials",
        help="Mirror HK PIT financial statements into parquet + manifest assets",
    )
    rqdata_assets.add_hk_financial_mirror_args(rq_pit)
    rq_pit.set_defaults(func=handle_rqdata_mirror_hk_pit_financials)

    rq_details = rq_sub.add_parser(
        "mirror-hk-financial-details",
        help="Mirror HK raw financial detail items into parquet + manifest assets",
    )
    rqdata_assets.add_hk_financial_mirror_args(rq_details)
    rq_details.set_defaults(func=handle_rqdata_mirror_hk_financial_details)

    rq_ex_factors = rq_sub.add_parser(
        "mirror-hk-ex-factors",
        help="Mirror HK ex-factor history into parquet + manifest assets",
    )
    rqdata_assets.add_hk_ex_factors_mirror_args(rq_ex_factors)
    rq_ex_factors.set_defaults(func=handle_rqdata_mirror_hk_ex_factors)

    rq_dividends = rq_sub.add_parser(
        "mirror-hk-dividends",
        help="Mirror HK dividend history into parquet + manifest assets",
    )
    rqdata_assets.add_hk_dividends_mirror_args(rq_dividends)
    rq_dividends.set_defaults(func=handle_rqdata_mirror_hk_dividends)

    rq_shares = rq_sub.add_parser(
        "mirror-hk-shares",
        help="Mirror HK share-capital history into parquet + manifest assets",
    )
    rqdata_assets.add_hk_shares_mirror_args(rq_shares)
    rq_shares.set_defaults(func=handle_rqdata_mirror_hk_shares)

    rq_exchange_rate = rq_sub.add_parser(
        "mirror-hk-exchange-rate",
        help="Mirror HK exchange-rate history into parquet + manifest assets",
    )
    rqdata_assets.add_hk_exchange_rate_mirror_args(rq_exchange_rate)
    rq_exchange_rate.set_defaults(func=handle_rqdata_mirror_hk_exchange_rate)

    rq_announcement = rq_sub.add_parser(
        "mirror-hk-announcement",
        help="Mirror HK company announcements into parquet + manifest assets",
    )
    rqdata_assets.add_hk_announcement_mirror_args(rq_announcement)
    rq_announcement.set_defaults(func=handle_rqdata_mirror_hk_announcement)

    rq_southbound = rq_sub.add_parser(
        "mirror-hk-southbound",
        help="Mirror HK southbound eligibility history into parquet + manifest assets",
    )
    rqdata_assets.add_hk_southbound_mirror_args(rq_southbound)
    rq_southbound.set_defaults(func=handle_rqdata_mirror_hk_southbound)

    rq_instrument_industry = rq_sub.add_parser(
        "mirror-hk-instrument-industry",
        help="Mirror HK instrument-industry snapshots into parquet + manifest assets",
    )
    rqdata_assets.add_hk_instrument_industry_mirror_args(rq_instrument_industry)
    rq_instrument_industry.set_defaults(func=handle_rqdata_mirror_hk_instrument_industry)

    rq_industry_changes = rq_sub.add_parser(
        "mirror-hk-industry-changes",
        help="Mirror HK industry membership intervals into parquet + manifest assets",
    )
    rqdata_assets.add_hk_industry_changes_mirror_args(rq_industry_changes)
    rq_industry_changes.set_defaults(func=handle_rqdata_mirror_hk_industry_changes)

    rq_pit_fundamentals = rq_sub.add_parser(
        "build-hk-pit-fundamentals",
        help="Build a pipeline-readable fundamentals file from an HK PIT mirror asset",
    )
    rqdata_assets.add_hk_pit_fundamentals_build_args(rq_pit_fundamentals)
    rq_pit_fundamentals.set_defaults(func=handle_rqdata_build_hk_pit_fundamentals)

    rq_industry_labels = rq_sub.add_parser(
        "build-hk-industry-labels",
        help="Build local HK industry label files from an industry_changes asset",
    )
    rqdata_assets.add_hk_industry_labels_build_args(rq_industry_labels)
    rq_industry_labels.set_defaults(func=handle_rqdata_build_hk_industry_labels)

    rq_pit_coverage = rq_sub.add_parser(
        "inspect-hk-pit-coverage",
        help="Inspect HK PIT fundamentals coverage for selected raw or derived features",
    )
    rqdata_assets.add_hk_pit_coverage_args(rq_pit_coverage)
    rq_pit_coverage.set_defaults(func=handle_rqdata_inspect_hk_pit_coverage)

    rq_asset_health = rq_sub.add_parser(
        "inspect-hk-asset-health",
        help="Inspect local HK asset snapshots for latest-date coverage and field-level gaps",
    )
    rqdata_assets.add_hk_asset_health_args(rq_asset_health)
    rq_asset_health.set_defaults(func=handle_rqdata_inspect_hk_asset_health)
