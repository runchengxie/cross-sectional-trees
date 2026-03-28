from __future__ import annotations


def handle_data_catalog(args) -> int:
    from ..data_tools import data_warehouse

    return int(data_warehouse.refresh_catalog(args) or 0)


def handle_data_materialize(args) -> int:
    from ..data_tools import data_warehouse

    return int(data_warehouse.materialize_standardized(args) or 0)


def handle_data_query(args) -> int:
    from ..data_tools import data_warehouse

    return int(data_warehouse.query_standardized(args) or 0)


def register_data_command(subparsers) -> None:
    from ..data_tools import data_warehouse

    data = subparsers.add_parser(
        "data",
        help="Metadata catalog, standardized materialization, and DuckDB query helpers",
    )
    data_sub = data.add_subparsers(dest="data_command", required=True)

    data_catalog = data_sub.add_parser(
        "catalog",
        help="Scan manifest-backed assets into a SQLite metadata catalog",
    )
    data_warehouse.add_catalog_args(data_catalog)
    data_catalog.set_defaults(func=handle_data_catalog)

    data_materialize = data_sub.add_parser(
        "materialize",
        help="Build an analysis-ready standardized Parquet layer from raw or derived inputs",
    )
    data_warehouse.add_materialize_args(data_materialize)
    data_materialize.set_defaults(func=handle_data_materialize)

    data_query = data_sub.add_parser(
        "query",
        help="Refresh DuckDB standardized views and run a SQL query",
    )
    data_warehouse.add_query_args(data_query)
    data_query.set_defaults(func=handle_data_query)
