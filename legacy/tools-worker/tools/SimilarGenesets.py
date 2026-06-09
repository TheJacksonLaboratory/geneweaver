#!/usr/bin/env python

## file: SimilarGenesets.py
## desc: The view similar gene sets function implemented as a tool. Lets a user
##       find all gene sets in the DB that are similar to a single set of
##       interest. Implemented as a tool so the calculate_jaccard stored
##       procedure, which can take up to 15 minutes, doesn't block the 
##       application and allows the user to navigate away from the view similar
##       gene sets page.
## vers: 0.1.0
## auth: TR

import tools.toolbase
from tools.celeryapp import celery


class SimilarGenesets(tools.toolbase.GeneWeaverToolBase):

    name = "tools.SimilarGenesets.SimilarGenesets"

    def __init__(self, *arguments, **kwarguments):
        """
        Calls the initialization function for the base class in toolbase.py
        """

        self.init("SimilarGenesets")
        self.urlroot=''


    def _run_calculate_jaccard(self, gs_id):
        """
        Runs the calculate_jaccard stored procedure for the given gene set ID.
        This stored procedure will calculate jaccard coefficients between the
        given gene set and all other sets in the DB.

        arguments
            gs_id: gene set ID
        """

        cursor = self.db.cursor()

        cursor.execute(
            '''
            SELECT calculate_jaccard(%s);
            ''',
                (gs_id,)
        )

        cursor.close()


    def _update_geneset_jaccard_start(self, gs_id):
        """
        Updates the jaccard start time for the given gene set ID.

        arguments
            gs_id: gene set ID
        """

        cursor = self.db.cursor()

        cursor.execute(
            '''
            UPDATE  production.geneset_info
            SET     gsi_jac_started = NOW()
            WHERE   gs_id = %s;
            ''',
                (gs_id,)
        )

        cursor.connection.commit()
        cursor.close()


    def _update_geneset_jaccard_complete(self, gs_id):
        """
        Updates the jaccard completed time for the given gene set ID.

        arguments
            gs_id: gene set ID
        """

        cursor = self.db.cursor()

        cursor.execute(
            '''
            UPDATE  production.geneset_info
            SET     gsi_jac_completed = NOW()
            WHERE   gs_id = %s;
            ''',
                (gs_id,)
        )

        cursor.connection.commit()
        cursor.close()

    def _clear_jaccard_times(self, gs_id):
        """
        Removes the Jaccard started and completed times from the geneset_info
        table.

        arguments
            gs_id: gene set ID
        """

        cursor = self.db.cursor()

        cursor.execute(
            '''
            UPDATE  production.geneset_info
            SET     gsi_jac_started = NULL,
                    gsi_jac_completed = NULL
            WHERE   gs_id = %s;
            ''',
                (gs_id,)
        )

        cursor.connection.commit()
        cursor.close()

    def _clear_jaccard_cache(self, gs_id):
        """
        Delete Jaccard cache entries for this gene set otherwise we may run
        into duplicate key constraint errors.

        arguments
            gs_id: gene set ID
        """

        cursor = self.db.cursor()

        cursor.execute(
            '''
            DELETE
            FROM   extsrc.geneset_jaccard
            WHERE  gs_id_left = %s OR
                   gs_id_right = %s;
            ''',
                (gs_id, gs_id)
        )

        cursor.connection.commit()
        cursor.close()


    def mainexec(self, gsid=None):

        if not gsid:
            gs_id = self._gsids[0]
        else:
            gs_id = gsid

        ## These are cleared in case we're refreshing the cache. The
        ## application UI will display a message to the user based on these 
        ## times so we want to ensure that the appropriate message is 
        ## displayed.
        self._clear_jaccard_times(gs_id)

        ## The application wil use this time to inform the user about the
        ## similarity tool
        self._update_geneset_jaccard_start(gs_id)

        ## Prevent duplicate key errors
        self._clear_jaccard_cache(gs_id)

        ## Calculate all Jaccard coefficients between this set and all others
        self._run_calculate_jaccard(gs_id)

        ## Done, set the time to inform the user
        self._update_geneset_jaccard_complete(gs_id)

SimilarGenesets = celery.register_task(SimilarGenesets())

