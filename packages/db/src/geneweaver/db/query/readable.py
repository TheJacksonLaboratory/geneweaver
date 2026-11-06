"""Which gene sets a user may read, as one SQL predicate shared by search and ABBA.

It is ``production.geneset_is_readable2``, written set-based. The function is right but
costs ~15 ms for each private gene set it decides, re-running the user's group and project
lookups every row: a sorted search checks every match (10,825 for "dopamine", 40 s). Here
the user's groups, shared projects and admin flag are looked up once per query.

Keep it in step with the function (``pg_get_functiondef('production.geneset_is_readable2'
::regproc)``). A gene set is readable when:

- the user owns it;
- it is public (``gs_groups = '0'``) or in a public tier (``cur_id < 5``);
- one of the user's groups shares it;
- one of the user's groups shares a project holding it;
- or the user is an admin or curator (``usr_admin > 0``), who reads every gene set.

Checked equal to the function on dev for anonymous, grouped, project-sharing, admin, curator
and ordinary users. ABBA used legacy's own rule before -- every group of the gene set had to
be one of the user's -- which hid a user's own private gene sets and admitted a gene set with
no groups to anyone; it reads this one now, as search and a tool run's access check do.
"""

from psycopg.sql import SQL, Composed


def readable_by(table: str = "geneset", param: str = "is_readable_by") -> Composed:
    """The predicate over a ``production.geneset`` alias, for the user in ``%(param)s``.

    :param table: The query's alias for ``production.geneset`` (a literal, never input).
    :param param: The name of the bound parameter holding the user id.
    """
    return SQL(
        """({table}.usr_id = %({param})s
        OR {table}.gs_groups = '0'
        OR {table}.cur_id < 5
        OR ('{{' || {table}.gs_groups || '}}')::integer[] && ARRAY(
            SELECT u2g.grp_id FROM production.usr2grp u2g
             WHERE u2g.usr_id = %({param})s)
        OR {table}.gs_id IN (
            SELECT p2g.gs_id FROM production.project2geneset p2g
              JOIN production.project p ON p.pj_id = p2g.pj_id
              JOIN production.usr2grp u2g
                ON u2g.grp_id = ANY(('{{' || p.pj_groups || '}}')::integer[])
             WHERE u2g.usr_id = %({param})s)
        OR EXISTS (
            SELECT 1 FROM production.usr u
             WHERE u.usr_admin > 0 AND u.usr_id = %({param})s))"""
    ).format(table=SQL(table), param=SQL(param))
