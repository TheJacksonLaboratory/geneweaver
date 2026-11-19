"""The analysis tool catalogue: `odestatic.tool` and `odestatic.tool_param` (G3-801)."""

from geneweaver.db.query import tool as tool_query
from geneweaver.db.utils import temp_override_row_factory
from psycopg import Cursor, rows


@temp_override_row_factory(rows.dict_row)
def get_tools(cursor: Cursor) -> list[dict]:
    """Every tool, in legacy's display order (``tool_sort``).

    :param cursor: The database cursor.
    :return: One dict per tool, keyed by column name.
    """
    cursor.execute(*tool_query.tools())
    return cursor.fetchall()


@temp_override_row_factory(rows.dict_row)
def get_tool_params(cursor: Cursor, classname: str | None = None) -> list[dict]:
    """Every tool parameter, or one tool's.

    :param cursor: The database cursor.
    :param classname: A legacy tool classname; every tool's parameters if None.
    :return: One dict per parameter, keyed by column name.
    """
    cursor.execute(*tool_query.tool_params(classname))
    return cursor.fetchall()
