from cstree import cli
from cstree.cli import rqdata as cli_rqdata
from cstree.data_tools import rqdata_assets as rqdata_assets_tool
from cstree.data_tools.rqdata_assets.command_registry import (
    RQDataAssetArgsBuilder,
    rqdata_asset_command_specs,
)


def test_cli_parses_rqdata_quota_pretty():
    parser = cli.build_parser()
    args = parser.parse_args(["rqdata", "quota", "--pretty"])
    assert args.command == "rqdata"
    assert args.rq_command == "quota"
    assert args.pretty is True


def test_cli_parses_rqdata_info():
    parser = cli.build_parser()
    rq_info = parser.parse_args(
        [
            "rqdata",
            "info",
            "--config",
            "configs/presets/hk.yml",
            "--username",
            "user",
            "--password",
            "pass",
        ]
    )
    assert rq_info.command == "rqdata"
    assert rq_info.rq_command == "info"
    assert rq_info.config == "configs/presets/hk.yml"
    assert rq_info.username == "user"
    assert rq_info.password == "pass"
    assert callable(rq_info.func)


def test_rqdata_asset_specs_expose_runner_and_argument_defaults():
    specs = {spec.name: spec for spec in rqdata_asset_command_specs()}

    daily = specs["mirror-hk-daily"]

    assert daily.runner.__name__ == "mirror_hk_daily"
    assert daily.requires_client is True
    assert isinstance(daily.add_args, RQDataAssetArgsBuilder)
    assert daily.add_args.kwargs["default_batch_size"] == 20
    assert daily.add_args.kwargs["default_out_root"].endswith("artifacts/assets/rqdata")


def test_rqdata_asset_package_facade_omits_argument_builders():
    assert hasattr(rqdata_assets_tool, "mirror_hk_daily")
    assert hasattr(rqdata_assets_tool, "inspect_hk_current_health")
    assert not hasattr(rqdata_assets_tool, "add_hk_daily_mirror_args")


