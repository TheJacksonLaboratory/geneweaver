#
# The following SQL fragment defines the schema for the "curation_assignments" table.
#
# -- Table: production.curation_assignments
#
# -- DROP TABLE production.curation_assignments;
# -- SELECT * from production.curation_assignments
#
# CREATE TABLE production.curation_assignments
# (
#   gs_id bigint NOT NULL,
#   created timestamp without time zone DEFAULT now(),
#   updated timestamp without time zone DEFAULT now(),
#   curation_group integer NOT NULL,
#   curation_state integer NOT NULL,
#   curator integer DEFAULT '-1'::integer,
#   reviewer integer DEFAULT '-1'::integer,
#   notes character varying,
#   CONSTRAINT curation_assignments_pkey PRIMARY KEY (gs_id)
# )
#
#  WITH (
#   OIDS=FALSE
# );
# ALTER TABLE production.curation_assignments
#   OWNER TO postgres;
#
#
#  Curation States:
#    0 - undefined
#    1 - UNASSIGNED
#    2 - ASSIGNED
#    3 - READY_FOR_TEAM_REVIEW
#    4 - REVIEWED
#    5 - APPROVED
#

from __future__ import print_function
import geneweaverdb
import notifications


class CurationAssignment(object):

    UNASSIGNED = 1
    ASSIGNED = 2
    READY_FOR_TEAM_REVIEW = 3
    REVIEWED = 4

    def __init__(self, row_dict):
        self.state = row_dict['curation_state']
        self.gs_id = row_dict['gs_id']
        self.curator = row_dict['curator']
        self.reviewer = row_dict['reviewer']
        self.notes = row_dict['notes']
        self.group = row_dict['curation_group']
        self.created = row_dict['created']
        self.updated = row_dict['updated']

    @staticmethod
    def status_to_string(status):
        if (status == CurationAssignment.UNASSIGNED):
            return "Unassigned"
        elif (status == CurationAssignment.ASSIGNED):
            return "Assigned"
        elif (status == CurationAssignment.READY_FOR_TEAM_REVIEW):
            return "Ready for team review"
        elif (status == CurationAssignment.UNASSIGNED):
            return "Reviewed"


def get_geneset_url(geneset_id):
    """
    :param geneset_id: geneset submitted for curation
    :rtype: str
    """
    #return flask.url_for('render_curategeneset', gs_id=geneset_id)
    #return '<a href="https://www.google.com/"> CLICK </a>'
    return '<a href="/curategeneset/' + str(geneset_id) + '"> GS' + str(geneset_id) + '</a>'


def get_geneset_name(geneset_id):
    """
    :param geneset_id: geneset to fetch name of
    :rtype: string
    """

    with geneweaverdb.PooledCursor() as cursor:

        cursor.execute(
            '''
            SELECT gs_name
            FROM production.geneset
            WHERE gs_id=%s
            ''',
            (geneset_id,)
        )
        geneset_name = cursor.fetchone()[0]

    return geneset_name


def submit_geneset_for_curation(geneset_id, group_id, note):
    """
    :param geneset_id: geneset submitted for curation
    :param group_id: group responsible for the curation
    :param note: message that will be sent to the group admins
    :return:
    """

    print("Adding geneset to group...")
    curation_state = 1
    with geneweaverdb.PooledCursor() as cursor:

        # JGP - for now delete the object to prevent exception on the INSERT...
        cursor.execute(
            "DELETE FROM production.curation_assignments WHERE gs_id=%s", (geneset_id,))

        # Add a record to the table
        #log_entry = 'Geneset submitted for curation\n' + note
        cursor.execute(
            "INSERT INTO production.curation_assignments (gs_id, curation_group, curation_state, notes) VALUES (%s, %s, %s, %s)",
            (geneset_id, group_id, 1, note))
        cursor.connection.commit()

        # send notification to the group admins
        subject = 'New Geneset Awaiting Curation'
        message = get_geneset_url(geneset_id) + ' : <i>' + get_geneset_name(geneset_id) + '</i><br>' + note
        notifications.send_group_admin_notification(group_id, subject, message)
    return


def assign_geneset_curator(geneset_id, curator_id, reviewer_id, note):
    """
    :param geneset_id: geneset to be curated
    :param curator_id: id of user assigned as curator
    :param note: message that will be sent to the assigned curator
    :return:
    """

    print("Assigning curator...")
    curation_state = 2

    with geneweaverdb.PooledCursor() as cursor:
        #log_entry = 'Geneset assigned curator: \n' + note
        cursor.execute(
            "UPDATE production.curation_assignments SET curator=%s, reviewer=%s, curation_state=%s, notes=%s, updated=now() WHERE gs_id=%s",
            (curator_id, reviewer_id, curation_state, note, geneset_id)
        )
        cursor.connection.commit()

    # Send notification to curator
    subject = 'Geneset Curation Assigned To You'
    message = get_geneset_url(geneset_id) + ' : <i>' + get_geneset_name(geneset_id) + '</i><br>' + note
    notifications.send_usr_notification(curator_id, subject, message)
    return


