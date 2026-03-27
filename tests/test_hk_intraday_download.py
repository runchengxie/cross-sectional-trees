from csml.research.hk_intraday_download import build_parser


def test_hk_intraday_download_parser_defaults_to_pre_adjusted_bars():
    parser = build_parser()
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


def test_hk_intraday_download_parser_accepts_none_adjustment():
    parser = build_parser()
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
            "--adjust-type",
            "none",
        ]
    )
    assert args.adjust_type == "none"
