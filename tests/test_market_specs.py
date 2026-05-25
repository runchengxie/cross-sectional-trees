import pytest

from cstree.data_provider_contracts import require_supported_market, to_rqdata_symbol
from cstree.data_tools.symbols import normalize_symbol_for_market


def test_cn_symbols_map_between_canonical_and_rqdata_ids():
    assert normalize_symbol_for_market("600000.XSHG", market="cn") == "600000.SH"
    assert normalize_symbol_for_market("000001.XSHE", market="cn") == "000001.SZ"
    assert normalize_symbol_for_market("600519.sh", market="cn") == "600519.SH"
    assert normalize_symbol_for_market("1", market="cn") == "000001.SZ"

    assert to_rqdata_symbol("cn", "600000.SH") == "600000.XSHG"
    assert to_rqdata_symbol("cn", "000001.SZ") == "000001.XSHE"
    assert to_rqdata_symbol("cn", "600000") == "600000.XSHG"
    assert to_rqdata_symbol("cn", "000001") == "000001.XSHE"


def test_supported_markets_include_cn_and_reject_unknown():
    assert require_supported_market("cn") == "cn"
    assert require_supported_market("hk") == "hk"
    with pytest.raises(ValueError, match="Supported markets: cn, hk"):
        require_supported_market("us")
