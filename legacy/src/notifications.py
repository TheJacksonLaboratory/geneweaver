
import geneweaverdb


def send_usr_notification(usr_id, subject, message):
    with geneweaverdb.PooledCursor() as cursor:
        cursor.execute("INSERT INTO production.notifications (usr_id, message, subject) VALUES (%s, %s)", (usr_id, message, subject))
        cursor.connection.commit()
        return


def mark_notifications_read(*ids):
    with geneweaverdb.PooledCursor() as cursor:
        # build the proper format string for the list of IDs
        format_string = ','.join(['%s'] * len(ids))
        cursor.execute("UPDATE production.notifications SET read = True WHERE notification_id IN (%s)" % format_string, ids)
        cursor.connection.commit()
        return


def delete_notification(note_id):
    with geneweaverdb.PooledCursor() as cursor:
        cursor.execute("DELETE FROM production.notifications WHERE notification_id = %s", (note_id,))
        cursor.connection.commit()
        return


def get_notifications(usr_id, offset=0, limit=None):
    with geneweaverdb.PooledCursor() as cursor:
        cursor.execute("SELECT * FROM production.notifications WHERE usr_id = %s ORDER BY time_sent DESC OFFSET %s LIMIT %s", (usr_id, offset, limit))
        return list(geneweaverdb.dictify_cursor(cursor))


def get_unread_count(usr_id):
    with geneweaverdb.PooledCursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM production.notifications WHERE read = FALSE AND usr_id = %s", (usr_id,))
        return cursor.fetchone()[0]
