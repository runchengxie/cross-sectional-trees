from market_data_platform import data_warehouse as platform_data_warehouse

from cstree.data_tools import data_warehouse


def test_data_warehouse_uses_market_data_platform_backend():
    assert data_warehouse.refresh_catalog is platform_data_warehouse.refresh_catalog
    assert data_warehouse.materialize_standardized is platform_data_warehouse.materialize_standardized
    assert data_warehouse.query_standardized is platform_data_warehouse.query_standardized