def submit_geneset_curation_for_review(geneset_id, note):
    """
    :param geneset_id: geneset being curated
    :param note: message that will be sent to the assigned curator
    :return:
    """

    print("Submit for review...")
    curation_state = 3

    with geneweaverdb.PooledCursor() as cursor:
        #log_entry = 'Curation submitted for review: \n' + note
        cursor.execute(
            "UPDATE production.curation_assignments SET curation_state=%s, notes=%s, updated=now() WHERE gs_id=%s",
            (curation_state, note, geneset_id))
        cursor.connection.commit()

        cursor.execute(
            '''
            SELECT reviewer
            FROM production.curation_assignments
            WHERE gs_id=%s
            ''',
            (geneset_id,)
        )
        reviewer_id = cursor.fetchone()[0]

    # Send notification to reviewer
    subject = 'Geneset Curation Ready For Review'
    message = get_geneset_url(geneset_id) + ': <i>' + get_geneset_name(geneset_id) + '</i><br>' + note
    notifications.send_usr_notification(reviewer_id, subject, message)
    return


def geneset_curation_review_passed(geneset_id, note):
    """
    :param geneset_id: geneset being curated
    :param note: message that will be sent to the assigned curator
    :return:
    """

    print("Passed team review...")
    curation_state = 4

    with geneweaverdb.PooledCursor() as cursor:
        #log_entry = 'Curation passed team review: \n' + note
        cursor.execute(
            "UPDATE production.curation_assignments SET curation_state=%s, notes=%s, updated=now() WHERE gs_id=%s",
            (curation_state, note, geneset_id))
        cursor.connection.commit()

        cursor.execute(
            '''
            SELECT curator
            FROM production.curation_assignments
            WHERE gs_id=%s
            ''',
            (geneset_id,)
        )
        curator_id = cursor.fetchone()[0]

    # Send notification to curator
    subject = 'Geneset Curation Review PASSED'
    message = get_geneset_url(geneset_id) + ': <i>' + get_geneset_name(geneset_id) + '</i><br>' + note
    notifications.send_usr_notification(curator_id, subject, message)

    return


def geneset_curation_review_failed(geneset_id, note):
    """
    :param geneset_id: geneset being curated
    :param note: message that will be sent to the assigned curator
    :return:
    """

    print("Failed team review...")
    curation_type = 1
    curation_state = 2
    geneset_name = get_geneset_name(geneset_id)

    with geneweaverdb.PooledCursor() as cursor:
        #log_entry = 'Curation failed team review: \n' + note
        cursor.execute(
            "UPDATE production.curation_assignments SET curation_state=%s, notes=%s, updated=now() WHERE gs_id=%s",
            (curation_state, note, geneset_id))
        cursor.connection.commit()

        cursor.execute(
            '''
            SELECT curator
            FROM production.curation_assignments
            WHERE gs_id=%s
            ''',
            (geneset_id,)
        )
        curator_id = cursor.fetchone()[0]

    # Send notification to curator
    subject = 'Geneset Curation Review FAILED'
    message = get_geneset_url(geneset_id) + ': <i>' + get_geneset_name(geneset_id) + '</i><br>' + note
    notifications.send_usr_notification(curator_id, subject, message)

    return


def get_geneset_curation_assignment(geneset_id):

    with geneweaverdb.PooledCursor() as cursor:

        cursor.execute("SELECT * FROM production.curation_assignments WHERE gs_id=%s", (geneset_id,))

        assignments = list(geneweaverdb.dictify_cursor(cursor))
        if len(assignments) == 1:
            return CurationAssignment(assignments[0])
        else:
            return None

#
# Start of TEST program
#
def main():
    print("curation_assignments testing...")
    geneset_id=248306
    group_id=136
    curator=8446948
    reviewer=8446948

    submit_geneset_for_curation(geneset_id, group_id, "submission_note")
    assign_geneset_curator(geneset_id, curator, reviewer, "assignment_note")
    submit_geneset_curation_for_review(geneset_id, "ready_for_review_note")
    geneset_curation_review_failed(geneset_id, "failed_review_note")

    #print(get_geneset_curation_assignment(geneset_id))

if __name__ == "__main__": main()
