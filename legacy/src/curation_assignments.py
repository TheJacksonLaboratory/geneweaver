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
#   gs_id bigint NOT NULL,                             -- geneset for curation (geneset.gs_id)
#   created timestamp without time zone DEFAULT now(), -- time the geneset was submitted for curation
#   updated timestamp without time zone DEFAULT now(), -- time of last modification of this record
#   curation_group integer NOT NULL,                   -- group assigned for curation (grp.grp_id)
#   curation_state integer NOT NULL,                   -- 1=unassigned, 2=assigned, 3=curated, 4=reviewed, 5=approved
#   curator integer DEFAULT '-1'::integer,             -- assigned curator (usr.usr_id)
#   reviewer integer DEFAULT '-1'::integer,            -- assigned reviewer (usr.usr_id)
#   notes character varying,                           --
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
#    3 - READY_FOR_REVIEW
#    4 - REVIEWED
#    5 - APPROVED
#

from __future__ import print_function
import geneweaverdb
import notifications


class CurationAssignment(object):

    UNASSIGNED = 1
    ASSIGNED = 2
    READY_FOR_REVIEW = 3
    REVIEWED = 4

    def __init__(self, row_dict):
        self.state = row_dict['curation_state']
        self.gs_id = row_dict['gs_id']
        self.curator = row_dict['curator']
        self.notes = row_dict['notes']
        self.group = row_dict['curation_group']
        self.created = row_dict['created']
        self.updated = row_dict['updated']
        self.reviewer_tiers = None
        self._reviewer = None

        self.reviewer = row_dict['reviewer']


    @property
    def reviewer(self):
        return self._reviewer

    @reviewer.setter
    def reviewer(self, value):
        self._reviewer = value
        if value and value != -1:
            print(value)
            user = geneweaverdb.get_user(value)
            if user.is_curator or user.is_admin:
                self.reviewer_tiers = [(3, "III"), (4, "IV"), (5, "V")]
            else:
                self.reviewer_tiers = [(4, "IV"), (5, "V")]

            print (self.reviewer_tiers)

    @reviewer.getter
    def reviewer(self):
        return self._reviewer

    @staticmethod
    def status_to_string(status):

        state_dict = {
            CurationAssignment.UNASSIGNED:  "Unassigned",
            CurationAssignment.ASSIGNED:  "Assigned",
            CurationAssignment.READY_FOR_REVIEW: "Ready for review",
            CurationAssignment.REVIEWED:  "Reviewed"
        }

        try:
            return state_dict[status]
        except KeyError:
            return "Unknown"

    def assign_curator(self, curator_id, reviewer_id, notes):
        """
        :param curator_id: id of user assigned as curator
        :param reviewer_id: id of user assigned as a reviewer
        :param notes: curation assignment notes
        :return:
        """

        state = CurationAssignment.ASSIGNED

        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute(
                "UPDATE production.curation_assignments SET curator=%s, reviewer=%s, curation_state=%s, notes=%s, updated=now() WHERE gs_id=%s",
                (curator_id, reviewer_id, state, notes, self.gs_id)
            )
            cursor.connection.commit()

        self.state = state
        self.notes = notes
        self.curator = curator_id
        self.reviewer = reviewer_id

        # Send notification to curator
        subject = 'Geneset Curation Assigned To You'
        message = get_geneset_url(self.gs_id) + ' : <i>' + get_geneset_name(self.gs_id) + '</i><br>' + notes
        notifications.send_usr_notification(curator_id, subject, message)

    def submit_for_review(self, notes):
        """
        :param notes: curation notes
        :return:
        """

        assert self.state == CurationAssignment.ASSIGNED

        curation_state = CurationAssignment.READY_FOR_REVIEW

        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute(
                "UPDATE production.curation_assignments SET curation_state=%s, notes=%s, updated=now() WHERE gs_id=%s",
                (curation_state, notes, self.gs_id))
            cursor.connection.commit()

        self.state = curation_state
        self.notes = notes

        # Send notification to reviewer
        subject = 'Geneset Curation Ready For Review'
        message = get_geneset_url(self.gs_id) + ': <i>' + get_geneset_name(self.gs_id) + '</i><br>' + note
        notifications.send_usr_notification(self.reviewer, subject, message)

    def review_passed(self, notes, tier):
        """
        :param geneset_id: geneset being curated
        :param notes: message that will be sent to the assigned curator
        :param tier: curation tier for finalized geneset
        :return:
        """

        assert self.state == CurationAssignment.READY_FOR_REVIEW

        curation_state = CurationAssignment.REVIEWED

        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute(
                "UPDATE production.curation_assignments SET curation_state=%s, notes=%s, updated=now() WHERE gs_id=%s",
                (curation_state, notes, self.gs_id))
            cursor.connection.commit()
            # update curation tier of geneset
            cursor.execute("UPDATE production.geneset SET cur_id=%s WHERE gs_id=%s", (tier, self.gs_id))
            cursor.connection.commit()

        self.state = curation_state
        self.notes = notes

        # Send notification to curator
        subject = 'Geneset Curation Review PASSED'
        message = get_geneset_url(self.gs_id) + ': <i>' + get_geneset_name(self.gs_id) + '</i><br>' + notes
        notifications.send_usr_notification(self.curator, subject, message)

    def review_failed(self, notes):
        """
        :param notes: curation notes, saved in curation_assignment and sent to curator
        :return:
        """

        assert self.state == CurationAssignment.READY_FOR_REVIEW

        curation_state = CurationAssignment.ASSIGNED

        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute(
                "UPDATE production.curation_assignments SET curation_state=%s, notes=%s, updated=now() WHERE gs_id=%s",
                (curation_state, notes, self.gs_id))
            cursor.connection.commit()

        self.state = curation_state
        self.notes = notes

        # Send notification to curator
        subject = 'Geneset Curation Review FAILED'
        message = get_geneset_url(self.gs_id) + ': <i>' + get_geneset_name(self.gs_id) + '</i><br>' + notes
        notifications.send_usr_notification(self.curator, subject, message)


