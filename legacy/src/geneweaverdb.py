from collections import OrderedDict, defaultdict
from hashlib import md5
import json
import string
import random
from psycopg2 import Error
from psycopg2.pool import ThreadedConnectionPool
from tools import toolcommon as tc
import os
import flask
from flask import session
import config
import notifications
from curation_assignments import CurationAssignment
import pubmedsvc
import annotator as ann

app = flask.Flask(__name__)

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

# the global threaded connection pool that should be used for all DB
# connections in this application
pool = GeneWeaverThreadedConnectionPool(
    5, 20,
    database=config.get('db', 'database'),
    user=config.get('db', 'user'),
    password=config.get('db', 'password'),
    host=config.get('db', 'host'),
    port=config.getInt('db', 'port')
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
        OrderedDict(sorted(d.items()))
    return d


def dictify_cursor(cursor):
    """converts all cursor rows into dictionaries where the keys are the column names"""
    return (_dictify_row(cursor, row) for row in cursor)


class Project:
    def __init__(self, proj_dict):
        self.name = proj_dict['pj_name']
        self.project_id = proj_dict['pj_id']
        self.user_id = proj_dict['usr_id']

        # TODO in the database this is column 'pj_groups'. The name suggests
        # that this field can contain multiple groups but it looks like
        # in practice (in the DB) it is always a single integer value. This is why
        #	   I name it singular "group_id" here, but this should be confirmed
        #	   by Erich
        self.group_id = proj_dict['pj_groups']

        # NOTE: for now I'm ignoring pj_sessionid since it can be dangerous
        #		to let session IDs leak out and I assume it's not really useful
        #		as a readable property (I'm thinking it's more useful as a
        #		query param)
        self.created = proj_dict['pj_created']
        self.notes = proj_dict['pj_notes']
        self.star = proj_dict['pj_star']

        # depending on if/how the project table is joined the following may be available
        self.count = proj_dict.get('count')
        self.deprecated = proj_dict.get('deprecated')
        self.group_name = proj_dict.get('group')
        ## Displayed to others when a project is shared
        self.owner = proj_dict.get('owner')

    def get_genesets(self, auth_user_id):
        return get_genesets_for_project(self.project_id, auth_user_id)


def get_genesets_for_project(project_id, auth_user_id):
    """
    Get all genesets in the given project that the given user is authorized to read
    :param project_id:		the project that we're looking up genesets for
    :param auth_user_id:	the user that is authenticated (we need to ensure that the
                            genesets are readable by the user)
    :return:				A list of genesets in the project
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
                geneset_is_readable2(%(auth_user_id)s, gs.gs_id);
            ''',
                {
                    'project_id': project_id,
                    'auth_user_id': auth_user_id,
                }
        )
        return [Geneset(row_dict) for row_dict in dictify_cursor(cursor)]


def insert_geneset_to_project(project_id, geneset_id):
    with PooledCursor() as cursor:
        cursor.execute(
                '''
            INSERT INTO project2geneset (pj_id, gs_id, modified_on)
            VALUES (%s, %s, now())
            RETURNING pj_id;
            ''',
                (project_id, geneset_id,)
        )
        cursor.connection.commit()

        # return the primary ID for the insert that we just performed
        return cursor.fetchone()[0]


# this function creates a project with no genesets associated with it
# if a guest is creating a project, pass in -1 for user_id
# NOT TESTED
def create_project(project_name, user_id):
    if user_id > 0:
        with PooledCursor() as cursor:
            cursor.execute(
                    '''
                INSERT INTO project (pj_name, usr_id, pj_created)
                VALUES (%s, %s, now())
                RETURNING pj_id;
                ''',
                    (project_name, user_id,)
            )
            cursor.connection.commit()
            # return the primary ID for the insert that we just performed
            return cursor.fetchone()[0]
    else:
        with PooledCursor() as cursor:
            cursor.execute(
                    '''
                INSERT INTO project (pj_name, pj_created)
                VALUES (%s, now())
                RETURNING pj_id;
                ''',
                    (project_name,)
            )
            cursor.connection.commit()
            # return the primary ID for the insert that we just performed
            return cursor.fetchone()[0]


def get_project_by_id(pid):
    """
    Retrieves the project associated with the given project ID
    """
    with PooledCursor() as cursor:
        cursor.execute(
            '''
            SELECT  *
            FROM    production.project
            WHERE   pj_id = %s;
            ''',
                (pid,)
        )

        p = [Project(d) for d in dictify_cursor(cursor)]

        if not p:
            return None

        return p[0]

def get_all_projects(usr_id):
    """
    returns all projects associated with the given user ID
    """
    with PooledCursor() as cursor:
        cursor.execute(
                '''
            (SELECT p.*, p.pj_id, x.* FROM project p, (select CAST(NULL AS BIGINT) as count,
                CAST(NULL AS BIGINT) as deprecated, CAST(NULL AS VARCHAR) as group) x
                WHERE p.usr_id=%(usr_id)s AND p.pj_id not in
                (SELECT p2g.pj_id FROM project2geneset p2g WHERE p2g.pj_id=p.pj_id))
            UNION
            (SELECT p.*, x.* FROM project p, (
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
                        WHERE p.usr_id=%(usr_id)s AND g.grp_id=CAST((split_part(p.pj_groups, ',', 1) ) AS INTEGER)
                    ) g ON (g.pj_id=p2g.pj_id)
                WHERE p2g.pj_id IN (SELECT pj_id FROM project WHERE usr_id=%(usr_id)s)
                GROUP BY p2g.pj_id, x.count, g.group
            ) x WHERE x.pj_id=p.pj_id ORDER BY p.pj_name ASC);
            ''',
                {'usr_id': usr_id}
        )

        return [Project(d) for d in dictify_cursor(cursor)]


def get_shared_projects(usr_id):
    """
    Retrieves all the projects that have been shared with the given user.

    :type usr_id: int
    :arg usr_id: 

    :ret list: projects (as project objects) shared with the user
    """

    with PooledCursor() as cursor:
        cursor.execute(
            '''
            SELECT          COUNT(gs_id), pj_name, pj_id, pj.usr_id, pj_groups,
                            pj_created, pj_notes, pj_star, usr_email AS owner
            FROM            project AS pj
            NATURAL JOIN    project2geneset, usr
            WHERE           usr.usr_id = pj.usr_id AND 
                            pj.usr_id <> %s AND
                            project_is_readable(%s, pj_id) 
            GROUP BY        pj.usr_id, pj_name, pj_id, owner 
            ORDER BY        pj_name;
            ''',
                (usr_id, usr_id)
        )

        plist = [Project(d) for d in dictify_cursor(cursor)]

        return sorted(plist, key=lambda x: x.name, reverse=False)


####################################################################################
# Begin group block, Getting specific groups for a user, and creating/modifying them

def get_group_name(grp_id):
    """
    Return the name of a specific group.

    :type grp_id: int
    :arg grp_id: GW group ID

    :ret str: name of the group
    """
    with PooledCursor() as cursor:
        cursor.execute(
            '''
            SELECT grp_name
            FROM production.grp
            WHERE grp_id = %s;
            ''',
                (grp_id,)
        )

        name = cursor.fetchone()

    return name[0] if name else ''

def get_all_members_of_group(usr_id):
    """
    return a dictionary of groups owned by user_id and all members
    :param usr_id:
    :return: list
    """
    with PooledCursor() as cursor:
        cursor.execute(
                '''
            SELECT u2g.grp_id, u.usr_email, u.usr_id FROM usr2grp u2g, usr u WHERE u2g.grp_id IN
            (SELECT grp_id FROM usr2grp WHERE usr_id=%s) AND u.usr_id=u2g.usr_id ORDER BY u.usr_email''', (usr_id,)
        )
    usr_emails = list(dictify_cursor(cursor))
    return usr_emails if len(usr_emails) > 0 else None

def get_group_members(grp_id):
    """
    return a list of dictionaries of all members for a given group
    :param grp_id:
    :return: list
    """
    with PooledCursor() as cursor:
        cursor.execute(
                '''
            SELECT u.usr_id, u.usr_first_name, u.usr_last_name, u.usr_email FROM usr2grp u2g, usr u WHERE u2g.grp_id=%s
            AND u.usr_id=u2g.usr_id ORDER BY u.usr_last_name, u.usr_first_name, u.usr_email''', (grp_id,)
        )
    members = list(dictify_cursor(cursor))
    return members if len(members) > 0 else None


def get_group_admins(grp_id):
    """
    get all of the admins (aka owners) for a specified group id
    :param grp_id: group id
    :return: list of ordered dictionaries,
             each dictionary has keys 'usr_email', 'usr_id'. These are the email
             and usr_ids for each group admin
    """
    with PooledCursor() as cursor:
        cursor.execute(
                '''
            SELECT usr_email, usr_id  FROM usr WHERE usr_id IN
            (SELECT usr_id FROM usr2grp WHERE u2g_privileges=1 AND grp_id=%s) ORDER BY usr_email''', (grp_id,)
        )
    admin_emails = list(dictify_cursor(cursor))
    return admin_emails if len(admin_emails) > 0 else []


def get_all_owned_groups(usr_id):
    """
    returns all owned groups of the given user ID
    """
    with PooledCursor() as cursor:
        cursor.execute(
                '''SELECT * FROM production.grp WHERE grp_id in (SELECT grp_id
               FROM production.usr2grp
               WHERE usr_id = %s and u2g_privileges = 1)''', (usr_id,)
        )

        return list(dictify_cursor(cursor))


def get_all_member_groups(usr_id):
    """
    returns all groups the given user ID is a member of
    """
    with PooledCursor() as cursor:
        cursor.execute(
                '''SELECT * FROM production.grp WHERE grp_id in (SELECT grp_id
               FROM production.usr2grp
               WHERE usr_id = %s and (u2g_privileges = 0 or u2g_privileges IS NULL))''', (usr_id,)
        )

        return list(dictify_cursor(cursor))


def get_other_visible_groups(usr_id):
    """
    get all visible groups that a user is not a member (regular or admin) of
    basically returns all public groups a user is NOT a member of
    """
    with PooledCursor() as cursor:
        cursor.execute(
                '''SELECT * FROM production.grp WHERE grp_id NOT IN (SELECT grp_id
               FROM production.usr2grp WHERE usr_id = %s) AND grp_private = false''', (usr_id,)
        )

        return list(dictify_cursor(cursor))


def add_user_to_public_groups(group_ids, user_id):
    """

    :param group_ids: list of group_ids
    :param user_id: the user_id of the user to add to groups
    :return:
    """

    with PooledCursor() as c:
        c.execute(
            '''
            INSERT INTO production.usr2grp (grp_id, usr_id, u2g_privileges, u2g_status, u2g_comment, u2g_created)
            VALUES (unnest(%s), %s, 0, 2, NULL, now());
            ''',
            (group_ids, user_id)
        )
        c.connection.commit()
        return {'success': c.statusmessage, 'error': 'None'}


# group_name is a string provided by user, group_private should be either true or false
# true, the group is private. false the group is public.
# The user_id will be initialized as the owner of the group   

def create_group(group_name, group_private, user_id):
    if group_private == 'Private':
        priv = 't'
    else:
        priv = 'f'

    with PooledCursor() as cursor:
        cursor.execute(
                '''
            INSERT INTO production.grp (grp_name, grp_private, grp_created)
            VALUES (%s, %s, now())
            RETURNING grp_id;
            ''',
                (group_name, priv,)
        )
        cursor.connection.commit()
        # return the primary ID for the insert that we just performed
        grp_id = cursor.fetchone()[0]

    with PooledCursor() as cursor:
        cursor.execute(
                '''
            INSERT INTO production.usr2grp (grp_id, usr_id, u2g_privileges)
            VALUES (%s, %s, 1 );
            ''',
                (grp_id, user_id,)
        )
        cursor.connection.commit()
        print cursor.statusmessage

    return group_name


# edit group name


def edit_group_name(group_name, group_id, group_private, user_id):
    if int(flask.session['user_id']) == int(user_id):
        group_id = int(group_id)
        user_id = int(user_id)
        priv = 't' if group_private == 'Private' else 'f'
        with PooledCursor() as cursor:
            cursor.execute('''UPDATE production.grp SET grp_name=%s, grp_private=%s WHERE grp_id=%s
							  AND EXISTS (SELECT 1 FROM usr2grp WHERE grp_id=%s AND usr_id=%s AND u2g_privileges=1)''',
                           (group_name, priv, group_id, group_id, user_id,))
            cursor.connection.commit()
        return {'error': 'None'}
    else:
        return {'error': 'User does not have permission'}


def add_user_to_group(group_id, owner_id, usr_email, permission=0):
    """
    Adds a user to a group.

    args
        group_id:   the grp_id of the group the user is being added to
        owner_id:   the usr_id of the user that owns the group
        usr_email:  the email of the user being added to the group
        permission: flag indicating whether or not the user being added is an
                    admin. For normal users permission == 0, admins it is == 1.

    returns
        a dict containing a single field, 'error' that indicates if any errors
        were encountered while adding the user to the group.
    """

    usr_email = str(usr_email).lower()
    email_from_db = ''

    with PooledCursor() as cursor:

        cursor.execute(
            '''
            SELECT  usr_email 
            FROM    usr 
            WHERE   LOWER(usr_email) = %s
            ''', 
                (usr_email,)
        )

        if cursor.rowcount == 0:
            return {'error': 'No User'}
        else:
            email_from_db = cursor.fetchone()[0]
        
        cursor.execute(
            '''
            SELECT  u.usr_id 
            FROM    usr u, usr2grp ug 
            WHERE   LOWER(u.usr_email) = %s AND 
                    u.usr_id = ug.usr_id AND
                    ug.grp_id = %s;
            ''', (usr_email, group_id)
        )

        if cursor.rowcount > 0:
            return {'error': 'Already belongs to group'}

        cursor.execute(
            '''
            INSERT INTO production.usr2grp (grp_id, usr_id, u2g_privileges, u2g_status, u2g_created)
            VALUES ((SELECT grp_id
                     FROM production.usr2grp
                     WHERE grp_id = %s AND usr_id = %s AND u2g_privileges = 1),
                    (SELECT usr_id
                     FROM production.usr
                     WHERE LOWER(usr_email) = %s LIMIT 1), %s, 2, now())
            RETURNING grp_id;
            ''',
                (group_id, owner_id, usr_email, permission,)
        )

        cursor.connection.commit()

        group_name = get_group_name(group_id)
        owner = get_user(owner_id)
        owner_name = owner.first_name + " " + owner.last_name
        notifications.send_usr_notification(
            email_from_db, 
            "Added to Group",
            "You have been added to the group {} by {}".format(group_name, owner_name),
            True
        )

        return {'error': 'None'}


def remove_user_from_group(group_name, owner_id, usr_email):
    with PooledCursor() as cursor:
        cursor.execute(
                '''
            DELETE FROM production.usr2grp
            WHERE (grp_id = (SELECT grp_id
                            FROM production.usr2grp
                            WHERE grp_id = (SELECT grp_id FROM production.grp WHERE grp_name = %s)
                            AND usr_id = %s AND u2g_Privileges = 1)
                            OR grp_id = (SELECT grp_id
                                         FROM production.usr2grp
                                         WHERE grp_id = (SELECT grp_id FROM production.grp WHERE grp_name = %s) AND usr_id = (SELECT usr_id
                                                                         FROM production.usr
                                                                         WHERE usr_email = %s LIMIT 1)))
                 AND usr_id = (SELECT usr_id
                               FROM production.usr
                               WHERE usr_email = %s LIMIT 1);

            ''',
                (group_name, owner_id, group_name, usr_email, usr_email,)
        )
        cursor.connection.commit()

        #send notification

        owner = get_user(owner_id)
        owner_name = owner.first_name + " " + owner.last_name
        notifications.send_usr_notification(usr_email, "Removed from Group",
                                            "You have been removed from the group {} by {}".format(group_name, owner_name),
                                            True)


def remove_selected_users_from_group(user_id, user_emails, grp_id):
    user_email = user_emails.split(',')

    # group name/owner names are used for notifications
    group_name = get_group_name(grp_id)
    owner = get_user(user_id)
    owner_name = owner.first_name + " " + owner.last_name

    for e in user_email:
        with PooledCursor() as cursor:
            cursor.execute(
                    '''
                DELETE FROM production.usr2grp
                WHERE grp_id=%s AND usr_id = (SELECT usr_id FROM production.usr WHERE usr_email=%s limit 1) AND
                  EXISTS (SELECT 1 FROM production.usr2grp WHERE grp_id=%s AND usr_id=%s AND u2g_privileges=1)
                ''',
                    (grp_id, e, grp_id, user_id,))
            cursor.connection.commit()
            print cursor.statusmessage

            # if we deleted a user from the group send that user a notification
            if cursor.rowcount:
                notifications.send_usr_notification(e, "Removed from Group",
                                                    "You have been removed from the group {} by {}".format(group_name, owner_name),
                                                    True)

    return {'error': 'None'}


def update_group_admins(admin_id, user_ids, grp_id):
    """

    :param admin_id: ID of the admin making the request
    :param user_ids: list of user ids to set as administrators
    :param grp_id: group id that we are updating
    :return:
    """
    admins = get_group_admins(grp_id)

    # get_group_admins gives us a list of OrderedDics with keys usr_id and usr_
    # email we want to convert it to a list of just usr_ids
    admin_uids = []
    for a in admins:
        admin_uids.append(a['usr_id'])

    # make sure submitting user has appropriate permissions
    # application has already made sure admin_id == flask.session['user_id']
    if int(admin_id) not in admin_uids:
        return {'error': 'You do not have permission to modify this group'}

    # group name/owner names are used for notifications
    admin = get_user(admin_id)
    group_name = get_group_name(grp_id)
    admin_name = admin.first_name + " " + admin.last_name

    for uid in user_ids:
        if uid in admin_uids:
            # don't need to update, but remove from our list of current admins
            # anyone still left in current_admins at the end will get removed
            # as a group administrator
            admin_uids.remove(uid)
        else:
            with PooledCursor() as cursor:
                cursor.execute(
                        '''
                    UPDATE production.usr2grp SET u2g_privileges=1
                    WHERE grp_id=%s AND usr_id=%s
                    ''',
                        (grp_id, uid)
                )
                cursor.connection.commit()
                # send notification that user has been promoted to admin
                if cursor.rowcount:
                    notifications.send_usr_notification(uid, "Promoted to Group Admin",
                                                        "You have been promoted to admin of the group {} by {}".format(group_name, admin_name))

    # do we have anyone left in current_admins?  if so, they were not passed in
    # as part of the list of new admins,  so we need to remove their admin
    # permissions. They are not being removed from the group, just demoted.

    # This can be improved.  We do need to keep track of who loses admin privs
    # so that we can notify them.  That is why we don't just clear everyone's
    # admin privileges first, and then set the permissions for the new list
    # of admins.

    # iterate over everyone that was an admin but is not in the new list
    # remove their admin privs and send them a notification
    for uid in admin_uids:
        with PooledCursor() as cursor:
            cursor.execute(
                    '''
                UPDATE production.usr2grp SET u2g_privileges=0
                WHERE grp_id=%s AND usr_id=%s
                ''',
                    (grp_id, uid)
            )
            cursor.connection.commit()
            #send notification that user has been demoted from admin
            if cursor.rowcount:
                notifications.send_usr_notification(uid, "Admin Privileges Revoked",
                                                    "Your admin privileges of the group {} have been removed by {}. "
                                                    "You now have standard group membership.".format(group_name, admin_name))

    return {'success': True}

# switches group active field between false and true, and true and false
def toggle_group_active(group_id, user_id):
    with PooledCursor() as cursor:
        cursor.execute(
                '''
            UPDATE production.usr2grp
            SET u2g_active = not u2gactive
            WHERE grp_id = %s and usr_id = %s;
            ''',
                (group_id, user_id,)
        )
        cursor.connection.commit()
        return


# Be Careful with this function
# Only let owners of groups call this function
def delete_group(group_name, owner_id):
    if int(flask.session['user_id']) != int(owner_id):
        return {'error': 'You do not have permission to delete this group'}
    else:
        with PooledCursor() as cursor:
            cursor.execute(
                    '''
                DELETE FROM production.usr2grp
                WHERE grp_id = (SELECT grp_id
                                FROM production.usr2grp
                                WHERE grp_id = %s AND  usr_id = %s AND u2g_privileges = 1)
                RETURNING grp_id;
                ''',
                    (group_name, owner_id,)
            )
            cursor.connection.commit()
        with PooledCursor() as cursor:
            cursor.execute(
                    '''
                DELETE FROM production.grp
                WHERE grp_id = %s;
                ''',
                    (group_name,)
            )
            cursor.connection.commit()
        remove_group_from_all_projects(group_name, owner_id)
        return {'error': 'None'}


# Remove yourself as a member of a group
def remove_member_from_group(group_name, owner_id):
    if int(flask.session['user_id']) != int(owner_id):
        return {'error': 'You do not have permission to exit this group'}
    else:
        with PooledCursor() as cursor:
            cursor.execute(
                    '''
                DELETE FROM production.usr2grp
                WHERE grp_id=%s AND usr_id=%s AND u2g_privileges=0;
                ''',
                    (group_name, owner_id,)
            )
            cursor.connection.commit()
    return {'error': 'None'}


# Remove group from all projects
def remove_group_from_all_projects(grp_id, user_id):
    with PooledCursor() as cursor:
        cursor.execute('''SELECT pj_groups, pj_id FROM project;''')
        results = cursor.fetchall()
        for r in results:
            g = r[0]
            h = g.split(',')
            if grp_id in h:
                h.remove(grp_id)
                res = '-1' if len(h) == 0 else str(','.join(h))
                print res
                cursor.execute('''UPDATE project SET pj_groups=%s WHERE pj_id=%s''', (res, r[1],))
                cursor.connection.commit()


def get_file_contents(file_id):
    """
    Retrieves the file contents of a geneset.

    arguments
        file_id: int file ID associated with a geneset

    returns
        a string of the file contents. An empty string is returned if errors
        are encountered or the contents are missing.
    """

    with PooledCursor() as cursor:
        cursor.execute('''
            SELECT file_contents
            FROM file
            WHERE file_id = %s''', (file_id,))

        contents = cursor.fetchone()

        if not contents:
            return ''

        return contents[0]


def get_all_species():
    """
    returns an ordered mapping from species ID to species name for all available species
    """
    with PooledCursor() as cursor:
        cursor.execute('''SELECT sp_id, sp_name FROM species ORDER BY sp_id;''')
        return OrderedDict(cursor)


def get_all_publications(gs_id):
    """
    :param gs_id:
    :return: All information in the publication table if pub_id is attached to publication table
    """
    with PooledCursor() as cursor:
        cursor.execute('''SELECT * FROM publication p, geneset g WHERE p.pub_id=g.pub_id AND g.gs_id=%s''', (gs_id,))
        publications = [Publication(row_dict) for row_dict in dictify_cursor(cursor)]
        return publications[0] if len(publications) == 1 else None


def get_all_attributions():
    """
    returns an ordered mapping from attribution ID to attribution name for all available attributions

    TODO remark - there is an added statement to remove null attributions. At the time of writing, this would be
    attribution id 1. It has an abbreviation that is null, and description 'none'. However, there are no genesets with
    gs_attribution set to 1. They are either NULL or 0.
    """
    with PooledCursor() as cursor:
        # TODO resolve issue of the null at_abbrev. For now this is truncated for the search feature, but could be
        # enabled in the future.
        cursor.execute('''SELECT at_id, at_abbrev FROM attribution WHERE at_abbrev IS NOT NULL ORDER BY at_id;''')
        return OrderedDict(cursor)

def get_attributed_genesets(atid=None, abbrev=None):
    """
    Returns geneset and distinct gene counts for the given attribution.

    :return:
    """

    with PooledCursor() as cursor:
        if not atid and abbrev:
            cursor.execute('''
                SELECT at_id
                FROM odestatic.attribution
                WHERE at_abbrev ILIKE %s;''', (abbrev,))

            atid = cursor.fetchone()

            if not atid:
                return []
            else:
                atid = atid[0]

        cursor.execute('''
            SELECT COUNT(gs_id) AS gs_count, SUM(gs_count) AS gene_count
            FROM production.geneset
            WHERE gs_attribution = %s;
            ''', (atid,))
            #SELECT COUNT(DISTINCT gs.gs_id) AS gs_count,
            #       COUNT(gsv.ode_gene_id) AS gene_count
            #FROM geneset_value AS gsv
            #INNER JOIN geneset AS gs
            #ON gsv.gs_id = gs.gs_id
            #WHERE gs_attribution = %s;
        #counts = OrderedDict(cursor)
        #counts['at_id'] = atid

        #if abbrev:
        #    counts['at_abbrev'] = abbrev

        return cursor.fetchone()


def resolve_feature_id(sp_id, feature_id):
    """
    For the given species and feature IDs get the corresponding ODE gene ID (which
    is our canonical ID type)
    :param sp_id:		species ID
    :param feature_id:	feature ID (this can be a gene ID from any of the many source databases)
    :return:			the list of DB rows containing 3 columns:
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

def resolve_feature_ids(sp_id, ref_ids):
    """
    For the given species and feature IDs get the corresponding ODE gene IDs
    (which is our canonical ID type).
    """

    ref_ids = tuple(map(lambda r: r.lower(), ref_ids))

    with PooledCursor() as cursor:
        cursor.execute(
            '''
            SELECT  ode_ref_id, ode_gene_id
            FROM    extsrc.gene
            WHERE   sp_id = %s AND
                    lower(ode_ref_id) IN %s;
            ''',
                (sp_id, ref_ids)
        )

        return list(dictify_cursor(cursor))

def get_gene_id_types(sp_id=0):
    with PooledCursor() as cursor:
        cursor.execute(
                '''SELECT * FROM genedb WHERE %(sp_id)s=0 OR sp_id=0 OR sp_id=%(sp_id)s ORDER BY gdb_id;''',
                {'sp_id': sp_id})

        return list(dictify_cursor(cursor))


def get_ode_ref_id(value, sp_id):
    value = value.lower()
    ids = []
    with PooledCursor() as cursor:
        if sp_id == 'None':
            cursor.execute(
                '''SELECT ode_ref_id FROM gene WHERE lower(ode_ref_id) LIKE '%%%s%%' ''' % (value,)
            )
        else:
            cursor.execute(
                '''SELECT ode_ref_id FROM gene WHERE lower(ode_ref_id) LIKE '%%%s%%' AND sp_id=%s''' % (value, sp_id,)
            )
    results = cursor.fetchall()
    for res in results:
        ids.append(res[0])
    return ids


def get_microarray_types(sp_id=0):
    """
    get all rows from the platform table with the given species identifier
    :param sp_id:	the species identifier
    :return:		the list of rows from the platform table
    """
    with PooledCursor() as cursor:
        cursor.execute(
                '''SELECT * FROM platform WHERE (sp_id=%(sp_id)s OR 0=%(sp_id)s) ORDER BY pf_name;''',
                {'sp_id': sp_id})
        return list(dictify_cursor(cursor))


def get_news():
    """
    get the top three stories from the news feed.
    :return: array of stories
    """
    with PooledCursor() as cursor:
        cursor.execute(
                '''SELECT nf_title, nf_date, nf_text, nf_type FROM odestatic.news_feed ORDER BY nf_timestamp DESC LIMIT 3;'''
        )
        news = list(dictify_cursor(cursor))
        return news


def get_stats():
    """
    get the number of tier I, II, III, IV genesets
    :return:
    """
    final_stats = []
    with PooledCursor() as cursor:
        cursor.execute(
                '''
            SELECT stat_geneset, stat_genes, stat_res, stat_users
              FROM (SELECT count(*) FROM result) AS stat_res,
              (SELECT count(DISTINCT usr_id) FROM result) AS stat_users,
              (SELECT count(*) FROM gene) AS stat_genes,
              (SELECT count(*) FROM geneset WHERE cur_id IN (1,2,3,4)) AS stat_geneset;
            '''
        )
        stats = dictify_cursor(cursor)
        for k in stats:
            for v in k:
                final_stats.append(k[v][1:-1])
        return final_stats


# *************************************

def delete_geneset_by_gsid(rargs):
    usr_id = rargs.get('user_id', type=int)
    gs_id = rargs.get('gs_id', type=int)
    with PooledCursor() as cursor:
        cursor.execute(
                '''
            UPDATE geneset
            SET gs_status = 'deleted'
            WHERE gs_id =%s AND usr_id =%s;
            ''',
                (gs_id, usr_id,)
        )
        cursor.connection.commit()
        return


def delete_project_by_id(rargs):
    projids = rargs.split(',')
    user_id = flask.session['user_id']
    if user_id != 0 or get_user(user_id).is_admin is not False or get_user(user_id).is_curator is not False:
        with PooledCursor() as cursor:
            cursor.execute('''DELETE from project2geneset WHERE pj_id in (%s)''' % ",".join(str(x) for x in projids))
            cursor.execute('''DELETE from project WHERE pj_id in (%s)''' % ",".join(str(x) for x in projids))
            # print cursor.statusmessage
            cursor.connection.commit()
        return


def add_project_by_name(name, comment):
    name = name
    comment = comment
    if name == '':
        return {'error': 'You must provide a valid Project Name'}
    else:
        user_id = flask.session['user_id']
        if user_id != 0 or get_user(user_id).is_admin is not False or get_user(user_id).is_curator is not False:
            with PooledCursor() as cursor:
                cursor.execute('''INSERT INTO project (usr_id, pj_name, pj_created, pj_notes) VALUES
                                (%s, %s, now(), %s)''', (user_id, name, comment,))
                # print cursor.statusmessage
                cursor.connection.commit()
            return {'error': 'None'}
        else:
            return {'error': 'You do not have permission to add a Project to this account.'}


def change_project_by_id(rargs):
    id = rargs['projid']
    name = rargs['projname']
    notes = rargs['comments']
    if name == '':
        return {'error': 'You must provide a valid Project Name'}
    else:
        user_id = flask.session['user_id']
        if user_id != 0 or get_user(user_id).is_admin is not False or get_user(user_id).is_curator is not False:
            with PooledCursor() as cursor:
                cursor.execute('''UPDATE project SET pj_name=%s, pj_notes=%s WHERE pj_id=%s''', (name, notes, id,))
                # print cursor.statusmessage
                cursor.connection.commit()
            return {'error': 'None'}
        else:
            return {'error': 'You do not have permission to add a Project to this account.'}


def delete_geneset_value_by_id(rargs):
    gs_id = rargs.get('gsid', type=int)
    gene_id = rargs.get('id', type=str)
    with PooledCursor() as cursor:
        cursor.execute('''DELETE from temp_geneset_value WHERE gs_id=%s AND src_id =%s''', (gs_id, gene_id,))
        # print cursor.statusmessage
        cursor.connection.commit()
        return


def user_is_owner(usr_id, gs_id):
    with PooledCursor() as cursor:
        cursor.execute('''SELECT COUNT(gs_id) FROM geneset WHERE usr_id=%s AND gs_id=%s''', (usr_id, gs_id))
        return cursor.fetchone()[0]


def user_is_assigned_curation(usr_id, gs_id):
    with PooledCursor() as cursor:
        cursor.execute('''SELECT COUNT(gs_id) FROM curation_assignments WHERE curator=%s AND gs_id=%s AND curation_state=%s''', (usr_id, gs_id, CurationAssignment.ASSIGNED))

        if cursor.fetchone()[0] == 0:
            return False
        return True


def user_can_edit(usr_id, gs_id):
    if user_is_owner(usr_id, gs_id) or user_is_assigned_curation(usr_id, gs_id):
        return True

    return False


def edit_geneset_id_value_by_id(rargs):
    gs_id = rargs.get('gsid', type=int)
    gene_id = rargs.get('id', type=str)
    gene_old = rargs.get('idold', type=str)
    value = rargs.get('value', type=float)
    user_id = flask.session['user_id']
    if (get_user(user_id).is_admin != 'False' or
                get_user(user_id).is_curator != 'False') or user_can_edit(user_id,
                                                                          gs_id):
        with PooledCursor() as cursor:
            cursor.execute('''UPDATE temp_geneset_value SET src_id=%s, src_value=%s WHERE gs_id=%s AND src_id=%s''',
                           (gene_id, value, gs_id, gene_old,))
            cursor.connection.commit()
            return

def update_geneset_values(gs_id):
    '''
    update file_contents column in file table with values from
    production.temp_geneset_values data, and run reparse_geneset_values
    stored procedure to update geneset data

    :param gs_id (geneset id)
    :return

    '''
    file_contents = ""
    with PooledCursor() as cursor:
        #get the file_id row in file table to update
        fsql = "select file_id from production.geneset where gs_id = {}".format(gs_id)
        cursor.execute(fsql)
        file_id = cursor.fetchone()[0]
        '''get all gene data from temp_geneset values table and 
                create a tab delimited string with newline characters
                for each gene / value pair'''
        sql = "select src_value, src_id from production.temp_geneset_value where gs_id = {}".format(gs_id)
        cursor.execute(sql)
        for row in cursor:
            file_contents += "{}\t{}\n".format(str(row[1]), row[0])
        #update the file_contents field in the file table
        udsql = "update production.file set file_contents = '{}' where file_id={}".format(file_contents, file_id)
        cursor.execute(udsql)
        cursor.connection.commit()
        #run the reparse_geneset_file() stored procedure
        rgf = "select production.reparse_geneset_file({})".format(gs_id)
        cursor.execute(rgf)
        cursor.connection.commit()
        return


def add_geneset_gene_to_temp(rargs):
    gs_id = rargs.get('gsid', type=int)
    gene_id = rargs.get('id', type=str)
    value = rargs.get('value', type=float)
    user_id = flask.session['user_id']
    if (get_user(user_id).is_admin != 'False' or
                get_user(user_id).is_curator != 'False') or user_can_edit(user_id,
                                                                          gs_id):
        with PooledCursor() as cursor:
            ##Check to see if ode_gene_id exists
            cursor.execute('''SELECT g.ode_gene_id FROM gene g, geneset gs WHERE gs.gs_id=%s AND gs.sp_id=g.sp_id AND
							  g.ode_ref_id=%s''', (gs_id, gene_id,))
            if cursor.rowcount == 0:
                return {'error': 'Identifier Not Found'}
            else:
                ode_gene_id = cursor.fetchone()[0]
            ##Check to see if the src_id already exists
            cursor.execute('''SELECT src_id FROM temp_geneset_value WHERE gs_id=%s AND src_id=%s''', (gs_id, gene_id,))
            if cursor.rowcount != 0:
                return {'error': 'The Source Identifier already exists for this geneset'}
            ##Insert into temp table
            cursor.execute('''INSERT INTO temp_geneset_value (gs_id, ode_gene_id, src_value, src_id)
							  VALUES (%s, %s, %s, %s)''', (gs_id, ode_gene_id, value, gene_id,))
            cursor.connection.commit()
            return {'error': 'None'}


def cancel_geneset_edit_by_id(rargs):
    gs_id = rargs.get('gsid', type=int)
    user_id = rargs.get('user_id', type=int)
    if (get_user(user_id).is_admin != 'False' or get_user(user_id).is_curator != 'False') or user_can_edit(user_id,
                                                                                                           gs_id):
        with PooledCursor() as cursor:
            cursor.execute('''DELETE FROM temp_geneset_value WHERE gs_id=%s''', (gs_id,))
            cursor.execute('''DELETE FROM temp_geneset_meta WHERE gs_id=%s''', (gs_id,))
            cursor.connection.commit()
            return gs_id


def update_geneset(usr_id, form):
    """
    Selectively updates geneset metacontent and publication information. The
    function determines how to update things in the following order: 
    If a PMID (pub_pubmed) is provided, all metacontent fields will be 
    updated. 
    If a PMID is not provided and all other metacontent fields are blank, all
    publication information associated with the geneset is removed. 
    Finally, if any metacontent fields are filled out, all publication
    metacontent fields are updated and a new publication ID (pub_id) is created
    depending on whether it already exstis or not.

    :param usr_id:  ID of the user updating the geneset
    :param form:    form dict containing data from the edit geneset form
    :return:        an object containing two fields, 'success' and 'error'. If
                    any error occurs during update 'success' is set to False
                    and the error message is contained in 'error'. A successful
                    update results in 'success' being set to True and the 'error'
                    field missing from the result dict.
    """

    gs_id = int(form.get('gs_id', 0))
    gs_abbreviation = form.get('gs_abbreviation', '').strip()
    gs_description = form.get('gs_description', '').strip()
    gs_name = form.get('gs_name', '').strip()
    gs_threshold_type = int(form.get('gs_threshold_type', 0))
    pub_authors = form.get('pub_authors', '').strip()
    pub_title = form.get('pub_title', '').strip()
    pub_abstract = form.get('pub_abstract', '').strip()
    pub_journal = form.get('pub_journal', '').strip()
    pub_volume = form.get('pub_volume', '').strip()
    pub_pages = form.get('pub_pages', '').strip()
    pub_month = form.get('pub_month', '').strip()
    pub_year = form.get('pub_year', '').strip()
    pub_pubmed = form.get('pub_pubmed', '').strip()
    pub_id = form.get('pub_id', '').strip()

    ## Should have already been checked but does't hurt to do it again I guess
    if ((get_user(usr_id).is_admin == False and\
        get_user(usr_id).is_curator == False) and\
        (user_is_owner(usr_id, gs_id) != 1) and not
        user_is_assigned_curation(usr_id, gs_id)):
            return {
                'success': False,
                'error': 'You do not have permission to update this GeneSet'
            }

    if not gs_abbreviation or not gs_description or not gs_name:
        return {
            'success': False,
            'error': 'You did not provide a required field'
        }

    ## PMID exists, we insert a new publication entry if it doesn't already
    ## exist in the publication table
    if pub_pubmed:
        with PooledCursor() as cursor:
            cursor.execute('''
                INSERT INTO publication (
                    pub_authors, pub_title, pub_abstract, pub_journal, 
                    pub_volume, pub_pages, pub_month, pub_year, pub_pubmed
                )
				SELECT %s, %s, %s, %s, %s, %s, %s, %s, %s
				WHERE NOT EXISTS (
                    SELECT 1 
                    FROM publication 
                    WHERE pub_pubmed = %s
                );
                ''', (pub_authors, pub_title, pub_abstract, pub_journal,
                      pub_volume, pub_pages, pub_month, pub_year, pub_pubmed,
                      pub_pubmed)
            )

            cursor.connection.commit()

        with PooledCursor() as cursor:
            cursor.execute('''
                SELECT pub_id 
                FROM publication 
                WHERE pub_pubmed = %s;
                ''', (pub_pubmed,)
            )

            pub_id = cursor.fetchone()[0]

    ## All publication metacontent is missing, any publication info associated
    ## with this geneset is removed
    elif not pub_authors and not pub_title and not pub_abstract and\
         not pub_journal and not pub_volume and not pub_pages and\
         not pub_month and not pub_year:
             pub_id = None

    ## Some publication metacontent is filled out, we update all metacontent
    ## fields
    else:
        ## A pub_id already exists, we don't need to do any insertions
        if pub_id:
            with PooledCursor() as cursor:
                cursor.execute('''
                    UPDATE publication 
                    SET pub_title = %s, pub_abstract = %s, pub_journal = %s, 
                        pub_volume = %s, pub_pages = %s, pub_month = %s, 
                        pub_year = %s, pub_pubmed = %s 
                    FROM geneset 
                    WHERE publication.pub_id = geneset.pub_id AND
						  geneset.gs_id = %s;
                    ''', (pub_title, pub_abstract, pub_journal, pub_volume,
                          pub_pages, pub_month, pub_year, pub_pubmed, gs_id,)
                )

                cursor.connection.commit()

        ## No pub_id exists, we need to insert a new publication entry
        else:
            with PooledCursor() as cursor:
                cursor.execute('''
                    INSERT INTO publication (
                        pub_authors, pub_title, pub_abstract, pub_journal, 
                        pub_volume, pub_pages, pub_month, pub_year
                    ) 
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s
                    ) 
                    RETURNING pub_id;
                    ''', (pub_authors, pub_title, pub_abstract, pub_journal,
                          pub_volume, pub_pages, pub_month, pub_year)
                )

                cursor.connection.commit()

                pub_id = cursor.fetchone()[0]

    # update geneset with changes
    with PooledCursor() as cursor:
        sql = cursor.mogrify('''
            UPDATE geneset 
            SET pub_id = %s, gs_name = (%s), gs_abbreviation = (%s), 
                gs_description = (%s), gs_threshold_type = (%s)
			WHERE gs_id = %s;
            ''', (pub_id, gs_name, gs_abbreviation, gs_description, gs_threshold_type, gs_id,)
        )

        cursor.execute(sql)
        cursor.connection.commit()

    return {'success': True}


def byteify(input):
    if isinstance(input, dict):
        return {byteify(key): byteify(value) for key, value in input.iteritems()}
    elif isinstance(input, list):
        return [byteify(element) for element in input]
    elif isinstance(input, unicode):
        return input.encode('utf-8')
    else:
        return input


def clear_geneset_ontology(gs_id):
    with PooledCursor() as cursor:
        cursor.execute(
                '''
            DELETE FROM geneset_ontology
            WHERE gs_id=%s;
            ''',
                (gs_id,)
        )
        cursor.connection.commit()


def add_ont_to_geneset(gs_id, ont_id, gso_ref_type):
    with PooledCursor() as cursor:
        cursor.execute('''
            INSERT INTO geneset_ontology
                (gs_id, ont_id, gso_ref_type) 
            VALUES 
                (%s, %s, %s);
            ''', (gs_id, ont_id, gso_ref_type))
        cursor.connection.commit()

def get_ontologies_by_refs(ont_ref_ids):
    """
    Returns ont_ids (if they exist) for each of the given ont_ref_ids.

    :param ont_ref_ids: list of the ontology reference IDs
    :return:            list of ont_ids
    """

    ont_ref_ids = tuple(ont_ref_ids)

    with PooledCursor() as cursor:
        cursor.execute('''
            SELECT ont_id
            FROM ontology
            WHERE ont_ref_id IN %s
            ''', (ont_ref_ids,))

        result = cursor.fetchall()

        if not result:
            return []

        return map(lambda t: t[0], result)

def does_geneset_have_annotation(gs_id, ont_id):
    """
    Checks to see if a particular ontology term has been annotated to a
    geneset.

    :param gs_id:   geneset ID 
    :param ont_id:  ontology ID for the term being checked
    :return:        true if the term is annotated to the given geneset,
                    otherwise false
    """

    with PooledCursor() as cursor:

        cursor.execute('''
            SELECT EXISTS(
                SELECT 1
                FROM geneset_ontology
                WHERE gs_id = %s AND
                      ont_id = %s
            );
            ''', (gs_id, ont_id))

        return cursor.fetchone()[0]

def get_geneset_annotation_reference(gs_id, ont_id):
    """
    Returns the reference type for an ontology term that's been annotated to a
    geneset.

    :param gs_id:   geneset ID
    :param ont_id:  ontology term ID
    :return:        the reference type (a string) if it exists, otherwise None
    """

    with PooledCursor() as cursor:

        cursor.execute('''
            SELECT gso_ref_type
            FROM geneset_ontology
            WHERE gs_id = %s AND
                  ont_id = %s;
            ''', (gs_id, ont_id))

        result = cursor.fetchone()

        if not result:
            return None

        return result[0]

def update_geneset_ontology_reference(gs_id, ont_id, ref_type):
    """
    Updates the ontology reference type for the given geneset and ontology
    term.

    :param gs_id:       geneset ID 
    :param ont_id:      ontology ID for the term being checked
    :param ref_type:    new reference type
    """

    with PooledCursor() as cursor:

        cursor.execute('''
            UPDATE geneset_ontology
            SET gso_ref_type = %s
            WHERE gs_id = %s AND
                  ont_id = %s;
            ''', (ref_type, gs_id, ont_id))

        cursor.connection.commit()

def add_project(usr_id, pj_name):
    with PooledCursor() as cursor:
        cursor.execute(
                ''' INSERT INTO production.project
                (usr_id, pj_name) VALUES (%s, %s)
                RETURNING pj_id;
                ''', (usr_id, pj_name,))
        cursor.connection.commit()
    return cursor.fetchone()[0]


def add_geneset2project(pj_id, gs_id):
    """ Function to associate a geneset with a project in the database.
    
    Args:
        proj_id (int): The ID of the project to which geneset will be associated
        gs_id (int): The ID of the geneset to associate with the project

    Returns:
        Nothing

    """

    if gs_id[:2] == 'GS':
        gs_id = gs_id[2:]
    with PooledCursor() as cursor:
        cursor.execute(
                ''' INSERT INTO project2geneset
                (pj_id, gs_id) SELECT %s, %s
                WHERE NOT EXISTS
                (SELECT pj_id, gs_id FROM project2geneset WHERE pj_id=%s AND gs_id=%s)
              ''', (pj_id, gs_id, pj_id, gs_id)
        )
        cursor.connection.commit()


def get_selected_genesets_by_projects(gs_ids):
    """
    :param gs_ids:
    :return: all genesets and projects associated with gs_ids
    """
    if flask.session['user_id']:
        user_id = flask.session['user_id']
        gs_id = gs_ids.split(',')
        with PooledCursor() as cursor:
            cursor.execute(
                    '''SELECT p2g.pj_id, p2g.gs_id, pj.pj_name, gs.gs_name FROM
                        project2geneset p2g, project pj, geneset gs
                    WHERE p2g.pj_id=pj.pj_id AND pj.usr_id=%s AND gs.gs_id=p2g.gs_id AND
                    p2g.gs_id IN (%s)''' % (
                    user_id, ",".join(str(x) for x in gs_id),)
            )
            genesets = list(dictify_cursor(cursor))
            return genesets if len(genesets) > 0 else None
    else:
        return None


def user_is_project_owner(user_id, proj_id):
    with PooledCursor() as cursor:
        cursor.execute('''SELECT COUNT(pj_id) FROM project WHERE usr_id=%s AND pj_id=%s''', (user_id, proj_id))
        return cursor.fetchone()[0]


def remove_geneset_from_project(rargs):
    user_id = flask.session['user_id']
    gs_id = rargs.get('gs_id', type=int)
    proj_id = rargs.get('proj_id', type=int)
    if get_user(user_id).is_admin or user_is_project_owner(user_id, proj_id):
        with PooledCursor() as cursor:
            cursor.execute('''DELETE FROM project2geneset WHERE pj_id=%s AND gs_id=%s''', (proj_id, gs_id,))
            cursor.connection.commit()

def add_geneset_group(gs_id, grp_id):
    """
    Adds a new group to a geneset's gs_groups column. 

    arguments
        gs_id: geneset ID
        group_id: group ID being added
    """

    if not grp_id or not gs_id:
        raise TypeError('Both gs_id and grp_id cannot be none.')

    grp_id = str(grp_id)

    with PooledCursor() as cursor:
        cursor.execute(
            '''SELECT gs_groups
               FROM geneset
               WHERE gs_id = %s;''', (gs_id,)
        )

        groups = cursor.fetchone()

        if not groups:
            raise ValueError('No groups returned for gs_id')

        groups = groups[0].split(',')

        if '-1' in groups:
            groups = []

        if grp_id in groups or '0' in groups:
            raise ValueError('Group exists, or geneset is public')

        groups.append(grp_id)
        groups = ','.join(groups)

        cursor.execute(
            '''UPDATE geneset
               SET gs_groups = %s
               WHERE gs_id = %s;''', (groups, gs_id)
        )
        cursor.connection.commit()


def update_project_groups(proj_id, groups, user_id):
    usr_id = flask.session['user_id']
    if int(user_id) == int(usr_id):
        with PooledCursor() as cursor:
            cursor.execute('''UPDATE project SET pj_groups=%s WHERE pj_id=%s''', (groups, proj_id,))
            cursor.connection.commit()
            return {'error': 'None'}


def update_stared_project(proj_id, user_id):
    if int(user_id) == int(flask.session['user_id']):
        with PooledCursor() as cursor:
            cursor.execute('''SELECT pj_star FROM project WHERE pj_id=%s''', (proj_id,))
            star = 't' if cursor.fetchone()[0] == 'f' else 'f'
            cursor.execute('''UPDATE project SET pj_star=%s WHERE pj_id=%s''', (star, proj_id,))
            cursor.connection.commit()
        return {'error': 'None'}


def remove_genesets_from_multiple_projects(rargs):
    user_id = flask.session['user_id']
    pjgs = rargs.get('pjgs', type=str)
    ids = pjgs.split(',')
    for i in ids:
        pj = i.split('-')[0]
        gs = i.split('-')[1]
        if get_user(user_id).is_admin or user_is_project_owner(user_id, pj):
            with PooledCursor() as cursor:
                cursor.execute('''DELETE FROM project2geneset WHERE pj_id=%s AND gs_id=%s''', (pj, gs,))
                cursor.connection.commit()
    return {'error': 'None'}


def remove_ont_from_geneset(gs_id, ont_id, gso_ref_type):
    with PooledCursor() as cursor:
        cursor.execute('''
            DELETE FROM geneset_ontology
            WHERE gs_id = %s AND 
                  ont_id = %s
            ''', (gs_id, ont_id)
        )
        cursor.connection.commit()
        return


def delete_results_by_runhash(rargs):
    # ToDO: Remove results from RESULTS Dir
    user_id = rargs.get('user_id', type=int)
    runHash = rargs.get('runHash', type=str)
    with PooledCursor() as cursor:
        cursor.execute(
                '''
            DELETE FROM result
            WHERE usr_id=%s AND res_runhash=%s;
            ''',
                (user_id, runHash,)
        )
        cursor.connection.commit()
        return


def edit_results_by_runhash(rargs):
    user_id = rargs.get('user_id', type=int)
    runHash = rargs.get('runHash', type=str)
    editName = rargs.get('editName', type=str)
    with PooledCursor() as cursor:
        cursor.execute(
                '''
            UPDATE result SET res_name=%s
            WHERE usr_id=%s AND res_runhash=%s;
            ''',
                (editName, user_id, runHash,)
        )
        cursor.connection.commit()
        return


def update_threshold_values(rargs):
    user_id = rargs.get('user_id', type=int)
    min = rargs.get('min', type=float)
    max = rargs.get('max', type=float)
    gs_id = rargs.get('gs_id', type=int)
    if (get_user(user_id).is_admin != 'False' or get_user(user_id).is_curator != 'False') or user_is_owner(user_id,
                                                                                                           gs_id) != 0 or user_is_assigned_curation(user_id, gs_id):
        minmax = str(min) + ',' + str(max)
        with PooledCursor() as cursor:
            cursor.execute('''UPDATE geneset SET gs_threshold_type=5, gs_threshold=%s WHERE gs_id=%s''',
                           (minmax, gs_id,))
            cursor.connection.commit()
            return {'error': 'None'}


def get_server_side_genesets(rargs):
    user_id = rargs.get('user_id', type=int)

    select_columns = ['', 'sp_id', 'cur_id', 'gs_attribution', 'gs_count', 'gs_id', 'gs_name']
    select_clause = """SELECT gs_status, sp_id, cur_id, gs_attribution, gs_count, GS.gs_id, gs_name, gs_abbreviation, gs_description,
					to_char(gs_created, '%s'), to_char(gs_updated, '%s'), curation_group, grp_name FROM geneset GS
					LEFT OUTER JOIN curation_assignments CA ON CA.gs_id = GS.gs_id
					LEFT OUTER JOIN grp G ON G.grp_id = CA.curation_group
					WHERE gs_status NOT LIKE 'de%%' AND usr_id=%s""" % \
                    ('YYYY-MM-DD', 'YYYY-MM-DD', user_id,)
    source_columns = ['cast(sp_id as text)', 'cast(cur_id as text)', 'cast(gs_attribution as text)',
                      'cast(gs_count as text)',
                      'cast(gs.gs_id as text)', 'cast(gs_name as text)']

    # Paging
    iDisplayStart = rargs.get('start', type=int)
    iDisplayLength = rargs.get('length', type=int)
    limit_clause = 'LIMIT %d OFFSET %d' % (iDisplayLength, iDisplayStart) \
        if (iDisplayStart is not None and iDisplayLength != -1) \
        else ''

    # searching
    search_value = rargs.get('search[value]')
    search_clauses = []
    if search_value:
        for i in range(len(source_columns)):
            search_clauses.append('''%s LIKE '%%%s%%' ''' % (source_columns[i], search_value))
        search_clause = 'OR '.join(search_clauses)
    else:
        search_clause = ''

    # Sorting
    sorting_col = select_columns[rargs.get('order[0][column]', type=int)]
    sorting_direction = rargs.get('order[0][dir]', type=str)
    sort_dir = 'ASC NULLS LAST' \
        if sorting_direction == 'asc' \
        else 'DESC NULLS LAST'
    order_clause = 'ORDER BY %s %s' % (sorting_col, sort_dir) if sorting_col else ''

    # joins all clauses together as a query
    if search_clause:
        where_clause = ' AND (%s' % search_clause
        where_clause += ') '

    else:
        where_clause = ''

    # print where_clause
    sql = ' '.join([select_clause,
                    where_clause,
                    order_clause,
                    limit_clause]) + ';'

    with PooledCursor() as cursor:
        # cursor.execute(sql, ac_patterns + pc_patterns)
        cursor.execute(sql)
        things = cursor.fetchall()

        sEcho = rargs.get('sEcho', type=int)

        # Count of all values in table
        cursor.execute("SELECT COUNT(*) FROM geneset WHERE gs_status NOT LIKE 'de%%' AND usr_id = %d" % user_id)
        iTotalRecords = cursor.fetchone()[0]

        # Count of all values that satisfy WHERE clause
        iTotalDisplayRecords = iTotalRecords
        if where_clause:
            sql = ' '.join([select_clause, where_clause]) + ';'
            # cursor.execute(sql, ac_patterns + pc_patterns)
            cursor.execute(sql)
            iTotalDisplayRecords = cursor.rowcount

        response = {'sEcho': sEcho,
                    'iTotalRecords': iTotalRecords,
                    'iTotalDisplayRecords': iTotalDisplayRecords,
                    'aaData': things
                    }

        return response


def get_server_side_grouptasks(rargs):
    group_id = rargs.get('group_id', type=int)
    sEcho = rargs.get('sEcho', type=int)
    response = {'sEcho': sEcho,
                'iTotalRecords': 0,
                'iTotalDisplayRecords': 0,
                'aaData': []
                }
    if group_id:
        select_columns = ['full_name', 'task_id', 'task', 'task_type', 'updated', 'task_status', 'reviewer']
        # The GeneSet half of the query
        select_clause = """
          SELECT uc.usr_last_name || ', ' || uc.usr_first_name AS full_name,
                 gs.gs_id AS task_id,
                 'GS' || gs.gs_id AS task,
                 'GeneSet' AS task_type,
                 to_char(ca.updated, 'YYYY-MM-DD') AS updated,
                 ca.curation_state AS task_status,
                 ur.usr_last_name || ', ' || ur.usr_first_name AS reviewer,
                 p.pub_pubmed AS pubmedid,
                 0 AS geneset_count,
                 pa.id AS pub_assign_id
        """

        # The publication half of the query
        union_select = """
          SELECT uc1.usr_last_name || ', ' || uc1.usr_first_name AS full_name,
                 pa.id AS task_id,
                 p.pub_pubmed AS task,
                 'Publication' AS task_type,
                 to_char(pa.updated, 'YYYY-MM-DD') AS updated,
                 pa.assignment_state AS task_status,
                 ur1.usr_last_name || ', ' || ur1.usr_first_name AS reviewer,
                 null AS pubmedid,
                 count(gpa.gs_id) AS geneset_count,
                 null AS pub_assign_id
        """

        # Separate FROM and WHERE for counting purposes
        # GeneSet where clause
        from_where = """
          FROM production.grp g,
               production.geneset gs,
               production.curation_assignments ca
               LEFT OUTER JOIN production.usr uc ON ca.curator = uc.usr_id
               LEFT OUTER JOIN production.usr ur ON ca.reviewer = ur.usr_id
               LEFT OUTER JOIN production.gs_to_pub_assignment gpa ON ca.gs_id = gpa.gs_id
               LEFT OUTER JOIN production.pub_assignments pa ON gpa.pub_assign_id = pa.id
               and pa.curation_group = ca.curation_group
               LEFT OUTER JOIN production.publication p ON pa.pub_id = p.pub_id
          WHERE g.grp_id = %s
            AND g.grp_id = ca.curation_group
            AND ca.gs_id = gs.gs_id
        """ % (group_id)

        # Publication where clause
        union_where = """
          FROM production.grp g1,
               production.publication p,
               production.pub_assignments pa
               LEFT OUTER JOIN production.usr uc1 ON pa.assignee = uc1.usr_id
               LEFT OUTER JOIN production.usr ur1 ON pa.assigner = ur1.usr_id
               LEFT OUTER JOIN production.gs_to_pub_assignment gpa ON pa.id = gpa.pub_assign_id
          WHERE g1.grp_id = %s
            AND g1.grp_id = pa.curation_group
            AND pa.pub_id = p.pub_id
        """ % (group_id)

        group_by = """
          GROUP BY full_name, task_id, task, task_type, updated, task_status, reviewer
        """

        search_columns = ['cast(uc.usr_first_name as text)',
                          'cast(uc.usr_last_name as text)',
                          'cast(gs.gs_id as text)',
                          'cast(ca.updated as text)',
                          'cast(ca.curation_state as text)',
                          'cast(ur.usr_first_name as text)',
                          'cast(ur.usr_last_name as text)']

        union_columns  = ['cast(uc1.usr_first_name as text)',
                          'cast(uc1.usr_last_name as text)',
                          'cast(p.pub_pubmed as text)',
                          'cast(pa.updated as text)',
                          'cast(pa.assignment_state as text)',
                          'cast(ur1.usr_first_name as text)',
                          'cast(ur1.usr_last_name as text)']

        # Paging
        iDisplayStart = rargs.get('start', type=int)
        iDisplayLength = rargs.get('length', type=int)
        limit_clause = 'LIMIT %d OFFSET %d' % (iDisplayLength, iDisplayStart) \
            if (iDisplayStart is not None and iDisplayLength != -1) \
            else ''

        # Searching
        search_value = rargs.get('search[value]')
        search_clauses = []
        union_clauses = []
        if search_value.startswith('status='):
            search_value = search_value[7:]
            search_clause = '''%s = '%s' ''' % (search_columns[4], search_value)
            union_clause = '''%s = '%s' ''' % (union_columns[4], search_value)
        elif search_value:
            search_clauses = ['''%s LIKE '%%%s%%' ''' % (search_columns[i], search_value) for i in range(len(search_columns))]
            union_clauses = ['''%s LIKE '%%%s%%' ''' % (union_columns[i], search_value) for i in range(len(union_columns))]
            search_clause = 'OR '.join(search_clauses)
            union_clause = 'OR '.join(union_clauses)
        else:
            search_clause = ''
            union_clause = ''

        if search_clause:
            search_where_clause = ' AND (%s' % search_clause
            search_where_clause += ') '
            union_where_clause = ' AND (%s' % union_clause
            union_where_clause += ') '

        else:
            search_where_clause = ''
            union_where_clause = ''

        # Sorting
        sorting_col = select_columns[rargs.get('order[0][column]', type=int)]
        sorting_direction = rargs.get('order[0][dir]', type=str)
        sort_dir = 'ASC NULLS FIRST' \
            if sorting_direction == 'asc' \
            else 'DESC NULLS FIRST'
        order_clause = 'ORDER BY %s %s' % (sorting_col, sort_dir) if sorting_col else ''

        # Joins all clauses together as a query
        sql = ' '.join([select_clause,
                        from_where,
                        search_where_clause,
                        " UNION ",
                        union_select,
                        union_where,
                        union_where_clause,
                        group_by,
                        order_clause,
                        limit_clause]) + ';'

        with PooledCursor() as cursor:
            cursor.execute(sql)
            things = cursor.fetchall()

            # Count of all values in table
            count_query = ' '.join(["SELECT COUNT(1)", from_where]) + ';'
            cursor.execute(count_query)
            iTotalRecords = cursor.fetchone()[0]
            count_query = ' '.join(["SELECT COUNT(1)", union_where]) + ';'
            cursor.execute(count_query)
            iTotalRecords += cursor.fetchone()[0]

            # Count of all values that satisfy WHERE clause
            iTotalDisplayRecords = iTotalRecords
            if search_where_clause:
                sql = ' '.join([select_clause, from_where, search_where_clause]) + ';'
                cursor.execute(sql)
                iTotalDisplayRecords = cursor.rowcount
                sql = ' '.join([union_select, union_where, union_where_clause, group_by]) + ';'
                cursor.execute(sql)
                iTotalDisplayRecords += cursor.rowcount

            response = {'sEcho': sEcho,
                        'iTotalRecords': iTotalRecords,
                        'iTotalDisplayRecords': iTotalDisplayRecords,
                        'aaData': things
                        }

    return response


def get_server_side_results(rargs):
    user_id = rargs.get('user_id', type=int)

    select_columns = ['temp', 'res_name', 'res_created', 'res_description', 'res_id', 'res_runhash', 'res_duration']
    ## res_name doesn't exist in the result table...
    select_clause = """SELECT cast(to_char((select now() - res_created), 'DDD') as int) as temp, res_name,
					to_char(res_created, '%s') as res_created, res_description, res_id, res_runhash,
					to_char(age(res_completed, res_created), '%s') as res_duration FROM result
					WHERE usr_id=%s """ % ('YYYY-MM-DD', 'HH24:MI:SS', user_id,)
    source_columns = ['cast(res_id as text)', 'cast(res_runhash as text)', 'cast(res_created as text)',
                      'cast(res_name as text)', 'cast(res_description as text)']

    # Paging
    iDisplayStart = rargs.get('start', type=int)
    iDisplayLength = rargs.get('length', type=int)
    limit_clause = 'LIMIT %d OFFSET %d' % (iDisplayLength, iDisplayStart) \
        if (iDisplayStart is not None and iDisplayLength != -1) \
        else ''

    # searching
    search_value = rargs.get('search[value]')
    search_clauses = []
    if search_value:
        for i in range(len(source_columns)):
            search_clauses.append('''%s LIKE '%%%s%%' ''' % (source_columns[i], search_value))
        search_clause = 'OR '.join(search_clauses)
    else:
        search_clause = ''

    # Sorting
    sorting_col = select_columns[rargs.get('order[0][column]', type=int)]
    sorting_direction = rargs.get('order[0][dir]', type=str)
    sort_dir = 'ASC NULLS LAST' \
        if sorting_direction == 'asc' \
        else 'DESC NULLS LAST'
    order_clause = 'ORDER BY %s %s' % (sorting_col, sort_dir) if sorting_col else ''

    # joins all clauses together as a query
    where_clause = ' AND %s' % search_clause if search_clause else ''
    # print where_clause
    sql = ' '.join([select_clause,
                    where_clause,
                    order_clause,
                    limit_clause]) + ';'
    # print sql

    with PooledCursor() as cursor:
        # cursor.execute(sql, ac_patterns + pc_patterns)
        cursor.execute(sql)
        things = cursor.fetchall()

        sEcho = rargs.get('sEcho', type=int)

        # Count of all values in table
        cursor.execute('SELECT COUNT(*) FROM result WHERE usr_id = %d' % user_id)
        iTotalRecords = cursor.fetchone()[0]

        # Count of all values that satisfy WHERE clause
        iTotalDisplayRecords = iTotalRecords
        if where_clause:
            sql = ' '.join([select_clause, where_clause]) + ';'
            # cursor.execute(sql, ac_patterns + pc_patterns)
            cursor.execute(sql)
            iTotalDisplayRecords = cursor.rowcount

        response = {'sEcho': sEcho,
                    'iTotalRecords': iTotalRecords,
                    'iTotalDisplayRecords': iTotalDisplayRecords,
                    'aaData': things
                    }

        return response


def get_server_side(rargs):
    source_table = rargs.get('table', type=str)
    user_id = rargs.get('user_id', type=int)
    source_columns = []
    select_columns = []

    # print source_table

    i = 0
    temp = rargs.get('columns[%d][name]' % i)
    while temp is not None:
        col_name = 'cast(' + temp + ' as text)'
        source_columns.append(col_name)
        select_columns.append(temp)
        i = i + 1
        temp = rargs.get('columns[%d][name]' % i)

    # select and from clause creation
    select_clause = 'SELECT %s ' % ','.join(select_columns)
    from_clause = 'FROM %s' % source_table

    # Paging
    iDisplayStart = rargs.get('start', type=int)
    iDisplayLength = rargs.get('length', type=int)
    limit_clause = 'LIMIT %d OFFSET %d' % (iDisplayLength, iDisplayStart) \
        if (iDisplayStart is not None and iDisplayLength != -1) \
        else ''

    # searching
    search_value = rargs.get('search[value]')
    search_clauses = []
    if search_value:
        for i in range(len(source_columns)):
            search_clauses.append('''%s LIKE '%%%s%%' ''' % (source_columns[i], search_value))
        search_clause = 'OR '.join(search_clauses)
    # if source_table == 'production.result':
    #	  search_clause += ' AND usr_id = %d ' % user_id
    else:
        # if source_table == 'production.result':
        #	  search_clause = "usr_id = %d " % user_id
        # else:
        search_clause = ''

    # Sorting
    sorting_col = select_columns[rargs.get('order[0][column]', type=int)]
    sorting_direction = rargs.get('order[0][dir]', type=str)
    sort_dir = 'ASC NULLS LAST' \
        if sorting_direction == 'asc' \
        else 'DESC NULLS LAST'
    order_clause = 'ORDER BY %s %s' % (sorting_col, sort_dir) if sorting_col else ''

    # joins all clauses together as a query
    where_clause = 'WHERE %s' % search_clause if search_clause else ''
    # print where_clause
    sql = ' '.join([select_clause,
                    from_clause,
                    where_clause,
                    order_clause,
                    limit_clause]) + ';'
    # print sql

    with PooledCursor() as cursor:
        # cursor.execute(sql, ac_patterns + pc_patterns)
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
            # cursor.execute(sql, ac_patterns + pc_patterns)
            cursor.execute(sql)
            iTotalDisplayRecords = cursor.rowcount

        response = {'sEcho': sEcho,
                    'iTotalRecords': iTotalRecords,
                    'iTotalDisplayRecords': iTotalDisplayRecords,
                    'aaData': things
                    }

        return response


def get_all_columns(table):
    sql = '''SELECT column_name FROM information_schema.columns WHERE table_name='%s'AND table_schema='%s';''' % (
        table.split(".")[1], table.split(".")[0])
    try:
        with PooledCursor() as cursor:
            cursor.execute(sql)
            return list(dictify_cursor(cursor))
    except Exception, e:
        return str(e)


def get_primary_keys(table):
    sql = '''SELECT pg_attribute.attname FROM pg_index, pg_class, pg_attribute WHERE pg_class.oid = '%s'::regclass AND indrelid = pg_class.oid AND pg_attribute.attrelid = pg_class.oid AND pg_attribute.attnum = any(pg_index.indkey) AND indisprimary;''' % (
        table)
    try:
        with PooledCursor() as cursor:
            cursor.execute(sql)
            return list(dictify_cursor(cursor))
    except Exception, e:
        return str(e)


# get all columns for a table that aren't auto increment and can't be null
def get_required_columns(table):
    sql = '''SELECT column_name FROM information_schema.columns WHERE table_name='%s'AND table_schema='%s' AND is_nullable='NO' AND column_name NOT IN (SELECT column_name FROM information_schema.columns WHERE table_name = '%s' AND column_default LIKE '%s' AND table_schema='%s');''' % (
        table.split(".")[1], table.split(".")[0], table.split(".")[1], "%nextval(%", table.split(".")[0])
    try:
        with PooledCursor() as cursor:
            cursor.execute(sql)
            return list(dictify_cursor(cursor))
    except Exception, e:
        return str(e)


# gets all columns for a table that aren't auto increment and can be null
def get_nullable_columns(table):
    sql = '''SELECT column_name FROM information_schema.columns WHERE table_name='%s' AND table_schema='%s' AND is_nullable='YES' AND column_name NOT IN (SELECT column_name FROM information_schema.columns WHERE table_name = '%s' AND column_default LIKE '%s' AND table_schema='%s');''' % (
        table.split(".")[1], table.split(".")[0], table.split(".")[1], "%nextval(%", table.split(".")[0])
    # print sql
    try:
        with PooledCursor() as cursor:
            cursor.execute(sql)
            return list(dictify_cursor(cursor))
    except Exception, e:
        return str(e)


# gets values for columns of specified key(s)
def admin_get_data(table, cols, keys):
    sql = '''SELECT %s FROM %s WHERE %s;''' % (','.join(cols), table, ' AND '.join(keys))
    # print sql
    try:
        with PooledCursor() as cursor:
            cursor.execute(sql)
            return list(dictify_cursor(cursor))
    except Exception, e:
        return str(e)


# removes item from db that has specified primary key(s)
def admin_delete(args, keys):
    table = args.get('table', type=str)

    if len(keys) <= 0:
        return "Error: No primary key constraints set."

    sql = '''DELETE FROM %s WHERE %s;''' % (table, ' AND '.join(keys))

    # print sql
    try:
        with PooledCursor() as cursor:
            cursor.execute(sql)
            cursor.connection.commit()
            return "Deletion Successful"
    except Exception, e:
        return str(e)


# updates columns for specified key(s)
def admin_set_edit(args, keys):
    table = args.get('table', type=str)

    if len(keys) <= 0:
        return "Error: No primary key constraints set"

    colmerge = []
    colkeys = args.keys()
    for key in colkeys:
        if key != 'table':
            value = args.get(key, type=str)
            if value and value != "None":
                colmerge.append(key + '=\'' + value.replace("'", "\'") + '\'')

    sql = '''UPDATE %s SET %s WHERE %s;''' % (table, ','.join(colmerge), ' AND '.join(keys))

    # print sql
    try:
        with PooledCursor() as cursor:
            cursor.execute(sql)
            cursor.connection.commit()
            return "Edit Successful"
    except Exception, e:
        return str(e)


# adds item into db for specified table
def admin_add(args):
    table = args.get('table', type=str)
    source_columns = []
    column_values = []

    keys = args.keys()

    # sql creation
    for key in keys:
        if key != 'table':
            value = args.get(key, type=str)
            if value:
                source_columns.append(key)
                column_values.append(value)

    if len(source_columns) <= 0:
        return "Nothing to insert"
    sql = 'INSERT INTO %s (%s) VALUES (\'%s\');' % (table, ','.join(source_columns), '\',\''.join(column_values))
    # print sql
    try:
        with PooledCursor() as cursor:
            cursor.execute(sql)
            cursor.connection.commit()
            return "Add Successful"
    except Exception, e:
        return str(e)


def genesets_per_tier(includeDeleted):
    if includeDeleted:
        sql1 = '''SELECT count(*) FROM production.geneset WHERE cur_id = 1;'''
        sql2 = '''SELECT count(*) FROM production.geneset WHERE cur_id = 2;'''
        sql3 = '''SELECT count(*) FROM production.geneset WHERE cur_id = 3;'''
        sql4 = '''SELECT count(*) FROM production.geneset WHERE cur_id = 4;'''
        sql5 = '''SELECT count(*) FROM production.geneset WHERE cur_id = 5;'''
    else:
        sql1 = '''SELECT count(*) FROM production.geneset WHERE gs_status NOT LIKE 'de%' AND cur_id = 1;'''
        sql2 = '''SELECT count(*) FROM production.geneset WHERE gs_status NOT LIKE 'de%' AND cur_id = 2;'''
        sql3 = '''SELECT count(*) FROM production.geneset WHERE gs_status NOT LIKE 'de%' AND cur_id = 3;'''
        sql4 = '''SELECT count(*) FROM production.geneset WHERE gs_status NOT LIKE 'de%' AND cur_id = 4;'''
        sql5 = '''SELECT count(*) FROM production.geneset WHERE gs_status NOT LIKE 'de%' AND cur_id = 5;'''

    try:
        with PooledCursor() as cursor:
            cursor.execute(sql1)
            one = cursor.fetchone()[0]
            cursor.execute(sql2)
            two = cursor.fetchone()[0]
            cursor.execute(sql3)
            three = cursor.fetchone()[0]
            cursor.execute(sql4)
            four = cursor.fetchone()[0]
            cursor.execute(sql5)
            five = cursor.fetchone()[0]
            response = OrderedDict([('Tier 1', one),
                                    ('Tier 2', two),
                                    ('Tier 3', three),
                                    ('Tier 4', four),
                                    ('Tier 5', five)
                                    ])
        return response
    except Exception, e:
        return str(e)


def genesets_per_species_per_tier(includeDeleted):
    if includeDeleted:
        sql1 = '''SELECT sp_id, count(*) FROM production.geneset WHERE cur_id = 1 GROUP BY sp_id ORDER BY sp_id;'''
        sql2 = '''SELECT sp_id, count(*) FROM production.geneset WHERE cur_id = 2 GROUP BY sp_id ORDER BY sp_id;'''
        sql3 = '''SELECT sp_id, count(*) FROM production.geneset WHERE cur_id = 3 GROUP BY sp_id ORDER BY sp_id;'''
        sql4 = '''SELECT sp_id, count(*) FROM production.geneset WHERE cur_id = 4 GROUP BY sp_id ORDER BY sp_id;'''
        sql5 = '''SELECT sp_id, count(*) FROM production.geneset WHERE cur_id = 5 GROUP BY sp_id ORDER BY sp_id;'''
    else:
        sql1 = '''SELECT sp_id, count(*) FROM production.geneset WHERE gs_status NOT LIKE 'de%' AND cur_id = 1 GROUP BY sp_id ORDER BY sp_id;'''
        sql2 = '''SELECT sp_id, count(*) FROM production.geneset WHERE gs_status NOT LIKE 'de%' AND cur_id = 2 GROUP BY sp_id ORDER BY sp_id;'''
        sql3 = '''SELECT sp_id, count(*) FROM production.geneset WHERE gs_status NOT LIKE 'de%' AND cur_id = 3 GROUP BY sp_id ORDER BY sp_id;'''
        sql4 = '''SELECT sp_id, count(*) FROM production.geneset WHERE gs_status NOT LIKE 'de%' AND cur_id = 4 GROUP BY sp_id ORDER BY sp_id;'''
        sql5 = '''SELECT sp_id, count(*) FROM production.geneset WHERE gs_status NOT LIKE 'de%' AND cur_id = 5 GROUP BY sp_id ORDER BY sp_id;'''

    try:
        with PooledCursor() as cursor:
            cursor.execute(sql1)
            one = OrderedDict(cursor)
            cursor.execute(sql2)
            two = OrderedDict(cursor)
            cursor.execute(sql3)
            three = OrderedDict(cursor)
            cursor.execute(sql4)
            four = OrderedDict(cursor)
            cursor.execute(sql5)
            five = OrderedDict(cursor)
            response = OrderedDict([('Tier 1', one),
                                    ('Tier 2', two),
                                    ('Tier 3', three),
                                    ('Tier 4', four),
                                    ('Tier 5', five)
                                    ])
        return response
    except Exception, e:
        return str(e)


def get_species_name():
    try:
        with PooledCursor() as cursor:
            cursor.execute('''SELECT sp_id, sp_name FROM odestatic.species;''')
        return OrderedDict(cursor)
    except Exception, e:
        return str(e)


def get_species_id_by_name(sp_name):
    sp_name = sp_name.strip()
    with PooledCursor() as cursor:
        cursor.execute('''SELECT sp_id FROM species WHERE sp_name=%s''', (sp_name,))
        results = cursor.fetchone()[0]
        return results


def get_gdb_id_by_name(gdb_name):
    gdb_name = gdb_name.strip()
    # print gdb_name
    with PooledCursor() as cursor:
        cursor.execute('''SELECT gdb_id FROM genedb WHERE gdb_shortname=%s''', (gdb_name,))
        if cursor.rowcount != 0:
            results = cursor.fetchone()[0]
            return -1 * results
        else:
            cursor.execute('''SELECT pf_id FROM platform WHERE pf_shortname=%s''', (gdb_name,))
            results = cursor.fetchone()[0]
            return results


def monthly_tool_stats():
    tools = [];
    with PooledCursor() as cursor:
        cursor.execute(
                '''SELECT DISTINCT res_tool FROM production.result WHERE res_created >= now() - INTERVAL '30 days';''')
    tools = list(dictify_cursor(cursor))

    try:
        with PooledCursor() as cursor:
            response = OrderedDict()
            for tool in tools:
                cursor.execute(
                        '''SELECT res_created, count(*) FROM production.result WHERE res_created >= now() - interval '30 days' AND res_tool=%s GROUP BY res_created ORDER BY res_created desc;''',
                        (tool['res_tool'],))
                response.update({tool['res_tool']: OrderedDict(cursor)})
        return response
    except Exception, e:
        return str(e)


def get_bimodal_threshold(gs_id):
    with PooledCursor() as cursor:
        cursor.execute('''SELECT gsv_value FROM geneset_value WHERE gs_id=%s GROUP BY gsv_value''', (gs_id,))
        bi_modal = 'True' if cursor.rowcount == 1 else 'False'
        return bi_modal


def user_tool_stats():
    try:
        with PooledCursor() as cursor:
            cursor.execute(
                    '''SELECT usr_id, count(*) FROM production.result WHERE res_created >= now() - INTERVAL '6 months' GROUP BY usr_id ORDER BY count(*) DESC LIMIT 20;''')
        return OrderedDict(cursor)
    except Exception, e:
        return str(e)


def tool_stats_by_user(user_id):
    try:
        with PooledCursor() as cursor:
            cursor.execute('''SELECT res_description, res_started, age(res_completed,res_started) as res_duration
						  FROM production.result
						  WHERE res_created >= now() - interval '30 days' AND usr_id=%s
						  ORDER BY res_started desc;''', (user_id,))
        return list(dictify_cursor(cursor))
    except Exception, e:
        return str(e)


def currently_running_tools():
    try:
        with PooledCursor() as cursor:
            cursor.execute(
                    '''SELECT res_id, usr_id, res_tool, res_status FROM production.result WHERE res_completed IS NULL;''')
        return list(dictify_cursor(cursor))
    except Exception, e:
        return str(e)


def size_of_genesets():
    try:
        with PooledCursor() as cursor:
            cursor.execute(
                    '''SELECT gs_id, gs_count FROM production.geneset WHERE gs_status not like 'de%' ORDER BY gs_count DESC limit 1000;''')
        return OrderedDict(cursor)
    except Exception, e:
        return str(e)


def avg_tool_times(keys, tool):
    sql = '''SELECT avg(res_completed - res_started) FROM production.result WHERE res_tool='%s' AND res_id=%s;''' % (
        tool, ' OR res_id='.join(str(v) for v in keys))
    # print sql
    try:
        with PooledCursor() as cursor:
            cursor.execute(sql)
        return cursor.fetchone()[0]
    except Exception, e:
        return 0


def avg_genes(keys):
    sql = '''SELECT avg(gs_count) FROM production.geneset WHERE gs_id=%s;''' % (' OR gs_id='.join(str(v) for v in keys))
    # print sql
    try:
        with PooledCursor() as cursor:
            cursor.execute(sql)
        return cursor.fetchone()[0]
    except Exception, e:
        return 0


def gs_in_tool_run():
    try:
        with PooledCursor() as cursor:
            cursor.execute(
                    '''SELECT res_id, res_tool, gs_ids, res_completed FROM production.result WHERE res_completed IS NOT NULL ORDER BY res_completed DESC LIMIT 500;''')
        return list(dictify_cursor(cursor))
    except Exception, e:
        return str(e)


def tools():
    try:
        with PooledCursor() as cursor:
            cursor.execute('''SELECT DISTINCT res_tool FROM production.result;''')
        return list(dictify_cursor(cursor))
    except Exception, e:
        return str(e)


# New code for Tools, Next 5 functions Modify usr2gene for Emphasis
# Not tested fucntion, query tested; returns usr id of usr it was inserted for
def create_usr2gene(user_id, ode_gene_id):
    with PooledCursor() as cursor:
        cursor.execute(
                '''
            INSERT INTO extsrc.usr2gene (usr_id, ode_gene_id)
            VALUES (%s, %s)
            ''',
                (user_id, ode_gene_id,)
        )
        cursor.connection.commit()
        # return the primary ID for the insert that we just performed


# insert delete all  with usr id
def delete_usr2gene_by_user(user_id):
    with PooledCursor() as cursor:
        cursor.execute(
                '''DELETE FROM usr2gene WHERE usr_id=%s;''', (user_id,)
        )

        cursor.connection.commit()
        return


# insert delete specific gene_id with usr id
def delete_usr2gene_by_user_and_gene(user_id, ode_gene_id):
    with PooledCursor() as cursor:
        cursor.execute(
                '''DELETE FROM usr2gene WHERE usr_id=%s AND ode_gene_id=%s;''', (user_id, ode_gene_id,)
        )
        cursor.connection.commit()
        return


# Not tested fucntion, query tested; insert get all gene and species stuff from u2g, gene, and species
def get_gene_and_species_info_by_user(user_id):
    with PooledCursor() as cursor:
        cursor.execute(
                '''SELECT gene.*, species.* FROM (extsrc.gene INNER JOIN odestatic.species USING (sp_id))
              INNER JOIN usr2gene USING (ode_gene_id) WHERE gene.ode_pref and usr2gene.usr_id = (%s);''',
                (user_id,))
    return list(dictify_cursor(cursor))


# Not tested fucntion, query tested;gets all gene and species stuff from gene, and species
def get_gene_and_species_info(ode_ref_id):
    with PooledCursor() as cursor:
        cursor.execute(
                '''SELECT gene.*, species.* FROM extsrc.gene INNER JOIN odestatic.species USING (sp_id)
              WHERE lower(ode_ref_id)=lower(%s);''',
                (ode_ref_id,))
    return list(dictify_cursor(cursor))


# end block of Emphasis functions

# *************************************************************
class User:
    def __init__(self, usr_dict):
        self.user_id = usr_dict['usr_id']
        self.first_name = usr_dict['usr_first_name']
        self.last_name = usr_dict['usr_last_name']
        self.email = usr_dict['usr_email']
        self.prefs = usr_dict['usr_prefs']
        self.api_key = usr_dict['apikey']

        usr_admin = usr_dict['usr_admin']
        self.is_curator = usr_admin == 1
        self.is_admin = usr_admin == 2 or usr_admin == 3
        self.last_seen = usr_dict['usr_last_seen']
        self.creation_date = usr_dict['usr_created']
        self.ip_addr = usr_dict['ip_addr']

        self.is_guest = bool(usr_dict['is_guest'])

        self.__projects = None
        self.__shared_projects = None
        self.__get_groups_by_user = None

    @property
    def projects(self):
        if self.__projects is None:
            self.__projects = get_all_projects(self.user_id)

        ## Case insensitive sorting otherwise project names with captial
        ## letters come before those with lowercase. 
        self.__projects = sorted(self.__projects, key=lambda p: p.name.lower())

        return self.__projects

    @property
    def shared_projects(self):
        if self.__shared_projects is None:
            self.__shared_projects = get_shared_projects(self.user_id)
        return self.__shared_projects

    @property
    def get_groups_by_user(self):
        if self.__get_groups_by_user is None:
            self.__get_groups_by_user = get_user_group_membership(self.user_id)
        return self.__get_groups_by_user


def get_user_group_membership(usr_id):
    """
    Returns a list of Group objects for groups the user is a member of.
    Almost a duplicate of "get_user_groups" and the two should probably be
    merged at some point.

    :param usr_id:	the user ID
    :return:		The list of groups the user belongs to
    """

    with PooledCursor() as cursor:
        cursor.execute(
            '''
            SELECT  g.grp_id, g.grp_name, g.grp_private AS private
            FROM    grp AS g, usr2grp AS u2g
            WHERE   usr_id = %s AND
                    g.grp_id = u2g.grp_id;
            ''',
                (usr_id,)
        )

        return [Group(row_dict) for row_dict in dictify_cursor(cursor)]


def get_groups_owned_by_user(user_id):
    """
    returns: all group ids and group names for projects belonging to user_id and group priv = 1
    """
    with PooledCursor() as cursor:
        cursor.execute('''SELECT g.grp_id AS grp_id, g.grp_name AS grp_name, u.u2g_privileges AS priv FROM grp g, usr2grp u
                          WHERE u.usr_id=%s AND u.u2g_privileges=1 AND g.grp_id=u.grp_id''', (user_id, ))
    return [Groups(row_dict) for row_dict in dictify_cursor(cursor)]


def get_group_by_id(group_id):
    """
    Returns a Group by its ID
    :param group_id:   Identifier for the group in question
    :return: A group object for given ID
    """
    with PooledCursor() as cursor:
        cursor.execute('''SELECT g.grp_id AS grp_id, g.grp_name AS grp_name, g.grp_private AS private FROM grp g
                          WHERE g.grp_id=%s''', (group_id,))
        groups = [Group(row_dict) for row_dict in dictify_cursor(cursor)]
    return None if len(groups) == 0 else groups[0]


def get_curation_group():
    """

    :return: Group object representing "core GW Curators group" (GeneWeaverCuration)
    """
    with PooledCursor() as cursor:
        cursor.execute('''SELECT g.grp_id AS grp_id, g.grp_name AS grp_name, g.grp_private AS private FROM grp g
                          WHERE g.grp_name=%s''', ("GeneWeaverCuration",))
        groups = [Group(row_dict) for row_dict in dictify_cursor(cursor)]

    # TODO -- this is a database configuration error if there are multiple
    # groups named GeneWeaverCuration. We should throw an exception if
    # len(groups) > 1
    return None if len(groups) == 0 else groups[0]


def get_all_curators_admins():
    """

    :return: List of Users that are GW Admins or Curators
    """
    with PooledCursor() as cursor:
        cursor.execute('''SELECT * FROM production.usr WHERE usr_admin > 0;''')
        users = [User(row) for row in dictify_cursor(cursor)]
    return users


class Groups:
    """
    This class has a specific purpose for conveying user privleges on a given group
    """
    def __init__(self, grp_dict):
        self.grp_id = grp_dict['grp_id']
        self.grp_name = grp_dict['grp_name']
        self.privileges = grp_dict['priv']


class Group:
    """
    This class is intended to represent a group and whether it's private or public
    """
    def __init__(self, grp_dict):
        self.grp_id = grp_dict['grp_id']
        self.grp_name = grp_dict['grp_name']
        self.private = grp_dict['private']


class Publication:
    def __init__(self, pub_dict):
        self.pub_id = pub_dict['pub_id']
        self.authors = pub_dict['pub_authors'] if 'pub_authors' in pub_dict else ""
        self.title = pub_dict['pub_title']
        self.abstract = pub_dict['pub_abstract']
        self.journal = pub_dict['pub_journal']
        self.volume = pub_dict['pub_volume']
        self.pages = pub_dict['pub_pages']
        self.month = pub_dict['pub_month']
        self.year = pub_dict['pub_year']
        self.pubmed_id = pub_dict['pub_pubmed']

class MSETGeneset:
    def __init__(self, gs_dict):
        self.project_id = gs_dict['pj_id']
        self.int_id = gs_dict['int_id']
        self.user_id = gs_dict['usr_id']
        self.name = gs_dict['pj_name']
        self.description = gs_dict['pj_notes']
        self.creation_date = gs_dict['pj_created']
        #self.num_genes = gs_dict['num_genes']

        # declare value caches for instance properties
        self.__geneset_values = None

    @property
    def geneset_values(self):
        if self.__geneset_values is None:
            self.__geneset_values = get_geneset_values_for_mset(self.project_id, self.int_id)
        return self.__geneset_values

def get_publication_by_pubmed(pubmed_id, create=False):
    """
    get a Publication for a pubmed id
    :param pubmed_id: pubmed id
    :param create: if true, a new database record will be created if the
     Publication does not exist in the database
    :return: Publication object for the specified publication
    """
    with PooledCursor() as cursor:
        cursor.execute("SELECT * from publication WHERE pub_pubmed=CAST(%s as VARCHAR)",
                       (pubmed_id,))

        publications = list(dictify_cursor(cursor))

        publication = None

        if len(publications) >= 1:
            #TODO what to do about pubmed_ids with multiple records?
            publication = Publication(publications[0])
        else:
            #publication is not in database, need to fetch it
            try:
                pub_dict = pubmedsvc.get_pubmed_info(pubmed_id)
                pub_dict['pub_pubmed'] = pubmed_id

            except Exception as e:
                pub_dict = {}

            if pub_dict:
                if create:
                    if 'pub_day' in pub_dict:
                        # get_pubmed_info() may add this to the dict, but it is not
                        # a column in the database, so the INSERT below will fail
                        # if we don't remove it
                        del pub_dict['pub_day']

                    placeholders = ', '.join(['%s'] * len(pub_dict))
                    columns = ', '.join(pub_dict.keys())
                    values = pub_dict.values()

                    sql = '''INSERT INTO publication (%s) VALUES (%s) RETURNING pub_id''' % (columns, placeholders)
                    cursor.execute(sql, values)
                    cursor.connection.commit()

                    pub_dict['pub_id'] = cursor.fetchone()[0]

                # sometimes fields are missing (example, online only articles
                # will not have pages).  We need to make sure the keys at least
                # exist, or we can't create a Publication object
                required_keys = ['pub_volume', 'pub_pages', 'pub_author',
                                 'pub_abstract', 'pub_id', 'pub_year',
                                 'pub_month']

                for key in required_keys:
                    if key not in pub_dict:
                        pub_dict[key] = None

                publication = Publication(pub_dict)

        return publication


def get_publication(pub_id):
    with PooledCursor() as cursor:
        cursor.execute("SELECT * from publication WHERE pub_id=%s",
                       (pub_id,))

        rows = list(dictify_cursor(cursor))
        return Publication(rows[0]) if rows else None

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
        # self.name = gs_dict['gs_name'].decode('utf-8')
        self.name = gs_dict['gs_name']
        self.abbreviation = gs_dict['gs_abbreviation']
        self.pub_id = gs_dict['pub_id']
        if self.pub_id is not None:
            try:
                self.publication = get_all_publications(self.geneset_id)
            except KeyError:
                self.publication = None
        else:
            self.publication = None

        try:
            self.pub_assign_id = gs_dict['pub_assign_id']
        except KeyError:
            self.pub_assign_id = None

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

        # add two values for geneset

        # declare value caches for instance properties
        self.__ontological_associations = None
        self.__geneset_values = None

    @property
    def ontological_associations(self):
        if self.__ontological_associations is None:
            self.__ontological_associations = get_all_ontologies_by_geneset(self.geneset)
        return self.__ontological_associations

    @property
    def geneset_values(self):
        if self.__geneset_values is None:
            self.__geneset_values = get_geneset_values(self.geneset_id)
        return self.__geneset_values


class TempGeneset(Geneset):
    def __init__(self, gs_dict):
        Geneset.__init__(self, gs_dict)
        self.__temp_geneset_values = None

    @property
    def temp_geneset_values(self):
        if self.__temp_geneset_values is None:
            # self.__geneset_values = get_geneset_values(self.geneset_id)
            self.__temp_geneset_values = get_temp_geneset_values(self.geneset_id)
        return self.__temp_geneset_values


class SimGeneset(Geneset):
    def __init__(self, gs_dict):
        Geneset.__init__(self, gs_dict)
        self.jac_value = gs_dict['jac_value']
        self.gic_value = gs_dict['jac_value']


class Ontology:
    def __init__(self, ont_dict):
        self.ontology_id = ont_dict['ont_id']
        self.reference_id = ont_dict['ont_ref_id']
        self.name = ont_dict['ont_name']
        self.description = ont_dict['ont_description']
        self.children = ont_dict['ont_children']
        self.parents = ont_dict['ont_parents']
        self.ontdb_id = ont_dict['ontdb_id']


class Ontologydb:
    def __init__(self, ontdb_dict):
        self.ontologydb_id = ontdb_dict['ontdb_id']
        self.name = ontdb_dict['ontdb_name']
        self.prefix = ontdb_dict['ontdb_prefix']
        self.ncbo_id = ontdb_dict['ontdb_ncbo_id']
        self.date = ontdb_dict['ontdb_date']
        self.linkout_url = ontdb_dict['ontdb_linkout_url']
        self.ncbo_vid = ontdb_dict['ontdb_ncbo_vid']

class GenesetInfo:
    def __init__(self, gi_dict):
        self.geneset_id = gi_dict['gs_id']
        self.page_views = gi_dict['gsi_pageviews']
        self.referers = gi_dict['gsi_referers']
        self.analyses = gi_dict['gsi_analyses']
        self.resource_id = gi_dict['gsi_resource_id']
        self.last_sim = gi_dict['gsi_last_sim']
        self.last_ann = gi_dict['gsi_last_ann']
        self.jac_started = gi_dict['gsi_jac_started']
        self.jac_completed = gi_dict['gsi_jac_completed']

def authenticate_user(email, password):
    """
    Looks up user in the database
    :param email:		the user's email address
    :param password:	the user's password
    :return:			the User with the corresponding email address and password
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
            try:
                cursor.execute(
                        '''SELECT * FROM usr WHERE usr_email=%(email)s AND usr_password=%(password_md5)s;''',
                        {
                            'email': email,
                            'password_md5': password_md5.hexdigest(),
                        }
                )
                users = [User(row_dict) for row_dict in dictify_cursor(cursor)]
                return users[0] if len(users) == 1 else None
            except:
                return None

def update_user_seen(usr_id):
    """
    Updates the usr_last_seen date for a given user.

    arguments
        usr_id: the user ID to update
    """

    if not usr_id:
        return

    with PooledCursor() as cursor:
        cursor.execute(
            '''
            UPDATE  usr
            SET     usr_last_seen = NOW()
            WHERE   usr_id = %s;
            ''',
                (usr_id,)
        )

def get_recent_users():
    """
    Retrieves the 100 most recent users.

    arguments
        usr_id: the user ID to update
    """

    with PooledCursor() as cursor:
        cursor.execute(
            '''
            SELECT   usr_id, usr_email, usr_last_seen
            FROM     production.usr
            WHERE    usr_last_seen IS NOT NULL AND
                     is_guest = FALSE
            ORDER BY usr_last_seen DESC
            LIMIT    100;
            '''
        )

    return dictify_cursor(cursor)

## There's a similarly titled get_result_by_runhash, but it's API function.
def get_results_by_runhash(runhash):
    with PooledCursor() as cursor:
        cursor.execute(
            '''
            SELECT res_data, res_tool
            FROM production.result
            WHERE res_runhash = %s;
            ''',
                (runhash,)
        )

        result = cursor.fetchone()
        print result

        return {'res_data': result[0], 'res_tool': result[1]}


def get_user(user_id):
    """
    Looks up a User in the database
    :param user_id:		the user's ID
    :return:			the User matching the given ID or None if no such user is found
    """
    with PooledCursor() as cursor:
        try:
            cursor.execute('''SELECT * FROM usr WHERE usr_id=%s''', (user_id,))
            users = [User(row_dict) for row_dict in dictify_cursor(cursor)]
            return users[0] if len(users) == 1 else None
        except:
            return None


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


def new_guest():
    """
    Creates a new empty user to use as a guest account
    :return:
    """
    with PooledCursor() as cursor:
        cursor.execute(
            '''INSERT INTO usr
               (usr_first_name, usr_last_name, usr_email, usr_admin, usr_password, usr_last_seen, usr_created, is_guest)
               VALUES
               ('GUEST', 'GUEST', '', '0', '', NOW(), NOW(), 't')
               RETURNING usr_id
            ''', {}
        )
        cursor.connection.commit()
        return get_user(cursor.fetchone()[0])


def register_user(user_first_name, user_last_name, user_email, user_password):
    """
    Insert a user to the db
    :param user_first_name: the user's first name, if not provided use "Guest" as default
    :param user_last_name:	the user's last name, if not provided use "User" as default
    :param user_email:		the user's email address, if not provided use "" as default
    :param user_password:	the user's password, if not provided use "" as default
    """
    with PooledCursor() as cursor:
        password_md5 = md5(user_password).hexdigest()
        cursor.execute(
                '''INSERT INTO usr
                   (usr_first_name, usr_last_name, usr_email, usr_admin, usr_password, usr_last_seen, usr_created, is_guest)
                   VALUES
                   (%(user_first_name)s, %(user_last_name)s, %(user_email)s, '0', %(user_password)s, NOW(), NOW(), 'f')
                ''',
                {
                    'user_first_name': user_first_name,
                    'user_last_name': user_last_name,
                    'user_email': user_email,
                    'user_password': password_md5
                }
        )
        cursor.connection.commit()
        return get_user_byemail(user_email)


def register_user_from_guest(user_first_name, user_last_name, user_email, user_password, guest_id):
    """
    Updates a guest user to a registered user
    :param user_first_name: the user's first name, if not provided use "Guest" as default
    :param user_last_name:	the user's last name, if not provided use "User" as default
    :param user_email:		the user's email address, if not provided use "" as default
    :param user_password:	the user's password, if not provided use "" as default
    :param guest_id:        the id of the guest account to register
    """
    with PooledCursor() as cursor:
        password_md5 = md5(user_password).hexdigest()
        cursor.execute(
            '''UPDATE usr SET
               usr_first_name = %s, usr_last_name = %s, usr_email = %s, usr_admin = '0', usr_password = %s, usr_last_seen = NOW(), usr_created = NOW() , is_guest = 'f'
               WHERE usr.usr_id = %s''', (user_first_name, user_last_name, user_email, password_md5, guest_id)
        )
        cursor.connection.commit()
        return get_user_byemail(user_email)


def reset_password(user_email):
    """
    Update a user password
    :param user_email:		the user's email address, if not provided use "" as default
    """

    char_set = string.ascii_lowercase + string.ascii_uppercase + string.digits
    new_password = ''.join(random.sample(char_set, 8))
    with PooledCursor() as cursor:
        password_md5 = md5(new_password).hexdigest()
        cursor.execute(
                '''UPDATE usr
               SET usr_password = %s
               WHERE usr_email = %s''', (password_md5, user_email)
        )
        cursor.connection.commit()
    return new_password


def change_password(user_id, new_password):
    """
    Update a user password
    :param user_id:		the user's id as default
    :param new_password:	 the user's password, if not provided use "" as default
    """
    with PooledCursor() as cursor:
        password_md5 = md5(new_password).hexdigest()
        cursor.execute(
                '''UPDATE usr
               SET usr_password = %s
               WHERE usr_id = %s''', (password_md5, user_id)
        )
        cursor.connection.commit()
    return


def update_notification_pref(user_id, state):
    with PooledCursor() as cursor:
        cursor.execute(
                '''select usr_prefs FROM usr WHERE usr_id=%s''', (user_id,)
        )
        results = cursor.fetchall()
        if len(results) == 1:
            preferences = json.loads(results[0][0])
            preferences['email_notification'] = state
            cursor.execute(
                '''UPDATE usr SET usr_prefs=%s WHERE usr_id=%s''', (json.dumps(preferences), user_id)
            )
            cursor.connection.commit()
            return {'success': True}

    return {'error': 'unable to update user notification email preference'}

def get_genes_for_mset(tg_id, int_id):
    """
    Gets the Geneset if either the geneset is publicly visible or the user
    has permission to view it.
    :param geneset_id:	the geneset ID
    :param user_id:		the user ID that needs permission
    :return:			the Geneset corresponding to the given ID if the
                        user has read permission, None otherwise
    """

    with PooledCursor() as cursor:
        cursor.execute(
                '''
            SELECT usr_id, pj_name, pj_notes, pj_created, pj_id, %(int_id)s AS int_id
            FROM project
            WHERE project.pj_id=%(tg_id)s;
            ''',
                {
                    'tg_id': tg_id,
                    'int_id': int_id
                }
        )
        genesets = [MSETGeneset(row_dict) for row_dict in dictify_cursor(cursor)]

        return genesets[0] if len(genesets) == 1 else None

def update_annotation_pref(user_id, annotator):
    if annotator not in ann.ANNOTATORS:
        return {'error': "invalid annotator: '{}' must be one of {}".format(annotator, ", ".join(ann.ANNOTATORS))}
    with PooledCursor() as cursor:
        cursor.execute(
                '''select usr_prefs FROM usr WHERE usr_id=%s''', (user_id,)
        )
        results = cursor.fetchall()
        if len(results) == 1:
            preferences = json.loads(results[0][0])
            preferences['annotator'] = annotator
            cursor.execute(
                '''UPDATE usr SET usr_prefs=%s WHERE usr_id=%s''', (json.dumps(preferences), user_id)
            )
            cursor.connection.commit()
            return {'success': True}

    return {'error': 'unable to update user annotation'}


def get_geneset_tier(gsid):
    """
    Returns the tier associated with the given gene set ID.

    :param gsid:    the gene set ID
    :return:        the tier (cur_id)
    """

    with PooledCursor() as cursor:
        cursor.execute(
            '''
            SELECT  cur_id
            FROM    geneset
            WHERE   gs_id = %s;
            ''',
                (gsid,)
        )

        result = cursor.fetchone()

        if not result:
            return None

        return result[0]


def get_geneset(geneset_id, user_id=None, temp=None):
    """
    Gets the Geneset if either the geneset is publicly visible or the user
    has permission to view it.
    :param geneset_id:	the geneset ID
    :param user_id:		the user ID that needs permission
    :return:			the Geneset corresponding to the given ID if the
                        user has read permission, None otherwise
    """

    # TODO not sure if we really need to convert to -1 here. The geneset_is_readable2 function may be able to handle None
    if user_id is None:
        user_id = -1



    with PooledCursor() as cursor:
        cursor.execute(
                '''
            SELECT geneset.*, curation_assignments.curation_group, publication.*, gs_to_pub_assignment.pub_assign_id
            FROM geneset
            LEFT OUTER JOIN publication ON geneset.pub_id = publication.pub_id
            LEFT OUTER JOIN curation_assignments ON geneset.gs_id = curation_assignments.gs_id
            LEFT OUTER JOIN gs_to_pub_assignment ON geneset.gs_id = gs_to_pub_assignment.gs_id
            WHERE geneset.gs_id=%(geneset_id)s AND geneset_is_readable2(%(user_id)s, %(geneset_id)s);
            ''',
                {
                    'geneset_id': geneset_id,
                    'user_id': user_id,
                }
        )
        if temp is None:
            genesets = [Geneset(row_dict) for row_dict in dictify_cursor(cursor)]
        elif temp == 'temp':
            # genesets = [Geneset(row_dict) for row_dict in dictify_cursor(cursor)]
            genesets = [TempGeneset(row_dict) for row_dict in dictify_cursor(cursor)]
        return genesets[0] if len(genesets) == 1 else None


def get_similar_genesets(geneset_id, user_id, grp_by):
    """
    Gets similar genesets if either the geneset is publicly visible or the user
    has permission to view it.
    :param geneset_id:	the geneset ID
    :param user_id:		the user ID that needs permission
    :param grp_by:      this appends a group by parameter for tiers, species, etc
    :return:			the Geneset corresponding to the given ID if the
                        user has read permission, with jac_value, None otherwise
    """

    # TODO not sure if we really need to convert to -1 here. The geneset_is_readable2 function may be able to handle None
    if user_id is 0:
        user_id = -1

    # updating the sql to include a partition_by clause. 0 = sorted by jaccard (no grouping; 1 = group by tier;
    # 2 = group by species; 3 = group by attribution
    if grp_by == 0:
        order_by = ''
    elif grp_by == 1:
        order_by = ' cur_id ASC,'
    elif grp_by == 2:
        order_by = ' sp_id ASC,'
    else:
        order_by = ' gs_attribution ASC, '

    with PooledCursor() as cursor:
        cursor.execute(
            '''SELECT a.* FROM (
                   (SELECT geneset.*,jac_value,gic_value 
                       FROM geneset, geneset_jaccard gj
                       WHERE gs_id=gs_id_right AND gs_id_left=%(geneset_id)s 
                         AND geneset_is_readable(%(user_id)s, gs_id) 
                         AND gs_status NOT LIKE 'de%%' 
                           ORDER BY gj.jac_value DESC LIMIT 500
                     ) 
                     UNION
                   (SELECT geneset.*,jac_value,gic_value 
                       FROM geneset, geneset_jaccard gj 
                       WHERE gs_id=gs_id_left AND gs_id_right=%(geneset_id)s 
                         AND geneset_is_readable(%(user_id)s, gs_id) 
                         AND gs_status NOT LIKE 'de%%' 
                           ORDER BY gj.jac_value DESC LIMIT 500
                     ) 
                 ) AS a ORDER BY ''' + order_by + ''' a.jac_value DESC LIMIT 1000''',
            {
                'geneset_id': geneset_id,
                'user_id': user_id,
            }
        )

        simgc = [SimGeneset(row_dict) for row_dict in dictify_cursor(cursor)]

        return simgc


def get_similar_genesets_by_publication(geneset_id, user_id):
    """
    Get all other genesets with the same publication id as the geneset id passed to this function
    :param geneset_id:	the geneset ID
    :param user_id:		the user ID that needs permission
    :return:			the Geneset corresponding to the given publication ID if the
                        user has read permission, with jac_value, None otherwise
    """
    gs_ids = []
    gs_ids_clean = []
    # TODO not sure if we really need to convert to -1 here. The geneset_is_readable2 function may be able to handle None
    if user_id is 0:
        user_id = -1
    # print geneset_id
    with PooledCursor() as cursor:
        cursor.execute('''SELECT gs_id FROM geneset WHERE pub_id IN (SELECT pub_id FROM geneset WHERE gs_id=%s)''',
                       (geneset_id,))
        res = cursor.fetchall()
        for r in res:
            gs_ids.append(r[0])

        for gs_id in gs_ids:
            cursor.execute('''SELECT geneset_is_readable2(%s, %s)''', (user_id, gs_id))
            a = cursor.fetchone()[0]
            if a:
                gs_ids_clean.append(gs_id)

        # s = ','.join(gs_ids_clean)
        cursor.execute(cursor.mogrify(
                '''SELECT geneset.* FROM geneset WHERE geneset.gs_id IN (%s)''' % ",".join(str(x) for x in gs_ids)))

        genesets = [Geneset(row_dict) for row_dict in dictify_cursor(cursor)]
        return genesets


def get_genesets_for_publication(pub_id, user_id):
    """

    :param pub_id: publication id
    :param user_id: user id
    :return: list of Genesets associated with the specified publication that are
             visible to the specified user
    """

    gs_ids = []
    gs_ids_readable = []
    genesets = []

    # TODO not sure if we really need to convert to -1 here. The geneset_is_readable2 function may be able to handle None
    if user_id is 0:
        user_id = -1

    with PooledCursor() as cursor:

        # first get all genesets with this pub_id
        cursor.execute('''SELECT gs_id FROM geneset WHERE pub_id = %s''', (pub_id,))
        res = cursor.fetchall()
        for r in res:
            gs_ids.append(r[0])

        # now find out which of those are readable to the user
        for gs_id in gs_ids:
            cursor.execute('''SELECT geneset_is_readable2(%s, %s)''', (user_id, gs_id))
            a = cursor.fetchone()[0]
            if a:
                gs_ids_readable.append(gs_id)

        if gs_ids_readable:
            SQL = "SELECT geneset.* FROM geneset WHERE geneset.gs_id IN ({})".format(','.join(['%s'] * len(gs_ids_readable)))
            cursor.execute(SQL, gs_ids_readable)

            genesets = [Geneset(row_dict) for row_dict in dictify_cursor(cursor)]

        return genesets


def compare_geneset_jac(gs_id1, gs_id2):
    """
    Compares two genesets together. returns 1 if they are > .95 similar
    :param gs_id1:
    :param gs_id2:
    :return:
    """
    if gs_id2 < gs_id1:
        gs1 = gs_id2
        gs2 = gs_id1
    else:
        gs1 = gs_id1
        gs2 = gs_id2
    with PooledCursor() as cursor:
        cursor.execute(
                '''SELECT jac_value FROM geneset_jaccard
              WHERE gs_id_left=%(gs_id1)s AND gs_id_right=%(gs_id2)s AND jac_value > 0.95;
              ''',
                {
                    'gs_id1': gs1,
                    'gs_id2': gs2,
                }
        )
    if cursor.fetchone():
        return 1
    else:
        return 0


def get_geneset_no_user(geneset_id):
    """
    Gets the Geneset regardless of whether the user has permission to view it
    :param geneset_id:	the geneset ID
    :return:			the Geneset corresponding to the given ID if the
                        user has read permission, None otherwise
    """

    with PooledCursor() as cursor:
        cursor.execute(
                '''
            SELECT *
            FROM geneset LEFT OUTER JOIN publication ON geneset.pub_id = publication.pub_id
            WHERE gs_id=%(geneset_id)s;
            ''',
                {
                    'geneset_id': geneset_id,
                }
        )
        genesets = [Geneset(row_dict) for row_dict in dictify_cursor(cursor)]
        return genesets[0] if len(genesets) == 1 else None


def get_groups_by_project(proj_id):
    """
    the proj_id returns a string of groups that need to be split
    :param proj_id: the project id
    :return a list of lists [[id, group name, email address of owner, private],...]
    """
    with PooledCursor() as cursor:
        cursor.execute('''SELECT pj_groups FROM project WHERE pj_id=%s''', (proj_id,))
        groups = (cursor.fetchone()[0]).split(',')
        cursor.execute('''SELECT g.grp_id, g.grp_name, u.usr_email, g.grp_private FROM grp g, usr u, usr2grp u2g
                          WHERE g.grp_id=u2g.grp_id AND u2g.usr_id=u.usr_id AND g.grp_id IN (%s)''' % ",".join(str(x) for x in groups))
        results = list(dictify_cursor(cursor))
    return results if len(results) > 0 else None


def get_user_groups(usr_id):
    """
    Gets a list of groups that the user belongs to
    :param usr_id:	the user ID
    :return:		The list of group ids that the user belongs to
    """

    with PooledCursor() as cursor:
        cursor.execute(
                '''
            SELECT grp_id
            FROM usr2grp
            WHERE usr_id=%(usr_id)s;
            ''',
                {
                    'usr_id': usr_id,
                }
        )
        grp_ids = [row_dict['grp_id'] for row_dict in dictify_cursor(cursor)]
        return grp_ids


def get_group_users(grp_id):
    """
    Gets a list of users in a group
    :param grp_id:	the group ID
    :return:		The list of user ids that the belong to a group
    """

    with PooledCursor() as cursor:
        cursor.execute(
                '''
            SELECT usr_id
            FROM usr2grp
            WHERE grp_id=%(grp_id)s;
            ''',
                {
                    'grp_id': grp_id,
                }
        )
        usr_ids = [row_dict['usr_id'] for row_dict in dictify_cursor(cursor)]
        return usr_ids

def get_all_users():
    """
    Gets a list of all users
    :return:		The list of user ids for every user in the database
    """

    with PooledCursor() as cursor:
        cursor.execute(
                '''
            SELECT usr_id
            FROM usr;
            '''
        )
        usr_ids = [row_dict['usr_id'] for row_dict in dictify_cursor(cursor)]
        return usr_ids


def get_geneset_brief(geneset_id, user_id=None):
    """
    Gets the Geneset if either the geneset is publicly visible or the user
    has permission to view it.
    :param geneset_id:	the geneset ID
    :param user_id:		the user ID that needs permission
    :return:			the Geneset corresponding to the given ID if the
                        user has read permission, None otherwise
    """

    # TODO not sure if we really need to convert to -1 here. The geneset_is_readable2 function may be able to handle None
    if user_id is None:
        user_id = -1

    with PooledCursor() as cursor:
        cursor.execute(
                '''
            SELECT geneset.cur_id, geneset.sp_id, geneset.gs_abbreviation, geneset.gs_count, geneset.gs_status, geneset.gs_id, geneset.gs_name
            FROM geneset
            WHERE gs_id=%(geneset_id)s AND geneset_is_readable2(%(user_id)s, %(geneset_id)s);
            ''',
                {
                    'geneset_id': geneset_id,
                    'user_id': user_id,
                }
        )
        genesets = [Geneset(row_dict) for row_dict in dictify_cursor(cursor)]
        return genesets[0] if len(genesets) == 1 else None


def get_genesets_by_user_id(user_id):
    """
    Gets all Genesets owned by the specified user
    :param user_id:		the owning user ID
    :return:			the Genesetx corresponding to the given ID
    """

    # TODO not sure if we really need to convert to -1 here. The
    # geneset_is_readable2 function may be able to handle None
    # if user_id is None:
    #	 user_id = -1

    with PooledCursor() as cursor:
        cursor.execute(
                '''
            SELECT *
            FROM production.geneset
            WHERE usr_id=%(user_id)s;
            ''',
                {
                    'user_id': user_id,
                }
        )
        genesets = [Geneset(row_dict) for row_dict in dictify_cursor(cursor)]
        return genesets if len(genesets) > 0 else None


def get_all_parents_for_ontology(ont_id):
    """
    Gets all parent ontology for a given ontology
    :param ont_id:	   ontology ID
    :return:			a list of ontology objects that are the parents
    """
    with PooledCursor() as cursor:
        cursor.execute(
                '''
            SELECT ont1.ont_id, ont_ref_id, ont_name, ont_description, ont_children, ont_parents, ontdb_id
            FROM ontology ont1 INNER JOIN ontology_relation ont2
            ON ont2.right_ont_id = ont1.ont_id
            WHERE left_ont_id=%s
            GROUP BY ont1.ont_id, ont_ref_id, ont_name, ont_description, ont_children, ont_parents, ontdb_id;
            ''' % (ont_id,)
        )
    # Note:	removed AND or_type='is_a' from query
    parents = [Ontology(row_dict) for row_dict in dictify_cursor(cursor)]
    return parents


def get_all_parents_to_root_for_ontology(ont_id):
    """
    Gets a path from the starting ontology to it's root ontology
    and returns it as a list starting from the root
    :param ont_id:	   selected ontology ID
    :return:			a list of ontology ids that represents the path from root to the selected id
    """
    result = [1]
    ont_cur_id = ont_id
    parent_path_list = []
    parent_path_list.append([ont_cur_id])
    list_of_ordered_parent_cur_path_list = []
    while result[0] != 0:
        if parent_path_list == []:
            # print list_of_ordered_parent_cur_path_list
            return list_of_ordered_parent_cur_path_list
        parent_cur_path_list = parent_path_list.pop()
        ont_cur_id = parent_cur_path_list[-1]

        with PooledCursor() as cursor:
            cursor.execute(
                    '''
                SELECT count(*)
                FROM ontology
                WHERE ont_id = %s AND ont_parents = 0
                ''' % (ont_cur_id)
            )
        # if there's a parent, return 0, else return 1
        result = cursor.fetchall()  # Fun fact: cursor.fetchall() returns a list of tuples
        if result[0][0] == 1:  # result[0] = a tuple of one element, result[0][0] = an element from a tuple from a list
            # if there are no parent, then a root is reached, so time to pop and
            # reorder this specific path to root and send to the master parent list
            ordered_parent_cur_path_list = []
            while len(parent_cur_path_list) > 1:
                back = parent_cur_path_list[-1]
                parent_cur_path_list = parent_cur_path_list[0]
                ordered_parent_cur_path_list.append(back)
            if len(parent_cur_path_list) == 1:
                ordered_parent_cur_path_list.append(parent_cur_path_list[-1])
            list_of_ordered_parent_cur_path_list.append(ordered_parent_cur_path_list)
        else:
            # if there is multiple parent paths from my given ontology position, append
            # those multiple paths of parents onto the path_list
            for ont in get_all_parents_for_ontology(ont_cur_id):
                parent_path_list.append([parent_cur_path_list, ont.ontology_id])
                # print "==================="
                # print parent_path_list
                # print "==================="


def get_all_children_for_ontology(ont_id):
    """
    Gets all child ontology for a given ontology
    :param ont_id:	   ontology ID
    :return:			a list of ontology objects that are the child
    """
    with PooledCursor() as cursor:
        cursor.execute(
                '''
            SELECT ont1.ont_id, ont_ref_id, ont_name, ont_description, ont_children, ont_parents, ontdb_id
            FROM ontology ont1 INNER JOIN ontology_relation ont2
            ON ont2.left_ont_id = ont1.ont_id
            WHERE right_ont_id=%s
            GROUP BY ont1.ont_id, ont_ref_id, ont_name, ont_description, ont_children, ont_parents, ontdb_id;
            ''' % (ont_id,)
        )
    # Note:	removed AND or_type='is_a' from query
    children = [Ontology(row_dict) for row_dict in dictify_cursor(cursor)]
    return children


def get_all_ontologydb():
    """
    Gets all ontology databases
    :param
    :return:			a list of ontologydb objects
    """
    with PooledCursor() as cursor:
        cursor.execute(
                '''SELECT * FROM ontologydb;'''
        )
        return [Ontologydb(row_dict) for row_dict in dictify_cursor(cursor)]


def get_all_gso_ref_type():
    """
    Gets all gso_ref_types is possible
    :param
    :return:			a list of gso_ref_type string that is possible
    """
    with PooledCursor() as cursor:
        gso_ref_types = []
        cursor.execute(
                '''SELECT gso_ref_type FROM geneset_ontology GROUP BY gso_ref_type'''
        )
        result = cursor.fetchall()
        for type in result:
            gso_ref_types.append(type[0])
    return gso_ref_types


def get_all_root_ontology_for_database(ontdb_id):
    """
    Gets all root ontology for a given ontology database
    :param ont_id:	   ontologydb ID
    :return:			a list of ontology objects that are the root of a given ontology database
    """
    # if a default of 'All Reference Types' is passed, set ont_db to GO
    if ontdb_id.startswith('All'):
        ontdb_id = 1

    with PooledCursor() as cursor:
        cursor.execute(
                '''
               SELECT *
               FROM ontology
               WHERE ont_parents = 0 AND ontdb_id = %s;
            ''' % (ontdb_id,)
        )
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
        #self.hom = list(set(gsv_dict['hom']))  # had to remove duplicates from list
        self.hom_id = gsv_dict['hom_id']
        self.hom = get_species_homologs(self.hom_id)
        self.gene_rank = ((float(gsv_dict['gene_rank']) / 0.15) * 100)
        #self.ode_ref = gsv_dict['ode_ref']
        self.ode_ref = gsv_dict['ode_ref_id']
        self.gdb_id = gsv_dict['gdb_id']


class TempGenesetValue:
    def __init__(self, gsv_dict):
        self.gs_id = gsv_dict['gs_id']
        self.ode_gene_id = gsv_dict['ode_gene_id']
        self.value = gsv_dict['gsv_value']
        self.hits = gsv_dict['gsv_hits']
        self.source_list = gsv_dict['gsv_source_list']
        self.value_list = gsv_dict['gsv_value_list']
        self.is_in_threshold = gsv_dict['gsv_in_threshold']
        self.date = gsv_dict['gsv_date']


def get_temp_geneset_values(geneset_id):
    """
    This geneset value query has been augmented to return a list of sp_ids that can be used
    on the geneset information page.
    Also, augmented to add a session call for sorting
    :param geneset_id:
    :returns to geneset class.
    """
    with PooledCursor() as cursor:
        cursor.execute('''SELECT gs_id, ode_gene_id, avg(src_value) as gsv_value,
										   count(ode_gene_id) as gsv_hits, array_accum(src_id) as gsv_source_list,
										   array_accum(src_value) as gsv_value_list,'t' as gsv_in_threshold, now() as gsv_date
										   FROM production.temp_geneset_value
										   WHERE gs_id=%s GROUP BY gs_id, ode_gene_id ORDER BY ode_gene_id;''' % (
            geneset_id,))
        return [TempGenesetValue(gsv_dict) for gsv_dict in dictify_cursor(cursor)]


def get_genes_by_gs_id(geneset_id):
    '''
    Returns all of the ode_gene_ids for a given gs_id. This is seperate form the geneset_value class, created specifically
    for making edgelist files outside of the scope.
    :param geneset_id:
    :return: list of genes
    '''
    genes = []
    with PooledCursor() as cursor:
        cursor.execute('''SELECT ode_gene_id FROM geneset_value WHERE gs_id=%s''', (geneset_id,))
        res = cursor.fetchall()
        for r in res:
            genes.append(r[0])
    return genes


def transpose_genes_by_species(attr):
    """
    Return a list of genes based on a new ID and gbd_id
    :param attr:
    :return:
    """
    genes = json.loads(attr['genes'])
    g = []
    for i in genes:
        g.append(str(i))
    newSpecies = json.loads(attr['newSpecies'])
    with PooledCursor() as cursor:
        cursor.execute('''SELECT ode_ref_id FROM gene WHERE gene.ode_gene_id IN
                            (SELECT distinct h2.ode_gene_id FROM homology h1
                                NATURAL JOIN homology h2
                                NATURAL JOIN gene
                                WHERE h2.hom_source_name='Homologene'
                                      AND h1.hom_source_id=h2.hom_source_id
                                      AND ode_ref_id IN %(genelist)s)
                            AND sp_id=%(newSpecies)s AND ode_pref='t' AND gdb_id=7;''', {'genelist': tuple(g), 'newSpecies': newSpecies})
        res = cursor.fetchall()
        transposedGenes = []
        if res is not None:
            for r in res:
                transposedGenes.append(r[0])
        return transposedGenes


def get_omicssoft(gs_id):
    '''
    Return data from the omicssoft table if any exists
    :param gs_id: 
    :return: dictionary
    '''
    omicssoft = {'project': 'N\A', 'tag': 'GeneWeaver', 'type': 'N\A'}
    with PooledCursor() as cursor:
        cursor.execute('''SELECT os_project, os_tag, os_source FROM production.omicsoft WHERE gs_id=%s''', (gs_id,))
        res = cursor.fetchall()
        if res is not None:
            for r in res:
                omicssoft['project'] = r[0] if r[0] is not None else 'N\A'
                omicssoft['tag'] = r[1] if r[0] is not None else 'GeneWeaver'
                omicssoft['type'] = r[2] if r[0] is not None else 'N\A'
    return omicssoft


def get_all_geneset_values(gs_id):
    '''
    Generic function to get all geneset values geneset_value.gs_values
    :param geneset_id:
    :return:
    '''
    user_id = flask.session['user_id']
    geneset = get_geneset(gs_id, user_id)
    with PooledCursor() as cursor:
        if geneset.gene_id_type < 0:
            cursor.execute('''SELECT gv.gsv_value as gsv, g.ode_ref_id as ref FROM geneset_value gv, gene g, geneset gs WHERE
							  g.ode_pref='t' AND gv.gs_id=%s AND gs.gs_id=gv.gs_id AND gs.sp_id=g.sp_id AND
							  gv.ode_gene_id=g.ode_gene_id ORDER BY gv.gsv_value ASC''', (gs_id,))
        else:
            cursor.execute('''SELECT gv.gsv_value, g.ode_ref_id FROM geneset_value gv, gene g, geneset gs WHERE
							  gv.gs_id=%s AND gs.gs_id=gv.gs_id AND gs.sp_id=g.sp_id AND gv.ode_gene_id=g.ode_gene_id AND
							  g.ode_pref='t' ORDER BY gv.gsv_value ASC''', (gs_id,))
        return list(dictify_cursor(cursor)) if cursor.rowcount != 0 else None

def get_species_homologs(hom_id):
    """
    Uses a given homology ID to return a list of homologous species.

    :type hom_id: int (const)
    :param hom_id: Homology ID

    :return:
    """

    if not hom_id:
        return []

    with PooledCursor() as cursor:
        cursor.execute('''
            SELECT sp_id
            FROM homology
            WHERE hom_id = %s''', (hom_id,))

    return map(lambda l: l[0], set(cursor))

def get_geneset_values_for_mset(pj_tg_id, pj_int_id):
    """
    This geneset value query has been augmented to return a list of sp_ids that can be used
    on the geneset information page.
    Also, augmented to add a session call for sorting
    :param geneset_id:
    :returns to geneset class.
    """
    s = ' ORDER BY gsv.gs_id ASC'

    if 'sort' in session:
        d = session['dir']
        if session['sort'] == 'value':
            s = ' ORDER BY gsv.gsv_value ' + d
        elif session['sort'] == 'priority':
            s = ' ORDER BY gi.gene_rank ' + d
        elif session['sort'] == 'symbol':
            s = ' ORDER BY gsv.gsv_source_list ' + d
        elif session['sort'] == 'alt':
            s = ' ORDER BY g.ode_ref_id ' + d

    ode_ref = '1'
    if 'extsrc' in session:
        ode_ref = session['extsrc']


    with PooledCursor() as cursor:
        cursor.execute('''
            SELECT gsv.gs_id, gsv.ode_gene_id, gsv.gsv_value, gsv.gsv_hits,
                   gsv.gsv_source_list, gsv.gsv_value_list, gsv.gsv_in_threshold,
                   gsv.gsv_date, h.hom_id, gi.gene_rank, g.ode_ref_id, g.gdb_id
            FROM geneset_value AS gsv
            INNER JOIN homology AS h
            ON gsv.ode_gene_id = h.ode_gene_id
            INNER JOIN gene_info AS gi
            ON gsv.ode_gene_id = gi.ode_gene_id
            INNER JOIN gene AS g
            ON gsv.ode_gene_id = g.ode_gene_id
            WHERE gsv.gs_id IN
                  (SELECT gs_id
	                FROM production.project2geneset
	                WHERE pj_id = %s)
	              AND
		          gsv.ode_gene_id IN
		          ((SELECT DISTINCT ode_gene_id
					FROM geneset_value
					WHERE gs_id IN (SELECT gs_id
					FROM production.geneset
					WHERE gs_id IN
						(SELECT gs_id
						FROM production.project2geneset
						WHERE pj_id = %s))
					INTERSECT
					SELECT DISTINCT ode_gene_id
					FROM geneset_value
					WHERE gs_id IN (SELECT gs_id
					FROM production.geneset
					WHERE gs_id IN
						(SELECT gs_id
						FROM production.project2geneset
						WHERE pj_id = %s))))
		          AND
                  -- This checks to see if the alternate symbol the user wants to view actually exists
                  -- for the given gene. If it doesn't, a default gene symbol is returned. If null was
                  -- returned then there would be missing genes on the view geneset page.
                  g.gdb_id = (SELECT COALESCE (
                    (SELECT gdb_id FROM gene AS g2 WHERE g2.ode_gene_id = gsv.ode_gene_id AND g2.gdb_id = %s LIMIT 1),
                    (SELECT gdb_id FROM gene AS g2 WHERE g2.ode_gene_id = gsv.ode_gene_id AND g2.gdb_id = 7 LIMIT 1)
                  ))
                  AND
                  -- When viewing symbols, always pick the preferred gene symbol
                  CASE WHEN g.gdb_id = 7
                  THEN g.ode_pref = 't'
                  ELSE true
                  END''' + s, (pj_tg_id, pj_int_id, pj_tg_id, ode_ref))

        return [GenesetValue(gsv_dict) for gsv_dict in dictify_cursor(cursor)]

def get_geneset_values_for_mset_small(pj_tg_id, pj_int_id):
    """
    This geneset value query has been augmented to return a list of sp_ids that can be used
    on the geneset information page.
    Also, augmented to add a session call for sorting
    :param geneset_id:
    :returns to geneset class.
    """

    with PooledCursor() as cursor:
        cursor.execute('''
            SELECT unnest(gsv_source_list)
					FROM geneset_value
					WHERE gs_id IN (SELECT gs_id
					FROM production.geneset
					WHERE gs_id IN
						(SELECT gs_id
						FROM production.project2geneset
						WHERE pj_id = %s))
			INTERSECT
			SELECT unnest(gsv_source_list)
				    FROM geneset_value
					WHERE gs_id IN (SELECT gs_id
					FROM production.geneset
					WHERE gs_id IN
						(SELECT gs_id
						FROM production.project2geneset
						WHERE pj_id = %s))''', (pj_tg_id, pj_int_id))

        return cursor.fetchall()

def get_genecount_in_geneset(geneset_id):
    """
    get a count of total number of genes associated with a geneset.
    :param geneset_id:
    :returns count of total genes in geneset
    """

    stmt = '''SELECT count(*) FROM geneset_value WHERE gs_id = {}'''.format(geneset_id)

    with PooledCursor() as cursor:
        cursor.execute(stmt)
        return cursor.fetchone()[0]


def get_gene_homolog_ids(ode_gene_ids, gdb_id):
    """
    Maps genes in a given gene set to their homolog IDs, then uses those
    homolog IDs to retrieve MOD gene identifiers for another species.
    Used when for e.g. a user is viewing a human gene set but wants to see
    equivalent genes using MGI or ZFIN identifiers.

    arguments
        ode_gene_ids:   list of ode_gene_ids in the gene set
        gdb_id:         ID of the different gene type the user wants to see

    returns
        a mapping of ode_gene_ids to ode_ref_ids. 
        The ode_gene_ids in this case are the originals provided in the first 
        argument of this function. The ode_ref_ids are the reference IDs to
        some other MOD, mapped across species.
    """

    ode_gene_ids = list(set(ode_gene_ids))
    ode_gene_ids = tuple(ode_gene_ids)

    with PooledCursor() as cursor:
        cursor.execute(
            '''
            SELECT      h.ode_gene_id, g.ode_ref_id 
            FROM        homology AS h 
            INNER JOIN  homology AS h2 
            ON          h.hom_id = h2.hom_id 
            INNER JOIN  gene AS g
            ON          g.ode_gene_id = h2.ode_gene_id 
            WHERE       h.ode_gene_id in %s AND 
                        g.gdb_id = %s;
            ''', (ode_gene_ids, gdb_id,)
        )

        ode2ref = {}

        for row in cursor.fetchall():
            ode2ref[row[0]] = row[1]

        return ode2ref

def get_geneset_values(
    gs_id, gdb_id='7', limit=50, offset=0, search='', sort='', direct='asc'
):
    """
    Retrieves the list of gene set values for the given gene set.
    Updated version of the get_geneset_values function designed to remove
    dependence on session variables and fix several bugs: 1) genes without
    homologs don't show up in the gene list, 2) paralogs for all genes show up
    in the gene list, 3) genes with more than one of the same identifier 
    types prevent other identifiers from showing up.
    The original function was a nightmare to debug so this is split into
    a separate component for retrieving IDs across species.

    arguments
        gs_id:  gene set ID for the values being retrieved
        gdb_id: gene type (genedb) ID to use when retrieving gene set genes
        limit:  number of rows to return
        offset: used in conjuction w/ limit to paginate the returned results
        search: gene symbol string to filter results with
        sort:   string specifying how the results should be sorted, this can be
                one of several values:
                    value:  sort by the gene score
                    alt:    sort by the currently displayed gene identifier
                    otherwise the default sort is the originally uploaded gene
                    identifier
        direct: specifies the direction of the sort, either 'asc' or 'desc'

    returns
        a list of GenesetValue objects
    """

    sp_id = get_sp_id_by_gsid(gs_id)[0]['sp_id']
    ## stupid return value for this function needs to be changed
    gdb_spid = get_gdb_sp(gdb_id)[0]['sp_id']

    ## The user wants to convert identifiers to another species' MOD IDs. We
    ## temporarily set gdb_id to symbols (7) otherwise the query below won't 
    ## return anything since the original gdb_id is for a different species
    if gdb_spid != 0 and gdb_spid != sp_id:
        original_gdb_id = gdb_id
        gdb_id = 7

    ## Not supposed to do this 'cause potential SQL injection vector but 
    ## ORDER BY CASE doesn't work with mixed types (varchar and int in our
    ## case)
    if sort == 'value':
        sort = 'gsv.gsv_value'
    elif sort == 'alt':
        sort = 'gsv.ode_ref_id'
    elif sort == 'priority':
        sort = 'gi.gene_rank'
    else:
        sort = 'gsv.gsv_source_list'

    with PooledCursor() as cursor:
        cursor.execute(
            '''
            SELECT gsv.gs_id, gsv.ode_gene_id, gsv.gsv_value, gsv.gsv_hits,
                   gsv.gsv_source_list, gsv.gsv_value_list, 
                   gsv.gsv_in_threshold, gsv.gsv_date, h.hom_id, gi.gene_rank,
                   gsv.ode_ref_id, gsv.gdb_id
                   
            --
            -- Use a subquery here so we can prevent duplicate gene identifiers
            -- of the same type from being returned (the DISTINCT ON section) 
            -- otherwise when we try to change identifier types from the view 
            -- GS page, duplicate entries screw things up
            --
            FROM (
                SELECT DISTINCT ON (g.ode_gene_id, g.gdb_id) 
                        gsv.*, g.ode_ref_id, g.gdb_id, g.ode_pref
                FROM    geneset_value as gsv, gene as g 
                WHERE   gsv.gs_id = %s AND 
                        g.ode_gene_id = gsv.ode_gene_id AND
                        g.gdb_id = (SELECT COALESCE (
                            (SELECT gdb_id 
                             FROM   gene AS g2 
                             WHERE g2.ode_gene_id = gsv.ode_gene_id AND 
                                   g2.gdb_id = %s 
                             LIMIT 1),
                            (SELECT gdb_id 
                             FROM   gene AS g2 
                             WHERE g2.ode_gene_id = gsv.ode_gene_id AND 
                                   g2.gdb_id = 7
                             LIMIT 1)
                        )) AND

                        --
                        -- When the user provides a gene to search for in the
                        -- gene list. If no search query is provided, skip it.
                        --
                        CASE %s
                            WHEN '' THEN true
                            ELSE g.ode_ref_id ~* %s 
                        END AND
 
                        --
                        -- When viewing symbols, always pick the preferred gene symbol
                        --
                        CASE 
                            WHEN g.gdb_id = 7 THEN g.ode_pref = 't'
                            ELSE true
                        END
            ) gsv

            --
            -- gene_info necessary for the priority scores
            --
            INNER JOIN  gene_info AS gi
            ON          gsv.ode_gene_id = gi.ode_gene_id

            --
            -- Have to use a left outer join because some genes may not have homologs
            --
            LEFT OUTER JOIN homology AS h
            ON          gsv.ode_gene_id = h.ode_gene_id 
             
            WHERE h.hom_source_name = 'Homologene' OR
                  -- In case the gene doesn't have any homologs
                  h.hom_source_name IS NULL
            
            ORDER BY 
            ''' + sort + ' ' + direct +
            '''
            LIMIT %s OFFSET %s
            ''',
            (gs_id, gdb_id, search, search, limit, offset)
            #ORDER BY 
            #    CASE WHEN %s = 'asc' THEN
            #        CASE %s
            #            WHEN 'value' THEN gsv.gsv_value :: character varying
            #            WHEN 'alt' THEN gsv.ode_ref_id 
            #            ELSE gsv.gsv_source_list :: character varying
            #        END
            #    ELSE ''
            #    END asc,
            #    CASE WHEN %s = 'desc' THEN
            #        CASE %s
            #            WHEN 'value' THEN gsv.gsv_value :: character varying
            #            WHEN 'alt' THEN gsv.ode_ref_id 
            #            ELSE gsv.gsv_source_list :: character varying
            #        END
            #    ELSE ''
            #    END desc
            #LIMIT %s OFFSET %s
            #''', 
            #(gs_id, gdb_id, search, search, direct, sort, direct, sort, limit, offset)
        )

        gsvs = [GenesetValue(gsv_dict) for gsv_dict in dictify_cursor(cursor)]

        ## We are converting IDs from this set to identifiers belonging to a
        ## separate species. e.g. human symbols to MGI IDs

        if gdb_spid != 0 and gdb_spid != sp_id:
            ode2ref = get_gene_homolog_ids(
                map(lambda v: v.ode_gene_id, gsvs), original_gdb_id
            )

            for gsv in gsvs:
                if gsv.ode_gene_id in ode2ref:
                    gsv.ode_ref = ode2ref[gsv.ode_gene_id]
                else:
                    gsv.ode_ref = 'None'

                gsv.gdb_id = original_gdb_id

        return gsvs
        #return [GenesetValue(gsv_dict) for gsv_dict in dictify_cursor(cursor)]


def get_geneset_values_simple(gsid):
    """
    Returns all geneset_values for the given gsid without selecting based on
    homology, gene ID types, or any of the complicated stuff get_geneset_values
    does. 
    This function only returns genes that have an entry in the gene table. Many
    gene sets have defunct or singular ode_gene_ids used to represent genes
    that may not exist or are unknown (microarray probes, riken clones, etc).
    This is done to match the results returned by our tools, namely Jaccard
    similarity.

    arguments
        gsid: gene set ID

    returns
        a list of dicts for each geneset_value
    """

    with PooledCursor() as cursor:
        cursor.execute(
            '''
            SELECT DISTINCT ON (gv.ode_gene_id) gv.*
            FROM        geneset_value gv
            INNER JOIN  gene g
            USING       (ode_gene_id)
            WHERE  gs_id = %s AND
                   g.ode_pref;
            ''', (gsid,)
        )

        return dictify_cursor(cursor)


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
            cursor.execute('''SELECT * FROM tool_param WHERE tool_classname=%s ORDER BY tp_name;''',
                           (tool_classname,))
        return [ToolParam(d) for d in dictify_cursor(cursor)]


class ToolConfig:
    def __init__(self, tool_dict):
        self.classname = tool_dict['tool_classname']
        self.name = tool_dict['tool_name']
        self.description = tool_dict['tool_description']
        try:
            self.requirements = [x.strip() for x in tool_dict['tool_requirements'].split(',')]
        except:
            self.requirements = None
        self.is_active = tool_dict['tool_active'] == '1'
        self.sort_priority = tool_dict['tool_sort']
        self.__params = None

    @property
    def params(self):
        if self.__params is None:
            self.__params = OrderedDict(((tp.name, tp)
                                         for tp in get_tool_params(self.classname)))

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


def insert_result(usr_id, res_runhash, gs_ids, res_data, res_tool, res_description, res_status, res_api='f'):
    with PooledCursor() as cursor:
        ## res_api isn't part of the database (at least on crick), rather than
        ## screw up table structure, res_api is commented out for now
        # cursor.execute(
        #	 '''
        #	 INSERT INTO result (usr_id, res_runhash, gs_ids, res_data, res_tool, res_description, res_status, res_started, res_api)
        #	 VALUES (%s, %s, %s, %s, %s, %s, %s, now(), %s)
        #	 RETURNING res_id;
        #	 ''',
        #	 (usr_id, res_runhash, ','.join(gs_ids), res_data, res_tool, res_description, res_status, res_api)
        # )
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


def get_all_userids():
    with PooledCursor() as cursor:
        cursor.execute(
                '''SELECT usr_id, usr_email FROM production.usr LIMIT 15;'''),
    return list(dictify_cursor(cursor))


def get_species_name_by_id(sp_id):
    """
    returns the species name given a valid species id
    """
    with PooledCursor() as cursor:
        cursor.execute('''SELECT sp_name FROM species WHERE sp_id=%s;''', (sp_id,))
        sp_name = cursor.fetchone()[0]
    return sp_name


def get_sp_id():
    """
    returns all species ids
    """
    with PooledCursor() as cursor:
        cursor.execute('''SELECT sp_id FROM species WHERE sp_id > 0 ORDER BY sp_id ASC;''')
        sp_id = list(dictify_cursor(cursor))
    return sp_id

def get_sp_id_by_gsid(gs_id):
    """
    Returns the sp_id associated with a geneset
    :param gs_id:
    :return:
    """
    with PooledCursor() as cursor:
        cursor.execute('''SELECT sp_id FROM geneset WHERE gs_id=%s;''', (gs_id,))
        sp_id = list(dictify_cursor(cursor))
    return sp_id


def get_gdb_sp(ode_ref):
    """
    Returns the sp_id associated with a geneset
    :param gs_id:
    :return:
    """
    with PooledCursor() as cursor:
        cursor.execute('''SELECT sp_id FROM genedb WHERE gdb_id=%s;''', (ode_ref,))
        gdb_sp = list(dictify_cursor(cursor))
    return gdb_sp


def export_results_by_gs_id(gs_id):
    """
    Write a generic tab file for geneset products
    :param args: gs_id
    :return: status. 1 == success, 0 == failure
    """
    gene = {}
    with PooledCursor() as cursor:
        cursor.execute(
                '''SELECT gsv_source_list[1], gsv_value from geneset_value
              WHERE gs_id=%s;''', (gs_id,)
        )
        for gid in cursor:
            gene[gid[0]] = str(gid[1])
    return gene


def get_gdb_names():
    """
    get all names associated with gene databases, essentially all external resources for gene names
    :return: 
    """
    gdb_names = []
    with PooledCursor() as cursor:
        cursor.execute(
            '''SELECT gdb_name FROM genedb ORDER BY gdb_id'''
        )
        for name in cursor:
            gdb_names.append(name[0])
    return gdb_names


def get_all_gene_ids(gs_id):
    """
    this exports all gene symbols in a list
    :param gs_id: 
    :return: 
    """
    # Get all of the gdb_names for seeding the disctionary
    gdb_names = get_gdb_names()
    # perform query and loop over them to create a dictionary of dictionaries
    data = defaultdict(dict)
    with PooledCursor() as cursor:
        cursor.execute(
            '''SELECT gsv.ode_gene_id, g.ode_ref_id, gdb.gdb_name 
                FROM gene g, genedb gdb, geneset_value gsv, geneset gs
                 WHERE gs.gs_id=%s AND gs.sp_id=g.sp_id AND gs.gs_id=gsv.gs_id AND gsv.ode_gene_id=g.ode_gene_id 
                 AND g.gdb_id=gdb.gdb_id ORDER BY g.ode_gene_id''' % (gs_id,)
        )
        results = cursor.fetchall()
    # loop through results to build dictionary
    for name in gdb_names:
        for gid in results:
            # initialize dict if name does not exist
            if name not in data[gid[0]]:
                data[gid[0]][name] = '-'
            cur_value = data[gid[0]][name]
            if str(gid[2]) == name:
                if data[gid[0]][name] is '-':
                    data[gid[0]][name] = str(gid[1])
                else:
                    data[gid[0]][name] = '|'.join((cur_value + '|' + str(gid[1])).split('|'))
    return data


def get_gene_sym_by_intersection(geneset_id1, geneset_id2):
    """
    Get all gene info for all genes in both genesets (mainly for jaccard similarity intersection page)
    :return: all the gene ids (ode gene ids) for the genes intersecting
    """
    gene_id1 = []
    gene_id2 = []
    intersect_sym = []
    with PooledCursor() as cursor:
        cursor.execute(
                '''SELECT ode_gene_id
               FROM extsrc.geneset_value
               where gs_id = %s;
            ''', (geneset_id1,))
        for gid in cursor:
            gene_id1.append(gid[0])
        cursor.execute(
                '''SELECT ode_gene_id
               FROM extsrc.geneset_value
               where gs_id = %s;
            ''', (geneset_id2,))
        for gid in cursor:
            gene_id2.append(gid[0])

        intersect_id = list(set(gene_id1).intersection(gene_id2))
        print "intersect_id ", intersect_id

        for gene_id in intersect_id:
            cursor.execute(
                    '''SELECT gi_symbol
                   FROM extsrc.gene_info
                   where ode_gene_id = %s;
                ''', (gene_id,))
            for gid in cursor:
                intersect_sym.append(gid[0])

        # print "intersect_sym ", intersect_sym
        return intersect_sym, intersect_id


def if_gene_has_homology(gene_id):
    """
    Chech if the gene has homolgy (use in intersection page)
    :param gene_id:
    :return:
    """
    with PooledCursor() as cursor:
        cursor.execute(
                '''SELECT hom_id
               FROM extsrc.homology
               where ode_gene_id = %s;
            ''', (gene_id,))
        if cursor.fetchone():
            return 1
        else:
            return 0


def get_intersect_by_homology(gsid1, gsid2):
    """
    Returns genes found in the intersection of two gene sets while including
    homologous relationships. If a gene has no homologs, it is not returned.

    arguments
        gsid1: gene set ID for the first set
        gsid2: gene set ID for the second set

    returns
        a list of dicts containing gene symbols, ODE IDs, and homology IDs for
        each gene found at the intersection of both sets
    """

    genes = []

    with PooledCursor() as cursor:
        ## Retrieves gene set values for each gene set then finds genes at the
        ## intersection of both sets using homology IDs
        cursor.execute(
            '''
            SELECT g1.gi_symbol, g1.ode_gene_id, g1.hom_id 
            FROM   (
                SELECT      gv.ode_gene_id, gi.gi_symbol, h.hom_id
                FROM        extsrc.geneset_value AS gv 
                INNER JOIN  homology AS h 
                USING       (ode_gene_id) 
                INNER JOIN  gene_info AS gi 
                USING       (ode_gene_id) 
                WHERE       gs_id = %s
            ) g1
            INNER JOIN (
                SELECT      gv.ode_gene_id, gi.gi_symbol, h.hom_id
                FROM        extsrc.geneset_value AS gv 
                INNER JOIN  homology AS h 
                USING       (ode_gene_id) 
                INNER JOIN  gene_info AS gi 
                USING       (ode_gene_id) 
                WHERE       gs_id = %s
            ) g2
            ON g1.hom_id = g2.hom_id;
            ''', (gsid1, gsid2)
        )

        return dictify_cursor(cursor)


def get_geneset_intersect(gsid1, gsid2):
    """
    Returns genes found in the intersection of two gene sets. Should only be
    used on sets of the same species since this function does not account for
    homology. Use get_intersect_by_homolgy if the sets are from two different
    species.

    arguments
        gsid1: gene set ID for the first set
        gsid2: gene set ID for the second set

    returns
        a list of dicts containing gene symbols and ODE IDs for each gene found
        at the intersection of both sets
    """

    genes = []

    with PooledCursor() as cursor:
        cursor.execute(
            '''
            SELECT  gv.ode_gene_id, gi.gi_symbol
            FROM    (
                SELECT  ode_gene_id
                FROM    geneset_value
                WHERE   gs_id = %s

                INTERSECT

                SELECT  ode_gene_id
                FROM    extsrc.geneset_value
                WHERE   gs_id = %s
            ) gv
            INNER JOIN  gene_info AS gi
            USING       (ode_gene_id);
            ''', (gsid1, gsid2)
        )

        return dictify_cursor(cursor)

# function to check whether an emphasis gene is found in a geneset
def check_emphasis(gs_id, em_gene):
    inGeneset = False;
    # Find all the genes in a geneset
    with PooledCursor() as cursor:
        cursor.execute(
                ''' SELECT *
                FROM geneset_value
                WHERE gs_id = %s;
            ''', (gs_id,)
        )

    result = cursor.fetchall()
    # If there were no genes do nothing else put the ode_gene_ids of the geneset
    # into a list
    if result != None:
        geneList = [gene[1] for gene in result]

    em_gene = long(em_gene)

    # If the emphasis gene was found in the geneset return true
    if em_gene in geneList:
        inGeneset = True

    return inGeneset


def get_geneset_info(gs_id):
    """
    Retrieves the geneset_info entry for the given gene set ID. If an entry for
    the gene set does not exist in the geneset_info table, a new one is created
    and the new instance is returned.

    args
        gs_id: gene set ID

    returns
        a GenesetInfo object
    """

    with PooledCursor() as cursor:

        cursor.execute(
            '''
            SELECT  *
            FROM    production.geneset_info
            WHERE   gs_id = %s
            ''',
                (gs_id,)
        )

        if not cursor.rowcount:
            insert_geneset_info(gs_id)

            ## I hope there's no way for this to cause a recursion loop...
            return get_geneset_info(gs_id)

        else:
            gi_list = [GenesetInfo(d) for d in dictify_cursor(cursor)]

            if gi_list:
                return gi_list[0]

            else:
                return None


def insert_geneset_info(gs_id):
    """
    Inserts a new entry into the geneset_info table for the given gene set ID.
    This function does not check to make sure an entry already exists, that is
    up to the caller.

    args
        gs_id: gene set ID

    returns
        a GenesetInfo object
    """
    with PooledCursor() as cursor:

        cursor.execute(
            '''
            INSERT INTO production.geneset_info (gs_id)
            VALUES      (%s);
            ''',
                (gs_id,)
        )

        cursor.connection.commit()


def insert_omicssoft_metadata(gs_id, project, source, tag, otype):
    """
    Inserts metadata from OmicsSoft gene sets into the special OmicsSoft table.
    This is additional GW functionality requested by Sanofi.

    arguments
        gs_id: gene set ID
        project: the project field from an OmicsSoft gene set 
        tag: the tag field from an OmicsSoft gene set 
        source: the source field from an OmicsSoft gene set 
    """

    with PooledCursor() as cursor:

        cursor.execute(
            '''
            INSERT INTO production.omicsoft
                (gs_id, os_project, os_tag, os_source, os_type)
            VALUES
                (%s, %s, %s, %s, %s);
            ''', (gs_id, project, tag, source, otype)
        )

        cursor.connection.commit()

## These functions below were added for the new batch parser. If some variant
## of them already exists elsewhere in this file (I looked and couldn't find 
## them), please delete these and update batch.py accordingly.

def get_gene_ids_by_spid_type(sp_id, gdb_id):
    """
    Returns a mapping of ode_ref_ids -> ode_gene_ids.

    arguments
        sp_id:  the species ID
        gdb_id: the gene type ID

    returns
        a dict
    """

    ## There is an issue with gene symbols. Some species have duplicate symbols
    ## with different ode_gene_ids. One is the correct entry, the other is an
    ## entry for another gene with the same symbol (incorrectly attributed).
    ## One e.g. is the mouse Ccr4 gene. There is the true entry for Ccr4, but
    ## another gene (Cnot6) also has CCR4 as a gene symbol synonym which 
    ## screws with our case insensitive searches. So, when symbols are
    ## searched for the ode_pref_tag MUST be used.
    #gene_types = get_short_gene_types()
    gene_types = get_gene_id_types()
    use_pref = False

    for d in gene_types:
        if d['gdb_shortname'] == 'symbol' and d['gdb_id'] == gdb_id:
            use_pref = True

    with PooledCursor() as cursor:

        if use_pref:
            cursor.execute(
                '''
                SELECT  lower(ode_ref_id), ode_gene_id
                FROM    extsrc.gene
                WHERE   sp_id = %s AND
                        gdb_id = %s AND
                        ode_pref = 't';
                ''',
                    (sp_id, gdb_id)
            )

        else:
            cursor.execute(
                '''
                SELECT  lower(ode_ref_id), ode_gene_id
                FROM    extsrc.gene
                WHERE   sp_id = %s AND
                        gdb_id = %s;
                ''',
                    (sp_id, gdb_id)
            )

        d = {}

        for ref_id, gene_id in cursor.fetchall():
            d[ref_id] = gene_id

        return d

def get_platform_probes(pf_id):
    """
    Returns a mapping of probe names (prb_ref_ids from a particular microarray
    platform) to their IDs.

    arguments
        pf_id:  platform ID

    returns
        a dict mapping prb_ref_ids -> prb_ids
    """

    with PooledCursor() as cursor:

        cursor.execute(
            '''
            SELECT  prb_ref_id, prb_id
            FROM    odestatic.probe
            WHERE   pf_id = %s;
            ''',
                (pf_id,)
        )

        d = {}

        for ref_id, gene_id in cursor.fetchall():
            d[ref_id] = gene_id

        return d

def get_probe2gene(prb_ids):
    """
    Returns a mapping of prb_ids -> ode_gene_ids for the given set of prb_ids.

    arguments
        prb_ids: a list of probe IDs

    returns
        a dict mapping of prb_id -> prb_ref_id
    """

    if type(prb_ids) == list:
        prb_ids = tuple(prb_ids)

    with PooledCursor() as cursor:

        cursor.execute(
            '''
            SELECT  prb_id, ode_gene_id
            FROM    extsrc.probe2gene
            WHERE   prb_id in %s;
            ''',
                (prb_ids,)
        )

        d = {}

        for ref_id, gene_id in cursor.fetchall():
            if ref_id in d:
                d[ref_id].append(gene_id)

            else:
                d[ref_id] = [gene_id]

        return d

def get_publication_mapping():
    """
    Returns a mapping of PMID -> pub_id for all publications in the DB.

    returns
        a dict mapping PMIDs -> pub_ids
    """

    with PooledCursor() as cursor:

        cursor.execute(
            '''
            SELECT DISTINCT ON  (pub_pubmed) pub_pubmed, pub_id
            FROM                production.publication
            ORDER BY            pub_pubmed, pub_id;
            '''
        )

        return OrderedDict(cursor)

def insert_file(contents, comments):
    """
    Inserts a new file into the database.

    arguments
        contents:   file contents which MUST be in the format:
                        gene\tvalue\n
        comments:   misc. comments about this file

    returns
        a file_id
    """

    with PooledCursor() as cursor:

        cursor.execute(
            '''
            INSERT INTO file
                (file_size, file_contents, file_comments, file_created)
            VALUES
                (%s, %s, %s, NOW())
            RETURNING file_id;
            ''',
                (len(contents), contents, comments)
        )

        cursor.connection.commit()

        return cursor.fetchone()[0]

def insert_geneset_value(gs_id, gene_id, value, name, threshold):
    """
    Inserts a new geneset_value into the database.

    arguments
        gs_id:      gene set ID
        gene_id:    ode_gene_id
        value:      value associated with this gene
        name:       a gene name or symbol (typically an ode_ref_id)
        threshold:  boolean indicating if the value is within the threshold

    returns
        the gs_id associated with this gene set value
    """

    with PooledCursor() as cursor:

        cursor.execute(
            '''
            INSERT INTO geneset_value

                (gs_id, ode_gene_id, gsv_value, gsv_source_list,
                gsv_value_list, gsv_in_threshold, gsv_hits, gsv_date)

            VALUES

                (%s, %s, %s, %s, %s, %s, 0, NOW())

            RETURNING gs_id;
            ''',
                (gs_id, gene_id, value, [name], [float(value)], threshold)
        )

        cursor.connection.commit()

        return cursor.fetchone()[0]

def insert_publication(pub):
    """
    Inserts a new publication into the database.

    arguments
        pub: a dict with fields matching the columns in the publication table

    returns
        a pub_id
    """

    with PooledCursor() as cursor:

        cursor.execute(
            '''
            INSERT INTO publication

                (pub_authors, pub_title, pub_abstract, pub_journal,
                pub_volume, pub_pages, pub_month, pub_year, pub_pubmed)

            VALUES

                (%(pub_authors)s, %(pub_title)s, %(pub_abstract)s,
                %(pub_journal)s, %(pub_volume)s, %(pub_pages)s, %(pub_month)s,
                %(pub_year)s, %(pub_pubmed)s)

            RETURNING pub_id;
            ''',
                pub
        )

        cursor.connection.commit()

        return cursor.fetchone()[0]

def insert_geneset(gs):
    """
    Inserts a new geneset into the database.

    arguments
        gs: a dict whose keys match the columns in the geneset table

    returns
        a gs_id
    """

    if ('gs_created' not in gs):
        gs['gs_created'] = 'NOW()'

    if ('pub_id' not in gs):
        gs['pub_id'] = None

    if 'gs_attribution' not in gs:
        gs['gs_attribution'] = None

    with PooledCursor() as cursor:

        cursor.execute(
            '''
            INSERT INTO geneset

                (usr_id, file_id, gs_name, gs_abbreviation, pub_id, cur_id,
                gs_description, sp_id, gs_count, gs_threshold_type,
                gs_threshold, gs_groups, gs_gene_id_type, gs_created,
                gs_attribution)

            VALUES

                (%(usr_id)s, %(file_id)s, %(gs_name)s, %(gs_abbreviation)s,
                %(pub_id)s, %(cur_id)s, %(gs_description)s, %(sp_id)s,
                %(gs_count)s, %(gs_threshold_type)s, %(gs_threshold)s,
                %(gs_groups)s, %(gs_gene_id_type)s, %(gs_created)s,
                %(gs_attribution)s)

            RETURNING gs_id;
            ''',
                gs
        )

        cursor.connection.commit()

        return cursor.fetchone()[0]


# sample api calls begin

# get all genesets associated to a gene by gene_ref_id and gdb_id
#	if homology is included at the end of the URL also return all

# Tool Information Functions  


def get_file(apikey, task_id, file_type):
    # check to see if user has permissions for the result
    user_id = get_user_id_by_apikey(apikey)
    with PooledCursor() as cursor:
        cursor.execute('''SELECT usr_id FROM production.result WHERE res_runhash=%s''', (task_id,))
    user_id_result = cursor.fetchone()
    if (user_id != user_id_result):
        return "Error: User does not have permission to view the file."

    # if exists
    rel_path = task_id + "." + file_type
    # abs_file_path = os.path.join(RESULTS_PATH, rel_path)
    abs_file_path = os.path.join(config.get('application', 'results'), rel_path)
    # print(abs_file_path)
    if (os.path.exists(abs_file_path)):
        return flask.redirect("/results/" + rel_path)
    else:
        return "Error: No such File! Check documentatin for supported file types of each tool."


def get_link(apikey, task_id, file_type):
    # check to see if user has permissions for the result
    user_id = get_user_id_by_apikey(apikey)
    with PooledCursor() as cursor:
        cursor.execute('''SELECT usr_id FROM production.result WHERE res_runhash=%s''', (task_id,))
    user_id_result = cursor.fetchone()
    if (user_id != user_id_result):
        return "Error: User does not have permission to view the file."

    # if exists
    rel_path = task_id + "." + file_type
    # abs_file_path = os.path.join(RESULTS_PATH, rel_path)
    abs_file_path = os.path.join(config.get('application', 'results'), rel_path)
    # print(abs_file_path)
    if (os.path.exists(abs_file_path)):
        return "/results/" + rel_path
    else:
        return "Error: No such File! Check documentatin for supported file types of each tool."


def get_status(task_id):
    async_result = tc.celery_app.AsyncResult(task_id)
    return async_result.state


# private function that is not called by api
def get_user_id_by_apikey(apikey):
    """
    Looks up a User in the database
    :param user_id:		the user's apikey
    :return:			the User id matching the apikey or None if no such user is found
    """
    with PooledCursor() as cursor:
        cursor.execute('''SELECT usr_id FROM production.usr WHERE apikey=%s''', (apikey,))
    return cursor.fetchone()


#	genesets associated with homologous genes 
def get_genesets_by_gene_id(apikey, gene_ref_id, gdb_name, homology):
    """
    Get all genesets for a specific gene_id
    :return: the geneset into matching the given ID or None if no such gene is found
    """
    curUsrId = get_user_id_by_apikey(apikey)
    if (curUsrId):
        if not homology:
            with PooledCursor() as cursor:
                cursor.execute(
                        ''' SELECT row_to_json(row, true)
                        FROM (	SELECT geneset.*
                                FROM production.geneset
                                WHERE geneset.gs_id in
                                (
                                    SELECT gs_id
                                    FROM (extsrc.gene join odestatic.genedb using(gdb_id))
                                        join extsrc.geneset_value using(ode_gene_id)
                                    WHERE ode_ref_id = %s and gdb_name = %s
                                ) and ( cur_id < 5 or (cur_id = 5 and usr_id = %s) )
                            ) row; ''', (gene_ref_id, gdb_name, curUsrId,))
        else:
            with PooledCursor() as cursor:
                cursor.execute(
                        ''' SELECT row_to_json(row, true)
                        FROM (	SELECT geneset.*
                                FROM production.geneset
                                WHERE geneset.gs_id in
                                (
                                    SELECT gs_id
                                    FROM extsrc.geneset_value
                                    WHERE geneset_value.ode_gene_id in
                                    (
                                        SELECT ode_gene_id
                                        FROM extsrc.homology
                                        WHERE hom_id in
                                        (
                                            SELECT hom_id
                                            FROM extsrc.homology join extsrc.gene using(ode_gene_id)
                                                join odestatic.genedb using(gdb_id)
                                            WHERE ode_ref_id = %s and gdb_name = %s
                                        )
                                    )
                                ) and ( cur_id < 5 or (cur_id = 5 and usr_id = %s) )
                            ) row; ''', (gene_ref_id, gdb_name, curUsrId,))
    else:
        if not homology:
            with PooledCursor() as cursor:
                cursor.execute(
                        ''' SELECT row_to_json(row, true)
                        FROM (	SELECT geneset.*
                                FROM production.geneset
                                WHERE geneset.gs_id in
                                (
                                    SELECT gs_id
                                    FROM (extsrc.gene join odestatic.genedb using(gdb_id))
                                        join extsrc.geneset_value using(ode_gene_id)
                                    WHERE ode_ref_id = %s and gdb_name = %s
                                ) and cur_id < 5
                            ) row; ''', (gene_ref_id, gdb_name,))
        else:
            with PooledCursor() as cursor:
                cursor.execute(
                        ''' SELECT row_to_json(row, true)
                        FROM (	SELECT geneset.*
                                FROM production.geneset
                                WHERE geneset.gs_id in
                                (
                                    SELECT gs_id
                                    FROM extsrc.geneset_value
                                    WHERE geneset_value.ode_gene_id in
                                    (
                                        SELECT ode_gene_id
                                        FROM extsrc.homology
                                        WHERE hom_id in
                                        (
                                            SELECT hom_id
                                            FROM extsrc.homology join extsrc.gene using(ode_gene_id)
                                                join odestatic.genedb using(gdb_id)
                                            WHERE ode_ref_id = %s and gdb_name = %s
                                        )
                                    )
                                ) and cur_id < 5
                            ) row; ''', (gene_ref_id, gdb_name,))
    return cursor.fetchall()


def get_genes_by_geneset_id(geneset_id):
    """
    Get all gene info for a specifics gene_id
    :return: the gene matching the given ID or None if no such gene is found
    """

    with PooledCursor() as cursor:
        cursor.execute(
                ''' SELECT row_to_json(row, true)
                FROM (	SELECT gene.*
                        FROM extsrc.gene join extsrc.geneset_value using(ode_gene_id)
                        where gs_id = %s) row; ''', (geneset_id,))

    return cursor.fetchall()


def get_gene_by_id(gene_id):
    """
    Get all gene info for a specific gene_id
    :return: the gene matching the given ID or None if no such gene is found
    """

    with PooledCursor() as cursor:
        cursor.execute(
                ''' SELECT row_to_json(row, true)
                FROM (	SELECT *
                        FROM extsrc.gene_info
                        where ode_gene_id = %s) row; ''', (gene_id,))

    return cursor.fetchall()


def get_geneset_by_geneset_id(geneset_id):
    """
    Get all gene info for a specifics gene_id
    :return: the gene matching the given ID or None if no such gene is found
    """

    with PooledCursor() as cursor:
        cursor.execute(
                ''' SELECT row_to_json(row, true)
                FROM (	SELECT *
                        FROM production.geneset
                        where gs_id = %s) row; ''', (geneset_id,))

    return cursor.fetchall()


def get_geneset_by_user(apikey):
    """
    Get all gene info for a specifics user
    :return: the genesets matching the given apikey or None if no such genesets are found
    """
    apiUsrId = get_user_id_by_apikey(apikey)
    if (apiUsrId):
        with PooledCursor() as cursor:
            cursor.execute(
                    ''' SELECT row_to_json(row, true)
                    FROM (	SELECT *
                            FROM production.geneset
                            WHERE usr_id = %s) row; ''', (apiUsrId,))
        return cursor.fetchall()
    else:
        return "No user with that key"


def get_projects_by_user(apikey):
    with PooledCursor() as cursor:
        cursor.execute(
                ''' SELECT row_to_json(row, true)
                FROM(	SELECT *
                        FROM production.project
                        WHERE usr_id = (SELECT usr_id
                                        FROM production.usr
                                        WHERE apikey = %s)
                    ) row; ''', (apikey,))
    return cursor.fetchall()


def get_probes_by_gene(apikey, ode_ref_id):
    with PooledCursor() as cursor:
        cursor.execute(
                ''' SELECT row_to_json(row, true)
                FROM(	SELECT *
                        FROM odestatic.probe
                        WHERE prb_id IN (	SELECT prb_id
                                            FROM extsrc.probe2gene
                                            WHERE ode_gene_id IN (	SELECT ode_gene_id
                                                                    FROM extsrc.gene
                                                                    WHERE ode_ref_id = %s))
                    ) row; ''', (ode_ref_id,))
    return cursor.fetchall()


def get_platform_by_id(apikey, pf_id):
    with PooledCursor() as cursor:
        cursor.execute(
                ''' SELECT row_to_json(row, true)
                FROM(	SELECT *
                        FROM odestatic.platform
                        WHERE pf_id = %s
                    ) row; ''', (pf_id,))
    return cursor.fetchall()


def get_snp_by_geneid(apikey, ode_ref_id):
    with PooledCursor() as cursor:
        cursor.execute(
                ''' SELECT row_to_json(row, true)
                FROM(	SELECT *
                        FROM extsrc.snp
                        WHERE ode_gene_id IN (	SELECT ode_gene_id
                                                FROM extsrc.gene
                                                WHERE ode_ref_id = %s)
                    ) row; ''', (ode_ref_id,))
    return cursor.fetchall()


def get_publication_by_id(apikey, pub_id):
    with PooledCursor() as cursor:
        cursor.execute(
                ''' SELECT row_to_json(row, true)
                FROM(	SELECT *
                        FROM production.publication
                        WHERE pub_id = %s
                    ) row; ''', (pub_id,))
    return cursor.fetchall()


def get_species_by_id(apikey, sp_id):
    with PooledCursor() as cursor:
        cursor.execute(
                ''' SELECT row_to_json(row, true)
                FROM(	SELECT *
                        FROM odestatic.species
                        WHERE sp_id = %s
                    ) row; ''', (sp_id,))
    return cursor.fetchall()


def get_results_by_user(apikey):
    usr_id = get_user_id_by_apikey(apikey)
    with PooledCursor() as cursor:
        cursor.execute(
                ''' SELECT row_to_json(row, true)
                FROM(	SELECT res_created, res_runhash
                        FROM production.result
                        WHERE usr_id = %s ORDER BY res_created DESC
                    ) row; ''', (usr_id,))
    return cursor.fetchall()


def get_result_by_runhash(apikey, res_runhash):
    usr_id = get_user_id_by_apikey(apikey)
    with PooledCursor() as cursor:
        cursor.execute(
                ''' SELECT row_to_json(row, true)
                FROM(	SELECT *
                        FROM production.result
                        WHERE usr_id = %s and res_runhash = %s
                    ) row; ''', (usr_id, res_runhash))
    return cursor.fetchall()


def get_all_ontologies_by_geneset(gs_id, gso_ref_type):
    with PooledCursor() as cursor:
        if gso_ref_type == "All Reference Types":
            cursor.execute(
                    '''
                    SELECT *
                    FROM extsrc.ontology NATURAL JOIN odestatic.ontologydb
                    WHERE ont_id in (
                                      SELECT ont_id
                                      FROM extsrc.geneset_ontology
                                      WHERE gs_id = %s
                                    )
                    ORDER BY ont_id
                    ''', (gs_id,)
            )
        else:
            cursor.execute(
                    '''
                    SELECT *
                    FROM extsrc.ontology NATURAL JOIN odestatic.ontologydb
                    WHERE ont_id in (
                                      SELECT ont_id
                                      FROM extsrc.geneset_ontology
                                      WHERE gs_id = %s AND gso_ref_type = %s
                                    )
                    ORDER BY ont_id
                    ''', (gs_id, gso_ref_type,)
            )
    ontology = [Ontology(row_dict) for row_dict in dictify_cursor(cursor)]
    return ontology


def search_ontology_terms(search):
    """
    Returns a list of ontology terms (as Ontology objects) that match a given
    search string.
    """

    with PooledCursor() as cursor:
        ## Wildcards have to be part of the substituted string or a syntax
        ## error will get thrown
        search = '%%' + search + '%%'

        cursor.execute(
            '''
            SELECT  *
            FROM        extsrc.ontology AS o
            INNER JOIN  odestatic.ontologydb AS odb
            ON          o.ontdb_id = odb.ontdb_id
            WHERE       ont_name ILIKE %s OR 
                        ont_ref_id ILIKE %s
            LIMIT       30;
            ''',
                (search, search)
        )

        return dictify_cursor(cursor)


def get_all_ontologies_by_geneset_and_db(gs_id, ontdb_id):
    with PooledCursor() as cursor:
        cursor.execute(
                '''
                SELECT *
                FROM extsrc.ontology NATURAL JOIN odestatic.ontologydb
                WHERE ont_id in (
                                  SELECT ont_id
                                  FROM extsrc.geneset_ontology
                                  WHERE gs_id = %s
                                )
                AND ontdb_id = %s
                ORDER BY ont_id
                ''', (gs_id, ontdb_id,)
        )
    ontology = [Ontology(row_dict) for row_dict in dictify_cursor(cursor)]
    return ontology


def get_ontology_by_id(ont_id):
    with PooledCursor() as cursor:
        cursor.execute(
            '''
                SELECT *
                FROM extsrc.ontology
                WHERE ont_id = %s
            ''', (ont_id,)
        )
    ontology = [Ontology(row_dict) for row_dict in dictify_cursor(cursor)]
    return ontology[0]

# call by API only
def get_genesets_by_projects(apikey, projectids):
    user = get_user_id_by_apikey(apikey)
    projects = '('
    pArray = projectids.split(':')
    formGenesets = ''
    # print(user[0])

    for proj in pArray:
        if (len(projects) > 1):
            projects += ','
        projects += proj
    projects += ')'

    query = 'SELECT gs_id FROM production.project2geneset WHERE pj_id IN ' \
            '(SELECT pj_id FROM production.geneset WHERE pj_id IN '
    query += projects
    query += ' and usr_id = '
    query += str(user[0])
    query += ');'

    with PooledCursor() as cursor:
        cursor.execute(query)

    genesets = cursor.fetchall()

    for geneset in genesets:
        if (len(formGenesets) > 0):
            formGenesets += ':'
        formGenesets += str(geneset[0])

    return formGenesets


def get_geneset_by_project_id(apikey, projectid):
    user = get_user_id_by_apikey(apikey)
    with PooledCursor() as cursor:
        cursor.execute(
                ''' SELECT row_to_json(row, true)
                FROM(	SELECT gs_id
                        FROM production.project2geneset
                        WHERE pj_id in (SELECT pj_id
                                        FROM production.geneset
                                        WHERE pj_id = %s and usr_id = %s)
                    ) row; ''', (projectid, user))
    return cursor.fetchall()

def get_geneset_by_project_id(projectid):
    with PooledCursor() as cursor:
        cursor.execute(
                ''' SELECT gs_id
                        FROM production.project2geneset
                        WHERE pj_id = %s;
                ''', (projectid,))
    return cursor.fetchall()

def get_user_by_project_id(projectid):
    with PooledCursor() as cursor:
        cursor.execute(
                '''
            select usr_id from production.project where pj_id = %s;
            ''', (projectid,)
        )

    return cursor.fetchall()


def get_gene_database_by_id(apikey, gdb_id):
    user = get_user_id_by_apikey(apikey)
    with PooledCursor() as cursor:
        cursor.execute(
                ''' SELECT row_to_json(row, true)
                FROM(	SELECT *
                        FROM odestatic.genedb
                        WHERE gdb_id = %s
                    ) row; ''', (gdb_id,))
    return cursor.fetchall()


def get_genesymbols_by_gs_id(gs_id):
    with PooledCursor() as cursor:
        cursor.execute(
                '''
            select g.ode_ref_id from gene g, geneset_value gv where gv.gs_id= %s and gv.ode_gene_id=g.ode_gene_id and g.gdb_id=7 and ode_pref='t';
            ''', (gs_id,)
        )

    return cursor.fetchall()

def get_genesymbols_by_pj_id(pj_id):
    with PooledCursor() as cursor:
        cursor.execute(
                '''
            SELECT g.ode_ref_id
            FROM extsrc.gene g, extsrc.geneset_value gv
            WHERE (gv.gs_id IN
             (SELECT gs_id AS geneSetId
               FROM production.project2geneset
               WHERE pj_id = %s))
             AND gv.ode_gene_id=g.ode_gene_id AND g.gdb_id=7 AND ode_pref='t';
            ''', (pj_id,)
        )

    return cursor.fetchall()


def get_gsinfo_by_gs_id(gs_id):
    with PooledCursor() as cursor:
        cursor.execute(
                '''
            select gs_name, gs_abbreviation, sp_id from geneset where gs_id = %s;
            ''', (gs_id,)
        )

    return cursor.fetchall()

def get_gsinfo_by_pj_id(pj_id):
    with PooledCursor() as cursor:
        cursor.execute(
                '''
            SELECT gs_name, gs_abbreviation, sp_id
            FROM production.geneset
            WHERE gs_id IN
              (SELECT gs_id
                FROM production.project2geneset
                WHERE pj_id = %s);
            ''', (pj_id,)
        )

    return cursor.fetchall()

def get_pjname_by_pj_id(pj_id):
    with PooledCursor() as cursor:
        cursor.execute(
                '''
            select pj_name from project where pj_id = %s;
            ''', (pj_id,)
        )

    return cursor.fetchall()

def get_parameters_for_tool(tp_name):
    with PooledCursor() as cursor:
        cursor.execute(
                '''
            select tp_options from odestatic.tool_param where tp_name = %s;
            ''', (tp_name,)
        )

    return cursor.fetchall()

def get_species_name_by_sp_id(sp_id):
    with PooledCursor() as cursor:
        cursor.execute(
                '''
            select sp_name from species where sp_id = %s;
            ''', (sp_id,)
        )

    return cursor.fetchall()[0][0]


# API only
def add_project_for_user(apikey, pj_name):
    user = get_user_id_by_apikey(apikey)
    with PooledCursor() as cursor:
        cursor.execute(
                ''' INSERT INTO production.project
                (usr_id, pj_name) VALUES (%s, %s)
                RETURNING pj_id;
                ''', (user, pj_name,))
        cursor.connection.commit()
    return cursor.fetchone()


# API only
def add_geneset_to_project(apikey, pj_id, gs_id):
    user = get_user_id_by_apikey(apikey)
    with PooledCursor() as cursor:
        cursor.execute(
                ''' INSERT INTO production.project2geneset
                        (pj_id, gs_id) VALUES ((SELECT pj_id
                                                FROM production.project
                                                WHERE usr_id = %s AND pj_id = %s),
                                                (SELECT gs_id
                                                 FROM production.geneset
                                                 WHERE gs_id = %s AND ( usr_id = %s OR
                                                                        cur_id != 5)))
                        RETURNING pj_id, gs_id;
            ''', (user, pj_id, gs_id, user,))
        cursor.connection.commit()
    return cursor.fetchall()


# API only
def delete_geneset_from_project(apikey, pj_id, gs_id):
    user = get_user_id_by_apikey(apikey)
    with PooledCursor() as cursor:
        cursor.execute(
                '''DELETE FROM production.project2geneset
                        WHERE pj_id = ( SELECT pj_id
                                        FROM production.project
                                        WHERE usr_id = %s AND pj_id = %s)
                                        AND gs_id = %s
                        RETURNING pj_id, gs_id;
            ''', (user, pj_id, gs_id))
        cursor.connection.commit()
    return cursor.fetchall()


def generate_api_key(user_id):
    char_set = string.ascii_lowercase + string.ascii_uppercase + string.digits
    new_api_key = ''.join(random.sample(char_set, 24))
    with PooledCursor() as cursor:
        cursor.execute(
                '''UPDATE usr
               SET apikey = %s
               WHERE usr_id = %s''', (new_api_key, user_id)
        )
        cursor.connection.commit()
    return new_api_key


def checkJaccardResultExists(setSize1, setSize2):
    try:
        with PooledCursor() as cursor:
            cursor.execute(
                    ''' SELECT *
                    FROM jaccard_distribution_results
                    WHERE set_size1 = %s and set_size2 = %s;
                ''', (setSize1, setSize2)
            )

        return list(dictify_cursor(cursor))
    except:
        # print "In the except"
        return []


def getPvalue(setSize1, setSize2, jaccard):
    try:
        with PooledCursor() as cursor:
            cursor.execute(
                    ''' SELECT *
                    FROM jaccard_distribution_results
                    WHERE set_size1 = %s and set_size2 = %s and jaccard_coef = %s;
                ''', (setSize1, setSize2, jaccard)
            )
        pVal = dictify_cursor(cursor)
        return cursor.fetchone()[5]
    except:
        return 0
