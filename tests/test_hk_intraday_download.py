from market_data_platform.hk_assets import intraday_download as platform_intraday_download

from cstree.research import hk_intraday_download


def test_hk_intraday_download_uses_market_data_platform_backend():
    assert hk_intraday_download.build_parser is platform_intraday_download.build_parser
    assert hk_intraday_download.download_hk_intraday_cache is (
        platform_intraday_download.download_hk_intraday_cache
    )
    assert hk_intraday_download.merge_batch_parts is platform_intraday_download.merge_batch_parts


def test_hk_intraday_download_parser_defaults_to_pre_adjusted_bars():
    parser = hk_intraday_download.build_parser()
    args = parser.parse_args(
        [
            "--symbols-file",
            "symbols.txt",
            "--start-date",
            "20250327",
            "--end-date",
            "20260326",
            "--output",
            "artifacts/cache/intraday/demo.parquet",
        ]
    )
    assert args.adjust_type == "pre"
