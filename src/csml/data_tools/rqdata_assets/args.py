from __future__ import annotations

import argparse


def _add_rqdata_credentials_args(
    parser: argparse.ArgumentParser,
    *,
    config_help: str,
) -> None:
    parser.add_argument("--config", help=config_help)
    parser.add_argument("--username", help="Override RQData username")
    parser.add_argument("--password", help="Override RQData password")


def _add_hk_symbol_selection_args(
    parser: argparse.ArgumentParser,
    *,
    symbol_help: str,
    symbols_file_help: str,
    by_date_file_help: str,
) -> None:
    parser.add_argument(
        "--symbol",
        action="append",
        default=[],
        help=symbol_help,
    )
    parser.add_argument(
        "--symbols-file",
        help=symbols_file_help,
    )
    parser.add_argument(
        "--by-date-file",
        help=by_date_file_help,
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional cap on the resolved symbol count after dedupe.",
    )


def _add_mirror_output_args(
    parser: argparse.ArgumentParser,
    *,
    default_out_root: str,
) -> None:
    parser.add_argument(
        "--out-root",
        default=default_out_root,
        help=f"Mirror root directory. Default: {default_out_root}",
    )
    parser.add_argument(
        "--name",
        help="Optional snapshot folder name. Default: auto-generated from range + timestamp.",
    )


def _add_resume_args(
    parser: argparse.ArgumentParser,
    *,
    resume_help: str,
    include_skip_existing: bool = True,
) -> None:
    parser.add_argument(
        "--resume",
        action="store_true",
        help=resume_help,
    )
    if include_skip_existing:
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Skip symbols whose parquet files already exist under data/. Implied by --resume.",
        )


def _add_retry_args(
    parser: argparse.ArgumentParser,
    *,
    max_attempts_default: int,
    backoff_seconds_default: float,
    max_backoff_seconds_default: float,
    attempts_help: str,
) -> None:
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=max_attempts_default,
        help=f"{attempts_help} Default: {max_attempts_default}.",
    )
    parser.add_argument(
        "--backoff-seconds",
        type=float,
        default=backoff_seconds_default,
        help=f"Initial retry backoff in seconds. Default: {backoff_seconds_default}.",
    )
    parser.add_argument(
        "--max-backoff-seconds",
        type=float,
        default=max_backoff_seconds_default,
        help=f"Maximum retry backoff in seconds. Default: {max_backoff_seconds_default}.",
    )


def add_list_hk_financial_fields_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--contains",
        action="append",
        default=[],
        help="Keep only field names containing this token. Repeatable.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional cap on the number of printed field names.",
    )
    parser.add_argument(
        "--out",
        help="Optional output path. Default: print to stdout.",
    )


