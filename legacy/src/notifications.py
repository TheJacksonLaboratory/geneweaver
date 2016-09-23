
from __future__ import print_function

import json
import smtplib
import sys
from email.mime.text import MIMEText

import config
import geneweaverdb


def send_usr_notification_by_id(uid, subject, message):
    send_usr_notification(uid, subject, message, False)


def send_usr_notification_by_email(user_email, subject, message):
    send_usr_notification(user_email, subject, message, True)


def send_usr_notification(to, subject, message, email=False):
    """

    :param to: user to send email notification to, can be user id or email
    :param subject: subject of notificatino
    :param message: body of notification
    :param email: boolean, if True "to" is a user's email address, otherwise
                  "to" is a user id
    :return:
    """

    if email:
        usr = geneweaverdb.get_user_byemail(to)
    else:
        usr = geneweaverdb.get_user(to)

    with geneweaverdb.PooledCursor() as cursor:
        cursor.execute("INSERT INTO production.notifications (usr_id, message, subject) VALUES (%s, %s, %s)", (usr.user_id, message, subject))
        cursor.connection.commit()

    # if user wants to receive email notification, send that now
    user_prefs = json.loads(usr.prefs)

    if user_prefs.get('email_notification', False):
        send_email(usr.email, subject, message)


def send_email(to, subject, message):
    smtp_server = config.get('application', 'smtp')
    admin_email = config.get('application', 'admin_email')

    msg = MIMEText(message)
    msg['From'] = admin_email
    msg['To'] = to
    msg['Subject'] = subject

    try:
        smtp = smtplib.SMTP(smtp_server)
        smtp.sendmail(admin_email, to, msg.as_string())
        smtp.quit()
    except smtplib.SMTPException as e:
        print("Error sending email: {}".format(e), file=sys.stderr)


def mark_notifications_read(*ids):
    with geneweaverdb.PooledCursor() as cursor:
        # build the proper format string for the list of IDs
        format_string = ','.join(['%s'] * len(ids))
        cursor.execute("UPDATE production.notifications SET read = True WHERE notification_id IN (%s)" % format_string, ids)
        cursor.connection.commit()


def delete_notification(note_id):
    with geneweaverdb.PooledCursor() as cursor:
        cursor.execute("DELETE FROM production.notifications WHERE notification_id = %s", (note_id,))
        cursor.connection.commit()


def get_notifications(usr_id, offset=0, limit=None):
    with geneweaverdb.PooledCursor() as cursor:
        cursor.execute("SELECT * FROM production.notifications WHERE usr_id = %s ORDER BY time_sent DESC OFFSET %s LIMIT %s", (usr_id, offset, limit))
        return list(geneweaverdb.dictify_cursor(cursor))


def get_unread_count(usr_id):
    with geneweaverdb.PooledCursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM production.notifications WHERE read = FALSE AND usr_id = %s", (usr_id,))
        return cursor.fetchone()[0]
