import flask
import json
import uuid

import geneweaverdb as gwdb
import toolcommon as tc

TOOL_CLASSNAME = 'GeneSetViewer'
geneset_viewer_blueprint = flask.Blueprint(TOOL_CLASSNAME, __name__)


@geneset_viewer_blueprint.route('/run-geneset-viewer.html', methods=['POST'])
def run_tool():
    form = flask.request.form

    # pull out the selected geneset IDs
    selected_geneset_ids = tc.selected_geneset_ids(form)
    if len(selected_geneset_ids) < 2:
        # TODO add nice error message about missing genesets
        raise Exception('there must be at least two genesets selected to run this tool')

    # gather the params into a dictionary
    homology_str = 'Homology'
    params = {homology_str: None}
    for tool_param in gwdb.get_tool_params(TOOL_CLASSNAME, True):
        params[tool_param.name] = form[tool_param.name]
        if tool_param.name.endswith('_' + homology_str):
            params[homology_str] = form[tool_param.name]
    if params[homology_str] != 'Excluded':
        params[homology_str] = 'Included'

    # TODO include logic for "use emphasis" (see prepareRun2(...) in Analyze.php)

    # insert result for this run
    user_id = None
    if 'user_id' in flask.session:
        user_id = flask.session['user_id']
    else:
        # TODO add nice error message about missing user ID.
        raise Exception('internal error: user ID missing')

    task_id = str(uuid.uuid4())
    tool_name = gwdb.get_tool(TOOL_CLASSNAME).name
    desc = '{} on {} GeneSets'.format(tool_name, len(selected_geneset_ids))
    gwdb.insert_result(
        user_id,
        task_id,
        selected_geneset_ids,
        json.dumps(params),
        tool_name,
        desc,
        desc)

    tc.celery_app.send_task(
        tc.fully_qualified_name(TOOL_CLASSNAME),
        kwargs={
            'gsids': selected_geneset_ids,
            'output_prefix': task_id,
            'params': params,
        },
        task_id=task_id)

    #TODO redirect using task_id
    return "hi world"