def add_hk_instruments_export_args(
    parser: argparse.ArgumentParser,
    *,
    default_out_root: str,
    default_instruments_filename_prefix: str,
) -> None:
    _add_rqdata_credentials_args(
        parser,
        config_help="Optional config path or alias for rqdata.init.",
    )
    parser.add_argument(
        "--use-config-universe",
        action="store_true",
        help="Filter to the universe resolved from --config instead of exporting the full HK instrument list.",
    )
    parser.add_argument(
        "--instrument-type",
        default="CS",
        help=(
            "RQData instrument_type passed to all_instruments, for example CS or ETF. "
            "Default: CS."
        ),
    )
    _add_hk_symbol_selection_args(
        parser,
        symbol_help="HK symbol to keep, for example 00005.HK. Repeatable.",
        symbols_file_help="Text file with one HK symbol per line.",
        by_date_file_help="Universe-by-date CSV used to derive the HK symbol set.",
    )
    parser.add_argument(
        "--out",
        help=(
            "Output file path. Default: "
            + default_out_root
            + "/hk/instruments/"
            + default_instruments_filename_prefix
            + "_<timestamp>.parquet"
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )


def add_hk_daily_mirror_args(
    parser: argparse.ArgumentParser,
    *,
    default_batch_size: int,
    default_out_root: str,
    max_attempts_default: int,
    backoff_seconds_default: float,
    max_backoff_seconds_default: float,
) -> None:
    _add_rqdata_credentials_args(
        parser,
        config_help="Optional config path or alias for rqdata.init and default universe.",
    )
    parser.add_argument("--start-date", required=True, help="Date range start, for example 20000101.")
    parser.add_argument("--end-date", required=True, help="Date range end, for example 20260311.")
    parser.add_argument(
        "--field",
        action="append",
        default=[],
        help="Extra daily field name. Repeatable. The default OHLCV + total_turnover fields are always included.",
    )
    parser.add_argument(
        "--fields-file",
        action="append",
        default=[],
        help="Text file with one extra daily field per line. Repeatable.",
    )
    _add_hk_symbol_selection_args(
        parser,
        symbol_help="HK symbol to mirror, for example 00005.HK. Repeatable.",
        symbols_file_help="Text file with one HK symbol per line. If provided, this takes precedence over config universe symbols.",
        by_date_file_help="Universe-by-date CSV. If provided, this takes precedence over config universe symbols.",
    )
    parser.add_argument(
        "--adjust-type",
        help="Optional RQData adjust_type passed to get_price, for example none or pre.",
    )
    parser.add_argument(
        "--skip-suspended",
        dest="skip_suspended",
        action="store_true",
        help="Skip suspended data in RQData get_price. Default for HK is enabled.",
    )
    parser.add_argument(
        "--include-suspended",
        dest="skip_suspended",
        action="store_false",
        help="Include suspended rows instead of using the HK default skip behavior.",
    )
    parser.set_defaults(skip_suspended=None)
    parser.add_argument(
        "--batch-size",
        type=int,
        default=default_batch_size,
        help=f"Number of order_book_ids per RQData request. Default: {default_batch_size}.",
    )
    _add_mirror_output_args(parser, default_out_root=default_out_root)
    _add_resume_args(
        parser,
        resume_help="Resume into an existing snapshot directory. Requires matching fields, symbols, and query settings.",
    )
    _add_retry_args(
        parser,
        max_attempts_default=max_attempts_default,
        backoff_seconds_default=backoff_seconds_default,
        max_backoff_seconds_default=max_backoff_seconds_default,
        attempts_help="Retry attempts per request batch.",
    )


def add_hk_valuation_mirror_args(
    parser: argparse.ArgumentParser,
    *,
    default_batch_size: int,
    default_out_root: str,
    max_attempts_default: int,
    backoff_seconds_default: float,
    max_backoff_seconds_default: float,
) -> None:
    add_hk_dated_mirror_args(
        parser,
        default_batch_size=default_batch_size,
        default_out_root=default_out_root,
        max_attempts_default=max_attempts_default,
        backoff_seconds_default=backoff_seconds_default,
        max_backoff_seconds_default=max_backoff_seconds_default,
        supports_fields=True,
        field_help=(
            "Extra HK valuation factor name. The default archive fields "
            "hk_total_market_val/pe_ratio_ttm/pb_ratio_ttm are always included."
        ),
        fields_file_help="Text file with one extra HK valuation factor name per line. Repeatable.",
    )


def add_hk_dated_mirror_args(
    parser: argparse.ArgumentParser,
    *,
    default_batch_size: int,
    default_out_root: str,
    max_attempts_default: int,
    backoff_seconds_default: float,
    max_backoff_seconds_default: float,
    supports_fields: bool = False,
    field_help: str | None = None,
    fields_file_help: str | None = None,
) -> None:
    _add_rqdata_credentials_args(
        parser,
        config_help="Optional config path or alias for rqdata.init and default universe.",
    )
    parser.add_argument("--start-date", required=True, help="Date range start, for example 20000101.")
    parser.add_argument("--end-date", required=True, help="Date range end, for example 20260317.")
    if supports_fields:
        parser.add_argument(
            "--field",
            action="append",
            default=[],
            help=field_help or "Extra field name. Repeatable.",
        )
        parser.add_argument(
            "--fields-file",
            action="append",
            default=[],
            help=fields_file_help or "Text file with one extra field per line. Repeatable.",
        )
    _add_hk_symbol_selection_args(
        parser,
        symbol_help="HK symbol to mirror, for example 00005.HK. Repeatable.",
        symbols_file_help="Text file with one HK symbol per line. If provided, this takes precedence over config universe symbols.",
        by_date_file_help="Universe-by-date CSV. If provided, this takes precedence over config universe symbols.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=default_batch_size,
        help=f"Number of order_book_ids per RQData request. Default: {default_batch_size}.",
    )
    _add_mirror_output_args(parser, default_out_root=default_out_root)
    _add_resume_args(
        parser,
        resume_help="Resume into an existing snapshot directory. Requires matching fields, symbols, and query settings.",
    )
    _add_retry_args(
        parser,
        max_attempts_default=max_attempts_default,
        backoff_seconds_default=backoff_seconds_default,
        max_backoff_seconds_default=max_backoff_seconds_default,
        attempts_help="Retry attempts per request batch.",
    )


def add_hk_ex_factors_mirror_args(
    parser: argparse.ArgumentParser,
    *,
    default_batch_size: int,
    default_out_root: str,
    max_attempts_default: int,
    backoff_seconds_default: float,
    max_backoff_seconds_default: float,
) -> None:
    add_hk_dated_mirror_args(
        parser,
        default_batch_size=default_batch_size,
        default_out_root=default_out_root,
        max_attempts_default=max_attempts_default,
        backoff_seconds_default=backoff_seconds_default,
        max_backoff_seconds_default=max_backoff_seconds_default,
    )


def add_hk_dividends_mirror_args(
    parser: argparse.ArgumentParser,
    *,
    default_batch_size: int,
    default_out_root: str,
    max_attempts_default: int,
    backoff_seconds_default: float,
    max_backoff_seconds_default: float,
) -> None:
    add_hk_dated_mirror_args(
        parser,
        default_batch_size=default_batch_size,
        default_out_root=default_out_root,
        max_attempts_default=max_attempts_default,
        backoff_seconds_default=backoff_seconds_default,
        max_backoff_seconds_default=max_backoff_seconds_default,
    )


def add_hk_shares_mirror_args(
    parser: argparse.ArgumentParser,
    *,
    default_batch_size: int,
    default_out_root: str,
    max_attempts_default: int,
    backoff_seconds_default: float,
    max_backoff_seconds_default: float,
) -> None:
    add_hk_dated_mirror_args(
        parser,
        default_batch_size=default_batch_size,
        default_out_root=default_out_root,
        max_attempts_default=max_attempts_default,
        backoff_seconds_default=backoff_seconds_default,
        max_backoff_seconds_default=max_backoff_seconds_default,
        supports_fields=True,
        field_help=(
            "Extra shares field name. The documented total/circulation/HK share fields "
            "are included by default. Repeatable."
        ),
        fields_file_help="Text file with one extra shares field per line. Repeatable.",
    )


def add_hk_exchange_rate_mirror_args(
    parser: argparse.ArgumentParser,
    *,
    default_out_root: str,
    max_attempts_default: int,
    backoff_seconds_default: float,
    max_backoff_seconds_default: float,
) -> None:
    _add_rqdata_credentials_args(
        parser,
        config_help="Optional config path or alias for rqdata.init.",
    )
    parser.add_argument("--start-date", required=True, help="Date range start, for example 20000101.")
    parser.add_argument("--end-date", required=True, help="Date range end, for example 20260319.")
    parser.add_argument(
        "--field",
        action="append",
        default=[],
        help=(
            "Extra exchange-rate field name. currency_pair + middle_referrence_rate are included "
            "by default. Repeatable."
        ),
    )
    parser.add_argument(
        "--fields-file",
        action="append",
        default=[],
        help="Text file with one extra exchange-rate field per line. Repeatable.",
    )
    _add_mirror_output_args(parser, default_out_root=default_out_root)
    _add_resume_args(
        parser,
        resume_help="Resume into an existing snapshot directory. Requires matching dates and fields.",
        include_skip_existing=False,
    )
    _add_retry_args(
        parser,
        max_attempts_default=max_attempts_default,
        backoff_seconds_default=backoff_seconds_default,
        max_backoff_seconds_default=max_backoff_seconds_default,
        attempts_help="Retry attempts per exchange-rate request.",
    )


def add_hk_announcement_mirror_args(
    parser: argparse.ArgumentParser,
    *,
    default_batch_size: int,
    default_out_root: str,
    max_attempts_default: int,
    backoff_seconds_default: float,
    max_backoff_seconds_default: float,
) -> None:
    add_hk_dated_mirror_args(
        parser,
        default_batch_size=default_batch_size,
        default_out_root=default_out_root,
        max_attempts_default=max_attempts_default,
        backoff_seconds_default=backoff_seconds_default,
        max_backoff_seconds_default=max_backoff_seconds_default,
        supports_fields=True,
        field_help="Announcement field name passed to rqdatac.hk.get_announcement. Repeatable.",
        fields_file_help="Text file with one announcement field name per line. Repeatable.",
    )


def add_hk_southbound_mirror_args(
    parser: argparse.ArgumentParser,
    *,
    default_out_root: str,
    max_attempts_default: int,
    backoff_seconds_default: float,
    max_backoff_seconds_default: float,
) -> None:
    _add_rqdata_credentials_args(
        parser,
        config_help="Optional config path or alias for rqdata.init and default universe.",
    )
    parser.add_argument("--start-date", required=True, help="Date range start, for example 20141117.")
    parser.add_argument("--end-date", required=True, help="Date range end, for example 20260318.")
    _add_hk_symbol_selection_args(
        parser,
        symbol_help="HK symbol to keep, for example 00005.HK. Repeatable.",
        symbols_file_help="Text file with one HK symbol per line. If provided, this takes precedence over config universe symbols.",
        by_date_file_help="Universe-by-date CSV. If provided, both symbols and query dates are resolved from this file.",
    )
    parser.add_argument(
        "--trading-type",
        action="append",
        default=[],
        choices=["sh", "sz", "both"],
        help="Southbound channel to mirror. Repeatable. Default: both.",
    )
    parser.add_argument(
        "--rebalance-frequency",
        default="D",
        help="Snapshot frequency applied to resolved trading dates. Default: D. Use M/Q to sample fewer dates.",
    )
    _add_mirror_output_args(parser, default_out_root=default_out_root)
    _add_resume_args(
        parser,
        resume_help="Resume into an existing snapshot directory. Requires matching symbols, dates, and trading types.",
    )
    _add_retry_args(
        parser,
        max_attempts_default=max_attempts_default,
        backoff_seconds_default=backoff_seconds_default,
        max_backoff_seconds_default=max_backoff_seconds_default,
        attempts_help="Retry attempts per southbound request.",
    )


def add_hk_instrument_industry_mirror_args(
    parser: argparse.ArgumentParser,
    *,
    default_batch_size: int,
    default_out_root: str,
    max_attempts_default: int,
    backoff_seconds_default: float,
    max_backoff_seconds_default: float,
    default_industry_source: str,
    default_industry_level: int,
) -> None:
    add_hk_dated_mirror_args(
        parser,
        default_batch_size=default_batch_size,
        default_out_root=default_out_root,
        max_attempts_default=max_attempts_default,
        backoff_seconds_default=backoff_seconds_default,
        max_backoff_seconds_default=max_backoff_seconds_default,
    )
    parser.add_argument(
        "--source",
        default=default_industry_source,
        help=f"Industry taxonomy source passed to rqdatac.get_instrument_industry. Default: {default_industry_source}.",
    )
    parser.add_argument(
        "--level",
        default=str(default_industry_level),
        choices=["0", "1", "2", "3"],
        help="Industry hierarchy depth. 0 keeps first/second/third industry columns. Default: 0.",
    )
    parser.add_argument(
        "--rebalance-frequency",
        default="M",
        help="Snapshot frequency applied to resolved dates. Default: M. Use D to keep every date.",
    )


def add_hk_industry_changes_mirror_args(
    parser: argparse.ArgumentParser,
    *,
    default_batch_size: int,
    default_out_root: str,
    max_attempts_default: int,
    backoff_seconds_default: float,
    max_backoff_seconds_default: float,
    default_industry_source: str,
    default_change_level: int,
) -> None:
    add_hk_dated_mirror_args(
        parser,
        default_batch_size=default_batch_size,
        default_out_root=default_out_root,
        max_attempts_default=max_attempts_default,
        backoff_seconds_default=backoff_seconds_default,
        max_backoff_seconds_default=max_backoff_seconds_default,
    )
    parser.add_argument(
        "--source",
        default=default_industry_source,
        help=f"Industry taxonomy source passed to rqdatac.get_industry_change. Default: {default_industry_source}.",
    )
    parser.add_argument(
        "--level",
        default=str(default_change_level),
        choices=["1", "2", "3"],
        help="Industry hierarchy level used to enumerate mapping codes. Default: 1.",
    )
    parser.add_argument(
        "--mapping-date",
        help="Optional mapping as-of date used for get_industry_mapping. Default: --end-date.",
    )


def add_hk_financial_mirror_args(
    parser: argparse.ArgumentParser,
    *,
    default_batch_size: int,
    default_out_root: str,
    max_attempts_default: int,
    backoff_seconds_default: float,
    max_backoff_seconds_default: float,
) -> None:
    _add_rqdata_credentials_args(
        parser,
        config_help="Optional config path or alias for rqdata.init and default universe.",
    )
    parser.add_argument("--start-quarter", required=True, help="Quarter range start, for example 2011q1.")
    parser.add_argument("--end-quarter", required=True, help="Quarter range end, for example 2025q4.")
    parser.add_argument(
        "--date",
        help="Optional PIT as-of date. Use an absolute date such as 20260310 for reproducible mirrors.",
    )
    parser.add_argument(
        "--statements",
        default="latest",
        choices=["latest", "all"],
        help="Return latest or all statements for each quarter. Default: latest.",
    )
    parser.add_argument(
        "--field-profile",
        action="append",
        choices=["starter", "full"],
        default=[],
        help="Bundled HK financial field set. starter=repo baseline, full=all fields exposed by local rqdatac metadata.",
    )
    parser.add_argument(
        "--field",
        action="append",
        default=[],
        help="Financial field name. Repeatable.",
    )
    parser.add_argument(
        "--fields-file",
        action="append",
        default=[],
        help="Text file with one financial field per line. Repeatable.",
    )
    _add_hk_symbol_selection_args(
        parser,
        symbol_help="HK symbol to mirror, for example 00005.HK. Repeatable.",
        symbols_file_help="Text file with one HK symbol per line. If provided, this takes precedence over config universe symbols.",
        by_date_file_help="Universe-by-date CSV. If provided, this takes precedence over config universe symbols.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=default_batch_size,
        help=f"Number of order_book_ids per RQData request. Default: {default_batch_size}.",
    )
    _add_mirror_output_args(parser, default_out_root=default_out_root)
    _add_resume_args(
        parser,
        resume_help="Resume into an existing snapshot directory. Requires matching fields, symbols, and query settings.",
    )
    _add_retry_args(
        parser,
        max_attempts_default=max_attempts_default,
        backoff_seconds_default=backoff_seconds_default,
        max_backoff_seconds_default=max_backoff_seconds_default,
        attempts_help="Retry attempts per request batch.",
    )


def add_hk_pit_fundamentals_build_args(
    parser: argparse.ArgumentParser,
    *,
    default_pipeline_fundamentals_name: str,
) -> None:
    parser.add_argument(
        "--asset-dir",
        required=True,
        help="Path to a mirror-hk-pit-financials output directory.",
    )
    parser.add_argument(
        "--field-profile",
        action="append",
        choices=["starter", "full"],
        default=[],
        help="Bundled HK financial field set. starter=repo baseline, full=all fields exposed by local rqdatac metadata.",
    )
    parser.add_argument(
        "--field",
        action="append",
        default=[],
        help="Value field to keep in the output fundamentals file. Repeatable. Default: use asset manifest fields.",
    )
    parser.add_argument(
        "--fields-file",
        action="append",
        default=[],
        help="Text file with one financial field per line. Repeatable.",
    )
    parser.add_argument(
        "--out",
        help=(
            "Output file path. Default: <asset-dir>/"
            + default_pipeline_fundamentals_name
            + ". Use .csv to write CSV, otherwise Parquet."
        ),
    )
    parser.add_argument(
        "--source-universe-by-date",
        help="Optional source universe-by-date CSV. Use with --universe-by-date-out to derive a research-ready PIT universe.",
    )
    parser.add_argument(
        "--universe-by-date-out",
        help="Optional filtered universe-by-date CSV output. Requires --source-universe-by-date.",
    )
    parser.add_argument(
        "--symbols-out",
        help=(
            "Optional text file output with one canonical symbol per line for names present "
            "in the derived fundamentals file. Legacy ts_code inputs remain compatible."
        ),
    )
    parser.add_argument(
        "--keep-meta",
        action="store_true",
        help="Keep PIT metadata columns such as quarter, info_date, fiscal_year and rice_create_tm.",
    )
    parser.add_argument(
        "--duplicate-policy",
        choices=["keep-last", "error"],
        default="keep-last",
        help="How to handle duplicate trade_date + symbol rows after mapping trade_date=info_date.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )


def add_hk_industry_labels_build_args(
    parser: argparse.ArgumentParser,
    *,
    default_industry_labels_filename_prefix: str,
) -> None:
    parser.add_argument(
        "--asset-dir",
        required=True,
        help="Path to a mirror-hk-industry-changes output directory.",
    )
    parser.add_argument(
        "--source-universe-by-date",
        help="Optional universe-by-date CSV used as the exact date + symbol grid. Best for M/Q label files.",
    )
    parser.add_argument(
        "--daily-asset-dir",
        help="Optional local daily asset snapshot used to derive a daily trade_date + symbol grid.",
    )
    parser.add_argument(
        "--start-date",
        help="Optional lower date bound in YYYYMMDD. Applies to the selected source grid.",
    )
    parser.add_argument(
        "--end-date",
        help="Optional upper date bound in YYYYMMDD. Applies to the selected source grid.",
    )
    parser.add_argument(
        "--frequency",
        default="D",
        choices=["D", "M", "Q"],
        help="Output sampling frequency over the source grid. D keeps all dates, M/Q keep each symbol's last trade date per period. Default: D.",
    )
    parser.add_argument(
        "--out",
        help=(
            "Output file path. Default: <asset-dir>/"
            + default_industry_labels_filename_prefix
            + "_<freq>.parquet. Use .csv to write CSV, otherwise Parquet."
        ),
    )
    parser.add_argument(
        "--symbols-out",
        help=(
            "Optional text file output with one canonical symbol per line for names present "
            "in the derived label file. Legacy ts_code inputs remain compatible."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )


def add_hk_pit_coverage_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        help=(
            "Optional pipeline config path or alias. "
            "When provided, the command defaults to config fundamentals.file "
            "and uses fundamentals.features as the inspection feature set."
        ),
    )
    parser.add_argument(
        "--asset-dir",
        help="Optional PIT asset directory. Defaults to the parent of pipeline_fundamentals.parquet when possible.",
    )
    parser.add_argument(
        "--fundamentals-file",
        help="Optional pipeline fundamentals file path. Defaults to <asset-dir>/pipeline_fundamentals.parquet.",
    )
    parser.add_argument(
        "--field-profile",
        action="append",
        choices=["starter", "full"],
        default=[],
        help="Optional bundled field set. Useful when you want to inspect raw PIT columns instead of config features.",
    )
    parser.add_argument(
        "--field",
        action="append",
        default=[],
        help="Feature or raw PIT field to inspect. Repeatable.",
    )
    parser.add_argument(
        "--fields-file",
        action="append",
        default=[],
        help="Text file with one feature or raw PIT field per line. Repeatable.",
    )
    parser.add_argument(
        "--mode",
        default="strict",
        choices=["strict", "trainable", "both"],
        help=(
            "Coverage mode. strict keeps the current source-level complete-case check. "
            "trainable estimates PIT trainability after quarterly ffill + features.missing. "
            "both includes the trainable estimate alongside strict coverage. Default: strict."
        ),
    )
    parser.add_argument(
        "--min-symbols",
        type=int,
        help="Quarter viability threshold. Defaults to universe.min_symbols_per_date from --config, else 5.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Number of worst-coverage features shown in text output. Default: 10.",
    )
    parser.add_argument(
        "--quarter-limit",
        type=int,
        default=12,
        help="Number of recent quarters shown in text output. Default: 12.",
    )
    parser.add_argument(
        "--format",
        default="text",
        choices=["text", "json"],
        help="Output format. Default: text.",
    )
    parser.add_argument(
        "--out",
        help="Optional output path. Default: print to stdout.",
    )


def add_hk_asset_health_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--asset-dir",
        required=True,
        help="Path to a local HK asset snapshot directory containing data/.",
    )
    parser.add_argument(
        "--field",
        action="append",
        default=[],
        help=(
            "Value column to audit on the target date. Repeatable. "
            "Default: dataset-aware fields such as daily OHLCV or valuation ratios."
        ),
    )
    parser.add_argument(
        "--date-column",
        help="Override the date column name. Default: auto-detect trade_date/date/info_date.",
    )
    parser.add_argument(
        "--target-date",
        help=(
            "Optional target date in YYYYMMDD. Default: latest date from audit.csv when available, "
            "else manifest query date, else parquet scan max date."
        ),
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=5,
        help="Number of sample stale or missing symbols shown. Default: 5.",
    )
    parser.add_argument(
        "--top-latest-dates",
        type=int,
        default=5,
        help="Number of latest-date buckets shown in the summary. Default: 5.",
    )
    parser.add_argument(
        "--format",
        default="text",
        choices=["text", "json"],
        help="Output format. Default: text.",
    )
    parser.add_argument(
        "--out",
        help="Optional output path. Default: print to stdout.",
    )
