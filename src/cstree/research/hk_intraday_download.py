from __future__ import annotations

import sys

from cstree._mdp_compat import load_market_data_platform_module

_mdp_intraday_download = load_market_data_platform_module("hk_assets.intraday_download")

ADJUST_TYPE_CHOICES = _mdp_intraday_download.ADJUST_TYPE_CHOICES
DEFAULT_FIELDS = _mdp_intraday_download.DEFAULT_FIELDS
REPO_ROOT = _mdp_intraday_download.REPO_ROOT
_read_symbol_file = _mdp_intraday_download._read_symbol_file
build_parser = _mdp_intraday_download.build_parser
download_hk_intraday_cache = _mdp_intraday_download.download_hk_intraday_cache
merge_batch_parts = _mdp_intraday_download.merge_batch_parts


def main() -> None:
    print(
        "python -m cstree.research.hk_intraday_download is a compatibility wrapper; "
        "use marketdata rqdata refresh-hk-intraday or "
        "python -m market_data_platform.hk_assets.intraday_download.",
        file=sys.stderr,
    )
    _mdp_intraday_download.main()


if __name__ == "__main__":
    main()
