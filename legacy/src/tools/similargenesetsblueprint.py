from decimal import Decimal
import json
import uuid
import config

import celery.states as states
import flask
from flask import request

import geneweaverdb as gwdb
import tools.toolcommon as tc


TOOL_CLASSNAME = 'SimilarGenesets'

similar_genesets_blueprint = flask.Blueprint(TOOL_CLASSNAME, __name__)

@similar_genesets_blueprint.route('/runSimilarGenesets.json', methods=['GET'])
def run_tool():
    """
    Runs a similarity analysis--calculates jaccard coefficients between the
    given gene set and all others in the database using a stored procedure.
    This is a minimal tool wrapper around a stored procedure:
    calculate_jaccard. It is implemented as a tool so 1) the application
    doesn't block as the procedure is running and 2) the user can navigate away
    from the view similar gene sets page without killing the procedure run
    early.
    Since this is just a minimal tool, it doesn't require status checking or
    redirecting to a results page on completion like all the other tools.

    args
        request.args['gs_id']: gene set ID
    """
    
    gs_id = request.args.get('gs_id')
    task_id = str(uuid.uuid4())
    tool = TOOL_CLASSNAME
    user_id = flask.session['user_id']
    desc = '{} on {}'.format(tool, 'GS' + str(gs_id))

    ## Uses the Jaccard Similarity entry in the tool table so that this tool
    ## doesn't require it's own tool row.
    gwdb.insert_result(
        user_id,
        task_id,
        [gs_id],
        json.dumps({}),
        'Jaccard Similarity',
        desc,
        desc
    )

    async_result = tc.celery_app.send_task(
        tc.fully_qualified_name(TOOL_CLASSNAME),
        kwargs={
            'gsids': [gs_id],
            'output_prefix': task_id,
            'params': {},
        },
        task_id=task_id
    )

    return flask.jsonify({'error': None})