def test_cli_parses_rqdata_asset_commands():
    parser = cli.build_parser()

    list_fields = parser.parse_args(
        [
            "rqdata",
            "list-hk-financial-fields",
            "--contains",
            "profit",
            "--out",
            "artifacts/exports/hk_fields.txt",
        ]
    )
    assert list_fields.command == "rqdata"
    assert list_fields.rq_command == "list-hk-financial-fields"
    assert list_fields.contains == ["profit"]
    assert list_fields.out == "artifacts/exports/hk_fields.txt"
    assert callable(list_fields.func)

    export_instruments = parser.parse_args(
        [
            "rqdata",
            "export-hk-instruments",
            "--config",
            "configs/presets/hk.yml",
            "--instrument-type",
            "ETF",
            "--use-config-universe",
            "--limit",
            "100",
            "--out",
            "artifacts/assets/rqdata/hk/instruments/demo.parquet",
            "--force",
        ]
    )
    assert export_instruments.command == "rqdata"
    assert export_instruments.rq_command == "export-hk-instruments"
    assert export_instruments.config == "configs/presets/hk.yml"
    assert export_instruments.instrument_type == "ETF"
    assert export_instruments.use_config_universe is True
    assert export_instruments.limit == 100
    assert export_instruments.out == "artifacts/assets/rqdata/hk/instruments/demo.parquet"
    assert export_instruments.force is True
    assert callable(export_instruments.func)

    daily = parser.parse_args(
        [
            "rqdata",
            "mirror-hk-daily",
            "--by-date-file",
            "artifacts/assets/universe/hk_connect_full_by_date.csv",
            "--start-date",
            "20000101",
            "--end-date",
            "20260311",
            "--field",
            "vwap",
            "--batch-size",
            "50",
            "--resume",
            "--include-suspended",
            "--name",
            "daily_demo",
        ]
    )
    assert daily.command == "rqdata"
    assert daily.rq_command == "mirror-hk-daily"
    assert daily.by_date_file == "artifacts/assets/universe/hk_connect_full_by_date.csv"
    assert daily.start_date == "20000101"
    assert daily.end_date == "20260311"
    assert daily.field == ["vwap"]
    assert daily.batch_size == 50
    assert daily.resume is True
    assert daily.skip_suspended is False
    assert daily.name == "daily_demo"
    assert callable(daily.func)

    pit = parser.parse_args(
        [
            "rqdata",
            "mirror-hk-pit-financials",
            "--config",
            "configs/presets/hk.yml",
            "--field-profile",
            "full",
            "--fields-file",
            "configs/field_profiles/hk_financial_fields_starter.txt",
            "--start-quarter",
            "2011q1",
            "--end-quarter",
            "2025q4",
            "--date",
            "20260310",
            "--batch-size",
            "10",
            "--resume",
            "--max-attempts",
            "5",
            "--backoff-seconds",
            "0.25",
            "--max-backoff-seconds",
            "2.0",
            "--name",
            "pit_demo",
        ]
    )
    assert pit.command == "rqdata"
    assert pit.rq_command == "mirror-hk-pit-financials"
    assert pit.config == "configs/presets/hk.yml"
    assert pit.field_profile == ["full"]
    assert pit.fields_file == ["configs/field_profiles/hk_financial_fields_starter.txt"]
    assert pit.start_quarter == "2011q1"
    assert pit.end_quarter == "2025q4"
    assert pit.batch_size == 10
    assert pit.resume is True
    assert pit.skip_existing is False
    assert pit.max_attempts == 5
    assert pit.backoff_seconds == 0.25
    assert pit.max_backoff_seconds == 2.0
    assert pit.name == "pit_demo"
    assert callable(pit.func)

    details = parser.parse_args(
        [
            "rqdata",
            "mirror-hk-financial-details",
            "--symbol",
            "00005.HK",
            "--field",
            "revenue",
            "--start-quarter",
            "2024q1",
            "--end-quarter",
            "2025q4",
        ]
    )
    assert details.command == "rqdata"
    assert details.rq_command == "mirror-hk-financial-details"
    assert details.symbol == ["00005.HK"]
    assert details.field == ["revenue"]
    assert details.start_quarter == "2024q1"
    assert details.end_quarter == "2025q4"
    assert callable(details.func)

    ex_factors = parser.parse_args(
        [
            "rqdata",
            "mirror-hk-ex-factors",
            "--symbol",
            "00005.HK",
            "--start-date",
            "20100101",
            "--end-date",
            "20260317",
            "--batch-size",
            "5",
            "--resume",
        ]
    )
    assert ex_factors.command == "rqdata"
    assert ex_factors.rq_command == "mirror-hk-ex-factors"
    assert ex_factors.symbol == ["00005.HK"]
    assert ex_factors.start_date == "20100101"
    assert ex_factors.end_date == "20260317"
    assert ex_factors.batch_size == 5
    assert ex_factors.resume is True
    assert callable(ex_factors.func)

    dividends = parser.parse_args(
        [
            "rqdata",
            "mirror-hk-dividends",
            "--by-date-file",
            "artifacts/assets/universe/hk_connect_full_by_date.csv",
            "--start-date",
            "20100101",
            "--end-date",
            "20260317",
        ]
    )
    assert dividends.command == "rqdata"
    assert dividends.rq_command == "mirror-hk-dividends"
    assert dividends.by_date_file == "artifacts/assets/universe/hk_connect_full_by_date.csv"
    assert dividends.start_date == "20100101"
    assert dividends.end_date == "20260317"
    assert callable(dividends.func)

    shares = parser.parse_args(
        [
            "rqdata",
            "mirror-hk-shares",
            "--config",
            "configs/presets/hk.yml",
            "--field",
            "free_float",
            "--start-date",
            "20100101",
            "--end-date",
            "20260317",
            "--name",
            "shares_demo",
        ]
    )
    assert shares.command == "rqdata"
    assert shares.rq_command == "mirror-hk-shares"
    assert shares.config == "configs/presets/hk.yml"
    assert shares.field == ["free_float"]
    assert shares.start_date == "20100101"
    assert shares.end_date == "20260317"
    assert shares.name == "shares_demo"
    assert callable(shares.func)

    announcement = parser.parse_args(
        [
            "rqdata",
            "mirror-hk-announcement",
            "--symbols-file",
            "artifacts/assets/universe/hk_selected_pit_research_symbols.txt",
            "--start-date",
            "20250101",
            "--end-date",
            "20250331",
            "--field",
            "title",
            "--batch-size",
            "10",
            "--resume",
        ]
    )
    assert announcement.command == "rqdata"
    assert announcement.rq_command == "mirror-hk-announcement"
    assert announcement.symbols_file == "artifacts/assets/universe/hk_selected_pit_research_symbols.txt"
    assert announcement.start_date == "20250101"
    assert announcement.end_date == "20250331"
    assert announcement.field == ["title"]
    assert announcement.batch_size == 10
    assert announcement.resume is True
    assert callable(announcement.func)

    southbound = parser.parse_args(
        [
            "rqdata",
            "mirror-hk-southbound",
            "--by-date-file",
            "artifacts/assets/universe/hk_connect_full_by_date.csv",
            "--start-date",
            "20250101",
            "--end-date",
            "20250331",
            "--trading-type",
            "both",
            "--rebalance-frequency",
            "M",
            "--resume",
        ]
    )
    assert southbound.command == "rqdata"
    assert southbound.rq_command == "mirror-hk-southbound"
    assert southbound.by_date_file == "artifacts/assets/universe/hk_connect_full_by_date.csv"
    assert southbound.start_date == "20250101"
    assert southbound.end_date == "20250331"
    assert southbound.trading_type == ["both"]
    assert southbound.rebalance_frequency == "M"
    assert southbound.resume is True
    assert callable(southbound.func)

    instrument_industry = parser.parse_args(
        [
            "rqdata",
            "mirror-hk-instrument-industry",
            "--by-date-file",
            "artifacts/assets/universe/hk_connect_full_by_date.csv",
            "--start-date",
            "20250101",
            "--end-date",
            "20251231",
            "--level",
            "0",
            "--rebalance-frequency",
            "M",
        ]
    )
    assert instrument_industry.command == "rqdata"
    assert instrument_industry.rq_command == "mirror-hk-instrument-industry"
    assert instrument_industry.by_date_file == "artifacts/assets/universe/hk_connect_full_by_date.csv"
    assert instrument_industry.start_date == "20250101"
    assert instrument_industry.end_date == "20251231"
    assert instrument_industry.level == "0"
    assert instrument_industry.rebalance_frequency == "M"
    assert callable(instrument_industry.func)

    industry_changes = parser.parse_args(
        [
            "rqdata",
            "mirror-hk-industry-changes",
            "--symbol",
            "00005.HK",
            "--start-date",
            "20250101",
            "--end-date",
            "20251231",
            "--level",
            "1",
            "--mapping-date",
            "20251231",
        ]
    )
    assert industry_changes.command == "rqdata"
    assert industry_changes.rq_command == "mirror-hk-industry-changes"
    assert industry_changes.symbol == ["00005.HK"]
    assert industry_changes.start_date == "20250101"
    assert industry_changes.end_date == "20251231"
    assert industry_changes.level == "1"
    assert industry_changes.mapping_date == "20251231"
    assert callable(industry_changes.func)

    valuation = parser.parse_args(
        [
            "rqdata",
            "mirror-hk-valuation",
            "--symbols-file",
            "artifacts/assets/universe/hk_all_full_symbols.txt",
            "--start-date",
            "20000101",
            "--end-date",
            "20260324",
            "--field",
            "ps_ratio_ttm",
            "--batch-size",
            "10",
            "--name",
            "hk_all_2000_20260324_valuation_full_market_latest",
            "--resume",
        ]
    )
    assert valuation.command == "rqdata"
    assert valuation.rq_command == "mirror-hk-valuation"
    assert valuation.symbols_file == "artifacts/assets/universe/hk_all_full_symbols.txt"
    assert valuation.start_date == "20000101"
    assert valuation.end_date == "20260324"
    assert valuation.field == ["ps_ratio_ttm"]
    assert valuation.batch_size == 10
    assert valuation.name == "hk_all_2000_20260324_valuation_full_market_latest"
    assert valuation.resume is True
    assert callable(valuation.func)

    pit_fundamentals = parser.parse_args(
        [
            "rqdata",
            "build-hk-pit-fundamentals",
            "--asset-dir",
            "artifacts/assets/rqdata/hk/pit_financials/pit_demo",
            "--field-profile",
            "starter",
            "--field",
            "revenue",
            "--field",
            "net_profit",
            "--out",
            "artifacts/assets/fundamentals/pit_fundamentals.parquet",
            "--source-universe-by-date",
            "artifacts/assets/universe/hk_connect_full_by_date.csv",
            "--universe-by-date-out",
            "artifacts/assets/universe/hk_connect_full_research_by_date.csv",
            "--max-latest-report-age-days",
            "365",
            "--symbols-out",
            "artifacts/assets/universe/hk_connect_full_research_symbols.txt",
            "--keep-meta",
            "--duplicate-policy",
            "error",
            "--force",
        ]
    )
    assert pit_fundamentals.command == "rqdata"
    assert pit_fundamentals.rq_command == "build-hk-pit-fundamentals"
    assert pit_fundamentals.asset_dir == "artifacts/assets/rqdata/hk/pit_financials/pit_demo"
    assert pit_fundamentals.field_profile == ["starter"]
    assert pit_fundamentals.field == ["revenue", "net_profit"]
    assert pit_fundamentals.out == "artifacts/assets/fundamentals/pit_fundamentals.parquet"
    assert pit_fundamentals.source_universe_by_date == "artifacts/assets/universe/hk_connect_full_by_date.csv"
    assert pit_fundamentals.universe_by_date_out == "artifacts/assets/universe/hk_connect_full_research_by_date.csv"
    assert pit_fundamentals.max_latest_report_age_days == 365
    assert pit_fundamentals.symbols_out == "artifacts/assets/universe/hk_connect_full_research_symbols.txt"
    assert pit_fundamentals.keep_meta is True
    assert pit_fundamentals.duplicate_policy == "error"
    assert pit_fundamentals.force is True
    assert callable(pit_fundamentals.func)

    industry_labels = parser.parse_args(
        [
            "rqdata",
            "build-hk-industry-labels",
            "--asset-dir",
            "artifacts/assets/rqdata/hk/industry_changes/demo",
            "--source-universe-by-date",
            "artifacts/assets/universe/hk_connect_full_by_date.csv",
            "--frequency",
            "M",
            "--out",
            "artifacts/assets/industry/industry_labels_m.parquet",
            "--symbols-out",
            "artifacts/assets/industry/industry_symbols.txt",
            "--force",
        ]
    )
    assert industry_labels.command == "rqdata"
    assert industry_labels.rq_command == "build-hk-industry-labels"
    assert industry_labels.asset_dir == "artifacts/assets/rqdata/hk/industry_changes/demo"
    assert industry_labels.source_universe_by_date == "artifacts/assets/universe/hk_connect_full_by_date.csv"
    assert industry_labels.frequency == "M"
    assert industry_labels.out == "artifacts/assets/industry/industry_labels_m.parquet"
    assert industry_labels.symbols_out == "artifacts/assets/industry/industry_symbols.txt"
    assert industry_labels.force is True
    assert callable(industry_labels.func)

    pit_coverage = parser.parse_args(
        [
            "rqdata",
            "inspect-hk-pit-coverage",
            "--config",
            "configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml",
            "--mode",
            "trainable",
            "--include-health",
            "--target-date",
            "20260331",
            "--symbols-file",
            "artifacts/assets/universe/hk_selected_symbols.txt",
            "--by-date-file",
            "artifacts/assets/universe/hk_selected_by_date.csv",
            "--health-sample-limit",
            "6",
            "--min-symbols",
            "10",
            "--fail-on-severity",
            "warning",
            "--format",
            "json",
            "--out",
            "artifacts/reports/hk_pit_coverage.json",
        ]
    )
    assert pit_coverage.command == "rqdata"
    assert pit_coverage.rq_command == "inspect-hk-pit-coverage"
    assert pit_coverage.config == "configs/experiments/baseline/hk_selected__quarterly_pit_core_hybrid.yml"
    assert pit_coverage.mode == "trainable"
    assert pit_coverage.include_health is True
    assert pit_coverage.target_date == "20260331"
    assert pit_coverage.symbols_file == "artifacts/assets/universe/hk_selected_symbols.txt"
    assert pit_coverage.by_date_file == "artifacts/assets/universe/hk_selected_by_date.csv"
    assert pit_coverage.health_sample_limit == 6
    assert pit_coverage.min_symbols == 10
    assert pit_coverage.fail_on_severity == "warning"
    assert pit_coverage.format == "json"
    assert pit_coverage.out == "artifacts/reports/hk_pit_coverage.json"
    assert callable(pit_coverage.func)

    asset_health = parser.parse_args(
        [
            "rqdata",
            "inspect-hk-asset-health",
            "--asset-dir",
            "artifacts/assets/rqdata/hk/valuation/demo",
            "--symbols-file",
            "artifacts/assets/rqdata/hk/valuation/demo_symbols.txt",
            "--by-date-file",
            "artifacts/assets/universe/demo_by_date.csv",
            "--field",
            "pe_ratio_ttm",
            "--field",
            "pb_ratio_ttm",
            "--target-date",
            "20260331",
            "--daily-asset-dir",
            "artifacts/assets/rqdata/hk/daily/demo",
            "--sample-limit",
            "8",
            "--top-latest-dates",
            "3",
            "--include-history",
            "--history-sample-limit",
            "4",
            "--fail-on-severity",
            "error",
            "--format",
            "json",
            "--out",
            "artifacts/reports/hk_asset_health.json",
        ]
    )
    assert asset_health.command == "rqdata"
    assert asset_health.rq_command == "inspect-hk-asset-health"
    assert asset_health.asset_dir == "artifacts/assets/rqdata/hk/valuation/demo"
    assert asset_health.symbols_file == "artifacts/assets/rqdata/hk/valuation/demo_symbols.txt"
    assert asset_health.by_date_file == "artifacts/assets/universe/demo_by_date.csv"
    assert asset_health.field == ["pe_ratio_ttm", "pb_ratio_ttm"]
    assert asset_health.target_date == "20260331"
    assert asset_health.daily_asset_dir == "artifacts/assets/rqdata/hk/daily/demo"
    assert asset_health.sample_limit == 8
    assert asset_health.top_latest_dates == 3
    assert asset_health.include_history is True
    assert asset_health.history_sample_limit == 4
    assert asset_health.fail_on_severity == "error"
    assert asset_health.format == "json"
    assert asset_health.out == "artifacts/reports/hk_asset_health.json"
    assert callable(asset_health.func)

    current_health = parser.parse_args(
        [
            "rqdata",
            "inspect-hk-current-health",
            "--artifacts-root",
            "artifacts",
            "--current-contract",
            "artifacts/metadata/current_assets/hk_current.json",
            "--asset",
            "daily_clean",
            "--asset",
            "universe_meta",
            "--target-date",
            "20260409",
            "--fail-on-severity",
            "warning",
            "--format",
            "json",
            "--out",
            "artifacts/reports/hk_current_health.json",
        ]
    )
    assert current_health.command == "rqdata"
    assert current_health.rq_command == "inspect-hk-current-health"
    assert current_health.artifacts_root == "artifacts"
    assert current_health.current_contract == "artifacts/metadata/current_assets/hk_current.json"
    assert current_health.asset == ["daily_clean", "universe_meta"]
    assert current_health.target_date == "20260409"
    assert current_health.fail_on_severity == "warning"
    assert current_health.format == "json"
    assert current_health.out == "artifacts/reports/hk_current_health.json"
    assert callable(current_health.func)

    data_asset_audit = parser.parse_args(
        [
            "rqdata",
            "inspect-hk-data-assets",
            "--artifacts-root",
            "artifacts",
            "--target-date",
            "20260410",
            "--asset",
            "etf_daily",
            "--scan-family",
            "daily",
            "--intraday-mode",
            "scan",
            "--health-report",
            "artifacts/reports/hk_current_health_20260410.json",
            "--run-refresh",
            "--refresh-mode",
            "patch",
            "--refresh-asset",
            "daily",
            "--refresh-dry-run",
            "--approved-repair-action",
            "patch-refresh",
            "--approved-prune-path",
            "artifacts/assets/rqdata/hk/daily/old_patch",
            "--sample-limit",
            "9",
            "--fail-on-severity",
            "warning",
            "--format",
            "json",
            "--out",
            "artifacts/reports/hk_data_asset_audit_20260410.json",
        ]
    )
    assert data_asset_audit.command == "rqdata"
    assert data_asset_audit.rq_command == "inspect-hk-data-assets"
    assert data_asset_audit.artifacts_root == "artifacts"
    assert data_asset_audit.target_date == "20260410"
    assert data_asset_audit.asset == ["etf_daily"]
    assert data_asset_audit.scan_family == ["daily"]
    assert data_asset_audit.intraday_mode == "scan"
    assert data_asset_audit.health_report == ["artifacts/reports/hk_current_health_20260410.json"]
    assert data_asset_audit.run_refresh is True
    assert data_asset_audit.refresh_mode == "patch"
    assert data_asset_audit.refresh_asset == ["daily"]
    assert data_asset_audit.refresh_dry_run is True
    assert data_asset_audit.approved_repair_action == ["patch-refresh"]
    assert data_asset_audit.approved_prune_path == ["artifacts/assets/rqdata/hk/daily/old_patch"]
    assert data_asset_audit.sample_limit == 9
    assert data_asset_audit.fail_on_severity == "warning"
    assert data_asset_audit.format == "json"
    assert data_asset_audit.out == "artifacts/reports/hk_data_asset_audit_20260410.json"
    assert callable(data_asset_audit.func)

    intraday_health = parser.parse_args(
        [
            "rqdata",
            "inspect-hk-intraday-health",
            "--input",
            "artifacts/cache/intraday/hk_all_5m_20260327_20260401.parquet",
            "--input",
            "artifacts/cache/intraday/hk_all_5m_2026.parquet",
            "--daily-asset-dir",
            "artifacts/assets/rqdata/hk/daily/hk_all_daily_latest",
            "--sample-limit",
            "7",
            "--expected-bars-per-day",
            "66",
            "--numeric-rtol",
            "0.001",
            "--numeric-atol",
            "0.01",
            "--fail-on-severity",
            "info",
            "--format",
            "json",
            "--out",
            "artifacts/reports/hk_intraday_health.json",
        ]
    )
    assert intraday_health.command == "rqdata"
    assert intraday_health.rq_command == "inspect-hk-intraday-health"
    assert intraday_health.input == [
        "artifacts/cache/intraday/hk_all_5m_20260327_20260401.parquet",
        "artifacts/cache/intraday/hk_all_5m_2026.parquet",
    ]
    assert intraday_health.daily_asset_dir == "artifacts/assets/rqdata/hk/daily/hk_all_daily_latest"
    assert intraday_health.sample_limit == 7
    assert intraday_health.expected_bars_per_day == 66
    assert intraday_health.numeric_rtol == 0.001
    assert intraday_health.numeric_atol == 0.01
    assert intraday_health.fail_on_severity == "info"
    assert intraday_health.format == "json"
    assert intraday_health.out == "artifacts/reports/hk_intraday_health.json"
    assert callable(intraday_health.func)

    intraday_asset = parser.parse_args(
        [
            "rqdata",
            "build-hk-intraday-asset",
            "--input",
            "artifacts/cache/intraday/hk_all_5m_20260327_20260401.parquet",
            "--input",
            "artifacts/cache/intraday/hk_connect_research_5m_20250317_20260317.parquet",
            "--out-root",
            "artifacts/assets/rqdata",
            "--name",
            "hk_intraday_formal_latest",
            "--alias",
            "artifacts/assets/rqdata/hk/intraday/hk_intraday_latest",
        ]
    )
    assert intraday_asset.command == "rqdata"
    assert intraday_asset.rq_command == "build-hk-intraday-asset"
    assert intraday_asset.input == [
        "artifacts/cache/intraday/hk_all_5m_20260327_20260401.parquet",
        "artifacts/cache/intraday/hk_connect_research_5m_20250317_20260317.parquet",
    ]
    assert intraday_asset.out_root == "artifacts/assets/rqdata"
    assert intraday_asset.name == "hk_intraday_formal_latest"
    assert intraday_asset.alias == "artifacts/assets/rqdata/hk/intraday/hk_intraday_latest"
    assert callable(intraday_asset.func)

    intraday_sync = parser.parse_args(
        [
            "rqdata",
            "sync-hk-intraday",
            "--config",
            "configs/presets/hk.yml",
            "--symbols-file",
            "artifacts/assets/rqdata/hk/daily/hk_all_daily_latest/symbols.txt",
            "--start-date",
            "20260402",
            "--end-date",
            "20260409",
            "--output",
            "artifacts/cache/intraday/hk_all_5m_20260402_20260409.parquet",
            "--resume",
            "--inspect-fail-on-severity",
            "error",
            "--verify-full-asset",
            "--full-health-out",
            "artifacts/reports/hk_intraday_latest_health.json",
            "--full-inspect-fail-on-severity",
            "none",
            "--asset-name",
            "hk_all_5m_20260402_20260409_latest",
            "--package",
            "--release",
            "--repo",
            "owner/name",
            "--tag",
            "hk-intraday-20260409",
        ]
    )
    assert intraday_sync.command == "rqdata"
    assert intraday_sync.rq_command == "sync-hk-intraday"
    assert intraday_sync.config == "configs/presets/hk.yml"
    assert intraday_sync.symbols_file == "artifacts/assets/rqdata/hk/daily/hk_all_daily_latest/symbols.txt"
    assert intraday_sync.start_date == "20260402"
    assert intraday_sync.end_date == "20260409"
    assert intraday_sync.output == "artifacts/cache/intraday/hk_all_5m_20260402_20260409.parquet"
    assert intraday_sync.resume is True
    assert intraday_sync.inspect_fail_on_severity == "error"
    assert intraday_sync.verify_full_asset is True
    assert intraday_sync.full_health_out == "artifacts/reports/hk_intraday_latest_health.json"
    assert intraday_sync.full_inspect_fail_on_severity == "none"
    assert intraday_sync.asset_name == "hk_all_5m_20260402_20260409_latest"
    assert intraday_sync.package is True
    assert intraday_sync.release is True
    assert intraday_sync.repo == "owner/name"
    assert intraday_sync.tag == "hk-intraday-20260409"
    assert callable(intraday_sync.func)

    daily_clean = parser.parse_args(
        [
            "rqdata",
            "build-hk-daily-clean-layer",
            "--asset-dir",
            "artifacts/assets/rqdata/hk/daily/hk_all_daily_latest",
            "--out-dir",
            "artifacts/assets/rqdata/hk/daily/hk_all_daily_clean_20260402",
            "--alias",
            "artifacts/assets/rqdata/hk/daily/hk_all_daily_clean_latest",
            "--symbols-file",
            "artifacts/assets/rqdata/hk/daily/hk_all_daily_latest/symbols.txt",
            "--instruments-file",
            "artifacts/assets/rqdata/hk/instruments/hk_etf_instruments_latest.parquet",
            "--zero-price-min-run",
            "7",
            "--etf-short-zero-max-run",
            "3",
            "--overwrite",
        ]
    )
    assert daily_clean.command == "rqdata"
    assert daily_clean.rq_command == "build-hk-daily-clean-layer"
    assert daily_clean.asset_dir == "artifacts/assets/rqdata/hk/daily/hk_all_daily_latest"
    assert daily_clean.out_dir == "artifacts/assets/rqdata/hk/daily/hk_all_daily_clean_20260402"
    assert daily_clean.alias == "artifacts/assets/rqdata/hk/daily/hk_all_daily_clean_latest"
    assert daily_clean.symbols_file == "artifacts/assets/rqdata/hk/daily/hk_all_daily_latest/symbols.txt"
    assert daily_clean.instruments_file == "artifacts/assets/rqdata/hk/instruments/hk_etf_instruments_latest.parquet"
    assert daily_clean.zero_price_min_run == 7
    assert daily_clean.etf_short_zero_max_run == 3
    assert daily_clean.overwrite is True
    assert callable(daily_clean.func)


