import celery.states as states
import flask
import json
import uuid

import geneweaverdb as gwdb
import toolcommon as tc

TOOL_CLASSNAME = 'GeneSetViewer'
geneset_viewer_blueprint = flask.Blueprint(TOOL_CLASSNAME, __name__)

@geneset_viewer_blueprint.route('/run-genesest-viewer.html', methods=['POST'])
def run_tool():
    # TODO need to check for read permissions on genesets

    form = flask.request.form

    # pull out the selected geneset IDs
    selected_geneset_ids = tc.selected_geneset_ids(form)
    if len(selected_geneset_ids) < 2:
        # TODO add nice error message about missing genesets
        flask.flash("Warning: You need at least 2 genes!")
        return flask.redirect('analyze.html')

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
    tool = gwdb.get_tool(TOOL_CLASSNAME)
    desc = '{} on {} GeneSets'.format(tool.name, len(selected_geneset_ids))
    gwdb.insert_result(
        user_id,
        task_id,
        selected_geneset_ids,
        json.dumps(params),
        tool.name,
        desc,
        desc)

    async_result = tc.celery_app.send_task(
        tc.fully_qualified_name(TOOL_CLASSNAME),
        kwargs={
            'gsids': selected_geneset_ids,
            'output_prefix': task_id,
            'params': params,
        },
        task_id=task_id)

    # render the status page and perform a 303 redirect to the
    # URL that uniquely identifies this run
    new_location = flask.url_for(TOOL_CLASSNAME + '.view_result', task_id=task_id)
    response = flask.make_response(tc.render_tool_pending(async_result, tool))
    response.status_code = 303
    response.headers['location'] = new_location

    return response
    
@geneset_viewer_blueprint.route('/run-genesest-viewer-api.html', methods=['POST'])  
def run_tool_api(apikey, homology, supressDisconnected, minDegree, genesets ):
    # TODO need to check for read permissions on genesets

    user_id = gwdb.get_user_id_by_apikey(apikey)
    

    # gather the params into a dictionary
    homology_str = 'Homology'
    params = {homology_str: None}
    
    for tool_param in gwdb.get_tool_params(TOOL_CLASSNAME, True):
        if tool_param.name.endswith('_' + 'SupressDisconnected'):
		    params[tool_param.name] = supressDisconnected
		    if supressDisconnected not in ['On','Off']:
				params[tool_param.name] = 'On'
        if tool_param.name.endswith('_' + 'MinDegree'):
		    params[tool_param.name] = minDegree
		    if minDegree not in ['Auto','1','2','3','4','5','10','20']:
		        params[tool_param.name] = 'Auto'
        if tool_param.name.endswith('_' + homology_str):
            params[homology_str] = 'Excluded'
            params[tool_param.name] = 'Excluded'
            if homology != 'Excluded':
                params[homology_str] = 'Included'
                params[tool_param.name] = 'Included'
    # TODO include logic for "use emphasis" (see prepareRun2(...) in Analyze.php)

    
    # pull out the selected geneset IDs
    selected_geneset_ids = genesets.split(":")
    if len(selected_geneset_ids) < 2:
        # TODO add nice error message about missing genesets
        raise Exception('there must be at least two genesets selected to run this tool')

    
    # insert result for this run

    task_id = str(uuid.uuid4())
    tool = gwdb.get_tool(TOOL_CLASSNAME)
    desc = '{} on {} GeneSets'.format(tool.name, len(selected_geneset_ids))
    gwdb.insert_result(
        user_id,
        task_id,
        selected_geneset_ids,
        json.dumps(params),
        tool.name,
        desc,
        desc)

    async_result = tc.celery_app.send_task(
        tc.fully_qualified_name(TOOL_CLASSNAME),
        kwargs={
            'gsids': selected_geneset_ids,
            'output_prefix': task_id,
            'params': params,
        },
        task_id=task_id)

    return task_id


@geneset_viewer_blueprint.route('/' + TOOL_CLASSNAME + '-result/<task_id>.html', methods=['GET', 'POST'])
def view_result(task_id):
    # TODO need to check for read permissions on task
    async_result = tc.celery_app.AsyncResult(task_id)
    tool = gwdb.get_tool(TOOL_CLASSNAME)

    if async_result.state in states.PROPAGATE_STATES:
        # TODO render a real descriptive error page not just an exception
        raise Exception('error while processing: ' + tool.name)
    elif async_result.state in states.READY_STATES:
        # results are ready. render the page for the user
        return flask.render_template(
            'tool/GeneSetViewer_result.html',
            async_result=async_result,
            tool=tool)
    else:
        # render a page telling their results are pending
        return tc.render_tool_pending(async_result, tool)


@geneset_viewer_blueprint.route('/' + TOOL_CLASSNAME + '-status/<task_id>.json')
def status_json(task_id):
    # TODO need to check for read permissions on task
    async_result = tc.celery_app.AsyncResult(task_id)

    return flask.jsonify({
        'isReady': async_result.state in states.READY_STATES,
        'state': async_result.state,
    })
