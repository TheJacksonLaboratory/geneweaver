
from __future__ import print_function

import json
import smtplib
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import request
from HTMLParser import HTMLParser

import config
import geneweaverdb


def __strip_html_tags(html):
    class HTMLStripper(HTMLParser):
        def __init__(self):
            self.reset()
            self.fed = []

        def handle_data(self, d):
            self.fed.append(d)

        def get_data(self):
            return ''.join(self.fed)

    # first unescape html entities like $amp; (otherwise these get stripped too)
    html = HTMLParser().unescape(html)

    stripper = HTMLStripper()
    stripper.feed(html)
    return stripper.get_data()


def send_usr_notification(to, subject, message, to_is_email=False):
    """

    send a user a notification. notificatinos can be sent to a user id or an
    email address.

    TODO should we get rid of the optional 'to_is_email' and if the "to" param
    is an integer assume it is a user id, otherwise assume it is an email?

    :param to: user to send email notification to, can be user id or email
    :param subject: subject of notificatino
    :param message: body of notification
    :param to_is_email: boolean, if True "to" is a user's email address,
                  otherwise "to" is a user id
    :return:
    """

    if to_is_email:
        usr = geneweaverdb.get_user_byemail(to)
    else:
        usr = geneweaverdb.get_user(to)

    with geneweaverdb.PooledCursor() as cursor:
        cursor.execute("INSERT INTO production.notifications (usr_id, message, subject) "
                       "VALUES (%s, %s, %s)", (usr.user_id, message, subject))
        cursor.connection.commit()

    # if user wants to receive email notification, send that now
    user_prefs = json.loads(usr.prefs)

    if user_prefs.get('email_notification', False):
        send_email(usr.email, subject, message)


def send_group_admin_notification(group_id, subject, message):
    """

    send a notification to each admin of a group. users will recieve email
    in addition to in-app notification if they have enabled that option in their
    user preferences

    :param group_id: group id of the group we need to send an admin notification
    :param subject: subject of the notification (text)
    :param message: notification body (text)
    :return: None
    """

    for admin in geneweaverdb.get_group_admins(group_id):
        send_usr_notification(admin['usr_id'], subject, message)


def send_group_notification(group_id, subject, message):
    """

    send a notification to each memeber for a group. users will recieve email
    in addition to in-app notification if they have enabled that option

    :param group_id: group id of the group we need to send an admin notification
    :param subject: subject of the notification (text)
    :param message: notification body (text)
    :return: None
    """

    for user in geneweaverdb.get_group_users(group_id):
        send_usr_notification(user, subject, message)


def send_all_users_notification(subject, message):
    """

    send a notification to all gw users. users will recieve email
    in addition to in-app notification if they have enabled that option

    :param group_id: group id of the group we need to send an admin notification
    :param subject: subject of the notification (text)
    :param message: notification body (text)
    :return: None
    """

    for user in geneweaverdb.get_all_users():
	send_usr_notification(user['usr_id'], subject, message)


def send_email(to, subject, message):
    smtp_server = config.get('application', 'smtp')
    admin_email = config.get('application', 'admin_email')

    # notification message bodies may include URLs.  These are stored
    # as relative URLs, but with a Python format placeholder {url_prefix} that
    # can be used to turn them into absolute URLs before sending as email.
    # get the url_root from the flask request module, we will leave off the
    # trailing slash,  since the URL in the message will start with a slash
    url_prefix = request.url_root[:-1]
    message = message.format(url_prefix=url_prefix)

    msg = MIMEMultipart('alternative')
    msg['From'] = admin_email
    msg['To'] = to
    msg['Subject'] = subject

    # strip out html tags for plain text version
    # it would be nice to do something different with links rather than just
    # strip out the tags (replacing the link text with the url would be better)
    # I expect email clients to support the html version, so this isn't a big
    # deal
    text = __strip_html_tags(message)

    html = """\
    <html>
        <head></head>
        <body>
        <p><strong>{subject}:</strong></p>
        {msg}
        </body>
    </html>
    """.format(msg=message, subject=subject)

    part1 = MIMEText(text, 'plain')
    part2 = MIMEText(html, 'html')

    msg.attach(part1)
    msg.attach(part2)

    try:
        smtp = smtplib.SMTP(smtp_server)
        smtp.sendmail(admin_email, to, msg.as_string())
        smtp.quit()
    except Exception as e:
        print("Error sending email: {}".format(e), file=sys.stderr)


def mark_notifications_read(*ids):
    with geneweaverdb.PooledCursor() as cursor:
        # build the proper format string for the list of IDs
        format_string = ','.join(['%s'] * len(ids))
        cursor.execute("UPDATE production.notifications "
                       "SET read = True "
                       "WHERE notification_id IN (%s)" % format_string, ids)
        cursor.connection.commit()


def delete_notification(note_id):
    with geneweaverdb.PooledCursor() as cursor:
        cursor.execute("DELETE FROM production.notifications "
                       "WHERE notification_id = %s", (note_id,))
        cursor.connection.commit()


def get_notifications(usr_id, offset=0, limit=None):
    with geneweaverdb.PooledCursor() as cursor:
        cursor.execute("SELECT * FROM production.notifications "
                       "WHERE usr_id = %s ORDER BY time_sent DESC "
                       "OFFSET %s LIMIT %s", (usr_id, offset, limit))

        # notifications may include a format placeholder for an url_prefix
        # this is used when sending notifications via email, so that we can
        # include an absolute url (without storing that url in the database)
        # when displaying notifications in the application, we can use relative
        # urls,  so we go through and replace that placeholder with an empty
        # string before we return them for display in app
        notifications = []
        for notification in geneweaverdb.dictify_cursor(cursor):
            notification['message'] = notification['message'].format(url_prefix="")
            notifications.append(notification)
        return notifications


def get_unread_count(usr_id):
    with geneweaverdb.PooledCursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM production.notifications "
                       "WHERE read = FALSE AND usr_id = %s", (usr_id,))
        return cursor.fetchone()[0]

