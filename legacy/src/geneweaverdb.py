from collections import OrderedDict
from hashlib import md5
import json
from psycopg2.pool import ThreadedConnectionPool
import distutils.sysconfig
from distutils.util import strtobool
import simplejson


class GeneWeaverThreadedConnectionPool(ThreadedConnectionPool):
    """Extend ThreadedConnectionPool to initialize the search_path"""
    def __init__(self, minconn, maxconn, *args, **kwargs):
        ThreadedConnectionPool.__init__(self, minconn, maxconn, *args, **kwargs)

    def _connect(self, key=None):
        """Create a new connection and set its search_path"""
        conn = super(GeneWeaverThreadedConnectionPool, self)._connect(key)
        conn.set_client_encoding('UTF-8')
        cursor = conn.cursor()
        cursor.execute('SET search_path TO production, extsrc, odestatic;')
        conn.commit()

        return conn


# the global threaded connection pool that should be used for all DB connections in this application
pool = GeneWeaverThreadedConnectionPool(
    5, 20,
    database='geneweaver',
    user='odeadmin',
    password='odeadmin',
    host='crick.ecs.baylor.edu',
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


def _dictify_row(cursor, row):
    """Turns the given row into a dictionary where the keys are the column names"""
    d = OrderedDict()
    for i, col in enumerate(cursor.description):
        # TODO find out what the right way to do unicode for postgres is? Is UTF-8 the right encoding here?
        # This prevents exceptions when non-ascii chars show up in a jinja2 template variable
        # but I'm not sure if it's the correct solution
        d[col[0]] = row[i].decode('utf-8') if type(row[i]) == str else row[i]
    return d


def dictify_cursor(cursor):
    """converts all cursor rows into dictionaries where the keys are the column names"""
    return (_dictify_row(cursor, row) for row in cursor)


class Project:
    def __init__(self, proj_dict):
        self.project_id = proj_dict['pj_id']
        self.user_id = proj_dict['usr_id']
        self.name = proj_dict['pj_name']

        # TODO in the database this is column 'pj_groups'. The name suggests
        #      that this field can contain multiple groups but it looks like
        #      in practice (in the DB) it is always a single integer value. This is why
        #      I name it singular "group_id" here, but this should be confirmed
        #      by Erich
        self.group_id = proj_dict['pj_groups']

        # NOTE: for now I'm ignoring pj_sessionid since it can be dangerous
        #       to let session IDs leak out and I assume it's not really useful
        #       as a readable property (I'm thinking it's more useful as a
        #       query param)
        self.created = proj_dict['pj_created']
        self.notes = proj_dict['pj_notes']

        # depending on if/how the project table is joined the following may be available
        self.count = proj_dict.get('count')
        self.deprecated = proj_dict.get('deprecated')
        self.group_name = proj_dict.get('group')

    def get_genesets(self, auth_user_id):
        return get_genesets_for_project(self.project_id, auth_user_id)


def get_genesets_for_project(project_id, auth_user_id):
    """
    Get all genesets in the given project that the given user is authorized to read
    :param project_id:      the project that we're looking up genesets for
    :param auth_user_id:    the user that is authenticated (we need to ensure that the
                            genesets are readable by the user)
    :return:                A list of genesets in the project
    """
    with PooledCursor() as cursor:
        cursor.execute(
            '''
            SELECT *
            FROM
                (
                    -- selects all genesets for the given project ID
                    SELECT geneset.*
                    FROM geneset INNER JOIN project2geneset
                    ON geneset.gs_id=project2geneset.gs_id
                    WHERE project2geneset.pj_id=%(project_id)s
                ) AS gs
                -- join with publications (there should be 1 or 0 per geneset so
                -- this will not generate extra rows)
                LEFT OUTER JOIN
                publication ON gs.pub_id = publication.pub_id
            WHERE
                -- security check: make sure the authenticated user has the
                -- right to view the geneset
                geneset_is_readable(%(auth_user_id)s, gs.gs_id);
            ''',
            {
                'project_id': project_id,
                'auth_user_id': auth_user_id,
            }
        )
        return [Geneset(row_dict) for row_dict in dictify_cursor(cursor)]


def get_all_projects(usr_id):
    """
    returns all projects associated with the given user ID
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

        return [Project(d) for d in dictify_cursor(cursor)]


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
#*************************************

def get_server_side(rargs):
    
    source_table = rargs.get('table', type=str)
    source_columns = []
    select_columns = []

    i=0
    temp = rargs.get('columns[%d][name]' % i)    
    while temp is not None:
	col_name ='cast(' + temp + ' as text)'
	source_columns.append(col_name)
	select_columns.append(temp)
        i=i+1
        temp = rargs.get('columns[%d][name]' % i)  
    

    #select and from clause creation
    select_clause = 'SELECT %s ' % ','.join(select_columns)
    from_clause = 'FROM %s' % source_table
  

    # Paging
    iDisplayStart = rargs.get('start', type=int)
    iDisplayLength = rargs.get('length', type=int)
    limit_clause = 'LIMIT %d OFFSET %d' % (iDisplayLength, iDisplayStart) \
    		    if (iDisplayStart is not None and iDisplayLength != -1) \
    		    else ''    

    #searching
    search_value = rargs.get('search[value]')     
    search_clauses = []
    if search_value:
        for i in range(len(source_columns)):
	    search_clauses.append('''%s LIKE '%%%s%%' ''' % (source_columns[i],search_value))
	search_clause = 'OR '.join(search_clauses)
    else:
 	search_clause=''
    
 
    # Sorting
    sorting_col = select_columns[rargs.get('order[0][column]', type=int)]
    sorting_direction = rargs.get('order[0][dir]', type=str)
    sort_dir = 'ASC NULLS LAST' \
    	   	if sorting_direction == 'asc' \
    		else 'DESC NULLS LAST'
    order_clause = 'ORDER BY %s %s' % (sorting_col, sort_dir) if sorting_col else ''
  
 
    # Filtering ("ac" is "all columns", "pc" is "per column")  <--- not used atm
    ac_search = rargs.get('sSearch')
    ac_like_exprs, ac_patterns, pc_like_exprs, pc_patterns = [], [], [], []
    for i, col in enumerate(source_columns):
        if rargs.get('bSearchable_%d' % i, type=strtobool):
            like_expr = Template("$col LIKE %s").safe_substitute(dict(col=col))
            if ac_search:
    		ac_like_exprs.append(like_expr)
    		ac_patterns.append('%' + ac_search + '%')
 
    	    pc_search = rargs.get('sSearch_%d' % i)
    	    if pc_search:
    		pc_like_exprs.append(like_expr)
   		pc_patterns.append('%' + pc_search + '%')
 
    ac_subclause = '(%s)' % ' OR '.join(ac_like_exprs) if ac_search else ''
    pc_subclause = ' AND '.join(pc_like_exprs)
    subclause = ' AND '.join([ac_subclause, pc_subclause]) \
    		if ac_subclause and pc_subclause \
    		else ac_subclause or pc_subclause
        	
    #joins all clauses together as a query
    where_clause = 'WHERE %s' % search_clause if search_clause else ''
    #print where_clause
    sql = ' '.join([select_clause,
    		    from_clause,
    		    where_clause,
    		    order_clause,
   		    limit_clause]) + ';'
    #print sql
 
    with PooledCursor() as cursor:
        #cursor.execute(sql, ac_patterns + pc_patterns)
	cursor.execute(sql)
        things = cursor.fetchall()


        sEcho = rargs.get('sEcho', type=int)
 
    # Count of all values in table
        cursor.execute(' '.join(['SELECT COUNT(*)', from_clause]) + ';')
        iTotalRecords = cursor.fetchone()[0]
 
    # Count of all values that satisfy WHERE clause
        iTotalDisplayRecords = iTotalRecords
        if where_clause:
            sql = ' '.join([select_clause, from_clause, where_clause]) + ';'
            #cursor.execute(sql, ac_patterns + pc_patterns)
	    cursor.execute(sql)
            iTotalDisplayRecords = cursor.rowcount
 
        response = {'sEcho': sEcho,
    	    	    'iTotalRecords': iTotalRecords,
    		    'iTotalDisplayRecords': iTotalDisplayRecords,
   		    'aaData': things
   		    }
 
        return response

def get_all_groups():
    with PooledCursor() as cursor:
	cursor.execute(
	     '''SELECT * FROM production.grp limit 200;''')
	return list(dictify_cursor(cursor))

def get_all_genes():
    with PooledCursor() as cursor:
	cursor.execute(
	     '''SELECT * FROM extsrc.gene limit 200;''')
	return list(dictify_cursor(cursor))

def get_all_gene_info():
    with PooledCursor() as cursor:
	cursor.execute(
	     '''SELECT * FROM extsrc.gene_info limit 200;''')
	return list(dictify_cursor(cursor))

def get_all_geneset_info():
    with PooledCursor() as cursor:
	cursor.execute(
	     '''SELECT * FROM production.geneset_info limit 200;''')
	return list(dictify_cursor(cursor))


#*************************************************************
class User:
    def __init__(self, usr_dict):
        self.user_id = usr_dict['usr_id']
        self.first_name = usr_dict['usr_first_name']
        self.last_name = usr_dict['usr_last_name']
        self.email = usr_dict['usr_email']
        self.prefs = usr_dict['usr_prefs']

        usr_admin = usr_dict['usr_admin']
        self.is_curator = usr_admin == 1
        self.is_admin = usr_admin == 2 or usr_admin == 3
        self.last_seen = usr_dict['usr_last_seen']
        self.creation_date = usr_dict['usr_created']
        self.ip_addr = usr_dict['ip_addr']

        self.__projects = None

    @property
    def projects(self):
        if self.__projects is None:
            self.__projects = get_all_projects(self.user_id)

        return self.__projects


class Publication:
    def __init__(self, pub_dict):
        self.pub_id = pub_dict['pub_id']
        self.authors = pub_dict['pub_authors']
        self.title = pub_dict['pub_title']
        self.abstract = pub_dict['pub_abstract']
        self.journal = pub_dict['pub_journal']
        self.volume = pub_dict['pub_volume']
        self.pages = pub_dict['pub_pages']
        self.month = pub_dict['pub_month']
        self.year = pub_dict['pub_year']
        self.pubmed_id = pub_dict['pub_pubmed']


class Geneset:
    def __init__(self, gs_dict):
        self.geneset_id = gs_dict['gs_id']
        self.user_id = gs_dict['usr_id']
        if self.user_id is not None:
            try:
                self.user = User(gs_dict)
            except KeyError:
                self.user = None
        else:
            self.user = None
        self.file_id = gs_dict['file_id']
        #self.name = gs_dict['gs_name'].decode('utf-8')
        self.name = gs_dict['gs_name']
        self.abbreviation = gs_dict['gs_abbreviation']
        self.pub_id = gs_dict['pub_id']
        if self.pub_id is not None:
            try:
                self.publication = Publication(gs_dict)
            except KeyError:
                self.publication = None
        else:
            self.publication = None
        self.res_id = gs_dict['res_id']
        self.cur_id = gs_dict['cur_id']
        self.description = gs_dict['gs_description']
        self.sp_id = gs_dict['sp_id']
        self.count = gs_dict['gs_count']
        # TODO document what different threshold values mean
        self.threshold_type = gs_dict['gs_threshold_type']
        self.threshold = gs_dict['gs_threshold']
        # a comma seperated list of group IDs (0=development, -1=private)
        self.group_ids = gs_dict['gs_groups']
        self.attribution_old = gs_dict['gs_attribution_old']
        self.uri = gs_dict['gs_uri']
        self.gene_id_type = gs_dict['gs_gene_id_type']
        self.creation_date = gs_dict['gs_created']
        # TODO document how admin flag works. Is it similar to usr_admin in the user table?
        self.admin_flag = gs_dict['admin_flag']
        self.updated_date = gs_dict['gs_updated']
        # TODO document how status works
        self.status = gs_dict['gs_status']
        # TODO figure out what this field is for
        self.gsv_qual = gs_dict['gsv_qual']
        self.attribution = gs_dict['gs_attribution']

        # declare value caches for instance properties
        self.__ontological_associations = None
        self.__geneset_values = None

    @property
    def ontological_associations(self):
        if self.__ontological_associations is None:
            self.__ontological_associations = get_ontologies_for_geneset(self.geneset)
        return self.__ontological_associations

    @property
    def geneset_values(self):
        if self.__geneset_values is None:
            self.__geneset_values = get_geneset_values(self.geneset_id)
        return self.__geneset_values


class Ontology:
    def __init__(self, ont_dict):
        self.ontology_id = ont_dict['ont_id']
        self.reference_id = ont_dict['ont_ref_id']
        self.name = ont_dict['ont_name']
        self.description = ont_dict['ont_description']
        self.children = ont_dict['ont_children']
        self.parents = ont_dict['ont_parents']
        self.ontdb_id = ont_dict['ontdb_id']


def authenticate_user(email, password):
    """
    Looks up user in the database
    :param email:       the user's email address
    :param password:    the user's password
    :return:            the User with the corresponding email address and password
                        OR None if no such User is found
    """
    email = email.strip()
    if not email or not password:
        # this check is probably not needed but it makes me feel better
        return None
    else:
        with PooledCursor() as cursor:
            password_md5 = md5()
            password_md5.update(password)
            cursor.execute(
                '''SELECT * FROM usr WHERE usr_email=%(email)s AND usr_password=%(password_md5)s;''',
                {
                    'email': email,
                    'password_md5': password_md5.hexdigest(),
                }
            )
            users = [User(row_dict) for row_dict in dictify_cursor(cursor)]
            return users[0] if len(users) == 1 else None


def get_user(user_id):
    """
    Looks up a User in the database
    :param user_id:     the user's ID
    :return:            the User matching the given ID or None if no such user is found
    """
    with PooledCursor() as cursor:
        cursor.execute('''SELECT * FROM usr WHERE usr_id=%s''', (user_id,))
        users = [User(row_dict) for row_dict in dictify_cursor(cursor)]
        return users[0] if len(users) == 1 else None


def get_user_byemail(user_email):
    """
    Looks up a User in the database
    :param user_email: the email a user entered
    :return: the User matching the given email or None if no such user is found
    """
    with PooledCursor() as cursor:
        cursor.execute('''SELECT * FROM usr WHERE usr_email=%s''', (user_email,))
        users = [User(row_dict) for row_dict in dictify_cursor(cursor)]
        return users[0] if len(users) == 1 else None


def register_user(user_first_name, user_last_name, user_email, user_password):
        """
        Insert a user to the db
        :param user_first_name: the user's first name, if not provided use "Guest" as default
        :param user_last_name:  the user's last name, if not provided use "User" as default
        :param user_email:      the user's email address, if not provided use "" as default
        :param user_password:   the user's password, if not provided use "" as default
        """
        with PooledCursor() as cursor:
                password_md5 = md5(user_password).hexdigest()
                cursor.execute(
                        '''INSERT INTO usr (usr_first_name, usr_last_name, usr_email, usr_admin, usr_password)
                        VALUES (%(user_first_name)s, %(user_last_name)s, %(user_email)s, '0', %(user_password)s)''',
                        {
                                'user_first_name': user_first_name,
                                'user_last_name': user_last_name,
                                'user_email': user_email,
                                'user_password': password_md5
                        }
                )
                cursor.connection.commit()
                return get_user_byemail(user_email)


def get_geneset(geneset_id, user_id=None):
    """
    Gets the Geneset if either the geneset is publicly visible or the user
    has permission to view it.
    :param geneset_id:  the geneset ID
    :param user_id:     the user ID that needs permission
    :return:            the Geneset corresponding to the given ID if the
                        user has read permission, None otherwise
    """

    # TODO not sure if we really need to convert to -1 here. The geneset_is_readable function may be able to handle None
    if user_id is None:
        user_id = -1

    with PooledCursor() as cursor:
        cursor.execute(
            '''
            SELECT *
            FROM geneset LEFT OUTER JOIN publication ON geneset.pub_id = publication.pub_id
            WHERE gs_id=%(geneset_id)s AND geneset_is_readable(%(user_id)s, %(geneset_id)s);
            ''',
            {
                'geneset_id': geneset_id,
                'user_id': user_id,
            }
        )
        genesets = [Geneset(row_dict) for row_dict in dictify_cursor(cursor)]
        return genesets[0] if len(genesets) == 1 else None


def get_ontologies_for_geneset(geneset_id):
    with PooledCursor() as cursor:
        cursor.execute(
            '''SELECT * FROM ontology NATURAL JOIN geneset_ontology WHERE gs_id=%s AND gso_ref_type<>'Blacklist';''',
            (geneset_id,))
        return [Ontology(row_dict) for row_dict in dictify_cursor(cursor)]


class GenesetValue:
    def __init__(self, gsv_dict):
        self.gs_id = gsv_dict['gs_id']
        self.ode_gene_id = gsv_dict['ode_gene_id']
        self.value = gsv_dict['gsv_value']
        self.hits = gsv_dict['gsv_hits']
        self.source_list = gsv_dict['gsv_source_list']
        self.value_list = gsv_dict['gsv_value_list']
        self.is_in_threshold = gsv_dict['gsv_in_threshold']
        self.date = gsv_dict['gsv_date']


def get_geneset_values(geneset_id):
    with PooledCursor() as cursor:
        cursor.execute('''SELECT * FROM geneset_value WHERE gs_id=%s;''', (geneset_id,))
        return [GenesetValue(gsv_dict) for gsv_dict in dictify_cursor(cursor)]


class ToolParam:
    def __init__(self, tool_param_dict):
        self.tool_classname = tool_param_dict['tool_classname']
        self.name = tool_param_dict['tp_name']
        self.description = tool_param_dict['tp_description']
        self.default = tool_param_dict['tp_default']
        self.options = json.loads(tool_param_dict['tp_options'])
        self.select_type = tool_param_dict['tp_seltype']
        self.is_visible = tool_param_dict['tp_visible']

    @property
    def label_name(self):
        """
        The name from the DB is prefixed by the owning tool's classname. This property
        strips that string off
        :return: the label friendly name
        """
        prefix = self.tool_classname + '_'
        if self.name.startswith(prefix):
            return self.name[len(prefix):]
        else:
            return self.name


def get_tool_params(tool_classname, only_visible=False):
    """
    Get tool parameters for the tool with the given classname
    :param tool_classname: identifies the tool that we're getting params for
    :param only_visible: if True only return parameters marked visible
    :return: the list of ToolParams
    """
    with PooledCursor() as cursor:
        if only_visible:
            cursor.execute(
                '''SELECT * FROM tool_param WHERE tool_classname=%s AND tp_visible ORDER BY tp_name;''',
                (tool_classname,))
        else:
            cursor.execute(
                '''SELECT * FROM tool_param WHERE tool_classname=%s ORDER BY tp_name;''',
                (tool_classname,))
        return [ToolParam(d) for d in dictify_cursor(cursor)]


class ToolConfig:
    def __init__(self, tool_dict):
        self.classname = tool_dict['tool_classname']
        self.name = tool_dict['tool_name']
        self.description = tool_dict['tool_description']
        self.requirements = [x.strip() for x in tool_dict['tool_requirements'].split(',')]
        self.is_active = tool_dict['tool_active'] == '1'
        self.sort_priority = tool_dict['tool_sort']
        self.__params = None

    @property
    def params(self):
        if self.__params is None:
            self.__params = OrderedDict(((tp.name, tp) for tp in get_tool_params(self.classname)))

        return self.__params


def get_tool(tool_classname):
    with PooledCursor() as cursor:
        cursor.execute('''SELECT * FROM tool WHERE tool_classname=%s;''', (tool_classname,))
        tools = [ToolConfig(tool_dict) for tool_dict in dictify_cursor(cursor)]

        return tools[0] if len(tools) == 1 else None


def get_active_tools():
    """
    Get all tools that are marked active in the DB
    :return: a list of active tools
    """
    with PooledCursor() as cursor:
        cursor.execute('''SELECT * FROM tool WHERE tool_active='1' ORDER BY tool_sort;''')
        return [ToolConfig(tool_dict) for tool_dict in dictify_cursor(cursor)]


def get_run_status(run_hash):
    """
    Finds the total number of runs queued up and the number queued up ahead of the give hash
    :param run_hash: we're finding out the queue position of this run
    :return: a tuple where the 1st element is the total number of runs queued and the
             2nd is the number of runs queued ahead of run_hash
    """

    with PooledCursor() as cursor:
        # finds the total number of runs waiting to run
        cursor.execute('''SELECT count(*) FROM result WHERE res_started IS NULL;''')
        total_queued = list(cursor)[0][0]

        # finds the number of runs ahead of us that are waiting to run
        cursor.execute(
            '''
            SELECT count(*)
            FROM
                result AS r1
                CROSS JOIN
                (SELECT * FROM result WHERE res_runhash=%(run_hash)s) as r2
                WHERE r1.res_started IS NULL AND r1.res_created<r2.res_created;
            ''')
        before_queued = list(cursor)[0][0]

        return total_queued, before_queued


def insert_result(usr_id, res_runhash, gs_ids, res_data, res_tool, res_description, res_status):
    with PooledCursor() as cursor:
        cursor.execute(
            '''
            INSERT INTO result (usr_id, res_runhash, gs_ids, res_data, res_tool, res_description, res_status, res_started)
            VALUES (%s, %s, %s, %s, %s, %s, %s, now())
            RETURNING res_id;
            ''',
            (usr_id, res_runhash, ','.join(gs_ids), res_data, res_tool, res_description, res_status)
        )
        cursor.connection.commit()

        # return the primary ID for the insert that we just performed
        return cursor.fetchone()[0]
