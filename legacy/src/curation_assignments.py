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
import psycopg2
import pub_assignments

__CORE_CURATION_GROUP = None


class CurationAssignment(object):

    UNASSIGNED = 1
    ASSIGNED = 2
    READY_FOR_REVIEW = 3
    REVIEWED = 4
    APPROVED = 5

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
        self._pub_assignment = None


    @property
    def reviewer(self):
        return self._reviewer

    @reviewer.setter
    def reviewer(self, value):
        self._reviewer = value
        if value and value != -1:
            user = geneweaverdb.get_user(value)
            if user.is_curator or user.is_admin:
                self.reviewer_tiers = [(3, "III"), (4, "IV"), (5, "V")]
            else:
                self.reviewer_tiers = [(4, "IV"), (5, "V")]

    @property
    def pub_assignment(self):
        if not self._pub_assignment:
            self._pub_assignment = pub_assignments.get_pub_assignment_from_geneset_id(self.gs_id)
        return self._pub_assignment

    def generic_message(self, previous_state=None):
        message = get_geneset_url(self.gs_id) + ' : <i>' + get_geneset_name(self.gs_id) + '</i><br>'
        message += "from Publication Assignment: " + self.pub_assignment.get_url()
        message += ': <i>' + self.pub_assignment.publication.title + '</i><br>'
        message +=  self.notes + '<br>' if self.notes else ''
        message += 'Previously state was "{}"'.format(previous_state) if previous_state else ''
        return message

    def status_to_string(self):

        state_dict = {
            CurationAssignment.UNASSIGNED:  "Unassigned",
            CurationAssignment.ASSIGNED:  "Assigned",
            CurationAssignment.READY_FOR_REVIEW: "Ready for review",
            CurationAssignment.REVIEWED:  "Reviewed"
        }

        try:
            return state_dict[self.state]
        except KeyError:
            return "Unknown"

    @staticmethod
    def string_to_status(string):
        s = string.lower()
        state_dict = {
            "unassigned": 1,
            "assigned": 2,
            "ready for review": 3,
            "reviewed": 4
        }

        try:
            return state_dict[s]
        except KeyError:
            raise ValueError("String status must be one of: 'Unassigned', 'Assigned', 'Ready for review', 'Reviewed'")

    def assign_curator(self, curator_id, reviewer_id, notes=''):
        """
        :param curator_id: id of user assigned as curator
        :param reviewer_id: id of user assigned as a reviewer
        :param notes: curation assignment notes
        :return:
        """

        previous_state = self.status_to_string()

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
        message = self.generic_message(previous_state=previous_state)
        notifications.send_usr_notification(curator_id, subject, message)

    def submit_for_review(self, notes):
        """
        :param notes: curation notes
        :return:
        """

        previous_state = self.status_to_string()
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
        message = get_geneset_url(self.gs_id) + ': <i>' + get_geneset_name(self.gs_id) + '</i><br>' + notes
        message = self.generic_message(previous_state=previous_state)
        notifications.send_usr_notification(self.reviewer, subject, message)

    def review_passed(self, notes, tier, submitter):
        """
        :param geneset_id: geneset being curated
        :param notes: message that will be sent to the assigned curator
        :param tier: curation tier for finalized geneset
        :return:
        """

        previous_state = self.status_to_string()
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
        geneset_url = get_geneset_url(self.gs_id)
        geneset_name = get_geneset_name(self.gs_id)
        message = geneset_url + ': <i>' + geneset_name + '</i><br>' + notes
        message = self.generic_message(previous_state=previous_state)
        notifications.send_usr_notification(self.curator, subject, message)

        if not (submitter.is_admin or submitter.is_curator):
            users = geneweaverdb.get_all_curators_admins()

            geneset_url = get_geneset_url(self.gs_id, 'reset_assignment_state=True')
            message = geneset_url + ': <i>' + geneset_name + '</i><br>'
            message += 'Clicking this link will set the curation state to \'Ready for review\' and will set you as the reviewer'
            subject = 'Tier IV Geneset Needs Additional Review by Geneweaver Curator/Admin'
            for user in users:
                notifications.send_usr_notification(user.user_id, subject, message)

    def review_failed(self, notes):
        """
        :param notes: curation notes, saved in curation_assignment and sent to curator
        :return:
        """

        previous_state = self.status_to_string()
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
        message = self.generic_message(previous_state=previous_state)
        notifications.send_usr_notification(self.curator, subject, message)

    def set_curation_state(self, state_string):
        state = self.string_to_status(state_string)

        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute(
                "UPDATE production.curation_assignments SET curation_state=%s, updated=now() WHERE gs_id=%s",
                (state, self.gs_id))
            cursor.connection.commit()

        self.state = state



