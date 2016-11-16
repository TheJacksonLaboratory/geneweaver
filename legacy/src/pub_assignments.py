#
# The following SQL fragment defines the schema for the "curation_assignments" table.
#
# -- Table: production.pub_assignments
#
# -- DROP TABLE production.pub_assignments;
# -- SELECT * from production.pub_assignments
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


class PubAssignment(object):

    UNASSIGNED = 1
    ASSIGNED = 2
    READY_FOR_TEAM_REVIEW = 3
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
            PubAssignment.ASSIGNED: "Assigned",
            PubAssignment.READY_FOR_TEAM_REVIEW: "Under Review",
            PubAssignment.REVIEWED: "Complete"
        }

        try:
            return state_dict[self.state]
        except KeyError:
            return "Unknown"


def get_pub_assignment_url(pub_id, group_id):
    """
    returns a URL to view a publication assignment. the publication id and
    group id together uniquely identify the assignment
    :param pub_id: publication id
    :param group_id: group id
    :return:
    """
    return '<a href="{url_prefix}/viewPubAssignment/' + str(group_id) + '/' + str(pub_id) + '">' + str(pub_id) + '</a>'


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
            'INSERT INTO production.pub_assignments (pub_id, curation_group, assignment_state, notes) VALUES (%s, %s, %s, %s)',
            (pub_id, group_id, state, note))
        cursor.connection.commit()

        # send notification to the group admins
        subject = 'Publication Queued for Review'
        message = 'production.publication.pub_id: <i>' + get_pub_assignment_url(pub_id, group_id) + '</i><br>' + note
        notifications.send_group_admin_notification(group_id, subject, message)


def assign_publication(pub_id, group_id, assignee_id, assigner_id, note):
    """
    :param pub_id: publication submitted for review
    :param group_id: publication to be curated
    :param assignee_id: id of user assigned task
    :param note: message that will be sent to the assignee
    :return:
    """

    state = PubAssignment.ASSIGNED

    with geneweaverdb.PooledCursor() as cursor:
        cursor.execute(
            'UPDATE production.pub_assignments SET assignee=%s, assigner=%s, assignment_state=%s, notes=%s, updated=now() WHERE pub_id=%s AND curation_group=%s',
            (assignee_id, assigner_id, state, note, pub_id, group_id)
        )
        cursor.connection.commit()

    # Send notification to curator
    subject = "Publication Assigned To You For Review"
    message = "production.publication.pub_id: <i>" + get_pub_assignment_url(pub_id, group_id) + '</i><br>' + note
    notifications.send_usr_notification(assignee_id, subject, message)


def assignment_complete(pub_id, group_id, note):
    """
    :param geneset_id: geneset being curated
    :param note: message that will be sent to the assigned curator
    :return:
    """

    state = PubAssignment.READY_FOR_TEAM_REVIEW

    with geneweaverdb.PooledCursor() as cursor:
        cursor.execute(
            "UPDATE production.pub_assignments SET assignment_state=%s, notes=%s, updated=now() WHERE pub_id=%s AND curation_group=%s",
            (state, note, pub_id, group_id))
        cursor.connection.commit()

        cursor.execute(
            '''
            SELECT assigner
            FROM production.pub_assignments
            WHERE pub_id=%s AND curation_group=%s
            ''',
            (pub_id, group_id)
        )
        assignee_id = cursor.fetchone()[0]

    # Send notification to assigner
    subject = 'Publication Assignment Complete'
    message = "production.publication.pub_id: <i>" + get_pub_assignment_url(pub_id, group_id) + '</i><br>' + note
    notifications.send_usr_notification(assignee_id, subject, message)


def review_accepted(pub_id, group_id, note):
    """
    :param pub_id: publication being reviewed
    :param note: message that will be sent to the assigned reviewer
    :return:
    """

    state = PubAssignment.REVIEWED

    with geneweaverdb.PooledCursor() as cursor:
        cursor.execute(
            "UPDATE production.pub_assignments SET assignment_state=%s, notes=%s, updated=now() WHERE pub_id=%s AND curation_group=%s",
            (state, note, pub_id, group_id))
        cursor.connection.commit()

        cursor.execute(
            '''
            SELECT assignee
            FROM production.pub_assignments
            WHERE pub_id=%s AND curation_group=%s
            ''',
            (pub_id, group_id)
        )
        assignee_id = cursor.fetchone()[0]

    # Send notification to curator
    subject = 'Publication Assignment Accepted'
    message = "production.publication.pub_id: <i>" + get_pub_assignment_url(pub_id, group_id) + '</i><br>' + note
    notifications.send_usr_notification(assignee_id, subject, message)


def review_rejected(pub_id, group_id, note):
    """
    :param pub_id: geneset being curated
    :param note: message that will be sent to the assigned reviewer
    :return:
    """

    state = PubAssignment.ASSIGNED

    with geneweaverdb.PooledCursor() as cursor:
        cursor.execute(
            "UPDATE production.pub_assignments SET assignment_state=%s, notes=%s, updated=now() WHERE pub_id=%s AND curation_group=%s",
            (state, note, pub_id, group_id))
        cursor.connection.commit()

        cursor.execute(
            '''
            SELECT assignee
            FROM production.pub_assignments
            WHERE pub_id=%s AND curation_group=%s
            ''',
            (pub_id, group_id)
        )
        assignee_id = cursor.fetchone()[0]

    # Send notification to curator
    subject = 'Publication Assignment Rejected'
    message = "production.publication.pub_id: <i>" + get_pub_assignment_url(pub_id, group_id) + '</i><br>' + note
    notifications.send_usr_notification(assignee_id, subject, message)


