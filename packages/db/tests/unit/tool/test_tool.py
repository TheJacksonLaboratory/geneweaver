"""Test the tool catalogue functions (G3-801)."""

from geneweaver.db import tool
from geneweaver.db.query import tool as tool_query

from tests.unit.testing_utils import create_execute_raises_error_test


def test_tools_are_read_in_legacys_order(cursor):
    """All of odestatic.tool, ordered by tool_sort."""
    cursor.fetchall.return_value = [{"tool_classname": "PhenomeMap"}]

    assert tool.get_tools(cursor) == [{"tool_classname": "PhenomeMap"}]
    sql = cursor.execute.call_args.args[0].as_string(None)
    assert "FROM odestatic.tool " in sql
    assert sql.endswith("ORDER BY tool_sort, tool_classname")


def test_one_tools_parameters_are_filtered_by_classname(cursor):
    """The classname is a bound parameter, never formatted in."""
    tool.get_tool_params(cursor, "DBSCAN")

    sql, params = cursor.execute.call_args.args
    assert "WHERE tool_classname = %(classname)s" in sql.as_string(None)
    assert params == {"classname": "DBSCAN"}


def test_every_parameter_without_a_classname():
    """No filter; tp_html is not read."""
    sql, params = tool_query.tool_params()

    assert "WHERE" not in sql.as_string(None)
    assert "tp_html" not in sql.as_string(None)
    assert params == {}


test_get_tools_execute_raises_error = create_execute_raises_error_test(tool.get_tools)