def get_geneset_url(geneset_id, query=None):
    """
    :param geneset_id: geneset submitted for curation
    :param query optional query string to add to url link, automatically add ?
    :rtype: str
    """
    gs_id_str = str(geneset_id)
    u = '<a href="{url_prefix}/curategeneset/' + gs_id_str
    u = u + '?' + query if query else u
    u += '"> GS' + gs_id_str + '</a>'
    return u


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


def submit_geneset_for_curation(geneset_id, group_id, note, notify=True, delete_existing=True):
    """
    :param geneset_id: geneset submitted for curation
    :param group_id: group responsible for the curation
    :param note: message that will be sent to the group admins
    :return:
    """

    curation_state = CurationAssignment.UNASSIGNED
    with geneweaverdb.PooledCursor() as cursor:

        if delete_existing:
            cursor.execute(
                "DELETE FROM production.curation_assignments WHERE gs_id=%s",
                (geneset_id,))

        # Add a record to the table
        cursor.execute(
            "INSERT INTO production.curation_assignments (gs_id, curation_group, curation_state, notes) VALUES (%s, %s, %s, %s)",
            (geneset_id, group_id, curation_state, note))
        cursor.connection.commit()

        if notify:
            # send notification to the group admins
            subject = 'New Geneset Awaiting Curation'
            message = get_geneset_url(geneset_id) + ' : <i>' + get_geneset_name(geneset_id) + '</i><br>' + note
            notifications.send_group_admin_notification(group_id, subject, message)


def get_geneset_curation_assignment(geneset_id):

    with geneweaverdb.PooledCursor() as cursor:

        cursor.execute("SELECT * FROM production.curation_assignments WHERE gs_id=%s", (geneset_id,))

        assignments = list(geneweaverdb.dictify_cursor(cursor))
        if len(assignments) == 1:
            return CurationAssignment(assignments[0])
        else:
            return None


def nominate_public_gs(geneset_id, notes):
    """
    nominate a public geneset for curation by the GW core curation team
    will raise an exception if the geneset can't be assigned (for example,
    it might already be assigned for curation)
    :param geneset_id: geneset ID identifying the geneset that needs curation
    :param notes: notes from the submitter indicating why they feel the geneset
                  needs attention
    :return:
    """

    global __CORE_CURATION_GROUP

    if not __CORE_CURATION_GROUP:
        __CORE_CURATION_GROUP = geneweaverdb.get_curation_group()
        if not __CORE_CURATION_GROUP:
            raise Exception("GeneWeaverCurators group is not defined")

    assignment = get_geneset_curation_assignment(geneset_id)
    if assignment and assignment.state == assignment.REVIEWED:
        # if there is already a curation assignment record for this geneset it
        # is okay to delete it if the assigment has been reviewed (closed)
        delete_existing = True
    else:
        delete_existing = False


    try:
        submit_geneset_for_curation(geneset_id, __CORE_CURATION_GROUP.grp_id,
                                    notes, delete_existing=delete_existing)
    except psycopg2.IntegrityError:
        raise Exception("Geneset already assigned to curation group")

