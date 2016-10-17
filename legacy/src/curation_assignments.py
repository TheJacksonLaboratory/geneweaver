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
#   object_id integer NOT NULL,
#   object_type integer NOT NULL,
#   updated timestamp without time zone DEFAULT now(),
#   curation_group integer NOT NULL,
#   curation_state integer NOT NULL,
#   curator integer DEFAULT '-1'::integer,
#   reviewer integer DEFAULT '-1'::integer,
#   notes character varying,
#   CONSTRAINT curation_assignments_pkey PRIMARY KEY (object_id, object_type)
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
# Curation Object Types
#    0 - undefined
#    1 - GENESET
#    2 - PUBLICATION
#
#

from __future__ import print_function

import json
import smtplib
import sys
from email.mime.text import MIMEText

import config
import geneweaverdb
import notifications


def submit_geneset_for_curation(geneset_id, group_id, note):
    """
    :param geneset_id: geneset submitted for curation
    :param group_id: group responsible for the curation
    :param note: message that will be sent to the group admins
    :return:
    """

    print("Adding geneset to group...")
    curation_type = 1
    curation_state = 1
    with geneweaverdb.PooledCursor() as cursor:

        # JGP - for now delete the object to prevent exception on the INSERT...
        cursor.execute(
            "DELETE FROM production.curation_assignments WHERE object_id=%s AND object_type=%s", (geneset_id, 1))

        # Add a record to the table
        log_entry = 'Geneset submitted for curation\n' + note
        cursor.execute(
            "INSERT INTO production.curation_assignments (object_id, object_type, curation_group, curation_state, notes) VALUES (%s, %s, %s, %s, %s)",
            (geneset_id, curation_type, group_id, 1, log_entry))
        cursor.connection.commit()

        # send notification to the group admins
        subject = 'Geneset added for curation'
        # JGP - need a meaningful message with link to geneset
        message = 'Geneset added for curation'
        #notifications.send_group_admin_notification(group_id, subject, message)
    return


def assign_geneset_curator(geneset_id, curator_id, reviewer_id, note):
    """
    :param geneset_id: geneset to be curated
    :param curator_id: id of user assigned as curator
    :param note: message that will be sent to the assigned curator
    :return:
    """

    print("Assigning curator...")
    curation_type = 1
    curation_state = 2
    with geneweaverdb.PooledCursor() as cursor:

        # JGP - need to append to existing "note"
        log_entry = 'Geneset assigned curator\n' + note
        cursor.execute(
            "UPDATE production.curation_assignments SET curator=%s, reviewer=%s, curation_state=%s, notes=%s, updated=now() WHERE object_id=%s AND object_type=%s",
            (curator_id, reviewer_id, curation_state, log_entry, geneset_id, curation_type))
        cursor.connection.commit()

        # Send notification to curator
        subject = 'Geneset curation assigned to you'
        # JGP - need a meaningful message with link to geneset
        message = 'Geneset curation assigned to you'
        sendEmail = False
        notifications.send_usr_notification(curator_id, subject, message, sendEmail)

    return


def submit_geneset_curation_for_review(geneset_id, note):
    print("Submit for review...")
    curation_type = 1
    curation_state = 3
    with geneweaverdb.PooledCursor() as cursor:

        # JGP - append to existing "note"
        log_entry = 'Curation submitted for review\n' + note
        cursor.execute(
            "UPDATE production.curation_assignments SET curation_state=%s, notes=%s, updated=now() WHERE object_id=%s AND object_type=%s",
            (curation_state, log_entry, geneset_id, curation_type))
        cursor.connection.commit()
        # JGP - send notification to reviewer

    return


def geneset_curation_review_passed(geneset_id, note):
    print("Passed team review...")
    curation_type = 1
    curation_state = 4
    with geneweaverdb.PooledCursor() as cursor:

        # JGP - append to existing "note"
        log_entry = 'Curation passed team review\n' + note
        cursor.execute(
            "UPDATE production.curation_assignments SET curation_state=%s, notes=%s, updated=now() WHERE object_id=%s AND object_type=%s",
            (curation_state, log_entry, geneset_id, curation_type))
        cursor.connection.commit()

        # JGP - send notification to ???
    return


def geneset_curation_review_failed(geneset_id, note):
    print("Passed team review...")
    curation_type = 1
    curation_state = 2
    with geneweaverdb.PooledCursor() as cursor:

        # JGP - append to existing "note"
        log_entry = 'Curation failed team review\n' + note
        cursor.execute(
            "UPDATE production.curation_assignments SET curation_state=%s, notes=%s, updated=now() WHERE object_id=%s AND object_type=%s",
            (curation_state, log_entry, geneset_id, curation_type))
        cursor.connection.commit()

        # JGP - send notification curator

    return


#
# Start of TEST program
#
def main():
    print("curation_assignments testing...")
    geneset_id=42
    group_id=136
    curator=8446948
    reviewer=8446948

    #submit_geneset_for_curation(geneset_id, group_id, "submission_note")
    #assign_geneset_curator(geneset_id, curator, reviewer, "assignment_note")
    #submit_geneset_curation_for_review(geneset_id, "ready_for_review_note")

if __name__ == "__main__": main()