def get_geneset_url(geneset_id):
    """
    :param geneset_id: geneset submitted for curation
    :rtype: str
    """
    #return flask.url_for('render_curategeneset', gs_id=geneset_id)
    #return '<a href="https://www.google.com/"> CLICK </a>'
    return '<a href="{url_prefix}/curategeneset/' + str(geneset_id) + '"> GS' + str(geneset_id) + '</a>'


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


def submit_geneset_for_curation(geneset_id, group_id, note, notify=True):
    """
    :param geneset_id: geneset submitted for curation
    :param group_id: group responsible for the curation
    :param note: message that will be sent to the group admins
    :return:
    """

    curation_state = CurationAssignment.UNASSIGNED
    with geneweaverdb.PooledCursor() as cursor:

        # JGP - for now delete the object to prevent exception on the INSERT...
        cursor.execute(
            "DELETE FROM production.curation_assignments WHERE gs_id=%s", (geneset_id,))

        # Add a record to the table
        cursor.execute(
            "INSERT INTO production.curation_assignments (gs_id, curation_group, curation_state, notes) VALUES (%s, %s, %s, %s)",
            (geneset_id, group_id, 1, note))
        cursor.connection.commit()

        if notify:
            # send notification to the group admins
            subject = 'New Geneset Awaiting Curation'
            message = get_geneset_url(geneset_id) + ' : <i>' + get_geneset_name(geneset_id) + '</i><br>' + note
            notifications.send_group_admin_notification(group_id, subject, message)
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

    print("Adding geneset to group...")
    submit_geneset_for_curation(geneset_id, group_id, "submission_note")

    assignment = get_geneset_curation_assignment(geneset_id)

    print("Assigning curator...")
    assignment.assign_curator(curator, reviewer, "assignment_note")

    print("Submit for review...")
    assignment.submit_for_review("ready_for_review_note")

    print("Failed team review...")
    assignment.review_failed("failed_review_note")

    #print("Passed team review...")

    #print(get_geneset_curation_assignment(geneset_id))

if __name__ == "__main__":
    main()
