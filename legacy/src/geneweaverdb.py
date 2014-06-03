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
        conn.commit()

        return conn

# the global thread pool that we're using for this app
pool = MyThreadedConnectionPool(
    5, 20,
    database='ODE',
    user='odeadmin',
    password='odeadmin',
    host='ode-db1.jax.org',
    port=5432,
)


class PooledConnection(object):
    """
    A pooled connection suitable for using in a with ... as ...: construct (the connection is automatically
    returned to the pool at the end of the with block)
    """

    def __init__(self, conn_pool=pool, rollback_on_exception=False):
        self.conn_pool = conn_pool
        self.rollback_on_exception = rollback_on_exception
        self.connection = None

    def __enter__(self):
        self.connection = self.conn_pool.getconn()
        return self.connection

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection is not None:
            if self.rollback_on_exception and exc_type is not None:
                self.connection.rollback()

            self.conn_pool.putconn(self.connection)


class PooledCursor(object):
    """
    A cursor obtained from a connection pool. This is suitable for using in a with ... as ...: construct (the
    underlying connection will be automatically returned to the connection pool
    """

    def __init__(self, conn_pool=pool, rollback_on_exception=False):
        self.conn_pool = conn_pool
        self.rollback_on_exception = rollback_on_exception
        self.connection = None

    def __enter__(self):
        self.connection = self.conn_pool.getconn()
        return self.connection.cursor()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection is not None:
            if self.rollback_on_exception and exc_type is not None:
                self.connection.rollback()

            self.conn_pool.putconn(self.connection)


def dictify_row(cursor, row):
    """Turns the given row into a dictionary where the keys are the column names"""
    d = OrderedDict()
    for i, col in enumerate(cursor.description):
        d[col[0]] = row[i]
    return d


def dictify_cursor(cursor):
    """converts all cursor rows into dictionaries where the keys are the column names"""
    return (dictify_row(cursor, row) for row in cursor)


def get_all_projects(usr_id):
    """
    returns all projects associated with the given project ID
    """
    with PooledCursor() as cursor:
        cursor.execute(
            '''
            SELECT p.*, x.* FROM project p, (
                SELECT p2g.pj_id, COUNT(gs_id), x.count AS deprecated, g.group
                FROM
                    project2geneset p2g
                    LEFT JOIN (
                        SELECT pj_id, COUNT(gs.gs_id)
                        FROM project2geneset p2g, geneset gs
                        WHERE
                            gs_status LIKE 'deprecated%%' AND p2g.gs_id=gs.gs_id
                            AND pj_id IN (SELECT pj_id FROM project WHERE usr_id=%(usr_id)s) GROUP BY pj_id
                    ) x ON x.pj_id=p2g.pj_id
                    LEFT JOIN (
                        SELECT pj_id, grp_name AS GROUP
                        FROM project p, grp g
                        WHERE p.usr_id=%(usr_id)s AND g.grp_id=CAST(p.pj_groups AS INTEGER)
                    ) g ON (g.pj_id=p2g.pj_id)
                WHERE p2g.pj_id IN (SELECT pj_id FROM project WHERE usr_id=%(usr_id)s)
                GROUP BY p2g.pj_id, x.count, g.group
            ) x WHERE x.pj_id=p.pj_id ORDER BY p.pj_name;
            ''',
            {'usr_id': usr_id}
        )

        return list(cursor)


def get_all_species():
    """
    returns an ordered mapping from species ID to species name for all available species
    """
    with PooledCursor() as cursor:
        cursor.execute('''SELECT sp_id, sp_name FROM species ORDER BY sp_id;''')
        return OrderedDict(cursor)


def resolve_feature_id(sp_id, feature_id):
    """
    For the given species and feature IDs get the corresponding ODE gene ID (which
    is our canonical ID type)
    :param sp_id:       species ID
    :param feature_id:  feature ID (this can be a gene ID from any of the many source databases)
    :return:            the list of DB rows containing 3 columns:
                        ODE IDs, gene datbase IDs and reference IDs (should be a case
                        insensitive match of the given feature ID
    """
    with PooledCursor() as cursor:
        cursor.execute(
            '''
            SELECT ode_gene_id, gdb_id, ode_ref_id
            FROM gene
            WHERE sp_id=%(sp_id)s AND LOWER(ode_ref_id)=%(feature_id)s;
            ''',
            {'sp_id': sp_id, 'feature_id': feature_id})

        return list(cursor)


def get_gene_id_types(sp_id=0):
    with PooledCursor() as cursor:
        cursor.execute(
            '''SELECT * FROM genedb WHERE %(sp_id)s=0 OR sp_id=0 OR sp_id=%(sp_id)s ORDER BY gdb_id;''',
            {'sp_id': sp_id})

        return list(dictify_cursor(cursor))


def get_microarray_types(sp_id=0):
    """
    get all rows from the platform table with the given species identifier
    :param sp_id:   the species identifier
    :return:        the list of rows from the platform table
    """
    with PooledCursor() as cursor:
        cursor.execute(
            '''SELECT * FROM platform WHERE (sp_id=%(sp_id)s OR 0=%(sp_id)s) ORDER BY pf_name;''',
            {'sp_id': sp_id})
        return list(dictify_cursor(cursor))