def test_cli_main_rqdata_info_prints_client_info(monkeypatch, capsys):
    class _FakeClient:
        def info(self):
            return {"user": "demo"}

    monkeypatch.setattr(cli_rqdata, "init_rqdatac", lambda args: _FakeClient())

    assert cli.main(["rqdata", "info"]) == 0
    assert capsys.readouterr().out.strip() == "{'user': 'demo'}"


def test_cli_main_rqdata_export_hk_instruments_passes_args_and_client(monkeypatch):
    calls: list[tuple[object, object]] = []
    fake_client = object()

    monkeypatch.setattr(cli_rqdata, "init_rqdatac", lambda args: fake_client)
    monkeypatch.setattr(
        rqdata_assets_tool,
        "export_hk_instruments",
        lambda args, rqdatac: calls.append((args, rqdatac)) or 0,
    )

    assert (
        cli.main(
            [
                "rqdata",
                "export-hk-instruments",
                "--limit",
                "10",
                "--config",
                "configs/presets/hk.yml",
            ]
        )
        == 0
    )
    assert len(calls) == 1
    args, rqdatac = calls[0]
    assert args.limit == 10
    assert args.config == "configs/presets/hk.yml"
    assert rqdatac is fake_client


def test_cli_main_rqdata_mirror_hk_exchange_rate_passes_args_and_client(monkeypatch):
    calls: list[tuple[object, object]] = []
    fake_client = object()

    monkeypatch.setattr(cli_rqdata, "init_rqdatac", lambda args: fake_client)
    monkeypatch.setattr(
        rqdata_assets_tool,
        "mirror_hk_exchange_rate",
        lambda args, rqdatac: calls.append((args, rqdatac)) or 0,
    )

    assert (
        cli.main(
            [
                "rqdata",
                "mirror-hk-exchange-rate",
                "--start-date",
                "20000101",
                "--end-date",
                "20260319",
                "--config",
                "configs/presets/hk.yml",
            ]
        )
        == 0
    )
    assert len(calls) == 1
    args, rqdatac = calls[0]
    assert args.start_date == "20000101"
    assert args.end_date == "20260319"
    assert args.config == "configs/presets/hk.yml"
    assert rqdatac is fake_client
