#
# The following SQL fragment defines the schema for the "pub_assignments" table.
#
# -- Table: production.pub_assignments
#
# -- DROP TABLE production.pub_assignments;
# -- SELECT * from production.pub_assignments
#
#
# CREATE TABLE production.pub_assignments
# (
#   id serial NOT NULL,
#   pub_id bigint NOT NULL,                            -- geneset for curation (publication.pub_id)
#   curation_group integer NOT NULL,                   -- group assigned for assignment (grp.grp_id)
#   created timestamp without time zone DEFAULT now(), -- time the geneset was submitted for curation
#   updated timestamp without time zone DEFAULT now(), -- time of last modification of this record
#   assignment_state integer NOT NULL,                 -- 1=unassigned, 2=assigned, 3=completed, 4=reviewed
#   assignee integer DEFAULT '-1'::integer,            -- performer of task (usr.usr_id)
#   assigner integer DEFAULT '-1'::integer,            -- assigner of task (usr.usr_id)
#   notes character varying,                           --
#   CONSTRAINT pub_assignments_pkey PRIMARY KEY (pub_id, curation_group)
#  )
#  WITH (OIDS=FALSE);
#

from __future__ import print_function
import geneweaverdb
import notifications
import uploadfiles
import curation_assignments
import annotator as ann
import json


class PubAssignment(object):

    UNASSIGNED = 1
    ASSIGNED = 2
    READY_FOR_REVIEW = 3
    REVIEWED = 4

    def __init__(self, row_dict):
        self.id = row_dict['id']
        self.state = row_dict['assignment_state']
        self.pub_id = row_dict['pub_id']
        self.assignee = row_dict['assignee']
        self.assigner = row_dict['assigner']
        self.notes = row_dict['notes']
        self.group = row_dict['curation_group']
        self.created = row_dict['created']
        self.updated = row_dict['updated']

    @property
    def state_as_string(self):
        state_dict = {
            PubAssignment.UNASSIGNED: "Unassigned",
            PubAssignment.ASSIGNED: "Assigned (in progress)",
            PubAssignment.READY_FOR_REVIEW: "Under Review",
            PubAssignment.REVIEWED: "Complete"
        }

        try:
            return state_dict[self.state]
        except KeyError:
            return "Unknown"

    def assign_to_curator(self, assignee_id, assigner_id, notes):
        """
        :param pub_assignment_id: id of assignment record
        :param assignee_id: id of user assigned task
        :param assigner_id: id of group admin assigning this publication
        :param note: message that will be sent to the assignee
        :return:
        """
        state = self.ASSIGNED

        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute(
                'UPDATE production.pub_assignments SET assignee=%s, assigner=%s, assignment_state=%s, notes=%s, updated=now() WHERE id=%s',
                (assignee_id, assigner_id, state, notes, self.id)
            )
            cursor.connection.commit()

        # Send notification to curator
        subject = "Publication Assigned To You For Review"
        message = "View Assignment: <i>" + self.get_url() + '</i><br>' + notes
        notifications.send_usr_notification(assignee_id, subject, message)

        self.notes = notes
        self.assignee = assignee_id
        self.assigner = assigner_id
        self.state = state

    def mark_as_complete(self, notes):
        state = self.READY_FOR_REVIEW

        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute(
                "UPDATE production.pub_assignments SET assignment_state=%s, notes=%s, updated=now() WHERE id=%s RETURNING assigner",
                (state, notes, self.id))
            cursor.connection.commit()
            assignee_id = cursor.fetchone()[0]

        # Send notification to assigner
        subject = 'Publication Assignment Complete'
        message = "View Assignment: <i>" + self.get_url() + '</i><br>' + notes
        notifications.send_usr_notification(assignee_id, subject, message)
        self.notes = notes
        self.state = state

    def review_accepted(self, notes):
        """
        :param notes: message that will be sent to the assigned reviewer
           and stored in the database and sent to the curator
        :return:
        """

        state = PubAssignment.REVIEWED

        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute(
                "UPDATE production.pub_assignments SET assignment_state=%s, notes=%s, updated=now() WHERE id=%s RETURNING assignee",
                (state, notes, self.id))
            cursor.connection.commit()
            assignee_id = cursor.fetchone()[0]

        # Send notification to curator
        subject = 'Publication Assignment Accepted'
        message = "View Assignment: <i>" + self.get_url() + '</i><br>' + notes
        notifications.send_usr_notification(assignee_id, subject, message)

        self.state = state

    def review_rejected(self, notes):
        """
        :param notes: notes to be stored in the database and sent to the curator
        :return:
        """

        state = PubAssignment.ASSIGNED

        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute(
                "UPDATE production.pub_assignments SET assignment_state=%s, notes=%s, updated=now() WHERE id=%s RETURNING assignee",
                (state, notes, self.id))
            cursor.connection.commit()
            assignee_id = cursor.fetchone()[0]

        # Send notification to curator
        subject = 'Publication Assignment Rejected'
        message = "View Assignment: <i>" + self.get_url() + '</i><br>' + notes
        notifications.send_usr_notification(assignee_id, subject, message)

        self.state = state

    def update_notes(self, notes):
        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute(
                "UPDATE production.pub_assignments SET notes=%s, updated=now() WHERE id=%s",
                (notes, self.id))
            cursor.connection.commit()
        self.notes = notes

    def get_genesets(self):
        gs_ids = []
        genesets = []
        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute("SELECT gs_id FROM production.gs_to_pub_assignment WHERE pub_assign_id=%s ORDER BY gs_id ASC", (self.id,))

            res = cursor.fetchall()
            for r in res:
                gs_ids.append(r[0])

            if gs_ids:
                sql = "SELECT geneset.* FROM geneset WHERE geneset.gs_id IN ({})".format(','.join(['%s'] * len(gs_ids)))
                cursor.execute(sql, gs_ids)

                genesets = [geneweaverdb.Geneset(row_dict) for row_dict in geneweaverdb.dictify_cursor(cursor)]
        return genesets

    def __insert_gs_to_pub(self, gs_id):
        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute('''INSERT INTO production.gs_to_pub_assignment (gs_id,
                              pub_assign_id) VALUES (%s, %s)''',
                           (gs_id, self.id))
            cursor.connection.commit()

    def create_geneset_stub(self, name, label, description, species_id, group_id='-1'):
        """
        create a stub geneset for this publication.  a stub geneset is a record
        that only has the basic information filled out.  This will generate a new
        geneset curation assignment for the publication curator. They will finish
        filling out the geneset through the geneset curation workflow.

        :param name: name of new geneset
        :param label: figure label for new geneset
        :param description: description of geneset
        :return: ID of new geneset
        """

        geneset_id = None

        if self.state == self.ASSIGNED:
            user = geneweaverdb.get_user(self.assignee)
            user_prefs = json.loads(user.prefs)

            # get the user's annotator preference.  if there isn't one in their user
            # preferences, default to the monarch annotator. if set, valid values
            # are 'ncbo', 'monarch', 'both'
            annotator = user_prefs.get('annotator', 'monarch')
            ncbo = True
            monarch = True
            if annotator == 'ncbo':
                monarch = False
            elif annotator == 'monarch':
                ncbo = False

            # default geneset as 'Private'
            # group id -1 signifies private
            gs_groups = group_id
            # set initial curation level to 5 (private)
            cur_id = 5

            # right now, this can be set in the curation view.  should we
            # set this in the stub?
            gene_identifier = 0

            with geneweaverdb.PooledCursor() as cursor:
                file_id = uploadfiles.insert_new_contents_to_file("")
                cursor.execute('''INSERT INTO production.geneset (usr_id, file_id, gs_name, gs_abbreviation, pub_id, cur_id,
                                  gs_description, sp_id, gs_count, gs_groups, gs_gene_id_type, gs_created, gs_status)
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s) RETURNING gs_id''',
                               (self.assignee, file_id, name, label,
                                self.pub_id, cur_id,
                                description, species_id, 0, gs_groups,
                                gene_identifier,
                                'delayed',))
                geneset_id = cursor.fetchone()[0]
                cursor.connection.commit()

            if geneset_id:
                curation_assignments.submit_geneset_for_curation(geneset_id,
                                                                 self.group,
                                                                 "", False)
                assignment = curation_assignments.get_geneset_curation_assignment(geneset_id)
                assignment.assign_curator(self.assignee, self.assigner, "")

                self.__insert_gs_to_pub(geneset_id)

                # run the annotator for the geneset (on geneset description and the
                # publication
                gs = geneweaverdb.get_geneset(geneset_id, self.assignee)
                publication = geneweaverdb.get_publication(self.pub_id)
                ann.insert_annotations(cursor, geneset_id, gs.description,
                                       publication.abstract, ncbo=ncbo,
                                       monarch=monarch)

        return geneset_id

    def get_url(self):
        return get_pub_assignment_url(self.id)


