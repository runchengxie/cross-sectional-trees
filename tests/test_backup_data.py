from market_data_platform import backup_data as platform_backup_data

from cstree.data_tools import backup_data


def test_backup_data_uses_market_data_platform_backend():
    assert backup_data.main is platform_backup_data.main
    assert backup_data.add_backup_data_args is platform_backup_data.add_backup_data_args
