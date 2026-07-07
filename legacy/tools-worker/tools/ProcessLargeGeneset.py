import psycopg2
from celery import Task

from tools.celeryapp import celery
import tools.config as config
# TODO: Uncomment when logging is added to GW config
# import logging
# logger = logging.getLogger()


class LargeGenesetUpload(Task):
    name = "tools.LargeGenesetUpload.LargeGenesetUpload"

    def __init__(self):
        self.urlroot=''
        self._results = {}
        self._db = None
        self.gs_id = None
        self.user_id = None

    @property
    def db(self):
        """
        This will create a new DB connection when it is called if one does not
        already exist. Otherwise, the function returns the existing connection.
        DB connections are created per task, so no two tasks or tools can
        share a connection and run into potential problems.
        """

        if self._db and not self._db.closed:
            return self._db

        self._db = psycopg2.connect(
            database=config.get('db', 'database'),
            user=config.get('db', 'user'),
            password=config.get('db', 'password'),
            host=config.get('db', 'host'),
            port=config.get('db', 'port')
        )

        return self._db


    def database_query(self, query, args=None, fetch_result=False, raise_errors=True):
        """
        Setup, query, and tear down a PostgreSQL connection.
        :param query: well formated SQL query
        :param args: tuple of query arguments
        :param fetch_result: bool indicating if fetchone()[0] should be returned from cursor
        :param raise_errors: bool indicating if database errors should be raised out of the method
        :return: query result
        """
        cursor = self.db.cursor()
        conn = cursor.connection
        return_val = None
        set_search_path = "SET search_path TO production, odestatic, extsrc; "
        try:
            # set search path
            cursor.execute(set_search_path)
            # execute the query
            cursor.execute(query, args) if args else cursor.execute(query)
            # get result if needed
            return_val = cursor.fetchone()[0] if fetch_result else None

        except psycopg2.Error as e:
            # roll back any yuckiness, log the error
            conn.rollback()
            print('{0}: {1}'.format(e.diag.severity, e.diag.message_primary))
            # TODO: Uncomment when logging is added to GW config
            # logger.error('{0}: {1}'.format(e.diag.severity, e.diag.message_primary))
            if raise_errors:
                raise e

        finally:
            # commit any changes and tear down the connection
            conn.commit()
            conn.close()

        return return_val

    def send_user_notification(self, message, subject):
        self.database_query("INSERT INTO production.notifications (usr_id, message, subject) "
               "VALUES (%s, %s, %s)", (self.user_id, message, subject))

    @staticmethod
    def get_geneset_url(geneset_id):
        """
        :param geneset_id: geneset submitted for curation
        :param query optional query string to add to url link, automatically add ?
        :rtype: str
        """
        gs_id_str = str(geneset_id)
        u = '<a href="{url_prefix}/curategeneset/' + gs_id_str
        u += '"> GS' + gs_id_str + '</a>'
        return u

    def update_geneset_status(self, status):
        self.database_query('''UPDATE geneset SET gs_status=%s WHERE gs_id=%s''',
                            (status, self.gs_id),
                            raise_errors=False)

    def delete_geneset(self):
        self.update_geneset_status('deleted')
        deletion_message = 'GeneSet upload with id {} has been deleted. '.format(self.gs_id)
        deletion_message += 'No Genes in the GeneSet could be uploaded. Please try again and check that the ' \
                            'Identifier and Species, and that your genes exist and are valid.'
        deletion_subject = 'GeneSet Upload Deleted: No Valid Genes'
        self.send_user_notification(deletion_message, deletion_subject)

    def release_geneset(self):
        self.update_geneset_status('normal')
        success_message = self.get_geneset_url(self.gs_id) + " has finished processing and is now available for use."
        success_subject = "Geneset {} Finished Processing".format(self.gs_id)
        self.send_user_notification(success_message, success_subject)

    def mainexec(self):
        try:
            self.database_query("SELECT production.reparse_geneset_file(%s)", (self.gs_id,))
            self.database_query("SELECT production.process_thresholds(%s)", (self.gs_id,))
            num_genes = self.database_query('''SELECT count(*) FROM extsrc.geneset_value WHERE gs_id=%s''',
                                            (self.gs_id,),
                                            fetch_result=True)
            if num_genes < 1:
                self.delete_geneset()
            else:
                self.release_geneset()
        except psycopg2.Error:
            self.delete_geneset()


    def run(self, gs_id, user_id):
        self.user_id = user_id
        self.gs_id = gs_id
        self.mainexec()


PROCESSLARGEGENESET = celery.register_task(LargeGenesetUpload())