def get_pub_assignment_url(pub_assignment_id):
    """
    returns a URL to view a publication assignment. the publication id and
    group id together uniquely identify the assignment
    :param pub_id: publication id
    :param group_id: group id
    :return:
    """
    return '<a href="{url_prefix}/viewPubAssignment/' + str(pub_assignment_id) + '">' + str(pub_assignment_id) + '</a>'


def queue_publication(pub_id, group_id, note):
    """
    :param pub_id: publication submitted for review
    :param group_id: group responsible for the curation
    :param note: message that will be sent to the group admins
    :return:
    """

    state = PubAssignment.UNASSIGNED
    with geneweaverdb.PooledCursor() as cursor:

        # JGP - for now delete the object to prevent exception on the INSERT...
        cursor.execute(
            "DELETE FROM production.pub_assignments WHERE pub_id=%s AND curation_group=%s", (pub_id, group_id))

        # Add a record to the table
        cursor.execute(
            'INSERT INTO production.pub_assignments (pub_id, curation_group, assignment_state, notes) VALUES (%s, %s, %s, %s) RETURNING id',
            (pub_id, group_id, state, note))
        cursor.connection.commit()
        assignment_id = cursor.fetchone()[0]

        # send notification to the group admins
        subject = 'Publication Queued for Review'
        message = 'View Assignment: <i>' + get_pub_assignment_url(assignment_id) + '</i><br>' + note
        notifications.send_group_admin_notification(group_id, subject, message)


def get_publication_assignment(pub_assignment_id):
    with geneweaverdb.PooledCursor() as cursor:

        cursor.execute("SELECT * FROM production.pub_assignments WHERE id=%s", (pub_assignment_id,))

        assignments = list(geneweaverdb.dictify_cursor(cursor))
        return PubAssignment(assignments[0]) if len(assignments) == 1 else None


def get_publication_assignment_by_pub_id(pub_id, group_id):
    with geneweaverdb.PooledCursor() as cursor:

        cursor.execute("SELECT * FROM production.pub_assignments WHERE pub_id=%s AND curation_group=%s", (pub_id, group_id))

        assignments = list(geneweaverdb.dictify_cursor(cursor))
        return PubAssignment(assignments[0]) if len(assignments) == 1 else None






