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
    return (dictify_row(cursor, row) for row in cursor)


def get_all_projects(usr_id):
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
    # TODO remove this impl note:
    # If I do the following:
    # select count(*), ode_gene_id, sp_id from extsrc.gene where ode_pref group by ode_gene_id, sp_id order by count(*) desc;
    # it looks like I get all counts of 1, so even though the total count may have many values, the preferred id is unique
    # for a sp_id + feature_id combination
    with PooledCursor() as cursor:
        cursor.execute(
            '''
            SELECT ode_gene_id, gdb_id, ode_ref_id
            FROM gene
            WHERE sp_id=%(sp_id)s AND LOWER(ode_ref_id)=%(feature_id)s;
            ''',
            {'sp_id': sp_id, 'feature_id': feature_id})

        return list(cursor)


'''
   /******************************************************
    * simple database retrieval functions (no modifications)
    *****************************************************/
   function getGeneIDTypes($spc_id=0, &$species=null)
   {
      $SQL = 'SELECT * FROM genedb WHERE (sp_id=$1 OR $1=0) OR sp_id=0 ORDER BY gdb_id;';
      $results = $this->query_params( $SQL, Array($spc_id) );
      while($row = pg_fetch_array($results)){
         $gs_gene_id_types[ -$row['gdb_id'] ] = $row['gdb_name'];
         if( is_array($species) ) $species[ -$row['gdb_id'] ] = $row['sp_id'];
      }

      $gs_gene_id_types[ "MicroArrays" ] = $this->getMicroArrayTypes($spc_id, $species);

      return $gs_gene_id_types;
   }
'''

def get_gene_id_types(spc_id=0):
    # based on getGeneIDTypes function found in ODE_DB.php
    with PooledCursor() as cursor:
        if spc_id == 0:
            cursor.execute(
                '''SELECT * FROM genedb WHERE (sp_id=$1 OR $1=0) OR sp_id=0 ORDER BY gdb_id;'''
                )


'''
   function getMicroArrayTypes($spc_id=0, &$species=null)
   {
      $ret_array = array();
      $SQL = 'SELECT * FROM platform WHERE (sp_id=$1 OR 0=$1) ORDER BY pf_name;';
      $results = $this->query_params($SQL, Array($spc_id));
      while($row = pg_fetch_array($results)){
         $ret_array[$row["pf_id"]] =$row["pf_name"] ;
         if( is_array($species) ) $species[ $row['pf_id'] ] = $row['sp_id'];
      }
      return $ret_array;
   }
'''