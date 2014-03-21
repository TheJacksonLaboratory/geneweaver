from psycopg2.pool import ThreadedConnectionPool
from collections import OrderedDict

class MyThreadedConnectionPool(ThreadedConnectionPool):
    """Extend ThreadedConnectionPool to initialize the search_path"""
    def __init__(self, minconn, maxconn, *args, **kwargs):
        ThreadedConnectionPool.__init__(self, minconn, maxconn, *args, **kwargs)

    def _connect(self, key=None):
        """Create a new connection and set its search_path"""
        conn = super(MyThreadedConnectionPool, self)._connect(key)
        cursor = conn.cursor()
        cursor.execute('SET search_path TO production, extsrc, odestatic;')
        return conn

pool = MyThreadedConnectionPool(
    1, 20,
    database='ODE',
    user='odeadmin',
    password='odeadmin',
    host='ode-db1.jax.org',
    port=5432,
)

def dictify_row(cursor, row):
    """Turns the given row into a dictionary where the keys are the column names"""
    d = OrderedDict()
    for i, col in enumerate(cursor.description):
        d[col[0]] = row[i]
    return d

def get_all_projects(usr_id):
    connection = pool.getconn()
    try:
        cursor = connection.cursor()
        cursor.execute(
            '''
            select p.*, x.* FROM project p, (
                select p2g.pj_id, count(gs_id), x.count as deprecated, g.group
                FROM
                    project2geneset p2g
                    LEFT JOIN (
                        select pj_id, count(gs.gs_id)
                        from project2geneset p2g, geneset gs
                        where
                            gs_status like 'deprecated%%' and p2g.gs_id=gs.gs_id
                            and pj_id in (select pj_id from project where usr_id=%(usr_id)s) group by pj_id
                    ) x on x.pj_id=p2g.pj_id
                    LEFT JOIN (
                        SELECT pj_id, grp_name as group
                        FROM project p, grp g
                        WHERE p.usr_id=%(usr_id)s AND g.grp_id=CAST(p.pj_groups AS integer)
                    ) g ON (g.pj_id=p2g.pj_id)
                where p2g.pj_id in (select pj_id from project where usr_id=%(usr_id)s)
                group by p2g.pj_id, x.count, g.group
            ) x where x.pj_id=p.pj_id order by p.pj_name;
            ''',
            {'usr_id': usr_id})

        return list(cursor)
    finally:
        pool.putconn(connection)