def update_notes(pub_id, group_id, notes):
    with geneweaverdb.PooledCursor() as cursor:
        cursor.execute(
            "UPDATE production.pub_assignments SET notes=%s, updated=now() WHERE pub_id=%s AND curation_group=%s",
            (notes, pub_id, group_id))
        cursor.connection.commit()


def get_publication_assignment(pub_id, group_id):
    with geneweaverdb.PooledCursor() as cursor:

        cursor.execute("SELECT * FROM production.pub_assignments WHERE pub_id=%s AND curation_group=%s", (pub_id, group_id))

        assignments = list(geneweaverdb.dictify_cursor(cursor))
        if len(assignments) == 1:
            return PubAssignment(assignments[0])
        else:
            return None


def get_publication_assignment_by_id(pub_assign_id):
    """
    get a PubAssignment object from the database given a pub_assignment id
    :param pub_assign_id: id of Publication Assignment we want to retrive from
          the database
    :return: PubAssignment object
    """
    with geneweaverdb.PooledCursor() as cursor:
        cursor.execute("SELECT * FROM production.pub_assignments WHERE id=%s", (pub_assign_id,))
        assignments = list(geneweaverdb.dictify_cursor(cursor))

        return PubAssignment(assignments[0]) if len(assignments) == 1 else None


def create_geneset_stub_for_publication(pub_assign_id, name, label, description,
                                        species_id):
    """
    create a stub geneset for this publication.  a stub geneset is a record
    that only has the basic information filled out.  This will generate a new
    geneset curation assignment for the publication curator. They will finish
    filling out the geneset through the geneset curation workflow.

    :param pub_assign_id: ID of the publication assignment for which this
        geneset is being created
    :param name: name of new geneset
    :param label: figure label for new geneset
    :param description: description of geneset
    :return: ID of new geneset
    """

    geneset_id = None
    assignment = get_publication_assignment_by_id(pub_assign_id)

    if assignment:

        # default geneset as 'Private'
        # group id -1 signifies private
        gs_groups = '-1'
        #set initial curation level to 5 (private)
        cur_id = 5

        # right now, this can be set in the curation view.  should we
        # set this in the stub?
        gene_identifier = 0

        with geneweaverdb.PooledCursor() as cursor:
            file_id = uploadfiles.insert_new_contents_to_file("")
            cursor.execute('''INSERT INTO production.geneset (usr_id, file_id, gs_name, gs_abbreviation, pub_id, cur_id,
                              gs_description, sp_id, gs_count, gs_groups, gs_gene_id_type, gs_created, gs_status)
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s) RETURNING gs_id''',
                           (assignment.assignee, file_id, name, label,
                            assignment.pub_id, cur_id,
                            description, species_id, 0, gs_groups,
                            gene_identifier,
                            'delayed',))
            geneset_id = cursor.fetchone()[0]
            cursor.connection.commit()

        if geneset_id:
            curation_assignments.submit_geneset_for_curation(geneset_id, assignment.group, "", False)
            curation_assignments.assign_geneset_curator(geneset_id, assignment.assignee, assignment.assigner, "")
            insert_gs_to_pub_assignment(geneset_id, id)

    return geneset_id


def insert_gs_to_pub_assignment(gs_id, pub_assign_id):
    with geneweaverdb.PooledCursor() as cursor:
        cursor.execute('''INSERT INTO production.gs_to_pub_assignment (gs_id, pub_assign_id)
                          VALUES (%s, %s)''', (gs_id, pub_assign_id))
        cursor.connection.commit()


def get_genesets_for_assignment(pub_assign_id):
    gs_ids = []
    with geneweaverdb.PooledCursor() as cursor:
        cursor.execute("SELECT gs_id FROM production.gs_to_pub_assignment WHERE pub_assign_id=%s ORDER BY gs_id ASC", (pub_assign_id,))

        for row in geneweaverdb.dictify_cursor(cursor):
            gs_ids.append(row['gs_id'])

    return gs_ids


#
# Start of TEST program
#
def main():
    print("pub_assignments testing...")
    pub_id=1500
    group_id=136
    assignee=8446948
    assigner=8446948

    print("Queuing publication for review...")
    queue_publication(pub_id, group_id, "This publication should be reviewed for useful content for our group...")

    print("Assigning publication task...")
    assign_publication(pub_id, group_id, assignee, assigner, "Please review this publication for genesets.")

    print("Assignment Complete...")
    assignment_complete(pub_id, group_id, "Hey - I'm done with the assignment")

    print("Assignment rejected")
    review_rejected(pub_id, group_id, "Not quiet good enough.  Try again, please.")

    print("Assignment Reworked...")
    assignment_complete(pub_id, group_id, "Hey - Is this better?")

    print("Assignment Passed team review...")
    review_accepted(pub_id, group_id, "Nice work...")

if __name__ == "__main__": main()
