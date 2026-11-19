"""Generate SQL queries over the analysis tool catalogue: `odestatic.tool` and `tool_param`.

Legacy's forms were built from these tables (`geneweaverdb.get_tool`, `get_tool_params`);
v3 reads them so the analysis page can build its forms from data as well (G3-801).
"""

from psycopg.sql import SQL


def tools() -> tuple[SQL, dict]:
    """Every tool, in legacy's display order.

    :return: A query (and params) that can be executed on a cursor.
    """
    return (
        SQL(
            "SELECT tool_classname, tool_name, tool_description, tool_requirements, "
            "tool_active, tool_sort FROM odestatic.tool ORDER BY tool_sort, tool_classname"
        ),
        {},
    )


def tool_params(classname: str | None = None) -> tuple[SQL, dict]:
    """Every tool parameter, or one tool's.

    ``tp_html`` is left out: no reader, legacy included, uses it.

    :param classname: A legacy tool classname (`odestatic.tool.tool_classname`).
    :return: A query (and params) that can be executed on a cursor.
    """
    query = (
        "SELECT tool_classname, tp_name, tp_description, tp_default, tp_options, tp_seltype, "
        "tp_visible FROM odestatic.tool_param"
    )
    params: dict = {}
    if classname is not None:
        query += " WHERE tool_classname = %(classname)s"
        params["classname"] = classname
    return SQL(query + " ORDER BY tool_classname, tp_name"), params
