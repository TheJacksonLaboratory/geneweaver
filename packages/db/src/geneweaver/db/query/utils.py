"""Utility functions for the SQL generation functions."""

from datetime import date

from psycopg.sql import SQL, Composed, Identifier, Placeholder
from typing_extensions import LiteralString

SQLList = list[Composed | SQL]
ParamDict = dict[str, str | int | list]
OptionalParamDict = dict[str, str | int | None]
OptionalParamTuple = tuple[str, str | int | None]


def construct_filter(
    filters: SQLList,
    params: ParamDict,
    filter_name: str,
    filter_value: str | int | None,
    operator: LiteralString = "=",
    place_holder: str | None = None,
    table: str | None = None,
) -> tuple[SQLList, ParamDict]:
    """Construct a simple filter for a query.

    :param filters: The existing filters.
    :param params: The existing parameters.
    :param filter_name: The filter name to construct.
    :param filter_value: The filter value to construct.
    :param operator: sql operator
    :param place_holder: parameter placeholder name
    :param table: table name

    :return: The constructed filters and parameters.

    """
    if place_holder is None:
        place_holder = filter_name

    if filter_value is not None:
        if table:
            filter_str = SQL("{table}.{filter_name} {operator} {param_name}")
        else:
            filter_str = SQL("{filter_name} {operator} {param_name}")

        filters.append(
            filter_str.format(
                filter_name=Identifier(filter_name),
                param_name=Placeholder(place_holder),
                operator=SQL(operator),
                table=Identifier(table) if table else None,
            )
        )
        params[place_holder] = filter_value
    return filters, params


def construct_filters(
    filters: SQLList,
    params: ParamDict,
    filter_items: OptionalParamDict,
    table: str | None = None,
) -> tuple[SQLList, ParamDict]:
    """Construct multiple simple filters for a query.

    Calls the `construct_filter` function for each filter item.

    :param filters: The existing filters.
    :param params: The existing parameters.
    :param filter_items: The filter items to construct.
    :param table: table name

    :return: The constructed filters and parameters.
    """
    for filter_name, filter_value in filter_items.items():
        filters, params = construct_filter(filters, params, filter_name, filter_value, table=table)

    return filters, params


def add_op_filters(
    filters: SQLList,
    params: ParamDict,
    lte_count: int | None = None,
    gte_count: int | None = None,
    created_after: date | None = None,
    created_before: date | None = None,
    updated_after: date | None = None,
    updated_before: date | None = None,
    table: str | None = None,
) -> tuple[SQLList, ParamDict]:
    """Add multiple simple filters with operators to the query.

    :param filters: The existing filters.
    :param params: The existing parameters.
    :param lte_count: The count less than value.
    :param gte_count: The count greater than value.
    :param created_before: Show only results created before this date.
    :param created_after: Show only results updated before this date.
    :param updated_before: Show only results updated before this date.
    :param updated_after: Show only results updated after this date.
    :param table: table name
    """
    return construct_op_filters(
        filters=filters,
        params=params,
        filter_items=[
            {
                "field": "gs_count",
                "value": lte_count,
                "op": "<=",
                "place_holder": "count_less_than",
            },
            {
                "field": "gs_count",
                "value": gte_count,
                "op": ">=",
                "place_holder": "count_greater_than",
            },
            {
                "field": "gs_created",
                "value": created_before,
                "op": "<=",
                "place_holder": "created_before",
            },
            {
                "field": "gs_created",
                "value": created_after,
                "op": ">=",
                "place_holder": "created_after",
            },
            {
                "field": "gs_updated",
                "value": updated_before,
                "op": "<=",
                "place_holder": "updated_before",
            },
            {
                "field": "gs_updated",
                "value": updated_after,
                "op": ">=",
                "place_holder": "updated_after",
            },
        ],
        table=table,
    )


def construct_op_filters(
    filters: SQLList,
    params: ParamDict,
    filter_items: [dict],
    table: str | None = None,
) -> tuple[SQLList, ParamDict]:
    """Construct multiple simple filters with operators for a query.

    Calls the `construct_filter` function for each filter item.

    :param filters: The existing filters.
    :param params: The existing parameters.
    :param filter_items: The filter items to construct.
    :param table: table name

    :return: The constructed filters and parameters.
    """
    for filter_item in filter_items:
        filters, params = construct_filter(
            filters=filters,
            params=params,
            filter_name=filter_item.get("field"),
            filter_value=filter_item.get("value"),
            operator=filter_item.get("op"),
            place_holder=filter_item.get("place_holder"),
            table=table,
        )

    return filters, params
